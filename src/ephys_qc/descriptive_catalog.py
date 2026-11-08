"""Per-route contracts around shared descriptive mathematics; no cross-modal thresholds."""
from . import ecog_catalog
from .modalities import route


def _adapt(value, modality):
    if modality == 'ecog':
        return value
    info = route(modality)
    if isinstance(value, str):
        return (value.replace('ecog-basic/1', info['profile'])
                .replace('ECoG', info['label']).replace('ecog', info['key']))
    if isinstance(value, list):
        return [_adapt(v, modality) for v in value]
    if isinstance(value, dict):
        return {k: _adapt(v, modality) for k, v in value.items()}
    return value


def module_overrides(module_id, modality):
    result = _adapt(ecog_catalog.module_overrides(module_id), modality)
    if modality in {'ecog', 'seeg'} and module_id == 'M03':
        result.update(description='检查非有限值、MNE持续平线；EDF/BDF可核对文件量程端点平台。',
                      outputs=['数值完整性计数', '持续平线与量程端点候选', '原始样本坐标'])
    if modality in {'ecog', 'seeg'} and module_id == 'M05':
        result.update(description='逐触点统计；明确比较组后可选组内幅度离群，参考未确认时只测量。',
                      outputs=['逐触点测量', '可选分组离群候选', '未评组及原因'])
    if modality in {'ecog', 'seeg'} and module_id == 'M06':
        result.update(selectable=True, implementation='available', description='可选FieldTrip差分z值区间线索；不自动判定生理伪迹。',
                      inputs=['已标定连续电压'], outputs=['候选区间与原始样本坐标'])
    if modality == 'seeg' and module_id == 'M02':
        result['limitations'] = ['电极杆、触点邻接、坐标和双极派生须有来源；不凭名称推断或跨杆比较。']
    if modality == 'extracellular':
        if module_id == 'M01':
            result['description'] = '核对SpikeGLX配套文件或NWB信号对象、探针声明与逐通道电压标定；保留处理史。'
            result['limitations'] = ['仅已核验设备的连续电压；不接收排序结果，不自动对齐多个信号或解释同步脉冲。']
        elif module_id == 'M02':
            result['description'] = '冻结所选连续信号、源通道及样本坐标；保留NWB对象路径、探针、时钟和处理声明。'
            result['limitations'] = ['AP与LF分别运行；采样相位补偿、漂移估计、spike sorting与单元质量未接入。']
        elif module_id == 'M03':
            result.update(description='检查NaN/Inf与整窗恒值；分别提供数值有效性和通道状态的计分证据。',
                          outputs=['逐道数值计数', '整窗恒值通道及来源身份', '数值有效性分项'],
                          limitations=['短量化重复只保留测量；有限恒值不在数值有效性中重复扣分。'])
        elif module_id == 'M05':
            result.update(description='逐道统计电压；AP满足条件时可用SpikeInterface筛查离群通道。',
                          outputs=['逐通道测量', '条件AP离群候选及分项'],
                          limitations=['RMS、PSD不直接判坏；LF不套用AP参数。AP候选合并至通道状态，不另加权。'])
        elif module_id == 'M08':
            result.update(description='合并恒值与AP候选，按可调权重汇总数值有效性和通道状态。',
                          outputs=['去重后的通道状态', '综合分及有效权重', '受限检查与证据来源'],
                          limitations=['受限项不计入；项目初版评分尚未经过专家校准。'])
    return result


def custom_methods(modality):
    rows = _adapt(ecog_catalog.custom_methods(), modality)
    if modality != 'ecog':
        for item in rows:
            doc = item['documentation']
            doc['implementation_origin'] += ' → src/ephys_qc/modules/continuous/' + item['module_id'].lower() + '.py'
            doc['how_it_works'] += ' 共用描述性数学核，但模态、输入和参数独立核验。'
            if modality == 'extracellular':
                doc['when_to_use'] = '已核验Neuropixels设备、单个SpikeGLX或NWB连续电压信号、时钟及电极映射。'
                doc['when_not_to_use'] = '设备身份未知的细胞外记录、分选后spike/units、未选择的多流或同步数字通道。'
                item['limitations'] += ['AP高频包含神经放电；原始RMS和PSD不直接称为噪声。没有分选，不计算单元指标。']
                if item['module_id'] == 'M03':
                    doc['how_it_works'] += ' 另外保存各来源通道整窗恒值标记；NaN/Inf形成数值有效性分项，整窗恒值与适用的AP候选在M08去重。'
    return rows
