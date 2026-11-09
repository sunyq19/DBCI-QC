"""Versioned project scores; detectors and historical scoring remain independent."""
import copy
import hashlib
import json
import math

VERSION = 'project-weighted/1.2'
METHOD_VERSIONS = ('project-weighted/1.1', VERSION)
LEGACY_VERSION = 'project-weighted/1.0'
SPECS = {'integrity': ('M03', '信号完整性'), 'line_noise': ('M04', '工频干扰'),
         'hf_burst': ('M06', '高频突发')}
FORMULA = '分项 = 100 × (1 − 候选量 / 有效检查量)；总分 = Σ(分项 × 权重) / Σ权重。'


def capability(module_id, modality):
    from .score_registry import outputs
    components = [s['id'] for s in outputs(modality) if s['module_id'] == module_id]
    aggregate = module_id == 'M08' and bool(outputs(modality))
    return dict(can_output_score=bool(components or aggregate), component_ids=components,
                role='aggregate' if aggregate else 'component' if components else 'evidence',
                version=VERSION if components or aggregate else None,
                reason='仅汇总，不重复参与加权' if aggregate else '按方法输出候选占比' if components else '保留测量与流程输出')


def normalize(config, modality, selected, extensions=()):
    """Freeze requested weights; effective weights are recorded in results."""
    from .score_registry import SPECS as registry, outputs, enabled
    if config is None:
        weights = {s['id']: s['default_weight'] for s in outputs(modality)
                   if s['default_weight'] and s['module_id'] in selected}
        return {'version': VERSION, 'weights': weights} if weights else None
    if not isinstance(config, dict) or not {'version', 'weights'} <= set(config) or set(config)-{'version','weights','preset','group_weights'} or config['version'] not in (*METHOD_VERSIONS, LEGACY_VERSION):
        raise ValueError('评分配置须包含有效的 project-weighted 版本及 weights。')
    if 'preset' in config:
        from .ieeg_scoring import PRESETS, LEGACY_PRESETS
        from .neuropixels_scoring import PRESET
        presets={**PRESETS,'extracellular':PRESET}
        if modality not in presets or config['preset'] not in {presets[modality], LEGACY_PRESETS.get(modality)}:
            raise ValueError('评分方案版本与模态不匹配。')
    weights = config['weights']
    legacy = config['version'] == LEGACY_VERSION
    if not isinstance(weights, dict) or (legacy and (modality != 'scalp_eeg' or set(weights) != set(SPECS))):
        raise ValueError('旧版评分仅支持头皮 EEG 完整性、工频、高频三项。')
    eligible = {s['id'] for s in outputs(modality)}
    if set(weights) - eligible:
        raise ValueError('当前模态不支持这些计分项目：' + ', '.join(sorted(set(weights)-eligible)))
    for key, value in weights.items():
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError('评分权重须为 0–100 的有限数值；0 表示不纳入。')
        if value and not enabled(registry[key], selected, extensions):
            raise ValueError(registry[key]['name']+'方法未选择；请启用方法及模块或将权重设为 0。')
    if modality in {'ecog','seeg'}:
        from .ieeg_scoring import validate_family_weights, child_weights
        validate_family_weights(weights)
        child_weights(config)
    elif 'group_weights' in config:
        raise ValueError('当前模态不支持稳定性子项权重。')
    if modality=='extracellular':
        from .neuropixels_scoring import validate_family_weights
        validate_family_weights(weights)
    if legacy and not any(weights.values()):
        raise ValueError('至少一个评分权重须大于 0。')
    return copy.deepcopy(config)


def weighted_score(evidence, expected_channels, config, *, expected_windows=1, coverage_complete=True):
    from .scoring import burden_score
    # Reuse strict evidence/identity/coverage checks; do not reuse the RMS score.
    normalize(config, 'scalp_eeg', ['M03','M04','M06'])
    if config['version'] in METHOD_VERSIONS:
        from .method_scores import core_outputs, aggregate
        return aggregate(core_outputs(evidence, expected_channels, expected_windows=expected_windows, coverage_complete=coverage_complete), config, coverage_complete=coverage_complete)
    score = burden_score(evidence, expected_channels, expected_windows=expected_windows, coverage_complete=coverage_complete)
    weights = config['weights']
    parts = score['components']
    weight_sum = sum(weights.values())
    for part in parts:
        eligible = part['value'] is not None
        part['value'] = 100 * part['numerator'] / part['denominator'] if eligible else None
        part.update(aggregation='pooled_unflagged_fraction', weight=weights[part['id']],
                    normalized_weight=weights[part['id']]/weight_sum,
                    candidate_fraction=1-part['numerator']/part['denominator'] if eligible else None)
        part.pop('rms_burden', None)
    missing = [p['id'] for p in parts if p['weight'] > 0 and p['value'] is None]
    value = (sum(p['value']*p['weight'] for p in parts if p['weight']>0)/weight_sum
             if coverage_complete and not missing else None)
    digest = hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
    score.update(version=LEGACY_VERSION,name='项目自定义评分',value=value,weights=copy.deepcopy(weights),
                 formula=FORMULA,aggregation='pooled_fraction_then_weighted_mean',
                 aggregation_version=LEGACY_VERSION,configuration_id=digest,
                 missing_components=missing,limiting_components=[],
                 missing_reason=('检查范围未完整覆盖' if not coverage_complete else '缺少有效计分证据：'+ '、'.join(SPECS[k][1] for k in missing) if missing else ''),
                 scope='selected_checks_only')
    return score


def apply_to_view(view, config):
    """Explicit score revision from saved sufficient statistics, without detectors."""
    from .scoring import score_revision
    revised = copy.deepcopy(view)
    old = view['score']
    from .method_scores import aggregate
    if old.get('version') in METHOD_VERSIONS and config['version'] in METHOD_VERSIONS:
        # Method outputs already contain validated sufficient statistics, including
        # optional methods. Reweight them without dropping extensions or rereading signals.
        score = aggregate(old['components'], config, coverage_complete=old.get('coverage_complete',True))
    else:
        score = weighted_score(view['channel_evidence'], view['recording']['channel_count'], config,
                               expected_windows=old.get('expected_windows',1),
                               coverage_complete=old.get('coverage_complete',True))
    for part in score['components']:
        previous = next((p for p in old['components'] if p['id']==part['id']), {})
        for key in ('assessed_window_seconds', 'window_count'):
            if key in previous: part[key] = previous[key]
    revised['score'] = score
    revised['score_revision'] = score_revision({'report_view':view}, score)
    for window in revised.get('window_scores',[]):
        parts = window.get('components',[])
        if config['version'] in METHOD_VERSIONS:
            from .method_scores import observation
            from .score_registry import SPECS as registry
            rows = [p if 'assessed_amount' in p else observation(registry[p['id']],
                    p['denominator']-p['numerator'] if p.get('value') is not None else None,
                    p['denominator'] if p.get('value') is not None else None) for p in parts]
            scored = aggregate(rows, config, coverage_complete=window.get('status','completed') in {'completed','partial'})
            window.update(value=scored['value'], components=scored['components'], excluded_components=scored.get('excluded_components',[]))
            continue
        for p in parts:
            p['value'] = (100*p['numerator']/p['denominator'] if p.get('value') is not None and p.get('denominator',0)>0 else None)
            p['weight'] = config['weights'][p['id']]
        active = [p for p in parts if p['weight']>0]
        window['value'] = (sum(p['value']*p['weight'] for p in active)/sum(p['weight'] for p in active)
                           if active and len(parts)==3 and all(p['value'] is not None for p in active) else None)
    valid = [w for w in revised.get('window_scores',[]) if w['value'] is not None]
    if 'lowest_window' in revised: revised['lowest_window'] = min(valid,key=lambda w:w['value']) if valid else None
    if revised.get('local_quality'): revised['local_quality']['explanation']='通道分项与总体分项均按各自范围的候选量与有效检查量计算。'
    revised['scoring_complete'] = score['value'] is not None
    revised['notes'] = [n for n in revised.get('notes',[]) if '均方根' not in n and '最低分项' not in n]
    if score['value'] is not None:
        revised['notes'] = [n for n in revised['notes'] if '不给整份总分' not in n]
    revised['notes'].append(FORMULA + '仅比较相同规则、权重、处理状态与检查范围的结果。')
    return revised
