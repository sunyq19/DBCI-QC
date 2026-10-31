"""Real upstream calls, gating and source-clock/input-preservation contracts."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.research_runtime import IDS, evaluate_extension, run_extension
from ephys_qc.external_runtime import availability
from ephys_qc.planning import build_plan
from test_research_methods import record


def facts(count=16, fs=256, seconds=40, **kwargs):
    return {'modality':'scalp_eeg','verified_voltage':True,'n_eeg':count,
            'sampling_rate_hz':fs,'window_seconds':seconds,'reference_scheme':'common_reference',
            'comparison_groups':{'all':count}, **kwargs}


class ResearchGateTests(unittest.TestCase):
    def test_planning_does_not_read_any_file_or_import_scientific_libraries(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('planning must stay metadata-only')):
            for mid in IDS - {'spikeinterface_bad_channels'}:
                evaluate_extension(mid, facts())

    def test_no_cross_modality_or_missing_units(self):
        for mid in IDS:
            self.assertEqual(evaluate_extension(mid,None)['status'],'blocked')
            self.assertEqual(evaluate_extension(mid,facts(verified_voltage=False))['status'],'blocked')
        for mid in IDS - {'fieldtrip_zvalue','spikeinterface_bad_channels'}:
            self.assertEqual(evaluate_extension(mid,facts(modality='seeg'))['status'],'blocked')

    def test_asr_requires_explicit_calibration_rank_window_and_supported_rate(self):
        self.assertEqual(evaluate_extension('asr_bursts',facts())['status'],'blocked')
        for f,p in [(facts(fs=160),{}),(facts(seconds=20),{}),(facts(count=128,fs=100),{'window_seconds':.5}),
                    (facts(),{'calibration_start_seconds':20}),(facts(scope='recording'),{})]:
            self.assertEqual(evaluate_extension('asr_bursts',f,{'calibration_confirmed':True,**p})['status'],'blocked')
        self.assertEqual(evaluate_extension('asr_bursts',facts(),{'calibration_confirmed':True})['status'],'partial')
        r=record('scalp_eeg')
        with self.assertRaises(ValueError):
            build_plan(r,[],{'scope':'recording','method_config':{'extensions':['asr_bursts']}})

    def test_sparse_unknown_reference_unmeasurable_band_and_lf_block(self):
        for mid in ('faster_channels','asr_bursts','zapline_plus'):
            self.assertEqual(evaluate_extension(mid,facts(count=2))['status'],'blocked')
            self.assertEqual(evaluate_extension(mid,facts(reference_scheme='unknown'))['status'],'blocked')
        for mid in ('cleanline','zapline_plus'):
            self.assertEqual(evaluate_extension(mid,facts(fs=100))['status'],'blocked')
            self.assertEqual(evaluate_extension(mid,facts(preprocessing_lowpass_hz=40))['status'],'blocked')
        npfacts=facts(modality='extracellular',fs=30000,seconds=2,stream_band='ap',probe_shanks=[0]*16)
        self.assertEqual(evaluate_extension('spikeinterface_bad_channels',npfacts)['status'],'partial')
        for change in ({'stream_band':'lf'},{'probe_shanks':None},{'probe_shanks':[0]*15+[1]}):
            self.assertEqual(evaluate_extension('spikeinterface_bad_channels',{**npfacts,**change})['status'],'blocked')

    def test_strict_parameter_types_no_execution_paths(self):
        bad=[('cleanline',{'alpha':1}),('cleanline',{'line_frequency_hz':float('nan')}),
             ('faster_channels',{'max_iter':True}),('asr_bursts',{'calibration_confirmed':1}),
             ('spikeinterface_bad_channels',{'method':'coherence+psd'}),('zapline_plus',{'command':'anything'})]
        for mid,p in bad:
            with self.assertRaises(ValueError):evaluate_extension(mid,facts(),p)


SCIENTIFIC=all(importlib.util.find_spec(p) for p in ('numpy','mne_faster','spikeinterface'))
EXTERNAL=availability('fieldtrip_zvalue') is None


@unittest.skipUnless(SCIENTIFIC,'Optional scientific packages required')
class ResearchExecutionTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np=np;self.rng=np.random.default_rng(72)

    def run_method(self,mid,data,fs,p=None,context=None):
        before=data.copy(); names=[f'电极{i}' for i in range(len(data))]
        out=run_extension(mid,data,fs,names,73,p or {},facts=context or facts(count=len(data),fs=fs,seconds=data.shape[1]/fs))
        self.np.testing.assert_array_equal(data,before)
        self.assertTrue(out['input_unchanged']);self.assertEqual(out['automatic_actions'],[])
        json.dumps(out,allow_nan=False)
        self.assertEqual(out['status'],'completed',out['reason'])
        self.assertTrue(out['calculated']);self.assertEqual(out['review_status'],'pending')
        self.assertEqual(len(out['source']['implementation_sha256']),64)
        return out

    def test_faster_detects_injected_outlier_and_keeps_metric_attribution(self):
        x=self.rng.normal(0,20e-6,(24,256*12));x[7]*=30
        out=self.run_method('faster_channels',x,256)
        self.assertIn('电极7',out['by_metric']['variance'])
        self.assertEqual(out['segmentation']['ranges'][0]['start_seconds'],73)
        self.assertTrue(all(c['start_seconds'] is None for c in out['candidates']))

    def test_spikeinterface_preserves_per_shank_mapping_and_seed(self):
        x=self.rng.normal(0,20e-6,(16,60000));x[3]*=30
        meta=facts(fs=30000,seconds=2,modality='extracellular',stream_band='ap',probe_shanks=[1]*8+[0]*8)
        first=self.run_method('spikeinterface_bad_channels',x,30000,context=meta)
        second=self.run_method('spikeinterface_bad_channels',x,30000,context=meta)
        self.assertEqual(first['channel_labels'],second['channel_labels'])
        self.assertIn(3,[c['channel_index'] for c in first['candidates']])
        self.assertTrue(all(c['shank']==meta['probe_shanks'][c['channel_index']] for c in first['channel_labels']))

    def test_degenerate_input_and_fact_mismatch_cannot_be_success(self):
        data=self.rng.normal(0,1e-5,(16,256*12));data[0]=0
        for x,meta in [(data,facts(seconds=12)),(data+1e-5,facts(fs=128,seconds=12))]:
            out=run_extension('faster_channels',x,256,[str(i) for i in range(16)],0,{},facts=meta)
            self.assertEqual(out['status'],'blocked');self.assertFalse(out['calculated'])
        data[0,0]=self.np.nan
        with self.assertRaises(ValueError):run_extension('faster_channels',data,256,[str(i) for i in range(16)],0,{},facts=facts(seconds=12))

    @unittest.skipUnless(EXTERNAL,'Configured pinned Octave runtime required')
    def test_fieldtrip_absolute_sample_mapping_on_injected_step(self):
        x=self.rng.normal(0,1e-6,(8,256*12));x[2,256*7:]+=200e-6
        out=self.run_method('fieldtrip_zvalue',x,256,context=facts(count=8,seconds=12,modality='seeg'))
        self.assertTrue(any(c['start_seconds'] <= 80 <= c['stop_seconds'] for c in out['candidates']))
        for pair,candidate in zip(out['sample_intervals_one_based_inclusive'],out['candidates']):
            self.assertEqual(candidate['start_seconds'],73+(pair[0]-1)/256)
            self.assertEqual(candidate['stop_seconds'],73+pair[1]/256)

    @unittest.skipUnless(EXTERNAL,'Configured pinned Octave runtime required')
    def test_cleanline_known_tone_reduction_and_untouched_tail(self):
        n=256*9+37;t=self.np.arange(n)/256
        x=self.rng.normal(0,2e-6,(8,n))+80e-6*self.np.sin(2*self.np.pi*50*t)
        out=self.run_method('cleanline',x,256,{'window_seconds':2,'step_seconds':1})
        e=out['evaluation'];idx=self.np.argmin(abs(self.np.asarray(e['frequencies_hz'])-50))
        self.assertLess(e['mean_psd_after_v2_hz'][idx],.1*e['mean_psd_before_v2_hz'][idx])
        self.assertEqual(e['tail_samples_not_processed'],37)

    @unittest.skipUnless(EXTERNAL,'Configured pinned Octave runtime required')
    def test_asr_calibration_and_processing_are_separate_from_raw(self):
        x=self.rng.normal(0,20e-6,(8,256*40));x[2,256*35:256*36]*=100
        out=self.run_method('asr_bursts',x,256,{'calibration_confirmed':True})
        self.assertEqual(out['preprocessing']['calibration']['source_clock_start_seconds'],73)
        self.assertEqual(out['preprocessing']['calibration']['source_clock_stop_seconds'],103)
        self.assertNotEqual(out['evaluation']['input_sha256'],out['data_sha256'])
        self.assertNotEqual(out['evaluation']['input_sha256'],out['evaluation']['output_sha256'])
        self.assertEqual(set(out['calibration_state']),{'M','T','A','B'})
        self.assertFalse(out['evaluation']['cleaned_signal_exported'])

    @unittest.skipUnless(EXTERNAL,'Configured pinned Octave runtime required')
    def test_zapline_fixed_chunk_has_upstream_config_and_tone_effect(self):
        t=self.np.arange(256*32)/256
        x=self.rng.normal(0,2e-6,(8,len(t)))+50e-6*self.np.sin(2*self.np.pi*50*t)
        out=self.run_method('zapline_plus',x,256)
        self.assertIn('upstream_configuration',out);self.assertIn('upstream_analytics',out)
        self.assertFalse(out['evaluation']['original_signal_overwritten'])
        e=out['evaluation'];idx=self.np.argmin(abs(self.np.asarray(e['frequencies_hz'])-50))
        self.assertLess(e['mean_psd_after_v2_hz'][idx],.2*e['mean_psd_before_v2_hz'][idx])

    def test_unconfigured_runtime_is_unassessed_not_empty_success(self):
        x=self.rng.normal(0,20e-6,(8,256*12))
        with patch.dict(os.environ,{'DBCI_QC_METHODS_CONFIG':'/no/such/config.json'}):
            out=run_extension('fieldtrip_zvalue',x,256,[str(i) for i in range(8)],0,{},facts=facts(count=8,seconds=12))
        self.assertEqual(out['status'],'blocked');self.assertFalse(out['calculated'])


if __name__=='__main__':unittest.main()
