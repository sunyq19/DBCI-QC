"""A frozen comparison needs two completed runs and no live-runtime links."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]
spec=importlib.util.spec_from_file_location('publish_example_cache',REPO/'scripts/publish_example_cache.py')
publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)


class ComparisonPublicationTests(unittest.TestCase):
    def setUp(self):
        self.ids=['a'*32,'b'*32]
        self.comparison={'id':'eeg-workflows','label':'EEG 方案对照','label_en':'EEG comparison',
                         'description':'相同输入的检查方案','description_en':'Same input, two workflows',
                         'input_id':'public-eeg','window':'w000001--','limit':64,
                         'variants':[{'job_id':j,'label':f'方案 {i+1}','description':'检查与图表',
                                      'visualizations':['psd']} for i,j in enumerate(self.ids)]}
        self.example={'package_id':'public-dataset','label':'EEG','formats':'EDF','description':'公开样例',
                      'subjects':1,'records':1,'reported':1}
        self.overview={'records':[{'modality':'scalp_eeg'}],'source':{}}
        self.view={'label':'public-eeg','source_sha256':'identical-source','scope':'recording',
                   'recording':{'start_seconds':0.0,'duration_seconds':240.0,'channel_count':2,
                                'sampling_rate_hz':250.,'source_indices':[0,1]},
                   'score':{'value':90.,'components':[{'id':'integrity','name':'完整性','weight':1,'value':90.}]},
                   'window_scores':[{'id':'w000001','start_seconds':0.,'duration_seconds':120.}],
                   'artifacts':[]}

    def store(self,root,status='completed'):
        return SimpleNamespace(settings={'demo_comparisons':[self.comparison]},root=root,
            inputs={'public-eeg':{'provenance':{'name':'Public EEG','url':'https://example.org/data','license':'CC0'}}},
            job=lambda j:{'status':status,'input_id':'public-eeg','created_at':'2026-11-11T00:00:00Z',
                          'plan': {'input_modality': {'value': getattr(self, 'interactive_mode', None)}}},workspace=lambda j:None)

    def test_incomplete_run_does_not_replace_published_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'cache';out.mkdir();(out/'manifest.json').write_text('existing release')
            with patch.object(publisher,'snapshot',return_value=self.store(root,'running')), \
                 patch('data_library.featured_reports',return_value=[self.example]), \
                 patch('dataset_overview.build_overview',return_value=self.overview):
                with self.assertRaisesRegex(ValueError,'not complete'):
                    publisher.publish(root/'config.json',out)
            self.assertEqual((out/'manifest.json').read_text(),'existing release')

    def test_missing_overall_score_keeps_coverage_note_instead_of_zero(self):
        view=copy.deepcopy(self.view);view['score']['value']=None
        self.comparison['variants'][1]['result_note']='末段不满足频谱条件，已完成分项保留。'
        html=publisher.comparison_page(self.comparison,[self.view,view],{},'zh-CN')
        self.assertIn('整份总分未汇总',html)
        self.assertIn('末段不满足频谱条件，已完成分项保留',html)
        self.assertNotIn('0.00 / 100',html.replace('90.00 / 100',''))

    def test_snapshot_freezes_charts_pdf_and_evidence_without_runtime_links(self):
        def report(store,jid,language,*,interactive=True):
            self.assertEqual(interactive, bool(getattr(self, 'interactive_mode', None)))
            base=f'/api/v1/jobs/{jid}'
            return f'<html><head></head><body><nav class="saved-report-nav"></nav><div data-waveform-base="{base}"></div><iframe data-chart-src="{base}/visualizations?embedded=1"></iframe><a href="{base}/visualizations">Charts</a><a href="{base}/report.pdf">PDF</a><img src="{base}/report-evidence.png"></body></html>'
        def gallery(*args,**kwargs):
            return f'<html><head><script src="/visualizations.js" defer></script></head><body><form><button>Recompute</button></form><p>原记录 0–120 秒，非整份汇总</p><svg></svg><a href="{kwargs["back_url"]}">Report</a></body></html>'
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);out=root/'cache'
            with patch.object(publisher,'snapshot',return_value=self.store(root)), \
                 patch('data_library.featured_reports',return_value=[self.example]), \
                 patch('dataset_overview.build_overview',return_value=self.overview), \
                 patch('dataset_overview.render_overview',return_value='<html><body><main>Dataset</main></body></html>'), \
                 patch('saved_reports.served_report',side_effect=report), \
                 patch('saved_reports.frozen_view',side_effect=lambda *a:copy.deepcopy(self.view)) as frozen, \
                 patch('project_score_cache.load',return_value=None), \
                 patch('example_review.snapshot',return_value={'findings':{'findings':[], 'default_method_ids':[]}, 'source':{'source_sha256':'a'*64}}), \
                 patch('ephys_qc.report_export.evidence_figure',return_value=(b'PNG',[])), \
                 patch('ephys_qc.report_export.pdf_bytes',return_value=b'%PDF-fixture'), \
                 patch('ephys_qc.visualizations.render.render_gallery',side_effect=gallery):
                publisher.publish(root/'config.json',out)
            frozen.assert_any_call(unittest.mock.ANY,self.ids[0])
            data=json.loads((out/'manifest.json').read_text());release=out/data['release']
            self.assertEqual(len(data['examples']),1)
            self.assertEqual(len(data['comparisons']),1)
            self.assertNotIn('variants',data['comparisons'][0])
            from example_cache import homepage
            html=homepage(SimpleNamespace(settings={'example_cache_dir':str(out)}),(REPO/'apps/workbench/web/index.html').read_text())
            self.assertEqual(html.count('class="demo-report"'),1)
            self.assertNotIn('example-comparison-link',html)
            for jid in self.ids:
                if getattr(self, 'interactive_mode', None):
                    self.assertIn(jid, data['review_snapshots'])
                    self.assertTrue((release/f'review/{jid}.json').is_file())
                    self.assertIn('/api/v1/examples/'+data['release']+'/records/'+jid,
                                  (release/f'records/{jid}.zh-CN.html').read_text())
                self.assertEqual((release/f'records/{jid}.pdf').read_bytes(),b'%PDF-fixture')
                self.assertIn(data['comparisons'][0]['url'],(release/f'records/{jid}.zh-CN.html').read_text())
                self.assertEqual((release/f'records/{jid}.evidence.png').read_bytes(),b'PNG')
                graph=(release/f'visualizations/{jid}.zh-CN.html').read_text()
                self.assertNotIn('<form',graph);self.assertIn('0–120 秒',graph)
                self.assertTrue((release/f'visualizations/{jid}.embedded.zh-CN.html').is_file())
                self.assertIn(f'/visualizations/{jid}.embedded.zh-CN.html', (release/f'records/{jid}.zh-CN.html').read_text())
            for path in release.rglob('*.html'):
                text=path.read_text()
                self.assertNotIn('/api/v1/jobs/',text)
                if not getattr(self, 'interactive_mode', None):
                    self.assertNotIn('data-waveform-base',text)
                self.assertNotIn('/examples/RELEASE/',text)
            self.assertTrue((release/'assets/visualizations.js').is_file())
            if not getattr(self, 'interactive_mode', None):
                self.assertFalse(list(release.rglob('*.json')))

    def test_intracranial_and_neuropixels_keep_frozen_waveform_routes(self):
        for mode in ('ecog', 'seeg', 'extracellular'):
            with self.subTest(mode=mode):
                self.interactive_mode = mode
                self.test_snapshot_freezes_charts_pdf_and_evidence_without_runtime_links()


if __name__=='__main__':unittest.main()
