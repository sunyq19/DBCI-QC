"""Private, expiring upload workspace; public catalog never learns its records.

Enabled by data_policy=public-only/1. Files are temporary disk work products,
not zero-copy/browser-only processing. A random HttpOnly cookie scopes reads.
"""
import copy
import fcntl
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path
import re
import secrets
import shutil
import threading
import time
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

    @contextmanager
    def request(self, handler, path):
        token = None
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
            if token:
                session = self.sessions[token]
                if session['created'] + MAX_SECONDS <= self.clock():
                    raise PermissionError('临时检查已到期，请重新上传。')
                session['requests'] += 1
                session['touched'] = self.clock()
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
        with self.lock:
            token = self._session(handler)
            return {'policy': POLICY, 'active': bool(token), 'result_minutes': 60,
                    'idle_minutes': 30, 'maximum_hours': 6}

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
                with self.store.lock:
                    jobs = [j for j in self.store.jobs.values() if self._owner('jobs', j['id']) == token]
                    active = [j for j in jobs if j['status'] in ACTIVE]
                    # Presentation generation may follow completion; do not delete its workspace mid-write.
                    busy = any(j['id'] in self.store.processes for j in jobs)
                if active or busy:
                    session.pop('completed_at', None)
                elif jobs:
                    session.setdefault('completed_at', now)
                deadline = session.get('completed_at', session['touched']) + (RESULT_SECONDS if jobs else IDLE_SECONDS)
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
                    records = [i for i in self.store.inputs.values() if self._owner('inputs', i['id']) == token]
                    for job in jobs:
                        directory = self.store.root / 'jobs' / job['id']
                        if directory.exists():
                            shutil.rmtree(directory)
                        self.store.jobs.pop(job['id'], None)
                        self.store.report_views.pop(job['id'], None)
                    for record in records:
                        if record['id'].startswith('revision-'):
                            directory = self.store.revisions.root / record['id']
                            if directory.exists(): shutil.rmtree(directory)
                        self.store.inputs.pop(record['id'], None)
                    for identifier in session['intakes']:
                        directory = self.store.intakes._directory(identifier)
                        if directory.exists():
                            shutil.rmtree(directory)
                        self.owners.pop(identifier, None)
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
