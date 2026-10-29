# 工具箱方法来源核对记录

核对日期：2026-10-29。本文件记录来源和实现边界，不新增算法、不改变方法适用性或参数。逐项中文说明位于 `src/ephys_qc/method_descriptions.py`，由 `enrich_method(row)` 添加为 `documentation`，保留原方法是否可运行、是否可选等字段。未知方法会明确报错，要求补做来源核对。

这24项包括16个基础流程分项、5个已接入的可选开源扩展、3个计划方法。已接入不等于完成独立准确率或临床验证；临床事件、任务事件和睡眠阶段均不作为伪迹真值输入检测器。

## 实际依赖证据

核对了工作区 `work/brainelecqc_review_20261027/venv/lib/python3.11/site-packages/brainelecqc/` 中的安装源码、平台运行调用点和适配器，并以GitHub连接器核对公开固定提交中的非空间坏道实现。BrainElecQC的版本号本身不能替代文件或提交身份：

- 本地BrainElecQC 0.1.0 wheel SHA256：`f40e94c5a4dcff45ccb94078a2333d0c17d5f76e429b3fc2ec04cbfc93d13925`。
- 公开来源固定提交：[`f007d829712d1b824cda79409d181a3313d6a78f`](https://github.com/Jlei61/BrainElecQC/tree/f007d829712d1b824cda79409d181a3313d6a78f)。该链接提供可追溯代码位置；没有据此声称所有方法的统计正确性或许可状态已确认。
- 核对时安装版本：MNE 1.13.2、SciPy 1.17.1、FOOOF 1.1.1、PyPREP 0.5.0、autoreject 0.5.1。mne-icalabel未安装。
- 在线stable文档可能变化。尤其PyPREP文档核对时是0.10.0，不能把其新增API直接当作本地0.5.0能力。实际运行参数与包版本应随结果保存。

## 算法与封装分界

| 分项 | 实际来源与调用 | 关键边界 |
| --- | --- | --- |
| EDF结构、标定 | BrainElecQC `EdfBdfReader` / `inspect_input_header` | 平台当前只适配连续EDF/EDF+；可解析不等于信号合格 |
| 连续性 | BrainElecQC `compute_continuity_qc` 自有实现 | 扫描精确恒值和非有限样本；低幅度变化信号不自动叫平线 |
| Welch | 直接调用 `scipy.signal.welch` | PSD是描述量，参数与单位必须一起解释 |
| Thomson工频 | BrainElecQC用DPSS自行计算多窗F检验 | 参考PREP参数和Chronux原理，不直接调用Chronux，也不去工频 |
| 谱模型、α功率 | 直接调用 `fooof.FOOOF.fit`；另行积分PSD | 背景上方的峰与含背景的频带功率不同；不是质量分 |
| PREP非空间 | BrainElecQC独立再实现 | 主流程不调用PyPREP；`compare_with_pyprep`仅为独立对照；没有RANSAC、插值或稳健平均参考 |
| ECG/EOG锁时 | 直接调用MNE `find_ecg_events` / `find_eog_events`，再由BrainElecQC汇总EEG锁时证据 | 事件不自动等于污染；没有辅助导联保留未评 |
| 基础HF/EMG支持 | BrainElecQC组合方法，使用MNE滤波和Hilbert原语 | 不是直接调用 `annotate_muscle_zscore`；没有EMG只称高频线索 |
| MNE幅度、平线 | `annotate_amplitude` | 相邻样本差值，不是分窗峰峰值；坏通道可能没有区间 |
| MNE肌电 | `annotate_muscle_zscore` | 固定110–140Hz、采样率>280Hz；输出为跨所选通道的时间候选 |
| MNE桥接 | `compute_bridged_electrodes` | `lm_cutoff`是拟合范围上限，不是最终判定阈值；通道对不伪造起止时间 |
| MNE LOF | `find_bad_channels_lof` | 整段通道离群；不证明是伪迹，不提供时间定位 |
| 全局AutoReject | `get_rejection_threshold` | 同一连续选区分段拟合后描述超阈值；内部CV不等于独立验证，不删数据 |
| PyPREP RANSAC | 计划 `NoisyChannels.find_bad_by_ransac` | 尚未接入；需核实空间坐标和足够通道 |
| local AutoReject | 计划 `AutoReject.fit` / `get_reject_log` | 尚未接入；拟合也需要有效位置，不只是最终插值需要 |
| ICA/ICLabel | 计划 `mne_icalabel.iclabel.iclabel_label_components` | 尚未接入；模型训练条件、秩、坐标、参考与滤波须另行核验 |
| 计划、3类标注、汇总、报告 | 本项目 `planning.py`、`annotations.py`、`runtime.py` | 编排和证据封装，不冒充外部科学方法；总分为null，状态标签不改检测阈值 |

## 来源类型与阅读顺序

每项 `references` 区分“算法论文”“上游代码”“官方文档”“本项目封装”。前三类是HTTPS一手来源；“本项目封装”是仓内相对路径，界面应作为代码位置展示，不能将它当作官方网页或合规标准。推荐先读实际调用和实现来源，再读原理；不能仅凭方法名称推断依赖关系。

核心原理来源包括[PREP原论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC4471356/)、[Chronux F检验说明](https://chronux.org/chronuxFiles/Documentation/chronux/spectral_analysis/continuous/ftestc.html)、[SciPy Welch文档](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html)、[FOOOF文档](https://fooof-tools.github.io/fooof/)和[Autoreject原论文](https://arxiv.org/abs/1612.08194)。MNE、PyPREP、autoreject、MNE-ICALabel的逐函数官方链接附在相应方法中。EDF和BIDS链接只支持文件与元数据解释，不被扩大为临床质量认证。

所有数值默认应理解为上游算法默认或本项目实验筛查设置。4道PREP比较组门槛、桥接/LOF最少通道数、分析时长、肌电频带和阈值均须结合实际适用性解释，不能被写成所有EEG的通行质量标准。既有PREP非空间结果与ds002034来源坏道标签不一致的负结果继续保留。
