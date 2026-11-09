"""Read-only report exploration. Native clocks, bounded reads, no QC execution."""
from review_workspace import _verify_sources, _channel_indices, MAX_READ_BYTES, MAX_POINTS

MAX_SECONDS = 60.0
MAX_CHANNELS = 15


def context(workspace):
    from ephys_qc.readers import open_reader
    from ephys_qc.source_selection import reader_kwargs, validate_frozen_stream
    record = workspace.request['input']
    selection = workspace.request.get('qc_config', {}).get('selection', {})
    validate_frozen_stream(record.get('metadata', {}), selection)
    m01 = workspace._waveform_sources()
    reader = (workspace.reader_factory or open_reader)(record['source_path'], str(record['id']),
                                                       **reader_kwargs(record.get('metadata', {})))
    try:
        description = reader.describe()
        verified = _verify_sources(record, description, m01.get('source_files'), m01.get('source_sha256'))
        if not verified:
            raise ValueError('未能核对原始记录，暂不能展开波形。')
        streams = []
        for stream in description['streams']:
            fs = float(stream['sampling_frequency_hz'])
            streams.append({
                'stream_id': stream['stream_id'], 'sampling_rate_hz': fs,
                'channels': [{'source_index': c['source_index'], 'channel_id': c['channel_id'],
                              'name': c['raw_name'], 'unit': c.get('unit') or c.get('physical_unit') or 'unknown'}
                             for c in stream['channels']],
                'segments': [{'segment_id': s['segment_id'], 'start_seconds': s['recording_start_seconds'],
                              'stop_seconds': s['recording_start_seconds'] + (s['stop_sample'] - s['start_sample']) / fs}
                             for s in stream['segments']],
            })
        reader.assert_unchanged() if hasattr(reader, 'assert_unchanged') else None
        return {'schema_version': 'waveform-explorer/1.0', 'streams': streams,
                'limits': {'max_seconds': MAX_SECONDS, 'max_channels': MAX_CHANNELS,
                           'max_points': MAX_POINTS, 'max_read_bytes': MAX_READ_BYTES},
                'checked_range': {'start_seconds': selection.get('start_seconds', 0),
                                  'duration_seconds': selection.get('duration_seconds')},
                'analysis_modified': False, 'frozen_source_verified': True}
    finally:
        reader.close()


def window(workspace, **query):
    # Explicit selection avoids the legacy preview's default first 16 channels.
    wanted = _channel_indices(query.get('channel_indices'))
    if len(wanted) > MAX_CHANNELS:
        raise ValueError('同屏最多对照 15 个通道。')
    wave = workspace.waveform(**query, _max_seconds=MAX_SECONDS, _include_psd=False)
    if not wave.get('frozen_source_verified'):
        raise ValueError('未能核对原始记录，暂不能展开波形。')
    # Browser only needs native-clock values, not duplicate sample indices or PSD.
    for channel in wave['channels']:
        channel.pop('psd', None)
        channel.pop('source_samples', None)
    return wave
