"""Retention must remove owned copies, preserve reports and never follow originals."""
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from intake import IntakeStore, _save
from upload_retention import expire_uploads
from saved_reports import served_report, artifact_names
from server import Store, Handler
from types import SimpleNamespace
from test_intake import recording, confirmation


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.store = IntakeStore(self.root/'runtime')
        self.original = self.root/'my-original.edf'; self.original.write_bytes(recording())
        data = self.original.read_bytes()
        self.intake = self.store.receive(self.original.name, len(data), io.BytesIO(data))
        self.directory = self.store.root/self.intake['id']
        self.record = self.store.confirm(self.intake['id'], confirmation())
        self.deadline = datetime.fromisoformat(self.intake['retention']['expires_at'])
        self.report = self.root/'runtime/jobs/saved/artifacts/report.html'; self.report.parent.mkdir(parents=True)
        self.report.write_text('saved evidence')

    def test_seven_day_boundary_preserves_report_and_original_and_receipts(self):
        received = datetime.fromisoformat(self.intake['received_at'])
        self.assertEqual(self.deadline - received, timedelta(days=7))
        self.assertEqual(self.record['library_origin'], 'user_upload')
        self.assertEqual(expire_uploads(self.store, at=self.deadline-timedelta(seconds=1)), [])
        self.assertTrue(Path(self.record['source_path']).exists())
        rows = expire_uploads(self.store, at=self.deadline)
        self.assertEqual(len(rows), 1)
        self.assertFalse(Path(self.record['source_path']).exists())
        self.assertEqual(self.original.read_bytes(), recording())
        self.assertEqual(self.report.read_text(), 'saved evidence')
        self.assertEqual({p.name for p in self.directory.iterdir()}, {'intake.json', 'confirmation.json', 'record.json'})
        self.assertEqual(self.store.registered()[0]['retention']['state'], 'expired')
        with self.assertRaisesRegex(ValueError, '到期'): self.store._verified_source(self.store.get(self.intake['id']))
        self.assertEqual(expire_uploads(self.store, at=self.deadline), [])

    def test_active_family_is_protected_then_expires(self):
        family = self.record['record_family']
        self.assertEqual(expire_uploads(self.store, protected_families={family}, at=self.deadline), [])
        self.assertTrue(Path(self.record['source_path']).exists())
        self.assertEqual(len(expire_uploads(self.store, at=self.deadline)), 1)

    def test_legacy_and_linked_records_are_not_deleted(self):
        receipt = self.store.get(self.intake['id'])
        receipt.pop('library_origin'); _save(self.directory/'intake.json', receipt)
        self.assertEqual(expire_uploads(self.store, at=self.deadline), [])
        receipt['library_origin'] = 'user_upload'; receipt['linked_root'] = str(self.root)
        _save(self.directory/'intake.json', receipt)
        self.assertEqual(expire_uploads(self.store, at=self.deadline), [])
        self.assertTrue(Path(self.record['source_path']).exists())

    def test_symlink_payload_cannot_delete_external_original(self):
        source = Path(self.record['source_path']); source.unlink(); source.symlink_to(self.original)
        expire_uploads(self.store, at=self.deadline)
        self.assertFalse(source.is_symlink()); self.assertEqual(self.original.read_bytes(), recording())

    def test_pending_upload_expires_and_does_not_reappear_for_confirmation(self):
        intake = self.store.get(self.intake['id']); intake['status'] = 'needs_confirmation'
        _save(self.directory/'intake.json', intake)
        expire_uploads(self.store, at=self.deadline)
        self.assertEqual(self.store.pending(), [])


class SavedReportTests(unittest.TestCase):
    def test_report_open_never_rebuilds_score_and_keeps_dataset_return_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); jid = 'a'*32; artifacts = root/'jobs'/jid/'artifacts'; artifacts.mkdir(parents=True)
            html = '<html><head></head><body><main>frozen result<img src="waveform.png"><a href="M03.json">Evidence</a></main></body></html>'
            file = artifacts/'report.html'; file.write_text(html)
            job = dict(id=jid, status='completed', dataset_context={'package_id':'example-seeg'})
            store = SimpleNamespace(root=root, job=lambda ident:job, result=lambda *a,**kw: self.fail('Recomputed scores'))
            rendered = served_report(store, jid)
            self.assertIn('/api/v1/packages/example-seeg/overview/report', rendered)
            self.assertIn(f'/api/v1/jobs/{jid}/artifacts/waveform.png', rendered)
            self.assertIn('返回数据集报告', rendered)
            self.assertEqual(file.read_text(), html)
            # The exact handler users click has the same no-recompute guarantee.
            handler = Handler.__new__(Handler); handler.server = SimpleNamespace(store=store)
            handler.path = f'/api/v1/jobs/{jid}/report'; output=[]
            handler.send_bytes=lambda data,*a,**kw:output.append(data)
            handler.get(handler.path)
            self.assertIn('返回数据集报告'.encode(), output[0])

    def test_descriptive_report_uses_saved_measurements_without_a_quality_score(self):
        from descriptive_report import render
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); jid='c'*32; folder=root/'jobs'/jid; artifacts=folder/'artifacts'; artifacts.mkdir(parents=True)
            item={'id':'r','label':'A <sample>','modality':'seeg','metadata':{'format':'FIF','duration_seconds':10,'channels':[{'index':0,'sampling_rate_hz':100}]}}
            job={'id':jid,'status':'completed','plan':{'qc_config':{'selection':{'eeg_indices':[0]}}}}
            (folder/'request.json').write_text(json.dumps({'input':item}))
            (artifacts/'coverage.json').write_text(json.dumps({'total_seconds':10,'completed_seconds':10,'unexecuted_seconds':0,'gap_seconds':0}))
            modules=[{'id':'M03','summary':{'nonfinite_sample_count':5,'candidate_details_truncated':True}}, {'id':'M04','summary':{'psd_computed_channel_count':1}}, {'id':'M05','summary':{'described_channel_count':1}}]
            (artifacts/'window-results.json').write_text(json.dumps([{'id':'w000001','start_seconds':0,'duration_seconds':10,'status':'partial','modules':modules}]))
            store=SimpleNamespace(root=root,job=lambda ident:job)
            html=render(store,jid)
            self.assertIn('5 个非有限值',html); self.assertIn('A &lt;sample&gt;',html)
            self.assertIn('保存上限',html); self.assertNotIn('0.00%',html)
            self.assertNotIn('EEG 基础质控评分',html)
            self.assertIn('10 s',html)

    def test_artifact_allowlist_is_independent_of_report_calculation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); jid='b'*32; folder=root/'jobs'/jid;folder.mkdir(parents=True)
            p=folder/'result.json';p.write_text(json.dumps({'candidate_index':[{'x':1}]*1000,'artifacts':[{'name':'waveform.png'}]}))
            store=SimpleNamespace(root=root,job=lambda ident:{'status':'completed'})
            self.assertEqual(artifact_names(store,jid),{'waveform.png'})
            with patch('ijson.items',side_effect=AssertionError('Should use saved manifest')):
                self.assertEqual(artifact_names(store,jid),{'waveform.png'})
            p.write_text(json.dumps({'artifacts':[{'name':'new.png'}]}))
            self.assertEqual(artifact_names(store,jid),{'new.png'})

if __name__ == '__main__': unittest.main()
