"""Unified record access and neutral workflow documents do not select algorithms."""
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'apps/workbench')]
from server import Handler
from standards_page import render_standards, safe_url


class UnifiedWorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inputs = {}
        for modality in ('scalp_eeg', 'ecog', 'seeg'):
            inputs[modality] = {'id': modality, 'label': modality, 'modality': modality,
                'source_path': '/private/not-for-list.fif', 'expected_sha256': '0' * 64,
                'metadata': {'format': 'FIF', 'duration_seconds': 1,
                    'channels': [{'index': 0, 'name': 'C1', 'unit': 'V', 'sampling_rate_hz': 1000}]},
                'default_config': {'selection': {'eeg_indices': [0], 'reference_indices': {},
                    'start_seconds': 0, 'duration_seconds': 1}}}
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.server.store = SimpleNamespace(lock=threading.RLock(), inputs=inputs, jobs={})
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(2)

    def get(self, path):
        try:
            response = self.opener.open(self.base + path, timeout=5)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.read()

    def test_record_listing_includes_all_modalities_without_private_source_or_job(self):
        status, data = self.get('/api/v1/inputs')
        self.assertEqual(status, 200)
        records = json.loads(data)['inputs']
        self.assertEqual({r['modality'] for r in records}, {'scalp_eeg', 'ecog', 'seeg'})
        self.assertTrue(all('source_path' not in r for r in records))
        self.assertEqual(self.server.store.jobs, {})
        self.assertEqual(self.get('/api/v1/inputs?modality=ecog')[0], 400)

    def test_neutral_documents_return_to_unified_entry_and_preserve_language(self):
        for prefix, directory, lang in [('', 'docs', 'zh-CN'), ('/en', 'docs/en', 'en')]:
            status, raw = self.get(prefix + '/standards/overview')
            self.assertEqual(status, 200)
            page = raw.decode()
            self.assertIn('<html lang="' + lang + '">', page)
            self.assertIn('href="' + prefix + '/standards/ecog"', page)
            self.assertIn('href="' + prefix + '/standards"', page)
            self.assertNotIn('/standards/overview/modules/', page)
            self.assertNotIn('href="/?modality=', page)
            self.assertIn('href="/en/standards/overview"', page)
            self.assertIn('href="/standards/overview"', page)
            self.assertEqual(self.get(prefix + '/standards/overview.md')[1],
                             (REPO / directory / 'workflow-standards.md').read_bytes())

    def test_neutral_document_routes_do_not_allow_arbitrary_path_or_module(self):
        self.assertEqual(safe_url('/standards/overview'), '/standards/overview')
        self.assertIsNone(safe_url('/standards/overview/../../secret'))
        with self.assertRaises(ValueError):
            render_standards('# Test', 'M03', modality='overview')
        self.assertEqual(self.get('/standards/overview/modules/M03')[0], 404)


if __name__ == '__main__':
    unittest.main()
