"""Bounded, headless engineering acceptance over explicitly configured records.

Use the scientific Python environment. Examples::

    python scripts/validate_data_coverage.py --config .local/workbench.json \
        --output-dir ../work/data-coverage-new
    python scripts/validate_data_coverage.py --config records.json \
        --record-id example --scope recording --max-record-seconds 1800 \
        --max-total-seconds 1800 --output-dir ../work/whole-example-new

The default adopts the same metadata-based recommendation as the workbench.
Use --selection all-base for all base modules with configured extensions.
The recommendation, original declaration and execution plan are saved separately.
Partial assessment is not an execution failure and is never a quality score.
"""
import argparse
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
POLICIES = {'recommended': 'recommended_modules_and_parameters',
            'all-base': 'all_base_modules_with_configured_extensions'}


def read_json(path):
    def reject(value): raise ValueError('Non-finite JSON value: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=reject)


def save(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def load_records(path, selected_ids=None):
    path = Path(path).resolve(); content = read_json(path)
    if isinstance(content, dict):
        if 'inputs' in content and 'records' in content:
            raise ValueError('Use only one of inputs or records')
        content = content.get('records', content.get('inputs'))
    if not isinstance(content, list) or not content:
        raise ValueError('Configuration needs a nonempty records/inputs array')
    ids = [r.get('id') if isinstance(r, dict) else None for r in content]
    if any(not isinstance(id_, str) or not id_.strip() for id_ in ids) or len(set(ids)) != len(ids):
        raise ValueError('Record IDs must be nonempty and unique')
    selected = set(selected_ids or ids)
    if selected - set(ids): raise ValueError('Unknown record IDs: ' + ', '.join(sorted(selected - set(ids))))
    records = copy.deepcopy([r for r in content if r['id'] in selected])
    for record in records:
        def absolute(value):
            item = Path(value).expanduser()
            return str((path.parent / item).resolve() if not item.is_absolute() else item.resolve())
        record['source_path'] = absolute(record['source_path'])
        for item in record.get('expected_source_files', []): item['path'] = absolute(item['path'])
        annotation = record.get('annotation') or {}
        for key in ('path', 'source_path'):
            if annotation.get(key): annotation[key] = absolute(annotation[key])
    return records


def source_paths(record):
    paths = [Path(record['source_path']).resolve()]
    paths += [Path(item['path']).resolve() for item in record.get('expected_source_files', [])]
    annotation = record.get('annotation') or {}
    paths += [Path(annotation[k]).resolve() for k in ('path', 'source_path') if annotation.get(k)]
    return list(dict.fromkeys(paths))


def check_output(output, records):
    output = Path(output).resolve()
    if output.exists() or output == REPO or REPO in output.parents:
        raise ValueError('Choose a NEW output directory outside the repository')
    for record in records:
        for source in source_paths(record):
            if output == source or output in source.parents or source in output.parents:
                raise ValueError('Output overlaps an input or annotation')
    return output


def source_snapshot(record):
    return [{'path': str(path), 'sha256': digest(path)} for path in source_paths(record)]


def assert_registered(record, snapshot):
    observed = {item['path']: item['sha256'] for item in snapshot}
    expected = record.get('expected_sha256')
    if expected and observed[str(Path(record['source_path']).resolve())] != expected:
        raise ValueError('Source SHA-256 differs from registered source; it will not be re-baselined')
    for item in record.get('expected_source_files', []):
        if observed[str(Path(item['path']).resolve())] != item['sha256']:
            raise ValueError('A registered companion SHA-256 differs; it will not be re-baselined')


def integrity_after(folder):
    path = folder / 'sources-before.json'
    if not path.exists(): return None, []
    rows = []
    for item in read_json(path):
        try:
            after = digest(item['path'])
            rows.append({**item, 'after_sha256': after, 'unchanged': after == item['sha256']})
        except OSError as error:
            rows.append({**item, 'after_sha256': None, 'unchanged': False, 'error': str(error)})
    save(folder / 'sources-after.json', rows)
    return all(item['unchanged'] for item in rows), rows


def planned_seconds(plan):
    if plan['scope'] == 'recording': return float(plan['coverage_plan']['available_seconds'])
    return float(plan['qc_config']['selection']['duration_seconds'])


def record_summary(record, selection_policy='recommended'):
    metadata = record.get('metadata', {})
    selection = record.get('default_config', {}).get('selection', {})
    return {'record_id': record['id'], 'label': record.get('label', record['id']),
            'dataset_id': record.get('dataset_id', 'unknown'),
            'subject_id': record.get('subject_id', metadata.get('subject_id', 'unknown')) or 'unknown',
            'format': metadata.get('format', 'unknown'),
            'source_duration_seconds': metadata.get('duration_seconds'),
            'n_eeg': len(selection.get('eeg_indices', [])),
            'evaluated_seconds': 0., 'engineering_pass': False,
            'execution_policy': POLICIES[selection_policy], 'scientific_accuracy_not_evaluated': True}


def assess_result(result, plan, job, expected_source_hash):
    """Check evidence completeness, not agreement with any clinical labels."""
    issues = []
    def require(condition, message):
        if not condition: issues.append(message)
    require(result.get('status') in {'completed', 'partial'}, 'Execution failed or did not finish')
    require(result.get('plan_id') == plan['plan_id'], 'Result plan identity mismatch')
    require(result.get('source_sha256') == expected_source_hash, 'Result source fingerprint mismatch')
    require(set(result.get('selected_modules', [])) == set(plan['selected_modules']), 'Selected modules mismatch')
    require(result.get('score', {}).get('value') is None, 'Unexpected calibrated/global quality score')
    require((job / 'request.json').is_file(), 'Frozen request missing')
    require((job / 'result.json').is_file(), 'Result JSON missing')
    if (job / 'result.json').is_file():
        require(read_json(job / 'result.json') == result, 'Returned result differs from saved result')
    report = result.get('report_path')
    report_path = (job / report).resolve() if isinstance(report, str) else None
    safe_report = report_path is not None and job.resolve() in report_path.parents
    require(safe_report and report_path.is_file() and report_path.stat().st_size > 0, 'Nonempty local report missing')
    rows = result.get('modules', [])
    ids = [row.get('id') for row in rows]
    require(len(set(ids)) == len(ids) and set(ids) == {node['id'] for node in plan['nodes']}, 'Module rows missing or duplicated')
    for row in rows:
        require(row.get('status') in {'completed', 'partial', 'skipped', 'failed'}, f"{row.get('id')}: missing module status")
        require(row.get('status') != 'failed', f"{row.get('id')}: method execution failed")
        if row.get('status') in {'partial', 'skipped', 'failed'}:
            require(isinstance(row.get('reason'), str) and bool(row['reason'].strip()), f"{row.get('id')}: missing unassessed reason")
        require(not row.get('summary', {}).get('window_status_counts', {}).get('failed', 0), f"{row.get('id')}: hidden failed window")
    require(not any(e.get('status') == 'failed' for e in result.get('extensions', [])), 'Configured extension failed')
    if plan['scope'] == 'recording':
        coverage = result.get('coverage', {})
        required = ('total_seconds', 'available_seconds', 'completed_seconds', 'failed_seconds',
                    'running_seconds', 'unexecuted_seconds', 'gap_seconds')
        valid = all(isinstance(coverage.get(k), (int, float)) and math.isfinite(coverage[k]) and coverage[k] >= 0 for k in required)
        require(valid, 'Recording coverage incomplete')
        if valid:
            require(abs(sum(coverage[k] for k in ('completed_seconds', 'failed_seconds', 'running_seconds', 'unexecuted_seconds')) - coverage['available_seconds']) <= 1e-6, 'Available coverage does not partition')
            require(abs(coverage['available_seconds'] + coverage['gap_seconds'] - coverage['total_seconds']) <= 1e-6, 'Total coverage does not partition')
            require(all(coverage[k] == 0 for k in ('failed_seconds', 'running_seconds', 'unexecuted_seconds')), 'Recording contains failed or unexecuted samples')
        windows = result.get('windows', [])
        require(len(windows) == plan['window_count'], 'Window rows missing')
        require(all(w.get('status') in {'completed', 'partial'} for w in windows), 'A recording window did not finish')
        evaluated = coverage.get('completed_seconds', 0.)
    else:
        actual = result.get('recording', {}); selection = plan['qc_config']['selection']
        fs = actual.get('sampling_rate_hz') or 1.
        require(abs(actual.get('start_seconds', -1) - selection['start_seconds']) <= .5 / fs + 1e-9, 'Window start mismatch')
        require(abs(actual.get('duration_seconds', -1) - selection['duration_seconds']) <= .5 / fs + 1e-9, 'Window duration mismatch')
        evaluated = actual.get('duration_seconds', 0.) if any(r.get('id') == 'M02' and r.get('status') in {'completed', 'partial'} for r in rows) else 0.
        coverage = {'scope': 'window', 'planned_seconds': selection['duration_seconds'],
                    'evaluated_seconds': evaluated, 'whole_recording_claim': False,
                    'interpretation': 'execution_coverage_not_signal_quality'}
    return {'issues': issues, 'modules': [{'id': r['id'], 'status': r['status'], 'reason': r.get('reason', ''),
              'summary': r.get('summary', {})} for r in rows], 'coverage': coverage,
            'evaluated_seconds': evaluated, 'report': 'job/' + report if safe_report else None,
            'result': 'job/result.json', 'execution_status': result.get('status')}


def run_case(record, folder, *, scope=None, budget_seconds=900., selection_policy='recommended'):
    from ephys_qc import toolkit
    folder = Path(folder); summary = record_summary(record, selection_policy); started = time.monotonic()
    try:
        before = source_snapshot(record); save(folder / 'sources-before.json', before)
        assert_registered(record, before)
        config = copy.deepcopy(record['default_config'])
        if scope: config['scope'] = scope
        prepared = toolkit.prepare_recording(record['source_path'], record_id=record['id'],
            modality=record.get('modality'), qc_config=config, reference_scheme=record.get('reference_scheme', 'unknown'),
            label=record.get('label'), provenance=record.get('provenance'))
        fresh_main = prepared['expected_sha256']
        if fresh_main != next(item['sha256'] for item in before if item['path'] == str(Path(record['source_path']).resolve())):
            raise ValueError('Source changed while preparing the case')
        old_files = record.get('expected_source_files')
        if old_files is not None:
            old = {str(Path(f['path']).resolve()): f['sha256'] for f in old_files}
            fresh = {f['path']: f['sha256'] for f in prepared['expected_source_files']}
            if old != fresh: raise ValueError('Prepared source package differs from registered manifest')
        old_meta = record.get('metadata', {}).get('source_files')
        if old_meta and {f['name']: f['sha256'] for f in old_meta} != {f['name']: f['sha256'] for f in prepared['expected_source_files']}:
            raise ValueError('Prepared source package differs from registered metadata fingerprints')
        prepared = {**copy.deepcopy(record), **prepared, 'modality_source': record.get('modality_source', 'caller_confirmation')}
        save(folder / 'prepared-record.json', prepared)
        save(folder / 'sources-before.json', source_snapshot(prepared))
        summary.update(record_summary(prepared, selection_policy)); save(folder / 'record-summary.json', summary)
        recommendation = toolkit.recommend(prepared, config)
        save(folder / 'recommendation.json', recommendation)
        summary['recommendation'] = {'status': recommendation['status'], 'selected_modules': recommendation['selected_modules'],
             'blocked_methods': recommendation['blocked_methods'], 'adopted': selection_policy == 'recommended', 'artifact': 'recommendation.json'}
        if selection_policy == 'recommended':
            if not recommendation.get('can_apply'):
                raise ValueError('Recommendation cannot be applied: ' + recommendation.get('reason', recommendation.get('summary', 'missing conditions')))
            modules, execution_config = recommendation['selected_modules'], recommendation['qc_config']
        else:
            modules, execution_config = [spec['id'] for spec in toolkit.catalog()], config
        plan = toolkit.build_plan(prepared, modules, execution_config)
        if scope and plan['scope'] != scope: raise ValueError('Recommendation changed the explicit requested scope')
        original_groups = record.get('default_config', {}).get('method_config', {}).get('comparison_groups')
        actual_groups = plan['qc_config']['method_config'].get('comparison_groups')
        audit = {'execution_policy': POLICIES[selection_policy], 'registered_comparison_groups': original_groups,
                 'effective_comparison_groups': actual_groups, 'comparison_groups_unchanged': original_groups == actual_groups,
                 'original_config_artifact': 'input-record.json', 'fresh_metadata_artifact': 'prepared-record.json',
                 'recommendation_adopted': selection_policy == 'recommended',
                 'registered_extensions': record.get('default_config', {}).get('method_config', {}).get('extensions', []),
                 'effective_extensions': plan['qc_config']['method_config'].get('extensions', [])}
        save(folder / 'configuration-audit.json', audit)
        if not audit['comparison_groups_unchanged']: raise ValueError('Comparison-group declaration changed; requires explicit review')
        save(folder / 'execution-plan.json', plan)
        seconds = planned_seconds(plan)
        summary.update(scope=plan['scope'], planned_seconds=seconds, configured_extensions=plan['qc_config']['method_config'].get('extensions', []))
        if not math.isfinite(seconds) or seconds > budget_seconds:
            summary.update(engineering_status='budget_skipped', issues=[f'Planned {seconds:g} seconds exceeds remaining per-record budget {budget_seconds:g} seconds'], budget_consumed_seconds=0.)
        else:
            summary['budget_consumed_seconds'] = seconds
            save(folder / 'record-summary.json', summary)
            with (folder / 'events.jsonl').open('w', encoding='utf-8') as events:
                def emit(mid, status, message):
                    events.write(json.dumps({'module_id': mid, 'status': status, 'message': message}, ensure_ascii=False) + '\n'); events.flush()
                result = toolkit.run_modules(prepared, folder / 'job', modules, qc_config=plan['qc_config'], emit=emit)
            summary.update(assess_result(result, plan, folder / 'job', prepared['expected_sha256']))
            summary['source_sha256'] = result.get('source_sha256')
            summary['engineering_status'] = 'passed' if not summary['issues'] else 'failed'
    except Exception as error:
        summary.update(engineering_status='failed', issues=[f'{type(error).__name__}: {error}'])
        (folder / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
    unchanged, _ = integrity_after(folder)
    summary['source_unchanged'] = unchanged
    if unchanged is not True and summary.get('engineering_status') != 'budget_skipped':
        summary.setdefault('issues', []).append('Input integrity could not be verified after this case')
        summary['engineering_status'] = 'failed'
    summary['engineering_pass'] = summary.get('engineering_status') == 'passed'
    summary['elapsed_seconds'] = round(time.monotonic() - started, 3)
    save(folder / 'acceptance.json', summary)
    return summary


def render_index(folder, coverage):
    esc = lambda value: html.escape(str(value), quote=True)
    rows = []
    for row in coverage['records']:
        links = [f'<a href="{esc(row["directory"] + "/acceptance.json")}">验收</a>']
        for key, title in [('report', '报告'), ('result', '结果'), ('recommendation_path', '推荐')]:
            if row.get(key): links.append(f'<a href="{esc(row["directory"] + "/" + row[key])}">{title}</a>')
        rows.append('<tr>' + ''.join(f'<td>{esc(value)}</td>' for value in [row['record_id'], row['dataset_id'], row['format'],
            row.get('source_duration_seconds'), row.get('evaluated_seconds', 0), row['engineering_status'], row.get('execution_status', '未执行')]) +
            '<td>' + ' · '.join(links) + '</td></tr>')
    (folder / 'index.html').write_text('''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>数据覆盖工程验收</title><style>body{font:15px/1.6 system-ui;color:#15354c;margin:32px}main{max-width:1300px;margin:auto}table{border-collapse:collapse;width:100%}th,td{padding:10px;text-align:left;border-bottom:1px solid #d7e4ee}a{color:#1768ab}.table{overflow:auto}</style><main><h1>数据覆盖工程验收</h1><p>默认采用推荐方案；all-base 可用于全部基础模块对照。部分可评不等于执行失败，也不等于质量合格。此处未验证科学准确性。</p><p>''' +
        esc(f"工程通过 {coverage['passed']} / {len(coverage['records'])}；失败 {coverage['failed']}；预算跳过 {coverage['budget_skipped']}；超时 {coverage['timed_out']}") +
        '</p><p><a href="coverage.json">下载完整覆盖矩阵</a></p><div class="table"><table><thead><tr><th>记录</th><th>数据集</th><th>格式</th><th>源时长/s</th><th>执行/s</th><th>工程验收</th><th>模块执行</th><th>证据</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></main></html>', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--record-id', action='append', default=[])
    parser.add_argument('--scope', choices=('window', 'recording'))
    parser.add_argument('--selection', choices=('recommended', 'all-base'), default='recommended')
    parser.add_argument('--max-records', type=int, default=32)
    parser.add_argument('--max-total-seconds', type=float, default=1800.)
    parser.add_argument('--max-record-seconds', type=float, default=900.)
    parser.add_argument('--timeout-seconds', type=float, default=600.)
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    for name in ('max_records', 'max_total_seconds', 'max_record_seconds', 'timeout_seconds'):
        if not math.isfinite(getattr(args, name)) or getattr(args, name) <= 0: parser.error(name + ' must be positive and finite')
    if args.worker:
        result = run_case(read_json(args.config), args.output_dir, scope=args.scope, budget_seconds=args.max_record_seconds, selection_policy=args.selection)
        return 0 if result['engineering_pass'] or result['engineering_status'] == 'budget_skipped' else 1
    try:
        records = load_records(args.config, args.record_id)
        if len(records) > args.max_records: raise ValueError('Record count exceeds --max-records')
        output = check_output(args.output_dir, records)
    except (ValueError, KeyError, OSError, TypeError) as error: parser.error(str(error))
    output.mkdir(parents=True)
    save(output / 'input-config.json', records)
    coverage = {'schema_version': 'ephys-data-coverage/1.0', 'execution_policy': POLICIES[args.selection],
        'scientific_accuracy_not_evaluated': True, 'records': [], 'passed': 0, 'failed': 0,
        'budget_skipped': 0, 'timed_out': 0, 'budget': {'max_total_seconds': args.max_total_seconds,
        'max_record_seconds': args.max_record_seconds, 'per_record_timeout_seconds': args.timeout_seconds,
        'consumed_seconds': 0., 'meaning': 'planned source seconds reserved for attempted jobs, not CPU time or quality'}}
    environment = dict(os.environ)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'): environment[key] = '1'
    for index, record in enumerate(records, 1):
        slug = re.sub(r'[^A-Za-z0-9_.-]+', '-', record['id']).strip('.-')[:60] or 'record'
        directory = f'{index:03d}-{slug}-{hashlib.sha256(record["id"].encode()).hexdigest()[:8]}'
        folder = output / directory; folder.mkdir(); save(folder / 'input-record.json', record)
        remaining = max(0., args.max_total_seconds - coverage['budget']['consumed_seconds'])
        budget = min(args.max_record_seconds, remaining)
        print('RUN', record['id'], flush=True)
        if budget <= 0:
            row = {**record_summary(record, args.selection), 'engineering_status': 'budget_skipped', 'issues': ['Total source-seconds budget exhausted']}
        else:
            command = [sys.executable, str(Path(__file__).resolve()), '--worker', '--config', str(folder / 'input-record.json'),
                       '--output-dir', str(folder), '--max-record-seconds', str(budget), '--selection', args.selection]
            if args.scope: command += ['--scope', args.scope]
            try:
                with (folder / 'worker.log').open('w', encoding='utf-8') as log:
                    process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=environment, timeout=args.timeout_seconds)
                if not (folder / 'acceptance.json').exists(): raise RuntimeError(f'Worker exited {process.returncode} without an acceptance record')
                row = read_json(folder / 'acceptance.json')
                if process.returncode and row['engineering_pass']:
                    row.update(engineering_pass=False, engineering_status='failed', issues=['Worker returned a nonzero exit code'])
            except (subprocess.TimeoutExpired, RuntimeError) as error:
                row = read_json(folder / 'record-summary.json') if (folder / 'record-summary.json').exists() else record_summary(record, args.selection)
                row.update(engineering_pass=False, engineering_status='timed_out' if isinstance(error, subprocess.TimeoutExpired) else 'failed', issues=[str(error)])
                row['source_unchanged'], _ = integrity_after(folder)
        row['directory'] = directory
        row['recommendation_path'] = 'recommendation.json' if (folder / 'recommendation.json').exists() else None
        coverage['budget']['consumed_seconds'] += row.get('budget_consumed_seconds', 0.)
        save(folder / 'acceptance.json', row)
        coverage['records'].append(row); coverage[row['engineering_status']] += 1
        save(output / 'coverage.json', coverage); render_index(output, coverage)
        print('RESULT', record['id'], row['engineering_status'], row.get('execution_status', ''), flush=True)
    return 0 if all(row['engineering_pass'] for row in coverage['records']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
