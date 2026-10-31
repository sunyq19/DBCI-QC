"""Independent review contracts: sample extrema, provenance and immutable results."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'apps' / 'workbench'))
from review_workspace import (ReviewWorkspace, ReviewConflict, waveform_for_input,
                              minmax_envelope, normalize_candidates)

NUMPY = importlib.util.find_spec('numpy') is not None


def request_fixture():
    return {'input': {'id': 'record', 'source_path': '/not-opened/record.fif',
                     'metadata': {'channels': [{'index': 7, 'name': 'same'}, {'index': 2, 'name': 'same'}]},
                     'expected_sha256': 'a' * 64},
            'plan': {'plan_id': 'frozen-plan'},
            'qc_config': {'selection': {'eeg_indices': [7, 2], 'reference_indices': {},
                                        'start_seconds': 1., 'duration_seconds': 2.}}}


def selected_fixture():
    return {'channels': [{'source_index': 7, 'raw_name': 'same', 'channel_id': 'record:ch:7'},
                         {'source_index': 2, 'raw_name': 'same', 'channel_id': 'record:ch:2'}],
            'recording': {'start_seconds': 1., 'duration_seconds': 2.}}


def candidate_fixture():
    return {'candidates': [{'channel_index': 1, 'channel_id': 'record:ch:2', 'channel_name': 'same',
                           'kind': 'flat', 'start_seconds': 1.25, 'stop_seconds': 1.5,
                           'evidence': {'value_volts': 0.}, 'reason': 'constant'}]}


class CandidateContracts(unittest.TestCase):
    def normalize(self, payload, method='raw_continuity_review', **kwargs):
        return normalize_candidates(payload, module_id='M03', method=method, request=request_fixture(),
                                    selection_artifact=selected_fixture(), artifact_name='M03_continuity.json', **kwargs)

    def test_analysis_position_maps_to_source_index_and_duplicate_names_stay_distinct(self):
        result = self.normalize(candidate_fixture())[0]
        self.assertEqual(result['channel_indices'], [2])
        self.assertEqual(result['channel_names'], ['same'])
        self.assertEqual(result['start_seconds'], 1.25)
        self.assertEqual(result['localization'], 'interval')

    def test_extension_mapping_takes_priority_over_selection_positions(self):
        payload = candidate_fixture()
        payload['channel_mapping'] = [{'analysis_index': 1, 'source_index': 12, 'raw_name': 'Z', 'channel_id': 'record:ch:12'}]
        payload['candidates'][0].pop('channel_id')
        self.assertEqual(self.normalize(payload)[0]['channel_indices'], [12])

    def test_pair_only_is_whole_window_not_an_invented_artifact_interval(self):
        result = self.normalize({'candidates': [{'channel_indices': [0, 1], 'localization': 'pair_only',
            'start_seconds': None, 'stop_seconds': None, 'analysis_range': [1., 3.], 'kind': 'bridge'}]}, 'mne_bridge')[0]
        self.assertEqual(result['channel_indices'], [7, 2])
        self.assertEqual(result['localization'], 'whole_window')
        self.assertFalse(result['interval_is_detection'])
        self.assertEqual((result['start_seconds'], result['stop_seconds']), (1., 3.))

    def test_prep_global_candidate_does_not_invent_time_precision(self):
        payload = candidate_fixture(); payload['candidates'][0]['window_indices'] = []
        result = self.normalize(payload, 'prep_nonspatial_review')[0]
        self.assertEqual(result['localization'], 'whole_window')
        payload['candidates'][0]['window_indices'] = [1]
        self.assertEqual(self.normalize(payload, 'prep_nonspatial_review')[0]['localization'], 'interval')

    def test_interval_only_does_not_invent_single_channel(self):
        payload = {'candidates': [{'kind': 'BAD_flat', 'localization': 'interval_only',
                    'start_seconds': 1., 'stop_seconds': 2., 'channel_index': None}]}
        result = self.normalize(payload, 'mne_amplitude')[0]
        self.assertEqual(result['channel_indices'], [])
        self.assertEqual(result['scope_channel_indices'], [7, 2])

    def test_flagged_line_windows_only_no_inference_from_psd_or_events(self):
        payload = {'line_noise': {'observations': [
            {'channel_index': 0, 'flagged': False},
            {'channel_index': 1, 'flagged': True, 'start_seconds': 1., 'stop_seconds': 2., 'p_corrected': .001}]},
            'events': [{'onset': 1, 'label': 'seizure'}], 'psd': [999]}
        result = self.normalize(payload, 'line_noise')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['evidence']['json_pointer'], '/line_noise/observations/1')
        self.assertEqual(self.normalize({'events': [{'onset': 1}]}), [])

    def test_line_observation_without_time_is_explicit_whole_window(self):
        payload = {'line_noise': {'observations': [{'channel_index': 0, 'flagged': True}]}}
        result = self.normalize(payload, 'line_noise')[0]
        self.assertEqual(result['localization'], 'whole_window')
        self.assertFalse(result['interval_is_detection'])
        self.assertEqual((result['start_seconds'], result['stop_seconds']), (1., 3.))

    def test_changed_method_parameters_do_not_reuse_old_decision_identity(self):
        payload = candidate_fixture(); payload['parameters'] = {'threshold': 3}
        first = self.normalize(payload)[0]['id']
        payload['parameters']['threshold'] = 4
        self.assertNotEqual(self.normalize(payload)[0]['id'], first)

    def test_ids_are_stable_per_source_and_distinct_across_windows(self):
        one = self.normalize(candidate_fixture(), window_id='w000001')[0]
        self.assertEqual(one['id'], self.normalize(candidate_fixture(), window_id='w000001')[0]['id'])
        two = self.normalize(candidate_fixture(), window_id='w000002')[0]
        self.assertNotEqual(one['id'], two['id'])
        self.assertEqual(one['start_seconds'], two['start_seconds'])  # no second offset


class ReviewLogContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.write(self.root / 'request.json', request_fixture())
        self.write(self.root / 'result.json', {'status': 'partial'})
        self.write(self.root / 'artifacts/M02_selection.json', selected_fixture())
        self.write(self.root / 'artifacts/M03_continuity.json', candidate_fixture())
        self.workspace = ReviewWorkspace(self.root)

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def body(self, version=0, decision='accepted'):
        return {'expected_version': version, 'candidate_id': self.workspace.candidates()['candidates'][0]['id'],
                'decision': decision, 'note': 'Checked raw signal', 'reviewer': 'reviewer-A'}

    def test_read_only_initial_state_does_not_create_review_log(self):
        self.assertEqual(self.workspace.review()['version'], 0)
        self.assertEqual(self.workspace.review()['counts']['pending'], 1)
        self.assertFalse((self.root / 'reviews.json').exists())

    def test_truncated_evidence_stays_explicit_after_stored_candidates_reviewed(self):
        payload = candidate_fixture()
        payload.update(candidate_details_truncated=True, candidate_evidence={
            'truncated': True, 'observed_interval_count': 5, 'stored_interval_count': 1,
            'omitted_interval_count': 4})
        path = self.root / 'artifacts/M03_continuity.json'
        self.write(path, payload)
        original = path.read_bytes()
        before = self.workspace.candidates()
        self.assertEqual(before['count'], 1)
        warning = before['warnings'][0]
        self.assertEqual(warning['code'], 'candidate_details_truncated')
        self.assertEqual(warning['omitted_interval_count'], 4)
        saved = self.workspace.update_review(self.body())
        self.assertEqual(saved['counts']['pending'], 0)
        self.assertEqual(saved['warnings'], before['warnings'])
        self.assertEqual(self.workspace.review()['warnings'], before['warnings'])
        self.assertIsNone(self.workspace.candidates()['quality_pass'])
        self.assertEqual(path.read_bytes(), original)

    def test_decisions_append_versions_without_mutating_algorithm_files(self):
        protected = {p: p.read_bytes() for p in self.root.rglob('*.json')}
        first = self.workspace.update_review(self.body())
        self.assertEqual(first['version'], 1)
        self.assertEqual(first['status'], 'reviewed')
        second = self.workspace.update_review(self.body(1, 'uncertain'))
        self.assertEqual(len(second['history']), 2)
        self.assertEqual(second['history'][0]['decision'], 'accepted')
        self.assertEqual(second['counts']['uncertain'], 1)
        self.assertEqual(second['status'], 'in_progress')
        self.assertEqual(self.workspace.candidates()['candidates'][0]['status'], 'uncertain')
        for path, content in protected.items():
            self.assertEqual(path.read_bytes(), content)

    def test_stale_version_conflicts_without_overwriting(self):
        body = self.body(); self.workspace.update_review(body)
        before = (self.root / 'reviews.json').read_bytes()
        with self.assertRaises(ReviewConflict): self.workspace.update_review(body)
        self.assertEqual((self.root / 'reviews.json').read_bytes(), before)

    def test_malformed_history_is_rejected_without_overwriting(self):
        body = self.body()
        self.write(self.root / 'reviews.json', {'version': 1, 'history': []})
        before = (self.root / 'reviews.json').read_bytes()
        with self.assertRaises(ValueError): self.workspace.update_review(body)
        self.assertEqual((self.root / 'reviews.json').read_bytes(), before)

    def test_invalid_candidate_rejected_without_creating_a_log(self):
        body = self.body(); body['candidate_id'] = 'not-a-candidate'
        with self.assertRaises(ValueError): self.workspace.update_review(body)
        self.assertFalse((self.root / 'reviews.json').exists())

    def test_invalid_decisions_identity_lengths_and_version_are_rejected(self):
        for key, value in [('decision', 'normal'), ('decision', {}), ('expected_version', True), ('reviewer', ' '),
                           ('reviewer', 'x' * 161), ('note', 'x' * 4001), ('candidate_id', 4)]:
            body = self.body(); body[key] = value
            with self.subTest(key=key, value=str(value)[:20]), self.assertRaises(ValueError):
                self.workspace.update_review(body)

    def test_concurrent_same_version_allows_exactly_one_save(self):
        body = self.body(); outcomes = []
        def save():
            try:
                ReviewWorkspace(self.root).update_review(body); outcomes.append('saved')
            except ReviewConflict:
                outcomes.append('conflict')
        threads = [threading.Thread(target=save) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertCountEqual(outcomes, ['saved', 'conflict'])
        self.assertEqual(len(self.workspace.review()['history']), 1)

    def test_recording_children_keep_absolute_times_and_flat_artifact_names(self):
        for i in [1, 2]:
            child = self.root / 'windows' / f'w{i:06}'
            self.write(child / 'request.json', request_fixture())
            self.write(child / 'result.json', {'status': 'partial'})
            self.write(child / 'artifacts/M02_selection.json', selected_fixture())
            self.write(child / 'artifacts/M03_continuity.json', candidate_fixture())
        result = self.workspace.candidates()
        self.assertEqual(result['count'], 2)  # parent artifacts are not counted twice
        self.assertEqual({c['start_seconds'] for c in result['candidates']}, {1.25})
        self.assertEqual({c['evidence']['artifact'] for c in result['candidates']},
                         {'w000001--M03_continuity.json', 'w000002--M03_continuity.json'})

    def test_unfinished_window_and_failed_module_evidence_are_not_promoted(self):
        child = self.root / 'windows/w000001'
        self.write(child / 'request.json', request_fixture())
        self.write(child / 'artifacts/M03_continuity.json', candidate_fixture())
        result = self.workspace.candidates()
        self.assertEqual(result['count'], 0)
        self.assertEqual(result['warnings'][0]['window_ids'], ['w000001'])
        self.write(child / 'result.json', {'status': 'failed', 'modules': [{'id': 'M03', 'status': 'failed'}]})
        result = self.workspace.candidates()
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['warnings'])

    def test_failed_extension_and_auxiliary_events_do_not_become_candidates(self):
        self.write(self.root / 'artifacts/M06_auxiliary_events.json', {'events': [{'kind': 'ecg'}]})
        self.write(self.root / 'artifacts/M05_mne_lof.json', {**candidate_fixture(), 'status': 'failed'})
        self.assertEqual(self.workspace.candidates()['count'], 1)

    def test_symlink_artifact_is_reported_without_following_it(self):
        path = self.root / 'artifacts/M03_continuity.json'
        other = self.root / 'elsewhere.json'; path.rename(other); path.symlink_to(other)
        result = self.workspace.candidates()
        self.assertEqual(result['count'], 0)
        self.assertTrue(result['warnings'])
        self.assertIsNone(result['quality_pass'])


@unittest.skipUnless(NUMPY, 'Requires NumPy in the scientific environment')
class WaveformContracts(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.data = np.zeros((2, 6000))
        self.data[0, 1103] = .004
        self.data[0, 1104] = -.003
        self.data[1] = np.arange(6000) * 1e-12
        self.closed = False
        self.calls = []
        self.description = {'source_files': [{'name': 'record.fif', 'role': 'main', 'sha256': 'a' * 64}],
                            'streams': [{'stream_id': 's', 'sampling_frequency_hz': 1000.,
                                'channels': [{'source_index': 7, 'raw_name': 'same', 'channel_id': 'record:ch:7', 'unit': 'V'},
                                             {'source_index': 2, 'raw_name': 'same', 'channel_id': 'record:ch:2', 'unit': 'T'}],
                                'segments': [{'segment_id': 'a', 'start_sample': 12900, 'stop_sample': 15900, 'recording_start_seconds': 0.},
                                             {'segment_id': 'b', 'start_sample': 16400, 'stop_sample': 18900, 'recording_start_seconds': 3.5}]}]}
        outer = self
        class Reader:
            def describe(self): return copy.deepcopy(outer.description)
            def read_window(self, stream, segment, channels, start, stop, representation):
                outer.calls.append((stream, segment, channels, start, stop, representation))
                indices = [0 if c.endswith(':7') else 1 for c in channels]
                return outer.data[indices, start - 12900:stop - 12900].copy()
            def assert_unchanged(self, hashes=False): outer.hash_checked = hashes
            def close(self): outer.closed = True
        self.factory = lambda *args: Reader()

    def waveform(self, **kwargs):
        request = request_fixture()
        return waveform_for_input(request['input'], selection=request['qc_config']['selection'],
                                  reader_factory=self.factory, **kwargs)

    def test_positive_and_negative_spikes_survive_envelope_with_time_order(self):
        result = self.waveform(channel_indices=[7], max_points=20)
        row = result['channels'][0]
        self.assertLessEqual(row['display_point_count'], 20)
        self.assertIn(4000., row['values']); self.assertIn(-3000., row['values'])
        self.assertLess(row['values'].index(4000.), row['values'].index(-3000.))
        self.assertEqual(row['source_samples'][row['values'].index(4000.)], 14003)
        self.assertAlmostEqual(row['times_seconds'][row['values'].index(4000.)], 1.103)
        self.assertTrue(self.closed); self.assertTrue(self.hash_checked)
        self.assertFalse(result['analysis_modified'])

    def test_source_order_units_and_fif_origin_are_preserved(self):
        result = self.waveform(channels='2,7', max_points=2000)
        self.assertEqual([c['source_index'] for c in result['channels']], [2, 7])
        self.assertEqual([c['unit'] for c in result['channels']], ['T', 'µV'])
        self.assertEqual(result['start_sample'], 13900)
        self.assertEqual(result['start_seconds'], 1.)
        self.assertEqual(self.calls[0][2], ['record:ch:2', 'record:ch:7'])

    def test_nonfinite_markers_are_json_safe_and_not_hidden(self):
        import numpy as np
        self.data[0, 1200] = np.nan; self.data[0, 1300] = np.inf
        row = self.waveform(channel_indices=[7], max_points=20)['channels'][0]
        self.assertEqual(row['nonfinite_sample_count'], 2)
        self.assertIn(None, row['values'])
        json.dumps(row, allow_nan=False)

    def test_continuous_boundary_rejected_and_later_segment_clock_preserved(self):
        with self.assertRaisesRegex(ValueError, 'continuous'):
            self.waveform(start_seconds=2.9, duration_seconds=1)
        result = self.waveform(start_seconds=3.6, duration_seconds=.2)
        self.assertEqual(result['segment_id'], 'b')
        self.assertEqual(result['start_sample'], 16500)
        self.assertAlmostEqual(result['start_seconds'], 3.6)

    def test_fractional_rate_cannot_round_above_hard_ten_second_cap(self):
        stream = self.description['streams'][0]
        stream['sampling_frequency_hz'] = 300.35
        stream['segments'] = [{'segment_id': 'a', 'start_sample': 12900, 'stop_sample': 18900, 'recording_start_seconds': 0.}]
        result = self.waveform(start_seconds=0, duration_seconds=10, channel_indices=[7])
        self.assertLessEqual(result['duration_seconds'], 10.)
        self.assertEqual(result['stop_sample'] - result['start_sample'], 3003)

    def test_limits_and_bad_channel_indices_reject_before_native_read(self):
        cases = [{'duration_seconds': 11}, {'duration_seconds': 0}, {'start_seconds': -1},
                 {'duration_seconds': float('nan')}, {'max_points': 2001}, {'channel_indices': [True]},
                 {'channel_indices': [7, 7]}, {'channel_indices': '7,../2'}, {'channel_indices': [99]},
                 {'channels': '7', 'channel_indices': [7]}, {'channel_indices': list(range(17))}]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError): self.waveform(**case)
        self.assertEqual(self.calls, [])

    def test_changed_frozen_source_is_rejected(self):
        self.description['source_files'][0]['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'frozen'): self.waveform()
        self.assertTrue(self.closed); self.assertEqual(self.calls, [])

    def test_companion_manifest_change_rejects_even_with_same_main_file(self):
        record = request_fixture()['input']
        record['metadata']['source_files'] = [*self.description['source_files'], {'name': 'companion.eeg', 'sha256': 'c' * 64}]
        with self.assertRaisesRegex(ValueError, 'package'):
            waveform_for_input(record, channel_indices=[7], duration_seconds=1, reader_factory=self.factory)
        self.assertEqual(self.calls, [])

    def test_each_bucket_extremum_is_retained_and_envelope_never_exceeds_budget(self):
        import numpy as np
        rng = np.random.default_rng(7)
        data = rng.normal(size=10001)
        indices, output = minmax_envelope(data, 2000)
        self.assertLessEqual(len(indices), 2000)
        self.assertEqual(indices, sorted(set(indices)))
        edges = np.linspace(0, len(data), (2000 - 2) // 3 + 1, dtype=int)
        for left, right in zip(edges[:-1], edges[1:]):
            self.assertIn(left + int(np.argmin(data[left:right])), indices)
            self.assertIn(left + int(np.argmax(data[left:right])), indices)
        np.testing.assert_array_equal(output, data[indices])


if __name__ == '__main__':
    unittest.main()
