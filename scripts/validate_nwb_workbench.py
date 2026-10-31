"""Local NWB upload/selection/report acceptance, with independent h5py value checks.

Creates three confirmed records and four reports. Preserves public source files.
Synthetic checks validate engineering behavior, not clinical effectiveness.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import time
from urllib.parse import quote, urlsplit
import urllib.error
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
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert urlsplit(args.base).hostname in {'127.0.0.1', 'localhost'}
    args.output.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    evidence = {'scope': 'engineering_only', 'visual_validation': 'not_performed', 'cases': [], 'negative_cases': []}

    def save():
        (args.output / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

    def call(path, body=None, upload=None, raw=False, expected=200):
        headers = {'Content-Type': 'application/json'}
        data = json.dumps(body).encode() if body is not None else None
        if upload:
            headers = {'Content-Type': 'application/octet-stream', 'X-Filename': quote(upload.name)}
            data = upload.read_bytes()
        try:
            response = opener.open(urllib.request.Request(args.base + path, data=data, headers=headers), timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        content = response.read()
        assert response.status == expected, (path, response.status, content[:2000])
        return content if raw else json.loads(content)

    def confirm(intake, name, source_note):
        body = {'confirmed': True, 'modality': 'ecog', 'reference_scheme': 'unknown',
                'eeg_indices': intake['suggestions']['eeg_indices'], 'reference_indices': {},
                'selected_stream_id': intake['metadata']['selected_stream_id'],
                'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'},
                'label': name, 'source_note': source_note}
        return call('/api/v1/intakes/' + intake['id'] + '/confirm', body)['input']

    def execute(record, source, name, scope='window'):
        request = {'input_id': record['id']}
        if scope == 'recording':
            request['qc_config'] = {'scope': 'recording', 'recording_options': {'window_seconds': 5}}
        recommendation = call('/api/v1/recommend', request)
        assert recommendation['can_apply'], recommendation
        request.update(selected_modules=recommendation['selected_modules'], qc_config=recommendation['qc_config'])
        plan = call('/api/v1/plan', request)
        assert plan['plan_id'] == recommendation['plan_id']
        stream = record['metadata']['selected_stream_id']
        assert plan['qc_config']['selection']['stream_id'] == stream
        job = call('/api/v1/jobs', {**request, 'plan_id': plan['plan_id']}, expected=202)
        print(json.dumps({'case': name, 'job_id': job['id']}), flush=True)
        deadline = time.monotonic() + 300
        while job['status'] in {'queued', 'running'}:
            assert time.monotonic() < deadline
            time.sleep(.3)
            job = call('/api/v1/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + job['id'] + '/result')
        assert result['source_sha256'] == digest(source)
        assert result['analysis_profile'] == 'ecog-basic/1'
        assert result['score']['value'] is None
        assert all(m['status'] != 'failed' for m in result['modules'])
        assert next(m for m in result['modules'] if m['id'] == 'M06')['status'] == 'skipped'
        html = call('/api/v1/jobs/' + job['id'] + '/report', raw=True)
        assert b'<html' in html
        config = call('/api/v1/jobs/' + job['id'] + '/configuration')
        assert config['qc_config']['selection']['stream_id'] == stream
        independent = []
        import h5py
        import numpy as np
        with h5py.File(source, 'r') as f:
            group = f[stream]
            raw = group['data']
            cc = group['channel_conversion'][:] if 'channel_conversion' in group else np.ones(raw.shape[1])
            parts = result['windows'] if scope == 'recording' else [result['recording']]
            for part in parts:
                first, stop = part['start_sample'], part['stop_sample']
                values = ((raw[first:stop].astype(float) * float(raw.attrs.get('conversion', 1.))) * cc + float(raw.attrs.get('offset', 0.))).T
                sha = hashlib.sha256(np.ascontiguousarray(values, dtype='<f8').tobytes()).hexdigest()
                if scope == 'recording':
                    child = call('/api/v1/jobs/' + job['id'] + '/artifacts/' + part['result_artifact'])
                    actual = child['data_sha256']
                else:
                    actual = result['data_sha256']
                assert sha == actual, (name, first, stop, 'Independent voltage values differ')
                independent.append({'first': first, 'stop': stop, 'stored_values': values.size,
                                    'h5py_sha256': sha, 'runtime_sha256': actual, 'exact_sha_match': sha == actual})
        if scope == 'recording':
            assert result['coverage']['execution_percent'] == 100
            assert all(a['stop_sample'] == b['start_sample'] for a,b in zip(result['windows'], result['windows'][1:]))
        (args.output / (name + '-result.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2))
        evidence['cases'].append({'name': name, 'job_id': job['id'], 'input_id': record['id'],
            'stream': stream, 'scope': scope, 'modules': {m['id']:m['status'] for m in result['modules']},
            'source_sha256': result['source_sha256'], 'independent_h5py': independent,
            'report_url': args.base + '/api/v1/jobs/' + job['id'] + '/report'})
        save()

    evidence['health'] = call('/api/v1/health')
    for name, filename, stream in [
        ('public-ecog', 'DANDI_000019_EC9_B15_samples30518-61036.nwb', None),
        ('synthetic-acquisition', 'DBCI_synthetic_multistream.nwb', '/acquisition/raw_regular'),
        ('synthetic-lfp', 'DBCI_synthetic_multistream.nwb', '/processing/ecephys/LFP/lfp_timestamps')]:
        source = args.samples / filename
        original_hash = digest(source)
        before = {j['id'] for j in call('/api/v1/jobs')['jobs']}
        intake = call('/api/v1/intakes', upload=source, expected=201)
        assert intake['status'] == 'needs_confirmation'
        assert intake['metadata']['annotations']['extraction_status'] == 'not_extracted'
        assert intake['metadata']['annotations']['count'] is None
        if stream:
            assert intake['metadata']['selected_stream_id'] is None and intake['metadata']['channels'] == []
            intake = call('/api/v1/intakes/' + intake['id'] + '/stream', {'stream_id': stream})
        assert before == {j['id'] for j in call('/api/v1/jobs')['jobs']}
        assert intake['metadata']['nwb']['units_count'] == (0 if name == 'public-ecog' else 2)
        note = ('DANDI 000019 / 0.220126.2148 EC9 B15; source samples 30518:61036, 256 channels; no clinical QC labels.'
                if name == 'public-ecog' else 'Synthetic engineering fixture. ECoG route selected only to test mechanics; no biological modality or clinical validity.')
        record = confirm(intake, name + ' NWB verification', note)
        execute(record, source, name)
        if name == 'synthetic-lfp':
            execute(record, source, name + '-whole', scope='recording')
        assert digest(source) == original_hash
    for filename in ['DBCI_synthetic_units_only.nwb', '边界样例/sub-70375_ses-20170317T094453_behavior+ecephys.nwb']:
        intake = call('/api/v1/intakes', upload=args.samples / filename, expected=201)
        assert intake['metadata']['selected_stream_id'] is None and not intake['metadata']['channels']
        response = call('/api/v1/intakes/' + intake['id'] + '/confirm', {
            'confirmed': True, 'modality': 'ecog', 'reference_scheme': 'unknown',
            'eeg_indices': [0], 'reference_indices': {}, 'selected_stream_id': '/acquisition/fake'}, expected=400)
        evidence['negative_cases'].append({'filename': filename, 'intake_id': intake['id'], 'error': response,
                                           'streams': intake['metadata']['available_streams']})
        save()
    evidence['passed'] = True
    save()


if __name__ == '__main__':
    main()
