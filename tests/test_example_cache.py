"""Published examples must not depend on runtime jobs, NAS or first-request work."""
import hashlib,json,re,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit, unquote
REPO=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]
from example_cache import manifest,homepage,asset,DEFAULT_ROOT
from server import Handler


class ExampleCacheTests(unittest.TestCase):
    def test_seeg_and_probe_examples_use_current_scoring_and_saved_findings(self):
        from ephys_qc.ieeg_scoring import default_config as ieeg_config
        from ephys_qc.neuropixels_scoring import default_config as probe_config
        store=SimpleNamespace(settings={});data=manifest(store)
        expected={'seeg':ieeg_config('seeg')['preset'],
                  'extracellular':probe_config()['preset']}
        counts={'seeg':0,'extracellular':0}
        for jid,score in data['report_scores'].items():
            mode=score['modality']
            if mode not in expected:continue
            counts[mode]+=1
            self.assertEqual(score['preset'],expected[mode])
            self.assertIsInstance(score['value'],(float,int))
            active=[c for c in score['components'] if c['weight'] and c['weight']>0]
            self.assertGreater(len(active),1)
            self.assertAlmostEqual(score['value'],sum(c['value']*c['weight'] for c in active)/sum(c['weight'] for c in active))
            html=asset(store,f'/examples/{data["release"]}/records/{jid}.zh-CN.html').read_text()
            self.assertIn(f'{score["value"]:.2f}',html)
            self.assertNotIn('data-location-inspector',html)
            example=next(e for e in data['examples'] if e['modality']==mode and
                         f'/records/{jid}.' in asset(store,e['url']).read_text())
            overview=asset(store,example['url']).read_text()
            self.assertIn(f'本方案评分 {score["value"]:.2f} / 100',overview)
            self.assertNotIn('当前提供技术描述',overview)
        self.assertEqual(counts,{'seeg':2,'extracellular':5})

    def test_shipped_snapshot_hashes_and_links_are_self_contained(self):
        store=SimpleNamespace(settings={})
        data=manifest(store)
        self.assertEqual(len(data['examples']),8)
        self.assertEqual(sum(r['reported'] for r in data['examples']),21)
        self.assertFalse(data['raw_data_included'])
        for name,digest in data['files'].items():
            path=asset(store,'/examples/'+data['release']+'/'+name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            self.assertIn(path.suffix,{'.html','.css','.js','.png','.svg','.pdf','.json'})
            if path.suffix=='.json':
                self.assertTrue(name.startswith('review/'))
                self.assertNotRegex(path.read_text(),r'/(?:home|media|tmp|mnt)/')
            if path.suffix=='.html':
                text=path.read_text()
                self.assertNotRegex(text,r'/(?:home|media|tmp)/')
                for url in re.findall(r'(?:data-chart-src|src|href)=["\']([^"\']+)',text):
                    if url.startswith('/examples/'):
                        parsed=urlsplit(url);target=asset(store,parsed.path)
                        self.assertTrue(target.is_file(),url)
                        if parsed.fragment and target.suffix=='.html':
                            self.assertTrue(re.search(r'id=["\']'+re.escape(unquote(parsed.fragment))+r'["\']',target.read_text()),url)
                    elif url.startswith('/'):self.assertTrue(urlsplit(url).path=='/' or url.startswith('/standards'),url)
                    if url.startswith('#'):
                        self.assertNotEqual(url,'#snapshot-info','Unavailable evidence must not pretend to be a working link')
                        self.assertTrue(re.search(r'id=["\']'+re.escape(unquote(url[1:]))+r'["\']',text),url)
        self.assertEqual({r['modality'] for r in data['examples']},{'scalp_eeg','ecog','seeg','extracellular'})

    def test_all_modalities_freeze_current_location_viewer_and_all_saved_candidates(self):
        store=SimpleNamespace(settings={});data=manifest(store)
        expected=set(data['report_scores'])
        self.assertEqual(set(data['review_snapshots']),expected)
        for jid in expected:
            saved=json.loads(asset(store,f'/examples/{data["release"]}/review/{jid}.json').read_text())
            findings=saved['findings'];found={f['method'] for f in findings['findings']}
            self.assertEqual(set(findings['default_method_ids']),found)
            self.assertEqual(findings['selection_policy'],'all_saved_candidates')
            self.assertEqual(len(findings['findings']),data['review_snapshots'][jid]['finding_count'])
            for language in ['zh-CN','en']:
                html=asset(store,f'/examples/{data["release"]}/records/{jid}.{language}.html').read_text()
                self.assertIn(f'data-waveform-base="/api/v1/examples/{data["release"]}/records/{jid}"',html)
                self.assertIn('id="finding-filters"',html)
                self.assertIn('id="finding-fullscreen"',html)

    def test_html_contains_examples_before_javascript_or_personal_directory(self):
        store=SimpleNamespace(settings={},root=Path('/nonexistent-runtime'))
        template=(REPO/'apps/workbench/web/index.html').read_text()
        with patch('data_library.featured_reports',side_effect=AssertionError('no runtime scan')):
            html=homepage(store,template)
        self.assertEqual(html.count('class="demo-report"'),8)
        self.assertIn('<span id="demo-reports-count" class="tag subtle rail-count">8</span>',html)
        self.assertIn('id="example-cache" type="application/json"',html)
        self.assertNotIn('正在读取示例目录',html)
        self.assertNotIn('href="#demo-reports" hidden',html)
        self.assertNotIn('example-comparison-link',html)
        self.assertNotIn('comparison-en',html)
        self.assertNotIn('Same data · Two workflows',html)
        self.assertNotIn('EEG 方案对照',html)
        self.assertNotIn('example-shortcut',html)

    def test_cache_absence_has_immediate_empty_state_not_computation(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SimpleNamespace(settings={'example_cache_dir':directory})
            self.assertEqual(manifest(store)['examples'],[])
            html=homepage(store,(REPO/'apps/workbench/web/index.html').read_text())
            self.assertIn('尚未发布示例报告',html)

    def test_path_traversal_cannot_read_pointer_or_runtime(self):
        store=SimpleNamespace(settings={});release=manifest(store)['release']
        for path in ['/examples/'+release+'/../manifest.json','/examples/'+release+'/../../server.py','/examples/../manifest.json']:
            with self.assertRaises(KeyError):asset(store,path)

    def test_handler_serves_immutable_cache_with_no_store_services(self):
        store=SimpleNamespace(settings={});row=manifest(store)['examples'][0]
        handler=Handler.__new__(Handler);handler.server=SimpleNamespace(store=store);handler.path=row['url'];handler.send_bytes=lambda data,mime='x',code=200,headers=None:(data,mime,headers)
        result=handler.get(row['url'])
        self.assertIn('text/html',result[1]);self.assertIn('immutable',result[2]['Cache-Control'])
        handler.path='/';data,mime,headers=handler.get('/')
        self.assertEqual(data.count(b'class="demo-report"'),8)

if __name__=='__main__':unittest.main()
