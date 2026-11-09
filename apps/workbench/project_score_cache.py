"""Explicit, derived score publications. Original detector files stay immutable."""
import copy
import json
from pathlib import Path

FILE = 'project-score-view.json'
SCHEMA = 'project-score-publication/1'


def _signature(root, names):
    result = {}
    for name in sorted(set(names)):
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Invalid score publication source')
        stat = path.stat()
        result[name] = [stat.st_size, stat.st_mtime_ns]
    return result


def load(store, identifier):
    """No detector reads or calculation on the report/navigation path."""
    return load_root(store.root / 'jobs' / identifier)


def load_root(root):
    """Share the validated publication with report evidence presentation."""
    path = root / FILE
    try:
        if path.is_symlink() or path.stat().st_size > 8*1024*1024: return None
        payload = json.loads(path.read_text())
        if payload.get('schema') != SCHEMA: return None
        if payload['signature'] != _signature(root, payload['signature']): return None
        return copy.deepcopy(payload['summary'])
    except (OSError, ValueError, KeyError, TypeError): return None


def publish(root, summary, config, *, published_at):
    """Used by an explicit publication command; never invoked by browsing."""
    from ephys_qc.project_scoring import apply_to_view
    from server import save_json
    root = Path(root)
    summary = copy.deepcopy(summary)
    view = apply_to_view(summary['report_view'], config)
    summary['report_view'] = view
    summary.pop('candidate_index', None)
    names = ['result.json', 'request.json'] + ['artifacts/' + name for name in view['source_fingerprints']]
    # Parent window manifests are also needed for exact coverage/identity.
    names += ['artifacts/' + a['name'] for a in summary.get('artifacts',[]) if a['name'].endswith('--result.json')]
    payload = dict(schema=SCHEMA,published_at=published_at,configuration=config,
                   signature=_signature(root,names),summary=summary)
    save_json(root / FILE, payload)
    return view
