"""Basic iEEG routing, original MNE behavior, and saved-evidence report checks."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from ephys_qc.extensions import run_extension
from ephys_qc.ieeg_baseline import FLAT_PARAMETERS
from ephys_qc.recommendations import recommend
from ephys_qc.visualizations.render import render_gallery
from ephys_qc.visualizations.evidence import read_evidence
from test_neuromodal_routes import recording
from ieeg_report import collect


class BaselineTests(unittest.TestCase):
    def test_real_mne_preserves_contact_types_positions_and_input(self):
        data=np.random.default_rng(44).normal(size=(3,10000))*1e-5
        data[0,:]=0
        data[1,2000:2080]=0  # longer than 50 ms, less than 5% of this window
        data[2,3000:3020]=0  # quantization-like short plateau is not selected
        before=data.copy()
        for modality in ('ecog','seeg'):
            result=run_extension('mne_amplitude',data,1000,['A1','A2','A3'],120,FLAT_PARAMETERS,facts={'modality':modality})
            self.assertEqual(result['status'],'completed')
            self.assertEqual(result['channel_type'],modality)
            self.assertEqual(result['bad_channels'],['A1'])
            intervals=[c for c in result['candidates'] if c['localization']=='interval_only']
            self.assertEqual(len(intervals),1)
            self.assertAlmostEqual(intervals[0]['start_seconds'],122)
            self.assertAlmostEqual(intervals[0]['stop_seconds'],122.079)
            self.assertIsNone(intervals[0]['channel_index'])
            self.assertTrue(result['can_output_score'])
            self.assertEqual(len(result['score_outputs']),2)
            np.testing.assert_array_equal(data,before)

    def test_proposal_is_explicit_and_respects_custom_parameters(self):
        for modality in ('ecog','seeg'):
            source=recording(modality);original=copy.deepcopy(source)
            proposal=recommend(source)
            self.assertTrue(proposal['can_apply'])
            self.assertEqual(proposal['qc_config']['method_config']['extension_parameters']['mne_amplitude'],FLAT_PARAMETERS)
            self.assertEqual(proposal['qc_config']['scoring']['weights'] if 'scoring' in proposal['qc_config'] else {},{})
            custom=recommend(source,{'method_config':{'extensions':['mne_amplitude'],'extension_parameters':{'mne_amplitude':{'min_duration_seconds':.3}}}})
            self.assertEqual(custom['qc_config']['method_config']['extension_parameters']['mne_amplitude']['min_duration_seconds'],.3)
            self.assertEqual(source,original)
        self.assertNotIn('mne_amplitude',recommend(recording('extracellular'))['qc_config']['method_config']['extensions'])

    def test_continuous_charts_read_saved_shape_and_do_not_invent_hits(self):
        spectral={'psd':{'frequencies_hz':[0,1,2], 'power_v2_hz':[[0,1e-12,2e-12]],'channels':[{'channel_id':'source:4','channel_name':'G1','status':'computed'}]},
            'line_noise':{'observations':[{'channel_id':'source:4','channel_name':'G1','nominal_hz':50,'half_width_hz':1,'status':'computed','band_power_v2':3e-12,'artifact_classification':'not_performed'}]}}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'M04_spectral.json';p.write_text(json.dumps(spectral))
            reduced=read_evidence(p)
        evidence={'M04_spectral.json':reduced,'M05_channel_description.json':{'channels':[{'channel_name':'G1','rms_volts':2e-6,'peak_to_peak_volts':8e-6}]}}
        html=render_gallery({'artifacts':[{'name':n} for n in evidence]},evidence.__getitem__,selected=['psd','interference','channel_metrics'])
        for value in ['G1','触点 RMS','触点峰峰值','50 Hz 邻域功率','μV²','原始输入 · Welch PSD']:
            self.assertIn(value,html)
        for value in ['没有有效的正频率 PSD','工频命中窗 / 可评窗口','BrainElecQC / PREP']:
            self.assertNotIn(value,html)
        self.assertEqual(reduced['line_noise']['observations'][0]['band_power_v2'],3e-12)

    def test_pooling_preserves_duplicate_labels_and_missing_flat_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            windows=[{'id':f'w{i}','start_seconds':i*10,'duration_seconds':10} for i in (0,1)]
            for i in (0,1):
                rows=[{'channel_id':f'source:{n}','channel_name':'A1','source_index':n,'sample_count':100,'finite_sample_count':100,'nonfinite_sample_count':0,'rms_volts':(i+1)*1e-6,'peak_to_peak_volts':(i+2)*1e-6} for n in (0,1)]
                (root/f'w{i}--M05_channel_description.json').write_text(json.dumps({'channels':rows}))
            (root/'w0--M03_mne_amplitude.json').write_text(json.dumps({'status':'completed','candidates':[{'channel_name':'A1 [1]','localization':'channel_only'}],'channel_mapping':[{'adapter_name':'A1 [1]','raw_name':'A1','channel_id':'source:1'}]}))
            (root/'w1--M03_mne_amplitude.json').write_text(json.dumps({'status':'failed','calculated':False,'reason':'nonfinite'}))
            result=collect(root,windows)
        self.assertEqual(len(result['contacts']),2)
        self.assertAlmostEqual(result['contacts'][0]['rms'],np.sqrt(2.5)*1e-6)
        self.assertEqual(result['flats'][0]['channel_id'],'source:1')
        self.assertEqual(result['flat_windows'],1)
        self.assertEqual(result['sample_count'],400)
        self.assertEqual(result['flat_failures'],['nonfinite'])


if __name__=='__main__':unittest.main()
