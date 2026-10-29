"""Real local intake -> recommendation -> plan -> report, in an isolated store.

Reads only explicitly registered inputs; creates one job on a copied public EDF.
Does not use a browser, change live settings, or publish/transfer data remotely.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import quote
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from server import Store, Handler, read_json


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            hasher.update(block)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=REPO / '.local/workbench.json')
    parser.add_argument('--output', type=Path, required=True, help='Fresh evidence directory outside the repository')
    parser.add_argument('--input-id', default='eegmmidb-s001r02', help='Registered public EDF to copy through intake')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(REPO):
        raise SystemExit('Use a fresh evidence directory outside the repository.')
    output.mkdir(parents=True)
    settings = copy.deepcopy(read_json(args.config))
    original = next(item for item in settings['inputs'] if item['id'] == args.input_id)
    source = Path(original['source_path'])
    before = digest(source)
    settings['data_dir'] = str(output / 'runtime')
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.store = Store(settings)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{server.server_port}'

    def call(path, body=None, binary=False, text=False):
        headers = {'Content-Type': 'application/octet-stream' if binary else 'application/json'}
        if binary:
            headers['X-Filename'] = quote(source.name)
        request = urllib.request.Request(base + '/api/v1' + path,
            data=body if binary else json.dumps(body).encode() if body is not None else None, headers=headers)
        with opener.open(request, timeout=60) as response:
            payload = response.read()
        return payload.decode() if text else json.loads(payload)

    evidence = {'schema_version': 'toolkit-integration-validation/1.0', 'browser_visual_check': 'not_performed',
                'clinical_accuracy_validated': False, 'original_input_id': args.input_id, 'recommendations': []}
    try:
        catalog = call('/catalog')
        assert catalog['api_version'] == 'modular-qc-api/1.0'
        methods = [m for module in catalog['modules'] for m in module['methods']]
        assert len(methods) == 24
        assert all(m.get('documentation', {}).get('purpose') and m['documentation'].get('references') for m in methods)
        for item in catalog['inputs']:
            request = {'input_id': item['id'], 'qc_config': item['default_config']}
            recommended = call('/recommend', request)
            assert recommended['can_apply'] is True, recommended
            plan = call('/plan', {**request, 'qc_config': recommended['qc_config'], 'selected_modules': recommended['selected_modules']})
            assert plan['plan_id'] == recommended['plan_id']
            assert plan['data_tags'] == recommended['data_tags']
            assert plan['method_applicability'] == recommended['method_applicability']
            assert recommended['qc_config']['method_config']['extensions'] == ['mne_amplitude']
            altered = copy.deepcopy(request)
            altered['qc_config']['context_tags'] = {'disease': 'epilepsy', 'task': 'sleep', 'age_group': 'child'}
            contextual = call('/recommend', altered)
            assert contextual['qc_config']['method_config'] == recommended['qc_config']['method_config']
            assert contextual['selected_modules'] == recommended['selected_modules']
            evidence['recommendations'].append({'input_id': item['id'], 'recommendation': recommended})
        assert not call('/jobs')['jobs'], 'Recommendations must not run an analysis'
        intake = call('/intakes', source.read_bytes(), binary=True)
        assert intake['status'] == 'needs_confirmation' and intake['sha256'] == before
        assert len(call('/catalog')['inputs']) == len(catalog['inputs'])
        body = {'confirmed': True, 'modality': 'scalp_eeg', 'reference_scheme': original.get('reference_scheme', 'unknown'),
                'eeg_indices': original['default_config']['selection']['eeg_indices'],
                'reference_indices': original['default_config']['selection'].get('reference_indices', {}),
                'context_tags': original['default_config'].get('context_tags', {}),
                'label': '本机提交流程验收 · ' + source.stem,
                'source_note': '隔离验收副本；原始公开记录及来源说明保留。'}
        registered = call('/intakes/' + intake['id'] + '/confirm', body)
        assert registered == call('/intakes/' + intake['id'] + '/confirm', body)
        assert call('/intakes/' + intake['id'])['input_id'] == registered['input']['id']
        assert len(call('/catalog')['inputs']) == len(catalog['inputs']) + 1
        recommendation = call('/recommend', {'input_id': registered['input']['id']})
        assert recommendation['can_apply']
        request = {'input_id': registered['input']['id'], 'qc_config': recommendation['qc_config'],
                   'selected_modules': recommendation['selected_modules']}
        plan = call('/plan', request)
        assert plan['plan_id'] == recommendation['plan_id']
        job = call('/jobs', {**request, 'plan_id': plan['plan_id']})
        deadline = time.monotonic() + 300
        while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(.5)
            job = call('/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        result = call('/jobs/' + job['id'] + '/result')
        assert result['source_sha256'] == before and digest(source) == before
        assert result['plan_id'] == plan['plan_id'] and result['review_status'] == 'pending'
        assert result['score']['value'] is None
        assert all(m['status'] != 'failed' for m in result['modules'])
        assert set(result['selected_modules']) == set(recommendation['selected_modules'])
        assert [e['id'] for e in result['extensions']] == ['mne_amplitude']
        assert result['extensions'][0]['status'] == 'completed'
        report = call('/jobs/' + job['id'] + '/report', text=True)
        assert '原始' in report and '总分未校准' in report
        stored = server.store.inputs[registered['input']['id']]
        assert stored['intake_confirmation']['roles_reference_modality'] == 'user_confirmed'
        assert stored['source_path'] != str(source) and digest(stored['source_path']) == before
        evidence.update(passed=True, registered_input=registered['input'], intake=intake,
                        original_source_unchanged=True, copy_sha256=before, recommendation=recommendation,
                        plan_id=plan['plan_id'], job_id=job['id'], result=result,
                        data_directory=str(output / 'runtime'))
        (output / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'passed': True, 'recommendation_cases': len(evidence['recommendations']),
                          'job_id': job['id'], 'output': str(output)}, ensure_ascii=False), flush=True)
    finally:
        for identifier in list(server.store.processes):
            server.store.cancel(identifier)
        server.shutdown()
        server.server_close()
        thread.join(2)


if __name__ == '__main__':
    main()
