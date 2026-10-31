"""Fetch three pinned, unprocessed OpenNeuro SET examples and their source notes.

No waveform conversion, cleaning, inferred reference or quality labels. Downloaded
signal bytes must match the SHA256E keys at the fixed dataset Git revision.
"""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import urllib.request

REPO = Path(__file__).resolve().parents[2]
REVISION = '73b1b04c0a8e45e96c6f0682cc077a7919480fc4'
RAW = f'https://raw.githubusercontent.com/OpenNeuroDatasets/ds004504/{REVISION}/'
S3 = 'https://s3.amazonaws.com/openneuro.org/ds004504/'
SUBJECTS = {'001': ('A', '阿尔茨海默病', 'dementia'),
            '037': ('C', '健康对照', 'healthy_control'),
            '066': ('F', '额颞叶痴呆', 'dementia')}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def fetch(url, path, *, expected_sha256=None, expected_bytes=None):
    if path.exists():
        if expected_sha256 and digest(path) != expected_sha256:
            raise ValueError('Existing input differs from pinned source: ' + str(path))
        if expected_bytes is not None and path.stat().st_size != expected_bytes:
            raise ValueError('Existing input size differs from pinned source: ' + str(path))
        # Metadata uses commit-addressed URLs; compare even when a local copy exists.
        if expected_sha256 is None:
            with urllib.request.urlopen(url, timeout=60) as response:
                if response.read(2 * 1024 * 1024) != path.read_bytes():
                    raise ValueError('Existing metadata differs from fixed revision: ' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.part')
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('xb') as stream:
            total = 0
            while block := response.read(1024 * 1024):
                total += len(block)
                if total > (expected_bytes if expected_bytes is not None else 2 * 1024 * 1024):
                    raise ValueError('Source exceeds registered size budget')
                stream.write(block)
        if expected_bytes is not None and temporary.stat().st_size != expected_bytes:
            raise ValueError('Downloaded source size mismatch')
        if expected_sha256 and digest(temporary) != expected_sha256:
            raise ValueError('Downloaded source fingerprint mismatch')
        temporary.replace(path)
    return {'url': url, 'path': str(path), 'bytes': path.stat().st_size,
            'sha256': digest(path), 'official_sha256_verified': expected_sha256 is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.is_relative_to(REPO):
        parser.error('Keep signal data and local registration outside the repository')
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / 'src'))
    from ephys_qc.toolkit import prepare_recording
    files = []
    for name in ('README', 'dataset_description.json', 'participants.tsv', 'participants.json'):
        files.append(fetch(RAW + name, output / '_provenance' / name))
    description = json.loads((output / '_provenance/dataset_description.json').read_text())
    if description['License'] != 'CC0':
        raise ValueError('Dataset license changed')
    people = {row['participant_id']: row for row in csv.DictReader(
        io.StringIO((output / '_provenance/participants.tsv').read_text()), delimiter='\t')}
    records = []
    for subject, (group, label, disease) in SUBJECTS.items():
        person = people['sub-' + subject]
        if person['Group'] != group:
            raise ValueError('Participant group changed')
        stem = f'sub-{subject}/eeg/sub-{subject}_task-eyesclosed_eeg'
        files.append(fetch(RAW + stem + '.set', output / '_provenance' / f'sub-{subject}.annex-key'))
        pointer = (output / '_provenance' / f'sub-{subject}.annex-key').read_text()
        match = re.search(r'SHA256E-s(\d+)--([0-9a-f]{64})\.set', pointer)
        if not match:
            raise ValueError('Source does not expose a SHA256E key')
        files.append(fetch(S3 + stem + '.set', output / (stem + '.set'),
                           expected_bytes=int(match[1]), expected_sha256=match[2]))
        files.append(fetch(RAW + stem + '.json', output / (stem + '.json')))
        sidecar = json.loads((output / (stem + '.json')).read_text())
        age = int(person['Age'])
        config = {'selection': {'eeg_indices': list(range(19)), 'reference_indices': {},
                                'start_seconds': 0, 'duration_seconds': 120},
                  'method_config': {'comparison_groups': None},
                  'context_tags': {'disease': disease, 'age_group': 'older_adult' if age >= 65 else 'adult', 'task': 'rest'}}
        record = prepare_recording(output / (stem + '.set'), record_id='ds004504-sub' + subject,
                                   modality='scalp_eeg', qc_config=config, reference_scheme='unknown',
                                   label=f'OpenNeuro · sub-{subject} {label}闭眼静息',
                                   provenance={'name': description['Name'], 'version': '1.0.8', 'license': 'CC0',
                                               'git_revision': REVISION, 'url': 'https://openneuro.org/datasets/ds004504/versions/1.0.8',
                                               'doi': description['DatasetDOI'], 'source_branch': 'unprocessed subject folder; not derivatives'})
        channels = record['metadata']['channels']
        if len(channels) != 19 or any(c['sampling_rate_hz'] != 500 for c in channels):
            raise ValueError('Source channel/rate facts differ from declared EEG protocol')
        if abs(record['metadata']['duration_seconds'] - sidecar['RecordingDuration']) > .01:
            raise ValueError('Source length differs from sidecar')
        record.update(dataset_id='ds004504-1.0.8', subject_id='sub-' + subject,
                      profile_id='clinical_rest_set', modality_source='Fixed dataset README: 19 scalp EEG electrodes',
                      reference_evidence='README declares Cz; per-record EEGReference says A1 A2. Conflict unresolved; no comparison groups or spatial methods.',
                      preprocessing={'verified': False, 'note': 'Source metadata disagree: README acquisition high-frequency filter 70 Hz; sidecar SoftwareFilters 0.4–50. No filtering inferred or applied.'},
                      verified_electrode_coordinates=False, verified_epochs=False,
                      context_evidence={'disease': f'participants.tsv Group={group}; original label: {label}; not a QC verdict.',
                                        'age_group': f'participants.tsv Age={age}; project age grouping adult<65 / older_adult>=65.',
                                        'task': 'Dataset README and TaskName: eyes-closed resting-state EEG.'},
                      scientific_limits={'quality_labels': 'not_available', 'raw_modified': False, 'automated_cleaning': False},
                      data_usage={'typical_use': f'真实连续SET临床静息记录；来源组别：{label}。默认仅检查前120秒。',
                                  'annotations': '来源设备自动伪迹标注未公开；疾病分组不是质量标签。',
                                  'annotation_limits': '参考存在README(Cz)与侧车(A1 A2)冲突；滤波史也不一致，均保留未核实。未使用清洗后的derivatives作为干净真值。'})
        records.append(record)
        print(record['id'], record['metadata']['duration_seconds'], 'seconds, SHA256 verified', flush=True)
    save(output / 'download_manifest.json', {'dataset_version': '1.0.8', 'git_revision': REVISION, 'files': files})
    save(output / 'additions.json', {'inputs': records, 'profiles': [{'id': 'clinical_rest_set', 'name': '临床静息 SET', 'description': '连续EEGLAB临床记录；背景分组不改变质量阈值，参考冲突保留未知。'}]})


if __name__ == '__main__':
    main()
