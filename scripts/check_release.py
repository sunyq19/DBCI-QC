"""One local release regression entry point; use the configured scientific Python."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def main():
    missing = [name for name in ('numpy', 'mne', 'brainelecqc', 'autoreject', 'pynwb', 'h5py')
               if importlib.util.find_spec(name) is None]
    if missing or not shutil.which('node'):
        raise SystemExit('Use the configured scientific Python and Node; missing: ' + ', '.join(missing or ['node']))
    checks = [
        [sys.executable, "scripts/build_eeg_specification.py", "--check"],
        [sys.executable, '-m', 'pytest', 'tests', '-q', '-rs'],
        ['node', 'apps/workbench/web/check-ui-contract.mjs'],
        ['node', 'tests/check-i18n.mjs'],
        ['node', 'tests/check-standards-navigation.mjs'],
        ['node', 'tests/check-workbench-layout.mjs'],
        ['node', 'tests/check-dataset-ui.mjs'],
        ['node', 'tests/check-dataset-review.mjs'],
        ['node', 'tests/check-dataset-report.mjs'],
        ['node', 'tests/check-data-library.mjs'],
        ['node', 'tests/check-project-result.mjs'],
        ['node', 'tests/check-report-interactions.mjs'],
        ['node', 'tests/check-waveform-explorer.mjs'],
        ['node', 'tests/check-chart-refresh.mjs'],
        ['node', 'tests/check-ieeg-groups.mjs'],
        ['node', 'tests/check-ieeg-scoring.mjs'],
        ['git', 'diff', '--check'],
    ]
    for command in checks:
        print('CHECK: ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=REPO, check=True)
    print('Automated regression passed. Real-file acceptance and browser walk-through are separate release gates.')


if __name__ == '__main__':
    main()
