"""Source identity and safe companion references shared by all adapters."""
from pathlib import Path
import hashlib


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def companion(main, name, extension=None):
    if (not isinstance(name, str) or not name or name.strip() != name or
            any(c in name for c in ('/', '\\', ':', '\x00')) or name in {'.', '..'} or
            any(ord(c) < 32 for c in name)):
        raise ValueError('伴随文件引用必须是同目录文件名，不能使用绝对路径、目录跳转或远程地址。')
    path = Path(main).parent / name
    if path.is_symlink() or not path.is_file() or path.resolve().parent != Path(main).resolve().parent:
        raise ValueError('伴随文件缺失、符号链接或越出包目录。')
    if extension and path.suffix.lower() != extension:
        raise ValueError('伴随文件扩展名与格式不符。')
    return path.resolve()


def source_manifest(paths):
    result = []
    seen = set()
    for path, role in paths:
        path = Path(path).resolve()
        if path in seen:
            continue
        seen.add(path)
        stat = path.stat()
        result.append({'path': str(path), 'name': path.name, 'role': role,
                       'size_bytes': stat.st_size, 'sha256': sha256(path)})
    return result


def public_manifest(manifest):
    return [{k: v for k, v in item.items() if k != 'path'} for item in manifest]


def annotation_summary(events, sources):
    names = sorted({str(e.get('text', e.get('description', ''))) for e in events})
    return {'available': bool(events), 'count': len(events), 'kinds': names[:100],
            'kinds_truncated': len(names) > 100, 'source': [Path(s).name for s in sources],
            'time_reference': 'recording_start_seconds', 'clinical_interpretation': 'not_inferred'}


class SourceGuard:
    def capture(self, manifest):
        self.source_files = manifest
        self._file_states = {item['path']: self._stat(item['path']) for item in manifest}

    @staticmethod
    def _stat(path):
        stat = Path(path).stat()
        return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def assert_unchanged(self, hashes=False):
        for item in self.source_files:
            path = item['path']
            if Path(path).is_symlink() or self._stat(path) != self._file_states[path]:
                raise ValueError('来源文件在读取期间发生改变。')
            if hashes and sha256(path) != item['sha256']:
                raise ValueError('来源文件哈希在读取期间发生改变。')

    def close(self):
        pass
