"""Export correctness: real deduction arithmetic, source mapping and missing evidence."""
import copy
import importlib.util
import json
import math
import re
from pathlib import Path
import tempfile
import unittest
from ephys_qc.report_export import score_rows, evidence_figure, pdf_bytes
import test_report_view as fixtures


class ReportExportTests(unittest.TestCase):
    setUp = fixtures.ReportViewTests.setUp
    view = fixtures.ReportViewTests.view
    def test_deductions_and_missing_component(self):
        view=self.view();rows=score_rows(view)
        self.assertAlmostEqual(rows[1]['deduction'],100*math.sqrt(.5**2/2))
        view['score']['components'][1]['value']=None
        self.assertIsNone(score_rows(view)[1]['deduction'])
        self.assertIn('未计分',score_rows(view)[1]['reason'])

    @unittest.skipUnless(importlib.util.find_spec('reportlab'), 'optional PDF dependency')
    def test_pdf_preserves_score_and_handles_unavailable_figure(self):
        view=self.view();before=copy.deepcopy(view)
        data=pdf_bytes(view,figure_notes=['来源不可用'],job_id=self.jid)
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertEqual(view,before)
        count=re.search(rb'/Count (\d+)',data)
        self.assertIsNotNone(count)
        self.assertEqual(int(count[1]),2)

    def test_human_findings_keep_measurements_and_missing_configured_share(self):
        from ephys_qc.project_scoring import apply_to_view, VERSION
        from ephys_qc.report_export import score_composition
        view=apply_to_view(self.view(),{'version':VERSION,'weights':{'integrity':1,'line_noise':2,'hf_burst':1}})
        before=copy.deepcopy(view)
        rows=score_rows(view)
        self.assertEqual([r['share'] for r in rows],[.25,.5,.25])
        self.assertIn('通道检查窗',rows[1]['finding'])
        self.assertNotIn('权重',rows[1]['reason'])
        self.assertIn(' / ',rows[1]['measurement'])
        view['score']['components'][1]['value']=None
        self.assertEqual(score_rows(view)[1]['share'],.5)
        self.assertEqual(score_composition(before['score']),'总分由 3 个分项按设定比例汇总。')

    @unittest.skipUnless(importlib.util.find_spec('reportlab'), 'optional PDF dependency')
    def test_print_report_keeps_weights_missing_values_and_page_totals(self):
        import shutil
        import subprocess
        if not shutil.which('pdftotext'): self.skipTest('PDF text extraction needs Poppler')
        from ephys_qc.project_scoring import apply_to_view, VERSION
        view=apply_to_view(self.view(),{'version':VERSION,'weights':{'integrity':1,'line_noise':2,'hf_burst':1}})
        view['run_name']='方案对照 <A&B> · '+('连续脑电检查 ' * 12)
        view['score']['value']=None
        view['score']['components'][1]['value']=None
        view['score']['missing_reason']='工频测量不足'
        before=copy.deepcopy(view)
        path=self.root/'missing-score.pdf';path.write_bytes(pdf_bytes(view,job_id=self.jid))
        text=subprocess.check_output(['pdftotext','-layout',str(path),'-'],text=True)
        pages=[p for p in text.split('\f') if p.strip()]
        self.assertEqual(len(pages),2)
        self.assertIn('方案对照 <A&B>',pages[0])
        self.assertIn('工频测量不足',pages[0])
        self.assertIn('50.0%',pages[0])
        self.assertIn('未评',pages[0])
        self.assertIn('问题定位与证据',pages[1])
        for i,page in enumerate(pages,1):self.assertRegex(page,rf'{i}\s*/\s*2\s*$')
        self.assertEqual(view,before)

    def test_weights_belong_to_result_rows_and_preview_precedes_candidates(self):
        from ephys_qc.project_scoring import apply_to_view, VERSION
        from ephys_qc.report_view import render_report_view
        from ephys_qc.report_export import score_weight_label
        view=apply_to_view(self.view(),{'version':VERSION,'weights':{'integrity':1,'line_noise':2,'hf_burst':1}})
        before=copy.deepcopy(view)
        rows=score_rows(view)
        self.assertEqual([score_weight_label(r,view['score']) for r in rows],['25.0%','50.0%','25.0%'])
        page=render_report_view(view,focus_url=lambda i:f'/focus-{i}.png',visualization_url='/charts')
        overview=page.split('<header id="overview"')[1].split('</header>')[0]
        self.assertNotIn('同等计入',overview)
        self.assertNotIn('按设定比例',overview)
        results=page.split('<section id="score-table">')[1].split('</section>')[0]
        self.assertIn('>权重</th>',results)
        self.assertIn('class="result-weight">50.0%</td>',results)
        self.assertLess(page.index('id="finding-preview"'),page.index('<table class="finding-table"'))
        self.assertIn('id="finding-status" role="status"',page)
        self.assertIn('aria-controls="finding-preview" aria-current="true"',page)
        self.assertEqual(view,before)
        view['score']['components'][1]['value']=None
        self.assertEqual(score_weight_label(score_rows(view)[1],view['score']),'50.0%')

    def test_archived_v01_keeps_its_mean_formula_and_actual_fraction(self):
        from ephys_qc.report_export import score_composition
        from ephys_qc.report_view import render_report_view
        view=self.view()
        view['score']['version']='eeg-basic-screen/0.1'
        view['score']['components'][1]['value']=50
        for row in view['score']['components']:row.pop('candidate_fraction',None)
        before=copy.deepcopy(view)
        self.assertIn('平均分',score_composition(view['score']))
        self.assertIn('50.00%',score_rows(view)[1]['finding'])
        page=render_report_view(view)
        self.assertIn('项目试行 v0.1',page)
        self.assertNotIn('使用均方根',page)
        self.assertNotIn('取最低分项',page)
        self.assertEqual(view,before)

    def test_missing_full_record_component_locates_the_actual_unassessed_segment(self):
        view=self.view();part=view['score']['components'][2]
        part['value']=None
        view['window_scores']=[{'start_seconds':720.,'duration_seconds':13.,'components':[
            {'id':'hf_burst','value':None,'reason':'原版方法未完成：ValueError: Degenerate band statistic'}]}]
        before=copy.deepcopy(view);row=score_rows(view)[2]
        self.assertIn('720–733 秒',row['finding'])
        self.assertIn('高频统计未得到有效结果',row['finding'])
        self.assertIn('0 / 1',row['measurement'])
        self.assertEqual(view,before)

    def test_visible_coverage_uses_valid_windows_not_scheduled_window_count(self):
        from ephys_qc.report_export import display_checks
        view=self.view();name=view['score']['components'][2]['name']
        view['checks']=[{'name':name,'value':'2/2 个窗口可计分，0 秒'}]
        view['window_scores']=[{'duration_seconds':120.,'components':[{'id':'hf_burst','value':95.}]},
                               {'duration_seconds':13.,'components':[{'id':'hf_burst','value':None}]}]
        before=copy.deepcopy(view)
        self.assertEqual(display_checks(view)[0]['value'],'1/2 个窗口可计分，120 秒')
        self.assertEqual(view,before)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'optional plotting dependency')
    def test_figure_maps_channel_identity_and_refuses_unverified_source(self):
        (self.artifacts/'M02_selection.json').write_text(json.dumps({'channels':[{'channel_id':'a','source_index':17}]}))
        called=[]
        class Workspace:
            root=self.job
            def waveform(inner,**kwargs):
                called.append(kwargs)
                return {'frozen_source_verified':False}
        before={p:p.read_bytes() for p in self.artifacts.iterdir()}
        figure,notes=evidence_figure(self.view(),Workspace())
        self.assertIsNone(figure);self.assertTrue(notes)
        self.assertEqual(called[0]['channel_indices'],[17])
        self.assertLessEqual(called[0]['duration_seconds'],10)
        for p,raw in before.items():self.assertEqual(p.read_bytes(),raw)

if __name__=='__main__':unittest.main()
