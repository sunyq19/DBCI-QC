# 示例数据集

首页的示例统一以数据集为入口。点击 **查看报告**，直接阅读检查范围、主要发现和逐份结果；无需进入多层管理页面。

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
示例数据集 → 数据集报告（检查范围、主要发现、逐份结果）
                       └─ 单份报告 ← 返回数据集报告
```

- 首页及数据集报告不展示跨个体、跨模态总分，不按试行分数排名。
- “我的数据”默认空，只展示新上传记录或明确登记的个人数据；旧开发记录仍保留，可通过历史链接访问。
- D01 核对应到文件与读取状态；D02 核对个体资料、通道表、单位、采样率和事件；D03 只按声明的比较组核对。独立来源、原始/派生、AP/LF 分组。
- EEG 信号检查按条件启用完整性、频谱、通道与伪迹方法。ECoG/sEEG/Neuropixels 当前为完整性、频谱和接触点描述，不直接套用 EEG 判坏阈值。
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

该脚本整理本地样本及来源清单，不下载数据、不改原件、不自动启动质检，也不覆盖内容已变化的示例文件。运行检查仍通过质控台的资料检查和记录检查入口完成。原始数据和完整运行证据不进入 Git；仓库自带四类数据集的展示快照与 13 份记录报告，可直接浏览。下载入口见[公开样例](public-examples.md)。

发布命令：`.venv/bin/python scripts/publish_example_cache.py --config .local/workbench.json`。快照目录为 `apps/workbench/example-cache`，随云端服务一起部署；不用再提供 NAS 路径。快照仅由显式发布更新，个人数据报告仍按原服务维护。

单份 HTML 报告读取已保存结果，不在打开时重算 EEG 分数。非 EEG 的展示整理只使用分窗摘要与已存波形，保留运行时原始报告。页面提供打印 / PDF 入口；仍需浏览器视觉验收。
