"""Initial Neuropixels voltage score; channel evidence is unioned, never summed."""
import copy
import math

VERSION = 'neuropixels-score/0.1'
PRESET = 'neuropixels-voltage-score/0.1'
NUMERIC = 'neuropixels_numeric_integrity'
CONSTANT = 'neuropixels_constant_channels'
STATE = 'neuropixels_channel_state'
AP = 'spikeinterface_bad_channels'
EVIDENCE = (CONSTANT, AP)


def default_config():
    return {'version': 'project-weighted/1.2', 'preset': PRESET,
            'weights': {NUMERIC: 30, STATE: 70}}


def validate_family_weights(weights):
    if sum(weights.get(k, 0) > 0 for k in (STATE, *EVIDENCE)) > 1:
        raise ValueError('通道状态及其恒值/AP离群证据只能计入一次；请选择合并项或单独一个原始检查项。')


def continuity_outputs(payload, recording, artifact):
    from .ieeg_scoring import numeric_output
    from .method_scores import observation
    from .score_registry import SPECS
    numeric = numeric_output(payload, recording, artifact, spec_id=NUMERIC)
    rows = payload.get('channels', [])
    valid = numeric['value'] is not None and numeric['candidate_amount'] == 0 and all(
        type(r.get('fully_constant')) is bool and type(r.get('max_exact_constant_run_samples')) is int
        and r['sample_count'] >= 2 and 0 <= r['max_exact_constant_run_samples'] <= r['finite_sample_count']
        and r['fully_constant'] == (r['max_exact_constant_run_samples'] == r['sample_count']) for r in rows)
    out = observation(SPECS[CONSTANT], sum(r['fully_constant'] for r in rows) if valid else None,
        len(rows) if valid else None, artifact=artifact, scope=payload.get('input_range', {}),
        reason='整分析窗保持同一有限值的通道比例；短量化重复不扣分。' if valid else '含非有限样本，或整窗恒值汇总/通道身份缺失；此项未评。')
    if valid:
        out['channel_evidence'] = {'assessed': [r['channel_id'] for r in rows],
                                  'candidates': [r['channel_id'] for r in rows if r['fully_constant']]}
    return [numeric, out]


def attach_ap_identity(row, payload):
    """A legacy AP fraction is retained, but cannot enter a union without identities."""
    mapping = payload.get('channel_mapping', [])
    names = payload.get('channel_names', [])
    if (row['value'] is not None and len(mapping) == len(names)
            and {r.get('adapter_name') for r in mapping} == set(names)
            and all(isinstance(r.get('channel_id'), str) and r['channel_id'] for r in mapping)
            and len({r['channel_id'] for r in mapping}) == len(names)):
        ids = {r['adapter_name']: r['channel_id'] for r in mapping}
        row['channel_evidence'] = {'assessed': list(ids.values()),
                                  'candidates': sorted({ids[c['channel_name']] for c in payload['candidates']})}
    return row


def _identities(row):
    from .method_scores import number
    if not row or row.get('status') != 'computed' or not number(row.get('value')):
        return None
    evidence = row.get('channel_evidence', {})
    assessed, candidates = evidence.get('assessed'), evidence.get('candidates')
    if not isinstance(assessed, list) or not assessed or not isinstance(candidates, list): return None
    if any(not isinstance(i, str) or not i for i in assessed + candidates): return None
    if len(set(assessed)) != len(assessed) or len(set(candidates)) != len(candidates): return None
    if not set(candidates) <= set(assessed): return None
    if row.get('assessed_amount') != len(assessed) or row.get('candidate_amount') != len(candidates): return None
    if not math.isclose(row['value'], 100 * (1 - len(candidates) / len(assessed)), abs_tol=1e-9): return None
    return set(assessed), set(candidates)


def _union(rows):
    """All rows must cover the same channels and recording interval."""
    from .method_scores import number
    identities = [_identities(r) for r in rows]
    if not rows or any(i is None for i in identities): raise ValueError('缺少完整的候选通道身份。')
    common = identities[0][0]
    if any(i[0] != common for i in identities): raise ValueError('受检通道集合不一致，不能合并。')
    scopes = [r.get('scope', {}) for r in rows]
    for s in scopes:
        if not all(number(s.get(k)) for k in ('start_seconds', 'stop_seconds', 'duration_seconds')):
            raise ValueError('缺少明确的通道检查时段。')
        if s['duration_seconds'] <= 0 or not math.isclose(s['stop_seconds']-s['start_seconds'], s['duration_seconds'], abs_tol=1e-6):
            raise ValueError('通道检查时段不一致。')
    if any(not math.isclose(s[k], scopes[0][k], abs_tol=1e-6) for s in scopes for k in ('start_seconds','stop_seconds')):
        raise ValueError('检查窗口不一致，不能合并候选。')
    return common, set().union(*(i[1] for i in identities)), scopes[0]


def state_output(rows, *, windows=None):
    """For whole records, use only methods valid in every executed window.

    Union within each window first, then pool channel-window durations. This
    retains distinct-channel findings even when two method scores are identical.
    """
    from .method_scores import observation, number
    from .score_registry import SPECS
    evidence = [copy.deepcopy(r) for r in rows if r['id'] in EVIDENCE]
    scope = {}; unions = []; active = []; rejected = []
    batches = [rows] if windows is None else [w.get('method_scores', []) for w in windows]
    for key in EVIDENCE:
        if not any(r['id'] == key for batch in batches for r in batch): continue
        parts = [next((r for r in batch if r['id'] == key), None) for batch in batches]
        if batches and all(_identities(r) is not None for r in parts):
            active.append(key)
        else:
            rejected.append({'id': key, 'reason': '部分窗口未完成、受限或缺少可核对的通道身份；本次合并不采用此项。'})
    bad = total = None
    reason = '没有有效的通道状态检查结果。'
    try:
        if active:
            bad = total = 0
            for index, batch in enumerate(batches):
                selected = [r for r in batch if r['id'] in active]
                ids, affected, scope = _union(selected)
                duration = 1 if windows is None else windows[index].get('duration_seconds')
                if not number(duration) or duration <= 0 or (windows is not None and
                        (windows[index].get('status','completed') not in {'completed','partial'} or
                         not math.isclose(duration,scope['duration_seconds'],abs_tol=1e-6))):
                    raise ValueError('分析窗未完整执行或时长不一致。')
                bad += len(affected)*duration; total += len(ids)*duration
                unions.append({'window_id': None if windows is None else windows[index]['id'],
                               'scope': copy.deepcopy(scope), 'candidate_channel_ids': sorted(affected),
                               'assessed_channel_count': len(ids)})
            reason = '整窗恒值与适用的AP离群按通道并集合并，同一通道在同一窗口只计一次。'
    except (ValueError, TypeError, KeyError) as error:
        bad = total = None; reason = str(error)
    out = observation(SPECS[STATE], bad, total, scope=scope if windows is None else {}, reason=reason)
    out.update(scoring_rule=VERSION, aggregation='deduplicated_channel_windows',
        assessed_methods=active if bad is not None else [], unavailable_methods=rejected,
        evidence_components=evidence, window_unions=unions if bad is not None else [],
        source_artifacts=list(dict.fromkeys(a for r in evidence for a in r.get('source_artifacts', []))))
    if windows is not None: out.update(unit='channel_block_seconds', window_count=len(windows))
    return out
