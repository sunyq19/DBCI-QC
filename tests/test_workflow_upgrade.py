"""Processing eligibility, batch lifecycle, and comparable frozen evidence."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]
from ephys_qc.processing_history import scope, restrict_line_evidence, validate_declaration
from ephys_qc.report_view import line_summary
from ephys_qc.report_aggregate import channel_evidence
from ephys_qc.recommendations import recommend
from ephys_qc.planning import build_plan
from ephys_qc.comparison import comparison_row, compare
from batch_jobs import BatchJobs
from test_recommendations import recording

class ProcessingTests(unittest.TestCase):
    def test_lowpass40_is_unassessed_not_a_clean_score(self):
        record=recording(fs=500)
        record['preprocessing']=validate_declaration(dict(verified=True,lowpass_hz=40,note='export settings'))
        assessment=scope(record,{},500)
        self.assertTrue(assessment['hf_limited_by_history'])
        self.assertEqual(assessment['line_evaluable_hz'],[])
        rec=recommend(record)
        rows={m['id']:m for m in build_plan(record,['M03','M04','M06'])['method_applicability']}
        self.assertEqual(rows['thomson_line']['status'],'blocked')
        self.assertEqual(rows['hf_burst']['status'],'blocked')
        data={'line_noise':{'status':'computed','observations':[dict(nominal_hz=50,status='computed',flagged=False)]}}
        restrict_line_evidence(data,assessment)
        self.assertEqual(data['line_noise']['status'],'not_assessed_preprocessing')
        self.assertIsNone(line_summary(data['line_noise'])['percent'])
        self.assertEqual(data['line_noise']['observations'][0]['upstream_observation']['status'],'computed')

    def test_notch_does_not_assume_all_harmonics_removed(self):
        a=scope({'preprocessing':dict(verified=True,notch_hz=[50])},{},500)
        self.assertNotIn(50,a['line_evaluable_hz']);self.assertIn(100,a['line_evaluable_hz']);self.assertIn(60,a['line_evaluable_hz'])

    def test_partial_notch_keeps_other_measurements_without_a_full_score(self):
        line={'processing_exclusions':[{'frequency_hz':50}], 'observations':[dict(status='computed',flagged=False,channel_id='a',channel_name='A',start_sample=0,stop_sample=10)]}
        summary=line_summary(line)
        self.assertEqual(summary['total'],1)
        self.assertFalse(summary['score_eligible'])
        self.assertEqual(channel_evidence({},summary,[]),[])

    def test_unknown_history_does_not_invent_a_filter(self):
        a=scope({'preprocessing':dict(verified=False,lowpass_hz=40)},{},500)
        self.assertFalse(a['hf_limited_by_history']);self.assertIn(50,a['line_evaluable_hz'])

    def test_invalid_declarations(self):
        for p in [dict(verified=True,note=''),dict(verified=False,notch_hz=[float('nan')]),dict(verified=False,highpass_hz=50,lowpass_hz=40)]:
            with self.assertRaises(ValueError):validate_declaration(p)

class FakeStore:
    def __init__(self,root):
        self.root=root;self.lock=threading.RLock();self.jobs={};self.inputs={}
        self.directory=dict(package_id='p',manifest_hash='h',records=[dict(id='r1',path='a.edf'),dict(id='r2',path='b.edf')])
        self.packages=Mock();self.packages.records.side_effect=lambda _:copy.deepcopy(self.directory)
        self.inputs['input1']=dict(id='input1',record_revision=1,dataset_context=dict(package_id='p',manifest_hash='h',record_id='r1'))
    def recommend_request(self,body):return dict(can_apply=True,selected_modules=['M03'],qc_config=body['qc_config'])
    def plan_request(self,body):return self.inputs[body['input_id']],dict(plan_id='plan',method_applicability=[])
    def submit(self,body,*,batch_id=None):
        identifier=str(len(self.jobs)+1);job=dict(id=identifier,status='completed',batch_id=batch_id)
        self.jobs[identifier]=job;return job
    def job(self,identifier):return copy.deepcopy(self.jobs[identifier])
    def cancel(self,identifier):self.jobs[identifier]['status']='cancelled'

class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=FakeStore(Path(self.temp.name));self.b=BatchJobs(self.store,start_worker=False)
    def preview(self):return self.b.preview(dict(package_id='p',manifest_hash='h',record_ids=['r1','r2']))
    def submit(self,p):return self.b.submit(dict(preview_id=p['id'],preview_hash=p['preview_hash'],confirmed=True))
    def test_unconfirmed_record_remains_explicit_and_repeated_submit_is_idempotent(self):
        p=self.preview();self.assertEqual([r['status'] for r in p['records']],['ready','unavailable'])
        a=self.submit(p);b=self.submit(p);self.assertEqual(a['id'],b['id']);self.assertEqual(self.b.queue.qsize(),1)
        self.b._run(p['id']);result=self.b.get(p['id'])
        self.assertEqual(result['finished'],1);self.assertEqual(result['runnable'],1)
        self.assertEqual(self.store.jobs['1']['batch_id'],p['id'])
        self.assertEqual(result['records'][1]['status'],'unavailable')
    def test_stale_manifest_and_revision_rejected(self):
        p=self.preview();self.store.directory['manifest_hash']='changed'
        with self.assertRaisesRegex(ValueError,'清单'):self.submit(p)
        self.store.directory['manifest_hash']='h';self.store.inputs['input2']={**self.store.inputs['input1'],'id':'input2','record_revision':2}
        with self.assertRaisesRegex(ValueError,'修改'):self.submit(p)
    def test_cancel_stops_pending_children(self):
        p=self.preview();self.submit(p);self.b.cancel(p['id']);self.b._run(p['id'])
        self.assertEqual(self.b.get(p['id'])['status'],'cancelled');self.assertFalse(self.store.jobs)
    def test_restart_keeps_child_links_and_marks_parent_interrupted(self):
        p=self.preview();self.submit(p)
        restored=BatchJobs(self.store,start_worker=False)
        self.assertEqual(restored.get(p['id'])['status'],'interrupted');self.assertTrue(restored.queue.empty())
    def test_client_cannot_inject_paths(self):
        with self.assertRaises(ValueError):self.b.preview(dict(package_id='p',manifest_hash='h',record_ids=['r1'],source_path='/tmp/a'))

class ComparisonTests(unittest.TestCase):
    def row(self,id='a',change=None):
        r=recording();r['preprocessing']=dict(verified=True,note='unfiltered',notch_hz=[])
        req=dict(input=r,qc_config=r['default_config'],selected_modules=['M03'])
        view={'score':dict(version='v1',value=90,coverage_complete=True,components=[dict(id='integrity',value=90,denominator=100,unit='samples')])}
        env=[dict(implementation='v1',packages={'numpy':'1'},actual_executed_sources={'m03':{'sha256':'a','file':'/private/a'}})]
        if change: change(req,env)
        return comparison_row(dict(id=id,label=id),req,view,env)
    def test_same_conditions_compare_without_local_paths(self):
        data=compare([self.row('a'),self.row('b')]);self.assertTrue(data['groups'][0]['comparable'])
        self.assertNotIn('/private',json.dumps(data))
    def test_unknown_history_keeps_values_but_disables_claim_of_comparability(self):
        a=self.row();a['unknown']=['处理史未确认'];data=compare([a,self.row('b')]);self.assertFalse(data['groups'][0]['comparable'])
        self.assertEqual(data['groups'][0]['rows'][0]['components'][0]['value'],90)
    def test_different_rules_are_separate_groups(self):
        changes=[lambda req,env:req['input'].update(reference_scheme='bipolar'),
                 lambda req,env:req['qc_config']['method_config'].update(spectral={'line_family_alpha':.001}),
                 lambda req,env:req['input']['preprocessing'].update(notch_hz=[50]),
                 lambda req,env:env[0]['packages'].update(numpy='2')]
        for change in changes:
            data=compare([self.row('a'),self.row('b',change)])
            self.assertEqual(len(data['groups']),2)
            self.assertTrue(all(not g['comparable'] for g in data['groups']))
    def test_missing_component_never_becomes_zero(self):
        a=self.row();a['components'][0]['value']=None;data=compare([a,self.row('b')]);self.assertEqual(data['groups'][0]['component_ids'],[])

if __name__=='__main__':unittest.main()
