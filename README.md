# DBCI-QC

**电生理数据质量控制工具集与本地工作台。**

DBCI-QC 以数据为入口，将文件读取、信息确认、方法选择、模块执行和人工复核组织为可追溯的质控流程。项目面向多模态电生理数据扩展，当前可执行的质量检查聚焦**头皮 EEG**。

当前版本：**1.0.0rc1（候选版）**。提供中英文工作台、五类文件读取、九个顶层模块及结构化报告。版本变化见 [CHANGELOG](CHANGELOG.md)，实现与验收范围见[运行验收记录](docs/runtime-validation.md)。

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

模块内进一步区分通用、条件和可选方法。当前可选扩展包括 MNE 相邻采样变化/平线、电极桥接、LOF 通道离群、高频线索，以及 autoreject 全局阈值估计。各模块页面列出输入、输出、依赖、参数、方法来源及限制；完整目录见[方法与数据标签](docs/eeg-methods-tags.md)。

## 文件支持

| 格式 | 提交方式 | 当前范围 |
| --- | --- | --- |
| EDF / EDF+ | 单个 `.edf` | 连续波形记录 |
| BDF | 单个 `.bdf` | 连续记录，保留原生采样流 |
| BrainVision | `.vhdr`、`.vmrk`、`.eeg` 同目录打包 ZIP | 完整配套记录 |
| EEGLAB | 内嵌数据 `.set`，或 `.set` / `.fdt` 配套 ZIP | 连续数据 |
| FIF | 单个 `.fif` | 单文件 Raw 数据 |

上传文件及 ZIP 解压后总量上限均为 **512 MiB**；一包对应一份记录。EDF+D/BDF+D、分段 EEGLAB、分卷 FIF 和 NWB 尚未纳入当前流程。格式不决定模态；读取到其他模态信息不代表已支持其质控。详细约定见[文件格式与读取模块](docs/file-formats.md)。

## 安装与启动

已验证环境为 **Linux、Python 3.11**。工作台无前端构建步骤；Node.js 仅用于开发检查。当前按源码目录运行，`pip install -e .` 只安装编排包，不会自动安装计算后端。

### 1. 获取项目与依赖

```bash
git clone https://github.com/sunyq19/DBCI-QC.git
cd DBCI-QC
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python -m pip install "brainelecqc[qc,readers,figures] @ git+https://github.com/Jlei61/BrainElecQC.git@f007d829712d1b824cda79409d181a3313d6a78f"
python -m pip install "mne==1.13.2" "autoreject==0.5.1" "h5io==0.2.5" "pymatreader==1.3.2"
```

BrainElecQC 为单独安装的外部依赖，不随本仓库分发。已测包版本见[环境记录](profiles/tested-environment.json)；该记录不是完整依赖锁。第三方使用与再分发边界见[第三方说明](THIRD_PARTY_NOTICES.md)。

### 2. 配置本机目录

```bash
mkdir -p .local
cp -n apps/workbench/workbench.minimal.json .local/workbench.json
```

编辑 `.local/workbench.json` 中两处路径：

- `python`：本项目 `.venv/bin/python` 的**绝对路径**。
- `data_dir`：仓库外的运行目录，例如 `/path/to/DBCI-QC-data/runtime`，用于保存上传副本、任务和报告。

最小配置不含预登记数据，可直接在工作台提交本机文件。需要固定示例时，再参考[完整登记模板](apps/workbench/workbench.example.json)；其中的路径须自行配置，原始数据不随代码提供。已有 `.local/workbench.json` 时保留原配置。

### 3. 启动工作台

```bash
python apps/workbench/server.py --config .local/workbench.json
```

浏览器打开 **[http://127.0.0.1:8769/](http://127.0.0.1:8769/)**，终端按 `Ctrl+C` 停止。服务仅监听本机地址，无需登录；提交文件保存到本机运行目录。

Linux 下也可用 `python scripts/run_local.py` 在后台启动；`--status` 查询状态，`--stop` 停止本启动器管理的服务。配置字段与 API 见[工作台说明](apps/workbench/README.md)。

## 报告与复现

每次任务保存输入版本、主文件及配套文件指纹、方法选择、参数、执行状态和软件环境。支持短窗预检与整份记录分块检查；整份检查分别报告已评、失败、未执行及来源缺口，分块计算不等同于全记录一次建模。

主要输出包括 `request.json`、`job.json`、`result.json`、`run.log` 和 `artifacts/`。人工复核另存版本化 `reviews.json`；复制配置重跑产生新任务，保留父任务关系。

仓库提供 5 个公开数据集、11 份记录的登记信息和数据准备脚本，覆盖静息、运动/运动想象、注意任务、睡眠及临床发作背景；另有多格式读取样例来源。数据和标注需按来源说明单独获取，见[公开数据示例](docs/public-examples.md)。记录数不代表独立受试者数，任务、睡眠及发作标注不作为伪迹真值。

## 验证与当前限制

在上述计算环境中安装 Node.js 后，可运行自动回归：

```bash
python scripts/check_release.py
```

自动检查覆盖读取边界、计划和模块契约、版本化修订、复核冲突、分块覆盖及界面状态。依赖本地样例配置的用例在新环境可能跳过；真实文件流程验收需按[验收记录](docs/runtime-validation.md)另行准备数据。自动检查不能替代浏览器人工走查。

当前结果用于科研数据筛查与人工复核，尚未完成独立专家标注下的检测准确率验证。**总质量分尚未校准，保持 `null`**。sEEG/ECoG 等其他模态质控、疾病专属判定、跨窗候选自动合并和 Linxi 宿主集成属于后续范围。技术规范为项目草案，不是已发布的行业或团体标准。

## 文档与开发

| 内容 | 入口 |
| --- | --- |
| 项目技术规范 | [头皮脑电数据质量控制技术规范](docs/qc-standards.md) · [English](docs/en/qc-standards.md) |
| 流程与接口 | [架构](docs/architecture.md) · [接口约定](docs/contracts.md) · [推荐规则](docs/recommendations.md) |
| 方法及依据 | [方法与标签](docs/eeg-methods-tags.md) · [来源核对](docs/toolkit-sources.md) |
| 数据与验证 | [公开示例](docs/public-examples.md) · [模块验证计划](docs/module-validation-plan.md) · [运行验收](docs/runtime-validation.md) |
| 版本维护 | [版本管理](docs/versioning.md) · [变更记录](CHANGELOG.md) |

工作台中的“质控标准”读取同一份文档源，模块详情可进入对应说明页。维护方法、参数或技术要求时，同步更新实现、模块文档和相关验证记录。

```text
src/ephys_qc/      读取器、适用性、计划、方法适配与报告
apps/workbench/   本地界面、HTTP API、任务与复核管理
docs/             技术规范、模块说明、依据与验证记录
datasets/         来源登记、格式样例清单与数据卡模板
profiles/         场景设计、实现覆盖与已测环境
tests/            工程与接口测试
scripts/          启动、数据准备及验收工具
```

## 方法来源与许可

[BrainElecQC](https://github.com/Jlei61/BrainElecQC) 提供首个 EEG 计算后端。DBCI-QC 在其上组织统一读取接口、数据描述、方法适用性、模块调度、追溯报告与人工复核，并接入 MNE、autoreject 等方法。原方法与本项目适配的职责、调用位置和论文来源分别记录于[来源核对](docs/toolkit-sources.md)。

本仓库当前尚未指定项目许可证；第三方代码与数据的许可分别适用，详见[第三方说明](THIRD_PARTY_NOTICES.md)。原始记录、私有标注、运行报告、本机配置和第三方安装包不纳入仓库。
