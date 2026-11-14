# 公开方法扩展接口 v1

版本：2026-11-14。性质：项目实现约定，未经专家审定，不构成通用质量标准。

## 1. 模块位置与输出

| 方法 | 所属模块 | 适用数据 | 计分 | 用户得到的结果 |
| --- | --- | --- | --- | --- |
| PyPREP RANSAC | M05 通道质量 | 完整且唯一的头坐标；头皮 EEG，16–256道、≥30秒、≥100Hz；共同或连接耳参考 | 可选，默认权重0 | 空间预测候选、逐道相关及异常窗占比 |
| local AutoReject | M03 信号完整性 | 完整且唯一的头坐标；头皮 EEG，8–256道；≥20个完整固定段，且分段数≥4×交叉验证折数；默认每段2秒；非双极/混合参考 | 可选，默认权重0 | 通道×片段标签、逐道峰峰值阈值、整段建议 |
| MNE ICLabel | M06 生理伪迹 | 完整且唯一的头坐标；头皮 EEG，8–256道、≥60秒、采样率>200Hz；非双极/混合参考；已知低通<100Hz时不运行 | 仅测量 | ICA 七类概率、分解参数；不自动移除成分 |
| SpikeInterface DREDge LF | M05 通道质量 | Neuropixels LF/LFP；来源探针几何、shank；每杆≥16道及8个深度；≥10秒、>250Hz | 仅测量 | 每杆相对位移曲线，单位µm |
| NWB Inspector | M01 文件读取 | 已登记的 NWB 2 文件；不依赖信号模态 | 规范校验 | NWB 结构错误和最佳实践建议 |
| BIDS Validator | D01 数据集完整性 | 根目录有 dataset_description.json 且声明 BIDSVersion 的本地数据集 | 规范校验 | 目录、侧车表和元数据错误/建议及位置 |

前五项通过质控台对应模块查看；前三项及DREDge、NWB校验均需主动选择。BIDS在D01识别到声明的BIDS数据集后运行，不对普通文件夹强行套用BIDS。

## 2. 计分约定

- RANSAC：100 × (1 − 空间预测候选通道数 / 实际完成空间预测的通道数)。NaN/平线导致未参与预测的通道不计为通过；另列未评名单；存在未评通道时，本项不计入综合分。
- local AutoReject：100 × (1 − 超阈值通道片段数 / 实际完成检查的通道片段数)。原版标签1与2均为超阈值，每个通道片段只算一次；不完整尾段不计入分母。
- 两项均为可选计分，默认权重0。受限、失败或无有效分母时，不输出数值，不以100分补齐；综合分按已有有效权重归一化。
- 这两项与PREP、幅度检查可能提供重叠证据；不自动加入默认方案，也不宣称加权平均代表异常区间并集。用户须按研究方案决定选项和权重。
- ICLabel的类别概率、DREDge的位移、NWB/BIDS的问题数量没有统一的质量换算依据，不能设置为信号质量评分项。

## 3. 输入输出接口

信号方法沿用 `run_extension(id, data_volts, sfreq, channel_names, start_seconds, parameters, facts=...)`。

输入必须是已标定为V的通道×采样数组；原生采样率；唯一通道名与源索引映射；原记录起点。`facts`携带模态、参考、处理史及坐标：

- EEG：`electrode_positions_m`、`electrode_coordinate_frame=head`，只接收文件内坐标。头坐标来自MNE读取器的文件解析，不按通道名补10–20模板，也不保证它是个体实测坐标。
- Neuropixels：`probe_positions_um`、`probe_shanks`、`stream_band=LF/LFP`。

输出使用 `ephys-extension-result/1.0`：方法/依赖版本、参数、实际范围、候选及定位类型、测量、处理记录、计分输出。通道候选只表示该分析块中的通道整体，不能伪造时间区间；AutoReject片段使用原记录时钟。

NWB校验单独接收本次登记文件路径。BIDS校验单独接收已准入的数据集根目录。两者不使用信号数组接口，也不收客户端任意服务器路径。

## 4. 运行边界

- PyPREP使用原版NaN/平线、偏差、相关/掉线准备，再调用RANSAC。准备项不在RANSAC分数重复计入。
- AutoReject使用原版`fit/get_reject_log`；固定连续分段不是任务试次。训练与检查在同一记录，不能据此声称跨记录泛化性能。
- ICLabel在副本上平均参考、1–100Hz滤波、extended-infomax分解（最多20成分）。已知低通<100Hz阻断；未知处理史在输出中明确保留。没有EOG/ECG也能分类，但不能据概率确认生理来源。
- DREDge调用SpikeInterface原版`dredge_lfp`，副本0.5–100Hz、重采样250Hz、同深度平均、每杆刚性配准。未自动补偿未知采样相位。每个分析块单独零点，不能拼接成跨块绝对运动；AP漂移需峰检测/定位，不纳入本版。
- 所有方法只读原数据。整份检查仍按平台分块策略执行；每块独立拟合并保存范围。
- BIDS调用固定版本的离线内置规则，禁止联网、源目录写入和子进程；完整扫描TSV，不只查文件名。公开数据的下载子集可能缺原数据集文件，报告必须保留此类问题。
- NWB Inspector包含PyNWB结构检查与最佳实践建议。执行失败与规范问题分开记录；不会因存在建议阻断其他信号检查。

## 5. 来源

- [PyPREP](https://pyprep.readthedocs.io/en/stable/generated/pyprep.NoisyChannels.html)，MIT。
- [AutoReject](https://autoreject.github.io/stable/auto_examples/plot_auto_repair.html)，BSD-3-Clause。
- [MNE-ICALabel](https://mne.tools/mne-icalabel/stable/generated/examples/00_iclabel.html)，BSD-3-Clause。
- [SpikeInterface / DREDge LF](https://spikeinterface.readthedocs.io/en/latest/how_to/drift_with_lfp.html)，MIT。
- [NWB Inspector](https://nwb.org/tools/core/nwbinspector/)，BSD-3-Clause。
- [BIDS Validator](https://bids-validator.readthedocs.io/en/latest/)，MIT。
