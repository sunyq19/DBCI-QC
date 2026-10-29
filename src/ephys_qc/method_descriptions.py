"""Source-checked, display-only documentation for the method catalogue.

Reviewed against the installed BrainElecQC wheel and the project adapters on
2026-10-29. These descriptions neither enable methods nor change their gates.
Scientific packages are deliberately not imported by this module.
"""
from copy import deepcopy


_BRAIN_SOURCE = (
    "https://github.com/Jlei61/BrainElecQC/blob/"
    "f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/"
)
_BRAIN_VERSION = (
    "2026-10-29核对本地BrainElecQC 0.1.0安装源码及固定提交"
    "f007d829712d1b824cda79409d181a3313d6a78f；同名方法不代表调用同名第三方包。"
)
_MNE_VERSION = (
    "2026-10-29核对本地MNE 1.13.2与平台适配器；网页stable文档可能更新，"
    "实际参数与版本以本次运行记录为准。"
)
_PROJECT_VERSION = (
    "本项目2026-10-29实现快照；下列仓内路径是封装代码位置，不是外部标准或公开算法认证。"
)
_EXPLORATORY = (
    "已接入候选筛查；工程运行与有限样例检查不等于独立质量真值验证，"
    "尚未建立跨数据集准确率或临床验证。"
)
_STRUCTURAL = (
    "已接入结构或时间映射核验；验证对象是文件与程序契约，"
    "不能据此认定信号合格或临床有效。"
)
_PLANNED = "尚未接入，本平台未执行或验证该方法；不能引用上游论文准确率作为本平台结果。"


def _ref(title, url, kind="官方文档"):
    return {"title": title, "url": url, "kind": kind}


def _brain(path, title):
    return _ref(title, _BRAIN_SOURCE + path, "上游代码")


def _local(path, title):
    return _ref(title, path, "本项目封装")


def _mne(name):
    return _ref("MNE：" + name,
                "https://mne.tools/stable/generated/mne.preprocessing." + name + ".html")


def _doc(purpose, how_it_works, interpretation, when_to_use, when_not_to_use,
         upstream_call, references, implementation_origin,
         validation_status=_EXPLORATORY, version_note=_BRAIN_VERSION):
    return {
        "purpose": purpose,
        "how_it_works": how_it_works,
        "interpretation": interpretation,
        "when_to_use": when_to_use,
        "when_not_to_use": when_not_to_use,
        "validation_status": validation_status,
        "upstream_call": upstream_call,
        "references": references,
        "implementation_origin": implementation_origin,
        "version_note": version_note,
    }


_PREP_PAPER = _ref(
    "Bigdely-Shamlo等，The PREP pipeline（2015）",
    "https://pmc.ncbi.nlm.nih.gov/articles/PMC4471356/", "算法论文")
_WELCH_DOC = _ref(
    "SciPy：scipy.signal.welch",
    "https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html")
_EDF_SPEC = _ref("EDF原始格式规范", "https://www.edfplus.info/specs/edf.html")
_AUTOREJECT_PAPER = _ref(
    "Jas等，Autoreject: Automated artifact rejection for MEG and EEG data（2017）",
    "https://arxiv.org/abs/1612.08194", "算法论文")


_DOCUMENTATION = {
    "edf_reader": _doc(
        "确认读到哪个文件、哪些原始通道，以及样本和记录时钟是否可解释。",
        "读取器注册表按实际格式分派EDF/BDF、BrainVision、EEGLAB和FIF适配器；统一返回源通道、原生时钟、电压单位、标注摘要和每个配套文件的指纹。",
        "结构可读只说明文件可解析。哈希能核对文件一致性，不能证明文件内容真实、设备正常或信号质量良好。",
        "已被相应读取器核验的连续记录；先确认模态、角色和源索引，再选择同一原生时钟的分析与辅助信号。",
        "不支持断续EDF、EEGLAB分段数据和分卷FIF；多文件记录必须完整提交。文件可读不证明模态，非头皮EEG不套用现有质控；不自动重采样。",
        "ephys_qc.readers.inspect_recording / open_reader；EDF/BDF后端为BrainElecQC，其他首批格式使用MNE",
        [_ref("MNE supported data formats", "https://mne.tools/stable/auto_tutorials/io/20_reading_eeg_data.html"), _brain("readers/edf.py", "BrainElecQC EDF读取器"),
         _brain("eeg/header_qc.py", "BrainElecQC技术头检查"), _EDF_SPEC,
         _local("src/ephys_qc/runtime.py", "本平台M01与原始通道映射")],
        "统一读取契约封装独立适配器；新增格式只注册读取模块，不修改下游算法。",
        validation_status=_STRUCTURAL),

    "voltage_calibration": _doc(
        "确认ADC数字值能否依据文件声明换算成具有明确单位的电压。",
        "读取逐道digital/physical最小值、最大值和单位，按线性比例及偏移换算；平台只把核验后的V量纲数据交给电压阈值方法。",
        "标定参数有效不等于仪器经过计量校准。错误的文件头、接线或传感器增益仍可能产生看似合理的电压。",
        "单位与标定范围明确、选中EEG及辅助通道可换算为V时；端点平台检查还需保留源标定端点。",
        "单位未知、比例退化或所选通道不是电压时不能直接套用微伏阈值；不能凭通道名称猜单位。",
        "brainelecqc.readers.edf.EdfBdfReader；ephys_qc.runtime._read_window",
        [_EDF_SPEC, _brain("readers/edf.py", "BrainElecQC逐道标定与读取"),
         _local("src/ephys_qc/runtime.py", "本平台电压单位与同钟读取门控")],
        "BrainElecQC按文件头实现数字值到物理值换算；本平台核验下游所需单位。",
        validation_status=_STRUCTURAL),

    "qc_plan": _doc(
        "在运行前明确要检查的选区、方法、依赖，以及哪些条件已知或尚未知。",
        "根据技术头、明确登记的背景与用户参数生成稳定计划标识，补齐必要依赖，逐项记录ready、partial、blocked等适用性和原因。",
        "计划可运行不等于检测通过。年龄、疾病、睡眠或任务背景帮助解释信号，不直接变成质量扣分阈值；缺失元数据保留未知。",
        "每次运行前；更换选道、时间范围、参考构型或方法参数后重新生成计划。",
        "不能代替读取文件或实际检测；不能把未核实的坐标、滤波史、参考方式当作已知，也不能以疾病标签推断伪迹。",
        "ephys_qc.planning.build_plan；ephys_qc.tagging.data_facts；ephys_qc.method_registry.evaluate_methods",
        [_local("src/ephys_qc/planning.py", "本平台计划与依赖"),
         _local("src/ephys_qc/tagging.py", "本平台技术事实与背景标签"),
         _local("src/ephys_qc/method_registry.py", "本平台方法适用性")],
        "本项目规则编排；不是外部EEG质量评分算法。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "continuity": _doc(
        "找到非有限样本、精确恒值段及ADC端点平台等可定位的数据连续性问题。",
        "在未滤波样本上扫描连续相等值，结合逐道标定端点区分端点平台、近零平线和其他恒值段，保存原始通道及半开时间区间。",
        "候选是可复核的局部数据现象，不自动指认设备故障。幅度小但仍变化的信号不会仅因低幅度被认作恒值。",
        "已知采样率的连续数据；端点平台解释需源标定信息。当前最短恒值段默认0.1秒是筛查配置。",
        "不把该默认时长视为统一EEG规范；本项不能覆盖所有断线、任意重复数据块或缓慢漂移。",
        "brainelecqc.eeg.continuity.compute_continuity_qc",
        [_brain("eeg/continuity.py", "BrainElecQC原始样本连续性实现"),
         _local("src/ephys_qc/runtime.py", "本平台M03定位与后续保护区")],
        "直接调用BrainElecQC基于NumPy的自有连续性实现；没有调用EEGLAB清洗流程。"),

    "welch_psd": _doc(
        "观察各通道的频率能量分布，为工频、谱形和状态解释提供基础描述。",
        "BrainElecQC直接调用SciPy Welch：分段、加Hann窗并平均周期图；当前默认4秒窗、50%重叠、去常数趋势，输出V²/Hz。",
        "PSD是估计量，分辨率取决于实际窗长。某频段功率升高可能来自脑活动、参考、设备或伪迹，不能单独作为质量结论。",
        "电压单位、采样率和实际可测频带明确时；比较记录应对齐估计参数与采集条件。",
        "不能分析Nyquist频率以上的成分；已被采集或软件滤除的频率不能由功率谱恢复，也不宜混比不同参考或滤波条件。",
        "brainelecqc.eeg.spectral._welch → scipy.signal.welch",
        [_WELCH_DOC, _brain("eeg/spectral.py", "BrainElecQC Welch参数与输出")],
        "直接调用SciPy算法；BrainElecQC负责参数、定位与结果组织。",
        version_note=_BRAIN_VERSION + " 本地SciPy 1.17.1；在线文档版本可能更高。"),

    "thomson_line": _doc(
        "在可测范围内寻找50/60Hz及其谐波附近稳定窄带成分的统计证据。",
        "BrainElecQC用SciPy DPSS窗自行计算Thomson多窗F统计量，扫描目标频率邻域，并对通道、完整时间窗和被测频率组成的检验族做Bonferroni校正。",
        "显著结果支持存在近似正弦窄带成分，不直接证明电源污染或设备故障。只记录证据，不执行去工频。",
        "窗口足够、目标频率低于Nyquist且记录频带确实保留该频率时；当前4秒窗、1秒步长和族显著性0.01是可记录的算法配置。",
        "低采样率或已滤除目标频率时只能报告未评或受限；不能把未检出解释为没有工频，也不能把统计显著性当质量总分。",
        "brainelecqc.eeg.spectral._line_analysis / _thomson_spectrum；scipy.signal.windows.dpss",
        [_brain("eeg/spectral.py", "BrainElecQC Thomson F检验与多重比较"),
         _ref("Chronux ftestc：正弦成分F检验说明",
              "https://chronux.org/chronuxFiles/Documentation/chronux/spectral_analysis/continuous/ftestc.html"), _PREP_PAPER],
        "BrainElecQC依据多窗F检验与PREP参数做的再实现；主流程没有调用Chronux或MNE去工频函数。"),

    "spectral_model": _doc(
        "把谱背景、突出谱峰和实际α频带能量分开描述，减少将谱形差异直接当作坏数据的误读。",
        "在Welch PSD上直接调用FOOOF 1.1.1拟合非周期背景和高于背景的峰，默认固定背景模式、2–40Hz；另以PSD积分计算含背景的α功率及相对α功率。",
        "FOOOF峰高与α频带积分不是同一量。拟合优度、背景指数和α峰缺失均不是质量分；状态、年龄、疾病和参考方式会影响结果。",
        "拟合频带可测、功率为正、分辨率与时长足够时；当前每次拟合要求至少10秒和4个Welch周期图，短尾窗单独保留未评。",
        "不能把无α峰认作坏记录，也不能用拟合模型替代临床判断；频带被滤除或短窗不满足条件时不应强行拟合。",
        "brainelecqc.eeg.spectral.compute_spectral_qc → fooof.FOOOF.fit；brainelecqc.eeg.alpha_power.compute_alpha_power",
        [_ref("FOOOF 1.1.1官方文档", "https://fooof-tools.github.io/fooof/"),
         _brain("eeg/spectral.py", "BrainElecQC FOOOF与拟合门控"),
         _brain("eeg/alpha_power.py", "BrainElecQC α频带积分")],
        "直接调用FOOOF；BrainElecQC实现拟合门控、窗口汇总和独立的α功率积分。",
        version_note=_BRAIN_VERSION + " 当前实现显式要求fooof==1.1.1；不能直接以新版specparam替换。"),

    "prep_nonspatial": _doc(
        "在可比较的通道组内，筛查幅度异常、高频噪声、相关性偏低及掉线等坏道线索。",
        "BrainElecQC在分析副本上处理滤波，独立计算稳健幅度、高低频差异、分窗相关和掉线统计，再按声明的比较组应用门控与阈值。",
        "这是PREP非空间思想的再实现，不是完整PREP。没有RANSAC、插值或稳健平均重参考；组内异常也可能是局部生理或病理信号。",
        "参考方式可比较且显式声明分组时；当前每组至少4个可用通道是实现门槛，必须连同有效窗数和零离散度情况解释。",
        "未知比较组、少通道或混合参考时只保留可计算描述量，不强行出组阈值结论；不能凭电极名称构造空间坐标或把双极导联视作共同参考。",
        "brainelecqc.eeg.bad_channels.compute_bad_channels；主流程不调用pyprep.NoisyChannels",
        [_PREP_PAPER, _brain("eeg/bad_channels.py", "BrainElecQC非空间指标及独立PyPREP对照函数")],
        "直接调用BrainElecQC再实现；PyPREP仅在独立compare_with_pyprep对照函数中使用，不属于当前主检测调用。",
        validation_status="已接入，但既有两份ds002034全长结果与来源坏道标签不一致；该负结果保留，不能宣称准确率或临床验证。"),

    "ecg_locked": _doc(
        "借助真实ECG导联，检查EEG中是否存在与心电事件重复锁时的成分。",
        "直接用MNE find_ecg_events从所配置ECG检测事件；BrainElecQC随后对EEG锁时分段，汇总均值、中位数、标准误和分半一致性，边界不完整事件不参与平均。",
        "事件和重复锁时成分是支持证据，不能单独确认污染或诊断心脏问题；共同参考、真实生理耦合或错误辅助导联也会影响结果。",
        "辅助导联身份已确认且与EEG同采样时钟、时长足够时；当前ECG检测默认5–35Hz，结果应连同可用事件数复核。",
        "没有ECG、导联恒值或事件不足时保留未评；不能把未检出当干净，也不从EEG通道名猜出独立ECG证据。",
        "brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_ecg_events；锁时统计由BrainElecQC实现",
        [_mne("find_ecg_events"), _brain("eeg/events.py", "BrainElecQC ECG事件和EEG锁时汇总")],
        "直接复用MNE事件检测；BrainElecQC自建EEG锁时统计，没有自动投影或删除成分。",
        version_note=_BRAIN_VERSION + " 本地事件检测依赖MNE 1.13.2。"),

    "eog_locked": _doc(
        "借助真实EOG导联，检查眼动或眨眼事件附近EEG中的重复锁时成分。",
        "直接用MNE find_eog_events检测辅助EOG事件；BrainElecQC以这些时刻截取EEG并汇总平均形态、离散程度和分半一致性。",
        "EOG事件不等于所有EEG通道被污染；锁时平均可提示相关成分，但需要结合空间分布、参考和波形复核。",
        "有身份明确、时钟一致且信号可用的EOG时；当前检测默认1–10Hz，只在分析副本上进行。",
        "没有EOG或事件不可用时不能给出通过结论；睡眠慢眼动与任务相关眼动需要背景解释，不能把状态标签直接变为扣分。",
        "brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_eog_events；锁时统计由BrainElecQC实现",
        [_mne("find_eog_events"), _brain("eeg/events.py", "BrainElecQC EOG事件和EEG锁时汇总")],
        "直接复用MNE事件检测；BrainElecQC自建锁时证据，不运行自动眼电去除。",
        version_note=_BRAIN_VERSION + " 本地事件检测依赖MNE 1.13.2。"),

    "hf_burst": _doc(
        "定位高频突发，并把一般高频线索与具有独立EMG支持的候选分开。",
        "BrainElecQC复用MNE滤波和Hilbert包络原语，自建包络、相对功率、频谱分散度等多重门控；M03连续性问题形成保护区，有真实EMG时再检查同步支持。",
        "无EMG支持的结果只称高频突发；有EMG支持也仍需复核。高频脑活动、工频谐波和尖锐瞬变均可能影响统计。",
        "当前默认30–min(100,0.45×采样率)Hz有效带宽至少20Hz、选区至少10秒；应同时查看实际频带、连续性保护与参考导联。",
        "频带不足或已被采集滤除时不评；不能把该方法等同于MNE固定110–140Hz肌电方法，不能将癫痫尖波或高频病理活动自动认作伪迹。",
        "brainelecqc.eeg.muscle.compute_muscle_qc；MNE Raw.filter / Raw.apply_hilbert等原语",
        [_brain("eeg/muscle.py", "BrainElecQC高频多门控实现"),
         _mne("annotate_muscle_zscore"),
         _local("src/ephys_qc/method_registry.py", "本平台高频频带及时长门控")],
        "BrainElecQC自有组合筛查，使用MNE底层信号处理；没有直接调用annotate_muscle_zscore。"),

    "sleep_timeline": _doc(
        "把来源睡眠分期与选区对齐，明确各阶段覆盖及未知时间。",
        "核验登记标注及来源哈希，按原始onset/duration裁剪交叠区间，并映射到原始样本时钟；保存来源标签、覆盖量和缺口。",
        "睡眠阶段用于解释EEG状态，不是质量真值。未知覆盖不代表清醒或数据合格；R&K与AASM标签体系不能无依据合并。",
        "已有来源明确且记录对应关系已核对的sleep_stages_tsv时；HMC或Sleep-EDF配套标注可验证时间映射。",
        "没有分期文件时不推测阶段；程序映射一致不证明原始人工分期准确，也不独立证明设备时钟同步。",
        "ephys_qc.annotations.check_annotations（sleep_stages_tsv）",
        [_local("src/ephys_qc/annotations.py", "本平台睡眠分期映射与覆盖计算"),
         _ref("PhysioNet Sleep-EDF Expanded 1.0.0：记录与分期说明", "https://physionet.org/content/sleep-edfx/1.0.0/")],
        "本项目注释核验与时间映射；不运行睡眠分期预测模型。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "task_timeline": _doc(
        "核对所选时间内的任务事件及其原始样本位置，保留事件来源。",
        "读取已登记的事件转换表，检查数值、时长与来源哈希，计算事件与选区交叠；原始时间和裁剪后时间分别保存。",
        "任务事件描述实验安排，不证明受试者完成动作、行为正确或没有伪迹；事件标签不作为M03–M06检测输入。",
        "记录关联和转换规则明确的event_name事件表，包括当前ds002034及EEGMMIDB适配。",
        "当前bids_events_tsv名称不代表通用BIDS验证器；未经适配的任意BIDS事件列不能假定支持，任务背景标签不能替代事件文件。",
        "ephys_qc.annotations.check_annotations（当前注册的bids_events_tsv适配）",
        [_local("src/ephys_qc/annotations.py", "本平台事件表契约与时间映射"),
         _ref("BIDS EEG规范：记录元数据与事件关联",
              "https://bids-specification.readthedocs.io/en/stable/modality-specific-files/electroencephalography.html")],
        "本项目对指定事件格式的适配；没有实现完整BIDS合规检查。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "clinical_timeline": _doc(
        "把来源标注的发作等临床事件映射到选区，帮助解释病理信号与算法候选的关系。",
        "读取clinical_events_tsv的onset_s、duration_s、label和label_type，核对来源哈希并报告交叠事件、样本位置与区间并集时长。",
        "发作等临床事件不是伪迹真值；无标注不自动等于正常。事件不进入信号检测或质量评分，也不据此调整疾病阈值。",
        "有官方或经授权来源、清楚的事件定义、同一记录时间轴时；例如CHB-MIT官方summary的发作区间。",
        "不能把事件表当完整临床诊断或连续正常/异常标注，也不能用病理事件监督坏段检测而仍声称独立QC。",
        "ephys_qc.annotations.check_annotations（clinical_events_tsv）",
        [_local("src/ephys_qc/annotations.py", "本平台临床事件映射与标签隔离"),
         _ref("PhysioNet CHB-MIT 1.0.0：发作标注说明", "https://physionet.org/content/chbmit/1.0.0/")],
        "本项目临床事件注释层；不运行疾病检测算法。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "aggregate": _doc(
        "把本次实际选定的方法结果、未评原因和失败状态放在同一份可追溯记录中。",
        "汇总实际模块和子方法状态，保留候选、缺失条件、跳过项及运行错误；总分value保持null，注明尚未校准。",
        "完成率不是信号质量。没有候选可能来自未评、缺少辅助导联或方法灵敏度有限；汇总只覆盖本次选择的检查。",
        "运行结束或部分失败后；先看适用性和实际执行状态，再解释结果。",
        "不能生成未经校准的跨疾病、跨设备或跨数据集总分；未选择方法不能算通过。",
        "ephys_qc.runtime.execute（M08汇总与score.value=null）",
        [_local("src/ephys_qc/runtime.py", "本平台实际状态汇总和未校准总分")],
        "本项目证据汇总；不是经过验证的综合质量量表。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "report": _doc(
        "让候选可以被人复核，并能追溯到原文件、选区、参数和软件版本。",
        "将结果写为JSON及HTML，保留来源哈希、计划、原始索引与时间映射、适用性和未评原因；生成有限范围波形预览。",
        "报告记录自动筛查证据，人工复核仍为待处理。预览不是全记录审阅，也不是临床诊断报告。",
        "交付研究记录或复核候选时；必须同时检查报告所载时间范围、所选通道和原始波形。",
        "不能仅凭缩略波形排除全段问题，不能把生成报告视作已经完成临床判读或人工签署。",
        "ephys_qc.runtime._report / _waveform；ephys_qc.runtime.execute（M09）",
        [_local("src/ephys_qc/runtime.py", "本平台报告、预览及证据输出")],
        "本项目可追溯报告封装；不自动删除、插值或重写原始数据。",
        validation_status=_STRUCTURAL, version_note=_PROJECT_VERSION),

    "mne_amplitude": _doc(
        "用成熟库补充相邻样本突变和平线筛查，并保留时间段与通道两种输出。",
        "直接调用MNE annotate_amplitude，按相邻样本差值判定peak/flat并结合最小时长与坏样本比例；平台默认peak=None、flat=0、min_duration=0.1秒、bad_percent=5。",
        "它不是固定时间窗峰峰值法。MNE可能只返回坏通道候选而没有区间；时间注释可跨通道合并，不能伪造成逐道精确定位。",
        "已核验电压单位和采样率，理解量化精度、采集与处理历史时；默认设置主要补查精确平线。",
        "不能用本项覆盖缓慢漂移或所有高幅度伪迹；没有时间注释不等于没有通道候选，也不能把默认值当临床标准。",
        "mne.preprocessing.annotate_amplitude；ephys_qc.extensions.run_extension('mne_amplitude', ...)",
        [_mne("annotate_amplitude"), _local("src/ephys_qc/extensions.py", "本平台MNE幅度和平线适配")],
        "直接调用MNE；本平台设定实验默认、保留两类输出并映射原始索引，不写入raw.info['bads']。",
        version_note=_MNE_VERSION),

    "mne_muscle": _doc(
        "在满足高频采样条件时，补充独立于基础HF方法的全选区肌电样高频线索。",
        "直接调用MNE annotate_muscle_zscore，显式指定EEG及固定110–140Hz；Hilbert包络标准化后跨通道汇总和平滑，当前阈值4、min_length_good=0.1秒。",
        "输出是所选通道集合的时间候选，不是每个通道的肌电结论。没有同步EMG确认，120Hz工频谐波等也可能混入，始终按探索性结果解释。",
        "采样率严格大于280Hz、选区至少10秒且该频带可测时；滤波史未知保留partial，已知频带不支持则阻止。",
        "不能把110–140Hz自动下移到低采样率记录；常数或非有限分数不能报通过，无候选也不证明无肌电。",
        "mne.preprocessing.annotate_muscle_zscore；ephys_qc.extensions.run_extension('mne_muscle', ...)",
        [_mne("annotate_muscle_zscore"), _local("src/ephys_qc/extensions.py", "本平台固定频带肌电方法与失效门控")],
        "直接调用MNE公开函数；平台添加固定频带、时长、滤波史和输出有效性门控，不做清洗。",
        version_note=_MNE_VERSION),

    "mne_bridge": _doc(
        "检查通道对是否异常相似，为可能的电极桥接提供线索。",
        "直接调用MNE compute_bridged_electrodes，对分段后的通道差值方差估计电距离分布并寻找桥接候选；默认0.5–30Hz、2秒段、epoch_threshold=0.5。",
        "lm_cutoff默认16µV²是寻找分布局部极小值的范围上限，不是最终桥接阈值。候选定位到整个分析选区内的通道对，逐段距离不能冒充桥接起止时间。",
        "当前适配要求已核实共同参考或联耳参考、单一完整比较组、至少8道、10秒及5个完整段；硬件和电极信息用于后续解释。",
        "不直接用于双极、混合或未知参考；不凭名字猜坐标。完全重复信号可能令分布拟合退化，失败必须保留，不能报无桥接。",
        "mne.preprocessing.compute_bridged_electrodes；ephys_qc.extra_methods.run_extension",
        [_mne("compute_bridged_electrodes"), _local("src/ephys_qc/extra_methods.py", "本平台桥接输入门控与通道对定位")],
        "直接调用MNE；本平台增加适用性约束、原始通道映射和失败说明，不插值通道。",
        version_note=_MNE_VERSION),

    "mne_lof": _doc(
        "根据通道间局部密度差异，补充整段波形异常通道候选。",
        "直接调用MNE find_bad_channels_lof，以通道波形为特征、邻近通道为参照计算Local Outlier Factor；默认20个邻居、Euclidean距离和1.5阈值。",
        "候选是整段通道离群，不是具体坏段。局部脑活动、病理波形、幅度和参考差异都可能造成离群；分数不是异常概率。",
        "当前要求已核实共同或联耳参考、单一完整比较组、至少8道和10秒，通道数还须严格多于配置的邻居数；参数应随评估记录。",
        "不用于当前双极、混合或未知参考输入；不静默缩小邻居数。算法前没有额外幅度归一化或重参考，跨采集条件不可直接比较阈值表现。",
        "mne.preprocessing.find_bad_channels_lof；ephys_qc.extra_methods.run_extension",
        [_mne("find_bad_channels_lof"), _local("src/ephys_qc/extra_methods.py", "本平台LOF门控与候选封装")],
        "直接调用MNE及其scikit-learn依赖；本平台保留原始分数、通道身份与复核状态。",
        version_note=_MNE_VERSION),

    "autoreject_global": _doc(
        "探索数据驱动的全局EEG峰峰值阈值，补充固定阈值之外的分段描述。",
        "将分析副本分成不重叠的默认2秒段，直接调用get_rejection_threshold，以默认5折CV和固定随机种子估计一个EEG全局阈值；再报告同一拟合选区中超阈值的段。",
        "这是同一选区上的描述性超阈值结果。连续相邻段有关联，内部CV优化不等于独立受试者验证；分段不是任务试次，也不是已执行剔除。",
        "当前至少max(20,4×CV折数)个完整段且段长对应整数样本；可用于少通道或双极数据的探索，未使用的尾段必须显示。",
        "不能把此全局阈值当local AutoReject；不调用drop_bad或transform，也不能借用论文准确率证明本平台候选正确。",
        "autoreject.get_rejection_threshold(epochs, decim=1, random_state=0, ch_types=['eeg'], cv=5)（默认配置）",
        [_ref("autoreject：get_rejection_threshold",
              "https://autoreject.github.io/stable/generated/autoreject.get_rejection_threshold.html"),
         _AUTOREJECT_PAPER, _local("src/ephys_qc/extra_methods.py", "本平台固定分段、拟合与同选区描述")],
        "直接调用autoreject全局阈值估计；本平台建立临时连续分段并映射候选，不清洗数据。",
        version_note="2026-10-29核对本地autoreject 0.5.1与MNE 1.13.2；参数与实际完整分段数写入运行结果。"),

    "pyprep_ransac": _doc(
        "计划增加空间预测一致性检查，补充现有PREP非空间指标。",
        "PyPREP从其他电极的随机子集按空间信息预测各通道，再比较预测信号与实测信号相关性；未来适配需冻结坐标、参考、随机种子和有效通道规则。",
        "空间不可预测性是候选线索，不直接证明伪迹；它不能被现有非空间相关指标替代，也不等同于完整PREP清洗。",
        "未来仅在坐标已经核实、通道足够且参考可比较、空间覆盖适合时评估。",
        "当前尚不可运行；不能靠通道名补坐标，不宜直接套到少通道PSG、临床双极导联或未经验证的颅内布局。",
        "计划调用pyprep.NoisyChannels.find_bad_by_ransac；尚无平台执行调用",
        [_ref("PyPREP：NoisyChannels及find_bad_by_ransac",
              "https://pyprep.readthedocs.io/en/stable/generated/pyprep.NoisyChannels.html"), _PREP_PAPER,
         _local("src/ephys_qc/method_registry.py", "本平台计划方法登记")],
        "仅登记未来直接调用PyPREP的方案；不能与已执行的BrainElecQC再实现混同。",
        validation_status=_PLANNED,
        version_note="本地安装PyPREP 0.5.0但该方法未接入；2026-10-29在线stable文档为0.10.0，后续须按实际安装版本重核API。"),

    "autoreject_epochs": _doc(
        "计划对足够且可比较的试次或窗口，估计局部通道阈值与试次复核建议。",
        "local AutoReject通过交叉验证联合选择逐通道峰峰值阈值、坏通道共识和插值数量；未来拟合后提取reject log，不默认应用清洗。",
        "local方法与现有单个全局阈值不同。坏试次/坏通道建议仍需独立真值评估，存在事件标签不代表已有可用且足够的试次。",
        "未来有明确分段规则、足够数据、已核实电极位置及可比较采集条件时；拟合本身也依赖有效位置。",
        "当前尚不可运行；不能把坐标要求只归于最终插值，也不能在缺少位置或少量窗口上宣称完成local AutoReject。",
        "计划调用autoreject.AutoReject.fit及get_reject_log；尚无平台执行调用",
        [_ref("autoreject：AutoReject",
              "https://autoreject.github.io/stable/generated/autoreject.AutoReject.html"), _AUTOREJECT_PAPER,
         _local("src/ephys_qc/method_registry.py", "本平台计划方法登记")],
        "仅登记未来直接调用local AutoReject的方案；拟合内部可能用插值评估，平台不默认执行transform。",
        validation_status=_PLANNED,
        version_note="本地autoreject 0.5.1已供全局阈值使用；local AutoReject未接入，依赖已安装不代表功能可运行。"),

    "ica_iclabel": _doc(
        "计划借助ICA成分类别提示，帮助人工区分脑、眼、肌肉等可能来源。",
        "ICLabel用ICA成分头皮图、功率谱和自相关预测七类成分概率；必须先有适当且可复现的ICA分解。",
        "分类概率是模型对成分来源的判断，不是整段EEG质量分，也不能直接变成删除规则。训练条件外的概率可靠性需重新验证。",
        "未来核实坐标、秩、参考和处理史，且有足够数据满足平均参考、1–100Hz、extended-infomax等模型适用条件时。",
        "当前尚不可运行；不借用头皮EEG论文准确率到颅内、少通道PSG或低采样率数据，不凭通道名猜空间位置，也不自动移除成分。",
        "计划调用mne_icalabel.iclabel.iclabel_label_components；尚无平台执行调用",
        [_ref("MNE-ICALabel：ICLabel特征与训练条件",
              "https://mne.tools/mne-icalabel/stable/generated/api/mne_icalabel.iclabel.iclabel_label_components.html"),
         _local("src/ephys_qc/method_registry.py", "本平台计划方法登记")],
        "仅登记未来通过MNE-ICALabel调用ICLabel的方案；现有ECG/EOG锁时与高频方法不依赖ICA。",
        validation_status=_PLANNED,
        version_note="2026-10-29本地未安装mne-icalabel，平台未接入ICA/ICLabel；将来接入需记录包及模型版本。"),
}


def method_documentation(identifier):
    """Return independent display text; unknown identifiers raise KeyError.

    A new executable/planned catalogue entry must receive an explicit source
    review rather than inheriting generic documentation that implies support.
    """
    return deepcopy(_DOCUMENTATION[identifier])


def enrich_method(method):
    """Copy a catalogue row and add documentation without changing capability."""
    result = deepcopy(method)
    result["documentation"] = method_documentation(method["id"])
    return result
