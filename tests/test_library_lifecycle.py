"""Archive, restore and scoped deletion using isolated real intake copies."""
import copy
import io
import json
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from server import Store, save_json
from data_library import library, configuration_source
from test_intake import recording, confirmation


@pytest.fixture
def store(tmp_path):
    settings = {'data_dir': str(tmp_path/'runtime'), 'inputs': [], 'packages': [],
                'example_cache_dir': str(tmp_path/'no-examples')}
    with patch('threading.Thread.start'):
        result = Store(settings)
    return result


def upload(store, *, confirm=True):
    data = recording()
    item = store.intakes.receive('sample.edf', len(data), io.BytesIO(data))
    if confirm:
        record = store.confirm_intake(item['id'], confirmation())['input']
        return store.inputs[record['id']]
    return item


def job(store, record, status='completed', package=False):
    identifier = uuid.uuid4().hex
    value = {'id': identifier, 'input_id': record['id'], 'status': status,
             'created_at': '2026-11-10T05:00:00Z', 'modules': [], 'dataset_context': record.get('dataset_context')}
    folder = store.root/'jobs'/identifier
    (folder/'artifacts').mkdir(parents=True)
    (folder/'artifacts/report.html').write_text('saved report')
    (folder/'request.json').write_text(json.dumps({'input': record}))
    save_json(folder/'job.json', value)
    store.jobs[identifier] = value
    return identifier


def row_for(store, record):
    return next(r for r in library(store)['items'] if r['id'] == 'record:'+record['id'] or
                any(j['job_id'] in store.jobs and store.jobs[j['job_id']]['input_id']==record['id'] for g in r.get('workflow_groups',[]) for j in g['runs']))


def delete(store, row):
    selection = {'ids': [row['id']]}
    preview = store.library_state.preview(selection)
    return store.library_state.delete({**selection, 'token': preview['token'], 'confirmed': True})


def restart(store):
    with patch('threading.Thread.start'):
        return Store(copy.deepcopy(store.settings))


def test_group_archive_restore_persists_all_workflows(store):
    first, second = upload(store), upload(store)
    a, b = job(store, first), job(store, second)
    rows = library(store)['items']
    assert len(rows) == 1
    old_reports = [(store.root/'jobs'/i/'artifacts/report.html').read_bytes() for i in (a,b)]
    store.library_state.archive({'ids':[rows[0]['id']]})
    assert all(store.library_state.is_archived(r) for r in (first,second))
    with pytest.raises(ValueError, match='归档'):
        configuration_source(store, first['id'])
    again = restart(store)
    assert library(again)['items'][0]['archived']
    again.library_state.archive({'ids':[library(again)['items'][0]['id']]}, restore=True)
    assert not library(again)['items'][0]['archived']
    assert set(again.jobs) == {a,b}
    assert old_reports == [(store.root/'jobs'/i/'artifacts/report.html').read_bytes() for i in (a,b)]


def test_delete_requires_archive_confirmation_and_current_preview(store):
    record=upload(store); row=library(store)['items'][0]
    with pytest.raises(ValueError, match='归档'):
        store.library_state.preview({'ids':[row['id']]})
    store.library_state.archive({'ids':[row['id']]})
    preview=store.library_state.preview({'ids':[row['id']]})
    with pytest.raises(ValueError, match='确认'):
        store.library_state.delete({'ids':[row['id']], 'token':preview['token']})
    job(store,record)  # A changed target set invalidates an earlier preview.
    with pytest.raises(ValueError, match='变化'):
        store.library_state.delete({'ids':[row['id']], 'token':preview['token'], 'confirmed':True})


def test_purge_removes_all_copies_revisions_reports_preserves_original(store, tmp_path):
    original=tmp_path/'original.edf'; original.write_bytes(recording())
    first,second=upload(store),upload(store)
    store.settings['inputs']=[dict(first, id='configured', source_path=str(original))]
    store.inputs['configured']=store.settings['inputs'][0]
    revision=dict(first,id='revision-'+uuid.uuid4().hex,record_family=first['id'],record_revision=2)
    folder=store.revisions.root/revision['id'];folder.mkdir();save_json(folder/'record.json',revision)
    store.inputs[revision['id']]=revision
    jobs=[job(store,r) for r in (first,second,revision,store.inputs['configured'])]
    row=library(store)['items'][0]
    store.library_state.archive({'ids':[row['id']]})
    result=delete(store,row)
    assert result['runs']==4 and result['cleanup_pending']==0
    assert not list(store.intakes.root.iterdir()) and not folder.exists()
    assert all(not (store.root/'jobs'/i).exists() for i in jobs)
    assert original.read_bytes()==recording()
    again=restart(store)
    assert not again.inputs and not again.jobs and not library(again)['items']
    upload(again)  # A new upload of the same bytes is a new active entry.
    assert len(library(again)['items'])==1 and not library(again)['items'][0]['archived']


@pytest.mark.parametrize('status',['queued','running','cancelling'])
def test_running_work_blocks_archive_and_purge(store,status):
    record=upload(store); jid=job(store,record,status)
    row=library(store)['items'][0]
    with pytest.raises(ValueError,match='运行'):
        store.library_state.archive({'ids':[row['id']]})
    store.jobs[jid]['status']='completed'
    store.library_state.archive({'ids':[row['id']]})
    store.jobs[jid]['status']=status
    with pytest.raises(ValueError,match='运行'):
        delete(store,row)


def test_pending_intake_can_be_archived_restored_and_deleted(store):
    pending=upload(store,confirm=False); row=library(store)['items'][0]
    store.library_state.archive({'ids':[row['id']]})
    with pytest.raises(ValueError,match='归档'):
        store.confirm_intake(pending['id'],confirmation())
    store.library_state.archive({'ids':[row['id']]},restore=True)
    store.library_state.archive({'ids':[row['id']]})
    assert delete(store,row)['runs']==0
    assert not library(restart(store))['items']


def test_dataset_delete_includes_signal_runs_package_reports_batches_not_linked_root(store,tmp_path):
    source=tmp_path/'dataset';source.mkdir();(source/'data.edf').write_bytes(recording())
    store.packages.packages['p']={'id':'p','label':'Dataset','root':str(source),
        'expectations':str(tmp_path/'missing.json'),'library_origin':'user_registered'}
    store.settings['packages']=list(store.packages.packages.values())
    record=upload(store);record['dataset_context']={'package_id':'p'}
    jid=job(store,record)
    pid=uuid.uuid4().hex; folder=store.packages.root/pid;folder.mkdir()
    value={'id':pid,'package_id':'p','status':'completed','created_at':'today','manifest_hash':'x'}
    store.packages.jobs[pid]=value;save_json(folder/'job.json',value)
    bid=uuid.uuid4().hex; batch={'id':bid,'package_id':'p','status':'completed','records':[{'job_id':jid,'request':{'input_id':record['id']}}]}
    store.batches.items[bid]=batch;store.batches._save(batch)
    row=next(r for r in library(store)['items'] if r['id']=='dataset:p')
    store.library_state.archive({'ids':[row['id']]})
    result=delete(store,row)
    assert result['runs']==2
    assert not store.packages.jobs and not store.batches.items
    assert not folder.exists() and not (store.batches.root/(bid+'.json')).exists()
    assert (source/'data.edf').read_bytes()==recording()
    assert not restart(store).packages.packages


def test_shared_payload_and_symlink_targets_are_not_removed(store,tmp_path):
    record=upload(store);jid=job(store,record)
    other=dict(record,id='another-stream',record_family='another-stream',metadata=dict(record['metadata'],selected_stream_id='B'))
    store.inputs[other['id']]=other
    row=row_for(store,record)
    external=tmp_path/'external';external.mkdir();(external/'keep').write_text('keep')
    (store.root/'jobs'/jid/'external-link').symlink_to(external,target_is_directory=True)
    store.library_state.archive({'ids':[row['id']]});delete(store,row)
    assert Path(other['source_path']).exists()
    assert (external/'keep').read_text()=='keep'
    assert other['id'] in store.inputs
    remaining=row_for(store,other)
    store.library_state.archive({'ids':[remaining['id']]});delete(store,remaining)
    assert not Path(other['source_path']).exists()
    assert (external/'keep').read_text()=='keep'


def test_partial_filesystem_failure_retries_without_reviving_deleted_records(store):
    record=upload(store);job(store,record);row=library(store)['items'][0]
    store.library_state.archive({'ids':[row['id']]})
    with patch('library_lifecycle.shutil.rmtree',side_effect=OSError('busy')):
        result=delete(store,row)
    assert result['cleanup_pending']>0 and not store.inputs and not store.jobs
    again=restart(store)
    assert not again.inputs and not again.jobs and not again.library_state.state['pending']


def test_clear_archive_keeps_active_data_and_rejects_arbitrary_ids(store):
    first=upload(store);job(store,first)
    row=library(store)['items'][0];store.library_state.archive({'ids':[row['id']]})
    other=upload(store);other['expected_sha256']='b'*64
    for value in ['../', 'record:../../etc', '/tmp/nope']:
        with pytest.raises(ValueError):store.library_state.archive({'ids':[value]})
    preview=store.library_state.preview({'all_archived':True})
    assert preview['items']==1
    store.library_state.delete({'all_archived':True,'token':preview['token'],'confirmed':True})
    assert set(store.inputs)=={other['id']}


def test_http_archive_restore_delete_and_catalog_visibility(store):
    import threading
    import urllib.request
    import urllib.error
    from http.server import ThreadingHTTPServer
    from server import Handler
    record=upload(store);jid=job(store,record)
    http=ThreadingHTTPServer(('127.0.0.1',0),Handler);http.store=store
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}'
    def request(path, body=None):
        payload=None if body is None else json.dumps(body).encode()
        req=urllib.request.Request(base+'/api/v1/'+path,data=payload,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req) as response:return json.load(response)
    try:
        rid=request('data')['items'][0]['id']
        request('data/archive',{'ids':[rid]})
        assert not request('inputs')['inputs'] and not request('jobs')['jobs']
        assert request('data')['items'][0]['archived']
        assert request('jobs/'+jid)['id']==jid
        request('data/restore',{'ids':[rid]})
        assert len(request('inputs')['inputs'])==1 and len(request('jobs')['jobs'])==1
        request('data/archive',{'ids':['report:'+jid]})
        assert len(request('inputs')['inputs'])==1 and not request('jobs')['jobs']
        row=request('data')['items'][0]
        assert not row['archived'] and row['archived_reports']==1
        assert request('jobs/'+jid)['id']==jid
        request('data/restore',{'ids':['report:'+jid]})
        assert len(request('jobs')['jobs'])==1
        request('data/archive',{'ids':[rid]})
        preview=request('data/delete-preview',{'all_archived':True})
        request('data/delete',{'all_archived':True,'token':preview['token'],'confirmed':True})
        assert not request('data')['items']
        with pytest.raises(urllib.error.HTTPError) as error:request('jobs/'+jid)
        assert error.value.code==404
    finally:
        http.shutdown();http.server_close();thread.join()


def test_single_report_archive_keeps_sibling_workflows_and_input_active(store):
    record=upload(store)
    first,second=job(store,record),job(store,record)
    store.jobs[first]['created_at']='2026-11-09T01:00:00Z'
    store.jobs[second]['created_at']='2026-11-10T01:00:00Z'
    for identifier in (first,second):
        save_json(store.root/'jobs'/identifier/'job.json',store.jobs[identifier])
    store.library_state.archive({'ids':['report:'+second]})
    row=library(store)['items'][0]
    assert not row['archived'] and row['archived_reports']==1 and row['active_reports']==1
    runs={r['job_id']:r for g in row['workflow_groups'] for r in g['runs']}
    assert runs[second]['archived'] and not runs[first]['archived']
    assert configuration_source(store,record['id'])[1]['id']==first
    again=restart(store)
    assert not again.library_state.is_archived(again.inputs[record['id']])
    assert again.library_state.report_archived(again.jobs[second])
    assert (again.root/'jobs'/second/'artifacts/report.html').read_text()=='saved report'


def test_deleting_one_report_removes_its_artifacts_only_and_survives_restart(store):
    record=upload(store);first,second=job(store,record),job(store,record)
    artifacts=store.root/'jobs'/first/'artifacts'
    for name in ('report.pdf','waveform.png','result.json'):(artifacts/name).write_text('test result')
    original=Path(record['source_path']).read_bytes()
    selection={'ids':['report:'+first]}
    store.library_state.archive(selection)
    preview=store.library_state.preview(selection)
    assert preview['reports_only'] and preview['runs']==1 and preview['records']==0
    result=store.library_state.delete({**selection,'token':preview['token'],'confirmed':True})
    assert not result['input_ids'] and result['job_ids']==[first]
    assert not artifacts.parent.exists()
    assert Path(record['source_path']).read_bytes()==original
    assert (store.root/'jobs'/second/'artifacts/report.html').read_text()=='saved report'
    again=restart(store)
    assert set(again.jobs)=={second} and record['id'] in again.inputs
    assert not library(again)['items'][0]['archived_reports']


def test_restoring_one_report_from_legacy_group_archive_leaves_other_reports_archived(store):
    record=upload(store);first,second=job(store,record),job(store,record)
    row=library(store)['items'][0]
    store.library_state.archive({'ids':[row['id']]})
    # The legacy parent marker has no individual report markers.
    assert 'report:'+first not in store.library_state.state['archived']
    store.library_state.archive({'ids':['report:'+first]},restore=True)
    assert not store.library_state.is_archived(record)
    assert not store.library_state.report_archived(store.jobs[first])
    assert store.library_state.report_archived(store.jobs[second])
    store.library_state.archive({'ids':[row['id']]},restore=True)
    assert not store.library_state.state['archived']


def test_clear_archive_combines_whole_entries_and_individual_reports(store):
    first=upload(store);a=job(store,first)
    second=upload(store);second['expected_sha256']='b'*64
    b,c=job(store,second),job(store,second)
    store.library_state.archive({'ids':[row_for(store,first)['id'],'report:'+b]})
    selection={'all_archived':True};preview=store.library_state.preview(selection)
    assert preview['items']==2 and preview['runs']==2
    store.library_state.delete({**selection,'token':preview['token'],'confirmed':True})
    assert set(store.jobs)=={c} and set(store.inputs)=={second['id']}
    assert Path(second['source_path']).exists()
    assert not store.library_state.state['archived']


def test_deleting_report_from_finished_batch_preserves_other_reports(store):
    record=upload(store);first,second=job(store,record),job(store,record)
    bid=uuid.uuid4().hex
    store.batches.items[bid]={'id':bid,'package_id':'p','status':'completed','records':[
        {'job_id':i,'status':'completed','request':{'input_id':record['id']}} for i in (first,second)]}
    store.batches._save(store.batches.items[bid])
    store.library_state.archive({'ids':['report:'+first]})
    delete(store,{'id':'report:'+first})
    batch=store.batches.get(bid)
    assert batch['finished']==2 and batch['records'][0]['status']=='deleted'
    assert 'report_url' not in batch['records'][0]
    assert batch['records'][1]['report_url'].endswith(second+'/report')
    assert (store.batches.root/(bid+'.json')).exists()


def test_active_sibling_does_not_block_completed_report_unless_same_batch(store):
    record=upload(store);first=job(store,record);second=job(store,record,'running')
    store.library_state.archive({'ids':['report:'+first]})
    store.library_state.archive({'ids':['report:'+first]},restore=True)
    bid=uuid.uuid4().hex
    store.batches.items[bid]={'id':bid,'package_id':'p','status':'running',
        'records':[{'job_id':first},{'job_id':second}]}
    with pytest.raises(ValueError,match='运行'):
        store.library_state.archive({'ids':['report:'+first]})


def test_dataset_report_archive_is_independent_of_signal_reports_and_baseline(store,tmp_path):
    source=tmp_path/'dataset';source.mkdir()
    store.packages.packages['p']={'id':'p','label':'Dataset','root':str(source),
        'expectations':str(tmp_path/'missing.json'),'library_origin':'user_registered'}
    record=upload(store);record['dataset_context']={'package_id':'p'};signal=job(store,record)
    first,second=uuid.uuid4().hex,uuid.uuid4().hex
    for identifier,baseline in ((first,None),(second,first)):
        value={'id':identifier,'package_id':'p','status':'completed','created_at':'today',
            'manifest_hash':'x','baseline_job_id':baseline}
        folder=store.packages.root/identifier;folder.mkdir();save_json(folder/'job.json',value)
        (folder/'report.html').write_text('dataset report')
        store.packages.jobs[identifier]=value
    store.library_state.archive({'ids':['package-report:'+first]})
    row=next(r for r in library(store)['items'] if r['id']=='dataset:p')
    assert row['archived_reports']==1 and row['active_reports']==2 and not row['archived']
    assert len(row['recent_reports'])==3
    with pytest.raises(ValueError,match='基线'):
        delete(store,{'id':'package-report:'+first})
    store.library_state.archive({'ids':['package-report:'+second]})
    preview=store.library_state.preview({'all_archived':True})
    assert preview['reports_only'] and preview['runs']==2
    store.library_state.delete({'all_archived':True,'token':preview['token'],'confirmed':True})
    assert not store.packages.jobs and 'p' in store.packages.packages
    assert signal in store.jobs and Path(record['source_path']).exists()
