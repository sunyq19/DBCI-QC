"""Saved configuration selection is metadata-only and preserves run history."""
import copy
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/workbench'))
from data_library import configuration_source


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.record = dict(id='one', label='EEG', expected_sha256='a'*64,
                           modality='scalp_eeg', metadata={'format':'EDF'},
                           source_path='/must-not-read-signal.edf')
        self.store = SimpleNamespace(lock=threading.RLock(), inputs={'one':self.record}, jobs={})

    def job(self, identifier, date, input_id='one', **extra):
        self.store.jobs[identifier] = dict(id=identifier, input_id=input_id, created_at=date,
                                         status='completed', **extra)

    def test_latest_time_not_insertion_order_or_result_status(self):
        self.job('new', '2026-11-10T01:00:00Z')
        self.job('old', '2026-11-09T01:00:00Z')
        self.store.jobs['new']['status'] = 'failed'
        before = copy.deepcopy(self.store.jobs)
        record, job = configuration_source(self.store, 'one')
        self.assertEqual(job['id'], 'new')
        self.assertEqual(record['id'], 'one')
        self.assertEqual(before, self.store.jobs)
        record['label'] = 'changed'
        self.assertEqual(self.record['label'], 'EEG')

    def test_identical_reuploads_share_latest_configuration_from_actual_confirmation(self):
        self.store.inputs['two'] = dict(self.record, id='two')
        self.job('old', '2026-11-09', 'one')
        self.job('new', '2026-11-10', 'two')
        record, job = configuration_source(self.store, 'one')
        self.assertEqual((record['id'], job['id']), ('two', 'new'))

    def test_other_data_modalities_and_selected_streams_do_not_leak(self):
        for fields in [dict(expected_sha256='b'*64),dict(modality='ecog'),
                       dict(metadata={'format':'EDF','selected_stream_id':'different'}),
                       dict(dataset_context={'package_id':'other'})]:
            self.store.inputs['other'] = dict(self.record, id='other', **fields)
            self.job('newest', '2026-11-10', 'other')
            self.assertIsNone(configuration_source(self.store, 'one')[1])

    def test_old_confirmation_does_not_replace_new_revision(self):
        self.store.inputs['revision'] = dict(self.record, id='revision', record_family='one', record_revision=2)
        self.job('old-confirmation', '2026-11-10')
        self.assertIsNone(configuration_source(self.store, 'revision')[1])
        with self.assertRaisesRegex(ValueError, '记录信息已更新'):
            configuration_source(self.store, 'one')

    def test_unavailable_copies_not_reused_and_expired_data_remain_read_only(self):
        for field in [dict(availability={'status':'unavailable'}),dict(retention={'state':'expired'})]:
            self.store.inputs['gone'] = dict(self.record, id='gone', **field)
            self.job('new', '2026-11-10', 'gone')
            self.assertIsNone(configuration_source(self.store, 'one')[1])
            with self.assertRaisesRegex(ValueError, '数据副本不可用'):
                configuration_source(self.store, 'gone')

    def test_new_data_returns_its_confirmation_without_a_run(self):
        record, job = configuration_source(self.store, 'one')
        self.assertEqual(record, self.record)
        self.assertIsNone(job)


if __name__ == '__main__':
    unittest.main()
