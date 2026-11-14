"""Separate quantization measurements from localized Neuropixels findings."""


def neuropixels_locations(payload):
    """Project frozen evidence without changing measurements or saved scores.

    Old artifacts stored every equal-value run. Those are not evidence of a
    dropout. Channel summaries recover whole-block constants even when the
    original location storage budget was exhausted by short repeats.
    """
    if payload.get('modality') != 'extracellular':
        return payload
    rows = payload.get('channels', [])
    if not rows or any('fully_constant' not in r for r in rows):
        return payload  # Older evidence without the needed facts stays explicit.
    candidates = [r for r in payload.get('candidates', []) if r.get('kind') != 'exact_constant_samples']
    span = payload.get('input_range', {})
    for row in rows:
        if row['fully_constant']:
            candidates.append({**row, **span, 'kind': 'constant_analysis_block'})
    nonfinite_runs = sum(r.get('nonfinite_run_count', 0) for r in rows)
    located_nonfinite = sum(r.get('kind') == 'nonfinite_samples' for r in candidates)
    incomplete = located_nonfinite < nonfinite_runs
    return {**payload, 'candidates': candidates,
            'candidate_details_truncated': incomplete,
            'candidate_evidence': {**payload.get('candidate_evidence', {}), 'truncated': incomplete},
            'location_policy': 'nonfinite_and_constant_blocks',
            'measurement_summary': {
                'nonfinite_sample_count': sum(r.get('nonfinite_sample_count', 0) for r in rows),
                'constant_channel_blocks': sum(bool(r['fully_constant']) for r in rows),
                'max_equal_seconds': max((r.get('max_exact_constant_run_seconds', 0) for r in rows), default=0),
                'adjacent_equal_runs': sum(r.get('exact_constant_run_count', 0) for r in rows)}}
