"""Method score contracts: counts, unions, missingness, opt-in and aggregation."""
import copy,math,unittest
from ephys_qc.method_scores import extension_outputs,observation,aggregate,pool_windows,prep_output,finalize
from ephys_qc.score_registry import SPECS,outputs
from ephys_qc.project_scoring import normalize,VERSION
from ephys_qc.method_registry import methods


def payload(names=('A','B'),candidates=()):
    return dict(status='completed',calculated=True,channel_names=list(names),candidates=list(candidates),
                range=dict(start_seconds=10.,stop_seconds=20.,duration_seconds=10.,sampling_rate_hz=2.,n_samples=20))

def channel(name):return dict(localization='channel_only',channel_name=name)
def interval(a,b,name=None):return dict(localization='channel_interval' if name else 'interval_only',channel_name=name,start_seconds=a,stop_seconds=b)
def score(mid,data,modality='scalp_eeg'):return extension_outputs(mid,data,modality)[0]


class MethodScoreTests(unittest.TestCase):
    def test_catalog_all_methods_explicit_and_default_only_three(self):
        self.assertTrue({'ieeg_range_plateau','ieeg_group_outliers'} <= set(SPECS))
        self.assertEqual(sum(s['default_weight']>0 for s in outputs()),3)
        for modality in ['scalp_eeg','ecog','seeg','extracellular']:
            for m in methods(modality):
                self.assertIn('can_output_score',m)
                self.assertEqual(m['can_output_score'],bool(m['scoring']['outputs']))
        gnosis={m['id']:m for m in methods() if m['id'].startswith('gnosis_')}
        self.assertEqual(sum(m['can_output_score'] for m in gnosis.values()),5)
        self.assertFalse(gnosis['gnosis_reference_ranges']['can_output_score'])
        self.assertFalse(gnosis['gnosis_band_power']['can_output_score'])

    def test_line_length_is_candidate_fraction_not_normalized_voltage(self):
        p=payload(candidates=[channel('A'),channel('A')]);p['metrics']={'line_length_by_channel':{'A':123,'B':1}}
        r=score('gnosis_line_length',p);self.assertEqual(r['value'],50);self.assertEqual(r['candidate_amount'],1)
        p['metrics']['line_length_by_channel']['B']=math.nan
        self.assertIsNone(score('gnosis_line_length',p)['value'])

    def test_psd_scores_only_declared_retained_scope(self):
        p=payload(candidates=[channel('A')]);p['metrics']={'psd_distance':[dict(channel_name=n,band='full',value=2) for n in ['A','B']], 'effective_duration_seconds':6,'used_intervals':[[10,16]]}
        r=score('gnosis_psd_deviation',p);self.assertEqual(r['value'],50);self.assertEqual(r['scope']['effective_duration_seconds'],6)
        p['metrics'].pop('effective_duration_seconds');self.assertIsNone(score('gnosis_psd_deviation',p)['value'])

    def test_time_ratios_union_overlap_and_reconcile_original_measurement(self):
        p=payload(candidates=[interval(10,13,'A'),interval(12,15,'A')]);p['metrics']={'ratio_by_channel':{'A':.5,'B':0}}
        for mid in ['gnosis_artifact','gnosis_low_band','gnosis_high_band']:
            r=score(mid,p);self.assertEqual(r['candidate_amount'],5);self.assertEqual(r['assessed_amount'],20);self.assertEqual(r['value'],75)
        p['metrics']['ratio_by_channel']['A']=.7;self.assertIsNone(score('gnosis_artifact',p)['value'])

    def test_gnosis_roundoff_and_missing_channel_never_full_credit(self):
        p=payload();p['metrics']={'ratio_by_channel':{'A':0,'B':0},'assessed_duration_seconds':9.99}
        self.assertEqual(score('gnosis_artifact',p)['assessed_amount'],19.98)
        del p['metrics']['ratio_by_channel']['B'];self.assertIsNone(score('gnosis_artifact',p)['value'])

    def test_mne_amplitude_distinct_outputs(self):
        p=payload(candidates=[channel('A'),interval(10,12),interval(11,13)]);p['bad_channels']=['A']
        rows=extension_outputs('mne_amplitude',p)
        self.assertEqual([r['value'] for r in rows],[50,70])
        self.assertEqual([r['unit'] for r in rows],['channels','seconds'])
        p['bad_channels']=[];self.assertIsNone(score('mne_amplitude',p)['value'])

    def test_muscle_excludes_invalid_filter_edges(self):
        p=payload(candidates=[interval(10,12)]);p['scores_z']=[None,None]+list(range(18))
        r=score('mne_muscle',p);self.assertEqual(r['candidate_amount'],2);self.assertEqual(r['assessed_amount'],18)
        p['scores_z']=[None]*20;self.assertIsNone(score('mne_muscle',p)['value'])

    def test_bridge_counts_involved_channels_not_pairs(self):
        p=payload(names=('A','B','C','D'),candidates=[dict(localization='pair_only',channel_names=['A','B']),dict(localization='pair_only',channel_names=['B','C'])])
        names=p['channel_names'];p['segmentation']={'n_epochs':5}
        p['electrical_distance_uv2']=[dict(channel_names=[a,b],values_by_epoch=[1]*5) for i,a in enumerate(names) for b in names[i+1:]]
        self.assertEqual(score('mne_bridge',p)['value'],25)
        p['electrical_distance_uv2'].pop();self.assertIsNone(score('mne_bridge',p)['value'])

    def test_lof_and_faster_preserve_native_decisions(self):
        p=payload(candidates=[channel('A')]);p['bad_channels']=['A'];p['channel_scores']=[dict(channel_name=n,negative_outlier_factor=-1) for n in ['A','B']]
        self.assertEqual(score('mne_lof',p)['value'],50)
        p['by_metric']={'variance':['A'],'kurtosis':[]};self.assertEqual(score('faster_channels',p)['value'],50)
        p['by_metric']={};self.assertIsNone(score('faster_channels',p)['value'])

    def test_autoreject_denominator_is_evaluated_epochs(self):
        p=payload(candidates=[dict(localization='epoch_only',epoch_index=1)])
        p['segmentation']={'n_epochs':2,'ranges':[[10,14],[14,18]],'tail_samples_not_used':4};p['epoch_max_ptp_volts']=[.1,.3]
        self.assertEqual(score('autoreject_global',p)['value'],50)
        p['candidates'][0]['epoch_index']=2;self.assertIsNone(score('autoreject_global',p)['value'])

    def test_fieldtrip_original_time_union_with_nonzero_start(self):
        p=payload(candidates=[interval(11,14),interval(13,15)]);p['zvalue']=list(range(20))
        for modality in ['scalp_eeg','ecog','seeg']:self.assertEqual(score('fieldtrip_zvalue',p,modality)['value'],60)
        p['zvalue'][0]=None;self.assertIsNone(score('fieldtrip_zvalue',p)['value'])

    def test_neuropixels_only_declared_noise_channel_labels(self):
        p=payload(candidates=[channel('B')]);p['channel_labels']=[dict(channel_name='A',label='good'),dict(channel_name='B',label='noise')]
        self.assertEqual(score('spikeinterface_bad_channels',p,'extracellular')['value'],50)
        p['channel_labels'][1]['label']='outside';self.assertIsNone(score('spikeinterface_bad_channels',p,'extracellular')['value'])
        self.assertEqual(extension_outputs('spikeinterface_bad_channels',p,'scalp_eeg'),[])

    def test_unavailable_not_zero_or_perfect(self):
        for status in ['failed','blocked','skipped']:
            p=payload();p['status']=status
            for mid in ['gnosis_artifact','mne_muscle','mne_amplitude','fieldtrip_zvalue']:
                self.assertIsNone(score(mid,p)['value'])
        p=payload();p.pop('candidates');self.assertIsNone(score('mne_amplitude',p)['value'])

    def test_prep_requires_all_comparison_groups(self):
        p={'groups':[dict(thresholds_active=True)],'channels':[dict(channel_id='a',flags=['noise']),dict(channel_id='b',flags=[])]}
        self.assertEqual(prep_output(p,2)['value'],50)
        p['groups'][0]['thresholds_active']=False;self.assertIsNone(prep_output(p,2)['value'])

    def test_optin_weights_require_method_and_matching_modality(self):
        c={'version':VERSION,'weights':{'gnosis_artifact':2,'integrity':1}}
        self.assertEqual(normalize(c,'scalp_eeg',['M03','M06'],['gnosis_artifact']),c)
        with self.assertRaises(ValueError):normalize(c,'scalp_eeg',['M03','M06'],[])
        with self.assertRaises(ValueError):normalize(c,'ecog',['M03','M06'],['gnosis_artifact'])
        self.assertIsNone(normalize(None,'ecog',['M03','M04','M06']))
        self.assertEqual(normalize({'version':VERSION,'weights':{}},'ecog',[])['weights'],{})

    def test_weight_average_excludes_unavailable_without_fabricating_values(self):
        rows=[observation(SPECS['integrity'],0,100),observation(SPECS['gnosis_artifact'],4,10)]
        config={'version':VERSION,'weights':{'integrity':1,'gnosis_artifact':3}}
        self.assertEqual(aggregate(rows,config)['value'],70)
        auto=aggregate(rows[:1],config)
        self.assertEqual(auto['value'],100)
        self.assertEqual(auto['effective_weights']['gnosis_artifact'],0)
        self.assertEqual(auto['components'][1]['configured_weight'],3)
        self.assertIsNone(auto['components'][1]['value'])
        missing=aggregate([],config)
        self.assertIsNone(missing['value']);self.assertEqual(missing['status'],'unavailable')
        frozen=copy.deepcopy(config);frozen['version']='project-weighted/1.1'
        self.assertIsNone(aggregate(rows[:1],frozen)['value'])
        config['weights']['gnosis_artifact']=0;self.assertEqual(aggregate(rows[:1],config)['value'],100)
        self.assertIsNone(aggregate(rows,config,coverage_complete=False)['value'])
        config['weights']['integrity']=0;self.assertIsNone(aggregate(rows,config)['value'])

    def test_valid_zero_remains_weighted_and_input_configuration_is_immutable(self):
        rows=[observation(SPECS['integrity'],100,100),observation(SPECS['gnosis_artifact'],None,None,reason='条件未满足')]
        config={'version':VERSION,'weights':{'integrity':1,'gnosis_artifact':3}}
        before=copy.deepcopy((rows,config));out=aggregate(rows,config)
        self.assertEqual(out['value'],0)
        self.assertEqual(out['components'][0]['normalized_weight'],1)
        self.assertEqual(out['excluded_components'],['gnosis_artifact'])
        self.assertEqual(out['components'][1]['reason'],'条件未满足')
        self.assertEqual((rows,config),before)

    def test_whole_record_pools_native_denominators_and_channel_blocks(self):
        a=observation(SPECS['gnosis_artifact'],2,10);b=observation(SPECS['gnosis_artifact'],0,30)
        a2=observation(SPECS['gnosis_line_length'],1,2);b2=observation(SPECS['gnosis_line_length'],0,2)
        windows=[dict(id='w1',duration_seconds=5,method_scores=[a,a2]),dict(id='w2',duration_seconds=15,method_scores=[b,b2])]
        rows=pool_windows(windows);self.assertEqual(rows[0]['value'],95);self.assertEqual(rows[1]['value'],87.5)
        self.assertEqual(rows[1]['unit'],'channel_block_seconds')
        windows[1]['method_scores']=[];self.assertTrue(all(r['value'] is None for r in pool_windows(windows)))

    def test_non_eeg_finalize_cannot_inherit_scalp_core_scores(self):
        r={'input_modality':{'value':'ecog'},'selected_modules':['M03','M04','M05','M06'],'qc_config':{'method_config':{'extensions':[]}},'modules':[]}
        finalize(r,[])
        self.assertFalse({'integrity','line_noise','hf_burst'} & {row['id'] for row in r['method_scores']})
        self.assertTrue(all(row['value'] is None for row in r['method_scores']))

if __name__=='__main__':unittest.main()
