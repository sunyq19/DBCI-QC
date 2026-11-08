"""Declarative score-output contracts; independent of algorithms and the UI."""
from copy import deepcopy

CONTRACT = 'method-score/1'
SCALP = ['scalp_eeg']
# id, method, module, label, native denominator, output reducer, modality scope
_ROWS = [
 ('integrity','continuity','M03','信号完整性','channel_samples','core',SCALP),
 ('line_noise','thomson_line','M04','工频干扰','channel_windows','core',SCALP),
 ('hf_burst','hf_burst','M06','高频突发','channel_seconds','core',SCALP),
 ('prep_nonspatial','prep_nonspatial','M05','PREP 非空间通道候选','channels','prep',SCALP),
 ('mne_amplitude_channels','mne_amplitude','M03','MNE 幅度通道候选','channels','channels',['scalp_eeg','ecog','seeg']),
 ('mne_amplitude_time','mne_amplitude','M03','MNE 幅度区间候选','seconds','intervals',['scalp_eeg','ecog','seeg']),
 ('mne_muscle','mne_muscle','M06','MNE 高频伪迹候选','samples','finite_samples',SCALP),
 ('mne_bridge','mne_bridge','M05','MNE 桥接涉及通道','channels','pairs',SCALP),
 ('mne_lof','mne_lof','M05','MNE LOF 通道候选','channels','channels',SCALP),
 ('autoreject_global','autoreject_global','M03','AutoReject 超阈值片段','epochs','epochs',SCALP),
 ('gnosis_line_length','gnosis_line_length','M05','灵犀云 · 线长通道候选','channels','channels',SCALP),
 ('gnosis_artifact','gnosis_artifact','M06','灵犀云 · 伪差区间','channel_seconds','ratios',SCALP),
 ('gnosis_low_band','gnosis_low_band','M06','灵犀云 · 低频异常','channel_seconds','ratios',SCALP),
 ('gnosis_high_band','gnosis_high_band','M06','灵犀云 · 高频异常','channel_seconds','ratios',SCALP),
 ('gnosis_psd_deviation','gnosis_psd_deviation','M05','灵犀云 · PSD 异常通道','channels','channels',SCALP),
 ('faster_channels','faster_channels','M05','FASTER 通道候选','channels','channels',SCALP),
 ('fieldtrip_zvalue','fieldtrip_zvalue','M06','FieldTrip 跳变区间','seconds','intervals',['scalp_eeg','ecog','seeg']),
 ('ieeg_numeric_integrity','ieeg_numeric_integrity','M03','数值有效性','channel_samples','ieeg_numeric',['ecog','seeg']),
 ('ieeg_signal_stability','mne_amplitude','M03','信号稳定性','dimensionless','ieeg_stability',['ecog','seeg']),
 ('ieeg_range_plateau','ieeg_range_plateau','M03','文件量程端点平台','channel_samples','encoding_samples',['ecog','seeg']),
 ('ieeg_group_outliers','ieeg_group_outliers','M05','分组触点幅度离群','channels','assessed_channels',['ecog','seeg']),
 ('spikeinterface_bad_channels','spikeinterface_bad_channels','M05','SpikeInterface 噪声通道','channels','channels',['extracellular']),
 ('neuropixels_numeric_integrity','neuropixels_numeric_integrity','M03','数值有效性','channel_samples','np_numeric',['extracellular']),
 ('neuropixels_constant_channels','neuropixels_constant_channels','M03','整窗恒值通道','channels','np_constant',['extracellular']),
 ('neuropixels_channel_state','aggregate','M08','通道状态','channels','np_state',['extracellular']),
]
SPECS = {key:dict(id=key,method_id=method,module_id=module,name=name,unit=unit,reducer=reducer,
                 modalities=list(modalities),default_weight=1 if reducer=='core' else 0,
                 contract_version=CONTRACT,formula='100 * (1 - candidate_amount / assessed_amount)',
                 interpretation='指定方法未命中的比例；候选不是已确认坏道或伪迹。')
         for key,method,module,name,unit,reducer,modalities in _ROWS}

SPECS['ieeg_signal_stability'].update(formula='min(valid related-method scores)',
    interpretation='相关候选只取最低分计一次，不代表逐样本异常并集。')

def outputs(modality=None, method_id=None):
    return [deepcopy(s) for s in SPECS.values() if
            (modality is None or modality in s['modalities']) and
            (method_id is None or s['method_id']==method_id)]


def describe(method, modality):
    out=outputs(modality,'ieeg_numeric_integrity' if modality in {'ecog','seeg'} and method['id'] in {'ecog_continuity','seeg_continuity'} else method['id']) if method.get('implementation')=='available' else []
    if modality=='extracellular' and method['module_id']=='M03' and method.get('implementation')=='available':
        out=[s for s in outputs(modality) if s['reducer'] in {'np_numeric','np_constant'}]
    reason=('按本方法的有效证据输出项目分数；是否计入由模态方案和评分配置决定。' if out else
            '未实现，不能计分。' if method.get('implementation')!='available' else
            '处理变化量不等于输入质量。' if method['id'] in {'asr_bursts','cleanline','zapline_plus'} else
            '参考范围的人群适用性未确认，不将范围外直接判为质量差。' if method['id']=='gnosis_reference_ranges' else
            '没有独立质量判定及有效分母，保留测量或流程输出。')
    return {**method,'can_output_score':bool(out),'scoring':dict(can_output_score=bool(out),
            outputs=out,contract_version=CONTRACT,reason=reason)}


def enabled(spec, selected, extensions):
    return spec['module_id'] in selected and (spec['reducer'] in {'core','prep','ieeg_numeric','np_numeric','np_constant','np_state'} or spec['method_id'] in extensions)
