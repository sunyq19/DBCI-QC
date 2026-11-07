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
from data_library import library, featured_reports
from package_jobs import fingerprint
from server import Handler


def signal(scope='recording',status='completed'):
    return {'job':dict(id='a'*32,status=status,created_at='2026-11-06'),'source_status':'matched',
            'result':{'scope':scope,'coverage':dict(total_seconds=10,completed_seconds=10,failed_seconds=0,unexecuted_seconds=0,gap_seconds=0),
                      'modules':[dict(id='M03',status='partial'),dict(id='M07',status='skipped')],
                      'report_view':{'score':{'value':88.51,'version':'test/1','components':[dict(id='line',name='工频',value=88.51)]}}}}


class SummaryTests(unittest.TestCase):
    def setUp(self):
        linked_fixtures.LinkedRecordTests.setUp(self)
        self.store.settings['example_cache_dir']=str(self.store.root/'unpublished-examples')

    freeze=linked_fixtures.LinkedRecordTests.freeze

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
        if status=='completed':
            (path/'artifacts').mkdir()
            (path/'artifacts/report.html').write_text('<html>Saved report</html>')
        return item

    def test_latest_failed_attempt_does_not_fall_back_to_good_score(self):
        self.save_dataset();self.save_signal();self.save_signal('b'*32,'failed','2026-11-07')
        with patch.object(self.store,'dataset_result',return_value=signal()['result']) as reader:
            data=build_overview(self.store,'pilot');reader.assert_not_called()
        self.assertEqual(data['records'][0]['signal']['status'],'failed')
        self.assertEqual(data['summary']['reported'],0)

    def test_saved_fingerprints_join_and_manifest_history(self):
        jid=self.save_dataset();item=self.save_signal()
        result=evaluate_dataset(self.root,self.plan)
        self.assertEqual(source_match(item,str(self.root),result),'matched')
        with patch.object(self.store,'dataset_result',return_value=signal()['result']):
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
        with patch.object(self.store,'dataset_result',return_value=signal()['result']):data=build_overview(self.store,'pilot')
        self.assertEqual(data['summary']['reported'],0)
        self.assertEqual(data['records'][0]['signal']['status'],'source_mismatch')
        data['label']='<script>alert(1)</script>'
        html=render_overview(data)
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
        self.assertIn('来源不一致',html);self.assertIn('清单指纹',html)
        self.assertIn('Source mismatch',render_overview(data,'en'))

    def test_dataset_examples_are_selectable_without_reports_and_not_duplicated(self):
        self.store.settings['demo_examples'] = [
            dict(id='old', kind='record', job_id='old', input_id='old'),
            dict(id='demo', kind='dataset', package_id='pilot', label='EEG', description='Two participants'),
            dict(id='duplicate', kind='dataset', package_id='pilot')]
        data = library(self.store)
        self.assertEqual(data['examples'], [])  # Not published; no request-time generation.
        demo = featured_reports(self.store)[0]
        self.assertTrue(demo['available'])
        self.assertEqual(demo['reported'], 0)
        self.assertEqual(demo['status'], 'not_run')
        self.assertEqual(demo['url'], '/api/v1/packages/pilot/overview/report')
        self.assertNotIn('score', demo)
        self.assertFalse(any(r['id'] == 'dataset:pilot' for r in data['items']))
        self.assertEqual(data['counts']['datasets'], 0)

    def test_dataset_navigation_streams_execution_only_and_invalidates_saved_cache(self):
        self.save_signal()
        path = self.store.root / 'jobs' / ('a' * 32) / 'result.json'
        value = dict(signal()['result'], schema_version='ephys-recording-result/1.0',
                     candidate_index=[{'evidence': 'x' * 1000}] * 1000)
        path.write_text(json.dumps(value))
        result = self.store.dataset_result('a' * 32)
        self.assertEqual(result['coverage']['total_seconds'], 10)
        self.assertNotIn('candidate_index', result)
        self.assertNotIn('report_view', result)
        self.store.dataset_summaries.clear()
        with patch('dataset_overview.read_signal_summary', side_effect=AssertionError('must use valid disk cache')):
            self.assertEqual(self.store.dataset_result('a' * 32), result)
        value['coverage']['completed_seconds'] = 9
        path.write_text(json.dumps(value))
        self.assertEqual(self.store.dataset_result('a' * 32)['coverage']['completed_seconds'], 9)
        path.write_text('{"scope":"recording",')
        with self.assertRaises(ValueError): self.store.dataset_result('a' * 32)

    def test_example_coverage_uses_current_manifest_and_latest_attempt(self):
        self.store.settings['demo_examples'] = [dict(id='demo', kind='dataset', package_id='pilot')]
        self.save_dataset(); self.save_signal()
        with patch.object(self.store, 'dataset_result', return_value=signal()['result']):
            self.assertEqual(featured_reports(self.store)[0]['reported'], 1)
            report = render_overview(build_overview(self.store, 'pilot'))
            self.assertIn('/api/v1/jobs/', report)
            self.assertNotIn('88.51', report)
            self.assertNotIn('EEG 分数 / 分项', report)
            self.plan['scope'] = 'new selection'
            self.config.write_text(json.dumps(self.plan))
            self.assertEqual(featured_reports(self.store)[0]['reported'], 0)
        with patch.object(self.store.packages, 'catalog', return_value={'packages': [dict(id='pilot', available=False)]}):
            row = featured_reports(self.store)[0]
            self.assertFalse(row['available'])
            self.assertEqual(row['status'], 'unavailable')

    def test_library_latest_revision_no_duplicate_linked_inputs_or_paths(self):
        self.save_dataset();self.save_signal()
        self.store.packages.packages['pilot']['library_origin'] = 'user_upload'
        self.store.inputs['old']=dict(id='old',label='old',record_family='f',record_revision=1,library_origin='user_upload')
        self.store.inputs['new']=dict(id='new',label='new',record_family='f',record_revision=2,library_origin='user_upload')
        self.store.jobs['old-run']=dict(id='old-run',status='completed',input_id='old',created_at='2026-11-01')
        with patch.object(self.store.intakes,'pending',return_value=[dict(id='pending',filename='p.edf',received_at='2026-11-07',library_origin='user_upload')]):
            data=library(self.store)
        self.assertEqual(data['counts'],dict(datasets=1,records=2))
        row=next(r for r in data['items'] if r['id']=='record:new')
        self.assertEqual(row['status'],'not_run');self.assertIsNone(row['latest_run_url'])
        self.assertNotIn('source_path',json.dumps(data));self.assertNotIn(str(self.root),json.dumps(data))

    def test_library_separates_only_explicit_validation_cases(self):
        self.store.packages.packages['pilot']['library_origin'] = 'user_upload'
        self.store.settings['validation_library_ids'] = ['dataset:pilot']
        self.store.inputs['ordinary'] = dict(id='ordinary', label='New upload', library_origin='user_upload')
        self.store.jobs['failed'] = dict(id='failed', input_id='ordinary', status='failed', created_at='2026-11-06')
        data = library(self.store)
        self.assertEqual(next(r for r in data['items'] if r['id']=='dataset:pilot')['category'], 'validation')
        self.assertEqual(next(r for r in data['items'] if r['id']=='record:ordinary')['category'], 'data')
        self.assertEqual(data['examples'], [])

    def test_legacy_single_report_is_not_a_dataset_example(self):
        item = self.save_signal()
        self.store.settings['demo_examples'] = [dict(kind='record', id='demo', label='Demo',
                                                    job_id='a'*32, input_id=item['id'])]
        self.assertEqual(library(self.store)['examples'], [])

    def test_example_directory_does_not_read_signal_results_or_claim_missing_reports(self):
        self.save_dataset();self.save_signal()
        self.store.settings['demo_examples']=[dict(kind='dataset',package_id='pilot')]
        with patch('dataset_overview.build_overview',side_effect=AssertionError('directory must not aggregate reports')):
            self.assertEqual(featured_reports(self.store)[0]['reported'],1)
            (self.store.root/'jobs'/('a'*32)/'artifacts/report.html').unlink()
            self.assertEqual(featured_reports(self.store)[0]['reported'],0)

    def test_featured_dataset_keeps_issues_and_uses_latest_attempt(self):
        self.save_dataset(); self.save_signal()
        self.store.settings['demo_examples'] = [dict(kind='dataset', id='demo', label='Demo', package_id='pilot')]
        with patch.object(self.store, 'dataset_result', return_value=signal()['result']):
            row = featured_reports(self.store)[0]
            self.assertEqual(row['reported'], 1)
            self.assertEqual(row['records'], 4)
        self.save_signal('b'*32, 'failed', '2026-11-07')
        row = featured_reports(self.store)[0]
        self.assertTrue(row['available'])
        self.assertEqual(row['reported'], 0)

    def test_empty_personal_library_does_not_delete_legacy_or_linked_data(self):
        self.save_dataset(); self.save_signal()
        self.store.inputs['legacy'] = dict(id='legacy', label='Development recording')
        data = library(self.store)
        self.assertEqual(data['items'], [])
        self.assertIn('legacy', self.store.inputs)
        self.assertIn('pilot', self.store.packages.packages)
        self.store.inputs['fresh'] = dict(id='fresh', label='My upload', library_origin='user_upload')
        self.assertEqual([r['id'] for r in library(self.store)['items']], ['record:fresh'])

    def test_missing_metadata_is_collapsed_without_becoming_a_pass(self):
        data = aggregate_overview(self.plan, dataset_result=evaluate_dataset(self.root, self.plan))
        data.update(package_id='pilot', label='Pilot', generated_at='now', manifest_hash='hash')
        data['findings'].append(dict(id='unknown', module='D02', code='extra', status='unassessed', label='Extra metadata', message='Missing auxiliary table'))
        html = render_overview(data)
        before, after = html.split('<details class="disclosure">', 1)
        self.assertNotIn('Missing auxiliary table', before)
        self.assertIn('Missing auxiliary table', after)
        self.assertNotIn('尚无法判断', before)

    def test_personal_record_groups_completed_reports_without_moving_evidence(self):
        item=dict(id='personal',label='My EEG',library_origin='user_registered',
                  report_labels={'a'*32:{'zh-CN':'推荐方案','en':'Recommended workflow'},
                                 'b'*32:{'zh-CN':'灵犀云方案','en':'Gnosis workflow'}})
        self.store.inputs[item['id']]=item
        for i,key in enumerate(['a','b','c']):
            jid=key*32
            self.store.jobs[jid]=dict(id=jid,input_id=item['id'],status='completed',created_at=f'2026-11-0{i+1}')
            if key!='c':
                path=self.store.root/'jobs'/jid/'artifacts'/'report.html'
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text('saved report')
        rows=library(self.store)['items']
        row=next(r for r in rows if r['id']=='record:personal')
        self.assertEqual([r['label'] for r in row['recent_reports']],['灵犀云方案','推荐方案'])
        self.assertEqual(row['recent_reports'][0]['visualizations_url'],'/api/v1/jobs/'+'b'*32+'/visualizations')
        self.assertTrue(all(r['url'].startswith('/api/v1/jobs/') for r in row['recent_reports']))
        self.assertEqual((self.store.root/'jobs'/('a'*32)/'artifacts/report.html').read_text(),'saved report')
        # A corrected Gnosis run should replace Gnosis, not hide the comparison.
        item['report_labels']['d'*32]=item['report_labels']['b'*32]
        self.store.jobs['d'*32]=dict(id='d'*32,input_id=item['id'],status='completed',created_at='2026-11-07')
        path=self.store.root/'jobs'/('d'*32)/'artifacts/report.html'
        path.parent.mkdir(parents=True);path.write_text('new report')
        updated=next(r for r in library(self.store)['items'] if r['id']=='record:personal')
        self.assertEqual([r['job_id'] for r in updated['recent_reports']],['d'*32,'a'*32])
        # A revised confirmation must not inherit the previous revision's reports.
        item.update(record_family='family',record_revision=1)
        self.store.inputs['revised']=dict(item,id='revised',record_revision=2)
        rows=library(self.store)['items']
        self.assertFalse(any(r['id']=='record:personal' for r in rows))
        self.assertEqual(next(r for r in rows if r['id']=='record:revised')['recent_reports'],[])

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
            self.assertIn(b'Dataset report',body)
            self.assertEqual(get('/api/v1/packages/pilot/overview?job=invalid')[0],400)
            self.assertEqual(get('/api/v1/packages/pilot/overview?path=/tmp')[0],400)
            self.assertEqual(get('/api/v1/data',{'Origin':'https://other.test'})[0],403)
        finally:
            server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
