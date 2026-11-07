# ECoG基础质量检查技术约定

项目技术规范 · 版本 ecog-basic/1 · 2026-10-31 · 文档修订 3 · 研究用途

共同要求见[总则](/standards/overview)、[字段字典](/standards/fields)与[方法适用规则](/standards/applicability)，实际能力见[实现范围](/standards/implementation)。物种和年龄应保留来源、单位与时间依据，不得将人类年龄分组套用于动物。本次字段要求不改变既有分析配置版本，也不建立新的跨物种阈值。

## 1 范围

本约定适用于明确确认为皮层表面脑电的连续电压数据。当前实现提供基础描述与可追溯报告，不定义临床坏触点阈值，不适用于sEEG或胞外放电单元。

## 2 输入

应确认模态、分析源通道、电压单位、原生采样率和时间范围。参考、滤波史和位置不明时应保留未知。BrainVision普通电压的默认EEG类型不能代替模态证据；FIF明确声明的其他类型不得强行按ECoG运行。

## 3 配置

采用独立的`method_config.ecog`：`psd_window_seconds=4`、`line_frequencies_hz=[50,60]`。频谱使用Hann窗、50%重叠与逐段去均值；短窗须记录实际有效窗长。窄带半宽为max(1 Hz,频率分辨率)，仅描述可测频段，不作阈值判定。这些是项目计算约定，不是行业质量标准。


### 基础推荐方案 v0.1（2026-11-07）

读取并确认模态、触点、单位与参考 → 数值完整性与持续平线 → PSD、工频邻域及触点统计 → 汇总报告。有经过核实并登记的事件表时加入 M07。

M03 默认建议启用原版 MNE `annotate_amplitude`：`flat=0 V`、`peak=None`、`min_duration=0.05 s`、`bad_percent=5`。50 ms 参考 MNE-BIDS `inspect_dataset` 的平线检视设置；5% 仅用于 MNE 将结果分流为通道候选或时间标记，不是临床坏道判定线。参数可修改，实际配置随每次运行保存。

持续平线在每个分析窗口内计算。返回通道候选时不伪造精确异常起止；返回合并时间标记时不推测具体触点。跨分段边界的短片段可能不能合并检出；不能把空候选解释为全部质量合格。

默认不启用综合分。MNE 的通道候选占比和合并区间占比提供可选计分输出，默认权重为 0；不能将两者相加解释为污染时长。PSD、工频邻域功率及 RMS 是描述量，不直接转成坏道分数。

报告包含检查范围、五项检查结果、候选位置、逐触点统计、分段图表与运行依据。RMS 按有限样本数合并；汇总峰峰值是各分析窗峰峰值的最大值，并非整段全局峰峰值。

依据：[MNE annotate_amplitude](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html)、[MNE-BIDS inspect_dataset](https://mne.tools/mne-bids/stable/generated/mne_bids.inspect_dataset.html)。本方案是可运行的项目初稿，尚未经过专家审核或坏道真值验证。

## 4 执行与结果

默认执行M03、M04、M05；登记事件时加入M07。M01、M02、M08、M09为必要步骤，M06可显式选择FieldTrip差分区间线索，默认不启用。短窗最多120秒，整份检查保留逐窗覆盖和短尾窗。原数据不清洗、不删除、不重参考。非空头皮专属参数应被拒绝，不静默改写。默认总分为 null；显式选定有效计分项和权重后可生成项目自定义分。

## 5 模块要求

### 5.1 M01 数据接入与结构核验

复用已注册读取器，冻结来源指纹、原生采样流及连续段。 BrainVision的默认EEG类型不证明头皮位置；ECoG须按来源或用户确认。

[模块详情](/standards/ecog/modules/M01)

### 5.2 M02 数据画像与检查计划

沿用原生采样时钟读取分析副本，保留每个源通道身份；不自动重参考。 分析通道字段沿用eeg_indices接口名；本路线语义为ECoG分析触点。

[模块详情](/standards/ecog/modules/M02)

### 5.3 M03 基础信号完整性

定位非有限值，以及至少两个相邻样本完全相等的连续段。 精确恒值仅是技术描述，不使用头皮幅度或坏段时长阈值，不自动删段。

每窗详细候选位置最多10,000条；扫描及逐触点计数仍覆盖所有样本。截断时须保留总数、省略数并标记partial；未存位置不代表正常。

[模块详情](/standards/ecog/modules/M03)

### 5.4 M04 频谱与工频观察

使用SciPy Welch计算PSD；在配置频率附近记录窄带功率和峰值位置。 不调用FOOOF、α评分、Thomson判定或肌电阈值；谱峰不能证明干扰来源。

[模块详情](/standards/ecog/modules/M04)

### 5.5 M05 逐触点统计

逐触点计算有限值数量、均值、标准差、RMS和峰峰值。 不运行PREP、LOF或电极桥接；不根据幅度、触点名称或相邻编号判坏。

[模块详情](/standards/ecog/modules/M05)

### 5.6 M06 伪迹方法边界

仅显式选择fieldtrip_zvalue后执行差分z值区间检测。病理活动也可能触发，候选须复核；不迁移头皮生理伪迹阈值，不自动剔除。

[模块详情](/standards/ecog/modules/M06)

### 5.7 M07 来源事件核对

复用事件时间核对，映射至原记录时间与当前选区。 点事件保留点事件；未验证的起止标签不自动拼接为临床区间。发作不是伪迹真值。

[模块详情](/standards/ecog/modules/M07)

### 5.8 M08 分项评价与汇总

汇总运行覆盖、已评观察量、失败及未评原因。 完成率不是质量分；不同参考、窗口和处理史下的统计不直接比较。

[模块详情](/standards/ecog/modules/M08)

### 5.9 M09 报告与复核

生成HTML与JSON证据；工作台另存人工复核决定。 自动证据不被人工意见覆盖；报告不是临床诊断结论。

[模块详情](/standards/ecog/modules/M09)

## 6 验证与数据

公开样例采用MNE epilepsy_ecog的OpenNeuro ds003029来源记录。原BrainVision与派生FIF是同一观测，不能计作两个独立受试者。原记录98道中仅89道由BIDS声明为ECoG；9道MISC不推断为辅助生理导联。来源标坏信息不输入检测器。读取一致性、实际执行和科学准确性分别验证。头标nV与侧车未提供单位的差异须保留，数值读取一致不代表源物理标定已经独立验证。

[OpenNeuro ds003029](https://openneuro.org/datasets/ds003029) · [MNE epilepsy_ecog](https://mne.tools/stable/generated/mne.datasets.epilepsy_ecog.data_path.html)
