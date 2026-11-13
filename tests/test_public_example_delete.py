"""Exercise real catalog endpoints without modifying any published examples."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.error import HTTPError

import pytest
from test_temporary_uploads import service
from example_cache import manifest, asset


@pytest.fixture
def catalog(service, tmp_path):
    server, call, _ = service
    cache = tmp_path/'cache'; release = '0123456789abcdef'
    rows, files = [], {}
    for name, job in [('one', '1'*32), ('two', '2'*32)]:
        urls = {}
        for lang in ['zh-CN', 'en']:
            page = f'datasets/{name}.{lang}.html'
            urls['url' if lang == 'zh-CN' else 'url_en'] = f'/examples/{release}/{page}'
            files[page] = f'<a href="/examples/{release}/records/{job}.{lang}.html">report</a>'
            files[f'records/{job}.{lang}.html'] = 'report'
        files[f'records/{job}.pdf'] = 'pdf'
        files[f'review/{job}/findings.json'] = '{}'
        rows.append({'id':name, 'kind':'dataset', 'package_id':name, **urls,
                     'source':{'name':'Public fixture', 'url':'https://example.org/public', 'license':'CC0'}})
    for name, value in files.items():
        path = cache/release/name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value)
    data = {'schema_version':'example-cache/1', 'release':release, 'examples':rows,
            'files':dict.fromkeys(files, {}), 'report_scores':{'1'*32:{},'2'*32:{}},
            'review_snapshots':{'1'*32:{},'2'*32:{}}}
    (cache/'manifest.json').write_text(json.dumps(data))
    server.store.settings['example_cache_dir'] = str(cache)

    class Auth(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            assert body['action'] == 'verify'
            assert self.headers['Origin'] == f'http://127.0.0.1:{self.server.server_port}'
            status = 200 if body['password'] == 'test-only' else 401
            self.send_response(status); self.end_headers()
            self.wfile.write(json.dumps({'verified':status==200}).encode())
        def log_message(self, *args): pass
    auth = ThreadingHTTPServer(('127.0.0.1', 0), Auth)
    thread = threading.Thread(target=auth.serve_forever, daemon=True); thread.start()
    server.store.settings['admin_auth_url'] = f'http://127.0.0.1:{auth.server_port}/api/access'
    yield server, call, release
    auth.shutdown(); auth.server_close(); thread.join(2)


def test_example_requires_password_and_protects_old_report_urls(catalog):
    server, call, release = catalog
    for body, code in [({'id':'one','confirmed':True},400),
                       ({'id':'one','confirmed':True,'password':'wrong'},403),
                       ({'id':'one','password':'test-only'},400)]:
        with pytest.raises(HTTPError) as e: call('/api/v1/examples/delete', body)
        assert e.value.code == code
    assert len(call('/api/v1/data')['examples']) == 2
    call('/api/v1/examples/delete', {'id':'one','password':'test-only','confirmed':True})
    directory = call('/api/v1/data', client=1)
    assert directory['examples_authoritative']
    assert [r['id'] for r in directory['examples']] == ['two']
    for suffix in ['datasets/one.zh-CN.html', 'records/'+'1'*32+'.pdf', 'records/'+'1'*32+'.en.html', 'review/'+'1'*32+'/findings.json']:
        with pytest.raises(KeyError): asset(server.store, f'/examples/{release}/'+suffix)
    assert asset(server.store, f'/examples/{release}/datasets/two.zh-CN.html').is_file()
    assert '1'*32 not in manifest(server.store)['review_snapshots']
    # State lives in the data volume, survives a new store object, and has no credentials.
    from types import SimpleNamespace
    restarted = SimpleNamespace(root=server.store.root, settings=server.store.settings)
    assert [r['id'] for r in manifest(restarted)['examples']] == ['two']
    assert 'test-only' not in (server.store.root/'public-example-state.json').read_text()


def test_example_delete_fails_closed_when_password_service_unavailable(catalog):
    server, call, _ = catalog
    server.store.settings['admin_auth_url'] = 'http://127.0.0.1:1/api/access'
    with pytest.raises(HTTPError) as e:
        call('/api/v1/examples/delete', {'id':'one','password':'test-only','confirmed':True})
    assert e.value.code == 503
    assert len(manifest(server.store)['examples']) == 2
