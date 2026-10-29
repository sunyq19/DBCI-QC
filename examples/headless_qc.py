"""Generate a synthetic EDF and run M03 without a website or external dataset.

Run: python examples/headless_qc.py --output /path/to/new-demo
Requires the scientific dependencies from README. This is an engineering demo,
not a natural-artifact benchmark. The original signal is never cleaned.
"""
import argparse
import json
import math
from pathlib import Path
import struct

from ephys_qc.toolkit import prepare_recording, run_module


def write_synthetic_edf(path):
    def cell(value, width):
        text = str(value).encode('ascii')
        if len(text) > width:
            raise ValueError('EDF field exceeds width')
        return text.ljust(width, b' ')
    head = b''.join(cell(value, width) for value, width in [
        (0, 8), ('X X X X', 80), ('Synthetic engineering fixture', 80),
        ('01.01.01', 8), ('00.00.00', 8), (768, 8), ('', 44), (10, 8), (1, 8), (2, 4)])
    fields = [(16, ['Cz', 'Pz']), (80, ['', '']), (8, ['uV', 'uV']),
              (8, [-32768, -32768]), (8, [32767, 32767]),
              (8, [-32768, -32768]), (8, [32767, 32767]),
              (80, ['', '']), (8, [200, 200]), (32, ['', ''])]
    with Path(path).open('xb') as target:
        target.write(head + b''.join(cell(value, width) for width, values in fields for value in values))
        for second in range(10):
            for channel in range(2):
                values = [0 if channel == 1 and second in (3, 4) else
                          round(40 * math.sin(2 * math.pi * (10 + channel) * (second + i / 200)))
                          for i in range(200)]
                target.write(struct.pack('<200h', *values))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = root / 'synthetic.edf'
    write_synthetic_edf(source)
    config = {'selection': {'eeg_indices': [0, 1], 'reference_indices': {},
                            'start_seconds': 0, 'duration_seconds': 10},
              'method_config': {'comparison_groups': None}}
    record = prepare_recording(source, record_id='synthetic-001', modality='scalp_eeg', qc_config=config,
                               provenance={'name': 'Generated engineering fixture', 'quality_ground_truth': False})
    (root / 'record.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
    (root / 'config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
    result = run_module('M03', record, root / 'qc')
    print(json.dumps({'status': result['status'], 'selected_modules': result['selected_modules'],
                      'report': str(root / 'qc' / result['report_path']), 'score': result['score']}, ensure_ascii=False, indent=2))
    if result['status'] == 'failed' or any(row['status'] == 'failed' for row in result['modules']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
