"""Multi-format numerical, source identity and safe-reference contracts.

Scientific cases use the configured MNE environment; no downloads or clinical
data are needed. Synthetic waveforms validate decoding, not quality accuracy.
"""
from pathlib import Path
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.readers import list_readers, inspect_recording, open_reader
from ephys_qc.readers.common import companion
from ephys_qc.planning import build_plan

SCIENTIFIC = importlib.util.find_spec('mne') is not None and importlib.util.find_spec('brainelecqc') is not None


def brainvision_fixture(root, names=('Cz', 'Pz')):
    import numpy as np
    data = np.array([np.arange(400), 3 * np.arange(400) - 300], dtype='<i2')
    (root / 'signal.eeg').write_bytes(data.T.tobytes())
    (root / 'signal.vmrk').write_text('Brain Vision Data Exchange Marker File, Version 1.0\n'
        '[Common Infos]\nDataFile=signal.eeg\n[Marker Infos]\nMk1=Stimulus,S 1,101,1,0\n', encoding='utf-8')
    header = ('Brain Vision Data Exchange Header File Version 1.0\n[Common Infos]\nCodepage=UTF-8\n'
        'DataFile=signal.eeg\nMarkerFile=signal.vmrk\nDataFormat=BINARY\nDataOrientation=MULTIPLEXED\n'
        'NumberOfChannels=2\nSamplingInterval=10000\n[Binary Infos]\nBinaryFormat=INT_16\n'
        f'[Channel Infos]\nCh1={names[0]},,0.5,µV\nCh2={names[1]},,0.01,mV\n')
    path = root / 'signal.vhdr'; path.write_text(header, encoding='utf-8')
    return path, data * np.array([0.5e-6, 0.01e-3])[:, None]


def eeglab_fixture(root, embedded=False, boundary=False):
    import numpy as np
    from scipy.io import savemat
    data = np.array([np.arange(400), -2 * np.arange(400)], dtype='<f4')
    eeg = {'nbchan': 2, 'pnts': 400, 'trials': 1, 'srate': 100.0, 'xmin': 0., 'xmax': 3.99,
           'chanlocs': np.array([{'labels': 'Cz'}, {'labels': 'Pz'}], dtype=object),
           'event': {'type': 'boundary' if boundary else 'stimulus', 'latency': 201.,
                     'duration': 100. if boundary else 1.},
           'data': data if embedded else 'signal.fdt'}
    if not embedded:
        (root / 'signal.fdt').write_bytes(data.T.tobytes())
    path = root / 'signal.set'; savemat(path, {'EEG': eeg})
    return path, data.astype(float) * 1e-6


def fif_fixture(root, skip=False):
    import mne
    import numpy as np
    data = np.array([np.arange(400) * 1e-6, np.arange(400) * 1e-12, -np.arange(400) * 1e-6])
    raw = mne.io.RawArray(data, mne.create_info(['Cz', 'MEG', 'EOG'], 100., ['eeg', 'mag', 'eog']),
                         first_samp=500, verbose='ERROR')
    raw.set_annotations(mne.Annotations([2. if skip else 1.], [.5 if skip else .01],
                                       ['BAD_ACQ_SKIP' if skip else 'stimulus']))
    path = root / 'signal_raw.fif'; raw.save(path, fmt='double', overwrite=True, verbose='ERROR'); raw.close()
    return path, data


def qc_record(path, metadata, indices=None):
    indices = indices if indices is not None else [c['index'] for c in metadata['channels'] if c.get('channel_type') in {None, 'eeg'} and c['unit'] in {'V', 'uV', 'µV'}]
    return {'id': 'fixture', 'source_path': str(path), 'modality': 'scalp_eeg', 'modality_source': 'test_explicit_confirmation',
            'metadata': metadata, 'default_config': {'selection': {'eeg_indices': indices,
             'reference_indices': {}, 'start_seconds': 0., 'duration_seconds': min(1., metadata['duration_seconds'])},
             'method_config': {'comparison_groups': None}}}


def native_tal_fixture(root, *, bdf=False, onsets=('0', '1')):
    """Real EDF+/BDF+ bytes: two native rates and a per-record timekeeping TAL."""
    def cell(value, width): return str(value).encode('ascii').ljust(width, b' ')
    width = 3 if bdf else 2
    kind = 'BDF' if bdf else 'EDF'
    low, high = (-8388608, 8388607) if bdf else (-32768, 32767)
    head = (b'\xffBIOSEMI' if bdf else cell(0, 8)) + b''.join(cell(v, w) for v, w in [
        ('', 80), ('', 80), ('01.01.01', 8), ('00.00.00', 8), (1024, 8), (kind + '+C', 44),
        (len(onsets), 8), (1, 8), (3, 4)])
    fields = [(16, ['Cz', 'EOG', kind + ' Annotations']), (80, ['', '', '']),
              (8, ['uV', 'uV', '']), (8, [low, low, -1]), (8, [high, high, 1]),
              (8, [low] * 3), (8, [high] * 3), (80, ['', '', '']), (8, [100, 50, 32]), (32, ['', '', ''])]
    payload = []
    for record_index, onset in enumerate(onsets):
        payload.append(b''.join((record_index * 100 + i).to_bytes(width, 'little', signed=True) for i in range(100)))
        payload.append(b''.join((record_index * 50 + i).to_bytes(width, 'little', signed=True) for i in range(50)))
        payload.append((('+' + onset).encode('ascii') + b'\x14\x14\0').ljust(32 * width, b'\0'))
    path = root / ('tal.' + kind.lower())
    path.write_bytes(head + b''.join(cell(v, w) for w, row in fields for v in row) + b''.join(payload))
    return path


class RegistryTests(unittest.TestCase):
    def test_catalog_covers_formats_without_importing_heavy_dependencies(self):
        specs = list_readers()
        self.assertEqual({f for s in specs for f in s['formats']}, {'EDF', 'BDF', 'BrainVision', 'EEGLAB', 'FIF', 'SpikeGLX', 'NWB'})
        specs[0]['extensions'].append('.wrong')
        self.assertNotIn('.wrong', list_readers()[0]['extensions'])
        json.dumps(list_readers(), allow_nan=False)

    def test_companion_references_reject_escape_remote_absolute_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); main = root / 'signal.vhdr'; main.touch()
            (root / 'signal.eeg').write_bytes(b'1'); (root / 'linked.eeg').symlink_to(root / 'signal.eeg')
            self.assertEqual(companion(main, 'signal.eeg'), (root / 'signal.eeg').resolve())
            for name in ['../signal.eeg', '/tmp/signal.eeg', 'C:\\signal.eeg', 'https://x/s.eeg',
                         'sub/signal.eeg', 'sub\\signal.eeg', ' signal.eeg', 'linked.eeg', 'absent.eeg']:
                with self.subTest(name=name), self.assertRaises(ValueError): companion(main, name)


@unittest.skipUnless(SCIENTIFIC, 'Requires configured MNE/BrainElecQC environment')
class ScientificReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def read(self, path, start=100, count=70):
        reader = open_reader(path, 'fixture')
        self.addCleanup(reader.close)
        desc = reader.describe(); stream = desc['streams'][0]; segment = stream['segments'][0]
        origin = stream['sample_index_origin']
        values = reader.read_window(stream['stream_id'], segment['segment_id'],
                                    [c['channel_id'] for c in stream['channels']], origin + start, origin + start + count)
        return reader, values

    def test_brainvision_actual_binary_scaling_units_events_and_source_identity(self):
        import numpy as np
        path, expected = brainvision_fixture(self.root)
        reader, actual = self.read(path)
        np.testing.assert_allclose(actual, expected[:, 100:170], rtol=0, atol=1e-18)
        metadata = reader.metadata()
        self.assertEqual(metadata['annotations']['count'], 1)
        self.assertEqual(reader.describe()['events'][0]['onset_seconds'], 1.)
        self.assertEqual(len(metadata['source_files']), 3)
        self.assertEqual([c['index'] for c in metadata['channels']], [0, 1])
        self.assertTrue(all('path' not in f for f in metadata['source_files']))
        self.assertEqual(metadata['modality_evidence']['value'], 'unknown')
        self.assertEqual(metadata['modality_evidence']['source'], 'reader_default')
        json.dumps(metadata, allow_nan=False)

    def test_bdf_mixed_native_rates_are_not_resampled_or_combined(self):
        import numpy as np
        def cell(value, width): return str(value).encode('ascii').ljust(width, b' ')
        head = b'\xffBIOSEMI' + b''.join(cell(v, w) for v, w in [
            ('', 80), ('', 80), ('01.01.01', 8), ('00.00.00', 8), (768, 8), ('', 44), (2, 8), (1, 8), (2, 4)])
        fields = [(16, ['Cz', 'EOG']), (80, ['', '']), (8, ['uV', 'uV']),
                  (8, [-8388608, -8388608]), (8, [8388607, 8388607]),
                  (8, [-8388608, -8388608]), (8, [8388607, 8388607]),
                  (80, ['', '']), (8, [100, 50]), (32, ['', ''])]
        payload = []
        for second in range(2):
            for n, offset in [(100, 10), (50, -30)]:
                values = (np.arange(n, dtype=np.int32) + second * n + offset) & 0xffffff
                payload.append(np.column_stack([values & 255, values >> 8 & 255, values >> 16 & 255]).astype('u1').tobytes())
        path = self.root / 'mixed.bdf'; path.write_bytes(head + b''.join(cell(v, w) for w, row in fields for v in row) + b''.join(payload))
        reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
        metadata = reader.metadata(); streams = reader.describe()['streams']
        self.assertEqual([c['sampling_rate_hz'] for c in metadata['channels']], [100., 50.])
        self.assertEqual(len(streams), 2)
        stream = next(s for s in streams if s['sampling_frequency_hz'] == 50.)
        values = reader.read_window(stream['stream_id'], stream['segments'][0]['segment_id'], ['fixture:ch:1'], 50, 75)
        np.testing.assert_array_equal(values[0], (np.arange(50, 75) - 30) * 1e-6)
        with self.assertRaisesRegex(ValueError, 'native sample clock'): build_plan(qc_record(path, metadata, [0, 1]))

    def test_real_edf_and_bdf_tal_gap_is_rejected_at_inspection(self):
        from brainelecqc.readers.edf import EdfBdfReader
        for bdf in (False, True):
            path = native_tal_fixture(self.root, bdf=bdf, onsets=('0', '2'))
            original = path.read_bytes()
            raw = EdfBdfReader(path, 'raw').describe()
            self.assertTrue(all(len(s['segments']) == 2 for s in raw['streams']))
            with self.subTest(bdf=bdf), self.assertRaisesRegex(ValueError, '不支持此 EDF/BDF TAL 时钟布局'):
                inspect_recording(path)
            self.assertEqual(path.read_bytes(), original)

    def test_real_edf_and_bdf_nonzero_tal_origin_is_rejected(self):
        from brainelecqc.readers.edf import EdfBdfReader
        for bdf in (False, True):
            path = native_tal_fixture(self.root, bdf=bdf, onsets=('0.25', '1.25'))
            raw = EdfBdfReader(path, 'raw').describe()
            self.assertTrue(all(len(s['segments']) == 1 for s in raw['streams']))
            self.assertEqual(raw['streams'][0]['segments'][0]['recording_start_seconds'], .25)
            with self.subTest(bdf=bdf), self.assertRaisesRegex(ValueError, '不表示文件必然损坏'):
                open_reader(path, 'fixture')

    def test_contiguous_edf_bdf_tal_keeps_all_native_samples_and_units(self):
        import numpy as np
        for bdf in (False, True):
            path = native_tal_fixture(self.root, bdf=bdf)
            reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
            self.assertEqual(reader.metadata()['duration_seconds'], 2.)
            self.assertEqual(reader.metadata()['format'], 'BDF' if bdf else 'EDF')
            for stream in reader.describe()['streams']:
                seg = stream['segments'][0]
                values = reader.read_window(stream['stream_id'], seg['segment_id'], [stream['channels'][0]['channel_id']], 0, stream['sample_count'])
                np.testing.assert_allclose(values[0], np.arange(stream['sample_count']) * 1e-6, rtol=0, atol=1e-15)
            self.assertEqual([c['sampling_rate_hz'] for c in reader.metadata()['channels']], [100., 50.])

    def test_subnanosecond_zero_tolerance_remains_readable_without_losing_source_value(self):
        from ephys_qc.runtime import _read_window
        path = native_tal_fixture(self.root, onsets=('0.0000000001', '1.0000000001'))
        reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
        description = reader.describe()
        segment = description['streams'][0]['segments'][0]
        self.assertEqual(segment['source_recording_start_seconds'], 1e-10)
        self.assertEqual(segment['recording_start_seconds'], 0.)
        state = {'reader': reader, 'description': description}
        _read_window(state, {'selection': {'eeg_indices': [0], 'reference_indices': {}, 'start_seconds': 0., 'duration_seconds': 2.},
                             'method_config': {'comparison_groups': None}})
        self.assertEqual(state['recording']['start_sample'], 0)
        self.assertEqual(state['recording']['stop_sample'], 200)

    def test_source_index_order_is_preserved_and_unsupported_duplicate_brainvision_is_explicit(self):
        import numpy as np
        path, expected = brainvision_fixture(self.root)
        reader, _ = self.read(path)
        desc = reader.describe(); stream = desc['streams'][0]; seg = stream['segments'][0]
        self.assertEqual([c['raw_name'] for c in stream['channels']], ['Cz', 'Pz'])
        values = reader.read_window(stream['stream_id'], seg['segment_id'], ['fixture:ch:1', 'fixture:ch:0'], 100, 120)
        np.testing.assert_allclose(values, expected[[1, 0], 100:120], rtol=0, atol=1e-18)
        reader.close()
        path, _ = brainvision_fixture(self.root, ('duplicate', 'duplicate'))
        with self.assertRaisesRegex(ValueError, '重复通道名'): open_reader(path)

    def test_eeglab_external_fdt_and_embedded_mat_have_correct_microvolt_scaling(self):
        import numpy as np
        for embedded in (False, True):
            path, expected = eeglab_fixture(self.root, embedded=embedded)
            reader, actual = self.read(path)
            np.testing.assert_allclose(actual, expected[:, 100:170], rtol=0, atol=1e-18)
            self.assertEqual(len(reader.metadata()['source_files']), 1 if embedded else 2)
            self.assertEqual(reader.metadata()['annotations']['count'], 1)
            reader.close()

    def test_eeglab_removed_boundary_splits_without_removing_stored_postboundary_data(self):
        path, _ = eeglab_fixture(self.root, boundary=True)
        reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
        segments = reader.describe()['streams'][0]['segments']
        self.assertEqual([(s['start_sample'], s['stop_sample']) for s in segments], [(0, 200), (200, 400)])
        record = qc_record(path, reader.metadata())
        record['default_config']['selection'].update(start_seconds=1.5, duration_seconds=1.)
        with self.assertRaisesRegex(ValueError, '连续段'): build_plan(record)

    def test_fif_keeps_nonzero_source_origin_and_mixed_channel_units_without_projection(self):
        import numpy as np
        path, expected = fif_fixture(self.root)
        reader, actual = self.read(path)
        np.testing.assert_array_equal(actual, expected[:, 100:170])
        meta = reader.metadata()
        self.assertEqual(meta['clock']['first_sample'], 500)
        self.assertEqual(meta['clock']['first_time_seconds'], 5.)
        self.assertEqual([c['channel_type'] for c in meta['channels']], ['eeg', 'mag', 'eog'])
        self.assertEqual([c['unit'] for c in meta['channels']], ['V', 'T', 'V'])
        self.assertAlmostEqual(reader.describe()['events'][0]['onset_seconds'], 1.)
        self.assertEqual(reader.describe()['processing_applied'], [])
        self.assertTrue(meta['declared_filters']['verified_declaration'])

    def test_mixed_fif_non_eeg_type_or_non_scalp_record_cannot_enter_qc(self):
        path, _ = fif_fixture(self.root); meta = inspect_recording(path)
        self.assertEqual(build_plan(qc_record(path, meta, [0]))['input_modality']['value'], 'scalp_eeg')
        with self.assertRaises(ValueError): build_plan(qc_record(path, meta, [1]))
        record = qc_record(path, meta, [0]); record['modality'] = 'seeg'
        with self.assertRaises(ValueError): build_plan(record)
        del record['modality']
        with self.assertRaises(ValueError): build_plan(record)

    def test_fif_acquisition_skip_excluded_from_native_segments(self):
        path, _ = fif_fixture(self.root, skip=True)
        reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
        segments = reader.describe()['streams'][0]['segments']
        self.assertEqual([(s['start_sample'], s['stop_sample']) for s in segments], [(500, 700), (750, 900)])

    def test_brainvision_unsafe_data_or_marker_reference_is_rejected_before_mne_open(self):
        path, _ = brainvision_fixture(self.root)
        original = path.read_text()
        for text in [original.replace('DataFile=signal.eeg', 'DataFile=../signal.eeg'),
                     original.replace('MarkerFile=signal.vmrk', 'MarkerFile=/tmp/marker.vmrk')]:
            path.write_text(text)
            with patch('mne.io.read_raw_brainvision') as open_:
                with self.assertRaises(ValueError): open_reader(path)
                open_.assert_not_called()

    def test_corrupt_format_parser_errors_are_client_errors_without_internal_paths(self):
        for suffix in ('.vhdr', '.set', '.fif'):
            path = self.root / ('broken' + suffix); path.write_bytes(b'not a recording')
            with self.subTest(suffix=suffix), self.assertRaises(ValueError) as failure:
                inspect_recording(path)
            self.assertNotIn(str(self.root), str(failure.exception))
        path = self.root / 'missing_keys.vhdr'
        path.write_text('Brain Vision Data Exchange Header File Version 1.0\n[Common Infos]\nDataFile=unknown.eeg\n')
        with self.assertRaises(ValueError): inspect_recording(path)

    def test_eeglab_unsafe_reference_truncated_fdt_and_epochs_are_rejected(self):
        from scipy.io import loadmat, savemat
        path, _ = eeglab_fixture(self.root)
        (self.root / 'signal.fdt').write_bytes(b'1')
        with self.assertRaisesRegex(ValueError, 'FDT'): inspect_recording(path)
        path, _ = eeglab_fixture(self.root)
        eeg = loadmat(path, simplify_cells=True)['EEG']; eeg['data'] = '../signal.fdt'; savemat(path, {'EEG': eeg})
        with patch('mne.io.read_raw_eeglab') as open_:
            with self.assertRaises(ValueError): inspect_recording(path)
            open_.assert_not_called()
        eeg['data'] = 'signal.fdt'; eeg['trials'] = 2; savemat(path, {'EEG': eeg})
        with self.assertRaisesRegex(ValueError, 'epochs'): inspect_recording(path)

    def test_fif_split_reference_is_rejected_before_loading_referenced_source(self):
        from mne._fiff.write import start_file, write_string, end_file
        from mne._fiff.constants import FIFF
        path = self.root / 'split_raw.fif'
        handle = start_file(path); write_string(handle, FIFF.FIFF_REF_FILE_NAME, '/outside/private.fif'); end_file(handle)
        with patch('mne.io.read_raw_fif') as open_:
            with self.assertRaisesRegex(ValueError, 'split FIF'): inspect_recording(path)
            open_.assert_not_called()

    def test_hdf5_external_link_is_rejected_before_eeglab_parser(self):
        import h5py
        path = self.root / 'external.set'
        with h5py.File(path, 'w') as handle: handle['outside'] = h5py.ExternalLink('/outside/data.h5', '/samples')
        with patch('mne.io.eeglab.eeglab._check_load_mat') as parse:
            with self.assertRaisesRegex(ValueError, '外部'): inspect_recording(path)
            parse.assert_not_called()

    def test_source_mutation_and_invalid_windows_are_rejected(self):
        path, _ = brainvision_fixture(self.root)
        reader, _ = self.read(path)
        stream = reader.describe()['streams'][0]; seg = stream['segments'][0]
        for start, stop, names in [(0, 401, ['fixture:ch:0']), (True, 3, ['fixture:ch:0']),
                                   (3, 3, ['fixture:ch:0']), (0, 3, ['fixture:ch:0'] * 2)]:
            with self.assertRaises(ValueError): reader.read_window(stream['stream_id'], seg['segment_id'], names, start, stop)
        data = self.root / 'signal.eeg'; data.write_bytes(data.read_bytes()[:-2] + b'xx')
        with self.assertRaisesRegex(ValueError, '改变'): reader.describe()

    def test_plan_freezes_public_reader_metadata_and_changes_with_companion_identity(self):
        path, _ = brainvision_fixture(self.root); metadata = inspect_recording(path)
        record = qc_record(path, metadata)
        plan = build_plan(record, ['M03'])
        metadata['channels'][0]['name'] = 'changed outside plan'
        self.assertEqual(plan['input_metadata']['channels'][0]['name'], 'Cz')
        self.assertNotEqual(plan['plan_id'], build_plan(record, ['M03'])['plan_id'])
        record['expected_source_files'] = [{'path': str(self.root / f['name']), 'sha256': f['sha256']} for f in metadata['source_files']]
        first = build_plan(record, ['M03'])['plan_id']
        record['expected_source_files'].reverse()
        self.assertEqual(first, build_plan(record, ['M03'])['plan_id'])
        record['expected_source_files'][0]['sha256'] = '0' * 64
        self.assertNotEqual(first, build_plan(record, ['M03'])['plan_id'])

    def test_runtime_uses_new_reader_and_preserves_hashes_without_full_pipeline_wrapper(self):
        from ephys_qc.runtime import execute
        path, _ = brainvision_fixture(self.root); metadata = inspect_recording(path)
        record = qc_record(path, metadata)
        record['expected_source_files'] = [{'path': str(self.root / f['name']), 'sha256': f['sha256']} for f in metadata['source_files']]
        result = execute({'input': record, 'selected_modules': ['M03']}, self.root / 'job', lambda *_: None)
        self.assertNotEqual(result['status'], 'failed')
        self.assertEqual(result['recording']['source_indices'], [0, 1])
        self.assertEqual(result['recording']['unit'], 'V')
        self.assertEqual(len(result['data_sha256']), 64)
        self.assertEqual(len(result['source_files']), 3)
        self.assertEqual(next(m for m in result['modules'] if m['id'] == 'M03')['status'], 'partial')
        self.assertTrue((self.root / 'job' / 'artifacts' / 'report.html').is_file())
        record['expected_source_files'][1]['sha256'] = '0' * 64
        failed = execute({'input': record, 'selected_modules': []}, self.root / 'tampered-job', lambda *_: None)
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['modules'][0]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
