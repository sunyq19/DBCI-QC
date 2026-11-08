"""Identity boundaries: equal names/shapes cannot merge different EEG data."""
import copy
from pathlib import Path
import tempfile
import unittest

from library_identity import data_identity, workflow_identity, workflow_groups


class LibraryIdentityTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(id='one', label='EEG', source_path='/a/file.edf',
                           expected_sha256='a'*64, metadata={'format':'EDF'},
                           modality='scalp_eeg', reference_scheme='unknown')
        self.job = dict(id='1'*32, input_id='one', status='completed', created_at='2026-11-07',
                        software_version='test/1', plan={'schema_version':'plan/1',
                        'selected_modules':['M01','M03','M09'], 'qc_config':{
                            'scope':'recording', 'selection':{'eeg_indices':[0,1], 'duration_seconds':60},
                            'method_config':{'extensions':['b','a']},
                            'scoring':{'version':'score/1','weights':{'integrity':1}}}})

    def test_rename_or_reupload_identical_bytes_keeps_identity(self):
        other = dict(self.record, id='two', label='Different name', source_path='/b/renamed.edf',
                     expected_source_files=[dict(path='/b/renamed.edf', role='main', sha256='a'*64)])
        self.assertEqual(data_identity(self.record), data_identity(other))
        self.assertNotEqual(data_identity(self.record), data_identity(dict(other, expected_sha256='b'*64)))

    def test_companions_streams_and_missing_hashes_are_not_merged(self):
        a = dict(self.record, expected_source_files=[dict(role='data', sha256='b'*64)])
        b = dict(self.record, expected_source_files=[dict(role='data', sha256='c'*64)])
        self.assertNotEqual(data_identity(a), data_identity(b))
        a = dict(self.record, metadata=dict(format='NWB', selected_stream_id='/acquisition/A'))
        b = dict(self.record, metadata=dict(format='NWB', selected_stream_id='/acquisition/B'))
        self.assertNotEqual(data_identity(a), data_identity(b))
        self.assertNotEqual(data_identity(dict(self.record, expected_sha256=None)),
                            data_identity(dict(self.record, expected_sha256=None, id='two')))

    def test_workflow_ignores_title_time_order_but_preserves_actual_settings(self):
        a = copy.deepcopy(self.job)
        a.update(id='2'*32, created_at='later', run_name='renamed run')
        a['plan']['selected_modules'].reverse()
        a['plan']['qc_config']['method_config']['extensions'].reverse()
        a['plan']['qc_config']['scoring']['weights']['integrity'] = 1.0
        expected = workflow_identity(self.job, self.record)
        self.assertEqual(expected, workflow_identity(a, self.record))
        for section, value in [
            ('selection', {'eeg_indices':[1], 'duration_seconds':60}),
            ('selection', {'eeg_indices':[0,1], 'duration_seconds':30}),
            ('scoring', {'version':'score/1','weights':{'integrity':0}}),
            ('method_config', {'extensions':['a','b'],'extension_parameters':{'a':{'threshold':3}}}),
        ]:
            changed = copy.deepcopy(a); changed['plan']['qc_config'][section] = value
            self.assertNotEqual(expected, workflow_identity(changed, self.record))
        self.assertNotEqual(expected, workflow_identity(a, dict(self.record, reference_scheme='bipolar')))
        self.assertNotEqual(expected, workflow_identity(dict(a, software_version='test/2'), self.record))

    def test_repeated_scheme_keeps_history_and_failed_latest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root/'jobs'/self.job['id']/'artifacts'/'report.html'
            report.parent.mkdir(parents=True); report.write_text('frozen')
            retry = dict(self.job, id='2'*32, status='failed', created_at='2026-11-08', run_name='重跑')
            groups = workflow_groups(root,[self.job,retry],{'one':self.record},{'one'})
            self.assertEqual(len(groups),1)
            self.assertEqual(len(groups[0]['runs']),2)
            self.assertEqual(groups[0]['latest']['status'],'failed')
            self.assertEqual(groups[0]['latest_report']['job_id'],self.job['id'])
            self.assertFalse(groups[0]['latest']['report_available'])
            self.assertEqual(report.read_text(),'frozen')

    def test_missing_configuration_is_never_grouped_by_run_name(self):
        a = dict(self.job, plan={}, run_name='same')
        b = dict(a, id='2'*32)
        self.assertNotEqual(workflow_identity(a,self.record), workflow_identity(b,self.record))

    def test_unmet_gnosis_conditions_do_not_look_like_a_scored_workflow(self):
        job = copy.deepcopy(self.job)
        job['plan']['qc_config']['method_config']['extensions'] = ['gnosis_artifact']
        job['plan']['method_applicability'] = [dict(id='gnosis_artifact',status='blocked',reason='Reference unknown')]
        with tempfile.TemporaryDirectory() as folder:
            group = workflow_groups(Path(folder),[job],{'one':self.record},{'one'})[0]
        self.assertTrue(group['requirements_unmet'])
        self.assertEqual(group['requirement_notes'],['Reference unknown'])


if __name__ == '__main__':
    unittest.main()
