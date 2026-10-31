"""NWB decoding, selection and provenance tests; synthetic values are not QC validation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.readers import open_reader, inspect_recording, detect_format

HAS_NWB = importlib.util.find_spec('pynwb') is not None


def nwb_fixture(path, *, multiple=False, units=False, only_units=False, timestamps=None,
                duplicate_labels=False, neuropixels=False, name='voltage', one_dim=False,
                spike_events=False, filtered=False):
    import numpy as np
    from hdmf.backends.hdf5.h5_utils import H5DataIO
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries, LFP, FilteredEphys, SpikeEventSeries
    nwb = NWBFile('Synthetic decoding test; not scientific data', 'fixture', datetime(2020, 1, 1, tzinfo=timezone.utc))
    device_args = {'name': 'Neuropixels_filename_is_not_model', 'description': 'No model claim'}
    if neuropixels:
        from pynwb.device import DeviceModel
        model = DeviceModel(name='Neuropixels 1.0', manufacturer='Imec', model_number='NP1000')
        nwb.add_device_model(model)
        device_args['model'] = model
    device = nwb.create_device(**device_args)
    group = nwb.create_electrode_group(name='group', description='test', location='brain area not a modality', device=device)
    nwb.add_electrode_column(name='label', description='Source channel label')
    for index, electrode_id in enumerate([101, 305, 999]):
        nwb.add_electrode(id=electrode_id, x=float(index), y=0., z=0., imp=np.nan,
                         location='motor cortex', filtering='unknown', group=group,
                         label='duplicate' if duplicate_labels else f'e{electrode_id}')
    rows = [2] if one_dim else [2, 0]
    region = nwb.create_electrode_table_region(region=rows, description='Noncontiguous IDs and reordered rows')
    values = np.arange(12, dtype=np.int16) if one_dim else np.arange(24, dtype=np.int16).reshape(12, 2)
    if not only_units:
        timing = {'timestamps': timestamps} if timestamps is not None else {'starting_time': 7.25, 'rate': 4.}
        raw = ElectricalSeries(name=name, data=H5DataIO(values, chunks=True, compression='gzip'), electrodes=region,
                               conversion=.001, channel_conversion=np.array([.5] if one_dim else [.5, 2.]),
                               offset=.125, description='Source processing description', comments='Source comments', **timing)
        nwb.add_acquisition(raw)
        if multiple:
            processing = nwb.create_processing_module(name='ecephys', description='processed')
            lfp = LFP(name='LFP')
            lfp.add_electrical_series(ElectricalSeries(name='same_name_lfp', data=np.arange(10, dtype=float).reshape(5, 2),
                electrodes=region, starting_time=90., rate=2., conversion=1e-6))
            processing.add(lfp)
        if filtered:
            processing = nwb.processing.get('ecephys') or nwb.create_processing_module(name='ecephys', description='processed')
            container = FilteredEphys(name='FilteredEphys')
            container.add_electrical_series(ElectricalSeries(name='filtered', data=values, electrodes=region,
                                                             starting_time=0., rate=4.))
            processing.add(container)
        if spike_events:
            nwb.add_acquisition(SpikeEventSeries(name='spike_events', data=np.ones((3, len(rows), 4)),
                                                electrodes=region, timestamps=np.array([.1, .4, .9])))
    if units or only_units:
        nwb.add_unit(id=42, spike_times=[.2, .3])
        nwb.add_unit(id=102, spike_times=[1.])
    with NWBHDF5IO(path, 'w') as io:
        io.write(nwb)
    return values


@unittest.skipUnless(HAS_NWB, 'Requires PyNWB scientific environment')
class NWBReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / 'fixture.nwb'

    def tearDown(self):
        self.temp.cleanup()

    def reader(self, *, stream_id=None, record_id='fixture'):
        reader = open_reader(self.path, record_id, stream_id=stream_id)
        self.addCleanup(reader.close)
        return reader

    def read(self, reader, indices=(0, 1), start=0, stop=12):
        stream = reader.describe()['streams'][0]
        return reader.read_window(stream['stream_id'], stream['segments'][0]['segment_id'],
                                  [stream['channels'][i]['channel_id'] for i in indices], start, stop)

    def test_calibration_dtr_rows_not_ids_original_order_and_native_clock(self):
        import numpy as np
        values = nwb_fixture(self.path)
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        reader = self.reader()
        expected = (values * .001 * np.array([.5, 2.]) + .125).T
        np.testing.assert_allclose(self.read(reader), expected, rtol=0, atol=1e-17)
        np.testing.assert_allclose(self.read(reader, indices=(1, 0), start=2, stop=7), expected[[1, 0], 2:7], rtol=0, atol=1e-17)
        metadata, description = reader.metadata(), reader.describe()
        self.assertEqual(metadata['selected_stream_id'], '/acquisition/voltage')
        self.assertEqual([c['electrode_row_index'] for c in metadata['channels']], [2, 0])
        self.assertEqual([c['electrode_id'] for c in metadata['channels']], [999, 101])
        self.assertEqual([c['name'] for c in metadata['channels']], ['e999', 'e101'])
        self.assertEqual(metadata['clock']['first_sample'], 0)
        self.assertEqual(metadata['clock']['source_starting_time_seconds'], 7.25)
        self.assertEqual(metadata['duration_seconds'], 3.)
        self.assertEqual(description['streams'][0]['segments'][0]['recording_start_seconds'], 0.)
        self.assertEqual(metadata['modality_evidence']['value'], 'unknown')
        self.assertTrue(all(c['channel_type'] == 'unknown' for c in metadata['channels']))
        self.assertTrue(metadata['capabilities']['electrode_mapping_verified'])
        self.assertEqual(metadata['acquisition']['description'], 'Source processing description')
        self.assertEqual(metadata['acquisition']['comments'], 'Source comments')
        self.assertEqual(metadata['acquisition']['raw_source'], 'unknown')
        self.assertIsNone(metadata['capabilities']['processed'])
        self.assertEqual(metadata['annotations'], description['annotations'])
        self.assertEqual(metadata['annotations']['extraction_status'], 'not_extracted')
        self.assertEqual(metadata['annotations']['time_reference'], 'not_mapped_to_selected_series')
        self.assertIsNone(metadata['annotations']['available'])
        self.assertIsNone(metadata['annotations']['count'])
        self.assertTrue(any('不表示文件中不存在标注' in warning for warning in metadata['warnings']))
        self.assertNotIn('path', metadata['source_files'][0])
        json.dumps(metadata, allow_nan=False)
        self.assertEqual(hashlib.sha256(self.path.read_bytes()).hexdigest(), digest)

    def test_multiple_streams_never_choose_by_order_name_or_record_id(self):
        nwb_fixture(self.path, multiple=True, units=True)
        reader = self.reader()
        metadata = reader.metadata()
        self.assertIsNone(metadata['selected_stream_id'])
        self.assertEqual(metadata['channels'], [])
        self.assertIsNone(metadata['annotations']['available'])
        self.assertIsNone(metadata['annotations']['count'])
        self.assertEqual(metadata['duration_seconds'], 0.)
        self.assertTrue(metadata['stream_selection_required'])
        self.assertEqual(len(metadata['available_streams']), 2)
        self.assertEqual(reader.describe()['streams'], [])
        self.assertEqual(metadata['nwb']['units_count'], 2)
        selected = self.reader(stream_id='/processing/ecephys/LFP/same_name_lfp', record_id='different')
        selected_metadata = selected.metadata()
        self.assertEqual(selected_metadata['duration_seconds'], 2.5)
        self.assertEqual(selected_metadata['channels'][0]['sampling_rate_hz'], 2.)
        self.assertEqual(selected_metadata['clock']['source_starting_time_seconds'], 90.)
        self.assertEqual(selected_metadata['acquisition']['stream_band'], 'lf')
        self.assertEqual(selected_metadata['acquisition']['processing_status'], 'processed')
        self.assertIs(selected_metadata['capabilities']['raw_source'], False)
        self.assertEqual(len(selected.describe()['streams']), 1)
        self.assertEqual(metadata['source_files'], selected_metadata['source_files'])

    def test_regular_timestamps_are_all_verified_in_chunks(self):
        import numpy as np
        nwb_fixture(self.path, timestamps=123. + np.arange(12) / 4.)
        with patch('ephys_qc.readers.nwb_reader.TIMESTAMP_CHUNK', 3):
            metadata = inspect_recording(self.path)
        self.assertEqual(metadata['clock']['verified_timestamp_count'], 12)
        self.assertEqual(metadata['clock']['source'], 'fully_verified_regular_timestamps')
        self.assertEqual(metadata['clock']['source_starting_time_seconds'], 123.)
        self.assertEqual(metadata['duration_seconds'], 3.)

    def test_timestamp_gap_backwards_nonfinite_and_cross_chunk_failure(self):
        import numpy as np
        for change in ('gap', 'backwards', 'nan', 'duplicate'):
            times = np.arange(12) / 4.
            times[7] = {'gap': 1.76, 'backwards': 1., 'nan': np.nan, 'duplicate': 1.5}[change]
            nwb_fixture(self.path, timestamps=times)
            with patch('ephys_qc.readers.nwb_reader.TIMESTAMP_CHUNK', 7):
                metadata = inspect_recording(self.path)
            with self.subTest(change=change):
                self.assertEqual(metadata['available_streams'][0]['status'], 'unsupported')
                self.assertEqual(metadata['channels'], [])
                with self.assertRaisesRegex(ValueError, '不可读'):
                    open_reader(self.path, stream_id='/acquisition/voltage')

    def test_units_only_is_not_waveform_and_keeps_count(self):
        nwb_fixture(self.path, only_units=True)
        metadata = inspect_recording(self.path)
        self.assertEqual(metadata['available_streams'], [])
        self.assertTrue(metadata['nwb']['units_present'])
        self.assertEqual(metadata['nwb']['units_count'], 2)
        self.assertEqual(metadata['nwb']['electrical_series_count'], 0)
        self.assertFalse(metadata['stream_selection_required'])
        self.assertEqual(metadata['channels'], [])

    def test_explicit_neuropixels_device_model_and_lfp_band(self):
        nwb_fixture(self.path, neuropixels=True, multiple=True)
        metadata = inspect_recording(self.path, stream_id='/acquisition/voltage')
        self.assertEqual(metadata['modality_evidence']['value'], 'extracellular')
        self.assertTrue(metadata['acquisition']['neuropixels_device_declared'])
        self.assertEqual(metadata['acquisition']['probe_model'], 'Neuropixels 1.0')
        self.assertEqual(metadata['acquisition']['probe_type'], 0)
        self.assertEqual(metadata['acquisition']['stream_band'], 'unknown')
        self.assertEqual(metadata['channels'][0]['channel_type_source'], 'file_declared')

    def test_neuropixels_name_and_anatomy_do_not_declare_device_or_ap(self):
        nwb_fixture(self.path, name='Neuropixels_AP_motor_cortex')
        metadata = inspect_recording(self.path)
        self.assertFalse(metadata['acquisition']['neuropixels_device_declared'])
        self.assertEqual(metadata['acquisition']['stream_band'], 'unknown')
        self.assertEqual(metadata['modality_evidence']['value'], 'unknown')

    def test_duplicate_labels_preserved_with_unique_channel_ids(self):
        nwb_fixture(self.path, duplicate_labels=True)
        reader = self.reader()
        self.assertEqual([c['name'] for c in reader.metadata()['channels']], ['duplicate', 'duplicate'])
        self.assertEqual([c['channel_id'] for c in reader.describe()['streams'][0]['channels']], ['fixture:ch:0', 'fixture:ch:1'])
        self.assertTrue(any('重复' in message for message in reader.metadata()['warnings']))

    def test_legacy_unit_is_read_from_hdf_attributes_not_pynwb_default(self):
        import h5py
        import numpy as np
        for unit, factor in [('volt', 1.), ('mV', 1e-3), ('microvolts', 1e-6), ('µV', 1e-6)]:
            values = nwb_fixture(self.path)
            with h5py.File(self.path, 'r+') as file:
                file['acquisition/voltage/data'].attrs['unit'] = unit
            with self.subTest(unit=unit):
                reader = self.reader()
                np.testing.assert_allclose(self.read(reader), ((values * .001 * [.5, 2.] + .125) * factor).T, rtol=1e-15, atol=1e-20)
                self.assertEqual(reader.metadata()['channels'][0]['source_unit'], unit)
                self.assertTrue(any('非规范' in text for text in reader.metadata()['warnings']))
                reader.close()

    def test_unknown_units_and_invalid_calibration_are_unsupported(self):
        import h5py
        import numpy as np
        cases = [('unit', 'counts'), ('conversion', 0.), ('conversion', -1.),
                 ('conversion', np.inf), ('offset', np.nan)]
        for attr, value in cases:
            nwb_fixture(self.path)
            with h5py.File(self.path, 'r+') as file:
                file['acquisition/voltage/data'].attrs[attr] = value
            with self.subTest(attr=attr, value=value):
                self.assertEqual(inspect_recording(self.path)['available_streams'][0]['status'], 'unsupported')

    def test_invalid_channel_conversion_and_electrode_mapping_rejected(self):
        import h5py
        for target, values in [('channel_conversion', [1.]), ('channel_conversion', [1., float('nan')]), ('electrodes', [999, 101])]:
            nwb_fixture(self.path)
            with h5py.File(self.path, 'r+') as file:
                dataset = file['acquisition/voltage/' + target]
                if len(values) == 2:
                    dataset[:] = values
                else:
                    attrs = dict(dataset.attrs)
                    del file['acquisition/voltage/' + target]
                    new = file['acquisition/voltage'].create_dataset(target, data=values)
                    for key, value in attrs.items():
                        new.attrs[key] = value
            with self.subTest(target=target, values=values):
                self.assertEqual(inspect_recording(self.path)['available_streams'][0]['status'], 'unsupported')

    def test_supported_stream_autoselects_when_other_stream_is_unsupported(self):
        import h5py
        nwb_fixture(self.path, multiple=True)
        with h5py.File(self.path, 'r+') as file:
            file['processing/ecephys/LFP/same_name_lfp/data'].attrs['unit'] = 'not_voltage'
        metadata = inspect_recording(self.path)
        self.assertEqual(metadata['selected_stream_id'], '/acquisition/voltage')
        self.assertEqual([s['status'] for s in metadata['available_streams']], ['available', 'unsupported'])

    def test_one_dimensional_voltage_and_small_chunks(self):
        import numpy as np
        values = nwb_fixture(self.path, one_dim=True)
        with patch('ephys_qc.readers.nwb_reader.READ_CHUNK_BYTES', 16):
            actual = self.read(self.reader(), indices=(0,), start=1, stop=11)
        np.testing.assert_allclose(actual[0], values[1:11] * .001 * .5 + .125, atol=1e-17, rtol=0)

    def test_window_budget_invalid_bounds_and_ids_reject(self):
        nwb_fixture(self.path)
        reader = self.reader()
        stream = reader.describe()['streams'][0]
        args = [stream['stream_id'], stream['segments'][0]['segment_id'], ['fixture:ch:0'], 0, 12]
        for index, value in [(0, 'wrong'), (1, 'wrong'), (2, []), (2, ['fixture:ch:0'] * 2),
                             (2, ['fixture:ch:9']), (3, -1), (3, True), (4, 13), (4, .5)]:
            changed = args.copy(); changed[index] = value
            with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                reader.read_window(*changed)
        with patch('ephys_qc.readers.nwb_reader.MAX_WINDOW_BYTES', 4), self.assertRaisesRegex(ValueError, '256 MiB'):
            reader.read_window(*args)
        with self.assertRaises(ValueError):
            reader.read_window(*args, representation='digital')

    def test_unknown_stream_and_no_selection_read_blocked(self):
        nwb_fixture(self.path, multiple=True)
        with self.assertRaisesRegex(ValueError, '未知'):
            open_reader(self.path, stream_id='/acquisition/nonexistent')
        with self.assertRaises(ValueError):
            self.reader().read_window('/acquisition/voltage', 'x', ['fixture:ch:0'], 0, 2)

    def test_external_link_cannot_be_hidden_under_soft_link(self):
        import h5py
        nwb_fixture(self.path)
        with h5py.File(self.path, 'r+') as file:
            file['z_external'] = h5py.ExternalLink('do-not-open.nwb', '/')
            file['a_alias'] = h5py.SoftLink('/z_external/missing')
        with self.assertRaisesRegex(ValueError, '外部链接'):
            open_reader(self.path)

    def test_internal_soft_link_allowed_and_cycle_rejected(self):
        import h5py
        nwb_fixture(self.path)
        with h5py.File(self.path, 'r+') as file:
            file['internal_alias'] = h5py.SoftLink('/acquisition/voltage/data')
        self.assertEqual(inspect_recording(self.path)['duration_seconds'], 3.)
        with h5py.File(self.path, 'r+') as file:
            file['cyclic'] = h5py.SoftLink('/cyclic')
        with self.assertRaisesRegex(ValueError, '循环'):
            open_reader(self.path)

    def test_external_dataset_and_virtual_dataset_rejected_before_pynwb(self):
        import h5py
        for virtual in (False, True):
            nwb_fixture(self.path)
            with h5py.File(self.path, 'r+') as file:
                if virtual:
                    layout = h5py.VirtualLayout((2,), dtype='f8')
                    layout[:] = h5py.VirtualSource('missing.h5', 'x', shape=(2,))
                    file.create_virtual_dataset('unsafe', layout)
                else:
                    file.create_dataset('unsafe', shape=(2,), dtype='f8', external=[('missing.bin', 0, 16)])
            with self.subTest(virtual=virtual), self.assertRaisesRegex(ValueError, '外部原始|虚拟'):
                open_reader(self.path)

    def test_changed_source_detected_and_manifest_not_mutable(self):
        import os
        nwb_fixture(self.path)
        reader = self.reader()
        metadata = reader.metadata()
        metadata['available_streams'][0]['capabilities']['regular_sampling'] = False
        self.assertTrue(reader.metadata()['available_streams'][0]['capabilities']['regular_sampling'])
        os.utime(self.path, ns=(self.path.stat().st_atime_ns, self.path.stat().st_mtime_ns + 1000000))
        with self.assertRaisesRegex(ValueError, '发生改变'):
            reader.metadata()

    def test_hdf_container_and_nwb_major_version_required(self):
        import h5py
        self.path.write_bytes(b'not an HDF5 file')
        with self.assertRaisesRegex(ValueError, 'HDF5'):
            detect_format(self.path)
        nwb_fixture(self.path)
        with h5py.File(self.path, 'r+') as file:
            file.attrs['nwb_version'] = '3.0.0'
        with self.assertRaisesRegex(ValueError, 'NWB 2'):
            open_reader(self.path)

    def test_filtered_ephys_discovered_and_spike_event_series_excluded(self):
        nwb_fixture(self.path, filtered=True, spike_events=True)
        metadata = inspect_recording(self.path)
        self.assertEqual(metadata['nwb']['electrical_series_count'], 2)
        self.assertEqual({s['container_type'] for s in metadata['available_streams']}, {'NWBFile', 'FilteredEphys'})
        filtered = inspect_recording(self.path, stream_id='/processing/ecephys/FilteredEphys/filtered')
        self.assertEqual(filtered['acquisition']['stream_band'], 'unknown')
        self.assertIs(filtered['capabilities']['processed'], True)
        self.assertFalse(filtered['acquisition']['neuropixels_device_declared'])

    def test_time_units_not_assumed_to_be_seconds(self):
        import h5py
        import numpy as np
        for timestamps in (None, np.arange(12) / 4.):
            nwb_fixture(self.path, timestamps=timestamps)
            with h5py.File(self.path, 'r+') as file:
                name = 'timestamps' if timestamps is not None else 'starting_time'
                file['acquisition/voltage/' + name].attrs['unit'] = 'milliseconds'
            metadata = inspect_recording(self.path)
            self.assertEqual(metadata['available_streams'][0]['status'], 'unsupported')
            self.assertIn('时钟单位', metadata['available_streams'][0]['reason'])

    def test_float_nan_preserved_but_calibration_overflow_rejected(self):
        import h5py
        import numpy as np
        nwb_fixture(self.path)
        with h5py.File(self.path, 'r+') as file:
            group = file['acquisition/voltage']
            attrs = dict(group['data'].attrs)
            values = np.arange(24, dtype=float).reshape(12, 2)
            values[3, 0] = np.nan
            del group['data']
            dataset = group.create_dataset('data', data=values)
            for key, value in attrs.items():
                dataset.attrs[key] = value
        reader = self.reader()
        self.assertTrue(np.isnan(self.read(reader)[0, 3]))
        reader.close()
        with h5py.File(self.path, 'r+') as file:
            file['acquisition/voltage/data'][0, 0] = 1.7e308
            file['acquisition/voltage/data'].attrs['conversion'] = 100.
        with self.assertRaisesRegex(ValueError, '溢出'):
            self.read(self.reader())


if __name__ == '__main__':
    unittest.main()
