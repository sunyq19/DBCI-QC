# EEG 质控依据与适用边界

资料性文件 · evidence/1 · 核验日期：2026年10月31日

[返回头皮 EEG 规范](/standards) · [返回质控台](/)

本页为 DBCI-QC 项目技术规范提供可追溯依据。项目规范是征求意见稿，不是已发布的国家标准、行业标准或团体标准。下列资料按其原有适用范围引用；采用某项字段或方法不构成对整份外部标准的符合性声明。

## 1 依据类型

| 类型 | 用途 | 引用规则 |
| --- | --- | --- |
| 行业标准 | 数据集描述、采集记录、标注和追溯要求 | 记录状态、适用对象、具体条款；尚未实施的文件仅作前瞻参考 |
| 专家指南、协会工作文件 | 特定临床场景的采集、报告与人工评价结构 | 保留场景及推荐性质，不扩展为所有研究数据的拒收线 |
| 数据规范 | 字段含义、组织关系及互操作要求 | 数据结构符合性与信号质量分别评价 |
| 方法论文、作者手册、官方接口 | 指标定义、算法前提和实现来源 | 方法默认参数不是行业合格线；文献结果不是本平台准确率 |
| 项目约定 | 坐标、状态、覆盖、配置与报告之间的工程契约 | 明示为项目规定，并以可复算样例及测试验证 |

以下 `SRC-*` 为稳定依据标识，供规则、模块和报告引用。M01–M09 是本项目的实现映射，不是外部标准的章节名称。来源本身不证明当前软件已经实现相应要求；实际能力以[实现范围](/standards/implementation)为准。

## 2 依据索引

| 标识 | 依据 | 主要对应内容 |
| --- | --- | --- |
| [SRC-1833](#src-1833) | YY/T 1833.2—2022 | 数据身份、用途、采集依据、标注及追溯；M01、M02、M07、M09 |
| [SRC-2029](#src-2029) | YY/T 2029—2026 | 电极、采样、滤波、噪声和版本记录；M01–M07、M09 |
| [SRC-CAAE](#src-caae) | CAAE 2022 专家指南 | 临床记录背景及报告结构；M02、M07、M09 |
| [SRC-CAAE-QC](#src-caae-qc) | CAAE 2024 质控工作意见 | 记录与报告分别评价、专家复核；M08、M09 |
| [SRC-IFCN](#src-ifcn) | IFCN/ILAE 2023 最低记录指南 | 常规与睡眠临床 EEG 采集条件；M01、M02 |
| [SRC-BIDS](#src-bids) | BIDS EEG 1.11.2 | 通道、电极、参考、采样及滤波字段；M01、M02、M07 |
| [SRC-PREP](#src-prep) | PREP 2015 方法论文 | 非有限、平坦、幅度、相关和噪声线索；M03、M05 |
| [SRC-FASTER](#src-faster) | FASTER 2010 论文及作者手册 | 统计离群通道筛查；当前扩展M05 |
| [SRC-AR](#src-ar) | Autoreject 2017 方法论文 | 分段峰峰值及交叉验证阈值；当前扩展M03 |
| [SRC-SCIPY](#src-scipy) | SciPy Welch官方接口 | PSD计算口径；M04 |
| [SRC-FOOOF](#src-fooof) | Donoghue等2020论文及FOOOF接口 | 非周期背景和谱峰参数；M04 |
| [SRC-BRAINELECQC](#src-brainelecqc) | BrainElecQC固定版本源码 | 完整性、工频检验、频带积分及高频组合方法；M03–M06 |
| [SRC-MNE](#src-mne) | MNE 官方接口 | 谱估计、桥接、LOF及辅助信号事件；M04–M06 |
| [SRC-PROJECT](#src-project) | DBCI-QC 项目约定 | 状态、原始坐标、覆盖分母、报告及复核契约；M01–M09 |

## SRC-1833

**YY/T 1833.2—2022《人工智能医疗器械 质量要求和评价 第2部分：数据集通用要求》**。官方目录标为现行，2023-07-01 实施。

- **定位：**§4.1.1–4.1.4，正文第3–4页／PDF第7–8页；§5.2.11，正文第8–9页／PDF第12–13页。§4.1.4.3短摘录：“标注分歧的仲裁机制”。
- **采用：**数据形态、用途、版本、来源、预处理和标注流程的说明，以及审核与更新的可追溯性。
- **边界：**适用于人工智能医疗器械数据集。它不指定 EEG 坏道算法、固定振幅阈值或统一质量总分。文件哈希、运行 ID 和本项目报告排版是工程实现选择。

[官方目录](https://hbba.sacinfo.org.cn/stdDetail/ad8c7508b67bea44c82a1d0dd7f749d35b7b258990738862da863ef34317ad30) · [官方全文](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2022/20220720/YYT183322022.pdf)

## SRC-2029

**YY/T 2029—2026《脑机接口医疗器械 用于人工智能算法的脑电数据集质量要求与评价方法》**。2026-08-24 发布，2027-09-01 实施；核验日官方目录为“即将实施”。

- **定位：**§5.1–5.2.9，正文第2–3页／PDF第8–9页；§6.5、§7.4、§7.7及§8.2.2，正文第7–10页／PDF第13–16页。§5.2.6以责任方“声称值”约束系统噪声。
- **采用：**前瞻参考电极、参考、采样率、滤波、处理履历、标注和版本记录。§8.2.2分别给出工频峰值或功率谱及特定频带 RMS 的噪声测量思路。
- **边界：**适用对象是相应 BCI 医疗器械的数据集；未给出对所有头皮 EEG 通用的工频比例或坏道界线。当前平台的高频功率比不能直接标称为该条款的基底噪声测量。

[官方目录](https://hbba.sacinfo.org.cn/stdDetail/866eaadd4e5c255fdb8e12030faa6b574a71658ab56fa22d356104c3561fd11b) · [官方全文](https://app.nidc.org.cn/jianybz/bz_file_pdf/wwgk/ylqxtjxhybz/2026/2026-10/2c9048cca08f981001a12512f7a54d97.pdf)

## SRC-CAAE

**中国抗癫痫协会，2022《临床脑电图技术操作指南》专家指南系列**，《癫痫杂志》8(1)。

- **定位：**指南九§1–3，期刊第38–39页／PDF第37–38页；开篇要求“全面、简要和有重点”的描述。指南一§2.7及指南九§1.5–1.6分别涉及参数、记录状态和检查信息。
- **采用：**记录背景、实际采集条件、状态及事件的结构化描述；区分技术记录与专业解释。
- **边界：**这是专家指南；研究质控报告不据此自动形成临床诊断。不得将2022指南条文标成2026团体标准条文。

[协会官方全文](https://www.caae.org.cn/Public/Uploads/20220118/video/61e6242d78ca7.pdf)

## SRC-CAAE-QC

**中国抗癫痫协会《关于开展脑电图质控工作的意见》**，中抗协发〔2024〕11号，2024-03-25。

- **定位：**第二、三部分，PDF第3–4页；短摘录：“复核和内控机制”。文件分别列出9项报告质量与7项记录质量评价内容。
- **采用：**记录质量、报告质量分别评价，并保留专家抽样评价和复核环节。
- **边界：**面向协会癫痫中心质控工作，不是自动算法评分表；不能从16项名称推出算法权重、0–100分或统一伪迹阈值。

[协会正文入口](https://www.caae.org.cn/news/show/id/539) · [官方PDF](https://www.caae.org.cn/ueditor/php/upload/file/20240325/1711335645879652.pdf)

## SRC-IFCN

**Peltola 等，2023，IFCN/ILAE 常规与睡眠 EEG 最低记录指南**。

- **定位：**§3.2、Table 3、§3.3.1；原文短摘录：“our recommendations are conditional”。本页采用作者全文的章节定位，不混用两家期刊的页码。
- **采用：**在对应临床场景下记录电极配置、辅助导、采样和时长。表中256 Hz为该场景最低采样率建议；0.5–70 Hz属于显示滤波建议。
- **边界：**这些条件性推荐不能直接作为所有研究片段、少导睡眠数据或侵入式数据的拒收线；显示滤波不等于必须改写原始数据。

[正式论文：Clinical Neurophysiology](https://doi.org/10.1016/j.clinph.2023.01.002) · [联合发表：Epilepsia](https://doi.org/10.1111/epi.17448) · [作者全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC10006292/)

## SRC-BIDS

**BIDS EEG，固定版本1.11.2**。

- **定位：**EEG章节的术语说明、Sidecar JSON、Channels description及Electrodes description；字段等级同时核对版本化schema。
- **采用：**区分电极与采样通道；参考、采样率、工频及软件滤波为对应BIDS对象的必填字段；提供通道表时，`name/type/units`为必需列。
- **边界：**BIDS规定组织和元数据。BIDS验证通过不代表信号质量合格；原始格式缺少某个BIDS字段也不等于文件损坏。来源通道`status`不自动成为本项目的独立质量真值。

[官方版本化章节](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/modality-specific-files/electroencephalography.md) · [Sidecar字段等级](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/schema/rules/sidecars/eeg.yaml) · [通道表字段等级](https://github.com/bids-standard/bids-specification/blob/v1.11.2/src/schema/rules/tabular_data/eeg.yaml)

## SRC-PREP

**Bigdely-Shamlo 等，2015，The PREP pipeline**。

- **定位：**摘要及方法小节“Detecting noisy or outlier channels”；短摘录：“identification of noisy channels depends on the reference”。
- **采用：**参考条件下的幅度、相关、预测及高频噪声筛查思路，附带数值异常和恒值检查。
- **边界：**当前基础模块来自 BrainElecQC 的非空间实现，不等于完整 PREP 或 PyPREP。论文参数及实验准确率不能直接当作本平台验收结果；本地实现的分位数、滤波和比较组条件须单独记录。

[原论文全文](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2015.00016/full) · [原始MATLAB项目](https://github.com/VisLab/EEG-Clean-Tools) · [BrainElecQC固定实现](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/bad_channels.py)

2026-10-12的[勘误](https://www.frontiersin.org/journals/neuroinformatics/articles/10.3389/fninf.2026.2015651/full)修正代码获取链接并补充可用性声明；未发布新的通道判据。

## SRC-FASTER

**Nolan、Whelan、Reilly，2010，FASTER**；作者手册v1.2.3，发行文件v1.2.3b。

- **定位：**论文摘要；手册PDF第15页“Channel rejection”、第32页FAQ和脚本用法。短摘录：“It has not been tested on fewer than 32 channels”。
- **采用：**多个通道统计量的离群筛查，以及方法参数和模块开关的记录。
- **边界：**论文全文未取得；详细操作依据作者手册。本平台使用 MNE-FASTER Python实现，不能声称运行了原始MATLAB全流程。适配器的8道执行门槛不等于原研究覆盖了8道数据；默认标准分3不是行业质量线。

[论文及摘要](https://pubmed.ncbi.nlm.nih.gov/20654646/) · [作者发行页](https://sourceforge.net/projects/faster/files/) · [作者手册](https://downloads.sourceforge.net/project/faster/FASTER%20manual.pdf)

## SRC-AR

**Jas 等，2017，Autoreject: Automated artifact rejection for MEG and EEG data**。

- **定位：**作者版本v3，§2.1公式(1)–(4)、§2.2及§3；global方法短摘录：“same threshold for all sensors”。
- **采用：**分段峰峰值、交叉验证阈值和训练/评价范围的记录。
- **边界：**global阈值估计与local逐通道阈值、插值是不同功能。当前固定窗筛查不等于任务试次有效性，也不证明已经实现local清洗。估计阈值依赖数据，不是统一振幅标准。

[正式论文](https://doi.org/10.1016/j.neuroimage.2017.06.030) · [作者全文v3](https://arxiv.org/html/1612.08194v3) · [global接口](https://autoreject.github.io/stable/generated/autoreject.get_rejection_threshold.html) · [local接口](https://autoreject.github.io/stable/generated/autoreject.AutoReject.html)

## SRC-SCIPY

**SciPy `signal.welch`官方文档及Welch（1967）原始方法**。接口页核验时标示SciPy 1.18.0，运行版本另行记录。

- **定位：**接口说明、`scaling`、`average`和Notes；短摘录：“averaging the periodograms”。原始方法见Welch，IEEE Transactions on Audio and Electroacoustics 15(2):70–73。
- **采用：**以窗函数、分段、重叠、去趋势及聚合方式定义PSD；输入为V且频率为Hz时，`density`输出V²/Hz，区别于V²功率谱。
- **边界：**BrainElecQC选择的4秒窗等是封装配置；PSD和积分提供测量值，不提供EEG质量合格线。频点间距与真实谱分辨能力不能一概等同。

[官方接口](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html) · [Welch原论文DOI](https://doi.org/10.1109/TAU.1967.1161901)

## SRC-FOOOF

**Donoghue等，2020，Parameterizing neural power spectra into periodic and aperiodic components**，Nature Neuroscience 23:1655–1665；FOOOF 1.1.1官方接口。

- **定位：**论文Methods的“Algorithmic parameterization”及Discussion；接口Notes、`aperiodic_mode`、`peak_params_`、`r_squared_`。原文短摘录：“putative periodic oscillatory peaks”。
- **采用：**分开描述非周期背景与背景上方的谱峰，保留拟合范围、模式、峰参数及误差。接口接收线性频率和线性功率，内部在log10功率空间建模。
- **边界：**峰高不是含背景的α频带积分；拟合优度不是信号质量总分。谱峰不必然代表真实振荡，无峰也不能判为坏道。当前固定背景模式与拟合门槛是项目选择。

[正式论文](https://doi.org/10.1038/s41593-020-00744-x) · [作者全文](https://pmc.ncbi.nlm.nih.gov/articles/PMC8106550/) · [FOOOF接口](https://fooof-tools.github.io/fooof/generated/fooof.FOOOF.html)

## SRC-BRAINELECQC

**BrainElecQC，固定提交`f007d829712d1b824cda79409d181a3313d6a78f`**，本项目基础方法的直接实现来源。

| 源码位置 | 采用内容 | 依据性质 |
| --- | --- | --- |
| [`continuity.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/continuity.py)，`ContinuityConfig`及标定分类 | 非有限、连续相等、近零及端点平台 | 参数与分类是实现规则，不来自通用临床阈值 |
| [`spectral.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/spectral.py)、[`alpha_power.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/alpha_power.py) | Welch封装、DPSS/F检验、多重校正及频带积分 | [Chronux `ftestc`](https://chronux.org/chronuxFiles/Documentation/chronux/spectral_analysis/continuous/ftestc.html)是F检验原理参考，平台未直接调用Chronux；扫描及校正范围须按本实现记录 |
| [`bad_channels.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/bad_channels.py) | PREP非空间分项 | 与完整PREP分开标识，见SRC-PREP |
| [`events.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/events.py)、[`muscle.py`](https://github.com/Jlei61/BrainElecQC/blob/f007d829712d1b824cda79409d181a3313d6a78f/src/brainelecqc/eeg/muscle.py) | EEG锁时汇总、高频联合条件与EMG支持 | 高频组合方法使用MNE原语，不能称为原版`annotate_muscle_zscore` |

固定源码支持追溯实现，不证明其参数已获得行业共识或独立临床验证。

## SRC-MNE

**MNE官方接口说明**。核验时网页标示1.13.2；这是来源文档版本，不声明本次运行使用相同版本。

| 官方接口及定位 | 支持的定义 | 使用边界 |
| --- | --- | --- |
| [`psd_array_welch`，Parameters / Returns](https://mne.tools/stable/generated/mne.time_frequency.psd_array_welch.html) | Welch谱估计的分段、窗、重叠、FFT和聚合参数 | PSD测量不直接提供EEG合格线；报告须保留实际参数及功率单位 |
| [`compute_bridged_electrodes`，Parameters / Returns](https://mne.tools/stable/generated/mne.preprocessing.compute_bridged_electrodes.html) | 通道差波形方差构成的电距离与桥接通道对 | `lm_cutoff`是寻找局部极小值的范围上限；不能当作平台已返回的实际最终分界点 |
| [`find_bad_channels_lof`，threshold](https://mne.tools/stable/generated/mne.preprocessing.find_bad_channels_lof.html) | 基于距离的通道离群因子 | 官方将阈值称为“hyperparameter to optimize”；默认1.5不是行业标准 |
| [`find_eog_events`](https://mne.tools/stable/generated/mne.preprocessing.find_eog_events.html) / [`find_ecg_events`](https://mne.tools/stable/generated/mne.preprocessing.find_ecg_events.html)，Returns | 辅助信号中眼动/心搏事件的位置 | 检出辅助事件本身不证明EEG受到污染；仍需锁时或其他支持证据 |
| [`annotate_amplitude`](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html) / [`annotate_muscle_zscore`](https://mne.tools/stable/generated/mne.preprocessing.annotate_muscle_zscore.html)，Parameters / Returns | 可选的相邻差值检查和跨通道高频时间候选 | 与BrainElecQC基础恒值扫描、高频组合方法分别报告 |

这些接口文档说明方法行为，不提供本平台准确率背书。运行报告应另外给出实际包版本、调用参数、适用性和来源身份映射。

## SRC-PROJECT

**DBCI-QC 项目规定**，来源为本项目[总则](/standards/overview)、[字段字典](/standards/fields)、[方法适用规则](/standards/applicability)和模块说明。

以下要求属于本项目为可复核性制定的契约：稳定记录与候选ID、原始样本坐标、覆盖分母、重叠区间去重、未评与未检出分离、配置冻结、HTML与JSON一致、算法候选与人工结论分别保存。它们不能标成上述外部文件的逐字条款。

非有限值、数值平坦、端点平台、高频比等检查，应逐项说明“直接实现来源”和“项目参数”。没有外部数值依据的判据明确登记为项目规则，不以多个文献名称代替阈值验证。跨数据比较和总分还需独立的校准与用途验证。

[EEG 项目评分规则](/standards/eeg-scoring)中的候选占比、可配置加权平均及整份汇总口径均为本项目规定；PREP、HAPPE 和外部标准不提供该公式或其有效性背书。

## 3 核验层级与版本

- 两份YY/T官方目录于本次重新核验；条款位置据既有中检院官方PDF留档复核。CAAE官方网页本次读取返回502，引用内容据既有协会官方PDF留档复核，不声明重新下载成功。
- **T/CAAE 002—2026**的[官方目录](https://www.ttbz.org.cn/standardDetail/3dbp0828nk5v40yqbkss6m7m651q4sj.html)本次显示现行、2026-02-06实施；未取得正式正文，不分配用于具体判据的依据ID，也不假定它与2022专家指南逐条相同。
- IFCN/ILAE、PREP、Autoreject正文及官方软件文档已在线核验；FASTER论文只核到摘要，手册为既有作者发行PDF。BIDS采用固定版本源码和字段schema，避免网页宏未展开时猜测要求等级。
- 本页仅保留短摘录、定位和链接，不随仓库再分发外部标准全文。下列SHA-256用于区分核验版本，不表示发布方认可本项目。

| 留档文件 | SHA-256 |
| --- | --- |
| YY/T 1833.2—2022 PDF | `ea6ddb9169c3685e16f6faa607b8d284a94675ccfb06c1bc3787cdcb505efb40` |
| YY/T 2029—2026 PDF | `cfaabe9e6202a9f06fe90aa16a1837f9c39ab65e150a0913dfea76e76b10bfac` |
| CAAE 2022 指南PDF | `68a9d87e194b6d17bd7d8685469194ad16e5cd06d268b35321818394af1e55a2` |
| CAAE 2024 工作意见PDF | `8375dc49108d0fbe13d54d57b3eb1ab1fcf720cd6c8751537e0bfe2c751bf70f` |
| FASTER 作者手册PDF | `2dcf3fd0c73b950a7d1e5e6d36ea468b89b7ae2adcb15bd42f43bda5365445c1` |
