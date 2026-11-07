# 示例数据集

首页的示例统一以数据集为入口。点击 **打开数据集**，先看汇总，再从“记录”页查看报告或打开原记录继续检查，无需重新上传。

## 当前本机演示

| 示例 | 组成 | 格式 | 已有信号报告 |
| --- | --- | --- | --- |
| 头皮 EEG | 注意任务，2 位受试者各 1 份记录 | EDF | 2 / 2 |
| ECoG | 2 位受试者，各 3 份发作记录 | BrainVision | 6 / 6 |
| sEEG | 两个独立公开来源，各 1 份深部电极记录 | FIF、EDF | 2 / 2 |
| Neuropixels | 3 位受试者的 AP / LF 电压片段 | SpikeGLX | 3 / 3 |

以上是 2026-11-07 的本机验证快照：四个数据集均完成资料检查，13 份记录均有信号报告。报告数量是执行覆盖，不是合格率。

EEG 来源为 [OpenNeuro ds002034 v1.0.3](https://openneuro.org/datasets/ds002034/versions/1.0.3)；ECoG 来源为 [ds003029 v1.0.7](https://openneuro.org/datasets/ds003029/versions/1.0.7)。sEEG 使用 [MNE sEEG 样本](https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html) 和 [ds004100](https://openneuro.org/datasets/ds004100)。Neuropixels 来源为 [人类 Neuropixels 公开记录](https://zenodo.org/records/5899237)。具体提交、文件校验值和裁剪信息保存在每个示例的来源文件中。

Neuropixels 的三个片段分别为 Pt01 LF 400–420 秒、Pt02 AP 300–304 秒、Pt03 AP 60–62 秒。“全时长检查”指本地片段的全部时长，不代表完整上游记录。sEEG 的两个来源分别分组，AP 与 LF 分组；不将不同来源或频带自动视为可比较队列。

## 页面层级

```text
示例数据集
  └─ 数据集总览：资料检查、报告覆盖、需核对事项
       └─ 个体与记录：逐份报告、打开记录、批量检查
            └─ 单份报告：检查指标、异常证据、复核
```

- 首页不展示试行分数，不按分数排序。数据集汇总不计算跨个体或跨模态总分。
- 示例不会再次出现在“已导入数据”中；后者保留其他本机记录和历史。
- 缺件、信息不一致等控制案例归入“验证样例”。普通数据即使检查失败，也仍是普通数据。
- 原资料的差异和未评项照实保留。默认示例选用可读取数据；ds003029 的 umf004 sEEG 文件存在不足一个采样帧的尾部，保留为读取边界案例，未裁尾修补后冒充原件。

## 登记与复现

示例卡片由本机配置 `demo_examples` 中的 `kind: dataset` 条目决定，关联 `packages` 中的数据集；报告来自当前清单关联的最新任务。尚未生成报告时仍可打开数据集，失效来源会显示不可用。

已下载并登记 `attention-demo`、`ieeg-package`，且已有 sEEG、Neuropixels 公开样本目录时，可运行：

```bash
.venv/bin/python scripts/prepare_local_example_datasets.py \
  --config .local/workbench.json \
  --samples-root /path/to/测试数据
```

该脚本整理本地样本及来源清单，不下载数据、不改原件、不自动启动质检，也不覆盖内容已变化的示例文件。运行检查仍通过质控台的资料检查和记录检查入口完成。原始数据和本机运行报告不进入 Git；新克隆的仓库不会自带这 13 份报告。下载入口见[公开样例](public-examples.md)。

数据集页面只读取保存的执行摘要，不因打开首页而重算 EEG 评分。摘要缓存随结果文件变化失效；完整候选证据和单份报告保留。
