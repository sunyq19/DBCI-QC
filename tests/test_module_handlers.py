"""Module handoff contracts and selected-only execution, without a web server.

Stub tests check orchestration/argument identity, not detector accuracy. Small
real waveform tests exercise the configured scientific backend when available.
"""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.modules import ModuleContext, get_handler, module_specs, run_module

SCIENTIFIC = (importlib.util.find_spec('mne') is not None and
              importlib.util.find_spec('brainelecqc') is not None)


def backend_patch(name, function, callback):
    fake = types.ModuleType('brainelecqc.eeg.' + name)
    setattr(fake, function, callback)
    return patch.dict(sys.modules, {fake.__name__: fake})


class HandlerContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.evidence = {}
        self.state = {'data': object(), 'fs': 256., 'first': 2560, 'start': 10.,
            'channels': [{'channel_id': 'record:ch:2', 'raw_name': 'Cz', 'source_index': 2,
                          'physical_min': -1., 'physical_max': 1., 'digital_to_physical_scale': .01}],
            'references': {}, 'reference_channels': {}, 'recording': {'duration_seconds': 2.}}

    def tearDown(self):
        self.temp.cleanup()

    def context(self, mid, *, methods=None, record=None, result=None):
        row = {'id': mid, 'name': mid, 'status': 'completed', 'reason': 'ready',
               'summary': {}, 'duration_seconds': 0., 'artifacts': []}
        def save(name, payload, attached_row):
            self.assertIs(attached_row, row)
            self.evidence[name] = copy.deepcopy(payload)
            attached_row['artifacts'].append(name)
        return ModuleContext(record=record or {}, plan={}, config={'method_config': methods or {}},
            state=self.state, result=result if result is not None else {}, row=row,
            source=self.root / 'source', root=self.root, artifacts=self.root,
            write_artifact=save)

    def test_registry_exposes_nine_real_distinct_file_entrypoints(self):
        specs = module_specs()
        self.assertEqual([s['id'] for s in specs], [f'M{i:02d}' for i in range(1, 10)])
        files = set()
        for spec in specs:
            handler = get_handler(spec['id'])
            self.assertEqual(handler.__module__ + ':' + handler.__name__, spec['entrypoint'])
            files.add(handler.__code__.co_filename)
        self.assertEqual(len(files), 9)
        self.assertTrue(all(Path(p).parent.name == 'modules' for p in files))
        specs[0]['provides_state'].clear()
        self.assertEqual(module_specs()[0]['provides_state'], ['reader', 'description'])
        json.dumps(module_specs(), allow_nan=False)
        with self.assertRaises(ValueError): get_handler('M99')

    def test_registry_and_all_handlers_import_without_scientific_or_web_packages(self):
        script = '''
import importlib.abc, sys
sys.path.insert(0, sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'numpy','scipy','mne','matplotlib','brainelecqc','apps'}:
            raise AssertionError('Unexpected import: '+fullname)
sys.meta_path.insert(0, Block())
from ephys_qc.modules import module_specs, get_handler
for spec in module_specs(): get_handler(spec['id'])
'''
        subprocess.run([sys.executable, '-c', script, str(REPO / 'src')], check=True,
                       capture_output=True, cwd=self.root)

    def test_m03_forwards_source_identity_config_and_retains_guard_without_exclusion(self):
        candidate = {'kind': 'flat', 'onset_seconds': 10.5, 'duration_seconds': .1}
        payload = {'candidates': [candidate]}
        compute = Mock(return_value=payload)
        context = self.context('M03', methods={'continuity': {'test_parameter': .5}})
        with backend_patch('continuity', 'compute_continuity_qc', compute):
            self.assertIs(run_module('M03', context), context.row)
        args, kwargs = compute.call_args
        self.assertIs(args[0], self.state['data'])
        self.assertEqual(args[1:], (256., ['record:ch:2'], ['Cz']))
        self.assertEqual(kwargs['start_sample'], 2560)
        self.assertEqual(kwargs['start_seconds'], 10.)
        self.assertIs(kwargs['channels'], self.state['channels'])
        self.assertEqual(kwargs['config'], {'test_parameter': .5})
        self.assertIs(self.state['continuity_candidates'], payload['candidates'])
        self.assertEqual(context.row['summary']['automatic_exclusions'], 0)
        self.assertEqual(context.row['status'], 'completed')
        self.assertEqual(self.evidence['M03_continuity.json'], payload)

    def test_m03_unknown_adc_still_retains_continuity_evidence_as_partial(self):
        self.state['channels'][0].pop('physical_min')
        context = self.context('M03')
        with backend_patch('continuity', 'compute_continuity_qc', Mock(return_value={'candidates': []})):
            run_module('M03', context)
        self.assertEqual(context.row['status'], 'partial')
        self.assertEqual(context.row['summary']['adc_endpoint_assessment'], 'unavailable_for_some_channels')
        self.assertIn('M03_continuity.json', context.row['artifacts'])

    def test_m04_unassessed_tail_is_partial_even_when_line_noise_computed(self):
        payload = {'line_noise': {'status': 'computed', 'observations': [{'flagged': True}]},
            'parameterization': {'full': [{'status': 'computed'}],
                                 'windows': [{'status': 'insufficient_duration'}]}}
        context = self.context('M04')
        with backend_patch('spectral', 'compute_spectral_qc', Mock(return_value=payload)):
            run_module('M04', context)
        self.assertEqual(context.row['status'], 'partial')
        self.assertEqual(context.row['summary']['line_flagged_observations'], 1)
        self.assertEqual(self.evidence['M04_spectral.json'], payload)

    def test_m05_keeps_unthresholded_group_descriptions_without_claiming_good(self):
        group = {'group_id': 'unknown', 'usable_channel_count': 1,
                 'thresholds_active': False, 'status': 'insufficient_group'}
        payload = {'candidates': [], 'channels': [{'channel_name': 'Cz', 'flags': []}],
                   'groups': [group]}
        compute = Mock(return_value=payload)
        context = self.context('M05', methods={'comparison_groups': None})
        with backend_patch('bad_channels', 'compute_bad_channels', compute):
            run_module('M05', context)
        self.assertIsNone(compute.call_args.kwargs['groups'])
        self.assertEqual(context.row['status'], 'partial')
        self.assertEqual(context.row['summary']['groups'], [group])
        self.assertFalse(context.row['summary']['quality_labels_used_for_detection'])

    def test_m06_calls_two_methods_with_original_aux_and_continuity_guard(self):
        self.state['continuity_candidates'] = [{'kind': 'flat'}]
        self.state['references'] = {'ecg': object()}
        events = Mock(return_value={'by_kind': {'ecg': {'status': 'computed', 'detected_event_count': 2},
                                               'eog': {'status': 'missing_reference', 'detected_event_count': 0}}})
        muscle = Mock(return_value={'status': 'ok', 'reference': {'status': 'missing_reference'},
                                    'candidates': [{'kind': 'high_frequency_burst'}]})
        context = self.context('M06')
        with backend_patch('events', 'compute_event_qc', events), backend_patch('muscle', 'compute_muscle_qc', muscle):
            run_module('M06', context)
        self.assertIs(events.call_args.kwargs['references'], self.state['references'])
        self.assertIs(muscle.call_args.kwargs['excluded_intervals'], self.state['continuity_candidates'])
        self.assertEqual(muscle.call_args.kwargs['start_seconds'], 10.)
        self.assertEqual(context.row['status'], 'partial')
        self.assertEqual(context.row['summary']['emg_supported_count'], 0)
        self.assertEqual(context.row['artifacts'], ['M06_auxiliary_events.json', 'M06_muscle.json'])

    def test_m07_retains_original_annotation_clock_and_non_quality_scope(self):
        source = self.root / 'events.tsv'
        source.write_text('onset\tduration\tevent_value\tevent_name\n10.5\t0\t1\tstimulus\n')
        context = self.context('M07', record={'metadata': {'duration_seconds': 20.},
            'annotation': {'format': 'bids_events_tsv', 'path': str(source),
                           'label_scope': 'task_events_not_quality'}})
        run_module('M07', context)
        self.assertEqual(context.row['summary']['selected_count'], 1)
        self.assertFalse(context.row['summary']['quality_ground_truth'])
        self.assertEqual(context.row['status'], 'completed')
        self.assertNotIn('continuity_candidates', self.state)

    def test_m08_keeps_null_score_and_prior_failure_evidence(self):
        result = {'source_sha256': None, 'score': {'value': None},
                  'modules': [{'id': 'M03', 'status': 'failed', 'reason': 'injected', 'summary': {}}]}
        context = self.context('M08', result=result)
        run_module('M08', context)
        self.assertEqual(context.row['status'], 'partial')
        self.assertIsNone(context.row['summary']['score']['value'])
        self.assertIsNone(context.row['summary']['source_unchanged'])
        self.assertEqual(context.row['summary']['module_assessments'][0]['status'], 'failed')

    def test_m09_without_loaded_data_keeps_a_failure_report_not_fake_waveform(self):
        self.state.pop('data')
        context = self.context('M09', result={'warnings': []})
        run_module('M09', context)
        self.assertEqual(context.row['status'], 'partial')
        self.assertEqual(context.row['artifacts'], ['report.html'])
        self.assertEqual(context.row['summary']['review_status'], 'pending')


@unittest.skipUnless(SCIENTIFIC, 'Requires configured scientific environment')
class SelectedExecutionTests(unittest.TestCase):
    def setUp(self):
        from test_readers import brainvision_fixture, qc_record
        from ephys_qc.readers import inspect_recording
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        fixture = self.root / 'source'; fixture.mkdir()
        path, self.expected = brainvision_fixture(fixture)
        self.record = qc_record(path, inspect_recording(path))
        self.record['default_config']['selection']['duration_seconds'] = 4.

    def tearDown(self):
        self.temp.cleanup()

    def execute(self, selected):
        from ephys_qc.core import run_job
        self.events = []
        return run_job({'input': self.record, 'selected_modules': selected},
                       self.root / 'job', lambda *args: self.events.append(args))

    def test_only_selected_spectral_method_runs_on_real_waveforms(self):
        from brainelecqc.eeg.spectral import compute_spectral_qc
        with patch('brainelecqc.eeg.spectral.compute_spectral_qc', wraps=compute_spectral_qc) as chosen, \
             patch('brainelecqc.eeg.continuity.compute_continuity_qc', side_effect=AssertionError('unselected')) as continuity, \
             patch('brainelecqc.eeg.bad_channels.compute_bad_channels', side_effect=AssertionError('unselected')) as bad_channels, \
             patch('brainelecqc.eeg.events.compute_event_qc', side_effect=AssertionError('unselected')) as events, \
             patch('brainelecqc.eeg.muscle.compute_muscle_qc', side_effect=AssertionError('unselected')) as muscle:
            result = self.execute(['M04'])
        chosen.assert_called_once()
        for skipped in (continuity, bad_channels, events, muscle): skipped.assert_not_called()
        self.assertEqual(set(result['selected_modules']), {'M01', 'M02', 'M04', 'M08', 'M09'})
        self.assertFalse(any(m['status'] == 'failed' for m in result['modules']))
        self.assertEqual(result['recording']['source_indices'], [0, 1])
        self.assertEqual(result['recording']['stop_sample'], 400)
        self.assertTrue((self.root / 'job/artifacts/report.html').is_file())

    def test_selected_m06_executes_its_real_m03_dependency_and_no_other_detector(self):
        from brainelecqc.eeg.continuity import compute_continuity_qc
        from brainelecqc.eeg.events import compute_event_qc
        from brainelecqc.eeg.muscle import compute_muscle_qc
        with patch('brainelecqc.eeg.continuity.compute_continuity_qc', wraps=compute_continuity_qc) as guard, \
             patch('brainelecqc.eeg.events.compute_event_qc', wraps=compute_event_qc) as events, \
             patch('brainelecqc.eeg.muscle.compute_muscle_qc', wraps=compute_muscle_qc) as muscle, \
             patch('brainelecqc.eeg.spectral.compute_spectral_qc') as spectral, \
             patch('brainelecqc.eeg.bad_channels.compute_bad_channels') as bad_channels:
            result = self.execute(['M06'])
        for chosen in (guard, events, muscle): chosen.assert_called_once()
        spectral.assert_not_called(); bad_channels.assert_not_called()
        self.assertEqual(set(result['selected_modules']), {'M01', 'M02', 'M03', 'M06', 'M08', 'M09'})
        starts = [mid for mid, status, _ in self.events if status == 'running']
        self.assertLess(starts.index('M03'), starts.index('M06'))
        self.assertEqual(next(m for m in result['modules'] if m['id'] == 'M06')['status'], 'partial')
        self.assertFalse(any(m['status'] == 'failed' for m in result['modules']))

    def test_failed_dependency_preserves_error_skips_consumer_and_still_reports(self):
        with patch('brainelecqc.eeg.continuity.compute_continuity_qc', side_effect=RuntimeError('controlled failure')), \
             patch('brainelecqc.eeg.events.compute_event_qc') as events, \
             patch('brainelecqc.eeg.muscle.compute_muscle_qc') as muscle:
            result = self.execute(['M06'])
        events.assert_not_called(); muscle.assert_not_called()
        rows = {m['id']: m for m in result['modules']}
        self.assertEqual(rows['M03']['status'], 'failed')
        self.assertEqual(rows['M06']['status'], 'skipped')
        self.assertEqual(rows['M08']['status'], 'partial')
        self.assertEqual(rows['M09']['status'], 'completed')
        self.assertIsNone(result['score']['value'])
        error = json.loads((self.root / 'job/artifacts/M03_error.json').read_text())
        self.assertEqual(error['message'], 'controlled failure')
        self.assertTrue((self.root / 'job/artifacts/report.html').is_file())


if __name__ == '__main__':
    unittest.main()
