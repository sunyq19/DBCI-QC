"""Read-only admission of a complete, server-resolved dataset snapshot.

Counts actual files (including unlisted files), not claimed manifest sizes.
Remote upload finalization must first materialize/verify its complete snapshot;
this adapter is for accessible local directories, not arbitrary object-store URLs.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

from ..admission import DEFAULT_INTAKE_LIMITS
from ..readers import detect_format, inspect_recording, list_readers
from .consistency import validate_consistency


def scan_snapshot(root, limits=DEFAULT_INTAKE_LIMITS):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('接入范围须为可访问的普通目录。')
    root = root.resolve()
    rows, total, entries = {}, 0, 0
    pending = [root]
    while pending:
        parent = pending.pop()
        with os.scandir(parent) as stream:
            for entry in stream:
                entries += 1
                # Bound traversal even if a tree contains only empty directories.
                if entries > 20000:
                    raise ValueError('目录条目过多，云端首版最多遍历 20,000 个文件和目录条目。')
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    pending.append(Path(entry.path))
                    continue
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError('云端接入只接受普通文件和目录，不跟随符号链接。')
                name = Path(entry.path).relative_to(root).as_posix()
                limits.check('file_bytes', info.st_size, '单个文件大小')
                total += info.st_size
                limits.check('dataset_bytes', total, '数据集总大小')
                limits.check('files', len(rows) + 1, '数据集文件数')
                if name.lower().endswith(('.zip', '.7z', '.tar', '.tgz', '.tar.gz')):
                    raise ValueError('数据集快照须为展开后的文件目录；请先经受限解包接入单记录压缩包。')
                rows[name] = {'size_bytes': info.st_size,
                              'state': [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns]}
    fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return root, rows, total, fingerprint


def _companion_name(main, name):
    if not isinstance(name, str) or not name or '/' in name or '\\' in name or ':' in name or name in {'.', '..'}:
        raise ValueError('读取器未提供可核验的同目录配套文件名。')
    return str(PurePosixPath(main).parent / name)


def check_dataset_snapshot(root, plan, *, limits=DEFAULT_INTAKE_LIMITS, transport_bytes=None):
    """Return evidence for admission only; missing/invalid files remain QC issues.

    transport_bytes, when used by a future finalization adapter, must come from
    verified storage receipts, never a value asserted by an untrusted client.
    """
    config = validate_consistency(plan)
    if transport_bytes is not None:
        limits.check('dataset_bytes', transport_bytes, '本次上传总大小')
    root, files, total, before = scan_snapshot(root, limits)
    declared = {r['path']: r for r in config['records']}
    options = {r['path']: r.get('stream_id') for r in plan['recordings']}
    entries = set(declared)
    extensions = tuple(ext for spec in list_readers() for ext in spec['extensions'])
    for name in files:
        if name.lower().endswith(extensions):
            entries.add(name)
        else:
            # Also recognize EDF/BDF magic under a nonstandard extension.
            try:
                if detect_format(root / name) in {'EDF', 'BDF'}:
                    entries.add(name)
            except ValueError:
                pass
    limits.check('records', len(entries), '数据集记录数')
    evidence = []
    for name in sorted(entries):
        binding = declared.get(name, {})
        associated = {name}
        associated.update(binding.get('metadata_json', []))
        associated.update(binding[k] for k in ('channels_tsv', 'participants_tsv', 'sessions_tsv', 'scans_tsv') if binding.get(k))
        if binding.get('events'):
            associated.add(binding['events']['path'])
        mode = 'missing_record'
        if name in files:
            try:
                metadata = inspect_recording(root / name, **({'stream_id': options[name]} if options.get(name) else {}))
                associated.update(_companion_name(name, f['name']) for f in metadata.get('source_files', []))
                mode = 'reader_verified'
            except (ValueError, OSError, ImportError):
                # An unreadable record must still be reported by D01. A complete
                # sibling-directory sum conservatively bounds unresolved companions.
                associated.update(n for n in files if PurePosixPath(n).parent == PurePosixPath(name).parent)
                mode = 'directory_upper_bound'
        size = sum(files[n]['size_bytes'] for n in associated if n in files)
        limits.check('record_bytes', size, '记录及配套文件合计' if mode != 'directory_upper_bound' else '配套关系未确认的同目录大小上界')
        evidence.append({'path': name, 'size_bytes': size, 'basis': mode})
    _, _, _, after = scan_snapshot(root, limits)
    if before != after:
        raise ValueError('接入检查期间文件发生变化，请重新提交。')
    return {'policy_version': limits.version, 'status': 'accepted', 'files': len(files), 'records': len(entries),
            'dataset_bytes': total, 'transport_bytes': transport_bytes,
            'snapshot_fingerprint': before, 'record_sizes': evidence,
            'scope': 'complete_directory_including_unlisted_files', 'evidence': 'server_filesystem_stat_and_readers'}


def assert_snapshot_unchanged(root, admitted, *, limits=DEFAULT_INTAKE_LIMITS):
    _, _, _, fingerprint = scan_snapshot(root, limits)
    if fingerprint != admitted['snapshot_fingerprint']:
        raise ValueError('数据集在接入后发生变化，本次任务未执行，请重新确认后提交。')
