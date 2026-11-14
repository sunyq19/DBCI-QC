"""Point standalone workbenches at the team's existing collaboration site."""
from urllib.parse import urlsplit, urlunsplit


def dispatch(handler, path):
    config = handler.server.store.settings.get('collaboration', {})
    if path not in {'/flow', '/flow/'} or not config.get('enabled') or not config.get('url'):
        return False
    # Administrator configuration, never a destination supplied by the visitor.
    target = urlsplit(config['url'])
    if (target.scheme not in {'http', 'https'} or not target.hostname
            or target.username or target.password or '\r' in config['url'] or '\n' in config['url']):
        raise ValueError('模块协作地址配置无效。')
    if target.netloc == handler.headers.get('Host'):
        raise ValueError('模块协作地址不能指向自身。')
    if handler.command != 'GET':
        handler.json({'error': '请打开模块协作页面后再编辑。'}, 405)
        return True
    location = urlunsplit((target.scheme, target.netloc, target.path or '/flow/',
                          urlsplit(handler.path).query or target.query, target.fragment))
    handler.send_bytes(b'', code=302, headers={'Location': location})
    return True
