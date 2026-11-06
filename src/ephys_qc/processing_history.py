"""Declared processing history and shared frequency eligibility rules.

These rules limit interpretation of saved signals; they never infer a filter
from a waveform or prove the original acquisition was free of interference.
"""
import copy
import math

VERSION = 'processing-scope/1.0'


def validate_declaration(value):
    allowed = {'verified', 'highpass_hz', 'lowpass_hz', 'notch_hz', 'note'}
    if not isinstance(value, dict) or set(value) - allowed or type(value.get('verified')) is not bool:
        raise ValueError('请确认处理史，或保留“未知”。')
    result = copy.deepcopy(value)
    for key in ('highpass_hz', 'lowpass_hz'):
        x = result.get(key)
        if x is not None and (type(x) not in (int, float) or not math.isfinite(x) or x < 0 or (key == 'lowpass_hz' and x == 0)):
            raise ValueError('滤波频率应为有效数值；未知可留空。')
    lo, hi = result.get('highpass_hz'), result.get('lowpass_hz')
    if lo is not None and hi is not None and lo >= hi:
        raise ValueError('高通频率必须小于低通频率。')
    notches = result.get('notch_hz', [])
    if not isinstance(notches, list) or len(notches) > 32 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in notches):
        raise ValueError('陷波频率应为正数列表。')
    result['notch_hz'] = sorted(set(notches))
    note = result.get('note', '')
    if not isinstance(note, str) or len(note) > 2000 or (result['verified'] and not note.strip()):
        raise ValueError('已确认的处理史需要填写来源依据，最多2000字。')
    return {**result, 'source': 'user_declaration_not_independent_measurement'}


def scope(record, config, sampling_rate):
    p = record.get('preprocessing') or {}
    known = p.get('verified') is True
    hp = p.get('highpass_hz') if known else None
    lp = p.get('lowpass_hz') if known else None
    notches = p.get('notch_hz', []) if known else []
    spectral = config.get('method_config', {}).get('spectral', {})
    half = spectral.get('line_scan_half_width_hz', 2.0)
    fundamentals = spectral.get('line_fundamentals_hz', [50., 60.])
    targets = sorted({float(f * n) for f in fundamentals for n in range(1, int(sampling_rate / 2 / f) + 1)
                      if f * n + half < sampling_rate / 2}) if sampling_rate else []
    excluded = []
    for f in targets:
        reason = ('目标频率处于已声明陷波邻域' if any(abs(f - n) <= half for n in notches) else
                  '目标频率不在已声明保留频带内' if (hp is not None and f - half <= hp) or (lp is not None and f + half >= lp) else None)
        if reason: excluded.append({'frequency_hz': f, 'reason': reason})
    muscle = config.get('method_config', {}).get('muscle', {})
    low = muscle.get('lower_frequency_hz', 30.)
    high = min(muscle.get('upper_frequency_hz', 100.), muscle.get('upper_sampling_fraction', .45) * sampling_rate) if sampling_rate else 0
    # Keep the original algorithm band fixed. A changed band is a distinct
    # method configuration, not an implicit adjustment made by the viewer.
    hf_limited = known and ((hp is not None and hp > low) or (lp is not None and lp < high))
    return {'version': VERSION, 'history_known': known, 'basis': p.get('source', 'registered_declaration'),
            'highpass_hz': hp, 'lowpass_hz': lp, 'notch_hz': notches,
            'line_targets_hz': targets, 'line_excluded': excluded,
            'line_evaluable_hz': [f for f in targets if f not in {r['frequency_hz'] for r in excluded}],
            'hf_band_hz': [low, high], 'hf_limited_by_history': hf_limited,
            'interpretation': '评价当前输入信号；不能追溯证明清洗前质量。' if known else '处理史未知；结果仅描述当前输入信号。'}


def restrict_line_evidence(payload, assessment):
    """Keep original observations for audit, exclude unavailable targets from scoring."""
    reasons = {r['frequency_hz']: r['reason'] for r in assessment['line_excluded']}
    payload['processing_scope'] = copy.deepcopy(assessment)
    line = payload['line_noise']
    for row in line.get('observations', []):
        if row.get('nominal_hz') in reasons and row.get('status') == 'computed':
            row['upstream_observation'] = {'status': row['status'], 'flagged': row.get('flagged')}
            row.update(status='not_assessed_preprocessing', flagged=False, reason=reasons[row['nominal_hz']])
    if reasons:
        for row in line.get('channel_summary', []):
            if row.get('nominal_hz') in reasons:
                row['upstream_summary'] = copy.deepcopy(row)
                for key in ('assessed_window_count', 'flagged_window_count', 'flagged_window_fraction', 'flagged_union_seconds', 'flagged_union_fraction_of_input', 'minimum_corrected_p'):
                    row[key] = None
                row.update(status='not_assessed_preprocessing', reason=reasons[row['nominal_hz']])
        line['processing_exclusions'] = copy.deepcopy(assessment['line_excluded'])
        line['status'] = 'partial_preprocessing' if any(r.get('status') == 'computed' for r in line.get('observations', [])) else 'not_assessed_preprocessing'


def summarize_methods(methods, module_id=None):
    selected = [m for m in methods if m.get('selected') and (module_id is None or m['module_id'] == module_id)]
    ready = sum(m['status'] in {'ready', 'partial'} for m in selected)
    blocked = sum(m['status'] == 'blocked' for m in selected)
    return {'selected': len(selected), 'executable': ready, 'unavailable': blocked,
            'label': f'{ready} 项可检查' + (f' · {blocked} 项缺条件' if blocked else '')}
