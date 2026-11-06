"""Group frozen EEG reports by declared, reproducible comparison conditions."""
import copy
import hashlib
import json
import math

VERSION = 'report-comparison/1'


def signature(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def comparison_row(job, request, view, environments):
    record, config = request['input'], request['qc_config']
    selection = config.get('selection', {})
    by_index = {c['index']: c for c in record['metadata']['channels']}
    channels = [by_index[i] for i in selection.get('eeg_indices', [])]
    prep = record.get('preprocessing') or {}
    unknown = []
    reference = record.get('reference_scheme')
    if reference in (None, '', 'unknown', 'unspecified'):
        unknown.append('参考方式未确认')
    if prep.get('verified') is not True:
        unknown.append('处理史未确认')
    if not environments:
        unknown.append('执行版本缺失')
    names = [c['name'] for c in channels]
    if not channels or len(names) != len(set(names)):
        unknown.append('通道身份无法唯一对齐')
    methods = copy.deepcopy(config.get('method_config', {}))
    groups = methods.pop('comparison_groups', None)
    # Group names are arbitrary; retain their actual membership, by channel name.
    partitions = {}
    if groups:
        for name, group in zip(names, groups):
            partitions.setdefault(str(group), []).append(name)
    groups = sorted(sorted(v) for v in partitions.values())
    score = view.get('score') or {}
    envs = []
    for env in environments:
        envs.append({'implementation': env.get('implementation'), 'packages': env.get('packages'),
                     'sources': {k: v.get('sha256') for k, v in env.get('actual_executed_sources', {}).items()},
                     'upstream': {k: v.get('sha256') for k, v in env.get('method_sources', {}).items()}})
    envs = sorted({signature(e): e for e in envs}.values(), key=signature)
    conditions = {'modality': record.get('modality'), 'reference': reference,
                  'channels': sorted((c['name'], c.get('sampling_rate_hz'), c.get('unit'), c.get('type')) for c in channels),
                  'comparison_groups': groups, 'processing': {k: prep.get(k) for k in ('verified', 'highpass_hz', 'lowpass_hz', 'notch_hz')},
                  'methods': methods, 'selected_modules': sorted(request.get('selected_modules', [])),
                  'feature_config': config.get('feature_config'), 'policy_config': config.get('policy_config'),
                  'context': config.get('context_tags', {}), 'scope': config.get('scope', 'window'),
                  'duration': record['metadata'].get('duration_seconds') if config.get('scope') == 'recording' else selection.get('duration_seconds'),
                  'recording_options': config.get('recording_options'), 'score_version': score.get('version'),
                  'execution': envs}
    components = []
    for c in score.get('components', []):
        value = c.get('value')
        components.append({k: c.get(k) for k in ('id', 'name', 'numerator', 'denominator', 'unit', 'assessed_channels', 'affected_channels')} | {
            'value': value if type(value) in (int, float) and math.isfinite(value) else None})
    return {'job_id': job['id'], 'label': job['label'], 'conditions': conditions,
            'condition_id': signature(conditions), 'unknown': unknown, 'components': components,
            'score': score.get('value'), 'score_version': score.get('version'),
            'coverage_complete': score.get('coverage_complete', False),
            'report_url': '/api/v1/jobs/' + job['id'] + '/report'}


def compare(rows):
    groups = {}
    for row in rows:
        key = row['condition_id']
        groups.setdefault(key, {'id': key, 'conditions': row['conditions'], 'rows': []})['rows'].append(row)
    for group in groups.values():
        group['comparable'] = len(group['rows']) > 1 and not any(r['unknown'] for r in group['rows'])
        group['component_ids'] = sorted(set.intersection(*[{c['id'] for c in r['components'] if c['value'] is not None} for r in group['rows']]))
    return {'version': VERSION, 'groups': list(groups.values()), 'record_count': len(rows),
            'interpretation': '仅比较相同条件下的项目试行指标；缺项显示未评，不生成跨组排名。'}
