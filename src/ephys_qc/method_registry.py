"""Method-level descriptions and gates, separate from top-level module choices."""
from .tagging import data_facts
from .modalities import ROUTES, DESCRIPTIVE, route
import math

UPSTREAM = {'name': 'BrainElecQC 0.1.0', 'url': 'https://github.com/Jlei61/BrainElecQC', 'license': '上游仓库许可待确认；仅使用本地安装包'}
PROJECT = {'name': '本平台', 'url': '', 'license': '本地项目；尚未发布许可'}


_DOMAINS = (
    ('data_intake', '数据与元信息', ('M01', 'M02')),
    ('signal_integrity', '信号完整性', ('M03',)),
    ('spectrum_interference', '频谱与干扰', ('M04',)),
    ('channel_quality', '通道质量', ('M05',)),
    ('artifacts', '伪迹线索', ('M06',)),
    ('events_sync', '事件与时间', ('M07',)),
    ('reporting', '结果与报告', ('M08', 'M09')),
)
_DOMAIN_BY_MODULE = {module: (id_, label) for id_, label, modules in _DOMAINS for module in modules}
_ACTIVATION = {
    'basic': ('with_module', '随模块运行'),
    'conditional': ('conditional', '满足条件'),
    'optional': ('manual_extension', '手动扩展'),
}


def tool_domains():
    """Current functional domains, separate from modality and activation gates.

    New domains (for example spike/unit quality) can be registered when methods
    exist. An unimplemented domain is not advertised as a current capability.
    """
    return [{'id': id_, 'label': label, 'module_ids': list(modules)}
            for id_, label, modules in _DOMAINS]


def _classification(method, modality='scalp_eeg'):
    """Presentation metadata only; never alters a method's eligibility rules."""
    domain, label = _DOMAIN_BY_MODULE[method['module_id']]
    activation, activation_label = _ACTIVATION[method['category']]
    if method['implementation'] == 'planned':
        scope = ('计划面向' + route(modality)['label'] +
                 '；尚未接入，未完成本平台执行验证。未声明其他模态支持。')
    elif modality in {'seeg', 'extracellular'}:
        scope = route(modality)['scope_note']
    elif modality == 'ecog':
        scope = '当前ECoG基础描述路线；仅声明工程执行范围，不代表伪迹准确性已验证，不迁移头皮判坏阈值。'
    elif domain == 'data_intake':
        scope = ('当前声明的质控工程执行范围仅限头皮 EEG。读器提取其他模态元信息，'
                 '不表示已验证其质控流程；通用处理思路不等于跨模态支持。')
    else:
        scope = ('当前已验证的工程执行范围仅限头皮 EEG，仍需满足本方法条件；'
                 '不表示已验证科学准确性或其他脑电模态。')
    planned = method['implementation'] == 'planned'
    return {**method, 'domain': domain, 'domain_label': label,
            'activation': activation, 'activation_label': activation_label,
            'supported_modalities': [] if planned else [modality],
            'intended_modalities': [modality] if planned else [], 'scope_note': scope}


def _method(id_, name, module, category, description, requirements, outputs, *, source=None, implementation='available', limitations=None):
    return {'id': id_, 'name': name, 'module_id': module, 'category': category, 'description': description,
            'inputs': requirements.copy(), 'requirements': requirements.copy(), 'outputs': outputs,
            'source': dict(source or UPSTREAM), 'implementation': implementation,
            'limitations': limitations or ['计算完成不等于质量合格；候选需复核。'], 'optional_extension': False}


def methods(modality='scalp_eeg'):
    if modality not in ROUTES:
        raise ValueError('Unsupported QC modality: ' + str(modality))
    rows = [
        _method('edf_reader', '多格式读取与来源核验', 'M01', 'basic', '核对文件结构、时钟、索引与来源指纹。', ['已核验文件及配套文件'], ['结构与来源核验']),
        _method('voltage_calibration', '单位与电压标定', 'M01', 'basic', '确认数字值可转换成物理电压。', ['有效单位及逐道标定'], ['标定信息', '无法评估原因']),
        _method('qc_plan', '数据标签与检查计划', 'M02', 'basic', '根据已知技术条件选择方法；背景标签用于解释。', ['通道选择', '技术头', '可选实验背景'], ['冻结计划', '标签与适用性'], source=PROJECT),
        _method('continuity', '缺失、恒值与端点平台', 'M03', 'basic', '检查非有限样本、恒值区间及标定端点平台。', ['连续信号', '端点判断需标定'], ['通道和原始时间候选']),
        _method('welch_psd', 'Welch功率谱', 'M04', 'basic', '描述各通道频率能量分布。', ['电压信号', '采样率'], ['PSD原值与频段']),
        _method('thomson_line', '工频及可测谐波', 'M04', 'conditional', '在实际可测频带内检查窄带干扰。', ['采样率满足待测频率', '足够的分析窗口'], ['工频观察量与候选']),
        _method('spectral_model', '背景谱拟合与α功率', 'M04', 'conditional', '分离背景谱与谱峰，提供研究描述量。', ['足够时长和可测频带'], ['谱拟合', 'α功率'], limitations=['谱形与状态、年龄、疾病有关，不能直接把差异判为低质量。', '不满足拟合时长的尾窗保留未评。']),
        _method('prep_nonspatial', 'PREP非空间坏道线索', 'M05', 'conditional', '结合幅度、相关、高频与掉线等分项给出候选。', ['已声明参考比较组', '每组至少4道为当前实现门槛'], ['分项指标', '通道候选'], limitations=['4道门槛是当前实现条件，不是统一行业阈值。', '既有两份全长ds002034结果与来源坏道标签不一致；尚未证明准确率。']),
        _method('ecg_locked', 'ECG锁时污染线索', 'M06', 'conditional', '利用已确认的心电导联核对EEG中的锁时成分。', ['已配置ECG辅助导联', '相同采样时钟'], ['ECG事件及支持证据']),
        _method('eog_locked', 'EOG锁时污染线索', 'M06', 'conditional', '利用已确认的眼电导联核对相关事件。', ['已配置EOG辅助导联', '相同采样时钟'], ['EOG事件及支持证据']),
        _method('hf_burst', '高频突发与EMG支持', 'M06', 'conditional', '提取高频突发，再判断是否有独立EMG支持。', ['足够可测高频带', 'M03连续性保护区', 'EMG用于确认性支持'], ['高频候选', 'EMG支持状态'], limitations=['无EMG时仅是高频线索；不等同于已确认肌电伪迹。']),
        _method('sleep_timeline', '睡眠分期时间核对', 'M07', 'conditional', '将睡眠分期映射到原始时间轴并标出未知覆盖。', ['已登记睡眠分期'], ['阶段覆盖和未知区间'], source=PROJECT),
        _method('task_timeline', '任务事件时间核对', 'M07', 'conditional', '核对本次选区事件与原始记录时间。', ['已登记任务事件'], ['事件列表及样本定位'], source=PROJECT, limitations=['适配已登记的event_name事件表，包括ds002034及EEGMMIDB来源转换表；不等于通用BIDS验证。', '事件不是质量真值。']),
        _method('clinical_timeline', '临床事件时间核对', 'M07', 'conditional', '将来源标注的临床事件映射到原始记录时间。', ['已登记临床事件表'], ['选区事件和时长'], source=PROJECT, limitations=['发作等病理信号不是伪迹；事件标签不输入检测器或质量分。', '无标注区间不自动解释为正常。']),
        _method('aggregate', '分项汇总与未评说明', 'M08', 'basic', '汇总实际完成、未评、失败和未选择的方法。', ['实际模块输出'], ['分项结果', '未校准总分'], source=PROJECT),
        _method('report', '证据报告', 'M09', 'basic', '记录方法、参数、来源、范围与人工复核状态。', ['检查结果及原始选区'], ['HTML报告', 'JSON证据', '波形图'], source=PROJECT),
    ]
    from .extensions import extension_specs
    for extension in extension_specs():
        if extension.get('research_modalities'):
            continue
        spec = dict(extension)
        spec.update(optional_extension=True, implementation='available', category='optional')
        rows.append(spec)
    rows.extend([
        _method('pyprep_ransac', 'PyPREP空间预测 / RANSAC', 'M05', 'optional', '比较实际信号与其他电极空间预测的一致性。',
                ['已核实电极坐标', '足够多的可用EEG通道', '可比较参考与采集条件'], ['空间坏道候选'],
                source={'name': 'PyPREP', 'url': 'https://pyprep.readthedocs.io/en/stable/generated/pyprep.NoisyChannels.html', 'license': 'MIT'}, implementation='planned',
                limitations=['尚未接入；安装了库不代表平台已具备该功能。', '不凭通道名称自动补坐标；需真实数据验收。']),
        _method('autoreject_epochs', 'local AutoReject试次质量估计', 'M03', 'optional', '在分段数据中估计局部通道阈值和试次建议；与已接入的全局阈值方法不同。',
                ['足够的试次/窗口', '明确分段规则', 'local AutoReject拟合需已核实电极坐标'], ['坏试次与通道建议'],
                source={'name': 'autoreject', 'url': 'https://autoreject.github.io/stable/index.html', 'license': 'BSD-3-Clause'}, implementation='planned',
                limitations=['尚未接入；有任务事件不等于已有足够且可比的试次。', '后续接入只提取评估结果，不默认删除或插值。']),
        _method('ica_iclabel', 'ICA成分 / ICLabel', 'M06', 'optional', '对独立成分分类，辅助人工判断来源。',
                ['足够数据和可用EEG通道', '已核对的坐标、秩、参考与滤波处理', '满足模型训练条件的ICA分解'], ['成分类别与概率'],
                source={'name': 'MNE-ICALabel', 'url': 'https://mne.tools/mne-icalabel/stable/generated/examples/00_iclabel.html', 'license': 'BSD-3-Clause'}, implementation='planned',
                limitations=['尚未接入；平均参考、1–100Hz和extended-infomax等训练条件需要单独核对。', '分类概率不是质量分，不自动移除成分。']),
    ])
    from .method_descriptions import enrich_method
    from .research_methods import research_methods
    candidates = [_classification(row, modality) for row in research_methods(modality)]
    if modality in DESCRIPTIVE:
        from .descriptive_catalog import custom_methods, _adapt
        shared = [row for row in rows if row['module_id'] in {'M01', 'M02', 'M07', 'M08', 'M09'}]
        common = [enrich_method(_classification(row, modality)) for row in shared]
        for row in common:
            doc = row['documentation']
            if row['id'] == 'edf_reader':
                doc['when_not_to_use'] = '不支持未建模的断续EDF、EEGLAB分段数据和分卷FIF；多文件须完整。文件可读不证明采集位置，ECoG须明确确认，不自动重采样。'
            elif row['id'] == 'voltage_calibration':
                doc.update(how_it_works='按格式读取器核验源单位与标定，统一返回原始物理电压V；不对波形重参考、插值或重采样。',
                           when_to_use='已明确确认ECoG，分析及辅助通道电压单位可核验时。',
                           when_not_to_use='单位未知或所选通道不是电压时不得进入ECoG分析；不凭触点名猜单位。',
                           upstream_call='ephys_qc.readers.open_reader；ephys_qc.modules.m02.read_window',
                           implementation_origin='按实际格式使用BrainElecQC或MNE读取器；ECoG测量不调用头皮判坏阈值。')
        common = [_adapt(row, modality) for row in common]
        if modality == 'extracellular':
            for row in common:
                if row['id'] in {'edf_reader', 'voltage_calibration'}:
                    row['source'] = dict(PROJECT)
                    row['documentation']['references'] = [
                        {'title': 'SpikeGLX metadata and sample conversion', 'url': 'https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html', 'kind': 'official documentation'},
                        {'title': 'NWB extracellular electrophysiology', 'url': 'https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html', 'kind': 'official documentation'},
                        {'title': 'SpikeGLX IMRO and probe mappings', 'url': 'https://billkarsh.github.io/SpikeGLX/help/imroTables/', 'kind': 'official documentation'}]
                    row['documentation']['version_note'] = 'Native format readers; SpikeGLX NP1 real AP/LF, NP2 synthetic; NWB2 continuous ElectricalSeries.'
                if row['id'] == 'edf_reader':
                    row.update(name='Neuropixels连续电压读取与来源核验', description='核验SpikeGLX或NWB所选信号，保留通道身份、电极映射、样本时钟及处理史。')
                    row['documentation'].update(
                        purpose='读取有明确设备身份的Neuropixels连续电压。',
                        how_it_works='SpikeGLX核对BIN/META及标定；NWB核对ElectricalSeries路径、单位、规则时钟、电极映射与设备声明。',
                        when_to_use='已支持的SpikeGLX AP/LF或NWB2/HDF5连续ElectricalSeries。',
                        when_not_to_use='裸BIN、压缩cbin、NIDQ、sorting/unit、未支持探针或不一致长度与标定。',
                        upstream_call='ephys_qc.readers.open_reader',
                        implementation_origin='本项目格式适配器；保留源标定及处理声明，不调用头皮流程。')
                elif row['id'] == 'voltage_calibration':
                    row['documentation'].update(
                        how_it_works='SpikeGLX按量程与增益标定；NWB按conversion、channel_conversion、offset及明确单位标定为V。',
                        upstream_call='ephys_qc.readers.open_reader',
                        implementation_origin='SpikeGLX已用官方readSGLX核对；NWB通过h5py独立核对源切片及单位。')
        return sorted(common + [_classification(row, modality) for row in custom_methods(modality)] + candidates, key=lambda row: row['module_id'])
    return [enrich_method(_classification(row)) for row in rows] + candidates


def _hf_applicability(facts, config):
    """Mirror the existing BrainElecQC bandwidth/duration gates, without importing it."""
    parameters = {'lower_frequency_hz': 30., 'upper_frequency_hz': 100., 'upper_sampling_fraction': .45,
                  'min_duration_seconds': 10.}
    supplied = config.get('method_config', {}).get('muscle', {})
    parameters.update({key: supplied[key] for key in parameters if key in supplied})
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in parameters.values()):
        return 'blocked', '高频方法的频带/时长参数无效。'
    low, high, fraction, duration = (parameters[k] for k in ('lower_frequency_hz', 'upper_frequency_hz', 'upper_sampling_fraction', 'min_duration_seconds'))
    fs = facts['sampling_rate_hz']
    if low >= high or fraction >= .5 or duration < 10:
        return 'blocked', '高频方法的频带/时长参数不满足当前方法要求。'
    if fs is None or min(high, fraction * fs) - low < 20:
        return 'blocked', '当前采样率下有效高频带不足20 Hz，这是现有方法的实现门槛。'
    if facts['window_seconds'] < duration:
        return 'blocked', f'当前窗口短于该方法设定的{duration:g}秒。'
    if not facts['has_emg']:
        return 'partial', '可计算高频线索，但没有EMG导联支持，不能确认为肌电。'
    return 'ready', '采样、时长与EMG配置初步满足；仍需运行核对可用证据。'


def evaluate_methods(record, config, selected_modules):
    facts = data_facts(record, config)
    selected = set(selected_modules)
    extensions = set(config.get('method_config', {}).get('extensions', []))
    extension_params = config.get('method_config', {}).get('extension_parameters', {})
    from .extensions import evaluate_extension
    result = []
    for method in methods(record.get('modality', 'scalp_eeg')):
        mid, id_ = method['module_id'], method['id']
        chosen = mid in selected and (not method['optional_extension'] or id_ in extensions)
        status, reason, parameters = 'ready', '适用条件初步满足，仍以实际执行与子方法结果为准。', None
        if method['implementation'] == 'planned':
            status, reason, chosen = 'planned', '扩展目录已登记；尚未接入和完成真实数据验收。', False
        elif not chosen:
            status, reason = 'not_selected', '本次未选择该模块或可选增强方法。'
        elif method['optional_extension']:
            gate = evaluate_extension(id_, facts, extension_params.get(id_))
            status, reason, parameters = gate['status'], gate['reason'], gate.get('parameters')
        elif id_.endswith('_line_description') and record.get('modality') in DESCRIPTIVE and any(f >= facts['sampling_rate_hz'] / 2 for f in config['method_config'][route(record['modality'])['key']]['line_frequencies_hz']):
            status, reason = 'partial', '部分配置频率超出可测范围；仅保留可测窄带原值，不作干扰判定。'
        elif id_ == 'ecg_locked' and not facts['has_ecg']:
            status, reason = 'blocked', '没有确认并配置ECG导联。'
        elif id_ == 'eog_locked' and not facts['has_eog']:
            status, reason = 'blocked', '没有确认并配置EOG导联。'
        elif id_ == 'hf_burst':
            status, reason = _hf_applicability(facts, config)
        elif id_ == 'prep_nonspatial' and (not facts['min_group_channels'] or facts['min_group_channels'] < config.get('method_config', {}).get('bad_channels', {}).get('min_group_channels', 4)):
            minimum = config.get('method_config', {}).get('bad_channels', {}).get('min_group_channels', 4)
            status, reason = 'partial', f'比较组未声明或不足本次设定的{minimum}道，保留描述量，相关组阈值不启用。'
        elif id_ == 'sleep_timeline' and not facts['has_sleep_stages']:
            status, reason = 'blocked', '未登记睡眠分期；不通过疾病或任务标签推测睡眠阶段。'
        elif id_ == 'task_timeline' and not facts['has_task_events']:
            status, reason = 'blocked', '未登记支持的事件文件；仅填写任务标签不能替代事件。'
        elif id_ == 'clinical_timeline' and not facts['has_clinical_events']:
            status, reason = 'blocked', '未登记临床事件文件；疾病背景标签不能替代原始事件标注。'
        elif id_ == 'spectral_model':
            status, reason = 'partial', '全段与每个窗口分别核验频带和时长，短尾窗可能未评。'
        elif id_ == 'thomson_line' and facts['sampling_rate_hz'] and facts['sampling_rate_hz'] <= 120:
            status, reason = 'partial', '采样率不足以覆盖全部50/60Hz及其谐波；仅评估可测频率。'
        elif id_ == 'voltage_calibration' and not facts['verified_voltage']:
            status, reason = 'partial', '技术头未确认全部选中通道单位；执行时必须核验物理标定。'
        result.append({'id': id_, 'module_id': mid, 'name': method['name'], 'status': status,
                       'reason': reason, 'selected': chosen, 'parameters': parameters})
    return result
