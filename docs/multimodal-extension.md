# 多模态模块分层与接入约定

项目设计约定 · 2026-10-30 · 对应 seeg-basic/1 与 neuropixels-raw/1

## 1 产品流程

所有输入沿用“读取 → 确认 → 推荐 → 执行 → 报告与复核”。首页不要求先选择模态。读取器提取格式、流、通道、采样率、单位、时长和来源标注；文件声明足够时提出模态建议，用户确认后才登记并生成计划。未知模态不回退到头皮EEG。

文件、记录系统、模态和信号层级是不同字段。例如，SpikeGLX是保存与采集约定，Neuropixels是探针记录系统，extracellular表示胞外记录，AP/LF是所选电压流；分选后的unit属于另一信号层级。FIF可以保存sEEG，但FIF扩展名本身不证明sEEG。

一个文件可以含多个通道角色。分析组仅包含本次兼容神经通道；辅助生理通道、数字同步字及其他神经模态应分别保留身份。一次计划不混用不同采样时钟，不自动拼接AP/LF或跨探针对齐。

## 2 软件层级

| 层 | 责任 | 本次新增 |
| --- | --- | --- |
| 读取器 | 配套文件、原生流、标定、通道和时间身份 | sEEG复用FIF等已接入电压读取器；Neuropixels接入明确支持的SpikeGLX单流 |
| 数据画像 | 模态证据、所选分析组、记录系统、上下文和缺失项 | sEEG与extracellular独立画像；AP/LF保留不同流属性 |
| 检查职责 | M01–M09共同责任、依赖和结果契约 | 不为每个模态重建一套用户流程 |
| 方法实现 | 适用性、配置、数学计算与解释 | M03–M05复用描述性数学核；sEEG/Neuropixels分别设入口和参数 |
| 报告与复核 | 源指纹、版本、覆盖、指标单位、证据及未评原因 | 所有路线使用同一可追溯结果结构；评分仍为null |

共享计算核不等于共享判定标准。有限值扫描、Welch和逐通道统计可共享计算；头皮空间邻域、参考比较、幅度异常阈值或临床解释不可随代码复用自动迁移。

## 3 路线与参数

| 路线 | 数据对象 | 方法配置键 | 默认频谱窗 | 当前基本模块 |
| --- | --- | --- | --- | --- |
| seeg-basic/1 | 已确认的sEEG源触点电压 | method_config.seeg | 4秒 | M03完整性、M04频谱观察、M05逐触点统计 |
| neuropixels-raw/1 | 一个SpikeGLX AP流 | method_config.neuropixels | 0.1秒 | M03完整性、M04流内频谱、M05逐通道统计 |
| neuropixels-raw/1 | 一个SpikeGLX LF流 | method_config.neuropixels | 1秒 | M03完整性、M04流内频谱、M05逐通道统计 |

以上均保留M01接入、M02计划、M08汇总、M09报告；登记合适事件表后加入M07。M06当前未接入，不能以“未发现伪迹”替代未评状态。频谱默认观察50/60Hz附近可测频段，显示实际分辨率；计算配置不是质量阈值。

## 4 sEEG的专属边界

电极杆、触点、记录通道及双极派生应分别有身份与来源。相邻编号不保证解剖相邻，同一杆也可能跨越不同组织。当前只保留来源声明；不由名称猜配对、不自动重参考、不做跨杆统计异常判定。

来源坏道、发作标注和病理活动必须保留原语义。发作、棘波或高频活动不能仅凭频谱作为伪迹扣分；任务事件也不作为质量真值。后续每个专属方法需要明确目标、标注覆盖、独立验证数据与可解释失败条件。

[sEEG技术规范](/standards/seeg)

## 5 Neuropixels的信号层级

| 层级 | 必需输入 | 合理检查 | 本版状态 |
| --- | --- | --- | --- |
| 原始电压 | .bin/.meta、探针和增益、源通道/样本 | 长度与标定一致性、基本完整性、幅度统计、流内频谱 | 接入受支持的SpikeGLX AP/LF单流 |
| 预处理与探针状态 | 原始电压、空间布局、滤波/参考、方法配置 | 噪声估计、坏道候选、漂移及采样相位问题 | 后续独立方法；不在本版报告中声称完成 |
| 分选结果 | unit身份、spike时间、分选器和参数、原始记录引用 | 时间合法性、发放率、presence ratio、ISI违例 | 尚未接入 |
| 依赖原始波形的unit评价 | 分选结果、波形/模板、噪声估计与时间映射 | SNR、幅度稳定性、模板及隔离相关指标 | 尚未接入；依赖不足时不得伪造数值 |

原始通道数不等于unit数；神经元产量不等于原始记录质量。AP与LF来自同一记录时应共享观测标识，避免重复计作独立验证样本。即使存在同步道，跨设备同步仍需独立验证。

[Neuropixels原始记录规范](/standards/neuropixels)

## 6 数据与验证门槛

### 6.1 sEEG公开样例

来源固定为mne-tools/mne-misc-data提交`d8ceb830cf0b05191dbde118e05f39a410567a8b`的`seeg/sample_seeg_ieeg.fif`。复现脚本为`scripts/public_examples/prepare_seeg_example.py`；独立读取核对脚本为`scripts/public_examples/audit_seeg_example.py`。下载、证据与登记草稿均写到仓库外，脚本不修改工作台配置或触发任务。

样例保留119道、59,966样本、999.412109375Hz和32条任务标注。上传副本与来源SHA-256一致，不重新写FIF、不裁切或清洗。原始首样本1,310,640与文件内0秒同时保留；派生事件表仅转换为文件内时间坐标。独立按FIFF标签和大端float32缓冲区解码，7,135,954个数值与适配器全部一致。疾病、原始采集参考和完整处理史未独立证实。

### 6.2 Neuropixels公开样例

本次正例为人脑Pt03 AP原记录60–62秒的2秒派生片段，以及Noise4Sam LF的5.2652秒格式测试片段；两者均已完成独立读取核对。0.02秒短窗边界来自已核验人脑AP片段内的选区，不另计独立观测。ACSF AP的声明SHA1与实际不符，截短Noise4Sam AP的原始长度/哈希也不一致，均保留为拒绝负例，不登记为可运行数据。

来源、下载/派生头、许可与字节哈希须单独保存；LF格式测试文件不称为生理质量标注数据。实际工作台执行覆盖以版本验收记录为准。真实数据仅覆盖NP1；NP2型号21/24目前仅有合成读取契约测试，不能称为真实NP2验证。当前没有spike sorting或单元质量评价。

Pt03为公开大型记录的指定字节范围，不下载整份原记录；因此完整原文件MD5未核验。片段保持源数字帧，派生头应明确原始样本起点与新长度；不得保留失效的全文件哈希并声称它对应片段。

[Pt03来源](https://zenodo.org/records/5899237) · [格式测试库](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data)

### 6.3 执行验收

每条新路线都应保留以下证据，结果记录在版本验收文档中：

1. 来源、许可证、版本、下载大小与哈希；表示副本不增加独立观测数。
2. 独立核对样本数、采样率、单位、通道身份及非零首样本；Neuropixels另外核对逐通道增益和同步字排除。
3. 真实样例完成上传、提取、人工确认、推荐、计划、显式运行及报告；提取或推荐本身不创建任务。
4. 新模态走独立配置，旧EEG/ECoG任务与证据保持不变；跨模态浏览方法不修改当前计划。
5. 同步字、其他模态、未知单位、不支持探针、缺失配套及损坏长度应有明确拒绝或未评原因。
6. 数值计算、读取工程一致性、页面交互和科学准确性分别记录。运行成功不表示坏道检测已被临床标注验证。

## 7 依据

- [MNE sEEG示例](https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html)：公开示例文件及来源场景。
- [BIDS iEEG](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/intracranial-electroencephalography.html)：通道、电极、参考和采样信息的区分。
- [SpikeGLX元数据](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html)：配套文件、采样、保存通道和同步字声明。
- [SpikeInterface核心对象](https://spikeinterface.readthedocs.io/en/latest/modules/core.html)：原始recording与sorting以及联合分析对象的区分。
- [SpikeInterface Neuropixels示例](https://spikeinterface.readthedocs.io/en/stable/how_to/analyze_neuropixels.html)：探针预处理、分选和单元评价的不同阶段。
