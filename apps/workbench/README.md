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

当前实现：1.0.0rc3.dev4。NWB 2/HDF5支持范围、真实来源和边界例见[NWB接入样例](../../docs/nwb-testing.md)。单位表只展示其存在，不能计作连续通道或声称已完成unit质控。

首页选择本机文件，初次加载不选择登记记录、不推荐、不规划。支持连续EDF/EDF+、BDF、BrainVision、连续EEGLAB、单文件FIF、NWB 2/HDF5连续ElectricalSeries，以及已支持探针的SpikeGLX AP/LF单流。后者须将同名`.ap.bin/.ap.meta`或`.lf.bin/.lf.meta`打包ZIP；一次不同时提交AP和LF。服务复制到仓库外`intakes/<id>/`，保存原始上传和实际读取主/配套文件的SHA256。配套文件须同目录打包ZIP，一包仅一份记录，至多64个条目；上传与解压后总大小均不超过512 MiB。ZIP不得含越界路径、链接、重复文件名或加密内容。读取器复核真实文件结构，不接受服务器路径或URL。

右侧展示格式、通道数、时长、采样率、待确认模态、标注数及原始标签；保留通道名、索引、单位和文件声明。随后明确确认分析模态与通道角色，疾病、年龄、任务、参考及来源未知时保留未知。建议角色来自文件通道类型及名称线索，不证明电极位置。所选分析与辅助信号须有可换算电压单位、共用原生采样率，禁止自动上采样或按重名合并；BrainVision重名因当前后端限制明确拒绝。辅助导联每类最多一条。共同/联耳参考按用户声明建比较组；未知、混合或双极构型不自动成组。已接入模态按已确认信息进入各自路线，其他信号仅保留读取信息，不生成错配计划。NWB多流须先选择一个ElectricalSeries，流选择与输入版本、计划及报告一起冻结；NWB不自动证明电极位置。

确认后保存`record.json`和`confirmation.json`，服务重启仍能恢复；完全相同的确认重试不会新建记录，变化的重复确认不能覆盖已有来源。主文件及所有配套文件在确认、读取和汇总时校验。原始注释可读取计数与描述，但未核实的事件含义不能自动进入M07，也不作为质量真值。FIF的采集起始样本和滤波声明保留；报告时间为当前文件起点秒，滤波声明不等于独立测量。

确认自己的文件后，界面自动请求推荐、采用默认方案并核验执行计划，用户查看摘要并点击“开始检查”。这些准备请求不会创建任务。文件确认前隐藏检查区；来源、流水线、历史及方法长说明按需展开。新文件选择会立即作废旧草稿、计划与结果视图；上传失败不恢复为可运行的上一份文件，过期读取或确认响应不能切回旧文件。高级设置中的人工修改保留；运行前仍用当前配置核验计划。疾病背景只改变解释提示，不直接改坏道阈值或总分。推荐规则和方法级门控是可独立调用的库功能。

## API 1.0

服务版本为 `modular-qc-api/1.0`，URL 前缀继续使用 `/api/v1`。

| 请求 | 用途 |
|---|---|
| `GET /api/v1/catalog` | 模块定义、已登记数据与场景 |
| `POST /api/v1/intakes` | 二进制本机文件，技术读取但不登记 |
| `GET /api/v1/intakes/{id}` | 已读取的技术头及待确认信息 |
| `POST /api/v1/intakes/{id}/stream` | 用`{stream_id}`选择NWB中列出的可用连续流，仅用于尚未登记的接收文件 |
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

上传请求使用`Content-Type: application/octet-stream`和URL编码的`X-Filename`，body为文件字节。确认请求为`{confirmed:true,modality:"scalp_eeg"|"ecog"|"seeg"|"extracellular",reference_scheme,eeg_indices,reference_indices,context_tags,label?,source_note?,selected_stream_id?}`。推荐请求为`{input_id,qc_config?}`，返回规则版本、推荐标识、`can_apply`、理由及可直接传给计划接口的`selected_modules/qc_config`；无运行资格时不提供可执行推荐。技术确认不能由疾病标签替代。NWB确认须携带与当前接收状态一致的`selected_stream_id`；已登记记录不能由此接口覆盖信号选择，检查其他流须重新提交文件。

目录包含模块 `methods` 分项、输入 `data_tags`、背景选项 `context_tag_options`。头皮EEG目录现有29个方法分项（21个已接入、8个待接入）；其他模态按各自目录展示。新增候选及接入边界见[补充调研](../../docs/qc-methods-review-20261031.md)。界面根据目录中 `optional_extension` 与 `implementation` 动态生成开关，当前可选扩展如下。

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

七类格式，头皮EEG及ECoG/sEEG/Neuropixels连续电压描述路线；快速预检单窗最多120秒，整份检查按原生连续段拆窗。不接入EDF+D/BDF+D、epoched SET及split FIF。预登记数据包含头皮EEG、同一ECoG观测的两种格式、sEEG FIF、NP1人脑AP派生片段及设备测试LF。不能将格式表示或设备测试夹具当作独立临床受试者。NWB-Zarr、任意细胞外记录的通用质控、分选后单元质量、探针漂移、多模态联合、跨窗候选自动合并、已校准总分、疾病专属判定和Linxi宿主插件属于后续工作。人工意见独立保存于reviews.json，检测结果保持原样。睡眠、任务和发作标注不是伪迹真值。实际运行与独立读取器核验范围见[验收记录](../../docs/runtime-validation.md)。

## 模态目录与导航

`GET /api/v1/catalog?modality=scalp_eeg|ecog|seeg|extracellular`返回该模态的`modules`、`inputs`、`method_domains`，以及`active_modality`、`modalities`、`workflow`和`overview_url`。默认仍为头皮EEG。`workflow.groups`提供图示分组，`default_selected_modules`提供初始选择；每模块`documentation_url`指向对应模态文档，`selectable:false`表示当前不能启用。

首页统一使用`/`，`?job=<id>`定位任务，`&lang=en`选择英文。上传前不选择模态；`GET /api/v1/inputs`列出全部已登记输入，与可执行方法目录分离。旧`modality`地址参数保留兼容，不作为输入证据。选择记录/任务后按已确认或冻结信息加载内部目录，方法浏览筛选不改分析配置。

上传响应中的`suggestions.modality`仅为建议，依据另列于`suggestions.modality_evidence`，包含`status`（file_declared/unknown/mixed）、`source`、`reason`与按源索引列出的`channel_groups`。只有可靠文件声明可以提出模态，默认类型或名称不构成解剖位置证据。建议不自动注册或执行；多组记录须明确本次范围，缺条件的方法由推荐说明。

通用规范入口为`/standards/overview`；ECoG适用规则为`/standards/ecog`，模块为`/standards/ecog/modules/M01`至`M09`，英文加`/en`。报告返回原任务，不改写冻结报告文件。

sEEG规范位于`/standards/seeg`，Neuropixels规范位于`/standards/neuropixels`；模块与英文页沿用相同子路径结构。Neuropixels内部使用`extracellular`标识，当前支持已核验SpikeGLX AP/LF或有明确Neuropixels设备证据的NWB连续ElectricalSeries，不等于支持所有细胞外数据。路线标识为`neuropixels-voltage/2`，标签为“Neuropixels 电压”。

SpikeGLX读取器严格核验保存通道映射、探针与IMRO、逐道标定、原生时钟和声明文件长度/哈希；数字同步字保留为bits，不参与电压质控。NP1公开AP/LF已独立读回；NP2 type21/24仅有合成测试。新路线的M03–M05复用描述量计算核；M06不开放。数据准备与验收入口见[多模态接入设计](../../docs/multimodal-extension.md)。
