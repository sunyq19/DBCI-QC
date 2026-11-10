"""One data directory for uploaded/registered records and declared datasets."""
import copy
from urllib.parse import urlencode
from library_identity import data_identity, workflow_groups


def configuration_source(store, identifier):
    """Resume the newest run of this data's usable, current confirmations.

    Use saved identities/receipts only: entering configuration must not reread
    signal files, load a report, or start analysis. Never revive an old revision.
    """
    with store.lock:
        requested = copy.deepcopy(store.inputs[identifier])
        if hasattr(store, 'library_state'): store.library_state.assert_record_active(requested)
        inputs = copy.deepcopy(list(store.inputs.values()))
        jobs = copy.deepcopy(list(store.jobs.values()))
    if (requested.get('availability', {}).get('status') == 'unavailable' or
            requested.get('retention', {}).get('state') == 'expired'):
        raise ValueError('数据副本不可用；报告仍可查看，重新检查请再次上传。')
    latest_revisions = {}
    for item in inputs:
        family = item.get('record_family', item['id'])
        latest_revisions[family] = max(latest_revisions.get(family, 0), item.get('record_revision', 1))
    identity = data_identity(requested)
    eligible = {item['id']: item for item in inputs if
                data_identity(item) == identity and
                item.get('modality', 'scalp_eeg') == requested.get('modality', 'scalp_eeg') and
                item.get('dataset_context') == requested.get('dataset_context') and
                item.get('record_revision', 1) == latest_revisions[item.get('record_family', item['id'])] and
                item.get('availability', {}).get('status') != 'unavailable' and
                item.get('retention', {}).get('state') != 'expired'}
    if identifier not in eligible:
        raise ValueError('记录信息已更新，请从“我的数据”选择当前记录。')
    latest = max((job for job in jobs if job['input_id'] in eligible),
                 key=lambda job: (job['created_at'], job['id']), default=None)
    return (eligible[latest['input_id']], latest) if latest else (requested, None)


def featured_reports(store, packages=None):
    """Selectable datasets, with current evidence coverage rather than QC scores.

    A configured dataset remains selectable before its first run. Broken sources
    remain visible but disabled. Historical single-record demos are not promoted
    to datasets; they remain accessible through the ordinary data directory.
    """
    rows = []
    packages = packages if packages is not None else store.packages.catalog()['packages']
    packages = {p['id']: p for p in packages}
    # Directory navigation reads job receipts only. Full evidence verification
    # belongs to the report endpoint, never to the landing-page critical path.
    with store.lock:
        jobs = [{k: j.get(k) for k in ('id', 'status', 'created_at', 'dataset_context')}
                for j in store.jobs.values()]
    seen = set()
    for example in store.settings.get('demo_examples', []):
        if not isinstance(example, dict) or example.get('kind') != 'dataset': continue
        identifier = example.get('package_id')
        if identifier not in packages or identifier in seen: continue
        seen.add(identifier)
        package = packages[identifier]
        row = {'kind': 'dataset', 'package_id': identifier,
               'url': '/api/v1/packages/' + identifier + '/overview/report',
               'available': package['available'], 'records': package.get('records', 0),
               'subjects': package.get('subjects', 0), 'reported': 0,
               'status': 'not_run' if package['available'] else 'unavailable'}
        row.update({k: example.get(k, '') for k in
                    ('id', 'label', 'label_en', 'description', 'description_en', 'formats', 'modality')})
        latest = {}
        for job in jobs:
            context = job.get('dataset_context') or {}
            if (context.get('package_id') != identifier or
                    context.get('manifest_hash') != package.get('manifest_hash')): continue
            rid = context.get('record_id')
            if rid and (rid not in latest or (job.get('created_at') or '') > (latest[rid].get('created_at') or '')):
                latest[rid] = job
        row['reported'] = sum(j['status'] == 'completed' and
            (store.root / 'jobs' / j['id'] / 'artifacts' / 'report.html').is_file()
            for j in latest.values())
        if row['reported']: row['status'] = 'completed'
        rows.append(row)
    return rows


def library(store):
    datasets = store.packages.catalog()
    with store.packages.lock:
        dataset_jobs = copy.deepcopy(list(store.packages.jobs.values()))
    rows = []
    for package in datasets['packages']:
        configured = store.packages.packages.get(package['id'], {})
        if configured.get('library_origin') not in {'user_upload', 'user_registered'}: continue
        jobs = [j for j in dataset_jobs if j['package_id'] == package['id'] and j['manifest_hash'] == package.get('manifest_hash')]
        latest = max(jobs, key=lambda j:j['created_at']) if jobs else None
        reports = sorted((j for j in jobs if j['status']=='completed'),key=lambda j:j['created_at'],reverse=True)
        rows.append({'id': 'dataset:'+package['id'], 'kind':'dataset', 'label':package['label'],
                     'available':package['available'], 'records':package.get('records'), 'subjects':package.get('subjects'),
                     'status':latest['status'] if latest else 'not_run', 'updated_at':latest['created_at'] if latest else '',
                     'url':'/datasets?'+urlencode({'package':package['id']}),
                     'recent_reports':[{'label':j.get('run_name') or '资料检查', 'label_en':j.get('run_name') or 'Dataset check', 'created_at':j['created_at'],
                        'url':f"/api/v1/packages/{package['id']}/overview/report?job={j['id']}"} for j in reports]})
    with store.lock:
        inputs, jobs = copy.deepcopy(list(store.inputs.values())), copy.deepcopy(list(store.jobs.values()))
    families = {}
    for item in inputs:
        if item.get('dataset_context') or item.get('library_origin') not in {'user_upload', 'user_registered'}: continue
        family = item.get('record_family',item['id'])
        if family not in families or item.get('record_revision',1)>families[family].get('record_revision',1):families[family]=item
    validation = set(store.settings.get('validation_library_ids', []))
    grouped = {}
    for item in families.values():
        key = (data_identity(item), 'record:'+item['id'] in validation)
        grouped.setdefault(key, []).append(item)
    records = []
    for (identity, is_validation), copies in grouped.items():
        # Prefer a usable current confirmation, preserving every historical run.
        item = max(copies, key=lambda i: (i.get('availability', {}).get('status') != 'unavailable',
            i.get('revised_at') or i.get('provenance', {}).get('received_at', ''), i['id']))
        current_ids = {i['id'] for i in copies}
        related = {i['id']: i for i in inputs if
                   not i.get('dataset_context') and i.get('library_origin') in {'user_upload', 'user_registered'}
                   and data_identity(i) == identity and ('record:'+i['id'] in validation) == is_validation}
        all_attempts = [j for j in jobs if j['input_id'] in related]
        # A prior confirmation's score never substitutes for the current revision.
        attempts = [j for j in all_attempts if j['input_id'] in current_ids]
        latest = max(attempts,key=lambda j:j['created_at']) if attempts else None
        completed = sorted((j for j in attempts if j['status']=='completed' and
                            (store.root/'jobs'/j['id']/'artifacts'/'report.html').is_file()),
                           key=lambda j:j['created_at'],reverse=True)
        reports = []
        seen_labels = set()
        for job in completed:
            labels = related[job['input_id']].get('report_labels', {})
            label = labels.get(job['id'], {})
            # A refreshed named workflow replaces its older run in this compact
            # list; it must not displace the other comparison workflow.
            key = job['id'] if job.get('run_name') else label.get('zh-CN') or job['id']
            if key in seen_labels: continue
            seen_labels.add(key)
            reports.append({'job_id':job['id'], 'label':job.get('run_name') or label.get('zh-CN','检查报告'),
                            'label_en':job.get('run_name') or label.get('en','QC report'), 'created_at':job['created_at'],
                            'url':f"/api/v1/jobs/{job['id']}/report",
                            'visualizations_url':f"/api/v1/jobs/{job['id']}/visualizations"})
        records.append({'id':'record:'+item['id'], 'kind':'record', 'label':item['label'],
                        'available':item.get('availability',{}).get('status')!='unavailable',
                        'retention':item.get('retention'), 'format':item.get('metadata',{}).get('format'), 'modality':item.get('modality'),
                        'status':latest['status'] if latest else 'not_run',
                        'recent_reports':reports,
                        'workflow_groups':workflow_groups(store.root, all_attempts, related, current_ids),
                        'registered_copies':len(copies),
                        'updated_at':latest['created_at'] if latest else item.get('provenance',{}).get('received_at',''),
                        'url':'/?'+urlencode({'input':item['id']}),
                        'latest_run_url':(f"/api/v1/jobs/{latest['id']}/report" if latest['status'] == 'completed' else '/?'+urlencode({'job':latest['id']})) if latest else None})
    for intake in store.intakes.pending():
        if hasattr(store, 'library_state') and intake['id'] in store.library_state.state['deleted']['intakes']: continue
        if intake.get('dataset_context') or intake.get('library_origin') not in {'user_upload', 'user_registered'}: continue
        records.append({'id':'intake:'+intake['id'],'kind':'record','label':intake['filename'],
                        'available':True,'format':intake.get('metadata',{}).get('format'), 'status':'needs_confirmation',
                        'updated_at':intake['received_at'],'url':'/?'+urlencode({'intake':intake['id']})})
    rows += sorted(records,key=lambda r:r['updated_at'],reverse=True)
    # Only explicitly designated controlled/compatibility tests are separated.
    # A newly uploaded record remains ordinary data even when its checks fail.
    for row in rows: row['category'] = 'validation' if row['id'] in validation else 'data'
    from example_cache import manifest
    examples = manifest(store)['examples']
    featured = {'dataset:' + row['package_id'] for row in examples}
    rows = [row for row in rows if row['id'] not in featured]
    if hasattr(store, 'library_state'): store.library_state.decorate(rows)
    return {'schema_version':'data-library/1','items':rows, 'examples':examples,
            'counts':{'datasets':sum(row['kind'] == 'dataset' for row in rows), 'records':len(records)}}
