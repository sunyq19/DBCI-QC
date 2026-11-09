"""Disposable, persistent display cache. Never changes detector evidence or scores."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from weakref import WeakValueDictionary

_LOCK = threading.RLock()
_KEY_LOCKS = WeakValueDictionary()
MAX_BYTES = 16 * 1024 * 1024


def stamps(paths):
    rows = []
    for path in sorted(set(map(Path, paths))):
        try:
            s = path.stat()
            rows.append([str(path), s.st_size, s.st_mtime_ns, s.st_ctime_ns])
        except OSError:
            rows.append([str(path), None])
    return rows


def job_signature(root, *, code=()):
    # Published display revisions and source evidence invalidate derived figures.
    paths = [root / n for n in ('request.json', 'result.json', 'project-score-view.json')]
    paths += list((root / 'artifacts').glob('*'))
    return stamps(paths + list(code))


def cached(root, key, signature, build):
    """Atomic bounded payload; cached images are verified, saved report evidence.

    Serving them later does not claim that the original signal still exists.
    Read-only archives can still render, without a writable cache directory.
    """
    folder = Path(root) / 'presentation-cache'
    path = folder / (hashlib.sha256(key.encode()).hexdigest() + '.json')
    digest = hashlib.sha256(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    with _LOCK:
        lock = _KEY_LOCKS.get(str(path))
        if lock is None:
            lock = threading.RLock()
            _KEY_LOCKS[str(path)] = lock
    with lock:
        try:
            if not path.is_symlink() and path.stat().st_size <= MAX_BYTES * 2:
                saved = json.loads(path.read_text())
                if saved.get('signature') == digest:
                    return base64.b64decode(saved['payload'], validate=True)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        data = build()
        if data and len(data) <= MAX_BYTES:
            try:
                folder.mkdir(exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', dir=folder, delete=False) as f:
                    json.dump({'signature': digest, 'payload': base64.b64encode(data).decode()}, f)
                    tmp = Path(f.name)
                tmp.replace(path)
            except OSError:
                pass
        return data


def gallery(store, identifier, query):
    from visualization_page import build_gallery
    from ephys_qc.visualizations import render, evidence, catalog
    from ephys_qc import report_view
    root = store.root / 'jobs' / identifier
    code = [Path(m.__file__) for m in (render, evidence, catalog, report_view)]
    code += [Path(__file__), Path(__file__).with_name('visualization_page.py')]
    return cached(root, 'gallery:' + json.dumps(query, sort_keys=True), job_signature(root, code=code),
                  lambda: build_gallery(store, identifier, query).encode())


def load_evidence(store, identifier, name):
    from ephys_qc.visualizations import evidence
    target = store.artifact(identifier, name)  # Authorize before touching a cache.
    raw = cached(store.root / 'jobs' / identifier, 'evidence:' + name,
                 stamps([target, Path(evidence.__file__)]),
                 lambda: json.dumps(evidence.read_evidence(target), allow_nan=False).encode())
    return json.loads(raw)


def focus(store, identifier, view, index):
    from ephys_qc import report_presentation, report_export
    from ephys_qc.report_presentation import focused_figure
    root = store.root / 'jobs' / identifier
    code = [Path(m.__file__) for m in (report_presentation, report_export)] + [Path(__file__)]
    return cached(root, 'focus:' + str(index), job_signature(root, code=code),
                  lambda: focused_figure(view, store.workspace(identifier), index)[0])


def prepare(store, identifier):
    """Warm the default embedded charts and all bounded waveform targets."""
    from saved_reports import frozen_view
    from project_score_cache import load
    from ephys_qc.report_presentation import focus_targets
    from finding_locations import locations
    locations(store.workspace(identifier))
    gallery(store, identifier, {'embedded': ['1']})
    published = load(store, identifier)
    view = published.get('report_view') if published else frozen_view(store, identifier)
    for i, _ in enumerate(focus_targets(view or {})):
        focus(store, identifier, view, i)
