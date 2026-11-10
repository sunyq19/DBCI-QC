"""Archive individual reports or whole entries; purge only owned descendants."""
import hashlib
import json
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import uuid

from library_identity import data_identity

ACTIVE = {'queued', 'running', 'cancelling'}
ORIGINS = {'user_upload', 'user_registered'}


def stamp():
    return datetime.now(timezone.utc).isoformat()


class LibraryLifecycle:
    def __init__(self, store):
        self.store = store
        self.path = store.root / 'library-state.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'version': 1, 'archived': {}, 'deleted': {k: [] for k in ('inputs', 'packages', 'intakes')},
            'pending': [], 'deletions': []}
        # Older whole-entry archives remain valid; report state is additive.
        for group in ('jobs', 'package_jobs'):
            self.state['deleted'].setdefault(group, [])
        self.state['version'] = 2
        self.apply_deleted()
        self.cleanup()

    def _save(self):
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.state, ensure_ascii=False, indent=2))
        temporary.replace(self.path)

    def locked(self):
        # Matches batch -> store ordering used by the batch runner. Linked intake
        # registration also finishes before package membership can be removed.
        stack = ExitStack()
        # Review saves acquire their own lock before the package lock. Wait for
        # them before removing a report directory, so a save cannot recreate it.
        for lock in (self.store.batches.lock, self.store.link_lock, self.store.lock,
                     self.store.package_reviews.lock, self.store.packages.lock):
            stack.enter_context(lock)
        return stack

    def record_key(self, record):
        context = record.get('dataset_context') or {}
        if context.get('package_id'):
            return 'dataset:' + context['package_id']
        validation = 'record:' + record['id'] in self.store.settings.get('validation_library_ids', [])
        return 'record:' + data_identity(record) + (':validation' if validation else '')

    def key(self, row):
        kind, identifier = row['id'].split(':', 1)
        return self.record_key(self.store.inputs[identifier]) if kind == 'record' else row['id']

    def is_archived(self, record):
        return self.record_key(record) in self.state['archived']

    def report_key(self, job, package=False):
        return ('package-report:' if package else 'report:') + job['id']

    def report_parent(self, job, package=False):
        return 'dataset:' + job['package_id'] if package else self.record_key(self.store.inputs[job['input_id']])

    def report_archived(self, job, package=False):
        return (self.report_key(job, package) in self.state['archived'] or
                self.report_parent(job, package) in self.state['archived'])

    def assert_record_active(self, record):
        if self.is_archived(record):
            raise ValueError('数据已归档，请先在“我的数据 → 归档”中恢复。')

    def assert_package_active(self, identifier):
        if identifier in self.state['deleted']['packages']:
            raise KeyError(identifier)
        if 'dataset:' + identifier in self.state['archived']:
            raise ValueError('数据集已归档，请先恢复。')

    def assert_intake_active(self, identifier):
        if identifier in self.state['deleted']['intakes']:
            raise KeyError(identifier)
        value = self.store.intakes.get(identifier)
        key = 'dataset:' + value['dataset_context']['package_id'] if value.get('dataset_context') else 'intake:' + identifier
        if key in self.state['archived']:
            raise ValueError('数据已归档，请先恢复。')
        if value.get('input_id') in self.store.inputs:
            self.assert_record_active(self.store.inputs[value['input_id']])

    def decorate(self, rows):
        for row in rows:
            archived = self.state['archived'].get(self.key(row))
            row['archived'] = bool(archived)
            if archived:
                row['archived_at'] = archived['archived_at']
            reports = list(row.get('recent_reports', []))
            for group in row.get('workflow_groups', []):
                reports += group['runs']
            seen = {}
            for report in reports:
                identifier = report.get('archive_id') or ('report:' + report['job_id'] if report.get('job_id') else None)
                if not identifier:
                    continue
                report['archive_id'] = identifier
                report['archived'] = bool(archived or identifier in self.state['archived'])
                seen[identifier] = report['archived']
            row['archived_reports'] = sum(seen.values())
            row['active_reports'] = len(seen) - row['archived_reports']
        return rows

    def _rows(self):
        from data_library import library
        rows = {row['id']: row for row in library(self.store)['items']}
        parents = {self.key(row): row for row in rows.values()}
        for package, jobs in ((False, self.store.jobs), (True, self.store.packages.jobs)):
            for job in jobs.values():
                if not package and job['input_id'] not in self.store.inputs:
                    continue
                parent = self.report_parent(job, package)
                if parent not in parents:
                    continue
                identifier = self.report_key(job, package)
                rows[identifier] = {'id': identifier, 'kind': 'report', 'parent_key': parent,
                    'label': job.get('run_name') or parents[parent]['label'] + ' · ' + job.get('created_at', ''),
                    'archived': self.report_archived(job, package)}
        return rows

    def _select(self, body, *, all_allowed=False):
        if not isinstance(body, dict):
            raise ValueError('请选择数据。')
        rows = self._rows()
        if all_allowed and body.get('all_archived') is True:
            chosen = [row for row in rows.values() if row.get('archived') and
                      not (row.get('kind') == 'report' and row['parent_key'] in self.state['archived'])]
        else:
            ids = body.get('ids')
            if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in rows for i in ids):
                raise ValueError('请选择“我的数据”中的报告或数据。')
            chosen = [rows[i] for i in dict.fromkeys(ids)]
        return chosen

    def targets(self, rows):
        keys = {self.key(row) for row in rows}
        packages = {key.split(':', 1)[1] for key in keys if key.startswith('dataset:')}
        inputs = {i['id'] for i in self.store.inputs.values() if i.get('library_origin') in ORIGINS and self.record_key(i) in keys}
        families = {self.store.inputs[i].get('record_family', i) for i in inputs}
        inputs |= {i['id'] for i in self.store.inputs.values() if i.get('record_family', i['id']) in families}
        intakes = {key.split(':', 1)[1] for key in keys if key.startswith('intake:')}
        # A shared payload may outlive the intake's original record. Include
        # the owned directory again when its last remaining reference is removed.
        for identifier in inputs:
            item = self.store.inputs[identifier]
            names = [item.get('source_path', '')] + [f.get('path', '') for f in item.get('expected_source_files', [])]
            for name in names:
                if not name:
                    continue
                path = Path(name)
                if path.is_relative_to(self.store.intakes.root):
                    parts = path.relative_to(self.store.intakes.root).parts
                    if parts and re.fullmatch('[a-f0-9]{32}', parts[0]):
                        intakes.add(parts[0])
        for path in self.store.intakes.root.glob('*/intake.json'):
            if path.is_symlink() or path.parent.is_symlink():
                continue
            value = json.loads(path.read_text())
            if (value.get('input_id') in inputs or 'local-' + path.parent.name in families or
                    (value.get('dataset_context') or {}).get('package_id') in packages):
                intakes.add(path.parent.name)
        jobs = {j['id'] for j in self.store.jobs.values() if 'report:' + j['id'] in keys or j['input_id'] in inputs or
                (j.get('dataset_context') or {}).get('package_id') in packages}
        package_jobs = {j['id'] for j in self.store.packages.jobs.values() if 'package-report:' + j['id'] in keys or j['package_id'] in packages}
        batches = {b['id'] for b in self.store.batches.items.values() if b['package_id'] in packages or
                   any(r.get('request', {}).get('input_id') in inputs for r in b.get('records', []))}
        active = [j for j in self.store.jobs.values() if j['id'] in jobs and j['status'] in ACTIVE]
        active += [j for j in self.store.packages.jobs.values() if j['id'] in package_jobs and j['status'] in ACTIVE]
        active += [b for b in self.store.batches.items.values() if b['status'] in ACTIVE and
                   (b['id'] in batches or any(r.get('job_id') in jobs for r in b.get('records', [])))]
        if active:
            raise ValueError('数据仍有检查在运行，请等待完成或取消后再操作。')
        return {key: sorted(value) for key, value in locals().copy().items()
                if key in {'keys', 'packages', 'inputs', 'intakes', 'jobs', 'package_jobs', 'batches'}}

    def archive(self, body, restore=False):
        if set(body) != {'ids'}:
            raise ValueError('归档请求仅接受数据列表。')
        with self.locked():
            rows = self._select(body)
            targets = self.targets(rows)
            for row in rows:
                key = self.key(row)
                if restore:
                    # Restoring one child must not restore its archived siblings.
                    parent = row.get('parent_key')
                    if parent in self.state['archived']:
                        saved = self.state['archived'].pop(parent)
                        for sibling in self._rows().values():
                            if sibling.get('parent_key') == parent:
                                self.state['archived'].setdefault(sibling['id'], saved.copy())
                    self.state['archived'].pop(key, None)
                    if row.get('kind') != 'report':
                        for child in self._rows().values():
                            if child.get('parent_key') == key:
                                self.state['archived'].pop(child['id'], None)
                else:
                    self.state['archived'].setdefault(key, {'archived_at': stamp()})
            self._save()
        return {'status': 'restored' if restore else 'archived', 'count': len(rows),
                'input_ids': targets['inputs'], 'intake_ids': targets['intakes'], 'job_ids': targets['jobs']}

    def _preview(self, body):
        rows = self._select(body, all_allowed=True)
        if not rows or any(not row.get('archived') for row in rows):
            raise ValueError('请先将数据归档，再从归档中删除。')
        targets = self.targets(rows)
        # Retests load their baseline evidence on demand. Do not break reports
        # outside the requested deletion scope by deleting their baseline.
        if any(j.get('baseline_job_id') in targets['package_jobs'] and j['id'] not in targets['package_jobs']
               for j in self.store.packages.jobs.values()):
            raise ValueError('该报告仍是其他复验报告的基线。请保留，或将关联复验报告一起归档后统一删除。')
        token = hashlib.sha256(json.dumps({'targets': targets, 'archived': {
            self.key(row): self.state['archived'].get(self.key(row), self.state['archived'].get(row.get('parent_key')))
            for row in rows}}, sort_keys=True).encode()).hexdigest()
        return rows, targets, token

    def preview(self, body):
        if set(body) - {'ids', 'all_archived'}:
            raise ValueError('删除预览仅接受数据列表。')
        with self.locked():
            rows, targets, token = self._preview(body)
            return {'token': token, 'items': len(rows), 'labels': [r['label'] for r in rows],
                    'runs': len(targets['jobs']) + len(targets['package_jobs']),
                    'records': len(targets['inputs']), 'batches': len(targets['batches']),
                    'reports_only': all(r['kind'] == 'report' for r in rows)}

    def _paths(self, targets):
        paths = []
        for group, directory, pattern, suffix in (
            ('jobs', 'jobs', r'[a-f0-9]{32}', ''), ('package_jobs', 'package_jobs', r'[a-f0-9]{32}', ''),
            ('batches', 'batches', r'[a-f0-9]{32}', '.json'),
            ('inputs', 'record-revisions', r'revision-[a-f0-9]{32}', '')):
            paths += [f'{directory}/{i}{suffix}' for i in targets[group] if re.fullmatch(pattern, i)]
        # An intake copy can back another NWB stream or another registered item.
        # Retain that shared directory until the last reference is deleted.
        remaining = [i for i in self.store.inputs.values() if i['id'] not in targets['inputs']]
        for identifier in targets['intakes']:
            if not re.fullmatch('[a-f0-9]{32}', identifier):
                raise ValueError('数据副本标识无效。')
            directory = self.store.intakes.root / identifier
            def uses(item):
                names = [item.get('source_path', '')] + [f.get('path', '') for f in item.get('expected_source_files', [])]
                return any(Path(name).is_relative_to(directory) for name in names if name)
            if not any(uses(item) for item in remaining):
                paths.append('intakes/' + identifier)
        return paths

    def apply_deleted(self):
        gone = self.state['deleted']
        for identifier in gone['inputs']:
            self.store.inputs.pop(identifier, None)
        for identifier in gone['packages']:
            self.store.packages.packages.pop(identifier, None)
        for job in list(self.store.jobs.values()):
            if job['id'] in gone['jobs'] or job['input_id'] in gone['inputs'] or (job.get('dataset_context') or {}).get('package_id') in gone['packages']:
                self.store.jobs.pop(job['id'], None)
                self.store.report_views.pop(job['id'], None)
        for job in list(self.store.packages.jobs.values()):
            if job['id'] in gone['package_jobs'] or job['package_id'] in gone['packages']:
                self.store.packages.jobs.pop(job['id'], None)
        for batch in list(self.store.batches.items.values()):
            if batch['package_id'] in gone['packages'] or any(r.get('request', {}).get('input_id') in gone['inputs'] for r in batch.get('records', [])):
                self.store.batches.items.pop(batch['id'], None)

    def cleanup(self):
        pending = []
        for relative in self.state['pending']:
            # No path submitted by the client or source manifest is removable.
            if not re.fullmatch(r'(?:jobs|package_jobs|intakes)/[a-f0-9]{32}|batches/[a-f0-9]{32}\.json|record-revisions/revision-[a-f0-9]{32}', relative):
                raise ValueError('无效的清理路径。')
            target = self.store.root / relative
            if target.parent.is_symlink():
                pending.append(relative)
                continue
            try:
                if target.is_symlink(): target.unlink()
                elif target.is_dir(): shutil.rmtree(target)
                elif target.exists(): target.unlink()
            except OSError:
                pending.append(relative)
        if pending != self.state['pending']:
            self.state['pending'] = pending
            self._save()
        return len(pending)

    def delete(self, body):
        if set(body) - {'ids', 'all_archived', 'token', 'confirmed'} or body.get('confirmed') is not True:
            raise ValueError('请确认彻底删除归档数据及全部检查记录和报告。')
        with self.locked():
            rows, targets, token = self._preview(body)
            if body.get('token') != token:
                raise ValueError('归档内容已变化，请重新查看删除范围。')
            paths = self._paths(targets)
            for group in ('inputs', 'packages', 'intakes', 'jobs', 'package_jobs'):
                self.state['deleted'][group] = sorted(set(self.state['deleted'][group]) | set(targets[group]))
            for key in targets['keys']:
                self.state['archived'].pop(key, None)
            for identifier in targets['jobs']:
                self.state['archived'].pop('report:' + identifier, None)
            for identifier in targets['package_jobs']:
                self.state['archived'].pop('package-report:' + identifier, None)
            self.state['pending'] = sorted(set(self.state['pending']) | set(paths))
            receipt = {'id': uuid.uuid4().hex, 'deleted_at': stamp(), 'items': len(rows),
                       'runs': len(targets['jobs']) + len(targets['package_jobs'])}
            self.state['deletions'].append(receipt)
            self._save()  # Tombstones commit before cleanup; restart cannot revive deleted data.
            self.apply_deleted()
            pending = self.cleanup()
            return {**receipt, 'status': 'deleted', 'cleanup_pending': pending,
                    'input_ids': targets['inputs'], 'intake_ids': targets['intakes'], 'job_ids': targets['jobs']}
