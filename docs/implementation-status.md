# 当前实现与验证范围

资料性文件 · 版本 implementation/1 · 2026-10-31 · 软件基线 1.0.0rc3.dev8

[总则](/standards/overview) · [字段字典](/standards/fields) · [方法适用规则](/standards/applicability)

本文件说明规范与当前软件的对应关系，不新增质量阈值。运行成功、数值一致、真实标签验证及临床有效性是不同证据等级。

## 1 数据描述与读取

| 项目 | 当前范围 | 边界 |
| --- | --- | --- |
| 字段字典 metadata-fields/1 | 35个字段定义，中英文从同一清单生成 | 设计约定，尚未整体迁移至上传表单、存储及运行API |
| 技术信息 | 现有读取器提取通道、采样、时长、单位、结构及部分标注 | 提取范围随格式而异；未提取不等于不存在 |
| 背景字段 | 现有疾病、年龄组、任务等上下文选项 | 尚未实现完整物种、数值年龄/单位/时间依据及状态时段模型；不能把现有人类年龄组选项套用到动物 |
| 文件入口 | EDF、BDF、BrainVision、EEGLAB SET、FIF、SpikeGLX、NWB 2/HDF5 | 必须满足配套文件、标定、时间轴和所选对象条件；不表示支持这些容器内所有对象 |
| NWB | 支持的连续ElectricalSeries及LFP/FilteredEphys对象 | Units不作为连续电压；普通LFP可读不等于已有完整质控路线；NWB-Zarr未接入 |

新的字段目录不是可直接提交的API请求格式。现有任务继续使用其冻结的输入与配置。三个真实来源的字段映射练习保存在仓库examples/metadata及独立验收记录中，不代表新字段导入已经上线。

## 2 模块与路线

| 路线 | 当前检查 | 解释边界 |
| --- | --- | --- |
| [头皮EEG](/standards) | 完整性、频谱、通道候选、满足前提的伪迹方法及事件核对 | 方法前提分别核验；没有统一临床合格线或跨物种有效性保证 |
| [ECoG](/standards/ecog) | M03–M05描述性检查；已有事件可启用M07；可显式启用M06 FieldTrip差分候选 | 不将颅内病理活动自动认定为伪迹；未校准坏触点或总分 |
| [sEEG](/standards/seeg) | 独立路线与参数；M03–M05描述性检查、事件核对及可选FieldTrip差分候选 | 电极杆关系、病理解释和位置适用性尚未完成 |
| [Neuropixels连续电压](/standards/neuropixels) | 单流M03–M05，条件性M07；可选SpikeInterface AP通道候选 | M06、分选后单元质量、漂移、跨流同步未接入；不把所有胞外记录归为Neuropixels |

每次任务使用一个支持的模态/兼容通道组或独立连续流。多个流不自动拼接；共同M01–M09编号不意味着相同算法、参数或验证范围。

## 3 可选研究扩展

| 方法 | 实际执行实现 | 当前验证/输出限制 |
| --- | --- | --- |
| FASTER通道统计 | mne-faster Python实现 | 不是原始MATLAB FASTER的原版接入；未证明两者等价 |
| FieldTrip差分区间 | 上游FieldTrip方法，经Octave兼容环境执行 | 为差分z值候选，不代表接入FieldTrip全部伪迹流程；未证明MATLAB数值等价 |
| SpikeInterface AP坏道 | 上游std/MAD方法，按来源shank分组 | 仅支持的AP条件；未接入LF/IBL完整方法或单元质量 |
| ASR影响评估 | 上游实现，经Octave兼容环境执行 | 必须显式选择校准段；整记录模式拒绝自动分窗重校准 |
| CleanLine影响评估 | 上游实现，经Octave兼容环境执行 | 指标及前后PSD，未证明MATLAB等价 |
| Zapline-plus影响评估 | 上游实现，经Octave兼容环境执行 | 已有处理过强样例，结果保留警示，不能自动认定改善 |

这些扩展均不是默认清洗。处理在临时副本上完成影响评估；尚无完整清洗副本导出、整记录清洗及前后复核工作流。PyPREP RANSAC、local AutoReject和ICLabel仍属计划项。

## 4 报告与证据

报告保留方法、配置、指标、候选、范围、未评原因和独立人工意见。总分尚未校准，score.value保持null，不将执行覆盖率转换为质量分。

截至本次整理，可选扩展已有四种模态公开文件的实际运行记录以及合成/拒绝路径测试。记录见仓库docs/research-adapter-validation-20261031.md和docs/optional-methods-runtime.md。它们证明声明范围内的工程行为，不证明所有物种、疾病或任务的误报、漏报和清洗信号保留性能。

本次字段核对使用真实人类EEG、猴ECoG和小鼠LFP来源，分别保留缺失年龄、实验开始年龄和月龄。小鼠样例使用Neuronexus探针，不能因此获得Neuropixels路线资格。验收说明见仓库docs/metadata-validation-20261031.md。

开发待办保存在仓库TODO.md，不作为本规范的要求或实现证据。后续实现变化应同步修订本页，既有报告保留生成时的版本。
