"""One data directory for uploaded/registered records and declared datasets."""
import copy
import math
from urllib.parse import urlencode


def featured_reports(store):
    """Explicit demonstration selection; never infer 'good' examples from scores.

    Job examples are pinned historical reports. Dataset examples use the current
    manifest and latest attempts, so a failure cannot silently borrow an old score.
    Missing local results simply make a configured example unavailable.
    """
    from dataset_overview import build_overview
    rows = []
    for example in store.settings.get('demo_examples', [])[:4]:
        if not isinstance(example, dict): continue
        try:
            if example.get('kind') == 'record':
                job = store.job(example['job_id'])
                if job['status'] != 'completed' or job['input_id'] != example['input_id']: continue
                result = store.result(job['id'], compact=True)
                view = result.get('report_view') or {}
                score = view.get('score') or {}
                value = score.get('value')
                if not isinstance(value, (int, float)) or not math.isfinite(value): value = None
                row = {'kind': 'record', 'url': '/?' + urlencode({'job': job['id']}),
                       'score': value, 'scope': result.get('scope'), 'score_version': score.get('version'),
                       'duration_seconds': view.get('input_duration_seconds'),
                       'summary': view.get('summary'), 'summary_en': None,
                       'completed_at': job.get('ended_at')}
            elif example.get('kind') == 'dataset':
                data = build_overview(store, example['package_id'])
                if not data['current_manifest'] or not data['summary']['reported']: continue
                row = {'kind': 'dataset', 'url': '/datasets?' + urlencode({'package': example['package_id']}),
                       'records': data['summary']['records'], 'subjects': data['summary']['subjects'],
                       'reported': data['summary']['reported'],
                       'attention_categories': len(data.get('attention_groups', []))}
            else: continue
            row.update({k: example.get(k, '') for k in ('id', 'label', 'label_en')})
            rows.append(row)
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return rows


def library(store):
    datasets = store.packages.catalog()
    with store.packages.lock:
        dataset_jobs = copy.deepcopy(list(store.packages.jobs.values()))
    rows = []
    for package in datasets['packages']:
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
        if item.get('dataset_context'): continue
        family = item.get('record_family',item['id'])
        if family not in families or item.get('record_revision',1)>families[family].get('record_revision',1):families[family]=item
    records = []
    for item in families.values():
        # A prior confirmation's score never substitutes for the current revision.
        attempts = [j for j in jobs if j['input_id']==item['id']]
        latest = max(attempts,key=lambda j:j['created_at']) if attempts else None
        records.append({'id':'record:'+item['id'], 'kind':'record', 'label':item['label'],
                        'available':item.get('availability',{}).get('status')!='unavailable',
                        'format':item.get('metadata',{}).get('format'), 'modality':item.get('modality'),
                        'status':latest['status'] if latest else 'not_run',
                        'updated_at':latest['created_at'] if latest else item.get('provenance',{}).get('received_at',''),
                        'url':'/?'+urlencode({'input':item['id']}),
                        'latest_run_url':'/?'+urlencode({'job':latest['id']}) if latest else None})
    for intake in store.intakes.pending():
        if intake.get('dataset_context'): continue
        records.append({'id':'intake:'+intake['id'],'kind':'record','label':intake['filename'],
                        'available':True,'format':intake.get('metadata',{}).get('format'), 'status':'needs_confirmation',
                        'updated_at':intake['received_at'],'url':'/?'+urlencode({'intake':intake['id']})})
    rows += sorted(records,key=lambda r:r['updated_at'],reverse=True)
    # Only explicitly designated controlled/compatibility tests are separated.
    # A newly uploaded record remains ordinary data even when its checks fail.
    validation = set(store.settings.get('validation_library_ids', []))
    for row in rows: row['category'] = 'validation' if row['id'] in validation else 'data'
    return {'schema_version':'data-library/1','items':rows,
            'examples':featured_reports(store),
            'counts':{'datasets':len(datasets['packages']),'records':len(records)}}
