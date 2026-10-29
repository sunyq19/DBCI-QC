"""Read-only signal/candidate views and a separate, versioned human-review log.

No detector is called here. Original requests, results and method artifacts are
never rewritten. Times are recording-relative seconds; samples retain the native
source origin, including FIF first_samp and discontinuity segment boundaries.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import fcntl
import hashlib
import json
import math
import os
import re
import tempfile


SCHEMA_VERSION = 'review-workspace/1.0'
MAX_SECONDS = 10.0
MAX_CHANNELS = 16
MAX_POINTS = 2000
MAX_READ_BYTES = 64 * 1024 * 1024
MAX_JSON_BYTES = 256 * 1024 * 1024
DECISIONS = frozenset({'accepted', 'rejected', 'uncertain'})
BASE_ARTIFACTS = {
    'M03_continuity.json': ('M03', 'raw_continuity_review'),
    'M04_spectral.json': ('M04', 'line_noise'),
    'M05_bad_channels.json': ('M05', 'prep_nonspatial_review'),
    'M06_muscle.json': ('M06', 'high_frequency_burst'),
}
EXTENSION_ARTIFACTS = {
    'M03_mne_amplitude.json': ('M03', 'mne_amplitude'),
    'M03_autoreject_global.json': ('M03', 'autoreject_global'),
    'M05_mne_bridge.json': ('M05', 'mne_bridge'),
    'M05_mne_lof.json': ('M05', 'mne_lof'),
    'M06_mne_muscle.json': ('M06', 'mne_muscle'),
}


class ReviewConflict(ValueError):
    """The submitted expected_version is stale (HTTP 409)."""


def _json(path, default=None):
    path = Path(path)
    if not path.exists():
        if default is not None:
            return copy.deepcopy(default)
        raise ValueError('Required review evidence is unavailable')
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError('Review evidence must be a bounded regular JSON file')
    with path.open(encoding='utf-8') as source:
        return json.load(source)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be finite')
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be finite') from None
    if not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return value


def _channel_indices(value):
    if isinstance(value, str):
        if not re.fullmatch(r'\d+(?:,\d+)*', value):
            raise ValueError('channel_indices must be comma-separated source indices')
        value = [int(x) for x in value.split(',')]
    if (not isinstance(value, (list, tuple)) or not 1 <= len(value) <= MAX_CHANNELS or
            any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in value) or
            len(set(value)) != len(value)):
        raise ValueError('Select 1–16 distinct nonnegative source channel indices')
    return list(value)


def minmax_envelope(values, max_points=MAX_POINTS):
    """Return native offsets/values, keeping each bucket's extrema in time order.

    A non-finite marker is retained per affected bucket. This is a display
    envelope, not resampling or a replacement for the native signal. First and
    last samples are retained, and the output never exceeds max_points.
    """
    import numpy as np
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 8 <= max_points <= MAX_POINTS:
        raise ValueError('max_points must be an integer from 8 to 2000')
    data = np.asarray(values, dtype=float)
    if data.ndim != 1 or not len(data):
        raise ValueError('A display channel must contain native samples')
    if len(data) <= max_points:
        indices = list(range(len(data)))
    else:
        bins = max(1, (max_points - 2) // 3)
        edges = np.linspace(0, len(data), bins + 1, dtype=int)
        selected = {0, len(data) - 1}
        for left, right in zip(edges[:-1], edges[1:]):
            chunk = data[left:right]
            valid = np.flatnonzero(np.isfinite(chunk))
            if len(valid):
                selected.add(int(left + valid[np.argmin(chunk[valid])]))
                selected.add(int(left + valid[np.argmax(chunk[valid])]))
            invalid = np.flatnonzero(~np.isfinite(chunk))
            if len(invalid):
                selected.add(int(left + invalid[0]))
        indices = sorted(selected)
    output = [float(data[i]) if np.isfinite(data[i]) else None for i in indices]
    return indices, output


def _verify_sources(record, description, expected_source_files=None, expected_sha256=None):
    manifest = description.get('source_files', [])
    expected = expected_source_files
    if expected is None:
        expected = record.get('expected_source_files')
    if expected is None:
        expected = record.get('metadata', {}).get('source_files')
    verified = False
    if expected is not None:
        identity = lambda row: (row.get('name') or Path(row.get('path', '')).name, row.get('sha256'))
        if not expected or Counter(map(identity, expected)) != Counter(map(identity, manifest)):
            raise ValueError('Source package no longer matches the frozen input fingerprints')
        verified = True
    digest = expected_sha256 or record.get('expected_sha256')
    if digest:
        main = next((row for row in manifest if row.get('role') == 'main'), None)
        if main is None or main.get('sha256') != digest:
            raise ValueError('Source file no longer matches the frozen input fingerprint')
        verified = True
    return verified


def waveform_for_input(record, start_seconds=None, duration_seconds=None, channel_indices=None,
                       max_points=MAX_POINTS, channels=None, *, selection=None,
                       expected_source_files=None, expected_sha256=None, reader_factory=None):
    """Bounded physical waveform from a trusted registered/frozen input object.

    channel_indices accepts an integer list or a comma-separated string. channels
    is an alias. Every requested channel must belong to one native sampling
    stream and the interval must fit one continuous segment. No implicit crop,
    filtering, resampling, projections or reference change is performed.
    """
    if reader_factory is None:
        from ephys_qc.readers import open_reader
        reader_factory = open_reader
    selection = copy.deepcopy(selection if selection is not None else record.get('default_config', {}).get('selection', {}))
    if channels is not None:
        if channel_indices is not None:
            raise ValueError('Use channel_indices or channels, not both')
        channel_indices = channels
    if channel_indices is None:
        channel_indices = (selection.get('eeg_indices', []) + list(selection.get('reference_indices', {}).values()))[:MAX_CHANNELS]
        if not channel_indices:
            channel_indices = [c['index'] for c in record.get('metadata', {}).get('channels', [])][:MAX_CHANNELS]
    wanted = _channel_indices(channel_indices)
    start = _number(selection.get('start_seconds', 0) if start_seconds is None else start_seconds, 'start_seconds')
    duration = _number(min(MAX_SECONDS, selection.get('duration_seconds', MAX_SECONDS)) if duration_seconds is None else duration_seconds, 'duration_seconds')
    if start < 0 or not 0 < duration <= MAX_SECONDS:
        raise ValueError('Waveform duration must be >0 and <=10 seconds, with a nonnegative start')
    if isinstance(max_points, str) and max_points.isdigit():
        max_points = int(max_points)
    if isinstance(max_points, bool) or not isinstance(max_points, int) or not 8 <= max_points <= MAX_POINTS:
        raise ValueError('max_points must be an integer from 8 to 2000')
    reader = reader_factory(record['source_path'], str(record['id']))
    try:
        description = reader.describe()
        verified = _verify_sources(record, description, expected_source_files, expected_sha256)
        streams = [s for s in description['streams'] if set(wanted).issubset({c['source_index'] for c in s['channels']})]
        if len(streams) != 1:
            raise ValueError('Waveform channels must share exactly one native sampling stream')
        stream = streams[0]
        fs = float(stream['sampling_frequency_hz'])
        segments = [s for s in stream['segments'] if s['recording_start_seconds'] <= start + 1e-9 and
                    start + duration <= s['recording_start_seconds'] + (s['stop_sample'] - s['start_sample']) / fs + 1e-9]
        if len(segments) != 1:
            raise ValueError('Waveform interval must stay within one continuous source segment')
        segment = segments[0]
        first = segment['start_sample'] + round((start - segment['recording_start_seconds']) * fs)
        # Respect the hard 10-second cap even at non-integer native rates where
        # rounding a requested 10 seconds could otherwise return >10 seconds.
        stop = first + min(round(duration * fs), math.floor(MAX_SECONDS * fs + 1e-9))
        if first < segment['start_sample'] or stop > segment['stop_sample'] or stop <= first:
            raise ValueError('Waveform interval does not map to a valid native sample range')
        if len(wanted) * (stop - first) * 8 > MAX_READ_BYTES:
            raise ValueError('Waveform native read exceeds the 64 MiB resource limit')
        lookup = {c['source_index']: c for c in stream['channels']}
        selected = [lookup[i] for i in wanted]
        values = reader.read_window(stream['stream_id'], segment['segment_id'],
                                    [c['channel_id'] for c in selected], first, stop, 'physical')
        import numpy as np
        values = np.asarray(values)
        if values.shape != (len(wanted), stop - first):
            raise ValueError('Reader returned an unexpected waveform shape')
        actual_start = segment['recording_start_seconds'] + (first - segment['start_sample']) / fs
        rows = []
        for channel, data in zip(selected, values):
            offsets, display = minmax_envelope(data, max_points)
            # Keep physical reader units. Explicit voltage display conversion is
            # lossless scaling; arbitrary physical units are never relabeled V.
            physical_unit = channel.get('unit') or channel.get('physical_unit') or 'unknown'
            scale = 1e6 if physical_unit == 'V' else 1.0
            rows.append({'source_index': channel['source_index'], 'name': channel['raw_name'],
                         'channel_id': channel['channel_id'], 'physical_unit': physical_unit,
                         'unit': 'µV' if physical_unit == 'V' else physical_unit, 'display_scale': scale,
                         'times_seconds': [actual_start + i / fs for i in offsets],
                         'source_samples': [first + i for i in offsets],
                         'values': [v * scale if v is not None else None for v in display],
                         'nonfinite_sample_count': int(np.count_nonzero(~np.isfinite(data))),
                         'native_sample_count': len(data), 'display_point_count': len(offsets)})
        if hasattr(reader, 'assert_unchanged'):
            reader.assert_unchanged(hashes=True)
        return {'schema_version': SCHEMA_VERSION, 'input_id': record['id'],
                'requested_start_seconds': start, 'requested_duration_seconds': duration,
                'start_seconds': actual_start, 'stop_seconds': actual_start + (stop - first) / fs,
                'duration_seconds': (stop - first) / fs, 'start_sample': first, 'stop_sample': stop,
                'sampling_rate_hz': fs, 'stream_id': stream['stream_id'], 'segment_id': segment['segment_id'],
                'time_reference': 'recording_start_seconds', 'interval_convention': 'half_open',
                'channels': rows, 'display_method': 'minmax_envelope', 'analysis_modified': False,
                'frozen_source_verified': verified, 'selection': selection,
                'warnings': [] if verified else ['No frozen source fingerprint was available; this is a current-input preview.']}
    finally:
        reader.close()


def _mapping(request, selection_artifact, payload):
    mapping = payload.get('channel_mapping')
    if mapping:
        return {row['analysis_index']: row for row in mapping}
    channels = selection_artifact.get('channels', [])
    if channels:
        return {i: {'source_index': c['source_index'], 'raw_name': c['raw_name'], 'channel_id': c['channel_id']}
                for i, c in enumerate(channels)}
    selection = request.get('qc_config', request.get('plan', {}).get('qc_config', {})).get('selection', {})
    lookup = {c['index']: c for c in request.get('input', {}).get('metadata', {}).get('channels', [])}
    return {i: {'source_index': source, 'raw_name': lookup.get(source, {}).get('name', ''),
                'channel_id': f"{request['input']['id']}:ch:{source}"}
            for i, source in enumerate(selection.get('eeg_indices', []))}


def normalize_candidates(payload, *, module_id, method, request, selection_artifact=None,
                         artifact_name='', window_id=None):
    """Normalize only explicit detector candidates, never events or spectrum fits."""
    if not isinstance(payload, dict):
        raise ValueError('Candidate evidence must be a JSON object')
    selection_artifact = selection_artifact or {}
    mapping = _mapping(request, selection_artifact, payload)
    by_id = {c.get('channel_id'): c for c in mapping.values() if c.get('channel_id')}
    by_name = {}
    for c in mapping.values():
        by_name.setdefault(c.get('adapter_name', c.get('raw_name')), []).append(c)
    cfg = request.get('qc_config', request.get('plan', {}).get('qc_config', {}))
    selection = cfg.get('selection', {})
    recording = selection_artifact.get('recording', {})
    left = recording.get('start_seconds', selection.get('start_seconds'))
    duration = recording.get('duration_seconds', selection.get('duration_seconds'))
    whole = [left, left + duration] if _finite(left) and _finite(duration) else [None, None]
    if method == 'line_noise':
        raw_candidates = [(i, row) for i, row in enumerate(payload.get('line_noise', {}).get('observations', [])) if row.get('flagged') is True]
        pointer = '/line_noise/observations/'
    else:
        raw_candidates = list(enumerate(payload.get('candidates', [])))
        pointer = '/candidates/'
    output = []
    for position, raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        indices = raw.get('channel_indices')
        if indices is None:
            indices = [raw['channel_index']] if raw.get('channel_index') is not None else []
        channels = []
        if raw.get('channel_id') in by_id:
            channels = [by_id[raw['channel_id']]]
        else:
            channels = [mapping[i] for i in indices if isinstance(i, int) and not isinstance(i, bool) and i in mapping]
        if not channels and raw.get('channel_name') and len(by_name.get(raw['channel_name'], [])) == 1:
            channels = by_name[raw['channel_name']]
        start, stop = raw.get('start_seconds'), raw.get('stop_seconds')
        loc = raw.get('localization')
        whole_only = (loc in {'channel_only', 'pair_only'} or
                      (method == 'prep_nonspatial_review' and not raw.get('window_indices')) or
                      (method == 'line_noise' and not (_finite(start) and _finite(stop) and stop > start)))
        if whole_only:
            interval = raw.get('analysis_range', whole)
            start, stop = interval if isinstance(interval, list) and len(interval) == 2 else whole
            localization = 'whole_window' if _finite(start) and _finite(stop) else 'unknown'
        else:
            localization = 'interval' if _finite(start) and _finite(stop) and stop > start else 'unknown'
        if localization == 'unknown':
            start = stop = None
        evidence_values = {k: v for k, v in raw.items() if k not in {
            'scan_frequencies_hz', 'scan_f_statistics', 'scan_p_values', 'action', 'review_status'}}
        stable = {'window_id': window_id, 'artifact': artifact_name, 'position': position,
                  'method': method, 'candidate': evidence_values,
                  'source_indices': [c['source_index'] for c in channels],
                  'plan_id': request.get('plan', {}).get('plan_id'),
                  'data_sha256': payload.get('data_sha256', payload.get('input', {}).get('data_sha256')),
                  'parameters': payload.get('parameters', payload.get('config', {})),
                  'method_identity': payload.get('method', payload.get('method_version', payload.get('source')))}
        identifier = hashlib.sha256(_canonical(stable).encode()).hexdigest()[:32]
        reason = raw.get('reason') or raw.get('label') or raw.get('kind') or ('Narrow-band interference screening window' if method == 'line_noise' else method)
        output.append({'id': identifier, 'module_id': module_id, 'method': method,
                       'kind': raw.get('kind', 'line_noise' if method == 'line_noise' else method),
                       'channel_indices': [c['source_index'] for c in channels],
                       'channel_names': [c.get('raw_name', '') for c in channels],
                       'scope_channel_indices': [c['source_index'] for c in mapping.values()],
                       'start_seconds': start, 'stop_seconds': stop, 'localization': localization,
                       'interval_is_detection': localization == 'interval',
                       'reason': reason, 'status': 'pending', 'window_id': window_id,
                       'evidence': {'artifact': artifact_name, 'json_pointer': pointer + str(position),
                                    'values': evidence_values, 'parameters': payload.get('parameters', payload.get('config', {})),
                                    'localization_note': 'Whole analysis window; abnormal onset/offset was not localized.' if localization == 'whole_window' else '',
                                    'channel_mapping_status': 'resolved' if channels or not indices else 'unresolved'}})
    return output


class ReviewWorkspace:
    def __init__(self, job_dir, *, reader_factory=None):
        self.root = Path(job_dir).resolve()
        self.request = _json(self.root / 'request.json')
        self.reader_factory = reader_factory

    def _contexts(self):
        windows = self.root / 'windows'
        if windows.is_dir() and not windows.is_symlink():
            for directory in sorted(windows.iterdir()):
                if (re.fullmatch(r'w\d+', directory.name) and directory.is_dir() and not directory.is_symlink()
                        and (directory / 'request.json').is_file() and (directory / 'result.json').is_file()):
                    yield directory, directory.name, _json(directory / 'request.json')
        elif (self.root / 'result.json').is_file():
            yield self.root, None, self.request

    def _algorithm_candidates(self):
        candidates, warnings = [], []
        windows = self.root / 'windows'
        if windows.is_dir() and not windows.is_symlink():
            unfinished = [p.name for p in windows.iterdir() if re.fullmatch(r'w\d+', p.name) and p.is_dir()
                          and not p.is_symlink() and (p / 'request.json').is_file() and not (p / 'result.json').is_file()]
            if unfinished:
                warnings.append({'artifact': 'recording-progress.json', 'reason':
                                 f'{len(unfinished)} unfinished windows retain partial artifacts; these are not promoted to review candidates.',
                                 'window_ids': sorted(unfinished)})
        for directory, window_id, request in self._contexts():
            selection = _json(directory / 'artifacts' / 'M02_selection.json', {})
            result = _json(directory / 'result.json')
            states = {m['id']: m.get('status') for m in result.get('modules', [])}
            for filename, (module, method) in {**BASE_ARTIFACTS, **EXTENSION_ARTIFACTS}.items():
                path = directory / 'artifacts' / filename
                if not path.exists():
                    continue
                try:
                    if states.get(module) == 'failed':
                        warnings.append({'artifact': filename, 'reason': 'Failed module evidence is not promoted to review candidates.'})
                        continue
                    payload = _json(path)
                    if filename in EXTENSION_ARTIFACTS and payload.get('status') not in {'completed', 'partial'}:
                        continue
                    artifact = f'{window_id}--{filename}' if window_id else filename
                    normalized = normalize_candidates(payload, module_id=module, method=method, request=request,
                                                      selection_artifact=selection, artifact_name=artifact, window_id=window_id)
                    for item in normalized:
                        item['run_status'] = result.get('status', 'unknown')
                    candidates.extend(normalized)
                except (ValueError, TypeError, KeyError) as error:
                    warnings.append({'artifact': f'{window_id + "/" if window_id else ""}{filename}', 'reason': str(error)})
        candidates.sort(key=lambda c: (c['start_seconds'] is None, c['start_seconds'] or 0, c['module_id'], c['id']))
        return candidates, warnings

    def _log(self):
        log = _json(self.root / 'reviews.json', {'schema_version': SCHEMA_VERSION, 'version': 0, 'history': []})
        if (not isinstance(log, dict) or type(log.get('version')) is not int or log['version'] < 0 or
                not isinstance(log.get('history'), list) or log['version'] != len(log['history'])):
            raise ValueError('Review history is invalid; it has not been overwritten')
        for version, entry in enumerate(log['history'], 1):
            if (not isinstance(entry, dict) or entry.get('version') != version or
                    not isinstance(entry.get('candidate_id'), str) or
                    not isinstance(entry.get('decision'), str) or entry['decision'] not in DECISIONS or
                    not all(isinstance(entry.get(k), str) for k in ('note', 'reviewer', 'recorded_at'))):
                raise ValueError('Review history is invalid; it has not been overwritten')
        return log

    @staticmethod
    def _review_state(log, candidates):
        valid = {c['id'] for c in candidates}
        decisions = {entry['candidate_id']: copy.deepcopy(entry) for entry in log['history'] if entry['candidate_id'] in valid}
        counts = Counter(entry['decision'] for entry in decisions.values())
        counts = {'total': len(valid), 'pending': len(valid) - len(decisions), **{k: counts[k] for k in sorted(DECISIONS)}}
        status = 'no_candidates' if not valid else ('reviewed' if counts['pending'] == 0 and counts['uncertain'] == 0 else ('in_progress' if decisions else 'pending'))
        return {'schema_version': SCHEMA_VERSION, 'version': log['version'], 'decisions': decisions,
                'history': copy.deepcopy(log['history']), 'counts': counts, 'status': status,
                'orphaned_history_count': sum(row['candidate_id'] not in valid for row in log['history']),
                'algorithm_results_modified': False}

    def review(self):
        candidates, warnings = self._algorithm_candidates()
        return {**self._review_state(self._log(), candidates), 'warnings': warnings}

    def candidates(self):
        candidates, warnings = self._algorithm_candidates()
        state = self._review_state(self._log(), candidates)
        for candidate in candidates:
            decision = state['decisions'].get(candidate['id'])
            if decision:
                candidate.update(status=decision['decision'], review=decision)
        return {'schema_version': SCHEMA_VERSION, 'candidates': candidates, 'count': len(candidates),
                'warnings': warnings, 'review_version': state['version'], 'review_counts': state['counts'],
                'quality_pass': None, 'physiological_and_clinical_events_are_quality_candidates': False}

    def waveform(self, start_seconds=None, duration_seconds=None, channel_indices=None,
                 max_points=MAX_POINTS, channels=None):
        record = self.request['input']
        m01 = _json(self.root / 'artifacts' / 'M01_input.json', {})
        if not m01:
            # Whole-record parents retain the input snapshot; a completed child's
            # M01 adds the exact source-member manifest without changing clocks.
            context = next(self._contexts(), None)
            if context:
                m01 = _json(context[0] / 'artifacts' / 'M01_input.json', {})
        return waveform_for_input(record, start_seconds, duration_seconds, channel_indices, max_points, channels,
                                  selection=self.request.get('qc_config', {}).get('selection'),
                                  expected_source_files=m01.get('source_files'),
                                  expected_sha256=m01.get('source_sha256'), reader_factory=self.reader_factory)

    def update_review(self, body):
        if not isinstance(body, dict) or set(body) != {'expected_version', 'candidate_id', 'decision', 'note', 'reviewer'}:
            raise ValueError('Review requires expected_version, candidate_id, decision, note and reviewer')
        version = body['expected_version']
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise ValueError('expected_version must be a nonnegative integer')
        if not isinstance(body['decision'], str) or body['decision'] not in DECISIONS:
            raise ValueError('decision must be accepted, rejected or uncertain')
        if not isinstance(body['candidate_id'], str):
            raise ValueError('candidate_id must identify an existing algorithm candidate')
        if not isinstance(body['reviewer'], str) or not body['reviewer'].strip() or len(body['reviewer']) > 160:
            raise ValueError('reviewer must contain 1–160 characters')
        if not isinstance(body['note'], str) or len(body['note']) > 4000:
            raise ValueError('note must contain at most 4000 characters')
        lock_path = self.root / '.reviews.lock'
        if lock_path.is_symlink():
            raise ValueError('Review lock cannot be a symbolic link')
        with lock_path.open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            log = self._log()
            if log['version'] != version:
                raise ReviewConflict('Review version changed; reload before saving')
            candidates, warnings = self._algorithm_candidates()
            if body['candidate_id'] not in {c['id'] for c in candidates}:
                raise ValueError('candidate_id does not exist in this job\'s algorithm evidence')
            entry = {'version': version + 1, 'candidate_id': body['candidate_id'], 'decision': body['decision'],
                     'note': body['note'], 'reviewer': body['reviewer'].strip(),
                     'recorded_at': datetime.now(timezone.utc).isoformat()}
            log['history'].append(entry)
            log['version'] = version + 1
            descriptor, temporary = tempfile.mkstemp(prefix='.reviews-', suffix='.tmp', dir=self.root)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as destination:
                    destination.write(json.dumps(log, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
                    destination.flush()
                    os.fsync(destination.fileno())
                os.replace(temporary, self.root / 'reviews.json')
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            return {**self._review_state(log, candidates), 'warnings': warnings}
