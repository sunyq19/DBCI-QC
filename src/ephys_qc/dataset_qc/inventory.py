"""D01: compare a local package with explicit, independently prepared expectations.

This is a file-inventory check, not a BIDS validator or hospital acceptance rule.
No expectation is inferred from an observed file list or from a modality label.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path, PurePosixPath
import re

RULE_VERSION = 'package-inventory/0.1'
LABELS = {'present': '齐备', 'missing': '缺失', 'mismatch': '与清单不符',
          'unsafe': '路径不可用', 'unknown': '待确认', 'not_applicable': '不适用',
          'readable': '结构可读取', 'read_failed': '读取未通过', 'not_run': '未读取'}


def _relative(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or ':' in value or PurePosixPath(value).is_absolute()
            or any(p in {'', '.', '..'} for p in value.split('/'))
            or value.split('/')[0] in {'.git', '.qc'}):
        raise ValueError('Expected files must use safe package-relative paths, outside .git/.qc')
    return value


def _validate(manifest):
    if not isinstance(manifest, dict) or manifest.get('schema_version') != 'package-expectations/1':
        raise ValueError('Expected package-expectations/1 manifest')
    if not isinstance(manifest.get('scope'), str) or not manifest['scope'].strip():
        raise ValueError('An explicit selection scope is required')
    files, items, recordings = manifest.get('files'), manifest.get('items'), manifest.get('recordings', [])
    if not isinstance(files, list) or not isinstance(items, list) or not items or not isinstance(recordings, list):
        raise ValueError('files, items and recordings must be lists; items cannot be empty')
    names = set()
    for entry in files:
        if not isinstance(entry, dict): raise ValueError('File entries must be objects')
        name = _relative(entry.get('path'))
        if name in names: raise ValueError('Duplicate expected file')
        names.add(name)
        size = entry.get('size_bytes')
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError('size_bytes must be a nonnegative integer')
        digest = entry.get('digest')
        if digest is not None:
            if not isinstance(digest, dict): raise ValueError('Invalid digest')
            length = {'sha256': 64, 'md5': 32}.get(digest.get('algorithm'))
            if not length or not re.fullmatch('[0-9a-f]{' + str(length) + '}', str(digest.get('value', ''))):
                raise ValueError('Only lowercase SHA-256 and upstream MD5 digests are supported')
    ids, covered = set(), set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or not item['id'] or item['id'] in ids:
            raise ValueError('Each item needs a unique nonempty id')
        ids.add(item['id'])
        required = item.get('requirement')
        paths = item.get('files', [])
        if required not in {'required', 'not_applicable', 'unknown'} or not isinstance(paths, list):
            raise ValueError('Invalid item requirement or files')
        if required == 'required':
            if not paths or len(set(paths)) != len(paths) or any(p not in names for p in paths):
                raise ValueError('Required items must refer to declared, distinct files')
            covered.update(paths)
        elif paths or not isinstance(item.get('reason'), str) or not item['reason'].strip():
            raise ValueError('Unknown/not-applicable items need a reason and no assumed file list')
    if covered != names: raise ValueError('Each expected file must belong to an item')
    seen = set()
    for recording in recordings:
        if not isinstance(recording, dict) or recording.get('path') not in names:
            raise ValueError('Recording entry must refer to an expected file')
        key = (recording['path'], recording.get('stream_id'))
        if key in seen: raise ValueError('Duplicate recording entry')
        if key[1] is not None and not isinstance(key[1], str): raise ValueError('Invalid stream_id')
        seen.add(key)


def _safe_file(root, name):
    path = root
    for part in PurePosixPath(name).parts:
        path = path / part
        if path.is_symlink():
            return None
    return path


def _check_file(root, expected):
    name = expected['path']; path = _safe_file(root, name)
    result = {'path': name, 'status': 'present', 'size_bytes': None, 'sha256': None, 'issues': []}
    if path is None:
        return {**result, 'status': 'unsafe', 'issues': ['symlink_not_followed']}
    if not path.exists():
        return {**result, 'status': 'missing', 'issues': ['expected_file_absent']}
    if not path.is_file():
        return {**result, 'status': 'unsafe', 'issues': ['not_a_regular_file']}
    try:
        before = path.stat()
        sha, md5 = hashlib.sha256(), hashlib.md5()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block); md5.update(block)
        after = path.stat()
        result.update(size_bytes=after.st_size, sha256=sha.hexdigest())
        if (before.st_ino, before.st_mtime_ns, before.st_size) != (after.st_ino, after.st_mtime_ns, after.st_size):
            result['issues'].append('changed_during_check')
        if expected.get('size_bytes') is not None and expected['size_bytes'] != after.st_size:
            result['issues'].append('size_mismatch')
        digest = expected.get('digest')
        if digest and {'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}[digest['algorithm']] != digest['value']:
            result['issues'].append('digest_mismatch')
        result['identity_verified'] = digest is not None and not result['issues']
        if result['issues']: result['status'] = 'mismatch'
    except OSError:
        result.update(status='unsafe', issues=['file_access_failed'])
    return result


def inspect_package(root, expectations, *, read_headers=True, metadata_sink=None):
    """Read-only D01 result. Original files and the supplied expectations never change.

    A present item means only that its explicitly expected files were found and
    matched supplied identity fields. Header checks reuse registered readers.
    """
    _validate(expectations)
    root = Path(root)
    if root.is_symlink() or not root.is_dir(): raise ValueError('Package root must be a local directory')
    root = root.resolve()
    files = [_check_file(root, entry) for entry in expectations['files']]
    by_path = {row['path']: row for row in files}
    items = []
    for item in expectations['items']:
        paths = item.get('files', [])
        status = item['requirement']
        if status == 'required':
            observed = {by_path[p]['status'] for p in paths}
            status = next((s for s in ('unsafe', 'mismatch', 'missing') if s in observed), 'present')
        items.append({**item, 'status': status, 'present_count': sum(by_path[p]['status'] == 'present' for p in paths),
                      'expected_count': len(paths)})
    # Scan the actual tree too: extra files remain visible and are never silently
    # included in the denominator. Do not honor .bidsignore as a QC exclusion.
    observed, scan_errors = [], []
    for parent, dirs, names in os.walk(root, followlinks=False, onerror=lambda _: scan_errors.append('directory_access_failed')):
        if Path(parent) == root:
            dirs[:] = [d for d in dirs if d not in {'.git', '.qc'}]
        for directory in list(dirs):
            if (Path(parent) / directory).is_symlink():
                observed.append((Path(parent) / directory).relative_to(root).as_posix()); dirs.remove(directory)
        observed.extend((Path(parent) / name).relative_to(root).as_posix() for name in names)
    unlisted = sorted(set(observed) - set(by_path))
    recordings = []
    for request in expectations.get('recordings', []):
        name = request['path']; row = {'path': name, 'status': 'not_run'}
        if by_path[name]['status'] != 'present':
            row['reason'] = 'expected_file_not_verified'
        elif not read_headers:
            row['reason'] = 'header_check_not_requested'
        else:
            from ..readers import inspect_recording
            try:
                options = {'stream_id': request['stream_id']} if request.get('stream_id') else {}
                metadata = inspect_recording(root / name, **options)
                if metadata_sink is not None:
                    metadata_sink[name] = metadata
                # Technical summary only; no header patient identifier or annotation text.
                channels = metadata.get('channels', [])
                rates = sorted({c['sampling_rate_hz'] for c in channels if isinstance(c.get('sampling_rate_hz'), (int, float))})
                row.update(status='readable', format=metadata.get('format'), channel_count=len(channels),
                           duration_seconds=metadata.get('duration_seconds'), sampling_rates_hz=rates,
                           units=dict(Counter(c.get('unit') or '未声明' for c in channels)),
                           warning_count=len(metadata.get('warnings', [])),
                           warning_codes=[w.get('code', 'reader_warning') if isinstance(w, dict) else 'reader_warning'
                                          for w in metadata.get('warnings', [])])
            except (ValueError, OSError, ImportError) as error:
                # A backend failure is not proof that the scientific recording is corrupt.
                row.update(status='read_failed', reason=getattr(error, 'code', 'current_reader_cannot_inspect'), error_type=type(error).__name__)
        recordings.append(row)
    counts = Counter(r['status'] for r in files)
    item_counts = Counter(r['status'] for r in items)
    record_counts = Counter(r['status'] for r in recordings)
    issues = sum(counts[s] for s in ('missing', 'mismatch', 'unsafe'))
    result = {'schema_version': 'package-inventory-result/1', 'module_id': 'D01', 'rule_version': RULE_VERSION,
              'checked_at': datetime.now(timezone.utc).isoformat(), 'scope': expectations['scope'],
              'source': expectations.get('source', {}), 'execution_status': 'completed',
              'inventory_status': 'needs_attention' if issues or item_counts['unknown'] or scan_errors else 'complete',
              'header_status': 'needs_attention' if record_counts['read_failed'] or record_counts['not_run'] else
                               ('completed' if recordings else 'not_requested'),
              'summary': {'expected_files': len(files), 'present_files': counts['present'], 'file_status_counts': dict(counts),
                          'item_status_counts': dict(item_counts), 'recording_status_counts': dict(record_counts),
                          'unlisted_files': len(unlisted), 'verified_bytes': sum(r['size_bytes'] or 0 for r in files if r['status'] == 'present')},
              'items': items, 'files': files, 'recordings': recordings, 'unlisted_files': unlisted,
              'scan_errors': scan_errors, 'excluded_inventory_directories': ['.git', '.qc'],
              'not_checked': ['BIDS compliance', 'table/header consistency', 'signal quality', 'clinical suitability', 'anonymization']}
    return result


def _report(result):
    esc = lambda value: html.escape(str(value))
    number = lambda value: f'{value:.3f}'.rstrip('0').rstrip('.') if isinstance(value, (int, float)) else str(value)
    categories = {'derived_eeg': '派生 EEG 及配套表', 'recording_package': '原始记录及配套表', 'shared_metadata': '共享元数据'}
    s = result['summary']
    title = '清单内文件齐备' if result['inventory_status'] == 'complete' else '数据包有待处理项'
    matrix = ''.join('<tr><td>' + '</td><td>'.join(esc(v) for v in
                     ('数据集' if r.get('subject') == 'dataset' else r.get('subject', '—'), categories.get(r.get('category'), r.get('category', r['id'])), LABELS[r['status']],
                      f'{r["present_count"]}/{r["expected_count"]}' if r['requirement'] == 'required' else '—', r.get('reason', ''))) + '</td></tr>'
                     for r in result['items'])
    records = ''.join('<tr><td>' + '</td><td>'.join(esc(v) for v in
                      (r['path'], LABELS[r['status']] + (f' · {r["warning_count"]} 项提示' if r.get('warning_count') else '')
                       + ('：二进制长度不是完整采样帧' if r.get('reason') == 'incomplete_sample_frame' else ''),
                       r.get('channel_count', '—'), number(r.get('duration_seconds', '—')),
                       ', '.join(number(v) for v in r.get('sampling_rates_hz', [])) or '—',
                       '、'.join(r.get('units', {})) or '—')) + '</td></tr>' for r in result['recordings'])
    problems = [r for r in result['files'] if r['status'] != 'present']
    problem_html = ''.join(f'<li>{esc(r["path"])}：{esc(LABELS[r["status"]])} · {esc(", ".join(r["issues"]))}</li>' for r in problems)
    if not problem_html: problem_html = '<li>清单内未发现缺件或文件指纹不符。</li>'
    unlisted = ''.join(f'<li>{esc(p)}</li>' for p in result['unlisted_files'])
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>数据包完整性检查</title><style>
body{{font:16px/1.65 system-ui,sans-serif;background:#f4f7fc;color:#18324d;margin:0;padding:32px}}main{{max-width:1180px;margin:auto}}
section{{background:white;border:1px solid #dce5f2;border-radius:16px;padding:28px;margin:20px 0}}h1{{margin:8px 0;font-size:30px}}h2{{font-size:21px}}
.tag{{color:#2459c6;font-weight:600}}.muted{{color:#61738b}}.stats{{display:flex;gap:48px;flex-wrap:wrap}}.stats b{{font-size:32px;display:block;color:#2459c6}}
table{{width:100%;border-collapse:collapse;font-size:14px}}td,th{{border-bottom:1px solid #e5ebf3;padding:12px;text-align:left;overflow-wrap:anywhere}}th{{background:#f5f8fd}}details{{margin-top:20px}}summary{{cursor:pointer;color:#2459c6}}a{{color:#2459c6}}.scroll{{overflow:auto}}@media print{{body{{padding:0}}section{{break-inside:avoid}}}}
</style><main><span class="tag">D01 · 数据包清点 · {esc(result['rule_version'])}</span><h1>数据包完整性检查</h1>
<section><h2>{title}</h2><p>{esc(result['scope'])}</p><div class="stats"><div><b>{s['present_files']} / {s['expected_files']}</b>清单内文件</div>
<div><b>{s['recording_status_counts'].get('readable', 0)} / {len(result['recordings'])}</b>结构可读取的记录</div>
<div><b>{s['item_status_counts'].get('unknown', 0)}</b>应有内容待确认</div></div><p class="muted">齐备仅针对本次明确列出的文件。通道表与文件头是否一致、信号质量及医院验收结论另行检查。</p></section>
<section><h2>应到与实到</h2><div class="scroll"><table><tr><th>对象</th><th>资料组</th><th>状态</th><th>文件</th><th>说明</th></tr>{matrix}</table></div></section>
<section><h2>待处理项</h2><ul>{problem_html}</ul><p class="muted">读取未通过表示当前读取器不能完成检查，不直接判定原始数据损坏。待确认、不适用均不计为已到。</p></section>
<section><h2>记录清单</h2><p class="muted">以下数值来自记录文件。单位缺失或有读取提示时，不能直接视为可做电压指标计算。</p><div class="scroll"><table><tr><th>文件</th><th>读取</th><th>通道数</th><th>时长 / 秒</th><th>采样率 / Hz</th><th>文件内单位</th></tr>{records}</table></div>
<details><summary>清单外文件 · {len(result['unlisted_files'])}</summary><p>单独列出，不自动纳入完整性分母；来源说明等附加文件可以合法存在。</p><ul>{unlisted}</ul></details>
<details><summary>范围与追溯</summary><p>递归清点文件，符号链接不跟随；忽略本地管理目录 .git、.qc；不按 .bidsignore 隐藏文件。</p><p>检查时间：{esc(result['checked_at'])}</p><p>本地检查报告，未执行敏感信息审查。</p><a href="result.json">下载结构化结果</a> · <a href="expectations.json">查看本次清单</a></details></section></main></html>'''


def run_package_inventory(root, expectations, output_dir, *, read_headers=True):
    """Write a standalone local HTML report and frozen evidence to a new folder."""
    if Path(root).is_symlink() or Path(output_dir).is_symlink():
        raise ValueError('Source and output directories must not be symbolic links')
    root, output = Path(root).resolve(), Path(output_dir).resolve()
    if root == output or root in output.parents or output in root.parents:
        raise ValueError('Output must be separate from the source package')
    if output.exists(): raise FileExistsError('Use a new output directory')
    # Copy through JSON so a caller cannot later mutate the saved manifest.
    frozen = json.loads(json.dumps(expectations, ensure_ascii=False, allow_nan=False))
    result = inspect_package(root, frozen, read_headers=read_headers)
    output.mkdir(parents=True, exist_ok=False)
    for name, content in (('expectations.json', frozen), ('result.json', result)):
        (output / name).write_text(json.dumps(content, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'report.html').write_text(_report(result), encoding='utf-8')
    return result
