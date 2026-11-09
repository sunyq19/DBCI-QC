"""Compact, cached locations from frozen detector artifacts. Never runs QC.

Unlike the review/audit endpoint this index omits per-sample measurements and
unions overlapping intervals of the same check/channel within a source block.
Channel-only and across-channel detections retain their distinct scope.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

from review_workspace import BASE_ARTIFACTS, EXTENSION_ARTIFACTS, _mapping, _json

LABELS = {
    'raw_continuity_review': ('信号完整性', 'Signal integrity', '#b45309'),
    'line_noise': ('工频干扰', 'Line interference', '#b77908'),
    'high_frequency_burst': ('高频突发', 'HF bursts', '#8b5bb5'),
    'prep_nonspatial_review': ('PREP 通道候选', 'PREP channels', '#477882'),
    'gnosis_artifact': ('灵犀云 · 伪差区间', 'Gnosis artifacts', '#cf5c55'),
    'gnosis_low_band': ('灵犀云 · 低频异常', 'Gnosis low band', '#24968a'),
    'gnosis_high_band': ('灵犀云 · 高频异常', 'Gnosis high band', '#b55f92'),
    'gnosis_line_length': ('灵犀云 · 线长', 'Gnosis line length', '#596ba5'),
    'gnosis_psd_deviation': ('灵犀云 · 频谱差异', 'Gnosis PSD deviation', '#7f7953'),
    'mne_amplitude': ('MNE 幅度异常', 'MNE amplitude', '#b56b35'),
    'mne_muscle': ('MNE 高频伪迹', 'MNE muscle', '#6a64b0'),
    'fieldtrip_zvalue': ('FieldTrip 跳变', 'FieldTrip jumps', '#bd525d'),
}
PALETTE = ['#447d9a', '#8c6c4b', '#3d8b76', '#8866a3', '#b2646f', '#6b7c48']
FIELDS = {'channel_id', 'channel_name', 'channel_index', 'channel_indices', 'kind',
          'start_seconds', 'stop_seconds', 'analysis_range', 'localization', 'scope',
          'window_indices', 'flagged', 'status'}


def registry():
    from ephys_qc.score_registry import SPECS
    specs = {**BASE_ARTIFACTS, **EXTENSION_ARTIFACTS}
    labels = dict(LABELS)
    for row in SPECS.values():
        key = row['method_id']
        if row['reducer'] in {'core', 'prep', 'ieeg_numeric', 'np_numeric', 'np_constant', 'np_state', 'ieeg_stability'}:
            continue
        specs[f"{row['module_id']}_{key}.json"] = (row['module_id'], key)
        labels.setdefault(key, (row['name'], key.replace('_', ' '), PALETTE[len(labels) % len(PALETTE)]))
    return specs, labels


def read_locations(path):
    """Selective streaming; no giant muscle sample_metrics / spectrum arrays."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024**3:
        raise ValueError('location_evidence_unavailable')
    import ijson
    spectral = path.name == 'M04_spectral.json'
    muscle = path.name == 'M06_muscle.json'
    if not spectral and not muscle and path.stat().st_size < 16 * 1024**2:
        p = _json(path)
        p['candidates'] = [{k: v for k, v in r.items() if k in FIELDS} for r in p.get('candidates', [])]
        return p
    if spectral:
        rows, assessed = [], 0
        with path.open('rb') as handle:
            for r in ijson.items(handle, 'line_noise.observations.item', use_float=True):
                if type(r.get('flagged')) is not bool or r.get('status', 'computed') != 'computed': continue
                assessed += 1
                if r['flagged']: rows.append({k: v for k, v in r.items() if k in FIELDS})
        return {'candidates': rows, 'localization_assessed': assessed > 0}
    prefix = 'candidates'
    meta = {'candidates': []}
    row = None
    # Scalar candidate fields and small identity arrays only. Skipped spectral
    # scan arrays never materialize; M06's trailing sample_metrics are not read.
    array = None
    with path.open('rb') as handle:
        for where, event, value in ijson.parse(handle, use_float=True):
            if where == prefix + '.item' and event == 'start_map': row = {}
            elif row is not None:
                field = where.removeprefix(prefix + '.item.')
                if where == prefix + '.item' and event == 'end_map':
                    if not spectral or (row.get('flagged') is True and row.get('status', 'computed') == 'computed'):
                        meta['candidates'].append(row)
                    row = None
                elif field in FIELDS and event in {'string', 'number', 'boolean', 'null'}: row[field] = value
                elif field in FIELDS and event == 'start_array': array = field; row[field] = []
                elif array and field == array + '.item' and event in {'number', 'string'}: row[array].append(value)
                elif array and field == array and event == 'end_array': array = None
            elif where in {'status', 'candidate_details_truncated'} and event in {'string', 'boolean'}:
                meta[where] = value
            if muscle and where == prefix and event == 'end_array':
                break  # This schema places all identities before candidates.
    return meta


def _finite(v):
    return type(v) in (int, float) and math.isfinite(v)


def build(workspace):
    specs, labels = registry()
    groups = defaultdict(list)
    channels, methods, warnings = {}, {}, set()
    for directory, window_id, request in workspace._contexts():
        selection = _json(directory / 'artifacts' / 'M02_selection.json', {})
        # Read just module statuses, not the possibly huge result report_view.
        import ijson
        with (directory / 'result.json').open('rb') as f:
            states = {r['id']: r.get('status') for r in ijson.items(f, 'modules.item')}
        for filename, (module, method) in specs.items():
            path = directory / 'artifacts' / filename
            if not path.exists(): continue
            label, en, color = labels.get(method, (method, method, '#687c94'))
            m = methods.setdefault(method, dict(id=method, module_id=module, label=label, label_en=en,
                                                color=color, evidence_count=0, unavailable_blocks=0, locating_blocks=0))
            try:
                if states.get(module) == 'failed': raise ValueError('failed_module')
                payload = read_locations(path)
                if payload.get('localization_assessed') is False: continue
                if payload.get('status') in {'blocked', 'failed', 'skipped', 'unavailable'} or payload.get('calculated') is False:
                    raise ValueError('unavailable_method')
                m['locating_blocks'] += 1
                if payload.get('candidate_details_truncated') or payload.get('candidate_evidence', {}).get('truncated'):
                    warnings.add((method, 'stored_locations_incomplete'))
                mapping = _mapping(request, selection, payload)
                by_id = {r.get('channel_id'): r for r in mapping.values()}
                by_name = defaultdict(list)
                for r in mapping.values():
                    by_name[r.get('raw_name', r.get('adapter_name'))].append(r)
                    channels[r['channel_id']] = dict(id=r['channel_id'], name=r.get('raw_name', ''), source_index=r['source_index'])
                cfg = request.get('qc_config', request.get('plan', {}).get('qc_config', {})).get('selection', {})
                rec = selection.get('recording', {})
                left = rec.get('start_seconds', cfg.get('start_seconds', 0))
                duration = rec.get('duration_seconds', cfg.get('duration_seconds', 0))
                right = left + duration
                for raw in payload.get('candidates', []):
                    m['evidence_count'] += 1
                    found = []
                    if raw.get('channel_id') in by_id: found = [by_id[raw['channel_id']]]
                    else:
                        ids = raw.get('channel_indices', [raw.get('channel_index')])
                        found = [mapping[i] for i in ids if type(i) is int and i in mapping]
                    if not found and len(by_name.get(raw.get('channel_name'), [])) == 1:
                        found = by_name[raw['channel_name']]
                    scope = raw.get('localization', '')
                    aggregate = scope == 'interval_only' and raw.get('scope') in {'across_selected_channels', 'selected_channels', 'across_selected_eeg_channels'}
                    if not found and aggregate: found = list(mapping.values())
                    if not found:
                        warnings.add((method, 'unresolved_channel')); continue
                    a, b = raw.get('start_seconds'), raw.get('stop_seconds')
                    kind = raw.get('kind', method)
                    only = scope in {'channel_only', 'pair_only'} or (method == 'prep_nonspatial_review' and not raw.get('window_indices'))
                    timed = not only and _finite(a) and _finite(b) and b > a
                    localization = 'group_interval' if timed and aggregate else 'interval' if timed else 'channel'
                    if not timed: a, b = left, right
                    if not (_finite(a) and _finite(b) and b > a):
                        warnings.add((method, 'unresolved_time')); continue
                    # Keep paired and aggregate scope intact; no individual
                    # channel blame is inferred from a group-level interval.
                    channel_ids = tuple(sorted(r['channel_id'] for r in found))
                    groups[(method, channel_ids, localization, str(kind), window_id)].append([a, b])
            except (ValueError, TypeError, KeyError, OSError, OverflowError):
                m['unavailable_blocks'] += 1
                warnings.add((method, 'location_evidence_unavailable'))
    findings = []
    for (method, ids, loc, kind, wid), intervals in groups.items():
        merged = []
        for a, b in sorted(intervals):
            if merged and a <= merged[-1][1] + 1e-9: merged[-1][1] = max(b, merged[-1][1])
            else: merged.append([a, b])
        for a, b in merged:
            findings.append(dict(method=method, channels=list(ids), start=a, stop=b, localization=loc, kind=kind))
    findings.sort(key=lambda r: (r['start'], r['method'], r['channels'], r['stop']))
    for n, row in enumerate(findings): row['id'] = str(n)
    for m in methods.values(): m['location_count'] = sum(r['method'] == m['id'] for r in findings)
    return dict(schema_version='finding-locations/1', methods=[m for m in methods.values() if m['id'] != 'line_noise' or m['locating_blocks'] or m['unavailable_blocks']], channels=list(channels.values()),
                findings=findings, warnings=[dict(method=m, code=c) for m, c in sorted(warnings)],
                interval_convention='half_open', analysis_modified=False)


def locations(workspace):
    from presentation_cache import cached, stamps
    from review_workspace import __file__ as review_code
    paths = [Path(__file__), Path(review_code), workspace.root / 'request.json', workspace.root / 'result.json']
    paths += list((workspace.root / 'windows').glob('w*/result.json'))
    paths += list((workspace.root / 'windows').glob('w*/request.json'))
    paths += list((workspace.root / 'windows').glob('w*/artifacts/*.json'))
    paths += list((workspace.root / 'artifacts').glob('*.json'))
    raw = cached(workspace.root, 'finding-locations-v1', stamps(paths),
                 lambda: json.dumps(build(workspace), ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode())
    return json.loads(raw)
