import copy
import math
import unittest
from ephys_qc.project_scoring import VERSION, SPECS, normalize, weighted_score, apply_to_view
from ephys_qc.planning import catalog, build_plan
from test_report_view import ReportViewTests


def evidence():
    return [dict(channel_id=cid,name=cid,components={
        key:dict(numerator=value,denominator=100) for key,value in
        zip(SPECS, values)}) for cid,values in [('a',[100,20,90]),('b',[100,100,100])]]


def config(weights=(1,1,1)):
    return {'version':VERSION,'weights':dict(zip(SPECS, weights))}


class ProjectScoreTests(unittest.TestCase):
    def test_archived_v10_rules_stay_frozen(self):
        frozen=config((1,2,1));frozen['version']='project-weighted/1.0'
        before=copy.deepcopy(frozen)
        self.assertEqual(normalize(frozen,'scalp_eeg',['M03','M04','M06']),before)
        score=weighted_score(evidence(),2,frozen)
        self.assertEqual(score['version'],'project-weighted/1.0')
        self.assertEqual(score['value'],78.75)
        self.assertEqual(frozen,before)
        frozen['weights']={k:0 for k in SPECS}
        with self.assertRaises(ValueError):normalize(frozen,'scalp_eeg',['M03','M04','M06'])

    def test_current_report_failure_and_disabled_scoring_are_distinct(self):
        fixture=ReportViewTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        from ephys_qc.report_view import build_report_view
        row=copy.deepcopy(fixture.result);row['qc_config']={'scoring':config()}
        row['modules'][1]['status']='failed'
        failed=build_report_view(row,fixture.artifacts)
        self.assertIsNone(failed['score']['value'])
        self.assertIn('line_noise',failed['score']['missing_components'])
        row=copy.deepcopy(fixture.result);row['qc_config']={'scoring':config((0,0,0))}
        disabled=build_report_view(row,fixture.artifacts)
        self.assertIsNone(disabled['score']['value'])
        self.assertEqual(disabled['score']['status'],'disabled')
        self.assertNotIn('未完成',disabled['headline'])

    def test_transparent_fraction_and_weighted_mean(self):
        score=weighted_score(evidence(),2,config((1,2,1)))
        self.assertEqual([p['value'] for p in score['components']],[100,60,95])
        self.assertEqual(score['value'],78.75)
        self.assertEqual(score['components'][1]['normalized_weight'],.5)
        # Weight scale does not change the result or detector evidence.
        self.assertEqual(weighted_score(evidence(),2,config((2,4,2)))['value'],78.75)

    def test_missing_positive_weight_never_silently_renormalizes(self):
        rows=evidence();rows[1]['components'].pop('line_noise')
        self.assertIsNone(weighted_score(rows,2,config())['value'])
        score=weighted_score(rows,2,config((1,0,1)))
        self.assertEqual(score['value'],97.5)
        self.assertIsNone(score['components'][1]['value'])
        self.assertIsNone(weighted_score(rows,2,config((1,0,1)),coverage_complete=False)['value'])

    def test_incomplete_identities_and_window_coverage_are_not_pass(self):
        rows=evidence();rows[1]['channel_id']='a'
        self.assertIsNone(weighted_score(rows,2,config())['value'])
        self.assertIsNone(weighted_score(evidence(),2,config(),expected_windows=2)['value'])

    def test_validation_and_modalities(self):
        for weights in [(-1,1,1),(True,1,1),(math.nan,1,1),(math.inf,1,1),(101,1,1)]:
            with self.subTest(weights=weights), self.assertRaises(ValueError): normalize(config(weights),'scalp_eeg',['M03','M04','M06'])
        with self.assertRaises(ValueError): normalize(config(),'scalp_eeg',['M03'])
        for modality in ['ecog','seeg','extracellular']:
            self.assertIsNone(normalize(None,modality,['M03']))
            with self.assertRaises(ValueError): normalize(config(),modality,['M03','M04','M06'])
            self.assertTrue(any(m['can_output_score'] for m in catalog(modality)))
        modules=catalog('scalp_eeg')
        self.assertEqual([m['id'] for m in modules if m['can_output_score']],['M03','M04','M05','M06','M08'])
        self.assertEqual(next(m for m in modules if m['id']=='M08')['scoring']['role'],'aggregate')

    def test_real_report_fixture_weighted_view_html_pdf_and_legacy_immutable(self):
        fixture=ReportViewTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        from ephys_qc.report_view import build_report_view, render_report_view
        from ephys_qc.report_export import pdf_bytes
        old=fixture.view();before=copy.deepcopy(old)
        revised=apply_to_view(old,config((1,2,1)))
        self.assertEqual(old,before)
        # 100 integrity; 2/3 good channel-windows; 90 HF; weights 1:2:1.
        self.assertAlmostEqual(revised['score']['value'],(100+2*100*2/3+90)/4)
        report=render_report_view(revised)
        self.assertIn('3 项计入总分',report)
        self.assertNotIn('总分取最低分项',report)
        self.assertIn('<th>工频干扰</th><td>50.0%</td>',report)
        self.assertTrue(pdf_bytes(revised).startswith(b'%PDF'))
        result=copy.deepcopy(fixture.result);result['qc_config']={'scoring':config((1,2,1))}
        live=build_report_view(result,fixture.artifacts)
        self.assertEqual(live['score'],revised['score'])
