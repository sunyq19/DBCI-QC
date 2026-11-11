"""Generate portable demo configuration; never read a developer's local settings."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'apps/workbench'))
from deployment import deployment


def settings_from_env(env, catalog=None):
    value = {'port': 18769, 'python': sys.executable, 'data_dir': '/data/runtime',
             'inputs': [], 'profiles': [], 'public_records': {}, 'public_packages': {},
             'data_policy': 'public-only/1', 'admission_policy': 'cloud-intake/1.3',
             'deployment': {'mode': 'shared_demo',
                            'public_origin': env.get('PUBLIC_ORIGIN', 'http://localhost:8769'),
                            'reserve_gib': float(env.get('RESERVE_GIB', '10'))}}
    if catalog is not None:
        allowed = {'inputs', 'profiles', 'packages', 'public_records', 'public_packages', 'example_review_sources'}
        if not isinstance(catalog, dict) or set(catalog) - allowed:
            raise ValueError('public-catalog.json may only register public inputs, packages and their sources')
        value.update(catalog)
    deployment(value)
    return value


def main():
    catalog = Path('/data/public-catalog.json')
    settings = settings_from_env(os.environ, json.loads(catalog.read_text()) if catalog.exists() else None)
    target = Path('/data/workbench.json')
    target.write_text(json.dumps(settings, indent=2) + '\n')
    target.chmod(0o600)
    os.execv(sys.executable, [sys.executable, str(ROOT / 'apps/workbench/server.py'),
                             '--config', str(target), '--host', '0.0.0.0'])


if __name__ == '__main__':
    main()
