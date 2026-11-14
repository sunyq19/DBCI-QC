import io
import json
from http.cookiejar import CookieJar
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from urllib.request import build_opener, ProxyHandler, HTTPCookieProcessor, Request
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'src'), str(ROOT/'apps/workbench'), str(ROOT/'tests')]
from server import Store, Handler
from temporary_uploads import TemporaryUploads, POLICY, IDLE_SECONDS, RESULT_SECONDS, MAX_SECONDS
from test_intake import recording, confirmation


@pytest.fixture
def service(tmp_path):
    settings = {'python': sys.executable, 'data_dir': str(tmp_path), 'inputs': [], 'profiles': [], 'data_policy': POLICY}
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.store = Store(settings)
    clock = [1000.0]
    server.temporary = TemporaryUploads(server.store, Store, clock=lambda: clock[0])
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    clients = [build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar())) for _ in range(2)]
    def call(path, data=None, client=0, upload=False):
        headers = {'Content-Type': 'application/octet-stream', 'X-Filename': 'private.edf'} if upload else {'Content-Type': 'application/json'}
        body = data if upload else json.dumps(data).encode() if data is not None else None
        response = clients[client].open(Request(f'http://127.0.0.1:{server.server_port}'+path, data=body, headers=headers))
        return json.load(response)
    yield server, call, clock
    server.shutdown(); server.temporary.shutdown(); server.server_close(); thread.join(2)


def upload(call, client=0):
    intake = call('/api/v1/intakes', recording(), client, True)
    record = call('/api/v1/intakes/'+intake['id']+'/confirm', confirmation(), client)['input']
    return intake, record


def test_upload_private_even_if_bytes_match_other_browser(service):
    server, call, _ = service
    first, a = upload(call)
    second, b = upload(call, 1)
    assert a['retention']['state'] == 'temporary'
    mine = call('/api/v1/data')['items']
    other = call('/api/v1/data', client=1)['items']
    assert [row['id'] for row in mine] == ['record:'+a['id']]
    assert [row['id'] for row in other] == ['record:'+b['id']]
    assert mine[0]['temporary'] and mine[0]['retention']['expires_at']
    assert first['id'] not in json.dumps(other)
    assert second['id'] not in json.dumps(mine)
    assert [i['id'] for i in call('/api/v1/inputs')['inputs']] == [a['id']]
    assert [i['id'] for i in call('/api/v1/inputs', client=1)['inputs']] == [b['id']]
    assert call('/api/v1/inputs/'+a['id']+'/configuration')['input']['id'] == a['id']
    for endpoint in ['/api/v1/intakes/'+first['id'], '/api/v1/inputs/'+a['id'], '/api/v1/inputs/'+a['id']+'/waveform']:
        with pytest.raises(HTTPError) as exc: call(endpoint, client=1)
        assert exc.value.code == 403
    assert not list((server.store.root/'intakes').glob('*/intake.json'))


def test_finish_removes_intake_metadata_revisions_and_reports(service):
    server, call, _ = service
    intake, record = upload(call)
    private = server.temporary.store
    revised = private.revise_input(record['id'], {**confirmation(), 'base_revision': 1})['input']
    jobid = 'a'*32
    folder = private.root/'jobs'/jobid; folder.mkdir()
    (folder/'report.html').write_text('private report')
    (folder/'run.log').write_text('private filename')
    private.jobs[jobid] = {'id': jobid, 'input_id': record['id'], 'status': 'completed'}
    assert call('/api/v1/temporary-session/finish', {})['status'] == 'cleared'
    assert not (private.root/'intakes'/intake['id']).exists()
    assert not (private.revisions.root/revised['id']).exists()
    assert not folder.exists()
    assert not private.inputs and not private.jobs
    assert not call('/api/v1/temporary-session')['active']


def test_idle_cleanup_does_not_delete_other_session(service):
    server, call, clock = service
    a, _ = upload(call)
    clock[0] += IDLE_SECONDS - 1
    b, _ = upload(call, 1)
    clock[0] += 2; server.temporary.sweep()
    assert not (server.temporary.store.intakes.root/a['id']).exists()
    assert (server.temporary.store.intakes.root/b['id']).exists()


def test_report_expiry_is_fixed_not_extended_by_reading(service):
    server, call, clock = service
    intake, record = upload(call)
    private = server.temporary.store; jobid = 'b'*32
    (private.root/'jobs'/jobid).mkdir()
    private.jobs[jobid] = {'id':jobid, 'input_id':record['id'], 'status':'completed'}
    server.temporary.sweep()
    clock[0] += RESULT_SECONDS - 1
    call('/api/v1/inputs/'+record['id'])
    clock[0] += 2; server.temporary.sweep()
    assert not private.jobs and not private.inputs


def test_hard_expiry_cancels_queued_work_before_cleanup(service):
    server, call, clock = service
    intake, record = upload(call)
    private = server.temporary.store; jobid = 'd'*32
    directory = private.root/'jobs'/jobid; directory.mkdir()
    private.jobs[jobid] = {'id':jobid, 'input_id':record['id'], 'status':'queued', 'modules':[]}
    clock[0] += MAX_SECONDS
    server.temporary.sweep()
    assert private.jobs[jobid]['status'] == 'cancelled'
    assert directory.exists()
    with pytest.raises(HTTPError) as exc: call('/api/v1/inputs/'+record['id'])
    assert exc.value.code in {403, 404}  # Expired work may already have been physically removed.
    server.temporary.sweep()
    assert not directory.exists() and not private.inputs


def test_failed_upload_leaves_no_payload_or_public_record(service):
    server, call, _ = service
    with pytest.raises(HTTPError): call('/api/v1/intakes', b'not an EDF recording', upload=True)
    assert list(server.temporary.store.intakes.root.iterdir()) == []
    assert call('/api/v1/data')['items'] == []


def test_opt_in_public_demo_reports_do_not_restore_history_or_merge_uploads(service):
    server, call, _ = service
    public = server.store
    intake = public.intakes.receive('public.edf', len(recording()), io.BytesIO(recording()))
    identifier = 'local-'+intake['id']
    public.settings['public_records'] = {identifier: {'name':'Public fixture', 'url':'https://example.org/data', 'license':'CC0'}}
    public.confirm_intake(intake['id'], confirmation())
    for jid in ['a'*32, 'b'*32, 'c'*32]:
        folder=public.root/'jobs'/jid/'artifacts'; folder.mkdir(parents=True)
        (folder/'report.html').write_text('Saved public report')
        public.jobs[jid]={'id':jid, 'input_id':identifier, 'status':'completed', 'created_at':'2026-11-13'}
    assert call('/api/v1/data')['items'] == []
    public.settings['demo_library_reports'] = ['a'*32, 'b'*32, 'unknown']
    rows=call('/api/v1/data')['items']
    assert len(rows)==1 and rows[0]['id']=='record:'+identifier
    assert {r['job_id'] for r in rows[0]['recent_reports']} == {'a'*32, 'b'*32}
    assert rows[0]['source']['license']=='CC0' and not rows[0].get('temporary')
    # Identical bytes in an upload still belong exclusively to that browser.
    _, private=upload(call)
    mine=call('/api/v1/data')['items']; other=call('/api/v1/data',client=1)['items']
    assert {r['id'] for r in mine} == {'record:'+identifier, 'record:'+private['id']}
    assert [r['id'] for r in other] == ['record:'+identifier]
    call('/api/v1/temporary-session/finish', {})
    assert len(call('/api/v1/data')['items'])==1
    public.settings['public_records'] = {}
    assert call('/api/v1/data')['items'] == []


def test_public_archive_delete_denied_while_own_temporary_cleanup_still_works(service):
    server, call, _ = service
    public = server.store
    intake = public.intakes.receive('public.edf', len(recording()), io.BytesIO(recording()))
    public.settings['public_records'] = {'local-'+intake['id']: {'name':'Public fixture','url':'https://example.org/data','license':'CC0'}}
    item = public.confirm_intake(intake['id'], confirmation())['input']
    jobid = 'e'*32
    folder = public.root/'jobs'/jobid; folder.mkdir()
    (folder/'report.html').write_text('public report')
    public.jobs[jobid] = {'id':jobid,'input_id':item['id'],'status':'completed'}
    for client in (0, 1):
        for action in ('archive','restore','delete-preview','delete'):
            with pytest.raises(HTTPError) as exc:
                call('/api/v1/data/'+action, {'ids':['report:'+jobid], 'all_archived':True,'confirmed':True}, client)
            assert exc.value.code == 403
    own, _ = upload(call)
    call('/api/v1/temporary-session/finish', {}, client=1)
    assert (server.temporary.store.intakes.root/own['id']).exists()
    call('/api/v1/temporary-session/finish', {})
    assert not (server.temporary.store.intakes.root/own['id']).exists()
    assert (folder/'report.html').read_text() == 'public report'
    assert public.intakes._directory(intake['id']).exists()
    assert not public.library_state.state['archived']


def test_failed_cleanup_retries_without_losing_ownership(service, monkeypatch):
    server, call, _ = service
    intake, _ = upload(call)
    import temporary_uploads
    remove = temporary_uploads.shutil.rmtree
    with monkeypatch.context() as m:
        m.setattr(temporary_uploads.shutil, 'rmtree', lambda *a, **kw: (_ for _ in ()).throw(OSError('busy')))
        with pytest.raises(OSError): server.temporary.finish(type('H', (), {'headers': {'Cookie':'dbci_temporary='+next(iter(server.temporary.sessions))}})())
    server.temporary.sweep()
    assert not server.temporary.sessions
    assert not (server.temporary.store.intakes.root/intake['id']).exists()


def test_restart_removes_abandoned_owned_workspace(tmp_path):
    public = Store({'python':sys.executable,'data_dir':str(tmp_path),'inputs':[],'profiles':[],'data_policy':POLICY})
    old = tmp_path/'.temporary'; old.mkdir(); (old/'.owned-by-dbci').touch()
    (old/'private.log').write_text('must not survive restart')
    manager = TemporaryUploads(public, Store)
    assert not (old/'private.log').exists()
    with pytest.raises(BlockingIOError): TemporaryUploads(public, Store)
    manager.shutdown()


def test_existing_unknown_records_and_jobs_are_not_published(tmp_path):
    settings = {'python':sys.executable,'data_dir':str(tmp_path),'inputs':[],'profiles':[]}
    old = Store(settings)
    intake = old.intakes.receive('old.edf', len(recording()), io.BytesIO(recording()))
    item = old.confirm_intake(intake['id'], confirmation())['input']
    job = tmp_path/'jobs'/('c'*32); job.mkdir()
    (job/'job.json').write_text(json.dumps({'id':'c'*32,'input_id':item['id'],'status':'completed'}))
    strict = Store({**settings,'data_policy':POLICY})
    assert not strict.inputs and not strict.jobs
    with pytest.raises(KeyError): strict.intake_status(intake['id'])
    assert strict.intakes._directory(intake['id']).exists()  # Migration never silently deletes an unclassified old record.
    declared = {'name':'Public fixture','url':'https://example.org/data','license':'CC0'}
    approved = Store({**settings,'data_policy':POLICY,'public_records':{item['id']:declared}})
    assert approved.inputs[item['id']]['public_source'] == {**declared,'version':''}
    assert 'c'*32 in approved.jobs


def add_job(service, record, digit, status='completed'):
    private = service[0].temporary.store
    jobid = digit*32
    folder = private.root/'jobs'/jobid/'artifacts'; folder.mkdir(parents=True)
    (folder/'report.html').write_text('private report')
    private.jobs[jobid] = {'id':jobid,'input_id':record['id'],'status':status,'modules':[],
                           'created_at':'2026-11-13T01:00:00Z'}
    return jobid


def test_pending_confirmed_and_reports_visible_only_to_owner(service):
    server, call, _ = service
    pending = call('/api/v1/intakes', recording(), upload=True)
    assert [r['id'] for r in call('/api/v1/data')['items']] == ['intake:'+pending['id']]
    assert call('/api/v1/data', client=1)['items'] == []
    record = call('/api/v1/intakes/'+pending['id']+'/confirm', confirmation())['input']
    job = add_job(service, record, '1')
    rows = call('/api/v1/data')['items']
    assert len(rows) == 1 and rows[0]['id'] == 'record:'+record['id']
    assert rows[0]['recent_reports'][0]['job_id'] == job
    assert rows[0]['workflow_groups'][0]['latest']['temporary']
    assert call('/api/v1/data', client=1)['items'] == []


def test_own_report_delete_keeps_upload_other_report_and_deadline(service):
    server, call, clock = service
    intake, record = upload(call)
    first, second = add_job(service, record, '1'), add_job(service, record, '2')
    deadline = call('/api/v1/temporary-session')['retention']['expires_at']
    clock[0] += 500
    call('/api/v1/data/delete-temporary', {'id':'report:'+first, 'confirmed':True})
    private = server.temporary.store
    assert first not in private.jobs and second in private.jobs
    assert record['id'] in private.inputs and private.intakes._directory(intake['id']).exists()
    assert not (private.root/'jobs'/first).exists()
    assert call('/api/v1/temporary-session')['retention']['expires_at'] == deadline
    call('/api/v1/data/delete-temporary', {'id':'report:'+second, 'confirmed':True})
    assert call('/api/v1/temporary-session')['retention']['expires_at'] == deadline


def test_delete_owned_data_cancels_active_runs_without_deleting_same_bytes_for_other_browser(service):
    server, call, _ = service
    intake, a = upload(call); other, b = upload(call, 1)
    job = add_job(service, a, '1', 'queued')
    with pytest.raises(HTTPError) as e:
        call('/api/v1/data/delete-temporary', {'id':'record:'+a['id'],'confirmed':True}, client=1)
    assert e.value.code == 403
    with pytest.raises(HTTPError) as e:
        call('/api/v1/data/delete-temporary', {'id':'report:'+job,'confirmed':True}, client=1)
    assert e.value.code == 403
    result = call('/api/v1/data/delete-temporary', {'id':'record:'+a['id'],'confirmed':True})
    assert result['cleanup_pending']
    server.temporary.sweep()
    assert not server.temporary.store.intakes._directory(intake['id']).exists()
    assert server.temporary.store.intakes._directory(other['id']).exists()
    assert b['id'] in server.temporary.store.inputs
    assert call('/api/v1/data')['items'] == []


def test_idle_countdown_does_not_restart_on_poll_or_read(service):
    server, call, clock = service
    _, record = upload(call)
    first = call('/api/v1/data')['items'][0]['retention']
    clock[0] += 300
    call('/api/v1/inputs/'+record['id'])
    current = call('/api/v1/data')['items'][0]['retention']
    assert current['expires_at'] == first['expires_at']
    assert current['server_now'] != first['server_now']
    clock[0] += IDLE_SECONDS
    assert call('/api/v1/data')['items'] == []
    assert not call('/api/v1/temporary-session')['active']


def test_my_data_starts_empty_with_preloaded_public_catalog(service):
    server, call, _ = service
    public = server.store
    intake = public.intakes.receive('public.edf', len(recording()), io.BytesIO(recording()))
    public.settings['public_records'] = {'local-'+intake['id']:
        {'name':'Public fixture', 'url':'https://example.org/data', 'license':'CC0'}}
    registered = public.confirm_intake(intake['id'], confirmation())['input']
    for client in (0, 1):
        directory = call('/api/v1/data', client=client)
        assert directory['items'] == []
        assert directory['counts'] == {'records':0, 'datasets':0}
        assert len(directory['examples']) == 8
    _, own = upload(call)
    assert [r['id'] for r in call('/api/v1/data')['items']] == ['record:'+own['id']]
    assert call('/api/v1/data', client=1)['items'] == []
    # The public source remains available for cached examples and direct report access.
    assert registered['id'] in public.inputs
    assert public.intakes._directory(intake['id']).exists()
