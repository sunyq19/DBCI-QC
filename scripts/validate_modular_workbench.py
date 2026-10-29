"""Check actual local API jobs and independently selected module execution.

This is engineering validation, not a detector-accuracy benchmark. Existing
full runs may be supplied in a manifest to avoid repeating scientific work.
"""
from pathlib import Path
import argparse
import hashlib
import json
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8769')
    parser.add_argument('--job-manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new output file; existing evidence is retained.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(path, body=None, expect=200, raw=False):
        request = urllib.request.Request(args.url.rstrip('/') + path,
                                         data=None if body is None else json.dumps(body).encode(),
                                         headers={'Content-Type': 'application/json'})
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        assert response.status == expect, (path, response.status, response.read()[:1000])
        payload = response.read()
        return payload if raw else json.loads(payload)

    def submit(item, modules):
        body = {'input_id': item['id'], 'selected_modules': modules, 'qc_config': item['default_config']}
        plan = call('/api/v1/plan', body)
        body['plan_id'] = plan['plan_id']
        job = call('/api/v1/jobs', body, 202)
        return {'input_id': item['id'], 'job_id': job['id'], 'plan_id': plan['plan_id']}

    def wait(id_):
        deadline, previous = time.monotonic() + 900, None
        while time.monotonic() < deadline:
            job = call('/api/v1/jobs/' + id_)
            state = (job['status'], job.get('phase'))
            if state != previous:
                print(id_, *state, flush=True)
                previous = state
            if job['status'] in {'completed', 'failed', 'cancelled', 'interrupted'}:
                return job
            time.sleep(2)
        raise TimeoutError(id_)

    catalog = call('/api/v1/catalog')
    assert len(catalog['modules']) == 9
    inputs = {item['id']: item for item in catalog['inputs']}
    full = json.loads(args.job_manifest.read_text()) if args.job_manifest else [submit(item, ['M03', 'M04', 'M05', 'M06', 'M07']) for item in inputs.values()]
    checks = []
    for entry in full:
        job = wait(entry['job_id'])
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + job['id'] + '/result')
        assert result['plan_id'] == entry['plan_id']
        assert result['score']['value'] is None and result['review_status'] == 'pending'
        assert all(m['status'] != 'failed' for m in result['modules'])
        assert {m['id'] for m in result['modules']} == {f'M{i:02d}' for i in range(1, 10)}
        item = inputs[entry['input_id']]
        selection = item['default_config']['selection']
        assert result['recording']['source_indices'] == selection['eeg_indices']
        assert result['recording']['start_seconds'] == selection['start_seconds']
        assert result['recording']['duration_seconds'] == selection['duration_seconds']
        artifacts = {a['name']: a for a in result['artifacts']}
        report = call('/api/v1/jobs/' + job['id'] + '/report', raw=True)
        assert b'<html' in report and b'/artifacts/waveform.png' in report
        image = call(artifacts['waveform.png']['url'], raw=True)
        assert image.startswith(b'\x89PNG\r\n\x1a\n')
        for name, artifact in artifacts.items():
            if name.startswith('M0') and name.endswith('.json'):
                data = call(artifact['url'])
                if name == 'M07_annotations.json':
                    assert data['quality_ground_truth'] is False
                    assert data['used_for_signal_detection'] is False
                    if entry['input_id'] == 'hmc-sn062':
                        assert data['stage_seconds'] == {'N1': 50.0, 'N2': 50.0}
                        assert data['input_range']['start_sample'] == 25600
        check = {**entry, 'recording': result['recording'], 'source_sha256': result['source_sha256'],
                 'module_statuses': {m['id']: m['status'] for m in result['modules']},
                 'report_bytes': len(report), 'waveform_sha256': hashlib.sha256(image).hexdigest(),
                 'score_is_null': True, 'review_pending': True, 'all_modules_without_execution_failure': True}
        checks.append(check)

    first = next(iter(inputs.values()))
    stale = {'input_id': first['id'], 'selected_modules': ['M03'], 'qc_config': first['default_config'], 'plan_id': 'stale'}
    call('/api/v1/jobs', stale, 400)
    subset = submit(first, ['M03'])
    cancelled = submit(first, ['M04'])
    call('/api/v1/jobs/' + cancelled['job_id'] + '/cancel', {})
    assert wait(cancelled['job_id'])['status'] == 'cancelled'
    call('/api/v1/jobs/' + cancelled['job_id'] + '/result', expect=400)
    assert wait(subset['job_id'])['status'] == 'completed'
    result = call('/api/v1/jobs/' + subset['job_id'] + '/result')
    chosen = {'M01', 'M02', 'M03', 'M08', 'M09'}
    assert set(result['selected_modules']) == chosen
    assert {m['id'] for m in result['modules'] if m['status'] != 'skipped'} == chosen
    assert all(m['status'] == 'skipped' and not m['artifacts'] for m in result['modules'] if m['id'] not in chosen)
    names = {a['name'] for a in result['artifacts']}
    assert 'M03_continuity.json' in names
    assert not any(name.startswith(('M04_', 'M05_', 'M06_', 'M07_')) for name in names)
    summary = {'schema_version': 'modular-workbench-validation/0.1', 'full_runs': checks,
               'subset_run': subset, 'subset_excludes_unselected_computations': True,
               'cancelled_run': cancelled, 'cancelled_has_no_final_result': True,
               'stale_plan_rejected': True, 'scientific_accuracy_validated': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Verified:', args.output, flush=True)


if __name__ == '__main__':
    main()
