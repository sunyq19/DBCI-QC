"""Keep local navigation on one shared collaboration history."""
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/workbench'))
from collaboration_route import dispatch


def handler(url='http://team.example:8769/flow/', path='/flow/?version=approved-v1', command='GET'):
    return SimpleNamespace(server=SimpleNamespace(store=SimpleNamespace(settings={
        'collaboration': {'enabled': True, 'url': url}})), path=path,
        command=command, headers={'Host': '127.0.0.1:8769'}, send_bytes=Mock(), json=Mock())


@pytest.mark.parametrize('path', ['/flow', '/flow/'])
def test_version_link_reuses_shared_history(path):
    h = handler(path=path+'?version=approved-v1')
    assert dispatch(h, path)
    assert h.send_bytes.call_args.kwargs == {'code': 302, 'headers': {
        'Location': 'http://team.example:8769/flow/?version=approved-v1'}}


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'http://user:secret@team.example/flow/',
                                  'http://127.0.0.1:8769/flow/', 'http://team.example/\r\nX-Fake:1'])
def test_invalid_or_looping_destination_rejected(url):
    h = handler(url=url)
    with pytest.raises(ValueError): dispatch(h, '/flow/')
    h.send_bytes.assert_not_called()


def test_request_cannot_choose_redirect_destination():
    h = handler(path='/flow/?next=https://untrusted.example')
    dispatch(h, '/flow/')
    assert h.send_bytes.call_args.kwargs['headers']['Location'].startswith('http://team.example:8769/flow/?')


def test_cloud_and_api_routing_unchanged():
    h = handler()
    assert not dispatch(h, '/api/flow')
    h.server.store.settings = {}
    assert not dispatch(h, '/flow/')


def test_edit_body_is_not_redirected_to_other_site():
    h = handler(command='POST')
    assert dispatch(h, '/flow/')
    assert h.json.call_args.args[1] == 405
    h.send_bytes.assert_not_called()
