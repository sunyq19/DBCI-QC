"""One data directory for uploaded/registered records and declared datasets."""
import copy
from urllib.parse import urlencode


def featured_reports(store):
    """Selectable datasets, with current evidence coverage rather than QC scores.

    A configured dataset remains selectable before its first run. Broken sources
    remain visible but disabled. Historical single-record demos are not promoted
    to datasets; they remain accessible through the ordinary data directory.
    """
    from dataset_overview import build_overview
    rows = []
    packages = {p['id']: p for p in store.packages.catalog()['packages']}
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
        try:
            if package['available']:
                data = build_overview(store, identifier)
                if data['current_manifest']:
                    row.update(records=data['summary']['records'], subjects=data['summary']['subjects'],
                               reported=data['summary']['reported'],
                               status=(data.get('dataset_job') or {}).get('status', 'not_run'))
        except (OSError, ValueError, KeyError, TypeError):
            row['status'] = 'report_unavailable'
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
        rows.append({'id': 'dataset:'+package['id'], 'kind':'dataset', 'label':package['label'],
                     'available':package['available'], 'records':package.get('records'), 'subjects':package.get('subjects'),
                     'status':latest['status'] if latest else 'not_run', 'updated_at':latest['created_at'] if latest else '',
                     'url':'/datasets?'+urlencode({'package':package['id']})})
    with store.lock:
        inputs, jobs = copy.deepcopy(list(store.inputs.values())), copy.deepcopy(list(store.jobs.values()))
    families = {}
    for item in inputs:
        if item.get('dataset_context') or item.get('library_origin') not in {'user_upload', 'user_registered'}: continue
        family = item.get('record_family',item['id'])
        if family not in families or item.get('record_revision',1)>families[family].get('record_revision',1):families[family]=item
    records = []
    for item in families.values():
        # A prior confirmation's score never substitutes for the current revision.
        attempts = [j for j in jobs if j['input_id']==item['id']]
        latest = max(attempts,key=lambda j:j['created_at']) if attempts else None
        records.append({'id':'record:'+item['id'], 'kind':'record', 'label':item['label'],
                        'available':item.get('availability',{}).get('status')!='unavailable',
                        'retention':item.get('retention'), 'format':item.get('metadata',{}).get('format'), 'modality':item.get('modality'),
                        'status':latest['status'] if latest else 'not_run',
                        'updated_at':latest['created_at'] if latest else item.get('provenance',{}).get('received_at',''),
                        'url':'/?'+urlencode({'input':item['id']}),
                        'latest_run_url':(f"/api/v1/jobs/{latest['id']}/report" if latest['status'] == 'completed' else '/?'+urlencode({'job':latest['id']})) if latest else None})
    for intake in store.intakes.pending():
        if intake.get('dataset_context') or intake.get('library_origin') not in {'user_upload', 'user_registered'}: continue
        records.append({'id':'intake:'+intake['id'],'kind':'record','label':intake['filename'],
                        'available':True,'format':intake.get('metadata',{}).get('format'), 'status':'needs_confirmation',
                        'updated_at':intake['received_at'],'url':'/?'+urlencode({'intake':intake['id']})})
    rows += sorted(records,key=lambda r:r['updated_at'],reverse=True)
    # Only explicitly designated controlled/compatibility tests are separated.
    # A newly uploaded record remains ordinary data even when its checks fail.
    validation = set(store.settings.get('validation_library_ids', []))
    for row in rows: row['category'] = 'validation' if row['id'] in validation else 'data'
    examples = featured_reports(store)
    featured = {'dataset:' + row['package_id'] for row in examples}
    rows = [row for row in rows if row['id'] not in featured]
    return {'schema_version':'data-library/1','items':rows, 'examples':examples,
            'counts':{'datasets':sum(row['kind'] == 'dataset' for row in rows), 'records':len(records)}}
