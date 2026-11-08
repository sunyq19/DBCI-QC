"""Verify an isolated local installation, cached examples and a synthetic EDF run.

Uses a temporary runtime and loopback port; never opens the user's configuration.
Run with the installed scientific Python. This is not browser visual acceptance.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix='dbci-smoke-') as directory:
        root = Path(directory)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        config = root / 'workbench.json'
        config.write_text(json.dumps({'port': port, 'python': sys.executable,
                                     'data_dir': str(root / 'runtime'),
                                     'inputs': [], 'profiles': []}), encoding='utf-8')
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'), PYTHONNOUSERSITE='1',
                   OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
        base = f'http://127.0.0.1:{port}'
        with (root / 'server.log').open('w+') as log:
            server = subprocess.Popen([sys.executable, str(ROOT / 'apps/workbench/server.py'),
                                       '--config', str(config)], cwd=ROOT, env=env,
                                      stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 45
                while True:
                    try:
                        with urlopen(base + '/api/v1/health', timeout=2) as response:
                            health = json.load(response)
                        break
                    except OSError:
                        if server.poll() is not None or time.monotonic() >= deadline:
                            log.seek(0)
                            raise RuntimeError('Isolated service did not start:\n' + log.read())
                        time.sleep(.2)
                manifest = json.loads((ROOT / 'apps/workbench/example-cache/manifest.json').read_text())
                assert len(manifest['examples']) == 4, 'Four cached modality examples are required'
                paths = ['/', '/standards'] + [row['url'] for row in manifest['examples']]
                pdfs = [name for name in manifest['files'] if name.endswith('.pdf')]
                assert pdfs, 'Cached PDF report is missing'
                paths.append('/examples/' + manifest['release'] + '/' + pdfs[0])
                for path in paths:
                    with urlopen(base + path, timeout=15) as response:
                        body = response.read()
                    assert body, f'Empty response: {path}'
                    if path == '/':
                        assert body.count(b'class="demo-report"') == 4
                    if path.endswith('.pdf'):
                        assert body.startswith(b'%PDF-')
                subprocess.run([sys.executable, str(ROOT / 'examples/headless_qc.py'),
                                '--output', str(root / 'synthetic')], cwd=ROOT, env=env,
                               check=True, timeout=120)
                print(json.dumps({'status': 'passed', 'health': health,
                                  'http_pages_checked': len(paths), 'example_datasets': 4,
                                  'synthetic_check': 'M03', 'runtime': 'isolated temporary directory',
                                  'visual_verification': False}, ensure_ascii=False))
            finally:
                server.terminate()
                try:
                    server.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


if __name__ == '__main__':
    main()
