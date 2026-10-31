# NWB 测试数据与来源

路径说明：以下`/path/to/DBCI-QC-data`为可替换的数据根目录示例；本机原始路径及验收产物不随公开仓库发布。

本页记录 NWB 接入使用的公开文件、派生关系和测试边界。数据来源为正式发布的 DANDI 版本及依据 PyNWB 官方接口构建的合成文件；没有将本项目已有 FIF 转为 NWB 后冒充新的真实来源。数据不随代码仓库分发。

## 1. 文件位置与使用顺序

- 人类 ECoG 上传样例：`/path/to/DBCI-QC-data/测试数据/ECoG/02_语音任务_EC9_B15/`
- 其余读取兼容、合成及异常样例：`/path/to/DBCI-QC-data/验证记录/开发测试样例/`
- 原文件、来源元数据、HTTP 范围缓存和核对记录：`/path/to/DBCI-QC-data/公开数据/NWB/`
- 仓库清单：[datasets/nwb-examples.json](../datasets/nwb-examples.json)
- 准备脚本：[prepare_nwb_examples.py](../scripts/public_examples/prepare_nwb_examples.py)

2026-10-31 起，日常上传目录统一按“模态 → 样例”组织，格式和来源放在每个样例内的 `来源与说明.txt`、`来源.json`。建议先上传人类 ECoG 片段；开发测试样例各有独立目录，记录预期行为与限制。原 `测试数据/NWB/` 已归档至 `验证记录/目录整理_20261031/原测试数据/NWB/`，原始数据和已有运行输入路径未变。文件能被解析不等于适合任何模态的质控路线。

| 文件 | 来源与内容 | 应检查的行为 |
|---|---|---|
| `DANDI_000019_EC9_B15_samples30518-61036.nwb` | 真实人类 ECoG 原生 NWB 的约 10 秒派生片段；256 道 | 保留单位、原采样率、电极映射和非零时间起点；依据来源确认 ECoG |
| `sub-Sumac_ses-Sumac06-LinearTrack_behavior+ecephys.nwb` | 真实小鼠 LFP 原文件；32 道、1000 Hz、274.737 秒，另含 Units | 按历史文件明确声明的 `microvolts` 换算，显示规范差异；普通细胞外 LFP 不自动变成 Neuropixels 或头皮 EEG |
| `DBCI_synthetic_multistream.nwb` | 合成的两个连续流和 2 个单位 | 显示独立流；保存各自电极顺序、采样时钟和单位转换；Units 不是波形通道 |
| `DBCI_synthetic_units_only.nwb` | 仅 2 个合成单位，没有连续电压 | 明确提示没有可供连续信号质控的 ElectricalSeries |
| `sub-70375_ses-20170317T094453_behavior+ecephys.nwb` | 真实小鼠 LFP，时间戳发生回跳 | 不得把它伪装为一段连续等间隔记录 |
| `sub-TC6_ses-20190320_obj-18hbwq8_ecephys.nwb` | 真实人类处理后高伽马数据 | 来源描述优先纳入解释；不作为原始 ECoG 幅度或频谱基准 |
| `sub-703279277_ses-719161530_probe-729445654_ecephys.nwb` | Allen Neuropixels LFP 原文件；分散窗口抽查均为零 | 如运行检查，应如实呈现平线信息；不得称为正常信号样例 |

本批涉及 5 个独立的公开来源记录和 2 个合成工程文件。该数量不是经过专家标注的临床验证样本量，也不是坏道检测准确率证据。

## 2. 真实人类 ECoG 正例

来源：[DANDI 000019，版本 0.220126.2148](https://dandiarchive.org/dandiset/000019/0.220126.2148)，标题为 *Human ECoG speaking consonant-vowel syllables*，许可为 CC-BY-4.0。对象为 EC9 的 B15 记录，原生文件是 `sub-EC9/sub-EC9_ses-EC9-B15.nwb`，资产 ID 为 `4e4287f2-b557-4f30-a2d6-932f18c3e915`。

原文件 558,155,445 字节，NWB 2.0.2；连续数据位于 `/acquisition/ElectricalSeries`，形状为 `595093 × 256`，储存类型为 float32，采样率为 3051.7578 Hz。原文件明确声明 `unit=volt`、`conversion=0.001`，因此物理电压为储存值乘以 0.001 V。原始采集放大器标定没有另行独立核验。

本地片段只保留源样本 **[30518, 61036)** 和全部 256 个源通道，时长为 **10.000138280960567 秒**。片段的 `starting_time` 同样为 **10.000138280960567 秒**，保留它在源记录时钟中的位置。它不是把时钟悄悄归零后的完整原件。

所有 **7,812,608 个储存值**与 HTTP Range 读取的源数组逐位相同，电极表行和源电极 ID 的对应关系已核对。没有滤波、重采样、重参考或伪迹清理。派生写入将历史单位拼写 `volt` 规范为 `volts`，数值及 conversion 不变；空的源电极位置写为 `unknown`，原值保留在来源记录中。刺激、试次及其他非电压对象未复制，不能把派生文件没有标注解释为原实验没有标注。

原文件只做了范围读取，**没有验证原文件全量 SHA-256 或 DANDI ETag**。来源记录保留官方摘要、原文件字节数、实际读取的各个字节范围及其本地 SHA-256、源样本范围和导出文件摘要；不把选区核对表述为全文件核对。

## 3. 其他真实文件的解释边界

### 3.1 Sumac：历史单位与 LFP/Units 分层

来源：[DANDI 000165，版本 0.211118.1526](https://dandiarchive.org/dandiset/000165/0.211118.1526)，CC-BY-4.0。该研究包含小鼠海马多层记录及行为实验。本文件是 Sumac06 的线性轨道记录，文件说明为 CNO 注射后 1 小时开始记录；不把实验处理直接当作疾病标签。

LFP 位于 `/processing/ecephys/LFP/ElectricalSeries`：274,737 个采样点、32 道、1000 Hz、int16，源声明经过 0.1–300 Hz Butterworth 带通。文件声明 `unit=microvolts`、`conversion=1`，其 SI 换算需再乘以 10⁻⁶。这属于历史文件的单位兼容情形，应保留原单位并提示与当前 ElectricalSeries 规范的差异，不能静默解释为 V。设备明确为 Neuronexus A4x8-5mm-400-200-703-CM32，不能归入 Neuropixels。

### 3.2 Jacobsen：时间戳回跳

来源：[DANDI 000230，版本 0.220506.1516](https://dandiarchive.org/dandiset/000230/0.220506.1516)，CC-BY-4.0。文件有 4 道 LFP，电极表引用行是 `[0, 4, 8, 12]`，并非简单地选表中前 4 行。

510,250 个时间戳中存在约 −1800.996 秒和 −119.996 秒的回跳。它不能按点数除以 250 Hz 当作一段无中断信号。当前接入应拒绝这种非单调时间轴，并保留原件供后续分段策略验证。不能通过排序时间戳、删除重复点或重建等间隔时钟“修好”后假称原件正常。

### 3.3 TC6：高伽马派生量

来源：[DANDI 001193，版本 0.240921.1006](https://dandiarchive.org/dandiset/001193/0.240921.1006)，CC-BY-4.0。来源描述、session description 和 ElectricalSeries description 都明确指向处理后的高伽马活动；文件不是未经处理的宽带 ECoG。

即使数据对象名为 ECoG、单位属性写为 volts，也不能据此把这些值当作经过独立标定的原始电压。该文件保留用于检查“可读取的格式”和“适用的科学方法”是否被正确区分。

### 3.4 Allen：真实来源中的零值流

来源：[DANDI 000021，版本 0.251116.2246](https://dandiarchive.org/dandiset/000021/0.251116.2246)，CC-BY-4.0，并应遵循来源列出的 Allen Institute 使用条款。记录为 session 719161530 的 probe 729445654（probeD），使用 Allen 的 `ndx-aibs-ecephys` 扩展。

设备对象声明为 `EcephysProbe`，提供 probe ID 和原始探针采样率；本文件不另含制造商或型号字符串。Neuropixels 身份由正式数据集和 Allen 来源说明支撑。连续 LFP 为 96 道、12,081,218 点；逐点时间戳严格递增，推导采样率约 1249.996706 Hz。电极组的 `lfp_sampling_rate` 属性约为 624.998353 Hz，与时间戳不一致，不应以它覆盖实际时间轴。

抽查文件开头、中间、末尾及其他相距较远的窗口均为零。该结果不等于逐点核对整个 11.6 亿数值阵列；它足以说明不能把该文件当作正常 LFP 信号演示。来源已处理的 Allen LFP 也不等于本项目既有 SpikeGLX 原始 LF 流。

## 4. 合成例及独立核对

合成结构参照 [PyNWB 官方细胞外电生理教程](https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html)，由本项目脚本生成固定正弦、余弦和事件，不是教程中的真实记录，也不是独立临床证据。

多流文件包含：

- 20 秒、1000 Hz、3 道的 acquisition ElectricalSeries；起点 5 秒，电极表引用行为 `[2, 0, 3]`，对应 ID `[120, 100, 130]`。conversion 为 10⁻⁶，channel_conversion 为 `[1, 2, 0.5]`，offset 为 2×10⁻⁶ V。
- 10 秒、250 Hz、2 道的 processing/LFP ElectricalSeries；显式时间戳从 12 秒开始，电极表引用行为 `[1, 3]`。它与前一流分别选取，不能拼接为 5 道单一时钟数据。
- session 时间 13 秒的事件，以及 2 个 Units。事件在两个流内的相对位置分别为 8 秒和 1 秒；单位数量不得加入连续通道数。

事件保留在合成文件中；当前读取器未将NWB事件自动映射到M07。上述时间关系是夹具定义，不代表事件提取已验收，也不能将“尚未提取”解释为源文件没有标注。

物理值应按 `stored × conversion × channel_conversion + offset` 换算，并在历史单位需要时显式转换为 SI。缺省 channel_conversion 为 1，缺省 offset 为 0。电极表引用的是**行索引**，不是电极 ID；合成例特意使两者不同。

`evidence/h5py-source-audit.json` 使用 h5py 直接读取 HDF5 数组、单位属性、电极引用和时钟，没有把 PyNWB 数据 getter 当作第二个独立读数器。`evidence/ecog-excerpt.json` 记录完整选区逐位核对；`evidence/pynwb-schema-validation.json` 记录新生成文件的结构验证。工程读取、结构合规、原始采集标定和临床检测准确率是四种不同证据。

`evidence/independent-adapter-readback.json`另外将当前适配器与直接HDF5计算的物理电压作对照：覆盖ECoG片段和Sumac LFP的全部数值、合成文件的两个完整流，并核对反向选道和电极映射。该证据验证读取与转换，不证明后续质量检测准确。

## 5. 重现与日期

在项目指定环境安装 PyNWB、h5py、NumPy 和 requests 后执行：

```bash
python scripts/public_examples/prepare_nwb_examples.py \
  --output /path/to/DBCI-QC-data/公开数据/NWB \
  --upload-dir /path/to/DBCI-QC-data/验证记录/NWB重新生成
```

增加`--audit-reader`可重新执行当前适配器与h5py直接读数的独立比较；该选项要求仓库的NWB读取器已接入。

上面的重现命令输出到独立验证目录；它不会重建旧的日常上传层级，也不会自动更新各样例目录。

脚本核对 4 份完整原件的官方 SHA-256 和 DANDI ETag；已经存在的原件仍须通过摘要检查。HTTP 范围缓存和原件保留在仓库外，脚本不修改本地注册配置、不运行质控、不发布数据。

来源清单分别保存正式发布时间、来源元数据修改时间、源数据对象修改时间和本地文件 mtime。**这些时间均不能替代 session_start_time 作为实验时间。** 新写入的派生文件和合成文件也不因拥有新的 mtime 而成为新的独立实验。
