# 常用质控方法补充调研

核对日期：2026-10-31。范围：头皮EEG、ECoG、sEEG和Neuropixels。本文是方法选型记录，不是质量判定标准。

> 后续状态：同日开发版本`1.0.0rc3.dev7`已为这六项增加有限范围的执行适配，见[运行规范](optional-methods-runtime.md)和[工程验收](research-adapter-validation-20261031.md)。下文保留首次调研时的“待接入”历史状态，不代表当前状态。

## 1. 本次变更

新增6个方法条目，全部标记为**待接入**：FASTER坏道、ASR、CleanLine、Zapline-plus、FieldTrip分段伪迹、SpikeInterface/IBL坏道。详情包括原理、输入输出、适用范围、限制、实际拟调用接口、许可及维护快照。

本次没有安装新算法、修改信号、调整阈值或新增可执行模块。目录可浏览不代表可以运行。新增条目不会被推荐为可执行方法，也不生成启用开关。现有方法和历史报告保留。

“常用”的依据是成熟工具生态的官方教程、默认插件、官方插件目录或既有方法论文；没有做论文引用量或用户数排名。尤其要区分FASTER方法族的应用历史与MNE-FASTER这个Python实现的使用规模。

## 2. 新增方法与所属模块

| 方法 | 工具箱位置 | 能补什么 | 生态依据与来源 | 接入条件和限制 |
|---|---|---|---|---|
| **FASTER坏道** | EEG → M05 通道质量 | 将方差、相关性、Hurst指数、峰度和可测工频特征的异常分别列出，便于与PREP、LOF比较 | FASTER是[EEGLAB官方扩展](https://eeglab.org/others/EEGLAB_Extensions.html)；拟选[独立MNE-FASTER实现](https://github.com/wmvanvliet/mne-faster/blob/main/mne_faster/faster.py) | 接口输入是Epochs，需明确分段。先接坏道步骤，不整体照搬删段、ICA和插值。上游使用MNE内部接口，须验证版本兼容；工频特征必须处于可测带宽。 |
| **ASR** | EEG → M06 伪迹线索 | 对偏离校准统计分布的突发成分提供候选和重建影响说明 | [clean_rawdata是EEGLAB默认插件](https://eeglab.org/tutorials/06_RejectArtifacts/cleanrawdata.html) | ASR原生执行重建或剔除，不是只读评分器。接入时需保存校准段、处理参数和原始/处理副本差异；不得把修改比例当质量分。[ASR文件含单独UC使用条款](https://github.com/sccn/clean_rawdata/blob/master/asr_calibrate.m)，需逐文件核对。 |
| **CleanLine** | EEG → M04 频谱与干扰 | 窄带正弦拟合、工频残留及处理前后比较 | [EEGLAB官方插件及教程](https://eeglab.org/plugins/cleanline/) | 多窗谱/F统计量与回归去噪；与当前Thomson检测有关，但当前实现没有调用CleanLine。必须保留副本，不能仅以“去掉峰”判合格。 |
| **Zapline-plus** | EEG → M04 频谱与干扰 | 分段适应变化的窄带干扰，记录噪声频率和移除成分 | [EEGLAB插件说明](https://eeglab.org/plugins/zapline-plus/)及[作者仓库](https://github.com/MariusKlug/zapline-plus) | 属于清洗评估；需足够多通道、稳定片段并检查邻近频带损失。不是对所有数据优于CleanLine的结论，也不与CleanLine默认串联。 |
| **FieldTrip z-value** | EEG / ECoG / sEEG → M06 伪迹线索 | 将指定特征的异常映射为原始起止样本 | [官方分段伪迹教程](https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/)；[FieldTrip支持EEG与iEEG](https://github.com/fieldtrip/fieldtrip) | 每个模态分别核实频带、参考、比较组、阈值和padding。EEG/iEEG适用性是拟验证路线，不是上游MEG示例的直接验证；不能将110–140Hz示例参数照搬到颅内。检测结果先用于复核，不调用剔除步骤。 |
| **SpikeInterface / IBL坏道** | Neuropixels → M05 通道质量 | 增加std/MAD或coherence+PSD坏道路线，区分噪声、掉线及脑外候选 | [官方预处理文档](https://spikeinterface.readthedocs.io/en/stable/modules/preprocessing.html)及[实际实现](https://github.com/SpikeInterface/spikeinterface/blob/main/src/spikeinterface/preprocessing/detect_bad_channels.py) | 优先AP流；需要物理单位、几何和通道顺序，coherence+PSD须按probe/shank分别运行。`dead/out`并非所有路线都输出；`out`不是解剖真值。AP高频默认值不能照搬到LF。 |

同一FieldTrip方法在三个模态目录各有一个计划条目，因此是**6个独立方法、8个模态目录条目**。头皮EEG目录由24项变为29项：21项已有实现，8项待接入；已有实现不等于独立准确率验证。

## 3. 已有目录中应优先完成的部分

不重复新建已有条目：

| 已登记方法 | 当前状态 | 主要价值与缺口 |
|---|---|---|
| PyPREP RANSAC | 待接入 | 空间预测一致性与现有非空间PREP互补；需要可信电极坐标、足够通道和可比参考。见[官方接口](https://pyprep.readthedocs.io/en/stable/generated/pyprep.NoisyChannels.html)。 |
| local AutoReject | 待接入 | 输出局部坏道/坏试次建议；不能与已运行的单个全局阈值混同。拟合需要明确分段、足够数据和有效位置。见[官方接口](https://autoreject.github.io/stable/generated/autoreject.AutoReject.html)。 |
| ICA / ICLabel | 待接入 | 成分来源分类，需先有可信ICA。坐标、秩、参考和滤波条件须核验，类别概率不是质量分。见[官方训练条件说明](https://mne.tools/mne-icalabel/stable/generated/api/mne_icalabel.iclabel.iclabel_label_components.html)。 |
| MNE幅度/平线、肌电、桥接、LOF、全局AutoReject | 已接入的可选扩展 | 本次保持不变；已有运行与限制见[来源核对](toolkit-sources.md)，不另建同名重复方法。 |

## 4. Neuropixels单元质量另设后续分支

[SpikeInterface的Neuropixels教程](https://github.com/SpikeInterface/spikeinterface/blob/main/examples/how_to/analyze_neuropixels.py)包括发放率、presence ratio、SNR、ISI violations和amplitude cutoff等单元指标；[Bombcell](https://github.com/Julie-Fabre/bombcell)提供已分选单元的自动质控与分类。

它们应挂在后续“分选结果 → 单元质量”分支，输入包括排序后的spike times、unit IDs及相应模板/波形/采样信息。不同指标所需证据不同，不能仅凭连续电压或一个NWB Units表的存在宣称已算出全部质量指标。

因此本次不把单元质量塞进当前电压流程的M05，也不把缺少分选结果解释为质量失败。Bombcell仓库核对时未归档、最近推送2026-10-19，标识GPL-3.0；这些是来源快照，非本地运行证据。

## 5. 接入顺序及验收数据

1. **FASTER坏道、PyPREP RANSAC、SpikeInterface坏道**：分别补统计、空间和探针三个现有缺口。RANSAC优先级受可信坐标是否齐全约束。
2. **local AutoReject、ICLabel、FieldTrip分段伪迹**：补试次、成分和可配置时间候选。先做逐方法验证，不能默认串成一条完整清洗链。
3. **ASR、CleanLine、Zapline-plus**：作为清洗效果评估分支，保存处理副本及前后对照，不改变质控输入本体。

上述顺序是基于本项目缺口和接口成本的工程判断，不是算法优劣排名。

| 路线 | 已有样例能支持的检查 | 启用前还需要的验收 |
|---|---|---|
| EEG统计坏道 | 多通道公开EEG用于读入、分段和通道回写；已有来源标签可作对照 | 已有负结果不得抹除；至少区分干净、污染、病理活动，检查低采样率时不可测特征的拒绝行为。 |
| RANSAC / local AutoReject / ICLabel | 已有多通道记录可做候选输入盘点 | 可信坐标、足够且可比较的数据、参考/滤波/秩记录；有坐标不等于准确率已验证。 |
| FieldTrip颅内 | HUP060/HUP064等来源明确的sEEG/ECoG可检查时间映射 | 人工伪迹区间与临床事件分开；同杆/同网格比较组有来源；须证明不将发作或HFO整体判坏。 |
| SpikeInterface坏道 | 已有NP1 AP/LF片段能检查单位和通道顺序 | AP与LF分开验证；需要几何/shank映射、较长覆盖及独立坏道证据；4秒AP片段不足以证明全记录稳定性。 |
| 清洗评估 | 现有原始记录可用于前后读回和溯源 | 独立干净信号、可控注入干扰及真实污染对照；量化目标干扰降低和非目标信号失真，两者都要报告。 |

## 6. 许可与维护快照

以下为2026-10-31通过公开仓库元数据、官方文档和指定源文件核对的记录。`pushed_at`是仓库最近推送，不是最后算法修改日期，也不直接证明维护质量。

| 实现 | 仓库最近推送 | 许可/状态 |
|---|---|---|
| MNE-FASTER | 2025-02-12 | BSD-3-Clause，未归档；最新列出版本1.2.2，须检查MNE内部接口兼容。 |
| clean_rawdata | 2026-09-07 | 仓库GPL-3.0；`asr_calibrate.m`有UC教育、研究和非营利用途条款及商业联系说明，不能忽略文件级差异。 |
| CleanLine | 2025-02-07 | 仓库自动许可检测为NOASSERTION，但`cleanline.m`声明GPL-3.0-or-later；BCILAB/Chronux等捆绑依赖另核。 |
| Zapline-plus | 2023-04-14 | GPL-3.0，未归档；NoiseTools依赖另核，长期少更新需冻结版本回归。 |
| FieldTrip | 2026-10-22 | GPL-3.0，未归档；MATLAB运行环境及函数依赖另核。 |
| SpikeInterface | 2026-10-30 | MIT，未归档；拟只使用坏道预处理接口，保持unit接口边界。 |

本次只登记链接和本项目编写的方法说明，没有分发第三方实现；正式集成时仍需冻结实际版本、参数与许可证文件。常用方法也不能直接产生统一的0–100分或跨疾病通行阈值。

## 7. 本轮登记验证

- 44项目录、来源、分类、推荐与候选保护测试，以及24项ECoG/sEEG/Neuropixels既有路由测试通过。
- 138项前端状态检查、29项中英文检查通过；新说明的完整翻译另由候选登记测试核对。
- 本机8769服务已返回新目录：EEG为29项；ECoG、sEEG、Neuropixels各13项。8个新增模态条目全部为`planned`，`supported_modalities=[]`，没有可执行扩展开关。
- 比较加入候选前后的推荐模块集合和计算配置，四条路线均不变；全选模块或伪造扩展ID不能启用候选方法。

这些是目录和路由验证，不是新增算法的数据验收；本轮未执行6项新增算法，也未做浏览器视觉复核。
