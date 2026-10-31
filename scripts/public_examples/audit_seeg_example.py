#!/usr/bin/env python3
"""Read the pinned sEEG FIF buffers independently and compare all adapter samples.

This audit decodes the FIFF big-endian tag chain and float32 signal payloads
directly. MNE provides metadata only; its data getter is not the reference.
No clinical ground truth or original acquisition calibration is established.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

REPO = Path(__file__).resolve().parents[2]
SHA256 = '76b0cfdb5708cc349d1aaf662757f477eb7c26fe396468e6a16f13b84df43ba4'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def audit(path):
    import numpy as np
    from ephys_qc.readers import open_reader
    assert digest(path) == SHA256
    # This fixed-file audit is intentionally narrow: only uncompressed,
    # single-file, no-skip float32 buffers, 119 channels with unity calibration.
    # It must fail if a source representation changes.
    blocks = []
    with Path(path).open('rb') as source:
        seen = set()
        while True:
            position = source.tell()
            assert position not in seen, 'Cyclic FIFF tag chain'
            seen.add(position)
            header = source.read(16)
            if not header:
                break
            assert len(header) == 16
            kind, typ, size, next_position = struct.unpack('>iiii', header)
            assert size >= 0 and position + 16 + size <= Path(path).stat().st_size
            if kind == 301:
                raise AssertionError('Skipped FIFF data not supported in this fixed-file audit')
            if kind == 300:
                assert typ == 4 and size % (4 * 119) == 0
                block = np.frombuffer(source.read(size), dtype='>f4').reshape(-1, 119).T
                blocks.append(block.astype(np.float64))
            else:
                source.seek(size, 1)
            if next_position == -1:
                break
            if next_position > 0:
                source.seek(next_position)
            else:
                assert next_position == 0
    reference = np.concatenate(blocks, axis=1)
    assert reference.shape == (119, 59966)
    reader = open_reader(path, 'independent-seeg-audit')
    try:
        desc = reader.describe()
        stream = desc['streams'][0]
        segment = stream['segments'][0]
        assert segment['start_sample'] == 1310640
        assert segment['stop_sample'] == 1370606
        assert stream['sample_count'] == 59966
        assert all(c['channel_type'] == 'seeg' and c['channel_type_source'] == 'file_declared'
                   and c['unit'] == 'V' for c in stream['channels'])
        assert all(c['cal'] == 1.0 and c['range'] == 1.0 and int(c['unit']) == 107
                   for c in reader.raw.info['chs'])
        actual = reader.read_window(stream['stream_id'], segment['segment_id'],
                                    [c['channel_id'] for c in stream['channels']],
                                    segment['start_sample'], segment['stop_sample'], 'physical')
        assert np.array_equal(actual, reference)
        first_time = desc['clock']['first_time_seconds']
        assert len(desc['events']) == 32
        assert all(abs(e['onset_seconds'] - (float(t) - first_time)) < 1e-10
                   for e, t in zip(desc['events'], reader.raw.annotations.onset))
        assert all(0 <= e['onset_seconds'] < stream['sample_count'] / stream['sampling_frequency_hz']
                   for e in desc['events'])
        reader.assert_unchanged(hashes=True)
        return {'schema_version': 'seeg-readback/1', 'status': 'passed',
                'source_sha256': SHA256, 'source_unchanged': digest(path) == SHA256,
                'reference': 'Direct FIFF tag-chain and big-endian float32 payload decoding; unity declared channel calibration; no MNE data getter as reference',
                'shape': list(reference.shape), 'source_buffer_count': len(blocks),
                'compared_values': int(reference.size), 'all_samples_bitwise_equal': True,
                'maximum_absolute_error_volts': float(np.abs(actual - reference).max()),
                'first_sample': 1310640, 'stop_sample_exclusive': 1370606,
                'annotation_count': 32, 'annotation_clock_relative_to_file_verified': True,
                'modality_file_declared': 'seeg', 'scientific_detection_accuracy_validated': False,
                'original_acquisition_calibration_independently_verified': False,
                'script_sha256': digest(__file__)}
    finally:
        reader.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().is_relative_to(REPO):
        parser.error('Audit evidence must remain outside the repository')
    sys.path.insert(0, str(REPO / 'src'))
    result = audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'compared_values': result['compared_values']}))


if __name__ == '__main__':
    main()
