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
    def test_shipped_snapshot_hashes_and_links_are_self_contained(self):
        store=SimpleNamespace(settings={})
        data=manifest(store)
        self.assertEqual(len(data['examples']),4)
        self.assertEqual(sum(r['reported'] for r in data['examples']),13)
        self.assertFalse(data['raw_data_included'])
        for name,digest in data['files'].items():
            path=asset(store,'/examples/'+data['release']+'/'+name)
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
            self.assertIn(path.suffix,{'.html','.css','.js','.png','.svg','.pdf'})
            if path.suffix=='.html':
                text=path.read_text()
                self.assertNotRegex(text,r'/(?:home|media|tmp)/')
                for url in re.findall(r'(?:src|href)=["\']([^"\']+)',text):
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

    def test_html_contains_examples_before_javascript_or_personal_directory(self):
        store=SimpleNamespace(settings={},root=Path('/nonexistent-runtime'))
        template=(REPO/'apps/workbench/web/index.html').read_text()
        with patch('data_library.featured_reports',side_effect=AssertionError('no runtime scan')):
            html=homepage(store,template)
        self.assertEqual(html.count('class="demo-report"'),4)
        self.assertIn('id="example-cache" type="application/json"',html)
        self.assertNotIn('正在读取示例目录',html)
        self.assertNotIn('href="#demo-reports" hidden',html)

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
        self.assertEqual(data.count(b'class="demo-report"'),4)

if __name__=='__main__':unittest.main()
