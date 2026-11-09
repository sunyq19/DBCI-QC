"""Original-library parity, routing and missing-evidence boundaries."""
import unittest
import numpy as np
from ephys_qc.voltage_methods import run_extension, evaluate_extension
from ephys_qc.method_scores import extension_outputs
from ephys_qc.neuropixels_scoring import state_output, attach_ap_identity


def facts(n=16,fs=2000,seconds=4,mode='extracellular',band='ap'):
    return dict(modality=mode,verified_voltage=True,n_eeg=n,sampling_rate_hz=fs,window_seconds=seconds,
        stream_band=band,probe_shanks=[0]*n,probe_positions_um=[[0.,i*20.] for i in range(n)])


class VoltageMethodsTests(unittest.TestCase):
    def test_line_original_kernel_detects_added_sine_and_retains_clock(self):
        fs=500;t=np.arange(4250)/fs;rng=np.random.default_rng(3)
        x=rng.normal(0,1e-6,(2,len(t)));x[0]+=30e-6*np.sin(2*np.pi*50*t);before=x.copy()
        f=facts(2,fs,8.5,'seeg');r=run_extension('ieeg_spectrum_fit',x,fs,['A','B'],17,{},facts=f)
        self.assertEqual(r['status'],'completed',r);self.assertEqual(r['assessed_windows'],4)
        self.assertEqual(r['unused_tail_seconds'],.5);self.assertGreaterEqual(r['candidate_windows'],2)
        self.assertEqual(r['candidates'][0]['start_seconds'],17);np.testing.assert_array_equal(x,before)
        score=extension_outputs('ieeg_spectrum_fit',r,'seeg')[0];self.assertEqual(score['assessed_amount'],4)
        self.assertEqual(evaluate_extension('ieeg_spectrum_fit',{**f,'preprocessing_notch_hz':[50,60]})['status'],'blocked')
        self.assertEqual(evaluate_extension('ieeg_spectrum_fit',{**f,'preprocessing_lowpass_hz':40})['status'],'blocked')

    def test_np_original_coherence_and_lf_parity(self):
        from spikeinterface import NumpyRecording
        from spikeinterface.preprocessing import detect_bad_channels
        for key,band,fs in [('spikeinterface_coherence_psd','ap',3000),('spikeinterface_lfp_neighbors','lf',500)]:
            f=facts(16,fs,4,band=band);rng=np.random.default_rng(7)
            common=rng.normal(0,2e-5,(1,fs*4));x=common+rng.normal(0,1e-6,(16,fs*4));x[5]=rng.normal(0,1e-4,fs*4)
            r=run_extension(key,x,fs,[f'C{i}' for i in range(16)],0,{},facts=f)
            self.assertEqual(r['status'],'completed',r)
            rec=NumpyRecording(x.T*1e6,fs,channel_ids=np.arange(16));rec.set_channel_gains(1.);rec.set_channel_offsets(0.);rec.set_channel_locations(np.array(f['probe_positions_um']))
            p=r['parameters'];kw=dict(chunk_duration_s=p['chunk_seconds'],num_random_chunks=20,seed=0)
            if band=='lf':rec.annotate(is_filtered=True);kw.update(method='neighborhood_r2',neighborhood_r2_threshold=.9,neighborhood_r2_radius_um=30.)
            else:kw.update(method='coherence+psd')
            _,labels=detect_bad_channels(rec,**kw)
            self.assertEqual([z['label'] for z in r['channel_labels']],list(labels))
            r['channel_mapping']=[dict(adapter_name=f'C{i}',channel_id=f'src:{i}') for i in range(16)]
            row=extension_outputs(key,r,'extracellular')[0];self.assertIsNotNone(row['value'])
            self.assertEqual(state_output([row])['value'],row['value'])
            self.assertEqual(evaluate_extension(key,{**f,'probe_positions_um':[None]*16})['status'],'blocked')
        self.assertEqual(evaluate_extension('spikeinterface_lfp_neighbors',facts())['status'],'blocked')
        f=facts(16,500,4,band='lf');f['probe_positions_um']=[[0.,i*100.] for i in range(16)]
        self.assertEqual(evaluate_extension('spikeinterface_lfp_neighbors',f)['status'],'blocked')

    def test_lof_groups_and_gate(self):
        f=facts(12,500,4,'seeg');x=np.random.default_rng(12).normal(0,1e-5,(12,2000));x[2]*=20
        self.assertEqual(evaluate_extension('ieeg_mne_lof',f)['status'],'blocked')
        f['comparison_group_labels']=['confirmed-group']*12
        r=run_extension('ieeg_mne_lof',x,500,[str(i) for i in range(12)],0,{'reference_confirmed':True},facts=f)
        self.assertEqual(r['status'],'completed',r);self.assertIn('2',r['bad_channels'])
        self.assertIsNotNone(extension_outputs('ieeg_mne_lof',r,'seeg')[0]['value'])

    def test_np_union_deduplicates_new_methods(self):
        from ephys_qc.method_scores import observation
        from ephys_qc.score_registry import SPECS
        keys=['spikeinterface_bad_channels','spikeinterface_coherence_psd']
        rows=[]
        for key in keys:
            r=observation(SPECS[key],1,4,scope=dict(start_seconds=0.,stop_seconds=1.,duration_seconds=1.))
            r['channel_evidence']=dict(assessed=['a','b','c','d'],candidates=['a']);rows.append(r)
        self.assertEqual(state_output(rows)['value'],75)
        rows[1]['channel_evidence']['candidates']=['b'];self.assertEqual(state_output(rows)['value'],50)

if __name__=='__main__':unittest.main()
