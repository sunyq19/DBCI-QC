# EEG 示例问题定位同步

日期：2026-11-10。发布版本：`ceb24baca8ff4f45`。

## 原因与改动

示例发布器此前删除 `data-waveform-base`，EEG 报告因此只显示少量保存图片，无法启动当前问题定位界面。更新评分缓存不能解决这一问题。

本次在每个 EEG 示例版本中固定完整候选索引、通道身份和时间轴，使用与实际报告相同的检查项筛选、彩色标记、全屏及最多 15 道对照。只读示例接口按服务配置寻找对应公开原文件，校验内容指纹后按需读取波形；无需把数 GB 的算法中间文件搬到服务器。

有已保存候选的方法默认显示，与是否计分无关。通道整体结果单独列出，不标成时间区间。没有原文件的部署仍可查看固定候选与报告，明确说明波形未配置，避免显示不对应的旧图片。

本次不执行检测算法，不修改历史证据、计分配置及分数。全部 15 份缓存报告的评分清单与上一发布版一致。ECoG、sEEG、Neuropixels 示例仍保留静态候选表，本次未扩大其交互支持范围。

## 实际检查

| EEG 记录 | 保存的位置数 | 默认展示的方法数 |
| --- | ---: | ---: |
| 数据集 sub-01 | 1206 | 4 |
| 数据集 sub-02 | 1781 | 4 |
| 方案对照：推荐方案 | 1207 | 5 |
| 方案对照：灵犀云扩展 | 3059 | 9 |

- 本机与 012 均核对上述四份报告的索引，并实际请求 15 道、10 秒波形。返回通道身份、原始时间及内容校验均正确；每道显示点数不超过 2000。
- 本机通过 29 项 Python 回归检查；012 通过已部署的 28 项对应检查。覆盖缓存文件与链接、内容指纹不匹配拒绝、缺少原文件、通道/时间限制、候选范围与默认选择。
- 前端状态检查覆盖候选组合、全屏、15 道上限，以及无原文件时保留位置筛选且不发无效波形请求。
- Chrome 实际打开 012 的 EEG 示例，检查完整候选筛选、15 通道全屏显示；另检查灵犀云示例的多类标记、通道对照及时间移动。

012 沿用已登记的两份 ds002034 公共 EDF，未复制或开放用户私有记录。源文件位置通过 `example_review_sources` 配置，仓库快照不包含原始波形及机器绝对路径。部署前备份位于服务器 `updates/eeg-example-review-20261110/backup`，旧缓存版本保留。

复验：

```bash
PYTHONPATH=src:apps/workbench:tests .venv/bin/python -m unittest -q test_example_cache test_example_review test_waveform_explorer test_finding_locations
node tests/check-waveform-explorer.mjs
node tests/check-finding-filters.mjs
QC_EXAMPLE_OFFLINE=1 node tests/check-finding-filters.mjs
```
