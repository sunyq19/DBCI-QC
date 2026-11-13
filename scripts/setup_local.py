"""Install the local workbench into .venv and create a private configuration."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def port_number(value):
    number = int(value)
    if not 1024 <= number <= 65535:
        raise argparse.ArgumentTypeError('Port must be between 1024 and 65535.')
    return number


def write_config(repo, python, data_dir, port):
    """Create once; rerunning setup must not replace existing inputs or paths."""
    target = repo / '.local' / 'workbench.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    settings = {'port': port, 'python': str(python.absolute()),
                'data_dir': str(data_dir.resolve()), 'inputs': [], 'profiles': [],
                'data_policy': 'public-only/1', 'public_records': {}, 'public_packages': {}}
    # Keep the venv entry point: resolving its symlink would select the base Python.
    try:
        with target.open('x', encoding='utf-8') as stream:
            json.dump(settings, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    except FileExistsError:
        return target, False
    return target, True


def setup(repo, data_dir, port):
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError('Use Python 3.11: python3.11 scripts/setup_local.py')
    if not shutil.which('git'):
        raise RuntimeError('Git is required to install BrainElecQC. Install Git and retry.')
    venv = repo / '.venv'
    python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if venv.exists() and not (venv / 'pyvenv.cfg').is_file():
        raise RuntimeError('.venv exists but is not a virtual environment; it was not changed.')
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    env['PYTHONNOUSERSITE'] = '1'
    if not python.is_file():
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True, env=env)
    subprocess.run([str(python), '-c',
                    'import sys; assert sys.version_info[:2] == (3, 11), "The existing .venv must use Python 3.11"; '
                    'assert sys.prefix != sys.base_prefix, "An isolated venv is required"'], check=True, env=env)
    subprocess.run([str(python), '-m', 'pip', 'install', '-e', str(repo) + '[reports]',
                    '-r', str(repo / 'requirements/workbench.txt')], check=True, env=env)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True, env=env)
    subprocess.run([str(python), str(repo / 'src/ephys_qc/runtime_environment.py')],
                   check=True, env=env)
    target, created = write_config(repo, python, data_dir, port)
    print('\nSetup complete. ' + ('Created: ' if created else 'Preserved existing config: ') + str(target))
    settings = json.loads(target.read_text(encoding='utf-8'))
    if Path(settings['python']).absolute() != python.absolute():
        print('Existing config uses another Python. Set its python field to ' + str(python) +
              ' to use the environment installed above; data paths and history were preserved.')
    print('Start from the repository directory:')
    print('  python scripts/run_local.py' if os.name == 'nt' else '  python3 scripts/run_local.py')
    print(f'Open: http://127.0.0.1:{settings.get("port", 8769)}/')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=port_number, default=8769, help='Port for a new configuration (default: 8769)')
    parser.add_argument('--data-dir', type=Path, default=REPO / '.local/runtime',
                        help='Directory for uploaded copies and results; existing configuration is preserved')
    args = parser.parse_args()
    try:
        setup(REPO, args.data_dir.expanduser(), args.port)
    except (RuntimeError, subprocess.CalledProcessError, OSError, ValueError, KeyError) as exc:
        raise SystemExit(f'Setup failed: {exc}\nResolve the error above and rerun the same command.') from exc


if __name__ == '__main__':
    main()
