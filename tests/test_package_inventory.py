"""Dataset inventory boundaries: missing records, immutable expectations, safe IO."""
import copy
from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.dataset_qc import inspect_package, run_package_inventory
from ephys_qc.__main__ import main


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name); self.root = self.base / 'source'; self.root.mkdir()
        (self.root / 'record.edf').write_bytes(b'original recording')
        (self.root / 'channels.tsv').write_text('name\nCz\n')
        self.manifest = {'schema_version': 'package-expectations/1', 'scope': 'Selected subject 1 only; not the full cohort',
            'files': [{'path': p.name, 'size_bytes': p.stat().st_size,
                       'digest': {'algorithm': 'sha256', 'value': hashlib.sha256(p.read_bytes()).hexdigest()}}
                      for p in sorted(self.root.iterdir())],
            'items': [{'id': 's1-recording', 'subject': 's1', 'category': 'EEG', 'requirement': 'required',
                       'files': ['record.edf', 'channels.tsv']}], 'recordings': [{'path': 'record.edf'}]}

    def inspect(self, manifest=None):
        return inspect_package(self.root, manifest or self.manifest, read_headers=False)

    def test_selected_subset_and_extra_files_do_not_invent_missing_subjects(self):
        (self.root / 'participants.tsv').write_text('participant_id\nsub-01\nsub-02\n')
        result = self.inspect()
        self.assertEqual(result['inventory_status'], 'complete')
        self.assertEqual(result['summary']['expected_files'], 2)
        self.assertEqual(result['unlisted_files'], ['participants.tsv'])
        self.assertEqual(result['header_status'], 'needs_attention')
        self.assertEqual(result['recordings'][0]['reason'], 'header_check_not_requested')

    def test_missing_companion_is_not_removed_from_denominator(self):
        (self.root / 'channels.tsv').unlink()
        result = self.inspect()
        self.assertEqual(result['inventory_status'], 'needs_attention')
        self.assertEqual(result['items'][0]['status'], 'missing')
        self.assertEqual(result['summary']['expected_files'], 2)
        self.assertEqual(result['summary']['present_files'], 1)

    def test_whole_expected_record_absent_is_reported(self):
        self.manifest['files'].append({'path': 'absent.edf'})
        self.manifest['items'].append({'id': 's2', 'subject': 's2', 'requirement': 'required', 'files': ['absent.edf']})
        self.assertEqual(self.inspect()['items'][1]['status'], 'missing')

    def test_unknown_and_not_applicable_are_never_present(self):
        self.manifest['items'] += [{'id': 'ct', 'requirement': 'not_applicable', 'reason': 'Scalp EEG demonstration scope'},
                                   {'id': 'events', 'requirement': 'unknown', 'reason': 'Protocol not confirmed'}]
        result = self.inspect()
        self.assertEqual([i['status'] for i in result['items']], ['present', 'not_applicable', 'unknown'])
        self.assertEqual(result['inventory_status'], 'needs_attention')
        self.assertEqual(result['summary']['expected_files'], 2)

    def test_same_size_corruption_detected_by_digest(self):
        p = self.root / 'record.edf'; p.write_bytes(b'X' * p.stat().st_size)
        result = self.inspect()
        row = next(f for f in result['files'] if f['path'] == p.name)
        self.assertEqual(row['issues'], ['digest_mismatch'])
        self.assertEqual(result['items'][0]['status'], 'mismatch')

    def test_malformed_manifests_fail_before_io(self):
        for value in ['../outside', '/tmp/outside', 'a/../b', 'a\\b', 'a//b', '.qc/hidden']:
            manifest = copy.deepcopy(self.manifest); manifest['files'][0]['path'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.inspect(manifest)
        for mutation in ('duplicate', 'uncovered', 'empty', 'wrong_digest', 'unknown_files'):
            m = copy.deepcopy(self.manifest)
            if mutation == 'duplicate': m['files'].append(m['files'][0])
            elif mutation == 'uncovered': m['items'][0]['files'].pop()
            elif mutation == 'empty': m['scope'] = ''
            elif mutation == 'wrong_digest': m['files'][0]['digest']['value'] = 'bad'
            else: m['items'][0]['requirement'] = 'unknown'; m['items'][0]['reason'] = 'unknown'
            with self.subTest(mutation=mutation), self.assertRaises(ValueError): self.inspect(m)

    def test_symlinks_and_symlink_directories_never_read(self):
        outside = self.base / 'private'; outside.mkdir(); (outside / 'channels.tsv').write_text('secret')
        (self.root / 'channels.tsv').unlink(); (self.root / 'channels.tsv').symlink_to(outside / 'channels.tsv')
        (self.root / 'linked').symlink_to(outside, target_is_directory=True)
        result = self.inspect()
        self.assertEqual(result['files'][0]['status'], 'unsafe')
        self.assertEqual(result['unlisted_files'], ['linked'])
        self.assertNotIn('secret', json.dumps(result))

    def test_no_global_bidsignore_exclusion(self):
        (self.root / '.bidsignore').write_text('extra.edf')
        (self.root / 'extra.edf').write_bytes(b'visible')
        self.assertIn('extra.edf', self.inspect()['unlisted_files'])

    def test_reader_failure_is_separate_from_file_completeness(self):
        with patch('ephys_qc.readers.inspect_recording', side_effect=ValueError('/private/name')):
            result = inspect_package(self.root, self.manifest)
        self.assertEqual(result['inventory_status'], 'complete')
        self.assertEqual(result['header_status'], 'needs_attention')
        self.assertEqual(result['recordings'][0]['status'], 'read_failed')
        self.assertNotIn('/private/name', json.dumps(result))

    def test_missing_voltage_unit_is_visible_even_if_structure_is_readable(self):
        metadata = {'format': 'EDF', 'duration_seconds': 10, 'channels': [{'unit': '', 'sampling_rate_hz': 100}],
                    'warnings': [{'code': 'unknown_physical_quantity', 'first_context': {'private': 'not exported'}}]}
        with patch('ephys_qc.readers.inspect_recording', return_value=metadata):
            result = inspect_package(self.root, self.manifest)
        self.assertEqual(result['recordings'][0]['units'], {'未声明': 1})
        self.assertEqual(result['recordings'][0]['warning_codes'], ['unknown_physical_quantity'])
        self.assertNotIn('not exported', json.dumps(result))

    def test_report_and_manifest_frozen_source_unchanged_and_html_escaped(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.manifest['scope'] = '<script>alert(1)</script>'
        out = self.base / 'report'
        run_package_inventory(self.root, self.manifest, out, read_headers=False)
        self.manifest['scope'] = 'mutated'
        self.assertEqual(json.loads((out / 'expectations.json').read_text())['scope'], '<script>alert(1)</script>')
        self.assertIn('&lt;script&gt;', (out / 'report.html').read_text())
        self.assertNotIn('<script>', (out / 'report.html').read_text())
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})
        with self.assertRaises(FileExistsError): run_package_inventory(self.root, self.manifest, out)
        with self.assertRaises(ValueError): run_package_inventory(self.root, self.manifest, self.root / 'out')

    def test_cli_nonzero_for_unknown_and_missing_and_success_for_inventory_only(self):
        # A manifest with no requested waveform inspection can complete inventory.
        self.manifest['recordings'] = []
        source = self.base / 'expected.json'; source.write_text(json.dumps(self.manifest))
        with redirect_stdout(io.StringIO()):
            code = main(['package-inspect', str(self.root), '--expectations', str(source), '--output', str(self.base / 'out1')])
        self.assertEqual(code, 0)
        (self.root / 'channels.tsv').unlink()
        with redirect_stdout(io.StringIO()):
            code = main(['package-inspect', str(self.root), '--expectations', str(source), '--output', str(self.base / 'out2')])
        self.assertEqual(code, 1)

    @unittest.skipUnless(importlib.util.find_spec('mne'), 'Requires MNE for actual companion validation')
    def test_actual_brainvision_reader_missing_binary_then_restored(self):
        from test_readers import brainvision_fixture
        path, _ = brainvision_fixture(self.root)
        names = ['signal.vhdr', 'signal.vmrk', 'signal.eeg']
        manifest = {'schema_version': 'package-expectations/1', 'scope': 'BrainVision record with companions',
                    'files': [{'path': p} for p in names], 'recordings': [{'path': path.name}],
                    'items': [{'id': 'brainvision', 'requirement': 'required', 'files': names}]}
        binary = self.root / 'signal.eeg'; original = binary.read_bytes(); binary.unlink()
        result = inspect_package(self.root, manifest)
        self.assertEqual(result['inventory_status'], 'needs_attention')
        self.assertEqual(result['recordings'][0]['status'], 'read_failed')
        binary.write_bytes(original)
        result = inspect_package(self.root, manifest)
        self.assertEqual(result['recordings'][0]['channel_count'], 2)
        self.assertEqual(result['recordings'][0]['duration_seconds'], 4)
        self.assertEqual(result['inventory_status'], 'complete')

    @unittest.skipUnless(importlib.util.find_spec('mne'), 'Requires MNE')
    def test_brainvision_trailing_partial_frame_is_rejected(self):
        from test_readers import brainvision_fixture
        from ephys_qc.readers import inspect_recording
        path, _ = brainvision_fixture(self.root)
        binary = self.root / 'signal.eeg'; original = binary.read_bytes()
        for data in (original[:-1], original + b'x', b''):
            binary.write_bytes(data)
            with self.subTest(length=len(data)), self.assertRaisesRegex(ValueError, '完整通道采样帧'):
                inspect_recording(path)


if __name__ == '__main__':
    unittest.main()
