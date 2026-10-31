# 典型 EEG 数据扩充与冻结验收：2026-10-30

本批补充真实 BDF、BrainVision、EEGLAB 配套文件、临床静息、运动伪迹及混合采样率睡眠记录。文件来自固定公开版本，完整下载；不裁剪、滤波、重参考或重命名内部伴随文件。工作台登记表与已有运行历史保持不变。

## 1. 案例与来源

| 案例 | 格式 | EEG 通道 | 原记录时长/s | 本次用途 |
| --- | --- | ---: | ---: | --- |
| ds005284 sub-001 | BDF | 64，另含 Status | 328 | 开发：激光刺激任务 |
| ds005284 sub-002 | BDF | 64，另含 Status | 329 | 冻结验证：另一受试者 |
| ds007020 PD1001 | BrainVision | 63 | 281.66 | 开发：临床睁眼静息 |
| ds007020 PD1011 | BrainVision | 63 | 326.04 | 冻结验证：另一受试者 |
| ds004584 sub-001 / PD1001 | SET＋FDT | 63 | 281.66 | 开发：配对格式、帕金森病背景 |
| ds004504 sub-002 | 单文件 SET | 19 | 793.1 | 冻结验证：阿尔茨海默病背景 |
| ds006386 sub-2 run-01 | EDF | 59 | 1404 | 开发：运动伪迹、人工标注 |
| Sleep-EDF SC4031 | EDF＋独立分期文件 | 2，另有 5 路其他信号 | 84600 | 冻结验证：稀疏 EEG、混合采样率 |

八个文件表示来自六个数据集，**不是八个独立受试者**。PD1001 的两种格式是配对表示，不计作独立观察；其他跨数据集受试者重叠未被完全排除。疾病信息仅在来源明确提供时登记，不能从受试者名字推断。

来源及许可：

- [ds005284 v1.0.0：激光刺激任务](https://openneuro.org/datasets/ds005284/versions/1.0.0)，CC0。
- [ds007020 v1.0.0：临床静息 EEG](https://openneuro.org/datasets/ds007020/versions/1.0.0)，CC0。
- [ds004584 v1.0.0：帕金森病与对照静息 EEG](https://openneuro.org/datasets/ds004584/versions/1.0.0)，CC0。
- [ds004504 v1.0.8：阿尔茨海默病、额颞叶痴呆与对照](https://openneuro.org/datasets/ds004504/versions/1.0.8)，CC0。
- [ds006386 v1.0.1：PhysioMotion Artifact](https://openneuro.org/datasets/ds006386/versions/1.0.1)，CC0。
- [Sleep-EDF Expanded v1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/)，ODC-By-1.0。分期为原始 R&K 分类，保留原标注含义。

各来源作者、引用文献、提交、数据 DOI、文件 URL、字节数与 SHA-256 见[固定下载清单](../scripts/public_examples/typical_batch_20261030.json)。OpenNeuro 信号文件使用固定提交中的 git-annex SHA256E 校验，普通侧车使用提交对应字节；PhysioNet 信号与分期使用官方 SHA256SUMS。

## 2. 冻结协议

基线为提交 `77746d3`。在信号下载和质控运行前确定案例、开发/验证划分及前 120 秒分析窗口。先执行四份开发案例，再在算法与阈值不变的条件下执行四份验证案例。不按运行结果替换样例，不通过新增针对单个文件的模块使案例通过。

验收采用确定性推荐及明确的通道、参考和背景字段；比较组保守地保持未声明。原始文件与本次分析范围分别记录。睡眠文件虽为完整长记录，本次只评估前 120 秒。

本批衡量读取、推荐、执行与证据完整性，不衡量临床准确率。验证样例完成本轮运行后已被使用，后续调参后的独立评价必须另留新样例。

## 3. 来源与适用性问题

1. **BDF 通道命名与侧车不同。** 文件内为 A1…B32，侧车为头皮电极名称；保留源索引及名字，不以未经核实的对应关系启用空间算法。Boolean Status 排除出电压通道。外部 events.tsv 已保存，但不自动转换为质量标签。
2. **参考信息缺失或冲突。** ds007020 未给出参考；ds004504 的 README 与侧车参考说明不同。未知信息保留未知，不用疾病背景填补。
3. **时间和单位声明需要交叉核对。** 部分侧车时长是最后一个样本的时间，文件时长则按样本数计算；ds004584 实验描述的两分钟与实际文件时长不同。PhysioMotion 侧车写 V，EDF 标定写 uV，按 EDF 标定读取并记录差异。
4. **部分检查需要额外采集信息。** BrainVision/SET 未声明 ADC 端点时，不评估是否达到采集量程端点；缺少辅助信号、比较组或电极位置时，相关方法保留未评原因。
5. **有标注不等于能直接算准确率。** PhysioMotion sub-2 run-01 提供 863 行人工标签，含双极导联和 ALL 范围。需先完成导联与时间映射，再制定计数规则。睡眠分期、疾病分组、任务事件均不是伪迹真值。

## 4. 校验层次

- 下载层：75 个固定文件，共 493,141,786 字节，逐项核对大小及 SHA-256；另存 Sleep-EDF 官方说明和许可快照。
- 上传层：8 个上传文件包经工作台同一接收、解包、确认与计划代码验证，在隔离目录运行；未写入在线工作台登记表。此项不是浏览器界面人工走查。
- 读取层：各文件首、中、末各一秒，合计 882,816 个 EEG 值，对照独立读取方式。EDF/BDF 对照 MNE；BrainVision 对照二进制排列与头中分辨率；SET 对照 SciPy MAT / FDT。所取样本最大绝对误差为 0 V。
- 配对格式：PD1001 的 8,872,290 个完整采样值在各自标定后比较，最大绝对差约 0.000061 uV，符合相对容差 1e-6。不同二进制哈希或标定系数本身不表示读取错误。
- 报告层：逐例保存源指纹、推荐、计划、模块状态、结果、运行日志与 HTML 报告；工程通过不表示数据质量合格。分项未评与未校准总分保持可见。

本轮实际结果：开发 4/4、冻结验证 4/4 工程通过，均生成报告；无执行失败、超时或预算跳过。合计检查 960 秒，八份报告均为 `partial`（部分可评），总分均为 `null`。67 个计算源文件及本机工作台配置的指纹保持不变。完整来源与人工标注均未修改；检测准确率尚未验证。

## 5. 本地复现

使用安装了项目计算依赖的 Python 环境；以下目录均放在仓库外。下载工具预算上限为 1 GiB，遇到不符的既有文件不会覆盖，失败的临时下载保留以供检查。

```bash
python scripts/public_examples/download_pinned_batch.py \
  --manifest scripts/public_examples/typical_batch_20261030.json \
  --data-root /path/to/public-data \
  --receipt /path/to/evidence/download-receipt.json

python scripts/public_examples/prepare_typical_batch.py \
  --data-root /path/to/public-data \
  --evidence-dir /path/to/evidence \
  --upload-dir /path/to/upload-examples

python scripts/validate_data_coverage.py \
  --config /path/to/evidence/records-development.json \
  --output-dir /path/to/evidence/new-development-run \
  --max-total-seconds 480 --max-record-seconds 120 --timeout-seconds 240

python scripts/validate_data_coverage.py \
  --config /path/to/evidence/records-frozen_validation.json \
  --output-dir /path/to/evidence/new-frozen-validation-run \
  --max-total-seconds 480 --max-record-seconds 120 --timeout-seconds 240
```

重新验证本地文件可在下载命令中加 `--offline`。ZIP 内仅包含读取所需原始伴随文件；外部标注与实验说明保留在公开数据目录，并不意味着上传 ZIP 时自动导入这些侧车。源信号、标注、个人环境配置及完整报告不随代码提交。
