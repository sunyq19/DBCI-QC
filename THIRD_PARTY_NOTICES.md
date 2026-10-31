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
| PyNWB | 3.1.3 | 发行包 `License` 为 `BSD-3-Clause`；[上游仓库](https://github.com/NeurodataWithoutBorders/pynwb) |
| HDMF | 4.3.1 | 发行包 `License-Expression` 为 `BSD-3-Clause`；[上游仓库](https://github.com/hdmf-dev/hdmf) |
| h5py | 3.16.0 | 发行包 `License-Expression` 为 `BSD-3-Clause`，另含 HDF5 等随包组件许可；[上游仓库](https://github.com/h5py/h5py) |

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

## sEEG 与 Neuropixels 公开读取示例

新增来源与派生清单见[datasets/neuromodal-examples.json](datasets/neuromodal-examples.json)。数据和上游审计脚本仍保存在仓库外；本仓库提供下载/审计程序，不附波形或分选结果。

- MNE sEEG：`mne-tools/mne-misc-data`固定提交`d8ceb830cf0b05191dbde118e05f39a410567a8b`；保留仓库BSD-3-Clause许可和原始FIF字节，不将未核实的临床背景补成事实。
- Noise4Sam LF：[NeuralEnsemble/ephy_testing_data](https://gin.g-node.org/NeuralEnsemble/ephy_testing_data)固定提交`4304c8cdc0d345e8ca70ff7720c1087f911d1d5b`；上游CC-BY-SA-4.0。它是设备读取测试材料，不是带生理质量标签的数据集。
- 人脑Pt03 AP：[Paulk等Zenodo记录5899237](https://zenodo.org/records/5899237)，上游CC0-1.0。派生仅取原记录60–62秒的全部数字帧，保留原META与修改清单；未下载或验证完整13.54 GB原文件MD5。
- 独立数值核对使用[SpikeGLX官方Datafile Tools](https://github.com/billkarsh/SpikeGLX_Datafile_Tools)的固定版本readSGLX，下载在仓库外，不作为本包依赖或随包分发。生产读取器是本项目依据元数据约定实现的原生适配器。

ACSF AP和截短Noise4Sam AP因源文件声明不一致保留作拒绝负例，不修正其头信息以登记为正例。

## NWB公开文件与合成工程例

来源和派生清单见[datasets/nwb-examples.json](datasets/nwb-examples.json)，解释边界见[NWB样例文档](docs/nwb-testing.md)。全部数据及来源元数据保留在仓库外；准备程序不把这些记录重新发布到本仓库。

| 正式来源 | 固定版本 | 许可与本地用途 |
| --- | --- | --- |
| [DANDI 000019](https://dandiarchive.org/dandiset/000019/0.220126.2148) | 0.220126.2148 | CC-BY-4.0；人类ECoG原生NWB的明确约10秒派生片段，保留全部256道 |
| [DANDI 000165](https://dandiarchive.org/dandiset/000165/0.211118.1526) | 0.211118.1526 | CC-BY-4.0；Sumac小鼠LFP原文件，历史单位兼容与Units分层 |
| [DANDI 000230](https://dandiarchive.org/dandiset/000230/0.220506.1516) | 0.220506.1516 | CC-BY-4.0；时间戳回跳的真实来源负例 |
| [DANDI 001193](https://dandiarchive.org/dandiset/001193/0.240921.1006) | 0.240921.1006 | CC-BY-4.0；处理后高伽马数据，不作原始电压基准 |
| [DANDI 000021](https://dandiarchive.org/dandiset/000021/0.251116.2246) | 0.251116.2246 | CC-BY-4.0；Allen Neuropixels LFP边界例，来源另列Allen Institute使用条款 |

正式DANDI元数据中的作者、DOI、许可、发布时间与源对象修改时间随本地文件保留。人ECoG片段保留原始对象引用、样本/字节范围、电极映射和修改说明；未下载完整原文件，不宣称验证其全量摘要。其他4份完整原件与官方SHA-256和DANDI ETag一致。引用或允许的再分发应保留适用署名、许可及派生说明，不能把项目软件许可套用到来源数据。

两个合成NWB使用本项目生成的固定数值，结构参照[PyNWB官方细胞外电生理教程](https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html)。它们用于多流、单位转换、电极表映射和Units边界测试，不是下载的真实实验，也不增加独立临床证据。


## 2026-10-31 可选研究运行环境

新增MNE-FASTER 1.2.2（BSD-3-Clause）、SpikeInterface 0.104.2（MIT）适配，以及对外部固定版本clean_rawdata、CleanLine、Zapline-plus、FieldTrip和Octave signal的调用。源码不随本仓库分发；许可、文件级ASR UC使用说明、运行依赖及兼容层边界见[研究扩展运行规范](docs/optional-methods-runtime.md#6-来源与许可)。不要仅凭本仓库许可证推定依赖具有相同商用或再分发条件。
