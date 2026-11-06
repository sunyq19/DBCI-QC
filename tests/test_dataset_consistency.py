"""Dataset rules: genuine EDF headers, explicit cohorts, negative controls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'apps/workbench'))
from test_workbench import edf_bytes
from ephys_qc.dataset_qc import run_dataset_qc
from ephys_qc.dataset_qc.consistency import evaluate_dataset, validate_consistency, _rate_equal
from package_jobs import PackageJobs, fingerprint
from server import Handler


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'source'; self.root.mkdir()
        self.plan = {'schema_version': 'package-expectations/1', 'scope': 'Two selected subjects only',
                     'files': [], 'items': [], 'recordings': [], 'consistency': {
                         'schema_version': 'dataset-consistency-plan/1', 'records': [], 'groups': [
                             dict(id='raw', label='Scalp raw', same_channels=True, same_rates=True, same_units=True, same_reference=True)]}}
        (self.root / 'participants.tsv').write_text('participant_id\nsub-01\nsub-02\nsub-not-selected\n')
        for subject in ('01', '02'):
            for run in (1, 2):
                stem = f'sub-{subject}_task-rest_run-{run:02d}'
                path = self.root / f'{stem}_eeg.edf'
                data = bytearray(edf_bytes()); data[-1] = int(subject) * 10 + run; path.write_bytes(data)
                channels = f'{stem}_channels.tsv'; meta = f'{stem}_eeg.json'; events = f'{stem}_events.tsv'
                (self.root / channels).write_text('name\ttype\tunits\tsampling_frequency\nCz\tEEG\tuV\t4\n')
                (self.root / meta).write_text(json.dumps(dict(SamplingFrequency=4, RecordingDuration=2, EEGReference='Cz')))
                (self.root / events).write_text('onset\tduration\n0\t1\n0.5\t1\n')
                self.plan['recordings'].append({'path': path.name})
                self.plan['consistency']['records'].append(dict(id=stem, path=path.name, subject=f'sub-{subject}', session='none',
                    modality='scalp_eeg', processing='raw', group='raw', channels_tsv=channels, participants_tsv='participants.tsv',
                    metadata_json=[meta], events={'path': events, 'mode': 'seconds'}))
        self.freeze()

    def freeze(self):
        self.plan['files'] = [{'path': p.name, 'size_bytes': p.stat().st_size,
                              'digest': {'algorithm': 'sha256', 'value': hashlib.sha256(p.read_bytes()).hexdigest()}}
                             for p in sorted(self.root.iterdir()) if p.is_file()]
        self.plan['items'] = [{'id': 'selected-files', 'requirement': 'required', 'files': [p['path'] for p in self.plan['files']]}]

    def run_checks(self): return evaluate_dataset(self.root, self.plan)

    def record(self, i=0): return self.plan['consistency']['records'][i]

    def statuses(self, result, code): return [c['status'] for c in result['checks'] if c['code'] == code]

    def test_real_reader_and_selected_subject_scope(self):
        result = self.run_checks()
        self.assertEqual(result['summary']['subjects'], 2)
        self.assertEqual(result['summary']['records'], 4)
        self.assertNotIn('conflict', result['summary']['status_counts'])
        self.assertEqual(self.statuses(result, 'individual_channels'), ['pass', 'pass'])
        self.assertEqual(self.statuses(result, 'cohort_rates'), ['pass'])
        self.assertEqual(self.statuses(result, 'events'), ['pass'] * 4)  # Overlap is legal.
        self.assertEqual(self.statuses(result, 'sessions'), ['unassessed'] * 4)

    def test_table_rate_conflict_is_individual_and_cohort_specific(self):
        path = self.root / self.record()['channels_tsv']
        path.write_text(path.read_text().replace('\t4\n', '\t8\n')); self.freeze()
        result = self.run_checks()
        self.assertEqual(self.statuses(result, 'rates')[0], 'conflict')
        self.assertEqual(self.statuses(result, 'individual_rates'), ['conflict', 'pass'])
        self.assertEqual(self.statuses(result, 'cohort_rates'), ['conflict'])

    def test_unknown_units_never_count_as_consistent(self):
        p = self.root / self.record()['channels_tsv']; p.write_text(p.read_text().replace('uV', 'n/a')); self.freeze()
        result = self.run_checks()
        self.assertEqual(self.statuses(result, 'units')[0], 'review')
        self.assertEqual(self.statuses(result, 'individual_units')[0], 'unassessed')
        self.assertEqual(self.statuses(result, 'cohort_units')[0], 'unassessed')

    def test_duplicate_participant_and_channel_name_detected(self):
        p = self.root / 'participants.tsv'; p.write_text(p.read_text() + 'sub-01\n')
        p = self.root / self.record()['channels_tsv']; p.write_text(p.read_text() + 'Cz\tEEG\tuV\t4\n'); self.freeze()
        result = self.run_checks()
        self.assertEqual(self.statuses(result, 'participants'), ['conflict', 'conflict', 'pass', 'pass'])
        self.assertEqual(self.statuses(result, 'channel_schema')[0], 'conflict')
        self.assertEqual(self.statuses(result, 'channel_names')[0], 'unassessed')

    def test_wrong_record_binding(self):
        self.record()['channels_tsv'] = self.record(1)['channels_tsv']
        self.assertEqual(self.statuses(self.run_checks(), 'binding')[0], 'conflict')

    def test_source_changes_do_not_redefine_expected_inventory(self):
        p = self.root / self.record()['channels_tsv']; p.write_text('changed')
        result = self.run_checks()
        self.assertEqual(self.statuses(result, 'files'), ['conflict'])
        self.assertEqual(self.statuses(result, 'channel_schema')[0], 'unassessed')

    def test_same_file_reused_for_different_subject_is_review_only(self):
        (self.root / self.record(2)['path']).write_bytes((self.root / self.record()['path']).read_bytes()); self.freeze()
        self.assertEqual(self.statuses(self.run_checks(), 'duplicates'), ['review'])

    def test_intracranial_cross_subject_layout_is_allowed_but_within_subject_is_checked(self):
        self.plan['consistency']['groups'][0]['same_channels'] = False
        for r in self.plan['consistency']['records']:
            r['modality'] = 'ecog'
        for r in self.plan['consistency']['records'][2:]:
            p = self.root / r['channels_tsv']; p.write_text(p.read_text().replace('Cz', 'GRID1'))
        self.freeze(); result = self.run_checks()
        self.assertEqual(self.statuses(result, 'cohort_channels'), ['not_applicable'])
        self.assertEqual(self.statuses(result, 'individual_channels'), ['pass', 'pass'])
        self.assertEqual(self.statuses(result, 'cohort_units'), ['pass'])
        p = self.root / self.record(3)['channels_tsv']; p.write_text(p.read_text().replace('GRID1', 'GRID2')); self.freeze()
        self.assertEqual(self.statuses(self.run_checks(), 'individual_channels'), ['pass', 'conflict'])

    def test_raw_and_derived_mixed_group_stops_comparison(self):
        self.record()['processing'] = 'derived'; result = self.run_checks()
        self.assertEqual(self.statuses(result, 'group_scope'), ['conflict', 'conflict'])
        self.assertEqual(self.statuses(result, 'individual_channels'), ['pass'])
        self.assertEqual(self.statuses(result, 'cohort_channels'), [])

    def test_event_boundaries_and_missing_values(self):
        p = self.root / self.record()['events']['path']
        for content, expected in [('onset\tduration\n-1\t1\n', 'review'), ('onset\tduration\n0\tn/a\n', 'unassessed'),
                                  ('onset\tduration\n3\t1\n', 'conflict'), ('onset\tduration\n0\t-1\n', 'conflict'),
                                  ('onset\tother\n0\t1\n', 'conflict')]:
            p.write_text(content); self.freeze()
            with self.subTest(content=content): self.assertEqual(self.statuses(self.run_checks(), 'events')[0], expected)

    def test_indices_unknown_origin_does_not_guess(self):
        self.record()['events'].update(mode='indices', origin=None)
        p = self.root / self.record()['events']['path']
        for stop, expected in [(8, 'review'), (10, 'conflict')]:
            p.write_text(f'indStart\tindStop\tstrChannelName\n0\t{stop}\tCz\n'); self.freeze()
            self.assertEqual(self.statuses(self.run_checks(), 'events')[0], expected)

    def test_clock_tolerance_has_a_physical_basis(self):
        self.assertTrue(_rate_equal(249.8750624687656, 249.85355222464145, fmt='BrainVision'))
        self.assertFalse(_rate_equal(249.8750624687656, 249.85355222464145, fmt='EDF'))
        self.assertFalse(_rate_equal(250, 256, fmt='BrainVision'))

    def test_unsafe_incomplete_or_implicit_plans_rejected(self):
        original = copy.deepcopy(self.plan)
        for bad in ('unlisted', 'unsafe', 'omit', 'implicit'):
            self.plan = copy.deepcopy(original)
            if bad == 'unlisted': self.record()['channels_tsv'] = 'other.tsv'
            elif bad == 'unsafe': self.record()['channels_tsv'] = '../other.tsv'
            elif bad == 'omit': self.plan['consistency']['records'].pop()
            else: del self.plan['consistency']['groups'][0]['same_channels']
            with self.subTest(bad=bad), self.assertRaises(ValueError): validate_consistency(self.plan)

    def test_report_preserves_source_and_escapes_identifiers(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.plan['scope'] = '<script>scope</script>'
        out = self.base / 'report'; result = run_dataset_qc(self.root, self.plan, out)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        self.assertNotIn('<script>', (out / 'report.html').read_text())
        self.assertIn('&lt;script&gt;', (out / 'report.html').read_text())
        self.assertEqual(result['expectations_sha256'], fingerprint(self.plan))
        with self.assertRaises(FileExistsError): run_dataset_qc(self.root, self.plan, out)
        with self.assertRaises(ValueError): run_dataset_qc(self.root, self.plan, self.root / 'out')

    def test_background_queue_freezes_plan_and_exposes_only_report_artifacts(self):
        config = self.base / 'plan.json'; config.write_text(json.dumps(self.plan))
        jobs = PackageJobs({'data_dir': str(self.base / 'state'), 'packages': [dict(id='pilot', label='Pilot', root=str(self.root), expectations=str(config))]})
        body = dict(package_id='pilot', manifest_hash=fingerprint(self.plan), confirmed=True)
        for changes in ({'confirmed': False}, {'root': str(self.root)}, {'manifest_hash': 'stale'}, {'package_id': 'unknown'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError): jobs.submit({**body, **changes})
        job = jobs.submit(body); jobs.queue.join()
        completed = jobs.get(job['id'])
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual([m['status'] for m in completed['modules']], ['completed'] * 3)
        self.assertTrue(jobs.artifact(job['id'], 'report.html').is_file())
        with self.assertRaises(KeyError): jobs.artifact(job['id'], '../request.json')
        self.plan['scope'] = 'changed'; config.write_text(json.dumps(self.plan))
        self.assertNotEqual(jobs.catalog()['packages'][0]['manifest_hash'], body['manifest_hash'])
        with self.assertRaises(ValueError): jobs.submit(body)


class DatasetHTTPTests(unittest.TestCase):
    freeze = DatasetTests.freeze

    def setUp(self):
        DatasetTests.setUp(self)
        config = self.base / 'plan.json'; config.write_text(json.dumps(self.plan))
        self.jobs = PackageJobs({'data_dir': str(self.base / 'runtime'), 'packages': [
            dict(id='pilot', label='Pilot', root=str(self.root), expectations=str(config))]})
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.store = SimpleNamespace(packages=self.jobs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def close(self):
        self.jobs.queue.join(); self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def request(self, path, body=None, headers=None):
        request = urllib.request.Request(self.url + path, data=json.dumps(body).encode() if body is not None else None,
                                         headers={'Content-Type': 'application/json', **(headers or {})})
        try: response = self.opener.open(request, timeout=3)
        except urllib.error.HTTPError as error: response = error
        return response.status, response.headers, response.read()

    def test_browser_workflow_and_artifact_boundaries(self):
        status, _, data = self.request('/api/v1/packages'); self.assertEqual(status, 200)
        package = json.loads(data)['packages'][0]
        self.assertNotIn(str(self.root), data.decode())
        body = dict(package_id='pilot', manifest_hash=package['manifest_hash'], confirmed=True)
        status, _, data = self.request('/api/v1/package-jobs', body); self.assertIn(status, (200, 201, 202))
        job = json.loads(data); self.jobs.queue.join()
        for suffix in ('', '/result', '/expectations', '/report', '/download?lang=en'):
            status, headers, data = self.request('/api/v1/package-jobs/' + job['id'] + suffix)
            with self.subTest(suffix=suffix):
                self.assertEqual(status, 200)
                if suffix.startswith('/download'): self.assertIn('attachment', headers['Content-Disposition'])
        self.assertEqual(self.request('/api/v1/package-jobs/' + job['id'] + '/request.json')[0], 404)
        for path in ('/datasets', '/datasets.js', '/datasets.css', '/standards/dataset-checks', '/en/standards/dataset-checks'):
            with self.subTest(path=path): self.assertEqual(self.request(path)[0], 200)

    def test_new_api_preserves_localhost_and_confirmation_guards(self):
        self.assertEqual(self.request('/api/v1/packages', headers={'Origin': 'https://example.com'})[0], 403)
        body = dict(package_id='pilot', manifest_hash=fingerprint(self.plan), confirmed=False)
        self.assertEqual(self.request('/api/v1/package-jobs', body)[0], 400)
        self.assertEqual(self.request('/api/v1/package-jobs', {**body, 'root': '/tmp/arbitrary'})[0], 400)
        self.assertEqual(self.request('/api/v1/package-jobs', {**body, 'confirmed': True, 'manifest_hash': 'old'})[0], 400)


if __name__ == '__main__': unittest.main()
