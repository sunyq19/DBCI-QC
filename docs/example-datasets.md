# 示例数据集

首页的示例统一以数据集为入口。点击 **查看报告**，直接阅读检查范围、主要发现和逐份结果；无需进入多层管理页面。

## 当前公开示例（2026-11-13）

8 个数据集示例，共 21 份记录。每个入口均包含资料核对、逐份信号报告、分项及方案综合分。分数属于对应检查方案，不用于跨模态排名。

| 示例 | 组成与范围 | 格式 | 固定来源 |
| --- | --- | --- | --- |
| EEG · 注意任务 | 2 位受试者，各 1 份记录 | EDF | [ds002034 v1.0.3](https://openneuro.org/datasets/ds002034/versions/1.0.3)，CC0 |
| EEG · 睁眼静息 | sub-001 / sub-002，完整记录，灵犀云方案 | SET + FDT | [ds004584 v1.0.0](https://openneuro.org/datasets/ds004584/versions/1.0.0)，CC0 |
| EEG · 睡眠多导 | SN061 / SN062，整夜 EEG、辅助导联及睡眠分期 | EDF | [HMC v1.1](https://physionet.org/content/hmc-sleep-staging/1.1/)，CC BY 4.0 |
| ECoG · 临床发作 | 2 位受试者，各 3 份记录 | BrainVision | [ds003029 v1.0.7](https://openneuro.org/datasets/ds003029/versions/1.0.7)，CC0 |
| ECoG · 语音任务 | EC9-B15 / GP31-B1，完整 NWB 连续电压 | NWB | [DANDI 000019 v0.220126.2148](https://dandiarchive.org/dandiset/000019/0.220126.2148)，CC BY 4.0 |
| sEEG · 临床发作 | HUP060 / HUP112，各 1 份发作记录，同一研究 | EDF | [ds004100 v1.1.3](https://openneuro.org/datasets/ds004100/versions/1.1.3)，CC0 |
| Neuropixels · 人类 AP / LF | 3 位受试者的公开电压片段，AP / LF 分组 | SpikeGLX | [Zenodo 5899237](https://zenodo.org/records/5899237)，CC0 |
| Neuropixels · 小鼠 LFP | 2 只小鼠，各取一个连续 60 秒片段 | NWB | [DANDI 000021 v0.251116.2246](https://dandiarchive.org/dandiset/000021/0.251116.2246)，CC BY 4.0 |

这些是明确选取的公开子集，均不代表完整原研究。sEEG 不再混合 MNE 样本和 HUP 数据；每位受试者保留原来的触点配置，不要求不同个体电极数量或位置相同。HUP 通道表将部分头皮及 EKG 导联也记作 SEEG；本例按来源电极表选取有定位坐标的植入触点，保留这些触点原有的 good/bad 标签，未根据检测分数选道。

人类 Neuropixels 的三个片段分别为 Pt01 LF 400–420 秒、Pt02 AP 300–304 秒、Pt03 AP 60–62 秒。小鼠 LFP 为 Allen 上游已处理的连续电压，只裁剪源文件前 75000 个采样点，保留样本、时间戳和电极映射，不额外滤波或重采样。60 秒为近似时长，精确范围见来源记录。“样本全长检查”不表示检查了完整上游记录。

睡眠分期、发作标注和实验事件用于背景及时间核对，不是伪迹真值。缺少独立通道表、重复会话或满足条件的片段时，对应检查仍列明未评理由；不补造元数据、不为获得低分而调阈值。

## 页面层级

```text
示例数据集 → 数据集报告（检查范围、主要发现、逐份结果）
                       └─ 单份报告 ← 返回数据集报告
```

- 首页及数据集报告不展示跨个体、跨模态总分，不按试行分数排名。
- “我的数据”默认空，只展示新上传记录或明确登记的个人数据；旧开发记录仍保留，可通过历史链接访问。
- D01 核对应到文件与读取状态；D02 核对个体资料、通道表、单位、采样率和事件；D03 只按声明的比较组核对。独立来源、原始/派生、AP/LF 分组。
- EEG 信号检查按条件启用完整性、频谱、通道与伪迹方法。ECoG/sEEG/Neuropixels 使用各自基础方案与可用扩展；受限项退出计分，不直接套用 EEG 判坏阈值。
- 原资料的差异保留：EEG 配套表存在重复 `REF` 名称；ECoG 文件头与表格存在 nV/uV 标注差异。缺少配套表或没有重复记录的检查，按类型折叠列示，不假装通过。
- Neuropixels 相邻恒值可能来自量化；不将恒值定位数量直接解释为坏道或数据不可用。

## 登记与复现

发布时由本机配置 `demo_examples` 中的 `kind: dataset` 条目决定，关联 `packages` 与已完成任务。发布脚本生成固定快照；首页直接嵌入快照目录，打开报告不读取原始样本，也不等待个人数据目录。

已下载并登记 `attention-demo`、`ieeg-package`，且已有 sEEG、Neuropixels 公开样本目录时，可运行：

```bash
.venv/bin/python scripts/prepare_local_example_datasets.py \
  --config .local/workbench.json \
  --samples-root /path/to/测试数据
```

该脚本整理本地样本及来源清单，不下载数据、不改原件、不自动启动质检，也不覆盖内容已变化的示例文件。运行检查仍通过质控台的资料检查和记录检查入口完成。原始数据和完整运行证据不进入 Git；仓库自带 8 个数据集的展示快照与 21 份记录报告，可直接浏览。下载入口见[公开样例](public-examples.md)。

发布命令：`.venv/bin/python scripts/publish_example_cache.py --config .local/workbench.json`。快照目录为 `apps/workbench/example-cache`，随云端服务一起部署；不用再提供 NAS 路径。快照仅由显式发布更新，个人数据报告仍按原服务维护。

单份 HTML 报告读取已保存结果，不在打开时重算 EEG 分数。非 EEG 的展示整理只使用分窗摘要与已存波形，保留运行时原始报告。页面提供打印 / PDF 入口；仍需浏览器视觉验收。

## 本次扩充与验收

`prepare_eight_datasets.py` 下载固定来源的 EEG、sEEG 和语音 ECoG；`prepare_allen_demo.py` 准备可追溯的 LFP 裁剪。原始文件、来源收据、标注和检查清单保留在各自样本目录，完整数据不进入 Git。

`build_eight_dataset_release.py` 在隔离的运行目录中调用普通读入、推荐与质检流程。发布前核对每份报告的来源指纹、覆盖时长、分项和综合分，以及图表资源和候选定位接口。仅复制完成的公开运行；未完成的任务不会替换线上示例。

缓存包含中英文报告、图表、EEG PDF 和各模态的候选位置索引。交互波形需要服务端通过 `example_review_sources` 配置对应公开源文件；只部署报告快照不会自动下载原始信号。具体安装与检查命令见项目 README。
