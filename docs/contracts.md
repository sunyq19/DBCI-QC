# 数据与模块接口约定

状态：本页描述通用数据与模块约定；当前可调用的 Python/CLI 合同见[模块工具包](toolkit.md)，HTTP 合同为 `modular-qc-api/1.0`，见[工作台 API](../apps/workbench/README.md)。旧工作台的 `qc-api/1.0` 与 `qc-result/1.0` 保持独立，没有把旧任务重新解释为新结果。

适用性先写入计划节点的 `ready/partial/skipped + reason`；执行结果使用 `completed/partial/skipped/failed`，并保留子方法状态与未评原因。`partial` 表示模块部分检查可评，不能等同于质量不合格。工作台已支持独立版本化人工复核；算法结果保持 `review_status=pending`，不被人工决定覆写。统一评分尚未校准，`score.value=null`。

## 数据说明

每批数据登记来源地址或提供方、版本与文件指纹、许可与访问条件、原始实验、受试者分组、设备、导联、参考、采样率、处理史及配套文件。

标签应单独说明：任务事件、睡眠阶段、发作区间、坏道、伪迹区间或人工质量评级；每种标签记录标注者/方法、覆盖范围、复核状态和时间单位。任务或疾病标签不自动等于质量标签。来源无法核实的资料保留待确认状态。

Python/CLI 工具包接受本机文件路径，显式确认后冻结来源与配置。面向网页的 HTTP 任务请求仍使用登记 ID，不能把任意服务器路径或可执行命令直接当输入。两类入口共用读取器、规划器与计算模块。

## 模块声明

| 字段 | 含义 |
| --- | --- |
| module_id / method_id / version | 职责模块与具体算法版本分别记录 |
| input_requirements | 所需信号、元数据、辅助通道与先前产物 |
| applicability | 可执行条件及缺失条件的处理 |
| dependencies | 必需的计算依赖；仅显示时依赖的材料另列 |
| parameters / parameter_sources | 实际参数与来自论文、实现默认值或项目校准的依据 |
| outputs | 指标、通道和时间范围、证据文件、单位 |
| validation_status | 未验证、工程核验、合成验证、独立真实标签验证等证据状态 |

## 运行计划与状态

计划应记录输入版本、配置指纹、分析时段、通道选择、参考比较组、方法版本和每个适用性决定。计划在执行前冻结。

任务状态拟沿用 `queued/running/completed/failed/cancelling/cancelled/interrupted`。模块执行状态用 `pending/running/completed/failed/skipped`；适用性另用 `applicable/not_applicable/insufficient_information`，避免把计算是否成功和数据是否适用混为一谈。

例如：缺少 EOG 的方法可为 `skipped + insufficient_information`；有 EOG 但计算异常为 `failed + applicable`；计算成功未发现显著影响为 `completed + applicable`。是否参与评分另有 assessment 状态，不从 completed 自动推断合格。

## 结果与人工复核

结果至少保留：

- 记录、输入指纹和已检查的真实范围。
- 方法、参数和软件环境版本。
- 指标原值、单位、阈值、分母、异常通道与原始样本区间。
- 可解释的支持证据和未评/失败原因。
- 分项、规则版本、覆盖及总分可用性。
- `review_status`、独立人工决定及理由；未经人工复核的结果保持待复核。

通道使用稳定 ID，显示名与原始索引同时保留。时间候选应可定位到原始样本，不依赖图上的近似位置。重叠异常按定义合并后计算占比。

## 第三方适配

BrainElecQC 的方法输出经适配映射到上述结构。先固定具体提交或安装包哈希与依赖环境；每次升级同时检查参数含义、字段映射、示例输出和评分变化。现阶段没有复制第三方核心代码。

Linxi 接入负责宿主参数、任务生命周期及结果引用。工作台通过统一任务接口访问；算法使用者不应被迫安装不需要的宿主插件。
