# DBCI-QC

**模块化电生理数据质控工具集，附本地质控台。**

[质控流程网页](https://sunyq19.github.io/DBCI-QC/) · [网页源码与部署](apps/flow-editor/README.md) · [English](README.en.md) · [模块接口](docs/toolkit.md) · [质控标准草案](docs/qc-standards.md) · [更新记录](CHANGELOG.md)

上传本机文件，确认模态与通道，运行推荐检查，查看报告。算法模块可独立调用，网页用于试用、展示与人工复核。

当前开发版：**1.0.0rc3.dev14**。支持头皮 EEG，以及 ECoG、sEEG、Neuropixels 连续电压的基础描述检查。EEG 报告提供试行评分、分项结果、候选位置与 PDF 下载。

## 快速开始

已验证环境：**Linux + Python 3.11 + Git**。首次安装需要联网，不需要 Node.js、前端构建或账号登录。Windows、macOS 尚未完成同等验证。

### 1. 下载并安装

```bash
git clone https://github.com/sunyq19/DBCI-QC.git
cd DBCI-QC
python3.11 scripts/setup_local.py
```

脚本自动创建 `.venv`、安装科学计算与 PDF 依赖，并生成 `.local/workbench.json`，无需手动填写路径。已有配置会保留。若使用 Conda，请先进入 Python 3.11 环境，再执行 `python scripts/setup_local.py`。

### 2. 启动

```bash
.venv/bin/python apps/workbench/server.py --config .local/workbench.json
```

### 3. 打开质控台

浏览器访问 **[http://127.0.0.1:8769/](http://127.0.0.1:8769/)**。

```text
上传文件 → 确认信息 → 查看推荐方案 → 开始检查 → 查看报告 / 下载 PDF
```

终端保持运行，按 `Ctrl+C` 停止。下次只需执行第 2 步。默认上传副本、任务和报告保存在 `.local/runtime/`，不进入 Git；原始文件保持不变。新上传副本保留 **7 天**，到期保留报告与检查证据。服务仅监听本机地址。

需要换端口、改数据目录或更新旧版本，见[安装与配置](docs/installation.md)。

## 支持哪些文件

| 格式 | 提交方式 |
| --- | --- |
| EDF / EDF+、BDF | 单个 `.edf` 或 `.bdf` |
| BrainVision | `.vhdr`、`.vmrk`、`.eeg` 同目录打包为 ZIP |
| EEGLAB | 内嵌数据的 `.set`，或 `.set` + `.fdt` 打包为 ZIP |
| FIF | 单个 Raw `.fif` |
| NWB 2 / HDF5 | 单个 `.nwb`，读取后选择连续 ElectricalSeries |
| SpikeGLX | 一个 AP 或 LF 流的 `.bin` + `.meta` 打包为 ZIP |

单次上传及 ZIP 解压后总量上限均为 **2 GiB**。当前处理连续记录；EDF+D/BDF+D、分段 SET、分卷 FIF、NWB-Zarr、`.cbin` 和分选后的神经元单元尚未支持。格式不决定模态，读取后需要确认。详见[文件要求](docs/file-formats.md)。

没有数据时，可先运行合成示例：

```bash
.venv/bin/python examples/headless_qc.py --output .local/demo
```

它生成 `.local/demo/synthetic.edf` 并运行完整性检查，也可将该 EDF 上传到质控台。它用于验证操作流程，不代表真实数据的检测准确性。输出目录须尚不存在。真实数据下载入口见[公开样例](docs/public-examples.md)。已配置的公开样本可从首页“示例数据集”直接打开，点击即看数据集报告，同页打开逐份结果，见[示例数据集说明](docs/example-datasets.md)。

## 模块与报告

| 阶段 | 模块 |
| --- | --- |
| 读取与确认 | M01 文件读取与结构核验；M02 数据画像与检查计划 |
| 质量检查 | M03 信号完整性；M04 频谱与干扰；M05 通道质量；M06 伪迹线索；M07 事件与时间 |
| 汇总与复核 | M08 分项评价；M09 报告与人工复核 |

模块独立存放在 [`src/ephys_qc/modules/`](src/ephys_qc/modules/)，提供 Python 和命令行接口，不依赖网页运行。算法、适配、调用与交接方式见[模块工具包](docs/toolkit.md)。

数据包层提供 **D01 文件完整性 → D02 个体一致性 → D03 数据集一致性 → D04 审核与复验**。在首页“我的数据”打开显式登记的个人数据集，确认范围后后台检查；总览显示文件齐备、资料问题、个体与记录信号结果，支持 HTML 汇总导出。“审核与复验”页签可记录处理意见、对比修正前后变化并下载 PDF；人工结论单独保存，不改写信号评分。检查核心位于 [`src/ephys_qc/dataset_qc/`](src/ephys_qc/dataset_qc/)，可独立通过 CLI/Python 调用。数据包目录由本机配置登记，尚不支持网页整包上传。见[配置与复现](docs/dataset-inventory.md)、[检查规则](docs/dataset-checks.md)。

读取后可补充滤波史；已滤除的检查频带记为未评。结果按“概览 / 问题复核 / 可视化”查看，候选联动原始波形与局部 PSD。数据集可预览后批量运行已确认记录，并按相同配置比较 EEG 报告。见[操作与适用范围](docs/design/eeg-workflow-v1.md)。

EEG 报告包含总览、完整性/工频/高频突发三个评分分项、通道与时段结果、候选波形和评分依据。整份记录在后台分段计算，报告保留实际覆盖和未评原因。

**评分 v0.2 是项目试行指标，尚未经专家校准。** 满分表示当前计分项未检出候选，不代表数据全面合格；缺项不补满分。其他模态目前提供基础描述报告，不套用 EEG 总分。详见[评分规则](docs/eeg-scoring.md)与[报告要求](docs/eeg-report.md)。

## 方法与扩展

默认安装包含 BrainElecQC、MNE-Python、autoreject、PyNWB 和 PDF 导出依赖。EEG 基础检测使用 BrainElecQC，平台负责统一读取、方法适用判断、模块调度和报告。

FASTER、SpikeInterface、FieldTrip、ASR、CleanLine、Zapline-plus 等研究扩展需要另外安装或配置，不随默认流程全部运行。详见[扩展方法安装与范围](docs/optional-methods-runtime.md)及[方法来源](docs/toolkit-sources.md)。

首页统一上传与已有数据目录。数据集总览可按个体/会话打开记录，无需再次上传；记录分项、检查范围、来源指纹和历史关联保留。整段计算覆盖不代表质量合格，不计算跨个体总分。

## 文档与开发

- [顶层设计 v1.0](docs/design/platform-v1.md)：统一工作台、数据层级、云端与本地执行及分阶段交付；设计基线，不表示云端功能已上线。
- [安装、配置与更新](docs/installation.md)
- [模块接口与独立调用](docs/toolkit.md) · [工作台 API](apps/workbench/README.md)
- [标准总则](docs/workflow-standards.md) · [EEG 技术规范](docs/qc-standards.md) · [检查词条](docs/eeg-checks.md) · [来源依据](docs/eeg-evidence.md)
- [实现与验证范围](docs/implementation-status.md) · [安装验收](docs/validation/local-install-20261103.md) · [待办](TODO.md)

开发检查另需 Node.js：

```bash
.venv/bin/python scripts/check_release.py
```

质控标准文档为项目草案，尚未经专家审核，不是已发布的行业或团体标准。本工具用于科研筛查与人工复核，不作临床诊断。字段字典的完整设计、跨数据评分比较与 Linxi 宿主接入仍在完善。

## 来源与许可

[本项目](https://github.com/sunyq19/DBCI-QC) · [雷佳欣 / BrainElecQC](https://github.com/Jlei61/BrainElecQC)

BrainElecQC 作为固定提交的外部依赖安装，不在本仓库复制分发。原始数据、个人配置和运行报告不随代码提供。本项目尚未指定许可证；第三方软件和数据按各自许可使用，见[第三方说明](THIRD_PARTY_NOTICES.md)。
