"""Versioned intake limits, independent of QC algorithms and deployment.

Passing admission is not a quality decision or a promise that a reader succeeds.
The local CLI remains unrestricted by the cloud dataset policy.
"""
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import stat


class LimitExceeded(ValueError):
    def __init__(self, field, observed, limit, label, *, version='cloud-intake/1.0'):
        self.field, self.observed, self.limit, self.version = field, observed, limit, version
        if field.endswith('_bytes'):
            def display(value):
                return f'{value / 1024**2:,.2f} MiB（{value:,} 字节）'
        else:
            def display(value):
                return f'{value:,} ' + ('份' if field == 'records' else '个')
        super().__init__(f'{label}为 {display(observed)}，上限为 {display(limit)}。请通过本地目录处理，或明确选择较小范围；未自动裁剪数据。')

    def payload(self):
        return {'error': str(self), 'code': 'intake_limit_exceeded', 'policy_version': self.version,
                'field': self.field, 'observed': self.observed, 'limit': self.limit}


@dataclass(frozen=True)
class IntakeLimits:
    version: str = 'cloud-intake/1.0'
    max_file_bytes: int = 512 * 1024**2
    max_record_bytes: int = 512 * 1024**2
    max_dataset_bytes: int = 5 * 1024**3
    max_records: int = 100
    max_files: int = 5000

    def describe(self):
        return asdict(self)

    def check(self, field, observed, label):
        if type(observed) is not int or observed < 0:
            raise ValueError('接入统计必须是非负整数。')
        limit = getattr(self, 'max_' + field)
        if observed > limit:
            raise LimitExceeded(field, observed, limit, label, version=self.version)


CLOUD_INTAKE_V1 = IntakeLimits()
CLOUD_INTAKE_V1_1 = replace(CLOUD_INTAKE_V1, version='cloud-intake/1.1',
                          max_file_bytes=1024**3, max_record_bytes=1024**3)
CLOUD_INTAKE_V1_2 = replace(CLOUD_INTAKE_V1_1, version='cloud-intake/1.2',
                          max_file_bytes=2 * 1024**3, max_record_bytes=2 * 1024**3)
CLOUD_INTAKE_V1_3 = replace(CLOUD_INTAKE_V1_2, version='cloud-intake/1.3', max_dataset_bytes=10 * 1024**3)
DEFAULT_INTAKE_LIMITS = CLOUD_INTAKE_V1_3
POLICIES = {p.version: p for p in (CLOUD_INTAKE_V1, CLOUD_INTAKE_V1_1, CLOUD_INTAKE_V1_2, CLOUD_INTAKE_V1_3)}


def configured_policy(settings):
    """Opt in on a local test instance; this does not enable network hosting."""
    name = settings.get('admission_policy', 'local')
    if name == 'local':
        return None
    if isinstance(name, str) and name in POLICIES:
        return POLICIES[name]
    raise ValueError('admission_policy 须为 local、cloud-intake/1.0、cloud-intake/1.1、cloud-intake/1.2 或 cloud-intake/1.3。')


def check_record_paths(paths, *, limits=DEFAULT_INTAKE_LIMITS):
    """Count each source once using actual bytes, before loading signal arrays."""
    states, total = {}, 0
    for value in paths:
        path = Path(value)
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError('记录接入只接受普通文件。')
        key = str(path.resolve())
        if key in states:
            continue
        info = path.stat()
        limits.check('file_bytes', info.st_size, '单个文件大小')
        total += info.st_size
        limits.check('record_bytes', total, '记录及配套文件合计')
        states[key] = [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]
    return {'policy_version': limits.version, 'status': 'accepted', 'record_bytes': total, 'files': len(states),
            'snapshot_fingerprint': hashlib.sha256(json.dumps(states, sort_keys=True).encode()).hexdigest()}


def check_registered_record(item, *, limits=DEFAULT_INTAKE_LIMITS):
    from .readers import inspect_recording
    from .readers.common import companion
    from .source_selection import reader_kwargs
    main = Path(item['source_path'])
    paths = [main] + [f['path'] for f in item.get('expected_source_files', [])]
    check_record_paths(paths, limits=limits)
    metadata = inspect_recording(main, **reader_kwargs(item.get('metadata', {})))
    paths.extend(companion(main, f['name']) for f in metadata.get('source_files', []))
    return check_record_paths(paths, limits=limits)
