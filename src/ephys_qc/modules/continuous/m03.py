"""M03 continuous voltage: nonfinite runs and exact adjacent equality, without scalp thresholds."""
from .common import method_prefix, identity, inputs, interval, provenance, run_bounds

# Evidence storage budget, not a signal-quality threshold. Counts remain exact.
MAX_REVIEW_CANDIDATES = 10000


def run(context):
    import numpy as np
    data, fs, config = inputs(context)
    state = context.state
    candidates, channels = [], []
    observed_count = 0
    for index, values in enumerate(data):
        ident = identity(state, index)
        finite = np.isfinite(values)
        equal = finite[:-1] & finite[1:] & (values[:-1] == values[1:])
        counts = {}
        for kind, mask, stop_extra in [('nonfinite_samples', ~finite, 0), ('exact_constant_samples', equal, 1)]:
            starts, stops = run_bounds(mask)
            counts[kind] = len(starts)
            observed_count += len(starts)
            keep = min(len(starts), MAX_REVIEW_CANDIDATES - len(candidates))
            for first, stop in zip(starts[:keep], stops[:keep] + stop_extra):
                location = interval(state, first, stop)
                candidates.append({**ident, **location,
                    'candidate_id': f"{method_prefix(context)}-continuity:{ident['channel_id']}:{location['start_sample']}:{location['stop_sample']}:{kind}",
                    'kind': kind, 'action': 'review', 'sample_count': int(stop - first),
                    'review_status': 'pending', 'quality_label': None,
                    'interpretation': 'Observed source samples; not a confirmed artifact or deletion instruction'})
        channels.append({**ident, 'sample_count': len(values), 'finite_sample_count': int(finite.sum()),
                         'nonfinite_sample_count': int((~finite).sum()), 'nonfinite_run_count': counts['nonfinite_samples'],
                         'exact_constant_run_count': counts['exact_constant_samples']})
    payload = {**provenance(context, data), 'method': method_prefix(context) + '_source_continuity', 'channels': channels,
               'candidate_total_count': observed_count, 'candidate_details_truncated': observed_count > len(candidates),
               'candidates': candidates, 'parameters': {'constant_rule': 'exact_equal_adjacent_finite_samples',
                 'minimum_constant_samples': 2, 'amplitude_threshold': None, 'minimum_duration_seconds': None},
               'candidate_evidence': {'observed_interval_count': observed_count, 'stored_interval_count': len(candidates),
                   'omitted_interval_count': observed_count-len(candidates), 'truncated': observed_count > len(candidates),
                   'storage_limit': MAX_REVIEW_CANDIDATES, 'ordering': 'source selection order, nonfinite then constant runs, chronological within kind',
                   'scope': 'All samples scanned; detailed review locations limited to stored candidates'},
               'notes': ['Exact equality can reflect quantization or physiology; candidates require source review.',
                         'No endpoint, near-zero, scalp amplitude or clinical-event threshold is applied.']}
    context.state['continuity_candidates'] = candidates
    context.save('M03_continuity.json', payload)
    context.row['summary'] = {'analysis_profile': payload['analysis_profile'], 'candidate_count': len(candidates),
        'kinds': sorted({c['kind'] for c in candidates}), 'nonfinite_sample_count': sum(c['nonfinite_sample_count'] for c in channels),
        'candidate_evidence': payload['candidate_evidence'],
        'candidate_total_count': observed_count, 'candidate_details_truncated': observed_count > len(candidates),
        'automatic_exclusions': 0, 'quality_classification': False, 'scalp_thresholds_used': False}
    if observed_count > len(candidates):
        context.row.update(status='partial', reason='已扫描全部样本；详细候选位置达到存储预算，省略数量及每道完整计数已保存，不能把未存位置视为正常。')
        context.result.setdefault('warnings', []).append('M03: ' + context.row['reason'])
    return context.row
