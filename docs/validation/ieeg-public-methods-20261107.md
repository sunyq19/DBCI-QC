# 颅内公开方法与数据库核对记录

日期：2026-11-07。对应本地版本1.0.0rc3.dev36、基础方案ieeg-basic-recipe/0.2。

## 采用与边界

| 来源 | 核对结果 | 本次处理 |
| --- | --- | --- |
| MNE / MNE-BIDS | 公开平线检视接口，适用于iEEG；支持通道及合并区间输出 | 保持原版调用，50 ms基础参数 |
| FieldTrip | 原版差分z值可产生时间候选，检测与删除分离 | 使用已安装原版Octave/MATLAB适配器；不把候选称为确定伪迹 |
| EDF | 文件标定端点有明确编码含义 | 新增文件量程端点平台；不声称它是硬件ADC饱和 |
| SciPy MAD | 公开稳健尺度函数 | 独立组装项目分组幅度候选规则；不是已发布临床标准 |
| BIDS / OpenNeuro | 规范字段与源标注；已有公开样本可验证读取和报告 | 保留源通道身份及标签；未知参考与分组不补造 |
| IEEG_Pipelines | 原版outlier_repeat的当前源码存在可复现的首通道漏检边界 | 不作为已接入或默认方法；本地留存核对源码 |
| ABCD论文 | 有明确训练型分类方案，但不能把论文阈值当作通用固定规则 | 作为后续候选；本次没有声称接入模型 |

## IEEG_Pipelines源码核对

仓库：[coganlab/IEEG_Pipelines](https://github.com/coganlab/IEEG_Pipelines)，MIT，核对提交`b2ad2c8ec842419f00db1c59af1373fbb75dce34`。

公开说明：[channel_outlier_marker](https://ieeg-pipelines.readthedocs.io/en/latest/references/ieeg.navigate.channel_outlier_marker.html)。该方法示例使用MNE的ECoG数据。源码先去趋势，再调用`ieeg.calc.stats.outlier_repeat`。

本次独立执行该提交的原函数，固定随机种子2，20道×2000样本，将第0道幅度乘100。参数sd=3、rounds=2：原顺序未返回候选；同一矩阵沿通道轴循环平移1行后返回第1道。其循环条件对索引数组做any，只有索引0时为false。结果证明该提交在此输入下不满足通道换序一致性；不代表所有历史版本或方法家族都无效。本项目未修改上游仓库、未把修补版冒充原版。

## ABCD与数据可得性

[ABCD原始论文](https://pmc.ncbi.nlm.nih.gov/articles/PMC12320219/)使用频谱和时域特征训练分类器，并以滑窗分类汇总通道。论文的数据声明为按请求提供；本次核对的论文页面未提供可直接安装的完整模型接口。未取得原模型及可复现部署条件前不列为平台已实现，也不套用其研究阈值给本地样本打分。

## 数据库规则的作用

[BIDS iEEG](https://bids-specification.readthedocs.io/en/stable/modality-specific-files/intracranial-electroencephalography.html)提供通道类型、单位、参考、分组、位置和status等字段的表达约定。它不等于信号好坏算法。

本地MNE pt1、MNE sEEG、OpenNeuro HUP064及HUP060提供真实运行范围。其中HUP样本的iEEGReference为n/a、未提供明确group列。不得将名字前缀当作已核实电极杆，也不得将发作事件当作噪声真值。

## 当前决定

基础方案固定技术检查和报告结构；条件方法明确触发字段；统计阈值保留项目版本和可配置参数。分组模块的数值与受限分支均测试，真实参考不足时只提供测量。正式标准仍需独立通道/区间标注及专家审核，工程跑通不等于已验证准确率。

执行规则见[颅内检查规则](../ieeg-checks.md)。运行验收另存`ieeg-methods-20261107.md`。
