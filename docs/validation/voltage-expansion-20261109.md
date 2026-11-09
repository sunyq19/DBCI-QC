# sEEG 与 Neuropixels 原版方法接入验收

日期：2026-11-09；代码版本：1.0.0rc3.dev41。项目试行，尚未完成专家标注校准。

## 1 方法与范围

| 方法 | 上游版本 | 默认用途 | 计分 |
| --- | --- | --- | --- |
| MNE spectrum_fit 原版检测内核 | MNE 1.13.2 | sEEG工频；ECoG可选 | 命中完整通道窗比例；sEEG默认20% |
| MNE find_bad_channels_lof | MNE 1.13.2 | 确认参考和比较组后的可选触点筛查 | 候选通道比例，并入稳定性子项 |
| IBL coherence+psd | SpikeInterface 0.104.2 | 有来源几何的AP | dead/noise按来源通道并集；out默认不计 |
| neighborhood_r2 | SpikeInterface 0.104.2 | 有邻居的LF/LFP | 与整窗恒值按来源通道并集 |

使用ProbeInterface 0.4.2解析来源探针坐标。LF原版read_spikeglx会忽略LF acquired IDs，本项目改用原版read_imro解析原文件IMRO表和探针部件号，再按来源LF偏移映射；没有根据通道名编造坐标。LF检查副本明确跳过300Hz高通。

MNE工频私有内核有签名核验，并保存上游版本和实现散列。原版过滤结果被丢弃，不修改输入。工程分块与计分由本项目提供，不声称是上游统一质量标准。

## 2 本地真实样本

sEEG：MNE公开sEEG样例（119触点、60.001秒片段），以及OpenNeuro ds004100的HUP060（按已确认选择的38触点、378秒）。HUP原JSON声明60Hz，因此该方案只检查60Hz，并包含已有FieldTrip跳变方法。

Neuropixels：公开人脑NP1数据Pt03 AP 2秒、Pt02 AP 4秒、Pt01 LF 20秒，每份384个神经通道，排除数字同步字。来源为[Paulk等公开数据](https://zenodo.org/records/5899237)。检查的是本地已声明片段，不代表整场实验。

| 样例与方案 | 本地文件时长 / s | 新方法分项 / 100 | 综合分 / 100 | 本地运行ID |
| --- | ---: | ---: | ---: | --- |
| sEEG MNE · 多窗工频基础方案 | 60.00127418658234 | 1.9808 | 80.3962 | `61650fbc8a0643c4a36fcf7a257be825` |
| sEEG HUP060 · 工频与跳变方案 | 378.0 | 0.4759 | 79.7582 | `ea1e5407ad35441485fdffc65145f6c9` |
| Neuropixels Pt03 AP · IBL通道检查 | 2.0 | 99.4792 | 99.6354 | `7ded2d80294241fb802b97ce47a2811c` |
| Neuropixels Pt02 AP · IBL通道检查 | 4.0 | 96.7334 | 97.7134 | `c06f38a1929c4832a4f68d6197db3785` |
| Neuropixels Pt01 LF · 邻域一致性 | 20.0 | 33.5938 | 53.5156 | `8f86bc4d1b3a4c5ab02abf09380cfd0b` |

AP Pt03检出2个候选通道；Pt02两个分析块分别检出12、14个。LF Pt01检出255/384个低邻域一致性候选，阈值未为改善分数而调整。这不是255道经专家确认的坏道；高候选比例及上游警告随证据保留。

sEEG工频命中率高，说明显著窄带证据广泛存在，不能据此断言工频幅度大、设备故障或整份数据不可用。多窗方法只纳入完整4秒窗；MNE样例剩余约3.996秒、HUP末尾2秒不进入工频分母，其余基础扫描仍覆盖完整本地文件。

分项按保存的原始分子分母独立复算一致。sEEG默认30/50/20；Neuropixels默认30/70。权重可调、缺项退出；同来源通道在同一窗口的NP候选取并集。

## 3 尚未覆盖的验证

- 分组LOF完成合成离群信号与原版输出一致性测试；现有真实样本参考/比较组证据不足，未强行启用，尚未完成真实数据验证。
- 不包括探针长期漂移、跨流同步、spike sorting或分选后unit质量。
- 上游默认阈值和本项目权重均未经过专家校准；不同模态、不同处理史的总分不能直接排名。

## 4 自动检查

86项针对性测试及223个子测试通过。覆盖原版方法输出一致性、原始电压不变、声明滤除频率不补满分、缺少几何/参考时退出、LF通道映射及跨方法候选去重。合成LF样例触发上游“候选超过三分之一”警告，作为可解释边界保留。

协作页从当前代码生成56项方法（53项已接入，3项计划）；保持模块层级、评分角色、来源链接及版本合并规则。工作台和协作页的默认权重均来自代码源。

## 5 方法来源

[MNE工频](https://mne.tools/stable/generated/mne.filter.notch_filter.html) · [MNE LOF](https://mne.tools/stable/generated/mne.preprocessing.find_bad_channels_lof.html) · [SpikeInterface](https://spikeinterface.readthedocs.io/en/0.104.2/api.html)
