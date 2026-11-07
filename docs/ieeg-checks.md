# ECoG与sEEG基础检查规则

项目技术约定 · ieeg-basic-recipe/0.2 · 2026-11-07 · 待专家审核

## 1 范围与流程

适用于已确认的ECoG或sEEG连续电压。检测技术异常候选，不判断癫痫活动是否应被删除。ECoG和sEEG共用以下步骤，比较组须按具体采集资料确认。

读取与确认 → 完整性、平线与量程 → 频谱、触点及跳变 → 汇总与人工复核。

## 2 模块与启用条件

| 模块 | 检查内容 | 启用条件 | 输出与依据 |
| --- | --- | --- | --- |
| M01 读取 | 格式、单位、标定、原生时钟 | 已接入读取器 | 技术头与源文件核验；格式规范 |
| M02 确认 | 模态、选道、参考、分析范围 | 用户确认分析触点 | 冻结配置；参考BIDS字段语义 |
| M03 完整性 | NaN/Inf、重复值 | 连续电压 | 逐道计数和原始位置 |
| M03 持续平线 | 连续相邻差值为零 | 有限电压及足够长度 | 原版MNE；默认50 ms、5%分流 |
| M03 量程端点 | 连续位于文件编码上下限 | EDF/BDF且实际读取有逐道标定 | 项目端点平台规则；不推测硬件ADC |
| M04 频谱 | Welch PSD、50/60 Hz邻域功率 | 采样率支持该频率 | 原版SciPy；描述量，不直接计分 |
| M05 触点统计 | RMS、峰峰值、非有限值 | 连续电压 | 按源触点输出测量 |
| M05 分组离群 | 组内幅度偏离 | 逐道比较组，组内参考可比较 | 项目规则，SciPy MAD；可选 |
| M06 跳变 | 相邻差分的z值 | 原版FieldTrip已配置、窗口≥10秒 | 合并时间候选；可选增强，默认不启用 |
| M07 事件 | 时间范围及来源映射 | 已登记支持的事件表 | 不将发作标签用作伪迹真值 |
| M08/M09 汇总 | 覆盖、候选、未评、方法版本 | 已保存的模块输出 | 同一报告呈现结果与复核位置 |

未选择的可选方法不显示为质量失败。已选择但缺条件的方法保留具体原因；其余有效结果仍输出。

## 3 可复算的项目规则

### 3.1 持续平线

调用MNE `annotate_amplitude`，默认 `flat=0`、`peak=None`、`min_duration=0.05`、`bad_percent=5`。50 ms参考MNE-BIDS检视设置。MNE可能返回通道候选，也可能返回跨通道合并的时间标注；报告须保留原定位粒度，不能为合并标注虚构单道位置。

### 3.2 文件量程端点平台

方法标识 `ieeg_range_plateau`。以实际读取的物理最小/最大值及量化步长为依据。与端点相差不超过四分之一个量化步长，且连续至少3点，列为候选。采样点数、单位、实际范围和起止时间一并保存。

3点为项目默认值，不是行业阈值。EDF编码量程可能是在导出时设定的；平台命中不等于已确认硬件饱和。没有端点资料的FIF/NWB不使用样本极值代替。

### 3.3 分组触点幅度离群

方法标识 `ieeg_group_outliers`，默认关闭。`comparison_groups`必须覆盖所选触点，可按稳定源ID映射。组应依据网格、条带、电极杆、参考及研究目的确定；不能仅由通道名前缀自动认定。

在质控台的高级设置中选择“分组触点幅度离群”，展开“触点比较组”逐道填写组名，并确认组内参考与采集条件可比较。修改分组后须重新确认；不清楚时保持未确认，只输出测量。

每个通道先减去自身中位数，再计算RMS，取 `a=log10(RMS)`。组内偏离值为 `(a−median(a))/MAD_normal(a)`，其中MAD使用SciPy原函数的normal尺度。默认 `abs(z)>4` 列为候选，至少4道。

组内参考未确认时只保留测量；通道不足、非有限/恒值信号或MAD近零时不判定该组，不把未评计为正常。4道及z=4均为项目试行参数，尚未按颅内坏道真值校准。灰白质差异、发作活动等可触发候选；不自动删道。这不是IEEG_Pipelines或ABCD的实现。

### 3.4 相邻跳变

方法标识 `fieldtrip_zvalue`。调用原版 `ft_artifact_zvalue`：`absdiff=yes`、`cumulative=no`、不加带通或padding，默认z阈值4。保留最大单道z值对应的合并时间区间；不反推出具体通道。

z=4及当前10秒窗口门槛为本适配器设置，不是FieldTrip颅内统一标准。原版检测没有把癫痫尖波与设备跳变可靠分开；报告命名为“跳变线索”。默认不启用。外部运行环境未安装时不可执行，目录中保留可选方法与安装说明。

## 4 报告与计分

报告显示范围、分项结果、候选位置、逐道测量、图表、方法参数和版本。跨窗候选保留各窗边界，不默认为整条通道持续异常。默认不提供颅内综合分。

可选评分接口统一为 `100 × (1−候选量/实际已评量)`，默认权重0：

| 输出 | 候选量 | 有效分母 |
| --- | --- | --- |
| MNE平线通道 | 原版返回的候选通道 | 原版实际受检通道 |
| MNE平线时间 | 合并时间标注时长 | 实际受检时长 |
| 量程端点平台 | 满足连续长度的端点样本 | 量程已核验的有限样本 |
| 分组离群 | 有效组中的候选触点 | 有效组中的受检触点 |
| FieldTrip跳变 | 合并候选时长 | z值有效的受检时长 |

不同分母不是同一种污染率，不相加解释为污染总时长。无有效分母时输出未评，权重按现有评分规则置0。PSD和RMS等描述量不直接计分。

## 5 公共数据库字段与验证要求

BIDS的`channels.tsv`可记录类型、单位、参考、状态及状态说明；`electrodes.tsv`可记录位置和分组。它们规范数据表达，不提供通用坏道阈值。库方bad标签应与检测候选分别保存，不能先删掉这些通道再声称检出准确。

本地MNE示例及OpenNeuro ds004100的发作记录可用于读取、时钟和运行验证。现有部分样本的参考标为`n/a`，没有明确group；不得为启用分组阈值而声称已核实。发作标注不是噪声标签。

进入正式标准前，应冻结本规则版本，用独立专家标注的通道和区间分别评价漏检、误报；按参考、处理史及发作/非发作分层。仅跑通公共记录或模拟噪声不能证明临床准确率。

## 6 来源

- [MNE annotate_amplitude](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html)
- [MNE-BIDS inspect_dataset](https://mne.tools/mne-bids/stable/generated/mne_bids.inspect_dataset.html)
- [EDF文件规范](https://www.edfplus.info/specs/edf.html)
- [FieldTrip自动伪迹检测](https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/)
- [SciPy MAD定义](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.median_abs_deviation.html)
- [BIDS颅内电生理规范](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/intracranial-electroencephalography.html)
- [OpenNeuro ds004100 v1.1.3](https://openneuro.org/datasets/ds004100/versions/1.1.3)

返回：[ECoG方案](/standards/ecog) · [sEEG方案](/standards/seeg)
