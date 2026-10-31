"""Local-only modular QC API. The HTTP layer owns no algorithm decisions."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, quote, parse_qs
import argparse
import copy
import json
import mimetypes
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import uuid

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.core import catalog, build_plan
from ephys_qc.method_registry import tool_domains
from ephys_qc.workflow import workflow
from ephys_qc.tagging import describe_data, context_defaults, context_options
from ephys_qc.readers import inspect_recording, list_readers
from ephys_qc.source_selection import reader_kwargs
from ephys_qc.version import __version__, API_VERSION
from ephys_qc.modalities import ROUTES, DESCRIPTIVE, route
from intake import IntakeStore, MAX_UPLOAD_BYTES
from record_revisions import RecordRevisions, RevisionConflict
from standards_page import render_standards, NAVIGATION_SCRIPT, DOCUMENT_PAGES

SERVICE = 'ephys-qc-modular-workbench'
TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)


def insert_report_navigation(report, navigation):
    """Add served-view navigation without rewriting frozen standalone reports."""
    rendered, count = re.subn(r'(<body\b[^>]*>)', lambda match: match.group(1) + navigation,
                             report, count=1, flags=re.I)
    if count:
        return rendered
    # The existing report writers use HTML's optional body start tag.
    return re.sub(r'(<main\b[^>]*>)', lambda match: navigation + match.group(1),
                  report, count=1, flags=re.I)


def public_input(item):
    result = {key: copy.deepcopy(item[key]) for key in ('id', 'label', 'dataset_id', 'profile_id', 'metadata', 'default_config', 'description', 'provenance', 'data_usage', 'modality', 'modality_source', 'reference_scheme', 'preprocessing', 'annotation_mapping', 'record_family', 'record_revision', 'parent_input_id', 'availability') if key in item}
    result.setdefault('record_family', item['id'])
    result.setdefault('record_revision', 1)
    result.setdefault('default_config', {}).setdefault('context_tags', context_defaults(item))
    result['data_tags'] = describe_data(item)
    return result


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.root = Path(settings['data_dir']).resolve()
        (self.root / 'jobs').mkdir(parents=True, exist_ok=True)
        self.inputs = {}
        for item in settings['inputs']:
            item = copy.deepcopy(item)
            self._availability(item, refresh=True)
            self.inputs[item['id']] = item
        self.intakes = IntakeStore(self.root)
        for item in self.intakes.registered():
            if item['id'] in self.inputs:
                raise ValueError('本机提交记录ID与预登记输入冲突。')
            self._availability(item)
            self.inputs[item['id']] = item
        self.revisions = RecordRevisions(self.root)
        for item in self.revisions.registered():
            self._availability(item)
            self.inputs[item['id']] = item
        self.jobs, self.processes = {}, {}
        self.lock = threading.RLock()
        self.queue = queue.Queue()
        for path in sorted((self.root / 'jobs').glob('*/job.json')):
            job = read_json(path)
            if job['status'] not in TERMINAL:
                job.update(status='interrupted', message='服务重启；本次运行未完成，可重新提交。', ended_at=now())
                for node in job['modules']:
                    if node['status'] in {'running', 'pending'}:
                        node.update(status='skipped', reason='本次运行已中断。')
                save_json(path, job)
            self.jobs[job['id']] = job
        threading.Thread(target=self._loop, daemon=True).start()

    @staticmethod
    def _availability(item, refresh=False):
        try:
            if refresh:
                item['metadata'] = inspect_recording(item['source_path'], **reader_kwargs(item.get('metadata', {})))
            paths = [item['source_path']] + [f['path'] for f in item.get('expected_source_files', [])]
            if not all(Path(p).is_file() for p in paths):
                raise ValueError('来源或配套文件暂时不可用。')
            item['availability'] = {'status': 'available'}
        except (OSError, ValueError) as exc:
            item.setdefault('metadata', {'channels': [], 'duration_seconds': 0})
            item['availability'] = {'status': 'unavailable', 'reason': str(exc)}

    def persist(self, job):
        save_json(self.root / 'jobs' / job['id'] / 'job.json', job)

    def plan_request(self, body):
        if not isinstance(body, dict) or set(body) - {'input_id', 'selected_modules', 'qc_config', 'plan_id', 'parent_job_id'}:
            raise ValueError('请求仅接受输入、所选模块、分析配置和计划标识。')
        input_id = body.get('input_id')
        if not isinstance(input_id, str) or input_id not in self.inputs:
            raise ValueError('请选择一个已登记的数据文件。')
        with self.lock:
            item = copy.deepcopy(self.inputs[input_id])
        if item.get('availability', {}).get('status') == 'unavailable':
            raise ValueError('来源文件暂时不可用，请恢复原始文件后重新载入服务。')
        plan = build_plan(item, body.get('selected_modules'), body.get('qc_config'))
        return item, plan

    def recommend_request(self, body):
        from ephys_qc.recommendations import recommend
        if not isinstance(body, dict) or set(body) - {'input_id', 'qc_config'}:
            raise ValueError('推荐请求仅接受已登记数据和当前分析配置。')
        identifier = body.get('input_id')
        if not isinstance(identifier, str) or identifier not in self.inputs:
            raise ValueError('请先完成数据读取与字段确认。')
        with self.lock:
            record = copy.deepcopy(self.inputs[identifier])
        return recommend(record, body.get('qc_config'))

    def confirm_intake(self, identifier, body):
        with self.lock:
            record = self.intakes.confirm(identifier, body)
            self.inputs[record['id']] = record
            return {'status': 'registered', 'input': public_input(record)}

    def select_intake_stream(self, identifier, body):
        with self.lock:
            return self.intakes.select_stream(identifier, body)

    def revise_input(self, identifier, body):
        with self.lock:
            original = self.inputs[identifier]
            family = original.get('record_family', identifier)
            latest = max(i.get('record_revision', 1) for i in self.inputs.values()
                         if i.get('record_family', i['id']) == family)
            record = self.revisions.revise(original, body, latest)
            self.inputs[record['id']] = record
            return {'status': 'registered', 'input': public_input(record)}

    def configuration(self, identifier):
        self.job(identifier)
        request = read_json(self.root / 'jobs' / identifier / 'request.json')
        return {'input_id': request['input']['id'], 'label': request['input']['label'],
                'input_modality': request['input'].get('modality', 'scalp_eeg'),
                'input_revision': request['input'].get('record_revision', 1),
                'selected_modules': request['selected_modules'], 'qc_config': request['qc_config'],
                'scope': request['qc_config'].get('scope', 'window'), 'parent_job_id': identifier}

    def workspace(self, identifier):
        from review_workspace import ReviewWorkspace
        self.job(identifier)
        return ReviewWorkspace(self.root / 'jobs' / identifier)

    def save_review(self, identifier, body):
        from review_workspace import ReviewConflict
        with self.lock:
            try:
                return self.workspace(identifier).update_review(body)
            except ReviewConflict as exc:
                raise RevisionConflict(str(exc)) from exc

    def submit(self, body):
        item, plan = self.plan_request(body)
        if body.get('plan_id') != plan['plan_id']:
            raise ValueError('检查方案与当前配置不一致，请重新预览方案后运行。')
        with self.lock:
            parent = body.get('parent_job_id')
            if parent is not None:
                if not isinstance(parent, str) or parent not in self.jobs:
                    raise ValueError('复制来源任务不存在。')
                old = read_json(self.root / 'jobs' / parent / 'request.json')['input']
                if old.get('record_family', old['id']) != item.get('record_family', item['id']):
                    raise ValueError('复制方案须保留同一来源记录。')
            if sum(j['status'] not in TERMINAL for j in self.jobs.values()) >= 5:
                raise ValueError('最多保留 5 个等待或运行中的任务，请等待现有任务完成。')
            id_ = uuid.uuid4().hex
            directory = self.root / 'jobs' / id_
            directory.mkdir()
            request = {'input': item, 'plan': plan, 'qc_config': plan['qc_config'],
                       'selected_modules': plan['selected_modules'], 'parent_job_id': parent}
            save_json(directory / 'request.json', request)
            job = {'id': id_, 'label': item['label'], 'input_id': item['id'], 'status': 'queued',
                   'input_revision': item.get('record_revision', 1), 'record_family': item.get('record_family', item['id']),
                   'parent_job_id': parent,
                   'phase': 'queued', 'message': '等待执行', 'created_at': now(), 'plan': plan,
                   'modules': [{'id': n['id'], 'name': n['name'], 'status': 'skipped' if n['status'] == 'skipped' else 'pending',
                                'reason': n.get('reason', ''), 'message': ''} for n in plan['nodes']]}
            self.jobs[id_] = job
            self.persist(job)
            self.queue.put(id_)
            return copy.deepcopy(job)

    def cancel(self, id_):
        with self.lock:
            job = self.jobs[id_]
            if job['status'] in TERMINAL:
                return copy.deepcopy(job)
            p = self.processes.get(id_)
            job.update(status='cancelling' if p else 'cancelled', message='正在停止任务' if p else '任务已取消')
            if not p:
                job['ended_at'] = now()
                self._stop_nodes(job, '任务已取消。')
            self.persist(job)
            if p:
                (self.root / 'jobs' / id_ / 'cancel.requested').touch()
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                def force_stop():
                    if p.poll() is None:
                        try:
                            os.killpg(p.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                timer = threading.Timer(5, force_stop)
                timer.daemon = True
                timer.start()
            return copy.deepcopy(job)

    @staticmethod
    def _stop_nodes(job, reason):
        for node in job['modules']:
            if node['status'] in {'pending', 'running'}:
                node.update(status='skipped', reason=reason, message=reason)

    def _loop(self):
        while True:
            id_ = self.queue.get()
            directory = self.root / 'jobs' / id_
            try:
                with self.lock:
                    job = self.jobs[id_]
                    if job['status'] != 'queued':
                        continue
                    env = dict(os.environ, MPLBACKEND='Agg', OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                               MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1', PYTHONUNBUFFERED='1',
                               MPLCONFIGDIR=str(self.root / 'matplotlib'))
                    p = subprocess.Popen([self.settings['python'], str(ROOT / 'worker.py'), str(directory)],
                                         cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, start_new_session=True)
                    self.processes[id_] = p
                    job.update(status='running', phase='starting', message='正在载入模块', started_at=now())
                    self.persist(job)
                with (directory / 'run.log').open('w', encoding='utf-8') as log:
                    for line in p.stdout:
                        log.write(line)
                        log.flush()
                        if line.startswith('@@QC@@'):
                            try:
                                event = json.loads(line[6:])
                            except (ValueError, TypeError):
                                continue
                            with self.lock:
                                if job['status'] == 'running':
                                    job.update(phase=event['module_id'], message=event['message'])
                                    for node in job['modules']:
                                        if node['id'] == event['module_id']:
                                            node.update(status=event['status'], message=event['message'])
                                    self.persist(job)
                code = p.wait()
                with self.lock:
                    if job['status'] == 'cancelling':
                        job.update(status='cancelled', message='任务已取消，未完成结果不作为最终报告。')
                        self._stop_nodes(job, '任务已取消。')
                    elif code == 0 and (directory / 'result.json').is_file():
                        result = read_json(directory / 'result.json')
                        if result.get('status') == 'cancelled':
                            job.update(status='cancelled', message='任务已取消；已完成范围保留，未检查范围不会视为正常。', modules=result['modules'])
                        elif result.get('status') == 'failed':
                            errors = [m['reason'] for m in result['modules'] if m['status'] == 'failed']
                            message = '关键步骤失败：' + '；'.join(errors)
                            job.update(status='failed', message=message, error=message, modules=result['modules'])
                        else:
                            job.update(status='completed', phase='M09', message='报告已生成；请查看各模块评估范围。', modules=result['modules'])
                    else:
                        error_file = directory / 'error.json'
                        error = read_json(error_file)['message'] if error_file.exists() else f'执行进程退出（{code}），请查看日志。'
                        job.update(status='failed', message=error, error=error)
                        self._stop_nodes(job, '执行失败，未完成评估。')
                    job['ended_at'] = now()
                    self.persist(job)
            except Exception as exc:
                with self.lock:
                    job = self.jobs[id_]
                    job.update(status='failed', message=str(exc), error=str(exc), ended_at=now())
                    self._stop_nodes(job, '服务执行异常。')
                    self.persist(job)
            finally:
                with self.lock:
                    self.processes.pop(id_, None)
                self.queue.task_done()

    def job(self, id_):
        with self.lock:
            job = copy.deepcopy(self.jobs[id_])
        progress = self.root / 'jobs' / id_ / 'recording-progress.json'
        if progress.is_file():
            job['recording_progress'] = read_json(progress)
        return job

    def result(self, id_):
        if self.job(id_)['status'] != 'completed':
            raise ValueError('任务尚未完成，没有可用的最终报告。')
        data = read_json(self.root / 'jobs' / id_ / 'result.json')
        for artifact in data['artifacts']:
            artifact['url'] = f'/api/v1/jobs/{id_}/artifacts/{quote(artifact["name"])}'
        return data

    def artifact(self, id_, name):
        if Path(name).name != name or name not in {a['name'] for a in self.result(id_)['artifacts']}:
            raise KeyError(name)
        root = (self.root / 'jobs' / id_ / 'artifacts').resolve()
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise KeyError(name)
        return target


class Handler(BaseHTTPRequestHandler):
    server_version = 'EphysModularQC/' + __version__

    @property
    def store(self):
        return self.server.store

    def log_message(self, fmt, *args):
        if len(args) > 1 and str(args[1]).startswith('5'):
            super().log_message(fmt, *args)

    def check_local(self):
        hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
        if self.headers.get('Host') not in hosts:
            raise PermissionError('只接受本机地址。')
        if self.headers.get('Origin') and self.headers['Origin'] not in {'http://' + h for h in hosts}:
            raise PermissionError('只接受本工作台发起的请求。')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise PermissionError('不接受跨站请求。')

    def send_bytes(self, data, mime='application/json; charset=utf-8', code=200, headers=None):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def json(self, value, code=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'), code=code)

    def body(self):
        if self.headers.get_content_type() != 'application/json':
            raise ValueError('请提交 JSON 配置。')
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 256 * 1024:
            raise ValueError('配置长度无效。')
        self.connection.settimeout(15)
        return json.loads(self.rfile.read(length))

    def waveform_query(self):
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        if set(query) - {'start_seconds', 'duration_seconds', 'channel_indices', 'channels', 'max_points'} or any(len(v) != 1 for v in query.values()):
            raise ValueError('波形请求字段无效。')
        channels = query.get('channel_indices', query.get('channels', ['']))[0]
        return {'start_seconds': float(query['start_seconds'][0]) if 'start_seconds' in query else None,
                'duration_seconds': float(query['duration_seconds'][0]) if 'duration_seconds' in query else None,
                'channel_indices': [int(i) for i in channels.split(',') if i != ''] if channels else None,
                'max_points': int(query.get('max_points', ['2000'])[0])}

    def dispatch(self):
        try:
            self.check_local()
            path = unquote(urlsplit(self.path).path)
            (self.get if self.command == 'GET' else self.post)(path)
        except PermissionError as exc:
            self.json({'error': str(exc)}, 403)
        except RevisionConflict as exc:
            self.json({'error': str(exc)}, 409)
        except KeyError:
            self.json({'error': '请求的数据、任务或结果不存在。'}, 404)
        except (ValueError, TypeError, OverflowError) as exc:
            self.json({'error': str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            print(f'Service exception: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
            self.json({'error': '本地服务处理失败，请查看服务日志。'}, 500)

    do_GET = dispatch
    do_POST = dispatch

    def get(self, path):
        english = path.startswith('/en/')
        document_path = path[3:] if english else path
        common_document = next((slug for slug in DOCUMENT_PAGES
                                if document_path in {'/standards/' + slug, '/standards/' + slug + '.md'}), None)
        if common_document:
            documents = (REPO / 'docs' / ('en' if english else '')).resolve()
            filename = DOCUMENT_PAGES[common_document][0]
            source = (documents / filename).resolve()
            if not source.is_relative_to(documents) or not source.is_file():
                raise KeyError('standards')
            data = source.read_bytes()
            if document_path.endswith('.md'):
                return self.send_bytes(data, 'text/markdown; charset=utf-8', headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'})
            return self.send_bytes(render_standards(data.decode('utf-8'), lang='en' if english else 'zh-CN',
                                                   modality=common_document).encode('utf-8'), 'text/html; charset=utf-8')
        document_modality = 'scalp_eeg'
        for modality, info in ROUTES.items():
            prefix = '/standards/' + info['slug']
            if info['slug'] and (document_path in {prefix, prefix + '.md'} or document_path.startswith(prefix + '/')):
                document_modality = modality
                document_path = document_path.replace(prefix, '/standards', 1)
                break
        module_document = re.fullmatch(r'/standards/modules/(M0[1-9])(\.md)?', document_path)
        if document_path in {'/standards', '/standards.md'} or module_document:
            module_id = module_document.group(1) if module_document else None
            documents = (REPO / 'docs' / 'en' if english else REPO / 'docs').resolve()
            if document_modality in DESCRIPTIVE:
                documents = documents / route(document_modality)['slug']
            source = (documents / 'modules' / f'{module_id}.md' if module_id else documents / 'qc-standards.md').resolve()
            if not source.is_relative_to(documents) or not source.is_file():
                raise KeyError('standards')
            # Read on every request: the readable page and download share one
            # maintained source, without a separate build or cached copy.
            data = source.read_bytes()
            if path.endswith('.md'):
                return self.send_bytes(data, 'text/markdown; charset=utf-8', headers={
                    'Content-Disposition': f'attachment; filename="{module_id + ".md" if module_id else "qc-standards.md"}"'})
            return self.send_bytes(render_standards(data.decode('utf-8'), module_id, lang='en' if english else 'zh-CN', modality=document_modality).encode('utf-8'),
                                   'text/html; charset=utf-8')
        if path in {'/standards-navigation.js', '/standards-print.js'}:
            return self.send_bytes(NAVIGATION_SCRIPT.encode('utf-8'), 'text/javascript; charset=utf-8')
        if path == '/api/v1/health':
            return self.json({'status': 'ok', 'service': SERVICE, 'api_version': API_VERSION, 'version': __version__})
        if path == '/api/v1/catalog':
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) - {'modality'} or any(len(values) != 1 for values in query.values()):
                raise ValueError('方法目录只接受一个modality字段。')
            modality = query.get('modality', ['scalp_eeg'])[0]
            if modality not in ROUTES:
                raise ValueError('当前目录：' + ', '.join(ROUTES))
            with self.store.lock:
                inputs = [public_input(i) for i in self.store.inputs.values() if i.get('modality', 'scalp_eeg') == modality]
            modules = catalog(modality)
            overview = '/standards' + ('/' + route(modality)['slug'] if route(modality)['slug'] else '')
            for module in modules:
                module['documentation_url'] = overview + '/modules/' + module['id']
                module.setdefault('selectable', not (modality in DESCRIPTIVE and module['id'] == 'M06'))
            return self.json({'service': SERVICE, 'api_version': API_VERSION, 'version': __version__, 'modules': modules,
                              'active_modality': modality, 'overview_url': overview,
                              'modalities': [{'id': key, 'label': value['label'], 'qc_supported': True, 'scope_note': value['scope_note']} for key, value in ROUTES.items()],
                              'workflow': workflow(modality),
                              'method_domains': tool_domains(),
                              'inputs': inputs,
                              'profiles': self.store.settings['profiles'], 'context_tag_options': context_options(),
                              'capabilities': {'intake': {'formats': ['EDF', 'BDF', 'BrainVision', 'EEGLAB', 'FIF', 'SpikeGLX', 'NWB'],
                                                          'readers': list_readers(), 'package_formats': ['ZIP'],
                                                          'modalities': list(ROUTES),
                                                          'inspection_modalities': ['scalp_eeg', 'ecog', 'seeg', 'extracellular', 'other'],
                                                          'max_upload_bytes': MAX_UPLOAD_BYTES, 'local_only': True},
                                               'recommendation': 'explicit_rules_with_reasons'}})
        if path == '/api/v1/intakes':
            return self.json({'intakes': self.store.intakes.pending()})
        if path == '/api/v1/inputs':
            if urlsplit(self.path).query:
                raise ValueError('记录列表统一展示全部已登记输入，不按执行目录过滤。')
            with self.store.lock:
                records = [public_input(item) for item in self.store.inputs.values()]
            return self.json({'inputs': records})
        match = re.fullmatch(r'/api/v1/intakes/([a-f0-9]{32})', path)
        if match:
            return self.json(self.store.intakes.get(match.group(1)))
        if path == '/api/v1/jobs':
            with self.store.lock:
                jobs = sorted(copy.deepcopy(list(self.store.jobs.values())), key=lambda j: j['created_at'], reverse=True)
            return self.json({'jobs': jobs})
        match = re.fullmatch(r'/api/v1/inputs/([A-Za-z0-9_-]+)(?:/(waveform))?', path)
        if match:
            identifier, action = match.groups()
            with self.store.lock:
                record = copy.deepcopy(self.store.inputs[identifier])
            if action == 'waveform':
                from review_workspace import waveform_for_input
                return self.json(waveform_for_input(record, **self.waveform_query()))
            return self.json(public_input(record))
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/(candidates|waveform|review|configuration)', path)
        if match:
            identifier, action = match.groups()
            if action == 'configuration':
                return self.json(self.store.configuration(identifier))
            workspace = self.store.workspace(identifier)
            if action == 'waveform':
                return self.json(workspace.waveform(**self.waveform_query()))
            if action == 'candidates':
                return self.json(workspace.candidates())
            return self.json(workspace.review())
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})(?:/(result|report|log|artifacts/(.+)))?', path)
        if match:
            id_, action, filename = match.groups()
            job = self.store.job(id_)
            if action is None:
                return self.json(job)
            if action == 'result':
                return self.json(self.store.result(id_))
            if action == 'log':
                log = self.store.root / 'jobs' / id_ / 'run.log'
                return self.send_bytes(log.read_bytes()[-100_000:] if log.exists() else b'', 'text/plain; charset=utf-8')
            if action == 'report':
                report = self.store.artifact(id_, 'report.html').read_text(encoding='utf-8')
                # Keep the standalone report usable both on disk and at the job's /report route.
                # Use explicit artifact URLs without relaxing the base-uri policy.
                for a in self.store.result(id_)['artifacts']:
                    safe_name = a['name']
                    for attr in ('src', 'href'):
                        report = report.replace(f'{attr}="{safe_name}"', f'{attr}="{a["url"]}"')
                        report = report.replace(f"{attr}='{safe_name}'", f'{attr}="{a["url"]}"')
                # Navigation belongs to the served view; frozen report bytes stay unchanged.
                from html import escape
                declared = job.get('plan', {}).get('input_modality', {})
                modality = declared.get('value') if isinstance(declared, dict) else declared
                modality = modality if modality in ROUTES else 'scalp_eeg'
                language = parse_qs(urlsplit(self.path).query).get('lang', ['zh-CN'])[0]
                back = f'/?modality={modality}&job={id_}' + ('&lang=en' if language == 'en' else '')
                label = 'Return to this QC run' if language == 'en' else '返回本次质控'
                navigation = f'<nav aria-label="QC navigation" style="padding:14px 24px;background:#eff6ff;border-bottom:1px solid #dbeafe"><a href="{escape(back, quote=True)}">← {label}</a></nav>'
                report = insert_report_navigation(report, navigation)
                return self.send_bytes(report.encode('utf-8'), 'text/html; charset=utf-8')
            if filename:
                target = self.store.artifact(id_, filename)
                mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                if target.suffix in {'.html', '.json', '.txt', '.csv', '.tsv'}:
                    mime += '; charset=utf-8'
                return self.send_bytes(target.read_bytes(), mime)
        static = {'/': 'index.html', '/app.js': 'app.js', '/i18n.js': 'i18n.js', '/styles.css': 'styles.css', '/favicon.svg': 'favicon.svg'}
        if path in static:
            target = ROOT / 'web' / static[path]
            return self.send_bytes(target.read_bytes(), (mimetypes.guess_type(target.name)[0] or 'text/plain') + '; charset=utf-8')
        raise KeyError(path)

    def post(self, path):
        if path == '/api/v1/intakes':
            if self.headers.get_content_type() != 'application/octet-stream' or self.headers.get('Transfer-Encoding'):
                raise ValueError('请提交带长度的本机文件或ZIP包，不接受远程路径。')
            length = int(self.headers.get('Content-Length', '0'))
            filename = unquote(self.headers.get('X-Filename', ''))
            self.connection.settimeout(60)
            return self.json(self.store.intakes.receive(filename, length, self.rfile), 201)
        match = re.fullmatch(r'/api/v1/intakes/([a-f0-9]{32})/confirm', path)
        if match:
            return self.json(self.store.confirm_intake(match.group(1), self.body()))
        match = re.fullmatch(r'/api/v1/intakes/([a-f0-9]{32})/stream', path)
        if match:
            return self.json(self.store.select_intake_stream(match.group(1), self.body()))
        match = re.fullmatch(r'/api/v1/inputs/([A-Za-z0-9_-]+)/revisions', path)
        if match:
            return self.json(self.store.revise_input(match.group(1), self.body()), 201)
        if path == '/api/v1/recommend':
            return self.json(self.store.recommend_request(self.body()))
        if path == '/api/v1/plan':
            _, plan = self.store.plan_request(self.body())
            return self.json(plan)
        if path == '/api/v1/jobs':
            return self.json(self.store.submit(self.body()), 202)
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/cancel', path)
        if match:
            self.body()
            return self.json(self.store.cancel(match.group(1)))
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/review', path)
        if match:
            return self.json(self.store.save_review(match.group(1), self.body()))
        raise KeyError(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path, default=REPO / '.local' / 'workbench.json')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    settings = read_json(args.config)
    if not Path(settings['python']).is_file():
        raise SystemExit('请在本机配置中填写已安装 BrainElecQC 的 Python 路径。')
    # Bind first: a duplicate launch must not mark a live process's jobs interrupted.
    server = ThreadingHTTPServer(('127.0.0.1', args.port or settings.get('port', 8769)), Handler)
    server.daemon_threads = True
    server.store = Store(settings)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    print(f'Local: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for id_ in list(server.store.processes):
            server.store.cancel(id_)
        server.server_close()


if __name__ == '__main__':
    main()
