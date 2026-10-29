# Third-Party Notices

本文件记录主要外部依赖和数据来源的许可边界，不替代上游许可正文，也不授予本项目或第三方内容的使用、修改或再分发许可。以下版本对应[已测环境快照](profiles/tested-environment.json)，不是完整的传递依赖清单。

## BrainElecQC

工作台通过 Python 接口调用独立安装的 [BrainElecQC](https://github.com/Jlei61/BrainElecQC)，已核验版本为 `0.1.0`，来源提交为 `f007d829712d1b824cda79409d181a3313d6a78f`。

BrainElecQC 源码和安装包未随本仓库分发。对上述提交及已安装发行包的核查尚未找到明确再分发授权：未发现上游 LICENSE/NOTICE/COPYING 文件，包元数据也未声明许可证。部署者须单独取得该依赖，并向权利人确认适用权限；本仓库不为其声明开源许可证。

## 主要科学计算依赖

| 依赖 | 已核验版本 | 许可记录与上游来源 |
|---|---|---|
| MNE-Python | 1.13.2 | 发行包 `License-Expression` 为 `BSD-3-Clause`；[上游仓库](https://github.com/mne-tools/mne-python/) |
| SciPy | 1.17.1 | 发行包含许可全文；许可条件及随包组件声明以上游为准；[上游仓库](https://github.com/scipy/scipy) |
| NumPy | 2.4.6 | 发行包 `License-Expression` 为 `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`；[上游仓库](https://github.com/numpy/numpy) |
| FOOOF | 1.1.1 | 发行包 `License` 为 `Apache License, 2.0`；[上游仓库](https://github.com/fooof-tools/fooof) |
| autoreject | 0.5.1 | 发行包 `License` 为 `BSD-3-Clause`；[上游仓库](https://github.com/autoreject/autoreject) |

这些依赖由用户另行安装，本仓库不附其源码或发行包。再分发包含依赖的环境、容器或安装包时，应另行核对所含全部组件的许可、版权和声明保留要求；主项目许可证不能覆盖第三方内容。

## 数据与读取样例

本仓库提供来源清单、配置模板和下载程序，不附原始记录、标注文件或样例 ZIP。数据许可与软件许可分别适用；具体来源、版本、署名和派生说明见[公开数据示例](docs/public-examples.md)及[读取样例清单](datasets/reader-samples.json)。

| 数据集 | 已登记版本 | 来源声明的许可 |
|---|---|---|
| [EEG Motor Movement/Imagery Dataset](https://physionet.org/content/eegmmidb/1.0.0/) | 1.0.0 | Open Data Commons Attribution License v1.0 |
| [HMC Sleep Staging Database](https://physionet.org/content/hmc-sleep-staging/1.1/) | 1.1 | CC-BY-4.0 |
| [OpenNeuro ds002034](https://openneuro.org/datasets/ds002034/versions/1.0.3) | 1.0.3 | CC0 |
| [Sleep-EDF Database Expanded](https://physionet.org/content/sleep-edfx/1.0.0/) | 1.0.0 | Open Data Commons Attribution License v1.0 |
| [CHB-MIT Scalp EEG Database](https://physionet.org/content/chbmit/1.0.0/) | 1.0.0 | Open Data Commons Attribution License v1.0 |

MNE-Python 读取夹具具有仓库许可，但未找到逐文件独立数据许可；MNE testing-data 中所选 EEGLAB 和 FIF 文件的独立许可尚未确认。其来源和用途说明保留在清单中，不据此推定可随本项目再分发。下载和使用时应核对相应来源条件；引用或允许的再分发应保留适用的署名、许可链接及修改说明。
