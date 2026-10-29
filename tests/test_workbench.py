"""Reader corruption and local HTTP boundaries; no algorithm accuracy claim."""
from pathlib import Path
import importlib.util
import json
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from input_config import edf_metadata
from server import Handler, SERVICE


def edf_bytes(records=2, unknown_records=False, annotation=False):
    def cell(value, size):
        return str(value).encode('ascii').ljust(size, b' ')
    n = 2 if annotation else 1
    head = b''.join([cell(0, 8), cell('', 80), cell('', 80), cell('01.01.01', 8), cell('00.00.00', 8),
                     cell(256 + n * 256, 8), cell('EDF+C' if annotation else '', 44),
                     cell(-1 if unknown_records else records, 8), cell(1, 8), cell(n, 4)])
    rows = [(16, ['Cz', 'EDF Annotations']), (80, ['', '']), (8, ['uV', '']),
            (8, [-100, -1]), (8, [100, 1]), (8, [-32768, -32768]),
            (8, [32767, 32767]), (80, ['', '']), (8, [4, 4]), (32, ['', ''])]
    block = b''.join(cell(v, size) for size, values in rows for v in values[:n])
    return head + block + b'\0' * (records * n * 4 * 2)


def interleaved_annotation_edf():
    """Valid EDF+C: Cz, timekeeping TAL, Pz; distinct calibrated voltages."""
    def cell(value, width):
        return str(value).encode('ascii').ljust(width, b' ')
    head = b''.join(cell(value, width) for value, width in [
        (0, 8), ('', 80), ('', 80), ('01.01.01', 8), ('00.00.00', 8),
        (1024, 8), ('EDF+C', 44), (2, 8), (1, 8), (3, 4)])
    fields = [(16, ['Cz', 'EDF Annotations', 'Pz']), (80, ['', '', '']),
              (8, ['uV', '', 'uV']), (8, [-32768, -1, -32768]),
              (8, [32767, 1, 32767]), (8, [-32768, -32768, -32768]),
              (8, [32767, 32767, 32767]), (80, ['', '', '']),
              (8, [100, 32, 100]), (32, ['', '', ''])]
    signal_header = b''.join(cell(v, width) for width, values in fields for v in values)
    payload = []
    for second in range(2):
        payload.extend([struct.pack('<100h', *([100 + second] * 100)),
                        (f'+{second}'.encode('ascii') + b'\x14\x14\0').ljust(64, b'\0'),
                        struct.pack('<100h', *([200 + second] * 100))])
    return head + signal_header + b''.join(payload)


class EDFBoundaryTests(unittest.TestCase):
    def parse(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.edf'
            path.write_bytes(data)
            return edf_metadata(path)

    def test_annotation_is_not_an_eeg_signal_and_keeps_raw_identity(self):
        data = self.parse(edf_bytes(annotation=True))
        self.assertEqual(data['raw_signal_count'], 2)
        self.assertEqual(data['annotation_signal_count'], 1)
        self.assertEqual(len(data['channels']), 1)
        self.assertEqual(data['channels'][0]['raw_index'], 0)
        self.assertEqual(data['channels'][0]['unit'], 'uV')

    def test_interleaved_annotation_preserves_noncontiguous_source_indices(self):
        data = self.parse(interleaved_annotation_edf())
        self.assertEqual(data['raw_signal_count'], 3)
        self.assertEqual(data['annotation_signal_count'], 1)
        self.assertEqual([c['index'] for c in data['channels']], [0, 2])
        self.assertEqual([c['raw_index'] for c in data['channels']], [0, 2])
        self.assertEqual([c['name'] for c in data['channels']], ['Cz', 'Pz'])

    @unittest.skipUnless(importlib.util.find_spec('brainelecqc') is not None and
                         importlib.util.find_spec('numpy') is not None,
                         'Dedicated scientific environment required for actual reader')
    def test_selected_source_index_two_reads_third_edf_signal_in_volts(self):
        import numpy as np
        from brainelecqc.readers.edf import EdfBdfReader
        from ephys_qc.runtime import _read_window
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'interleaved.edf'
            original = interleaved_annotation_edf()
            path.write_bytes(original)
            metadata = edf_metadata(path)
            self.assertEqual([c['index'] for c in metadata['channels']], [0, 2])
            reader = EdfBdfReader(path, 'interleaved')
            state = {'reader': reader, 'description': reader.describe()}
            config = {'selection': {'eeg_indices': [2], 'reference_indices': {},
                                    'start_seconds': 0, 'duration_seconds': 2},
                      'method_config': {'comparison_groups': None}}
            payload = _read_window(state, config)
            self.assertEqual(state['data'].shape, (1, 200))
            self.assertEqual(payload['recording']['source_indices'], [2])
            self.assertEqual(state['channels'][0]['channel_id'], 'interleaved:ch:2')
            self.assertEqual(state['channels'][0]['raw_name'], 'Pz')
            expected = np.repeat([200e-6, 201e-6], 100)
            np.testing.assert_allclose(state['data'][0], expected, rtol=0, atol=1e-15)
            self.assertGreater(float(state['data'].min()), 150e-6)
            self.assertEqual(path.read_bytes(), original)

    def test_unknown_record_count_is_derived_only_from_complete_payload(self):
        data = self.parse(edf_bytes(unknown_records=True))
        self.assertEqual(data['duration_seconds'], 2)
        with self.assertRaises(ValueError):
            self.parse(edf_bytes(unknown_records=True)[:-1])

    def test_truncated_or_extra_payload_rejected(self):
        for data in (edf_bytes()[:-1], edf_bytes()[:-8], edf_bytes() + b'\0' * 8):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                self.parse(data)

    def test_discontinuous_edf_is_not_silently_treated_as_continuous(self):
        data = bytearray(edf_bytes())
        data[192:197] = b'EDF+D'
        with self.assertRaises(ValueError):
            self.parse(data)


class LocalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def get(self, headers=None, path='/api/v1/health'):
        req = urllib.request.Request(self.url + path, headers=headers or {})
        try:
            response = self.opener.open(req, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        return response.status, response.headers, json.load(response)

    def test_health_is_available_locally(self):
        status, headers, data = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(data['service'], SERVICE)
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_foreign_webpage_cannot_access_api(self):
        for headers in ({'Origin': 'https://example.com'}, {'Host': 'example.com'}, {'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.get(headers)[0], 403)

    def test_unknown_file_route_does_not_expose_source(self):
        self.assertEqual(self.get(path='/.local/workbench.json')[0], 404)
        self.assertEqual(self.get(path='/../server.py')[0], 404)


if __name__ == '__main__':
    unittest.main()
