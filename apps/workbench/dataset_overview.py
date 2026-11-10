"""Workbench adapter for result snapshots. Source data are not reread on page polling."""
import copy
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from ephys_qc.dataset_qc.overview import aggregate_overview
from package_jobs import fingerprint


def read_signal_summary(path):
    """Read execution coverage without loading candidates or rebuilding scores.

    A recording result can contain hundreds of MB of candidate observations.
    Dataset navigation needs only frozen coverage and module execution states.
    Parsing to EOF also keeps a truncated result from counting as a report.
    """
    import ijson
    result = {'coverage': {}, 'recording': {}, 'modules': []}
    module = None
    coverage_fields = {'total_seconds', 'completed_seconds', 'failed_seconds',
                       'unexecuted_seconds', 'gap_seconds'}
    try:
        with Path(path).open('rb') as handle:
            for prefix, event, value in ijson.parse(handle, use_float=True):
                if event in {'string', 'number', 'boolean', 'null'}:
                    if prefix in {'schema_version', 'scope', 'status', 'analysis_profile'}:
                        result[prefix] = value
                    elif prefix.startswith('coverage.') and prefix[9:] in coverage_fields:
                        result['coverage'][prefix[9:]] = value
                    elif prefix in {'recording.start_seconds', 'recording.duration_seconds'}:
                        result['recording'][prefix.split('.')[1]] = value
                    elif module is not None and prefix in {'modules.item.id', 'modules.item.name', 'modules.item.status'}:
                        module[prefix.split('.')[-1]] = value
                elif prefix == 'modules.item' and event == 'start_map':
                    module = {}
                elif prefix == 'modules.item' and event == 'end_map':
                    if module and 'id' in module and 'status' in module:
                        result['modules'].append(module)
                    module = None
    except ijson.JSONError as error:
        raise ValueError('Incomplete recording result') from error
    if not result.get('schema_version') or result.get('scope') not in {'window', 'recording'}:
        raise ValueError('Missing recording result structure')
    return result


def recording_display(store, job, item):
    """Small measurements already saved by the runner; no waveforms reread."""
    meta = item.get('metadata', {})
    config = job.get('plan', {}).get('qc_config', item.get('default_config', {}))
    indices = config.get('selection', {}).get('eeg_indices', [])
    channels = [c for c in meta.get('channels', []) if c['index'] in indices]
    rates = sorted({c['sampling_rate_hz'] for c in channels})
    display = {'format': meta.get('format'), 'channels': len(channels),
               'duration_seconds': meta.get('duration_seconds'), 'rates_hz': rates,
               'summary_available': False}
    path = store.root / 'jobs' / job['id'] / 'artifacts' / 'window-results.json'
    if path.is_file() and path.stat().st_size <= 8 * 1024 * 1024:
        windows = json.loads(path.read_text())
        by_id = lambda mid: [m.get('summary', {}) for w in windows for m in w.get('modules', []) if m['id'] == mid]
        continuity, spectra, muscle = by_id('M03'), by_id('M04'), by_id('M06')
        display.update(summary_available=True, windows=len(windows),
            nonfinite_samples=(sum(m['nonfinite_sample_count'] for m in continuity)
                               if continuity and all('nonfinite_sample_count' in m for m in continuity) else None),
            line_detected=any(m.get('line_flagged_observations', 0) > 0 for m in spectra),
            hf_candidates=sum(m.get('high_frequency_candidate_count', 0) for m in muscle),
            psd_channels=min((m.get('psd_computed_channel_count', 0) for m in spectra), default=0),
            candidate_details_truncated=any(m.get('candidate_details_truncated') for m in continuity))
    return display


def source_match(item, source_root, dataset_result):
    if not dataset_result: return 'unverified'
    files = {f['path']: f for f in dataset_result['inventory']['files']}
    expected = item.get('expected_source_files') or []
    if not expected: return 'unverified'
    for file in expected:
        try: name = Path(file['path']).relative_to(Path(source_root)).as_posix()
        except (ValueError, TypeError): return 'mismatch'
        actual = files.get(name)
        if not actual or not actual.get('sha256'): return 'mismatch'
        if actual['sha256'] != file.get('sha256'): return 'mismatch'
    return 'matched'


def build_overview(store, package_id, job_id=None):
    package, current = store.packages._plan(package_id)
    manifest, dataset_result, dataset_job = current, None, None
    root = package['root']
    with store.packages.lock:
        jobs = copy.deepcopy(list(store.packages.jobs.values()))
    if job_id:
        dataset_job = store.packages.get(job_id)
        if dataset_job['package_id'] != package_id: raise ValueError('报告不属于当前数据集。')
        request = json.loads((store.packages.root / job_id / 'request.json').read_text())
        manifest, root = request['expectations'], request['source_root']
    else:
        eligible = [j for j in jobs if j['package_id'] == package_id and j['manifest_hash'] == fingerprint(current)
                    and (not hasattr(store, 'library_state') or not store.library_state.report_archived(j, package=True))]
        dataset_job = max(eligible, key=lambda j: j['created_at']) if eligible else None
    if dataset_job and dataset_job['status'] == 'completed':
        dataset_result = json.loads(store.packages.artifact(dataset_job['id'], 'result.json').read_text())
        request = json.loads((store.packages.root / dataset_job['id'] / 'request.json').read_text())
        root = request['source_root']
    manifest_hash = fingerprint(manifest)
    with store.lock:
        signal_jobs = copy.deepcopy(list(store.jobs.values()))
    selected = {}
    for job in signal_jobs:
        if not job_id and hasattr(store, 'library_state') and store.library_state.report_archived(job):
            continue
        context = job.get('dataset_context') or {}
        if context.get('package_id') != package_id or context.get('manifest_hash') != manifest_hash: continue
        rid = context.get('record_id')
        if rid not in selected or job['created_at'] > selected[rid]['created_at']: selected[rid] = job
    signals = {}
    for rid, job in selected.items():
        signal = {'job': job}
        try:
            item = json.loads((store.root / 'jobs' / job['id'] / 'request.json').read_text())['input']
            signal['source_status'] = source_match(item, root, dataset_result)
            if job['status'] == 'completed': signal['display'] = recording_display(store, job, item)
            if job['status'] == 'completed': signal['result'] = store.dataset_result(job['id'])
        except (OSError, ValueError, KeyError, TypeError):
            signal['result_error'] = True
        signals[rid] = signal
    result = aggregate_overview(manifest, dataset_job, dataset_result, signals)
    for row in result['records']:
        row['display'] = signals.get(row['id'], {}).get('display', {})
    result['source'] = manifest.get('source', {})
    result['example'] = next((copy.deepcopy(e) for e in store.settings.get('demo_examples', []) if e.get('package_id') == package_id), None)
    result.update(package_id=package_id, label=package['label'], manifest_hash=manifest_hash,
                  current_manifest=manifest_hash == fingerprint(current), generated_at=datetime.now(timezone.utc).isoformat(),
                  result_basis='saved_source_fingerprints', signal_jobs=[j['id'] for j in selected.values()])
    return result


def render_overview(data, language='zh-CN'):
    from dataset_report import render
    return render(data, language)
