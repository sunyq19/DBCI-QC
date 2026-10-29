"""Run available selected extensions through the workbench on registered data.

Engineering integration checks only; no accuracy or clinical scoring claim.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8769')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--input-id', action='append', help='Only run these registered inputs; default is all.')
    parser.add_argument('--all-modules', action='store_true', help='Also run the full core pipeline and annotation module.')
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Use a new evidence file; previous results are retained.')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def call(path, body=None, raw=False):
        request = urllib.request.Request(args.url.rstrip('/') + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=30) as response:
            payload = response.read()
        return payload if raw else json.loads(payload)

    catalog = call('/api/v1/catalog')
    assert catalog['api_version'] == 'modular-qc-api/1.0'
    assert len(catalog['modules']) == 9
    methods = [method for module in catalog['modules'] for method in module['methods']]
    assert len(methods) == len({m['id'] for m in methods})
    available = [m['id'] for m in methods if m.get('optional_extension') and m['implementation'] == 'available']
    assert {'mne_amplitude','mne_muscle','mne_bridge','mne_lof','autoreject_global'} <= set(available)
    assert set(catalog['context_tag_options']) == {'disease', 'age_group', 'task'}
    runs = []
    if args.input_id and set(args.input_id) - {item['id'] for item in catalog['inputs']}:
        raise ValueError('Requested input ID is not registered')
    for item in catalog['inputs']:
        if args.input_id and item['id'] not in args.input_id:
            continue
        assert {'reference_scheme','clinical_events','n_eeg','sampling_rate_hz'} <= {t['key'] for t in item['data_tags']}
        config = deepcopy(item['default_config'])
        config.setdefault('method_config', {})['extensions'] = available
        body = {'input_id': item['id'], 'selected_modules': ['M03','M04','M05','M06','M07'] if args.all_modules else [], 'qc_config': config}
        plan = call('/api/v1/plan', body)
        changed = deepcopy(body)
        changed['qc_config']['context_tags'] = {'disease': 'epilepsy', 'age_group': 'child', 'task': 'sleep'}
        contextual = call('/api/v1/plan', changed)
        assert contextual['method_applicability'] == plan['method_applicability']
        assert contextual['plan_id'] != plan['plan_id']
        body['plan_id'] = plan['plan_id']
        job = call('/api/v1/jobs', body)
        deadline = time.monotonic() + 300
        while job['status'] in {'queued', 'running'} and time.monotonic() < deadline:
            time.sleep(.5)
            job = call('/api/v1/jobs/' + job['id'])
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + job['id'] + '/result')
        assert result['plan_id'] == plan['plan_id']
        assert result['data_tags'] == plan['data_tags']
        assert result['method_applicability'] == plan['method_applicability']
        assert result['input_provenance'] == plan['input_provenance'] == item['provenance']
        assert result['input_data_usage'] == plan['input_data_usage'] == item['data_usage']
        assert result['score']['value'] is None and result['review_status'] == 'pending'
        assert all(m['status'] != 'failed' for m in result['modules'])
        chosen = {f'M{i:02d}' for i in range(1,10)} if args.all_modules else {'M01', 'M02', 'M03', 'M05', 'M06', 'M08', 'M09'}
        assert set(result['selected_modules']) == chosen
        summaries = {m['id']: m for m in result['modules']}
        assert summaries['M08']['summary']['source_unchanged'] is True
        artifacts = {a['name']: a for a in result['artifacts']}
        extensions = {e['id']: e for e in result['extensions']}
        assert set(extensions) == set(available)
        assert extensions['mne_amplitude']['status'] == 'completed'
        fs = result['recording']['sampling_rate_hz']
        assert extensions['mne_muscle']['status'] == ('skipped' if fs <= 280 else 'partial')
        gates = {m['id']: m for m in plan['method_applicability']}
        assert all(e['status'] != 'failed' for e in extensions.values()), extensions
        for id_ in ('mne_bridge','mne_lof'):
            if gates[id_]['status'] == 'blocked':
                assert extensions[id_]['status'] == 'skipped'
            else:
                assert extensions[id_]['status'] in {'completed','partial'}
        assert extensions['autoreject_global']['status'] == 'partial'
        for extra in extensions.values():
            detail = call(artifacts[extra['artifact']]['url'])
            if extra['status'] == 'skipped':
                assert detail['calculated'] is False
            else:
                assert detail['input_unchanged'] is True
                assert detail['automatic_actions'] == []
                assert detail['source']['version'] and detail['source']['implementation_sha256']
                assert detail['range']['start_seconds'] == result['recording']['start_seconds']
                assert detail['context_tags'] == result['qc_config']['context_tags']
                mapping = detail['channel_mapping']
                assert len(mapping) == result['recording']['channel_count']
                assert len({c['adapter_name'] for c in mapping}) == len(mapping)
                assert [c['source_index'] for c in mapping] == result['recording']['source_indices']
        if args.all_modules and item['id'] == 'chbmit-chb01-03':
            labels = call(artifacts['M07_annotations.json']['url'])
            assert labels['clinical_event_seconds'] == 40 and labels['selected_count'] == 1
            assert labels['quality_ground_truth'] is False and labels['used_for_signal_detection'] is False
        if args.all_modules and item['id'] == 'sleep-edfx-sc4001':
            labels = call(artifacts['M07_annotations.json']['url'])
            assert labels['covered_seconds'] == 120 and labels['selected_count'] == 2
        report = call('/api/v1/jobs/' + job['id'] + '/report', raw=True).decode()
        assert '本次选择的开源增强' in report
        assert 'M03_mne_amplitude.json' in report and 'M06_mne_muscle.json' in report
        entry = {'input_id': item['id'], 'job_id': job['id'], 'plan_id': plan['plan_id'],
                 'source_sha256': result['source_sha256'], 'recording': result['recording'],
                 'extensions': result['extensions'], 'tags_frozen_in_result': True,
                 'module_statuses': {m['id']:m['status'] for m in result['modules']},
                 'clinical_context_does_not_change_eligibility': True, 'source_unchanged': True}
        runs.append(entry)
        print(item['id'], job['id'], {k: e['status'] for k, e in extensions.items()}, flush=True)
    summary = {'schema_version': 'extensions-workbench-validation/1.0', 'runs': runs,
               'clinical_accuracy_validated': False, 'browser_visual_check': 'not_performed'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    print('Verified:', args.output, flush=True)


if __name__ == '__main__':
    main()
