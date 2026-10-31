# 可选研究方法运行规范

版本：`research-adapters/1` · 软件：`1.0.0rc3.dev7` · 更新：2026-10-31。

本文件规定六项研究扩展的调用范围、前置条件、证据和运行环境。默认推荐流程保持不变；扩展须明确选择。参数是软件默认值或项目研究配置，尚不是行业统一质量阈值。

## 1. 执行范围

| 方法 | 模块与模态 | 本版实际调用 | 输出与边界 |
|---|---|---|---|
| FASTER | M05 · EEG | `mne_faster.find_bad_channels`，1.2.2 | 按方差、相关、Hurst、峰度和可测工频列出通道候选；固定段不是任务试次；不是完整FASTER流程。 |
| SpikeInterface | M05 · Neuropixels AP | `detect_bad_channels(method="mad"/"std")`，0.104.2 | 按源文件声明的shank分别高通、固定种子抽样，输出good/noise；good仅指未超本阈值。不含IBL coherence+psd、dead/out、LF或单元质量。 |
| FieldTrip | M06 · EEG/ECoG/sEEG | `ft_artifact_zvalue(absdiff="yes", cumulative="no")` | 最大单道差分z值及区间候选；无带通、无边界扩展，无空间合并。病理放电也可能触发，不能据此判坏或剔除。 |
| ASR | M06 · EEG | clean_rawdata原版 `asr_calibrate/asr_process` | 保存校准状态与重建影响；只支持已明确选择校准段的单窗口。不是自动清洗流水线，不推断校准段干净。 |
| CleanLine | M04 · EEG | 官方 `cleanLineNoise` 新实现 | 指定单个工频；前后PSD、逐道变化量和指纹；不自动添加谐波。末尾不足滑窗部分保留原值。不是legacy `cleanline` 调用。 |
| Zapline-plus | M04 · EEG | `clean_data_with_zapline_plus` | 一个明确工频、当前窗口作为一个固定chunk，自动选择去除成分并调整sigma；未启用自动分段。保存配置和analytics。 |

所有方法接受已标定的V数组，保持源通道顺序和原始时钟。默认不删道、不插值、不修改原始文件。清洗类仅在内存副本中计算，保存评估量，不导出清洗波形，也不把变化量解释为伪迹比例或质量分。总分保持null。

## 2. 选择与条件

工作台上传文件、确认信息后，可在对应模块的可选方法中启用扩展。高级参数仍通过既有JSON编辑器填写；未知参数会拒绝。单窗口至多120秒、输入至多256MiB；外部方法每次执行限180秒。超时、缺依赖、上游版本改变或退化输入不得报告为空候选成功。

- FASTER、ASR、Zapline-plus：8–128个同参考比较通道，参考必须已核实为共同或连接耳参考。FASTER至少5个固定段、100Hz；工频统计须50/60Hz均可测。
- SpikeInterface：仅AP，文件声明shank，每组至少8道；单位V显式转换为µV。默认MAD阈值倍数5、高通300Hz、0.3秒×20次随机抽样、seed=0；可能重复抽样，不能把短片段当长记录覆盖。
- FieldTrip：至少10秒连续片段。阈值4为研究配置；多通道最大值受通道数影响，不跨配置比较为同一标准。
- CleanLine：默认4秒窗、1秒步长、alpha=0.01、工频50Hz；只允许2–10秒窗和整数采样点窗长/步长。频率与邻带须可测；不根据所在地自动猜50/60Hz。
- Zapline-plus：至少32秒、整数采样率，默认工频50Hz；整个选区作为一个固定chunk。
- ASR：调用者明确复核校准区间并设置 `calibration_confirmed=true`；至少30秒，起点相对于当前选区，且须对应整数采样点。先对整个副本进行四阶1Hz Butterworth零相位高通；校准与待处理副本使用同一滤波。默认cutoff=20、统计窗1秒、lookahead=0、stepsize=32、maxdims=0.66、maxmem=256MiB。记录校准实际范围、秩、SHA256及M/T/A/B。秩不足阻断；当前只用上游预置谱加权系数，支持100/128/200/256/300/500/512Hz；不自动重采样。整记录模式拒绝ASR，避免每个窗口重新校准却声称全局一致。

ASR选择示例（仅在已核对校准段后使用）：

```json
{
  "extensions": ["asr_bursts"],
  "extension_parameters": {
    "asr_bursts": {
      "calibration_start_seconds": 0,
      "calibration_seconds": 30,
      "calibration_confirmed": true
    }
  }
}
```

以上内容属于`method_config`。参考构型和比较组沿用已登记信息，不能为绕过门槛而填写虚假值。

## 3. 独立部署

Python适配器、前置条件和统一结果接口位于`src/ephys_qc/research_runtime.py`；Octave进程边界位于`external_runtime.py`；可交接模块不依赖网页。调用方式仍为`extensions.evaluate_extension/run_extension`。读取后的数据事实必须包含模态、单位、时钟、参考及方法所需来源字段。

在现有科学环境中安装可选Python依赖：

```bash
python -m pip install -e '.[research]'
```

MATLAB来源工具在本机以GNU Octave 10.3.0执行。准备一个独立安装的`octave-cli`，然后显式配置源码位置：

```bash
python scripts/configure_research_runtime.py \
  --source-root /path/to/external-qc-tools \
  --octave /path/to/octave/bin/octave-cli
```

脚本下载固定提交及校验后的GNU Octave signal 1.4.8源码，将配置写到忽略版本控制的`.local/qc-methods.json`。已有不同版本的源码不会被重置；已有配置不会被覆盖。安装版本须经回归后使用。上传或运行任务不会下载或执行用户指定脚本，也不接受上传内容提供的执行器路径。

运行时可用`DBCI_QC_METHODS_CONFIG`指定另一份管理员配置。工作进程继承此变量。API和命令行需使用同一科学Python环境；缺依赖时保留明确的未评原因。计划器只做元信息检查，不读信号或运行库，依赖检查在执行阶段进行。

| 上游 | 固定提交 |
|---|---|
| clean_rawdata | `85eab7d22f00f1ed36392c96eb0774752d62bd11` |
| CleanLine | `117bffa6e1fbc6d042a7e75cec9e289e1aa5be72` |
| Zapline-plus | `f4628a32f4ec53cebfb07b1f6a8f465f44f1377a` |
| FieldTrip | `02149cbf43920b87b823567b28feaa1cd9d5e6a4` |

执行记录包含包版本、commit、入口源文件和适配器SHA256、兼容层文件SHA256、引擎版本和日志末尾；运行前检查固定源码未被修改，并比对signal归档及解包内容。结果位于`Mxx_<method>.json`，清洗评估另有报告内PSD图片。

## 4. Octave兼容层

本版没有“与MATLAB逐位一致”的验证结论。算法入口来自上游；以下差异必须保留在交接说明与证据中：

1. CleanLine需要DPSS。Python用`scipy.signal.windows.dpss(sym=True, norm=2)`计算对称L2归一化窗及特征值，Octave接口仅接受与缓存完全相同的N/NW/K；不使用FieldTrip的插值近似DPSS。
2. Zapline-plus的MATLAB列式`pwelch`由逐列Octave signal调用实现；固定半窗重叠、无去均值、单边功率谱密度，NFFT=max(256,nextpow2(window))。`round(x,2)`只用于上游显示文本。Octave参数解析使用与固定源码对应的位置参数。
3. FieldTrip的`ft_fetch_data`在临时副本中选择上游已提供的`ft_getopt`分支，绕开Octave `inputParser.addOptional`与MATLAB的选项差异。记录原/修补文件SHA256；原始checkout保持不变。`convertStringsToChars`和`istable`只适配当前传入的char/数值/结构类型。
4. UTF-8路径通过环境变量传递，避免Octave MAT字符串截断；方法内部用稳定ASCII行标签，结果由Python映射回原始通道名称、索引及源ID。
5. 外部进程继承任务进程组，取消任务同时终止计算；单方法超时另行终止Octave。上游运行失败不会覆盖已完成的基础检查。

## 5. 验证与未覆盖范围

2026-10-31完成六项合成信号执行，并在4份公开来源文件上生成4份工作台报告，合计8次扩展执行：EEG五项，ECoG与sEEG各一次FieldTrip，Neuropixels AP一次SpikeInterface。详见[执行验收记录](research-adapter-validation-20261031.md)。

这些证据证明固定环境和选区能执行、索引/时钟可追溯、原始输入保留。它们不证明跨疾病准确率、真实坏道精确率、ASR校准段干净、无神经信号损伤、全记录覆盖或MATLAB数值一致性。RANSAC、local AutoReject和ICLabel仍为待接入。

## 6. 来源与许可

- [MNE-FASTER](https://github.com/wmvanvliet/mne-faster)：BSD-3-Clause；独立Python实现，不是MNE内置FASTER。
- [SpikeInterface](https://github.com/SpikeInterface/spikeinterface)：MIT；本版只接std/mad。
- [clean_rawdata ASR源码](https://github.com/sccn/clean_rawdata/blob/master/asr_calibrate.m)：仓库GPL-3.0，ASR文件另有UC教育、研究、非营利用途和商业使用说明。科研运行不表示已解决商业部署许可。
- [CleanLine](https://github.com/sccn/cleanline)：仓库包含GPL-3.0-or-later文件及分别许可的依赖；本版调用`cleanLineNoise`新实现，保留整份上游许可，不把所有文件归为同一许可。
- [Zapline-plus](https://github.com/MariusKlug/zapline-plus)：GPL-3.0，保留NoiseTools等依赖说明。
- [FieldTrip](https://github.com/fieldtrip/fieldtrip)：GPL-3.0；包括使用到的统计函数。
- [GNU Octave signal](https://gnu-octave.github.io/packages/signal/)：按文件保留GPL及相关许可。

仓库只交付本项目适配器和固定安装清单，不包含上述工具的源码或数据。分发与部署需保留相应文件级许可，见[第三方声明](../THIRD_PARTY_NOTICES.md)。
