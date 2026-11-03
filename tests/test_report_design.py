"""Reporting arithmetic checks; these do not validate detector accuracy."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('preview_report_design', Path(__file__).resolve().parents[1] / 'scripts/preview_report_design.py')
design = importlib.util.module_from_spec(spec)
spec.loader.exec_module(design)


def observation(channel='x', start=0, stop=400, flag=False, frequency=50, status='computed'):
    return dict(channel_id=channel, channel_index=0, channel_name=channel,
                start_sample=start, stop_sample=stop, window_index=0,
                flagged=flag, nominal_hz=frequency, amplitude_uv=1, status=status)


class ReportingArithmetic(unittest.TestCase):
    def test_trial_score_fixed_equal_weights(self):
        score=design.trial_score(
            dict(total=100, finite_outside_constant=90, measured_channels=1),
            dict(total=10,hits=2,assessed_channels=1),
            [dict(status='ok',valid_seconds=10,candidate_seconds=3)], 1)
        self.assertEqual([c['value'] for c in score['components']], [90,80,70])
        self.assertEqual(score['value'],80)

    def test_missing_component_does_not_renormalize_score(self):
        score=design.trial_score(
            dict(total=100, finite_outside_constant=None, measured_channels=1),
            dict(total=10,hits=0,assessed_channels=1),
            [dict(status='ok',valid_seconds=10,candidate_seconds=0)], 1)
        self.assertIsNone(score['value'])
        self.assertEqual([c['value'] for c in score['components']], [None,100,100])

    def test_partial_channel_coverage_does_not_produce_total(self):
        score=design.trial_score(
            dict(total=200, finite_outside_constant=200, measured_channels=2),
            dict(total=20,hits=0,assessed_channels=2),
            [dict(status='ok',valid_seconds=10,candidate_seconds=0)], 2)
        self.assertIsNone(score['components'][2]['value'])
        self.assertIsNone(score['value'])

    def test_score_preserves_extreme_problem_in_component(self):
        score=design.trial_score(
            dict(total=100, finite_outside_constant=100, measured_channels=1),
            dict(total=10,hits=10,assessed_channels=1),
            [dict(status='ok',valid_seconds=10,candidate_seconds=0)], 1)
        self.assertEqual(score['components'][1]['value'],0)
        self.assertAlmostEqual(score['value'],200/3)

    def test_multiple_frequencies_count_one_channel_window(self):
        result=design.line_summary({'observations':[
            observation(flag=True), observation(flag=True,frequency=60),
            observation(start=100,stop=500), observation(channel='y')]})
        self.assertEqual(result['flagged_frequency_rows'],2)
        self.assertEqual((result['hits'],result['total']),(1,3))
        self.assertAlmostEqual(result['percent'],100/3)
        self.assertEqual(result['affected_channels'],1)

    def test_only_evaluated_observations_enter_denominator(self):
        result=design.line_summary({'observations':[
            observation(status='unavailable',flag=True), observation(start=100,stop=500)]})
        self.assertEqual((result['hits'],result['total']),(0,1))
        self.assertEqual(result['percent'],0)

    def test_no_evidence_does_not_become_zero(self):
        self.assertIsNone(design.line_summary({})['percent'])
        self.assertIsNone(design.integrity_summary({})['finite_percent'])
        self.assertIsNone(design.integrity_summary({})['constant'])

    def test_sample_counts_use_actual_denominator(self):
        result=design.integrity_summary({'measurements':[
            dict(finite_sample_count=90,nonfinite_sample_count=10,constant_sample_count=5),
            dict(finite_sample_count=50,nonfinite_sample_count=0,constant_sample_count=0),
            dict(finite_sample_count=None)]})
        self.assertEqual(result['total'],150)
        self.assertEqual(result['measured_channels'],2)
        self.assertAlmostEqual(result['finite_percent'],140/150*100)
        self.assertAlmostEqual(result['constant_percent'],5/150*100)


if __name__ == '__main__':
    unittest.main()
