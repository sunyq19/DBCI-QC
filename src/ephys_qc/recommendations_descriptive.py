"""Metadata-only sEEG/Neuropixels voltage routes; never apply scalp detector parameters."""
import copy

from .planning import build_plan
from .tagging import data_facts


def recommend_descriptive(record, submitted=None):
    from .modalities import route
    info = route(record["modality"])
    label = info["label"]
    from .recommendations import _empty, _finish, _missing, _ANNOTATIONS
    def finish(value, source, config):
        def text(v):
            if isinstance(v, str): return v.replace('ECoG', label)
            if isinstance(v, list): return [text(x) for x in v]
            if isinstance(v, dict): return {k: text(x) for k, x in v.items()}
            return v
        # Do not transform frozen configurations, provenance or identifiers.
        for key in ('reason', 'summary', 'cautions', 'review_focus', 'missing_fields'):
            value[key] = text(value[key])
        if source['modality'] == 'extracellular':
            value['cautions'].append('仅单个连续电压信号描述，保留源处理声明；无spike sorting、单元指标、探针漂移或跨流同步判定。')
        return _finish(value, source, config)
    result = _empty(record, 'needs_input', '先核实ECoG模态、分析通道及电压单位。')
    result['policy_version'] = info['profile'] + '-metadata-rules/1.0'
    result['scope']['supported_modality'] = record['modality']
    result['scope']['analysis_profile'] = info['profile']
    if record['modality']=='seeg':
        from .ieeg_baseline import VERSION
        result['scope']['baseline_recipe'] = VERSION
        result['policy_version'] = info['profile'] + '-metadata-rules/1.1'
    if record['modality'] == 'extracellular':
        result['scope']['supported_metadata_formats'] = ['SpikeGLX', 'NWB']
        from .neuropixels_standard import VERSION, RECIPE
        result['scope'].update(standard_version=VERSION, baseline_recipe=RECIPE)
        result['policy_version'] = RECIPE
    metadata = record.get('metadata')
    format_ = metadata.get('format') if isinstance(metadata, dict) else None
    if format_ not in result['scope']['supported_metadata_formats']:
        result['status'] = 'needs_input' if format_ in {None, '', 'unknown'} else 'unsupported'
        result['missing_fields'] = [_missing('metadata.format', '原始文件格式', '须由已接入读取器核验文件格式。', True)]
        return finish(result, record, submitted)
    try:
        current = build_plan(record, ['M03','M04','M05'] if record['modality']=='extracellular' else [], submitted)
        config = copy.deepcopy(current['qc_config'])
        if record['modality'] in {'ecog', 'seeg'}:
            from .ieeg_baseline import configure
            config = configure(config, record)
        elif record['modality'] == 'extracellular':
            from .neuropixels_standard import configure
            config = configure(config, record, current, submitted)
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
        return finish(result, record, submitted)

    result.update(status='ready', can_apply=True, summary=('建议完整性、平线、量程、频谱与触点检查；FieldTrip跳变与分组离群可单独选择。' if record['modality']=='seeg' else '建议完整性、频谱与逐触点检查；有事件表时核对时间。'),
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
    if record['modality']=='extracellular':
        result['cautions'][-1]='默认总分仅评价所选连续电压检查；未验证神经元单元质量。'
    if facts['reference_scheme'] == 'unknown':
        result['missing_fields'].append(_missing('reference_scheme', '参考构型', '参考尚未核实；基础逐触点描述仍可运行，不进行跨触点相似性判定。'))
    if not facts['preprocessing_verified']:
        result['missing_fields'].append(_missing('preprocessing', '采集与滤波史', '滤波史未知；谱形和工频观察只能结合源记录说明解释。'))
    if not has_annotation:
        result['missing_fields'].append(_missing('annotation', '已核实事件表', '尚未登记支持的事件表；文件内事件描述不自动解释为临床或质量标注。'))
    if record['modality']=='extracellular':
        ap_selected='spikeinterface_bad_channels' in config['method_config']['extensions']
        result['summary']='完整性、频谱与通道统计；按探针杆检查AP通道离群。' if ap_selected else '完整性、频谱与通道统计；当前流不套用AP离群阈值。'
        result['reason']='依据已确认的连续电压流、原始通道映射和逐窗运行条件推荐。'
        result['review_focus']=['先看非有限值、整窗恒值与覆盖缺口，再复核AP离群通道和原始波形。',
                                '分清原始AP、LF和来源已处理LFP；不同处理状态及频带不直接比较。']
        result['cautions']=result['cautions'][:2]+[
            'AP通道筛查在每个来源shank内独立执行；未知映射时不猜测。',
            '相邻量化值重复不等于丢包；整窗恒值应复核，不能仅看有限值数量。',
            '默认数值有效性30%、通道状态70%；恒值与AP离群按通道去重，受限证据不采用。',
            '尚未执行分选后单元指标、漂移估计、同步字错误解码或跨流时钟校准。']
    return finish(result, record, submitted)
