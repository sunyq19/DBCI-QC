"""Saved-result aggregation: missing is not passing, and scores retain their scope."""
import copy
import json
from pathlib import Path
import sys
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]
import test_package_record_links as linked_fixtures
from ephys_qc.dataset_qc.consistency import evaluate_dataset
from ephys_qc.dataset_qc.overview import aggregate_overview, summarize_signal
from dataset_overview import build_overview, render_overview, source_match
from data_library import library
from package_jobs import fingerprint
from server import Handler


def signal(scope='recording',status='completed'):
    return {'job':dict(id='a'*32,status=status,created_at='2026-11-06'),'source_status':'matched',
            'result':{'scope':scope,'coverage':dict(total_seconds=10,completed_seconds=10,failed_seconds=0,unexecuted_seconds=0,gap_seconds=0),
                      'modules':[dict(id='M03',status='partial'),dict(id='M07',status='skipped')],
                      'report_view':{'score':{'value':88.51,'version':'test/1','components':[dict(id='line',name='工频',value=88.51)]}}}}


class SummaryTests(unittest.TestCase):
    freeze=linked_fixtures.LinkedRecordTests.freeze
    setUp=linked_fixtures.LinkedRecordTests.setUp

    def test_empty_summary_distinguishes_unassessed(self):
        data=aggregate_overview(self.plan)
        self.assertIsNone(data['dataset_score'])
        self.assertIsNone(data['summary']['file_counts'])
        self.assertFalse(data['summary']['dataset_assessed'])
        self.assertEqual(data['summary']['signal_status_counts'],{'not_run':4})
        self.assertTrue(all(r['signal']['score'] is None for r in data['records']))

    def test_full_time_does_not_erase_partial_checks_or_create_cohort_score(self):
        result=evaluate_dataset(self.root,self.plan)
        data=aggregate_overview(self.plan,dataset_result=result,signals={self.r['id']:signal()})
        self.assertEqual(data['summary']['reported'],1)
        self.assertEqual(data['summary']['full_duration_computed'],1)
        row=data['records'][0]['signal']
        self.assertEqual(row['score'],88.51)
        self.assertEqual(row['incomplete_modules'][0]['id'],'M03')
        self.assertEqual(row['skipped_modules'],['M07'])
        self.assertIsNone(data['dataset_score'])
        self.assertEqual(data['subjects'][0]['reported'],1)
        self.assertEqual(data['subjects'][1]['reported'],0)

    def test_window_gap_failures_and_unexecuted_are_not_full_coverage(self):
        self.assertFalse(summarize_signal(signal('window'))['full_duration_computed'])
        for key in ('failed_seconds','gap_seconds','unexecuted_seconds'):
            snap=signal();snap['result']['coverage'][key]=1
            with self.subTest(key=key):self.assertFalse(summarize_signal(snap)['full_duration_computed'])
        snap=signal();snap['result']['coverage']['completed_seconds']=9
        self.assertFalse(summarize_signal(snap)['full_duration_computed'])
        snap=signal();snap['result']['coverage']['total_seconds']=float('nan')
        self.assertFalse(summarize_signal(snap)['full_duration_computed'])

    def test_source_conflict_excludes_score_but_preserves_historical_report(self):
        snap=signal();snap['source_status']='mismatch';s=summarize_signal(snap)
        self.assertEqual(s['status'],'source_mismatch');self.assertTrue(s['report_available'])
        self.assertFalse(s['usable_report']);self.assertIsNone(s['score']);self.assertEqual(s['components'],[])
        self.assertFalse(s['full_duration_computed']);self.assertIsNotNone(s['report_url'])
        snap=signal();snap['result_error']=True;s=summarize_signal(snap)
        self.assertEqual(s['status'],'report_unavailable');self.assertFalse(s['report_available'])

    def test_non_eeg_no_score_and_nan_not_a_score(self):
        snap=signal();snap['result'].pop('report_view');s=summarize_signal(snap)
        self.assertIsNone(s['score']);self.assertTrue(s['full_duration_computed'])
        snap=signal();snap['result']['report_view']['score']['value']=float('nan')
        self.assertIsNone(summarize_signal(snap)['score'])

    def test_file_conflict_only_attributed_to_affected_record(self):
        # An item can list every file. Its one missing file must not taint every record.
        (self.root/self.r['channels_tsv']).unlink()
        result=evaluate_dataset(self.root,self.plan)
        data=aggregate_overview(self.plan,dataset_result=result)
        file_check=next(c for c in result['checks'] if c['code']=='files')
        self.assertIn(file_check['id'],data['records'][0]['finding_ids'])
        self.assertTrue(all(file_check['id'] not in r['finding_ids'] for r in data['records'][1:]))
        # A shared participants.tsv on a record-specific check cannot expand its attribution.
        result['checks']=[dict(id='specific',module='D02',code='participants',status='conflict',records=[self.r['id']],files=['participants.tsv'])]
        data=aggregate_overview(self.plan,dataset_result=result)
        self.assertEqual([r['finding_ids'] for r in data['records']],[['specific'],[],[],[]])

    def test_action_groups_preserve_checks_and_do_not_call_units_bad_signal(self):
        # The same label discrepancy on two recordings is one display category.
        result=evaluate_dataset(self.root,self.plan)
        rows=[]
        for n,r in enumerate(self.plan['consistency']['records'][:2]):
            rows.append(dict(id=f'u{n}',module='D02',code='units',status='conflict',records=[r['id']],files=[r['path']],
                             observed={'conflicts':[{'channel':'Cz','file':'nV','table':'uV'}]}))
        rows.append(dict(id='read',module='D01',code='read',status='conflict',records=[self.r['id']],files=[]))
        rows.append(dict(id='missing',module='D02',code='units',status='unassessed',records=[self.r['id']],files=[]))
        result['checks']=rows;before=copy.deepcopy(result)
        data=aggregate_overview(self.plan,dataset_result=result)
        self.assertEqual(result,before)
        self.assertEqual(len(data['attention_groups']),2)
        units=next(g for g in data['attention_groups'] if g['code']=='units')
        self.assertEqual(units['record_count'],2)
        self.assertEqual(units['unit_labels'],[dict(file_unit='nV',table_unit='uV')])
        self.assertIn('尚不能',units['meaning'])
        self.assertIn('标定',units['next_step'])
        self.assertEqual(data['summary']['findings']['conflict'],3)
        self.assertEqual(data['summary']['findings']['unassessed'],1)
        self.assertTrue(all('missing' not in g['check_ids'] for g in data['attention_groups']))

    def test_missing_metadata_is_not_worded_as_a_mismatch(self):
        from ephys_qc.dataset_qc.presentation import attention_groups
        checks=[dict(id='r',code='rates',status='review',observed={'unknown_channels':['Cz']})]
        groups=attention_groups(checks,[dict(id='record',subject='s',finding_ids=['r'])])
        self.assertIn('补充',groups[0]['title'])
        self.assertNotIn('不一致',groups[0]['title'])
        self.assertEqual(attention_groups([dict(id='p',code='rates',status='pass')],[]),[])

    def save_dataset(self):
        jid='d'*32;path=self.store.packages.root/jid;path.mkdir()
        (path/'request.json').write_text(json.dumps(dict(expectations=self.plan,source_root=str(self.root))))
        output=path/'result';output.mkdir();(output/'result.json').write_text(json.dumps(evaluate_dataset(self.root,self.plan)))
        self.store.packages.jobs[jid]=dict(id=jid,package_id='pilot',status='completed',created_at='2026-11-06',manifest_hash=fingerprint(self.plan))
        return jid

    def save_signal(self,jid='a'*32,status='completed',date='2026-11-06',digest=None):
        intake=self.store.open_package_record(self.body)
        public=self.store.confirm_intake(intake['id'],self.confirmation)['input']
        item=copy.deepcopy(self.store.inputs[public['id']])
        if digest:item['expected_source_files'][0]['sha256']=digest
        path=self.store.root/'jobs'/jid;path.mkdir(parents=True)
        (path/'request.json').write_text(json.dumps({'input':item}))
        self.store.jobs[jid]=dict(id=jid,status=status,created_at=date,input_id=item['id'],dataset_context=item['dataset_context'])
        return item

    def test_latest_failed_attempt_does_not_fall_back_to_good_score(self):
        self.save_dataset();self.save_signal();self.save_signal('b'*32,'failed','2026-11-07')
        with patch.object(self.store,'result',return_value=signal()['result']) as reader:
            data=build_overview(self.store,'pilot');reader.assert_not_called()
        self.assertEqual(data['records'][0]['signal']['status'],'failed')
        self.assertEqual(data['summary']['reported'],0)

    def test_saved_fingerprints_join_and_manifest_history(self):
        jid=self.save_dataset();item=self.save_signal()
        result=evaluate_dataset(self.root,self.plan)
        self.assertEqual(source_match(item,str(self.root),result),'matched')
        with patch.object(self.store,'result',return_value=signal()['result']):
            data=build_overview(self.store,'pilot')
            self.assertEqual(data['summary']['reported'],1)
            self.assertEqual(data['records'][0]['signal']['source_status'],'matched')
            self.plan['scope']='revised';self.config.write_text(json.dumps(self.plan))
            now=build_overview(self.store,'pilot');old=build_overview(self.store,'pilot',jid)
        self.assertFalse(now['summary']['dataset_assessed']);self.assertEqual(now['summary']['reported'],0)
        self.assertFalse(old['current_manifest']);self.assertEqual(old['summary']['reported'],1)
        with self.assertRaisesRegex(ValueError,'不属于'):
            self.store.packages.jobs[jid]['package_id']='other';build_overview(self.store,'pilot',jid)

    def test_mismatching_companion_sources_excluded_and_export_is_escaped(self):
        self.save_dataset();self.save_signal(digest='0'*64)
        with patch.object(self.store,'result',return_value=signal()['result']):data=build_overview(self.store,'pilot')
        self.assertEqual(data['summary']['reported'],0)
        self.assertEqual(data['records'][0]['signal']['status'],'source_mismatch')
        data['label']='<script>alert(1)</script>'
        html=render_overview(data)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('来源不一致',html);self.assertIn('清单指纹',html)
        self.assertIn('Source mismatch',render_overview(data,'en'))

    def test_library_latest_revision_no_duplicate_linked_inputs_or_paths(self):
        self.save_dataset();self.save_signal()
        self.store.inputs['old']=dict(id='old',label='old',record_family='f',record_revision=1)
        self.store.inputs['new']=dict(id='new',label='new',record_family='f',record_revision=2)
        self.store.jobs['old-run']=dict(id='old-run',status='completed',input_id='old',created_at='2026-11-01')
        with patch.object(self.store.intakes,'pending',return_value=[dict(id='pending',filename='p.edf',received_at='2026-11-07')]):
            data=library(self.store)
        self.assertEqual(data['counts'],dict(datasets=1,records=2))
        row=next(r for r in data['items'] if r['id']=='record:new')
        self.assertEqual(row['status'],'not_run');self.assertIsNone(row['latest_run_url'])
        self.assertNotIn('source_path',json.dumps(data));self.assertNotIn(str(self.root),json.dumps(data))

    def test_library_separates_only_explicit_validation_cases(self):
        self.store.settings['validation_library_ids'] = ['dataset:pilot']
        self.store.inputs['ordinary'] = dict(id='ordinary', label='New upload')
        self.store.jobs['failed'] = dict(id='failed', input_id='ordinary', status='failed', created_at='2026-11-06')
        data = library(self.store)
        self.assertEqual(next(r for r in data['items'] if r['id']=='dataset:pilot')['category'], 'validation')
        self.assertEqual(next(r for r in data['items'] if r['id']=='record:ordinary')['category'], 'data')
        self.assertEqual(data['examples'], [])

    def test_featured_record_requires_matching_completed_report(self):
        item = self.save_signal()
        self.store.settings['demo_examples'] = [dict(kind='record', id='demo', label='Demo',
                                                    job_id='a'*32, input_id=item['id'])]
        with patch.object(self.store, 'result', return_value=signal()['result']):
            row = library(self.store)['examples'][0]
            self.assertEqual(row['score'], 88.51)
            self.assertIn('job='+'a'*32, row['url'])
            self.store.settings['demo_examples'][0]['input_id'] = 'unrelated'
            self.assertEqual(library(self.store)['examples'], [])
            self.store.settings['demo_examples'][0]['input_id'] = item['id']
            self.store.jobs['a'*32]['status'] = 'failed'
            self.assertEqual(library(self.store)['examples'], [])
        self.store.jobs['a'*32]['status'] = 'completed'
        with patch.object(self.store, 'result', side_effect=FileNotFoundError):
            self.assertEqual(library(self.store)['examples'], [])

    def test_featured_dataset_keeps_issues_and_uses_latest_attempt(self):
        self.save_dataset(); self.save_signal()
        self.store.settings['demo_examples'] = [dict(kind='dataset', id='demo', label='Demo', package_id='pilot')]
        with patch.object(self.store, 'result', return_value=signal()['result']):
            row = library(self.store)['examples'][0]
            self.assertEqual(row['reported'], 1)
            self.assertEqual(row['records'], 4)
        self.save_signal('b'*32, 'failed', '2026-11-07')
        self.assertEqual(library(self.store)['examples'], [])

    def test_summary_api_export_and_local_origin_guard(self):
        self.save_dataset()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.store=self.store
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path,headers=None):
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,headers=headers or {})
            try: response=opener.open(req,timeout=3)
            except urllib.error.HTTPError as e: response=e
            with response:return response.status,response.headers,response.read()
        try:
            for path in ('/api/v1/data','/api/v1/packages/pilot/overview','/data-library.js'):
                self.assertEqual(get(path)[0],200)
            status,headers,body=get('/api/v1/packages/pilot/overview/report?lang=en&download=1')
            self.assertEqual(status,200);self.assertIn('attachment',headers['Content-Disposition'])
            self.assertIn(b'Dataset summary',body)
            self.assertEqual(get('/api/v1/packages/pilot/overview?job=invalid')[0],400)
            self.assertEqual(get('/api/v1/packages/pilot/overview?path=/tmp')[0],400)
            self.assertEqual(get('/api/v1/data',{'Origin':'https://other.test'})[0],403)
        finally:
            server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
