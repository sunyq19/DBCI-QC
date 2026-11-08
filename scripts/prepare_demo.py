"""Generate a shared-demo configuration and service files without installing them."""
import argparse
import json
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from deployment import deployment


def safe_path(value):
    path = Path(value).expanduser().absolute()
    # Paths are inserted into service configuration, never a shell command.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)):
        raise ValueError('Deployment paths must use ASCII letters, digits, / . _ -')
    return path


def prepare(origin, data_dir, output, user, port, python, reserve=10):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
        raise ValueError('Use an existing non-root Linux service user')
    if user == 'root' or not 1024 <= port <= 65535:
        raise ValueError('Use a non-root user and a port between 1024 and 65535')
    repo, output, data_dir, python = map(safe_path, (REPO, output, data_dir, python))
    if data_dir == repo or not python.is_file():
        raise ValueError('Install the Python environment first; choose a separate persistent data directory')
    settings = {'port': port, 'python': str(python), 'data_dir': str(data_dir),
                'inputs': [], 'profiles': [], 'admission_policy': 'cloud-intake/1.3',
                'deployment': {'mode': 'shared_demo', 'public_origin': origin, 'reserve_gib': reserve}}
    deployment(settings)
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o700)
    config = output / 'workbench.json'
    config.write_text(json.dumps(settings, indent=2) + '\n')
    config.chmod(0o600)
    service = f'''[Unit]
Description=DBCI-QC shared demo
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={repo}
ExecStart={python} {repo}/apps/workbench/server.py --config {config}
Environment=PYTHONNOUSERSITE=1 MPLBACKEND=Agg OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONPATH=
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
KillMode=control-group
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={data_dir}
Environment=MPLCONFIGDIR={data_dir}/.matplotlib XDG_CACHE_HOME={data_dir}/.cache

[Install]
WantedBy=multi-user.target
'''
    (output / 'dbci-qc.service').write_text(service)
    (output / 'Caddyfile').write_text(f'''{origin} {{
    request_body {{
        max_size 2147483648
    }}
    reverse_proxy 127.0.0.1:{port} {{
        transport http {{
            response_header_timeout 1h
        }}
    }}
}}
''')
    print(f'Created {output}\nCreate {data_dir} owned by {user}; then follow docs/deployment/demo.md.')
    return settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True, help='Exact public origin, e.g. https://qc.example.org')
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=REPO / '.local/demo')
    parser.add_argument('--user', default='dbciqc')
    parser.add_argument('--port', type=int, default=8769)
    parser.add_argument('--python', type=Path, default=REPO / '.venv/bin/python')
    parser.add_argument('--reserve-gib', type=float, default=10)
    args = parser.parse_args()
    prepare(args.origin, args.data_dir, args.output, args.user, args.port, args.python, args.reserve_gib)


if __name__ == '__main__':
    main()
