"""Versioned iEEG scoring: one vote for related voltage-candidate evidence."""
import copy
import math

VERSION = 'ieeg-score/0.1'
PRESETS = {m: f'{m}-basic-score/0.1' for m in ('ecog', 'seeg')}
NUMERIC = 'ieeg_numeric_integrity'
STABILITY = 'ieeg_signal_stability'
EVIDENCE = ('mne_amplitude_channels', 'mne_amplitude_time', 'ieeg_range_plateau',
            'fieldtrip_zvalue', 'ieeg_group_outliers')


def default_config(modality):
    return {'version': 'project-weighted/1.2', 'preset': PRESETS[modality],
            'weights': {NUMERIC: 30, STABILITY: 70}}


def validate_family_weights(weights):
    if sum(weights.get(k, 0) > 0 for k in (STABILITY, *EVIDENCE)) > 1:
        raise ValueError('稳定性相关检查只能计入一次；请选择信号稳定性汇总，或单独一个原始检查项。')


def numeric_output(payload, recording, artifact, *, spec_id=NUMERIC):
    from .method_scores import observation
    from .score_registry import SPECS
    rows=payload.get('channels',[])
    ids=[r.get('channel_id') for r in rows]
    counts=('sample_count','finite_sample_count','nonfinite_sample_count')
    n=recording.get('channel_count')
    valid=(len(rows)==n and n>0 and all(isinstance(i,str) and i for i in ids)
           and len(set(ids))==n and all(all(type(r.get(k)) is int and r[k]>=0 for k in counts)
           and r['sample_count']>0 and r['finite_sample_count']+r['nonfinite_sample_count']==r['sample_count'] for r in rows))
    return observation(SPECS[spec_id],sum(r['nonfinite_sample_count'] for r in rows) if valid else None,
        sum(r['sample_count'] for r in rows) if valid else None, artifact=artifact,scope=recording,
        reason='仅统计NaN/Inf占全部受检采样点的比例；重复有限值不在此项扣分。' if valid else '逐道样本计数不完整或不一致。')


def stability_output(rows):
    from .method_scores import observation, number
    from .score_registry import SPECS
    evidence=[copy.deepcopy(r) for r in rows if r['id'] in EVIDENCE]
    valid=[r for r in evidence if r.get('status')=='computed' and number(r.get('value'))
           and number(r.get('candidate_amount')) and number(r.get('assessed_amount'))
           and r['assessed_amount']>0 and 0<=r['candidate_amount']<=r['assessed_amount']
           and math.isclose(r['value'],100*(1-r['candidate_amount']/r['assessed_amount']),abs_tol=1e-9)]
    limiting=min(valid,key=lambda r:r['value']) if valid else None
    row=observation(SPECS[STABILITY],(100-limiting['value'])/100 if limiting else None,
        1 if limiting else None,
        reason=('取已完成的稳定性检查最低分，同类证据不叠加；本次由'+limiting['name']+'决定。') if limiting else '没有有效的稳定性检查结果。')
    row.update(formula='min(valid related-method scores)',scoring_rule=VERSION,
        interpretation='相关检查合并为一个计分项；不是逐样本污染率，也不代表已识别异常原因。',
        limiting_method=limiting['id'] if limiting else None,
        evidence_components=evidence,assessed_methods=[r['id'] for r in valid],
        unavailable_methods=[r['id'] for r in evidence if r not in valid],
        source_artifacts=list(dict.fromkeys(a for r in evidence for a in r.get('source_artifacts',[]))))
    return row
