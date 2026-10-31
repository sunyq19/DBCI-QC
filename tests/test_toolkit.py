"""Headless integration boundaries: actual files, source integrity and outputs."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'examples'))
from headless_qc import write_synthetic_edf
from ephys_qc.toolkit import prepare_recording, run_module, run_modules, build_plan
from ephys_qc.__main__ import main

SCIENTIFIC = all(importlib.util.find_spec(name) for name in ('brainelecqc', 'numpy', 'matplotlib'))


class CLIStatusTests(unittest.TestCase):
    def test_mixed_recording_failure_remains_nonzero(self):
        for result in [
            {'status': 'partial', 'modules': [], 'windows': [{'status': 'completed'}, {'status': 'failed'}]},
            {'status': 'partial', 'modules': [{'status': 'partial', 'summary': {'window_status_counts': {'failed': 1}}}]},
        ]:
            with self.subTest(result=result), patch('ephys_qc.__main__._read', return_value={}), \
                    patch('ephys_qc.__main__.run_modules', return_value=result), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['run', '--record', 'record.json', '--modules', 'M03', '--output', 'unused']), 1)


@unittest.skipUnless(SCIENTIFIC, 'Requires scientific execution environment')
class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.edf'
        write_synthetic_edf(self.source)
        self.config = {'selection': {'eeg_indices': [0, 1], 'reference_indices': {},
                                     'start_seconds': 0, 'duration_seconds': 10},
                       'method_config': {'comparison_groups': None}}
        self.record = prepare_recording(self.source, record_id='demo', modality='scalp_eeg', qc_config=self.config)

    def test_preparation_captures_files_without_running(self):
        self.assertEqual(len(self.record['expected_source_files']), 1)
        self.assertEqual(self.record['expected_source_files'][0]['sha256'], self.record['expected_sha256'])
        self.assertEqual(list(self.root.iterdir()), [self.source])
        self.config['selection']['eeg_indices'].clear()
        self.assertEqual(self.record['default_config']['selection']['eeg_indices'], [0, 1])

    def test_confirmation_and_explicit_module_selection_required(self):
        for modality in (None, 'other', 'unknown'):
            with self.assertRaises(ValueError):
                prepare_recording(self.source, record_id='x', modality=modality, qc_config=self.config)
        record = copy.deepcopy(self.record); del record['modality']
        with self.assertRaises(ValueError): build_plan(record, ['M03'])
        with self.assertRaises(ValueError): run_modules(self.record, self.root / 'out', None)
        self.assertFalse((self.root / 'out').exists())

    def test_unknown_units_cannot_use_legacy_planner_compatibility(self):
        record = copy.deepcopy(self.record); record['metadata']['channels'][0]['unit'] = None
        with self.assertRaises(ValueError): build_plan(record, ['M03'])

    def test_malformed_record_fields_are_input_errors(self):
        for field in ('channels', 'selection', 'reference_indices'):
            record = copy.deepcopy(self.record)
            if field == 'channels': record['metadata']['channels'] = {}
            elif field == 'selection': record['default_config']['selection'] = []
            else: record['default_config']['selection']['reference_indices'] = []
            with self.subTest(field=field), self.assertRaises(ValueError): build_plan(record, ['M03'])

    def test_single_module_has_dependency_closure_and_keeps_other_methods_unrun(self):
        original = self.source.read_bytes(); events = []
        result = run_module('M03', self.record, self.root / 'out', emit=lambda *event: events.append(event))
        self.assertEqual(set(result['selected_modules']), {'M01', 'M02', 'M03', 'M08', 'M09'})
        self.assertFalse(any(mid in {'M04', 'M05', 'M06', 'M07'} and status == 'running' for mid, status, _ in events))
        self.assertEqual(next(m for m in result['modules'] if m['id'] == 'M03')['status'], 'completed')
        self.assertGreater(next(m for m in result['modules'] if m['id'] == 'M03')['summary']['candidate_count'], 0)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertIsNone(result['score']['value'])
        self.assertTrue((self.root / 'out' / result['report_path']).is_file())
        frozen = json.loads((self.root / 'out/request.json').read_text())
        self.assertEqual(frozen['input']['expected_sha256'], self.record['expected_sha256'])
        self.assertEqual(json.loads((self.root / 'out/result.json').read_text())['plan_id'], result['plan_id'])

    def test_existing_partial_output_and_source_directory_are_not_overwritten(self):
        out = self.root / 'partial'; out.mkdir(); marker = out / 'evidence'; marker.write_text('keep')
        with self.assertRaises(FileExistsError): run_module('M03', self.record, out)
        self.assertEqual(marker.read_text(), 'keep')
        with self.assertRaises(ValueError): run_module('M03', self.record, self.root)
        self.assertTrue(self.source.is_file())

    def test_changed_source_is_failed_not_refingerprinted(self):
        data = bytearray(self.source.read_bytes()); data[-1] ^= 1; self.source.write_bytes(data)
        result = run_module('M03', self.record, self.root / 'changed')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(next(m for m in result['modules'] if m['id'] == 'M01')['status'], 'failed')
        self.assertEqual(next(m for m in result['modules'] if m['id'] == 'M03')['status'], 'skipped')

    def test_cli_returns_nonzero_for_recorded_failure_and_keeps_json_stdout(self):
        record = self.root / 'record.json'; record.write_text(json.dumps(self.record))
        self.source.unlink()
        import os
        env = dict(os.environ, PYTHONPATH=str(REPO / 'src'))
        result = subprocess.run([sys.executable, '-m', 'ephys_qc', 'run', '--record', str(record),
                                 '--modules', 'M03', '--output', str(self.root / 'failed')],
                                cwd=self.root, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
