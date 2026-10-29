"""Provenance-aware data tags; clinical context is not a signal-quality rule."""
import copy
import math
from collections import Counter


CONTEXT_OPTIONS = {
    'disease': [('unknown', '未提供 / 未核实'), ('healthy_control', '健康对照'),
                ('epilepsy', '癫痫'), ('sleep_disorder', '睡眠障碍'), ('parkinsons', '帕金森病'),
                ('stroke', '脑卒中'), ('dementia', '认知障碍 / 痴呆'), ('brain_injury', '脑损伤'),
                ('disorders_of_consciousness', '意识障碍'), ('psychiatric', '精神心理疾病'), ('other_neurological', '其他神经系统疾病'), ('other', '其他背景')],
    'age_group': [('unknown', '年龄未提供'), ('neonate', '新生儿'), ('child', '儿童 / 青少年'),
                  ('adult', '成年人'), ('older_adult', '老年人')],
    'task': [('unknown', '任务未提供'), ('rest', '静息'), ('sleep', '睡眠记录'),
             ('attention', '注意任务'), ('motor', '运动任务'), ('motor_imagery', '运动想象'), ('erp', '事件相关任务'), ('other', '其他任务')],
}


def context_options():
    return {key: [{'value': value, 'label': label} for value, label in rows] for key, rows in CONTEXT_OPTIONS.items()}


def context_defaults(record):
    task = {'adult_multichannel_rest': 'rest', 'sparse_psg_with_auxiliary': 'sleep',
            'adult_multichannel_attention_task': 'attention', 'multichannel_motor_execution': 'motor',
            'multichannel_motor_imagery': 'motor_imagery',
            'sparse_bipolar_sleep': 'sleep'}.get(record.get('profile_id'), 'unknown')
    # A profile called 'adult' is not evidence of the particular participant's age.
    return {'disease': 'unknown', 'age_group': 'unknown', 'task': task}


def validate_context(record, context=None):
    if context is None:
        context = {}
    if not isinstance(context, dict) or set(context) - set(CONTEXT_OPTIONS):
        raise ValueError('context_tags只接受疾病背景、年龄分组和任务类型。')
    result = context_defaults(record)
    for key, value in context.items():
        if not isinstance(value, str) or value not in dict(CONTEXT_OPTIONS[key]):
            raise ValueError(f'不支持的背景标签：{key}={value}')
        result[key] = value
    return result


def data_facts(record, config=None):
    config = config if config is not None else record.get('default_config', {})
    selection = config.get('selection', {})
    metadata = record.get('metadata', {})
    indices = selection.get('eeg_indices', [])
    refs = selection.get('reference_indices', {})
    channels = {c['index']: c for c in metadata.get('channels', [])}
    selected = [channels[i] for i in indices if i in channels]
    auxiliary = [channels[i] for i in refs.values() if i in channels]
    rates = {c.get('sampling_rate_hz') for c in selected + auxiliary}
    unit = lambda c: str(c.get('unit', '')).strip().lower().replace('μ', 'u').replace('µ', 'u')
    groups = config.get('method_config', {}).get('comparison_groups')
    labels = list(groups.values()) if isinstance(groups, dict) else groups or []
    counts = Counter(labels)
    annotation = record.get('annotation', {})
    context = validate_context(record, config.get('context_tags'))
    preprocessing = record.get('preprocessing', {})
    reference_scheme = record.get('reference_scheme', 'unknown')
    if reference_scheme not in {'unknown', 'common_reference', 'linked_ears', 'bipolar', 'mixed'}:
        raise ValueError('reference_scheme不是受支持的登记类型。')
    if not isinstance(preprocessing, dict) or ('verified' in preprocessing and type(preprocessing['verified']) is not bool):
        raise ValueError('preprocessing需为对象，verified需为明确的布尔值。')
    for key in ('highpass_hz', 'lowpass_hz'):
        value = preprocessing.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or (key == 'lowpass_hz' and value == 0)):
            raise ValueError('滤波史频率必须是有效非负数；低通频率须大于0。')
    if preprocessing.get('highpass_hz') is not None and preprocessing.get('lowpass_hz') is not None and preprocessing['highpass_hz'] >= preprocessing['lowpass_hz']:
        raise ValueError('滤波史高通频率须低于低通频率。')
    for key in ('verified_electrode_coordinates', 'verified_epochs'):
        if key in record and type(record[key]) is not bool:
            raise ValueError(key + '需为明确的布尔值。')
    return {'sampling_rate_hz': next(iter(rates)) if len(rates) == 1 else None,
            'n_eeg': len(indices), 'window_seconds': selection.get('duration_seconds'),
            'verified_voltage': bool(selected) and len(selected) == len(indices) and
                                all(unit(c) in {'v', 'mv', 'uv', 'nv'} for c in selected + auxiliary),
            'has_eog': 'eog' in refs, 'has_ecg': 'ecg' in refs, 'has_emg': 'emg' in refs,
            'comparison_groups': dict(counts), 'min_group_channels': min(counts.values()) if counts else None,
            'has_sleep_stages': annotation.get('format') == 'sleep_stages_tsv',
            'has_task_events': annotation.get('format') == 'bids_events_tsv',
            'has_clinical_events': annotation.get('format') == 'clinical_events_tsv',
            'reference_scheme': reference_scheme,
            'has_coordinates': bool(record.get('verified_electrode_coordinates')),
            'has_epochs': bool(record.get('verified_epochs')),
            'preprocessing_highpass_hz': preprocessing.get('highpass_hz') if preprocessing.get('verified') is True else None,
            'preprocessing_lowpass_hz': preprocessing.get('lowpass_hz') if preprocessing.get('verified') is True else None,
            'preprocessing_verified': preprocessing.get('verified') is True, 'context': context}


def describe_data(record, config=None):
    facts = data_facts(record, config)
    defaults = context_defaults(record)
    tags = []

    def tag(key, label, value, display, source, *, known=True, kind='technical', note=''):
        tags.append({'key': key, 'label': label, 'value': copy.deepcopy(value), 'display': display,
                     'kind': kind, 'source': source, 'status': 'known' if known else 'unknown', 'note': note})

    modality = record.get('modality', 'unknown')
    tag('modality', '模态', modality, {'scalp_eeg': '头皮 EEG', 'ecog': 'ECoG', 'seeg': 'sEEG', 'extracellular': '细胞外电生理', 'other': '其他模态', 'unknown': '模态未确认'}.get(modality, modality),
        record.get('modality_source', '登记信息；格式本身不能证明电极位置'), known=modality != 'unknown')
    format_ = record.get('metadata', {}).get('format', 'unknown')
    tag('format', '格式', format_, format_ if format_ != 'unknown' else '格式未核验', '接入器核验', known=format_ != 'unknown')
    tag('n_eeg', '分析导联', facts['n_eeg'], f"{facts['n_eeg']} 道 EEG", '本次明确的通道索引配置')
    fs = facts['sampling_rate_hz']
    tag('sampling_rate_hz', '采样率', fs, f'{fs:g} Hz' if fs else '采样率待核验', '文件元数据与选道', known=fs is not None)
    tag('verified_voltage', '电压单位', facts['verified_voltage'], '电压单位已登记' if facts['verified_voltage'] else '电压单位待核验',
        '读取模块元数据；执行时再核对标定', known=facts['verified_voltage'])
    for kind in ('eog', 'ecg', 'emg'):
        flag = facts['has_' + kind]
        tag('has_' + kind, kind.upper(), flag, ('已配置 ' if flag else '未配置 ') + kind.upper(), '辅助导联索引配置',
            note='未配置表示当前分析不可使用；不推断原文件是否另有未确认的辅助信号。')
    groups = facts['comparison_groups']
    tag('reference_groups', '比较组', groups or None, ' / '.join(f'{name}: {count}道' for name, count in groups.items()) if groups else '比较组未声明',
        '登记的参考比较组；未自动重参考', known=bool(groups))
    scheme = facts['reference_scheme']
    tag('reference_scheme', '导联构型', scheme, {'unknown': '参考构型未核实', 'common_reference': '共同参考', 'linked_ears': '连接耳参考', 'bipolar': '双极导联', 'mixed': '混合参考'}[scheme],
        '数据集来源及导联登记', known=scheme != 'unknown', note='双极导联不能直接套用普通共同参考下的跨通道相似性判断。')
    tag('sleep_stages', '状态标注', facts['has_sleep_stages'], '有睡眠分期' if facts['has_sleep_stages'] else '未登记睡眠分期', '配套标注登记', note='状态标注不是质量标签。')
    tag('task_events', '任务事件', facts['has_task_events'], '有任务事件' if facts['has_task_events'] else '未登记任务事件', '配套标注登记', note='有事件不表示已形成可用于交叉验证的试次集合。')
    tag('clinical_events', '临床事件', facts['has_clinical_events'], '有临床事件标注' if facts['has_clinical_events'] else '未登记临床事件', '配套标注登记', note='发作等病理事件不是伪迹真值，不输入质量检测或扣分。')
    tag('coordinates', '电极位置', True if facts['has_coordinates'] else None, '已登记位置' if facts['has_coordinates'] else '位置未核实',
        '坐标登记', known=facts['has_coordinates'], note='不凭通道名称自动赋予坐标或空间邻接。')
    tag('preprocessing', '滤波处理史', record.get('preprocessing') if facts['preprocessing_verified'] else None,
        '已有处理记录' if facts['preprocessing_verified'] else '滤波史未核实', '数据来源说明', known=facts['preprocessing_verified'],
        note='采样率足够并不能证明高频仍被保留；未知滤波史限制高频结论。')
    for key, label in [('disease', '疾病背景'), ('age_group', '年龄分组'), ('task', '任务场景')]:
        value = facts['context'][key]
        source = '登记的实验场景' if key == 'task' and value == defaults[key] and value != 'unknown' else '本次背景配置（未作为独立医学核实）'
        registered = record.get('default_config', {}).get('context_tags', {}).get(key)
        if value == registered and record.get('context_evidence', {}).get(key):
            source = '数据集资料登记：' + record['context_evidence'][key]
        tag(key, label, value, dict(CONTEXT_OPTIONS[key])[value], source, known=value != 'unknown', kind='context',
            note='用于解释和后续分层验证；本版不据此修改质量阈值或打分。')
    return tags
