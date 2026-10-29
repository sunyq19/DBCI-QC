"""Registration survives acquisition gaps; edits never mutate old provenance."""
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_intake import recording, confirmation
from intake import IntakeStore
from record_revisions import RecordRevisions, RevisionConflict
from ephys_qc.planning import build_plan
from server import Store, public_input


class RecordRevisionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.intakes = IntakeStore(self.temp.name)
        data = recording()
        self.intake = self.intakes.receive('sample.edf', len(data), io.BytesIO(data))
        self.record = self.intakes.confirm(self.intake['id'], confirmation())
        self.revisions = RecordRevisions(self.temp.name)

    def test_boundary_in_default_window_does_not_block_registration(self):
        meta = copy.deepcopy(self.record['metadata'])
        meta['continuous_segments'] = [
            {'start_sample': 0, 'stop_sample': 1500, 'recording_start_seconds': 0, 'segment_id': 's0'},
            {'start_sample': 2000, 'stop_sample': 6000, 'recording_start_seconds': 20, 'segment_id': 's1'}]
        data = recording()
        intake = self.intakes.receive('gapped.edf', len(data), io.BytesIO(data))
        with patch('intake.inspect_recording', return_value=meta):
            record = self.intakes.confirm(intake['id'], confirmation())
        self.assertEqual(record['default_config']['selection']['duration_seconds'], 15)
        build_plan(record, [])
        with self.assertRaisesRegex(ValueError, '连续段'):
            build_plan(record, [], {'selection': {'duration_seconds': 60}})

    def test_empty_continuous_segments_can_register_but_cannot_run(self):
        meta = copy.deepcopy(self.record['metadata'])
        meta['continuous_segments'] = []
        data = recording()
        intake = self.intakes.receive('allgap.edf', len(data), io.BytesIO(data))
        with patch('intake.inspect_recording', return_value=meta):
            record = self.intakes.confirm(intake['id'], confirmation())
        self.assertEqual(record['default_config']['selection']['duration_seconds'], 0)
        with self.assertRaises(ValueError):
            build_plan(record)

    def test_revision_preserves_old_source_and_snapshot(self):
        before = json.dumps(self.record, sort_keys=True)
        saved = (self.intakes.root / self.intake['id'] / 'record.json').read_bytes()
        revised = self.revisions.revise(self.record, confirmation(base_revision=1, reference_scheme='linked_ears'), 1)
        self.assertEqual(json.dumps(self.record, sort_keys=True), before)
        self.assertEqual((self.intakes.root / self.intake['id'] / 'record.json').read_bytes(), saved)
        self.assertEqual(revised['record_family'], self.record['id'])
        self.assertEqual(revised['record_revision'], 2)
        self.assertEqual(revised['parent_input_id'], self.record['id'])
        self.assertEqual(revised['expected_sha256'], self.record['expected_sha256'])
        self.assertEqual(revised['default_config']['method_config']['comparison_groups'], ['user_confirmed_reference'] * 2)
        self.assertNotEqual(revised['id'], self.record['id'])
        self.assertEqual(RecordRevisions(self.temp.name).registered(), [revised])

    def test_conflicting_or_unconfirmed_edits_are_rejected(self):
        for body, latest in [(confirmation(base_revision=2), 1), (confirmation(base_revision=1), 2)]:
            with self.assertRaises(RevisionConflict):
                self.revisions.revise(self.record, body, latest)
        with self.assertRaises(ValueError):
            self.revisions.revise(self.record, confirmation(base_revision=1, confirmed=False), 1)
        self.assertEqual(self.revisions.registered(), [])

    def test_preprocessing_needs_evidence_and_valid_frequency_range(self):
        for prep in [{'verified': True}, {'verified': True, 'note': 'manual', 'highpass_hz': 40, 'lowpass_hz': 20}]:
            with self.assertRaises(ValueError):
                self.revisions.revise(self.record, confirmation(base_revision=1, preprocessing=prep), 1)
        new = self.revisions.revise(self.record, confirmation(base_revision=1, preprocessing={
            'verified': True, 'highpass_hz': 0.1, 'lowpass_hz': 40, 'note': 'Acquisition manual'}), 1)
        self.assertEqual(new['preprocessing']['source'], 'user_declaration_not_independent_measurement')

    def test_annotation_mapping_uses_only_explicit_source_labels(self):
        events = [{'text': 'S  1', 'onset_seconds': 2, 'duration_seconds': 0},
                  {'text': 'boundary', 'onset_seconds': 4, 'duration_seconds': 0}]
        class Reader:
            def describe(self): return {'events': events}
            def close(self): pass
        mapping = {'kind': 'task', 'labels': {'S  1': 'left_hand'}, 'confirmed': True, 'note': 'Protocol'}
        with patch('record_revisions.open_reader', return_value=Reader()):
            new = self.revisions.revise(self.record, confirmation(base_revision=1, annotation_mapping=mapping), 1)
        self.assertIn('left_hand', Path(new['annotation']['path']).read_text())
        self.assertEqual(new['annotation']['format'], 'bids_events_tsv')
        self.assertNotIn('annotation', self.record)
        for invalid in [{'missing': 'event'}, {'boundary': 'event'}]:
            with patch('record_revisions.open_reader', return_value=Reader()), self.assertRaises(ValueError):
                self.revisions.revise(self.record, confirmation(base_revision=1, annotation_mapping={**mapping, 'labels': invalid}), 1)

    def test_missing_source_does_not_prevent_startup_or_hide_history(self):
        missing = {**self.record, 'id': 'missing', 'source_path': '/does-not-exist/record.edf'}
        store = Store({'python': sys.executable, 'data_dir': self.temp.name,
                       'inputs': [missing], 'profiles': []})
        self.assertEqual(public_input(store.inputs['missing'])['availability']['status'], 'unavailable')
        with self.assertRaisesRegex(ValueError, '暂时不可用'):
            store.plan_request({'input_id': 'missing'})

    def test_real_edf_tal_without_duration_maps_only_to_point_event(self):
        from test_workbench import interleaved_annotation_edf
        from ephys_qc.annotations import check_annotations
        data = bytearray(interleaved_annotation_edf())
        offset = 1024 + 200  # First record, after first 100-sample signal.
        data[offset:offset + 64] = b'+0\x14\x14\0+0.5\x14T1\x14\0'.ljust(64, b'\0')
        intake = self.intakes.receive('point.edf', len(data), io.BytesIO(data))
        record = self.intakes.confirm(intake['id'], confirmation(eeg_indices=[0, 2], reference_indices={}))
        mapping = {'kind': 'task', 'labels': {'T1': 'event'}, 'confirmed': True}
        revised = self.revisions.revise(record, {'confirmed': True, 'base_revision': 1, 'annotation_mapping': mapping}, 1)
        checked = check_annotations(revised['annotation'], 0., 2., 100.)
        self.assertEqual(checked['selected_count'], 1)
        self.assertEqual(checked['events'][0]['duration_seconds'], 0.)
        self.assertEqual(checked['events'][0]['onset_seconds'], .5)
        self.assertIn('false', Path(revised['annotation']['path']).read_text())
        with self.assertRaisesRegex(ValueError, '正时长'):
            self.revisions.revise(record, {'confirmed': True, 'base_revision': 1,
                                  'annotation_mapping': {**mapping, 'kind': 'sleep_stage'}}, 1)

    def test_unedited_external_annotations_and_filter_provenance_survive_revision(self):
        table = Path(self.temp.name) / 'external-events.tsv'
        table.write_text('onset\tduration\tevent_name\n1\t0\tstim\n')
        record = copy.deepcopy(self.record)
        record['annotation'] = {'path': str(table), 'format': 'bids_events_tsv'}
        record['preprocessing'] = {'verified': True, 'source': 'file_header_declaration',
                                   'highpass_hz': 0.1, 'lowpass_hz': 40., 'note': 'Source header'}
        old_bytes = table.read_bytes()
        new = self.revisions.revise(record, {'confirmed': True, 'base_revision': 1,
                                             'reference_scheme': 'linked_ears'}, 1)
        self.assertEqual(new['annotation'], record['annotation'])
        self.assertEqual(new['preprocessing'], record['preprocessing'])
        self.assertEqual(table.read_bytes(), old_bytes)


if __name__ == '__main__':
    unittest.main()
