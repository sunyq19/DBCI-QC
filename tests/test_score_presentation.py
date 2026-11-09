"""A score must expose its evidence without changing arithmetic or provenance."""
import copy
from html.parser import HTMLParser
import unittest

from ephys_qc.ieeg_scoring import NUMERIC, STABILITY, default_config, stability_output
from ephys_qc.method_scores import observation, aggregate
from ephys_qc.score_registry import SPECS
from ephys_qc.score_presentation import score_tree, measurement


def row(key, bad=0, total=100, **kwargs):
    return observation(SPECS[key], bad, total, **kwargs)


class Structure(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.components=[]; self.methods=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if 'data-score-id' in attrs:
            self.components.append((attrs, list(self.stack)))
        if 'data-score-method' in attrs:
            self.methods.append((attrs, list(self.stack)))
        if tag not in {'meta','link','img','br','hr','input'}:
            self.stack.append((tag,attrs))
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,-1,-1):
            if self.stack[i][0]==tag:
                del self.stack[i:]; break


class ScorePresentationTests(unittest.TestCase):
    def test_minimum_names_cause_and_weighted_impact_without_mutating_saved_result(self):
        children=[row('mne_amplitude_channels'),row('mne_amplitude_time',.31,378),
                  row('fieldtrip_zvalue',9.88,378),row('ieeg_range_plateau')]
        score=aggregate([row(NUMERIC,0,7182000),*children,stability_output(children)], {'version':'project-weighted/1.2','preset':'seeg-basic-score/0.1','weights':{NUMERIC:30,STABILITY:70}})
        before=copy.deepcopy(score)
        primary=[r for r in score['components'] if r['id'] in {NUMERIC,STABILITY}]
        html=score_tree(primary)
        self.assertEqual(score,before)
        self.assertIn('本项扣 2.61 分 × 权重 70.0% = 综合分扣 1.83 分', html)
        self.assertIn('9.88 / 378 秒', html)
        self.assertIn('0 / 7,182,000',html)
        parsed=Structure();parsed.feed(html)
        deciding=[a['data-score-method'] for a,_ in parsed.methods if a.get('class')=='score-determining']
        self.assertEqual(deciding,['fieldtrip_zvalue'])
        self.assertTrue(all('open' not in a for a,_ in parsed.components))
        for a,ancestors in parsed.methods:
            self.assertTrue(any(t=='details' and 'data-score-id' in x for t,x in ancestors))

    def test_ties_and_unavailable_checks_are_not_extra_deductions(self):
        children=[row('mne_amplitude_time',5),row('fieldtrip_zvalue',5),
                  observation(SPECS['ieeg_range_plateau'],reason='range missing <source>')]
        group=stability_output(children);group['normalized_weight']=.7
        html=score_tree([group]);p=Structure();p.feed(html)
        self.assertEqual(sum(a.get('class')=='score-determining' for a,_ in p.methods),2)
        self.assertIn('本次未计入',html)
        self.assertIn('range missing &lt;source&gt;',html)
        self.assertNotIn('range missing <source>',html)
        self.assertIn('综合分扣 3.5 分',html)
        missing=stability_output(children[2:]);missing['automatically_excluded']=True
        self.assertIn('本次权重为 0',score_tree([missing]))

    def test_weighted_children_show_shares_and_deductions(self):
        config=default_config('seeg')
        config['group_weights'][STABILITY].update(mne_amplitude_time=3,fieldtrip_zvalue=1)
        children=[row('mne_amplitude_time',20),row('fieldtrip_zvalue',0),observation(SPECS['ieeg_range_plateau'],reason='unknown range')]
        scored=aggregate([row(NUMERIC),*children],config)
        html=score_tree([r for r in scored['components'] if r['id']==STABILITY])
        self.assertIn('子项按本次有效权重平均',html)
        self.assertIn('75.0%',html)
        self.assertIn('25.0%',html)
        self.assertIn('<th scope="col">模块</th><th scope="col">得分</th><th scope="col">权重</th><th scope="col">检查发现</th>',html)
        self.assertNotIn('计分作用',html)
        self.assertNotIn('本项扣分',html)
        self.assertIn('<td>0%</td>',html)
        self.assertIn('本次未计入',html)
        self.assertNotIn('决定本项得分',html)
        self.assertNotIn('最低分',html)
        # Missing line evidence removes its 20%; stability becomes 50/(30+50).
        self.assertIn('62.5%',html)
        self.assertIn('综合分扣 9.38 分',html)

    def test_union_keeps_distinct_aggregation_and_rejected_identity_evidence(self):
        from ephys_qc.neuropixels_scoring import STATE, CONSTANT, AP
        parent=row(STATE,2,10)
        parent.update(normalized_weight=.7,assessed_methods=[CONSTANT],
            evidence_components=[row(CONSTANT,2,10),row(AP,3,10)],
            unavailable_methods=[{'id':AP,'reason':'缺少通道身份'}])
        html=score_tree([parent])
        self.assertIn('同一通道在同一窗口只计一次',html)
        self.assertIn('缺少通道身份',html)
        self.assertIn('<td>—</td>',html)
        self.assertIn('<td>0%</td>',html)
        self.assertNotIn('计分作用',html)
        self.assertNotIn('决定本项得分</span>',html)
        self.assertNotIn('取有效子项的最低分',html)
        self.assertIn('综合分扣 14 分',html)

    def test_unknown_historical_children_and_measurement_units_are_not_fabricated(self):
        group=row(STABILITY,1,10)
        self.assertIn('未保存子模块明细',score_tree([group]))
        channel=row('mne_amplitude_channels',25,100)
        channel['unit']='channel_block_seconds'
        self.assertEqual(measurement(channel),'分段通道候选占比按时长汇总：25.00%')
        self.assertNotIn('综合分扣',score_tree([group],total_available=False))
        self.assertIn('Signal stability',score_tree([group],english=True))

    def test_eeg_compact_report_retains_expandable_rows_inside_results_section(self):
        import test_report_view
        from ephys_qc.project_scoring import apply_to_view, VERSION
        from ephys_qc.report_view import render_report_view
        fixture=test_report_view.ReportViewTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        view=apply_to_view(fixture.view(),{'version':VERSION,'weights':{'integrity':1,'line_noise':2,'hf_burst':1}})
        before=copy.deepcopy(view);html=render_report_view(view);p=Structure();p.feed(html)
        self.assertEqual(view,before)
        self.assertEqual([a['data-score-id'] for a,_ in p.components],['integrity','line_noise','hf_burst'])
        for attrs,ancestors in p.components:
            self.assertTrue(any(a.get('id')=='score-table' for _,a in ancestors))
            self.assertFalse(any(a.get('id')=='checks' for _,a in ancestors))
        self.assertIn('所属模块 M04',html)


if __name__=='__main__':unittest.main()
