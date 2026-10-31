#!/usr/bin/env python3
"""Prepare one pinned public ECoG observation and a lossless FIF upload copy.

Requires the scientific environment (NumPy and MNE). Downloaded data, derived
files, registration drafts and evidence stay outside the repository. No QC job,
filtering, re-referencing, resampling, label-driven exclusion or cleaning runs.
"""
import argparse
import configparser
import csv
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[2]
URL = 'https://github.com/mne-tools/mne-data/releases/download/epilepsy_ecog-1/MNE-epilepsy-ecog-data.tar.gz'
SHA256 = '1af4d3566f33cc002d2ee3d7444f8bff6906f36aa743ae309b6a3fcab48e0fae'
MD5 = 'ffb139174afa0f71ec98adbbb1729dea'
SIZE = 88160485
UPSTREAM_REV = '62b403d544f42c095035efebafe43cb9479b32bd'
STEM = 'sub-pt1_ses-presurgery_task-ictal'


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def fetch(url, path, expected=None, size=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary = path.with_suffix(path.suffix + '.part')
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open('xb') as target:
            total = 0
            for chunk in iter(lambda: response.read(1024 * 1024), b''):
                total += len(chunk)
                if total > (size if size is not None else 2 * 1024 * 1024):
                    raise ValueError('Download exceeded fixed size budget')
                target.write(chunk)
        if size is not None and temporary.stat().st_size != size:
            raise ValueError('Downloaded source size mismatch')
        if expected and digest(temporary) != expected:
            raise ValueError('Downloaded source fingerprint mismatch')
        temporary.rename(path)
    if expected and digest(path) != expected:
        raise ValueError('Existing source differs from pinned source')
    if size is not None and path.stat().st_size != size:
        raise ValueError('Existing source size mismatch')
    return {'url': url, 'path': str(path), 'bytes': path.stat().st_size,
            'sha256': digest(path), 'official_sha256_verified': expected is not None}


def ini(path):
    text = path.read_text(encoding='utf-8-sig')
    header = text[text.index('[Common Infos]'):].split('[Comment]')[0]
    parser = configparser.ConfigParser(interpolation=None)
    parser.read_string(header)
    return parser


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.expanduser().resolve()
    if out.is_relative_to(REPO):
        parser.error('Data and evidence must remain outside the repository')
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / 'src'))
    import numpy as np
    import mne
    from mne._fiff.constants import FIFF
    from ephys_qc.readers import open_reader

    archive = out / 'downloads/MNE-epilepsy-ecog-data.tar.gz'
    download = fetch(URL, archive, SHA256, SIZE)
    assert digest(archive, 'md5') == MD5
    data_root = out / 'data'
    data_root.mkdir(exist_ok=True)
    with tarfile.open(archive, 'r:gz') as handle:
        for member in handle.getmembers():
            target = (data_root / member.name).resolve()
            if not target.is_relative_to(data_root.resolve()) or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            if member.isfile():
                value = handle.extractfile(member).read()
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.read_bytes() != value:
                    raise ValueError('Existing extracted source differs from archive')
                if not target.exists():
                    target.write_bytes(value)
    dataset = data_root / 'MNE-epilepsy-ecog-data'
    description = json.loads((dataset / 'dataset_description.json').read_text())
    assert description['License'] == 'CC0'
    docs = []
    for name in ['README', 'dataset_description.json', 'CHANGES']:
        docs.append(fetch(f'https://raw.githubusercontent.com/OpenNeuroDatasets/ds003029/{UPSTREAM_REV}/{name}',
                          out / 'provenance' / ('upstream-1.0.5-' + name)))
    folder = dataset / 'sub-pt1/ses-presurgery/ieeg'
    header = folder / (STEM + '_ieeg.vhdr')
    config = ini(header)
    data = folder / config['Common Infos']['DataFile']
    marker = folder / config['Common Infos']['MarkerFile']
    n = int(config['Common Infos']['NumberOfChannels'])
    fs = 1e6 / float(config['Common Infos']['SamplingInterval'])
    assert n == 98 and fs == 1000
    assert config['Common Infos']['DataOrientation'] == 'MULTIPLEXED'
    assert config['Binary Infos']['BinaryFormat'] == 'IEEE_FLOAT_32'
    channel_fields = [config['Channel Infos'][f'Ch{i + 1}'].split(',') for i in range(n)]
    names = [fields[0].replace(r'\1', ',') for fields in channel_fields]
    assert all(fields[2:] == ['1.000', 'nV'] for fields in channel_fields)
    channels_path = folder / (STEM + '_channels.tsv')
    channels = list(csv.DictReader(channels_path.open(), delimiter='\t'))
    assert [c['name'] for c in channels] == names
    assert {c['type'] for c in channels} == {'ECOG', 'MISC'}
    indices = [i for i, c in enumerate(channels) if c['type'] == 'ECOG']
    assert len(indices) == 89
    # The only role evidence is channels.tsv; neither channel spelling nor bad
    # status selects/excludes channels. MISC EKG1/2 are not changed to ECG.
    source_bads = [c['name'] for c in channels if c['status'] == 'bad']
    stored = np.memmap(data, mode='r', dtype='<f4').reshape(-1, n)
    samples = len(stored)
    assert samples == 269080
    source_hashes = {str(p.relative_to(dataset)): digest(p) for p in dataset.rglob('*') if p.is_file()}

    events_path = folder / (STEM + '_events.tsv')
    events = list(csv.DictReader(events_path.open(), delimiter='\t'))
    assert len(events) == 7
    assert all(round(float(e['onset']) * fs) == int(e['sample']) for e in events)
    derived_events = out / 'derived' / 'pt1-clinical-point-events.tsv'
    derived_events.parent.mkdir(exist_ok=True)
    with derived_events.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, delimiter='\t')
        writer.writerow(['onset_s', 'duration_s', 'label', 'label_type'])
        for event in events:
            writer.writerow([event['onset'], event['duration'], event['trial_type'], 'clinical_source_point'])

    upload = out / 'upload-samples'
    upload.mkdir(exist_ok=True)
    fif = upload / 'MNE_ECoG_pt1_raw.fif'
    conversion = {'schema_version': 'ecog-fif-lineage/1.0', 'source_observation_id': 'mne-epilepsy-ecog-1-pt1',
                  'source_files': source_hashes, 'archive_sha256': SHA256,
                  'source_format': 'BrainVision IEEE_FLOAT_32 little-endian, multiplexed',
                  'source_scale': 'header resolution 1.000 nV; float32 -> float64 multiplied by 1e-9 V',
                  'role_source': channels_path.name, 'source_bad_channels_preserved': source_bads,
                  'source_bad_channels_used_for_selection_or_detection': False,
                  'processing_applied': [], 'all_channels_preserved': True, 'all_samples_preserved': True,
                  'filter_history_verified': False, 'reference_scheme': 'unknown',
                  'sample_count': samples, 'channel_count': n, 'sampling_rate_hz': fs,
                  'structural_new_segment_marker': 'Preserved in original VMRK; not an experimental event in FIF.',
                  'bids_semantic_events': 'Seven original zero-duration points remain in separate exact-time TSV; no seizure interval inferred.',
                  'software': {'mne': mne.__version__, 'numpy': np.__version__}}
    native_markers = []
    for key, value in ini(marker)['Marker Infos'].items():
        parts = value.split(',')
        if parts[0] != 'New Segment':
            native_markers.append({'onset': (int(parts[2]) - 1) / fs, 'duration': int(parts[3]) / fs,
                                   'description': (parts[0] + '/' + parts[1]).replace(r'\1', ',')})
    assert len(native_markers) == 29
    if not fif.exists():
        volts = stored.astype(np.float64).T * 1e-9
        info = mne.create_info(names, fs, ['ecog' if c['type'] == 'ECOG' else 'misc' for c in channels])
        # MISC is a role, not a unit: all original header channels explicitly nV.
        for channel in info['chs']:
            channel['unit'] = FIFF.FIFF_UNIT_V
        info['description'] = 'Engineering upload copy of MNE epilepsy_ecog-1; CC0; no filtering, re-reference, resampling or channel exclusion. See conversion-lineage.json.'
        raw = mne.io.RawArray(volts, info, verbose='ERROR')
        raw.info['bads'] = source_bads
        raw.set_annotations(mne.Annotations([e['onset'] for e in native_markers],
                                           [e['duration'] for e in native_markers],
                                           [e['description'] for e in native_markers]))
        raw.save(fif, fmt='double', overwrite=False, verbose='ERROR')
        raw.close()
        del raw, volts
    conversion.update(output=str(fif), output_sha256=digest(fif), output_bytes=fif.stat().st_size,
                      retained_native_marker_count=len(native_markers))
    save(out / 'conversion-lineage.json', conversion)

    package = upload / 'MNE_ECoG_pt1_BrainVision.zip'
    if not package.exists():
        with zipfile.ZipFile(package, 'x', compression=zipfile.ZIP_DEFLATED) as zipped:
            for path in [header, marker, data]:
                zipped.write(path, path.name)
    with zipfile.ZipFile(package) as zipped:
        assert set(zipped.namelist()) == {p.name for p in [header, marker, data]}
        assert all(hashlib.sha256(zipped.read(p.name)).hexdigest() == digest(p) for p in [header, marker, data])

    annotation = {'format': 'clinical_events_tsv', 'path': str(derived_events), 'source_path': str(events_path),
                  'expected_sha256': digest(derived_events), 'source_expected_sha256': digest(events_path),
                  'label_scope': 'clinical_events_not_quality'}
    records = []
    validations = []
    for kind, path in [('brainvision', header), ('fif', fif)]:
        record_id = 'mne-ecog-pt1-' + kind
        reader = open_reader(path, record_id)
        try:
            desc = reader.describe()
            metadata = reader.metadata()
            stream = desc['streams'][0]
            segment = stream['segments'][0]
            assert stream['sampling_frequency_hz'] == fs and stream['sample_count'] == samples
            assert [c['raw_name'] for c in stream['channels']] == names
            assert [c['source_index'] for c in stream['channels']] == list(range(n))
            assert all(c['unit'] == 'V' for c in stream['channels'])
            checks = []
            # Compare every original numeric sample in bounded chunks. This
            # reference decodes binary bytes independently of MNE data readers.
            for first in range(0, samples, 30000):
                last = min(first + 30000, samples)
                reference = stored[first:last].astype(np.float64).T * 1e-9
                actual = reader.read_window(stream['stream_id'], segment['segment_id'],
                                            [c['channel_id'] for c in stream['channels']], first, last, 'physical')
                error = np.abs(actual - reference)
                checks.append({'start_sample': first, 'stop_sample': last, 'channel_count': n,
                               'bitwise_equal': bool(np.array_equal(actual, reference)),
                               'max_absolute_error_volts': float(error.max()),
                               'mismatch_count': int(np.count_nonzero(actual != reference))})
            reader.assert_unchanged(hashes=True)
            assert all(check['bitwise_equal'] for check in checks)
            validation = {'format': kind, 'source_path': str(path), 'source_sha256': digest(path), 'status': 'passed',
                          'reference': 'Independent NumPy memmap <f4, multiplexed bytes; header nV scale; no MNE data getter used for reference',
                          'shape': [n, samples], 'duration_seconds': samples / fs,
                          'last_sample_time_seconds': (samples - 1) / fs, 'channels_match': True,
                          'source_indices_match': True, 'sampling_rate_matches': True, 'all_units_volts': True,
                          'reader_channel_types': [c['channel_type'] for c in stream['channels']],
                          'checks': checks, 'default_original_range_seconds': [60, 180],
                          'default_source_sample_range': [60000, 180000], 'scientific_accuracy_validated': False}
            validations.append(validation)
            records.append({'id': record_id, 'label': 'ECoG · MNE pt1 临床记录 · ' + kind.upper(),
                            'dataset_id': 'mne-epilepsy-ecog-1', 'source_observation_id': 'mne-epilepsy-ecog-1-pt1',
                            'profile_id': 'ecog_basic', 'source_path': str(path), 'expected_sha256': digest(path),
                            'expected_source_files': desc['source_files'], 'metadata': metadata,
                            'modality': 'ecog', 'modality_source': 'Original BIDS channels.tsv: ECOG (89), MISC (9)',
                            'reference_scheme': 'unknown', 'reference_evidence': 'Original iEEGReference=n/a; blank per-channel header references.',
                            'preprocessing': {'verified': False, 'note': 'SoftwareFilters=n/a; sidecar low/high cutoff 0/500 does not establish complete acquisition or processing history. No filters applied by this preparation.'},
                            'annotation': annotation, 'verified_electrode_coordinates': False, 'verified_epochs': False,
                            'default_config': {'selection': {'eeg_indices': indices, 'reference_indices': {}, 'start_seconds': 60, 'duration_seconds': 120},
                                               'method_config': {'comparison_groups': None},
                                               'context_tags': {'disease': 'epilepsy', 'age_group': 'unknown', 'task': 'other'}},
                            'context_evidence': {'disease': 'MNE official tutorial identifies epilepsy recording during a seizure; not a quality label.',
                                                 'task': 'Original BIDS TaskName=ictal; clinical monitoring, not an experimental scalp EEG task.'},
                            'provenance': {'name': 'MNE epilepsy_ecog sample / OpenNeuro ds003029', 'version': 'MNE epilepsy_ecog-1 (pinned archive; not asserted identical to latest OpenNeuro snapshot)',
                                           'license': 'CC0', 'url': 'https://mne.tools/stable/auto_tutorials/clinical/30_ecog.html', 'download_url': URL},
                            'data_usage': {'typical_use': '真实临床ECoG样例，默认原始60–180秒；仅基础完整性、频谱描述与事件时间核对。',
                                           'annotations': '7个BIDS临床点事件；FIF另保留原VMRK29条原始描述事件。来源bad保留，不排除源ECoG道。',
                                           'annotation_limits': '临床事件和来源bad不构成本平台伪迹金标准；BV/FIF为同一记录，不能计作两个独立样本。'},
                            'scientific_limits': {'quality_ground_truth': False, 'raw_modified': False,
                                                  'physical_amplitude': 'Header-based nV-to-V calibration validated numerically. Source acquisition units are not independently verified; BIDS units=n/a. Some selected traces reach about 0.013 V; MISC $G11/$G12 about -6 V. No corrective rescaling inferred.'}})
        finally:
            reader.close()
    check_fif = mne.io.read_raw_fif(fif, preload=False, verbose='ERROR')
    try:
        assert check_fif.info['bads'] == source_bads
        assert check_fif.get_channel_types() == ['ecog' if c['type'] == 'ECOG' else 'misc' for c in channels]
        assert len(check_fif.annotations) == len(native_markers)
        marker_error = max(abs(float(a) - e['onset']) for a, e in zip(check_fif.annotations.onset, native_markers))
        assert marker_error <= 1 / fs
        assert list(check_fif.annotations.description) == [e['description'] for e in native_markers]
    finally:
        check_fif.close()
    assert source_hashes == {str(p.relative_to(dataset)): digest(p) for p in dataset.rglob('*') if p.is_file()}
    save(out / 'independent-reader.json', {'status': 'passed', 'all_source_files_unchanged': True,
                                         'all_arrays_bitwise_equal': True, 'cases': validations,
                                         'source_observation_count': 1, 'representation_count': 2,
                                         'annotation_timing_max_error_seconds': marker_error,
                                         'annotation_timing_limit': 'FIF annotation timestamps may round at sub-sample scale; original VMRK and BIDS TSV are retained.',
                                         'scientific_detection_accuracy_validated': False,
                                         'environment': {'mne': mne.__version__, 'numpy': np.__version__, 'script_sha256': digest(__file__)}})
    save(out / 'additions.json', {'inputs': records, 'profiles': [{'id': 'ecog_basic', 'name': 'ECoG 基础检查', 'description': '真实ECoG；不套用头皮阈值，不据病理活动扣分。'}]})
    save(out / 'download_manifest.json', {'source': download, 'mne_md5': MD5, 'data_license': 'CC0',
                                        'data_license_evidence': 'Pinned archive dataset_description.json',
                                        'source_files': source_hashes, 'background_documents': docs,
                                        'background_document_version': 'OpenNeuro ds003029 1.0.5; background only, not a claim that MNE subset bytes match that snapshot',
                                        'upload_samples': [{'path': str(p), 'bytes': p.stat().st_size, 'sha256': digest(p)} for p in [package, fif]]})
    (upload / 'README.txt').write_text(
        'ECoG 上传样例（同一公开记录的两种表示，不是两个独立样本）\n\n'
        '先上传 MNE_ECoG_pt1_raw.fif：完整269.080秒、98道、1000Hz；89道原生ECoG，9道MISC。\n'
        'FIF是工程副本，源BrainVision数值按文件头nV转换为V，以double完整保存；无滤波、重参考、重采样、裁切或删道。\n'
        'MNE_ECoG_pt1_BrainVision.zip是未经修改的原始三件套，原头不编码ECoG类型，需明确确认模态和按BIDS侧车选道。\n'
        '登记默认原始60–180秒；手动新上传默认范围依工作台建议，快速预检不代表整记录完成。\n'
        '只做ECoG基础完整性/频谱描述/事件时间核对，不沿用头皮EEG阈值；总分未校准。\n'
        '7个BIDS临床点事件已另派生TSV；不从onset/offset自动构造发作区间，不是伪迹真值。\n'
        'FIF保留原29条VMRK描述事件及来源bad标记；这些标记不参与自动阈值或清洗。\n'
        '参考、完整滤波史未知；文件头nV标定已逐样本核对，但采集端绝对单位未经另行独立确认（侧车units=n/a）。\n'
        '来源许可CC0：MNE epilepsy_ecog-1 / OpenNeuro ds003029；应引用来源研究。\n'
        '官方说明：https://mne.tools/stable/auto_tutorials/clinical/30_ecog.html\n'
        '数据来源：https://openneuro.org/datasets/ds003029\n'
        '下载、转换与数值核验证据见上级download_manifest.json、conversion-lineage.json、independent-reader.json。\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'output': str(out), 'observations': 1, 'representations': 2,
                      'samples_per_channel': samples, 'channels': n, 'ecog_channels': len(indices),
                      'source_download_bytes': SIZE, 'fif_bytes': fif.stat().st_size, 'zip_bytes': package.stat().st_size,
                      'marker_max_error_seconds': marker_error}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
