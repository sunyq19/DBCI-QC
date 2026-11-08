"""Neuropixels rule routing and non-physiological boundary checks."""
import copy
from types import SimpleNamespace
import unittest
from ephys_qc.recommendations import recommend
from ephys_qc.planning import build_plan
from test_neuromodal_routes import recording


def source(band='ap',count=16,seconds=4):
    r=recording('extracellular',band)
    template=r['metadata']['channels'][0]
    r['metadata']['channels']=[{**copy.deepcopy(template),'index':i,'name':f'AP{i}',
                               'probe_grid':{'shank':0}} for i in range(count)]
    r['metadata']['duration_seconds']=seconds
    r['default_config']['selection'].update(eeg_indices=list(range(count)),duration_seconds=seconds)
    return r


class NeuropixelsStandardTests(unittest.TestCase):
    def test_ap_is_conditional_and_user_can_deselect(self):
        r=source();before=copy.deepcopy(r)
        proposal=recommend(r)
        self.assertTrue(proposal['can_apply'])
        self.assertIn('spikeinterface_bad_channels',proposal['qc_config']['method_config']['extensions'])
        self.assertNotIn('scoring',proposal['qc_config'])
        self.assertEqual(proposal['scope']['standard_version'],'neuropixels-qc/0.1')
        self.assertEqual(r,before)
        deselected=recommend(r,{'method_config':{'extensions':[]}})
        self.assertNotIn('spikeinterface_bad_channels',deselected['qc_config']['method_config']['extensions'])

    def test_lf_missing_shanks_and_small_groups_do_not_inherit_ap_check(self):
        r=source();r['metadata']['channels'][0].pop('probe_grid')
        for item in (source('lf'),source(count=3),r,source(seconds=.1)):
            proposal=recommend(item)
            self.assertTrue(proposal['can_apply'],proposal)
            self.assertNotIn('spikeinterface_bad_channels',proposal['qc_config']['method_config']['extensions'])
            self.assertFalse(any('ECoG' in s for s in proposal['cautions']))

    def test_large_ap_uses_real_chunk_conditions_and_preserves_plan(self):
        r=source(count=384,seconds=4)
        proposal=recommend(r,{'scope':'recording','recording_options':{'window_seconds':120}})
        self.assertTrue(proposal['can_apply'],proposal)
        self.assertIn('spikeinterface_bad_channels',proposal['qc_config']['method_config']['extensions'])
        self.assertEqual(proposal['window_count'],2)
        self.assertEqual(build_plan(r,proposal['selected_modules'],proposal['qc_config'])['plan_id'],proposal['plan_id'])

    def test_short_tail_stays_unassessed_without_silently_removing_method(self):
        proposal=recommend(source(count=384,seconds=3),{'scope':'recording'})
        row=next(m for m in proposal['method_applicability'] if m['id']=='spikeinterface_bad_channels')
        self.assertEqual(row['status'],'partial')
        self.assertEqual(row['window_status_counts']['blocked'],1)

    def test_constant_channel_is_distinct_from_short_quantization_repeats(self):
        import numpy as np
        from ephys_qc.modules.neuropixels.m03 import run
        data=np.array([np.zeros(1000),np.tile([0.,0.,1.,1.],250),np.arange(1000,dtype=float)])
        data[2,12]=np.nan
        saved={}
        context=SimpleNamespace(record={'modality':'extracellular','metadata':{}},
            config={'method_config':{'neuropixels':{}}},result={},row={},
            state={'data':data,'fs':1000.,'start':5.,'first':5000,
                   'channels':[{'channel_id':f'src:{i}','raw_name':f'C{i}','source_index':i} for i in range(3)]},
            save=lambda name,payload:saved.update({name:payload}))
        run(context);rows=saved['M03_continuity.json']['channels']
        self.assertTrue(rows[0]['fully_constant'])
        self.assertEqual(rows[0]['max_exact_constant_run_seconds'],1.)
        self.assertFalse(rows[1]['fully_constant'])
        self.assertEqual(rows[1]['max_exact_constant_run_samples'],2)
        self.assertEqual(rows[2]['nonfinite_sample_count'],1)
        self.assertEqual(context.row['summary']['fully_constant_channel_count'],1)
        self.assertFalse(context.row['summary']['quality_classification'])

    def test_zero_signal_and_missing_historical_checks_are_visible_in_report(self):
        import json, tempfile, re
        from pathlib import Path
        from neuropixels_report import render
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);artifacts=root/'jobs'/'j'/'artifacts';artifacts.mkdir(parents=True)
            item=source('lf',count=1,seconds=2);item['label']='LF fixture'
            job={'id':'j','plan':{'qc_config':item['default_config']}}
            store=SimpleNamespace(root=root,job=lambda identifier:job)
            def save(name,data): (artifacts/name).write_text(json.dumps(data))
            (artifacts.parent/'request.json').write_text(json.dumps({'input':item}))
            save('window-results.json',[{'id':'w0','start_seconds':0,'duration_seconds':2,
                  'modules':[{'id':'M03','summary':{'nonfinite_sample_count':0}}]}])
            save('coverage.json',{'completed_seconds':2,'gap_seconds':0})
            channel={'channel_name':'C0','nonfinite_sample_count':0,'fully_constant':True,
                     'max_exact_constant_run_seconds':2}
            saved={'channels':[channel],'input_range':{'start_seconds':0,'stop_seconds':2}}
            save('w0--M03_continuity.json',saved)
            page=render(store,'j')
            self.assertIn('有待复核的通道或数值',page)
            self.assertIn('整分析窗恒值',page)
            self.assertNotIn('100.00',page)
            self.assertEqual(re.findall(r'<summary><h2>(.*?)</h2>',page),['检查结果','问题定位','图表分析','报告详情'])
            channel.pop('fully_constant');channel.pop('max_exact_constant_run_seconds')
            save('w0--M03_continuity.json',saved)
            page=render(store,'j')
            self.assertIn('历史记录未保存此汇总',page)
            self.assertIn('部分检查汇总未保存',page)

if __name__=='__main__':unittest.main()
