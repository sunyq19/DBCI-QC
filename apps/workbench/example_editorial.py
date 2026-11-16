"""Editorial context for the public showcase. Never supplies scientific results."""

CONTEXT = {
    'attention-demo': (
        '从工频候选通道定位到具体波形，查看基础 EEG 检查的完整报告。',
        'Follow line-interference candidates from channels to waveforms in a basic EEG report.'),
    'example-rest-eeg': (
        '灵犀云方案：查看伪差区间、频带特征与通道间的频谱差异。',
        'Gnosis workflow: artifact intervals, band features and spectral differences between channels.'),
    'example-sleep-eeg': (
        '整夜记录：结合 EEG 与辅助导联，查看长时程检查结果。',
        'Overnight recordings: inspect long-duration EEG with auxiliary leads.'),
    'example-ecog': (
        '两位受试者的多次记录：逐份检查信号，再核对同组资料。',
        'Repeated recordings from two participants: inspect signals and compare group metadata.'),
    'example-speech-ecog': (
        '读取 NWB 中的 ECoG 电压流，查看完整性、稳定性与窄带干扰。',
        'Read ECoG voltage from NWB and examine integrity, stability and narrowband interference.'),
    'example-seeg': (
        '按来源电极表选择植入触点，检查触点稳定性与窄带干扰。',
        'Select implanted contacts using the source electrode table, then inspect stability and narrowband interference.'),
    'example-neuropixels': (
        '分别检查 AP 与 LF 电压，按频带和探针位置选择通道检查方法。',
        'Inspect AP and LF voltage separately, using methods suited to the band and probe geometry.'),
    'example-mouse-neuropixels': (
        '已预处理的 LFP：检查数值有效性、恒值和相邻通道的一致性。',
        'Previously processed LFP: inspect numerical validity, constant signals and neighboring-channel agreement.'),
}

BOUNDARIES = {
    'example-neuropixels': (
        'AP 样本为 2 秒、4 秒，LF 为 20 秒；用于展示读取与检查流程，不代表整场实验。',
        'The AP excerpts are 2 and 4 seconds; LF is 20 seconds. They demonstrate the workflow, not a full-session assessment.'),
    'example-mouse-neuropixels': (
        '每只小鼠 60 秒，已滤波、重参考及抽样。部分触点脑区未注明；邻域差异需复核，不直接判为坏道。',
        '60 seconds per mouse, filtered, re-referenced and subsampled. Some contacts lack brain-region labels; neighbor differences need review and do not establish bad channels.'),
}


def context(package_id, english=False):
    index = int(english)
    return {'purpose': CONTEXT.get(package_id, ('', ''))[index],
            'boundary': BOUNDARIES.get(package_id, ('', ''))[index]}
