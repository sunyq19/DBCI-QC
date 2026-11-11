"""HTTP acceptance of cached examples and uploads in a fresh shared-demo store.

No browser automation, no access to the user's runtime. Downloaded test reports remain in --output; the service clears its temporary copies.
Use --edf for a public real recording; otherwise use a synthetic engineering file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, ProxyHandler, HTTPCookieProcessor, build_opener
from http.cookiejar import CookieJar

REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--edf', type=Path)
    parser.add_argument('--caddy', type=Path, help='Also exercise the generated reverse proxy using this local Caddy binary')
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    source = args.edf.resolve() if args.edf else root / 'synthetic.edf'
    if not args.edf:
        sys.path.insert(0, str(REPO / 'examples'))
        from headless_qc import write_synthetic_edf
        write_synthetic_edf(source)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    proxy_port = None
    if args.caddy:
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            proxy_port = listener.getsockname()[1]
    origin = f'http://demo.example.org:{proxy_port}' if proxy_port else 'http://demo.example.org'
    config = {'port': port, 'python': sys.executable, 'data_dir': str(root / 'runtime'),
              'inputs': [], 'profiles': [], 'data_policy': 'public-only/1', 'admission_policy': 'cloud-intake/1.3',
              'deployment': {'mode': 'shared_demo', 'public_origin': origin, 'reserve_gib': 2}}
    config_path = root / 'workbench.json'
    config_path.write_text(json.dumps(config))
    env = dict(os.environ, PYTHONPATH=str(REPO / 'src'), PYTHONNOUSERSITE='1', MPLBACKEND='Agg',
               OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    clients = [build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar())) for _ in range(2)]
    base = f'http://127.0.0.1:{proxy_port or port}'
    process = None
    proxy = None
    log = (root / 'server.log').open('a')

    def call(path, body=None, upload=None, raw=False, client=0, extra=None, direct=False):
        headers = {'Host': origin.split('://')[1], 'Origin': origin, 'Content-Type': 'application/json'}
        if upload:
            headers.update({'Content-Type': 'application/octet-stream', 'X-Filename': quote(upload.name)})
        headers.update(extra or {})
        data = upload.read_bytes() if upload else json.dumps(body).encode() if body is not None else None
        address = f'http://127.0.0.1:{port}' if direct else base
        with clients[client].open(Request(address + path, data=data, headers=headers), timeout=180) as response:
            data = response.read()
        return data if raw else json.loads(data)

    def start():
        nonlocal process
        process = subprocess.Popen([sys.executable, str(REPO / 'apps/workbench/server.py'),
                                    '--config', str(config_path)], cwd=REPO, env=env, stdout=log, stderr=log)
        deadline = time.monotonic() + 60
        while True:
            try:
                return call('/api/v1/health')
            except OSError:
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Service did not start; inspect ' + str(root / 'server.log'))
                time.sleep(.2)

    def stop():
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    checks = {}
    try:
        if args.caddy:
            from prepare_demo import prepare
            prepare(origin, root / 'runtime', root / 'service', 'dbciqc', port, Path(sys.executable), 2)
            caddyfile = root / 'service/Caddyfile'
            caddyfile.write_text('{\n    admin off\n}\n' + caddyfile.read_text().replace(origin + ' {', origin + ' {\n    bind 127.0.0.1', 1))
            proxy_env = dict(env, XDG_CONFIG_HOME=str(root / 'caddy-config'), XDG_DATA_HOME=str(root / 'caddy-data'))
            subprocess.run([str(args.caddy), 'validate', '--config', str(caddyfile), '--adapter', 'caddyfile'],
                           env=proxy_env, check=True, stdout=log, stderr=log)
            proxy = subprocess.Popen([str(args.caddy), 'run', '--config', str(caddyfile), '--adapter', 'caddyfile'],
                                     env=proxy_env, stdout=log, stderr=log)
            checks['real_reverse_proxy'] = True
        health = start()
        assert call('/api/v1/data')['items'] == []
        home = call('/', raw=True).decode()
        assert 'data-deployment="shared_demo"' in home and 'data-upload-policy="temporary"' in home
        assert home.count('class="demo-report"') == 4
        manifest = json.loads((REPO / 'apps/workbench/example-cache/manifest.json').read_text())
        for name, digest in manifest['files'].items():
            payload = call('/examples/' + manifest['release'] + '/' + name, raw=True)
            assert hashlib.sha256(payload).hexdigest() == digest, name
        checks['cached_examples'] = {'modalities': [e['modality'] for e in manifest['examples']],
                                     'verified_files': len(manifest['files'])}
        for headers in ({'Host': 'wrong.example.org'}, {'Origin': 'https://wrong.example.org'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            try:
                call('/api/v1/health', extra=headers, direct=True)
                raise AssertionError('Foreign request accepted')
            except HTTPError as error:
                assert error.code == 403
        checks['origin_boundary'] = True
        intake = call('/api/v1/intakes', upload=source)
        selected = intake['suggestions']['eeg_indices']
        confirm = {'confirmed': True, 'modality': 'scalp_eeg', 'reference_scheme': 'unknown',
                   'eeg_indices': selected, 'reference_indices': {}, 'context_tags': {'task': 'unknown'},
                   'label': '公开 EEG 演示' if args.edf else '合成信号流程验证',
                   'source_note': 'PhysioNet EEGMMIDB S001R03; public workflow test.' if args.edf else 'Synthetic engineering fixture.'}
        record = call('/api/v1/intakes/' + intake['id'] + '/confirm', confirm)['input']
        config = {'scope': 'recording', 'recording_options': {'window_seconds': 60, 'expensive_methods': 'skip'}}
        recommendation = call('/api/v1/recommend', {'input_id': record['id'], 'qc_config': config})
        assert recommendation['can_apply'], recommendation
        request = {'input_id': record['id'], 'selected_modules': recommendation['selected_modules'],
                   'qc_config': recommendation['qc_config'], 'run_name': '演示部署 · 推荐方案'}
        plan = call('/api/v1/plan', request)
        job = call('/api/v1/jobs', {**request, 'plan_id': plan['plan_id']})
        identifier = job['id']
        print('Running upload → recommended checks: ' + identifier, flush=True)
        deadline = time.monotonic() + 900
        while job['status'] not in {'completed', 'failed', 'cancelled', 'interrupted'}:
            if time.monotonic() > deadline:
                raise TimeoutError('QC exceeded 15 minutes')
            time.sleep(.5)
            job = call('/api/v1/jobs/' + identifier)
        assert job['status'] == 'completed', job
        result = call('/api/v1/jobs/' + identifier + '/summary')
        score = result['report_view']['score']
        assert isinstance(score['value'], (int, float)) and 0 <= score['value'] <= 100
        parts = {p['id']: p for p in score['components']}
        for key in ('integrity', 'line_noise', 'hf_burst'):
            part = parts[key]
            if part['value'] is None:
                assert part['weight'] == 0 and part['automatically_excluded'], part
            else:
                assert part['status'] == 'computed' and 0 <= part['value'] <= 100, part
        if not args.edf:
            assert all(parts[k]['value'] is not None for k in ('integrity', 'line_noise', 'hf_burst'))
        checks['score'] = {'total': score['value'], 'version': score['version'],
                           'components': {k: parts[k]['value'] for k in ('integrity', 'line_noise', 'hf_burst')}}
        (root / 'result-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        prefix = '/api/v1/jobs/' + identifier
        report = call(prefix + '/report', raw=True)
        pdf = call(prefix + '/report.pdf', raw=True)
        assert b'EEG' in report and pdf.startswith(b'%PDF-')
        (root / 'report.html').write_bytes(report)
        (root / 'report.pdf').write_bytes(pdf)
        charts = call(prefix + '/visualizations?embedded=1', raw=True)
        assert b'<html' in charts.lower()
        wave = call(prefix + '/waveform-window?start_seconds=0&duration_seconds=2&channel_indices=0,1&max_points=400')
        assert len(wave['channels']) == 2
        library = call('/api/v1/data', client=1)
        assert library['items'] == []
        assert call('/api/v1/jobs', client=1)['jobs'] == []
        for endpoint in (prefix, prefix+'/report', prefix+'/report.pdf', prefix+'/waveform-context', '/api/v1/inputs/'+record['id']):
            try:
                call(endpoint, raw=True, client=1)
                raise AssertionError('Other browser accessed a private upload')
            except HTTPError as error: assert error.code == 403
        assert call('/api/v1/data')['items'] == []
        checks['upload_recommendation_report_pdf_waveform'] = True
        checks['two_independent_http_clients_are_isolated'] = True
        checks['selected_modules'] = recommendation['selected_modules']
        checks['recording_seconds'] = intake['metadata']['duration_seconds']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == original_hash
        assert call('/api/v1/temporary-session/finish', {})['status'] in {'cleared','clearing'}
        deadline = time.monotonic() + 20
        temporary = root/'runtime/.temporary/runtime'
        while list((temporary/'jobs').glob('*/job.json')) and time.monotonic() < deadline: time.sleep(.2)
        assert not list((temporary/'jobs').glob('*'))
        assert not list((temporary/'intakes').glob('*'))
        assert not list((root/'runtime/jobs').glob('*'))
        assert not list((root/'runtime/intakes').glob('*'))
        checks['finish_removes_payload_reports_logs_and_metadata'] = True
        # Simulate a crash with a newly uploaded record; startup must purge it.
        call('/api/v1/intakes', upload=source)
        process.kill(); process.wait(); start()
        assert not list((temporary/'intakes').glob('*'))
        try:
            call(prefix, raw=True)
            raise AssertionError('Temporary report survived restart')
        except HTTPError as error: assert error.code == 404
        assert call('/api/v1/data', client=1)['items'] == []
        checks['restart_removes_abandoned_temporary_uploads'] = True
        checks['source_unchanged'] = True
        evidence = {'status': 'passed', 'version': health['version'], 'checks': checks,
                    'job_id': identifier, 'sample_sha256': original_hash,
                    'real_data': bool(args.edf), 'browser_visual_check': False, 'remote_server_deployed': False}
        (root / 'acceptance.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(evidence, ensure_ascii=False, indent=2))
    finally:
        stop()
        if proxy is not None:
            proxy.terminate()
            proxy.wait(15)
        log.close()


if __name__ == '__main__':
    main()
