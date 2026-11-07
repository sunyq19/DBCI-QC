"""Candidates must be calibrated, grouping-safe, localized and missing-safe."""
import copy
import unittest
from unittest.mock import patch
import numpy as np
from ephys_qc.extensions import run_extension
from ephys_qc.ieeg_baseline import encoding_ranges
from ephys_qc.planning import build_plan
from test_neuromodal_routes import recording


class IeegMethodTests(unittest.TestCase):
    def test_encoding_plateau_not_single_peak_or_nonfinite(self):
        x=np.array([[0.,1.,1.,1.,0.,-1.,-1.,0.,np.nan]])
        facts=dict(modality='seeg',verified_voltage=True,format='EDF',
                   encoding_ranges=[dict(minimum_volts=-1.,maximum_volts=1.,step_volts=.001)])
        original=x.copy()
        r=run_extension('ieeg_range_plateau',x,100,['A'],10,{},facts=facts)
        self.assertEqual(len(r['candidates']),1)
        self.assertEqual(r['candidates'][0]['sample_count'],3)
        self.assertAlmostEqual(r['candidates'][0]['start_seconds'],10.01)
        self.assertAlmostEqual(r['candidates'][0]['stop_seconds'],10.04)
        self.assertEqual(r['score_outputs'][0]['assessed_amount'],8)
        self.assertEqual(r['score_outputs'][0]['candidate_amount'],3)
        np.testing.assert_array_equal(x,original)

    def test_unknown_range_is_not_guessed_from_peak(self):
        r=run_extension('ieeg_range_plateau',np.ones((1,100)),100,['A'],0,{},facts=dict(modality='ecog',verified_voltage=True,format='EDF',encoding_ranges=[None]))
        self.assertEqual(r['candidates'],[])
        self.assertIsNone(r['score_outputs'][0]['value'])
        self.assertEqual(encoding_ranges([{}]),[None])
        self.assertEqual(encoding_ranges([dict(physical_min=-1000,physical_max=1000,digital_min=-100,digital_max=100,scale_to_si=1e-6)])[0]['step_volts'],1e-5)

    def test_location_budget_does_not_truncate_counts_or_scores(self):
        x=np.tile([0.,1.,1.,1.,0.,1.,1.,1.],(2,1))
        facts=dict(modality='seeg',verified_voltage=True,format='EDF',
                   encoding_ranges=[dict(minimum_volts=-1.,maximum_volts=1.,step_volts=.001)]*2)
        with patch('ephys_qc.ieeg_methods.MAX_CANDIDATE_DETAILS',1):
            r=run_extension('ieeg_range_plateau',x,100,['A','B'],0,{},facts=facts)
        self.assertEqual(len(r['candidates']),1)
        self.assertEqual(r['candidate_total_count'],4)
        self.assertEqual(r['candidate_channel_count'],2)
        self.assertTrue(r['candidate_details_truncated'])
        self.assertEqual(r['score_outputs'][0]['candidate_amount'],12)
        self.assertEqual(r['score_outputs'][0]['assessed_amount'],16)

    def group_run(self,x,labels,confirmed=True):
        return run_extension('ieeg_group_outliers',x,1000,[str(i) for i in range(len(x))],120,
            {'reference_confirmed':confirmed},facts=dict(modality='seeg',verified_voltage=True,comparison_group_labels=labels))

    def test_groups_scale_invariance_and_index_zero_outlier(self):
        base=np.random.default_rng(77).normal(size=(20,5000))*np.linspace(.8,1.2,20)[:,None]*1e-5
        base[0]*=100
        a=self.group_run(base,['a']*20)
        self.assertIn('0',[c['channel_name'] for c in a['candidates']])
        rolled=self.group_run(np.roll(base,1,axis=0),['a']*20)
        self.assertIn('1',[c['channel_name'] for c in rolled['candidates']])
        b=self.group_run(np.concatenate([base,base*1e3]),['a']*20+['b']*20)
        self.assertEqual([c['channel_index'] for c in b['candidates']],[0,20])
        np.testing.assert_allclose([r['robust_z'] for r in b['measurements'][:20]],
                                   [r['robust_z'] for r in b['measurements'][20:]],atol=1e-10)

    def test_unconfirmed_reference_and_degenerate_groups_never_pass(self):
        x=np.random.default_rng(0).normal(size=(8,1000))*1e-5
        for y,labels,confirmed in [(x,['g']*8,False),(x,['a']*3+['b']*5,True),
                                   (np.tile(x[0],(8,1)),['g']*8,True)]:
            r=self.group_run(y,labels,confirmed)
            self.assertEqual(r['status'],'partial')
            if not confirmed or np.all(y==y[0]):self.assertIsNone(r['score_outputs'][0]['value'])
            else:self.assertEqual(r['score_outputs'][0]['assessed_amount'],5)

    def test_stable_group_mapping_validated_not_positional_guess(self):
        record=recording('seeg');original=copy.deepcopy(record)
        groups={f"{record['id']}:ch:{i}":str(i) for i in reversed(range(3))}
        p=build_plan(record,['M05'],{'method_config':{'comparison_groups':groups,'extensions':['ieeg_group_outliers']}})
        from ephys_qc.tagging import data_facts
        self.assertEqual(data_facts(record,p['qc_config'])['comparison_group_labels'],['0','1','2'])
        with self.assertRaises(ValueError):build_plan(record,['M05'],{'method_config':{'comparison_groups':{'fake':'all'}}})
        self.assertEqual(record,original)


if __name__=='__main__':unittest.main()
