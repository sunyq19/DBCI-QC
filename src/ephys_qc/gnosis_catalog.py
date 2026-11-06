"""Optional Gnosis adapters. Importable without scientific or vendor packages."""
from copy import deepcopy

URL = 'https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE'
COMMIT = '3547548bb81e1e1e2bc90226add5574437921c0c'
SOURCE = {'name': '灵犀云 · GnosisNeuroDynamicSE', 'url': URL,
          'license': 'Notebook/文档 MIT；二进制 wheel 按提供方授权，平台不再分发。', 'commit': COMMIT}

# Each selected leaf executes only its own output and the declared prerequisites.
ROWS = [
 ('gnosis_line_length', '灵犀云 · 线长坏道候选', 'M05', 'get_bad_channels',
  '平均参考后比较通道线长总量；保留通道候选。',
  '256采样点平滑线长；按IQR与标准差双侧阈值的交集筛查，系数默认4.5。',
  ['候选通道', '逐道平滑线长总量'], {'threshold': 4.5}, False),
 ('gnosis_artifact', '灵犀云 · 伪差区间与占比', 'M06', 'get_Artifact',
  '定位振幅和高频线长异常区间，计算逐道及全局时间占比。',
  '原版内部使用150 μV振幅阈值、0.1秒线长窗、8倍中位数阈值及1秒间隔合并；会在副本上降采样/滤波。',
  ['逐道候选区间和占比', '全局候选区间'], {}, False),
 ('gnosis_low_band', '灵犀云 · 低频异常区间', 'M06', 'get_abnormal_inertvals',
  '在1–13 Hz中寻找通道和窗口间的异常功率变化。',
  '原版Hilbert功率统计；1秒窗、50%重叠；IQR系数3.5，另有固定3倍标准差条件。',
  ['逐道低频候选区间', '异常时间占比'], {'threshold': 3.5}, False),
 ('gnosis_high_band', '灵犀云 · 高频异常区间', 'M06', 'get_abnormal_inertvals',
  '在13–40 Hz中寻找异常功率变化，不直接判为肌电。',
  '原版Hilbert功率统计；1秒窗、50%重叠；IQR系数6，另有固定3倍标准差条件。',
  ['逐道高频候选区间', '异常时间占比'], {'threshold': 6.0}, False),
 ('gnosis_band_power', '灵犀云 · 相对频带功率', 'M04', 'cal_psd_freq → bands_repower',
  '输出δ、θ、α、β、γ五个频带的相对功率。',
  '原版2秒Hamming Welch窗、1秒重叠；各频带积分除以1–40 Hz总功率。',
  ['通道×五频带功率比例', 'PSD及有效统计时长'], {}, True),
 ('gnosis_band_amplitude', '灵犀云 · 频带平均幅值', 'M04', 'bands_amp',
  '输出五个频带滤波后的平均绝对幅值，单位μV。',
  '原版分别带通后计算平均绝对幅值；不是峰峰值或通用质量分。',
  ['通道×五频带幅值', '有效统计时长'], {}, True),
 ('gnosis_psd_deviation', '灵犀云 · PSD通道差异', 'M05', 'cal_psd_freq → detect_bad_channels_psd',
  '比较每个通道与其他通道的对数频谱距离，提出异常通道。',
  '五频带及1–40 Hz全频段的log10 PSD平均绝对距离；全频段使用Q1−3IQR、Q3+3IQR双侧界限。',
  ['逐道六频段距离', 'PSD异常通道候选'], {'threshold': 3.0}, True),
 ('gnosis_reference_ranges', '灵犀云 · 参考分布对照', 'M04', 'bands_repower / bands_amp / detect_bad_channels_psd → Standard',
  '把频带功率、幅值及频谱差异与包内参考上下界并列展示。',
  '读取原版Standard阈值表，逐道逐频带标记低于/范围内/高于；保留数值与阈值来源，不转成0–100总分。',
  ['三类特征的参考范围对照', '参考表SHA-256'], {}, True),
]
IDS = frozenset(row[0] for row in ROWS)


def extension_specs():
    result = []
    for key, name, module, api, purpose, how, outputs, options, spectral in ROWS:
        conditions = ['头皮EEG、单位V、至少3个可比较通道', '单一已确认参考比较组',
                      '采样率>140 Hz，源频带覆盖1–70 Hz；12–120秒分析窗口']
        if spectral:
            conditions.append('默认先检出伪差并取补集，只用持续时间>10秒的片段；可显式关闭该筛选')
        defaults = {'prepare_copy': True, **options}
        if spectral:
            defaults['exclude_artifacts'] = True
        limitations = ['自定义阈值，不是统一质控标准；不参与当前三项基础评分。',
                      '原始信号和其他方法的输入保持不变；不自动删除候选通道。',
                      '原示例针对静息态头皮EEG；任务/睡眠/疾病信号只能作探索性解释，不据此自动剔除。']
        if spectral:
            limitations.append('筛选后的片段按原示例拼接计算；接缝会影响滤波/PSD，结果没有连续时间定位。')
        if key == 'gnosis_line_length':
            limitations.append('双阈值交集可能对少通道不敏感；空候选不证明信号良好。')
        if key == 'gnosis_artifact':
            limitations.append('原版win_len/min_duration外层入参未完全决定内部常量；本适配不提供无效旋钮。')
        result.append(dict(id=key, name=name, module_id=module, category='optional',
            description=purpose, inputs=conditions.copy(), requirements=conditions, outputs=outputs,
            source=deepcopy(SOURCE), implementation='available', status='available',
            optional_extension=True, defaults=defaults, limitations=limitations,
            documentation=dict(purpose=purpose, how_it_works=how,
                interpretation='输出测量值和待复核候选，不是已确认坏道、疾病结论或统一合格线。',
                when_to_use='；'.join(conditions), when_not_to_use='颅内/动物/Neuropixels、双极混合参考、单位或输入频带不满足时不运行。',
                upstream_call='SignalQualityEval 3.0.0: '+api,
                implementation_origin='独立Python 3.12进程调用原版wheel；prepare_copy默认执行≤256Hz、1–70Hz、CAR，无ICA。关闭时需声明输入已按此准备。',
                validation_status='原版接口适配；实际验证样例和局限见仓库验证记录。',
                version_note='固定上游提交 '+COMMIT+'；不复制或重写编译算法。',
                references=[{'title':'灵犀云 GitHub','url':URL,'kind':'上游代码'},
                            {'title':'原版计算方法','url':URL+'/blob/'+COMMIT+'/算法计算方法.md','kind':'官方文档'},
                            {'title':'适配与验证说明','url':'https://github.com/sunyq19/DBCI-QC/blob/main/docs/gnosis-methods.md','kind':'官方文档'}])))
    return result
