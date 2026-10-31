"""Source identity and JSON-safe helpers for declared continuous voltage routes."""
import hashlib
import math

from ...modalities import DESCRIPTIVE, route, validate_descriptive_methods


def inputs(context):
    import numpy as np
    modality = context.record.get('modality')
    if modality not in DESCRIPTIVE:
        raise ValueError('Continuous handlers require explicit ECoG, sEEG or supported Neuropixels voltage modality')
    config = validate_descriptive_methods(context.config['method_config'], modality, context.record.get('metadata'))[route(modality)['key']]
    state = context.state
    data = np.asarray(state['data'])
    if data.ndim != 2 or not data.size or data.dtype.kind not in 'fiu':
        raise ValueError('Continuous measurements require real channel-by-sample voltage data')
    if len(state['channels']) != len(data):
        raise ValueError('Source-channel identity does not match loaded values')
    fs = float(state['fs'])
    if not math.isfinite(fs) or fs <= 0:
        raise ValueError('Continuous measurements require a finite positive native rate')
    return data, fs, config


def identity(state, index):
    channel = state['channels'][index]
    return {'channel_index': index, 'channel_id': channel['channel_id'],
            'channel_name': channel['raw_name'], 'source_index': channel['source_index']}


def interval(state, first, stop):
    return {'start_offset': int(first), 'stop_offset': int(stop),
            'start_sample': state['first'] + int(first), 'stop_sample': state['first'] + int(stop),
            'start_seconds': state['start'] + first / state['fs'],
            'stop_seconds': state['start'] + stop / state['fs'],
            'duration_seconds': (stop - first) / state['fs']}


def provenance(context, data):
    state = context.state
    modality = context.record['modality']
    info = route(modality)
    import numpy as np
    # Preserve the existing ECoG evidence schema and IDs during kernel consolidation.
    extra = {} if modality == 'ecog' else {
            'acquisition': context.record.get('metadata', {}).get('acquisition', {}),
            **({'selected_stream_id': context.record['metadata']['selected_stream_id']}
               if context.record.get('metadata', {}).get('format') == 'NWB' else {})}
    return {'schema_version': info['key'] + '-measurement/1.0', 'analysis_profile': info['profile'], 'modality': modality,
            **extra,
            'data_sha256': hashlib.sha256(np.ascontiguousarray(data, dtype='<f8').tobytes()).hexdigest(),
            'input_range': interval(state, 0, data.shape[1]), 'sampling_rate_hz': state['fs'], 'unit': 'V',
            'source_indices': [c['source_index'] for c in state['channels']],
            'processing_applied_to_source': [], 'quality_labels_used_for_detection': False,
            'assessment_scope': 'descriptive_measurements_not_quality_classification'}


def finite_float(value):
    value = float(value)
    return value if math.isfinite(value) else None


def run_bounds(mask):
    import numpy as np
    changes = np.diff(np.r_[False, mask, False].astype('int8'))
    return np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)


def method_prefix(context):
    return route(context.record["modality"])["key"]
