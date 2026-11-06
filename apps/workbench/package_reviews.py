"""Append-only D04 review records bound to immutable package-job results."""
from datetime import datetime, timezone
import json
import re
import threading
import os
import tempfile

from ephys_qc.dataset_qc.review import build_case, retest_delta, apply_changes


class ReviewConflict(ValueError):
    pass


class PackageReviews:
    def __init__(self, packages):
        self.packages = packages
        self.lock = threading.RLock()

    def _load(self, identifier, revision=None):
        if not isinstance(identifier, str) or not re.fullmatch('[a-f0-9]{32}', identifier):
            raise ValueError('检查任务标识无效。')
        job = self.packages.get(identifier)
        root = self.packages.root / identifier
        result = json.loads(self.packages.artifact(identifier, 'result.json').read_text())
        manifest = json.loads(self.packages.artifact(identifier, 'expectations.json').read_text())
        snapshots = sorted((root / 'reviews').glob('[0-9]' * 8 + '.json'))
        if revision is not None:
            snapshots = [p for p in snapshots if int(p.stem) <= revision]
        saved = json.loads(snapshots[-1].read_text()) if snapshots else {}
        if saved and saved['revision'] != len(snapshots):
            raise ValueError('审核历史不连续，请核对本地记录。')
        return job, result, manifest, saved, snapshots

    def get(self, identifier):
        with self.lock:
            job, result, manifest, saved, snapshots = self._load(identifier)
            previous, inherited = None, None
            baseline = job.get('baseline_job_id')
            if baseline:
                old_job, old_result, old_manifest, old_saved, _ = self._load(baseline, job.get('baseline_review_revision', 0))
                if old_job['package_id'] != job['package_id']:
                    raise ValueError('复验基线不属于本数据集。')
                previous = {'job_id': baseline, **retest_delta(old_result, result, old_manifest, manifest)}
                if previous['compatible']:
                    inherited = old_saved.get('decisions')
            case = build_case(result, manifest, saved, inherited=inherited, previous=previous)
            case.update(job_id=identifier, package_id=job['package_id'], label=job['label'], checked_at=result['checked_at'],
                        engineering_demo=bool(self.packages.packages[job['package_id']].get('engineering_demo')),
                        history=[{k: row.get(k) for k in ('revision', 'recorded_at', 'reviewer', 'final')}
                                 for row in (json.loads(p.read_text()) for p in snapshots)])
            return case

    def save(self, identifier, body):
        with self.lock:
            case = self.get(identifier)
            if isinstance(body, dict) and body.get('expected_revision') != case['revision']:
                raise ReviewConflict('另一份审核记录已保存，请刷新后重试。')
            _, _, _, saved, _ = self._load(identifier)
            record = apply_changes(case, saved, body, datetime.now(timezone.utc).isoformat())
            root = self.packages.root / identifier / 'reviews'
            root.mkdir(exist_ok=True)
            # Exclusive creation prevents a second process from replacing a revision.
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', dir=root, suffix='.tmp', encoding='utf-8', delete=False) as f:
                    temporary = f.name
                    json.dump(record, f, ensure_ascii=False, indent=2, allow_nan=False)
                    f.write('\n')
                    f.flush()
                    os.fsync(f.fileno())
                os.link(temporary, root / f'{record["revision"]:08d}.json')
            except FileExistsError as error:
                raise ReviewConflict('审核记录已更新，请刷新。') from error
            finally:
                if temporary:
                    os.unlink(temporary)
            return self.get(identifier)
