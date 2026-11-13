"""Generate a shared-demo configuration and service files without installing them."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps/workbench'))
from deployment import deployment


def safe_path(value):
    path = Path(value).expanduser().absolute()
    # Paths are inserted into service configuration, never a shell command.
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', str(path)):
        raise ValueError('Deployment paths must use ASCII letters, digits, / . _ -')
    return path


def prepare(origin, data_dir, output, user, port, python, reserve=10, *,
            with_flow=False, node=None, flow_bundle=None, flow_port=18770):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]*', user):
        raise ValueError('Use an existing non-root Linux service user')
    if user == 'root' or not 1024 <= port <= 65535:
        raise ValueError('Use a non-root user and a port between 1024 and 65535')
    repo, output, data_dir, python = map(safe_path, (REPO, output, data_dir, python))
    if data_dir == repo or not python.is_file():
        raise ValueError('Install the Python environment first; choose a separate persistent data directory')
    settings = {'port': port, 'python': str(python), 'data_dir': str(data_dir),
                'inputs': [], 'profiles': [], 'admission_policy': 'cloud-intake/1.3',
                'data_policy': 'public-only/1', 'public_records': {}, 'public_packages': {},
                'deployment': {'mode': 'shared_demo', 'public_origin': origin, 'reserve_gib': reserve}}
    deployment(settings)
    public_port = urlsplit(origin).port or (443 if origin.startswith('https:') else 80)
    if port == public_port:
        raise ValueError('The QC backend port must differ from the public proxy port')
    if with_flow:
        settings['admin_auth_url'] = f'http://127.0.0.1:{flow_port}/api/access'
        if not node or not 1024 <= flow_port <= 65535 or flow_port in {port, public_port}:
            raise ValueError('Provide a Node 24 executable and a separate flow backend port')
        node = safe_path(node)
        flow_bundle = safe_path(flow_bundle or repo / 'apps/flow-editor/dist-self-host')
        if not node.is_file() or not (flow_bundle / 'server.mjs').is_file():
            raise ValueError('Build the collaboration service first; provide the installed Node 24 path')
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
UnsetEnvironment=PYTHONHOME PYTHONPATH
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
    flow_proxy = ''
    if with_flow:
        (output / 'dbci-flow.service').write_text(f'''[Unit]
Description=DBCI-QC module collaboration
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={flow_bundle}
ExecStart={node} {flow_bundle}/server.mjs
Environment=FLOW_BIND=127.0.0.1 FLOW_PORT={flow_port}
Environment=FLOW_PUBLIC_ORIGIN={origin}
Environment=FLOW_DATA_DIR={data_dir}/flow
Environment=FLOW_PASSWORD_FILE={output}/flow-password.verifier
Restart=on-failure
RestartSec=5
TimeoutStopSec=30
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths={data_dir}/flow

[Install]
WantedBy=multi-user.target
''')
        flow_proxy = f'''    @collaboration path /flow /flow/* /api/flow /api/access /api/attachments
    reverse_proxy @collaboration 127.0.0.1:{flow_port} {{
        header_up X-Real-IP {{remote_host}}
    }}
'''
    (output / 'Caddyfile').write_text(f'''{origin} {{
    request_body {{
        max_size 2147483648
    }}
{flow_proxy}    reverse_proxy 127.0.0.1:{port} {{
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
    parser.add_argument('--with-flow', action='store_true', help='Include module collaboration at /flow/')
    parser.add_argument('--node', type=Path, help='Absolute path to the installed Node 24 executable')
    parser.add_argument('--flow-bundle', type=Path, help='Built dist-self-host directory')
    parser.add_argument('--flow-port', type=int, default=18770)
    args = parser.parse_args()
    prepare(args.origin, args.data_dir, args.output, args.user, args.port, args.python, args.reserve_gib,
            with_flow=args.with_flow, node=args.node, flow_bundle=args.flow_bundle, flow_port=args.flow_port)


if __name__ == '__main__':
    main()
