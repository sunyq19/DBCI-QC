"""Report integration contracts; detector performance is outside these tests."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from server import Store
from ephys_qc.report_view import build_report_view, render_report_view
from ephys_qc.modules.m09 import render_report


class ReportViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.jid = 'a' * 32
        self.job = self.root / 'jobs' / self.jid
        self.artifacts = self.job / 'artifacts'
        self.artifacts.mkdir(parents=True)
        obs = dict(channel_id='a', channel_index=0, channel_name='A', status='computed',
                   start_sample=0, stop_sample=400, start_seconds=0, stop_seconds=4,
                   amplitude_uv=2, peak_frequency_hz=50, flagged=True)
        rows = [obs, {**obs, 'flagged':False, 'start_sample':400,'stop_sample':800},
                {**obs,'channel_id':'b','channel_name':'B','flagged':False}]
        hf = dict(channel_id='a',channel_name='A',start_seconds=1,stop_seconds=3,peak_z_score=5)
        payloads = {
            'M03_continuity.json': {'measurements':[dict(channel_id=cid,channel_name=cid.upper(),finite_sample_count=100,nonfinite_sample_count=0,
                constant_sample_count=0,finite_outside_constant_sample_count=100) for cid in ("a","b")]},
            'M04_spectral.json': {'line_noise':{'observations':rows},'psd':{'channel_ids':['a','b']}},
            'M05_bad_channels.json': {'groups':[],'channels':[{},{}]},
            'M06_muscle.json': {'status':'ok','channels':[dict(channel_id='a',channel_name='A',status='ok',valid_seconds=10,candidate_seconds=2),
                dict(channel_id='b',channel_name='B',status='ok',valid_seconds=10,candidate_seconds=0)], 'candidates':[hf]},
        }
        for name, data in payloads.items():
            (self.artifacts / name).write_text(json.dumps(data))
        (self.artifacts / 'report.html').write_text('<html>original frozen report</html>')
        self.result = dict(analysis_profile='scalp-eeg/1',scope='window',score={'value':None},
            recording=dict(channel_count=2,sampling_rate_hz=100,start_seconds=0,duration_seconds=10),
            input_metadata=dict(format='EDF',duration_seconds=20),
            modules=[dict(id=mid,status='completed',summary={},reason='') for mid in ('M03','M04','M05','M06')],
            artifacts=[{'name':name} for name in [*payloads,'report.html']],warnings=[])

    def view(self):
        return build_report_view(self.result,self.artifacts,'<script>filename</script>')

    def test_new_report_and_served_historical_view_agree_without_rewriting_evidence(self):
        (self.job / 'result.json').write_text(json.dumps(self.result))
        original = {p:p.read_bytes() for p in self.job.rglob('*') if p.is_file()}
        store = Store.__new__(Store)
        store.root, store.lock, store.report_views = self.root, threading.RLock(), {}
        store.jobs = {self.jid:dict(id=self.jid,status='completed',label='example')}
        response = store.result(self.jid)
        self.assertAlmostEqual(response['report_view']['score']['value'],100*(1-math.sqrt(.5**2/2)))
        self.assertIsNone(response['score']['value'])
        self.assertEqual(store.result(self.jid)['report_view'],response['report_view'])
        for path, raw in original.items():
            self.assertEqual(path.read_bytes(),raw)
        new = copy.deepcopy(self.result)
        render_report(new,'example',self.artifacts / 'new-report.html')
        self.assertEqual(new['report_view']['score'],response['report_view']['score'])
        self.assertIn('64.64',(self.artifacts / 'new-report.html').read_text())

    def test_missing_or_failed_evidence_never_produces_a_total(self):
        for change in ('failed','undeclared','missing'):
            with self.subTest(change=change):
                row=copy.deepcopy(self.result)
                if change=='failed':row['modules'][1]['status']='failed'
                if change=='undeclared':row['artifacts']=[a for a in row['artifacts'] if a['name']!='M04_spectral.json']
                if change=='missing':(self.artifacts/'M04_spectral.json').unlink()
                v=build_report_view(row,self.artifacts)
                self.assertIsNone(v['score']['value'])
                self.assertIsNone(v['score']['components'][1]['value'])
                if change=='failed':self.assertEqual(v['failures'],['M04'])

    def test_other_modalities_and_whole_records_keep_existing_report_path(self):
        for field,value in [('analysis_profile','ecog/1'),('scope','recording')]:
            row=copy.deepcopy(self.result);row[field]=value
            self.assertIsNone(build_report_view(row,self.artifacts))

    def test_html_escapes_input_and_keeps_candidate_locations_and_trial_label(self):
        report=render_report_view(self.view())
        self.assertNotIn('<script>filename',report)
        self.assertIn('&lt;script&gt;filename',report)
        self.assertIn('1.00–3.00',report)
        self.assertIn('项目试行 v0.2',report)
        self.assertIn('href="M06_muscle.json"',report)

    def test_symlink_evidence_cannot_escape_artifact_directory(self):
        path=self.artifacts/'M04_spectral.json'
        external=self.root/'external.json';external.write_bytes(path.read_bytes())
        path.unlink();path.symlink_to(external)
        v=self.view()
        self.assertIsNone(v['score']['value'])
        self.assertEqual(v['evidence_errors'],['M04：证据路径不可用'])


if __name__ == '__main__':
    unittest.main()
