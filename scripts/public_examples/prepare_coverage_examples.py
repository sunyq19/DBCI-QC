"""Download and register 12 fixed public coverage examples; never run QC or edit a workbench registry.

Place coverage_examples_sources.json next to this script. Requires the repository's
scientific Python environment for source inspection and independent label extraction.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import urllib.request


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', required=True, type=Path, help='Destination outside the source repository')
    p.add_argument('--evidence-dir', required=True, type=Path, help='Output additions, derivations and verification evidence')
    p.add_argument('--repo-root', required=True, type=Path, help='Checkout containing src/ephys_qc')
    p.add_argument('--reuse-eegmmidb-dir', type=Path, help='Optional existing directory containing S003R01.edf/S003R02.edf; verified in place')
    p.add_argument('--sources', type=Path, default=Path(__file__).with_name('coverage_examples_sources.json'))
    p.add_argument('--offline', action='store_true', help='Only verify and reuse existing files; never access network')
    args = p.parse_args()
    for key in ('data_root', 'evidence_dir', 'repo_root', 'sources'):
        setattr(args, key, getattr(args, key).resolve())
    if args.reuse_eegmmidb_dir:
        args.reuse_eegmmidb_dir = args.reuse_eegmmidb_dir.resolve()
    if not (args.repo_root / 'src/ephys_qc').is_dir():
        p.error('--repo-root does not contain src/ephys_qc')
    if args.data_root == args.repo_root or args.repo_root in args.data_root.parents:
        p.error('--data-root must be outside the repository')
    if args.evidence_dir == args.repo_root or args.repo_root in args.evidence_dir.parents:
        p.error('--evidence-dir must be outside the repository')
    args.data_root.mkdir(parents=True, exist_ok=True)
    args.evidence_dir.mkdir(parents=True, exist_ok=True)
    return args


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def collect(args):
    spec = json.loads(args.sources.read_text(encoding='utf-8'))
    files = spec['files']
    if sum(row['bytes'] for row in files) > 1024**3:
        raise ValueError('Fixed source plan exceeds the 1 GiB download budget')
    native, physio, all_files = [], [], []
    transferred = 0
    for row in files:
        relative = Path(row['relative_path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source destination in fixed manifest')
        path = args.data_root / relative
        if args.reuse_eegmmidb_dir and row['dataset'] == 'eegmmidb' and path.name in {'S003R01.edf', 'S003R02.edf'}:
            existing = args.reuse_eegmmidb_dir / path.name
            if existing.is_file():
                path = existing
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise ValueError('Source must be a regular file, not a symbolic link: ' + path.name)
        if path.exists():
            operation = 'reused_existing_verified'
        else:
            if args.offline:
                raise FileNotFoundError('Offline source missing: ' + str(path))
            temp = path.with_name(path.name + '.partial')
            if temp.exists():
                raise FileExistsError('Unfinished download exists; inspect/remove it before retrying: ' + str(temp))
            request = urllib.request.Request(row['url'], headers={'User-Agent': 'DBCI-QC-public-coverage/1.0'})
            with urllib.request.urlopen(request, timeout=60) as response, temp.open('xb') as output:
                while True:
                    block = response.read(1024**2)
                    if not block:
                        break
                    transferred += len(block)
                    output.write(block)
                    if output.tell() > row['bytes'] or transferred > 1024**3:
                        raise ValueError('Source exceeded its fixed size or the transfer budget')
            if temp.stat().st_size != row['bytes'] or sha_file(temp) != row['sha256']:
                raise ValueError('Downloaded source differs from the fixed version; original target was not replaced')
            temp.rename(path)
            operation = 'downloaded'
        if path.stat().st_size != row['bytes'] or sha_file(path) != row['sha256']:
            raise ValueError('Existing source differs from fixed SHA256; refusing to overwrite: ' + path.name)
        entry = {**row, 'path': str(path), 'sha256': row['sha256'], 'official_expected_sha256': row['sha256'],
                 'official_hash_verified': True, 'operation': operation, 'relative': row['dataset_relative_path']}
        all_files.append(entry)
        if row['dataset'] == 'ds006386':
            physio.append(entry)
        elif row['role'] != 'official_checksum_manifest':
            native.append(entry)
        print(operation, relative, row['bytes'], flush=True)
    # Cross-check PhysioNet payload hashes against the downloaded official manifests.
    for entry in native:
        manifest_path = args.data_root / (entry['dataset'] + '-' + entry['version']) / '_provenance/official_SHA256SUMS.txt'
        hashes = {line.split(maxsplit=1)[1].lstrip('*'): line.split()[0] for line in manifest_path.read_text().splitlines() if line.strip()}
        if hashes.get(entry['relative']) != entry['sha256']:
            raise ValueError('Official dataset checksum list disagrees with frozen source entry')
    common = {'created_at': datetime.now(timezone.utc).isoformat(), 'transferred_bytes': transferred,
              'errors': [], 'registry_modified': False, 'signal_algorithms_run': False}
    save(args.evidence_dir / 'download_manifest.json', {**common, 'files': native})
    save(args.evidence_dir / 'physiomotion-download-manifest.json', {**common, 'files': physio,
         'dataset_id': 'ds006386', 'version': '1.0.1', 'license': 'CC0',
         'license_source': 'dataset_description.json at fixed official metadata commit'})
    save(args.evidence_dir / 'coverage-download-manifest.json', {**common, 'files': all_files,
         'licenses': spec['datasets'], 'total_source_bytes': sum(r['bytes'] for r in all_files)})


def prepare_native_examples(args):
    """Freeze public coverage inputs without modifying the workbench registry or running QC."""
    from pathlib import Path
    from datetime import datetime, timezone
    from collections import Counter
    import csv
    import hashlib
    import json
    import re
    import sys

    ROOT = args.evidence_dir
    REPO = args.repo_root
    sys.path.insert(0, str(REPO / 'src'))
    import mne
    from ephys_qc.toolkit import prepare_recording, build_plan, recommend
    from ephys_qc.annotations import check_annotations

    DATA = args.data_root
    DERIVED = ROOT / 'derived'
    DERIVED.mkdir(exist_ok=True)
    SOURCES = json.loads((ROOT / 'download_manifest.json').read_text())['files']
    SOURCE = {Path(x['path']).name: x for x in SOURCES}
    ODC = 'Open Data Commons Attribution License v1.0 (ODC-By-1.0)'
    LICENSES = {'eegmmidb': ODC, 'chbmit': ODC, 'sleep-edfx': ODC, 'hmc-sleep-staging': 'Creative Commons Attribution 4.0 International (CC BY 4.0)'}


    def sha(p):
        h = hashlib.sha256()
        with Path(p).open('rb') as f:
            for block in iter(lambda: f.read(1024**2), b''):
                h.update(block)
        return h.hexdigest()


    def dump(p, value):
        Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


    def tsv(path, columns, rows):
        with path.open('w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=columns, delimiter='\t')
            w.writeheader()
            w.writerows(rows)


    def annotations(path):
        a = mne.read_annotations(path)
        return [{'onset_s': float(t), 'duration_s': float(d), 'label': str(label)}
                for t, d, label in zip(a.onset, a.duration, a.description)]


    def annotated(record, path, source, kind, scope, details):
        record['annotation'] = {'path': str(path), 'source_path': str(source), 'format': kind,
                                'label_scope': scope, 'expected_sha256': sha(path),
                                'source_expected_sha256': sha(source)}
        dump(path.with_suffix('.derivation.json'), {'source_path': str(source), 'source_sha256': sha(source),
             'derived_path': str(path), 'derived_sha256': sha(path), 'quality_ground_truth': False,
             'used_for_signal_detection': False, **details})


    def make(code, record_id, label, dataset, profile, indices, refs, start, duration, task,
             reference='unknown', groups=None, disease='unknown', description='', usage=None):
        item = SOURCE[code + '.edf']
        slug, version = item['dataset'], item['version']
        record = prepare_recording(item['path'], record_id=record_id, modality='scalp_eeg',
             label=label, reference_scheme=reference,
             qc_config={'selection': {'eeg_indices': indices, 'reference_indices': refs,
                                     'start_seconds': start, 'duration_seconds': duration},
                        'method_config': {'comparison_groups': groups},
                        'context_tags': {'disease': disease, 'age_group': 'unknown', 'task': task}},
             provenance={'name': dataset, 'url': f'https://physionet.org/content/{slug}/{version}/',
                         'version': version, 'license': LICENSES[slug],
                         'license_url': f'https://physionet.org/content/{slug}/view-license/{version}/',
                         'waveform_url': item['url'], 'official_sha256_verified': True})
        record.update(dataset_id=f'{slug}-{version}', profile_id=profile, description=description,
                      modality_source='公开数据集说明确认头皮EEG；源通道角色经技术头逐项核对，不由扩展名推断。',
                      verified_electrode_coordinates=False, verified_epochs=False,
                      preprocessing={'verified': False}, data_usage=usage or {},
                      scientific_limits={'quality_labels': 'not_available', 'raw_modified': False,
                          'automated_cleaning': False, 'coordinates': 'not_inferred',
                          'independent_accuracy_validation': False})
        record['selection_evidence'] = {'selected_eeg': [
             {'source_index': i, 'name': record['metadata']['channels'][i]['name'],
              'sampling_rate_hz': record['metadata']['channels'][i]['sampling_rate_hz']}
             for i in indices], 'reference_indices': refs,
             'rule': '保留源索引、重复标签及双极导联身份；不重参考、不重采样、不自动合并。'}
        return record


    records = []
    tasks = {'S003R01': ('睁眼静息', 'rest', 61), 'S003R02': ('闭眼静息', 'rest', 61),
             'S004R02': ('闭眼静息', 'rest', 61), 'S005R03': ('真实左右握拳', 'motor', 120),
             'S006R04': ('想象左右握拳', 'motor_imagery', 120), 'S007R05': ('真实双拳或双足运动', 'motor', 120),
             'S008R06': ('想象双拳或双足运动', 'motor_imagery', 120)}
    protocol = 'https://archive.physionet.org/physiobank/database/eegmmidb/'
    for code, (name, task, length) in tasks.items():
        profile = {'rest': 'adult_multichannel_rest', 'motor': 'multichannel_motor_execution',
                   'motor_imagery': 'multichannel_motor_imagery'}[task]
        r = make(code, 'eegmmidb-' + code.lower(), f'EEGMMIDB · {code} {name}',
             'PhysioNet EEG Motor Movement/Imagery Dataset', profile, list(range(64)), {}, 0, length, task,
             description=f'64道160 Hz；官方运行协议为{name}，参考未核实。',
             usage={'typical_use': '跨受试者及运动/想象场景覆盖；检查报告适用性和事件解释。',
                    'annotations': '官方运行条件与EDF+ T0/T1/T2事件。',
                    'annotation_limits': '任务条件或时段不是坏道/伪迹真值；profile历史名称含adult不构成年龄证据，age_group仍unknown。'})
        assert len(r['metadata']['channels']) == 64
        assert all(c['sampling_rate_hz'] == 160 and c['unit'] == 'uV' for c in r['metadata']['channels'])
        r['source_participant_key'] = code[:4]
        r['reference_evidence'] = '已核对官方数据说明及技术头；具体采集参考未确认，comparison_groups=null。'
        r['context_evidence'] = {'task': f'官方运行{code[-2:]}：{name}。', 'url': protocol,
                                  'age_group': '未单独核实，保持unknown。', 'disease': '未单独核实，保持unknown。'}
        r['preprocessing']['note'] = '技术头占位HP:0Hz LP:0Hz N:0Hz不作为已核实频带或处理历史。'
        if task != 'rest':
            run = int(code[-2:])
            effect = 'motor_execution' if task == 'motor' else 'motor_imagery'
            taskmap = {'T0': 'rest', 'T1': ('left_fist_' if run in (3, 4) else 'both_fists_') + effect,
                       'T2': ('right_fist_' if run in (3, 4) else 'both_feet_') + effect}
            raw = annotations(r['source_path'])
            assert set(x['label'] for x in raw) <= set(taskmap)
            path = DERIVED / (code + '_task_events.derived.tsv')
            tsv(path, ['onset', 'duration', 'event_name', 'event_value'],
                [{'onset': x['onset_s'], 'duration': x['duration_s'],
                  'event_name': taskmap[x['label']], 'event_value': x['label']} for x in raw])
            annotated(r, path, Path(r['source_path']), 'bids_events_tsv', 'task_events_not_quality',
                      {'method': 'MNE read_annotations; retain original record-relative onset and duration; decode only the specified run',
                       'mapping': taskmap, 'mapping_source': protocol, 'source_rows': len(raw),
                       'adapter_name_limit': 'bids_events_tsv is an adapter name, not a claim of BIDS dataset compliance'})
        records.append(r)

    for code, participant, start, expected in [('chb02_16', 'chb02', 120, (130, 212)),
                                             ('chb03_01', 'chb03', 350, (362, 414))]:
        summary = Path(SOURCE[participant + '-summary.txt']['path'])
        section = summary.read_text().split('File Name: ' + code + '.edf\n', 1)[1].split('\nFile Name:', 1)[0]
        starts = [int(x) for x in re.findall(r'Seizure(?: \d+)? Start Time: (\d+) seconds', section)]
        stops = [int(x) for x in re.findall(r'Seizure(?: \d+)? End Time: (\d+) seconds', section)]
        assert list(zip(starts, stops)) == [expected]
        r = make(code, 'chbmit-' + code.replace('_', '-'), f'CHB-MIT · {code} 临床发作',
             'PhysioNet CHB-MIT Scalp EEG Database', 'bipolar_clinical_eeg', list(range(23)), {}, start, 120,
             'unknown', reference='bipolar', disease='epilepsy',
             description=f'23条双极EEG，256 Hz；默认{start}–{start+120}秒包含官方发作区间。',
             usage={'typical_use': '独立病例中临床发作与伪迹线索的边界核对。',
                    'annotations': f'官方summary发作时间{expected[0]}–{expected[1]}秒；保留原始.seizures伴随文件。',
                    'annotation_limits': '发作不是伪迹；未标注区间不表示信号正常，疾病背景不改变质量阈值。'})
        assert len(r['metadata']['channels']) == 23
        assert all(c['sampling_rate_hz'] == 256 and c['unit'] == 'uV' for c in r['metadata']['channels'])
        r['source_participant_key'] = participant
        r['reference_evidence'] = '官方summary和逐道技术标签为双极链；无公共参考跨道组，comparison_groups=null。'
        names = [c['name'] for c in r['metadata']['channels']]
        r['selection_evidence']['duplicate_labels'] = [{'name': n, 'source_indices': [i for i, x in enumerate(names) if x == n]}
            for n, count in Counter(names).items() if count > 1]
        r['selection_evidence']['reverse_pair'] = {'source_indices': [2, 18], 'names': [names[2], names[18]],
                                                  'note': '源双极反向导联保持独立身份，不当作公共参考电极。'}
        r['context_evidence'] = {'disease': '官方临床发作监测队列背景；非平台诊断。',
                                'age_group': '未逐例核实年龄，不能由数据库名称推断child。', 'task': '未知。'}
        path = DERIVED / (code + '_clinical_events.derived.tsv')
        tsv(path, ['onset_s', 'duration_s', 'label', 'label_type'],
            [{'onset_s': a, 'duration_s': b-a, 'label': 'seizure', 'label_type': 'seizure'} for a, b in zip(starts, stops)])
        annotated(r, path, summary, 'clinical_events_tsv', 'clinical_events_not_quality',
                  {'method': 'parse only matching File Name section; source seconds relative to that EDF',
                   'source_file_section': code + '.edf', 'events': [{'onset_s': a, 'end_s': b} for a, b in zip(starts, stops)],
                   'unlabelled_means_normal': False})
        records.append(r)


    def sleep_annotation(record, original, mapping, standard):
        raw = annotations(original)
        dump(DERIVED / (Path(original).stem + '.original_extracted.json'), raw)
        with Path(record['source_path']).open('rb') as f:
            f.seek(168); waveform_clock = f.read(16)
        with Path(original).open('rb') as f:
            f.seek(168); annotation_clock = f.read(16)
        assert waveform_clock == annotation_clock, 'EDF start clocks differ; do not assume zero offset'
        duration = record['metadata']['duration_seconds']
        rows, excluded = [], []
        for num, x in enumerate(raw, 1):
            left, right = max(0, x['onset_s']), min(duration, x['onset_s'] + x['duration_s'])
            if x['label'] not in mapping or right <= left:
                excluded.append({'source_annotation': num, **x, 'reason': 'non_stage_marker' if x['label'] not in mapping else 'outside_recorded_waveform'})
                continue
            rows.append({'onset_s': left, 'duration_s': right-left, 'end_s': right,
                         'stage': mapping[x['label']], 'label_type': standard,
                         'source_label': x['label'], 'source_annotation': num})
        path = DERIVED / (Path(record['source_path']).stem + '_state_intervals.derived.tsv')
        tsv(path, ['onset_s', 'duration_s', 'end_s', 'stage', 'label_type', 'source_label', 'source_annotation'], rows)
        annotated(record, path, original, 'sleep_stages_tsv', 'sleep_state_not_quality',
                  {'method': 'MNE read_annotations; intersect stage intervals with waveform duration; retain source staging taxonomy',
                   'mapping': mapping, 'raw_rows': len(raw), 'derived_rows': len(rows), 'excluded_rows': excluded,
                   'clock_check': 'PSG and annotation EDF fixed start-date/start-time fields agree; absolute values not copied',
                   'hardware_synchronization_independently_verified': False})
        return rows


    r = make('SN061', 'hmc-sn061', 'HMC · SN061 N3睡眠与辅助导联',
             'PhysioNet Haaglanden Medisch Centrum sleep staging database', 'sparse_psg_with_auxiliary',
             [0, 1, 2, 3], {'emg': 4, 'eog': 5, 'ecg': 7}, 1830, 120, 'sleep',
             reference='mixed', groups=['M1', 'M1', 'M1', 'M2'],
             description='4道EEG与同钟EOG/ECG/EMG均256 Hz；前三道M1、第四道M2，默认N3分期窗口。',
             usage={'typical_use': '深睡慢波背景和真实生理辅助导联的报告边界核对。',
                    'annotations': '官方AASM 2.4人工睡眠分期；默认1830–1950秒为N3。',
                    'annotation_limits': 'N3慢波不是坏段真值；睡眠障碍转诊队列不证明本例具体疾病。'})
    assert [c['name'] for c in r['metadata']['channels']] == ['EEG F4-M1', 'EEG C4-M1', 'EEG O2-M1', 'EEG C3-M2', 'EMG chin', 'EOG E1-M2', 'EOG E2-M2', 'ECG']
    assert all(c['sampling_rate_hz'] == 256 and c['unit'] == 'uV' for c in r['metadata']['channels'])
    r['source_participant_key'] = 'SN061'
    r['reference_evidence'] = '技术标签与官方导联说明一致；仅声明M1/M1/M1/M2分组，不混为单一公共参考。'
    r['context_evidence'] = {'task': '官方PSG及分期。', 'disease': '个体诊断未确认，保持unknown。', 'age_group': '未单独核实。'}
    r['selection_evidence']['not_selected'] = {'source_indices': [6], 'reason': '当前接口每类辅助导联一个整数；E2-M2保留在源信息中，不丢失原文件。'}
    sleep_annotation(r, Path(SOURCE['SN061_sleepscoring.edf']['path']),
         {'Sleep stage W': 'W', 'Sleep stage N1': 'N1', 'Sleep stage N2': 'N2', 'Sleep stage N3': 'N3', 'Sleep stage R': 'REM'}, 'sleep_state_AASM_2.4')
    records.append(r)

    r = make('SC4021E0-PSG', 'sleep-edfx-sc4021', 'Sleep-EDF · SC4021 R&K深睡',
             'PhysioNet Sleep-EDF Database Expanded', 'sparse_bipolar_sleep', [0, 1], {'eog': 2}, 0, 120, 'sleep',
             reference='bipolar', disease='healthy_control',
             description='2道双极EEG与同钟EOG为100 Hz；其余辅助流1 Hz，保留R&K 3/4原始分期体系。',
             usage={'typical_use': '独立参与者的少导联低采样率深睡场景。',
                    'annotations': '官方R&K 1968人工分期；默认窗按首个连续深睡至少120秒区间选择。',
                    'annotation_limits': 'R&K 3/4不自动合并为AASM N3；分期不是质量真值；1 Hz EMG包络不是原始肌电。'})
    assert [c['name'] for c in r['metadata']['channels'][:3]] == ['EEG Fpz-Cz', 'EEG Pz-Oz', 'EOG horizontal']
    assert all(c['sampling_rate_hz'] == 100 and c['unit'] == 'uV' for c in r['metadata']['channels'][:3])
    assert all(c['sampling_rate_hz'] == 1 for c in r['metadata']['channels'][3:])
    r['source_participant_key'] = 'SC02'
    r['reference_evidence'] = 'Fpz-Cz/Pz-Oz双极导联，不声明公共参考或跨道比较组。'
    r['context_evidence'] = {'task': '官方SC睡眠研究与人工分期。',
                             'disease': '官方SC健康研究招募背景，不是平台诊断。', 'age_group': '未逐例核实。'}
    r['selection_evidence']['not_selected'] = {'source_indices': [3, 4, 5, 6], 'reason': '原生1 Hz；含处理后的肌电包络及非EEG技术流，不做隐式重采样。'}
    rows = sleep_annotation(r, Path(SOURCE['SC4021EH-Hypnogram.edf']['path']),
         {'Sleep stage W': 'W', 'Sleep stage R': 'REM', 'Sleep stage 1': 'R&K 1', 'Sleep stage 2': 'R&K 2',
          'Sleep stage 3': 'R&K 3', 'Sleep stage 4': 'R&K 4', 'Movement time': 'Movement', 'Sleep stage ?': 'Unknown'}, 'sleep_state_RK1968')
    merged = []
    for row in rows:
        if row['stage'] not in {'R&K 3', 'R&K 4'}:
            continue
        a, b = row['onset_s'], row['end_s']
        if merged and abs(merged[-1][1] - a) < 1e-6:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    start = next(a for a, b in merged if b-a >= 120)
    r['default_config']['selection']['start_seconds'] = start
    r['data_usage']['annotations'] += f' 当前默认{start:g}–{start+120:g}秒；逐行分期未合并。'
    records.append(r)

    validations = []
    for r in records:
        plan = build_plan(r, ['M03', 'M04', 'M05', 'M06', 'M07'])
        rec = recommend(r)
        selection = r['default_config']['selection']
        annotation_result = None
        if r.get('annotation'):
            annotation_result = check_annotations(r['annotation'], selection['start_seconds'], selection['duration_seconds'],
                 r['metadata']['channels'][selection['eeg_indices'][0]]['sampling_rate_hz'],
                 r['metadata']['duration_seconds'])
            assert not annotation_result['issues'], (r['id'], annotation_result['issues'])
        validations.append({'id': r['id'], 'plan_id': plan['plan_id'], 'plan_nodes': plan['nodes'],
                            'recommendation_status': rec['status'], 'can_apply': rec['can_apply'],
                            'annotation_check': annotation_result, 'signal_algorithms_run': False})
        print(r['id'], len(selection['eeg_indices']), selection['start_seconds'], selection['duration_seconds'],
              'annotation_rows=' + str(annotation_result['selected_count'] if annotation_result else 0), flush=True)

    assert len(records) == 11 and len({r['id'] for r in records}) == 11
    profiles = [{'id': i, 'name': n, 'description': d} for i, n, d in [
        ('adult_multichannel_rest', '多通道静息EEG', '历史profile ID不构成年龄证据；个体背景另行登记。'),
        ('multichannel_motor_execution', '真实运动EEG', '按官方run协议解释任务事件。'),
        ('multichannel_motor_imagery', '运动想象EEG', '想象与真实运动事件分开。'),
        ('bipolar_clinical_eeg', '双极临床EEG', '临床事件不等于质量标签。'),
        ('sparse_psg_with_auxiliary', '少导联PSG与辅助信号', '不同参考分组与同钟辅助导联明确登记。'),
        ('sparse_bipolar_sleep', '少导联双极睡眠EEG', '保留原始分期体系与多采样率边界。')]]
    dump(ROOT / 'additions.json', {'schema_version': 'ephys-coverage-additions/1.0',
         'created_at': datetime.now(timezone.utc).isoformat(), 'inputs': records, 'profiles': profiles,
         'scope': '11 additional public records for report coverage; no detector accuracy claims',
         'source_manifest': str(ROOT / 'download_manifest.json'),
         'notes': ['11 records are not 11 independent participants: EEGMMIDB S003 contributes paired runs.',
                   'No workbench registry or repository source was modified.',
                   'No QC signal algorithms were executed by this preparation script.']})
    dump(ROOT / 'registration-validation.json', validations)
    dump(ROOT / 'derived-manifest.json', [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': sha(p)}
         for p in sorted(DERIVED.iterdir()) if p.is_file()])
    print('ADDITIONS READY', ROOT / 'additions.json')


def prepare_physiomotion_example(args):
    """Register a fixed public artifact-labelled source without feeding labels to detectors."""
    from pathlib import Path
    from datetime import datetime, timezone
    from collections import Counter
    import csv
    import hashlib
    import json
    import math
    import sys

    ROOT = args.evidence_dir
    REPO = args.repo_root
    sys.path.insert(0, str(REPO / 'src'))
    from ephys_qc.toolkit import prepare_recording, build_plan, recommend

    DATA = args.data_root / 'ds006386-1.0.1'
    SOURCE = DATA / 'sub-1/eeg/sub-1_task-artifact_run-01_eeg.edf'
    LABELS = DATA / 'derivatives/Manual_Annotations/sub1_run01.csv'
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    dump = lambda p, x: Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    manifest = json.loads((ROOT / 'physiomotion-download-manifest.json').read_text())
    for x in manifest['files']:
        assert sha(x['path']) == x['official_expected_sha256']
    sidecar = json.loads((SOURCE.with_suffix('.json')).read_text())
    with (DATA / 'sub-1/eeg/sub-1_task-artifact_run-01_channels.tsv').open(encoding='utf-8-sig', newline='') as f:
        channels = list(csv.DictReader(f, delimiter='\t'))
    assert len(channels) == 59 and all(c['type'] == 'EEG' for c in channels)

    record = prepare_recording(SOURCE, record_id='physiomotion-sub1-run01', modality='scalp_eeg',
        label='PhysioMotion · sub-1 run-01 人工伪迹标签', reference_scheme='unknown',
        qc_config={'selection': {'eeg_indices': list(range(59)), 'reference_indices': {},
                                 'start_seconds': 300, 'duration_seconds': 120},
                   'method_config': {'comparison_groups': None},
                   'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'other'}},
        provenance={'name': 'PhysioMotion_Artifact',
            'url': 'https://openneuro.org/datasets/ds006386/versions/1.0.1', 'version': '1.0.1',
            'doi': '10.18112/openneuro.ds006386.v1.0.1', 'license': 'CC0',
            'license_source': '固定版本 dataset_description.json 的 License 字段',
            'license_url': 'https://creativecommons.org/publicdomain/zero/1.0/',
            'waveform_url': 'https://s3.amazonaws.com/openneuro.org/ds006386/sub-1/eeg/sub-1_task-artifact_run-01_eeg.edf',
            'pinned_metadata_commit': '647f61744019ad41801598384bb461b7fdc06560',
            'article_url': 'https://doi.org/10.1038/s41597-026-07120-7',
            'official_sha256_verified': True})
    meta = record['metadata']
    assert len(meta['channels']) == 59
    assert [c['name'] for c in meta['channels']] == [c['name'] for c in channels]
    assert all(c['unit'] == 'uV' and c['sampling_rate_hz'] == 1000 for c in meta['channels'])
    assert sidecar['EEGReference'] == 'n/a'
    with LABELS.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    assert set(rows[0]) == {'channel', 'start_time', 'stop_time', 'label'}
    for row in rows:
        a, b = float(row['start_time']), float(row['stop_time'])
        assert math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= meta['duration_seconds']
    selected = [r for r in rows if float(r['start_time']) < 420 and float(r['stop_time']) > 300]
    record.update(dataset_id='ds006386-1.0.1', profile_id='multichannel_artifact_protocol',
        description='59道1000 Hz；300–420秒包含来源人工blink/hor_eyem标签。原信号与标签均未重参考或转换。',
        modality_source='官方数据集头皮EEG说明、59道EEG sidecar与源技术标签一致；非扩展名推断。',
        source_participant_key='sub-1', verified_electrode_coordinates=False, verified_epochs=False,
        preprocessing={'verified': False, 'note': 'sidecar 声明0–250 Hz，未独立核实采集/处理传递函数。'},
        reference_evidence='eeg.json明确EEGReference=n/a，reference_scheme=unknown，comparison_groups=null。',
        context_evidence={'task': '官方artifact任务及人工注释；无疾病或年龄推断。',
                          'disease': '未逐例核实，保持unknown。', 'age_group': '未逐例核实，保持unknown。'},
        selection_evidence={'source_indices': list(range(59)),
            'rule': '逐道名称与channels.tsv一致；使用EDF物理uV及1000 Hz原生时钟；不转换成标签所用双极导联。',
            'sidecar_unit_declaration': 'channels.tsv写V；EDF物理头为uV，读取器按EDF标定返回物理单位，不直接套用sidecar数值缩放。',
            'record_duration_note': 'EDF样本数对应1252.0秒；sidecar RecordingDuration=1251.999秒相当于最后一个样本时间，不据此裁掉末采样。'},
        data_usage={'typical_use': '人工眼部/运动伪迹标签下的候选定位和报告语义核查；准确率评估前需完成标注导联映射。',
            'annotations': 'Manual_Annotations CSV共382行，含ALL基线/活动段及双极导联伪迹；默认窗26行blink/hor_eyem。',
            'annotation_limits': '原始59道为单电极命名，标签导联含Fp1-F7等双极对及ALL；未作双极转换，不能直接按单电极算TP/FP/FN或准确率。baseline条件不证明全窗无伪迹。'},
        quality_reference={'path': str(LABELS), 'format': 'physiomotion_manual_artifact_csv',
            'source_url': 'https://s3.amazonaws.com/openneuro.org/ds006386/derivatives/Manual_Annotations/sub1_run01.csv',
            'expected_sha256': sha(LABELS), 'label_scope': 'manual_artifact_and_protocol_labels',
            'status': 'montage_alignment_pending', 'channel_semantics': 'ALL or source bipolar derivation label',
            'time_semantics': 'source record-relative seconds; original start_time/stop_time retained',
            'used_for_signal_detection': False, 'passed_to_M07': False,
            'independent_single_electrode_accuracy_ready': False, 'source_rows': len(rows),
            'selected_rows': len(selected), 'selected_labels': sorted({r['label'] for r in selected}),
            'mapping_performed': False, 'rereferencing_performed': False},
        scientific_limits={'quality_labels': 'manual_source_available_montage_alignment_pending',
            'raw_modified': False, 'automated_cleaning': False, 'independent_accuracy_validation': False})
    assert 'annotation' not in record
    plan = build_plan(record, ['M03', 'M04', 'M05', 'M06', 'M07'])
    rec = recommend(record)
    dump(ROOT / 'physiomotion-additions.json', {'schema_version': 'ephys-coverage-additions/1.0',
        'created_at': datetime.now(timezone.utc).isoformat(), 'inputs': [record],
        'profiles': [{'id': 'multichannel_artifact_protocol', 'name': '多通道人工伪迹协议',
                       'description': '质量来源标签独立保存，未作为信号检测或M07事件输入。'}],
        'source_manifest': str(ROOT / 'physiomotion-download-manifest.json'),
        'scope': 'Public artifact-labelled source; montage alignment pending; no detector accuracy claims'})
    dump(ROOT / 'physiomotion-registration-validation.json', {'id': record['id'], 'plan_id': plan['plan_id'],
        'plan_nodes': plan['nodes'], 'recommendation_status': rec['status'], 'can_apply': rec['can_apply'],
        'official_hashes_verified': True, 'label_rows': len(rows), 'selected_label_rows': len(selected),
        'label_counts': dict(Counter(r['label'] for r in rows)),
        'selected_label_counts': dict(Counter(r['label'] for r in selected)),
        'label_mapping_status': 'montage_alignment_pending', 'quality_labels_passed_to_detector': False,
        'signal_algorithms_run': False})
    print('PHYSIOMOTION ADDITION READY', ROOT / 'physiomotion-additions.json', flush=True)


def main():
    args = parse_args()
    collect(args)
    prepare_native_examples(args)
    prepare_physiomotion_example(args)
    print('Ready: additions.json and physiomotion-additions.json; no QC jobs created.', flush=True)


if __name__ == '__main__':
    main()
