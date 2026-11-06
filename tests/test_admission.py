"""Intake limits: real filesystem sizes, companion totals and no rejected jobs."""
from dataclasses import replace
import io
import http.client
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'apps/workbench')]
from ephys_qc.admission import CLOUD_INTAKE_V1, CLOUD_INTAKE_V1_1, CLOUD_INTAKE_V1_2, DEFAULT_INTAKE_LIMITS as POLICY, LimitExceeded, configured_policy, check_record_paths
from ephys_qc.dataset_qc.admission import check_dataset_snapshot, scan_snapshot, assert_snapshot_unchanged
from intake import IntakeStore
from package_jobs import PackageJobs, fingerprint
from server import Store
from test_workbench import edf_bytes
import test_dataset_consistency as fixtures


class LimitTests(unittest.TestCase):
    def test_all_fixed_limits_include_boundary_and_reject_one_over(self):
        for field, boundary in [('file_bytes', 2147483648), ('record_bytes', 2147483648),
                                ('dataset_bytes', 10737418240), ('records', 100), ('files', 5000)]:
            with self.subTest(field=field):
                POLICY.check(field, boundary, field)
                with self.assertRaises(LimitExceeded) as caught:
                    POLICY.check(field, boundary + 1, field)
                self.assertEqual(caught.exception.payload()['observed'], boundary + 1)
                self.assertEqual(caught.exception.payload()['limit'], boundary)
        for value in (-1, True, 1.5, '1', None):
            with self.assertRaises(ValueError): POLICY.check('files', value, 'files')

    def test_policy_does_not_enable_cloud_or_restrict_local_cli(self):
        self.assertIsNone(configured_policy({}))
        self.assertIs(configured_policy({'admission_policy': POLICY.version}), POLICY)
        self.assertEqual(POLICY.version, 'cloud-intake/1.3')
        old = configured_policy({'admission_policy': 'cloud-intake/1.0'})
        self.assertIs(old, CLOUD_INTAKE_V1)
        self.assertEqual(old.max_file_bytes, 536870912)
        self.assertIs(configured_policy({'admission_policy': 'cloud-intake/1.1'}), CLOUD_INTAKE_V1_1)
        self.assertEqual(CLOUD_INTAKE_V1_1.max_file_bytes, 1073741824)
        for name in ('cloud', None, {}, 'cloud-intake/2'):
            with self.assertRaises(ValueError): configured_policy({'admission_policy': name})

    def test_record_companions_are_summed_once_using_actual_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp) / 'a.eeg', Path(temp) / 'a.vmrk'
            with a.open('wb') as stream: stream.truncate(POLICY.max_record_bytes - 1)
            b.write_bytes(b'0')
            self.assertEqual(check_record_paths([a, b, a])['record_bytes'], POLICY.max_record_bytes)
            b.write_bytes(b'00')
            with self.assertRaises(LimitExceeded) as caught: check_record_paths([a, b])
            self.assertEqual(caught.exception.field, 'record_bytes')

    def test_upload_rejects_before_consuming_or_registering_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            store = IntakeStore(temp); stream = io.BytesIO(b'not consumed')
            with self.assertRaises(LimitExceeded): store.receive('large.edf', POLICY.max_file_bytes + 1, stream)
            self.assertEqual(stream.tell(), 0)
            self.assertEqual(list(store.root.iterdir()), [])

    def test_compressed_size_cannot_hide_expanded_record_limit(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('sample.edf', edf_bytes())
            archive.writestr('notes.txt', 'a' * 4096)
        with tempfile.TemporaryDirectory() as temp:
            store = IntakeStore(temp, limits=replace(POLICY, max_record_bytes=2048))
            self.assertLess(len(data.getvalue()), 2048)
            with self.assertRaises(LimitExceeded): store.receive('sample.zip', len(data.getvalue()), io.BytesIO(data.getvalue()))
            self.assertEqual(list(store.root.iterdir()), [])

    def test_nested_archives_not_silently_accepted(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('sample.edf', edf_bytes())
            archive.writestr('extra.zip', b'payload')
        with tempfile.TemporaryDirectory() as temp:
            store = IntakeStore(temp)
            with self.assertRaisesRegex(ValueError, '嵌套'):
                store.receive('sample.zip', len(data.getvalue()), io.BytesIO(data.getvalue()))
            self.assertEqual(list(store.root.iterdir()), [])


class DatasetAdmissionTests(unittest.TestCase):
    setUp = fixtures.DatasetTests.setUp
    freeze = fixtures.DatasetTests.freeze

    def test_real_headers_and_metadata_companions_are_counted(self):
        result = check_dataset_snapshot(self.root, self.plan)
        self.assertEqual(result['files'], len(self.plan['files']))
        self.assertEqual(result['records'], 4)
        self.assertTrue(all(r['basis'] == 'reader_verified' for r in result['record_sizes']))
        self.assertGreater(result['record_sizes'][0]['size_bytes'], len(edf_bytes()))
        self.assertEqual(result['dataset_bytes'], sum(p.stat().st_size for p in self.root.iterdir()))

    def test_claimed_sizes_and_manifest_omissions_do_not_bypass_limit(self):
        path = self.root / 'unlisted.bin'
        with path.open('wb') as stream: stream.truncate(POLICY.max_file_bytes + 1)
        for item in self.plan['files']: item['size_bytes'] = 0
        with patch('ephys_qc.dataset_qc.admission.inspect_recording') as reader:
            with self.assertRaises(LimitExceeded) as caught: check_dataset_snapshot(self.root, self.plan)
            reader.assert_not_called()
        self.assertEqual(caught.exception.field, 'file_bytes')

    def test_total_actual_dataset_bytes_even_with_small_individual_files(self):
        # Sparse files exercise the exact 10 GiB boundary without allocating 10 GiB.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for i, size in enumerate([2 * 1024**3] * 5):
                with (root / str(i)).open('wb') as stream: stream.truncate(size)
            self.assertEqual(scan_snapshot(root)[2], POLICY.max_dataset_bytes)
            (root / 'extra').write_bytes(b'x')
            with self.assertRaises(LimitExceeded) as caught: scan_snapshot(root)
            self.assertEqual(caught.exception.field, 'dataset_bytes')

    def test_explicit_legacy_policy_remains_512_mib(self):
        with (self.root / 'medium.bin').open('wb') as stream: stream.truncate(600 * 1024**2)
        with self.assertRaises(LimitExceeded): scan_snapshot(self.root, CLOUD_INTAKE_V1)
        self.assertGreater(scan_snapshot(self.root, POLICY)[2], 600 * 1024**2)

    def test_one_gib_policy_stays_fixed_and_two_gib_accepts_larger_file(self):
        path = self.root / 'large.bin'
        with path.open('wb') as stream: stream.truncate(1536 * 1024**2)
        with self.assertRaises(LimitExceeded): scan_snapshot(self.root, CLOUD_INTAKE_V1_1)
        self.assertGreater(scan_snapshot(self.root, POLICY)[2], 1536 * 1024**2)
        self.assertEqual(check_record_paths([path])['record_bytes'], 1536 * 1024**2)

    def test_legacy_dataset_limit_stays_five_gib(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for i in range(3):
                with (root / str(i)).open('wb') as stream: stream.truncate(2 * 1024**3)
            with self.assertRaises(LimitExceeded): scan_snapshot(root, CLOUD_INTAKE_V1_2)
            self.assertEqual(scan_snapshot(root, POLICY)[2], 6 * 1024**3)

    def test_unlisted_records_including_edf_with_nonstandard_suffix_count(self):
        for i in range(97): (self.root / f'extra{i}.EEG').write_bytes(edf_bytes())
        with self.assertRaises(LimitExceeded) as caught: check_dataset_snapshot(self.root, self.plan)
        self.assertEqual((caught.exception.field, caught.exception.observed), ('records', 101))

    def test_file_count_includes_control_directories_and_unlisted_files(self):
        limits = replace(POLICY, max_files=len(self.plan['files']))
        check_dataset_snapshot(self.root, self.plan, limits=limits)
        (self.root / '.qc').mkdir(); (self.root / '.qc' / 'unlisted.json').write_text('{}')
        with self.assertRaises(LimitExceeded) as caught: check_dataset_snapshot(self.root, self.plan, limits=limits)
        self.assertEqual(caught.exception.field, 'files')

    def test_companion_total_uses_reader_and_bound_tables(self):
        largest = max(r['size_bytes'] for r in check_dataset_snapshot(self.root, self.plan)['record_sizes'])
        with self.assertRaises(LimitExceeded) as caught:
            check_dataset_snapshot(self.root, self.plan, limits=replace(POLICY, max_record_bytes=largest - 1))
        self.assertEqual(caught.exception.field, 'record_bytes')

    def test_missing_files_remain_quality_findings_not_zero_records(self):
        (self.root / self.plan['recordings'][0]['path']).unlink()
        result = check_dataset_snapshot(self.root, self.plan)
        self.assertEqual(result['records'], 4)
        self.assertIn('missing_record', {r['basis'] for r in result['record_sizes']})

    def test_symlinks_and_nested_archives_fail_closed(self):
        bad = self.root / 'link'; bad.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, '符号链接'): check_dataset_snapshot(self.root, self.plan)
        bad.unlink(); (self.root / 'unlisted.zip').write_bytes(b'archive')
        with self.assertRaisesRegex(ValueError, '展开'): check_dataset_snapshot(self.root, self.plan)

    def test_resume_cannot_evaluate_only_newly_added_bytes(self):
        admitted = check_dataset_snapshot(self.root, self.plan)
        (self.root / 'extra.txt').write_text('new')
        with self.assertRaisesRegex(ValueError, '发生变化'): assert_snapshot_unchanged(self.root, admitted)
        reduced = replace(POLICY, max_dataset_bytes=admitted['dataset_bytes'])
        with self.assertRaises(LimitExceeded): check_dataset_snapshot(self.root, self.plan, limits=reduced, transport_bytes=3)

    def test_file_change_during_admission_is_rejected(self):
        from ephys_qc.readers import inspect_recording
        def change(path, **kwargs):
            result = inspect_recording(path, **kwargs)
            (self.root / 'changed.txt').write_text(str(path))
            return result
        with patch('ephys_qc.dataset_qc.admission.inspect_recording', side_effect=change):
            with self.assertRaisesRegex(ValueError, '期间文件发生变化'): check_dataset_snapshot(self.root, self.plan)

    def jobs(self, policy=POLICY.version):
        config = self.base / 'plan.json'; config.write_text(json.dumps(self.plan))
        # Queue execution is driven synchronously in these admission tests.
        with patch('package_jobs.threading.Thread.start'):
            return PackageJobs({'data_dir': str(self.base / 'runtime'), 'admission_policy': policy, 'packages': [
                dict(id='pilot', label='Pilot', root=str(self.root), expectations=str(config))]})

    def submit(self, jobs):
        return jobs.submit(dict(package_id='pilot', manifest_hash=fingerprint(self.plan), confirmed=True))

    def test_rejected_submission_creates_no_job_or_partial_report(self):
        jobs = self.jobs()
        with (self.root / 'oversize.bin').open('wb') as stream: stream.truncate(POLICY.max_file_bytes + 1)
        with self.assertRaises(LimitExceeded): self.submit(jobs)
        self.assertEqual(jobs.jobs, {}); self.assertTrue(jobs.queue.empty())
        self.assertEqual(list(jobs.root.iterdir()), [])

    def test_local_registered_dataset_is_not_restricted_by_cloud_limits(self):
        jobs = self.jobs('local')
        with (self.root / 'oversize.bin').open('wb') as stream: stream.truncate(POLICY.max_file_bytes + 1)
        job = self.submit(jobs)
        self.assertIsNone(job['admission'])
        self.assertIsNone(jobs.catalog()['admission_policy'])

    def test_queued_snapshot_growth_is_rejected_before_qc(self):
        jobs = self.jobs(); job = self.submit(jobs)
        (self.root / 'later.txt').write_text('new file')
        with patch.object(jobs.queue, 'get', side_effect=[job['id'], StopIteration]), patch('package_jobs.run_dataset_qc') as run:
            with self.assertRaises(StopIteration): jobs._loop()
            run.assert_not_called()
        self.assertEqual(jobs.get(job['id'])['status'], 'failed')
        self.assertFalse((jobs.root / job['id'] / 'result').exists())

    def test_accepted_snapshot_runs_and_saves_admission_evidence(self):
        jobs = self.jobs(); job = self.submit(jobs)
        with patch.object(jobs.queue, 'get', side_effect=[job['id'], StopIteration]):
            with self.assertRaises(StopIteration): jobs._loop()
        self.assertEqual(jobs.get(job['id'])['status'], 'completed')
        saved = json.loads((jobs.root / job['id'] / 'request.json').read_text())
        self.assertEqual(saved['admission']['policy_version'], POLICY.version)
        self.assertEqual(jobs.catalog()['admission_policy']['max_dataset_bytes'], 10 * 1024**3)


class AdmissionHTTPTests(unittest.TestCase):
    freeze = fixtures.DatasetTests.freeze
    setUp = fixtures.DatasetHTTPTests.setUp
    close = fixtures.DatasetHTTPTests.close
    request = fixtures.DatasetHTTPTests.request

    def test_oversize_dataset_returns_413_and_creates_no_job(self):
        self.jobs.admission_policy = POLICY
        with (self.root / 'oversize.dat').open('wb') as stream: stream.truncate(POLICY.max_file_bytes + 1)
        code, _, body = self.request('/api/v1/package-jobs', dict(package_id='pilot', manifest_hash=fingerprint(self.plan), confirmed=True))
        self.assertEqual(code, 413)
        value = json.loads(body)
        self.assertEqual(value['code'], 'intake_limit_exceeded')
        self.assertEqual(value['limit'], POLICY.max_file_bytes)
        self.assertEqual(self.jobs.jobs, {})

    def test_oversize_http_upload_rejected_before_body(self):
        self.server.store.intakes = IntakeStore(self.base / 'upload-runtime')
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        connection.putrequest('POST', '/api/v1/intakes')
        connection.putheader('Content-Type', 'application/octet-stream')
        connection.putheader('X-Filename', 'large.edf')
        connection.putheader('Content-Length', str(POLICY.max_file_bytes + 1))
        connection.endheaders()
        response = connection.getresponse()
        self.assertEqual(response.status, 413)
        self.assertEqual(json.loads(response.read())['observed'], POLICY.max_file_bytes + 1)
        self.assertEqual(list(self.server.store.intakes.root.iterdir()), [])

    def test_registered_signal_job_cannot_bypass_upload_limit(self):
        with patch('server.threading.Thread.start'):
            store = Store({'data_dir': str(self.base / 'signals'), 'python': sys.executable,
                           'inputs': [], 'profiles': [], 'admission_policy': POLICY.version})
        source = self.root / 'oversize.edf'
        with source.open('wb') as stream: stream.truncate(POLICY.max_file_bytes + 1)
        with patch.object(store, 'plan_request', return_value=({'source_path': str(source)}, {'plan_id': 'p'})):
            with self.assertRaises(LimitExceeded): store.submit({'plan_id': 'p'})
        self.assertEqual(store.jobs, {})
        self.assertEqual(list((store.root / 'jobs').iterdir()), [])


if __name__ == '__main__': unittest.main()
