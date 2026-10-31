# DBCI-QC

**模块化电生理数据质量控制工具集，附本地工作台。**

[English](README.en.md)

DBCI-QC 以数据为入口，将文件读取、信息确认、方法选择、模块执行和人工复核组织为可追溯的质控流程。当前提供**头皮 EEG**检查，以及 **ECoG、sEEG 和 Neuropixels 连续电压的基础描述检查**。统一工作流程由读取后的模态、通道和采集条件选择适用方法，不要求用户在上传前选择模态。

当前开发版本：**1.0.0rc3.dev8**；上一已标记候选版为 **1.0.0rc2**。核心交付为可独立安装和调用的 Python 工具包；九个模块按文件独立实现，提供 Python 与命令行入口，网页是可选应用。交接与调用见[模块工具包](docs/toolkit.md)，版本变化见 [CHANGELOG](CHANGELOG.md)，实现与验收范围见[运行验收记录](docs/runtime-validation.md)，未完成事项见[待办清单](TODO.md)。

规范入口：[总则](docs/workflow-standards.md) → [字段字典](docs/metadata-fields.md) → [方法适用规则](docs/method-applicability.md)；[实现与验证范围](docs/implementation-status.md)单独说明软件能力。

## 工作流程

```text
读取本机文件 → 确认通道与采集信息 → 推荐并确认检查方案
                                      ↓
人工复核 ← 报告、候选与波形证据 ← 按模块执行检查
```

1. **读取文件**：提取通道、采样率、时长、单位、文件关系和原始标注。
2. **确认信息**：核对模态、通道角色与参考，补充任务、疾病等背景；未知信息保留未知。
3. **确认方案**：根据技术条件推荐方法，检查依赖和适用范围，保存本次输入与配置。
4. **检查与复核**：运行选定模块，查看指标、候选位置及原始波形，独立保存人工意见。

上传文件和生成推荐均不会启动分析。算法结果保留证据与未评原因，不自动删除、插值或覆盖原始信号。疾病标签用于解释背景，当前不据此调整检测阈值。

## 模块划分

以下为九个共同职责；表内具体检测方法描述头皮EEG路线，其他模态采用各自适用方法与限制。

| 模块 | 职责 | 主要输出 |
| --- | --- | --- |
| [M01 数据接入与结构核验](docs/modules/M01.md) | 按格式读取，核对配套文件、单位与来源 | 技术信息、来源指纹、结构问题 |
| [M02 数据画像与检查计划](docs/modules/M02.md) | 判断方法适用性，组织选择与依赖 | 数据标签、冻结计划、适用或未评理由 |
| [M03 信号完整性](docs/modules/M03.md) | 检查非有限值、恒值、平台及幅度线索 | 通道或时间段候选 |
| [M04 频谱与干扰](docs/modules/M04.md) | 描述功率谱、工频、背景谱与谱峰 | 频谱指标及干扰证据 |
| [M05 坏通道候选](docs/modules/M05.md) | 在适用条件下检查噪声、相关性、桥接与离群 | 候选通道、通道对及判据 |
| [M06 生理伪迹线索](docs/modules/M06.md) | 分析 ECG/EOG 锁时关系、高频与 EMG 支持证据 | 生理事件关联及高频候选 |
| [M07 状态和事件检查](docs/modules/M07.md) | 核对分期、任务和临床事件与选区的对应关系 | 标注覆盖、时间对齐及来源问题 |
| [M08 分项评价与可比性](docs/modules/M08.md) | 汇总分项结果、实际覆盖与未评项目 | 分项摘要和比较条件 |
| [M09 报告与人工复核](docs/modules/M09.md) | 整理报告、候选定位、波形与复核记录 | HTML 报告、结构化证据、复核版本 |

方法工具箱按检查目的分为数据与元信息、信号完整性、频谱与干扰、通道质量、伪迹线索、事件与时间、结果与报告七个功能域。模态属于适用范围；随模块运行、满足条件、手动扩展属于启用方式，不作为顶层分类。当前可选扩展包括 MNE 相邻采样变化/平线、电极桥接、LOF 通道离群、高频线索，以及 autoreject 全局阈值估计。另接入 FASTER、FieldTrip 差分区间线索、SpikeInterface AP std/MAD，及 ASR、CleanLine、Zapline-plus 清洗影响评估；均须显式选择，实际子路径、条件和安装见[研究扩展运行规范](docs/optional-methods-runtime.md)。各模块页面列出输入、输出、依赖、参数、方法来源及限制；完整目录见[方法与数据标签](docs/eeg-methods-tags.md)，跨模态扩展约定见[架构](docs/architecture.md)。

## 多模态测试入口

工作台先读取文件，再提取信息、确认建议并生成检查方案；上传前无需选择模态。明确的逐通道类型可以预填建议，读取器默认类型仍待确认。所有记录和历史统一展示，内部方法路线由已确认的数据驱动；旧的`modality`地址参数仅保留兼容。ECoG、sEEG与Neuropixels连续电压复用接入、计划、事件与报告基础设施；描述性路线提供完整性、Welch PSD/窄带观察和逐触点统计，不套用头皮坏道或肌电阈值。ECoG/sEEG的M06可显式启用FieldTrip差分区间线索，Neuropixels的M06尚未接入。

| 路线 | 当前数据范围 | 专属边界 |
| --- | --- | --- |
| ECoG / ecog-basic/1 | 已确认的皮层表面电压 | 不自动推断网格邻接或坏触点 |
| sEEG / seeg-basic/1 | 已确认的深部触点电压 | 不推断电极杆、双极配对或病理伪迹 |
| Neuropixels 电压 / neuropixels-voltage/2 | SpikeGLX单个AP/LF流，或有明确Neuropixels设备证据的NWB连续ElectricalSeries | 同步字排除于电压分析；尚无分选及单元质量评价 |

```bash
python scripts/public_examples/prepare_ecog_example.py --output /path/to/ecog-examples
python scripts/public_examples/prepare_seeg_example.py --output /path/to/seeg-examples
python scripts/prepare_neuropixels_samples.py --destination /path/to/neuropixels-examples
```

`upload-samples/` 内提供可直接上传的 FIF 和原 BrainVision ZIP；原始下载、转换与独立读取证据均留在指定目录。它们源自同一份真实 ECoG 记录，不能当作两个独立受试者。平台示例登记与单文件上传分开：上传不会自动加载外部临床事件表。具体流程见 [ECoG 接入与测试](docs/ecog-testing.md)。sEEG脚本提供原始FIF字节副本；Neuropixels脚本提供Pt03人脑2秒AP片段及Noise4Sam LF格式测试文件，来源及派生记录单独保留。准备脚本不修改工作台登记或启动任务。模块分层与数据使用规则见[多模态接入规划](docs/multimodal-extension.md)。

Neuropixels读取器支持型号0、21、24的已声明结构；**当前真实数据验证仅覆盖NP1，NP2仅有合成读取契约测试**。ACSF AP与截短Noise4Sam AP因来源哈希或长度不一致保留为拒绝负例，不登记为可运行样例。0.02秒短窗验收使用已核验人脑AP片段内的选区，不将其计为独立数据。

## 文件支持

| 格式 | 提交方式 | 当前范围 |
| --- | --- | --- |
| EDF / EDF+ | 单个 `.edf` | 连续波形记录 |
| BDF | 单个 `.bdf` | 连续记录，保留原生采样流 |
| BrainVision | `.vhdr`、`.vmrk`、`.eeg` 同目录打包 ZIP | 完整配套记录 |
| EEGLAB | 内嵌数据 `.set`，或 `.set` / `.fdt` 配套 ZIP | 连续数据 |
| FIF | 单个 `.fif` | 单文件 Raw 数据 |
| SpikeGLX | 一个流的 `.ap.bin` / `.ap.meta` 或 `.lf.bin` / `.lf.meta`，一起ZIP | 已支持Neuropixels探针的原始单流；模拟通道与同步字分开 |
| NWB 2 / HDF5 | 单个 `.nwb` | 连续ElectricalSeries；多流须明确选择并冻结；Units不作为连续通道 |

上传文件及 ZIP 解压后总量上限均为 **512 MiB**；一包对应一份记录。EDF+D/BDF+D、分段 EEGLAB、分卷 FIF、NWB-Zarr、压缩SpikeGLX `.cbin`、NIDQ及分选后的spike/unit输入尚未纳入当前流程。格式不决定模态；读取到其他模态信息不代表已支持其质控。详细约定见[文件格式与读取模块](docs/file-formats.md)。

NWB是文件容器，不是新的脑电模态。读取后保留每个ElectricalSeries的电极映射、单位和时钟；用户选择一个流，选择随记录版本和执行计划冻结。其他NWB电压依据来源确认头皮EEG、ECoG或sEEG，不能仅因NWB含细胞外数据就进入Neuropixels路线。真实人ECoG片段、历史LFP及合成多流/Units边界见[NWB样例与来源](docs/nwb-testing.md)和[清单](datasets/nwb-examples.json)。

## 安装与启动

已验证环境为 **Linux、Python 3.11**。工作台无前端构建步骤；Node.js 仅用于开发检查。`pip install -e .` 安装工具包与 `dbci-qc` 命令，不会自动安装外部计算后端。

### 1. 获取项目与依赖

```bash
git clone https://github.com/sunyq19/DBCI-QC.git
cd DBCI-QC
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python -m pip install "brainelecqc[qc,readers,figures] @ git+https://github.com/Jlei61/BrainElecQC.git@f007d829712d1b824cda79409d181a3313d6a78f"
python -m pip install "mne==1.13.2" "autoreject==0.5.1" "h5io==0.2.5" "pymatreader==1.3.2"
python -m pip install "pynwb==3.1.3" "hdmf==4.3.1" "h5py==3.16.0"
```

BrainElecQC 为单独安装的外部依赖，不随本仓库分发。已测包版本见[环境记录](profiles/tested-environment.json)；该记录不是完整依赖锁。第三方使用与再分发边界见[第三方说明](THIRD_PARTY_NOTICES.md)。

### 2. 独立使用模块

无需启动网站即可查看模块、检查文件或运行示例：

```bash
dbci-qc catalog
dbci-qc inspect /path/to/record.edf
python examples/headless_qc.py --output /path/to/new-demo
```

示例现场生成合成信号并执行 M03 及必要依赖。实际数据的选道配置、Python 调用、命令行执行和 wheel 交接见[模块工具包](docs/toolkit.md)。

### 3. 可选：配置本地工作台

```bash
mkdir -p .local
cp -n apps/workbench/workbench.minimal.json .local/workbench.json
```

编辑 `.local/workbench.json` 中两处路径：

- `python`：本项目 `.venv/bin/python` 的**绝对路径**。
- `data_dir`：仓库外的运行目录，例如 `/path/to/DBCI-QC-data/runtime`，用于保存上传副本、任务和报告。

最小配置不含预登记数据，可直接在工作台提交本机文件。需要固定示例时，再参考[完整登记模板](apps/workbench/workbench.example.json)；其中的路径须自行配置，原始数据不随代码提供。已有 `.local/workbench.json` 时保留原配置。

### 4. 启动工作台

```bash
python apps/workbench/server.py --config .local/workbench.json
```

浏览器打开 **[http://127.0.0.1:8769/](http://127.0.0.1:8769/)**，终端按 `Ctrl+C` 停止。服务仅监听本机地址，无需登录；提交文件保存到本机运行目录。

Linux 下也可用 `python scripts/run_local.py` 在后台启动；`--status` 查询状态，`--stop` 停止本启动器管理的服务。配置字段与 API 见[工作台说明](apps/workbench/README.md)。

## 报告与复现

每次任务保存输入版本、主文件及配套文件指纹、方法选择、参数、执行状态和软件环境。支持短窗预检与整份记录分块检查；整份检查分别报告已评、失败、未执行及来源缺口，分块计算不等同于全记录一次建模。

主要输出包括 `request.json`、`job.json`、`result.json`、`run.log` 和 `artifacts/`。人工复核另存版本化 `reviews.json`；复制配置重跑产生新任务，保留父任务关系。

原有头皮EEG登记清单包含 **7 个公开数据集、26 份记录**，覆盖静息、运动/运动想象、注意任务、睡眠、临床发作、认知障碍背景和任务诱发伪迹。该批为真实 EDF/SET；ECoG新增1份公开观测的原BrainVision与派生FIF，另行记录于[ECoG清单](datasets/ecog-examples.json)。sEEG增加一份真实任务片段；Neuropixels增加一份真实人脑AP派生片段和一份LF格式测试记录，详见[多模态样例与验收边界](docs/multimodal-extension.md)。数据和标注按来源说明单独获取，见[公开数据示例](docs/public-examples.md)及[头皮EEG固定案例清单](datasets/coverage-cases.json)。格式表示数不等于独立样本数；工程格式样例不能混称自然伪迹基准，任务、睡眠及发作标注不作为伪迹真值。

2026-10-30 另补充了[8份典型 EEG 文件及冻结验收协议](docs/typical-batch-20261030.md)，覆盖真实 BDF、BrainVision、SET＋FDT、单文件 SET 和 EDF。该批独立保存下载清单与本地验收结果，不自动加入预登记菜单；使用上传文件包直接测试。

批量工程验收可脱离网页运行，并生成逐例报告索引：

```bash
python scripts/validate_data_coverage.py \
  --config /path/to/records.json --max-total-seconds 3600 \
  --output-dir /path/to/new-coverage
```

验收区分来源完整性、实际执行覆盖和科学准确性；未评、失败及预算跳过均保留，规则见[数据覆盖验收规范](docs/data-validation.md)。

## 验证与当前限制

在上述计算环境中安装 Node.js 后，可运行自动回归：

```bash
python scripts/check_release.py
```

自动检查覆盖读取边界、计划和模块契约、版本化修订、复核冲突、分块覆盖及界面状态。依赖本地样例配置的用例在新环境可能跳过；真实文件流程验收需按[验收记录](docs/runtime-validation.md)另行准备数据。自动检查不能替代浏览器人工走查。

当前结果用于科研数据筛查与人工复核，尚未完成独立专家标注下的检测准确率验证。**总质量分尚未校准，保持 `null`**。sEEG与Neuropixels目前仅提供基础描述检查；spike sorting、单元质量指标（如unit SNR、ISI违例）、探针漂移与跨流同步尚未接入。疾病专属判定、跨窗候选自动合并和 Linxi 宿主集成属于后续范围。技术规范为项目草案，不是已发布的行业或团体标准。

## 文档与开发

| 内容 | 入口 |
| --- | --- |
| 模块交接与独立调用 | [Python API、命令行、示例与安装包](docs/toolkit.md) |
| 项目技术规范 | [通用流程](docs/workflow-standards.md) · [头皮 EEG](docs/qc-standards.md) · [English](docs/en/qc-standards.md) · [ECoG](docs/ecog/qc-standards.md) · [ECoG English](docs/en/ecog/qc-standards.md) · [sEEG](docs/seeg/qc-standards.md) / [EN](docs/en/seeg/qc-standards.md) · [Neuropixels](docs/neuropixels/qc-standards.md) / [EN](docs/en/neuropixels/qc-standards.md) |
| 流程与接口 | [架构](docs/architecture.md) / [EN](docs/en/architecture.md) · [多模态模块规划](docs/multimodal-extension.md) · [接口约定](docs/contracts.md) · [推荐规则](docs/recommendations.md) |
| 方法及依据 | [方法与标签](docs/eeg-methods-tags.md) · [来源核对](docs/toolkit-sources.md) |
| 常用方法扩展 | [运行范围与安装](docs/optional-methods-runtime.md) · [公开样例验收](docs/research-adapter-validation-20261031.md) · [历史来源调研](docs/qc-methods-review-20261031.md) |
| 数据与验证 | [公开示例](docs/public-examples.md) · [非 EEG 样例验证](docs/non-eeg-coverage-20261031.md) · [覆盖验收规范](docs/data-validation.md) · [模块验证计划](docs/module-validation-plan.md) · [运行验收](docs/runtime-validation.md) |
| 版本维护 | [版本管理](docs/versioning.md) · [变更记录](CHANGELOG.md) |

工作台中的“质控标准”读取同一份文档源，模块详情可进入对应说明页。维护方法、参数或技术要求时，同步更新实现、模块文档和相关验证记录。

```text
src/ephys_qc/modules/  M01–M09 独立实现、注册表与模块上下文
src/ephys_qc/modules/ecog/  ECoG基础计算实现，与头皮判定隔离
src/ephys_qc/modules/seeg/  sEEG独立入口与适用性
src/ephys_qc/modules/neuropixels/  Neuropixels连续电压独立入口
src/ephys_qc/modules/continuous/  sEEG和Neuropixels共享的描述性数学核
src/ephys_qc/toolkit.py  面向接收方的 Python 接口
src/ephys_qc/      读取器、适用性、计划、方法适配与报告
apps/workbench/   本地界面、HTTP API、任务与复核管理
examples/         脱离网页的合成数据与模块调用示例
docs/             技术规范、模块说明、依据与验证记录
datasets/         来源登记、格式样例清单与数据卡模板
profiles/         场景设计、实现覆盖与已测环境
tests/            工程与接口测试
scripts/          启动、数据准备及验收工具
```

## 方法来源与许可

[BrainElecQC](https://github.com/Jlei61/BrainElecQC) 提供首个 EEG 计算后端。DBCI-QC 在其上组织统一读取接口、数据描述、方法适用性、模块调度、追溯报告与人工复核，并接入 MNE、autoreject 等方法。原方法与本项目适配的职责、调用位置和论文来源分别记录于[来源核对](docs/toolkit-sources.md)。

本仓库当前尚未指定项目许可证；第三方代码与数据的许可分别适用，详见[第三方说明](THIRD_PARTY_NOTICES.md)。原始记录、私有标注、运行报告、本机配置和第三方安装包不纳入仓库。
