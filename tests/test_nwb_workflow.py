"""NWB intake and frozen-stream integration, using generated PyNWB files.

These fixtures test routing, source identity and physical-value preservation.
They do not represent independent physiological data or detector accuracy.
No download, production service, browser, or external analysis job is used.
"""
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'apps/workbench')]
from intake import IntakeStore
from server import Handler, Store
from ephys_qc.planning import build_plan
from ephys_qc.runtime import execute
from review_workspace import ReviewWorkspace, waveform_for_input

HAVE_PYNWB = all(importlib.util.find_spec(name) is not None for name in ('numpy', 'pynwb', 'h5py'))
HAVE_SCIENCE = HAVE_PYNWB and importlib.util.find_spec('scipy') is not None
FIRST = '/acquisition/first'
SECOND = '/processing/ecephys/LFP/second'


def make_nwb(path):
    """Distinct clocks, dimensions and values make implicit first-stream use fail."""
    import numpy as np
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries, LFP
    nwb = NWBFile('Generated integration fixture, not physiological evidence',
                  'nwb-workflow-fixture', datetime(2026, 1, 1, tzinfo=timezone.utc))
    device = nwb.create_device('cortical-array', description='Generated fixture device')
    group = nwb.create_electrode_group('cortical', 'Generated contacts', 'cortex', device)
    nwb.add_electrode_column('channel_type', 'Explicit fixture signal type')
    nwb.add_electrode_column('channel_name', 'Original fixture channel name')
    for index in range(3):
        nwb.add_electrode(id=100 + index, x=float(index), y=0., z=0., imp=float('nan'),
                          location='cortex', filtering='unknown', group=group,
                          channel_type='ecog', channel_name=f'contact-{index}')
    first_values = np.full((800, 1), .002, dtype=np.float64)
    second_values = np.column_stack((np.arange(1200, dtype=np.float64) * 1e-8 + 5e-6,
                                    np.full(1200, -11e-6, dtype=np.float64)))
    nwb.add_acquisition(ElectricalSeries(name='first', data=first_values,
        electrodes=nwb.create_electrode_table_region([1], 'First signal mapping'),
        starting_time=0., rate=200., filtering='unknown'))
    lfp = LFP(name='LFP')
    nwb.create_processing_module('ecephys', 'Generated processing container').add(lfp)
    lfp.add_electrical_series(ElectricalSeries(name='second', data=second_values,
        electrodes=nwb.create_electrode_table_region([2, 0], 'Reordered second signal mapping'),
        starting_time=42.5, rate=100., filtering='unknown'))
    nwb.add_unit(id=0, spike_times=np.array([.5, 1.25]))
    with NWBHDF5IO(str(path), 'w') as handle:
        handle.write(nwb)
    return second_values.T


def confirmation(stream_id=SECOND, **overrides):
    return {'modality': 'ecog', 'reference_scheme': 'unknown', 'eeg_indices': [0, 1],
            'reference_indices': {}, 'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'},
            'confirmed': True, 'selected_stream_id': stream_id, **overrides}


def request(record, **config):
    plan = build_plan(record, ['M03'], config)
    return {'input': copy.deepcopy(record), 'plan': plan, 'qc_config': plan['qc_config'],
            'selected_modules': plan['selected_modules']}


def save_request(root, value):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'request.json').write_text(json.dumps(value), encoding='utf-8')


@unittest.skipUnless(HAVE_PYNWB, 'PyNWB, h5py and NumPy are required for NWB integration')
class NWBWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_temp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.fixture_temp.name) / 'multistream.nwb'
        cls.expected = make_nwb(cls.source)
        cls.data = cls.source.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixture_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = IntakeStore(self.root / 'intakes')

    def receive(self):
        return self.store.receive('multistream.nwb', len(self.data), io.BytesIO(self.data))

    def registered(self):
        intake = self.receive()
        selected = self.store.select_stream(intake['id'], {'stream_id': SECOND})
        return self.store.confirm(intake['id'], confirmation()), selected

    def assert_waveform(self, wave, start=0., duration=1.):
        import numpy as np
        self.assertEqual(wave['sampling_rate_hz'], 100.)
        self.assertEqual(wave['stream_id'], SECOND)
        self.assertTrue(wave['frozen_source_verified'])
        self.assertEqual([row['source_index'] for row in wave['channels']], [0, 1])
        first, stop = round(start * 100), round((start + duration) * 100)
        for index, channel in enumerate(wave['channels']):
            self.assertEqual(channel['physical_unit'], 'V')
            np.testing.assert_array_equal(channel['source_samples'], np.arange(first, stop))
            np.testing.assert_allclose(channel['times_seconds'], np.arange(first, stop) / 100., rtol=0, atol=1e-14)
            np.testing.assert_allclose(channel['values'], self.expected[index, first:stop] * 1e6, rtol=1e-14, atol=1e-12)

    def test_multistream_upload_is_unselected_and_cannot_confirm(self):
        intake = self.receive()
        self.assertEqual(intake['status'], 'needs_confirmation')
        self.assertIsNone(intake['metadata']['selected_stream_id'])
        self.assertEqual(intake['metadata']['channels'], [])
        available = {row['stream_id'] for row in intake['metadata']['available_streams'] if row['status'] == 'available'}
        self.assertEqual(available, {FIRST, SECOND})
        self.assertEqual(intake['suggestions']['eeg_indices'], [])
        self.assertEqual(intake['metadata']['nwb']['units_count'], 1)
        self.assertTrue(intake['metadata']['nwb']['units_present'])
        with self.assertRaises(ValueError):
            self.store.confirm(intake['id'], confirmation())
        self.assertEqual(self.store.registered(), [])

    def test_select_second_preserves_native_clock_mapping_and_unconfirmed_roles(self):
        intake = self.receive()
        selected = self.store.select_stream(intake['id'], {'stream_id': SECOND})
        self.assertEqual(selected['metadata']['selected_stream_id'], SECOND)
        self.assertEqual(selected['status'], 'needs_confirmation')
        self.assertGreater(selected['selection_revision'], intake['selection_revision'])
        self.assertEqual(selected['metadata']['duration_seconds'], 12.)
        self.assertEqual([row['sampling_rate_hz'] for row in selected['metadata']['channels']], [100., 100.])
        self.assertEqual(selected['suggestions']['eeg_indices'], [0, 1])
        self.assertEqual(selected['suggestions']['reference_indices'], {})
        # A non-standard custom electrode column is not anatomical evidence.
        self.assertEqual(selected['suggestions']['modality'], 'unknown')
        self.assertEqual(selected['suggestions']['modality_evidence']['status'], 'unknown')
        channels = selected['metadata']['channels']
        self.assertEqual([row['electrode_row_index'] for row in channels], [2, 0])
        self.assertEqual([row['electrode_id'] for row in channels], [102, 100])
        self.assertEqual([row['name'] for row in channels], ['contact-2', 'contact-0'])
        self.assertEqual(self.store.registered(), [])
        self.assertEqual(self.store.get(intake['id'])['metadata']['selected_stream_id'], SECOND)

    def test_unknown_units_and_extra_selection_fields_are_rejected_without_state_change(self):
        intake = self.receive()
        for body in ({'stream_id': '/not-a-stream'}, {'stream_id': '/units'}, {'stream_id': FIRST, 'confirmed': True}):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.store.select_stream(intake['id'], body)
        self.assertIsNone(self.store.get(intake['id'])['metadata']['selected_stream_id'])
        self.assertEqual(self.store.registered(), [])

    def test_stale_or_missing_stream_confirmation_is_rejected(self):
        intake = self.receive()
        self.store.select_stream(intake['id'], {'stream_id': FIRST})
        self.store.select_stream(intake['id'], {'stream_id': SECOND})
        missing = confirmation(); missing.pop('selected_stream_id')
        for body in (missing, confirmation(FIRST)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.store.confirm(intake['id'], body)
        self.assertEqual(self.store.registered(), [])
        record = self.store.confirm(intake['id'], confirmation())
        self.assertEqual(record['metadata']['selected_stream_id'], SECOND)

    def test_registered_stream_is_immutable_and_identical_confirmation_is_idempotent(self):
        record, intake = self.registered()
        before = json.dumps(record, sort_keys=True)
        with self.assertRaises(ValueError):
            self.store.select_stream(intake['id'], {'stream_id': FIRST})
        self.assertEqual(self.store.confirm(intake['id'], confirmation()), record)
        self.assertEqual(json.dumps(self.store.registered()[0], sort_keys=True), before)

    def test_source_change_blocks_selection_and_confirmation(self):
        for operation in ('select', 'confirm'):
            with self.subTest(operation=operation):
                intake = self.receive()
                if operation == 'confirm':
                    intake = self.store.select_stream(intake['id'], {'stream_id': SECOND})
                source = self.store.root / intake['id'] / intake['entry_file']
                with source.open('ab') as handle:
                    handle.write(b'changed-source')
                with self.assertRaisesRegex(ValueError, '指纹'):
                    if operation == 'select':
                        self.store.select_stream(intake['id'], {'stream_id': SECOND})
                    else:
                        self.store.confirm(intake['id'], confirmation())
        self.assertEqual(self.store.registered(), [])

    def test_plan_freezes_second_stream_and_refuses_a_different_stream(self):
        record, _ = self.registered()
        plan = build_plan(record, ['M03'])
        self.assertEqual(record['default_config']['selection']['stream_id'], SECOND)
        self.assertEqual(plan['qc_config']['selection']['stream_id'], SECOND)
        self.assertEqual(plan['input_metadata']['selected_stream_id'], SECOND)
        with self.assertRaises(ValueError):
            build_plan(record, ['M03'], {'selection': {'stream_id': FIRST}})
        whole = build_plan(record, ['M03'], {'scope': 'recording', 'recording_options': {'window_seconds': 5}})
        from ephys_qc.whole_record import window_config
        for window in whole['windows']:
            self.assertEqual(window_config(whole, window)['selection']['stream_id'], SECOND)

    def test_registered_input_preview_reads_second_stream_physical_samples(self):
        record, _ = self.registered()
        self.assert_waveform(waveform_for_input(record, 1., 1., [0, 1]), 1., 1.)
        conflicting = copy.deepcopy(record['default_config']['selection'])
        conflicting['stream_id'] = FIRST
        with self.assertRaises(ValueError):
            waveform_for_input(record, 1., 1., [0, 1], selection=conflicting)

    @unittest.skipUnless(HAVE_SCIENCE, 'SciPy is required for actual runtime integration')
    def test_runtime_and_job_review_use_the_frozen_second_stream(self):
        import numpy as np
        record, _ = self.registered()
        req = request(record, selection={'start_seconds': 1., 'duration_seconds': 2.})
        job = self.root / 'window-job'; save_request(job, req)
        result = execute(req, job, lambda *args: None)
        self.assertNotEqual(result['status'], 'failed', result)
        self.assertFalse(any(row['status'] == 'failed' for row in result['modules']), result['modules'])
        expected_hash = hashlib.sha256(np.ascontiguousarray(self.expected[:, 100:300], dtype='<f8').tobytes()).hexdigest()
        self.assertEqual(result['data_sha256'], expected_hash)
        self.assertEqual(result['recording']['sampling_rate_hz'], 100.)
        evidence = json.loads((job / 'artifacts/M02_selection.json').read_text())
        self.assertEqual(evidence['selection']['stream_id'], SECOND)
        self.assertEqual(evidence['recording']['source_indices'], [0, 1])
        self.assert_waveform(ReviewWorkspace(job).waveform(1., 1., [0, 1]), 1., 1.)

    @unittest.skipUnless(HAVE_SCIENCE, 'SciPy is required for actual whole-record integration')
    def test_whole_record_children_and_review_never_revert_to_first_stream(self):
        import numpy as np
        record, _ = self.registered()
        req = request(record, scope='recording', recording_options={'window_seconds': 5})
        job = self.root / 'whole-job'; save_request(job, req)
        result = execute(req, job, lambda *args: None)
        self.assertNotEqual(result['status'], 'failed', result)
        self.assertEqual(len(result['windows']), 3)
        for window in result['windows']:
            self.assertNotEqual(window['status'], 'failed', window)
            child = job / 'windows' / window['id']
            frozen = json.loads((child / 'request.json').read_text())
            observed = json.loads((child / 'result.json').read_text())
            self.assertEqual(frozen['qc_config']['selection']['stream_id'], SECOND)
            self.assertEqual(frozen['input']['metadata']['selected_stream_id'], SECOND)
            first, stop = window['start_sample'], window['stop_sample']
            expected_hash = hashlib.sha256(np.ascontiguousarray(self.expected[:, first:stop], dtype='<f8').tobytes()).hexdigest()
            self.assertEqual(observed['data_sha256'], expected_hash)
            self.assertEqual(observed['recording']['sampling_rate_hz'], 100.)
        self.assert_waveform(ReviewWorkspace(job).waveform(10., 1., [0, 1]), 10., 1.)

    @unittest.skipUnless(HAVE_SCIENCE, 'SciPy is required for actual Neuropixels integration')
    def test_explicit_neuropixels_model_recommends_and_reports_voltage_profile(self):
        from test_nwb_reader import nwb_fixture
        from ephys_qc.recommendations import recommend
        path = self.root / 'declared-probe.nwb'
        nwb_fixture(path, neuropixels=True, units=True)
        data = path.read_bytes()
        intake = self.store.receive(path.name, len(data), io.BytesIO(data))
        self.assertEqual(intake['metadata']['selected_stream_id'], '/acquisition/voltage')
        self.assertEqual(intake['suggestions']['modality'], 'extracellular')
        self.assertTrue(intake['metadata']['acquisition']['neuropixels_device_declared'])
        record = self.store.confirm(intake['id'], confirmation('/acquisition/voltage', modality='extracellular'))
        recommendation = recommend(record)
        self.assertTrue(recommendation['can_apply'], recommendation)
        plan = build_plan(record, recommendation['selected_modules'], recommendation['qc_config'])
        self.assertEqual(plan['analysis_profile'], 'neuropixels-voltage/2')
        req = {'input': record, 'plan': plan, 'qc_config': plan['qc_config'], 'selected_modules': plan['selected_modules']}
        job = self.root / 'probe-job'; save_request(job, req)
        result = execute(req, job, lambda *args: None)
        self.assertIn(result['status'], ('completed', 'partial'), result)
        self.assertFalse(any(row['status'] == 'failed' for row in result['modules']), result['modules'])
        self.assertEqual(result['analysis_profile'], 'neuropixels-voltage/2')
        self.assertIsNone(result['score']['value'])
        self.assertTrue((job / result['report_path']).is_file())
        self.assertEqual(result['input_metadata']['nwb']['units_count'], 2)

    def test_missing_neuropixels_model_cannot_be_overridden_by_route_or_filename(self):
        from test_nwb_reader import nwb_fixture
        path = self.root / 'Neuropixels_named_without_device_evidence.nwb'
        nwb_fixture(path, neuropixels=False)
        data = path.read_bytes()
        intake = self.store.receive(path.name, len(data), io.BytesIO(data))
        self.assertFalse(intake['metadata']['acquisition']['neuropixels_device_declared'])
        self.assertEqual(intake['suggestions']['modality'], 'unknown')
        with self.assertRaisesRegex(ValueError, 'Neuropixels'):
            self.store.confirm(intake['id'], confirmation('/acquisition/voltage', modality='extracellular'))
        self.assertEqual(self.store.registered(), [])

    def test_toolkit_stream_argument_freezes_selection_without_a_web_registry(self):
        from ephys_qc.toolkit import prepare_recording, build_plan as toolkit_plan
        config = {'selection': {'eeg_indices': [0, 1], 'reference_indices': {}, 'start_seconds': 1., 'duration_seconds': 2.}}
        record = prepare_recording(self.source, record_id='standalone-nwb', modality='ecog', qc_config=config, stream_id=SECOND)
        self.assertEqual(record['metadata']['selected_stream_id'], SECOND)
        self.assertEqual(record['expected_sha256'], hashlib.sha256(self.data).hexdigest())
        self.assertEqual(toolkit_plan(record, ['M03'])['qc_config']['selection']['stream_id'], SECOND)
        self.assertNotIn('stream_id', config['selection'])  # caller config is unchanged
        with self.assertRaises(ValueError):
            prepare_recording(self.source, record_id='missing-stream', modality='ecog', qc_config=config)
        with self.assertRaises(ValueError):
            prepare_recording(self.source, record_id='wrong-stream', modality='ecog', qc_config=config, stream_id='/missing')
        with self.assertRaisesRegex(ValueError, 'Neuropixels'):
            prepare_recording(self.source, record_id='unverified-probe', modality='extracellular', qc_config=config, stream_id=SECOND)

    @unittest.skipUnless(HAVE_SCIENCE, 'SciPy is required for actual CLI execution')
    def test_cli_inspect_prepare_stream_and_run_preserve_second_stream(self):
        config = self.root / 'qc-config.json'
        config.write_text(json.dumps({'selection': {'eeg_indices': [0, 1], 'reference_indices': {},
                                                   'start_seconds': 1., 'duration_seconds': 2.}}))
        record_path = self.root / 'prepared.json'
        environment = dict(os.environ, PYTHONPATH=str(REPO / 'src'))
        def cli(*arguments):
            return subprocess.run([sys.executable, '-m', 'ephys_qc', *map(str, arguments)], cwd=self.root,
                                  env=environment, capture_output=True, text=True, timeout=30)
        inspect = cli('inspect', self.source)
        self.assertEqual(inspect.returncode, 0, inspect.stderr)
        self.assertIsNone(json.loads(inspect.stdout)['selected_stream_id'])
        inspect_second = cli('inspect', self.source, '--stream', SECOND)
        self.assertEqual(inspect_second.returncode, 0, inspect_second.stderr)
        self.assertEqual(json.loads(inspect_second.stdout)['selected_stream_id'], SECOND)
        missing = cli('prepare', self.source, '--id', 'cli-nwb', '--modality', 'ecog', '--config', config, '--output', record_path)
        self.assertEqual(missing.returncode, 2, missing.stderr)
        self.assertFalse(record_path.exists())
        prepared = cli('prepare', self.source, '--stream', SECOND, '--id', 'cli-nwb', '--modality', 'ecog',
                       '--config', config, '--output', record_path)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        self.assertEqual(json.loads(prepared.stdout)['metadata']['selected_stream_id'], SECOND)
        plan = cli('plan', '--record', record_path, '--modules', 'M03')
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)['qc_config']['selection']['stream_id'], SECOND)
        result = cli('run', '--record', record_path, '--modules', 'M03', '--output', self.root / 'cli-job')
        self.assertEqual(result.returncode, 0, result.stderr)
        observed = json.loads(result.stdout)
        self.assertEqual(observed['qc_config']['selection']['stream_id'], SECOND)
        self.assertEqual(observed['recording']['sampling_rate_hz'], 100.)
        self.assertFalse(any(row['status'] == 'failed' for row in observed['modules']))

    def test_real_http_stream_and_confirmation_contract_does_not_start_jobs(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.store = Store({'python': sys.executable, 'data_dir': str(self.root / 'http'), 'inputs': [], 'profiles': []})
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f'http://127.0.0.1:{server.server_port}'
        def post(route, body, binary=False):
            data = body if binary else json.dumps(body).encode()
            headers = {'Content-Type': 'application/octet-stream', 'X-Filename': 'fixture.nwb'} if binary else {'Content-Type': 'application/json'}
            try:
                response = opener.open(urllib.request.Request(base + route, data=data, headers=headers), timeout=15)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)
        try:
            status, intake = post('/api/v1/intakes', self.data, True); self.assertEqual(status, 201, intake)
            path = f"/api/v1/intakes/{intake['id']}"
            self.assertEqual(post(path + '/confirm', confirmation())[0], 400)
            self.assertEqual(post(path + '/stream', {'stream_id': '/units'})[0], 400)
            status, selected = post(path + '/stream', {'stream_id': SECOND}); self.assertEqual(status, 200, selected)
            self.assertEqual(selected['metadata']['selected_stream_id'], SECOND)
            self.assertEqual(post(path + '/confirm', confirmation(FIRST))[0], 400)
            status, registered = post(path + '/confirm', confirmation()); self.assertEqual(status, 200, registered)
            self.assertNotIn('source_path', registered['input'])
            self.assertEqual(registered['input']['default_config']['selection']['stream_id'], SECOND)
            self.assertEqual(post(path + '/stream', {'stream_id': FIRST})[0], 400)
            status, plan = post('/api/v1/plan', {'input_id': registered['input']['id'], 'selected_modules': ['M03']})
            self.assertEqual(status, 200, plan)
            self.assertEqual(plan['qc_config']['selection']['stream_id'], SECOND)
            self.assertEqual(server.store.jobs, {})
        finally:
            server.shutdown(); server.server_close(); thread.join(2)


if __name__ == '__main__':
    unittest.main()
