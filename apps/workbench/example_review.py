"""Frozen example findings with optional, verified, read-only source exploration.

The published bundle contains no signal samples or machine paths. Only explicitly
configured example sources can supply waveforms; no runtime job is required.
"""
import copy
import json
from pathlib import Path

from example_cache import asset
from review_workspace import ReviewWorkspace


def snapshot(workspace):
    from finding_locations import locations
    record = workspace.request['input']
    metadata = record.get('metadata', {})
    selection = workspace.request.get('qc_config', {}).get('selection', {})
    source = workspace._waveform_sources()
    members = [{'name': row.get('name') or Path(row['path']).name,
                'sha256': row['sha256']} for row in source.get('source_files', [])]
    digest = source.get('source_sha256') or record.get('expected_sha256')
    if not digest:
        raise ValueError('Example exploration requires a frozen source fingerprint')
    return {
        'schema_version': 'example-review/1',
        'context': workspace.waveform_context(),
        'findings': locations(workspace),
        'input': {'id': record['id'], 'expected_sha256': digest,
                  'metadata': {k: metadata[k] for k in ('format', 'selected_stream_id', 'capabilities', 'channels') if k in metadata}},
        'selection': {k: selection[k] for k in ('start_seconds', 'duration_seconds', 'eeg_indices', 'reference_indices', 'stream_id') if k in selection},
        'source': {'source_sha256': digest, **({'source_files': members} if members else {})},
    }


def read(store, release, job_id):
    path = asset(store, f'/examples/{release}/review/{job_id}.json')
    if path.stat().st_size > 32 * 1024**2:
        raise ValueError('Example review snapshot exceeds the size limit')
    value = json.loads(path.read_text())
    if value.get('schema_version') != 'example-review/1':
        raise ValueError('Unsupported example review snapshot')
    return value


class ExampleWorkspace(ReviewWorkspace):
    def __init__(self, store, saved):
        record = copy.deepcopy(saved['input'])
        digest = saved['source']['source_sha256']
        configured = store.settings.get('example_review_sources', {}).get(digest)
        if not configured or not Path(configured).is_file():
            raise ValueError('此服务尚未配置对应的示例信号文件；已保存的检查结果仍可查看。')
        record['source_path'] = configured
        self.request = {'input': record, 'qc_config': {'selection': copy.deepcopy(saved['selection'])}}
        self.source = saved['source']
        self.reader_factory = None

    def _waveform_sources(self):
        return self.source


def response(store, release, job_id, action, query=None):
    saved = read(store, release, job_id)
    if action == 'finding-locations':
        return saved['findings']
    if action == 'waveform-context':
        # Both findings and channel/clock metadata remain available offline.
        # The window reader verifies the configured source before returning samples.
        result = copy.deepcopy(saved['context'])
        path = store.settings.get('example_review_sources', {}).get(saved['source']['source_sha256'])
        result['waveform_available'] = bool(path and Path(path).is_file())
        return result
    if action != 'waveform-window':
        raise KeyError(action)
    return ExampleWorkspace(store, saved).waveform_window(**(query or {}))
