#!/usr/bin/env python3
"""Fetch a pinned real sEEG FIF example without altering or converting its data.

Outputs a byte-identical upload copy, provenance, an independent full-sample
readback audit and a registration draft. It does not change workbench config,
register records or run QC. Requires the project's NumPy/MNE environment.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[2]
REV = 'd8ceb830cf0b05191dbde118e05f39a410567a8b'
BASE = f'https://raw.githubusercontent.com/mne-tools/mne-misc-data/{REV}/'
SOURCE = 'seeg/sample_seeg_ieeg.fif'
SIZE = 28563876
SHA256 = '76b0cfdb5708cc349d1aaf662757f477eb7c26fe396468e6a16f13b84df43ba4'
GIT_BLOB = '87bcb5f230da0a49710e52da4b5c22780c0eb694'
DOCUMENTS = {
    'LICENSE': (1510, '1b5da49b664c0a1b9fc8c7d9d797a1162092f2c9b5cabba222981afa9f6964cf'),
    'README.md': (35, '36e3930fc5e2e31f13a2d17d98926d16c7a6540c7409b6a6ce90dbabbab4c094'),
}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def fetch(relative, path, size, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.part')
        with urllib.request.urlopen(BASE + relative, timeout=60) as source, temporary.open('xb') as target:
            count = 0
            for block in iter(lambda: source.read(1024 * 1024), b''):
                count += len(block)
                if count > size:
                    raise ValueError('Pinned source exceeds expected size')
                target.write(block)
        assert temporary.stat().st_size == size and digest(temporary) == expected
        temporary.rename(path)
    assert path.stat().st_size == size and digest(path) == expected
    return {'url': BASE + relative, 'path': str(path), 'bytes': size, 'sha256': expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.expanduser().resolve()
    if out.is_relative_to(REPO):
        parser.error('Data and evidence must remain outside the repository')
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / 'src'))
    import mne
    from ephys_qc.readers import open_reader
    from audit_seeg_example import audit

    source = out / 'downloads/sample_seeg_ieeg.fif'
    source_entry = fetch(SOURCE, source, SIZE, SHA256)
    with source.open('rb') as stream:
        git_digest = hashlib.sha1(b'blob ' + str(SIZE).encode() + b'\0')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            git_digest.update(block)
    assert git_digest.hexdigest() == GIT_BLOB
    documents = [fetch(name, out / 'provenance' / name, size, sha)
                 for name, (size, sha) in DOCUMENTS.items()]
    upload = out / 'upload-samples'
    upload.mkdir(exist_ok=True)
    copy = upload / 'MNE_sEEG_sample_ieeg.fif'
    if not copy.exists():
        shutil.copyfile(source, copy)
    assert digest(copy) == SHA256
    shutil.copyfile(out / 'provenance/LICENSE', upload / 'LICENSE.mne-misc-data.txt')

    reader = open_reader(copy, 'mne-seeg-misc-fif')
    try:
        desc, metadata = reader.describe(), reader.metadata()
        stream = desc['streams'][0]
        assert len(stream['channels']) == 119
        assert all(c['channel_type'] == 'seeg' and c['unit'] == 'V' for c in stream['channels'])
        assert stream['sample_count'] == 59966 and stream['sample_index_origin'] == 1310640
        fs = stream['sampling_frequency_hz']
        events = desc['events']
        assert len(events) == 32
        event_file = out / 'derived/sample-task-events.tsv'
        event_file.parent.mkdir(exist_ok=True)
        with event_file.open('w', newline='', encoding='utf-8') as target:
            writer = csv.writer(target, delimiter='\t')
            writer.writerow(['onset', 'duration', 'event_name'])
            for event in events:
                writer.writerow([repr(event['onset_seconds']), repr(event['duration_seconds']), event['text']])
        record = {
            'id': 'mne-seeg-misc-fif', 'label': 'sEEG · MNE 按键任务 · FIF',
            'dataset_id': 'mne-misc-seeg', 'source_observation_id': 'mne-misc-seeg-sample',
            'profile_id': 'seeg_basic', 'source_path': str(copy), 'expected_sha256': SHA256,
            'expected_source_files': desc['source_files'], 'metadata': metadata,
            'modality': 'seeg', 'modality_source': 'FIF declares all 119 channels as FIFFV_SEEG_CH; official MNE sEEG tutorial identifies this exact file.',
            'reference_scheme': 'unknown',
            'reference_evidence': 'FIF custom_ref_applied=False does not identify the acquisition reference; no reference topology inferred from channel names.',
            'preprocessing': {'verified': False, 'note': 'Source is already a 60 s excerpt with nonzero first_samp. Header highpass=0 and lowpass=499.7060546875 Hz; complete prior processing is unknown. This preparation copies bytes only.'},
            'annotation': {'format': 'bids_events_tsv', 'path': str(event_file), 'source_path': str(copy),
                           'expected_sha256': digest(event_file), 'source_expected_sha256': SHA256,
                           'label_scope': 'task_events_not_quality'},
            'verified_electrode_coordinates': False, 'verified_epochs': False,
            'default_config': {'selection': {'eeg_indices': list(range(119)), 'reference_indices': {},
                                             'start_seconds': 0, 'duration_seconds': 60},
                               'method_config': {'comparison_groups': None},
                               'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'motor'}},
            'context_evidence': {'task': 'MNE official datasets overview describes a two-choice keyboard movement task; file annotations include Fixation, ISI Onset, Go Cue and Response.',
                                 'disease': 'Not independently documented for this excerpt; invasive recording alone does not establish a diagnosis.'},
            'provenance': {'name': 'MNE miscellaneous sEEG sample', 'version': REV,
                           'license': 'BSD-3-Clause (repository LICENSE)',
                           'url': 'https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html',
                           'download_url': BASE + SOURCE},
            'data_usage': {'typical_use': '真实sEEG任务片段；119道、约60秒。用于读取、时钟、基本完整性和描述性模块工程验收。',
                           'annotations': '32条来源任务标注；派生TSV将onset减去FIF first_time，保持文件内秒坐标。',
                           'annotation_limits': '任务事件不是伪迹真值；文件坐标存在不证明解剖定位已核验。'},
            'scientific_limits': {'quality_ground_truth': False, 'raw_modified': False,
                                  'original_acquisition_calibration_independently_verified': False,
                                  'original_time_origin_samples': 1310640,
                                  'file_duration_seconds': stream['sample_count'] / fs,
                                  'processing_history_complete': False},
        }
        reader.assert_unchanged(hashes=True)
        save(out / 'source-description.json', desc)
    finally:
        reader.close()
    result = audit(copy)
    save(out / 'independent-reader.json', result)
    save(out / 'additions.json', {'inputs': [record], 'profiles': [
        {'id': 'seeg_basic', 'name': 'sEEG 基础检查',
         'description': '原始触点描述性检查；不按病理放电扣分，不自动重参考或判定坏触点。'}]})
    save(out / 'download_manifest.json', {
        'source': source_entry, 'upstream_commit': REV, 'upstream_git_blob_sha1': GIT_BLOB,
        'git_blob_verified': True, 'sha256_kind': 'Locally pinned digest of upstream commit bytes, not a separately published official SHA-256',
        'license': 'BSD-3-Clause (repository LICENSE retained with local copy)',
        'background_documents': documents,
        'source_observation_count': 1, 'representation_count': 1, 'byte_identical_upload_copy': True,
        'upload_samples': [{'path': str(copy), 'bytes': SIZE, 'sha256': SHA256}],
        'processing_applied': [], 'fif_rewritten': False,
        'software': {'mne': mne.__version__}, 'script_sha256': digest(Path(__file__))})
    (upload / 'README.txt').write_text(
        'sEEG公开上传样例\n\nMNE_sEEG_sample_ieeg.fif 是官方公开文件的逐字节副本，没有转换、滤波、重参考、删道或重新保存FIF。\n'
        '119个sEEG源通道，59966样本，采样率999.412109375Hz，时长约60.001274秒；32条任务标注。\n'
        '文件来自较长记录的片段，first_samp=1310640；工作台文件内0秒不等于原采集0秒。\n'
        '上传后应显示sEEG建议，并等待用户确认后运行。默认登记检查文件内0–60秒。\n'
        '原始文件附有坐标，但本次未独立核验解剖定位、采集参考或患者诊断；不作为坏触点/伪迹金标准。\n'
        'LICENSE.mne-misc-data.txt 保留上游许可；仅将 .fif 文件上传质控台。\n', encoding='utf-8')
    print(json.dumps({'status': 'prepared', 'output': str(out), 'source_observation_count': 1,
                      'all_samples_verified': True, 'sample_count': 59966}, ensure_ascii=False))


if __name__ == '__main__':
    main()
