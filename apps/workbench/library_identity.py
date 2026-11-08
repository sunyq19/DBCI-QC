"""Content and workflow identities for browsing; never rewrites saved evidence."""
import copy
import hashlib
import json
import re


def canonical(value):
    if isinstance(value, dict):
        return {k: canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(v) for v in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def data_identity(record):
    """Exact file content only. Names/paths do not establish data identity.

    Companion files and selected NWB streams participate. Unknown fingerprints
    fall back to the declared record family, never a filename/shape heuristic.
    """
    main = record.get('expected_sha256', '')
    fallback = 'family:' + record.get('record_family', record['id'])
    if not isinstance(main, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', main):
        return fallback
    members = []
    for item in record.get('expected_source_files', []):
        sha = item.get('sha256', '')
        if not isinstance(sha, str) or not re.fullmatch(r'[a-fA-F0-9]{64}', sha):
            return fallback
        # Main-file membership is optional in historical manifests.
        if item.get('role') == 'main' or item.get('path') == record.get('source_path'):
            continue
        members.append((item.get('role', 'companion'), sha.lower()))
    meta = record.get('metadata', {})
    return 'content:' + digest({'main': main.lower(), 'members': sorted(members),
                                'format': meta.get('format'),
                                'stream': meta.get('selected_stream_id')})


def workflow_identity(job, record):
    plan = job.get('plan', {})
    config = copy.deepcopy(plan.get('qc_config'))
    if not isinstance(config, dict) or not plan.get('selected_modules'):
        # Old receipts without an executable configuration cannot be deduplicated.
        return 'run:' + job['id']
    method = config.get('method_config', {})
    if isinstance(method.get('extensions'), list):
        method['extensions'] = sorted(method['extensions'])
    annotation = record.get('annotation') or {}
    return 'workflow:' + digest({
        'schema': plan.get('schema_version'), 'profile': plan.get('analysis_profile'),
        'software': job.get('software_version', 'unrecorded'),
        'modules': sorted(plan['selected_modules']), 'config': config,
        'modality': record.get('modality'), 'reference': record.get('reference_scheme'),
        'preprocessing': record.get('preprocessing'),
        'annotation': {k: annotation.get(k) for k in ('expected_sha256', 'format', 'label_scope')},
    })


def workflow_groups(root, jobs, inputs, current_ids):
    groups = {}
    for job in sorted(jobs, key=lambda j: j['created_at'], reverse=True):
        record = inputs[job['input_id']]
        key = workflow_identity(job, record)
        config = job.get('plan', {}).get('qc_config', {})
        extensions = config.get('method_config', {}).get('extensions', [])
        is_gnosis = any(e.startswith('gnosis_') for e in extensions)
        family = 'gnosis' if is_gnosis else ('extended' if set(extensions)-{'mne_amplitude'} else 'basic')
        label = record.get('report_labels', {}).get(job['id'], {})
        default = {'gnosis':'灵犀云方案', 'basic':'基础方案', 'extended':'扩展方案'}[family]
        default_en = {'gnosis':'Gnosis workflow', 'basic':'Basic workflow', 'extended':'Extended workflow'}[family]
        available = job['status'] == 'completed' and (root/'jobs'/job['id']/'artifacts'/'report.html').is_file()
        run = {'job_id': job['id'], 'label': job.get('run_name') or label.get('zh-CN', default),
               'label_en': job.get('run_name') or label.get('en', default_en),
               'created_at': job['created_at'], 'status': job['status'],
               'input_revision': job.get('input_revision', record.get('record_revision', 1)),
               'report_available': available,
               'url': f"/api/v1/jobs/{job['id']}/report" if available else '/?job='+job['id']}
        if key not in groups:
            selection = config.get('selection', {})
            weights = config.get('scoring', {}).get('weights', {})
            selected_methods = set(extensions)
            blocked = [m for m in job.get('plan', {}).get('method_applicability', [])
                       if m.get('id') in selected_methods and m.get('status') == 'blocked']
            blocked_family = bool(is_gnosis and {e for e in extensions if e.startswith('gnosis_')} <=
                                  {m['id'] for m in blocked})
            groups[key] = {'id': key, 'label': run['label'], 'label_en': run['label_en'], 'method_family':family,
                           'requirements_unmet':blocked_family,
                           'requirement_notes':sorted({m.get('reason', '') for m in blocked}),
                           'scope': config.get('scope', 'window'),
                           'start_seconds': selection.get('start_seconds'),
                           'duration_seconds': selection.get('duration_seconds'),
                           'channels': len(selection.get('eeg_indices', [])),
                           'scored_items': sum(isinstance(v, (int, float)) and v > 0 for v in weights.values()),
                           'current_confirmation': False, 'runs': []}
        group = groups[key]
        group['current_confirmation'] |= job['input_id'] in current_ids
        group['runs'].append(run)
    for group in groups.values():
        group['latest'] = group['runs'][0]
        group['latest_report'] = next((r for r in group['runs'] if r['report_available']), None)
    return sorted(groups.values(), key=lambda g: (g['current_confirmation'], g['latest']['created_at']), reverse=True)
