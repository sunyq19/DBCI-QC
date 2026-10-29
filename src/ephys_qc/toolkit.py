"""Public, file-based QC interface. No web server, registry or GUI is required."""
import copy
import json
from pathlib import Path
import re

from .core import build_plan as _build_plan, catalog, run_job
from .readers import inspect_recording, list_readers, open_reader
from .recommendations import recommend


def _snapshot(value):
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _confirmed(record, config=None):
    if not isinstance(record, dict) or record.get('modality') != 'scalp_eeg':
        raise ValueError('Explicit scalp_eeg confirmation is required by the current toolkit')
    config = record.get('default_config', {}) if config is None else config
    metadata = record.get('metadata')
    if not isinstance(config, dict) or not isinstance(metadata, dict):
        raise ValueError('Configuration and technical metadata must be objects')
    selection = config.get('selection', {})
    rows = metadata.get('channels')
    if not isinstance(selection, dict) or not isinstance(rows, list) or any(not isinstance(c, dict) for c in rows):
        raise ValueError('selection must be an object and metadata.channels a list of channel objects')
    if any(type(c.get('index', c.get('source_index'))) is not int for c in rows):
        raise ValueError('Channel source indices must be integers')
    eeg = selection.get('eeg_indices', [])
    references = selection.get('reference_indices', {})
    if not isinstance(eeg, list) or not isinstance(references, dict):
        raise ValueError('eeg_indices must be a list and reference_indices an object')
    indices = eeg + list(references.values())
    if any(type(i) is not int for i in indices):
        raise ValueError('Selected source indices must be integers')
    channels = {c.get('index', c.get('source_index')): c for c in rows}
    voltage = {'V', 'mV', 'uV', 'µV', 'μV', 'nV'}
    if not indices or any(channels.get(i, {}).get('unit') not in voltage for i in indices):
        raise ValueError('Selected channels require explicit, verified voltage units')
    return record


def prepare_recording(source_path, *, record_id, modality, qc_config,
                      reference_scheme='unknown', label=None, provenance=None):
    """Inspect and fingerprint a source with caller-confirmed roles and selection.

    ``qc_config.selection`` must explicitly name ``eeg_indices``. The existing
    planner validates rates, time, roles and method parameters. No QC is run.
    Reader metadata cannot confirm electrode placement; modality is mandatory.
    """
    if modality != 'scalp_eeg':
        raise ValueError('Current QC requires explicit modality="scalp_eeg"; inspect other modalities separately')
    if not isinstance(record_id, str) or not record_id.strip():
        raise ValueError('record_id must be a nonempty stable identifier')
    if not isinstance(qc_config, dict):
        raise ValueError('qc_config must contain an explicit selection')
    source = Path(source_path)
    reader = open_reader(source, record_id)
    try:
        metadata = reader.metadata()
        files = copy.deepcopy(reader.describe()['source_files'])
        reader.assert_unchanged(hashes=True)
    finally:
        reader.close()
    source = source.resolve()
    digest = next(item['sha256'] for item in files if Path(item['path']).resolve() == source)
    record = _snapshot({'id': record_id, 'label': label or record_id,
                        'source_path': str(source), 'expected_sha256': digest,
                        'expected_source_files': files, 'metadata': metadata,
                        'modality': modality, 'modality_source': 'caller_confirmation',
                        'reference_scheme': reference_scheme, 'default_config': qc_config,
                        'provenance': provenance or {}})
    _confirmed(record)
    # Empty optional selection validates the record without selecting algorithms.
    build_plan(record, selected_modules=[])
    return record


def _source_paths(record):
    files = record.get('expected_source_files')
    if not isinstance(files, list) or not files:
        raise ValueError('A frozen source manifest is required; use prepare_recording first')
    expected = record.get('expected_sha256')
    if not isinstance(expected, str) or not re.fullmatch(r'[0-9a-f]{64}', expected):
        raise ValueError('A source SHA-256 fingerprint is required')
    main = Path(record['source_path']).resolve()
    paths = []
    for entry in files:
        if not isinstance(entry, dict) or not isinstance(entry.get('sha256'), str) or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256']):
            raise ValueError('Invalid frozen source manifest')
        path = Path(entry['path']).resolve()
        if path in paths:
            raise ValueError('Duplicate source in frozen manifest')
        if path == main and entry['sha256'] != expected:
            raise ValueError('Main source and manifest fingerprints disagree')
        paths.append(path)
    if main not in paths:
        raise ValueError('Main source is absent from frozen manifest')
    annotation = record.get('annotation') or {}
    if not isinstance(annotation, dict):
        raise ValueError('annotation must be an object')
    paths.extend(Path(annotation[key]).resolve() for key in ('path', 'source_path') if annotation.get(key))
    return paths


def build_plan(record, selected_modules, qc_config=None):
    """Plan explicitly selected modules for a confirmed, fingerprinted record."""
    record = _snapshot(record)
    if not isinstance(selected_modules, (list, tuple)) or any(not isinstance(m, str) for m in selected_modules):
        raise ValueError('selected_modules must be an explicit list of module IDs')
    _confirmed(record)
    _source_paths(record)
    plan = _build_plan(record, list(selected_modules), _snapshot(qc_config) if qc_config is not None else None)
    _confirmed(record, plan['qc_config'])
    return plan


def run_modules(record, output_dir, selected_modules, *, qc_config=None, emit=None):
    """Execute selected modules and required dependencies into a NEW directory.

    Returns the normal JSON-compatible pipeline result, including all module
    states. ``selected_modules`` must be explicit; [] runs only entry/exit nodes.
    Sources are read in place. A previous or partial output is never overwritten.
    Scientific failures are recorded in the result; callers must inspect status.
    """
    record = _snapshot(record)
    if emit is not None and not callable(emit):
        raise ValueError('emit must be a callback or None')
    plan = build_plan(record, selected_modules, qc_config)
    root = Path(output_dir).resolve()
    for path in _source_paths(record):
        if root == path or root in path.parents or path in root.parents:
            raise ValueError('Output must be separate from sources and annotations')
    request = _snapshot({'input': record, 'plan': plan, 'qc_config': plan['qc_config'],
                         'selected_modules': plan['selected_modules']})
    root.mkdir(parents=True, exist_ok=False)
    (root / 'request.json').write_text(json.dumps(request, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    try:
        return run_job(request, root, emit or (lambda *event: None))
    except Exception as error:
        (root / 'error.json').write_text(json.dumps({'type': type(error).__name__, 'message': str(error)}, ensure_ascii=False) + '\n', encoding='utf-8')
        raise


def run_module(module_id, record, output_dir, *, qc_config=None, emit=None):
    """Run one requested module with its dependency closure and evidence report.

    For example M06 also runs M03; M01/M02/M08/M09 remain mandatory. Inspect
    ``result['selected_modules']`` for the actual execution scope.
    """
    return run_modules(record, output_dir, [module_id], qc_config=qc_config, emit=emit)


__all__ = ['catalog', 'list_readers', 'inspect_recording', 'prepare_recording',
           'recommend', 'build_plan', 'run_modules', 'run_module']
