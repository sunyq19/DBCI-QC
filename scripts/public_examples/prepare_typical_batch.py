"""Prepare the 2026-10-30 pinned batch, with source-grounded roles and upload copies.

Does not change workbench configuration or detector code. Registrations remain
local; the original recordings and all companion references remain byte-identical.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(path, delimiter='\t'):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def sleep_labels(source, metadata, evidence):
    import mne
    labels = source.with_name('SC4031EC-Hypnogram.edf')
    with source.open('rb') as stream:
        clock = stream.read(184)[168:184]
    with labels.open('rb') as stream:
        if stream.read(184)[168:184] != clock:
            raise ValueError('Sleep annotation origin differs from waveform origin')
    annotations = mne.read_annotations(labels)
    original = [{'onset_s': float(o), 'duration_s': float(d), 'source_label': str(t)}
                for o, d, t in zip(annotations.onset, annotations.duration, annotations.description)]
    rows = []
    for row in original:
        left = max(0., row['onset_s'])
        right = min(metadata['duration_seconds'], row['onset_s'] + row['duration_s'])
        if right > left:
            rows.append({'onset_s': left, 'duration_s': right-left, 'stage': row['source_label']})
    target = evidence / 'SC4031_sleep_stages.derived.tsv'
    with target.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['onset_s', 'duration_s', 'stage'], delimiter='\t')
        writer.writeheader(); writer.writerows(rows)
    save(evidence / 'sleep-annotation-derivation.json', {
        'source_sha256': sha(labels), 'derived_sha256': sha(target), 'original_rows': original,
        'method': 'Preserve R&K source stage names; intersect intervals with recorded clock; no signal-dependent selection',
        'quality_ground_truth': False, 'clock_origins_match': True})
    return {'path': str(target), 'source_path': str(labels), 'format': 'sleep_stages_tsv',
            'label_scope': 'sleep_state_not_quality', 'expected_sha256': sha(target),
            'source_expected_sha256': sha(labels)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root', required=True, type=Path)
    p.add_argument('--evidence-dir', required=True, type=Path)
    p.add_argument('--upload-dir', required=True, type=Path)
    p.add_argument('--manifest', type=Path, default=Path(__file__).with_name('typical_batch_20261030.json'))
    args = p.parse_args()
    root, evidence, uploads = [v.resolve() for v in (args.data_root, args.evidence_dir, args.upload_dir)]
    if any(v == REPO or REPO in v.parents for v in (root, evidence, uploads)):
        p.error('Keep local data and evidence outside the repository')
    evidence.mkdir(parents=True, exist_ok=True); uploads.mkdir(parents=True, exist_ok=True)
    spec = json.loads(args.manifest.read_text())
    for row in spec['files']:
        source = root / row['relative_path']
        if source.stat().st_size != row['bytes'] or sha(source) != row['sha256']:
            raise ValueError('Input differs from source manifest: ' + str(source))
    from ephys_qc.toolkit import inspect_recording, prepare_recording
    records, audits, failures = [], [], []
    for case in spec['records']:
        try:
            source = root / case['entry']; meta = inspect_recording(source)
            channels = meta['channels']; ds = case['dataset']; issues = []
            refs = {}; reference = 'unknown'; source_names_match = None
            if ds.startswith('sleep-edfx'):
                assert [c['name'] for c in channels[:3]] == ['EEG Fpz-Cz', 'EEG Pz-Oz', 'EOG horizontal']
                indices = [0, 1]; refs = {'eog': 2}; reference = 'bipolar'
                issues += ['Mixed-rate auxiliaries preserved; only 2 EEG channels and the 100 Hz EOG selected.',
                           'First 120 seconds are a fixed preview, not a whole-night evaluation.']
            else:
                sidecar = json.loads(source.with_suffix('.json').read_text(encoding='utf-8-sig'))
                side_channels = table(source.with_name(source.stem.replace('_eeg', '_channels') + '.tsv'))
                n_eeg = int(sidecar['EEGChannelCount'])
                assert len(side_channels) == n_eeg
                indices = list(range(n_eeg))
                source_names_match = [c['name'] for c in channels[:n_eeg]] == [c['name'] for c in side_channels]
                if ds.startswith('ds005284'):
                    assert len(channels) == 65 and channels[-1]['name'] == 'Status'
                    assert all(c['unit'] == 'uV' for c in channels[:64])
                    issues += ['Header uses A1..B32; sidecar uses scalp names. Electrode mapping remains unverified.',
                               'Boolean Status channel excluded from voltage QC. External event TSV retained, not automatically imported.',
                               'CMS/DRL declared; no assumed common-reference comparison group.']
                else:
                    assert source_names_match, 'Channel names differ from source sidecar'
                if ds.startswith('ds004584'):
                    assert sidecar['EEGReference'] == 'Pz'; reference = 'common_reference'
                    issues += ['README says two minutes; file is 281.66 seconds. File sample clock governs processing.',
                               'Same EEG participant ID PD1001 as the BrainVision development package; not independent validation.']
                elif ds.startswith('ds004504'):
                    issues += ['README reference Cz conflicts with sidecar A1 A2; retain unknown reference.',
                               'README and sidecar filtering history conflict; not independently verified.']
                elif ds.startswith('ds007020'):
                    issues += ['Reference and mains frequency missing from sidecar.',
                               'Mortality label is not a quality label; no disease assigned from filename.']
                elif ds.startswith('ds006386'):
                    issues += ['Source channel table says V; EDF calibration says uV. Use EDF calibration, retain discrepancy.',
                               'Manual labels use bipolar derivations/ALL; no single-channel accuracy claim before alignment.']
                delta = meta['duration_seconds'] - float(sidecar['RecordingDuration'])
                if abs(delta) > 1e-7:
                    issues.append(f'File duration minus sidecar duration = {delta:.9g} seconds; source values retained.')
            config = {'selection': {'eeg_indices': indices, 'reference_indices': refs,
                                    'start_seconds': case['window_start_seconds'], 'duration_seconds': case['window_duration_seconds']},
                      'method_config': {'comparison_groups': None},
                      'context_tags': {'disease': case['disease'], 'task': case['task'], 'age_group': 'unknown'}}
            record = prepare_recording(source, record_id=case['id'], modality=case['modality'], qc_config=config,
                label=case['label'], reference_scheme=reference, provenance=spec['datasets'][ds])
            record.update(dataset_id=ds, subject_id=case['subject_id'], evaluation_split=case['split'],
                modality_source='Explicit dataset EEG protocol; not inferred from extension.',
                verified_electrode_coordinates=False, verified_epochs=False,
                preprocessing={'verified': False, 'note': 'Original files preserved; no additional cleaning, rereferencing or resampling.'},
                data_usage={'typical_use': case['label'], 'annotation_limits': ' '.join(issues)},
                source_metadata_issues=issues, source_channel_names_match=source_names_match)
            if ds.startswith('sleep-edfx'):
                record['annotation'] = sleep_labels(source, meta, evidence)
            if ds.startswith('ds006386'):
                labels = root / ds / 'derivatives/Manual_Annotations/sub2_run01.csv'
                rows = table(labels, ',')
                record['quality_reference'] = {'path': str(labels), 'expected_sha256': sha(labels),
                    'source_rows': len(rows), 'status': 'montage_alignment_pending',
                    'used_for_signal_detection': False, 'passed_to_M07': False}
            # Flat packages contain only the original main/companion files. Do not
            # rename references inside BrainVision/SET or imply sidecar auto-import.
            folder = uploads / ('01_开发样例' if case['split'] == 'development' else '02_冻结验证样例')
            folder.mkdir(exist_ok=True)
            members = record['expected_source_files']
            if len(members) == 1:
                target = folder / source.name
                if not target.exists(): shutil.copy2(source, target)
                assert sha(target) == record['expected_sha256']
            else:
                target = folder / (case['id'] + '.zip')
                if not target.exists():
                    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                        for entry in members: archive.write(entry['path'], entry['name'])
                with zipfile.ZipFile(target) as archive:
                    assert set(archive.namelist()) == {e['name'] for e in members}
                    for entry in members:
                        assert hashlib.sha256(archive.read(entry['name'])).hexdigest() == entry['sha256']
            audits.append({**case, 'upload_path': str(target), 'upload_sha256': sha(target),
                           'file_channels': len(channels), 'selected_eeg_channels': len(indices),
                           'duration_seconds': meta['duration_seconds'], 'issues': issues})
            records.append(record)
            print('PREPARED', case['id'], meta['duration_seconds'], 'seconds', flush=True)
        except Exception as error:
            failures.append({'id': case['id'], 'error': f'{type(error).__name__}: {error}'})
            print('FAILED', case['id'], str(error), flush=True)
    save(evidence / 'records-all.json', {'records': records})
    for split in ('development', 'frozen_validation'):
        save(evidence / ('records-' + split + '.json'), {'records': [r for r in records if r['evaluation_split'] == split]})
    save(evidence / 'preparation-audit.json', {'records': audits, 'failures': failures})
    save(uploads / '来源与文件校验.json', {'baseline': spec['baseline_commit'], 'datasets': spec['datasets'], 'records': audits})
    if failures: raise SystemExit(1)


if __name__ == '__main__':
    main()
