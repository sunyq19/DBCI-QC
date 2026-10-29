# 本地模块化工作台

工作台仅监听 `127.0.0.1`，无需登录。浏览器界面、HTTP 接口、模块调度、算法适配分别维护。新工作台默认端口为 `8769`；旧工作台的 `8768` 与历史任务保持独立。

## 启动

新安装请先按[仓库安装说明](../../README.md)准备运行环境，再以 [workbench.minimal.json](workbench.minimal.json) 创建 `.local/workbench.json`，填写本机 Python 解释器和仓库外运行目录的绝对路径。最小配置不预登记数据，可直接在界面提交本机文件。`.local/` 由 Git 忽略，克隆仓库不会包含已有配置、样例文件或运行结果。

配置完成后，在仓库目录运行 `python3 scripts/run_local.py`。加 `--open` 可以在系统浏览器中打开；`--status` 检查服务，`--stop` 停止本启动器记录的服务进程。停止功能使用 Linux 进程信息；其他系统尚未完成同等验收。

[workbench.example.json](workbench.example.json) 是可选的完整登记模板，包含5个数据集、11份记录的选道、默认窗口和来源指纹；使用前须另行准备数据并替换全部路径占位。执行环境须单独安装 BrainElecQC、MNE、autoreject 及所需依赖；[环境版本快照](../../profiles/tested-environment.json) 记录已测版本，不是完整依赖锁。第三方代码和数据的许可边界见[第三方声明](../../THIRD_PARTY_NOTICES.md)。

每个输入登记 `id`、`label`、`source_path`、`expected_sha256`、`dataset_id`、`profile_id`、`default_config`，并用 `provenance` 保存来源/版本/许可、`data_usage` 说明用途和标注边界。默认配置使用明确的 EEG 索引、辅助导联索引、时间范围、参考比较组；不根据名称自动推测。`selection.reference_indices` 是 ECG/EOG/EMG 辅助导联映射，采集参考构型和 `method_config.comparison_groups` 另行登记，不能混用。`metadata` 在服务启动时通过格式对应的读取器重新核验。

`annotation` 可登记睡眠分期、任务事件或临床事件的路径与格式。`expected_sha256` 核验实际使用的标注表；派生表另有 `source_path` 和 `source_expected_sha256` 指向原始标注。来源及派生说明应随数据保存。已有EDF下载、核验和登记草稿见 [公开数据示例](../../docs/public-examples.md)，新增格式见 [文件格式与读取模块](../../docs/file-formats.md)；准备脚本不会自动修改本机配置或创建运行任务。

## 文件分工

- `web/`：浏览器界面；向接口提交配置，显示服务返回的计划和状态。
- `server.py`：本机 API、任务队列、状态持久化、取消、结果访问。
- `worker.py`：每个任务独立运行，读取冻结请求，发送逐模块事件。
- `input_config.py`：兼容已有EDF技术头检查入口。
- `intake.py` / `uploads.py`：本机文件接收、受限ZIP配套包、信息提取和明确确认。
- `../../src/ephys_qc/readers/`：统一读取器注册、元数据、原生时间窗与单位接口；扩展格式不必重写HTTP或检测模块。
- `standards_page.py`：只读呈现技术规范及九个模块文档，提供层级目录、模块导航、下载和打印；只支持有限 Markdown 语法，转义原始 HTML，不引入额外依赖。
- `../../src/ephys_qc/`：适用性判断、依赖调度、计算适配与报告。

## 质控标准文档

首页导航“质控标准”打开 `GET /standards`，`GET /standards.md` 下载同一份 Markdown；`GET /standards/modules/M01` 至 `M09` 读取 `docs/modules/` 中对应文档，追加 `.md` 下载源文件。文档提供层级目录、标准条款与模块互链、上一/下一模块、返回质控台和 Alt+Q 快捷键。模块说明的“在质控台查看本模块”链接使用 `/#module-M01` 等精确白名单 hash，只打开模块弹窗，不选数据或启动任务。

`/standards-navigation.js` 提供同源目录、打印与返回交互，旧 `/standards-print.js` 保留兼容。返回入口仅在能保守确认仍处于最初文档历史项时使用浏览器后退，发生条款跳转等情况则可靠返回 `/`；Alt+Q 不在输入框、编辑内容或输入法组字期间触发。页面响应不缓存，不另存网页副本。技术规范规定要求，模块说明披露当前实现和参数；历史会议、审查和研发记录保存在归档文档，不列入对外规范正文。更新内容直接修改对应 Markdown；历史任务仍按自己的冻结配置解释，不被最新版文档覆盖。

英文规范与九模块路径在前面加 `/en`，只读取 `docs/en/` 对应文件。工作台语言按钮保存在本机浏览器，也接受 `/?lang=en`；切换不改变原始数据、填入值、后台配置或运行状态。用户文件名、原始通道标签、标注及证据JSON不翻译。英文文档需随中文同版本维护；已生成的报告和证据保持生成时原文。

## 数据提交和推荐

首页选择本机文件，初次加载不选择登记记录、不推荐、不规划。支持连续EDF/EDF+、BDF、BrainVision、连续EEGLAB、单文件FIF。服务复制到仓库外`intakes/<id>/`，保存原始上传和实际读取主/配套文件的SHA256。配套文件须同目录打包ZIP，一包仅一份记录，至多64个条目；上传与解压后总大小均不超过512 MiB。ZIP不得含越界路径、链接、重复文件名或加密内容。读取器复核真实文件结构，不接受服务器路径或URL。

右侧展示格式、通道数、时长、采样率、待确认模态、标注数及原始标签；保留通道名、索引、单位和文件声明。随后明确确认分析模态与通道角色，疾病、年龄、任务、参考及来源未知时保留未知。建议角色来自文件通道类型及名称线索，不证明电极位置。所选分析与辅助信号须有可换算电压单位、共用原生采样率，禁止自动上采样或按重名合并；BrainVision重名因当前后端限制明确拒绝。辅助导联每类最多一条。共同/联耳参考按用户声明建比较组；未知、混合或双极构型不自动成组。非头皮EEG可登记信息，但推荐返回unsupported，不生成可执行头皮EEG计划。

确认后保存`record.json`和`confirmation.json`，服务重启仍能恢复；完全相同的确认重试不会新建记录，变化的重复确认不能覆盖已有来源。主文件及所有配套文件在确认、读取和汇总时校验。原始注释可读取计数与描述，但未核实的事件含义不能自动进入M07，也不作为质量真值。FIF的采集起始样本和滤波声明保留；报告时间为当前文件起点秒，滤波声明不等于独立测量。

确认自己的文件后，界面自动请求推荐、采用默认方案并核验执行计划，用户查看摘要并点击“开始检查”。这些准备请求不会创建任务。文件确认前隐藏检查区；来源、流水线、历史及方法长说明按需展开。新文件选择会立即作废旧草稿、计划与结果视图；上传失败不恢复为可运行的上一份文件，过期读取或确认响应不能切回旧文件。高级设置中的人工修改保留；运行前仍用当前配置核验计划。疾病背景只改变解释提示，不直接改坏道阈值或总分。推荐规则和方法级门控是可独立调用的库功能。

## API 1.0

服务版本为 `modular-qc-api/1.0`，URL 前缀继续使用 `/api/v1`。

| 请求 | 用途 |
|---|---|
| `GET /api/v1/catalog` | 模块定义、已登记数据与场景 |
| `POST /api/v1/intakes` | 二进制本机文件，技术读取但不登记 |
| `GET /api/v1/intakes/{id}` | 已读取的技术头及待确认信息 |
| `POST /api/v1/intakes/{id}/confirm` | 明确确认角色和字段，登记为输入 |
| `POST /api/v1/recommend` | 按已登记输入及当前配置生成可解释推荐，不运行 |
| `POST /api/v1/plan` | 按数据和选择生成检查计划 |
| `POST /api/v1/jobs` | 用匹配的计划标识启动实际运行 |
| `GET /api/v1/jobs` | 运行历史 |
| `GET /api/v1/jobs/{id}` | 当前任务及逐模块状态 |
| `POST /api/v1/jobs/{id}/cancel` | 取消等待或运行中的任务 |
| `GET /api/v1/jobs/{id}/result` | 完成任务的结构化结果 |
| `GET /api/v1/jobs/{id}/report` | 完成任务的 HTML 报告 |
| `GET /api/v1/jobs/{id}/artifacts/{name}` | 报告登记的证据文件 |
| `GET /api/v1/jobs/{id}/log` | 执行日志 |

计划请求为 `{input_id, selected_modules, qc_config}`；运行请求在同一配置上增加 `plan_id`。修改配置后必须重新生成计划；服务端会复算标识并拒绝不一致的请求。任务不接受任意文件路径或任意 Python 代码。

上传请求使用`Content-Type: application/octet-stream`和URL编码的`X-Filename`，body为文件字节。确认请求为`{confirmed:true,modality:"scalp_eeg",reference_scheme,eeg_indices,reference_indices,context_tags,label?,source_note?}`。推荐请求为`{input_id,qc_config?}`，返回规则版本、推荐标识、`can_apply`、理由及可直接传给计划接口的`selected_modules/qc_config`；无运行资格时不提供可执行推荐。技术确认不能由疾病标签替代。

目录包含模块 `methods` 分项、输入 `data_tags`、背景选项 `context_tag_options`。当前有 18 项数据标签和 24 个方法分项（21 个已接入、3 个待接入）。界面根据目录中 `optional_extension` 与 `implementation` 动态生成开关，当前可选扩展如下。

| 扩展 ID | 所属模块 | 输出含义 |
|---|---|---|
| `mne_amplitude` | M03 | 相邻采样变化/平线候选，不是固定窗峰峰值检测 |
| `autoreject_global` | M03 | 探索性全局峰峰值阈值及固定分析段候选；分析段不自动等于任务试次 |
| `mne_bridge` | M05 | 电极桥接候选对，不是坏通道数量 |
| `mne_lof` | M05 | 通道离群候选，无伪迹时间定位 |
| `mne_muscle` | M06 | 跨通道高频时间候选，不能直接确认肌电来源 |

`qc_config.context_tags` 只接受 `disease/age_group/task`，不能覆盖采样率、辅助导联、参考构型等技术标签；未知背景保持未知，疾病标签不改变检测阈值。`method_config.extensions` 显式选择扩展 ID，参数保存在同级 `extension_parameters`。扩展所属模块与依赖会自动加入，固定入口/出口仍保留；不满足采样、参考或导联数条件时，计划给出阻断原因。细节见 [方法与标签](../../docs/eeg-methods-tags.md)。

计划保存 `data_tags`、`method_applicability`、`input_provenance`、`input_data_usage`、`input_metadata`、`input_modality`；输入和标注指纹参与 `plan_id` 计算，并随任务输入冻结。结果保存对应冻结来源与实际 `extensions` 状态、原因、候选类型和证据。计划就绪不表示已执行，执行完成也不表示信号正常。历史记录缺少的来源或标签显示未记录，不借用当前目录补全。修改时间窗口、方法或背景标签后，须重新预览计划。

每个任务保存 `request.json`、`job.json`、`result.json`、`run.log` 和 `artifacts/`。模块结果区分完成、部分完成、跳过、失败；界面另外区分“未选择”和“条件不满足而跳过”，跳过不会记成满分。候选摘要分别显示时间区间、通道、通道对和固定分析段；保留原始 JSON 供核对。原始记录保留，算法候选不自动删除数据。未建立校准标准前，总质量分为 `null`。

## 信息修订、查看与复核

`GET /api/v1/intakes` 返回已读完但尚未确认的文件，可恢复上传响应中断后的确认。`POST /api/v1/inputs/{id}/revisions` 创建独立输入版本；`base_revision` 必须与当前最新版本一致，冲突返回409。字段包括原确认字段、`preprocessing`及`annotation_mapping`；模态、参考、角色与来源解释不覆盖旧任务。

`GET /api/v1/inputs/{id}/waveform` 或 `GET /api/v1/jobs/{id}/waveform` 返回原始波形显示包络；后者用冻结输入。查询 `start_seconds`、`duration_seconds`（最多10秒）、`channel_indices`（逗号分隔源索引，最多16道）、`max_points`（8–2000）。包络保留桶内极值及其时序，不替代计算输入，也不暗中滤波或重参考。

`GET /api/v1/jobs/{id}/candidates` 将不同检测器的候选整理为源通道、原记录时间和证据定位。只到通道/整窗的指标明确标为whole_window，不伪造精确伪迹位置。`GET/POST /api/v1/jobs/{id}/review` 读写独立复核版本；提交`{expected_version,candidate_id,decision,reviewer,note}`，decision为accepted/rejected/uncertain。过期版本返回409；所有修改追加历史，原result.json不变。

`GET /api/v1/jobs/{id}/configuration` 返回冻结配置与`parent_job_id`。复制后可修改并重新规划，创建任务时保留父任务关系；复制本身不运行。`/?job={id}` 可直接返回任务；未提交配置保存在本机浏览器草稿中，不能替代冻结计划。

## 整份记录

`qc_config.scope` 为`window`或`recording`；后者使用`recording_options={window_seconds:120,expensive_methods:"skip"}`。每窗仍受120秒/256 MiB输入限制，按原生样本拆分，不跨文件声明的断点；短尾窗不丢弃。默认昂贵策略仅跳过重复的autoreject交叉验证，显式选择run才逐窗运行。分块可能改变滤波边界、频谱及阈值统计，不能宣称等同全记录一次建模。

冻结计划保存windows和coverage_plan，运行中保存recording-progress.json；每窗有独立request/result及报告。最终coverage分别列出完成、失败、运行中、未执行、来源缺口及逐模块范围。执行覆盖不是信号质量分；任何失败/未评都不会计为正常。取消保留已有证据，当前版本不自动续算中断窗，可复制配置新建任务。

## 当前范围

五类格式、明确的头皮EEG通道/参考配置，快速预检单窗最多120秒，整份检查按原生连续段拆窗；不接入EDF+D/BDF+D、epoched SET及split FIF。11份预登记记录来自5个数据集，包含同一受试者的多个运行，不能当成11名独立受试者；新增读取夹具另行记录。NWB、其他模态质控、跨窗候选自动合并、已校准总分、疾病专属判定、Linxi宿主插件属于后续工作。人工意见独立保存于 reviews.json，检测结果保持原样。睡眠、任务和发作标注不输入M03–M06检测器，也不是伪迹真值。实际运行与独立读取器核验范围见 [验收记录](../../docs/runtime-validation.md)。
