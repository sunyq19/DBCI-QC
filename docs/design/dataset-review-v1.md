# 数据集审核与复验 v1

2026-11-06 · `dataset-review/1` · 本地项目流程，医院验收规则待评审。

## 使用流程

资料检查 D01–D03 → 查看具体问题 → 记录影响与处理意见 → 确认本次结论 → 修正本地资料 → 重新检查并对比。

数据集界面分为总览、记录、审核与复验三个页签。总览回答资料有哪些问题；记录用于进入信号检查；审核页用于确认下一步和查看整改变化。细节默认折叠，不要求用户在同一屏理解所有模块。

## 模块边界

| 部分 | 职责 | 独立位置 |
| --- | --- | --- |
| D04 核心 | 证据绑定、处理校验、结论规则、复验差异 | `src/ephys_qc/dataset_qc/review.py` |
| 报告 | 同一结果生成中英文 HTML/PDF | `src/ephys_qc/dataset_qc/review_report.py` |
| 本地存储 | 追加审核版本、读取冻结基线、拒绝过期编辑 | `apps/workbench/package_reviews.py` |
| 接口 | 读取/保存审核及导出报告 | `apps/workbench/package_review_api.py` |
| 界面 | 按需加载、处理表单、报告入口、复验操作 | `apps/workbench/web/dataset-review.js` |

核心不依赖网页。日后接入其他界面或插件时，复用核心与报告契约。

## 输入与输出

输入为完成的 dataset-consistency 结果、冻结检查清单、可选基线结果及审核版本。输入数据不写回。检查 ID 由 D01–D03 提供；证据指纹覆盖规则、检查结果、相关文件指纹和记录主文件。处理意见只能绑定当前证据。

输出包含逐项处理、当前/建议结论、未评数量、变更分类和追溯。范围改变、项目未复查和明确消除分别呈现。新报告不继承上次最终结论。

保存通过 `expected_revision` 和 `result_hash` 校验。审核文件以排他方式追加，旧版本不覆盖；版本冲突返回 HTTP 409。`baseline_job_id` 必须属于同一数据集且已完成，提交复验时冻结其审核版本。

## 接口

- `GET /api/v1/package-jobs/{id}/review`：审核数据与历史。
- `POST /api/v1/package-jobs/{id}/review`：保存意见或明确确认结论。
- `GET /api/v1/package-jobs/{id}/review/report?lang=zh-CN`：HTML。
- `GET /api/v1/package-jobs/{id}/review/pdf?lang=zh-CN`：PDF；也支持 `en`。
- `POST /api/v1/package-jobs`：在原有请求上增加 `baseline_job_id`，开展复验。

## 当前限制

填写人自行声明；无身份认证、电子签章和云端多人权限。仍重新检查全部资料，不做增量调度。不修改信号评分，不把已记录意见的未评项算成通过。处理意见可能含个人信息，沿用本地保存；公共演示仅使用公开数据及明确标注的模拟意见。
