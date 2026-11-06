"""Dataset-to-record navigation must preserve sources, identity and history."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]
import test_dataset_consistency as fixtures
from server import Store, public_input
from intake import IntakeStore
from package_jobs import fingerprint


class LinkedRecordTests(unittest.TestCase):
    freeze=fixtures.DatasetTests.freeze

    def setUp(self):
        fixtures.DatasetTests.setUp(self)
        self.config=self.base/'plan.json';self.config.write_text(json.dumps(self.plan))
        self.settings={'data_dir':str(self.base/'runtime'),'python':sys.executable,'inputs':[],'profiles':[],
                       'packages':[dict(id='pilot',label='Pilot',root=str(self.root),expectations=str(self.config))]}
        with patch('threading.Thread.start'):self.store=Store(self.settings)
        self.r=self.plan['consistency']['records'][0]
        self.body=dict(package_id='pilot',record_id=self.r['id'],manifest_hash=fingerprint(self.plan))
        self.confirmation={'modality':'scalp_eeg','eeg_indices':[0],'reference_indices':{},'reference_scheme':'unknown','confirmed':True}

    def test_link_confirm_reopen_without_upload_or_duplicate_input(self):
        before=hashlib.sha256((self.root/self.r['path']).read_bytes()).hexdigest()
        intake=self.store.open_package_record(self.body)
        directory=self.store.intakes.root/intake['id']
        self.assertEqual([p.name for p in directory.iterdir()],['intake.json'])
        self.assertEqual(intake['dataset_context']['subject'],'sub-01')
        record=self.store.confirm_intake(intake['id'],self.confirmation)['input']
        stored=self.store.inputs[record['id']]
        self.assertEqual(Path(stored['source_path']),self.root/self.r['path'])
        self.assertEqual(record['dataset_id'],'package-pilot')
        self.assertEqual(record['dataset_context']['manifest_hash'],self.body['manifest_hash'])
        self.assertEqual(self.store.open_package_record(self.body)['id'],intake['id'])
        self.assertEqual(hashlib.sha256((self.root/self.r['path']).read_bytes()).hexdigest(),before)
        with patch('threading.Thread.start'):restored=Store(self.settings)
        self.assertEqual(restored.inputs[record['id']]['dataset_context'],record['dataset_context'])
        self.assertNotIn('source_path',public_input(stored))

    def test_reopening_uses_latest_confirmation_revision_and_keeps_origin(self):
        intake=self.store.open_package_record(self.body)
        item=self.store.confirm_intake(intake['id'],self.confirmation)['input']
        revised=self.store.revise_input(item['id'],{**self.confirmation,'base_revision':1,'label':'Corrected label'})['input']
        self.assertNotEqual(item['id'],revised['id'])
        reopened=self.store.open_package_record(self.body)
        self.assertEqual(reopened['input_id'],revised['id'])
        self.assertEqual(self.store.intake_status(intake['id'])['input_id'],revised['id'])
        self.assertEqual(revised['dataset_context'],item['dataset_context'])

    def test_manifest_membership_and_client_path_rejected(self):
        for body in ({**self.body,'record_id':'../outside.edf'}, {**self.body,'manifest_hash':'old'},
                     {**self.body,'source_path':str(self.root/self.r['path'])}):
            with self.subTest(body=body),self.assertRaises((ValueError,KeyError)):self.store.open_package_record(body)
        self.assertEqual(list(self.store.intakes.root.iterdir()),[])

    def test_source_change_blocks_confirmation_and_creates_new_snapshot(self):
        intake=self.store.open_package_record(self.body)
        source=self.root/self.r['path'];data=bytearray(source.read_bytes());data[-1]^=1;source.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'变化'):self.store.confirm_intake(intake['id'],self.confirmation)
        newer=self.store.open_package_record(self.body)
        self.assertNotEqual(newer['id'],intake['id'])
        self.assertNotEqual(newer['source_sha256'],intake['source_sha256'])

    def test_symlink_replacement_is_rejected_even_with_identical_bytes(self):
        intake=self.store.open_package_record(self.body)
        source=self.root/self.r['path'];outside=self.base/'outside.edf';outside.write_bytes(source.read_bytes())
        source.unlink();source.symlink_to(outside)
        with self.assertRaises(ValueError):self.store.confirm_intake(intake['id'],self.confirmation)
        with self.assertRaises(ValueError):self.store.open_package_record(self.body)
        self.assertFalse(self.store.package_records('pilot')['records'][0]['available'])

    def test_cloud_record_open_cannot_bypass_dataset_total(self):
        from ephys_qc.admission import DEFAULT_INTAKE_LIMITS, LimitExceeded
        self.store.packages.admission_policy=DEFAULT_INTAKE_LIMITS
        for i in range(6):
            with (self.root/f'unlisted-{i}.bin').open('wb') as handle:handle.truncate(2*1024**3)
        with self.assertRaises(LimitExceeded) as caught:self.store.open_package_record(self.body)
        self.assertEqual(caught.exception.field,'dataset_bytes')
        self.assertFalse(list(self.store.intakes.root.iterdir()))

    def test_metadata_changes_do_not_reuse_previous_manifest_identity(self):
        first=self.store.open_package_record(self.body)
        self.plan['scope']='Corrected scope';self.config.write_text(json.dumps(self.plan))
        with self.assertRaises(ValueError):self.store.open_package_record(self.body)
        second=self.store.open_package_record({**self.body,'manifest_hash':fingerprint(self.plan)})
        self.assertNotEqual(first['id'],second['id'])

    def test_run_keeps_dataset_context_and_history_without_merging_subjects(self):
        intake=self.store.open_package_record(self.body)
        item=self.store.confirm_intake(intake['id'],self.confirmation)['input']
        body={'input_id':item['id'],'selected_modules':['M01','M02','M03','M08','M09']}
        _,plan=self.store.plan_request(body)
        job=self.store.submit({**body,'plan_id':plan['plan_id']})
        self.assertEqual(job['dataset_context']['record_id'],self.r['id'])
        rows=self.store.package_records('pilot')['records']
        self.assertEqual(rows[0]['signal_runs'][0]['id'],job['id'])
        self.assertTrue(all(not r['signal_runs'] for r in rows[1:]))
        saved=json.loads((self.store.root/'jobs'/job['id']/'request.json').read_text())
        self.assertEqual(saved['input']['dataset_context'],job['dataset_context'])

    def test_changed_source_cannot_be_queued_after_confirmation(self):
        intake=self.store.open_package_record(self.body)
        item=self.store.confirm_intake(intake['id'],self.confirmation)['input']
        body={'input_id':item['id'],'selected_modules':['M01','M02','M03','M08','M09']}
        _,plan=self.store.plan_request(body)
        source=self.root/self.r['path'];data=bytearray(source.read_bytes());data[-1]^=1;source.write_bytes(data)
        with self.assertRaisesRegex(ValueError,'变化'):self.store.submit({**body,'plan_id':plan['plan_id']})
        self.assertFalse(self.store.jobs)


if __name__=='__main__':unittest.main()
