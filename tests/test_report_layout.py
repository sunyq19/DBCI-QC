"""Structural report checks. These do not constitute browser visual acceptance."""
import json
from html.parser import HTMLParser
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from descriptive_report import render


class ReportStructure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.tables = []
        self.ids = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get('id'):
            self.ids.append(values['id'])
        if tag == 'table':
            self.tables.append(list(self.stack))
        if tag == 'script':
            self.scripts.append(values.get('src'))
        if tag not in {'meta', 'link', 'img', 'br', 'hr', 'input'}:
            self.stack.append((tag, values))

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


class DescriptiveReportLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.identifier = 'a'*32
        self.job = self.root/'jobs'/self.identifier
        self.artifacts = self.job/'artifacts'
        self.artifacts.mkdir(parents=True)
        self.label = 'very-long-recording-'*12 + '<script>private-label</script>'
        (self.job/'request.json').write_text(json.dumps({'input':{'label':self.label, 'modality':'seeg'}}))
        windows = [{'id':'w000001', 'start_seconds':0, 'duration_seconds':30,
                    'status':'completed', 'modules':[{'id':'M05','summary':{'described_channel_count':2}}]}]
        (self.artifacts/'window-results.json').write_text(json.dumps(windows))
        (self.artifacts/'coverage.json').write_text(json.dumps({'completed_seconds':30,'unexecuted_seconds':0,'gap_seconds':0}))
        (self.artifacts/'w000001--M05_channel_description.json').write_text(json.dumps({'channels':[
            {'channel_name':'A1', 'rms_volts':.0001,'peak_to_peak_volts':.0004}]}))
        self.store = SimpleNamespace(root=self.root, job=lambda identifier: {'id':identifier})
        self.display = {'channels':2,'rates_hz':[1000],'duration_seconds':30,
                        'nonfinite_samples':0,'psd_channels':2}

    def page(self, language='zh-CN'):
        with patch('dataset_overview.recording_display', return_value=self.display):
            return render(self.store,self.identifier,language)

    def test_all_native_tables_have_keyboard_scroll_regions(self):
        for language in ['zh-CN','en']:
            parsed = ReportStructure(); parsed.feed(self.page(language))
            self.assertEqual(len(parsed.tables),3)
            for ancestors in parsed.tables:
                wrappers = [a for tag,a in ancestors if tag=='div' and 'table-scroll' in a.get('class','').split()]
                self.assertTrue(wrappers)
                self.assertEqual(wrappers[-1]['tabindex'],'0')
                self.assertEqual(wrappers[-1]['role'],'region')
                self.assertTrue(wrappers[-1]['aria-label'])

    def test_optional_scoring_table_is_contained_and_values_preserved(self):
        score = {'value':88.25, 'formula':'weighted mean', 'version':'project-weighted/1.1',
                 'configuration_id':'example', 'components':[{'name':'FieldTrip','value':88.25,'weight':2,'reason':'native candidate count'}]}
        (self.artifacts/'method-scores.json').write_text(json.dumps({'project_score':score}))
        html = self.page(); parsed = ReportStructure(); parsed.feed(html)
        self.assertEqual(len(parsed.tables),4)
        self.assertIn('88.25',html)
        self.assertIn('native candidate count',html)
        for ancestors in parsed.tables:
            self.assertTrue(any(tag=='div' and 'table-scroll' in attrs.get('class','').split() for tag,attrs in ancestors))

    def test_long_untrusted_labels_remain_text_and_controls_unique(self):
        html = self.page(); parsed = ReportStructure(); parsed.feed(html)
        self.assertEqual(parsed.scripts,['/dataset-report.js'])
        self.assertNotIn('<script>private-label</script>',html)
        self.assertIn('&lt;script&gt;private-label&lt;/script&gt;',html)
        self.assertEqual(len(parsed.ids),len(set(parsed.ids)))


class DatasetReportLayoutTests(unittest.TestCase):
    def test_all_four_dataset_tables_have_named_keyboard_scroll_regions(self):
        from dataset_report import render as render_dataset
        check = dict(module='D02', code='channels', label='通道表', label_en='Channel table',
                     status='unassessed', target='record-01', message='Companion table absent')
        data = dict(package_id='sample', label='Sample dataset',
                    summary=dict(dataset_assessed=False, subjects=0, reported=0, expected_files=1),
                    records=[], module_counts={}, findings=[check], checks=[check],
                    comparison_groups=[], scope='declared records', manifest_hash='test-manifest')
        expected = {'zh-CN':{'未核对资料','检查结果','逐份结果','检查记录'},
                    'en':{'Unassessed metadata','Check results','Recording results','Audit trail'}}
        for language in ['zh-CN','en']:
            parsed = ReportStructure(); parsed.feed(render_dataset(data,language))
            self.assertEqual(len(parsed.tables),4)
            labels = set()
            for ancestors in parsed.tables:
                wrappers = [a for tag,a in ancestors if tag=='div' and 'table-scroll' in a.get('class','').split()]
                self.assertTrue(wrappers)
                self.assertEqual(wrappers[-1]['tabindex'],'0')
                self.assertEqual(wrappers[-1]['role'],'region')
                labels.add(wrappers[-1]['aria-label'])
            self.assertEqual(labels,expected[language])


if __name__ == '__main__':
    unittest.main()
