"""Local registered dataset packages and bounded sequential background jobs."""
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import queue
import re
import threading
import uuid

from ephys_qc.dataset_qc import run_dataset_qc
from ephys_qc.dataset_qc.consistency import validate_consistency
from ephys_qc.admission import configured_policy, LimitExceeded
from ephys_qc.dataset_qc.admission import check_dataset_snapshot, assert_snapshot_unchanged


def now():return datetime.now(timezone.utc).isoformat()


def fingerprint(value):return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


class PackageJobs:
    def __init__(self, settings):
        self.admission_policy = configured_policy(settings)
        self.examples = {p['package_id']: p for p in settings.get('demo_examples', [])
                         if isinstance(p, dict) and p.get('kind') == 'dataset' and p.get('package_id')}
        self.validation_ids = set(settings.get('validation_library_ids', []))
        self.root=Path(settings['data_dir'])/'package_jobs';self.root.mkdir(parents=True,exist_ok=True)
        self.packages={};self.jobs={};self.lock=threading.RLock();self.queue=queue.Queue()
        for p in settings.get('packages',[]):
            if not isinstance(p,dict) or not re.fullmatch(r'[a-zA-Z0-9_-]+',p.get('id','')) or p['id'] in self.packages:
                raise ValueError('Invalid registered dataset package')
            self.packages[p['id']]=copy.deepcopy(p)
        for path in self.root.glob('*/job.json'):
            if not re.fullmatch('[a-f0-9]{32}',path.parent.name):continue
            job=json.loads(path.read_text());self.jobs[job['id']]=job
            if job['status'] in {'queued','running'}:
                job.update(status='interrupted',message='服务重启，可重新运行。');self._save(job)
        threading.Thread(target=self._loop,daemon=True).start()

    def _plan(self, identifier):
        p=self.packages[identifier]
        plan=json.loads(Path(p['expectations']).read_text(encoding='utf-8'))
        validate_consistency(plan)
        if not Path(p['root']).is_dir() or Path(p['root']).is_symlink():raise ValueError('数据包目录不可用。')
        return p,plan

    def catalog(self):
        packages=[]
        for identifier,p in self.packages.items():
            item={k:p[k] for k in ('id','label','description') if k in p}
            item['category'] = ('example' if identifier in self.examples else
                                'validation' if 'dataset:' + identifier in self.validation_ids else 'data')
            if identifier in self.examples:
                example = self.examples[identifier]
                item.update({k: example[k] for k in ('label', 'label_en', 'description', 'description_en') if example.get(k)})
            try:
                _,plan=self._plan(identifier);records=plan['consistency']['records']
                item.update(available=True,scope=plan['scope'],manifest_hash=fingerprint(plan),groups=plan['consistency']['groups'],
                            subjects=len({r['subject'] for r in records}),records=len(records),files=len(plan['files']))
            except (OSError,ValueError,KeyError,TypeError): item.update(available=False,error='目录或检查清单不可用。')
            packages.append(item)
        with self.lock:jobs=sorted(self.jobs.values(),key=lambda j:j['created_at'],reverse=True)
        return {'packages':packages,'jobs':copy.deepcopy(jobs[:30]),
                'admission_policy': self.admission_policy.describe() if self.admission_policy else None}

    def records(self, identifier):
        from ephys_qc.dataset_qc.inventory import _safe_file
        p, plan = self._plan(identifier)
        rows = []
        for record in plan['consistency']['records']:
            source = _safe_file(Path(p['root']), record['path'])
            rows.append({k: record.get(k) for k in ('id', 'path', 'subject', 'session', 'modality', 'group', 'processing')})
            rows[-1]['available'] = source is not None and source.is_file()
        return {'package_id': identifier, 'label': p['label'], 'manifest_hash': fingerprint(plan), 'records': rows}

    def record_source(self, body):
        if (not isinstance(body, dict) or set(body) != {'package_id', 'record_id', 'manifest_hash'}
                or any(not isinstance(body[k], str) for k in body)):
            raise ValueError('请选择数据集中的记录。')
        p, plan = self._plan(body['package_id'])
        if body['manifest_hash'] != fingerprint(plan):
            raise ValueError('检查清单已变化，请刷新数据集后重新选择。')
        record = next((r for r in plan['consistency']['records'] if r['id'] == body['record_id']), None)
        if record is None: raise ValueError('该记录不属于当前数据集。')
        if self.admission_policy:
            check_dataset_snapshot(p['root'], plan, limits=self.admission_policy)
        options = next(r for r in plan['recordings'] if r['path'] == record['path'])
        context = {'package_id': p['id'], 'package_label': p['label'], 'manifest_hash': fingerprint(plan),
                   'record_id': record['id'], 'record_path': record['path'],
                   **{k: record[k] for k in ('subject', 'session', 'group', 'processing')},
                   'declared_modality': record['modality'], 'declared_stream_id': options.get('stream_id')}
        return p['root'], record['path'], context, options.get('stream_id')

    def get(self,identifier):
        with self.lock:return copy.deepcopy(self.jobs[identifier])

    def _save(self,job):
        path=self.root/job['id']/'job.json';temp=path.with_suffix('.tmp')
        temp.write_text(json.dumps(job,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(path)

    def submit(self,body):
        required = {'package_id','manifest_hash','confirmed'}
        if not isinstance(body,dict) or not required <= set(body) or set(body) - required - {'baseline_job_id'} or body['confirmed'] is not True:
            raise ValueError('请确认本次检查范围与比较组。')
        if not isinstance(body['package_id'],str) or body['package_id'] not in self.packages:raise ValueError('请选择已登记的数据包。')
        p,plan=self._plan(body['package_id'])
        if body['manifest_hash']!=fingerprint(plan):raise ValueError('检查清单已变化，请刷新并重新确认。')
        baseline = body.get('baseline_job_id')
        baseline_revision = 0
        if baseline is not None:
            if not isinstance(baseline, str) or not re.fullmatch('[a-f0-9]{32}', baseline):
                raise ValueError('复验基线标识无效。')
            old = self.get(baseline)
            if old['package_id'] != p['id'] or old['status'] != 'completed':
                raise ValueError('复验须选择本数据集已完成的资料检查。')
            versions = list((self.root / baseline / 'reviews').glob('[0-9]' * 8 + '.json'))
            baseline_revision = max((int(v.stem) for v in versions), default=0)
        admission = check_dataset_snapshot(p['root'], plan, limits=self.admission_policy) if self.admission_policy else None
        with self.lock:
            for job in self.jobs.values():
                if job['package_id']==p['id'] and job['status'] in {'queued','running'}:
                    if job.get('baseline_job_id') != baseline or job['manifest_hash'] != fingerprint(plan):
                        raise ValueError('本数据集已有不同方案的检查在运行，请等待完成后再复验。')
                    return copy.deepcopy(job)
            identifier=uuid.uuid4().hex;folder=self.root/identifier;folder.mkdir()
            job={'id':identifier,'package_id':p['id'],'label':p['label'],'status':'queued','created_at':now(),
                 'manifest_hash':fingerprint(plan),'modules':[{'id':mid,'status':'pending'} for mid in ('D01','D02','D03')]}
            if baseline:
                job.update(baseline_job_id=baseline, baseline_review_revision=baseline_revision)
            job['admission'] = admission
            self.jobs[identifier]=job
            (folder/'request.json').write_text(json.dumps({'source_root':p['root'],'expectations':plan,'admission':admission,
                'baseline_job_id':baseline,'baseline_review_revision':baseline_revision},ensure_ascii=False,indent=2)+'\n')
            self._save(job);self.queue.put(identifier)
            return copy.deepcopy(job)

    def _loop(self):
        while True:
            identifier=self.queue.get();folder=self.root/identifier
            request = {}
            def progress(mid,status):
                with self.lock:
                    job=self.jobs[identifier];job['status']='running'
                    next(m for m in job['modules'] if m['id']==mid)['status']=status;self._save(job)
            try:
                request=json.loads((folder/'request.json').read_text())
                if request.get('admission'):
                    assert_snapshot_unchanged(request['source_root'], request['admission'], limits=self.admission_policy)
                result=run_dataset_qc(request['source_root'],request['expectations'],folder/'result',progress=progress)
                with self.lock:
                    job=self.jobs[identifier];job.update(status='completed',ended_at=now(),summary=result['summary'],
                                                       report_url=f'/api/v1/package-jobs/{identifier}/report')
                    self._save(job)
            except Exception as error:
                with self.lock:
                    job=self.jobs[identifier];job.update(status='failed',ended_at=now(),error_type=type(error).__name__,message='检查未完成，原始文件未修改。请核对清单与文件后重试。')
                    if request.get('admission') and isinstance(error, ValueError):
                        job['message'] = str(error)
                    if isinstance(error, LimitExceeded):
                        job['admission_error'] = error.payload()
                    for m in job['modules']:
                        if m['status']=='running':m['status']='failed'
                    self._save(job)
            finally:self.queue.task_done()

    def artifact(self,identifier,name):
        if self.get(identifier)['status']!='completed':raise ValueError('检查尚未完成。')
        if name not in {'result.json','report.html','report.en.html','expectations.json'}:raise KeyError(name)
        return self.root/identifier/'result'/name
