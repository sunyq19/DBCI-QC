"""Native-sample whole-record scheduling and durable, non-quality coverage.

Planning imports only the standard library. Each window runs the existing
independent modules, retains its own evidence, and is never treated as a task
epoch or as an independent validation example. No cleaning is performed.
"""
from collections import Counter
import copy
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import time

MAX_INPUT_BYTES = 256 * 1024 * 1024
MAX_WINDOWS = 10000
EXPENSIVE_METHODS = {'autoreject_global'}


class RecordingCancelled(Exception):
    """Cooperative cancellation, checked between modules and windows."""


def _hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def validate_recording_options(options):
    from .planning import _number
    if not isinstance(options, dict) or set(options) - {'window_seconds', 'expensive_methods'}:
        raise ValueError('recording_options accepts window_seconds and expensive_methods only')
    seconds = _number(options.get('window_seconds', 120), 'recording_options.window_seconds', True)
    if seconds > 120:
        raise ValueError('recording_options.window_seconds must be <= 120 seconds')
    mode = options.get('expensive_methods', 'skip')
    if mode not in {'skip', 'run'}:
        raise ValueError('recording_options.expensive_methods must be skip or run')
    return {'window_seconds': seconds, 'expensive_methods': mode}


def _source_layout(record, config):
    """Validate enough metadata to split; every window still uses full planner."""
    from .planning import _number
    meta = record.get('metadata', {})
    selection = config.get('selection', {})
    if not isinstance(selection, dict):
        raise ValueError('Invalid selection fields')
    indices = selection.get('eeg_indices')
    channels = meta.get('channels', [])
    if not isinstance(channels, list) or not channels:
        raise ValueError('metadata.channels is required for a reviewed selection')
    by_index = {c.get('index', c.get('source_index')): c for c in channels if isinstance(c, dict)}
    if not isinstance(indices, list) or not indices or any(type(i) is not int or i not in by_index for i in indices) or len(set(indices)) != len(indices):
        raise ValueError('eeg_indices must contain distinct registered source indices')
    refs = selection.get('reference_indices', {})
    if not isinstance(refs, dict) or any(type(i) is not int or i not in by_index for i in refs.values()):
        raise ValueError('reference_indices must identify registered channels')
    rates = {_number(by_index[i].get('sampling_rate_hz'), 'sampling_rate_hz', True) for i in indices + list(refs.values())}
    if len(rates) != 1:
        raise ValueError('EEG and auxiliary channels must share one native sample clock; no automatic resampling')
    fs = next(iter(rates))
    duration = _number(meta.get('duration_seconds'), 'metadata.duration_seconds', True)
    total = round(duration * fs)
    if total < 1 or abs(duration * fs - total) > 1e-4:
        raise ValueError('Recording duration must end on the selected native sample grid')
    origin = meta.get('clock', {}).get('first_sample', 0)
    if type(origin) is not int or origin < 0:
        raise ValueError('Invalid original sample origin')
    supplied = meta.get('continuous_segments')
    if supplied is None:
        supplied = [{'segment_id': None, 'start_sample': origin, 'stop_sample': origin + total,
                     'recording_start_seconds': 0.0}]
    if not isinstance(supplied, list) or not supplied:
        raise ValueError('No declared continuous source segment is available')
    segments, previous = [], 0
    for index, item in enumerate(supplied):
        if not isinstance(item, dict):
            raise ValueError('Invalid continuous source segment')
        first, stop = item.get('start_sample'), item.get('stop_sample')
        if type(first) is not int or type(stop) is not int or first < 0 or stop <= first:
            raise ValueError('Continuous segments require increasing integer sample bounds')
        onset = _number(item.get('recording_start_seconds'), 'segment.recording_start_seconds')
        local = round(onset * fs)
        if abs(onset * fs - local) > 1e-4 or local < previous or local + stop - first > total:
            raise ValueError('Continuous segments must be ordered, non-overlapping and on the native sample grid')
        if index == 0:
            origin = first - local
        if origin < 0 or first - local != origin:
            raise ValueError('Continuous segments disagree on the original sample origin')
        segments.append({'segment_id': item.get('segment_id'), 'start_sample': first, 'stop_sample': stop,
                         'recording_start_seconds': local / fs, 'local_start_sample': local,
                         'local_stop_sample': local + stop - first})
        previous = local + stop - first
    gaps, cursor = [], 0
    for segment in segments:
        if segment['local_start_sample'] > cursor:
            gaps.append({'start_sample': origin + cursor, 'stop_sample': origin + segment['local_start_sample'],
                         'start_seconds': cursor / fs, 'duration_seconds': (segment['local_start_sample'] - cursor) / fs,
                         'reason': 'declared_source_gap', 'status': 'not_assessable'})
        cursor = segment['local_stop_sample']
    if cursor < total:
        gaps.append({'start_sample': origin + cursor, 'stop_sample': origin + total, 'start_seconds': cursor / fs,
                     'duration_seconds': (total - cursor) / fs, 'reason': 'declared_source_gap', 'status': 'not_assessable'})
    available = sum(s['stop_sample'] - s['start_sample'] for s in segments)
    return {'sampling_rate_hz': fs, 'sample_origin': origin, 'total_samples': total,
            'available_samples': available, 'gap_samples': total - available,
            'total_seconds': total / fs, 'available_seconds': available / fs, 'gap_seconds': (total - available) / fs,
            'segments': segments, 'gaps': gaps, 'channel_count': len(indices),
            'loaded_channel_count': len(indices) + len(refs)}


def window_config(plan, window):
    config = copy.deepcopy(plan['qc_config'])
    config['scope'] = 'window'
    config.pop('recording_options', None)
    config['selection'].update(start_seconds=window['start_seconds'], duration_seconds=window['duration_seconds'])
    config['selection'].pop('segment_id', None)
    # Metadata was inspected with a temporary reader identity; runtime opens it
    # with the registered record identity. Match the unique native time range,
    # then assert exact source sample bounds, never reuse inspection-scoped IDs.
    skipped = {m['id'] for m in plan.get('skipped_methods', [])}
    config['method_config']['extensions'] = [m for m in config['method_config'].get('extensions', []) if m not in skipped]
    return config


def build_recording_plan(record, selected_modules=None, qc_config=None):
    from .planning import _build_window_plan, _finite_json, _merge
    default = record.get('default_config', {})
    if not isinstance(default, dict):
        raise ValueError('default_config must be an object')
    config = _merge(default, qc_config or {})
    _finite_json(config)
    if set(config) - {'scope', 'recording_options', 'selection', 'method_config', 'feature_config', 'policy_config', 'context_tags'}:
        raise ValueError('Unknown QC configuration fields')
    options = validate_recording_options(config.get('recording_options', {}))
    layout = _source_layout(record, config)
    fs = layout['sampling_rate_hz']
    max_samples = min(math.floor(options['window_seconds'] * fs + 1e-9),
                      MAX_INPUT_BYTES // (8 * layout['loaded_channel_count']))
    if max_samples < 1:
        raise ValueError('Selected recording chunk exceeds the input memory budget')
    windows = []
    for segment in layout['segments']:
        for first in range(segment['start_sample'], segment['stop_sample'], max_samples):
            if len(windows) >= MAX_WINDOWS:
                raise ValueError(f'Recording plan exceeds {MAX_WINDOWS} windows; increase the window duration')
            stop = min(first + max_samples, segment['stop_sample'])
            windows.append({'id': f'w{len(windows) + 1:06d}', 'index': len(windows), 'segment_id': segment['segment_id'],
                            'start_sample': first, 'stop_sample': stop, 'start_seconds': (first - layout['sample_origin']) / fs,
                            'duration_seconds': (stop - first) / fs})
    # Validate the original selection and all explicitly supplied method params.
    # Only timing/segment is replaced by the whole-record scope.
    config['scope'] = 'window'
    config.pop('recording_options', None)
    config['selection'].pop('stream_id', None)
    config['selection'].pop('segment_id', None)
    config['selection'].update(start_seconds=windows[0]['start_seconds'], duration_seconds=windows[0]['duration_seconds'])
    original = _build_window_plan(record, selected_modules, config)
    canonical = copy.deepcopy(original['qc_config'])
    canonical['scope'] = 'recording'
    canonical['recording_options'] = options
    canonical['selection'].pop('segment_id', None)
    canonical['selection'].update(start_seconds=0.0, duration_seconds=layout['total_seconds'])
    skipped = [{'id': method, 'module_id': 'M03', 'reason': '整记录策略跳过逐窗重复交叉验证；可明确设 expensive_methods=run 后运行。'}
               for method in canonical['method_config']['extensions']
               if options['expensive_methods'] == 'skip' and method in EXPENSIVE_METHODS]
    plan = copy.deepcopy(original)
    plan.update(scope='recording', schema_version='ephys-recording-plan/1.0', qc_config=canonical,
                windows=windows, window_count=len(windows), coverage_plan=layout,
                skipped_methods=skipped, algorithm_scope='independent_native_windows',
                auto_added_modules=original['auto_added_modules'])
    node_states = {n['id']: Counter() for n in original['nodes']}
    method_states = {m['id']: Counter() for m in original['method_applicability']}
    for window in windows:
        child = _build_window_plan(record, plan['selected_modules'], window_config(plan, window))
        window['plan_id'] = child['plan_id']
        for node in child['nodes']:
            node_states[node['id']][node['status']] += 1
        for method in child['method_applicability']:
            method_states[method['id']][method['status']] += 1
    for node in plan['nodes']:
        counts = node_states[node['id']]
        node['window_status_counts'] = dict(counts)
        if counts['skipped'] == len(windows):
            node['status'] = 'skipped'
        elif counts['ready'] == len(windows) and not any(m['module_id'] == node['id'] for m in skipped):
            node['status'] = 'ready'
            node['reason'] = f'{len(windows)} 个窗口均满足入口条件；不是质量合格结论。'
        else:
            node['status'] = 'partial'
            node['reason'] = '部分窗口或显式方法策略不可完整评估，逐窗保留状态。'
    for method in plan['method_applicability']:
        counts = method_states[method['id']]
        method['window_status_counts'] = dict(counts)
        if method['id'] in {m['id'] for m in skipped}:
            method.update(status='blocked', reason=next(m['reason'] for m in skipped if m['id'] == method['id']))
        elif len(counts) > 1:
            method.update(status='partial', reason='各窗口适用性不同；短尾窗与缺失条件须分别检查。')
    warnings = [
        '整记录采用不重叠的原生连续段分块，逐窗检测；不是把整份记录当一个统计样本。',
        '窗口边界会影响滤波、频谱、稳健阈值和短事件；跨窗候选保留独立证据，不自动合并为最终坏段。',
        '覆盖百分比仅表示执行范围，不表示信号质量；短尾窗、失败、跳过和来源缺口分别保留。',
    ]
    if layout['gap_samples']:
        warnings.append('文件声明存在无样本的采集缺口；这些时间不纳入已检查范围。')
    warnings += [m['reason'] for m in skipped]
    if 'M06' in plan['selected_modules'] or options['expensive_methods'] == 'run':
        warnings.append('已选生理伪迹或交叉验证方法将逐窗串行执行，长记录可能耗时较长，可取消；不会只抽查首窗。')
    plan['warnings'] = list(dict.fromkeys(original['warnings'] + warnings))
    # Dependency closure is identical whether callers submit the original
    # choices or the already-expanded selected_modules returned by the plan.
    plan['plan_id'] = _hash({k: v for k, v in plan.items() if k not in {'plan_id', 'auto_added_modules'}})
    return plan


def coverage(plan, windows):
    """Partition samples exactly; partial execution is never full assessment."""
    layout = plan['coverage_plan']; fs = layout['sampling_rate_hz']
    counts = Counter(); by_module = {mid: Counter() for mid in plan['selected_modules']}
    fully = 0
    for window in windows:
        samples = window['stop_sample'] - window['start_sample']
        status = window['status']
        key = 'completed' if status in {'completed', 'partial'} else 'failed' if status == 'failed' else 'running' if status == 'running' else 'unexecuted'
        counts[key] += samples
        mods = {m['id']: m for m in window.get('modules', [])}
        if key == 'completed' and all(mods.get(mid, {}).get('status') == 'completed' for mid in plan['selected_modules']) and not plan['skipped_methods']:
            fully += samples
        for mid, bucket in by_module.items():
            observed = mods.get(mid, {}).get('status')
            if observed == 'completed' and any(item['module_id'] == mid for item in plan['skipped_methods']):
                observed = 'partial'
            bucket[observed if observed in {'completed', 'partial', 'failed', 'skipped'} else 'unexecuted'] += samples
    total = layout['total_samples']; available = layout['available_samples']
    result = {key: layout[key] for key in ('total_samples', 'available_samples', 'gap_samples', 'total_seconds', 'available_seconds', 'gap_seconds')}
    for name in ('completed', 'failed', 'running', 'unexecuted'):
        result[name + '_samples'] = counts[name]
        result[name + '_seconds'] = counts[name] / fs
    result.update(execution_percent=100 * counts['completed'] / total,
                  available_execution_percent=100 * counts['completed'] / available,
                  fully_assessed_seconds=fully / fs, fully_assessed_percent=100 * fully / total,
                  quality_score=False, interpretation='execution_coverage_not_signal_quality',
                  by_module=[{'id': mid, **{key + '_seconds': bucket[key] / fs for key in ('completed', 'partial', 'failed', 'skipped', 'unexecuted')}} for mid, bucket in by_module.items()])
    return result


def _export_window(window, directory, artifacts):
    """Expose immutable sub-artifacts through the existing flat allowlist API."""
    prefix = window['id'] + '--'
    child_artifacts = directory / 'artifacts'
    paths = sorted(p for p in child_artifacts.iterdir() if p.is_file()) if child_artifacts.exists() else []
    names = [p.name for p in paths]
    for path in paths:
        target = artifacts / (prefix + path.name)
        if path.suffix == '.html':
            text = path.read_text(encoding='utf-8')
            for name in names:
                for attr in ('href', 'src'):
                    for quote in ('"', "'"):
                        text = text.replace(f'{attr}={quote}{name}{quote}', f'{attr}={quote}{prefix}{name}{quote}')
            target.write_text(text, encoding='utf-8')
        else:
            shutil.copyfile(path, target)
    if (directory / 'result.json').exists():
        window['result_artifact'] = prefix + 'result.json'
        shutil.copyfile(directory / 'result.json', artifacts / window['result_artifact'])
    if 'report.html' in names:
        window['report_artifact'] = prefix + 'report.html'


def _candidate_entries(window, directory):
    """Index original candidate objects; no new temporal/channel inference."""
    result = []
    for path in sorted((directory / 'artifacts').glob('M*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        candidates = [(f'/candidates/{index}', candidate) for index, candidate in enumerate(data.get('candidates', []))] if isinstance(data.get('candidates'), list) else []
        # Thomson hits are observations in overlapping windows, not independent
        # artifacts; retain that distinction in the source pointer and type.
        line = data.get('line_noise', {})
        if isinstance(line, dict) and isinstance(line.get('observations'), list):
            candidates += [(f'/line_noise/observations/{index}', candidate) for index, candidate in enumerate(line['observations'])
                           if isinstance(candidate, dict) and candidate.get('flagged') is True]
        for pointer, candidate in candidates:
            result.append({'window_id': window['id'], 'module_id': path.name[:3],
                           'artifact': window['id'] + '--' + path.name, 'json_pointer': pointer,
                           'candidate': candidate, 'time_reference': 'original_recording_no_added_offset',
                           'candidate_type': 'flagged_spectral_observation' if pointer.startswith('/line_noise') else 'source_candidate',
                           'assessment': 'candidate_not_human_confirmation'})
    return result


def _modules(plan, windows):
    modules = []
    for node in plan['nodes']:
        rows = [next((m for m in w.get('modules', []) if m['id'] == node['id']), None) for w in windows]
        counts = Counter(row['status'] if row else 'unexecuted' for row in rows)
        if node['id'] not in plan['selected_modules']:
            status = 'skipped'
        elif counts['completed'] == len(windows) and not any(m['module_id'] == node['id'] for m in plan['skipped_methods']):
            status = 'completed'
        elif counts['failed'] == len(windows):
            status = 'failed'
        elif counts['skipped'] == len(windows):
            status = 'skipped'
        else:
            status = 'partial'
        modules.append({'id': node['id'], 'name': node['name'], 'status': status,
                        'reason': '逐窗状态汇总；任何缺失或失败不会解释为正常。',
                        'summary': {'window_status_counts': dict(counts), 'window_count': len(windows)},
                        'duration_seconds': sum(row.get('duration_seconds', 0) for row in rows if row),
                        'artifacts': ['coverage.json', 'window-results.json']})
    return modules


def render_recording_report(result, path):
    esc = lambda v: html.escape(str(v), quote=True)
    c = result['coverage']
    rows = []
    labels = {'completed': '计算完成', 'partial': '部分可评', 'failed': '失败', 'not_run': '未执行', 'cancelled': '已取消', 'running': '执行中'}
    for window in result['windows']:
        links = ' · '.join(f'<a href="{esc(window[key])}">{title}</a>' for key, title in [('report_artifact', '报告'), ('result_artifact', 'JSON')] if window.get(key))
        rows.append(f'<tr><td>{esc(window["id"])}</td><td>{window["start_seconds"]:g}–{window["start_seconds"] + window["duration_seconds"]:g}</td><td>{esc(labels.get(window["status"], window["status"]))}</td><td>{links}</td><td>{esc(window.get("error", ""))}</td></tr>')
    warning = ''.join('<li>' + esc(w) + '</li>' for w in result['warnings'])
    gaps = ''.join(f'<li>{g["start_seconds"]:g}–{g["start_seconds"] + g["duration_seconds"]:g} 秒：来源声明缺口，未评估。</li>' for g in result['coverage_plan']['gaps'])
    module_rows = ''.join(f'<tr><td>{esc(m["id"])} {esc(m["name"])}</td><td>{esc(labels.get(m["status"], m["status"]))}</td><td>{esc(json.dumps(m["summary"]["window_status_counts"], ensure_ascii=False))}</td></tr>' for m in result['modules'])
    path.write_text(f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>整记录质控报告</title>
<style>body{{font:16px/1.7 system-ui,sans-serif;background:#f3f7fc;color:#18334c}}main{{max-width:1100px;margin:auto;padding:24px}}section,header{{background:white;padding:24px;margin:18px 0;border:1px solid #d4dfed;border-radius:10px}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:9px;text-align:left;border-bottom:1px solid #dce5ee;vertical-align:top}}a{{color:#1459ac}}.scroll{{overflow-x:auto}}.note{{border-left:4px solid #d89430;padding-left:16px}}@media print{{body{{background:white}}section,header{{break-inside:avoid}}}}</style><main>
<header><p>整记录分块质控 · 原生时钟</p><h1>{esc(result.get('label', '记录'))}</h1><p class="note">总分未校准 · 待人工复核。覆盖率是执行范围，不是质量合格率。</p>
<p>记录 {c['total_seconds']:g} 秒；完成计算 {c['completed_seconds']:g} 秒（{c['execution_percent']:.2f}%）；失败 {c['failed_seconds']:g} 秒；未执行 {c['unexecuted_seconds']:g} 秒；来源缺口 {c['gap_seconds']:g} 秒。</p><p>来源核验：{esc(result.get('source_integrity', 'unverified'))}。可用样本执行覆盖 {c['available_execution_percent']:.2f}%；所有已选模块均计算完成的范围 {c['fully_assessed_percent']:.2f}%，仍不代表质量合格。</p></header>
<section><h2>窗口与证据</h2><div class="scroll"><table><thead><tr><th>窗口</th><th>原始秒</th><th>状态</th><th>证据</th><th>原因</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section>
<section><h2>模块汇总</h2><div class="scroll"><table><tbody>{module_rows}</tbody></table></div></section>
<section><h2>覆盖与候选索引</h2><p><a href="coverage.json">覆盖明细</a> · <a href="candidate-index.json">{len(result['candidate_index'])} 个原始候选索引</a> · <a href="plan.json">冻结计划</a></p><ul>{gaps}</ul><p>候选按窗口保留原始时间和源通道身份；尚未自动合并跨窗重复/相邻事件，也不自动删除数据。</p><ul>{warning}</ul></section></main></html>''', encoding='utf-8')


def execute_recording(request, job_dir, emit, *, window_runner=None, cancel_requested=None, source_context=None):
    """Run serially; a cancel.requested file enables cooperative cancellation.

    A hard process kill leaves recording-progress.json with explicit running /
    not_run windows. The service must not promote that checkpoint to a result.
    """
    from .planning import build_plan
    from .runtime import _execute_window
    record = request['input']; supplied = request.get('plan') or {}
    plan = build_plan(record, request.get('selected_modules', supplied.get('selected_modules')),
                      request.get('qc_config', supplied.get('qc_config')))
    if plan.get('scope') != 'recording' or supplied and supplied.get('plan_id') != plan['plan_id']:
        raise ValueError('Submitted recording plan differs from input or configuration')
    root = Path(job_dir).resolve(); source = Path(record['source_path']).resolve()
    if root == source or root in source.parents or source in root.parents:
        raise ValueError('Job outputs must be separate from the original input file')
    root.mkdir(parents=True, exist_ok=True)
    if (root / 'result.json').exists() or (root / 'recording-progress.json').exists():
        raise FileExistsError('Recording job directory already contains a run; use a new directory')
    artifacts = root / 'artifacts'; artifacts.mkdir(exist_ok=True)
    _save(artifacts / 'plan.json', plan)
    windows = [{**copy.deepcopy(w), 'status': 'not_run', 'modules': []} for w in plan['windows']]
    started = time.time(); cancelled = False; fatal = None; own_reader = False; source_verified = False
    check_cancel = lambda: (root / 'cancel.requested').exists() or bool(cancel_requested and cancel_requested())
    progress = {'schema_version': 'ephys-recording-progress/1.0', 'scope': 'recording', 'plan_id': plan['plan_id'],
                'status': 'running', 'windows': windows, 'window_count': len(windows), 'started_at_unix': started}

    def checkpoint():
        progress.update(coverage=coverage(plan, windows), updated_at_unix=time.time())
        _save(root / 'recording-progress.json', progress)

    checkpoint()
    try:
        if source_context is None and window_runner is None:
            from .readers import open_reader
            reader = open_reader(source, str(record['id'])); own_reader = True
            description = reader.describe()
            digest = next(item['sha256'] for item in description['source_files'] if Path(item['path']).resolve() == source)
            source_context = {'reader': reader, 'sha256': digest}
        runner = window_runner or _execute_window
        for window in windows:
            if check_cancel():
                cancelled = True
                break
            directory = root / 'windows' / window['id']; directory.mkdir(parents=True)
            child_config = window_config(plan, window)
            child_plan = build_plan(record, plan['selected_modules'], child_config)
            if child_plan['plan_id'] != window['plan_id']:
                raise ValueError('Frozen child plan identity changed')
            child_request = {'input': record, 'plan': child_plan, 'qc_config': child_plan['qc_config'],
                             'selected_modules': child_plan['selected_modules']}
            _save(directory / 'request.json', child_request)
            window['status'] = 'running'; checkpoint()

            def child_emit(module_id, status, message):
                existing = next((m for m in window['modules'] if m['id'] == module_id), None)
                if existing is None:
                    node = next(n for n in child_plan['nodes'] if n['id'] == module_id)
                    existing = {'id': module_id, 'name': node['name'], 'duration_seconds': 0, 'artifacts': []}
                    window['modules'].append(existing)
                existing.update(status=status, reason=message)
                checkpoint()
                # Main-job node remains running until all windows finish.
                emit(module_id, 'running', f'窗口 {window["index"] + 1}/{len(windows)} · {status} · {message}')

            try:
                child = runner(child_request, directory, child_emit, source_context=source_context, cancel_requested=check_cancel)
                loaded = child.get('recording', {})
                if loaded.get('start_sample') is not None and (loaded['start_sample'] != window['start_sample'] or loaded.get('stop_sample') != window['stop_sample']):
                    raise ValueError('Loaded source sample bounds differ from frozen recording window')
                window.update(status=child['status'], modules=copy.deepcopy(child['modules']), data_sha256=child.get('data_sha256'))
                if child.get('source_sha256'):
                    window['source_sha256'] = child['source_sha256']
            except RecordingCancelled as error:
                window.update(status='cancelled', error=str(error)); cancelled = True
            except Exception as error:
                window.update(status='failed', error=f'{type(error).__name__}: {error}')
                _save(directory / 'window-error.json', {'error': window['error']})
            _export_window(window, directory, artifacts)
            checkpoint()
            if cancelled:
                break
        if source_context:
            source_context['reader'].assert_unchanged(hashes=True)
            source_verified = True
    except Exception as error:
        fatal = f'{type(error).__name__}: {error}'
    finally:
        if own_reader and source_context:
            source_context['reader'].close()
    candidate_index = []
    for window in windows:
        if (root / 'windows' / window['id']).exists():
            candidate_index.extend(_candidate_entries(window, root / 'windows' / window['id']))
    cov = coverage(plan, windows)
    modules = _modules(plan, windows)
    status = 'failed' if fatal or all(w['status'] == 'failed' for w in windows) else 'cancelled' if cancelled else 'partial' if any(w['status'] != 'completed' for w in windows) or plan['skipped_methods'] or cov['gap_samples'] else 'completed'
    result = {'schema_version': 'ephys-recording-result/1.0', 'scope': 'recording', 'status': status,
              'plan_id': plan['plan_id'], 'label': record.get('label', record['id']), 'qc_config': plan['qc_config'],
              'selected_modules': plan['selected_modules'], 'modules': modules, 'windows': windows,
              'window_count': len(windows), 'coverage': cov, 'coverage_plan': plan['coverage_plan'],
              'skipped_methods': plan['skipped_methods'], 'candidate_index': candidate_index,
              'score': {'value': None, 'label': '未校准', 'reason': '覆盖与执行状态不是信号质量评分。'},
              'review_status': 'pending', 'source_sha256': source_context.get('sha256') if source_context else None,
              'source_integrity': 'verified_after_run' if source_verified else 'verification_incomplete',
              'source_files': [{k: v for k, v in item.items() if k != 'path'} for item in source_context['reader'].source_files] if source_context else [],
              'warnings': plan['warnings'] + ([fatal] if fatal else []) + (['任务已取消；未执行窗口保留，不计入覆盖。'] if cancelled else []),
              'recording': {'channel_count': plan['coverage_plan']['channel_count'], 'sampling_rate_hz': plan['coverage_plan']['sampling_rate_hz'],
                            'start_seconds': 0.0, 'duration_seconds': plan['coverage_plan']['total_seconds'],
                            'source_indices': plan['qc_config']['selection']['eeg_indices'], 'unit': 'V'},
              'input_metadata': plan['input_metadata'], 'input_modality': plan['input_modality'], 'input_lineage': plan.get('input_lineage', {}),
              'input_provenance': plan['input_provenance'], 'input_data_usage': plan['input_data_usage'],
              'data_tags': plan['data_tags'], 'method_applicability': plan['method_applicability'], 'extensions': [],
              'report_path': 'artifacts/report.html', 'artifacts': [], 'duration_seconds': time.time() - started}
    _save(artifacts / 'coverage.json', cov)
    _save(artifacts / 'candidate-index.json', candidate_index)
    _save(artifacts / 'window-results.json', windows)
    render_recording_report(result, artifacts / 'report.html')
    result['artifacts'] = [{'name': p.name, 'bytes': p.stat().st_size, 'kind': 'image' if p.suffix == '.png' else 'report' if p.suffix == '.html' else 'json'} for p in sorted(artifacts.iterdir()) if p.is_file()]
    progress['status'] = status; checkpoint()
    _save(root / 'result.json', result)
    for module in modules:
        emit(module['id'], module['status'], module['reason'])
    return result
