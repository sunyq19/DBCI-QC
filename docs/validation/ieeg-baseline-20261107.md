# ECoG / sEEG 基础方案执行核验

版本：1.0.0rc3.dev35；基础推荐：ieeg-basic-recipe/0.1；日期：2026-11-07。

## 方案

读取确认 → 数值完整性与 MNE 持续平线 → Welch PSD / 工频邻域功率 / 触点统计 → 报告。

沿用原生采样率与来源参考。MNE 使用真实 ECoG / sEEG 通道类型，精确平线最短 50 ms，峰值检测关闭，5% 用于通道和区间候选分流。M07 仅在已登记、核实事件表时推荐。本次四次运行未登记临床事件表，不宣称验证了发作识别。

## 实际记录

四份数据均以本地文件上传入口登记，沿用先前核对的分析触点；整份后台检查，每段最多 120 秒。保留来源标坏触点，没有为得到较好结果而剔除通道。

| 模态 | 公开样例 | 分析触点 | 已检查时长 | 非有限值 | 持续平线输出 |
| --- | --- | ---: | ---: | ---: | --- |
| ECoG | MNE epilepsy_ecog pt1，FIF | 89 | 269.08 s | 0 | 合并区间 269.000–269.079 s |
| ECoG | OpenNeuro ds004100 HUP064，EDF | 86 | 278.00 s | 0 | 合并区间 277.271–277.998 s |
| sEEG | MNE sample_seeg_ieeg，FIF | 119 | 60.001 s | 0 | 未检出平线候选 |
| sEEG | OpenNeuro ds004100 HUP060，EDF | 38 | 378.00 s | 0 | 合并区间 155.766–155.918 s、377.840–377.998 s |

四份记录的请求范围均完成，无失败的检查模块。M03 的相邻重复值详细位置仍可能达到存储上限，但完整计数和有限值扫描保留。报告不将这些两点相等区间称为持续平线；平线结果来自独立的 MNE 方法。

MNE 时间输出跨所选触点合并，不据此虚构具体通道。本次没有返回通道级平线候选。末尾短平线可能与采集停止、补齐或导出有关，需要查阅原始记录；本核验不确定其原因。未检出平线不代表没有其他质量问题。

## 接口与展示核验

- 四份记录均出现在“我的数据”，各自保留当前方案与历次运行。
- 四份报告及其引用的波形图片均返回 HTTP 200；报告有统一的四个同级区块：检查结果、问题定位、图表分析、报告详情。
- 颅内 PSD 读取 `psd.channels`，触点图读取 `M05_channel_description.json`；工频图绘制保存的窄带功率，不误显示为头皮检测命中率。
- 有平线候选时，图表默认选中对应分析窗口；图表保留实际时段说明。
- 全长 RMS 以有限样本数合并；峰峰值取各分析窗的最大值，明确区分整段全局峰峰值。
- 本机接口核验中报告约 27–56 ms，已缓存图表约 5–19 ms；仅为此次本机测量，不是云端性能承诺。
- DOM 模拟测试覆盖刷新中的禁用与加载反馈、重复点击、失败保留旧图、成功保留展开状态，以及“我的数据”的并发请求顺序。
- 浏览器仍因已保存的本机地址访问权限拒绝页面读取；本次没有浏览器截图或目视验收。

## 方法验证范围

数值测试将持续平线、短重复值和恒值通道注入合成数组，分别在 ECoG / sEEG 类型上调用原版 MNE，核对时间偏移、通道建议、未被修改的输入和计分输出。此测试证明适配行为，不证明真实临床坏道识别准确率。

PSD、工频邻域和 RMS 默认不设置质量阈值；MNE 两种候选比例提供可选计分接口，默认不生成总分。后续需要带人工标记的数据验证阈值、分段边界和不同参考构型。

## 来源

- [MNE epilepsy_ecog / OpenNeuro ds003029](https://mne.tools/stable/generated/mne.datasets.epilepsy_ecog.data_path.html)
- [MNE sEEG tutorial](https://mne.tools/stable/auto_tutorials/clinical/20_seeg.html)
- [OpenNeuro ds004100](https://openneuro.org/datasets/ds004100/versions/1.1.3)
- [MNE annotate_amplitude](https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html)
- [MNE-BIDS inspect_dataset](https://mne.tools/mne-bids/stable/generated/mne_bids.inspect_dataset.html)
