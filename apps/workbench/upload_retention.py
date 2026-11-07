"""Seven-day retention of explicitly owned uploads, never of linked originals.

Legacy intakes have no ownership receipt and are deliberately outside this policy.
Reports, job evidence and confirmation records live outside the deleted payloads.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import re
import shutil

DAYS = 7
ACTIVE = {'queued', 'running', 'cancelling'}


def receipt(directory, source, received_at):
    received = datetime.fromisoformat(received_at)
    # Only these paths were created by uploads.prepare_source for this request.
    payloads = ['payload', 'original.zip'] if (directory / 'original.zip').is_file() else [source.name]
    return {'policy': 'upload-copy/1', 'days': DAYS, 'state': 'available',
            'expires_at': (received + timedelta(days=DAYS)).isoformat(), 'owned_payloads': payloads}


def is_user_upload(item):
    return item.get('library_origin') == 'user_upload'


def expire_uploads(intakes, *, protected_families=(), at=None):
    """Caller holds the store lock shared with registration/job admission."""
    from intake import _save
    at = at or datetime.now(timezone.utc)
    protected = set(protected_families)
    if intakes.root.is_symlink(): return []
    expired = []
    for path in intakes.root.glob('*/intake.json'):
        directory = path.parent
        if directory.is_symlink() or path.is_symlink() or not re.fullmatch('[a-f0-9]{32}', directory.name):
            continue
        value = json.loads(path.read_text())
        policy = value.get('retention') or {}
        family = 'local-' + directory.name
        if (not is_user_upload(value) or value.get('linked_root') or family in protected or
                policy.get('policy') != 'upload-copy/1' or policy.get('state') == 'expired'):
            continue
        deadline = datetime.fromisoformat(policy['expires_at'])
        if deadline.tzinfo is None or deadline > at: continue
        names = policy.get('owned_payloads', [])
        if not names or any(not (name in {'payload', 'original.zip'} or
                                re.fullmatch(r'source\.(edf|bdf|vhdr|set|fif|nwb)', name)) for name in names):
            continue
        removed = []
        for name in names:
            target = directory / name
            # Unlink a replaced symlink itself; never follow it to user originals.
            if target.is_symlink(): target.unlink()
            elif target.is_dir(): shutil.rmtree(target)
            elif target.exists(): target.unlink()
            removed.append(name)
        policy.update(state='expired', expired_at=at.isoformat(), removed_payloads=removed)
        if value['status'] == 'needs_confirmation': value['status'] = 'expired'
        _save(path, value)
        record_path = directory / 'record.json'
        if record_path.is_file() and not record_path.is_symlink():
            record = json.loads(record_path.read_text()); record['retention'] = policy
            _save(record_path, record)
        expired.append({'family': family, 'retention': policy})
    return expired
