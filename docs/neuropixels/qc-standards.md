# Neuropixels电压质量检查技术约定

项目技术规范 · 版本 neuropixels-voltage/2 · 2026-10-31 · 文档修订 2 · 研究用途

共同要求见[总则](/standards/overview)、[字段字典](/standards/fields)与[方法适用规则](/standards/applicability)，实际能力见[实现范围](/standards/implementation)。物种和年龄应保留来源、单位与时间依据，不得将人类年龄分组套用于动物。本次字段要求不改变既有分析配置版本，也不建立新的跨物种阈值。

## 1 范围

适用于读取器已支持的Neuropixels SpikeGLX原始AP/LF电压流，或有明确Neuropixels设备证据的NWB 2/HDF5连续ElectricalSeries。NWB电压可为来源已处理的LFP，应保留处理声明，不统一称为原始AP/LF。内部模态为extracellular，记录系统为Neuropixels；当前不支持sorting/unit输入，不执行分选、漂移校正或神经元质量判断。读取器支持型号0、21、24的明确声明结构；当前真实数据验收覆盖NP1，NP2仅有合成读取契约测试。

## 2 输入

SpikeGLX每次上传一个完整流的.bin与同名.meta，可一起ZIP；NWB上传单个文件，并明确选择一个连续ElectricalSeries。应有可核对的设备证据、采样率、通道映射、标定与时间原点。SpikeGLX模拟神经道和数字同步字必须分开；NWB按电极表行映射和单位转换字段读取。缺失必要标定或设备证据时不猜测模态，Units不得充当连续波形。

## 3 配置

analysis_profile为neuropixels-voltage/2，配置键为method_config.neuropixels。Welch窗长AP默认0.1秒，LF/LFP及其他已确认的Neuropixels电压默认1秒；line_frequencies_hz=[50,60]。记录有效频率分辨率，不将该设置视为通用噪声阈值。

## 4 执行与结果

与其他模态共用上传、确认、计划、运行及报告流程。默认M03–M05；登记事件后可核对M07，M06未接入。每个计划只执行一个流，保留原始采样率，不自动拼流或清洗。score.value保持null。

## 5 模块要求

### 5.1 M01 数据接入与结构核验

SpikeGLX核对二进制长度、采样率、保存通道数、通道映射、量化增益和firstSample，保留同步字身份。NWB核对连续ElectricalSeries、设备证据、电极表映射、单位转换和独立时钟；不把Units表当成连续通道。

不能将任意裸.bin按Neuropixels解码。支持范围以读取器实际识别的探针类型为准；NIDQ、压缩.cbin、NWB-Zarr和其他尚未接入的采集格式不在本版范围。

[模块详情](/standards/neuropixels/modules/M01)

### 5.2 M02 数据画像与检查计划

一次计划选择一个SpikeGLX AP/LF流或NWB连续ElectricalSeries；只对模拟神经通道计算电压指标，保留同步道但排除其参与。NWB多流选择连同对象路径、电极映射与时钟冻结，不能更换流后沿用旧计划。冻结neuropixels-voltage/2参数和来源。

内部modality为extracellular；Neuropixels是记录系统标签。不同AP/LF或NWB连续流不能强行拼接为同一采样时钟，probe/shank/site信息存在也不代表组织位置已经核验。一般NWB电压和普通LFP不因其容器格式自动归入本路线。

[模块详情](/standards/neuropixels/modules/M02)

### 5.3 M03 基础信号完整性

扫描非有限值和相邻精确恒值连续段；定位证据始终使用原始样本。

整数ADC量化会产生精确相等样本，不能把每次相等都视为丢包或坏道。本版不以恒值计数诊断采集故障，也不自动修复数据。

[模块详情](/standards/neuropixels/modules/M03)

### 5.4 M04 流内频谱观察

以Welch生成描述性PSD；Hann窗、50%重叠、逐段去均值。AP默认0.1秒窗，LF/LFP及其他已确认的Neuropixels电压默认1秒窗，记录实际频率分辨率。

短AP窗的分辨率可能不足以分辨邻近谱峰。采集滤波会改变可解释频段；工频观察不是噪声判定，神经放电高频不作为肌电扣分。

[模块详情](/standards/neuropixels/modules/M04)

### 5.5 M05 逐通道统计

计算有限值数量、均值、标准差、RMS及峰峰值；不将数字同步字计算为电压。

RMS包括神经信号，不能直接当噪声地板；可显式启用SpikeInterface AP std/MAD坏道候选，须满足AP及来源shank分组前提；不等于已确认坏道。当前不计算unit SNR、ISI违例或漂移。原始通道与sorting后的unit不是同一实体。

[模块详情](/standards/neuropixels/modules/M05)

### 5.6 M06 伪迹方法边界

本版本未接入，不调用EEG/ECoG伪迹算法替代；不执行去条纹、公共参考或运动校正。

探针漂移需要位置/时间和适当检测方法。完整性统计不能替代漂移估计或spike sorting准确率。

[模块详情](/standards/neuropixels/modules/M06)

### 5.7 M07 来源事件核对

对已登记或明确映射的事件作字段、范围和样本映射核对；NWB事件应转换到被选流的时间原点，不混用同文件其他流的时钟。

本版不从同步字自动提取边沿，不作跨探针或AP/LF时钟校准。同名时间戳或同步道存在不证明设备已对齐。

[模块详情](/standards/neuropixels/modules/M07)

### 5.8 M08 分项评价与汇总

汇总观察量、未评、失败及证据来源；保留每个流独立的执行范围。

不提供spike sorting质量分、unit产量或可用神经元结论。AP和LF是不同数据流，不算两个独立生物样本。

[模块详情](/standards/neuropixels/modules/M08)

### 5.9 M09 报告与复核

生成连续电压检查报告并保留人工复核链路；显示被选流、来源已做处理和未评范围，不将来源处理后的LFP标为未处理原始记录。

报告不代表已经执行分选或unit质控。后续unit报告必须引用分选器版本、配置、原始记录、时间映射和独立指标证据。

[模块详情](/standards/neuropixels/modules/M09)

## 6 分层与验证边界

连续电压层描述模拟电压和采样完整性，区分原始采集流与来源已处理的LFP。未来分选结果层应单独接入unit身份、spike时间、分选器版本与原始记录引用；只有满足指标所需数据后，才能计算发放率、presence ratio、ISI违例、SNR等。方法依赖、时间基准和缺失值须可追溯，不把工具默认阈值写成统一标准。当前仅接入连续电压层；真实样例验收与合成边界测试分别留档，不推断临床或分选准确性。

[SpikeGLX metadata](https://billkarsh.github.io/SpikeGLX/Sgl_help/Metadata_Help.html) · [SpikeInterface recording and sorting](https://spikeinterface.readthedocs.io/en/latest/modules/core.html) · [Neuropixels analysis example](https://spikeinterface.readthedocs.io/en/stable/how_to/analyze_neuropixels.html)

## 7 样例范围

本次接入的验收数据分开记录用途，不将格式测试文件当作神经活动质量真值。

| 样例 | 数据范围 | 验证用途 | 状态 |
| --- | --- | --- | --- |
| 人脑Pt03 AP | 来源记录60–62秒，保留原始二进制帧；配套头按派生片段登记 | 真实生物信号的读取、源时间和基本模块运行 | 独立读取核对通过；执行状态见版本验收 |
| Noise4Sam LF | 5.2652秒的公开格式测试片段 | LF标定、流身份和基础执行 | 独立读取核对通过；不当作生理基准 |
| 人脑AP短选区 | 从已核验Pt03片段内选择0.02秒 | 极短窗与频率分辨率不足时的partial报告 | 边界用例，不增加独立观测数 |
| ACSF AP | 公开测试文件，声明SHA1与实际二进制不符 | 来源不一致的拒绝行为 | 负例，不登记、不进入质控 |
| 截短Noise4Sam AP | 公开截短文件，原声明长度与哈希不匹配 | 配套信息不一致的拒绝行为 | 负例，不登记、不进入质控 |

Pt03只下载了声明字节范围，不能声称已核验完整原始大文件的MD5；应保留源URL、字节区间、原始头、派生头改动和片段哈希。样例实际覆盖与执行状态以版本验收记录为准。

[Pt03公开来源](https://zenodo.org/records/5899237) · [Neo公开格式测试库](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data)

### 7.1 NWB扩展（1.0.0rc3.dev4）

现行配置为`neuropixels-voltage/2`；旧`neuropixels-raw/1`任务按原冻结版本解释，不重写其结果。NWB来源的Allen probeD LFP保留了逐点时钟和设备扩展声明，分散窗口抽查为零，是异常信号边界例，不是正常生理基准。其电极组采样率属性与时间戳冲突应如实披露。其他真实ECoG或普通LFP样例不归入Neuropixels。当前样例来源、派生信息及核对口径见[NWB样例](../nwb-testing.md)；实际执行状态仍以版本验收为准。
