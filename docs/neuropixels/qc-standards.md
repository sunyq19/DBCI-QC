# Neuropixels连续电压质控技术规范

项目技术规范 · 版本 neuropixels-qc/0.1 · 2026-11-08 · 征求意见稿，待专家审核

## 1 范围与评价对象

本版固定Neuropixels连续电压的检查项目、触发条件和报告要求。适用于已核验的SpikeGLX AP/LF和具有明确Neuropixels设备声明的NWB连续ElectricalSeries。兼容执行配置`neuropixels-voltage/2`，推荐方案版本`neuropixels-basic-recipe/0.1`。本文件是项目规范，不是已发布的行业标准，也未完成检测准确性校准。

| 对象 | 本版处理 | 不得混淆 |
| --- | --- | --- |
| AP连续电压 | 文件、时间、完整性、频谱、通道统计；有条件时增加AP通道离群 | 高频包含神经放电，不能套用EEG肌电规则 |
| LF / LFP连续电压 | 文件、时间、完整性、低频频谱与通道统计 | 不套用AP的300 Hz高通和离群参数 |
| 分选后units / spikes | 尚未接入；另列后续输入和指标要求 | 一个记录通道不等于一个神经元 |

IBL分别提供原始电压RMS/频谱检查与分选结果指标；本版采用这种评价对象分层，不声称已运行完整IBL流程。[IBL原始数据质控接口](https://docs.internationalbrainlab.org/_autosummary/ibllib.ephys.ephysqc.html)

## 2 必需信息

运行前须确认文件格式、连续信号对象、AP/LF/LFP或未知频带、设备型号、原始通道身份、神经道与同步字角色、采样率、标定单位、记录范围和原始时间基准。NWB须固定ElectricalSeries路径及电极表映射。

probe/shank/site用于条件方法；缺shank时仍可运行逐通道描述，但不得自动建立跨杆比较。参考、来源滤波/降采样、物种、年龄及其单位、实验状态应随报告保存；缺失标为未知，不推断脑区或疾病阈值。来源已处理LFP不得称为未处理原始AP。

SpikeGLX文件长度应与保存字数、采样率及记录时长相符，`firstSample`提供原始样本位置。数字同步字不进入电压统计。[SpikeGLX元数据定义](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html)

## 3 默认流程与条件路由

```text
读取文件 → 确认一个连续电压流 → 排除同步字
                         ↓
             完整性、频谱、逐通道统计
                         ↓
          AP且shank/窗口条件满足 → AP通道离群
          LF/LFP或条件不足      → 保留描述量
                         ↓
               有事件表 → 核对事件时间
                         ↓
       报告：检查范围、测量、候选通道、未评原因
```

默认M03–M05；已登记事件表时增加M07。AP离群仅在至少一个实际分析窗满足条件时推荐；用户明确提供的方法列表优先。每个窗在执行时重新核验，短尾段不填正常。M01、M02、M08、M09承担接入、计划、汇总和报告。

长记录按原生采样点分块，保留失败、未执行和来源缺口。全长扫描与方法内部抽样必须区分。当前输入上限仍为单文件2 GiB、数据集10 GiB；上限不是最短实验时长或数据质量阈值。

## 4 结果解释与计分

结构不合法或无法标定：拒绝该信号进入检查。检查完成但发现非有限值、整窗恒值或AP离群：给出复核线索和位置。条件不足、失败或未接入：明确列为未评；不得解释为正常。

本版可输出AP通道离群分：`100 × (1 − 候选通道数 / 实际受检通道数)`。多窗按各窗受检通道数与时长加权汇总，重复候选按通道身份去重。同一方法的std/mad是二选一参数，不叠加计分。

该分仅表示本方法未标记的比例，不能代替完整性、漂移、同步或unit质量。默认报告保留该方法分项，不建立覆盖所有维度的Neuropixels综合分。用户手动纳入项目评分时须同时显示项目范围、实际权重与未评项。LF/LFP不继承AP分数。未评不补100，整窗全零也不能因为“没有NaN”而判为正常。

详细口径见[Neuropixels检查规则](/standards/neuropixels-checks)。

## 5 模块要求

### 5.1 M01 数据接入与结构核验

核对配套文件、声明大小/校验信息、原始帧结构、单位增益和连续流身份。现有SpikeGLX读取器识别探针类型0、21、24；NP1有真实样本，NP2只有合成契约测试。不接受任意裸bin冒充Neuropixels；cbin、NIDQ和NWB-Zarr尚未接入。

[模块详情](/standards/neuropixels/modules/M01)

### 5.2 M02 数据画像与检查计划

冻结一个流、原生采样率、源通道索引、时间范围、方法版本及参数。AP/LF可以来自同一次实验，但不能当作同一时钟或两个独立生物样本。分组、位置和处理史保持来源。

[模块详情](/standards/neuropixels/modules/M02)

### 5.3 M03 基础信号完整性

逐道统计NaN/Inf、精确重复连续段及其最长持续时间；单独列出整分析窗恒值的通道。精确恒值不证明硬件丢包，少量相邻相等不作为坏道。原始样本位置与详细位置保存预算必须可追溯，计数不因明细截断减少。

[模块详情](/standards/neuropixels/modules/M03)

### 5.4 M04 流内频谱观察

Welch PSD采用Hann窗、50%重叠和逐段去均值。AP默认0.1秒，LF/LFP默认1秒；报告实际频率分辨率和来源滤波史。测量50/60 Hz邻域，不把谱峰自动判成电源污染，不将AP高频作为肌电扣分。

[模块详情](/standards/neuropixels/modules/M04)

### 5.5 M05 逐通道统计

逐道输出有限样本数量、均值、标准差、RMS和峰峰值。RMS包含神经活动，不能改名为噪声地板。

AP有来源shank映射、每杆至少8个选中神经道且窗口满足执行限制时，推荐已接入的SpikeInterface原版MAD路径：300 Hz高通、0.3秒抽样块、20块、seed=0、阈值为各杆通道MAD中位数的5倍。仅检测高离散度noise候选；good只代表未超此阈值。参数为项目初版配置，不是行业合格线。IBL coherence+psd、dead/out分类当前未接入。[SpikeInterface方法说明](https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html#detect-bad-channels-interpolate-bad-channels)

[模块详情](/standards/neuropixels/modules/M05)

### 5.6 M06 伪迹方法边界

本版不默认执行去条纹、重参考、漂移校正或spike sorting。它们改变数据或评价对象，后续以独立可选模块接入，不能把修改比例当成质量分。

[模块详情](/standards/neuropixels/modules/M06)

### 5.7 M07 来源事件核对

核对已登记事件表的字段、范围和样本映射。当前未解码同步字错误位、未校准跨流/跨探针时钟；有同步通道不等于已同步。

[模块详情](/standards/neuropixels/modules/M07)

### 5.8 M08 分项评价与汇总

按真实分母合并已完成窗口；区分全长完整性扫描与AP离群方法的固定种子抽样。报告执行覆盖、原始候选、分项与未评范围，不能用相邻量化重复次数代替坏道率。

[模块详情](/standards/neuropixels/modules/M08)

### 5.9 M09 报告与复核

报告统一四层：检查结果、问题定位、图表分析、报告详情。首屏展示流类型、通道数、实际覆盖及主要发现；原始参数与证据在详情中。候选保留来源通道身份与分析窗口，不给仅有通道标签的方法编造事件起止时间。

[模块详情](/standards/neuropixels/modules/M09)

## 6 分选后单元的后续规范

后续接入须有unit ID、spike时间与时钟、原记录引用、分选器及版本、处理配置；波形、振幅和位置字段按具体指标提供。拟评估发放率、时间存在比例、ISI/不应期违例、振幅截断、隔离度及漂移。缺少指标输入就不计算。

这些指标反映不同问题，不能简单平均为一个unit分。Allen明确讨论指标偏差，并不建议单独用峰值通道SNR筛选Neuropixels单元。因此不把SNR设为本项目通用合格线，也不复制某数据库筛选阈值为通用标准。[Allen unit指标说明](https://allensdk.readthedocs.io/en/latest/_static/examples/nb/ecephys_quality_metrics.html)

## 7 验证与版本维护

使用真实AP、真实LF和明确标记的格式/边界样本验证读取、路由、测量及报告。人工确认的技术异常、模拟注入异常和生理事件分别保存，不能互当真值。算法/阈值/抽样/窗口/计分任何变化均需记录版本；历史运行不覆盖。

真实NP1公开样本目前包含Pt03 AP 2秒、Pt02 AP 4秒及Pt01 LF 20秒。它们是来源大文件的已声明片段，完整检查本地片段不代表检查了整场实验，不能验证长期漂移或跨日稳定性。Noise4Sam和已发现全零的NWB片段是边界用例，不作为健康生理基准。来源见本地各样例说明和[Pt03等公开数据](https://zenodo.org/records/5899237)。

共同要求见[总则](/standards/overview)、[字段字典](/standards/fields)、[方法适用规则](/standards/applicability)。本版还需专家审核和独立标注验证，不能以工程运行成功代替准确率验证。
