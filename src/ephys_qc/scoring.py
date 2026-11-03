"""Project-defined EEG candidate-burden score. Not an acceptance standard.

Pool native evidence within each channel first. Across channels use RMS burden;
across dimensions use the minimum score. No learned weights or hidden cutoffs.
"""
import math

SCORE_VERSION = 'eeg-basic-screen/0.2'
COMPONENTS = (
    ('integrity', '信号完整性', 'channel_samples'),
    ('line_noise', '工频干扰', 'channel_windows'),
    ('hf_burst', '高频突发', 'channel_seconds'),
)


def burden_score(evidence, expected_channels, *, expected_windows=1, coverage_complete=True):
    """Missing/invalid identities or measurements never become zero burden.

    Evidence numerator is the observed noncandidate amount; denominator is the
    method-valid amount. ``windows`` counts successful windows for this channel.
    """
    ids = [r.get('channel_id') for r in evidence]
    identities_ok = (expected_channels > 0 and len(ids) == expected_channels and
                     all(isinstance(cid, str) and cid for cid in ids) and
                     len(set(ids)) == len(ids))
    parts = []
    for key, name, unit in COMPONENTS:
        rows = []
        for row in evidence:
            part = row.get('components', {}).get(key, {})
            good, total = part.get('numerator'), part.get('denominator')
            if (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                        for v in (good, total)) or total <= 0 or not 0 <= good <= total or
                    part.get('windows', 1) != expected_windows):
                continue
            rows.append({'channel_id': row['channel_id'], 'name': row['name'],
                         'burden': (total-good)/total, 'numerator': good, 'denominator': total})
        n = len(rows)
        available = identities_ok and n == expected_channels and expected_windows > 0
        good = math.fsum(r['numerator'] for r in rows)
        total = math.fsum(r['denominator'] for r in rows)
        rms = math.sqrt(math.fsum(r['burden']**2 for r in rows)/n) if available else None
        worst = max(rows, key=lambda r: r['burden']) if rows else None
        parts.append(dict(id=key, name=name, unit=unit,
            value=100*(1-rms) if rms is not None else None,
            numerator=good, denominator=total, assessed_channels=n,
            aggregation='rms_channel_burden', rms_burden=rms,
            mean_channel_burden=math.fsum(r['burden'] for r in rows)/n if available else None,
            pooled_unflagged_percent=100*good/total if total else None,
            affected_channels=sum(r['burden'] > 0 for r in rows), worst_channel=worst))
    available = coverage_complete and all(p['value'] is not None for p in parts)
    value = min(p['value'] for p in parts) if available else None
    limiting = [p['id'] for p in parts if value is not None and math.isclose(p['value'], value, abs_tol=1e-9)]
    return dict(version=SCORE_VERSION, name='EEG 基础质控评分', status='project_trial',
                value=value, components=parts, limiting_components=limiting,
                aggregation='channel_pool_then_rms_then_min', aggregation_version='eeg-pooling/2',
                expected_channels=expected_channels, expected_windows=expected_windows,
                coverage_complete=coverage_complete, calibration='not_expert_calibrated',
                hf_valid_channel_seconds=parts[2]['denominator'],
                hf_candidate_channel_seconds=parts[2]['denominator']-parts[2]['numerator'])


def score_revision(result, current):
    """Describe a new display calculation without replacing frozen run evidence."""
    previous = result.get('report_view', {}).get('score', {})
    if previous.get('version') and previous['version'] != current['version']:
        return {'previous_version': previous['version'], 'previous_value': previous.get('value'),
                'current_version': current['version'], 'mode': 'recomputed_from_frozen_evidence'}
    return None
