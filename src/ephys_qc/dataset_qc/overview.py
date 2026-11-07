"""Combine frozen dataset checks and record results without inventing a cohort score.

The caller supplies resolved snapshots. No files, HTTP, or UI dependencies here.
"""
from collections import Counter
import copy
import math

from .presentation import attention_groups

VERSION = 'dataset-overview/1'


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def summarize_signal(snapshot):
    if not snapshot:
        return {'status': 'not_run', 'execution_status': 'not_run', 'scope': None, 'score': None,
                'components': [], 'full_duration_computed': False, 'report_available': False}
    job, result = snapshot['job'], snapshot.get('result') or {}
    status = job['status']
    source_status = snapshot.get('source_status', 'unverified')
    view = result.get('report_view') or {}
    coverage = result.get('coverage') or view.get('coverage') or {}
    scope = result.get('scope') or job.get('plan', {}).get('qc_config', {}).get('scope')
    score = view.get('score') or {}
    valid_report = status == 'completed' and bool(result) and not snapshot.get('result_error')
    usable = valid_report and source_status != 'mismatch'
    if not usable: score = {}
    value = score.get('value')
    full = usable and scope == 'recording' and all(finite(coverage.get(k)) for k in
            ('total_seconds', 'completed_seconds', 'failed_seconds', 'unexecuted_seconds', 'gap_seconds'))
    full = bool(full and coverage['total_seconds'] > 0 and coverage['failed_seconds'] == 0
                and coverage['unexecuted_seconds'] == 0 and coverage['gap_seconds'] == 0
                and coverage['completed_seconds'] >= coverage['total_seconds'] - 1e-6)
    components = [{k: c.get(k) for k in ('id', 'name', 'value')} for c in score.get('components', [])]
    for part in components:
        if not finite(part.get('value')): part['value'] = None
    incomplete = [{'id': m['id'], 'name': m.get('name', m['id']), 'status': m['status']}
                  for m in result.get('modules', job.get('modules', [])) if m.get('status') in ('partial', 'failed', 'blocked')]
    skipped = [m['id'] for m in result.get('modules', []) if m.get('status') == 'skipped']
    # A high score is never used to overwrite missing files, conflicts, or unassessed methods.
    effective = 'source_mismatch' if source_status == 'mismatch' else 'report_unavailable' if snapshot.get('result_error') else status
    return {'status': effective, 'execution_status': status, 'job_id': job['id'],
            'source_status': source_status, 'created_at': job.get('created_at'), 'scope': scope,
            'report_available': valid_report, 'usable_report': usable, 'full_duration_computed': full,
            'score': value if finite(value) and 0 <= value <= 100 and usable else None,
            'score_version': score.get('version'), 'components': components,
            'coverage': {k: coverage.get(k) if finite(coverage.get(k)) else None for k in ('total_seconds', 'completed_seconds', 'failed_seconds', 'unexecuted_seconds', 'gap_seconds')},
            'selection': {k: result.get('recording', {}).get(k) for k in ('start_seconds', 'duration_seconds')},
            'incomplete_modules': incomplete, 'skipped_modules': skipped,
            'findings': {'line_channels': (view.get('line') or {}).get('affected_channels'),
                         'hf_intervals': view.get('hf_candidate_count')},
            'report_url': f"/api/v1/jobs/{job['id']}/report" if valid_report else None,
            'run_url': f"/?job={job['id']}"}


def aggregate_overview(manifest, dataset_job=None, dataset_result=None, signals=None):
    signals = signals or {}
    bindings = manifest['consistency']['records']
    checks = copy.deepcopy((dataset_result or {}).get('checks', []))
    findings = [c for c in checks if c['status'] in ('conflict', 'review', 'unassessed')]
    bad_files = {f['path'] for f in (dataset_result or {}).get('inventory', {}).get('files', []) if f['status'] != 'present'}
    rows = []
    for record in bindings:
        linked_files = {record['path'], *record.get('metadata_json', [])}
        linked_files.update(record[k] for k in ('channels_tsv', 'participants_tsv', 'sessions_tsv', 'scans_tsv') if record.get(k))
        if record.get('events'): linked_files.add(record['events']['path'])
        related = []
        for check in findings:
            if check.get('records'):
                relevant = record['id'] in check['records']
            else:
                paths = set(check.get('files', []))
                if check['module'] == 'D01' and check['code'] == 'files': paths &= bad_files
                relevant = bool(linked_files & paths)
            if relevant: related.append(check)
        row = {k: record[k] for k in ('id', 'path', 'subject', 'session', 'group', 'modality', 'processing')}
        row.update(checks=dict(Counter(c['status'] for c in related)), finding_ids=[c['id'] for c in related],
                   signal=summarize_signal(signals.get(record['id'])))
        rows.append(row)
    subjects = []
    for subject in sorted({r['subject'] for r in rows}):
        subset = [r for r in rows if r['subject'] == subject]
        related_ids = {i for r in subset for i in r['finding_ids']}
        subjects.append({'id': subject, 'records': len(subset), 'sessions': len({r['session'] for r in subset}),
                         'findings': len(related_ids), 'reported': sum(bool(r['signal'].get('usable_report')) for r in subset),
                         'full_duration_computed': sum(r['signal']['full_duration_computed'] for r in subset),
                         'not_run': sum(r['signal']['status'] == 'not_run' for r in subset)})
    inventory = (dataset_result or {}).get('inventory', {})
    files = inventory.get('files', [])
    file_counts = dict(Counter(f['status'] for f in files)) if dataset_result else None
    module_counts = {mid: dict(Counter(c['status'] for c in checks if c['module'] == mid)) for mid in ('D01', 'D02', 'D03')}
    counts = dict(Counter(r['signal']['status'] for r in rows))
    return {'schema_version': VERSION, 'scope': manifest['scope'], 'records': rows, 'subjects': subjects,
            'comparison_groups': copy.deepcopy(manifest['consistency']['groups']),
            'checks': checks, 'findings': findings, 'module_counts': module_counts,
            'attention_groups': attention_groups(checks, rows),
            'dataset_job': {k: dataset_job.get(k) for k in ('id', 'status', 'created_at', 'ended_at', 'run_name')} if dataset_job else None,
            'summary': {'records': len(rows), 'subjects': len(subjects), 'expected_files': len(manifest['files']),
                        'file_counts': file_counts, 'dataset_assessed': dataset_result is not None,
                        'findings': dict(Counter(c['status'] for c in findings)),
                        'reported': sum(bool(r['signal'].get('usable_report')) for r in rows),
                        'full_duration_computed': sum(r['signal']['full_duration_computed'] for r in rows),
                        'signal_status_counts': counts,
                        'records_with_findings': sum(bool(r['finding_ids']) for r in rows)},
            'dataset_score': None,
            'interpretation': 'frozen_result_summary_not_current_file_revalidation_or_dataset_quality_score'}
