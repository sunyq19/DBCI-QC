"""Deployment boundaries for the shared demo; no QC or account logic."""
from contextlib import contextmanager
import shutil
import threading
from urllib.parse import urlsplit


def deployment(settings):
    value = settings.get('deployment', {})
    if not isinstance(value, dict) or set(value) - {'mode', 'public_origin', 'reserve_gib'}:
        raise ValueError('Invalid deployment configuration')
    mode = value.get('mode', 'local')
    if mode not in {'local', 'shared_demo'}:
        raise ValueError('deployment.mode must be local or shared_demo')
    if mode == 'local':
        return {'mode': mode}
    origin = value.get('public_origin', '')
    parts = urlsplit(origin)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname or
            parts.username or parts.password or parts.path or parts.query or parts.fragment or
            any(c.isspace() or c in '*;{}"\\' for c in origin) or
            parts.netloc != parts.netloc.lower() or
            origin != f'{parts.scheme}://{parts.netloc}' or
            not all(c.isascii() and (c.isalnum() or c in '.-:') for c in parts.hostname)):
        raise ValueError('public_origin must be one exact http(s) origin, without a path')
    # Accessing port also validates the numeric range.
    _ = parts.port
    reserve = value.get('reserve_gib', 10)
    if type(reserve) not in {int, float} or not 2 <= reserve <= 10000:
        raise ValueError('reserve_gib must be between 2 and 10000')
    return {'mode': mode, 'public_origin': origin, 'reserve_gib': reserve}


def check_request(settings, port, headers):
    config = deployment(settings)
    origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
    if config['mode'] == 'shared_demo':
        origins.add(config['public_origin'])
    host = headers.get('Host', '')
    allowed = {urlsplit(origin).netloc for origin in origins}
    if host not in allowed:
        raise PermissionError('请求地址不在工作台配置中。')
    origin = headers.get('Origin')
    if origin and (origin not in origins or urlsplit(origin).netloc != host):
        raise PermissionError('只接受本工作台发起的请求。')
    if headers.get('Sec-Fetch-Site') == 'cross-site':
        raise PermissionError('不接受跨站请求。')


class DemoCapacityError(ValueError):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


class UploadGuard:
    """One concurrent upload; reserve disk for expansion and existing jobs."""
    def __init__(self, settings, root, limits):
        self.config = deployment(settings)
        self.root, self.limits = root, limits
        self.lock = threading.Lock()

    @contextmanager
    def accept(self, filename, length):
        if self.config['mode'] != 'shared_demo':
            yield
            return
        if type(length) is not int or length <= 0:
            raise ValueError('请选择非空数据文件。')
        self.limits.check('file_bytes', length, '上传文件大小')
        if not self.lock.acquire(blocking=False):
            raise DemoCapacityError('另一个文件正在上传，请稍后重试。', 429)
        try:
            expanded = self.limits.max_record_bytes if filename.lower().endswith('.zip') else 0
            needed = int(self.config['reserve_gib'] * 1024**3) + length + expanded
            if shutil.disk_usage(self.root).free < needed:
                raise DemoCapacityError('演示服务器可用空间不足，暂不能接收新文件。请联系管理员。', 507)
            yield
        finally:
            self.lock.release()


def homepage(template, settings):
    from temporary_uploads import enabled
    private = enabled(settings)
    if private:
        template = template.replace('<html lang="zh-CN"', '<html lang="zh-CN" data-upload-policy="temporary"', 1)
        template = template.replace('上传文件保留 7 天，报告长期保留。', '文件与报告仅临时处理。完成后保留 1 小时供查看、下载；最长 6 小时自动清理。')
        template = template.replace('<p id="data-library-error"', '<aside id="temporary-session" class="temporary-session" hidden data-i18n-skip></aside><p id="data-library-error"', 1)
        template = template.replace('</head>', '<script src="/temporary-session.js" defer></script></head>', 1)
    if deployment(settings)['mode'] != 'shared_demo':
        return template
    template = template.replace('<html lang="zh-CN"', '<html lang="zh-CN" data-deployment="shared_demo"', 1)
    if not private:
        template = template.replace('<div id="upload-run-name-field"',
            '<p class="small muted shared-demo-note">共享演示区：文件和报告对所有访客可见，请仅上传公开或已脱敏数据。</p><div id="upload-run-name-field"', 1)
    return (template.replace('质控台 · 本地处理', '质控台')
            .replace('连接本地服务…', '连接服务…')
            .replace('保持本机服务运行即可', '处理完成后可回来查看报告'))
