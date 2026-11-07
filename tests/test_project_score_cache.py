import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from test_report_view import ReportViewTests
from ephys_qc.project_scoring import VERSION
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/workbench'))
from server import Store
from project_score_cache import publish,load
from saved_reports import served_report


class ScorePublicationTests(unittest.TestCase):
    def test_current_template_reuses_frozen_view_without_recalculating_or_mutating(self):
        fixture=ReportViewTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        view=fixture.view()
        (fixture.job/'result.json').write_text(json.dumps({**fixture.result,'report_view':view}))
        original={p:p.read_bytes() for p in fixture.job.rglob('*') if p.is_file()}
        store=Store.__new__(Store);store.root=fixture.root;store.lock=threading.RLock()
        store.jobs={fixture.jid:{'id':fixture.jid,'status':'completed','label':'Example'}}
        with patch('ephys_qc.report_view.build_report_view',side_effect=AssertionError('must use saved view')):
            page=served_report(store,fixture.jid)
        self.assertIn('检查发现',page)
        self.assertIn('测量明细与统计单位',page)
        self.assertNotIn('测量与扣分原因',page)
        self.assertIn('/visualizations',page)
        for path,content in original.items():self.assertEqual(path.read_bytes(),content)

    def test_frozen_source_retained_cached_api_and_html_agree_and_invalidate(self):
        fixture=ReportViewTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        (fixture.job/'request.json').write_text('{}')
        summary=dict(fixture.result,report_view=fixture.view())
        (fixture.job/'result.json').write_text(json.dumps(fixture.result))
        original={p:p.read_bytes() for p in fixture.job.rglob('*') if p.is_file()}
        conf={'version':VERSION,'weights':{'integrity':1,'line_noise':2,'hf_burst':1}}
        view=publish(fixture.job,summary,conf,published_at='test')
        for path,content in original.items():self.assertEqual(path.read_bytes(),content)
        store=Store.__new__(Store);store.root=fixture.root;store.lock=threading.RLock()
        store.jobs={fixture.jid:{'id':fixture.jid,'status':'completed','label':'Example'}}
        with patch('server.read_json',side_effect=AssertionError('must not parse large result')):
            result=store.result(fixture.jid,compact=True)
        self.assertEqual(result['report_view']['score'],view['score'])
        html=served_report(store,fixture.jid)
        self.assertIn('项目自定义 v1.1',html);self.assertIn('运行时原始报告',html)
        self.assertNotIn('按 v0.2',html);self.assertNotIn('使用均方根',html)
        (fixture.artifacts/'M04_spectral.json').write_text('{}')
        self.assertIsNone(load(store,fixture.jid))
