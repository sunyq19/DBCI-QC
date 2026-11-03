# EEG 检查词条与模块

项目实施规程 · 版本 eeg-basic/1.1 · 对应规范 0.8

[EEG规范](/standards) · [来源依据](/standards/eeg-evidence) · [报告要求](/standards/eeg-report) · [字段字典](/standards/fields)

## 1 目录与解释

本目录规定人类连续头皮EEG基础技术质控的词条、测量口径及证据输出。12个词条对应现有9个模块，未增加12种算法。基础项目应在评价规程中交代是否执行；条件项目核对前提后执行；描述项目没有好坏阈值。项目要求与外部资料性来源分开，所有默认数值均应由实际运行参数核对。

词条映射不是合规认证。人类/头皮范围须有来源确认；当前运行字段未完整支持该确认。算法候选、人工结论与执行状态应分别读取。完整性问题可能使后续频谱或事件方法失败；失败项没有零噪声或正常结论。

| 词条 | 检查目的 | 类型 | 模块 |
| --- | --- | --- | --- |
| [EEG-001](#eeg-001) | 文件、来源与标定 | 基础项目 | [M01](/standards/modules/M01) |
| [EEG-002](#eeg-002) | 信息、参考与检查范围 | 基础项目 | [M02](/standards/modules/M02) |
| [EEG-003](#eeg-003) | 非有限值、恒值与端点平台 | 基础项目 | [M03](/standards/modules/M03) |
| [EEG-004](#eeg-004) | 功率谱密度 | 基础项目 | [M04](/standards/modules/M04) |
| [EEG-005](#eeg-005) | 工频窄带线索 | 基础项目 | [M04](/standards/modules/M04) |
| [EEG-006](#eeg-006) | 背景谱、谱峰与α功率 | 描述项目 | [M04](/standards/modules/M04) |
| [EEG-007](#eeg-007) | 通道质量候选 | 条件项目 | [M05](/standards/modules/M05) |
| [EEG-008](#eeg-008) | 心电与眼电锁时线索 | 条件项目 | [M06](/standards/modules/M06) |
| [EEG-009](#eeg-009) | 高频突发及肌电支持 | 条件项目 | [M06](/standards/modules/M06) |
| [EEG-010](#eeg-010) | 标注与时间核对 | 条件项目 | [M07](/standards/modules/M07) |
| [EEG-011](#eeg-011) | 分项汇总与可比性 | 基础项目 | [M08](/standards/modules/M08) |
| [EEG-012](#eeg-012) | 报告、证据与人工复核 | 基础项目 | [M09](/standards/modules/M09) |

## EEG-001

**文件、来源与标定**

### 适用与计算

所有输入；主文件及必要配套成员应完整。

核对格式结构、源文件SHA-256、各采样流、通道角色、单位和数字到物理量的标定。头记录通道数与数值信号数分别保存。

### 判据与报告

文件缺失、指纹冲突或不能可靠标定应阻断相应输入；可读不表示信号合格。属于项目工程要求。

来源版本、格式、读取器版本、配套成员指纹、时钟、单位与结构警告。

### 实现与依据

[M01](/standards/modules/M01) · SRC-1833, SRC-BIDS, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M01_input.json`.

证据字段：`source_sha256`, `source_files`, `header`, `streams`, `clock`, `reader_id`, `reader_version`, `annotations`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-002

**信息、参考与检查范围**

### 适用与计算

选择已标定的头皮EEG通道和连续范围；物种/位置须有外部来源确认。

保存原始通道索引、名称、采样率、样本半开区间、辅助导联、参考和比较组。未知参考不自动确认；疾病和年龄标签不直接调整阈值。

### 判据与报告

缺少某方法前提只限制该方法。当前运行API尚未采集完整物种/年龄字段，不自动认定本专项范围已确认。

实际选道、起止秒及样本、参考声明、缺项、输入标签及冻结计划。

### 实现与依据

[M02](/standards/modules/M02) · SRC-BIDS, SRC-CAAE, SRC-IFCN, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M02_selection.json`.

证据字段：`selection`, `recording`, `channels`, `reference_channels`, `comparison_groups`, `processing_applied`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-003

**非有限值、恒值与端点平台**

### 适用与计算

已标定电压；量程端点分类另需ADC标定。

所有非有限样本均定位；对相邻有限原始采样严格相等的连续段分类（变化容差0），默认最少max(2,ceil(0.1×fs))点。近零容差max(1e-7 V,半个量化步长并考虑舍入)，仅用于恒值分类；端点容差0.25 LSB并考虑浮点精度。原始样本使用半开区间。

### 判据与报告

这些为BrainElecQC实现设置；near_zero_flatline不是生理低幅活动，端点平台不确认硬件饱和。重复数据块检测未实现。

逐道非有限计数、候选类型/位置/值、标定可用性、实际容差及未评原因；不把候选个数当异常时长。

### 实现与依据

[M03](/standards/modules/M03) · SRC-BRAINELECQC, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M03_continuity.json`.

证据字段：`parameters`, `input_range`, `measurements`, `candidates`, `interval_convention`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-004

**功率谱密度**

### 适用与计算

当前核心实现要求所选输入均有限；长度至少能形成2点窗。

Welch单边PSD，单位V²/Hz；Hann窗默认4秒、50%重叠、逐窗去均值、算术平均，nfft=nperseg。nperseg=min(N,max(2,round(4fs)))；频点间距Δf=fs/nperseg（产物字段frequency_resolution_hz）；可分辨能力还受窗函数影响。

### 判据与报告

PSD是描述量，没有统一好坏阈值。先核对参考、滤波史、分辨率和实际覆盖，再比较功率。

频率、逐道PSD、有效窗数、窗口及尾部覆盖、单位和实际参数。

### 实现与依据

[M04](/standards/modules/M04) · SRC-SCIPY, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M04_spectral.json`.

证据字段：`input`, `config`, `psd`, `software`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-005

**工频窄带线索**

### 适用与计算

至少完整4秒窗；中心加扫描半宽必须严格低于Nyquist。

BrainElecQC的Thomson型DPSS F检验：默认4秒窗/1秒步长、完整带宽2Hz，扫描50/60Hz及可测谐波±2Hz。对实际通道、完整窗和唯一扫描频点作Bonferroni校正；正弦幅值为峰值2|A|，不是RMS。

### 判据与报告

校正p<0.01是统计筛查配置，非行业合格线；显著窄带并不自动证明技术污染。

可测频带、F/p/峰值幅度、命中窗；按通道及目标频率的flagged_union_seconds为去重时长，flagged_union_fraction_of_input以输入时长为分母。不能将多个频率的时长相加当总工频时间，也不能当作已评范围污染率。

### 实现与依据

[M04](/standards/modules/M04) · SRC-BRAINELECQC, SRC-PREP, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M04_spectral.json`.

证据字段：`config`, `methods.line_noise`, `line_noise.status`, `line_noise.channel_summary`, `line_noise.observations`, `line_noise.windows`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-006

**背景谱、谱峰与α功率**

### 适用与计算

谱模型默认至少10秒、4个周期图、覆盖2–40Hz、功率为正且峰宽与分辨率相容；各输出单独检查。

FOOOF固定背景模型，默认2–40Hz，全选区和30秒局部窗分别拟合；α功率用边界插值后的PSD梯形积分，绝对8–13Hz，默认相对分母2–40Hz。

### 判据与报告

仅描述，不作合格判据；α能量含非周期背景，不等于谱峰高。年龄、状态和病理会影响谱形。

每次拟合状态、指数/峰参数/R²/误差、α绝对µV²和相对百分比、频带及未评原因。

### 实现与依据

[M04](/standards/modules/M04) · SRC-FOOOF, SRC-SCIPY, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M04_spectral.json`.

证据字段：`config`, `parameterization`, `alpha_power`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-007

**通道质量候选**

### 适用与计算

明确参考与比较组；组内阈值至少4条可用通道。混合参考或双极导联不自动放同组。

非空间PREP分项：稳健幅度0.7413×IQR及组内标准分、相对高频MAD比、1秒窗绝对相关的98% Hazen分位数、dropout比例。保留实际滤波、组尺度和已评窗分母。

### 判据与报告

默认|幅度z|>5、HF z>5；相关<0.4的窗或dropout窗占已评窗比例>0.01。为当前筛查规则，非通用坏道定义；零尺度/缺组条件不制造z值。

通道身份、描述值和判据、组门槛是否启用、候选理由、窗分母及尾部未评；来源坏道标签与检测器分开。

### 实现与依据

[M05](/standards/modules/M05) · SRC-BRAINELECQC, SRC-PREP, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M05_bad_channels.json`.

证据字段：`parameters`, `preprocessing`, `input_range`, `groups`, `channels`, `window_metrics`, `unwindowed_tail`, `candidates`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-008

**心电与眼电锁时线索**

### 适用与计算

已确认且同原生时钟的ECG/EOG辅助通道，信号有限、非恒值并满足完整锁时窗要求。

先检测辅助事件，再计算EEG锁时统计；事件数量和EEG污染程度是不同量。保留检测阈值、滤波、锁时窗、事件抽选及一致性统计设置。

### 判据与报告

辅助通道缺失或无完整锁时片段应标记未评，不能记为零污染；事件存在不直接判EEG伪迹。

每类辅助通道状态、检测/纳入事件数、原时钟位置、锁时统计、实际参数与未评原因。

### 实现与依据

[M06](/standards/modules/M06) · SRC-BRAINELECQC, SRC-MNE, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M06_auxiliary_events.json`.

证据字段：`config`, `start_sample`, `stop_sample`, `by_kind`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-009

**高频突发及肌电支持**

### 适用与计算

频带与Nyquist/滤波长度满足条件，使用M03完整性保护区；确认肌电支持另需合格同步EMG。

分析副本中的高频功率/包络突发，保留频带、时间窗、阈值和排除区；没有EMG支持的突发只能作高频线索。

### 判据与报告

当前实现配置不构成临床肌电判据；高频神经/病理活动不得直接删除。

候选区间、EMG支持状态、完整性保护范围、有效频带、实际阈值及未评原因。

### 实现与依据

[M06](/standards/modules/M06) · SRC-BRAINELECQC, SRC-MNE, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M06_muscle.json`.

证据字段：`parameters`, `status`, `reference`, `channels`, `candidates`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-010

**标注与时间核对**

### 适用与计算

提供来源明确、已支持格式和映射的标注；不把未提取等同于不存在。

核对单位、原始时间基准、越界/重叠、选区事件及覆盖；保留来源事件类别，不将任务、睡眠或发作标签改为质量标签。

### 判据与报告

缺标注表示该项未评；事件一致性不能替代硬件同步测量。

标注来源/格式、原始与映射时间、选中事件、覆盖及问题；quality_ground_truth单独声明。

### 实现与依据

[M07](/standards/modules/M07) · SRC-BIDS, SRC-1833, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M07_annotations.json`.

证据字段：`format`, `label_scope`, `selected_count`, `covered_seconds`, `issues`, `quality_ground_truth`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-011

**分项汇总与可比性**

### 适用与计算

汇总实际完成、部分、跳过和失败的模块，保留范围与配置。

分项保留原量和来源，执行覆盖按实际检查范围计算；仅比较物种、参考、带宽、状态、处理史与配置相容的数据。

### 判据与报告

通用未校准score.value保持null。EEG项目试行指数按eeg-basic-screen/0.2独立保存在report_view.score；分项为通道异常占比RMS的反向百分制，总分取最低分项，缺项不出总分。无行业合格线。

各分项状态、缺项/失败原因、原始数据未变核验、总分状态和比较条件。 EEG试行评分应另报公式版本、分项、原始分子分母及历史重算标识。

### 实现与依据

[M08](/standards/modules/M08) · SRC-1833, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`M08_assessment.json`.

证据字段：`score`, `source_unchanged`, `module_assessments`, `missing_capabilities`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## EEG-012

**报告、证据与人工复核**

### 适用与计算

所有输出；即使部分失败也应保留可追溯结果。

报告呈现来源、检查范围、分项、候选、参数与证据；词条快照关联实际产物指纹。人工意见独立追加并保留版本，旧报告不改写。

### 判据与报告

报告不作临床诊断或合规认证；未经人工复核保持pending。词条映射不是自动证明满足规范。

方法与环境版本、源代码指纹、显示范围、词条版本、证据索引和独立复核记录入口。

### 实现与依据

[M09](/standards/modules/M09) · SRC-1833, SRC-CAAE-QC, SRC-PROJECT · [依据定位](/standards/eeg-evidence)

产物：`environment.json`、`waveform_selection.json`.

证据字段：`implementation`, `packages`, `actual_executed_sources`, `channel_names`, `start_seconds`, `duration_seconds`.

工程行为与公开样例执行已有记录；未建立独立专家标签上的通用准确率或行业合格线。

## 2 可选方法与词条关系

可选方法补充已有词条的证据，不自动增加质量分或形成多数票真值。依赖、实际参数和失败原因保存在各扩展产物中；缺失原值明确标注，不从候选名单反推数值。

| 词条 | 已接入方法 | 解释边界 |
| --- | --- | --- |
| EEG-003 | MNE幅度；global AutoReject | 相邻差值与峰峰值不同；全局阈值是同选区探索估计，固定段非任务试次 |
| EEG-007 | MNE桥接、LOF；mne-faster | 通道对非坏道数；桥接实际分界点、FASTER原始特征及z值未导出；FASTER为Python实现 |
| EEG-009 | MNE高频包络；FieldTrip差分z值 | 通用高频/差分异常线索，不能自动确认肌电；FieldTrip通过Octave兼容运行 |
| 处理影响评估 | ASR、CleanLine、Zapline-plus | 显式选择、临时副本、未导出清洗信号；改变功率不证明质量改善 |

PyPREP RANSAC、local AutoReject、ICLabel未接入。选用门槛与论文验证范围不是同一概念；例如FASTER低通道数仍需独立验证，详见来源依据。

## 3 版本与复核

本页由src/ephys_qc/specifications/eeg-basic.v1.json生成。新EEG报告保存eeg-rules.json原始目录字节及SHA-256、eeg-assessment.json逐项证据索引、方法产物和有效参数。目录变化须更新版本并重建中英文页面；既有报告不回填。整记录须保留每窗报告，不累加不同频率、通道或重叠窗的时间作为总污染率。
