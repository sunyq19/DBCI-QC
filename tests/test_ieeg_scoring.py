"""Grouped iEEG score behavior, not clinical accuracy validation."""
import copy
import unittest
from ephys_qc.ieeg_scoring import NUMERIC, STABILITY, EVIDENCE, default_config, numeric_output, stability_output
from ephys_qc.method_scores import observation, aggregate, pool_windows, finalize
from ephys_qc.score_registry import SPECS
from ephys_qc.project_scoring import normalize
from ephys_qc.recommendations import recommend
from test_neuromodal_routes import recording


def row(key,score):
    return observation(SPECS[key],100-score,100)


class IeegScoreTests(unittest.TestCase):
    def test_related_findings_count_once_and_retain_evidence(self):
        evidence=[row(k,s) for k,s in zip(EVIDENCE,[80,80,80,90,95])]
        original=copy.deepcopy(evidence);group=stability_output(evidence)
        self.assertEqual(group['value'],80)
        self.assertEqual(len(group['evidence_components']),5)
        score=aggregate([row(NUMERIC,100),*evidence,group],default_config('seeg'))
        self.assertEqual(score['value'],90.625)
        self.assertEqual(sum(r['weight']>0 for r in score['components']),2)
        self.assertEqual(evidence,original)

    def test_group_ignores_unavailable_evidence_but_does_not_fill_it(self):
        good=row('mne_amplitude_time',95)
        missing=observation(SPECS['ieeg_range_plateau'],reason='unknown limits')
        group=stability_output([good,missing])
        self.assertEqual(group['value'],95)
        self.assertEqual(group['unavailable_methods'],['ieeg_range_plateau'])
        self.assertIsNone(group['evidence_components'][1]['value'])
        missing_group=stability_output([missing])
        score=aggregate([row(NUMERIC,90),missing_group],default_config('ecog'))
        self.assertEqual(score['value'],90)
        self.assertEqual(score['effective_weights'][STABILITY],0)
        self.assertIsNone(aggregate([row(NUMERIC,90),group],default_config('ecog'),coverage_complete=False)['value'])

    def test_full_record_groups_after_pooling_not_average_of_window_minima(self):
        windows=[]
        for scores in ([50,100],[100,50]):
            r=[row('mne_amplitude_time',scores[0]),row('fieldtrip_zvalue',scores[1])]
            windows.append({'id':str(len(windows)),'duration_seconds':10,'method_scores':r+[stability_output(r)]})
        pooled=pool_windows(windows)
        self.assertNotIn(STABILITY,[r['id'] for r in pooled])
        self.assertEqual(stability_output(pooled)['value'],75)

    def test_weighted_children_exclude_missing_and_disabled(self):
        config=default_config('seeg')
        config['group_weights'][STABILITY].update(mne_amplitude_time=3,fieldtrip_zvalue=1,ieeg_range_plateau=0)
        children=[row('mne_amplitude_time',80),row('fieldtrip_zvalue',100),row('ieeg_range_plateau',10),
                  observation(SPECS['mne_amplitude_channels'],reason='limited')]
        group=stability_output(children,config)
        self.assertEqual(group['value'],85)
        self.assertEqual(group['assessed_methods'],['mne_amplitude_time','fieldtrip_zvalue'])
        self.assertEqual(group['unavailable_methods'],['mne_amplitude_channels'])
        self.assertEqual([r['normalized_weight'] for r in group['evidence_components']],[.75,.25,0,0])
        self.assertEqual(aggregate([row(NUMERIC,100),*children],config)['value'],90.625)
        config['group_weights'][STABILITY]={key:0 for key in EVIDENCE}
        score=aggregate([row(NUMERIC,100),*children],config)
        self.assertIsNone(next(r for r in score['components'] if r['id']==STABILITY)['value'])
        self.assertEqual(score['effective_weights'][STABILITY],0)
        self.assertEqual(score['value'],100)

    def test_reweight_saved_children_and_keep_historical_minimum(self):
        children=[row('mne_amplitude_time',80),row('fieldtrip_zvalue',100)]
        historical=stability_output(children)
        config=default_config('seeg')
        scored=aggregate([row(NUMERIC,100),historical],config)
        self.assertEqual(scored['value'],93.75)
        legacy={'version':'project-weighted/1.2','preset':'seeg-basic-score/0.1','weights':{NUMERIC:30,STABILITY:70}}
        self.assertEqual(aggregate([row(NUMERIC,100),historical],legacy)['value'],86)
        self.assertEqual(historical['value'],80)
        self.assertEqual(normalize(legacy,'seeg',['M03'],['mne_amplitude']),legacy)

    def test_child_weight_validation_and_configuration_identity(self):
        for bad in (-1,101,float('nan'),True,'1'):
            config=default_config('seeg');config['group_weights'][STABILITY]['mne_amplitude_time']=bad
            with self.assertRaises(ValueError):normalize(config,'seeg',['M03'],['mne_amplitude'])
        config=default_config('seeg');config['group_weights'][STABILITY]['unknown']=1
        with self.assertRaises(ValueError):normalize(config,'seeg',['M03'],['mne_amplitude'])
        config=default_config('seeg');before=aggregate([row(NUMERIC,100)],config)
        config['group_weights'][STABILITY]['mne_amplitude_time']=2
        after=aggregate([row(NUMERIC,100)],config)
        self.assertNotEqual(before['configuration_id'],after['configuration_id'])

    def test_numeric_counts_require_all_source_identities(self):
        payload={'channels':[dict(channel_id=f'src:{i}',sample_count=100,finite_sample_count=90,nonfinite_sample_count=10,exact_constant_run_count=20) for i in range(2)]}
        self.assertEqual(numeric_output(payload,{'channel_count':2},'counts.json')['value'],90)
        payload['channels'][1]['channel_id']='src:0'
        self.assertIsNone(numeric_output(payload,{'channel_count':2},'counts.json')['value'])

    def test_presets_versions_adjustable_weights_and_exclusive_family(self):
        for modality in ('ecog','seeg'):
            proposed=recommend(recording(modality));self.assertTrue(proposed['can_apply'])
            config=proposed['qc_config'];self.assertEqual(config['scoring'],default_config(modality))
            config['scoring']['weights']={NUMERIC:50,STABILITY:50}
            self.assertEqual(recommend(recording(modality),config)['qc_config']['scoring']['weights'],{NUMERIC:50,STABILITY:50})
            config['scoring']['weights']={NUMERIC:0,STABILITY:0}
            self.assertEqual(recommend(recording(modality),config)['qc_config']['scoring']['weights'],{NUMERIC:0,STABILITY:0})
            bad=default_config(modality);bad['weights']['mne_amplitude_time']=20
            with self.assertRaises(ValueError):normalize(bad,modality,['M03'],['mne_amplitude'])
            with self.assertRaises(ValueError):aggregate([row(NUMERIC,100)],bad)
            bad=default_config('seeg' if modality=='ecog' else 'ecog')
            with self.assertRaises(ValueError):normalize(bad,modality,['M03'],['mne_amplitude'])
        self.assertEqual(recommend(recording('extracellular'))['qc_config']['scoring']['preset'],'neuropixels-voltage-score/0.2')

    def test_failed_module_cannot_supply_a_stability_score(self):
        result={'input_modality':'seeg','selected_modules':['M03','M08'],
            'modules':[{'id':'M03','status':'failed'}],
            'qc_config':{'method_config':{'extensions':['mne_amplitude']},'scoring':default_config('seeg')}}
        finalize(result,[row(NUMERIC,100),row('mne_amplitude_channels',100),row('mne_amplitude_time',100)])
        self.assertIsNone(result['project_score']['value'])
        self.assertTrue(all(r['value'] is None for r in result['method_scores']))

if __name__=='__main__':unittest.main()
