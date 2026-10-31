"""M05 continuous voltage: per-contact finite-sample statistics, without bad-channel thresholds."""
from .common import method_prefix, finite_float, identity, inputs, provenance


def run(context):
    import numpy as np
    data, fs, config = inputs(context)
    channels = []
    for index, values in enumerate(data):
        valid = values[np.isfinite(values)]
        with np.errstate(over='ignore', invalid='ignore'):
            stats = {'mean_volts': finite_float(np.mean(valid)), 'std_volts': finite_float(np.std(valid)),
                     'rms_volts': finite_float(np.sqrt(np.mean(valid ** 2))), 'peak_to_peak_volts': finite_float(np.ptp(valid))} if valid.size else {
                         key: None for key in ('mean_volts', 'std_volts', 'rms_volts', 'peak_to_peak_volts')}
        channels.append({**identity(context.state, index), 'sample_count': len(values),
                         'finite_sample_count': int(valid.size), 'nonfinite_sample_count': int(len(values) - valid.size),
                         'statistics_scope': 'finite_samples_only', **stats,
                         'status': 'computed' if valid.size and all(v is not None for v in stats.values()) else 'unassessed',
                         'quality_label': None})
    payload = {**provenance(context, data), 'method': method_prefix(context) + '_contact_description', 'channels': channels,
        'candidates': [], 'classification_performed': False, 'thresholds': None,
        'notes': ['Each source contact is described independently; no cross-contact similarity or geometry is inferred.',
                  'Amplitude, high-frequency and disease differences do not assign a bad-contact label.']}
    context.save('M05_channel_description.json', payload)
    context.row['summary'] = {'analysis_profile': payload['analysis_profile'], 'described_channel_count': len(channels),
        'unassessed_channel_count': sum(c['status'] != 'computed' for c in channels),
        'nonfinite_sample_count': sum(c['nonfinite_sample_count'] for c in channels),
        'quality_classification': False, 'cross_channel_comparison': False, 'scalp_thresholds_used': False}
    if any(c['status'] != 'computed' or c['nonfinite_sample_count'] for c in channels):
        context.row.update(status='partial', reason='部分触点含非有限样本或数值不可评；统计范围明确为有限样本，不作坏触点结论。')
    return context.row
