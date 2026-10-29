"""Actual HTTP intake, revision, multi-window analysis, review and clone checks.

Runs in a fresh store outside the repository. No browser automation or data
publication. This is workflow evidence, never a detector accuracy benchmark.
"""
import argparse
import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
from urllib.parse import quote
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from server import Handler, Store, read_json


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--config', type=Path, default=REPO / '.local/workbench.json')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.is_relative_to(REPO):
        raise SystemExit('Choose a fresh evidence directory outside this repository.')
    output.mkdir(parents=True)
    settings = copy.deepcopy(read_json(args.config))
    example = next(i for i in settings['inputs'] if i['id'] == 'eegmmidb-s001r03')
    source = Path(example['source_path'])
    before = digest(source)
    settings.update(inputs=[], profiles=[], data_dir=str(output / 'runtime'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.store = Store(settings)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    base = f'http://127.0.0.1:{server.server_port}'

    def call(path, body=None, upload=None, raw=False):
        headers = {'Content-Type': 'application/json'}
        if upload:
            headers.update({'Content-Type': 'application/octet-stream', 'X-Filename': quote(upload.name)})
        request = urllib.request.Request(base + '/api/v1' + path,
            data=upload.read_bytes() if upload else json.dumps(body).encode() if body is not None else None,
            headers=headers)
        with opener.open(request, timeout=120) as response:
            data = response.read()
        return data if raw else json.loads(data)

    def wait_job(job):
        deadline = time.monotonic() + 600
        while job['status'] not in {'completed', 'failed', 'cancelled', 'interrupted'}:
            if time.monotonic() > deadline:
                raise RuntimeError('Timed out waiting for local analysis')
            time.sleep(0.2)
            job = call('/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        return job

    evidence = {'schema_version': 'release-workflow-validation/1', 'browser_visual_check': 'not_performed',
                'clinical_accuracy_validated': False, 'checks': {}}
    try:
        evidence['health'] = call('/health')
        intake = call('/intakes', upload=source)
        assert intake['id'] in {i['id'] for i in call('/intakes')['intakes']}
        body = {'confirmed': True, 'modality': 'scalp_eeg', 'reference_scheme': 'unknown',
                'eeg_indices': example['default_config']['selection']['eeg_indices'], 'reference_indices': {},
                'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'motor'},
                'label': 'Release validation: 125-second public EEG', 'source_note': 'Public EEGMMIDB; workflow validation only.'}
        record = call('/intakes/' + intake['id'] + '/confirm', body)['input']
        assert record['record_revision'] == 1
        original = copy.deepcopy(record)
        revised = call('/inputs/' + record['id'] + '/revisions', {**body, 'base_revision': 1,
                       'reference_scheme': 'common_reference', 'annotation_mapping': {
                           'kind': 'task', 'labels': {'T1': 'T1'}, 'confirmed': True,
                           'note': 'Workflow mapping retains source label verbatim; not artifact truth.'}})['input']
        assert revised['record_revision'] == 2 and revised['parent_input_id'] == record['id']
        assert call('/inputs/' + record['id']) == original
        try:
            call('/inputs/' + record['id'] + '/revisions', {**body, 'base_revision': 1})
            raise AssertionError('Stale revision accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 409
        evidence['checks']['immutable_input_revisions'] = True
        waveform = call('/inputs/' + revised['id'] + '/waveform?start_seconds=20&duration_seconds=2&channel_indices=0,1&max_points=400')
        evidence['waveform'] = waveform
        assert len(waveform['channels']) == 2
        config = {'scope': 'recording', 'recording_options': {'window_seconds': 60, 'expensive_methods': 'skip'}}
        request = {'input_id': revised['id'], 'selected_modules': ['M03', 'M04', 'M05', 'M07'], 'qc_config': config}
        plan = call('/plan', request)
        assert plan['scope'] == 'recording' and plan['window_count'] == 3
        job = wait_job(call('/jobs', {**request, 'plan_id': plan['plan_id']}))
        result = call('/jobs/' + job['id'] + '/result')
        assert result['scope'] == 'recording' and len(result['windows']) == 3
        assert result['score']['value'] is None
        assert all(w['status'] in {'completed', 'partial'} for w in result['windows']), result['windows']
        assert all(next(m for m in w['modules'] if m['id'] == 'M07')['status'] in {'completed', 'partial'} for w in result['windows'])
        evidence['checks']['explicit_annotation_mapping_reaches_m07'] = True
        evidence['result'] = result
        evidence['checks']['full_record_three_windows'] = True
        candidates = call('/jobs/' + job['id'] + '/candidates')
        evidence['candidates'] = candidates
        assert candidates['count'] == len(candidates['candidates'])
        root = output / 'runtime/jobs' / job['id']
        result_hash = digest(root / 'result.json')
        if candidates['candidates']:
            candidate = candidates['candidates'][0]
            review = call('/jobs/' + job['id'] + '/review')
            update = {'expected_version': review['version'], 'candidate_id': candidate['id'],
                      'decision': 'uncertain', 'reviewer': 'release-test', 'note': 'Workflow check, no scientific adjudication.'}
            saved = call('/jobs/' + job['id'] + '/review', update)
            assert saved['version'] == review['version'] + 1
            try:
                call('/jobs/' + job['id'] + '/review', update)
                raise AssertionError('Stale review accepted')
            except urllib.error.HTTPError as error:
                assert error.code == 409
            assert digest(root / 'result.json') == result_hash
            assert call('/jobs/' + job['id'] + '/review') == saved
            evidence['checks']['review_saved_without_changing_result'] = True
        else:
            evidence['checks']['review_saved_without_changing_result'] = 'no_natural_candidate; see injected-fixture unit tests'
        clone = call('/jobs/' + job['id'] + '/configuration')
        assert clone['parent_job_id'] == job['id'] and clone['qc_config'] == plan['qc_config']
        clone_request = {k: clone[k] for k in ('input_id', 'selected_modules', 'qc_config', 'parent_job_id')}
        clone_request['qc_config'] = {**clone_request['qc_config'], 'scope': 'window', 'recording_options': {}}
        clone_request['qc_config']['selection'].update(start_seconds=1, duration_seconds=5)
        clone_plan = call('/plan', clone_request)
        child = wait_job(call('/jobs', {**clone_request, 'plan_id': clone_plan['plan_id']}))
        assert child['parent_job_id'] == job['id']
        evidence['checks']['copy_configuration_and_rerun'] = True
        for artifact in result['artifacts']:
            data = call('/jobs/' + job['id'] + '/artifacts/' + quote(artifact['name']), raw=True)
            assert data
        evidence['checks']['all_artifacts_accessible'] = True
        assert digest(source) == before
        evidence['checks']['source_unchanged'] = True
        # A controlled acquisition-gap fixture exercises the actual upload,
        # registration and scheduler path (not only a mocked planner).
        import mne
        import numpy as np
        t = np.arange(13000) / 100
        raw_data = np.stack([np.sin(2*np.pi*(8+i)*t) * 20e-6 for i in range(4)])
        raw_record = mne.io.RawArray(raw_data, mne.create_info(['C3', 'C4', 'Cz', 'Pz'], 100, 'eeg'), first_samp=12345, verbose='ERROR')
        raw_record.set_annotations(mne.Annotations([30.], [5.], ['BAD_ACQ_SKIP']))
        fixture = output / 'synthetic_gap_raw.fif'
        raw_record.save(fixture, overwrite=False, verbose='ERROR')
        gap_intake = call('/intakes', upload=fixture)
        gap_record = call('/intakes/' + gap_intake['id'] + '/confirm', {
            **body, 'eeg_indices': [0,1,2,3], 'label': 'Controlled gap fixture, not clinical data'})['input']
        assert gap_record['default_config']['selection']['duration_seconds'] == 30
        try:
            call('/inputs/' + gap_record['id'] + '/waveform?start_seconds=27&duration_seconds=10&channel_indices=0')
            raise AssertionError('Preview silently crossed source gap')
        except urllib.error.HTTPError as error:
            assert error.code == 400
        gap_request = {'input_id': gap_record['id'], 'selected_modules': ['M03'],
                       'qc_config': {'scope': 'recording', 'recording_options': {'window_seconds': 60}}}
        gap_plan = call('/plan', gap_request)
        gap_job = wait_job(call('/jobs', {**gap_request, 'plan_id': gap_plan['plan_id']}))
        gap_result = call('/jobs/' + gap_job['id'] + '/result')
        assert gap_result['coverage']['gap_seconds'] == 5
        assert gap_result['coverage']['completed_seconds'] == 125
        assert gap_result['coverage']['execution_percent'] < 100
        assert gap_result['windows'][0]['start_sample'] == 12345
        assert gap_result['windows'][1]['start_sample'] == 15845
        assert all(w['status'] in {'completed', 'partial'} for w in gap_result['windows'])
        evidence['gap_result'] = gap_result
        evidence['checks']['actual_fif_gap_registration_and_coverage'] = True
        evidence['jobs'] = [job['id'], child['id'], gap_job['id']]
        (output / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        print(json.dumps({'output': str(output), 'checks': evidence['checks']}, ensure_ascii=False))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
