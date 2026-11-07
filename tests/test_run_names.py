"""Run titles follow saved runs without affecting data identity or QC plans."""
import json
from pathlib import Path
import queue
import sys
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from ephys_qc.run_names import resolve_run_name
from ephys_qc.planning import build_plan
from server import Store
from package_jobs import PackageJobs, fingerprint
from test_whole_record import record, config


class RunNameTests(unittest.TestCase):
    def test_defaults_and_validation(self):
        self.assertRegex(resolve_run_name(None, 'sub-01.edf'), r'^sub-01 · 整份检查 · \d{2}-\d{2} \d{2}:\d{2}$')
        self.assertIn('片段检查', resolve_run_name('  ', 'sub-01', 'window'))
        self.assertIn('资料检查', resolve_run_name(None, 'dataset.zip', 'dataset'))
        self.assertEqual(resolve_run_name('  推荐方案 <对照>  ', 'source'), '推荐方案 <对照>')
        self.assertLessEqual(len(resolve_run_name(None, '长'*500)), 120)
        for value in [42, {}, [], '名'*121, 'a\nb', 'a\x00b', 'a\u202eb']:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                resolve_run_name(value, 'source')

    def test_submit_freezes_names_without_renaming_source_or_plan(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store.__new__(Store)
            store.root=Path(folder);(store.root/'jobs').mkdir()
            store.lock=threading.RLock();store.inputs={'whole-fixture':record()}
            store.jobs={};store.queue=queue.Queue();store.admission_policy=None
            body={'input_id':'whole-fixture','selected_modules':['M03'],'qc_config':config()}
            _,plan=store.plan_request(body);body['plan_id']=plan['plan_id']
            first=store.submit(dict(body,run_name='推荐方案'))
            second=store.submit(dict(body,run_name='灵犀云方案'))
            auto=store.submit(body)
            self.assertNotEqual(first['id'],second['id'])
            self.assertEqual(first['plan']['plan_id'],second['plan']['plan_id'])
            self.assertEqual(first['run_name'],'推荐方案')
            self.assertEqual(second['run_name'],'灵犀云方案')
            self.assertIn('整份检查',auto['run_name'])
            self.assertEqual(first['label'],store.inputs['whole-fixture']['label'])
            saved=json.loads((store.root/'jobs'/first['id']/'request.json').read_text())
            self.assertEqual(saved['run_name'],'推荐方案')
            self.assertNotIn('run_name',saved['input'])
            self.assertNotIn('run_name',saved['qc_config'])
            self.assertEqual(json.loads((store.root/'jobs'/second['id']/'job.json').read_text())['run_name'],'灵犀云方案')
            with self.assertRaises(ValueError):store.submit(dict(body,run_name='x'*121))
            self.assertEqual(len(store.jobs),3)

    def test_dataset_titles_are_saved_with_the_check_not_the_dataset(self):
        with tempfile.TemporaryDirectory() as folder:
            packages=PackageJobs.__new__(PackageJobs)
            packages.root=Path(folder);packages.lock=threading.RLock();packages.queue=queue.Queue()
            package={'id':'sample','label':'Example dataset','root':folder};plan={'schema_version':'fixture'}
            packages.packages={'sample':package};packages.jobs={};packages.admission_policy=None
            packages._plan=lambda identifier:(package,plan)
            job=packages.submit({'package_id':'sample','manifest_hash':fingerprint(plan),'confirmed':True,'run_name':'资料一致性 · 首次检查'})
            self.assertEqual(job['run_name'],'资料一致性 · 首次检查')
            self.assertEqual(job['label'],'Example dataset')
            self.assertNotIn('run_name',package)
            self.assertEqual(json.loads((packages.root/job['id']/'request.json').read_text())['run_name'],job['run_name'])

    def test_title_reaches_saved_html_and_pdf(self):
        from test_report_view import ReportViewTests
        from ephys_qc.modules.m09 import render_report
        from ephys_qc.report_export import pdf_bytes
        fixture=ReportViewTests();fixture.setUp()
        try:
            fixture.result['run_name']='灵犀云方案 <对照>'
            render_report(fixture.result,'source.edf',fixture.artifacts/'report.html')
            view=fixture.result['report_view']
            self.assertEqual(view['run_name'],'灵犀云方案 <对照>')
            self.assertEqual(view['label'],'source.edf')
            html=(fixture.artifacts/'report.html').read_text()
            self.assertIn('<h1>灵犀云方案 &lt;对照&gt;</h1>',html)
            self.assertNotIn('<对照>',html)
            pdf=pdf_bytes(view)
            self.assertTrue(pdf.startswith(b'%PDF'))
            import shutil, subprocess
            if not shutil.which('pdftotext'): self.skipTest('PDF text extraction needs Poppler')
            path=fixture.root/'named-report.pdf';path.write_bytes(pdf)
            text=subprocess.check_output(['pdftotext','-enc','UTF-8',str(path),'-'],text=True)
            self.assertIn('灵犀云方案 <对照>',text)
            self.assertIn('source.edf',text)
        finally:fixture.doCleanups()

    def test_real_file_run_keeps_title_for_both_scopes(self):
        from test_readers import fif_fixture, qc_record
        from ephys_qc.readers import inspect_recording
        from ephys_qc.core import run_job
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);path,_=fif_fixture(root)
            source=qc_record(path,inspect_recording(path),[0])
            for scope in ('window','recording'):
                with self.subTest(scope=scope):
                    plan=build_plan(source,['M03'],{'scope':scope})
                    request={'input':source,'plan':plan,'qc_config':plan['qc_config'],
                             'selected_modules':plan['selected_modules'],'run_name':'通路验证 · '+scope}
                    result=run_job(request,root/scope,lambda *args:None)
                    self.assertEqual(result['run_name'],request['run_name'])
                    self.assertEqual(result['report_view']['run_name'],request['run_name'])
                    self.assertIn(request['run_name'],(root/scope/'artifacts/report.html').read_text())

if __name__=='__main__':unittest.main()
