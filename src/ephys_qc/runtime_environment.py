"""Fail early when a workbench or worker environment cannot run the baseline.

This module uses only the standard library until the dependency probe runs, so
it can explain a broken installation even when the scientific stack is absent.
Optional research runtimes are deliberately not baseline requirements.
"""
import argparse
import importlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
MODULES = {
    'brainelecqc': 'brainelecqc', 'mne': 'mne', 'autoreject': 'autoreject',
    'h5io': 'h5io', 'pymatreader': 'pymatreader', 'pynwb': 'pynwb',
    'hdmf': 'hdmf', 'h5py': 'h5py', 'reportlab': 'reportlab', 'ijson': 'ijson',
    'spikeinterface': 'spikeinterface', 'probeinterface': 'probeinterface',
    'numpy': 'numpy', 'scipy': 'scipy.signal', 'matplotlib': 'matplotlib',
}


def isolated_environment():
    env = dict(os.environ)
    for key in ('PYTHONHOME', 'PYTHONPATH'):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE='1', MPLBACKEND='Agg', OMP_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    return env


def probe():
    errors, versions = [], {}
    if sys.version_info[:2] != (3, 11):
        errors.append('The workbench requires Python 3.11.')
    pins = {}
    requirements = ROOT / 'requirements/workbench.txt'
    if requirements.is_file():
        for line in requirements.read_text().splitlines():
            if '==' in line and not line.lstrip().startswith('#'):
                name, version = line.strip().split('==', 1)
                pins[name] = version
    for package, module in MODULES.items():
        try:
            importlib.import_module(module)
            versions[package] = importlib.metadata.version(package)
            if package in pins and versions[package] != pins[package]:
                errors.append(f'{package}: installed {versions[package]}, required {pins[package]}')
        except Exception as exc:
            errors.append(f'{package}: {type(exc).__name__}: {exc}')
    return {'python': sys.executable, 'prefix': sys.prefix, 'versions': versions,
            'errors': errors, 'ok': not errors}


def validate_runtime(worker_python=None):
    current = probe()
    results = [current]
    # Do not resolve symlinks here: a venv and its base interpreter may point
    # to the same binary while loading completely different site-packages.
    if worker_python and Path(worker_python).absolute() != Path(sys.executable).absolute():
        try:
            process = subprocess.run(
                [str(Path(worker_python).absolute()), str(Path(__file__).absolute()), '--json'],
                capture_output=True, text=True, timeout=120, env=isolated_environment())
            worker = json.loads(process.stdout)
            if process.returncode and worker.get('ok'):
                raise RuntimeError('Worker probe exited unsuccessfully')
            results.append(worker)
        except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
            results.append({'python': str(worker_python), 'ok': False,
                            'errors': [f'Worker environment could not be checked: {exc}']})
    failures = [r for r in results if not r['ok']]
    if failures:
        details = '\n'.join(r['python'] + '\n  ' + '\n  '.join(r['errors']) for r in failures)
        raise RuntimeError('质控环境检查失败 / Runtime check failed:\n' + details +
                           '\n请在仓库目录运行：python3.11 scripts/setup_local.py\n'
                           '然后使用：python3 scripts/run_local.py\n'
                           'Docker 部署请重新运行 sh deploy.sh；自定义 worker 也须安装 requirements/workbench.txt。')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Probe this interpreter only')
    parser.add_argument('--config', type=Path, help='Also validate the configured worker Python')
    args = parser.parse_args()
    if args.json:
        result = probe()
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['ok'] else 1
    worker = json.loads(args.config.read_text())['python'] if args.config else None
    try:
        for result in validate_runtime(worker):
            print('环境检查通过 / Runtime OK: ' + result['python'])
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
