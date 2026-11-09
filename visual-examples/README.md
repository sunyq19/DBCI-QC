# 可视化模块的公开数据示例

这些图片是模块协作页的静态示例。数值来自已完成的真实质检结果；未重新运行检测、未为制造效果添加噪声、未改变评分。

## 数据来源

- OpenNeuro **ds002034 v1.0.3**，CC0。
- https://openneuro.org/datasets/ds002034/versions/1.0.3
- DOI: https://doi.org/10.18112/openneuro.ds002034.v1.0.3
- 原数据记录：`sub-01/ses-01/eeg/sub-01_ses-01_task-offline_run-01_eeg.edf`。
- 实验：隐性注意任务；本图使用 62 个已选择的头皮 EEG 通道、512 Hz，原记录共 733 秒。
- 图中分析窗口：原记录 0–120 秒。只导出图表所示的少量测量值和波形片段，不分发完整 EDF、受试者表或本机路径。
- 原文件 SHA-256：`7edb1d6b813cf0b9c33e1b627f3181f8a9a2fb56603d6be3aca0879281a45f2e`。
- 数据作者：Christoph Schneider、Michael Pereira、Luca Tonin、José del R. Millán。
- 相关论文：https://doi.org/10.1007/s10548-019-00725-9
- This data was obtained from the Open Neuro database.

## 实际处理与图表范围

- 工频图：沿用 BrainElecQC 的已保存检查结果；同一道同一检查窗的多个频率命中只计一次。比例是窗口命中比例，不是污染时长。
- 波形图：直接读取公开 EDF 中 O2、O1、Pz 的 2.50–7.75 秒电压值；着色区间 O2 4.50–5.75 秒来自已保存高频突发候选。未为了绘图重新滤波。
- PREP 指标：显示已保存的稳健幅值；线长图显示灵犀云原版线长数值。两项不合并、不共用单位。
- 灵犀云分析副本：256 Hz、1–70 Hz、共同平均参考、无 ICA；输入文件不变。
- 灵犀云频谱相关图：从本窗口中排除候选片段后，保留 13.880–45.715、51.940–102.030、103.245–120.000 秒，按采样点计实际 98.68359375 秒。
- 原版保存的 PSD 范围为 1–40 Hz；频带列沿用原算法定义，gamma 仅表示该可测频带内的部分，不表示完整高频活动。
- 相对功率乘以 100 后显示为百分数；PSD 转换为 dB re μV²/Hz；其他指标保持原保存数值。
- 原记录输入 PSD 展示 1–80 Hz；与灵犀云分析副本 PSD 分开呈现。不能将曲线变化直接解释为清洗提高质量。
- 参考图使用原版参考上下界，不绘制虚构的群体密度曲线；超界不直接等于质量不合格。
- 时间轴与占比图独立显示检测方法；候选可能重叠，不能简单相加。
- 各图明确给出显示的通道子集；CSV 只包含实际绘制的样本和测量值，带公共记录编号与分析窗口。

## 方法来源

- BrainElecQC: https://github.com/Jlei61/BrainElecQC
- GnosisNeuroDynamicSE: https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE
- 当前质控台可视化代码：`src/ephys_qc/visualizations/`。

## 可用性

10 个子模块及 VIS 总览有真实图片和结果。脑地形图、雷达图仍为规划项，没有伪造预览：前者需要可信电极坐标，后者需要指标方向与归一化定义。

## 复现

仓库脚本 `apps/flow-editor/scripts/build-visual-examples.py` 接收 `--artifacts`（包含 `w000001--` 结果的目录）和 `--edf`（上述公开原始文件）两个参数。脚本校验原文件哈希、方法完成状态、时间窗与通道数，再从已保存证据绘图。图片与 CSV 均不包含本机绝对路径或运行日志。
