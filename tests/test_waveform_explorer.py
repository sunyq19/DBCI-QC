"""Extended review windows retain source identity, clocks and resource limits."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from review_workspace import ReviewWorkspace
from waveform_explorer import MAX_SECONDS, MAX_CHANNELS, window
import test_review_workspace as fixtures


class ExplorerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.WaveformContracts();self.fixture.setUp()
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.root.joinpath('request.json').write_text(json.dumps(fixtures.request_fixture()))
        self.workspace=ReviewWorkspace(self.root,reader_factory=self.fixture.factory)

    def test_context_preserves_native_segments_duplicate_names_and_hides_paths(self):
        data=self.workspace.waveform_context()
        channels=data['streams'][0]['channels']
        self.assertEqual(data['limits']['max_channels'],15)
        self.assertEqual([c['source_index'] for c in channels],[7,2])
        self.assertEqual([c['name'] for c in channels],['same','same'])
        self.assertEqual(data['streams'][0]['segments'],[
            {'segment_id':'a','start_seconds':0.,'stop_seconds':3.},
            {'segment_id':'b','start_seconds':3.5,'stop_seconds':6.}])
        self.assertTrue(data['frozen_source_verified']);self.assertTrue(self.fixture.closed)
        for value in ('source_path','sha256','/not-opened','record.fif'):
            self.assertNotIn(value,json.dumps(data))

    def test_context_refuses_changed_or_unverified_source(self):
        self.fixture.description['source_files'][0]['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'frozen'):self.workspace.waveform_context()
        self.workspace.request['input'].pop('expected_sha256')
        with self.assertRaisesRegex(ValueError,'原始记录'):self.workspace.waveform_context()

    def test_expanded_windows_can_go_beyond_qc_scope_and_keep_native_samples(self):
        import numpy as np
        stream=self.fixture.description['streams'][0]
        stream['sampling_frequency_hz']=100
        stream['segments']=[{'segment_id':'a','start_sample':12900,'stop_sample':18900,'recording_start_seconds':0.}]
        before=self.fixture.data.copy()
        with patch('scipy.signal.welch',side_effect=AssertionError('Viewer must not recalculate spectra')):
            wave=self.workspace.waveform_window(start_seconds=0,duration_seconds=60,channel_indices=[2,7])
        self.assertEqual(wave['duration_seconds'],MAX_SECONDS)
        self.assertEqual(wave['start_sample'],12900)
        self.assertEqual([c['source_index'] for c in wave['channels']],[2,7])
        self.assertEqual([c['unit'] for c in wave['channels']],['T','µV'])
        self.assertTrue(wave['frozen_source_verified']);self.assertFalse(wave['analysis_modified'])
        self.assertNotIn('psd',wave['channels'][0]);self.assertNotIn('source_samples',wave['channels'][0])
        self.assertLessEqual(len(wave['channels'][0]['values']),2000)
        np.testing.assert_array_equal(self.fixture.data,before)
        with self.assertRaises(ValueError):
            self.workspace.waveform(start_seconds=0,duration_seconds=60,channel_indices=[7])

    def test_hard_limits_gap_and_changed_source_remain_rejected(self):
        for query in [dict(duration_seconds=61,channel_indices=[7]),
                      dict(duration_seconds=2,channel_indices=list(range(16))),
                      dict(start_seconds=2.9,duration_seconds=1,channel_indices=[7]),
                      dict(start_seconds=-1,duration_seconds=1,channel_indices=[7]),
                      dict(duration_seconds=1,channel_indices=[7,7])]:
            with self.subTest(query=query),self.assertRaises(ValueError):
                self.workspace.waveform_window(**query)
        self.assertEqual(self.fixture.calls,[])
        self.fixture.description['source_files'][0]['sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'frozen'):
            self.workspace.waveform_window(duration_seconds=1,channel_indices=[7])

    def test_fifteen_channels_are_allowed_but_sixteen_rejected_before_read(self):
        from unittest.mock import Mock
        workspace=Mock()
        workspace.waveform.return_value={'frozen_source_verified':True,'channels':[{'source_index':i} for i in range(15)]}
        result=window(workspace,channel_indices=list(range(15)),duration_seconds=10)
        self.assertEqual(len(result['channels']),15)
        self.assertEqual(workspace.waveform.call_args.kwargs['channel_indices'],list(range(15)))
        workspace.waveform.reset_mock()
        with self.assertRaisesRegex(ValueError,'15'):
            window(workspace,channel_indices=list(range(16)),duration_seconds=10)
        workspace.waveform.assert_not_called()

    def test_later_segment_uses_recording_clock_without_concatenating_gap(self):
        wave=self.workspace.waveform_window(start_seconds=3.6,duration_seconds=.2,channel_indices=[2,7])
        self.assertEqual(wave['start_sample'],16500)
        self.assertAlmostEqual(wave['start_seconds'],3.6)
        self.assertEqual(wave['channels'][0]['times_seconds'],wave['channels'][1]['times_seconds'])

    def test_large_native_read_is_rejected_before_allocating(self):
        stream=self.fixture.description['streams'][0]
        stream['sampling_frequency_hz']=1_000_000
        stream['segments']=[{'segment_id':'a','start_sample':0,'stop_sample':100_000_000,'recording_start_seconds':0.}]
        with self.assertRaisesRegex(ValueError,'64 MiB'):
            self.workspace.waveform_window(start_seconds=0,duration_seconds=60,channel_indices=[7])
        self.assertEqual(self.fixture.calls,[])


if __name__=='__main__':unittest.main()
