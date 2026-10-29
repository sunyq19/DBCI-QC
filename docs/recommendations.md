# 基于数据条件的检查建议

`ephys_qc.recommendations.recommend(record, qc_config=None)` 根据已登记技术条件生成可解释、确定性的建议，再用现有 `build_plan` 核验最终选择。它不读取信号或标注文件、不检查文件是否现存、不运行算法、不创建任务，也不宣称 AI 最优或行业统一处方。

## 接口

输入与现有登记记录、QC 配置一致。规则版本为 `scalp-eeg-metadata-rules/1.1.0`。可执行建议须明确 `record.modality='scalp_eeg'`，且技术格式为 EDF/EDF+、BDF、BrainVision、EEGLAB 或 FIF；格式由对应读取器核验，不能凭扩展名推断。非头皮模态可登记提取信息，但本规则返回 `unsupported`。未知模态不会从 profile、通道名或临床背景补出。

返回的主要字段：

| 字段 | 含义 |
|---|---|
| `schema_version` / `policy_version` | 返回结构与确定性规则版本 |
| `recommendation_id` | 输入登记、当前配置、规则版本和建议计划的稳定指纹；JSON 对象键顺序不影响结果 |
| `status` / `can_apply` | `ready` 可应用建议；`needs_input` 需补足或纠正字段；`unsupported` 尚未接入该格式/模态 |
| `summary` / `reason` | 建议摘要与当前状态原因 |
| `selected_modules` / `qc_config` / `plan_id` | 可直接提交现有计划接口的完整建议；仅 `can_apply=true` 时有可用计划 |
| `recommended_methods` | 默认建议的方法，以及理由、现有适用性状态和参数 |
| `optional_methods` | 条件允许但需用户明确选择的探索方法；不是默认启用 |
| `blocked_methods` | 现有门槛阻断、标注登记不完整或尚未实现的方法 |
| `missing_fields` | 字段、理由和 `blocking`；`blocking=true` 阻止本次建议应用，非阻断缺失只限制相关能力 |
| `cautions` / `review_focus` | 技术限制和背景相关复核提示；不改变质量阈值 |
| `data_tags` / `method_applicability` | 最终推荐计划的原始标签与方法适用性，逐项等同 `build_plan` 返回值 |
| `plan_warnings` | 最终计划的原始提示 |
| `current_extensions` / `extension_selection_changed` | 当前扩展选择与建议之间是否发生变化 |
| `scope` / `quality_score` | 明确只使用登记元数据、没有读取信号或启动任务；质量分始终 `null` |

方法列表中的 `applicability` 是推荐/候选评估时的门槛状态；顶层 `method_applicability` 则严格对应最终建议计划。因此可选方法在列表中可以为 `ready`，而在最终计划中为 `not_selected`。`ready` 表示规则建议可应用，不表示方法已计算、数据合格或文件存在。

有效 JSON 缺少必要信息时返回结构化 `needs_input`。非 JSON、NaN 或无穷值抛出 `ValueError`，与计划器输入要求一致。字段缺失不会自动补选道、重参考、降低采样率或更换方法阈值。

```python
suggestion = recommend(record, current_qc_config)
if suggestion['can_apply']:
    body = {
        'input_id': record['id'],
        'selected_modules': suggestion['selected_modules'],
        'qc_config': suggestion['qc_config'],
    }
    # POST /api/v1/plan with body; its plan_id must match suggestion['plan_id'].
    # Applying a suggestion is not permission to start a job.
```

引擎在内部已经用同一配置构建最终计划。工作台默认在读取并确认本机文件后自动采用建议并核验计划，再显示简短方案供用户启动；初次打开不会替用户选示例，不要求连续点击生成、采用、预览。执行仍须通过明确的启动动作。高级设置中的人工修改不会被默认建议覆盖，运行前必须使用与当前配置匹配的计划。技术条件、选择、参数或背景变更会使旧建议和计划失效。

## 默认规则

| 模块/方法 | 规则 |
|---|---|
| M01、M02、M08、M09 | 沿用计划器固定入口、计划、汇总和报告 |
| M03 | 建议完整性检查 |
| M04 | 建议频谱描述；短窗和不可测频带如实保留未评 |
| M05 | 建议非空间描述及现有组门槛允许的分项；不创建参考组，不把未声明组提升为可比较组 |
| M06 | 现有 ECG、EOG 或高频方法至少一项 `ready/partial` 时建议；没有 EMG 的高频结果仍是探索线索 |
| M07 | 仅已登记支持格式且具有明确路径的睡眠、任务或临床事件表；不检查文件内容或硬件同步 |
| `mne_amplitude` | 条件允许时作为唯一默认增强；未明确参数时采用 `flat=0`、`peak=None` 的相邻差分平线检查 |
| `mne_bridge` / `mne_lof` | 满足现有参考、比较组、通道数及时长门槛时列为可选；双极、混合和未知参考不绕过阻断 |
| `mne_muscle` | 始终只列可选；未知滤波史时尤其只能解释为探索性高频线索 |
| `autoreject_global` | 始终只列可选；固定连续段不是任务试次，同窗口阈值候选不是独立验收指标 |
| RANSAC、local AutoReject、ICA/ICLabel | 尚未接入，不建议执行；无坐标时不从名称猜位置，有坐标也不将未实现方法变为可用 |

用户明确的选道、时间范围、参考比较组和方法参数会保留。建议会重新提出扩展选择集合，因此当前手动勾选的探索方法可能不进入默认建议；这一差异由 `current_extensions` 和 `extension_selection_changed` 明示。给出的默认阈值属于实现/研究配置，不是统一质量标准。

疾病、年龄和任务只改变 `review_focus`：例如睡眠波形和发作活动需要与伪迹区分，任务事件不等于动作伪迹。它们不会改变方法选择、阈值、选道或质量分。原始临床/任务/分期标注不进入本引擎的任何算法计算。

## 验证范围

`tests/test_recommendations.py` 使用标准库验证确定性、对象键重排、输入不变、缺字段、格式/模态边界、低采样率和辅助条件、未知参考、短窗、已有参数保留、背景标签不改阈值，以及建议与正式计划的一致性。

有本机 `.local/workbench.json` 时，测试读取其中八份公共记录的登记元数据，并禁止访问信号和标注文件。该测试覆盖推荐规则和计划往返，不代替真实信号计算，也不证明检测准确率。没有本机配置时，这一项明确跳过；其余使用人工元数据夹具。

运行：`PYTHONPATH=src python3 -m unittest discover -s tests -p test_recommendations.py -v`。
