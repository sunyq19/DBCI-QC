import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'apps/workbench'), str(ROOT / 'scripts')]
from deployment import deployment, check_request, UploadGuard, DemoCapacityError, homepage
from ephys_qc.admission import DEFAULT_INTAKE_LIMITS, LimitExceeded
from prepare_demo import prepare

SETTINGS = {'deployment': {'mode': 'shared_demo', 'public_origin': 'https://qc.example.org', 'reserve_gib': 2}}


class DeploymentTests(unittest.TestCase):
    def test_local_stays_local(self):
        check_request({}, 8769, {'Host': '127.0.0.1:8769'})
        with self.assertRaises(PermissionError):
            check_request({}, 8769, {'Host': 'qc.example.org'})

    def test_exact_origin_and_host(self):
        check_request(SETTINGS, 8769, {'Host': 'qc.example.org', 'Origin': 'https://qc.example.org'})
        for headers in (
                {'Host': 'qc.example.org.evil.test'},
                {'Host': 'qc.example.org', 'Origin': 'http://qc.example.org'},
                {'Host': 'qc.example.org', 'Origin': 'null'},
                {'Host': 'qc.example.org', 'Sec-Fetch-Site': 'cross-site'},
                {'Host': '127.0.0.1:8769', 'Origin': 'https://qc.example.org'},
                {'Host': 'other', 'X-Forwarded-Host': 'qc.example.org'}):
            with self.subTest(headers=headers), self.assertRaises(PermissionError):
                check_request(SETTINGS, 8769, headers)

    def test_configuration_rejects_ambiguous_addresses(self):
        for origin in ('*', 'https://qc.example.org/', 'https://a@qc.example.org',
                       'https://qc.example.org#', 'https://qc.example.org:99999',
                       'https://qc.example.org\nother', 'https://{host}', 'https://a$b'):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                deployment({'deployment': {'mode': 'shared_demo', 'public_origin': origin}})

    def test_no_disk_or_busy_upload_reads_body(self):
        with tempfile.TemporaryDirectory() as directory:
            guard = UploadGuard(SETTINGS, Path(directory), DEFAULT_INTAKE_LIMITS)
            stream = io.BytesIO(b'body')
            with patch('deployment.shutil.disk_usage') as disk:
                disk.return_value.free = 1
                with self.assertRaises(DemoCapacityError) as error:
                    with guard.accept('x.edf', 4):
                        stream.read()
                self.assertEqual(error.exception.status, 507)
                self.assertEqual(stream.tell(), 0)
                disk.return_value.free = 6 * 1024**3
                with guard.accept('x.zip', 4):
                    with self.assertRaises(DemoCapacityError) as error:
                        with guard.accept('y.edf', 4):
                            stream.read()
                    self.assertEqual(error.exception.status, 429)
                # The lock is released after both capacity and body errors.
                with self.assertRaises(RuntimeError):
                    with guard.accept('x.edf', 4):
                        raise RuntimeError()
                with guard.accept('x.edf', 4):
                    pass
            with self.assertRaises(LimitExceeded):
                with guard.accept('x.edf', 2 * 1024**3 + 1):
                    stream.read()

    def test_zip_reserves_uncompressed_space(self):
        guard = UploadGuard(SETTINGS, ROOT, DEFAULT_INTAKE_LIMITS)
        with patch('deployment.shutil.disk_usage') as disk:
            disk.return_value.free = 3 * 1024**3
            with guard.accept('x.edf', 10):
                pass
            with self.assertRaises(DemoCapacityError):
                with guard.accept('x.zip', 10):
                    pass

    def test_shared_notice_only_in_shared_mode(self):
        original = (ROOT / 'apps/workbench/web/index.html').read_text()
        self.assertEqual(homepage(original, {}), original)
        shared = homepage(original, SETTINGS)
        self.assertIn('data-deployment="shared_demo"', shared)
        self.assertIn('共享演示区', shared)
        self.assertNotIn('质控台 · 本地处理', shared)

    def test_service_config_created_once_and_without_root(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'config'
            settings = prepare('https://qc.example.org', Path(directory) / 'data',
                               output, 'dbciqc', 8769, Path(sys.executable))
            self.assertEqual(settings['inputs'], [])
            self.assertEqual(json.loads((output / 'workbench.json').read_text())['admission_policy'], 'cloud-intake/1.3')
            self.assertIn('User=dbciqc', (output / 'dbci-qc.service').read_text())
            self.assertIn('max_size 2147483648', (output / 'Caddyfile').read_text())
            with self.assertRaises(FileExistsError):
                prepare('https://qc.example.org', Path(directory) / 'data', output, 'dbciqc', 8769, Path(sys.executable))
            with self.assertRaises(ValueError):
                prepare('https://qc.example.org', Path(directory) / 'data', output, 'root', 8769, Path(sys.executable))


if __name__ == '__main__':
    unittest.main()
