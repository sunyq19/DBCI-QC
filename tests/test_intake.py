"""User-submitted files must cross a technical read and an explicit role gate."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
import threading
from http.server import ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'apps/workbench'))
from intake import IntakeStore, MAX_UPLOAD_BYTES, suggestions
from server import Store, Handler


def recording(names=('Cz', 'Pz', 'EOG', 'Temperature'), rates=(100, 100, 100, 1), units=('uV', 'uV', 'uV', 'C')):
    def cell(v, width):
        return str(v).encode('ascii').ljust(width, b' ')
    n, seconds = len(names), 60
    header = b''.join(cell(v, width) for v, width in [
        (0, 8), ('', 80), ('', 80), ('01.01.01', 8), ('00.00.00', 8),
        (256 + n * 256, 8), ('', 44), (seconds, 8), (1, 8), (n, 4)])
    fields = [(16, names), (80, [''] * n), (8, units), (8, [-100] * n), (8, [100] * n),
              (8, [-32768] * n), (8, [32767] * n), (80, [''] * n), (8, rates), (32, [''] * n)]
    return header + b''.join(cell(v, width) for width, values in fields for v in values) + b'\0' * (2 * seconds * sum(rates))


def confirmation(**overrides):
    return {'modality': 'scalp_eeg', 'reference_scheme': 'unknown', 'eeg_indices': [0, 1],
            'reference_indices': {'eog': 2}, 'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'},
            'confirmed': True, **overrides}


class IntakeBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = IntakeStore(self.temp.name)

    def receive(self, data=None, name='sample.edf'):
        data = data if data is not None else recording()
        return self.store.receive(name, len(data), io.BytesIO(data))

    def test_header_read_is_not_role_or_modality_confirmation(self):
        data = recording()
        intake = self.receive(data)
        self.assertEqual(intake['status'], 'needs_confirmation')
        self.assertEqual(intake['sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(intake['metadata']['duration_seconds'], 60)
        self.assertEqual(intake['suggestions']['modality'], 'unknown')
        self.assertEqual(intake['suggestions']['eeg_indices'], [0, 1])
        self.assertEqual(self.store.registered(), [])

    def test_declared_channel_types_are_used_even_with_nonstandard_names(self):
        metadata = {'channels': [
            {'index': 0, 'name': 'sensor-A', 'channel_type': 'eeg', 'unit': 'V', 'sampling_rate_hz': 100},
            {'index': 1, 'name': 'eye-sensor', 'channel_type': 'eog', 'unit': 'V', 'sampling_rate_hz': 100},
            {'index': 2, 'name': 'Cz', 'channel_type': 'mag', 'unit': 'T', 'sampling_rate_hz': 100}]}
        proposal, _ = suggestions(metadata)
        self.assertEqual(proposal['eeg_indices'], [0])
        self.assertEqual(proposal['reference_indices'], {'eog': 1})
        self.assertEqual(proposal['modality'], 'unknown')

    def test_extension_and_directory_name_never_control_storage(self):
        intake = self.receive(name='../../outside.eeg')
        self.assertEqual(intake['filename'], 'outside.eeg')
        self.assertEqual(intake['metadata']['format'], 'EDF')
        self.assertEqual(list(Path(self.temp.name).glob('outside*')), [])
        self.assertTrue((self.store.root / intake['id'] / 'source.edf').is_file())

    def test_iz_midline_electrode_is_suggested_without_matching_unrelated_names(self):
        intake = self.receive(recording(
            names=('Fp1.', 'Cz..', 'Iz..', 'Iz-M2', 'IZZZ', 'Temperature'),
            rates=(100, 100, 100, 100, 100, 1), units=('uV', 'uV', 'uV', 'uV', 'uV', 'C')))
        self.assertEqual(intake['suggestions']['eeg_indices'], [0, 1, 2, 3])
        self.assertEqual(intake['suggestions']['modality'], 'unknown')
        self.assertEqual(self.store.registered(), [])

    def test_fake_edf_and_incomplete_upload_leave_no_registration(self):
        with self.assertRaises(ValueError):
            self.receive(b'not EDF', 'valid.edf')
        with self.assertRaises(ValueError):
            self.store.receive('sample.edf', len(recording()) + 100, io.BytesIO(recording()))
        self.assertEqual(list(self.store.root.iterdir()), [])

    def test_size_limit_is_checked_before_consuming_bytes(self):
        stream = io.BytesIO(b'data')
        with self.assertRaises(ValueError):
            self.store.receive('large.edf', MAX_UPLOAD_BYTES + 1, stream)
        self.assertEqual(stream.tell(), 0)

    def test_confirmation_required_no_remote_paths_or_modality_guess(self):
        intake = self.receive()
        for body in (confirmation(confirmed=False), confirmation(modality='unknown'),
                     confirmation(modality='not_a_modality'), confirmation(source_path='/tmp/elsewhere')):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.store.confirm(intake['id'], body)
        self.assertEqual(self.store.registered(), [])

    def test_non_scalp_is_registered_for_inspection_but_cannot_run_scalp_qc(self):
        from ephys_qc.recommendations import recommend
        from ephys_qc.planning import build_plan
        intake = self.receive()
        record = self.store.confirm(intake['id'], confirmation(modality='seeg'))
        self.assertEqual(record['modality'], 'seeg')
        self.assertEqual(recommend(record)['status'], 'unsupported')
        with self.assertRaises(ValueError):
            build_plan(record)

    def test_nonvoltage_clock_and_duplicate_roles_are_rejected(self):
        intake = self.receive()
        for body in (confirmation(eeg_indices=[0, 3]), confirmation(reference_indices={'eog': 0}),
                     confirmation(reference_indices={'eog': 2, 'ecg': 2}), confirmation(eeg_indices=[0, 0])):
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.store.confirm(intake['id'], body)
        mixed = self.receive(recording(rates=(100, 100, 50, 1)))
        with self.assertRaisesRegex(ValueError, 'sample clock'):
            self.store.confirm(mixed['id'], confirmation())

    def test_confirmed_unknown_reference_stays_ungrouped_and_unlabelled(self):
        intake = self.receive()
        record = self.store.confirm(intake['id'], confirmation())
        self.assertEqual(record['modality'], 'scalp_eeg')
        self.assertIsNone(record['default_config']['method_config']['comparison_groups'])
        self.assertNotIn('annotation', record)
        self.assertFalse(record['preprocessing']['verified'])
        self.assertEqual(record['default_config']['context_tags']['disease'], 'unknown')
        self.assertEqual(record['intake_confirmation']['roles_reference_modality'], 'user_confirmed')

    def test_known_reference_requires_explicit_declaration_and_retains_identity(self):
        intake = self.receive(recording(names=('T8-P8', 'T8-P8', 'EOG', 'Temperature')))
        record = self.store.confirm(intake['id'], confirmation(reference_scheme='linked_ears'))
        self.assertEqual([c['index'] for c in record['metadata']['channels']], [0, 1, 2, 3])
        self.assertEqual(record['default_config']['method_config']['comparison_groups'], ['user_confirmed_reference'] * 2)
        self.assertIn('用户明确声明', record['reference_evidence'])

    def test_identical_confirmation_retry_and_restart_preserve_registered_record(self):
        intake = self.receive()
        first = self.store.confirm(intake['id'], confirmation())
        second = self.store.confirm(intake['id'], confirmation())
        self.assertEqual(first, second)
        reopened = IntakeStore(self.temp.name)
        self.assertEqual(reopened.registered(), [first])
        with self.assertRaises(ValueError):
            reopened.confirm(intake['id'], confirmation(reference_scheme='bipolar'))

    def test_modified_received_copy_cannot_be_confirmed(self):
        intake = self.receive()
        source = self.store.root / intake['id'] / 'source.edf'
        data = bytearray(source.read_bytes())
        data[-1] = 1
        source.write_bytes(data)
        with self.assertRaisesRegex(ValueError, '指纹'):
            self.store.confirm(intake['id'], confirmation())


class IntakeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.store = Store({'python': sys.executable, 'data_dir': cls.temp.name, 'inputs': [], 'profiles': []})
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)
        cls.temp.cleanup()

    def post(self, path, data, headers=None):
        request = urllib.request.Request(self.url + path, data=data, headers=headers or {'Content-Type': 'application/json'})
        try:
            response = self.opener.open(request, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        return response.status, json.load(response)

    def test_intake_confirm_recommend_does_not_create_a_job(self):
        status, data = self.post('/api/v1/intakes', recording(), {'Content-Type': 'application/octet-stream', 'X-Filename': 'sample.edf'})
        self.assertEqual(status, 201)
        status, registered = self.post(f"/api/v1/intakes/{data['id']}/confirm", json.dumps(confirmation()).encode())
        self.assertEqual(status, 200)
        self.assertNotIn('source_path', registered['input'])
        status, result = self.post('/api/v1/recommend', json.dumps({'input_id': registered['input']['id']}).encode())
        self.assertEqual(status, 200)
        self.assertTrue(result['can_apply'])
        self.assertEqual(self.server.store.jobs, {})

    def test_cross_site_upload_rejected_before_receiving_file(self):
        before = len(list(self.server.store.intakes.root.iterdir()))
        status, _ = self.post('/api/v1/intakes', recording(), {'Content-Type': 'application/octet-stream', 'X-Filename': 'x.edf', 'Origin': 'https://elsewhere.example'})
        self.assertEqual(status, 403)
        self.assertEqual(len(list(self.server.store.intakes.root.iterdir())), before)

    def test_upload_does_not_accept_server_paths_or_json_files(self):
        status, _ = self.post('/api/v1/intakes', b'{"path":"/etc/passwd"}')
        self.assertEqual(status, 400)


if __name__ == '__main__':
    unittest.main()
