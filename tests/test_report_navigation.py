"""Findings must lead to the corresponding source identity, not generic evidence."""
import copy
import json
import unittest
from unittest.mock import patch
from html.parser import HTMLParser
import test_report_view
from ephys_qc.report_presentation import focus_targets, focused_figure
from ephys_qc.report_view import render_report_view


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(); self.stack=[]; self.text=[]
    def handle_starttag(self,tag,attrs):
        if tag not in {'img','input','meta','link','br','hr'}: self.stack.append(tag)
    def handle_endtag(self,tag):
        if tag in self.stack:
            index=len(self.stack)-1-self.stack[::-1].index(tag);self.stack=self.stack[:index]
    def handle_data(self,data):
        if not {'details','style','script','head'} & set(self.stack): self.text.append(data)


class NavigationTests(unittest.TestCase):
    def setUp(self):
        fixture=test_report_view.ReportViewTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.view=fixture.view()

    def test_priority_targets_keep_real_id_and_interval_without_mutation(self):
        before=copy.deepcopy(self.view)
        rows=focus_targets(self.view)
        self.assertEqual([c['kind'] for c in rows],['line','hf'])
        self.assertEqual(rows[0]['channel_id'],'a')
        self.assertEqual((rows[0]['start_seconds'],rows[0]['stop_seconds']),(0,4))
        with patch('ephys_qc.report_export.evidence_figure',return_value=(b'image',[])) as render:
            focused_figure(self.view,None,1)
            chosen=render.call_args.args[0]
            self.assertEqual(len(chosen['hf_candidates']),1)
            self.assertEqual(chosen['hf_candidates'][0]['start_seconds'],1)
            self.assertEqual(chosen['line_channels'],[])
            self.assertTrue(render.call_args.kwargs['compact'])
        self.assertEqual(self.view,before)
        with self.assertRaises(KeyError):focused_figure(self.view,None,100)

    def test_report_exposes_location_and_hides_technical_details(self):
        self.view['source_sha256']='private-hash-example'
        report=render_report_view(self.view,focus_url=lambda i:f'/report-focus-{i}.png',visualization_url='/charts')
        self.assertIn('href="/report-focus-0.png"',report)
        self.assertIn('id="finding-image"',report)
        self.assertIn('data-chart-src="/charts?embedded=1"',report)
        self.assertIn('data-report-charts',report)
        self.assertNotIn('/charts#viz_timeline',report)
        self.assertIn('src="/report-interactions.js"',report)
        parsed=VisibleText();parsed.feed(report);visible=' '.join(parsed.text)
        self.assertNotIn('private-hash-example',visible)
        self.assertIn('private-hash-example',report)
        self.assertNotIn('本机原文件不变',visible)
        self.assertIn('问题定位',visible)
        self.assertIn('0–4 秒',visible)
        self.assertIn('1–3 秒',visible)
        self.assertNotIn('完整候选列表',visible)
        self.assertNotIn('测量明细与统计单位',visible)
        self.assertIn('完整候选列表',report)
        self.assertIn('测量明细与统计单位',report)
        self.assertNotIn('>查看波形</a>',report)
        self.assertLess(report.index('id="review"'),report.index('id="checks"'))

    def test_no_false_waveform_link_when_identity_or_interval_is_missing(self):
        view=copy.deepcopy(self.view)
        view['hf_candidates'][0]['channel_id']=None
        view['line_channels'][0]['example']['stop_seconds']=None
        self.assertEqual(focus_targets(view),[])

    def test_interactive_waveform_uses_explicit_frozen_identity_and_escaped_attributes(self):
        self.view['hf_candidates'][0]['channel_id']='channel"<unsafe>'
        before=copy.deepcopy(self.view)
        report=render_report_view(self.view,focus_url=lambda i:f'/focus-{i}.png',waveform_url='/api/v1/jobs/example')
        self.assertIn('data-waveform-base="/api/v1/jobs/example"',report)
        self.assertIn('data-channel-id="channel&quot;&lt;unsafe&gt;"',report)
        self.assertIn('data-start="1" data-stop="3"',report)
        self.assertIn('src="/waveform-explorer.js"',report)
        self.assertIn('id="wave-controls" hidden',report)
        self.assertEqual(self.view,before)


if __name__=='__main__':unittest.main()
