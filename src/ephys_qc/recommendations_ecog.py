"""Metadata-only ECoG basic route; never apply scalp detector parameters."""
import copy

from .planning import build_plan
from .tagging import data_facts


def recommend_ecog(record, submitted=None):
    from .recommendations import _empty, _finish, _missing, _ANNOTATIONS
    result = _empty(record, 'needs_input', '先核实ECoG模态、分析通道及电压单位。')
    result['policy_version'] = 'ecog-basic-metadata-rules/1.1'
    result['scope']['supported_modality'] = 'ecog'
    result['scope']['analysis_profile'] = 'ecog-basic/1'
    from .ieeg_baseline import VERSION
    result['scope']['baseline_recipe'] = VERSION
    metadata = record.get('metadata')
    format_ = metadata.get('format') if isinstance(metadata, dict) else None
    if format_ not in result['scope']['supported_metadata_formats']:
        result['status'] = 'needs_input' if format_ in {None, '', 'unknown'} else 'unsupported'
        result['missing_fields'] = [_missing('metadata.format', '原始文件格式', '须由已接入读取器核验文件格式。', True)]
        return _finish(result, record, submitted)
    try:
        current = build_plan(record, ['M03','M04','M05'], submitted)
        config = copy.deepcopy(current['qc_config'])
        if record['modality'] in {'ecog', 'seeg'}:
            from .ieeg_baseline import configure
            config = configure(config, record)
        facts = data_facts(record, config)
        if not facts['verified_voltage']:
            raise ValueError('所选信号须具有已核验的电压单位。')
        annotation = record.get('annotation') or {}
        has_annotation = annotation.get('format') in _ANNOTATIONS and bool(annotation.get('path'))
        selected = ['M03', 'M04', 'M05'] + (['M06'] if 'fieldtrip_zvalue' in config['method_config']['extensions'] else []) + (['M07'] if has_annotation else [])
        final = build_plan(record, selected, config)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        result['missing_fields'] = [_missing('qc_config', 'ECoG输入与配置', str(error), True)]
        result['reason'] = result['summary'] = '配置未通过ECoG入口核验；未自动移除或改写不相容参数。'
        return _finish(result, record, submitted)

    result.update(status='ready', can_apply=True, summary='建议完整性、平线、量程、频谱与触点检查；FieldTrip跳变与分组离群可单独选择。',
                  reason='根据已确认ECoG模态和技术信息生成基础检查计划。',
                  selected_modules=final['selected_modules'], qc_config=final['qc_config'],
                  plan_id=final['plan_id'], data_tags=final['data_tags'],
                  method_applicability=final['method_applicability'], plan_warnings=final['warnings'],
                  analysis_scope=final.get('scope', 'window'), window_count=final.get('window_count', 1),
                  coverage_plan=final.get('coverage_plan'), current_extensions=current['qc_config']['method_config']['extensions'],
                  extension_selection_changed=config['method_config']['extensions'] != current['qc_config']['method_config']['extensions'])
    for method in final['method_applicability']:
        entry = {'id': method['id'], 'module_id': method['module_id'], 'name': method['name'],
                 'reason': method['reason'], 'applicability': method['status'],
                 'implementation': method.get('implementation', 'available'),
                 'parameters': copy.deepcopy(method.get('parameters')), 'optional_extension': False}
        if method.get('selected') and method['status'] in {'ready', 'partial'}:
            result['recommended_methods'].append({**entry, 'disposition': 'recommended'})
        else:
            result['blocked_methods'].append({**entry, 'disposition': 'not_implemented' if method.get('implementation') == 'planned' else 'not_selected_or_condition_missing'})
    result['review_focus'] = ['逐触点结合原始波形和采集资料复核；异常幅度、谱峰或高频不自动等于坏道。',
                            '发作、癫痫样放电与生理高频可能是研究目标，不作为伪迹真值或扣分依据。']
    result['cautions'] += ['当前为ECoG基础描述流程；不运行PREP、头皮桥接/LOF、FOOOFα指标或肌电阈值。',
                           '不根据触点名推测电极邻接、脑区、共同参考或植入位置。',
                           '工频附近能量只作观察量，不以固定比值自动判定污染。',
                           '默认评分为数值有效性30%、信号稳定性70%；稳定性子项按可调权重平均，受限项不计入，项目参数尚未经过专家校准。']
    if facts['reference_scheme'] == 'unknown':
        result['missing_fields'].append(_missing('reference_scheme', '参考构型', '参考尚未核实；基础逐触点描述仍可运行，不进行跨触点相似性判定。'))
    if not facts['preprocessing_verified']:
        result['missing_fields'].append(_missing('preprocessing', '采集与滤波史', '滤波史未知；谱形和工频观察只能结合源记录说明解释。'))
    if not has_annotation:
        result['missing_fields'].append(_missing('annotation', '已核实事件表', '尚未登记支持的事件表；文件内事件描述不自动解释为临床或质量标注。'))
    return _finish(result, record, submitted)
