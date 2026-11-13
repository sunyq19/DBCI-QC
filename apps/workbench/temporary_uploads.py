"""Private, expiring upload workspace; public catalog never learns its records.

Enabled by data_policy=public-only/1. Files are temporary disk work products,
not zero-copy/browser-only processing. A random HttpOnly cookie scopes reads.
"""
import copy
from datetime import datetime, timezone
import fcntl
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
from types import SimpleNamespace
from urllib.parse import urlsplit, parse_qs

POLICY = 'public-only/1'
COOKIE = 'dbci_temporary'
IDLE_SECONDS = 30 * 60
RESULT_SECONDS = 60 * 60
MAX_SECONDS = 6 * 60 * 60
ACTIVE = {'queued', 'running', 'cancelling'}


def enabled(settings):
    return settings.get('data_policy') == POLICY


def source(value):
    if not isinstance(value, dict):
        return None
    if isinstance(value.get('sources'), list) and value['sources']:
        rows = [source(row) for row in value['sources']]
        if not all(rows): return None
        return {'name': ' / '.join(row['name'] for row in rows), 'url': rows[0]['url'],
                'version': '', 'license': ' / '.join(row['license'] for row in rows), 'sources': rows}
    result = {key: str(value.get(key, '')).strip() for key in ('name', 'url', 'version', 'license')}
    result['name'] = result['name'] or str(value.get('dataset') or value.get('dataset_id') or '')
    result['url'] = result['url'] or str(value.get('dataset_url') or '')
    result['version'] = result['version'] or str(value.get('snapshot') or value.get('version_doi') or '')
    url = urlsplit(result['url'])
    if (not result['name'] or not result['license'] or url.scheme not in {'http', 'https'}
            or not url.hostname or url.username or url.password):
        return None
    return result


def public_source(settings, item):
    declared = settings.get('public_records', {})
    context = item.get('dataset_context') or {}
    return source(declared.get(item['id']) or declared.get(item.get('record_family')) or
                  settings.get('public_packages', {}).get(context.get('package_id')))


def public_record(settings, item):
    if not enabled(settings):
        return item
    provenance = public_source(settings, item)
    if not provenance:
        return None
    item = copy.deepcopy(item)
    item.update(public_source=provenance, library_origin='user_registered')
    item['provenance'] = {**item.get('provenance', {}), **provenance}
    return item


def public_intake(settings, item):
    return not enabled(settings) or bool(public_source(settings, dict(item, id='local-' + item['id'])))


class TemporaryUploads:
    """One isolated worker queue, bounded sessions, no account database."""
    def __init__(self, public_store, factory, *, clock=time.time):
        self.public = public_store
        self.clock = clock
        self.lock = threading.RLock()
        self.sessions = {}
        self.owners = {}
        self.store = None
        self.factory = factory
        self.lease = (public_store.root / '.temporary.lock').open('a')
        fcntl.flock(self.lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.root = public_store.root / '.temporary'
        if self.root.is_symlink():
            raise ValueError('Temporary upload root must not be a symlink')
        if self.root.exists():
            if not (self.root / '.owned-by-dbci').is_file():
                raise ValueError('Temporary directory has no ownership marker; inspect it before enabling this policy')
            shutil.rmtree(self.root)
        self.root.mkdir(mode=0o700)
        (self.root / '.owned-by-dbci').touch(mode=0o600)
        self.closed = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _worker(self):
        if self.store is None:
            settings = copy.deepcopy(self.public.settings)
            settings.update(data_dir=str(self.root / 'runtime'), inputs=[], packages=[],
                            demo_examples=[], demo_comparisons=[], validation_library_ids=[],
                            data_policy=None, temporary_workspace=True)
            self.store = self.factory(settings)
        return self.store

    def token(self, handler):
        cookie = SimpleCookie()
        try:
            cookie.load(handler.headers.get('Cookie', ''))
            token = cookie[COOKIE].value if COOKIE in cookie else ''
        except Exception:
            token = ''
        return token if re.fullmatch('[a-f0-9]{64}', token) else ''

    def cookie(self, token, *, secure=False):
        return f'{COOKIE}={token}; Path=/; HttpOnly; SameSite=Strict' + ('; Secure' if secure else '') + ('; Max-Age=0' if not token else '')

    def _session(self, handler, *, create=False):
        token = self.token(handler)
        if token in self.sessions and not self.sessions[token].get('closing'):
            return token
        if not create:
            return None
        if len(self.sessions) >= 16:
            raise ValueError('临时检查人数已满，请稍后重试。')
        token = secrets.token_hex(32)
        now = self.clock()
        self.sessions[token] = {'created': now, 'touched': now, 'requests': 0, 'intakes': set(),
                                'workspace': secrets.token_hex(16)}
        secure = self.public.settings.get('deployment', {}).get('public_origin', '').startswith('https:')
        handler.temporary_cookie = self.cookie(token, secure=secure)
        handler.temporary_token = token
        return token

    def _owner(self, kind, identifier):
        if kind == 'intakes':
            return self.owners.get(identifier)
        if self.store is None:
            return None
        if kind == 'jobs':
            identifier = self.store.jobs.get(identifier, {}).get('input_id')
        item = self.store.inputs.get(identifier, {})
        family = item.get('record_family', item.get('id', ''))
        return self.owners.get(family.removeprefix('local-'))

    def _intake_id(self, identifier):
        item = self.store.inputs.get(identifier, {})
        return item.get('record_family', item.get('id', '')).removeprefix('local-')

    @contextmanager
    def request(self, handler, path):
        token = None
        self.sweep()
        with self.lock:
            body = None
            target = None
            if handler.command == 'POST' and path == '/api/v1/intakes':
                token = self._session(handler, create=True)
            else:
                match = re.match(r'^/api/v1/(intakes|inputs|jobs)/([A-Za-z0-9_-]+)(?:/|$)', path)
                if match:
                    target = self._owner(*match.groups())
                elif handler.command == 'POST' and path in {'/api/v1/recommend', '/api/v1/plan', '/api/v1/jobs'}:
                    body = handler.body()
                    target = self._owner('inputs', body.get('input_id')) if isinstance(body, dict) else None
                elif path in {'/comparisons', '/api/v1/comparisons'}:
                    ids = parse_qs(urlsplit(handler.path).query).get('jobs', [''])[0].split(',')
                    owners = {self._owner('jobs', jid) for jid in ids}
                    if any(owners):
                        if len(owners) != 1:
                            raise PermissionError('不能混合不同临时检查的报告。')
                        target = next(iter(owners))
                if target:
                    token = self._session(handler)
                    if target != token:
                        raise PermissionError('这份临时检查仅在上传它的浏览器中可查看。')
                    session = self.sessions[token]
                    if match:
                        kind, identifier = match.groups()
                        intake_id = identifier if kind == 'intakes' else self._intake_id(
                            self.store.jobs.get(identifier, {}).get('input_id') if kind == 'jobs' else identifier)
                        if (intake_id in session.get('deleting_intakes', set()) or
                                (kind == 'jobs' and identifier in session.get('deleting_jobs', set()))):
                            raise PermissionError('这份临时数据正在清理。')
                    elif body and self._intake_id(body.get('input_id')) in session.get('deleting_intakes', set()):
                        raise PermissionError('这份临时数据正在清理。')
            if token:
                session = self.sessions[token]
                if session['created'] + MAX_SECONDS <= self.clock():
                    raise PermissionError('临时检查已到期，请重新上传。')
                session['requests'] += 1
                if handler.command == 'POST': session['touched'] = self.clock()
                handler.temporary_token = token
                handler._request_store = self._worker()
        try:
            yield
        finally:
            if token:
                with self.lock:
                    if token in self.sessions:
                        self.sessions[token]['requests'] -= 1
                handler._request_store = None

    def uploaded(self, handler, intake):
        token = getattr(handler, 'temporary_token', None)
        if not token:
            return
        with self.lock:
            self.sessions[token]['intakes'].add(intake['id'])
            self.sessions[token].pop('completed_at', None)
            self.owners[intake['id']] = token
        # Persisted only inside the temporary workspace, with the same expiry.
        from intake import _save
        intake['retention'] = {'policy': POLICY, 'state': 'temporary', 'result_minutes': 60,
                               'workspace': self.sessions[token]['workspace']}
        _save(self.store.intakes._directory(intake['id']) / 'intake.json', intake)

    def inputs(self, handler):
        with self.lock:
            token = self._session(handler)
            if not token or self.store is None:
                return []
            with self.store.lock:
                return [copy.deepcopy(i) for i in self.store.inputs.values() if self._owner('inputs', i['id']) == token]

    def pending(self, handler):
        with self.lock:
            token = self._session(handler)
            if not token or self.store is None:
                return []
            return [i for i in self.store.intakes.pending() if self.owners.get(i['id']) == token]

    def status(self, handler):
        self.sweep()
        with self.lock:
            token = self._session(handler)
            return {'policy': POLICY, 'active': bool(token), 'result_minutes': 60,
                    'idle_minutes': 30, 'maximum_hours': 6,
                    'retention': self._timing(token) if token else None}

    def _timing(self, token):
        """The list, notice and sweeper share one server-owned deadline."""
        session = self.sessions[token]
        with self.store.lock:
            jobs = [j for j in self.store.jobs.values() if self._owner('jobs', j['id']) == token]
            busy = any(j['status'] in ACTIVE or j['id'] in self.store.processes for j in jobs)
        if busy:
            session.pop('completed_at', None)
        elif jobs:
            session.setdefault('completed_at', self.clock())
        hard = session['created'] + MAX_SECONDS
        has_results = 'completed_at' in session
        deadline = hard if busy else min(hard, session.get('completed_at', session['touched']) +
                                         (RESULT_SECONDS if has_results else IDLE_SECONDS))
        stamp = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
        return {'state': 'temporary', 'phase': 'running' if busy else 'results' if has_results else 'idle',
                'expires_at': stamp(deadline), 'server_now': stamp(self.clock()),
                'result_minutes': 60, 'idle_minutes': 30, 'maximum_hours': 6}

    def library(self, handler):
        """Build the directory only from this browser's records, before deduplication."""
        self.sweep()
        with self.lock:
            token = self._session(handler)
            if not token or self.store is None:
                return []
            session = self.sessions[token]
            with self.store.lock:
                inputs = {k: copy.deepcopy(v) for k, v in self.store.inputs.items()
                          if self._owner('inputs', k) == token and
                          self._intake_id(k) not in session.get('deleting_intakes', set())}
                jobs = {k: copy.deepcopy(v) for k, v in self.store.jobs.items()
                        if v['input_id'] in inputs and k not in session.get('deleting_jobs', set())}
                pending = [i for i in self.store.intakes.pending() if self.owners.get(i['id']) == token
                           and i['id'] not in session.get('deleting_intakes', set())]
                scope = SimpleNamespace(**{k: v for k, v in vars(self.store).items() if k != 'library_state'})
                scope.inputs, scope.jobs = inputs, jobs
                scope.intakes = SimpleNamespace(pending=lambda: pending)
                from data_library import library
                rows = library(scope)['items']
            timing = self._timing(token)
            for row in rows:
                row.update(temporary=True, retention=timing, source=None)
                for report in row.get('recent_reports', []): report['temporary'] = True
                for group in row.get('workflow_groups', []):
                    group['latest']['temporary'] = True
                    for report in group['runs']: report['temporary'] = True
            return rows

    def delete(self, handler, body):
        """Delete one owned row or report; no public or cross-browser target is accepted."""
        if not isinstance(body, dict) or body.get('confirmed') is not True:
            raise ValueError('请确认删除。')
        identifier = body.get('id', '')
        if not isinstance(identifier, str): raise ValueError('无效的数据标识。')
        self.sweep()
        with self.lock:
            token = self._session(handler)
            if not token or self.store is None: raise PermissionError('只能删除本浏览器的临时上传。')
            session = self.sessions[token]
            if identifier.startswith('report:'):
                jid = identifier.removeprefix('report:')
                if self._owner('jobs', jid) != token: raise PermissionError('只能删除本浏览器的临时报告。')
                session.setdefault('deleting_jobs', set()).add(jid)
            else:
                row = next((r for r in self.library(handler) if r['id'] == identifier), None)
                if not row: raise PermissionError('只能删除本浏览器的临时上传。')
                if identifier.startswith('intake:'):
                    intake_ids = {identifier.removeprefix('intake:')}
                else:
                    from library_identity import data_identity
                    selected = self.store.inputs[identifier.removeprefix('record:')]
                    intake_ids = {self._intake_id(k) for k, v in self.store.inputs.items()
                                  if self._owner('inputs', k) == token and data_identity(v) == data_identity(selected)}
                session.setdefault('deleting_intakes', set()).update(intake_ids)
            intake_ids = set(session.get('deleting_intakes', set()))
            input_ids = [k for k in self.store.inputs if self._owner('inputs', k) == token and self._intake_id(k) in intake_ids]
            job_ids = [k for k, v in self.store.jobs.items() if self._owner('jobs', k) == token and
                       (k in session.get('deleting_jobs', set()) or v['input_id'] in input_ids)]
        self.sweep()
        with self.lock:
            pending = token in self.sessions and bool(session.get('deleting_intakes') or session.get('deleting_jobs'))
        return {'status': 'clearing' if pending else 'cleared', 'cleanup_pending': pending, 'id': identifier,
                'input_ids': input_ids, 'job_ids': job_ids, 'intake_ids': sorted(intake_ids)}

    def _delete_selected(self, token, session):
        intake_ids = session.get('deleting_intakes', set())
        job_ids = session.get('deleting_jobs', set())
        if not intake_ids and not job_ids: return
        with self.store.lock:
            jobs = [j for j in self.store.jobs.values() if self._owner('jobs', j['id']) == token and
                    (j['id'] in job_ids or self._intake_id(j['input_id']) in intake_ids)]
            active = [j for j in jobs if j['status'] in ACTIVE]
            for job in active: self.store.cancel(job['id'])
            if active or any(j['id'] in self.store.processes for j in jobs): return
            self._remove(jobs, intake_ids)
            session['intakes'].difference_update(intake_ids)
            session.pop('deleting_intakes', None)
            session.pop('deleting_jobs', None)

    def _remove(self, jobs, intake_ids):
        """Only owned runtime paths; keep ownership until every deletion succeeds."""
        for job in jobs:
            directory = self.store.root / 'jobs' / job['id']
            if directory.exists(): shutil.rmtree(directory)
            self.store.jobs.pop(job['id'], None)
            self.store.report_views.pop(job['id'], None)
        for record in list(self.store.inputs.values()):
            if self._intake_id(record['id']) not in intake_ids: continue
            if record['id'].startswith('revision-'):
                directory = self.store.revisions.root / record['id']
                if directory.exists(): shutil.rmtree(directory)
            self.store.inputs.pop(record['id'], None)
        for identifier in list(intake_ids):
            directory = self.store.intakes._directory(identifier)
            if directory.exists(): shutil.rmtree(directory)
            self.owners.pop(identifier, None)

    def finish(self, handler):
        with self.lock:
            token = self._session(handler)
            if token:
                self.sessions[token]['closing'] = True
            handler.temporary_cookie = self.cookie('')
        self.sweep()
        return {'status': 'clearing' if token in self.sessions else 'cleared'}

    def sweep(self):
        with self.lock:
            if self.store is None:
                return
            now = self.clock()
            for token, session in list(self.sessions.items()):
                if session['requests']:
                    continue
                self._delete_selected(token, session)
                if not session['intakes']:
                    self.sessions.pop(token)
                    continue
                with self.store.lock:
                    jobs = [j for j in self.store.jobs.values() if self._owner('jobs', j['id']) == token]
                    active = [j for j in jobs if j['status'] in ACTIVE]
                    # Presentation generation may follow completion; do not delete its workspace mid-write.
                    busy = any(j['id'] in self.store.processes for j in jobs)
                timing = self._timing(token)
                deadline = datetime.fromisoformat(timing['expires_at']).timestamp()
                hard_expired = session['created'] + MAX_SECONDS <= now
                due = session.get('closing') or hard_expired or (not active and not busy and deadline <= now)
                if not due:
                    continue
                session['closing'] = True
                for job in active:
                    self.store.cancel(job['id'])
                if active or busy:
                    continue
                with self.store.lock:
                    self._remove(jobs, session['intakes'])
                    self.sessions.pop(token)

    def _loop(self):
        while not self.closed.wait(2):
            try:
                self.sweep()
            except Exception:
                # No filenames, tokens, patient headers or algorithm tracebacks in persistent service logs.
                import logging
                logging.error('Temporary cleanup failed; will retry')

    def shutdown(self):
        self.closed.set()
        with self.lock:
            for session in self.sessions.values():
                session['closing'] = True
        for _ in range(100):
            self.sweep()
            if not self.sessions:
                break
            time.sleep(.1)
        # Remaining owned work is removed at next startup if a worker cannot stop in time.
        self.lease.close()
