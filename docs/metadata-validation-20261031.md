# 字段字典 v1 来源核对记录

日期：2026-10-31 · 软件版本：1.0.0rc3.dev8 · 字典：metadata-fields/1。

本文件为维护与验证记录，不属于规范正文。这次核对验证字段能否忠实表达已有来源中的事实、缺项和冲突；没有运行新的质控算法，也没有完成新字段的上传/API接入。

## 1 真实来源与结果

| 样例 | 实际核对的资料 | 映射结果与保留边界 |
| --- | --- | --- |
| OpenNeuro ds007020 1.0.0，sub-PD1001，人类静息EEG | participants.tsv、来源README | 来源明确为人类临床记录；未提供年龄。疾病队列说明不自动变成该对象的诊断，PD文件名不作为疾病证据。 |
| OpenNeuro ds006890 1.0.0，monkeyb day09，猴ECoG | participants.tsv/json、iEEG侧车JSON、下载后的真实EDF文件头 | Macaca fuscata，F，9年；时间依据是实验开始，不能称为day09当天的精确年龄。EDF为196秒，侧车为195.047秒，保留冲突。 |
| DANDI 000165 0.211118.1526，Sumac06，小鼠LFP | NWB 2.4.0的Subject、Device、ElectricalSeries结构 | Mus musculus，F，P6.4M保留为6.4个月；没有显式年龄起点和时间声明，不套用新版本默认值。32道、274737样本、1000Hz。设备Neuronexus，不能归入Neuropixels。 |

猴EDF共51个存储信号，包含50个数值通道与1个注释信号；侧车各类通道计数合计49，ECoG明确32道。统计时应区分存储信号、数值通道与所选ECoG通道，不能把三者混称“通道数”。读取实际EDF使用originals目录；来源元数据目录中的209字节文件是指针，不能当波形解码。

猴年龄未明确起算事件，本次保留reference=unknown；小鼠源NWB未显式提供age.reference，本次也保留未知。科学解释可以记录外部规范的默认语义，但不得将其伪装为来源明确填写的事实。没有为三个对象自动生成“成年”标签。

[人类来源](https://openneuro.org/datasets/ds007020/versions/1.0.0) · [猴来源](https://openneuro.org/datasets/ds006890/versions/1.0.0) · [小鼠来源](https://dandiarchive.org/dandiset/000165/0.211118.1526)

## 2 可复核产物

- `specs/metadata-fields.v1.json`：35字段设计清单及版本。
- `examples/metadata/real-source-mappings.json`：3份局部映射，7个实际来源文件的相对路径、大小和SHA256。
- `scripts/audit_metadata_examples.py`：只读来源的样例核对脚本，需要h5py；不下载数据、不读取完整波形、不建立运行任务。
- `scripts/build_metadata_dictionary.py`：从字段清单生成中英文规范，支持`--check`检查漂移。

复现时将数据根目录设为既有“公开数据”目录，输出另选位置；源文件不写入Git：

```bash
python scripts/audit_metadata_examples.py --data-root /path/to/公开数据 --output /tmp/metadata-mappings.json
python scripts/build_metadata_dictionary.py --check
```

脚本只为这三个固定样例做语义明确的映射，不是通用BIDS/NWB导入器，也不声称覆盖全部35字段的真实数据验证。许可和实验背景沿用各数据集原始来源记录。

## 3 文档和接口边界

总则、字段字典、方法适用规则与实现说明各有独立中英文只读路由；网页与下载读取同一Markdown源。内部链接和锚点应可到达，模块条款编号保持兼容。

自动检查覆盖：字段生成一致性、来源映射保真、缺项/冲突、全部发布文档的内部跳转、只读路由、语言切换、缺失源文件及符号链接越界拒绝。本轮完整回归通过435项Python测试，以及138项前端状态、29项语言切换、15项文档导航和12项静态布局检查；字段字典生成一致性检查通过。

服务重载到1.0.0rc3.dev8后，8个中英文公共文档页与8个原文下载通过HTTP核对；49份既有任务的ID和状态保持一致。没有重新运行或改写已有报告。

原有任务、算法、默认推荐、质量阈值及总分逻辑不变。浏览器视觉走查未执行；自动路由和静态检查不等于视觉验收。
