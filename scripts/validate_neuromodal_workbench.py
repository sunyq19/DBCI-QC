"""Replay public sEEG and raw Neuropixels samples through the local HTTP workflow.

Creates three intake records and five reports in the selected local workbench.
Engineering acceptance only; no scientific accuracy or visual validation claim.
Use the sample directories produced by the public preparation scripts.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote, urlsplit
import urllib.request


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:8769')
    parser.add_argument('--samples-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    assert urlsplit(args.base).hostname in {'127.0.0.1', 'localhost'}, 'Only local workbenches are supported'
    assert not args.output.exists(), 'Use a fresh evidence directory'
    args.output.mkdir(parents=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(path, body=None, upload=None, raw=False):
        headers = {'Content-Type': 'application/json'}
        if upload:
            headers.update({'Content-Type': 'application/octet-stream', 'X-Filename': quote(upload.name)})
        request = urllib.request.Request(args.base.rstrip('/') + path,
            data=upload.read_bytes() if upload else json.dumps(body).encode() if body is not None else None,
            headers=headers)
        with opener.open(request, timeout=120) as response:
            content = response.read()
        return content if raw else json.loads(content)

    evidence = {'schema_version': 'neuromodal-workflow-acceptance/1',
                'visual_validation': 'not_performed', 'clinical_accuracy_validated': False,
                'health': call('/api/v1/health'), 'cases': []}
    def save():
        (args.output / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

    def execute(record, name, config=None, expect_short=False, expect_whole=False):
        request = {'input_id': record['id']}
        if config is not None: request['qc_config'] = config
        rec = call('/api/v1/recommend', request)
        assert rec['can_apply'], rec
        request.update(selected_modules=rec['selected_modules'], qc_config=rec['qc_config'])
        plan = call('/api/v1/plan', request)
        assert plan['plan_id'] == rec['plan_id']
        job = call('/api/v1/jobs', {**request, 'plan_id': plan['plan_id']})
        print(json.dumps({'case': name, 'job_id': job['id'], 'status': job['status']}), flush=True)
        deadline = time.monotonic() + 600
        while job['status'] in {'queued', 'running'}:
            assert time.monotonic() < deadline, job
            time.sleep(.3)
            job = call('/api/v1/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + job['id'] + '/result')
        assert result['analysis_profile'] == ('seeg-basic/1' if record['modality'] == 'seeg' else 'neuropixels-voltage/2')
        assert result['score']['value'] is None
        assert all(m['status'] != 'failed' for m in result['modules'])
        assert result['plan_id'] == plan['plan_id']
        assert result['source_sha256'] == record['expected_sha256']
        assert next(m for m in result['modules'] if m['id'] == 'M06')['status'] == 'skipped'
        if expect_short:
            assert next(m for m in result['modules'] if m['id'] == 'M04')['status'] == 'partial'
        if expect_whole:
            assert result['coverage']['execution_percent'] == 100, result['coverage']
            windows = result['windows']
            first = record['metadata']['continuous_segments'][0]['start_sample']
            last = record['metadata']['continuous_segments'][-1]['stop_sample']
            assert windows[0]['start_sample'] == first and windows[-1]['stop_sample'] == last
            assert all(a['stop_sample'] == b['start_sample'] for a, b in zip(windows, windows[1:]))
        else:
            assert result['recording']['start_sample'] == record['metadata']['clock']['first_sample']
            assert result['recording']['channel_count'] == len(record['default_config']['selection']['eeg_indices'])
        report = call('/api/v1/jobs/' + job['id'] + '/report', raw=True)
        assert b'<html' in report
        configuration = call('/api/v1/jobs/' + job['id'] + '/configuration')
        assert configuration['input_modality'] == record['modality']
        (args.output / (name + '-result.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        evidence['cases'].append({'name': name, 'job_id': job['id'], 'input_id': record['id'],
            'analysis_profile': result['analysis_profile'], 'plan_id': plan['plan_id'],
            'modules': {m['id']: m['status'] for m in result['modules']},
            'report_bytes': len(report), 'source_sha256': result['source_sha256'],
            'coverage': result.get('coverage'), 'recording': result.get('recording'),
            'report_url': args.base.rstrip('/') + '/api/v1/jobs/' + job['id'] + '/report'})
        save()
        print(json.dumps({'case': name, 'passed': True}), flush=True)
        return rec['qc_config']

    samples = [
        ('seeg', 'seeg/upload-samples/MNE_sEEG_sample_ieeg.fif', 'seeg'),
        ('neuropixels-lf', 'neuropixels/upload-samples/neo-neuropixels-noise4sam-lf.zip', 'extracellular'),
        ('neuropixels-ap', 'neuropixels/upload-samples/paulk-human-pt03-ap-60s-2s.zip', 'extracellular')]
    for name, relative, modality in samples:
        source = args.samples_root / relative
        original = digest(source)
        before = {j['id'] for j in call('/api/v1/jobs')['jobs']}
        intake = call('/api/v1/intakes', upload=source)
        assert intake['status'] == 'needs_confirmation'
        assert intake['sha256'] == original
        assert intake['suggestions']['modality'] == modality
        assert {j['id'] for j in call('/api/v1/jobs')['jobs']} == before
        selected = intake['suggestions']['eeg_indices']
        assert len(selected) == (119 if modality == 'seeg' else 384)
        assert all(intake['metadata']['channels'][i]['channel_type'] != 'stim' for i in selected)
        body = {'confirmed': True, 'modality': modality, 'reference_scheme': 'unknown',
                'eeg_indices': selected, 'reference_indices': {},
                'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'},
                'label': name + ' public upload verification',
                'source_note': 'Public source integration test; no channel or artifact ground truth.'}
        record = call('/api/v1/intakes/' + intake['id'] + '/confirm', body)['input']
        # Source hashes belong to intake/result, not the public record response.
        record['expected_sha256'] = intake['source_sha256']
        if modality == 'seeg':
            execute(record, name, {'scope': 'recording', 'recording_options': {'window_seconds': 120}}, expect_whole=True)
        else:
            config = execute(record, name)
            if name == 'neuropixels-ap':
                short = copy.deepcopy(config); short['selection']['duration_seconds'] = .02
                execute(record, name + '-short', short, expect_short=True)
                execute(record, name + '-whole', {'scope': 'recording', 'recording_options': {'window_seconds': 1}}, expect_whole=True)
        assert digest(source) == original
    evidence['passed'] = True
    save()


if __name__ == '__main__':
    main()
