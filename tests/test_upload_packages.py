"""Archive intake boundaries and frozen companion files."""
import io
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(REPO / 'apps/workbench'))
from intake import IntakeStore
from uploads import source_manifest
from test_intake import recording, confirmation


def package(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return data.getvalue()


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = IntakeStore(self.temp.name)

    def receive(self, data):
        return self.store.receive('record.zip', len(data), io.BytesIO(data))

    def rejected(self, entries):
        with self.assertRaises(ValueError):
            self.receive(package(entries))
        self.assertEqual(list(self.store.root.iterdir()), [])

    def test_nested_single_record_is_read_and_registered_without_path_escape(self):
        intake = self.receive(package([('folder/main.edf', recording()), ('README.txt', b'notes')]))
        self.assertEqual(intake['metadata']['format'], 'EDF')
        self.assertEqual(intake['entry_file'], 'payload/folder/main.edf')
        record = self.store.confirm(intake['id'], confirmation())
        self.assertEqual(len(record['expected_source_files']), 1)
        self.assertTrue(Path(record['source_path']).is_relative_to(self.store.root))
        self.assertEqual(record['expected_sha256'], intake['source_sha256'])
        self.assertNotEqual(intake['sha256'], intake['source_sha256'])

    def test_unsafe_paths_links_and_case_collisions_are_rejected(self):
        for name in ['../escape.edf', '/tmp/escape.edf', 'a\\escape.edf', 'C:/escape.edf', 'a/../../escape.edf']:
            with self.subTest(name=name):
                self.rejected([(name, recording())])
        link = zipfile.ZipInfo('main.edf')
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.rejected([(link, b'/tmp/outside')])
        self.rejected([('main.edf', recording()), ('MAIN.edf', recording())])

    def test_archive_must_have_one_recording_and_fit_resource_limits(self):
        self.rejected([('a.edf', recording()), ('b.edf', recording())])
        self.rejected([('notes.txt', b'no recording')])
        self.rejected([(f'{i}.txt', b'') for i in range(65)])
        with patch('uploads.MAX_BYTES', 10):
            self.rejected([('a.edf', recording())])

    def test_missing_brainvision_companion_and_external_reference_are_rejected(self):
        header = b'Brain Vision Data Exchange Header File Version 1.0\n[Common Infos]\nDataFile=missing.eeg\nMarkerFile=missing.vmrk\nDataFormat=BINARY\nDataOrientation=MULTIPLEXED\nNumberOfChannels=1\nSamplingInterval=1000\n[Binary Infos]\nBinaryFormat=INT_16\n[Channel Infos]\nCh1=Cz,,1,uV\n'
        self.rejected([('main.vhdr', header)])
        self.rejected([('main.vhdr', header.replace(b'missing.eeg', b'../outside.eeg'))])

    def test_declared_companion_changed_after_intake_blocks_confirmation(self):
        # A declared extra source is frozen even when it does not contain waveform samples.
        from intake import inspect_recording
        def with_companion(path):
            meta = inspect_recording(path)
            meta['source_files'].append({'name': 'sidecar.txt', 'role': 'sidecar'})
            return meta
        with patch('intake.inspect_recording', side_effect=with_companion):
            intake = self.receive(package([('main.edf', recording()), ('sidecar.txt', b'original')]))
        sidecar = self.store.root / intake['id'] / 'payload' / 'sidecar.txt'
        sidecar.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, '配套文件'):
            self.store.confirm(intake['id'], confirmation())
        self.assertEqual(self.store.registered(), [])

    def test_reader_cannot_declare_sources_outside_the_package(self):
        root = Path(self.temp.name)
        folder = root / 'folder'
        folder.mkdir()
        main = folder / 'main.edf'
        main.write_bytes(recording())
        (root / 'outside.eeg').write_bytes(b'not allowed')
        with self.assertRaises(ValueError):
            source_manifest(main, {'source_files': [{'name': '../outside.eeg'}]})


if __name__ == '__main__':
    unittest.main()
