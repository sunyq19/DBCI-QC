"""Password-protected withdrawal of published examples; no upload ownership here."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

from deployment import DemoCapacityError


def deleted_examples(store):
    if not getattr(store, 'root', None): return set()  # Offline cache tooling has no runtime state.
    path = store.root / 'public-example-state.json'
    if not path.exists(): return set()
    value = json.loads(path.read_text(encoding='utf-8'))
    return set(value['deleted_examples'])


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None


def verify_password(store, password):
    if not isinstance(password, str) or not password or len(password) > 256:
        raise ValueError('请输入模块协作的编辑密码。')
    # Fixed administrator configuration, never a user-supplied destination.
    endpoint = os.environ.get('QC_ADMIN_AUTH_URL') or store.settings.get('admin_auth_url') or 'http://127.0.0.1:18770/api/access'
    parsed = urlsplit(endpoint)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('管理员验证服务配置不正确。')
    origin = store.settings.get('deployment', {}).get('public_origin') or f'{parsed.scheme}://{parsed.netloc}'
    request = Request(endpoint, data=json.dumps({'action': 'verify', 'password': password}).encode(),
                      headers={'Content-Type': 'application/json', 'Origin': origin, 'Host': urlsplit(origin).netloc})
    try:
        with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=5) as response:
            if json.loads(response.read(4096)).get('verified') is not True:
                raise ValueError('unverified')
    except HTTPError as exc:
        if exc.code in {400, 401, 403}: raise PermissionError('编辑密码不正确。') from None
        if exc.code == 429: raise DemoCapacityError('尝试次数过多，请15分钟后再试。', 429) from None
        raise DemoCapacityError('编辑密码验证服务暂不可用，示例未删除。', 503) from None
    except (URLError, OSError, ValueError):
        raise DemoCapacityError('编辑密码验证服务暂不可用，示例未删除。', 503) from None


def delete_example(store, body):
    if not isinstance(body, dict) or body.get('confirmed') is not True:
        raise ValueError('请确认删除此公开示例。')
    identifier = body.get('id')
    if not isinstance(identifier, str): raise ValueError('示例标识无效。')
    verify_password(store, body.get('password'))
    with store.lock:
        from example_cache import manifest
        if identifier not in {row['id'] for row in manifest(store)['examples']}:
            raise KeyError(identifier)
        deleted = deleted_examples(store) | {identifier}
        path = store.root / 'public-example-state.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'deleted_examples': sorted(deleted)}, ensure_ascii=False), encoding='utf-8')
        temporary.chmod(0o600)
        temporary.replace(path)
    return {'status': 'deleted', 'id': identifier}
