"""Native clocks, subset/gain calibration and explicit unsupported boundaries."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.readers import detect_format, open_reader, inspect_recording


def spikeglx_fixture(root, band='ap', probe=0, overrides=None):
    import numpy as np
    # Source-acquired AP1/AP3 or LF1/LF3; never assume saved index == acquired index.
    np2 = probe in {21, 24}
    subset = '1,3,4' if np2 else '1,3,8' if band == 'ap' else '5,7,8'
    rows = ('(0,4)' + ''.join(f'({i} 0 0 {100 + 100*i} {20 + 10*i} 1)' for i in range(4)) if not np2 else
            f'({probe},4)' + ''.join(f'({i} 0 0 {i})' if probe == 21 else f'({i} 0 0 0 {i})' for i in range(4)))
    data = np.array([[-512, 0, 511, 1, -1, 34, 123, 3], [1, 10, -5, 77, 2, 42, -99, 6],
                     [0, 1, 64, -32768, -1, 0, 1, 64]], dtype='<i2').T
    meta = {'typeThis': 'imec', 'imDatPrb_type': str(probe), 'imAiRangeMax': '.6',
        'imMaxInt': '8192' if np2 else '512', 'acqApLfSy': '4,0,1' if np2 else '4,4,1',
        'snsApLfSy': '2,0,1' if band == 'ap' else '0,2,1', 'snsSaveChanSubset': subset,
        'nSavedChans': '3', 'imSampRate': '30000' if band == 'ap' else '2500',
        'firstSample': '456', 'fileSizeBytes': str(data.nbytes),
        'fileTimeSecs': str(len(data) / (30000 if band == 'ap' else 2500)), '~imroTbl': rows}
    if overrides:
        meta.update(overrides)
    path = root / ('record.imec0.' + band + '.bin')
    path.write_bytes(data.tobytes())
    path.with_suffix('.meta').write_text('\n'.join(f'{k}={v}' for k, v in meta.items()) + '\n')
    return path, data


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Requires NumPy scientific environment')
class SpikeGLXReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def reader(self, **kwargs):
        path, data = spikeglx_fixture(self.root, **kwargs)
        reader = open_reader(path, 'fixture'); self.addCleanup(reader.close)
        return reader, path, data

    def read(self, reader, indices=(0, 1), representation='physical'):
        stream = reader.describe()['streams'][0]
        return reader.read_window(stream['stream_id'], stream['segments'][0]['segment_id'],
                                  [f'fixture:ch:{i}' for i in indices], 456, 464, representation)

    def test_ap_subset_per_channel_calibration_clock_and_metadata(self):
        import numpy as np
        reader, path, raw = self.reader()
        self.assertEqual(detect_format(path), 'SpikeGLX')
        expected = raw[:, :2].T.astype(float) * np.array([.6 / 512 / 200, .6 / 512 / 400])[:, None]
        np.testing.assert_array_equal(self.read(reader), expected)
        m = reader.metadata(); d = reader.describe()
        self.assertEqual([c['acquired_index'] for c in m['channels']], [1, 3, 8])
        self.assertEqual(m['modality_evidence']['value'], 'extracellular')
        self.assertEqual(m['channels'][2]['channel_type'], 'stim')
        self.assertEqual(m['acquisition']['stream_band'], 'ap')
        self.assertEqual(m['continuous_segments'][0]['recording_start_seconds'], 0)
        self.assertEqual(m['clock']['first_sample'], 456)
        self.assertEqual(d['processing_applied'], [])
        self.assertEqual(d['events'], [])
        self.assertFalse(m['annotations']['available'])
        self.assertTrue(all('path' not in f for f in m['source_files']))
        json.dumps(m, allow_nan=False)

    def test_lf_uses_lf_gain_and_own_sample_clock(self):
        import numpy as np
        reader, _, raw = self.reader(band='lf')
        np.testing.assert_array_equal(self.read(reader), raw[:, :2].T.astype(float) * np.array([.6/512/30, .6/512/50])[:,None])
        self.assertEqual(reader.metadata()['acquisition']['sampling_rate_hz'], 2500.)

    def test_np2_fixed_gain_single_and_four_shank(self):
        import numpy as np
        for probe in (21, 24):
            reader, _, raw = self.reader(probe=probe)
            np.testing.assert_array_equal(self.read(reader), raw[:, :2].T.astype(float) * (.6 / 8192 / 80))
            self.assertEqual(reader.metadata()['acquisition']['probe_type'], probe)
            reader.close()

    def test_digital_bytes_and_sync_word_are_never_voltage(self):
        import numpy as np
        reader, _, raw = self.reader()
        np.testing.assert_array_equal(self.read(reader, (2, 0), 'digital'), raw[:, [2, 0]].T)
        np.testing.assert_array_equal(self.read(reader, (2,))[0], raw[:,2].view(np.uint16))
        channel = reader.describe()['streams'][0]['channels'][2]
        self.assertEqual(channel['unit'], 'bits'); self.assertIsNone(channel['digital_to_physical_scale'])

    def test_unregistered_binary_or_missing_meta_rejected(self):
        p = self.root / 'unknown.bin'; p.write_bytes(b'12345678')
        with self.assertRaises(ValueError): inspect_recording(p)
        p = self.root / 'unknown.ap.bin'; p.write_bytes(b'12345678')
        with self.assertRaisesRegex(ValueError, '伴随文件'): inspect_recording(p)
        p.write_bytes(b'0       ')  # Valid ADC words must not masquerade as an EDF header.
        self.assertEqual(detect_format(p),'SpikeGLX')
        with self.assertRaisesRegex(ValueError, '伴随文件'): inspect_recording(p)

    def test_incompatible_or_unproven_calibration_rejected(self):
        cases = [{'imDatPrb_type':'2013'}, {'imDatPrb_type':'NaN'}, {'imAiRangeMax':'nan'},
                 {'imMaxInt':'32768'}, {'~imroTbl':'(0,4)(0 0 0 0 10 1)'},
                 {'typeThis':'nidq'}, {'imSampRate':'0'}, {'firstSample':'-1'}]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                p,_=spikeglx_fixture(self.root,overrides=overrides)
                with self.assertRaises(ValueError): inspect_recording(p)

    def test_np2_conflicting_gain_and_lf_rejected(self):
        for band, extra in [('ap', {'imChan0apGain':'100'}), ('lf', {})]:
            p,_=spikeglx_fixture(self.root, band=band, probe=21, overrides=extra)
            with self.assertRaises(ValueError): inspect_recording(p)

    def test_part_number_imro_headers_require_known_consistent_mapping(self):
        for probe, part in [(0,'NP1010'), (21,'NP2000'), (24,'NP2010')]:
            p,_=spikeglx_fixture(self.root,probe=probe)
            meta=p.with_suffix('.meta')
            text=meta.read_text().replace(f'~imroTbl=({probe},4)',f'~imroTbl=({part},4)')
            meta.write_text(text+'imDatPrb_pn='+part+'\n')
            self.assertEqual(inspect_recording(p)['acquisition']['probe_type'],probe)
            meta.write_text(text+'imDatPrb_pn=NPUNKNOWN\n')
            with self.assertRaisesRegex(ValueError,'部件号'):inspect_recording(p)

    def test_truncated_or_inconsistent_frames_rejected(self):
        for changes in [{'fileSizeBytes':'100'}, {'fileTimeSecs':'20'}, {'nSavedChans':'2'},
                        {'snsSaveChanSubset':'3,1,8'}, {'snsSaveChanSubset':'1,1,8'},
                        {'snsSaveChanSubset':'1,3,100'}, {'snsApLfSy':'0,2,1'}]:
            p,_=spikeglx_fixture(self.root,overrides=changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError): inspect_recording(p)
        p,_=spikeglx_fixture(self.root); p.write_bytes(p.read_bytes()[:-1])
        with self.assertRaises(ValueError): inspect_recording(p)

    def test_header_duplicate_keys_and_companion_symlink_rejected(self):
        p,_=spikeglx_fixture(self.root); meta=p.with_suffix('.meta')
        with meta.open('a') as f:f.write('nSavedChans=3\n')
        with self.assertRaisesRegex(ValueError,'重复键'): inspect_recording(p)
        p,_=spikeglx_fixture(self.root); actual=self.root/'other.meta';meta.rename(actual);meta.symlink_to(actual)
        with self.assertRaisesRegex(ValueError,'符号链接'): inspect_recording(p)

    def test_source_mutation_guard(self):
        reader,p,_=self.reader();p.with_suffix('.meta').write_text('changed=1\n')
        with self.assertRaisesRegex(ValueError,'发生改变'): reader.metadata()

    def test_declared_sha1_must_match_and_cannot_be_silently_repaired(self):
        import hashlib
        p,_=spikeglx_fixture(self.root)
        meta=p.with_suffix('.meta')
        with meta.open('a') as f:f.write('fileSHA1='+hashlib.sha1(p.read_bytes()).hexdigest().upper()+'\n')
        self.assertEqual(inspect_recording(p)['acquisition']['declared_sha1_status'],'verified')
        raw=bytearray(p.read_bytes());raw[0]^=1;p.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'fileSHA1'):inspect_recording(p)
        p,_=spikeglx_fixture(self.root,overrides={'fileSHA1':'invalid'})
        with self.assertRaisesRegex(ValueError,'fileSHA1'):inspect_recording(p)

    def test_window_limits_and_identity(self):
        reader,_,_=self.reader();s=reader.describe()['streams'][0];seg=s['segments'][0]
        for a,b,ids in [(0,1,['fixture:ch:0']), (456,465,['fixture:ch:0']), (456,457,[]),
                        (456,457,['fixture:ch:0']*2), (True,457,['fixture:ch:0'])]:
            with self.subTest(a=a,b=b,ids=ids),self.assertRaises(ValueError):
                reader.read_window(s['stream_id'],seg['segment_id'],ids,a,b)

    def test_channel_map_must_agree_with_source_subset(self):
        p,_=spikeglx_fixture(self.root,overrides={'~snsChanMap':'(4,4,1)(AP0;0:0)(AP3;3:3)(SY0;8:8)'})
        with self.assertRaisesRegex(ValueError,'snsChanMap'): inspect_recording(p)


if __name__ == '__main__':
    unittest.main()
