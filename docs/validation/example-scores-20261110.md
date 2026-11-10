# sEEG 与 Neuropixels 示例评分更新

日期：2026-11-10。

## 问题与修正

示例入口指向 11 月 7 日发布的静态报告，未包含后来加入的默认计分方案。
数据集总览也只读取执行状态，省略了已经保存的项目评分，并保留了“仅提供技术描述”的旧说明。

本次重新运行两份 sEEG、三份 Neuropixels 文件，保留原始报告。总览逐份显示本方案评分，记录报告展示分项、权重及检查依据；不合成跨模态的数据集总分。

Neuropixels 的“恢复推荐”修正为重新选择满足条件的 AP/LF 方法。普通配置仍尊重用户主动取消的选择。

## 实际结果

| 样本 | 分析范围 | 计分方案 | 综合分 |
| --- | --- | --- | ---: |
| HUP060 sEEG | 38 个深部触点，378 秒，60 Hz 工频配置 | seeg-basic-score/0.3 | 80.08 |
| MNE sEEG sample | 119 道，60.001 秒 | seeg-basic-score/0.3 | 80.40 |
| Pt02 AP | 384 道，4 秒公开片段 | neuropixels-voltage-score/0.2 | 97.72 |
| Pt01 LF | 384 道，20 秒公开片段 | neuropixels-voltage-score/0.2 | 51.93 |
| Pt03 AP | 384 道，2 秒公开片段 | neuropixels-voltage-score/0.2 | 99.64 |

sEEG 使用数值有效性 30%、信号稳定性 50%、多窗工频候选 20%；稳定性按有效子项权重汇总。
Neuropixels 使用数值有效性 30%、通道状态 70%；通道状态合并整窗恒值及适用探针检查，同一通道、同一分析窗不重复计算。
受限项不计入有效权重。分数表示当前项目规则的检测结果，不是经专家校准的临床标准。

HUP060 的原始通道表将头皮及 EKG 标签也声明为 SEEG，不能只信任该类型列。本次对照此前已核对的同一文件配置和内容指纹，限定到 38 个深部触点；工频按配套 JSON 的 60 Hz 设置。早期全通道试跑保留，但不作为最终示例。

“整份检查”指下载到本地的样本文件全长，Neuropixels 仍是上述短片段，不代表上游完整研究记录。

## 发布与验证

- 缓存清单记录每份报告的运行时间、评分版本、分项和有效权重，避免界面更新掩盖过期示例。
- 回归检查要求两份 sEEG、三份 Neuropixels 示例使用当前默认方案，实际报告和总览均有对应分数，综合分与有效分项的加权平均一致。
- 静态示例保留已保存的候选位置表，不加载依赖原始信号接口的空白检查器。
- 示例文件、图表及中英文报告链接通过自包含校验；在线版通过 012 原有服务发布，旧版本地址保留。

复验：`PYTHONPATH=src:tests .venv/bin/python -m unittest -q test_example_cache test_dataset_overview test_neuropixels_standard test_neuropixels_scoring test_ieeg_scoring test_recommendations`。
