"""Persistent batch orchestration over the existing, frozen single-record API."""
import copy
import hashlib
import json
import queue
import threading
import uuid
from datetime import datetime, timezone

TERMINAL = {'completed', 'failed', 'cancelled', 'interrupted'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def latest_inputs(store, directory):
    found = {}
    with store.lock:
        for item in store.inputs.values():
            context = item.get('dataset_context') or {}
            if context.get('package_id') != directory['package_id'] or context.get('manifest_hash') != directory['manifest_hash']:
                continue
            key = context.get('record_id')
            old = found.get(key)
            if old is None or item.get('record_revision', 1) > old.get('record_revision', 1):
                found[key] = copy.deepcopy(item)
    return found


class BatchJobs:
    def __init__(self, store, *, start_worker=True):
        self.store = store
        self.root = store.root / 'batches'
        self.root.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.queue = queue.Queue()
        self.items = {}
        for path in self.root.glob('*.json'):
            item = json.loads(path.read_text())
            if item['status'] in {'queued', 'running', 'cancelling'}:
                item.update(status='interrupted', ended_at=stamp())
                self._save(item)
            self.items[item['id']] = item
        if start_worker:
            threading.Thread(target=self._loop, daemon=True).start()

    def _save(self, item):
        path = self.root / (item['id'] + '.json')
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(item, ensure_ascii=False, indent=2, allow_nan=False))
        temp.replace(path)

    def preview(self, body):
        if not isinstance(body, dict) or set(body) - {'package_id', 'manifest_hash', 'record_ids', 'scope'}:
            raise ValueError('批量预览仅接受数据集、记录和检查范围。')
        ids = body.get('record_ids')
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('请选择 1–100 份不同记录。')
        scope = body.get('scope', 'recording')
        if scope not in {'recording', 'window'}:
            raise ValueError('检查范围无效。')
        directory = self.store.packages.records(body['package_id'])
        directory['package_id'] = body['package_id']
        if directory['manifest_hash'] != body.get('manifest_hash'):
            raise ValueError('数据集清单已改变，请刷新后重新预览。')
        records = {r['id']: r for r in directory['records']}
        if set(ids) - records.keys():
            raise ValueError('记录不在当前数据集中。')
        inputs = latest_inputs(self.store, directory)
        rows = []
        for rid in ids:
            row = {'record_id': rid, 'label': records[rid].get('path', rid), 'status': 'unavailable'}
            item = inputs.get(rid)
            try:
                if not item:
                    raise ValueError('请先打开记录，确认模态和通道。')
                config = copy.deepcopy(item.get('default_config') or {})
                config['scope'] = scope
                rec = self.store.recommend_request({'input_id': item['id'], 'qc_config': config})
                if not rec['can_apply']:
                    raise ValueError(rec.get('reason') or rec['summary'])
                request = {'input_id': item['id'], 'selected_modules': rec['selected_modules'], 'qc_config': rec['qc_config']}
                _, plan = self.store.plan_request(request)
                request['plan_id'] = plan['plan_id']
                row.update(status='ready', request=request, input_revision=item.get('record_revision', 1),
                           methods=[{'id': m['id'], 'name': m['name'], 'status': m['status'], 'reason': m['reason']} for m in plan.get('method_applicability', []) if m.get('selected')])
            except (ValueError, KeyError) as exc:
                row['reason'] = str(exc)
            rows.append(row)
        item = {'id': uuid.uuid4().hex, 'version': 'signal-batch/1', 'status': 'preview', 'created_at': stamp(),
                'package_id': body['package_id'], 'manifest_hash': directory['manifest_hash'], 'scope': scope, 'records': rows}
        item['preview_hash'] = digest(rows)
        with self.lock:
            if hasattr(self.store, 'library_state'): self.store.library_state.assert_package_active(item['package_id'])
            self.items[item['id']] = item
            self._save(item)
        return self.get(item['id'])

    def submit(self, body):
        if not isinstance(body, dict) or set(body) != {'preview_id', 'preview_hash', 'confirmed'} or body['confirmed'] is not True:
            raise ValueError('请先预览并确认批量检查范围。')
        with self.lock:
            item = self.items[body['preview_id']]
            if hasattr(self.store, 'library_state'): self.store.library_state.assert_package_active(item['package_id'])
            if item['preview_hash'] != body['preview_hash']:
                raise ValueError('预览内容不一致。')
            if item['status'] != 'preview':
                return self.get(item['id'])  # Same preview never creates duplicate children.
            directory = self.store.packages.records(item['package_id'])
            directory['package_id'] = item['package_id']
            if directory['manifest_hash'] != item['manifest_hash']:
                raise ValueError('清单已改变，请重新预览。')
            inputs = latest_inputs(self.store, directory)
            ready = [r for r in item['records'] if r['status'] == 'ready']
            if not ready:
                raise ValueError('没有可运行的记录，请先完成信息确认。')
            for row in ready:
                if inputs.get(row['record_id'], {}).get('id') != row['request']['input_id']:
                    raise ValueError('记录信息已修改，请重新预览。')
                _, plan = self.store.plan_request(row['request'])
                if plan['plan_id'] != row['request']['plan_id']:
                    raise ValueError('检查规则已改变，请重新预览。')
            item.update(status='queued', submitted_at=stamp())
            self._save(item)
            self.queue.put(item['id'])
            return self.get(item['id'])

    def get(self, identifier):
        with self.lock:
            result = copy.deepcopy(self.items[identifier])
        for row in result['records']:
            if row.get('job_id'):
                job = self.store.job(row['job_id'])
                row['status'] = job['status']
                if job['status'] == 'completed':
                    row['report_url'] = '/api/v1/jobs/' + job['id'] + '/report'
        result['finished'] = sum(r['status'] in TERMINAL for r in result['records'])
        result['runnable'] = sum(r['status'] != 'unavailable' for r in result['records'])
        return result

    def catalog(self, package_id=None):
        with self.lock:
            ids = [i['id'] for i in self.items.values() if i['status'] != 'preview' and (not package_id or i['package_id'] == package_id)]
        return [self.get(i) for i in reversed(ids)]

    def cancel(self, identifier):
        with self.lock:
            item = self.items[identifier]
            if item['status'] in TERMINAL:
                return self.get(identifier)
            was_preview = item['status'] == 'preview'
            item.update(status='cancelled' if was_preview else 'cancelling', cancel_requested=True)
            for row in item['records']:
                if row.get('job_id'):
                    self.store.cancel(row['job_id'])
                elif row['status'] == 'ready':
                    row['status'] = 'cancelled'
            self._save(item)
        return self.get(identifier)

    def _run(self, identifier):
        with self.lock:
            item = self.items[identifier]
            item['status'] = 'running' if not item.get('cancel_requested') else 'cancelling'
            self._save(item)
        for row in item['records']:
            if row['status'] != 'ready':
                continue
            try:
                while True:
                    with self.lock:
                        if item.get('cancel_requested'):
                            break
                        # Avoid a check/submit race with other interactive submissions.
                        with self.store.lock:
                            busy = sum(j['status'] not in TERMINAL for j in self.store.jobs.values()) >= 5
                            if not busy:
                                child = self.store.submit(row['request'], batch_id=identifier)
                                row.update(job_id=child['id'], status=child['status'])
                                self._save(item)
                                break
                    threading.Event().wait(.5)
                while row.get('job_id'):
                    child = self.store.job(row['job_id'])
                    if child['status'] in TERMINAL:
                        with self.lock:
                            row['status'] = child['status']
                            self._save(item)
                        break
                    threading.Event().wait(.5)
            except (ValueError, OSError, KeyError) as exc:
                with self.lock:
                    row.update(status='failed', reason=str(exc))
                    self._save(item)
        with self.lock:
            item.update(status='cancelled' if item.get('cancel_requested') else 'completed', ended_at=stamp())
            item['failed_records'] = sum(r['status'] == 'failed' for r in item['records'])
            self._save(item)

    def _loop(self):
        while True:
            identifier = self.queue.get()
            try:
                self._run(identifier)
            except Exception as exc:
                with self.lock:
                    item = self.items[identifier]
                    item.update(status='failed', error=type(exc).__name__, ended_at=stamp())
                    self._save(item)
            finally:
                self.queue.task_done()
