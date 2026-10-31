"""Batch acceptance tests: partial semantics, source safety and bounded workers."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
sys.path.insert(0, str(REPO / 'src'))
import validate_data_coverage as runner


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def config(self, count=2):
        records = []
        for n in range(count):
            source = self.root / f'source-{n}.edf'; source.write_bytes(b'fixture')
            records.append({'id': f'case-{n}', 'source_path': source.name, 'dataset_id': 'test',
                            'metadata': {'format': 'EDF', 'duration_seconds': 10},
                            'default_config': {'selection': {'eeg_indices': [0], 'duration_seconds': 10}}})
        path = self.root / 'config.json'; runner.save(path, {'inputs': records})
        return path

    def fixture(self):
        job = self.root / 'job'; (job / 'artifacts').mkdir(parents=True)
        (job / 'artifacts/report.html').write_text('<p>Evidence</p>')
        runner.save(job / 'request.json', {})
        plan = {'scope': 'window', 'plan_id': 'plan', 'selected_modules': ['M01', 'M02', 'M03', 'M07', 'M08', 'M09'],
                'nodes': [{'id': f'M{i:02d}'} for i in range(1, 10)],
                'qc_config': {'selection': {'start_seconds': 0., 'duration_seconds': 10.}}}
        result = {'scope': 'window', 'status': 'partial', 'plan_id': 'plan', 'source_sha256': 'hash',
                  'selected_modules': plan['selected_modules'], 'score': {'value': None},
                  'report_path': 'artifacts/report.html', 'recording': {'start_seconds': 0., 'duration_seconds': 10., 'sampling_rate_hz': 100},
                  'modules': [{'id': n['id'], 'status': 'partial' if n['id'] == 'M03' else 'skipped' if n['id'] in {'M04','M05','M06','M07'} else 'completed',
                               'reason': 'No independent annotations' if n['id'] == 'M07' else 'Gate retained', 'summary': {}} for n in plan['nodes']]}
        runner.save(job / 'result.json', result)
        return plan, result, job

    def test_partial_and_selected_m07_without_annotations_are_engineering_pass(self):
        plan, result, job = self.fixture()
        acceptance = runner.assess_result(result, plan, job, 'hash')
        self.assertEqual(acceptance['issues'], [])
        self.assertEqual(acceptance['evaluated_seconds'], 10)
        self.assertFalse(acceptance['coverage']['whole_recording_claim'])

    def test_failure_cannot_hide_in_partial_aggregate_or_missing_reason(self):
        plan, result, job = self.fixture()
        result['modules'][2]['summary'] = {'window_status_counts': {'failed': 1}}
        result['modules'][6]['reason'] = ''
        runner.save(job / 'result.json', result)
        issues = runner.assess_result(result, plan, job, 'hash')['issues']
        self.assertTrue(any('hidden failed window' in issue for issue in issues))
        self.assertTrue(any('missing unassessed reason' in issue for issue in issues))

    def test_report_must_exist_inside_job_and_hash_must_match(self):
        plan, result, job = self.fixture()
        result['report_path'] = '../outside.html'; (self.root / 'outside.html').write_text('not this report')
        runner.save(job / 'result.json', result)
        issues = runner.assess_result(result, plan, job, 'changed')['issues']
        self.assertIn('Nonempty local report missing', issues)
        self.assertIn('Result source fingerprint mismatch', issues)

    def test_registered_source_changes_are_not_rebaselined(self):
        source = self.root / 'data.edf'; source.write_bytes(b'before')
        record = {'source_path': str(source), 'expected_sha256': runner.digest(source)}
        source.write_bytes(b'after')
        with self.assertRaisesRegex(ValueError, 'not be re-baselined'):
            runner.assert_registered(record, runner.source_snapshot(record))

    def test_workbench_alias_relative_paths_ids_and_no_overwrite(self):
        path = self.config()
        records = runner.load_records(path, ['case-1'])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['source_path'], str(self.root / 'source-1.edf'))
        with self.assertRaises(ValueError): runner.load_records(path, ['absent'])
        with self.assertRaises(ValueError): runner.check_output(self.root, records)
        with self.assertRaises(ValueError): runner.check_output(self.root / 'source-1.edf', records)
        repeated = [records[0], records[0]]; runner.save(path, {'records': repeated})
        with self.assertRaises(ValueError): runner.load_records(path)

    def test_recording_unexecuted_seconds_are_not_full_coverage(self):
        plan, result, job = self.fixture(); plan.update(scope='recording', window_count=2)
        result.update(scope='recording', windows=[{'status':'completed'},{'status':'not_run'}],
            coverage={'total_seconds':20., 'available_seconds':20., 'completed_seconds':10.,
                      'failed_seconds':0., 'running_seconds':0., 'unexecuted_seconds':10., 'gap_seconds':0.})
        runner.save(job / 'result.json', result)
        issues = runner.assess_result(result, plan, job, 'hash')['issues']
        self.assertIn('Recording contains failed or unexecuted samples', issues)
        self.assertIn('A recording window did not finish', issues)

    def test_worker_failure_continues_and_default_is_recommended(self):
        config = self.config(); output = self.root / 'coverage'; calls = []
        def worker(command, **kwargs):
            folder = Path(command[command.index('--output-dir') + 1]); calls.append(command)
            record = runner.read_json(folder / 'input-record.json')
            failed = record['id'] == 'case-0'
            row = {**runner.record_summary(record), 'engineering_status':'failed' if failed else 'passed',
                   'engineering_pass':not failed, 'execution_status':'partial', 'issues':['injected'] if failed else [],
                   'budget_consumed_seconds':10.}
            runner.save(folder / 'acceptance.json', row)
            return subprocess.CompletedProcess(command, int(failed))
        with patch.object(runner.subprocess, 'run', side_effect=worker):
            code = runner.main(['--config', str(config), '--output-dir', str(output)])
        self.assertEqual(code, 1); self.assertEqual(len(calls), 2)
        self.assertTrue(all(c[c.index('--selection')+1] == 'recommended' for c in calls))
        result = runner.read_json(output / 'coverage.json')
        self.assertEqual((result['passed'], result['failed']), (1,1))
        self.assertTrue(result['scientific_accuracy_not_evaluated'])
        self.assertTrue((output / 'index.html').is_file())

    def test_exhausted_budget_skips_without_launching_another_worker(self):
        config = self.config(); output = self.root / 'coverage'
        def worker(command, **kwargs):
            folder = Path(command[command.index('--output-dir') + 1])
            record = runner.read_json(folder / 'input-record.json')
            runner.save(folder / 'acceptance.json', {**runner.record_summary(record), 'engineering_status':'passed',
                        'engineering_pass':True, 'budget_consumed_seconds':10.})
            return subprocess.CompletedProcess(command, 0)
        with patch.object(runner.subprocess, 'run', side_effect=worker) as process:
            code = runner.main(['--config',str(config),'--output-dir',str(output),'--max-total-seconds','10'])
        self.assertEqual(code,1); process.assert_called_once()
        self.assertEqual(runner.read_json(output / 'coverage.json')['budget_skipped'],1)

    def test_timeout_retains_status_and_continues(self):
        config = self.config(); output = self.root / 'coverage'
        with patch.object(runner.subprocess, 'run', side_effect=subprocess.TimeoutExpired('worker', .1)) as process:
            self.assertEqual(runner.main(['--config',str(config),'--output-dir',str(output)]),1)
        self.assertEqual(process.call_count,2)
        result = runner.read_json(output / 'coverage.json')
        self.assertEqual(result['timed_out'],2)
        self.assertTrue(all(not r['engineering_pass'] for r in result['records']))


if __name__ == '__main__': unittest.main()
