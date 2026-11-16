"""Stage the two Allen excerpts with verified geometry units; preserve originals.

No samples, timestamps, electrode values or thresholds are changed. The two
custom coordinate-column descriptions are completed from AllenSDK's definition:
https://allensdk.readthedocs.io/en/latest/_modules/allensdk/brain_observatory/ecephys/nwb_util.html
The resulting files have new hashes and require new reports.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import h5py
import numpy as np

from build_eight_dataset_release import make_manifest, REPO


def prepare(config, output):
    settings = json.loads(config.read_text())
    pid = 'example-mouse-neuropixels'
    package = next(p for p in settings['packages'] if p['id'] == pid)
    original = Path(package['root'])
    if original.name.endswith('_位置核验版'):
        raise ValueError('Use the original example package, not an already curated one')
    target = original.with_name(original.name + '_位置核验版')
    target.mkdir(parents=True, exist_ok=True)
    for source in original.glob('*.nwb'):
        receipt = json.loads(source.with_suffix('.source.json').read_text())
        digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        assert digest(source) == receipt['excerpt_sha256']
        dest = target / source.name
        shutil.copy2(source, dest)
        with h5py.File(dest, 'r+') as f:
            table = f['general/extracellular_ephys/electrodes']
            for key in ('probe_horizontal_position', 'probe_vertical_position'):
                table[key].attrs['description'] = 'Retained source '+key+' (microns; AllenSDK electrode table definition)'
        with h5py.File(source) as a, h5py.File(dest) as b:
            for key in ('acquisition/LFP/lfp/data', 'acquisition/LFP/lfp/timestamps',
                        'general/extracellular_ephys/electrodes/probe_horizontal_position',
                        'general/extracellular_ephys/electrodes/probe_vertical_position'):
                assert np.array_equal(a[key][:], b[key][:]), key
        receipt.update(previous_excerpt_sha256=receipt['excerpt_sha256'], excerpt_sha256=digest(dest),
                       size_bytes=dest.stat().st_size,
                       geometry_documentation='https://allensdk.readthedocs.io/en/latest/_modules/allensdk/brain_observatory/ecephys/nwb_util.html',
                       metadata_changes='Coordinate-column descriptions now explicitly state microns; all numerical values unchanged.')
        dest.with_suffix('.source.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    staged = copy.deepcopy(settings)
    staged.update(data_dir=str(output.parent/'runtime'), inputs=[], packages=[], demo_examples=[],
                  demo_comparisons=[], public_records={}, public_packages={}, temporary_workspace=True)
    staged['packages'] = [make_manifest(pid, target, settings['public_packages'][pid])]
    staged['public_packages'][pid] = settings['public_packages'][pid]
    staged['demo_examples'] = [e for e in settings['demo_examples'] if e.get('package_id') == pid]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(staged, ensure_ascii=False, indent=2))
    print(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=REPO/'.local/workbench.json')
    parser.add_argument('--output', type=Path, default=REPO/'.local/curated-examples-20261114/staged.json')
    args = parser.parse_args()
    prepare(args.config, args.output)
