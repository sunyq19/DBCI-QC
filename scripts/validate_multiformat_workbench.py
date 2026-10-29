"""Run public EDF/BDF/BrainVision/EEGLAB/FIF intake through actual HTTP reports.

Isolated local store; no browser, publishing, or live configuration changes.
This verifies file integration and source preservation, not detector accuracy.
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
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=REPO / '.local/workbench.json')
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(REPO):
        raise SystemExit('Use a fresh evidence directory outside the repository.')
    output.mkdir(parents=True)
    settings = copy.deepcopy(read_json(args.config))
    edf = next(i for i in settings['inputs'] if i['id'] == 'eegmmidb-s001r02')
    sources = [('EDF', Path(edf['source_path'])),
               ('BDF', args.samples / '01_BDF/test.bdf'),
               ('BrainVision', args.samples / '02_BrainVision.zip'),
               ('EEGLAB', args.samples / '03_EEGLAB.zip'),
               ('FIF', args.samples / '04_FIF/sample_audvis_trunc_raw.fif')]
    settings.update(data_dir=str(output / 'runtime'), inputs=[], profiles=[])
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.store = Store(settings)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{server.server_port}'

    def call(path, body=None, source=None, raw=False):
        headers = {'Content-Type': 'application/octet-stream' if source else 'application/json'}
        if source:
            headers['X-Filename'] = quote(source.name)
        request = urllib.request.Request(base + path,
            data=source.read_bytes() if source else json.dumps(body).encode() if body is not None else None,
            headers=headers)
        with opener.open(request, timeout=90) as response:
            payload = response.read()
        return payload if raw else json.loads(payload)

    evidence = {'schema_version': 'multiformat-workbench-validation/1.0',
                'browser_visual_check': 'not_performed', 'clinical_accuracy_validated': False,
                'reference_scheme': 'unknown', 'cases': []}
    try:
        catalog = call('/api/v1/catalog')
        assert catalog['api_version'] == 'modular-qc-api/1.0'
        assert len(catalog['capabilities']['intake']['readers']) == 4
        for fmt, source in sources:
            before = digest(source)
            intake = call('/api/v1/intakes', source=source)
            assert intake['status'] == 'needs_confirmation' and intake['sha256'] == before
            assert intake['metadata']['format'] == fmt
            assert intake['suggestions']['modality'] == 'unknown'
            assert len(call('/api/v1/jobs')['jobs']) == len(evidence['cases'])
            suggested = intake['suggestions']
            confirmation = {'confirmed': True, 'modality': 'scalp_eeg', 'reference_scheme': 'unknown',
                'eeg_indices': suggested['eeg_indices'], 'reference_indices': suggested['reference_indices'],
                'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'},
                'label': fmt + ' public reader integration check',
                'source_note': 'Public upstream reader fixture; integration validation only.'}
            if fmt == 'EDF':
                confirmation['eeg_indices'] = edf['default_config']['selection']['eeg_indices']
            record = call('/api/v1/intakes/' + intake['id'] + '/confirm', confirmation)['input']
            recommendation = call('/api/v1/recommend', {'input_id': record['id']})
            assert recommendation['can_apply'], recommendation
            request = {'input_id': record['id'], 'selected_modules': recommendation['selected_modules'],
                       'qc_config': recommendation['qc_config']}
            plan = call('/api/v1/plan', request)
            assert plan['plan_id'] == recommendation['plan_id']
            assert plan['input_metadata'] == record['metadata']
            assert plan['input_modality']['value'] == 'scalp_eeg'
            job = call('/api/v1/jobs', {**request, 'plan_id': plan['plan_id']})
            deadline = time.monotonic() + 300
            while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
                time.sleep(.5)
                job = call('/api/v1/jobs/' + job['id'])
            assert job['status'] == 'completed', job
            result = call('/api/v1/jobs/' + job['id'] + '/result')
            assert all(m['status'] != 'failed' for m in result['modules']), result['modules']
            assert result['plan_id'] == plan['plan_id']
            assert result['score']['value'] is None and result['review_status'] == 'pending'
            assert result['source_sha256'] == intake['source_sha256']
            assert len(result['source_files']) == len(intake['source_files'])
            assert digest(source) == before
            assert result['recording']['source_indices'] == confirmation['eeg_indices']
            report = call('/api/v1/jobs/' + job['id'] + '/report', raw=True)
            assert b'<html' in report and '总分未校准'.encode() in report
            case = {'format': fmt, 'upload': source.name, 'upload_sha256': before,
                    'source_unchanged': True, 'metadata': intake['metadata'], 'confirmation': confirmation,
                    'plan_id': plan['plan_id'], 'job_id': job['id'], 'result': result, 'report_bytes': len(report)}
            evidence['cases'].append(case)
            (output / 'progress.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            print(json.dumps({'format': fmt, 'passed': True, 'channels': len(intake['metadata']['channels']),
                              'selected': len(confirmation['eeg_indices']),
                              'modules': {m['id']: m['status'] for m in result['modules']}}, ensure_ascii=False), flush=True)
        evidence['passed'] = True
        (output / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'passed': True, 'cases': len(evidence['cases']), 'output': str(output)}), flush=True)
    finally:
        for identifier in list(server.store.processes):
            server.store.cancel(identifier)
        server.shutdown()
        server.server_close()
        thread.join(2)


if __name__ == '__main__':
    main()
