# 文件格式与接入约定

适用实现：工作台 1.0.0rc2。格式读取、元数据确认与质量检查分别执行。

## 1 接入范围

| 格式 | 上传入口 | 必需文件 | 本版边界 |
| --- | --- | --- | --- |
| EDF / EDF+ | `.edf` | 单个波形文件 | 连续记录；EDF+D 和注释专用文件不作为连续波形输入 |
| BDF | `.bdf` | 单个波形文件 | 24 位数字样本；不支持 BDF+D；状态/触发通道不是 EEG 电压 |
| BrainVision | ZIP | `.vhdr` 及其引用的 `.vmrk/.eeg` | 三件套同目录，保留引用和原文件名；当前拒绝重名通道；`.eeg` 不能独立解释 |
| EEGLAB | 内嵌数据 `.set`，或 ZIP | `.set`；外置数据时还需其引用的 `.fdt` | 连续 SET；分段 epochs 不纳入本版连续质量检查 |
| FIF | 单个 `.fif` | 单个 Raw FIF | 分卷和 Epochs/Evoked 等非 Raw 对象不纳入；保留混合通道类型 |

ZIP 为上传容器，不是新增信号格式。包内应只包含一份记录及其配套文件；主文件必须唯一。文件引用限于同目录实体文件，不接受绝对路径、上级路径、远程引用或符号链接。缺件或歧义不通过自动改名、猜测或读取包外文件解决。

## 2 读取与确认

1. 格式适配器提取通道身份、采样率、样本数、物理单位、标定、时间起点、文件关系及可读出的标注。
2. 界面分别呈现技术事实与使用者补充字段，并保留来源和未知状态。
3. 使用者确认数据模态、通道角色、参考及背景后，系统检查方法适用性。
4. 只有确认的头皮 EEG 进入本版头皮质量检查。sEEG、ECoG、MEG 等可保留可提取技术信息，不执行错配的头皮算法。

格式不能证明模态，单位为 V 也不能证明信号来自头皮。读取器默认的 EEG 类型、名称推断、文件事件或坏道字段均不替代人工确认和来源说明。

## 3 单位与时间

适配器应保留原始通道索引、名称、单位声明和实际标定依据。分析输入转换为 V；不把任意非电压数据赋予电压单位。文件未提供量程端点时，不补造端点饱和证据。

本版不以隐式重采样、重参考或跨流对齐使输入满足条件。BDF 适配器按原生采样流读取，不调用 MNE 的混合采样率自动升采样路径。

当前只有 FIF 适配器提取源文件声明的高通和低通信息；该声明不是对实际滤波传递函数的验证。其余格式未取得的采集滤波史保留未知。

应保留源样本起点与时间偏移，尤其 FIF 的 `first_samp`。数据中的边界注释、删除段及采集跳过不能静默解释为无中断的原始记录。

当前原生EDF/BDF接入要求TAL时间轴与从零开始的连续头部时钟一致。实际TAL含缺口、非零首时钟或与头部累计时长不符时明确拒绝；不将其压缩成连续信号。这是本版时间模型的支持边界，不将所有此类来源判为文件损坏。

EDF+标记未写持续时间时，显式任务/临床映射仅保留为零时长点事件，派生表记录原始持续时间是否存在；不能据此推定分期或临床事件跨度。睡眠分期映射仍要求来源明确给出正时长。

## 4 背景与语言

疾病、年龄、任务和采集参考由来源文件或使用者明确提供，缺失时保留未知。疾病标签不构成质量阈值标准，也不单独触发质量扣分。

中文与英文为独立显示版本。语言切换不修改原始通道名、格式标识、模块或方法 ID、数值、单位、配置和判断结果；未知、未评、失败与待复核的含义保持一致。

## 5 公开样例与验证口径

本地样例提供四种新增格式及多文件 ZIP。下载文件保持上游字节，清单记录固定来源、许可核对、大小、SHA256、技术摘要和样例性质。

版本化来源登记为`datasets/reader-samples.json`。在新环境运行`python scripts/public_examples/prepare_reader_samples.py --output /path/to/new-samples`可复现下载和打包；对已有目录加`--verify-only`只校验原文件及ZIP成员，不联网或改写。实际信号不放入代码仓库。

| 样例 | 已核对技术信息 | 可支持的结论 |
| --- | --- | --- |
| MNE BDF 夹具 | 73 道、2048 Hz、1 s | 小文件读取与短窗条件边界；不能作为完整方法验证 |
| MNE BrainVision 夹具 | 32 道、1000 Hz、7.9 s，含非电压通道 | 三件套、单位和通道角色核对 |
| MNE EEGLAB 教程夹具 | 32 道、128 Hz、238.3125 s，SET/FDT | 连续 SET 配套读取；任务事件不是质量真值 |
| MNE sample 截短 FIF | 60 EEG、1 EOG，另含 MEG/STIM；约 20 s | 混合类型与非零起点保留；不等于支持 MEG 质量检查 |

工程夹具、真实记录派生片段和独立自然质量真值分开登记。读取成功、窗口数值一致和生成报告均不构成检测准确率验证。许可未明确的文件不随网站公开发布。

EDF、BDF、BrainVision、EEGLAB、FIF 五类文件已完成实际 HTTP 接入至报告流程，未出现失败模块。部分方法因时长、带宽或信息不足未评；上述结果不表示所有方法均可评或准确率验证通过。

## 6 读取模块接口

`src/ephys_qc/readers/` 独立于上传界面和质量算法。`list_readers()` 公开格式、扩展名、配套文件要求与边界；`inspect_recording(path)` 返回 JSON 技术信息；`open_reader(path, record_id)` 返回以下统一接口。

| 接口 | 必需内容 |
| --- | --- |
| `metadata()` | 格式、通道、单位、采样率、记录时长、来源清单、原始注释摘要、模态证据与未知状态 |
| `describe()` | 原始源索引、稳定通道ID、已标定单位、原生流和连续段、源样本起点、全部实际读取文件及其指纹 |
| `read_window(stream_id, segment_id, channel_ids, start_sample, stop_sample, 'physical')` | 一个连续段内的指定源通道，返回通道×采样点的SI数值；不得隐式重采样或读入包外成员 |
| `close()` | 释放读取资源 |

新增格式时增加适配器与注册项，补上主文件和伴随引用核验、独立数值对照、单位和时间边界测试，再用真实文件完成上传至报告的验收。无需在检测模块中增加格式分支。格式支持与模态质控支持分别声明；仅增加读取器不自动开放新的模态算法。

## 7 官方依据

- [BioSemi BDF 原始格式说明](https://www.biosemi.com/faq/file_format.htm)：24 位样本、通道标定与状态通道。
- [Brain Products BVCDF 说明](https://www.brainproducts.com/support-resources/brainvision-core-data-format-1-0/)：头、标记和波形三件套。
- [EEGLAB 数据结构](https://eeglab.org/tutorials/ConceptsGuide/Data_Structures.html#saved-set-files)：SET 内嵌数据与 SET/FDT 分离保存。
- [MNE BDF](https://mne.tools/stable/generated/mne.io.read_raw_bdf.html)、[BrainVision](https://mne.tools/stable/generated/mne.io.read_raw_brainvision.html)、[EEGLAB](https://mne.tools/stable/generated/mne.io.read_raw_eeglab.html)、[FIF](https://mne.tools/stable/generated/mne.io.read_raw_fif.html)：实际读取接口及其默认行为。
- [BIDS EEG 1.11.2](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/electroencephalography.html)：EEG 文件组织和元数据。FIF 的本地读取支持不代表它成为 BIDS EEG 原始格式。
