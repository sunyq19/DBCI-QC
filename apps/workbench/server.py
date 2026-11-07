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
from ephys_qc.admission import DEFAULT_INTAKE_LIMITS, POLICIES, LimitExceeded, configured_policy, check_registered_record
from ephys_qc.modalities import ROUTES, DESCRIPTIVE, route
from intake import IntakeStore
from record_revisions import RecordRevisions, RevisionConflict
from standards_page import render_standards, NAVIGATION_SCRIPT, DOCUMENT_PAGES
from package_jobs import PackageJobs

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
    result = {key: copy.deepcopy(item[key]) for key in ('id', 'label', 'dataset_id', 'profile_id', 'metadata', 'default_config', 'description', 'provenance', 'data_usage', 'modality', 'modality_source', 'reference_scheme', 'preprocessing', 'annotation_mapping', 'record_family', 'record_revision', 'parent_input_id', 'availability', 'dataset_context', 'library_origin', 'retention') if key in item}
    result.setdefault('record_family', item['id'])
    result.setdefault('record_revision', 1)
    result.setdefault('default_config', {}).setdefault('context_tags', context_defaults(item))
    result['data_tags'] = describe_data(item)
    return result


def public_intake(value):
    result = copy.deepcopy(value)
    result.pop('linked_root', None)
    return result


class Store:
    def __init__(self, settings):
        self.settings = settings
        self.admission_policy = configured_policy(settings)
        self.root = Path(settings['data_dir']).resolve()
        self.packages = PackageJobs(settings)
        from package_reviews import PackageReviews
        self.package_reviews = PackageReviews(self.packages)
        (self.root / 'jobs').mkdir(parents=True, exist_ok=True)
        self.inputs = {}
        for item in settings['inputs']:
            item = copy.deepcopy(item)
            self._availability(item, refresh=True)
            self.inputs[item['id']] = item
        self.link_lock = threading.RLock()
        self.intakes = IntakeStore(self.root, limits=self.admission_policy or DEFAULT_INTAKE_LIMITS)
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
        self.report_views = {}
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
        from batch_jobs import BatchJobs
        self.batches = BatchJobs(self)
        threading.Thread(target=self._retention_loop, daemon=True).start()

    def expire_uploads(self):
        from upload_retention import expire_uploads, ACTIVE
        with self.lock:
            protected = {j.get('record_family', j['input_id']) for j in self.jobs.values() if j['status'] in ACTIVE}
            expired = expire_uploads(self.intakes, protected_families=protected)
            for row in expired:
                for item in self.inputs.values():
                    if item.get('record_family', item['id']) == row['family']:
                        item['retention'] = copy.deepcopy(row['retention'])
                        self._availability(item)
            return expired

    def _retention_loop(self):
        import time, logging
        while True:
            try: self.expire_uploads()
            except Exception: logging.exception('Upload retention check failed; retry in 60 seconds')
            time.sleep(60)

    @staticmethod
    def _availability(item, refresh=False):
        try:
            if item.get('retention', {}).get('state') == 'expired':
                raise ValueError('上传副本已到期；报告保留，重新检查请再次上传。')
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

    def package_records(self, identifier):
        result = self.packages.records(identifier)
        with self.lock:
            for row in result['records']:
                inputs = {i['id'] for i in self.inputs.values()
                          if i.get('dataset_context', {}).get('package_id') == identifier
                          and i['dataset_context'].get('manifest_hash') == result['manifest_hash']
                          and i['dataset_context'].get('record_id') == row['id']}
                runs = sorted((j for j in self.jobs.values() if j['input_id'] in inputs),
                              key=lambda j: j['created_at'], reverse=True)
                row['signal_runs'] = [{k: j[k] for k in ('id', 'status', 'created_at', 'input_id')} for j in runs]
        return result

    def open_package_record(self, body):
        root, name, context, stream = self.packages.record_source(body)
        with self.link_lock:
            value = self.intakes.link_record(root, name, context, stream_id=stream)
        return self.intake_status(value['id'])

    def intake_status(self, identifier):
        value = self.intakes.get(identifier)
        if value.get('status') == 'registered' and value.get('dataset_context'):
            with self.lock:
                family = self.inputs.get(value['input_id'], {}).get('record_family', value['input_id'])
                versions = [i for i in self.inputs.values() if i.get('record_family', i['id']) == family]
                if versions:
                    latest = max(versions, key=lambda i: i.get('record_revision', 1))
                    value.update(input_id=latest['id'], input_modality=latest['modality'])
        return value

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

    def submit(self, body, *, batch_id=None):
        item, plan = self.plan_request(body)
        if body.get('plan_id') != plan['plan_id']:
            raise ValueError('检查方案与当前配置不一致，请重新预览方案后运行。')
        if item.get('linked_intake_id'):
            self.intakes._verified_source(self.intakes.get(item['linked_intake_id']))
        admission = check_registered_record(item, limits=self.admission_policy) if self.admission_policy else None
        with self.lock:
            # Recheck under the same lock as expiry, before a queued job protects its files.
            current = self.inputs[item['id']]
            if current.get('retention', {}).get('state') == 'expired':
                raise ValueError('上传副本已到期；报告保留，重新检查请再次上传。')
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
                       'selected_modules': plan['selected_modules'], 'parent_job_id': parent, 'batch_id': batch_id, 'admission': admission}
            save_json(directory / 'request.json', request)
            job = {'id': id_, 'label': item['label'], 'input_id': item['id'], 'status': 'queued',
                   'input_revision': item.get('record_revision', 1), 'record_family': item.get('record_family', item['id']),
                   'parent_job_id': parent, 'batch_id': batch_id, 'dataset_context': copy.deepcopy(item.get('dataset_context')),
                   'phase': 'queued', 'message': '等待执行', 'created_at': now(), 'plan': plan,
                   'modules': [{'id': n['id'], 'name': n['name'], 'status': 'skipped' if n['status'] == 'skipped' else 'pending',
                                'reason': n.get('reason', ''), 'message': ''} for n in plan['nodes']]}
            self.jobs[id_] = job
            job['admission'] = admission
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
                    request = read_json(directory / 'request.json')
                    if request['input'].get('linked_intake_id'):
                        self.intakes._verified_source(self.intakes.get(request['input']['linked_intake_id']))
                    if request.get('admission'):
                        current = check_registered_record(request['input'], limits=self.admission_policy)
                        if current['snapshot_fingerprint'] != request['admission']['snapshot_fingerprint']:
                            raise ValueError('来源文件在接入后发生变化，本次任务未执行，请重新提交。')
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

    def dataset_result(self, id_):
        """Small frozen summary for dataset listings; never re-score on navigation."""
        from dataset_overview import read_signal_summary
        if self.job(id_)['status'] != 'completed':
            raise ValueError('任务尚未完成。')
        path = self.root / 'jobs' / id_ / 'result.json'
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        with self.lock:
            if not hasattr(self, 'dataset_summaries'): self.dataset_summaries = {}
            cached = self.dataset_summaries.get(id_)
        if cached and cached[0] == signature:
            return copy.deepcopy(cached[1])
        cache_path = path.with_name('dataset-summary-cache.json')
        try:
            if cache_path.stat().st_size <= 65536:
                saved = read_json(cache_path)
                if (isinstance(saved, dict) and saved.get('version') == 'dataset-display/1' and
                        saved.get('signature') == list(signature) and isinstance(saved.get('summary'), dict)):
                    with self.lock:
                        if len(self.dataset_summaries) >= 128: self.dataset_summaries.pop(next(iter(self.dataset_summaries)))
                        self.dataset_summaries[id_] = (signature, saved['summary'])
                    return copy.deepcopy(saved['summary'])
        except (OSError, ValueError, TypeError):
            pass
        result = read_signal_summary(path)
        after = path.stat()
        if signature != (after.st_mtime_ns, after.st_size):
            raise ValueError('结果文件发生变化，请重新加载。')
        with self.lock:
            if len(self.dataset_summaries) >= 128: self.dataset_summaries.pop(next(iter(self.dataset_summaries)))
            self.dataset_summaries[id_] = (signature, copy.deepcopy(result))
            try:
                save_json(cache_path, {'version': 'dataset-display/1', 'signature': list(signature), 'summary': result})
            except OSError:
                pass  # Read-only archives still produce an in-memory summary.
        return result

    def result(self, id_, *, compact=False):
        if self.job(id_)['status'] != 'completed':
            raise ValueError('任务尚未完成，没有可用的最终报告。')
        from project_score_cache import load
        published = load(self, id_)
        if compact and published:
            for artifact in published.get('artifacts',[]):
                artifact['url'] = f'/api/v1/jobs/{id_}/artifacts/{quote(artifact["name"])}'
            return published
        result_path = self.root / 'jobs' / id_ / 'result.json'
        if compact:
            # Candidate observations can dwarf the report (tens of thousands of
            # rows). Keep the complete evidence on disk and at /result; summary
            # consumers need its count and artifact link, not a second copy.
            stat = result_path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size)
            with self.lock:
                if not hasattr(self, 'result_summaries'): self.result_summaries = {}
                cached = self.result_summaries.get(id_)
            if cached and cached[0] == stamp:
                data = copy.deepcopy(cached[1])
            else:
                import ijson
                from ijson.common import ObjectBuilder
                builder = ObjectBuilder()
                pending_candidates = skipping_candidates = saw_candidates = False
                candidate_count = 0
                with result_path.open('rb') as handle:
                    for prefix, event, value in ijson.parse(handle, use_float=True):
                        if prefix == '' and event == 'map_key' and value == 'candidate_index':
                            pending_candidates = True
                            continue
                        if pending_candidates:
                            pending_candidates = False
                            if event == 'start_array':
                                skipping_candidates = saw_candidates = True
                                continue
                            # Preserve non-array values from older files verbatim.
                            builder.event('map_key', 'candidate_index')
                        if skipping_candidates:
                            if prefix == 'candidate_index.item' and event not in {'end_map', 'end_array', 'map_key'}:
                                candidate_count += 1
                            if prefix == 'candidate_index' and event == 'end_array':
                                skipping_candidates = False
                            continue
                        builder.event(event, value)
                data = builder.value
                if saw_candidates:
                    data['candidate_index_count'] = candidate_count
                    data['candidate_index_artifact'] = 'candidate-index.json' if any(
                        a.get('name') == 'candidate-index.json' for a in data.get('artifacts', [])) else None
                after = result_path.stat()
                if stamp != (after.st_mtime_ns, after.st_size):
                    raise ValueError('结果文件发生变化，请重新加载。')
                with self.lock:
                    if len(self.result_summaries) >= 8: self.result_summaries.pop(next(iter(self.result_summaries)))
                    self.result_summaries[id_] = (stamp, copy.deepcopy(data))
        else:
            data = read_json(result_path)
        saved_view = published.get('report_view') if published else data.get('report_view')
        if isinstance(saved_view, dict) and saved_view.get('score'):
            # Browsing must use the same published/frozen scores as HTML and PDF.
            # The full result retains every original detector field and array.
            data['report_view'] = copy.deepcopy(saved_view)
        elif data.get('analysis_profile') == 'scalp-eeg/1' and data.get('scope') in {'window','recording'}:
            from ephys_qc.report_view import build_report_view, VIEW_VERSION
            root = self.root / 'jobs' / id_
            names = ['result.json', 'artifacts/M03_continuity.json', 'artifacts/M04_spectral.json',
                     'artifacts/M05_bad_channels.json', 'artifacts/M06_muscle.json']
            if data.get('scope') == 'recording':
                names = ['result.json'] + ['artifacts/' + a['name'] for a in data.get('artifacts',[]) if a['name'].endswith(('result.json','M03_continuity.json','M04_spectral.json','M05_bad_channels.json','M06_muscle.json'))]
            signature = [VIEW_VERSION]
            for name in names:
                try:
                    stat = (root / name).stat()
                    signature.append((stat.st_mtime_ns, stat.st_size))
                except FileNotFoundError:
                    signature.append(None)
            with self.lock:
                if not hasattr(self, 'report_views'): self.report_views = {}
                cached = self.report_views.get(id_)
            if not cached or cached[0] != signature:
                view = build_report_view(data, root / 'artifacts', self.job(id_).get('label', id_))
                with self.lock:
                    if len(self.report_views) >= 16:
                        self.report_views.pop(next(iter(self.report_views)))
                    self.report_views[id_] = (signature, view)
            else:
                view = cached[1]
            data['report_view'] = copy.deepcopy(view)
        for artifact in data['artifacts']:
            artifact['url'] = f'/api/v1/jobs/{id_}/artifacts/{quote(artifact["name"])}'
        return data

    def artifact(self, id_, name):
        from saved_reports import artifact_names
        if Path(name).name != name or name not in artifact_names(self, id_):
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
        self.send_header('Cache-Control', (headers or {}).get('Cache-Control', 'no-store'))
        self.send_header('X-Content-Type-Options', 'nosniff')
        frame_policy = "self" if re.fullmatch(r"/api/v1/jobs/[a-f0-9]{32}/visualizations", urlsplit(self.path).path) else "none"
        self.send_header('Content-Security-Policy', f"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors '{frame_policy}'; base-uri 'none'")
        for name, value in (headers or {}).items():
            if name.lower() != 'cache-control': self.send_header(name, value)
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
        except LimitExceeded as exc:
            self.close_connection = True
            self.json(exc.payload(), 413)
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
        from package_review_api import dispatch as package_review_dispatch
        if package_review_dispatch(self, path): return
        from workflow_api import dispatch as workflow_dispatch
        if workflow_dispatch(self, path): return
        from visualization_page import dispatch_visualizations
        if dispatch_visualizations(self, path):
            return
        if path == '/api/v1/data':
            from data_library import library
            return self.json(library(self.store))
        overview_match = re.fullmatch(r'/api/v1/packages/([a-zA-Z0-9_-]+)/overview(?:/(report))?', path)
        if overview_match:
            from dataset_overview import build_overview, render_overview
            package_id, action = overview_match.groups()
            query = parse_qs(urlsplit(self.path).query)
            if set(query) - {'job', 'lang', 'download'} or any(len(v) != 1 for v in query.values()):
                raise ValueError('汇总参数无效。')
            job_id = query.get('job', [None])[0]
            if job_id and not re.fullmatch('[a-f0-9]{32}', job_id): raise ValueError('任务标识无效。')
            data = build_overview(self.store, package_id, job_id)
            if not action: return self.json(data)
            language = query.get('lang', ['zh-CN'])[0]
            headers = {'Content-Disposition': f'attachment; filename="dataset-{package_id}-summary.html"'} if query.get('download') == ['1'] else None
            return self.send_bytes(render_overview(data, language).encode(), 'text/html; charset=utf-8', headers=headers)
        records_match = re.fullmatch(r'/api/v1/packages/([a-zA-Z0-9_-]+)/records', path)
        if records_match: return self.json(self.store.package_records(records_match.group(1)))
        if path == '/api/v1/packages':
            directory = self.store.packages.catalog()
            directory['packages'] = [p for p in directory['packages'] if p.get('category') == 'example' or self.store.packages.packages.get(p['id'], {}).get('library_origin') in {'user_upload', 'user_registered'}]
            return self.json(directory)
        package_match = re.fullmatch(r'/api/v1/package-jobs/([a-f0-9]{32})(?:/(result|report|download|expectations))?', path)
        if package_match:
            identifier, action = package_match.groups()
            if not action: return self.json(self.store.packages.get(identifier))
            if action in {'result', 'expectations'}:
                return self.send_bytes(self.store.packages.artifact(identifier, action + '.json').read_bytes())
            language = parse_qs(urlsplit(self.path).query).get('lang', ['zh-CN'])[0]
            target = self.store.packages.artifact(identifier, 'report.en.html' if language == 'en' else 'report.html')
            if action == 'download':
                return self.send_bytes(target.read_bytes(), 'text/html; charset=utf-8', headers={'Content-Disposition': 'attachment; filename="dataset-qc-report.html"'})
            back = f'/datasets?job={identifier}' + ('&lang=en' if language == 'en' else '')
            nav = f'<nav style="padding:12px 24px"><a href="{back}">← {"Dataset workbench" if language == "en" else "返回数据集检查"}</a></nav>'
            return self.send_bytes(insert_report_navigation(target.read_text(), nav).encode(), 'text/html; charset=utf-8')
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
                inputs = [public_input(i) for i in self.store.inputs.values() if i.get('modality', 'scalp_eeg') == modality and i.get('library_origin') in {'user_upload', 'user_registered'}]
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
                                                          'max_upload_bytes': self.store.intakes.limits.max_file_bytes,
                                                          'max_record_bytes': self.store.intakes.limits.max_record_bytes,
                                                          'intake_limit_version': self.store.intakes.limits.version, 'local_only': True},
                                               'admission_policy': self.store.admission_policy.describe() if self.store.admission_policy else None,
                                               'recommendation': 'explicit_rules_with_reasons'}})
        if path == '/api/v1/intakes':
            return self.json({'intakes': [public_intake(i) for i in self.store.intakes.pending() if i.get('library_origin') in {'user_upload', 'user_registered'}]})
        if path == '/api/v1/inputs':
            if urlsplit(self.path).query:
                raise ValueError('记录列表统一展示全部已登记输入，不按执行目录过滤。')
            with self.store.lock:
                records = [public_input(item) for item in self.store.inputs.values() if item.get('library_origin') in {'user_upload', 'user_registered'}]
            return self.json({'inputs': records})
        match = re.fullmatch(r'/api/v1/intakes/([a-f0-9]{32})', path)
        if match:
            return self.json(public_intake(self.store.intake_status(match.group(1))))
        if path == '/api/v1/jobs':
            with self.store.lock:
                jobs = sorted(copy.deepcopy([j for j in self.store.jobs.values() if self.store.inputs.get(j['input_id'], {}).get('library_origin') in {'user_upload', 'user_registered'}]), key=lambda j: j['created_at'], reverse=True)
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
        export_match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/(report.pdf|report-evidence.png)', path)
        if export_match:
            identifier, export_kind = export_match.groups()
            if self.store.job(identifier)['status'] != 'completed':
                raise ValueError('任务尚未完成，没有可用的最终报告。')
            from project_score_cache import load
            from saved_reports import frozen_view
            published = load(self.store, identifier)
            view = published.get('report_view') if published else frozen_view(self.store, identifier)
            if not view:
                raise ValueError('当前 PDF 导出支持头皮 EEG 报告。')
            from ephys_qc.report_export import evidence_figure, pdf_bytes
            try:
                figure, figure_notes = evidence_figure(view, self.store.workspace(identifier))
            except (OSError, KeyError, ValueError, RuntimeError, ImportError):
                figure, figure_notes = None, ['对应波形暂不可用；原始检测结果仍保留。']
            if export_kind == 'report-evidence.png':
                if not figure:
                    # Return an accessible text image instead of a broken-image icon.
                    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="90"><text x="24" y="48" font-size="18" fill="#687b92">候选波形暂不可用，请检查原始文件。</text></svg>'
                    return self.send_bytes(svg.encode('utf-8'), 'image/svg+xml')
                return self.send_bytes(figure, 'image/png')
            try:
                data = pdf_bytes(view, figure, figure_notes, identifier)
            except ImportError:
                return self.json({'error': 'PDF 组件未安装。请在服务环境安装 ephys-qc-workbench[reports]。'}, 503)
            return self.send_bytes(data, 'application/pdf', headers={
                'Content-Disposition': f'attachment; filename="DBCI-QC-{identifier[:8]}.pdf"'})
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
        match = re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})(?:/(result|summary|report|log|artifacts/(.+)))?', path)
        if match:
            id_, action, filename = match.groups()
            job = self.store.job(id_)
            if action is None:
                return self.json(job)
            if action == 'result':
                return self.json(self.store.result(id_, compact=parse_qs(urlsplit(self.path).query).get('view') == ['summary']))
            if action == 'summary':
                return self.json(self.store.result(id_, compact=True))
            if action == 'log':
                log = self.store.root / 'jobs' / id_ / 'run.log'
                return self.send_bytes(log.read_bytes()[-100_000:] if log.exists() else b'', 'text/plain; charset=utf-8')
            if action == 'report':
                from saved_reports import served_report
                language = parse_qs(urlsplit(self.path).query).get('lang', ['zh-CN'])[0]
                report = served_report(self.store, id_, language)
                return self.send_bytes(report.encode('utf-8'), 'text/html; charset=utf-8')
            if filename:
                target = self.store.artifact(id_, filename)
                mime = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
                if target.suffix in {'.html', '.json', '.txt', '.csv', '.tsv'}:
                    mime += '; charset=utf-8'
                return self.send_bytes(target.read_bytes(), mime)
        if path.startswith('/examples/'):
            from example_cache import asset
            target = asset(self.store, path)
            return self.send_bytes(target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream', headers={'Cache-Control': 'public, max-age=31536000, immutable'})
        static = {'/': 'index.html', '/app.js': 'app.js', '/i18n.js': 'i18n.js', '/styles.css': 'styles.css', '/ui-tokens.css': 'ui-tokens.css', '/workbench-ui.css': 'workbench-ui.css', '/favicon.svg': 'favicon.svg',
                  '/data-library.js': 'data-library.js', '/dataset-report.css': 'dataset-report.css', '/dataset-report.js': 'dataset-report.js', '/visualizations.js': 'visualizations.js', '/datasets': 'datasets.html', '/datasets.js': 'datasets.js', '/datasets.css': 'datasets.css',
                  '/dataset-review.js': 'dataset-review.js', '/dataset-review.css': 'dataset-review.css'}
        if path in static:
            target = ROOT / 'web' / static[path]
            if path == '/':
                from example_cache import homepage
                return self.send_bytes(homepage(self.store, target.read_text()).encode('utf-8'), 'text/html; charset=utf-8')
            return self.send_bytes(target.read_bytes(), (mimetypes.guess_type(target.name)[0] or 'text/plain') + '; charset=utf-8')
        raise KeyError(path)

    def post(self, path):
        from package_review_api import dispatch as package_review_dispatch
        if package_review_dispatch(self, path): return
        from workflow_api import dispatch as workflow_dispatch
        if workflow_dispatch(self, path): return
        if path == '/api/v1/package-record-intakes':
            return self.json(public_intake(self.store.open_package_record(self.body())), 201)
        if path == '/api/v1/package-jobs':
            return self.json(self.store.packages.submit(self.body()), 202)
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
            return self.json(public_intake(self.store.select_intake_stream(match.group(1), self.body())))
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
    parser.add_argument('--admission-policy', choices=['local', *POLICIES],
                        help='Validate cloud intake limits locally; does not enable cloud hosting or authentication')
    args = parser.parse_args()
    settings = read_json(args.config)
    if args.admission_policy:
        settings['admission_policy'] = args.admission_policy
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
