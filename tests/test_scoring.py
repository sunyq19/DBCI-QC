"""Score semantics and sensitivity, not clinical calibration."""
import copy
import math
import unittest
from ephys_qc.scoring import burden_score, score_revision


def evidence(burdens, key='line_noise'):
    return [{'channel_id':f'ch:{i}','name':f'C{i}', 'components':{
        k:{'numerator':100*(1-b if k==key else 1), 'denominator':100}
        for k in ('integrity','line_noise','hf_burst')}} for i,b in enumerate(burdens)]


class ScoringTests(unittest.TestCase):
    def test_clean_data_still_get_full_marks(self):
        s=burden_score(evidence([0]*63),63)
        self.assertEqual(s['value'],100)

    def test_no_good_dimension_compensates_for_failed_dimension(self):
        for key in ('integrity','line_noise','hf_burst'):
            with self.subTest(component=key):
                s=burden_score(evidence([1]*4,key),4)
                self.assertEqual(s['value'],0)
                self.assertEqual(s['limiting_components'],[key])

    def test_concentrated_and_distributed_burden_are_distinguished(self):
        spread=burden_score(evidence([.25]*4),4)
        local=burden_score(evidence([1,0,0,0]),4)
        self.assertEqual(spread['value'],75)
        self.assertEqual(local['value'],50)
        self.assertEqual(local['components'][1]['pooled_unflagged_percent'],75)

    def test_single_persistent_channel_is_visible_without_zeroing_recording(self):
        s=burden_score(evidence([1]+[0]*62),63)
        self.assertAlmostEqual(s['value'],100*(1-1/math.sqrt(63)))
        self.assertEqual(s['components'][1]['worst_channel']['name'],'C0')

    def test_more_detected_contamination_never_improves_score(self):
        for key in ('integrity','line_noise','hf_burst'):
            values=[burden_score(evidence([p,0,0,0],key),4)['value'] for p in (0,.1,.2,.5,1)]
            self.assertEqual(values,sorted(values,reverse=True))
        values=[burden_score(evidence([.5]*n+[0]*(8-n)),8)['value'] for n in range(9)]
        self.assertEqual(values,sorted(values,reverse=True))

    def test_repeating_channel_population_does_not_change_distribution_score(self):
        self.assertEqual(burden_score(evidence([.5,0]),2)['value'],
                         burden_score(evidence([.5,0,.5,0]),4)['value'])

    def test_no_duplicate_method_penalty(self):
        x=evidence([.4,.2]);s=burden_score(x,2)['value']
        for r in x:r['components']['hf_burst']=copy.deepcopy(r['components']['line_noise'])
        self.assertEqual(burden_score(x,2)['value'],s)

    def test_missing_invalid_duplicate_or_uncovered_is_not_full_credit(self):
        for case in ('missing','nan','negative','zero','duplicate','window','coverage'):
            x=evidence([.1,.2]);kwargs={}
            if case=='missing':del x[0]['components']['line_noise']
            if case=='nan':x[0]['components']['line_noise']['numerator']=float('nan')
            if case=='negative':x[0]['components']['line_noise']['numerator']=-1
            if case=='zero':x[0]['components']['line_noise']['denominator']=0
            if case=='duplicate':x[1]['channel_id']=x[0]['channel_id']
            if case=='window':kwargs['expected_windows']=2
            if case=='coverage':kwargs['coverage_complete']=False
            with self.subTest(case=case):self.assertIsNone(burden_score(x,2,**kwargs)['value'])

    def test_permutation_and_read_only_contract(self):
        x=evidence([0,.3,.8]);before=copy.deepcopy(x)
        self.assertEqual(burden_score(x,3)['value'],burden_score(list(reversed(x)),3)['value'])
        self.assertEqual(x,before)

    def test_revision_keeps_old_score_explicit(self):
        source={'report_view':{'score':{'version':'eeg-basic-screen/0.1','value':99.3}}}
        current=burden_score(evidence([.5,0]),2)
        r=score_revision(source,current)
        self.assertEqual(r['previous_value'],99.3)
        self.assertEqual(r['current_version'],'eeg-basic-screen/0.2')
        self.assertIsNone(score_revision({'report_view':{'score':current}},current))


if __name__=='__main__':unittest.main()
