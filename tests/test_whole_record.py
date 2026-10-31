"""Whole-record scheduling, failure/cancel coverage, and real-reader checks.

Synthetic cases test engineering boundaries, not algorithm accuracy. One small
public EEG fixture is used only when already present; no test downloads data.
"""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.planning import build_plan
from ephys_qc.whole_record import build_recording_plan, execute_recording, window_config

SCIENTIFIC = importlib.util.find_spec('mne') is not None and importlib.util.find_spec('brainelecqc') is not None


def record(duration=125., fs=100., channels=2):
    return {'id': 'whole-fixture', 'label': 'Synthetic recording', 'source_path': '/nonexistent/fixture.edf',
            'modality': 'scalp_eeg', 'metadata': {'format': 'EDF', 'duration_seconds': duration,
                'channels': [{'index': i, 'name': f'C{i}', 'unit': 'uV', 'sampling_rate_hz': fs} for i in range(channels)]},
            'default_config': {'selection': {'eeg_indices': list(range(channels)), 'reference_indices': {},
                 'start_seconds': 17., 'duration_seconds': 1.}, 'method_config': {'comparison_groups': None}}}


def config(seconds=60., **options):
    return {'scope': 'recording', 'recording_options': {'window_seconds': seconds, **options}}


def request(source=None, options=None, modules=None):
    source = source or record()
    plan = build_plan(source, modules if modules is not None else ['M03'], options or config())
    return {'input': source, 'plan': plan, 'qc_config': plan['qc_config'], 'selected_modules': plan['selected_modules']}


def fake_runner(calls, *, fail_at=None, mismatch=False):
    def run(req, directory, emit, **kwargs):
        index = len(calls); calls.append(req)
        if index == fail_at:
            raise RuntimeError('Injected middle-window failure')
        p = req['plan']; selection = p['qc_config']['selection']; fs = req['input']['metadata']['channels'][0]['sampling_rate_hz']
        origin = req['input']['metadata'].get('clock', {}).get('first_sample', 0)
        first = origin + round(selection['start_seconds'] * fs)
        modules = [{'id': n['id'], 'name': n['name'], 'status': 'completed' if n['id'] in p['selected_modules'] else 'skipped',
                    'reason': '', 'duration_seconds': .1, 'summary': {}, 'artifacts': []} for n in p['nodes']]
        result = {'status': 'completed', 'modules': modules, 'recording': {'start_sample': first + int(mismatch),
                  'stop_sample': first + round(selection['duration_seconds'] * fs)}, 'data_sha256': f'data-{index}'}
        artifacts = directory / 'artifacts'; artifacts.mkdir()
        (artifacts / 'M03_continuity.json').write_text(json.dumps({'candidates': [{'channel_id': 'whole-fixture:ch:1',
            'onset_seconds': selection['start_seconds'] + .2, 'duration_seconds': .1}]}))
        (artifacts / 'report.html').write_text('<a href="M03_continuity.json">Evidence</a>')
        (directory / 'result.json').write_text(json.dumps(result))
        emit('M03', 'completed', 'test')
        return result
    return run


class WholePlanTests(unittest.TestCase):
    def test_all_native_samples_including_short_tail_are_planned_once(self):
        plan = build_plan(record(), ['M03'], config())
        self.assertEqual([(w['start_sample'], w['stop_sample']) for w in plan['windows']], [(0, 6000), (6000, 12000), (12000, 12500)])
        self.assertEqual(plan['qc_config']['selection']['start_seconds'], 0.)
        self.assertEqual(plan['qc_config']['selection']['duration_seconds'], 125.)
        self.assertEqual(plan['coverage_plan']['available_samples'], 12500)
        self.assertEqual(plan['window_count'], 3)
        for window in plan['windows']:
            child = build_plan(record(), plan['selected_modules'], window_config(plan, window))
            self.assertEqual(child['plan_id'], window['plan_id'])
        json.dumps(plan, allow_nan=False)

    def test_scope_defaults_to_window_and_recording_is_explicit(self):
        plan = build_plan(record(), ['M03'])
        self.assertEqual(plan['scope'], 'window')
        with self.assertRaises(ValueError): build_plan(record(), ['M03'], {'scope': 'anything'})
        with self.assertRaises(ValueError): build_plan(record(), ['M03'], config(121))
        with self.assertRaises(ValueError): build_plan(record(), ['M03'], config(0))
        with self.assertRaises(ValueError): build_plan(record(), ['M03'], config(expensive_methods='guess'))

    def test_dependency_closure_and_json_order_do_not_change_identity(self):
        source = record(); plan = build_plan(source, ['M06'], config())
        replay = build_plan(source, plan['selected_modules'], plan['qc_config'])
        self.assertEqual(plan['plan_id'], replay['plan_id'])
        self.assertEqual(plan['plan_id'], build_plan(json.loads(json.dumps(source, sort_keys=True)), ['M06'], config())['plan_id'])
        self.assertIn('M03', plan['auto_added_modules'])

    def test_noninteger_sampling_rate_retains_exact_end_sample(self):
        fs = 300.3074951171875; source = record(duration=40001 / fs, fs=fs)
        plan = build_plan(source, ['M03'], config(120))
        self.assertEqual(plan['windows'][0]['stop_sample'], 36036)
        self.assertEqual(plan['windows'][-1]['stop_sample'], 40001)
        self.assertEqual(sum(w['stop_sample'] - w['start_sample'] for w in plan['windows']), 40001)

    def test_gap_and_nonzero_source_origin_are_never_bridged(self):
        source = record(duration=4.)
        source['metadata'].update(clock={'first_sample': 500}, continuous_segments=[
            {'segment_id': 'a', 'start_sample': 500, 'stop_sample': 700, 'recording_start_seconds': 0.},
            {'segment_id': 'b', 'start_sample': 750, 'stop_sample': 900, 'recording_start_seconds': 2.5}])
        plan = build_plan(source, ['M03'], config(1.5))
        self.assertEqual([(w['start_sample'], w['stop_sample']) for w in plan['windows']], [(500,650),(650,700),(750,900)])
        self.assertEqual(plan['coverage_plan']['gap_samples'], 50)
        self.assertEqual(plan['coverage_plan']['gaps'][0]['start_seconds'], 2.)
        self.assertEqual(plan['coverage_plan']['available_seconds'], 3.5)

    def test_zero_duration_boundary_still_separates_windows(self):
        source = record(duration=4.)
        source['metadata']['continuous_segments'] = [
            {'segment_id':'a','start_sample':0,'stop_sample':200,'recording_start_seconds':0.},
            {'segment_id':'b','start_sample':200,'stop_sample':400,'recording_start_seconds':2.}]
        plan = build_plan(source, ['M03'], config())
        self.assertEqual(plan['window_count'], 2)
        self.assertEqual(plan['coverage_plan']['gap_samples'], 0)
        self.assertEqual([w['segment_id'] for w in plan['windows']], ['a','b'])

    def test_overlapping_or_off_grid_segments_rejected(self):
        for item in [
            [{'start_sample':0,'stop_sample':200,'recording_start_seconds':0.}, {'start_sample':100,'stop_sample':300,'recording_start_seconds':1.}],
            [{'start_sample':0,'stop_sample':200,'recording_start_seconds':.001}],
            [{'start_sample':0,'stop_sample':100000,'recording_start_seconds':0.}]]:
            source = record(duration=4.); source['metadata']['continuous_segments'] = item
            with self.subTest(item=item), self.assertRaises(ValueError): build_plan(source, ['M03'], config())

    def test_memory_budget_reduces_chunk_without_resampling(self):
        source = record(duration=1., fs=100000., channels=512)
        plan = build_plan(source, ['M03'], config())
        self.assertEqual(plan['windows'][0]['stop_sample'], 65536)
        self.assertEqual(plan['windows'][-1]['stop_sample'], 100000)
        self.assertTrue(all((w['stop_sample'] - w['start_sample']) * 512 * 8 <= 256 * 1024**2 for w in plan['windows']))

    def test_expensive_policy_explicit_and_changes_fingerprint(self):
        source = record(channels=4)
        source['default_config']['method_config']['extensions'] = ['autoreject_global']
        skip = build_plan(source, ['M03'], config())
        run = build_plan(source, ['M03'], config(expensive_methods='run'))
        self.assertEqual([m['id'] for m in skip['skipped_methods']], ['autoreject_global'])
        self.assertNotIn('autoreject_global', window_config(skip, skip['windows'][0])['method_config']['extensions'])
        self.assertIn('autoreject_global', window_config(run, run['windows'][0])['method_config']['extensions'])
        self.assertNotEqual(skip['plan_id'], run['plan_id'])

    def test_record_revision_is_frozen_in_both_plan_scopes(self):
        source = record(); old = build_plan(source, ['M03'], config())
        source.update(record_family='family', record_revision=2, parent_input_id='old')
        new = build_plan(source, ['M03'], config())
        self.assertNotEqual(old['plan_id'], new['plan_id'])
        self.assertEqual(new['input_lineage']['record_revision'], 2)
        self.assertEqual(build_plan(source, ['M03'])['input_lineage'], new['input_lineage'])

    def test_recommendation_roundtrips_recording_scope_without_signal_access(self):
        from ephys_qc.recommendations import recommend
        source = record(channels=4)
        result = recommend(source, config())
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['analysis_scope'], 'recording')
        self.assertEqual(result['window_count'], 3)
        plan = build_plan(source, result['selected_modules'], result['qc_config'])
        self.assertEqual(plan['plan_id'], result['plan_id'])

    def test_scope_cannot_bypass_modality_units_or_mixed_clocks(self):
        for source in [dict(record(), modality='other'), record(), record()]:
            if source is not None and source['modality'] == 'scalp_eeg':
                source['metadata']['channels'][0]['unit'] = 'unknown'
            with self.assertRaises(ValueError): build_plan(source, ['M03'], config())
        source = record(); source['metadata']['channels'][0]['sampling_rate_hz'] = 50
        with self.assertRaises(ValueError): build_plan(source, ['M03'], config())


class ExecutionCoverageTests(unittest.TestCase):
    def test_middle_failure_keeps_successful_and_unassessed_partitions(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]; result = execute_recording(request(), folder, lambda *args:None, window_runner=fake_runner(calls, fail_at=1))
            self.assertEqual(result['coverage']['completed_seconds'], 65.)
            self.assertEqual(result['coverage']['failed_seconds'], 60.)
            self.assertEqual(result['coverage']['unexecuted_seconds'], 0.)
            self.assertEqual(result['status'], 'partial')
            self.assertEqual([w['status'] for w in result['windows']], ['completed','failed','completed'])
            self.assertEqual(result['modules'][2]['status'], 'partial')
            self.assertTrue((Path(folder)/'windows/w000003/result.json').is_file())

    def test_cancel_after_first_window_retains_rest_as_not_run(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]; result = execute_recording(request(), folder, lambda *args:None, window_runner=fake_runner(calls), cancel_requested=lambda:bool(calls))
            self.assertEqual(len(calls), 1)
            self.assertEqual(result['status'], 'cancelled')
            self.assertEqual(result['coverage']['completed_seconds'],60.)
            self.assertEqual(result['coverage']['unexecuted_seconds'],65.)
            checkpoint=json.loads((Path(folder)/'recording-progress.json').read_text())
            self.assertEqual(checkpoint['coverage'], result['coverage'])
            self.assertEqual(checkpoint['windows'][1]['status'],'not_run')

    def test_candidate_origin_and_flat_links_are_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]; result=execute_recording(request(), folder, lambda *args:None, window_runner=fake_runner(calls))
            self.assertEqual(result['candidate_index'][1]['candidate']['onset_seconds'],60.2)
            report=(Path(folder)/'artifacts/w000002--report.html').read_text()
            self.assertIn('href="w000002--M03_continuity.json"',report)
            self.assertIn('w000003--report.html',(Path(folder)/'artifacts/report.html').read_text())
            self.assertTrue(all('/' not in a['name'] for a in result['artifacts']))
            self.assertEqual(result['coverage']['execution_percent'],100.)
            self.assertIsNone(result['score']['value'])

    def test_wrong_source_sample_bounds_fail_instead_of_covering(self):
        with tempfile.TemporaryDirectory() as folder:
            result=execute_recording(request(),folder,lambda *args:None,window_runner=fake_runner([],mismatch=True))
            self.assertEqual(result['coverage']['completed_seconds'],0)
            self.assertEqual(result['coverage']['failed_seconds'],125)
            self.assertEqual(result['status'],'failed')

    def test_existing_checkpoint_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'recording-progress.json').write_text('{}')
            with self.assertRaises(FileExistsError): execute_recording(request(),folder,lambda *args:None,window_runner=fake_runner([]))

    def test_source_gap_never_becomes_executed_coverage(self):
        source=record(duration=4.)
        source['metadata'].update(clock={'first_sample':500},continuous_segments=[
            {'segment_id':'a','start_sample':500,'stop_sample':700,'recording_start_seconds':0.},
            {'segment_id':'b','start_sample':750,'stop_sample':900,'recording_start_seconds':2.5}])
        with tempfile.TemporaryDirectory() as folder:
            result=execute_recording(request(source,config(1.5)),folder,lambda *args:None,window_runner=fake_runner([]))
            self.assertEqual(result['coverage']['completed_seconds'],3.5)
            self.assertEqual(result['coverage']['gap_seconds'],.5)
            self.assertEqual(result['coverage']['execution_percent'],87.5)
            self.assertEqual(result['coverage']['available_execution_percent'],100.)
            self.assertEqual(result['status'],'partial')


@unittest.skipUnless(SCIENTIFIC, 'Requires configured scientific environment')
class RealReaderExecutionTests(unittest.TestCase):
    def test_cancel_between_real_modules_preserves_partial_evidence(self):
        from test_readers import fif_fixture, qc_record
        from ephys_qc.readers import inspect_recording
        from ephys_qc.annotations import file_sha256
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path,_=fif_fixture(root,skip=True)
            source=qc_record(path,inspect_recording(path),[0]); source['expected_sha256']=file_sha256(path)
            job=root/'job'
            stop=lambda:(job/'windows/w000001/artifacts/M03_continuity.json').is_file()
            result=execute_recording(request(source,config(1.5)),job,lambda *args:None,cancel_requested=stop)
            self.assertEqual(result['status'],'cancelled')
            self.assertEqual(result['windows'][0]['status'],'cancelled')
            self.assertTrue((job/'artifacts/w000001--M03_continuity.json').is_file())
            self.assertEqual(result['coverage']['completed_seconds'],0.)
            self.assertEqual(result['coverage']['unexecuted_seconds'],3.5)
            m03=next(m for m in result['coverage']['by_module'] if m['id']=='M03')
            self.assertEqual(m03['partial_seconds'],1.5)
            self.assertEqual(m03['unexecuted_seconds'],2.)
            self.assertEqual(result['source_integrity'],'verified_after_run')

    def test_fif_gap_nonzero_origin_exact_read_and_original_hash(self):
        from test_readers import fif_fixture, qc_record
        from ephys_qc.readers import inspect_recording
        from ephys_qc.annotations import file_sha256
        from ephys_qc.core import run_job
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); path, _=fif_fixture(root,skip=True); digest=file_sha256(path)
            source=qc_record(path,inspect_recording(path),[0]); source['expected_sha256']=digest
            req=request(source,config(1.5))
            result=run_job(req,root/'job',lambda *args:None)
            self.assertEqual(result['coverage']['completed_seconds'],3.5)
            self.assertEqual(result['coverage']['gap_seconds'],.5)
            self.assertEqual(result['source_integrity'],'verified_after_run')
            self.assertEqual(file_sha256(path),digest)
            self.assertFalse(any(w['status']=='failed' for w in result['windows']))
            self.assertEqual([(w['start_sample'],w['stop_sample']) for w in result['windows']],[(500,650),(650,700),(750,900)])
            for window in result['windows']:
                child=json.loads((root/'job/windows'/window['id']/'result.json').read_text())
                self.assertEqual(child['recording']['start_sample'],window['start_sample'])
                self.assertEqual(child['recording']['stop_sample'],window['stop_sample'])
                self.assertIsNotNone(child.get('data_sha256'))

    def test_existing_public_eeg_entire_record_with_tail_no_download(self):
        from ephys_qc.readers import inspect_recording
        from ephys_qc.annotations import file_sha256
        from ephys_qc.core import run_job
        settings=REPO/'.local/workbench.json'
        if not settings.is_file(): self.skipTest('Local public fixture registry absent')
        sources=json.loads(settings.read_text())['inputs']
        source=next((copy.deepcopy(s) for s in sources if s.get('id')=='eegmmidb-s001r01'),None)
        if not source or not Path(source['source_path']).is_file(): self.skipTest('Existing public EEG fixture absent')
        source['metadata']=inspect_recording(source['source_path']); source['expected_sha256']=file_sha256(source['source_path'])
        source['default_config']['selection']['eeg_indices']=source['default_config']['selection']['eeg_indices'][:2]
        source['default_config']['selection']['reference_indices']={}
        source['default_config']['method_config']={'comparison_groups':None}
        with tempfile.TemporaryDirectory() as folder:
            result=run_job(request(source,config(30.)),folder,lambda *args:None)
            self.assertEqual(result['coverage']['completed_seconds'],source['metadata']['duration_seconds'])
            self.assertEqual(result['coverage']['execution_percent'],100.)
            self.assertGreaterEqual(len(result['windows']),3)
            self.assertTrue(all(w.get('data_sha256') for w in result['windows']))
            self.assertEqual(file_sha256(source['source_path']),source['expected_sha256'])


if __name__ == '__main__': unittest.main()
