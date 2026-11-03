"""Unequal windows, missing evidence and local anomalies must retain their meaning."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from ephys_qc.report_view import build_report_view, render_report_view


class WholeScoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.parent={'analysis_profile':'scalp-eeg/1','scope':'recording','status':'completed','source_integrity':'verified_after_run',
                     'recording':{'channel_count':1,'sampling_rate_hz':10,'start_seconds':0,'duration_seconds':150,'source_indices':[7]},
                     'input_metadata':{'format':'EDF','duration_seconds':150},'modules':[{'id':f'M0{i}','status':'completed'} for i in range(3,7)],
                     'coverage':{'total_samples':1500,'completed_samples':1500,'gap_samples':0,'total_seconds':150,'completed_seconds':150,'gap_seconds':0,'unexecuted_seconds':0},'windows':[],'artifacts':[]}
        for i,(start,duration,valid,bad,nwin,nhit) in enumerate([(0,120,119,0,10,0),(120,30,29,15,2,1)]):
            wid=f'w{i+1:06d}';rec={**self.parent['recording'],'start_seconds':start,'duration_seconds':duration,'start_sample':start*10,'stop_sample':(start+duration)*10}
            obs=[{'channel_id':'source:7','channel_index':0,'channel_name':'Cz','status':'computed','start_sample':start*10+k*10,'stop_sample':start*10+k*10+10,'start_seconds':start+k,'stop_seconds':start+k+1,'flagged':k<nhit,'amplitude_uv':2,'peak_frequency_hz':50} for k in range(nwin)]
            payloads={'M03_continuity.json':{'measurements':[{'channel_id':'source:7','channel_name':'Cz','finite_sample_count':duration*10,'nonfinite_sample_count':0,'constant_sample_count':0,'finite_outside_constant_sample_count':duration*10}]},
                      'M04_spectral.json':{'line_noise':{'observations':obs}},'M05_bad_channels.json':{},
                      'M06_muscle.json':{'status':'ok','channels':[{'channel_id':'source:7','channel_name':'Cz','status':'ok','valid_seconds':valid,'candidate_seconds':bad}],
                                           'candidates':[{'channel_id':'source:7','channel_name':'Cz','start_seconds':start+1,'stop_seconds':start+1+bad,'peak_z_score':5}] if bad else []}}
            child={'analysis_profile':'scalp-eeg/1','scope':'window','recording':rec,'input_metadata':self.parent['input_metadata'],'modules':self.parent['modules'],'artifacts':[{'name':n} for n in payloads]}
            payloads['result.json']=child
            for n,data in payloads.items():
                filename=wid+'--'+n;(self.root/filename).write_text(json.dumps(data));self.parent['artifacts'].append({'name':filename})
            self.parent['windows'].append({'id':wid,'start_seconds':start,'duration_seconds':duration,'start_sample':start*10,'stop_sample':(start+duration)*10,'status':'completed','result_artifact':wid+'--result.json'})
    def view(self):return build_report_view(self.parent,self.root,'Example')
    def edit(self,name,fn):
        p=self.root/name;value=json.loads(p.read_text());fn(value);p.write_text(json.dumps(value))
    def test_aggregate_actual_denominators_not_mean_of_window_scores(self):
        v=self.view();parts=v['score']['components']
        self.assertEqual(parts[0]['value'],100)
        self.assertAlmostEqual(parts[1]['value'],1100/12)
        self.assertAlmostEqual(parts[2]['value'],13300/148)
        self.assertAlmostEqual(v['score']['value'],min(100,1100/12,13300/148))
        self.assertNotAlmostEqual(v['score']['value'],sum(w['value'] for w in v['window_scores'])/2)
        self.assertEqual(v['hf_candidates'][0]['start_seconds'],121)
        self.assertEqual(v['channel_evidence'][0]['components']['hf_burst']['denominator'],148)
    def test_local_component_survives_global_aggregation(self):
        v=self.view();low=v['local_quality']['lowest'];self.assertEqual(low['name'],'Cz')
        self.assertAlmostEqual(low['lowest_component']['value'],13300/148)
        report=render_report_view(v);self.assertIn('整份检查',report);self.assertIn('按通道查看分项',report);self.assertIn('按时段查看分数',report)
    def test_missing_tail_component_withholds_whole_total(self):
        self.edit('w000002--M06_muscle.json',lambda x:x.update(status='insufficient_duration',channels=[],candidates=[]))
        v=self.view();self.assertIsNone(v['score']['value']);self.assertIsNone(v['score']['components'][2]['value'])
        self.assertEqual(v['score']['components'][0]['value'],100)
        self.assertIsNone(v['local_quality']['channels'][0]['components'][2]['value'])
    def test_gap_and_unverified_source_do_not_yield_whole_total(self):
        for change in ('gap','source'):
            with self.subTest(change=change):
                original=copy.deepcopy(self.parent)
                if change=='gap':self.parent['coverage']['gap_samples']=5
                else:self.parent['source_integrity']='verification_incomplete'
                self.assertIsNone(self.view()['score']['value']);self.parent=original
    def test_failed_window_is_not_counted_as_good(self):
        self.parent['windows'][1]['status']='failed'
        v=self.view();self.assertIsNone(v['score']['value']);self.assertTrue(v['evidence_errors'])
    def test_source_channel_mismatch_is_rejected(self):
        self.edit('w000002--result.json',lambda x:x['recording'].update(source_indices=[8]))
        v=self.view();self.assertIsNone(v['score']['value']);self.assertTrue(v['evidence_errors'])
    def test_frozen_evidence_and_scores_remain_unchanged(self):
        before={p:p.read_bytes() for p in self.root.iterdir()};parent=copy.deepcopy(self.parent)
        self.view();self.assertEqual(self.parent,parent)
        for p,value in before.items():self.assertEqual(p.read_bytes(),value)

if __name__=='__main__':unittest.main()
