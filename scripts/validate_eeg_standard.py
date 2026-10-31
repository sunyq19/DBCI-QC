"""Replay registered EEG examples and verify rule/report evidence contracts.

This is engineering acceptance, not independent expert-label validation.
The server retains its frozen requests/results; this script records references.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8769')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--input-id', action='append')
    parser.add_argument('--scope', choices=['window', 'recording'])
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new output path; prior evidence is immutable.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def raw(path, body=None):
        req = urllib.request.Request(args.url.rstrip('/') + path,
                data=None if body is None else json.dumps(body).encode(),
                headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=45) as response:
            return response.read()

    def call(path, body=None):
        return json.loads(raw(path, body))

    catalog = call('/api/v1/catalog')
    inputs = {r['id']: r for r in catalog['inputs']}
    cases = [('eegmmidb-s003r01', 30, 'window'),
             ('hmc-sn062', 60, 'window'),
             ('ds002034-sub01', 60, 'window'),
             ('ds004504-sub001', 40, 'window'),
             ('eegmmidb-s003r01', None, 'recording')]
    evidence = {'schema_version': 'eeg-standard-acceptance/1',
                'version': call('/api/v1/health')['version'],
                'claim': 'Engineering/report consistency only; no expert accuracy or standard conformance claim',
                'cases': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for identifier, seconds, scope in cases:
        if args.input_id and identifier not in args.input_id or args.scope and scope != args.scope:
            continue
        record = inputs[identifier]
        config = deepcopy(record['default_config'])
        config['scope'] = scope
        config['method_config']['extensions'] = []
        config['method_config']['extension_parameters'] = {}
        if seconds is not None:
            config['selection']['duration_seconds'] = seconds
        else:
            config['recording_options'] = {'window_seconds': 30}
        body = {'input_id': identifier, 'qc_config': config,
                'selected_modules': [f'M{i:02d}' for i in range(1, 10)]}
        plan = call('/api/v1/plan', body)
        body['plan_id'] = plan['plan_id']
        job = call('/api/v1/jobs', body)
        print('RUN', identifier, scope, job['id'], flush=True)
        deadline = time.monotonic() + 600
        while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(1)
            job = call('/api/v1/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + job['id'] + '/result')
        index = result['eeg_assessment']
        assert index['conformance'] is None and not index['expert_accuracy_validated']
        assert index['population_confirmation'] == 'not_captured_by_runtime'
        assert len(index['checks']) == 12 and result['score']['value'] is None
        artifacts = {a['name']: a for a in result['artifacts']}
        rules = raw(artifacts['eeg-rules.json']['url'])
        assert hashlib.sha256(rules).hexdigest() == index['catalog_sha256']
        assert call(artifacts['eeg-assessment.json']['url']) == index
        observed_hashes = {}
        for item in index['checks']:
            for ref in item['evidence']:
                name = ref['artifact']
                if name not in observed_hashes:
                    observed_hashes[name] = hashlib.sha256(raw(artifacts[name]['url'])).hexdigest()
                assert observed_hashes[name] == ref['sha256'], ref
        if scope == 'window':
            continuity = call(artifacts['M03_continuity.json']['url'])
            c = next(row for row in index['checks'] if row['id'] == 'EEG-003')
            assert c['parameters']['M03_continuity.json#parameters'] == continuity['parameters']
            assert next(m for m in result['modules'] if m['id'] == 'M08')['summary']['source_unchanged'] is True
        else:
            assert index['child_results']
            assert result['source_integrity'] == 'verified_after_run'
            for child in index['child_results']:
                child_result = call(artifacts[child]['url'])
                assert child_result['eeg_assessment']['catalog_sha256'] == index['catalog_sha256']
            for mapping in index['child_artifact_maps']:
                if not mapping['result_artifact']:
                    continue
                child = call(artifacts[mapping['result_artifact']]['url'])
                for item in child['eeg_assessment']['checks']:
                    for ref in item['evidence']:
                        exported_name = mapping['artifacts'][ref['artifact']]
                        digest = hashlib.sha256(raw(artifacts[exported_name]['url'])).hexdigest()
                        assert digest == ref['sha256'], (mapping['window_id'], ref)
            assert all(row['observation_scope'] == 'window_execution_summary' for row in index['checks'])
        report_url = '/api/v1/jobs/' + job['id'] + '/report'
        report = raw(report_url).decode()
        assert '/standards/eeg-checks#eeg-003' in report and 'EEG 检查依据' in report
        assert artifacts['eeg-assessment.json']['url'] in report
        row = {'input_id': identifier, 'job_id': job['id'], 'scope': scope,
               'report_url': args.url.rstrip('/') + report_url,
               'format': record['metadata'].get('format'), 'status': result['status'],
               'source_sha256': result['source_sha256'], 'plan_id': result['plan_id'],
               'selection': result['qc_config']['selection'],
               'catalog_sha256': index['catalog_sha256'],
               'modules': {m['id']: {'status': m['status'], 'reason': m['reason']} for m in result['modules']},
               'checks': [{'id': r['id'], 'evidence_status': r['evidence_status'],
                           'effective_parameter_artifacts': list(r['parameters'])} for r in index['checks']],
               'checks_passed': ['rule_fingerprint', 'artifact_fingerprints', 'effective_parameters',
                                 'report_links', 'unknown_not_pass', 'source_unchanged'],
               'engineering_pass': True}
        evidence['cases'].append(row)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
        print('PASS', identifier, scope, result['status'], flush=True)
    print('Saved', args.output, flush=True)


if __name__ == '__main__':
    main()
