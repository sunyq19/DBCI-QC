"""Versioned EEG rule/evidence index, independent of detector and web runtimes.

This records what was actually executed. It never certifies conformance, turns
module execution states into quality labels, or fills absent metrics with zero.
"""
import copy
from collections import Counter
import hashlib
import html
import json
from pathlib import Path


CATALOG_PATH = Path(__file__).parent / 'specifications' / 'eeg-basic.v1.json'


def catalog_bytes():
    return CATALOG_PATH.read_bytes()


def load_catalog():
    return json.loads(catalog_bytes())


def _sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _read_evidence(artifacts, name):
    # Catalog names are package-owned, but keep this boundary explicit.
    if Path(name).name != name:
        raise ValueError('Evidence must be an artifact filename')
    path = artifacts / name
    if not path.is_file():
        return None
    if path.resolve().parent != artifacts.resolve():
        raise ValueError('Evidence must remain inside the artifact directory')
    return json.loads(path.read_text(encoding='utf-8'))


def _measurements(identifier, payloads, module):
    """Small direct observations; full precision/per-channel data stay upstream."""
    def take(payload, fields):
        return {key: copy.deepcopy(payload[key]) for key in fields if key in payload}
    if identifier == 'EEG-001':
        return take(payloads.get('M01_input.json', {}), ('source_sha256', 'reader_id', 'reader_version', 'warnings'))
    if identifier == 'EEG-002':
        return take(payloads.get('M02_selection.json', {}), ('recording', 'comparison_groups', 'processing_applied'))
    if identifier == 'EEG-003':
        payload = payloads.get('M03_continuity.json', {})
        return ({'candidate_interval_count': len(payload['candidates']),
                 'kinds': dict(Counter(row.get('kind', 'unknown') for row in payload['candidates']))}
                if 'candidates' in payload else {})
    if identifier == 'EEG-004':
        psd = payloads.get('M04_spectral.json', {}).get('psd', {})
        return take(psd, ('status', 'estimator'))
    if identifier == 'EEG-005':
        line = payloads.get('M04_spectral.json', {}).get('line_noise', {})
        value = take(line, ('status', 'reason', 'settings', 'multiplicity', 'unavailable_fundamentals', 'tail_samples'))
        if 'observations' in line:
            value.update(observation_count=len(line['observations']),
                         flagged_observation_count=sum(bool(r.get('flagged')) for r in line['observations']))
        return value
    if identifier == 'EEG-006':
        fits = payloads.get('M04_spectral.json', {}).get('parameterization', {})
        return {scope + '_status_counts': dict(Counter(row.get('status', 'unknown') for row in fits[scope]))
                for scope in ('full', 'windows') if scope in fits}
    if identifier == 'EEG-007':
        payload = payloads.get('M05_bad_channels.json', {})
        value = take(payload, ('groups', 'unwindowed_tail'))
        if 'candidates' in payload:
            value['candidate_entry_count'] = len(payload['candidates'])
        return value
    if identifier == 'EEG-008':
        kinds = payloads.get('M06_auxiliary_events.json', {}).get('by_kind', {})
        values = {}
        for kind, value in kinds.items():
            observed = take(value, ('status', 'reason', 'detected_event_count', 'averaged_event_count', 'complete_epoch_count', 'boundary_excluded_count'))
            if value.get('status') not in {'computed', 'no_events', 'no_complete_epochs'}:
                # Upstream initializes counts to zero before prerequisite checks.
                # Keep raw evidence, but do not present placeholders as measurements.
                for key in list(observed):
                    if key.endswith('_count'):
                        observed[key] = None
                observed['count_interpretation'] = 'not_measured; upstream initialization is not a zero-event finding'
            values[kind] = observed
        return values
    if identifier == 'EEG-009':
        payload = payloads.get('M06_muscle.json', {})
        value = take(payload, ('status', 'reason'))
        if 'reference' in payload:
            value['reference'] = take(payload['reference'], ('status', 'reason'))
        if 'candidates' in payload:
            evaluated = (payload.get('status') in {'ok', 'partial_channels'} and
                         any(c.get('status') == 'ok' and c.get('valid_seconds', 0) > 0
                             for c in payload.get('channels', [])))
            value['candidate_interval_count'] = len(payload['candidates']) if evaluated else None
            if not evaluated:
                value['count_interpretation'] = 'not_measured; no usable high-frequency assessment coverage'
        return value
    if identifier == 'EEG-010':
        return take(payloads.get('M07_annotations.json', {}), ('format', 'label_scope', 'selected_count', 'covered_seconds', 'issues', 'quality_ground_truth'))
    if identifier == 'EEG-011':
        return take(payloads.get('M08_assessment.json', {}), ('score', 'source_unchanged', 'missing_capabilities'))
    return take(payloads.get('environment.json', {}), ('implementation', 'packages'))


def attach_eeg_assessment(result, artifacts):
    """Attach a frozen index for new scalp-EEG runs; leave other routes untouched.

    Recording-level rows describe window execution only. Each executed child
    retains its own effective parameters and measurements; no cross-window
    detector equivalence or prevalence estimate is manufactured here.
    """
    from .modalities import ROUTES
    if result.get('analysis_profile') != ROUTES['scalp_eeg']['profile']:
        return None
    artifacts = Path(artifacts)
    raw = catalog_bytes()
    catalog = json.loads(raw)
    modules = {row['id']: row for row in result.get('modules', [])}
    recording = result.get('scope') == 'recording'
    payloads = {}
    evidence = {}
    names = (['window-results.json', 'coverage.json'] if recording else
             sorted({name for check in catalog['checks'] for name in check['artifacts']}))
    for name in names:
        payload = _read_evidence(artifacts, name)
        if payload is not None:
            payloads[name] = payload
            evidence[name] = {'artifact': name, 'sha256': _sha(artifacts / name)}
    checks = []
    for definition in catalog['checks']:
        module = modules.get(definition['module_id'], {})
        files = names if recording else definition['artifacts']
        observed = [name for name in files if name in evidence]
        parameters = {}
        for name in observed:
            payload = payloads[name]
            if isinstance(payload, dict):
                for key in ('parameters', 'config', 'preprocessing'):
                    if key in payload:
                        parameters[name + '#' + key] = payload[key]
        checks.append({
            'id': definition['id'], 'title': definition['title'],
            'module_id': definition['module_id'], 'source_ids': definition['source_ids'],
            'module_status': module.get('status', 'not_run'),
            'module_reason': module.get('reason', 'Module result is absent'),
            'observation_scope': 'window_execution_summary' if recording else 'selected_window',
            'evidence': [{**evidence[name], 'fields': [] if recording else definition['evidence_fields']} for name in observed],
            'evidence_status': 'recorded' if observed else 'not_recorded',
            'parameters': parameters,
            'measurement_summary': (copy.deepcopy(module.get('summary', {})) if recording else
                                    _measurements(definition['id'], payloads, module)),
        })
    assessment = {
        'schema_version': 'eeg-assessment/1', 'catalog_version': catalog['version'],
        'specification_version': catalog['specification_version'],
        'catalog_sha256': hashlib.sha256(raw).hexdigest(),
        'claim': 'project_rule_traceability_only', 'conformance': None,
        'intended_population': catalog['scope'],
        'population_confirmation': 'not_captured_by_runtime',
        'population_reason': 'Species and recording-site source confirmation are not yet a structured runtime gate; no human-population conformance is inferred.',
        'scope': result.get('scope', 'window'), 'plan_id': result.get('plan_id'),
        'score_calibrated': False, 'expert_accuracy_validated': False,
        'checks': checks,
        'optional_methods': copy.deepcopy(result.get('extensions', [])),
        'child_results': [w['result_artifact'] for w in result.get('windows', []) if w.get('result_artifact')],
        'review_state_at_generation': result.get('review_status', 'pending'),
        'catalog_artifact': 'eeg-rules.json',
    }
    if recording:
        # Child JSON stays byte-identical while flat exports rename files.
        assessment['child_artifact_maps'] = []
        exported = {p.name for p in artifacts.iterdir() if p.is_file()}
        for window in result.get('windows', []):
            prefix = window['id'] + '--'
            assessment['child_artifact_maps'].append({
                'window_id': window['id'], 'result_artifact': window.get('result_artifact'),
                'report_artifact': window.get('report_artifact'),
                'artifacts': {name[len(prefix):]: name for name in sorted(exported) if name.startswith(prefix)},
            })
    # Match the exact bytes whose digest was recorded; preserve old runs intact.
    (artifacts / 'eeg-rules.json').write_bytes(raw)
    (artifacts / 'eeg-assessment.json').write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    result['eeg_assessment'] = assessment
    return assessment


def render_eeg_assessment(result):
    """Compact disclosure: rule index with frozen evidence, not a pass badge."""
    assessment = result.get('eeg_assessment')
    if not assessment:
        return ''
    esc = lambda value: html.escape(str(value), quote=True)
    labels = {'completed': '完成', 'partial': '部分可评', 'skipped': '跳过', 'failed': '失败', 'not_run': '未执行'}
    rows = []
    for item in assessment['checks']:
        evidence = ' · '.join(f'<a href="{esc(e["artifact"])}">{esc(e["artifact"])}</a>' for e in item['evidence']) or '无产物'
        rows.append(f'<tr><td><a href="/standards/eeg-checks#{esc(item["id"].lower())}">{esc(item["id"])}</a> {esc(item["title"]["zh"])}</td><td>{esc(item["module_id"])}</td><td>{esc(labels.get(item["module_status"], item["module_status"]))}</td><td>{evidence}</td></tr>')
    whole = '<p>整记录状态仅汇总逐窗执行；有效参数和测量范围见各窗口报告。未合并跨窗候选。</p>' if assessment['scope'] == 'recording' else ''
    return f'''<section class="eeg-rule-index"><h2>EEG 检查依据</h2>
<p class="muted">项目规范 {esc(assessment['specification_version'])} · 词条 {esc(assessment['catalog_version'])} · 证据索引</p>
<p>尚未确认完整物种与记录位置字段；以下保留实际检查证据，不表示通过本专项规范或质量合格。</p>{whole}
<details><summary>12 项检查与模块对应</summary><div style="overflow-x:auto"><table style="width:100%;text-align:left;font-size:14px"><thead><tr><th>检查词条</th><th>模块</th><th>模块执行</th><th>证据</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></details>
<p><a href="eeg-assessment.json">本次检查索引</a> · <a href="eeg-rules.json">本次词条快照</a> · <a href="/standards/eeg-evidence">来源依据</a> · <a href="/standards/eeg-report">报告要求</a></p></section>'''
