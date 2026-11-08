"""Deduplication, explicit coverage and unavailable-weight behavior for NP scores."""
import copy
import unittest
from ephys_qc.neuropixels_scoring import (
    NUMERIC, CONSTANT, STATE, AP, default_config, continuity_outputs, state_output)
from ephys_qc.method_scores import observation, aggregate, finalize, pool_windows, extension_outputs
from ephys_qc.score_registry import SPECS
from ephys_qc.project_scoring import normalize
from ephys_qc.recommendations import recommend
from test_neuropixels_standard import source


def evidence(key, candidates=(), count=4, start=0, seconds=2):
    r=observation(SPECS[key],len(candidates),count,
        scope={'start_seconds':start,'stop_seconds':start+seconds,'duration_seconds':seconds})
    r['channel_evidence']={'assessed':[f'c{i}' for i in range(count)],'candidates':list(candidates)}
    return r


def numeric(value=100):return observation(SPECS[NUMERIC],100-value,100)


class NeuropixelsScoringTests(unittest.TestCase):
    def test_catalog_exposes_scoring_evidence_and_group(self):
        from ephys_qc.planning import catalog
        modules={r['id']:r for r in catalog('extracellular')}
        for key in ('M03','M05','M08'):
            self.assertTrue(modules[key]['can_output_score'])
        self.assertIn('整窗恒值',modules['M03']['description'])
        self.assertIn('可调权重',modules['M08']['description'])
        method=next(r for r in modules['M08']['methods'] if r['id']=='aggregate')
        self.assertIn('project_score',method['documentation']['how_it_works'])
        self.assertEqual([s['id'] for s in method['scoring']['outputs']],[STATE])

    def test_union_counts_overlap_once_and_keeps_distinct_channels(self):
        rows=[evidence(CONSTANT,['c0']),evidence(AP,['c0','c1'])]
        original=copy.deepcopy(rows);state=state_output(rows)
        self.assertEqual(state['value'],50)
        self.assertEqual(state['candidate_amount'],2)
        self.assertEqual(aggregate([numeric(),*rows,state],default_config())['value'],65)
        self.assertEqual(rows,original)
        self.assertEqual(state_output([evidence(CONSTANT,['c0']),evidence(AP,['c1'])])['value'],50)

    def test_restricted_method_is_omitted_without_destroying_other_evidence(self):
        missing=observation(SPECS[AP],reason='short window')
        state=state_output([evidence(CONSTANT,['c0']),missing])
        self.assertEqual(state['value'],75)
        self.assertEqual(state['assessed_methods'],[CONSTANT])
        self.assertEqual(state['unavailable_methods'][0]['id'],AP)
        self.assertEqual(state['evidence_components'][1]['value'],None)

    def test_missing_group_has_zero_weight_and_no_fake_hundred(self):
        state=state_output([observation(SPECS[CONSTANT])])
        result=aggregate([numeric(90),state],default_config())
        self.assertEqual(result['value'],90)
        self.assertEqual(result['effective_weights'][STATE],0)
        self.assertEqual(result['components'][1]['configured_weight'],70)
        self.assertEqual(result['components'][0]['normalized_weight'],1)
        self.assertIsNone(aggregate([observation(SPECS[NUMERIC]),state],default_config())['value'])
        self.assertIsNone(aggregate([numeric(),state],default_config(),coverage_complete=False)['value'])
        zero=aggregate([numeric(0),state],default_config())
        self.assertEqual(zero['value'],0)
        self.assertEqual(zero['effective_weights'][NUMERIC],30)
        self.assertIsNone(aggregate([numeric(),state],{'version':'project-weighted/1.2','weights':{NUMERIC:0,STATE:0}})['value'])

    def test_full_record_unions_before_weighting_each_window(self):
        windows=[]
        # Same channel in the first window, two different channels in the second.
        for i,(seconds,ap) in enumerate([(2,['c0']),(6,['c1'])]):
            rows=[evidence(CONSTANT,['c0'],start=i*2,seconds=seconds),evidence(AP,ap,start=i*2,seconds=seconds)]
            windows.append({'id':str(i),'duration_seconds':seconds,'method_scores':rows+[state_output(rows)]})
        state=next(r for r in pool_windows(windows) if r['id']==STATE)
        self.assertEqual(state['candidate_amount'],14)
        self.assertEqual(state['assessed_amount'],32)
        self.assertEqual(state['value'],56.25)

    def test_incomplete_method_is_excluded_from_whole_record_union(self):
        rows=[evidence(CONSTANT),evidence(AP,['c0'])]
        tail=[evidence(CONSTANT,start=2,seconds=.5),observation(SPECS[AP],reason='tail too short')]
        windows=[{'id':'w1','duration_seconds':2,'method_scores':rows+[state_output(rows)]},
                 {'id':'w2','duration_seconds':.5,'method_scores':tail+[state_output(tail)]}]
        pooled=pool_windows(windows);state=next(r for r in pooled if r['id']==STATE)
        self.assertEqual(state['value'],100)
        self.assertEqual(state['assessed_methods'],[CONSTANT])
        self.assertEqual(state['unavailable_methods'][0]['id'],AP)
        self.assertIsNone(next(r for r in pooled if r['id']==AP)['value'])

    def test_identity_and_time_mismatch_cannot_form_union(self):
        for change in ('ids','time'):
            a=evidence(CONSTANT,['c0']);b=evidence(AP,['c1'])
            if change=='ids':b['channel_evidence']['assessed'][-1]='other'
            else:b['scope'].update(start_seconds=10,stop_seconds=12)
            self.assertIsNone(state_output([a,b])['value'])
        b=evidence(AP,['c1']);b['channel_evidence']['assessed'][-1]='c0'
        self.assertEqual(state_output([evidence(CONSTANT),b])['unavailable_methods'][0]['id'],AP)

    def test_continuity_counts_distinguish_constants_nonfinite_and_quantization(self):
        rows=[dict(channel_id=f'c{i}',sample_count=100,finite_sample_count=100,
                   nonfinite_sample_count=0,fully_constant=i==0,max_exact_constant_run_samples=100 if i==0 else 2) for i in range(4)]
        p={'channels':rows,'input_range':{'start_seconds':0,'stop_seconds':2,'duration_seconds':2}}
        out=continuity_outputs(p,{'channel_count':4},'M03_continuity.json')
        self.assertEqual(out[0]['value'],100);self.assertEqual(out[1]['value'],75)
        rows[1].update(finite_sample_count=99,nonfinite_sample_count=1)
        out=continuity_outputs(p,{'channel_count':4},'M03_continuity.json')
        self.assertAlmostEqual(out[0]['value'],99.75);self.assertIsNone(out[1]['value'])
        rows[1].update(finite_sample_count=100,nonfinite_sample_count=0);rows[0].pop('fully_constant')
        self.assertIsNone(continuity_outputs(p,{'channel_count':4},'M03_continuity.json')[1]['value'])

    def test_ap_uses_source_ids_not_display_name_to_join(self):
        p={'status':'completed','calculated':True,'channel_names':['A','B'],
           'range':{'start_seconds':0,'stop_seconds':2,'duration_seconds':2},
           'candidates':[{'channel_name':'B','localization':'channel_only'}],
           'channel_labels':[{'channel_name':'A','label':'good'},{'channel_name':'B','label':'noise'}],
           'channel_mapping':[{'adapter_name':'A','channel_id':'c1'},{'adapter_name':'B','channel_id':'c0'}]}
        ap=extension_outputs(AP,p,'extracellular')[0]
        self.assertEqual(ap['channel_evidence']['candidates'],['c0'])
        self.assertEqual(state_output([evidence(CONSTANT,['c0'],count=2),ap])['value'],50)

    def test_presets_weights_zero_and_duplicate_families(self):
        for band in ('ap','lf'):
            proposed=recommend(source(band));self.assertTrue(proposed['can_apply'],proposed)
            config=proposed['qc_config'];self.assertEqual(config['scoring'],default_config())
            for weights in ({NUMERIC:50,STATE:50},{NUMERIC:0,STATE:0}):
                config['scoring']['weights']=weights
                self.assertEqual(recommend(source(band),config)['qc_config']['scoring']['weights'],weights)
        for member in (CONSTANT,AP):
            bad=default_config();bad['weights'][member]=10
            with self.assertRaises(ValueError):normalize(bad,'extracellular',['M03','M05','M08'],[AP])
            with self.assertRaises(ValueError):aggregate([numeric()],bad)
        with self.assertRaises(ValueError):normalize(default_config(),'ecog',['M03','M08'])

    def test_failed_modules_do_not_contribute_valid_scores(self):
        result={'input_modality':'extracellular','selected_modules':['M03','M05','M08'],
                'modules':[{'id':'M03','status':'failed'},{'id':'M05','status':'completed'}],
                'qc_config':{'method_config':{'extensions':[AP]},'scoring':default_config()}}
        finalize(result,[numeric(),evidence(CONSTANT),evidence(AP,['c0'])])
        self.assertEqual(result['project_score']['value'],75)
        self.assertEqual(result['project_score']['effective_weights'][NUMERIC],0)
        self.assertEqual(next(r for r in result['method_scores'] if r['id']==STATE)['assessed_methods'],[AP])


if __name__=='__main__':unittest.main()
