import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'apps/workbench')]
from ephys_qc.dataset_qc.review import build_case, apply_changes, retest_delta, evidence_id
from ephys_qc.dataset_qc.review_report import render_review_report
from package_reviews import PackageReviews, ReviewConflict


def fixture():
    m = {'consistency': {'groups': [{'same_rates': True}]}, 'items': [], 'recordings': []}
    c = {'id': 'c1', 'module': 'D02', 'code': 'rates', 'label': '采样率', 'label_en': 'Rates',
         'status': 'conflict', 'target': 'r1', 'message': '不同', 'records': ['r1'], 'files': ['channels.tsv'], 'observed': {'rate': 500}}
    r = {'rule_version': 'test/1', 'scope': 'one record', 'checked_at': '2026-11-06', 'checks': [c],
         'inventory': {'files': [{'path': 'channels.tsv', 'status': 'present', 'sha256': 'old', 'size_bytes': 10}]},
         'records': [{'id': 'r1', 'path': 'signal.edf'}], 'summary': {'records': 1}}
    return r,m


def body(case, disposition='needs_fix', finalize=False):
    r=case['rows'][0]
    return {'expected_revision':case['revision'],'result_hash':case['result_hash'],'reviewer':'Example reviewer',
            'finalize':finalize,'purpose':'engineering test only','changes':[{'check_id':r['id'],'evidence_id':r['evidence_id'],
            'disposition':disposition,'note':'Check the original metadata','impact':'Timing analyses','action':'Restore source table','owner':'Demo owner'}]}


class DatasetReviewTests(unittest.TestCase):
    def test_no_automatic_acceptance(self):
        r,m=fixture();r['checks']=[]
        c=build_case(r,m)
        self.assertEqual(c['proposed_outcome'],'accepted');self.assertEqual(c['outcome'],'pending_review')

    def test_decisions_do_not_change_machine_results_and_edit_clears_final(self):
        r,m=fixture();original=copy.deepcopy(r);c=build_case(r,m)
        saved=apply_changes(c,{},body(c,finalize=True),'time')
        c=build_case(r,m,saved);self.assertEqual(c['outcome'],'blocked');self.assertEqual(r,original)
        next_saved=apply_changes(c,saved,body(c,'follow_up'),'later')
        self.assertIsNone(next_saved['final'])

    def test_unknown_cannot_be_signed_as_pass_without_decision(self):
        r,m=fixture();r['checks'][0]['status']='unassessed';c=build_case(r,m)
        b=body(c);b.update(changes=[],finalize=True)
        with self.assertRaisesRegex(ValueError,'未处理'):apply_changes(c,{},b,'time')

    def test_required_reason_use_owner_and_evidence(self):
        r,m=fixture();c=build_case(r,m)
        for field in ('note','impact','owner','action','evidence_id'):
            b=body(c);b['changes'][0][field]=''
            with self.assertRaises(ValueError):apply_changes(c,{},b,'time')
        b=body(c);b['changes']*=2
        with self.assertRaises(ValueError):apply_changes(c,{},b,'time')

    def test_changed_file_invalidates_carried_decision(self):
        r,m=fixture();c=build_case(r,m);saved=apply_changes(c,{},body(c),'time')
        self.assertEqual(build_case(r,m,inherited=saved['decisions'])['summary']['reviewed'],1)
        r['inventory']['files'][0]['sha256']='new'
        self.assertEqual(build_case(r,m,inherited=saved['decisions'])['summary']['pending'],1)

    def test_retest_requires_pass_same_rules_and_same_scope(self):
        a,m=fixture();b=copy.deepcopy(a);b['checks'][0]['status']='pass'
        self.assertEqual(retest_delta(a,b,m,m)['counts'],{'resolved':1})
        b['checks']=[];self.assertEqual(retest_delta(a,b,m,m)['counts'],{'not_rechecked':1})
        b=copy.deepcopy(a);b['checks'][0]['status']='not_applicable'
        self.assertEqual(retest_delta(a,b,m,m)['counts'],{'not_rechecked':1})
        b['checks'][0]['status']='pass';b['rule_version']='test/2'
        self.assertEqual(retest_delta(a,b,m,m)['counts'],{'scope_changed':1})
        b['rule_version']='test/1';n=copy.deepcopy(m);n['consistency']['groups'][0]['same_rates']=False
        self.assertEqual(retest_delta(a,b,m,n)['counts'],{'scope_changed':1})

    def test_new_and_changed_findings(self):
        a,m=fixture();b=copy.deepcopy(a);b['checks'][0]['observed']['rate']=256
        self.assertEqual(retest_delta(a,b,m,m)['counts'],{'changed':1})
        a['checks'][0]['status']='pass'
        self.assertEqual(retest_delta(a,b,m,m)['counts'],{'new':1})

    def test_report_escapes_user_text_and_marks_demo(self):
        r,m=fixture();c=build_case(r,m);c.update(job_id='a'*32,label='<script>alert(1)</script>',checked_at='now',engineering_demo=True)
        for language in ('zh-CN','en'):
            h=render_review_report(c,language)
            self.assertNotIn('<script>',h);self.assertIn('&lt;script&gt;',h)
            self.assertIn('工程演示' if language=='zh-CN' else 'Engineering demo',h)


class ReviewStorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.packages=Mock();self.packages.root=self.root
        self.packages.packages={'p': {'engineering_demo':True}}
        self.jobs={};self.packages.get.side_effect=lambda i:copy.deepcopy(self.jobs[i])
        self.packages.artifact.side_effect=lambda i,n:self.root/i/'result'/n
        self.reviews=PackageReviews(self.packages)

    def job(self,identifier,baseline=None,revision=0):
        r,m=fixture();p=self.root/identifier/'result';p.mkdir(parents=True)
        (p/'result.json').write_text(json.dumps(r));(p/'expectations.json').write_text(json.dumps(m))
        self.jobs[identifier]={'id':identifier,'package_id':'p','label':'Demo','status':'completed'}
        if baseline:self.jobs[identifier].update(baseline_job_id=baseline,baseline_review_revision=revision)

    def test_append_only_stale_edits_and_restart(self):
        i='a'*32;self.job(i);c=self.reviews.get(i);b=body(c)
        self.reviews.save(i,b)
        first=(self.root/i/'reviews/00000001.json').read_bytes()
        with self.assertRaises(ReviewConflict):self.reviews.save(i,b)
        c=self.reviews.get(i);self.reviews.save(i,body(c,'follow_up'))
        self.assertEqual((self.root/i/'reviews/00000001.json').read_bytes(),first)
        self.assertEqual(PackageReviews(self.packages).get(i)['revision'],2)

    def test_retest_inherits_only_frozen_baseline_revision(self):
        a,b='a'*32,'b'*32;self.job(a);self.reviews.save(a,body(self.reviews.get(a)))
        self.job(b,a,1)
        self.reviews.save(a,body(self.reviews.get(a),'acceptable_difference'))
        c=self.reviews.get(b);self.assertEqual(c['rows'][0]['disposition'],'needs_fix');self.assertIsNone(c['final'])

    def test_no_path_escape_or_cross_package_retest(self):
        with self.assertRaises(ValueError):self.reviews.get('../private')
        a,b='a'*32,'b'*32;self.job(a);self.job(b,a);self.jobs[b]['package_id']='other'
        with self.assertRaisesRegex(ValueError,'不属于'):self.reviews.get(b)

    def test_http_adapter_exports_and_rejects_stale_edits(self):
        from package_review_api import dispatch
        i='a'*32;self.job(i);h=Mock();h.store.package_reviews=self.reviews
        route='/api/v1/package-jobs/'+i+'/review'
        h.command='GET';h.path=route
        self.assertTrue(dispatch(h,route));self.assertEqual(h.json.call_args.args[0]['revision'],0)
        h.command='POST';h.body.return_value=body(self.reviews.get(i));dispatch(h,route)
        self.assertEqual(h.json.call_args.args[1],201)
        dispatch(h,route);self.assertEqual(h.json.call_args.args[1],409)
        h.command='GET';h.path=route+'/report?lang=en';dispatch(h,route+'/report')
        self.assertIn(b'Dataset review and retest report',h.send_bytes.call_args.args[0])
        h.path=route+'/pdf';dispatch(h,route+'/pdf')
        self.assertTrue(h.send_bytes.call_args.args[0].startswith(b'%PDF-'))
        self.assertEqual(h.send_bytes.call_args.args[1],'application/pdf')
        h.path=route+'?lang=unsupported'
        with self.assertRaises(ValueError):dispatch(h,route)


if __name__=='__main__':unittest.main()
