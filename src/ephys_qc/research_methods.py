"""Source-reviewed optional research adapters; never default quality decisions.

Reviewed 2026-10-31. Only standard-library imports are allowed here. The English
strings also supply the marked section of web/i18n.js; they do not translate data.
"""
from copy import deepcopy

TRANSLATIONS = {}


def _t(zh, en):
    TRANSLATIONS[zh] = en
    return zh


_PENDING = _t(
    '尚未接入；本次仅核对上游来源和登记方法，没有运行或验证算法。',
    'Not integrated. This review registers upstream sources only; the algorithm has not been run or validated here.')
_ORIGIN = _t(
    '仅登记拟接入的上游调用；没有复制上游算法、安装依赖或改变现有计算。',
    'Proposed upstream call only; no algorithm was copied, dependency installed, or existing computation changed.')
_CALL = _t('尚无平台执行调用；拟调用：', 'No platform execution call; proposed API: ')


def _candidate(identifier, name, module, modalities, purpose, how, interpretation,
               requirements, outputs, exclusions, api, source, references, version):
    return {
        'id': identifier, 'name': name, 'module_id': module, 'category': 'optional',
        'description': purpose, 'inputs': requirements.copy(), 'requirements': requirements,
        'outputs': outputs, 'source': source, 'implementation': 'planned',
        'optional_extension': False, 'limitations': [_PENDING, interpretation, exclusions],
        'research_modalities': modalities, 'reviewed_on': '2026-10-31',
        'documentation': {
            'purpose': purpose, 'how_it_works': how, 'interpretation': interpretation,
            'when_to_use': '；'.join(requirements), 'when_not_to_use': exclusions,
            'validation_status': _PENDING, 'upstream_call': _CALL + api,
            'implementation_origin': _ORIGIN, 'version_note': version,
            'references': [{'title': title, 'url': url, 'kind': kind}
                           for title, url, kind in references],
        },
    }


_ROWS = [
    _candidate(
        'faster_channels', _t('FASTER 统计坏道', 'FASTER statistical bad channels'), 'M05', ['scalp_eeg'],
        _t('用多个统计特征寻找异常通道，补充现有PREP与LOF线索。',
           'Find channel outliers across several statistical features, complementing PREP and LOF.'),
        _t('拟采用MNE-FASTER的坏道步骤：在明确分段后的EEG上计算方差、相关性、Hurst指数、峰度和可测工频特征，按特征保留候选。',
           'Use the MNE-FASTER channel step on explicitly epoched EEG: variance, correlation, Hurst exponent, kurtosis and measurable line-noise features, retaining candidates by metric.'),
        _t('FASTER是成熟方法族；该Python实现不是MNE内置功能，也不等于完整FASTER流水线。统计离群不是伪迹真值。',
           'FASTER is an established method family. This Python implementation is not built into MNE and this entry is not the full FASTER pipeline. Outliers are not artifact ground truth.'),
        [_t('足够多且可比较的头皮EEG通道；明确分段与参考；逐项核对可测频带。',
            'Sufficient comparable scalp EEG channels, explicit epochs and reference, and measurable bands for each metric.')],
        [_t('按统计特征列出的通道候选', 'Channel candidates grouped by statistical metric')],
        _t('不直接用于少通道PSG或颅内记录；不把拼接窗口当任务试次；不自动删道。上游依赖MNE内部接口，接入须做版本兼容测试。',
           'Do not directly apply to sparse PSG or intracranial recordings, treat windows as task trials, or delete channels. Upstream uses internal MNE APIs, requiring compatibility tests.'),
        'mne_faster.find_bad_channels(..., return_by_metric=True)',
        {'name': 'MNE-FASTER', 'url': 'https://github.com/wmvanvliet/mne-faster', 'license': 'BSD-3-Clause'},
        [('MNE-FASTER source', 'https://github.com/wmvanvliet/mne-faster/blob/main/mne_faster/faster.py', '上游代码'),
         ('FASTER original paper (2010)', 'https://doi.org/10.1016/j.jneumeth.2010.07.015', '算法论文'),
         ('EEGLAB extension listing', 'https://eeglab.org/others/EEGLAB_Extensions.html', '官方文档')],
        _t('2026-10-31核对；上游最新列出版本1.2.2，仓库最近推送2025-02-12，未归档。本平台尚未做安装兼容测试。',
           'Reviewed 2026-10-31: latest listed release 1.2.2; repository last pushed 2025-02-12, not archived. Installation compatibility is untested here.')),
    _candidate(
        'asr_bursts', _t('ASR 突发伪迹', 'ASR artifact bursts'), 'M06', ['scalp_eeg'],
        _t('记录异常突发的候选区间及重建影响，作为可选清洗评估。',
           'Record candidate artifact bursts and reconstruction effects as an optional cleaning evaluation.'),
        _t('ASR由相对干净的校准数据估计协方差与阈值，再识别偏离校准分布的子空间。clean_rawdata还包含独立的坏道与窗口处理步骤。',
           'ASR estimates covariance and thresholds from relatively clean calibration data, then identifies subspaces departing from that distribution. clean_rawdata also includes separate channel and window operations.'),
        _t('这是重建或剔除工具，不能把被修改比例解释为质量分。校准段、阈值、随机性和前后差异必须保存；原始信号不覆盖。',
           'This reconstructs or rejects data; the modified fraction is not a quality score. Save calibration, thresholds, randomness and before/after differences, preserving the original.'),
        [_t('连续多通道头皮EEG；可说明来源的校准段；明确秩、参考、滤波及所用实现许可。',
            'Continuous multichannel scalp EEG, traceable calibration data, and explicit rank, reference, filtering and implementation licensing.')],
        [_t('突发候选及清洗前后差异（拟输出）', 'Burst candidates and before/after differences (proposed)')],
        _t('不直接迁移至发作期颅内或Neuropixels数据。上游ASR文件另含UC商业使用许可说明，不能仅凭仓库GPL标识认定可直接商用。',
           'Do not directly transfer to ictal intracranial or Neuropixels recordings. ASR files contain a separate UC commercial-use notice; the repository GPL label alone does not establish commercial permission.'),
        'clean_artifacts / asr_calibrate / asr_process',
        {'name': 'EEGLAB clean_rawdata / ASR', 'url': 'https://github.com/sccn/clean_rawdata',
         'license': _t('仓库GPL-3.0；ASR文件另有UC使用条款，接入前逐文件核对。',
                       'Repository GPL-3.0; ASR files have additional UC terms requiring file-level review.')},
        [('EEGLAB clean_rawdata tutorial', 'https://eeglab.org/tutorials/06_RejectArtifacts/cleanrawdata.html', '官方文档'),
         ('ASR calibration and license notice', 'https://github.com/sccn/clean_rawdata/blob/master/asr_calibrate.m', '上游代码')],
        _t('2026-10-31核对官方教程及源码；clean_rawdata为EEGLAB默认插件，仓库最近推送2026-09-07。本平台未安装MATLAB适配。',
           'Official tutorial and code reviewed 2026-10-31. clean_rawdata is a default EEGLAB plugin; last repository push 2026-09-07. No MATLAB adapter is installed here.')),
    _candidate(
        'cleanline', _t('CleanLine 工频处理评估', 'CleanLine line-noise evaluation'), 'M04', ['scalp_eeg'],
        _t('评估正弦工频的拟合、残留和处理影响。', 'Evaluate fitted sinusoidal line noise, residuals and processing effects.'),
        _t('CleanLine用多窗谱估计和F统计量识别正弦成分，再以回归估计并移除。计划保留原始与处理副本的频谱比较。',
           'CleanLine identifies sinusoidal components using multitaper estimates and an F statistic, then estimates and removes them by regression. Preserve spectra of the original and processed copy.'),
        _t('与现有Thomson工频检测有关，但当前平台没有调用CleanLine。移除工频不证明其他频段或神经信号未受影响。',
           'Related to the existing Thomson line-noise detector, but CleanLine is not currently called. Removing line noise does not prove preservation of other bands or neural signals.'),
        [_t('工频及谐波处于可测频带；明确窗长、频率扫描和原始处理史；MATLAB与EEGLAB环境。',
            'Measurable line frequencies and harmonics, explicit window and frequency scan settings, processing history, and MATLAB with EEGLAB.')],
        [_t('正弦拟合、残留PSD与处理差异（拟输出）', 'Sinusoidal fits, residual PSD and processing differences (proposed)')],
        _t('只对副本评估，不默认去工频；谱峰不自动证明电源干扰，尚未声明颅内适用性。依赖包许可需单独核对。',
           'Evaluate a copy only, without default cleaning. Peaks do not establish power-line interference; intracranial applicability is not claimed. Review dependency licenses separately.'),
        'cleanline / pop_cleanline',
        {'name': 'EEGLAB CleanLine', 'url': 'https://eeglab.org/plugins/cleanline/',
         'license': _t('cleanline.m为GPL-3.0-or-later；捆绑依赖须分别核对。', 'cleanline.m: GPL-3.0-or-later; review bundled dependencies separately.')},
        [('CleanLine official documentation', 'https://eeglab.org/plugins/cleanline/', '官方文档'),
         ('CleanLine source and license', 'https://github.com/sccn/cleanline/blob/master/cleanline.m', '上游代码')],
        _t('2026-10-31核对；EEGLAB官方插件，仓库最近推送2025-02-07，未归档。源码许可比仓库自动识别结果更具体。',
           'Reviewed 2026-10-31: official EEGLAB plugin; last repository push 2025-02-07, not archived. Source licensing is more specific than automatic repository detection.')),
    _candidate(
        'zapline_plus', _t('Zapline-plus 自适应工频', 'Zapline-plus adaptive line noise'), 'M04', ['scalp_eeg'],
        _t('评估随时间变化的窄带干扰及分段处理效果。', 'Evaluate time-varying narrowband interference and chunk-wise processing.'),
        _t('在ZapLine的频谱与空间分解基础上，自动寻找噪声频率、划分空间稳定片段并选择去除成分数量。',
           'Extends ZapLine spectral and spatial decomposition with noise-frequency detection, spatially stable chunks and automatic selection of removed components.'),
        _t('属于清洗扩展而非独立质量标准；需比较目标频带、邻近频带和前后波形，保留原始数据。',
           'A cleaning extension, not an independent quality standard. Compare target and neighboring bands and waveforms, retaining original data.'),
        [_t('多通道头皮EEG；足够的稳定片段；明确频谱参数、通道组与MATLAB依赖。',
            'Multichannel scalp EEG, sufficient stable chunks, and explicit spectral settings, channel groups and MATLAB dependencies.')],
        [_t('噪声频率、片段、去除成分及前后谱（拟输出）', 'Noise frequencies, chunks, removed components and before/after spectra (proposed)')],
        _t('不默认用于少通道、病理高频或Neuropixels；不能把生理窄带活动自动当作噪声。',
           'No default use for sparse channels, pathological high frequencies or Neuropixels; physiological narrowband activity must not automatically be labeled noise.'),
        'clean_data_with_zapline_plus',
        {'name': 'Zapline-plus', 'url': 'https://github.com/MariusKlug/zapline-plus', 'license': 'GPL-3.0'},
        [('Zapline-plus EEGLAB documentation', 'https://eeglab.org/plugins/zapline-plus/', '官方文档'),
         ('Zapline-plus source', 'https://github.com/MariusKlug/zapline-plus', '上游代码')],
        _t('2026-10-31核对；EEGLAB官方插件目录收录，仓库最近推送2023-04-14，未归档。更新较少，拟冻结版本做回归。',
           'Reviewed 2026-10-31: listed in the official EEGLAB plugins; last repository push 2023-04-14, not archived. Infrequent updates call for a pinned version and regression checks.')),
    _candidate(
        'fieldtrip_zvalue', _t('FieldTrip 分段伪迹线索', 'FieldTrip segment artifact evidence'), 'M06', ['scalp_eeg', 'ecog', 'seeg'],
        _t('按明确的通道组和频带检测时间区间异常。', 'Detect interval outliers in explicitly selected channel groups and bands.'),
        _t('ft_artifact_zvalue在带边界扩展的数据上提取所选特征，标准化并汇总通道证据，输出候选起止样本；检测与剔除是两个步骤。',
           'ft_artifact_zvalue extracts configured features with padding, standardizes and combines channel evidence, and returns candidate sample intervals. Detection and rejection are separate steps.'),
        _t('FieldTrip用于EEG与iEEG分析，但这不证明同一频带或阈值跨模态有效。颅内拟接入只保留待复核线索，发作及HFO不能据幅度判坏。',
           'FieldTrip supports EEG and iEEG analysis, but this does not validate shared bands or thresholds. Intracranial integration would retain review candidates only; amplitude alone must not reject seizures or HFOs.'),
        [_t('明确原始样本坐标、通道比较组、参考、频带、边界扩展与阈值；颅内需独立样例验证。',
            'Explicit source sample coordinates, channel groups, reference, bands, padding and thresholds; intracranial use requires independent examples.')],
        [_t('候选起止样本与检测配置', 'Candidate onset/offset samples and detection configuration')],
        _t('不复制官方MEG示例中的110–140Hz或跳变阈值作为EEG/iEEG默认值；不自动调用ft_rejectartifact。',
           'Do not copy the MEG tutorial 110–140 Hz band or jump thresholds as EEG/iEEG defaults; do not automatically call ft_rejectartifact.'),
        'ft_artifact_zvalue',
        {'name': 'FieldTrip', 'url': 'https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/', 'license': 'GPL-3.0'},
        [('FieldTrip automatic artifact tutorial', 'https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/', '官方文档'),
         ('FieldTrip source', 'https://github.com/fieldtrip/fieldtrip', '上游代码')],
        _t('2026-10-31核对官方教程；仓库最近推送2026-10-22，未归档。已有方法生态不等于本平台完成MATLAB或颅内验证。',
           'Official tutorial reviewed 2026-10-31; last repository push 2026-10-22, not archived. An established ecosystem is not platform validation of MATLAB or intracranial use.')),
    _candidate(
        'spikeinterface_bad_channels', _t('SpikeInterface / IBL 坏道', 'SpikeInterface / IBL bad channels'), 'M05', ['extracellular'],
        _t('补充Neuropixels原始电压的坏道候选分类。', 'Add candidate bad-channel classifications for raw Neuropixels voltage.'),
        _t('detect_bad_channels提供std、mad和coherence+psd等路线；IBL路线结合沿探针的相关证据与高频PSD，输出good、noise、dead、out标签。',
           'detect_bad_channels offers std, mad and coherence+psd routes. The IBL route combines along-probe correlation evidence with high-frequency PSD, yielding good, noise, dead and out labels.'),
        _t('这些是通道标签，不是分选单元质量。out是算法提出的脑外候选，不替代解剖证据；dead和out并非所有检测路线都有。',
           'These are channel labels, not sorted-unit quality. The out label is an algorithmic outside-brain candidate, not anatomical proof; dead and out are not available in every method.'),
        [_t('优先AP流；核实物理单位、探针几何与通道顺序；按probe/shank分别处理，固定抽样和滤波参数。',
            'Prioritize AP streams with verified physical units, geometry and channel order; process each probe/shank separately and freeze sampling and filtering settings.')],
        [_t('逐通道候选标签与方法配置', 'Per-channel candidate labels and method settings')],
        _t('不把同步字混入；不将AP默认高频阈值套到LF流；未知几何时不运行coherence+psd，不默认删道或插值。',
           'Exclude synchronization words; do not apply AP high-frequency defaults to LF streams. Block coherence+psd without geometry; do not remove or interpolate channels by default.'),
        'spikeinterface.preprocessing.detect_bad_channels',
        {'name': 'SpikeInterface / IBL', 'url': 'https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html', 'license': 'MIT'},
        [('SpikeInterface bad-channel documentation', 'https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html', '官方文档'),
         ('SpikeInterface implementation', 'https://github.com/SpikeInterface/spikeinterface/blob/main/src/spikeinterface/preprocessing/detect_bad_channels.py', '上游代码')],
        _t('2026-10-31核对官方文档及实现；仓库最近推送2026-10-30，未归档。本平台尚未建立Recording适配或验证阈值。',
           'Official docs and code reviewed 2026-10-31; last repository push 2026-10-30, not archived. A Recording adapter and threshold validation are still absent here.')),
]



# Execution follow-up: the historical source review remains in docs/.
_EXECUTION = {
    'faster_channels': (
        'FASTER 统计坏道', 'FASTER statistical bad channels',
        '调用MNE-FASTER 1.2.2的find_bad_channels。连续数据按固定段组织后参与通道统计；50/60Hz均可测时才启用line_noise。不作距离校正。',
        'Call MNE-FASTER 1.2.2 find_bad_channels on fixed continuous segments. Enable line_noise only when both 50 and 60 Hz are measurable. No reference-distance correction.',
        'mne_faster.find_bad_channels(return_by_metric=True, eeg_ref_corr=False)',
        '按特征列出通道候选；固定段不是任务试次，统计离群不等于伪迹。',
        'Channel candidates by metric. Fixed segments are not task trials; statistical outliers are not artifact ground truth.'),
    'spikeinterface_bad_channels': (
        'SpikeInterface AP 通道离群', 'SpikeInterface AP channel outliers',
        '调用SpikeInterface 0.104.2 detect_bad_channels的std/mad路径。输入V显式转为µV，按文件声明的shank分组，高通后固定种子抽样；不混入同步通道。',
        'Call SpikeInterface 0.104.2 detect_bad_channels with std/mad. Convert V to µV, group by file-declared shank, high-pass and sample with a fixed seed; exclude sync channels.',
        'spikeinterface.preprocessing.detect_bad_channels(method="mad" or "std")',
        '只输出good/noise；good表示未超本阈值，不是通道合格，也不是分选单元质量。coherence+psd、dead/out和LF未接入。',
        'Only good/noise labels. Good means below this threshold, not a passing channel or sorted-unit quality. coherence+psd, dead/out and LF are not integrated.'),
    'fieldtrip_zvalue': (
        'FieldTrip 差分区间线索', 'FieldTrip difference interval evidence',
        '调用ft_artifact_zvalue，特征固定为相邻差分绝对值、cumulative=no；保留最大单道z值。无带通、无边界扩展；从MATLAB一基闭区间映射到原始时钟半开区间。',
        'Call ft_artifact_zvalue with absolute sample differences and cumulative=no, retaining the maximum channel z value. No band-pass or padding. Map one-based inclusive samples to half-open source-clock intervals.',
        'ft_artifact_zvalue(absdiff="yes", cumulative="no", keepintermediate="yes")',
        'EEG、ECoG和sEEG共用这一描述性特征，不共享质量结论。病理放电也可能触发；候选不定位单道、不自动剔除。',
        'EEG, ECoG and sEEG share this descriptive feature, not quality conclusions. Pathological activity can trigger it. Intervals do not localize a channel and are not automatically rejected.'),
    'asr_bursts': (
        'ASR 重建影响评估', 'ASR reconstruction effects',
        '对副本做明确的1Hz四阶零相位高通，再调用clean_rawdata原版asr_calibrate/asr_process。必须显式确认窗口内至少30秒校准段，保留校准指纹、秩、矩阵和滤波器；lookahead=0。',
        'Apply an explicit fourth-order 1 Hz zero-phase high-pass to a copy, then call upstream asr_calibrate/asr_process. Explicitly confirm at least 30 s of calibration within the window; retain hashes, rank, matrices and filters. lookahead=0.',
        'clean_rawdata/asr_calibrate + asr_process; Octave subprocess',
        '保存相同高通副本之间的变化量与PSD，不把重建差异解释为伪迹比例或质量分。仅单窗口；秩不足、未确认校准或无预置谱滤波器时阻断。原始信号不覆盖。',
        'Save differences and PSD between identically high-pass-filtered copies, not artifact fractions or scores. Window only; block insufficient rank, unconfirmed calibration or missing upstream spectral filters. Preserve originals.'),
    'cleanline': (
        'CleanLine 工频处理评估', 'CleanLine line-noise evaluation',
        '调用官方cleanLineNoise新实现，仅处理明确指定的一个工频。多窗谱F检验和回归由上游执行；Octave的DPSS接口使用SciPy对称L2归一化窗。',
        'Call upstream cleanLineNoise, the newer CleanLine implementation, for one specified line frequency. Upstream performs multitaper F tests and regression; the Octave DPSS bridge uses symmetric L2-normalized SciPy tapers.',
        'cleanline/cleanLineNoise; scipy.signal.windows.dpss compatibility bridge',
        '前后PSD与变化量仅描述处理影响，不证明神经信号保留。末尾不足滑窗部分不处理；不自动补谐波，不覆盖原始信号。',
        'Before/after PSD and differences describe processing effects, not neural-signal preservation. Leave the incomplete sliding-window tail unchanged; do not add harmonics or overwrite originals.'),
    'zapline_plus': (
        'Zapline-plus 工频处理评估', 'Zapline-plus line-noise evaluation',
        '调用clean_data_with_zapline_plus。明确一个工频，把当前片段作为一个固定chunk；自动选择去除成分并调整sigma，保留配置和analytics。',
        'Call clean_data_with_zapline_plus for one explicit line frequency and one fixed chunk per selected window. Adapt removed components and sigma; retain configuration and analytics.',
        'clean_data_with_zapline_plus; fixed chunk, adaptiveNremove=1, adaptiveSigma=1',
        '本版未启用自动分段；至少32秒及8个同参考通道。处理影响不是质量分，生理窄带活动也可能被改变；原始信号不覆盖。',
        'Adaptive chunking is not enabled. Require at least 32 s and eight comparable channels. Effects are not a quality score; physiological narrowband activity may also change. Preserve originals.'),
}
for _row in _ROWS:
    _zh, _en, _how, _how_en, _api, _meaning, _meaning_en = _EXECUTION[_row['id']]
    _row['name'] = _t(_zh, _en)
    _doc = _row['documentation']
    _doc.update(how_it_works=_t(_how, _how_en), upstream_call=_api,
        interpretation=_t(_meaning, _meaning_en),
        implementation_origin=_t('独立适配器调用已安装的上游包或冻结源码；仅处理内存副本。兼容层和版本记录在运行证据中。',
            'Independent adapter calls installed upstream packages or pinned source on memory copies only. Execution evidence records compatibility layers and versions.'),
        validation_status=_t('已接入执行与报告；合成信号及公开样例用于工程回归，不代表临床准确率或质量阈值已验证。',
            'Execution and reporting integrated. Synthetic signals and public samples provide engineering regression, not clinical accuracy or validated quality thresholds.'),
        version_note=_t('2026-10-31执行适配；Python包固定版本，MATLAB源码固定commit，通过Octave兼容层执行。无MATLAB对照一致性结论。',
            'Execution adapter dated 2026-10-31. Python versions and MATLAB commits are pinned; Octave uses documented compatibility shims. MATLAB equivalence is not established.'))
    if _row['id'] == 'spikeinterface_bad_channels':
        _doc['when_to_use'] = _t('已标定的AP电压；文件声明的shank分组，每组至少8道。std/mad不使用空间坐标。',
            'Calibrated AP voltage with file-declared shank groups and at least eight channels per group. std/mad does not use spatial coordinates.')
    if _row['id'] == 'fieldtrip_zvalue':
        _doc['when_to_use'] = _t('至少10秒连续EEG/ECoG/sEEG电压及原始时钟；本版无滤波、无空间比较。',
            'At least 10 s of continuous EEG/ECoG/sEEG voltage and its source clock. This adapter uses neither filtering nor spatial comparisons.')
    if _row['id'] in {'asr_bursts', 'cleanline', 'zapline_plus'}:
        _doc['when_to_use'] = _t('满足运行规范中的通道、参考、频带与时长条件；已配置固定源码和Octave兼容运行环境。',
            'Meet the channel, reference, bandwidth and duration gates in the runtime specification; configure pinned sources and the Octave compatibility runtime.')
    _row['requirements'] = [_doc['when_to_use']]
    _row['inputs'] = [_doc['when_to_use']]
    _row['limitations'] = [_doc['interpretation'], _doc['when_not_to_use']]
    if _row['id'] in {'asr_bursts', 'cleanline', 'zapline_plus'}:
        _row['outputs'] = [_t('前后PSD、逐道变化量、输入输出指纹；不导出清洗波形。',
                             'Before/after PSD, channel-wise changes and hashes; no cleaned-waveform export.')]
    _short = {
        'faster_channels': ('多项统计特征筛查通道离群。', 'Screen channel outliers across statistical features.'),
        'spikeinterface_bad_channels': ('按shank分别筛查AP通道离群。', 'Screen AP channel outliers separately by shank.'),
        'fieldtrip_zvalue': ('按相邻差分z值标记待复核区间。', 'Mark review intervals using sample-difference z values.'),
        'asr_bursts': ('评估明确校准条件下的ASR重建影响。', 'Evaluate ASR reconstruction with explicit calibration.'),
        'cleanline': ('比较工频处理前后的频谱与变化量。', 'Compare spectra and differences before and after line-noise processing.'),
        'zapline_plus': ('固定片段内自适应处理工频，保留前后对照。', 'Adapt line-noise processing within a fixed chunk and retain comparisons.'),
    }[_row['id']]
    _row['description'] = _t(*_short)
    _doc['purpose'] = _row['description']
    if _row['id'] == 'spikeinterface_bad_channels':
        _row['source']['name'] = 'SpikeInterface std/mad'


def research_methods(modality):
    """Return fresh candidates for a route without granting execution support."""
    from .research_runtime import extension_specs
    return [row for row in extension_specs() if modality in row['research_modalities']]


def research_documentation(identifier):
    for row in _ROWS:
        if row['id'] == identifier:
            return deepcopy(row['documentation'])
    raise KeyError(identifier)


# Keep composed display strings translatable as exact phrases too.
for _row in _ROWS:
    _api = _row['documentation']['upstream_call']
    if _api.startswith(_CALL):
        TRANSLATIONS[_api] = TRANSLATIONS[_CALL] + _api[len(_CALL):]
