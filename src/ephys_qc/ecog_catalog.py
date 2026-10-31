"""ECoG-specific descriptions; implemented measurement is not accuracy validation."""
from copy import deepcopy

SCIPY_WELCH = 'https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html'


MODULE_OVERRIDES = {
    'M01': {'description': '核对ECoG来源文件、格式结构、原生时钟及单位；模态来自明确确认。',
            'limitations': ['读取器可读不证明电极位置；只有明确确认的ECoG分析通道可进入此路线。']},
    'M02': {'description': '冻结ECoG分析触点、原生时间窗和来源声明；不推断空间邻接或重新参考。',
            'inputs': ['已确认ECoG的源通道索引', '原生采样率和电压单位', '明确时间范围']},
    'M03': {'description': '描述非有限样本段与至少两个相邻完全相等样本的恒值段。',
            'outputs': ['原始样本区间', '非有限及精确恒值描述'],
            'limitations': ['恒值描述不是已确认伪迹；无头皮幅度或时长坏段阈值，不自动删除样本。']},
    'M04': {'description': '计算Welch PSD与已配置窄带的功率、峰值位置描述。',
            'outputs': ['PSD及单位', '窄带描述量', '不可测原因'],
            'limitations': ['不调用头皮FOOOF/α功率判定、Thomson阈值或肌电阈值；高频和病理活动不判坏。']},
    'M05': {'name': '接触点描述', 'description': '逐触点描述有限样本数、均值、标准差、RMS与峰峰值。',
            'inputs': ['原始ECoG电压', '稳定源通道身份'], 'outputs': ['逐触点描述统计'],
            'limitations': ['不调用PREP、LOF、桥接或跨触点阈值；不从触点名推测空间关系或坏触点。']},
    'M06': {'description': 'ECoG生理伪迹方法尚未接入，选中也明确保留未评。',
            'dependencies': ['M02'], 'inputs': [], 'outputs': ['未接入原因'],
            'limitations': ['头皮ECG/EOG/肌电阈值不迁移至ECoG。'], 'selectable': False, 'implementation': 'planned'},
}


def module_overrides(module_id):
    return deepcopy(MODULE_OVERRIDES.get(module_id, {}))


def _documentation(purpose, implementation, outputs, limitations, *, scipy=False):
    refs = [{'title': '本项目ECoG独立实现', 'url': implementation, 'kind': '本项目封装'}]
    if scipy:
        refs.append({'title': 'SciPy Welch 官方文档', 'url': SCIPY_WELCH, 'kind': '官方文档'})
    return {'purpose': purpose, 'how_it_works': outputs, 'interpretation': limitations,
            'when_to_use': '明确确认为ECoG且电压和原生采样时间已核验。',
            'when_not_to_use': '未确认模态、单位、采样时钟，或试图使用头皮判坏阈值。',
            'validation_status': '仅声明实现与工程执行范围；不宣称坏触点或伪迹准确性已验证。',
            'upstream_call': 'scipy.signal.welch' if scipy else '本项目描述性实现；不调用头皮检测流水线。',
            'implementation_origin': implementation, 'version_note': 'ecog-basic/1', 'references': refs}


def custom_methods():
    rows = []
    for id_, name, mid, category, description, outputs, limitation, scipy in [
        ('ecog_continuity', '非有限与精确恒值段', 'M03', 'basic', '定位非有限值及连续完全相等样本。', '原时钟样本区间与数量。', '至少2个相邻完全相等样本只是描述，不等于已确认伪迹。', False),
        ('ecog_welch_psd', 'ECoG Welch功率谱', 'M04', 'basic', '保留原始ECoG频率能量的描述。', 'Hann窗、50%重叠、常量去均值的Welch密度估计，单位V²/Hz。', '不进行α谱模型或高频判坏；去均值只用于PSD估计，不覆盖原始信号。', True),
        ('ecog_line_description', 'ECoG窄带功率描述', 'M04', 'conditional', '描述配置频率附近的可测功率及峰值。', '在同一PSD的±max(1Hz,频率分辨率)频带测量；不进行阈值分类。', '窄带峰值不证明干扰来源，不排除生理或病理活动；未自动扩展谐波。', True),
        ('ecog_channel_description', 'ECoG触点描述统计', 'M05', 'basic', '提供原始触点的有限样本统计。', '各触点独立均值、标准差、RMS、峰峰值与非有限计数。', '没有比较组阈值，不凭幅度、相关性、触点名称或病理标签判坏。', False),
    ]:
        path = f'src/ephys_qc/modules/ecog/{mid.lower()}.py'
        rows.append({'id': id_, 'name': name, 'module_id': mid, 'category': category,
                     'description': description, 'inputs': ['已确认ECoG电压', '原生时钟和源索引'],
                     'requirements': ['已确认ECoG电压', '原生时钟和源索引'], 'outputs': [outputs],
                     'source': {'name': 'SciPy及本项目' if scipy else '本项目', 'url': SCIPY_WELCH if scipy else '',
                                'license': 'SciPy: BSD-3-Clause；本项目许可见仓库'},
                     'implementation': 'available', 'limitations': [limitation], 'optional_extension': False,
                     'documentation': _documentation(description, path, outputs, limitation, scipy=scipy)})
    return rows
