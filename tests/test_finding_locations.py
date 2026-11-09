"""Locations are saved detector evidence, never inferred from scores or waves."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from finding_locations import build, locations, read_locations
from review_workspace import ReviewWorkspace


class Locations(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); (self.root/'artifacts').mkdir()
        self.save('request.json', {'input': {'id':'x'}, 'qc_config':{'selection':{'start_seconds':0,'duration_seconds':30}}})
        self.save('result.json', {'modules':[{'id':m,'status':'completed'} for m in ['M03','M04','M05','M06']]})
        self.save('artifacts/M02_selection.json', {'channels':[
            {'source_index':7,'raw_name':'same','channel_id':'x:7'},
            {'source_index':2,'raw_name':'same','channel_id':'x:2'}], 'recording':{'start_seconds':0,'duration_seconds':30}})
    def save(self, name, value): (self.root/name).write_text(json.dumps(value))
    def result(self): return build(ReviewWorkspace(self.root))
    def test_all_channels_and_checks_merged_without_cross_method_or_gap(self):
        self.save('artifacts/M06_muscle.json', {'candidates':[
            {'channel_index':i,'start_seconds':a,'stop_seconds':b,'kind':'hf'}
            for i in [0,1] for a,b in [(1,2),(1.5,3),(5,6),(8,9),(11,12),(14,15)]]})
        self.save('artifacts/M06_gnosis_high_band.json', {'status':'completed','candidates':[
            {'channel_index':1,'start_seconds':1,'stop_seconds':2,'localization':'channel_interval'}]})
        data=self.result();hf=[r for r in data['findings'] if r['method']=='high_frequency_burst']
        self.assertEqual(len(hf),10);self.assertEqual(hf[0]['start'],1);self.assertEqual(hf[0]['stop'],3)
        self.assertEqual({tuple(r['channels']) for r in hf},{('x:7',),('x:2',)})
        self.assertTrue(any(r['method']=='gnosis_high_band' for r in data['findings']))
        self.assertNotIn('source_path',json.dumps(data))
    def test_channel_only_and_group_scope_are_preserved(self):
        self.save('artifacts/M05_bad_channels.json', {'candidates':[
            {'channel_index':0,'window_indices':[],'start_seconds':0,'stop_seconds':30}]})
        self.save('artifacts/M06_fieldtrip_zvalue.json', {'status':'completed','candidates':[
            {'localization':'interval_only','scope':'selected_channels','start_seconds':4,'stop_seconds':5}]})
        data=self.result()['findings']
        self.assertEqual(data[0]['localization'],'channel')
        group=next(r for r in data if r['method']=='fieldtrip_zvalue')
        self.assertEqual(group['localization'],'group_interval');self.assertEqual(set(group['channels']),{'x:7','x:2'})
    def test_large_muscle_tail_is_not_read(self):
        blob=b'{"candidates":[{"channel_index":0,"start_seconds":1,"stop_seconds":2}],"sample_metrics":"'+b'0'*2**20+b'"}'
        class Reader(io.BytesIO):
            def close(self): self.consumed=self.tell();super().close()
        reader=Reader(blob)
        class File:
            name='M06_muscle.json'
            def is_symlink(self):return False
            def is_file(self):return True
            def stat(self):return type('Stat',(),{'st_size':len(blob)})()
            def open(self,*a):return reader
        data=read_locations(File())
        self.assertEqual(len(data['candidates']),1);self.assertLess(reader.consumed,200000)
    def test_spectral_nonflagged_not_promoted(self):
        self.save('artifacts/M04_spectral.json',{'line_noise':{'observations':[
            {'channel_index':0,'start_seconds':1,'stop_seconds':2,'flagged':False},
            {'channel_index':1,'start_seconds':1,'stop_seconds':2,'flagged':True,'status':'computed'}]}})
        result=self.result();self.assertEqual(len(result['findings']),1);self.assertEqual(result['findings'][0]['channels'],['x:2'])
    def test_descriptive_spectrum_is_not_an_empty_passed_line_check(self):
        self.save('artifacts/M04_spectral.json', {'psd':{'channels':[]}, 'line_noise':{'observations':[{'channel_index':0,'power':.1}]}})
        self.assertNotIn('line_noise',[m['id'] for m in self.result()['methods']])

    def test_unresolved_or_failed_not_promoted_and_truncation_visible(self):
        self.save('artifacts/M06_muscle.json',{'candidates':[{'channel_name':'same','start_seconds':1,'stop_seconds':2}]})
        self.save('artifacts/M06_gnosis_artifact.json',{'status':'failed','candidates':[{'channel_index':0,'start_seconds':1,'stop_seconds':2}]})
        self.save('artifacts/M03_continuity.json',{'candidate_details_truncated':True,'candidates':[]})
        data=self.result();self.assertEqual(data['findings'],[])
        self.assertEqual({r['code'] for r in data['warnings']},{'unresolved_channel','location_evidence_unavailable','stored_locations_incomplete'})
    def test_cache_invalidation_preserves_evidence(self):
        path=self.root/'artifacts/M06_muscle.json'
        self.save('artifacts/M06_muscle.json',{'candidates':[]});before=path.read_bytes()
        workspace=ReviewWorkspace(self.root);self.assertEqual(locations(workspace)['findings'],[])
        self.assertEqual(path.read_bytes(),before)
        self.save('artifacts/M06_muscle.json',{'candidates':[{'channel_index':0,'start_seconds':1,'stop_seconds':2}]})
        self.assertEqual(len(locations(workspace)['findings']),1)

if __name__=='__main__': unittest.main()
