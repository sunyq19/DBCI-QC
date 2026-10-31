# 数据字段字典

项目技术规范 · 版本 metadata-fields/1 · 2026-10-31 · 设计约定

本字典规定跨物种电生理数据的字段语义。字段可描述的数据范围不等于当前软件可执行范围；新字段尚未整体接入上传表单或运行API。

[总则](/standards/overview) · [方法适用规则](/standards/applicability) · [当前实现](/standards/implementation)

## 1 组织与粒度

字段分为受试对象、信号与文件、通道与采集、实验与状态、处理与来源五组。subject表示对象；session表示一次采集会话；recording表示记录；stream表示独立数据流；channel/electrode/channel_group分别表示通道、接触点和比较组；interval表示时段；analysis表示本次选区。会话级背景不得覆盖逐通道或逐时段的不同事实。

通道数由通道集合生成；年龄组由年龄和已声明物种规则生成。格式、物种、记录位置、信号对象和设备技术是独立字段。新增方法按所需前提扩展，不增加“物种×疾病×格式”的组合标签。

## 2 通用字段值约定

每个字段值应携带value、status、source和confirmation。known表示存在明确声明，不代表科学真值；unknown表示未提供或尚未提取；not_applicable须说明原因；conflict应保留各来源候选值，未解决前不得选择其一驱动方法。unknown/not_applicable/conflict的规范化value为null。

source应记录类型（file_header、sidecar、provider_document、manual、derived）、文件或资料引用和字段位置；派生值另记转换规则及版本。confirmation为unreviewed或confirmed，表示是否经过确认，不把“确认”当作医学或实验真值。空列表只有在已检查相应范围后才表示未发现。

缺项动作按方法解释：block_reading为无法可靠读取；block_registration为无法建立记录身份；block_execution为无法执行所请求选区；restrict_method只限制依赖该字段的方法；restrict_interpretation限制解释；retain_unknown保留未知。它们是目标约定，当前实际限制见实现范围。

qc_use取reader（读取）、routing（对象/路线选择）、technical（方法技术前提）、context（解释与验证分层）或provenance（追溯）。context字段未经独立验证不得自动改变阈值、扣分或清洗。

## 3 年龄与物种

年龄应保留lower/upper边界、day/week/month/year单位、birth/gestational/other/unknown参考起点、recording/session_start/experiment_start/source_unspecified时间语境及source_text。精确值两端相同；单侧未知用null，不得两端均空。区间须非负且lower≤upper。月与年保留原单位，不随意折算为固定天数。

孕期年龄应另记来源的起算定义；不得混淆出生后年龄、孕周和矫正年龄。只有发育阶段时允许仅保存life_stage；未经验证不自动建立跨物种“成年”分界。来源未明确物种时保留未知，即使外部格式存在兼容性默认值，也应将其记录为默认来源而非确认事实。

## 4 受试对象

| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |
| --- | --- | --- | --- | --- |
| `subject.id` · 对象标识 | 去标识的来源对象ID；不能跨数据集仅凭同名合并。 `string` | `subject` | `retain_unknown` | `provenance` |
| `subject.species` · 物种 | 保留来源物种文本；有依据时映射学名及分类标识，不默认人类。 `taxon` | `subject` | `restrict_interpretation` | `context` |
| `subject.age` · 来源年龄 | 数值或区间、单位、年龄起点及所属时间；不把实验开始年龄当本次记录精确年龄。 `age` | `session` | `restrict_interpretation` | `context` |
| `subject.life_stage` · 发育阶段 | 来源声明或按明确物种规则派生；保留规则版本，不反推实际年龄。 `stage` | `session` | `retain_unknown` | `context` |
| `subject.sex` · 生物学性别 | 保留来源定义与原值；不能把未提供解释成某一种性别。 `string` | `subject` | `retain_unknown` | `context` |
| `subject.strain` · 品系与基因型 | 动物品系、基因型分别记录；未知不自动填野生型。 `object` | `subject` | `retain_unknown` | `context` |
| `subject.background` · 疾病或动物模型 | 可有多个有来源的背景；健康对照须有声明，药物处理不自动成为疾病。 `array` | `session` | `restrict_interpretation` | `context` |

## 5 信号与文件

| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |
| --- | --- | --- | --- | --- |
| `recording.id` · 记录标识 | 本次原始或派生记录的稳定ID，区别于受试对象ID。 `string` | `recording` | `block_registration` | `provenance` |
| `recording.files` · 文件与成员 | 主文件、配套成员、格式、校验算法和值；格式不证明模态。 `array` | `recording` | `block_reading` | `reader` |
| `recording.signal_kind` · 信号对象 | continuous_voltage、epoched_voltage、sorted_units、derived_feature或unknown；可描述不代表可执行。 `string` | `stream` | `restrict_method` | `routing` |
| `recording.recording_site` · 记录位置 | scalp、cortical_surface、depth、other或unknown；允许同文件多组。 `string` | `channel_group` | `restrict_method` | `routing` |
| `recording.streams` · 数据流 | 每流稳定ID、源对象路径及通道映射；多流不默认拼接。 `array` | `recording` | `block_reading` | `reader` |
| `recording.sampling_rate_hz` · 采样率 | 原生采样率，Hz；保留头声明和时钟估计的差异，不取均值掩盖冲突。 `positive_number` | `stream` | `restrict_method` | `technical` |
| `recording.sample_count` · 采样点数 | 每流实际样本数，不由四舍五入后的时长反算。 `nonnegative_integer` | `stream` | `block_reading` | `technical` |
| `recording.duration_seconds` · 时长 | 记录存储时长与实验声明时长分开，单位s；不把填充当真实实验时间。 `nonnegative_number` | `stream` | `restrict_method` | `technical` |
| `recording.clock` · 原生时钟 | 源首样本、时间原点、时间戳或采样率及其参照；非零起点保留。 `clock` | `stream` | `restrict_method` | `technical` |
| `recording.continuity` · 连续性 | continuous、epoched、discontinuous或unknown，以及已知连续段/缺口。 `object` | `stream` | `restrict_method` | `technical` |
| `recording.selection` · 本次选区 | 所选流、源通道及样本半开区间；范围改变应生成新计划。 `selection` | `analysis` | `block_execution` | `routing` |

## 6 通道与采集

| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |
| --- | --- | --- | --- | --- |
| `acquisition.channels` · 通道身份与角色 | 稳定ID、源索引、源名称、声明类型、确认角色；重名不合并，数字同步道不作神经电压。 `array` | `channel` | `block_execution` | `technical` |
| `acquisition.calibration` · 单位与标定 | 源单位、转换系数和偏置、物理单位、依据及可信状态；未知单位禁用绝对幅度判据。 `calibration` | `channel` | `restrict_method` | `technical` |
| `acquisition.reference` · 参考与比较组 | 采集参考、当前参考及可比通道组分别保存；ECG/EOG辅助道不等于参考电极。 `object` | `channel_group` | `restrict_method` | `technical` |
| `acquisition.electrodes` · 电极接触点 | 接触点ID、通道到电极的映射、正负极关系；接触点数量不等于通道数量。 `array` | `electrode` | `restrict_method` | `technical` |
| `acquisition.coordinates` · 位置与坐标系 | 坐标值、单位、坐标系及实测/模板来源必须一起记录；未知时禁用依赖位置的操作。 `coordinates` | `electrode` | `restrict_method` | `technical` |
| `acquisition.hardware` · 采集设备 | 厂商、型号、采集技术及证据；Neuropixels是技术/设备，不是物种或文件格式。 `object` | `stream` | `restrict_method` | `routing` |
| `acquisition.probe_layout` · 探针与分组 | probe、shank、site、网格或电极杆关系及来源；不能仅凭名字建立邻接。 `object` | `channel_group` | `restrict_method` | `technical` |
| `acquisition.filters` · 采集滤波与带宽 | 硬件/采集软件的滤波及参数；未知与明确未滤波不同。 `array` | `stream` | `restrict_method` | `technical` |
| `acquisition.line_frequency_hz` · 供电频率 | 明确声明的50/60Hz等供电频率；信号谱峰与供电声明分别保存。 `positive_number` | `session` | `restrict_method` | `technical` |

## 7 实验与状态

| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |
| --- | --- | --- | --- | --- |
| `experiment.task` · 记录任务 | 任务ID、名称和来源；同一session多任务应有时段。 `object` | `session` | `retain_unknown` | `context` |
| `experiment.states` · 记录状态时段 | 清醒、睡眠、麻醉等按带时钟的时段记录；整个session的粗声明也应注明覆盖。 `array` | `interval` | `restrict_interpretation` | `context` |
| `experiment.events` · 事件与标注 | 原始标签、时间/样本、持续时间、时钟及映射；点事件不虚构持续时间。 `array` | `interval` | `restrict_method` | `technical` |
| `experiment.annotation_coverage` · 标注提取状态 | 区分未提取、已查未发现、部分提取及已提取的范围；不以空列表证明无事件。 `object` | `stream` | `restrict_interpretation` | `provenance` |

## 8 处理与来源

| 字段 | 定义与值类型 | 粒度 | 缺项动作 | 用途 |
| --- | --- | --- | --- | --- |
| `processing.derivation` · 原始与派生关系 | 来源是否处理、父记录和关系；不知道处理史不等于原始。 `object` | `recording` | `restrict_interpretation` | `provenance` |
| `processing.history` · 既往处理 | 滤波、重参考、重采样、插值、ICA/ASR等顺序、参数、范围及软件版本。 `array` | `stream` | `restrict_method` | `technical` |
| `processing.source` · 来源与版本 | 来源URL/DOI、固定版本、许可与冲突；原始声明和平台判断分开。 `object` | `recording` | `restrict_interpretation` | `provenance` |
| `processing.revision` · 描述修订 | 字段字典版本、描述版本及父版本；旧任务冻结原描述，不回填新结论。 `object` | `recording` | `block_registration` | `provenance` |

## 9 复合值结构

以下是值的结构摘要；对应字段仍需遵守第2章的来源和状态约定。原始来源文本应保留。

| Type | Structure |
| --- | --- |
| `string` | `string` |
| `object` | `object` |
| `array` | `array` |
| `positive_number` | `finite number > 0` |
| `nonnegative_number` | `finite number >= 0` |
| `nonnegative_integer` | `integer >= 0` |
| `taxon` | `{source_label, scientific_name?, taxonomy_id?}` |
| `age` | `{lower?, upper?, unit, reference, at, source_text}; bound required; lower <= upper; exact when equal` |
| `stage` | `{label, source_declared, rule_id?, rule_version?}; derived stage requires rule and known species` |
| `clock` | `{reference, first_sample?, origin_seconds?, rate_hz?, timestamps_reference?}; per-stream native time` |
| `selection` | `{stream_id, source_indices, start_sample, stop_sample_exclusive}; nonempty interval` |
| `calibration` | `{source_unit, physical_unit, scale, offset, mapping}; physical = stored * scale + offset` |
| `coordinates` | `{values, unit, frame, provenance}; values must reference stable electrode IDs` |

## 10 维护与映射

权威字段清单为仓库specs/metadata-fields.v1.json；本页中英文由scripts/build_metadata_dictionary.py生成。字段ID、定义、单位、粒度或缺项含义改变时应更新字典版本及迁移说明。对当前API的兼容映射须另行实现和测试；不得把本清单直接当成已接受的上传JSON。

BIDS映射按participants、recording JSON、channels、electrodes、coordsystem和events分层；NWB映射按Subject、ElectricalSeries、electrodes、device和时间对象分层。源字段不适配本字典时保留原值、限定解释，不静默丢弃。

[BIDS 1.11.2](https://bids-specification.readthedocs.io/en/v1.11.2/) · [NWB 2.11.0](https://github.com/NeurodataWithoutBorders/nwb-schema/blob/2.11.0/core/nwb.file.yaml)
