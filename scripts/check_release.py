"""One local release regression entry point; use the configured scientific Python."""
from pathlib import Path
import importlib.util
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def main():
    missing = [name for name in ('numpy', 'mne', 'brainelecqc', 'autoreject')
               if importlib.util.find_spec(name) is None]
    if missing or not shutil.which('node'):
        raise SystemExit('Use the configured scientific Python and Node; missing: ' + ', '.join(missing or ['node']))
    checks = [
        [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
        ['node', 'apps/workbench/web/check-ui-contract.mjs'],
        ['node', 'tests/check-i18n.mjs'],
        ['node', 'tests/check-standards-navigation.mjs'],
        ['node', 'tests/check-workbench-layout.mjs'],
        ['git', 'diff', '--check'],
    ]
    for command in checks:
        print('CHECK: ' + ' '.join(command), flush=True)
        subprocess.run(command, cwd=REPO, check=True)
    print('Automated regression passed. Real-file acceptance and browser walk-through are separate release gates.')


if __name__ == '__main__':
    main()
