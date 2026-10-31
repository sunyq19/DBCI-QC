"""Read-only, case-specific field-mapping exercise, NOT a general intake adapter.

Requires existing public files and h5py. Writes only the requested JSON output;
no downloads, source changes, waveform loading or scientific QC are performed.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ephys_qc.readers.edf_header import inspect_header


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def declared(value, kind, reference, locator, **extra):
    return {'value': value, 'status': 'known', 'confirmation': 'unreviewed',
            'source': [{'kind': kind, 'reference': reference, 'locator': locator}], **extra}


def unknown(reference, locator, reason='source_not_provided'):
    return {'value': None, 'status': 'unknown', 'confirmation': 'unreviewed',
            'reason': reason, 'source': [{'kind': 'provider_document', 'reference': reference, 'locator': locator}]}


def participant(path, identifier):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = [row for row in csv.DictReader(f, delimiter='\t') if row['participant_id'] == identifier]
    if len(rows) != 1:
        raise ValueError('Expected one source participant: ' + identifier)
    return rows[0]


def age(value, unit, at, source_text, reference='unknown'):
    return {'lower': value, 'upper': value, 'unit': unit, 'reference': reference,
            'at': at, 'source_text': source_text}


def build(data_root):
    import h5py
    manifests = []

    def source(path):
        path = path.resolve()
        relative = str(path.relative_to(data_root))
        manifests.append({'path': relative, 'sha256': digest(path), 'size_bytes': path.stat().st_size})
        return relative

    human = data_root / '典型扩充_20261030/ds007020-1.0.0'
    hp = source(human / 'participants.tsv')
    hr = source(human / 'README.md')
    hrow = participant(human / 'participants.tsv', 'sub-PD1001')
    if 'age' in hrow:
        raise ValueError('Human source changed; review the missing-age mapping')
    hfields = {
        'subject.id': declared(hrow['participant_id'], 'sidecar', hp, 'participant_id=sub-PD1001'),
        'subject.species': declared({'source_label': 'Human clinical participants', 'scientific_name': 'Homo sapiens'}, 'provider_document', hr, 'EEG Acquisition Details; Ethics & Privacy', mapping='human-clinical-cohort/1; reviewed source interpretation, not BIDS fallback'),
        'subject.age': unknown(hr, 'Participant Information'),
        'subject.background': unknown(hp, 'No individual diagnosis column; participant ID is not diagnosis evidence'),
        'recording.recording_site': declared('scalp', 'provider_document', hr, '10–20 montage; dataset-level declaration'),
        'recording.signal_kind': declared('continuous_voltage', 'provider_document', hr, 'Resting-state EEG recordings'),
        'experiment.task': declared({'id': 'rest', 'label': 'eyes-open resting state'}, 'provider_document', hr, 'EEG Acquisition Details'),
    }
    monkey = data_root / '非EEG补充_20261031/ds006890'
    mp = source(monkey / 'participants.tsv')
    mj = source(monkey / 'participants.json')
    mrow = participant(monkey / 'participants.tsv', 'sub-monkeyb')
    age_description = json.loads((monkey/'participants.json').read_text())['age']
    if 'years' not in age_description['LongName'] or 'start of experiment' not in age_description['Description']:
        raise ValueError('Monkey age semantics changed; review mapping')
    stem = monkey / 'sub-monkeyb/ses-day09/ieeg/sub-monkeyb_ses-day09_task-rest_run-01_ieeg'
    side = json.loads(stem.with_suffix('.json').read_text())
    ms = source(stem.with_suffix('.json'))
    edf = data_root / '非EEG补充_20261031/originals/ds006890' / stem.with_suffix('.edf').relative_to(monkey)
    me = source(edf)
    header = inspect_header(edf)
    side_duration = declared(side['RecordingDuration'], 'sidecar', ms, 'RecordingDuration')
    file_duration = declared(header['duration_seconds'], 'file_header', me, 'number_of_records * record_duration')
    duration = file_duration
    if side_duration['value'] != file_duration['value']:
        duration = {'value': None, 'status': 'conflict', 'confirmation': 'unreviewed',
                    'source': side_duration['source'] + file_duration['source'],
                    'alternatives': [side_duration, file_duration],
                    'reason': 'Different declared and stored duration; padding is possible but unverified'}
    mfields = {
        'subject.id': declared(mrow['participant_id'], 'sidecar', mp, 'participant_id=sub-monkeyb'),
        'subject.species': declared({'source_label': mrow['species'], 'scientific_name': mrow['species']}, 'sidecar', mp, 'sub-monkeyb/species'),
        'subject.age': declared(age(float(mrow['age']), 'year', 'experiment_start', mrow['age']), 'sidecar', mp, 'sub-monkeyb/age'),
        'subject.sex': declared(mrow['sex'], 'sidecar', mp, 'sub-monkeyb/sex'),
        'recording.recording_site': declared('cortical_surface', 'sidecar', ms, 'ECOGChannelCount=32; applies to ECoG group, not all file channels'),
        'recording.duration_seconds': duration,
        'acquisition.hardware': declared({'manufacturer': side['Manufacturer'], 'model': side['ManufacturersModelName']}, 'sidecar', ms, 'Manufacturer; ManufacturersModelName'),
    }
    mfields['subject.age']['source'].append({'kind': 'sidecar', 'reference': mj, 'locator': 'age.LongName; age.Description'})
    nwb = data_root / 'NWB/originals/sub-Sumac_ses-Sumac06-LinearTrack_behavior+ecephys.nwb'
    ns = source(nwb)
    series_path = '/processing/ecephys/LFP/ElectricalSeries'
    with h5py.File(nwb, 'r') as f:
        subject = f['general/subject']
        raw_age = text(subject['age'][()])
        match = re.fullmatch(r'P(\d+(?:\.\d+)?)M', raw_age)
        if not match:
            raise ValueError('This source-specific example expects an ISO age in months')
        raw_reference = subject['age'].attrs.get('reference')
        reference = text(raw_reference) if raw_reference is not None else 'unknown'
        series = f[series_path]; samples, channels = series['data'].shape
        rate = float(series['starting_time'].attrs['rate'])
        device = f['general/devices/array']
        mouse_fields = {
            'subject.id': declared(text(subject['subject_id'][()]), 'file_header', ns, '/general/subject/subject_id'),
            'subject.species': declared({'source_label': text(subject['species'][()]), 'scientific_name': text(subject['species'][()])}, 'file_header', ns, '/general/subject/species'),
            'subject.age': declared(age(float(match[1]), 'month', 'source_unspecified', raw_age, reference), 'file_header', ns, '/general/subject/age', note='NWB 2.4.0 source has no explicit age reference or timing declaration; no exact-day conversion or newer-schema default applied'),
            'subject.sex': declared(text(subject['sex'][()]), 'file_header', ns, '/general/subject/sex'),
            'subject.strain': declared({'strain': text(subject['strain'][()]), 'genotype': None}, 'file_header', ns, '/general/subject/strain'),
            'subject.background': unknown(ns, 'No disease assignment established by this audit'),
            'recording.signal_kind': declared('continuous_voltage', 'file_header', ns, series_path),
            'recording.sampling_rate_hz': declared(rate, 'file_header', ns, series_path+'/starting_time@rate'),
            'recording.sample_count': declared(samples, 'file_header', ns, series_path+'/data.shape[0]'),
            'recording.duration_seconds': declared(samples/rate, 'derived', ns, series_path, transformation='sample_count / rate', rule_version='stored-duration/1'),
            'acquisition.hardware': declared({'manufacturer': text(device.attrs['manufacturer']), 'model': text(device.attrs['description'])}, 'file_header', ns, '/general/devices/array attributes'),
            'experiment.task': declared({'id': 'linear_track', 'label': text(f['session_description'][()])}, 'file_header', ns, '/session_description'),
        }
    cases = [
        {'id': 'human-eeg', 'source_url': 'https://openneuro.org/datasets/ds007020/versions/1.0.0', 'fields': hfields,
         'scope': 'Partial metadata mapping only; individual disease and age are not inferred from the participant ID'},
        {'id': 'monkey-ecog', 'source_url': 'https://openneuro.org/datasets/ds006890/versions/1.0.0', 'fields': mfields,
         'scope': 'ECoG group; retains experiment-start age and unresolved duration conflict',
         'observations': {'file_signal_count': header['raw_signal_count'], 'file_numeric_channel_count': len(header['channels']), 'file_annotation_signal_count': header['annotation_signal_count'], 'sidecar_total_channel_count': sum(v for k,v in side.items() if k.endswith('ChannelCount')), 'ecog_channel_count': side['ECOGChannelCount']}},
        {'id': 'mouse-lfp', 'source_url': 'https://dandiarchive.org/dandiset/000165/0.211118.1526', 'fields': mouse_fields,
         'scope': 'Readable Neuronexus LFP; NOT Neuropixels QC eligibility; no QC algorithms run in this audit',
         'observations': {'channel_count': channels, 'age_reference_explicit': raw_reference is not None}},
    ]
    return {'dictionary_version': 'metadata-fields/1', 'audit_version': 'source-mapping/1',
            'scope': 'Partial design mapping examples, not runtime request payloads or general-purpose importers',
            'sources': manifests, 'cases': cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = build(args.data_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(f"Mapped {len(result['cases'])} real-source cases; {len(result['sources'])} files fingerprinted; no QC jobs run")


if __name__ == '__main__':
    main()
