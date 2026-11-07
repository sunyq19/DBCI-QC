"""Presentation contracts: no recomputation, source separation, units and missing data."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ephys_qc.visualizations import visualization_specs
from ephys_qc.visualizations.render import render_gallery, bars, spectrum
from ephys_qc.visualizations.evidence import read_evidence

class VisualizationTests(unittest.TestCase):
    def test_individual_selection_never_reads_unselected_evidence(self):
        data={'status':'completed','calculated':True,'metrics':{'relative_power':[{'channel_name':'C3','band':'alpha','value':.4},{'channel_name':'C4','band':'alpha','value':None}]}}
        old=copy.deepcopy(data);reads=[]
        def load(name):reads.append(name);return data
        result={'artifacts':[{'name':'M04_gnosis_band_power.json'},{'name':'M05_bad_channels.json'}]}
        html=render_gallery(result,load,selected=['band_power'])
        self.assertEqual(reads,['M04_gnosis_band_power.json']);self.assertEqual(data,old)
        self.assertIn('40',html);self.assertIn('未评',html);self.assertIn('0 → 100 %',html)
        self.assertIn('Gnosis-Neurodynamics',html)
        self.assertNotIn('id="viz_psd"',html)
    def test_empty_and_failed_results_are_not_zero(self):
        result={'artifacts':[{'name':'M04_gnosis_band_power.json'}]}
        html=render_gallery(result,lambda _:dict(status='failed',calculated=False,metrics={'relative_power':[dict(channel_name='X',band='alpha',value=.8)]}),selected=['band_power'])
        self.assertIn('对应指标未生成',html);self.assertNotIn('>80<',html)
        self.assertNotIn('id="viz_',render_gallery(result,lambda _: {},selected=[]))
    def test_scope_selection_does_not_merge_window_evidence(self):
        files=['w001--M02_selection.json','w002--M02_selection.json','w001--M04_gnosis_band_power.json','w002--M04_gnosis_band_power.json']
        reads=[]
        def load(n):reads.append(n);return {}
        result={'scope':'recording','recording':{'start_seconds':0,'duration_seconds':240},
                'windows':[{'id':'w001','start_seconds':0,'duration_seconds':120},
                           {'id':'w002','start_seconds':120,'duration_seconds':120}],
                'artifacts':[dict(name=n) for n in files]}
        page=render_gallery(result,load,selected=['band_power'],window='w002--')
        self.assertEqual(reads,['w002--M04_gnosis_band_power.json'])
        self.assertIn('当前图表：原记录 120–240 秒',page)
        self.assertIn('不是整份记录的汇总图',page)
        self.assertNotIn('当前图表：原记录 0–240 秒',page)
        with self.assertRaises(ValueError):render_gallery({'artifacts':[]},load,window='../')
    def test_units_and_unsafe_labels(self):
        a=spectrum([1,2],[[1e-12,1e-11]],['C3'],1e12)
        b=spectrum([1,2],[[1,10]],['C3'],1)
        self.assertEqual(a,b)
        html=bars([('<script>alert(1)</script>',None,False),('X',2,True)],'%')
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertIn('未评',html)
    def test_catalog_keeps_visualizations_out_of_algorithm_registry(self):
        from ephys_qc.method_registry import methods
        v=visualization_specs();self.assertEqual(len(v),12)
        self.assertEqual(sum(s['status']=='available' for s in v),10)
        self.assertFalse({s['id'] for s in v}&{m['id'] for m in methods()})
        with self.assertRaises(ValueError):render_gallery({},lambda _: {},selected=['radar'])

    def test_gallery_groups_keep_figures_available_but_expand_only_psd(self):
        html=render_gallery({},lambda _: {},selected=['waveform','psd','timeline'])
        self.assertIn('<details class="panel" id="viz_psd" open>',html)
        self.assertIn('<details class="panel" id="viz_waveform" >',html)
        self.assertIn('<details class="panel" id="viz_timeline" >',html)
        self.assertIn('href="#viz_timeline" data-panel-link',html)
        self.assertIn('<script src="/visualizations.js" defer></script>',html)
        self.assertNotIn('<script>',html)
        self.assertIn('本窗口没有已保存的波形图',html)

    def test_return_navigation_leaves_embedded_frame(self):
        page=render_gallery({},lambda _: {},selected=[],back_url='/api/v1/jobs/example/report')
        self.assertIn('href="/api/v1/jobs/example/report" target="_top"',page)

    def test_embedded_gallery_stays_within_report_when_controls_change(self):
        page=render_gallery({},lambda _: {},selected=['psd'],embedded=True,action='/charts')
        self.assertIn('<html lang="zh-CN" class="embedded-charts">',page)
        self.assertIn('name="embedded" value="1"',page)
        self.assertIn('action="/charts"',page)
        self.assertIn('id="viz_psd"',page)

    def test_declared_checks_keep_deep_link_targets_when_no_candidates_found(self):
        page=render_gallery({'artifacts':[{'name':'M04_spectral.json'},{'name':'M06_muscle.json'}]},
                            lambda _: {'status':'ok','candidates':[]})
        for target in ['viz_psd','viz_interference','viz_timeline']:
            self.assertIn('id="'+target+'"',page)
        self.assertIn('未检出带有效时间位置的候选区间',page)

    def test_http_gallery_uses_saved_view_without_generic_result_parse(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/workbench'))
        from visualization_page import dispatch_visualizations
        path='/api/v1/jobs/'+'a'*32+'/visualizations'
        view={'scope':'recording','recording':{'duration_seconds':120},
              'window_scores':[{'id':'w000001','start_seconds':0,'duration_seconds':120}],
              'artifacts':['w000001--M04_spectral.json']}
        store=SimpleNamespace(job=lambda _: {'status':'completed'},
                              result=lambda *a,**kw:self.fail('must not parse the generic result'))
        handler=SimpleNamespace(store=store,path=path+'?lang=zh-CN',
                                send_bytes=lambda *a:None)
        with patch('project_score_cache.load',return_value=None), \
             patch('saved_reports.frozen_view',return_value=view), \
             patch('visualization_page.render_gallery',return_value='ok') as render:
            self.assertTrue(dispatch_visualizations(handler,path))
        result=render.call_args.args[0]
        self.assertEqual(result['windows'],view['window_scores'])
        self.assertEqual(result['artifacts'],[{'name':'w000001--M04_spectral.json'}])

    def test_spectral_reader_preserves_window_counts_without_scan_arrays(self):
        from ephys_qc.report_view import line_summary
        rows=[dict(channel_id='C3',channel_name='C3',start_sample=0,stop_sample=100,
                   status='computed',flagged=flag,amplitude_uv=2,
                   scan_frequencies_hz=list(range(100))) for flag in [False,True]]
        original={'psd':{'power_v2_hz':[[1e-12]],'frequencies_hz':[1]},
                  'line_noise':{'observations':rows},'parameterization':{'unused':[1,2,3]}}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'M04_spectral.json';path.write_text(json.dumps(original))
            loaded=read_evidence(path)
        self.assertEqual(loaded['psd'],original['psd'])
        a=line_summary(original['line_noise']);b=line_summary(loaded['line_noise'])
        for key in ['total','hits','percent','observed_frequency_rows']:
            self.assertEqual(a[key],b[key])
        self.assertEqual(b['channels'][0]['percent'],100)
        self.assertNotIn('parameterization',loaded)
        self.assertNotIn('scan_frequencies_hz',loaded['line_noise']['observations'][0])

    @unittest.skipUnless(importlib.util.find_spec('ijson'), 'requires the visualization extra')
    def test_large_muscle_reader_streams_bounded_positions_and_preserves_total(self):
        from ephys_qc.visualizations.render import timeline
        rows=[{'channel_name':'C3','start_seconds':i,'stop_seconds':i+.5,'unneeded':[0]*20} for i in range(551)]
        rows.append({'channel_name':'C3','start_seconds':None,'stop_seconds':600})
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'w000001--M06_muscle.json'
            path.write_text(json.dumps({'filtered_signal':[0]*1000,'candidates':rows}))
            with patch('ephys_qc.visualizations.evidence.SMALL_LIMIT',1), \
                 patch('ephys_qc.visualizations.evidence.json.load',side_effect=AssertionError('must stream')):
                loaded=read_evidence(path)
        self.assertEqual(len(loaded['candidates']),500)
        self.assertEqual(loaded['_visualization_candidate_count'],551)
        self.assertEqual(set(loaded['candidates'][0]),{'channel_name','start_seconds','stop_seconds'})
        html=timeline(loaded['candidates'],0,600,64,loaded['_visualization_candidate_count'])
        self.assertIn('显示 500 / 551 条候选',html)
        self.assertNotIn('filtered_signal',loaded)

if __name__=='__main__':unittest.main()
