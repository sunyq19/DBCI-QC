# DBCI-QC

**模块化电生理数据质控工具集，附本地质控台。**

[模块协作页](https://sunyq19.github.io/DBCI-QC/) · [网页源码与部署](apps/flow-editor/README.md) · [English](README.en.md) · [模块接口](docs/toolkit.md) · [质控标准草案](docs/qc-standards.md) · [更新记录](CHANGELOG.md)

本次源码基线：**2026-11-08 / 1.0.0rc3.dev41**。本地版可安装运行，[共享演示版部署包](docs/deployment/demo.md)已提供：访客无需账号，共享“我的数据”，仅设一名管理员。部署进度见[准备清单](docs/deployment/cloud-readiness.md)。流程网页用于查看和共同维护模块说明，不承担原始数据质检计算。

上传本机文件，确认模态与通道，运行推荐检查，查看报告。算法模块可独立调用，网页用于试用、展示与人工复核。

当前开发版：**1.0.0rc3.dev41**。支持头皮 EEG，以及 ECoG、sEEG、Neuropixels 连续电压的基础描述检查。[ECoG / sEEG 基础方案](docs/ieeg-checks.md)包括完整性、持续平线、文件量程、频谱与触点统计，可选分组离群和原版 FieldTrip 跳变检查。ECoG / sEEG 默认提供可调权重的数值有效性与信号稳定性评分，相关方法合并计一次。EEG 报告提供试行评分、分项结果、候选位置与 PDF 下载。

[Neuropixels 首版规范](docs/neuropixels/qc-standards.md)固定连续电压的9项检查；AP有条件时推荐SpikeInterface通道离群，LF/LFP保留独立描述，报告展示数值有效性30%、通道状态70%的可调默认评分及候选。分选后unit、漂移与跨流同步尚未接入。

打开首页即可查看四类公开数据的缓存示例报告，无需先下载原始数据。配置检查时，点击流程图中的 M03–M07 展开子方法，查看推荐、适用条件与计分能力，逐项选择。选中任一子方法即启用所属模块，全部取消即关闭，没有独立总开关。EEG 默认三项等权计分，计分项和百分比权重直接显示在“02 质量检查”下方，随方法选择更新。

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

上传文件或打开“我的数据”后，可填写**质检名称**（如“推荐方案”“灵犀云方案”）。留空使用灰色提示的“文件名 · 检查范围 · 时间”。名称随报告和检查记录保存，便于对照同一数据的多次检查。

“我的数据”以**每次检查报告**为最小归档单位：报告右侧 **⋯ → 归档**，可独立恢复或彻底删除，包括同一方案的历次报告。“当前 / 归档”保留数据与方案层级，只显示各自的报告。删除单份报告清理该次检查的报告、图表与结果文件，保留输入数据及其他报告；数据行的“归档全部”仍可整组操作，“清空归档”会先确认范围。整组删除才会清理关联记录及独占上传副本，不删除外部原文件或其他数据仍引用的副本。运行中的任务暂不可归档或删除；归档不延长副本的 7 天保留期。

## 支持哪些文件

| 格式 | 提交方式 |
| --- | --- |
| EDF / EDF+、BDF | 单个 `.edf` 或 `.bdf` |
| BrainVision | `.vhdr`、`.vmrk`、`.eeg` 同目录打包为 ZIP |
| EEGLAB | 内嵌数据的 `.set`，或 `.set` + `.fdt` 打包为 ZIP |
| FIF | 单个 Raw `.fif` |
| NWB 2 / HDF5 | 单个 `.nwb`，读取后选择连续 ElectricalSeries |
| SpikeGLX | 一个 AP 或 LF 流的 `.bin` + `.meta` 打包为 ZIP |

**单文件最大 2 GiB，数据集总量最大 10 GiB**。一份记录及其配套文件合计不超过 2 GiB；单记录 ZIP 按解压后的大小核算。当前处理连续记录；EDF+D/BDF+D、分段 SET、分卷 FIF、NWB-Zarr、`.cbin` 和分选后的神经元单元尚未支持。格式不决定模态，读取后需要确认。详见[文件要求](docs/file-formats.md)。

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

**评分 project-weighted/1.2 是项目试行指标，尚未经专家校准。** 满分表示当前计分项未检出候选，不代表数据全面合格；缺项不补满分。ECoG/sEEG及Neuropixels采用各自的项目评分，不套用EEG判据。详见[评分规则](docs/eeg-scoring.md)与[报告要求](docs/eeg-report.md)。

## 方法与扩展

默认安装包含 BrainElecQC、MNE-Python、autoreject、PyNWB 和 PDF 导出依赖。EEG 基础检测使用 BrainElecQC，平台负责统一读取、方法适用判断、模块调度和报告。

FASTER、SpikeInterface、FieldTrip、ASR、CleanLine、Zapline-plus 等研究扩展需要另外安装或配置，不随默认流程全部运行。Neuropixels AP 推荐的离群筛查需要 SpikeInterface；未安装时该项未评，基础测量仍可运行。详见[扩展方法安装与范围](docs/optional-methods-runtime.md)及[方法来源](docs/toolkit-sources.md)。

首页统一上传与已有数据目录。数据集总览可按个体/会话打开记录，无需再次上传；记录分项、检查范围、来源指纹和历史关联保留。整段计算覆盖不代表质量合格，不计算跨个体总分。

## 文档与开发

- [在线演示版方案 v1.0](docs/design/demo-deployment-v1.md)：本轮部署范围；[原顶层设计](docs/design/platform-v1.md)保留为后续平台建设参考。
- [安装、配置与更新](docs/installation.md)
- [模块接口与独立调用](docs/toolkit.md) · [工作台 API](apps/workbench/README.md)
- [标准总则](docs/workflow-standards.md) · [EEG 技术规范](docs/qc-standards.md) · [检查词条](docs/eeg-checks.md) · [来源依据](docs/eeg-evidence.md)
- [实现与验证范围](docs/implementation-status.md) · [安装验收](docs/validation/local-install-20261103.md) · [待办](TODO.md)

开发检查另需 Node.js：

```bash
.venv/bin/python -m pip install -r tests/requirements-ui.txt
.venv/bin/python scripts/check_release.py
.venv/bin/python scripts/smoke_local.py
```

GitHub Actions 按上述安装流程从空白环境执行回归与独立启动检查。`smoke_local.py` 使用临时运行目录，核对首页、四类示例、PDF 和合成 EDF 检查；不读取个人配置。

质控标准文档为项目草案，尚未经专家审核，不是已发布的行业或团体标准。本工具用于科研筛查与人工复核，不作临床诊断。字段字典的完整设计、跨数据评分比较与 Linxi 宿主接入仍在完善。

## 来源与许可

[本项目](https://github.com/sunyq19/DBCI-QC) · [雷佳欣 / BrainElecQC](https://github.com/Jlei61/BrainElecQC) · [灵犀云 / GnosisNeuroDynamicSE](https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE)

BrainElecQC 作为固定提交的外部依赖安装，不在本仓库复制分发。原始数据、个人配置和个人运行报告不随代码提供；仓库仅附经检查的公开数据展示快照。本项目尚未指定许可证；第三方软件和数据按各自许可使用，见[第三方说明](THIRD_PARTY_NOTICES.md)。

评分在 **高级设置 → 评分与权重** 中配置。EEG默认三项；ECoG/sEEG默认数值有效性与信号稳定性；Neuropixels默认数值有效性与去重后的通道状态。总分按有效权重平均，受限项不计入。规则及边界见[评分规范](docs/eeg-scoring.md)。

Neuropixels的参与项目、去重与缺项处理见[评分规则](docs/neuropixels-scoring.md)。

### sEEG与Neuropixels基础检查补充

- sEEG：MNE平线、文件量程、原版MNE多窗工频检查；FieldTrip跳变与分组LOF可选。新方案默认权重为数值有效性30%、稳定性50%、工频20%。
- Neuropixels AP：几何齐全时默认调用SpikeInterface/IBL coherence+psd，保留dead/noise/out标签；缺少几何时使用既有MAD筛查。
- Neuropixels LF：来源探针几何齐全时调用neighborhood_r2，不使用AP高通。默认数值有效性30%、通道状态70%；同通道同窗候选取并集，受限项不计分。

均保留原版方法、候选位置、参数与来源。LOF需明确可比参考组，不默认跨脑区判坏；组织外候选默认不扣分。项目权重与阈值尚待专家审核。实际文件回放见[本次验证记录](docs/validation/voltage-expansion-20261109.md)。
