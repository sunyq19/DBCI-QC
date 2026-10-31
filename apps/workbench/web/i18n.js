/* QC Workbench UI localization. Data, JSON, input values and URLs are not translated.
 * Load before app.js (defer). Controls: data-language="zh-CN" or "en".
 * Explicit labels: data-i18n="key"; source values: data-i18n-skip / translate="no".
 * Only exact internal standards navigation paths receive a locale prefix.
 * No requests, analysis actions, innerHTML writes or form reconstruction occur here.
 */
(function (global) {
  "use strict";
  const STORAGE_KEY = "ephys-qc.language";
  const EVENT = "qc:languagechange";
  const pairs = `读取本机文件，生成检查报告。	Read a local recording and generate a QC report.
选择本机文件	Choose a local file
已选择文件	File selected
单个记录，或包含配套文件的 ZIP	A single recording or a ZIP with companion files
点击更换文件	Click to choose another file
基础方法	Core methods
按条件启用	Conditional methods
可选增强	Optional enhancements
输入、输出与依赖	Inputs, outputs and dependencies
← 查看所属模块	← Back to module
详情	Details
提取状态未记录	Extraction status not recorded
尚未提取	Not extracted
文件可能含事件；尚未映射到所选信号。	The file may contain events; they have not been mapped to the selected signal.
通道角色优先保留已声明类型，未声明时仅按名称提出角色建议；模态及参考仍须确认，不据名称推断疾病。	Declared channel types take priority. Names only suggest roles when types are undeclared; modality and reference still require confirmation. Disease is not inferred from names.
文件标注仅提取原始事件描述，不据此推断疾病、睡眠阶段或质量标签。	File annotations retain original event descriptions only; disease, sleep stages and quality labels are not inferred.
请先选择一个可读取的连续电压信号；Units表仅作内容识别，不进入波形质控。	Select a readable continuous-voltage signal first. Units tables are identified only and do not undergo waveform QC.
已核验SpikeGLX AP/LF或明确设备身份的NWB连续电压；保留源处理声明，不包含单元质量或跨流同步。	Verified SpikeGLX AP/LF or continuous NWB voltage with explicit device identity. Preserve source processing declarations; exclude unit quality and cross-stream synchronization.
核对SpikeGLX配套文件或NWB信号对象、探针声明与逐通道电压标定；保留处理史。	Check SpikeGLX companion files or NWB signal objects, probe declarations and per-channel voltage calibration; preserve processing history.
仅已核验设备的连续电压；不接收排序结果，不自动对齐多个信号或解释同步脉冲。	Continuous voltage from verified devices only. Sorting outputs are excluded; signals are not automatically aligned and synchronization pulses are not interpreted.
Neuropixels连续电压读取与来源核验	Neuropixels continuous-voltage reading and provenance checks
核验SpikeGLX或NWB所选信号，保留通道身份、电极映射、样本时钟及处理史。	Verify the selected SpikeGLX or NWB signal, preserving channel identity, electrode mapping, sample timing and processing history.
读取有明确设备身份的Neuropixels连续电压。	Read continuous Neuropixels voltage with explicit device identity.
SpikeGLX核对BIN/META及标定；NWB核对ElectricalSeries路径、单位、规则时钟、电极映射与设备声明。	For SpikeGLX, verify BIN/META and calibration. For NWB, verify the ElectricalSeries path, units, regular timing, electrode mapping and device declarations.
已支持的SpikeGLX AP/LF或NWB2/HDF5连续ElectricalSeries。	Supported SpikeGLX AP/LF or continuous ElectricalSeries in NWB 2 / HDF5.
本项目格式适配器；保留源标定及处理声明，不调用头皮流程。	This project's format adapters preserve source calibration and processing declarations without invoking the scalp EEG workflow.
SpikeGLX按量程与增益标定；NWB按conversion、channel_conversion、offset及明确单位标定为V。	SpikeGLX uses range and gain calibration. NWB uses conversion, channel_conversion, offset and explicit units to obtain volts.
SpikeGLX已用官方readSGLX核对；NWB通过h5py独立核对源切片及单位。	SpikeGLX was checked against official readSGLX. NWB source slices and units were independently checked with h5py.
冻结所选连续信号、源通道及样本坐标；保留NWB对象路径、探针、时钟和处理声明。	Freeze the selected continuous signal, source channels and sample coordinates; preserve the NWB object path, probe, timing and processing declarations.
已核验Neuropixels设备、单个SpikeGLX或NWB连续电压信号、时钟及电极映射。	Verified Neuropixels device, one continuous SpikeGLX or NWB voltage signal, timing and electrode mapping.
设备身份未知的细胞外记录、分选后spike/units、未选择的多流或同步数字通道。	Extracellular recordings with unknown device identity, sorted spikes or units, unselected multiple streams, or digital synchronization channels.
EDF/BDF 原生采样流	EDF/BDF native sampling streams
SpikeGLX · Neuropixels 原始流	SpikeGLX · Neuropixels raw streams
NWB · 连续电压流	NWB · Continuous-voltage streams
不支持 EDF+D/BDF+D；不同采样流不能隐式重采样。	EDF+D/BDF+D are unsupported; streams at different rates cannot be implicitly resampled.
主文件、MarkerFile 和 DataFile 须位于同一目录。	The main file, MarkerFile and DataFile must share one directory.
当前后端对重复通道名明确拒绝，不合并或静默改名。	The current backend rejects duplicate channel names; it does not merge or silently rename them.
只接入连续记录；外置 FDT 须在同一目录；不执行历史脚本或 ICA。	Continuous recordings only. External FDT files must share the directory; historical scripts and ICA are not executed.
只接入单文件原始记录；split FIF 暂不接入；保留非 EEG 通道类型。	Single-file Raw recordings only. Split FIF is unsupported; non-EEG channel types are preserved.
单个 AP 或 LF .bin 须配同名 .meta；当前接入 NP1 型号0及 NP2 型号21/24。	One AP or LF .bin requires its matching .meta. Supported models are NP1 type 0 and NP2 types 21/24.
不接入任意二进制、压缩 cbin、跨流自动同步或 spike sorting。	Arbitrary binary files, compressed cbin, automatic cross-stream synchronization and spike sorting are unsupported.
支持自包含 NWB 2 / HDF5 的连续 ElectricalSeries；多个可用流须明确选择。	Supports continuous ElectricalSeries in self-contained NWB 2 / HDF5 files. Multiple available streams require an explicit selection.
核验原生时钟、电压单位及电极映射；不接入不等距时钟、外部链接或 spike/unit 质控。	Verify native timing, voltage units and electrode mapping. Irregular timing, external links and spike/unit QC are unsupported.
NWB ElectricalSeries 缺少明确的电压单位；不能猜测单位。	NWB ElectricalSeries lacks explicit voltage units; units cannot be guessed.
NWB 时钟单位不是明确的秒；不能将其他时间单位直接当成秒。	NWB timing units are not explicitly seconds; other units cannot be treated as seconds.
NWB 样本数与采样时钟无法组成有效时长。	The NWB sample count and sampling clock do not define a valid duration.
NWB 内部链接循环或深度过大。	NWB internal links contain a cycle or exceed the depth limit.
NWB 连续流缺少规则采样时钟。	The continuous NWB stream lacks a regular sampling clock.
NWB timestamps 须与样本数一致且至少有两个数值。	NWB timestamps must match the sample count and contain at least two values.
NWB timestamps 数值精度不足，无法核验规则采样。	NWB timestamp precision is insufficient to verify regular sampling.
NWB 连续电压须为非空 time × channel 或一维数值数组。	Continuous NWB voltage must be a nonempty time-by-channel or one-dimensional numeric array.
NWB 流通道数必须在 1–4096 之间。	An NWB stream must contain 1–4096 channels.
NWB channel_conversion 必须为有限正数。	NWB channel_conversion values must be finite and positive.
NWB 电压校准超出数值范围。	NWB voltage calibration exceeds the numeric range.
NWB ElectricalSeries 缺少 electrodes 映射。	NWB ElectricalSeries lacks an electrodes mapping.
NWB electrodes 行索引必须与每个通道一一对应。	NWB electrode row indices must map to every channel.
NWB electrodes 行索引越界；不能把表 ID 当成行号。	NWB electrode row indices are out of bounds; table IDs cannot be treated as row numbers.
NWB ElectricalSeries 使用非规范单位拼写/量级；依据原始 data.unit 显式换算为 V。	NWB ElectricalSeries uses nonstandard unit spelling or scale; original data.unit explicitly determines conversion to volts.
NWB 读取窗口须位于明确选定的规则电压流内，输出仅为物理电压。	An NWB read window must remain within the explicitly selected regular voltage stream; output is physical voltage only.
NWB 读取通道须为不同的有效源通道 ID。	NWB read channels must have distinct, valid source channel IDs.
NWB 内部链接路径无效。	An NWB internal link path is invalid.
NWB 外部链接不受支持；请提供自包含 HDF5 文件。	NWB external links are unsupported; provide a self-contained HDF5 file.
NWB 内部链接目标缺失。	An NWB internal link target is missing.
NWB 虚拟数据集或外部原始数据存储不受支持。	NWB virtual datasets and external raw-data storage are unsupported.
NWB timestamps 存在缺失、回跳或重复，不能视为连续规则采样。	NWB timestamps contain missing, decreasing or duplicate values and cannot represent continuous regular sampling.
NWB timestamps 不等距或存在间断；当前不重采样。	NWB timestamps are irregular or contain gaps; resampling is not performed.
当前 NWB 读取器仅支持 NWB 2 / HDF5。	The NWB reader supports NWB 2 / HDF5 only.
NWB channel_conversion 必须与通道一一对应。	NWB channel_conversion must provide one value per channel.
NWB electrode ID 不是可追溯的整数或字符串。	An NWB electrode ID is not a traceable integer or string.
NWB ElectricalSeries 缺少可追溯的 HDF5 对象路径。	NWB ElectricalSeries lacks a traceable HDF5 object path.
NWB 电压校准发生数值溢出。	NWB voltage calibration overflowed.
NWB信号选择必须是文件中列出的对象路径。	The NWB signal selection must be an object path listed in the file.
请先选择一个可读取的NWB连续电压信号；Units不是连续波形。	Select a readable continuous NWB voltage signal first; Units are not continuous waveforms.
NWB所选信号尚未通过连续电压、规则时钟、单位和电极映射核验。	The selected NWB signal has not passed continuous-voltage, regular-timing, unit and electrode-mapping checks.
NWB信号已随记录冻结；切换信号须重新选择和确认记录。	The NWB signal is frozen with the record; changing it requires a new selection and confirmation.
请选择文件中列出的NWB信号。	Choose an NWB signal listed in the file.
已登记记录的NWB信号不可覆盖；请重新提交文件以检查其他信号。	A registered NWB signal cannot be overwritten; submit the file again to check another signal.
所选NWB信号不可读取，或不属于这份文件。	The selected NWB signal is unreadable or does not belong to this file.
NWB信号选择已变化，请重新核对当前信号后确认。	The NWB signal selection has changed; check the current signal before confirming again.
只有NWB记录接受信号对象选择。	Only NWB records accept a signal-object selection.
此 ElectricalSeries 位于处理结果容器；不是已核验的原始采集信号。	This ElectricalSeries is in a processing container; it is not a verified raw acquisition signal.
Neuropixels 电压	Neuropixels voltage
头皮 EEG · ECoG / sEEG · Neuropixels 电压	Scalp EEG · ECoG / sEEG · Neuropixels voltage
NWB：仅接入 NWB 2 / HDF5 中受支持的连续电压 ElectricalSeries；多流须选择一条，不拼接。Units 仅识别，不做波形质控。	NWB: supports selected continuous-voltage ElectricalSeries in NWB 2 / HDF5. Choose one stream; streams are not concatenated. Units are identified only, without waveform QC.
Neuropixels 接入受支持的 SpikeGLX AP/LF 与具明确设备证据的 NWB 连续电压，不评估已分选单元。单独 .eeg 不能上传。	Neuropixels accepts supported SpikeGLX AP/LF and continuous NWB voltage with explicit device evidence. Sorted-unit quality is not assessed. Standalone .eeg files cannot be uploaded.
当前接入受支持的 SpikeGLX AP/LF 与具有明确设备证据的 NWB 连续电压；不评估已分选单元。	Supported SpikeGLX AP/LF and continuous NWB voltage with explicit device evidence are accepted; sorted-unit quality is not assessed.
待选信号	Select a signal
选择信号	Select signal
选择连续电压流	Choose a continuous-voltage stream
当前信号	Selected signal
先选择信号，再确认模态与通道。	Select a signal, then confirm its modality and channels.
未找到可用的连续电压流。	No supported continuous-voltage stream was found.
信号列表与读取范围	Streams and read support
可读取	Readable
暂不支持	Unsupported
切换信号需重新读取文件并确认。	Read the file again and confirm it to change signals.
正在读取所选信号…	Reading the selected signal…
信号读取结果不完整，请恢复读取状态后核对。	The signal response is incomplete. Restore the intake and check its state.
信号已读取，请重新确认信息	Signal read. Confirm its information again.
信号未就绪，请重新选择或恢复读取	Signal is not ready. Select again or restore the intake.
请先选择可读取的连续电压流。	Choose a readable continuous-voltage stream first.
来源容器	Source container
信号频带	Signal band
已识别 Units 表。 Units 不属于连续电压流，不进行波形质控。	Units table identified. Units are not continuous-voltage streams and do not undergo waveform QC.
Neuropixels原始流基础检查	Neuropixels raw-stream basic checks
单个AP/LF流的完整性、频谱和逐通道统计；不含分选后单元质量。	Integrity, spectrum and per-channel statistics for one AP/LF stream; excludes sorted-unit quality.
本项目原生SpikeGLX标定；已用官方readSGLX独立核对公开NP1 AP/LF样例。	Native SpikeGLX calibration in this project; public NP1 AP/LF samples have been independently cross-checked using official readSGLX.
SpikeGLX须将同名.ap.bin/.ap.meta或.lf.bin/.lf.meta一起打包ZIP，不能单独提交META。	ZIP the matching .ap.bin/.ap.meta or .lf.bin/.lf.meta files together; a META file cannot be submitted alone.
请选择已支持格式；SpikeGLX的单流BIN和META必须一起打包ZIP。	Choose a supported format. The BIN and META of one SpikeGLX stream must be zipped together.
SpikeGLX配套缺失：META须对应同名AP或LF BIN。	A SpikeGLX companion file is missing: the META must match an AP or LF BIN with the same base name.
ZIP须包含唯一的EDF、BDF、VHDR、SET、FIF或SpikeGLX META主文件及其配套文件。	The ZIP must contain exactly one EDF, BDF, VHDR, SET, FIF or SpikeGLX META entry with its companion files.
SpikeGLX原始流读取与来源核验	SpikeGLX raw-stream reading and provenance checks
核验单个AP/LF二进制及META，保留原始通道身份与样本时钟。	Check one AP/LF binary file and its META, preserving original channel identities and sample timing.
读取已支持型号的Neuropixels原始AP或LF流。	Read a raw AP or LF stream from a supported Neuropixels probe model.
核对同名BIN/META、原始长度、保存通道映射、探针类型、逐道增益与firstSample；同步字独立保留。	Check matching BIN/META files, original length, saved-channel mapping, probe type, per-channel gain and firstSample; preserve synchronization words separately.
读取器明确支持的SpikeGLX AP/LF及完整配套META。	SpikeGLX AP/LF explicitly supported by the reader, with a complete companion META file.
裸BIN、压缩cbin、NIDQ、sorting/unit、未支持探针或不一致长度与标定。	A standalone BIN, compressed cbin, NIDQ, sorting or unit results, unsupported probes, or inconsistent length or calibration.
本项目原生int16读取器；依据SpikeGLX元数据校准，不调用头皮流程。	This project's native int16 reader calibrates from SpikeGLX metadata without invoking the scalp EEG workflow.
按imAiRangeMax / imMaxInt / 逐道gain校准为V；数字同步字保留bits且不参与神经信号指标。	Calibrate to V using imAiRangeMax / imMaxInt / per-channel gain. Digital synchronization words remain in bits and are excluded from neural-signal metrics.
SpikeGLX 文本头超过 4 MiB。	The SpikeGLX text header exceeds 4 MiB.
SpikeGLX 元数据存在无效或重复键。	SpikeGLX metadata contains invalid or duplicate keys.
SpikeGLX 保存通道子集无效。	The saved SpikeGLX channel subset is invalid.
SpikeGLX 保存通道范围倒置。	A saved SpikeGLX channel range is reversed.
SpikeGLX 保存通道子集须唯一、有序且与 nSavedChans 一致。	The saved SpikeGLX channel subset must be unique, ordered and consistent with nSavedChans.
SpikeGLX 保存通道超出采集通道范围。	Saved SpikeGLX channels exceed the acquired-channel range.
SpikeGLX 仅支持单流 .ap.bin 或 .lf.bin 与同名 .meta；不接入任意二进制文件。	SpikeGLX supports one .ap.bin or .lf.bin stream with its matching .meta file, not arbitrary binary files.
当前 SpikeGLX 仅接入 imec Neuropixels 流。	Only imec Neuropixels streams are supported by the current SpikeGLX reader.
当前仅支持 Neuropixels 型号 0、21、24；不会猜测未知型号的校准。	Only Neuropixels models 0, 21 and 24 are supported. Calibration is not guessed for unknown models.
SpikeGLX 保存或采集通道计数不一致。	Saved or acquired SpikeGLX channel counts are inconsistent.
SpikeGLX 文件名 AP/LF 与保存通道类型不一致。	The AP/LF filename designation conflicts with the saved channel types.
NP2 型号 21/24 不提供原生 LF 流。	NP2 models 21/24 do not provide native LF streams.
SpikeGLX 子集与 AP/LF/SY 计数不一致。	The SpikeGLX subset does not match the AP/LF/SY counts.
SpikeGLX ADC 范围与当前支持的探针型号不一致。	The SpikeGLX ADC range does not match the supported probe model.
SpikeGLX 数据字节数与元数据/完整采样帧不一致。	The SpikeGLX byte count does not match the metadata or complete sampling frames.
SpikeGLX 声明时长与采样帧数不一致。	The declared SpikeGLX duration does not match the sampling-frame count.
SpikeGLX imroTbl 型号或通道数不一致。	The SpikeGLX imroTbl model or channel count is inconsistent.
SpikeGLX imroTbl 条目格式不支持。	The SpikeGLX imroTbl entry format is unsupported.
SpikeGLX imroTbl 存在重复通道。	SpikeGLX imroTbl contains duplicate channels.
SpikeGLX imroTbl 未完整描述采集通道。	SpikeGLX imroTbl does not describe all acquired channels.
SpikeGLX snsChanMap 条目数不一致。	The SpikeGLX snsChanMap entry count is inconsistent.
SpikeGLX snsChanMap 与保存通道子集不一致。	SpikeGLX snsChanMap does not match the saved-channel subset.
SpikeGLX 通道名重复；不静默改名。	SpikeGLX channel names are duplicated; they are not silently renamed.
SpikeGLX LF 通道缺少对应 imroTbl 校准。	A SpikeGLX LF channel lacks its corresponding imroTbl calibration.
NP2 固定增益与声明值冲突。	The declared gain conflicts with the fixed NP2 gain.
SpikeGLX snsShankMap 与神经通道数不一致。	SpikeGLX snsShankMap does not match the neural-channel count.
SpikeGLX snsShankMap 条目无效。	A SpikeGLX snsShankMap entry is invalid.
SpikeGLX 读取窗口须位于一个原生连续段内。	A SpikeGLX read window must remain within one native continuous segment.
读取通道必须是不同的有效源通道 ID。	Read channels must use distinct valid source-channel IDs.
读取窗口超过 256 MiB 限制。	The read window exceeds the 256 MiB limit.
按注册读取器核对主文件与伴随文件指纹、格式结构、采样流与连续段。	Use registered readers to check main and companion file fingerprints, format structure, sampling streams and continuous segments.
已登记原始文件或配套文件组	Registered source file or companion-file set
支持连续EDF/BDF、BrainVision、EEGLAB与单文件FIF；只有已确认头皮EEG可执行本质控，结构可读不等于科学有效。	Continuous EDF/BDF, BrainVision, EEGLAB and single-file FIF are supported. This QC route requires confirmed scalp EEG; readable structure does not establish scientific validity.
单窗最多120秒；整记录按原生连续段分块；不自动重参考或跨采样流对齐。	Each window is at most 120 seconds. Whole-record checks use native continuous segments, without automatic re-referencing or alignment across sampling streams.
空间预测和插值尚未接入；桥接、LOF须单独选择；来源坏道标签不参与检测。	Spatial prediction and interpolation are not integrated. Bridging and LOF require explicit selection; source bad-channel labels are not used by detectors.
基础方法每组至少4道是当前实现门槛；扩展另有门槛，都不是国际共识。	The minimum of four channels per group is a requirement of the current basic implementation. Extensions have separate requirements; neither is an international consensus threshold.
任务事件TSV使用明确的event_name字段；支持登记的来源转换表，非通用BIDS解析器。	Task-event TSV files require an explicit event_name field. Registered source mappings are supported; this is not a general BIDS parser.
检测报告保持不变；人工意见在工作台独立留版本，不自动删除原数据。	Detection reports remain unchanged. The workbench stores versioned review decisions separately, without automatically deleting source data.
头皮EEG科研检查；准确率和总分仍需独立验证。	Scalp EEG research checks; accuracy and an overall score still require independent validation.
本项目	This project
SciPy: BSD-3-Clause；本项目许可见仓库	SciPy: BSD-3-Clause; see the repository for this project's license
SciPy及本项目	SciPy and this project
SciPy Welch 官方文档	Official SciPy Welch documentation
皮层表面触点基础描述；不迁移头皮判坏阈值。	Basic descriptions of cortical surface contacts; scalp rejection thresholds are not transferred.
深部触点基础描述；不推断电极杆邻接，不将病理放电判坏。	Basic descriptions of depth contacts. Electrode-shaft adjacency is not inferred, and pathological discharges are not classified as defective data.
电极杆、触点邻接、坐标和双极派生须有来源；不凭名称推断或跨杆比较。	Electrode shafts, contact adjacency, coordinates and bipolar derivations require documented sources; they are not inferred from names or compared across shafts.
核对SpikeGLX配套文件、探针声明、AP/LF原生流和逐通道电压标定；同步字保持独立。	Check SpikeGLX companion files, probe declarations, native AP/LF streams and per-channel voltage calibration; keep synchronization words separate.
仅已接入型号的原始单流；不接收排序结果，不自动对齐AP/LF或解释同步脉冲。	Only a single raw stream from a supported probe model is accepted. Sorted results are not accepted; AP/LF streams are not automatically aligned, and synchronization pulses are not interpreted.
仅已核验SpikeGLX单个原始AP/LF流；不包含spike sorting、单元质量或跨流同步。	Only a verified single raw SpikeGLX AP/LF stream is supported; spike sorting, unit quality and cross-stream synchronization are excluded.
冻结单个AP或LF流、源通道与原始样本坐标；保留探针和采样声明，不重参考或重采样。	Freeze one AP or LF stream, source channels and original sample coordinates. Preserve probe and sampling declarations without re-referencing or resampling.
AP与LF分别运行；采样相位补偿、漂移估计、spike sorting与单元质量未接入。	AP and LF run separately. Sampling-phase compensation, drift estimation, spike sorting and unit quality are not integrated.
AP高频包含神经放电；原始RMS和PSD不直接称为噪声。没有分选，不计算单元指标。	AP high-frequency activity includes neural firing; raw RMS and PSD are not directly labeled as noise. No sorting or unit metrics are computed.
已核验SpikeGLX探针型号、单个AP/LF流、电压标定与源通道。	The SpikeGLX probe model, single AP/LF stream, voltage calibration and source channels are verified.
任意其他细胞外格式、分选后spike/units、混合流或同步数字通道。	Other extracellular formats, sorted spikes or units, mixed streams, or digital synchronization channels.
仅原始单流描述；无spike sorting、单元指标、探针漂移或跨流同步判定。	Descriptions of a single raw stream only; no spike sorting, unit metrics, probe-drift assessment or cross-stream synchronization checks.
Neuropixels原始检查仅接入已核验SpikeGLX AP/LF流；未接入其他细胞外记录或已分选单元。	Raw Neuropixels checks accept verified SpikeGLX AP/LF streams only; other extracellular recordings and sorted units are not supported.
Neuropixels选道仅接受明确声明的神经电压通道；同步字不得进入分析。	Neuropixels analysis accepts explicitly declared neural voltage channels only; synchronization words must not enter analysis.
同步 / 数字通道（不分析）	Sync / digital channel (not analyzed)
同步 / 数字通道不能登记为分析信号或生理辅助导联。	Sync / digital channels cannot be assigned as analysis signals or physiological auxiliary channels.
头皮 EEG · ECoG / sEEG · Neuropixels AP/LF	Scalp EEG · ECoG / sEEG · Neuropixels AP/LF
ECoG / sEEG 与 Neuropixels 仅提供基础质控，不套用头皮 EEG 判坏阈值。	ECoG / sEEG and Neuropixels provide basic QC only; scalp EEG rejection thresholds are not applied.
SpikeGLX：每包仅一个 AP 或 LF 原始流，将同名 .bin 与 .meta 打包 ZIP；两类流不拼接、不混选。	SpikeGLX: ZIP one raw AP or LF stream with its matching .bin and .meta files. Streams are not concatenated or selected together.
Neuropixels 仅接入原始 AP/LF，不评估已分选单元；NWB 暂不支持读取，单独 .eeg 不能上传。	Neuropixels supports raw AP/LF only, not quality assessment of sorted units. NWB is not supported; a standalone .eeg file cannot be uploaded.
原始数据流	Raw stream
探针型号	Probe type
sEEG 触点	sEEG contacts
背景（可选）	Context (optional)
当前仅接入 SpikeGLX 原始 AP/LF；其他细胞外记录需另行核验。	Only raw SpikeGLX AP/LF is supported here; other extracellular recordings require separate validation.
质控台	QC Workbench
当前不支持此 EDF/BDF TAL 时钟布局：需要从记录时间0开始、覆盖文件头时长的单一连续段；这不表示文件必然损坏。	Unsupported EDF/BDF TAL clock layout: a single continuous segment must start at recording time 0 and cover the header duration. This does not necessarily mean the file is damaged.
本地处理	Local processing
质控模态	QC modalities
头皮 EEG · ECoG（基础质控）	Scalp EEG · ECoG (basic QC)
读取格式	File formats
读取后确认模态与通道，无需预选。	Confirm modality and channels after reading; no advance selection needed.
文件要求与支持范围	File requirements and support
BrainVision：将 .vhdr、.vmrk 和头文件指定的数据文件（通常为 .eeg）一起打包 ZIP。	BrainVision: ZIP the .vhdr, .vmrk and the data file referenced by the header (usually .eeg) together.
EEGLAB：连续记录 .set 可直接上传；有外置 .fdt 时一起打包 ZIP。	EEGLAB: upload a continuous .set recording directly; ZIP it with the external .fdt file when present.
FIF：仅支持单文件 Raw 记录；暂不支持拆分 FIF 或 epochs。	FIF: single-file Raw recordings only; split FIF and epochs are not supported.
EDF/BDF：暂不支持不连续记录 EDF+D / BDF+D。	EDF/BDF: discontinuous EDF+D / BDF+D recordings are not supported.
ZIP：每包一份记录，仅一个主文件；上传和解压后均不超过 512 MiB。	ZIP: one recording with one primary file per archive; both upload and extracted size must be within 512 MiB.
sEEG、细胞外记录尚未接入质控；格式可读取不代表该模态可分析。	sEEG and extracellular QC are not yet available; a readable format does not imply QC support for its modality.
NWB、Neuropixels 原生格式暂不支持读取；单独 .eeg 不能上传。	NWB and native Neuropixels formats cannot yet be read; a standalone .eeg file cannot be uploaded.
候选	Candidate
该记录未提供说明。	No description is available for this recording.
波形采用有界极值包络显示，不改变分析数据。同单位共用标尺并保留零基线；超范围显示会标记。候选不等于已确认伪迹。	Waveforms use a bounded extrema envelope without altering analysis data. Channels with the same unit share a scale and retain the zero baseline; clipped display values are marked. Candidates are not confirmed artifacts.
同单位共用幅度标尺	Shared amplitude scale for the same unit
以零为中心	Zero-centered display
显示裁切	Display clipped
显示起点位于数据间隙或有效段之外，请调整起点。	The display start is in a data gap or outside a valid segment. Adjust the start.
整份执行覆盖	Whole-recording execution coverage
任务已停止；上次正在执行的窗口按未完成显示。	The run has stopped. Previously running windows are shown as unfinished.
执行覆盖反映已计算时长，不是质量分数。	Execution coverage measures computed duration, not signal quality.
执行覆盖，非质量分数	Execution coverage, not a quality score
所选检查均完成范围	Range where all selected checks completed
停止时未完成	Unfinished when stopped
正在执行	Executing
逐窗执行记录	Window execution records
未完成	Unfinished
窗口	Window
有尚未运行的配置	A draft configuration is available
恢复草稿	Restore draft
丢弃草稿	Discard draft
取消读取	Cancel reading
恢复已读取文件	Recover received files
更正记录信息	Revise recording information
预览波形	Preview waveform
检查范围	Check scope
快速预检	Quick preview check
整份检查	Whole-recording check
快速预检仅检查所选时段，不代表整份记录。	A quick check covers only the selected range, not the whole recording.
整份检查按有界窗口逐段执行；数据间隙与未完成部分单独报告。	A whole-recording check processes bounded windows in sequence. Data gaps and unfinished ranges are reported separately.
基于本次配置再运行	Reuse this configuration
本次运行链接	Link to this run
复核候选	Review candidates
波形与候选复核	Waveforms and candidate review
收起复核	Close review
待复核候选	Candidates for review
全部模块	All modules
复核状态	Review status
全部候选	All candidates
待复核	Pending review
接受候选	Accept candidate
驳回候选	Reject candidate
待定	Uncertain
起点（秒）	Start (seconds)
显示时长	Display duration
查看波形	View waveform
显示增益	Display gain
选择显示通道（最多 16 道）	Display channels (up to 16)
原始信号波形	Source-signal waveform
波形为有界显示预览；显示降采样不改变分析数据。候选不等于已确认伪迹。	This is a bounded waveform preview. Display downsampling does not change analysis data. Candidates are not confirmed artifacts.
复核结论	Review decision
审核人	Reviewer
备注	Note
保存复核	Save review
上一段	Previous range
下一段	Next range
原记录或配置不可用，无法恢复这份方案。	The source recording or configuration is unavailable, so this configuration cannot be restored.
来源文件当前不可用。	The source file is currently unavailable.
仅波形预览，尚未执行质控。	Waveform preview only; no QC has been performed.
仅整窗定位	Whole-window localization only
定位未提供	Location unavailable
待检查原始证据	Review source evidence
显示更多候选	Show more candidates
当前筛选没有候选。没有候选不代表数据质量通过。	No candidates match this filter. Absence of candidates is not a quality pass.
正在读取候选与复核记录…	Loading candidates and review records…
候选读取未完成，可重新打开复核。	Candidates could not be loaded. Reopen the review to retry.
原始证据	Source evidence
标记区间为算法候选，需结合原始波形复核。	The highlighted interval is an algorithm candidate and requires review against source waveforms.
此候选没有精确异常起止；当前波形仅作为上下文。	This candidate has no precise abnormal onset or offset. The waveform provides context only.
候选原始依据	Original candidate evidence
请选择 1–16 道信号、非负起点和不超过 10 秒的显示时长。	Select 1–16 signals, a nonnegative start and a display duration of at most 10 seconds.
显示起点超出记录范围。	The display start is outside the recording.
正在读取波形…	Loading waveform…
波形读取未完成	Waveform could not be loaded
波形时间范围无效。	Invalid waveform time range.
无有限采样	No finite samples
显示方法未提供	Display method unavailable
各通道独立显示比例	Independent display scaling per channel
请选择复核结论并填写审核人。	Select a decision and enter the reviewer name.
复核已保存；原始检测结果保持不变。	Review saved. Original detection results are unchanged.
复核记录已被更新。你的输入已保留，请核对最新记录后再保存。	The review has changed. Your edits are retained; check the latest record before saving again.
滤波频率必须是非负数或留空。	Filter frequencies must be nonnegative numbers or left blank.
标注映射必须是合法 JSON，或留空。	Annotation mapping must be valid JSON or left blank.
预处理与标注映射	Preprocessing and annotation mapping
只填写有来源证据的信息；未知值留空。保存为新版本，不改写历史运行。	Enter only source-supported information; leave unknown values blank. Saving creates a new version without rewriting previous runs.
已核实滤波声明	Filter declarations verified
高通（Hz）	High-pass (Hz)
低通（Hz）	Low-pass (Hz)
处理史与证据	Processing history and evidence
标注映射 JSON（可留空）	Annotation mapping JSON (optional)
kind 为 task、sleep_stage 或 clinical_event；labels 将原标签映射到确认含义，confirmed 必须为 true。标签不是质量真值。	kind is task, sleep_stage or clinical_event. labels maps source descriptions to confirmed meanings, and confirmed must be true. These labels are not quality ground truth.
取消更正	Cancel revision
保存新版本并推荐	Save new version and recommend
正在传输文件…	Transferring file…
传输完成，正在解包和读取结构…	Transfer complete; unpacking and reading structure…
读取连接中断。可通过“恢复已读取文件”查询已接收记录。	The reading connection was interrupted. Use Recover received files to find received recordings.
读取超时。可通过“恢复已读取文件”查询结果；请勿立即重复上传。	Reading timed out. Use Recover received files to check the result before uploading again.
已取消等待。服务可能保留已接收的本机副本，可查询已读取文件。	Waiting cancelled. The service may retain a received local copy; check received files to recover it.
正在查询待确认记录…	Loading recordings awaiting confirmation…
没有待确认记录。	No recordings await confirmation.
范围未提供	Scope unavailable
复制配置运行	Run from copied configuration
本次运行证据	Evidence from this run
查看本次候选	View candidates from this run
本次结果尚未就绪。	Results for this run are not ready.
算法介绍与适用条件	Method background and requirements
背景可留未知	Background may remain unknown
既有两份全长ds002034结果与来源坏道标签不一致；尚未证明准确率。	Results for two full-length ds002034 recordings disagreed with source bad-channel labels. Accuracy has not been established.
适配已登记的event_name事件表，包括ds002034及EEGMMIDB来源转换表；不等于通用BIDS验证。	Supports registered event_name tables, including tables derived from ds002034 and EEGMMIDB. This is not general BIDS validation.
flat=0、最短0.1秒为项目研究参数；软件默认值也不代表公认好坏界线。	flat=0 and a 0.1-second minimum are project research settings. Software defaults are not accepted boundaries between good and poor quality.
默认peak=None，未启用突变阈值；启用时必须明确以V填写。	The default peak=None disables the abrupt-change threshold. Any configured threshold must explicitly be in volts.
MNE可能只返回通道建议而无时间标注；时间标注不提供单道定位。	MNE may return channel suggestions without time annotations. Time annotations do not locate findings within individual channels.
阈值依赖采样率、量化精度和处理史；结果不自动排除通道或样本。	Thresholds depend on sampling rate, quantization and processing history. Results do not automatically exclude channels or samples.
首版固定110–140Hz；160/256Hz输入不适用，不降低频带伪装同一方法。	The initial implementation fixes the band at 110–140 Hz. Inputs sampled at 160 or 256 Hz are ineligible; lowering the band would not be the same method.
首版固定110–140 Hz；160/256 Hz输入不适用，不降低频带伪装同一方法。	The initial implementation fixes the band at 110–140 Hz. Inputs sampled at 160 or 256 Hz are ineligible; lowering the band would not be the same method.
这是选中EEG通道的聚合时间分数，不提供单通道定位；选道会影响结果。	This is an aggregate time score across selected EEG channels, without per-channel localization. Channel selection affects the result.
120Hz工频谐波等也可能贡献高频能量；无同步EMG确认，不能诊断肌电。	A 120 Hz line-frequency harmonic and other components can contribute high-frequency energy. Without synchronous EMG confirmation, this cannot establish muscle activity.
120 Hz工频谐波等也可能贡献高频能量；无同步EMG确认，不能诊断肌电。	A 120 Hz line-frequency harmonic and other components can contribute high-frequency energy. Without synchronous EMG confirmation, this cannot establish muscle activity.
未知滤波史时仅作探索性输出；不执行自动剔除、ICA或修复。	With unknown filter history, outputs are exploratory only. No automatic rejection, ICA or repair is performed.
默认参数来自MNE实现，不是公认质量界线；至少8道/10秒是本项目的保守门槛。	Defaults come from the MNE implementation, not accepted quality boundaries. At least 8 channels and 10 seconds are conservative project requirements.
lm_cutoff是分布拟合范围上限，不是最终桥接阈值；MNE未返回拟合的局部极小值。	lm_cutoff limits the distribution-fitting range; it is not the final bridging threshold. MNE does not return the fitted local minimum.
双极、混合或未知参考阻断；当前适配不自动拆组或重参考。	Bipolar, mixed or unknown references block this method. The adapter does not automatically split comparison groups or re-reference data.
方法不需要坐标，但相近生理信号也会低电气距离；候选仍需原始波形和硬件记录复核。	Coordinates are not required, but similar physiological signals can also have low electrical distance. Candidates require review of original waveforms and hardware records.
完全重复或退化距离分布可能导致KDE失败；失败不得解释为无桥接。	Identical signals or degenerate distance distributions can cause KDE failure. Failure must not be interpreted as absence of bridging.
仅MNE副本上滤波；不插值、不删道，候选不提供已确认的起止时刻。	Filtering affects only an MNE copy. No interpolation or channel removal occurs, and candidates do not establish onset or offset times.
邻居20和阈值1.5是软件默认值，不是国际共识；少于21道时默认配置阻断。	Twenty neighbors and a threshold of 1.5 are software defaults, not international consensus. The default configuration is blocked below 21 channels.
比较整个当前片段的波形向量；参考、幅值、选道、片段长度和病理活动均影响离群结果。	The method compares waveform vectors over the current segment. Reference, amplitude, channel selection, segment length and pathological activity affect outlier results.
双极、混合或未知参考阻断；不把双极链中的不同导联当普通帽上通道比较。	Bipolar, mixed or unknown references block this method. Different leads in a bipolar chain are not compared as ordinary scalp-cap channels.
没有额外滤波、重参考、归一化或空间插值；不需要电极坐标。	No extra filtering, re-referencing, normalization or spatial interpolation is applied. Electrode coordinates are not required.
算法返回通道级候选，不提供单道异常时间；疾病标签不参与计算。	The algorithm returns channel-level candidates without per-channel abnormal intervals. Clinical-condition labels do not enter the calculation.
固定连续分段不是已验证独立任务试次；相邻时间段相关，CV结果不能当独立泛化验证。	Fixed segments from continuous data are not validated independent task trials. Adjacent segments are correlated; CV results are not independent generalization evidence.
分段2秒、随机种子0、至少20段是项目研究配置；cv=5是库默认值，均非通用质量阈值。	Two-second segments, random seed 0 and at least 20 segments are project research settings; cv=5 is the library default. None is a universal quality threshold.
允许双极导联作探索性阈值估计；睡眠慢波、癫痫样活动等可能影响阈值，不能据此称伪迹。	Exploratory threshold estimation allows bipolar leads. Sleep slow waves, epileptiform activity and other physiology may affect the threshold and must not therefore be called artifacts.
不执行drop_bad、reject、transform或局部AutoReject；不使用源坏道、事件或疾病标签。	Does not apply drop_bad, reject, transform or local AutoReject. Source bad-channel, event and clinical-condition labels are not used.
不足一个完整段的尾部不参与阈值估计并明确报告；不自动降采样或过滤数据。	A final incomplete segment is excluded from threshold estimation and explicitly reported. Data are not automatically downsampled or filtered.
尚未接入；安装了库不代表平台已具备该功能。	Not integrated. An installed library does not mean this platform provides the feature.
不凭通道名称自动补坐标；需真实数据验收。	Coordinates are not inferred from channel names. Acceptance checks on real data are required.
在分段数据中估计局部通道阈值和试次建议；与已接入的全局阈值方法不同。	Estimates local channel thresholds and epoch suggestions in segmented data. This differs from the integrated global-threshold method.
尚未接入；有任务事件不等于已有足够且可比的试次。	Not integrated. Task events do not establish sufficient, comparable trials.
尚未接入；平均参考、1–100Hz和extended-infomax等训练条件需要单独核对。	Not integrated. Training conditions, including average reference, 1–100 Hz and extended-infomax, require separate verification.
汇总实际模块和子方法状态，保留候选、缺失条件、跳过项及运行错误；总分value保持null，注明尚未校准。	Summarize actual module and method states, retaining candidates, missing requirements, skipped checks and execution errors. The overall score value remains null and is explicitly uncalibrated.
完成率不是信号质量。没有候选可能来自未评、缺少辅助导联或方法灵敏度有限；汇总只覆盖本次选择的检查。	Completion rate is not signal quality. No candidates may reflect unassessed checks, missing auxiliary channels or limited sensitivity. The summary covers only selected checks.
运行结束或部分失败后；先看适用性和实际执行状态，再解释结果。	Use after completion or partial failure. Review applicability and actual execution states before interpreting findings.
不能生成未经校准的跨疾病、跨设备或跨数据集总分；未选择方法不能算通过。	Do not generate uncalibrated overall scores across clinical conditions, devices or datasets. Unselected methods cannot be counted as passes.
ephys_qc.runtime.execute（M08汇总与score.value=null）	ephys_qc.runtime.execute (M08 aggregation; score.value=null)
本平台实际状态汇总和未校准总分	Platform execution-state summary and uncalibrated score
本项目证据汇总；不是经过验证的综合质量量表。	Platform evidence aggregation, not a validated composite quality scale.
将结果写为JSON及HTML，保留来源哈希、计划、原始索引与时间映射、适用性和未评原因；生成有限范围波形预览。	Write JSON and HTML results retaining source hashes, the plan, original indices, timeline mapping, applicability and assessment gaps. Generate waveform previews for a limited display range.
报告记录自动筛查证据，人工复核仍为待处理。预览不是全记录审阅，也不是临床诊断报告。	The report records automated screening evidence; manual review remains pending. A preview is neither a review of the full recording nor a clinical diagnostic report.
交付研究记录或复核候选时；必须同时检查报告所载时间范围、所选通道和原始波形。	Use for research handoff or candidate review. Check the reported analysis range, selected channels and original waveforms together.
不能仅凭缩略波形排除全段问题，不能把生成报告视作已经完成临床判读或人工签署。	A waveform thumbnail cannot rule out problems across the full range. Generating a report does not complete clinical interpretation or human sign-off.
本平台报告、预览及证据输出	Platform reports, previews and evidence outputs
本项目可追溯报告封装；不自动删除、插值或重写原始数据。	Platform traceable reporting; original data are not automatically deleted, interpolated or rewritten.
直接调用MNE annotate_amplitude，按相邻样本差值判定peak/flat并结合最小时长与坏样本比例；平台默认peak=None、flat=0、min_duration=0.1秒、bad_percent=5。	Calls MNE annotate_amplitude, applying peak/flat criteria to adjacent-sample differences with minimum duration and bad-sample percentage. Platform defaults: peak=None, flat=0, min_duration=0.1 seconds, bad_percent=5.
它不是固定时间窗峰峰值法。MNE可能只返回坏通道候选而没有区间；时间注释可跨通道合并，不能伪造成逐道精确定位。	This is not fixed-window peak-to-peak detection. MNE may return channel candidates without intervals; time annotations may merge across channels and must not be presented as precise per-channel locations.
已核验电压单位和采样率，理解量化精度、采集与处理历史时；默认设置主要补查精确平线。	Requires verified voltage units and sampling rate, with consideration of quantization, acquisition and processing history. Default settings mainly screen exact flat segments.
不能用本项覆盖缓慢漂移或所有高幅度伪迹；没有时间注释不等于没有通道候选，也不能把默认值当临床标准。	This does not cover slow drift or all high-amplitude artifacts. No time annotations does not imply no channel candidates; defaults are not clinical standards.
本平台MNE幅度和平线适配	Platform MNE amplitude and flat-segment adapter
直接调用MNE；本平台设定实验默认、保留两类输出并映射原始索引，不写入raw.info['bads']。	Calls MNE directly. The platform sets experimental defaults, retains both output types and maps source indices without writing raw.info['bads'].
2026-10-29核对本地MNE 1.13.2与平台适配器；网页stable文档可能更新，实际参数与版本以本次运行记录为准。	Checked local MNE 1.13.2 and platform adapters on 2026-10-29. Online stable documentation may change; the run record determines actual parameters and versions.
直接调用MNE annotate_muscle_zscore，显式指定EEG及固定110–140Hz；Hilbert包络标准化后跨通道汇总和平滑，当前阈值4、min_length_good=0.1秒。	Calls MNE annotate_muscle_zscore with EEG and a fixed 110–140 Hz band. Standardized Hilbert envelopes are aggregated across channels and smoothed. Current settings: threshold 4, min_length_good=0.1 seconds.
输出是所选通道集合的时间候选，不是每个通道的肌电结论。没有同步EMG确认，120Hz工频谐波等也可能混入，始终按探索性结果解释。	Outputs are time candidates for the selected channel set, not per-channel muscle conclusions. Without synchronous EMG confirmation, 120 Hz line harmonics and other components may contribute; results remain exploratory.
采样率严格大于280Hz、选区至少10秒且该频带可测时；滤波史未知保留partial，已知频带不支持则阻止。	Requires a sampling rate strictly above 280 Hz, at least 10 seconds and a measurable target band. Unknown filter history yields partial status; known incompatible filtering blocks the method.
不能把110–140Hz自动下移到低采样率记录；常数或非有限分数不能报通过，无候选也不证明无肌电。	Do not shift the 110–140 Hz band down for lower-rate recordings. Constant or non-finite scores cannot pass; no candidates does not prove absence of muscle activity.
本平台固定频带肌电方法与失效门控	Platform fixed-band muscle method and failure handling
直接调用MNE公开函数；平台添加固定频带、时长、滤波史和输出有效性门控，不做清洗。	Calls the public MNE function. The platform checks fixed bandwidth, duration, filter history and output validity without cleaning data.
直接调用MNE compute_bridged_electrodes，对分段后的通道差值方差估计电距离分布并寻找桥接候选；默认0.5–30Hz、2秒段、epoch_threshold=0.5。	Calls MNE compute_bridged_electrodes to estimate electrical-distance distributions from segmented channel-difference variance and identify bridging candidates. Defaults: 0.5–30 Hz, 2-second segments, epoch_threshold=0.5.
lm_cutoff默认16µV²是寻找分布局部极小值的范围上限，不是最终桥接阈值。候选定位到整个分析选区内的通道对，逐段距离不能冒充桥接起止时间。	The default lm_cutoff of 16 µV² limits the search for a distribution minimum; it is not the final bridging threshold. Candidates identify channel pairs over the selected range. Segment distances do not establish bridging onset and offset.
当前适配要求已核实共同参考或联耳参考、单一完整比较组、至少8道、10秒及5个完整段；硬件和电极信息用于后续解释。	The adapter requires a verified common or linked-ear reference, one complete comparison group, at least 8 channels, 10 seconds and 5 complete segments. Hardware and electrode information support later interpretation.
不直接用于双极、混合或未知参考；不凭名字猜坐标。完全重复信号可能令分布拟合退化，失败必须保留，不能报无桥接。	Do not apply directly to bipolar, mixed or unknown references, or infer coordinates from names. Identical signals may cause degenerate distribution fitting; retain failures rather than reporting no bridging.
本平台桥接输入门控与通道对定位	Platform bridging requirements and channel-pair localization
直接调用MNE；本平台增加适用性约束、原始通道映射和失败说明，不插值通道。	Calls MNE directly, adding applicability checks, source-channel mapping and failure explanations without channel interpolation.
直接调用MNE find_bad_channels_lof，以通道波形为特征、邻近通道为参照计算Local Outlier Factor；默认20个邻居、Euclidean距离和1.5阈值。	Calls MNE find_bad_channels_lof using channel waveforms as features and neighboring channels in feature space as references. Defaults: 20 neighbors, Euclidean distance and threshold 1.5.
候选是整段通道离群，不是具体坏段。局部脑活动、病理波形、幅度和参考差异都可能造成离群；分数不是异常概率。	Candidates are channel outliers over the full selected range, not localized bad intervals. Local brain activity, pathological waveforms, amplitude and reference differences may cause outliers; the score is not an abnormality probability.
当前要求已核实共同或联耳参考、单一完整比较组、至少8道和10秒，通道数还须严格多于配置的邻居数；参数应随评估记录。	Requires a verified common or linked-ear reference, one complete comparison group, at least 8 channels and 10 seconds, and strictly more channels than configured neighbors. Record parameters with the assessment.
不用于当前双极、混合或未知参考输入；不静默缩小邻居数。算法前没有额外幅度归一化或重参考，跨采集条件不可直接比较阈值表现。	Not applied to bipolar, mixed or unknown references. Neighbor count is not silently reduced. No extra amplitude normalization or re-referencing precedes the algorithm; threshold behavior is not directly comparable across acquisition conditions.
本平台LOF门控与候选封装	Platform LOF requirements and candidate adapter
直接调用MNE及其scikit-learn依赖；本平台保留原始分数、通道身份与复核状态。	Calls MNE and its scikit-learn dependency directly, retaining original scores, channel identity and review status.
将分析副本分成不重叠的默认2秒段，直接调用get_rejection_threshold，以默认5折CV和固定随机种子估计一个EEG全局阈值；再报告同一拟合选区中超阈值的段。	Split an analysis copy into nonoverlapping 2-second segments by default. Call get_rejection_threshold with default 5-fold CV and a fixed random seed to estimate one EEG threshold, then report exceedances in the same fitted range.
这是同一选区上的描述性超阈值结果。连续相邻段有关联，内部CV优化不等于独立受试者验证；分段不是任务试次，也不是已执行剔除。	These are descriptive exceedances in the fitted range. Adjacent continuous segments are correlated; internal CV optimization is not independent participant validation. Segments are not task trials, and no rejection has been applied.
当前至少max(20,4×CV折数)个完整段且段长对应整数样本；可用于少通道或双极数据的探索，未使用的尾段必须显示。	Requires at least max(20, 4×CV folds) complete segments with integer sample lengths. Exploratory use with few channels or bipolar data is allowed; the unused final partial segment must be reported.
不能把此全局阈值当local AutoReject；不调用drop_bad或transform，也不能借用论文准确率证明本平台候选正确。	This global threshold is not local AutoReject. It does not call drop_bad or transform, and published accuracy cannot establish correctness of this platform’s candidates.
autoreject.get_rejection_threshold(epochs, decim=1, random_state=0, ch_types=['eeg'], cv=5)（默认配置）	autoreject.get_rejection_threshold(epochs, decim=1, random_state=0, ch_types=['eeg'], cv=5) (default configuration)
Jas等，Autoreject: Automated artifact rejection for MEG and EEG data（2017）	Jas et al., Autoreject: Automated artifact rejection for MEG and EEG data (2017)
本平台固定分段、拟合与同选区描述	Platform fixed segmentation, fitting and within-range descriptions
直接调用autoreject全局阈值估计；本平台建立临时连续分段并映射候选，不清洗数据。	Calls autoreject global-threshold estimation directly. The platform constructs temporary segments and maps candidates without cleaning data.
2026-10-29核对本地autoreject 0.5.1与MNE 1.13.2；参数与实际完整分段数写入运行结果。	Checked local autoreject 0.5.1 and MNE 1.13.2 on 2026-10-29. Parameters and actual complete-segment counts are saved in the run results.
PyPREP从其他电极的随机子集按空间信息预测各通道，再比较预测信号与实测信号相关性；未来适配需冻结坐标、参考、随机种子和有效通道规则。	PyPREP uses spatial information and random subsets of other electrodes to predict each channel, then compares predicted and measured signals by correlation. A future adapter must freeze coordinates, reference, random seed and usable-channel rules.
空间不可预测性是候选线索，不直接证明伪迹；它不能被现有非空间相关指标替代，也不等同于完整PREP清洗。	Poor spatial predictability is a candidate indicator, not proof of an artifact. Existing non-spatial correlations do not replace it, and it is not the full PREP cleaning pipeline.
未来仅在坐标已经核实、通道足够且参考可比较、空间覆盖适合时评估。	Future assessment requires verified coordinates, sufficient channels, comparable reference and suitable spatial coverage.
当前尚不可运行；不能靠通道名补坐标，不宜直接套到少通道PSG、临床双极导联或未经验证的颅内布局。	Not currently runnable. Do not infer coordinates from names or directly apply it to sparse PSG, clinical bipolar leads or unvalidated intracranial layouts.
尚未接入，本平台未执行或验证该方法；不能引用上游论文准确率作为本平台结果。	Not implemented, executed or validated by this platform. Accuracy reported in upstream papers is not a platform result.
计划调用pyprep.NoisyChannels.find_bad_by_ransac；尚无平台执行调用	Planned call: pyprep.NoisyChannels.find_bad_by_ransac; no platform execution call exists yet
PyPREP：NoisyChannels及find_bad_by_ransac	PyPREP: NoisyChannels and find_bad_by_ransac
本平台计划方法登记	Platform registry of planned methods
仅登记未来直接调用PyPREP的方案；不能与已执行的BrainElecQC再实现混同。	Only a planned direct PyPREP integration is registered. It must not be confused with the executed BrainElecQC reimplementation.
本地安装PyPREP 0.5.0但该方法未接入；2026-10-29在线stable文档为0.10.0，后续须按实际安装版本重核API。	PyPREP 0.5.0 is installed locally, but this method is not integrated. Online stable documentation was 0.10.0 on 2026-10-29; verify the API against the installed version before integration.
local AutoReject通过交叉验证联合选择逐通道峰峰值阈值、坏通道共识和插值数量；未来拟合后提取reject log，不默认应用清洗。	Local AutoReject jointly selects per-channel peak-to-peak thresholds, bad-channel consensus and interpolation counts by cross-validation. Future integration would extract a reject log after fitting without applying cleaning by default.
local方法与现有单个全局阈值不同。坏试次/坏通道建议仍需独立真值评估，存在事件标签不代表已有可用且足够的试次。	The local method differs from the implemented single global threshold. Epoch and channel suggestions require independent quality labels for evaluation; event labels do not establish sufficient usable trials.
未来有明确分段规则、足够数据、已核实电极位置及可比较采集条件时；拟合本身也依赖有效位置。	Future use requires explicit segmentation, sufficient data, verified electrode positions and comparable acquisition conditions. Fitting itself depends on valid positions.
当前尚不可运行；不能把坐标要求只归于最终插值，也不能在缺少位置或少量窗口上宣称完成local AutoReject。	Not currently runnable. Coordinates are required during fitting, not only final interpolation. Missing positions or few windows cannot support a claim of completed local AutoReject.
计划调用autoreject.AutoReject.fit及get_reject_log；尚无平台执行调用	Planned calls: autoreject.AutoReject.fit and get_reject_log; no platform execution call exists yet
仅登记未来直接调用local AutoReject的方案；拟合内部可能用插值评估，平台不默认执行transform。	Only a planned direct local AutoReject integration is registered. Fitting may internally evaluate interpolation; the platform would not apply transform by default.
本地autoreject 0.5.1已供全局阈值使用；local AutoReject未接入，依赖已安装不代表功能可运行。	Local autoreject 0.5.1 supports the global-threshold method. Local AutoReject is not integrated; an installed dependency does not make the feature runnable.
ICLabel用ICA成分头皮图、功率谱和自相关预测七类成分概率；必须先有适当且可复现的ICA分解。	ICLabel predicts probabilities for seven component classes from ICA scalp maps, power spectra and autocorrelation. It requires an appropriate, reproducible ICA decomposition first.
分类概率是模型对成分来源的判断，不是整段EEG质量分，也不能直接变成删除规则。训练条件外的概率可靠性需重新验证。	Class probabilities describe the model’s interpretation of component sources, not whole-recording quality or automatic removal rules. Reliability outside training conditions requires new validation.
未来核实坐标、秩、参考和处理史，且有足够数据满足平均参考、1–100Hz、extended-infomax等模型适用条件时。	Future use requires verified coordinates, rank, reference and processing history, plus sufficient data meeting model conditions such as average reference, 1–100 Hz and extended-infomax ICA.
当前尚不可运行；不借用头皮EEG论文准确率到颅内、少通道PSG或低采样率数据，不凭通道名猜空间位置，也不自动移除成分。	Not currently runnable. Scalp-EEG paper accuracy cannot be transferred to intracranial, sparse PSG or low-rate data. Coordinates are not inferred from names, and components are not removed automatically.
计划调用mne_icalabel.iclabel.iclabel_label_components；尚无平台执行调用	Planned call: mne_icalabel.iclabel.iclabel_label_components; no platform execution call exists yet
MNE-ICALabel：ICLabel特征与训练条件	MNE-ICALabel: ICLabel features and training conditions
仅登记未来通过MNE-ICALabel调用ICLabel的方案；现有ECG/EOG锁时与高频方法不依赖ICA。	Only a future ICLabel integration through MNE-ICALabel is registered. Existing ECG/EOG-locked and high-frequency methods do not depend on ICA.
2026-10-29本地未安装mne-icalabel，平台未接入ICA/ICLabel；将来接入需记录包及模型版本。	As of 2026-10-29, mne-icalabel is not installed locally and ICA/ICLabel is not integrated. Future integration must record package and model versions.
Chronux ftestc：正弦成分F检验说明	Chronux ftestc: F-test for sinusoidal components
Bigdely-Shamlo等，The PREP pipeline（2015）	Bigdely-Shamlo et al., The PREP pipeline (2015)
BrainElecQC依据多窗F检验与PREP参数做的再实现；主流程没有调用Chronux或MNE去工频函数。	BrainElecQC reimplements the multitaper F-test using PREP-related parameters. The main pipeline does not call Chronux or MNE line-noise removal functions.
在Welch PSD上直接调用FOOOF 1.1.1拟合非周期背景和高于背景的峰，默认固定背景模式、2–40Hz；另以PSD积分计算含背景的α功率及相对α功率。	Calls FOOOF 1.1.1 on Welch PSD to fit the aperiodic background and peaks above it, using fixed background mode over 2–40 Hz by default. Separately integrates PSD to calculate alpha power including background and relative alpha power.
FOOOF峰高与α频带积分不是同一量。拟合优度、背景指数和α峰缺失均不是质量分；状态、年龄、疾病和参考方式会影响结果。	FOOOF peak height differs from integrated alpha-band power. Fit quality, aperiodic exponent and absence of an alpha peak are not quality scores; state, age, clinical condition and reference affect them.
拟合频带可测、功率为正、分辨率与时长足够时；当前每次拟合要求至少10秒和4个Welch周期图，短尾窗单独保留未评。	Requires a measurable fitting band, positive power and adequate resolution and duration. Each fit currently requires at least 10 seconds and 4 Welch periodograms; short final windows remain unassessed.
不能把无α峰认作坏记录，也不能用拟合模型替代临床判断；频带被滤除或短窗不满足条件时不应强行拟合。	Absence of an alpha peak does not establish a bad recording, and a spectral model does not replace clinical judgment. Do not force fitting when the band was filtered out or the window is too short.
FOOOF 1.1.1官方文档	FOOOF 1.1.1 official documentation
BrainElecQC FOOOF与拟合门控	BrainElecQC FOOOF fitting and requirements
BrainElecQC α频带积分	BrainElecQC alpha-band integration
直接调用FOOOF；BrainElecQC实现拟合门控、窗口汇总和独立的α功率积分。	Calls FOOOF directly. BrainElecQC implements fitting requirements, window summaries and separate alpha-power integration.
2026-10-29核对本地BrainElecQC 0.1.0安装源码及固定提交f007d829712d1b824cda79409d181a3313d6a78f；同名方法不代表调用同名第三方包。 当前实现显式要求fooof==1.1.1；不能直接以新版specparam替换。	Checked BrainElecQC 0.1.0 at commit f007d829712d1b824cda79409d181a3313d6a78f on 2026-10-29. Matching method names do not imply matching package dependencies. This implementation requires fooof==1.1.1; newer specparam versions are not direct replacements.
BrainElecQC在分析副本上处理滤波，独立计算稳健幅度、高低频差异、分窗相关和掉线统计，再按声明的比较组应用门控与阈值。	BrainElecQC filters an analysis copy and computes robust amplitude, high/low-frequency differences, windowed correlation and dropout statistics independently. Requirements and thresholds are applied within declared comparison groups.
这是PREP非空间思想的再实现，不是完整PREP。没有RANSAC、插值或稳健平均重参考；组内异常也可能是局部生理或病理信号。	This reimplements non-spatial PREP ideas, not the full PREP pipeline. It does not perform RANSAC, interpolation or robust-average re-referencing. Group outliers may also reflect local physiological or pathological activity.
参考方式可比较且显式声明分组时；当前每组至少4个可用通道是实现门槛，必须连同有效窗数和零离散度情况解释。	Requires comparable references and explicit groups. The current minimum of 4 usable channels per group is an implementation condition; interpret results with valid-window counts and any zero-dispersion cases.
未知比较组、少通道或混合参考时只保留可计算描述量，不强行出组阈值结论；不能凭电极名称构造空间坐标或把双极导联视作共同参考。	Unknown groups, few channels or mixed references permit descriptive measures only, without forcing group-threshold conclusions. Do not infer coordinates from names or treat bipolar leads as common-reference channels.
已接入，但既有两份ds002034全长结果与来源坏道标签不一致；该负结果保留，不能宣称准确率或临床验证。	Implemented, but two existing full-length ds002034 results disagree with source bad-channel labels. This negative result is retained; accuracy or clinical validation cannot be claimed.
brainelecqc.eeg.bad_channels.compute_bad_channels；主流程不调用pyprep.NoisyChannels	brainelecqc.eeg.bad_channels.compute_bad_channels; the main pipeline does not call pyprep.NoisyChannels
BrainElecQC非空间指标及独立PyPREP对照函数	BrainElecQC non-spatial measures and separate PyPREP comparison function
直接调用BrainElecQC再实现；PyPREP仅在独立compare_with_pyprep对照函数中使用，不属于当前主检测调用。	Calls the BrainElecQC reimplementation directly. PyPREP is used only by the separate compare_with_pyprep comparison function, not by the current main detector.
直接用MNE find_ecg_events从所配置ECG检测事件；BrainElecQC随后对EEG锁时分段，汇总均值、中位数、标准误和分半一致性，边界不完整事件不参与平均。	MNE find_ecg_events detects events in the configured ECG channel. BrainElecQC then extracts time-locked EEG segments and reports mean, median, standard error and split-half consistency; incomplete boundary events are excluded from averaging.
事件和重复锁时成分是支持证据，不能单独确认污染或诊断心脏问题；共同参考、真实生理耦合或错误辅助导联也会影响结果。	Events and recurring time-locked components provide supporting evidence, not standalone confirmation of contamination or a cardiac diagnosis. Common reference, physiological coupling or an incorrect auxiliary channel may affect results.
辅助导联身份已确认且与EEG同采样时钟、时长足够时；当前ECG检测默认5–35Hz，结果应连同可用事件数复核。	Requires a confirmed auxiliary channel sharing the EEG sample clock and sufficient duration. ECG detection defaults to 5–35 Hz; review results together with usable-event counts.
没有ECG、导联恒值或事件不足时保留未评；不能把未检出当干净，也不从EEG通道名猜出独立ECG证据。	Missing ECG, constant auxiliary signals or insufficient events remain unassessed. Nondetection does not establish clean EEG, and EEG channel names do not provide independent ECG evidence.
brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_ecg_events；锁时统计由BrainElecQC实现	brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_ecg_events; time-locked statistics are implemented by BrainElecQC
BrainElecQC ECG事件和EEG锁时汇总	BrainElecQC ECG events and time-locked EEG summaries
直接复用MNE事件检测；BrainElecQC自建EEG锁时统计，没有自动投影或删除成分。	Reuses MNE event detection directly. BrainElecQC implements time-locked EEG statistics without automatic projection or component removal.
2026-10-29核对本地BrainElecQC 0.1.0安装源码及固定提交f007d829712d1b824cda79409d181a3313d6a78f；同名方法不代表调用同名第三方包。 本地事件检测依赖MNE 1.13.2。	Checked BrainElecQC 0.1.0 at commit f007d829712d1b824cda79409d181a3313d6a78f on 2026-10-29. Matching names do not imply matching package dependencies. Local event detection uses MNE 1.13.2.
直接用MNE find_eog_events检测辅助EOG事件；BrainElecQC以这些时刻截取EEG并汇总平均形态、离散程度和分半一致性。	MNE find_eog_events detects auxiliary EOG events. BrainElecQC extracts EEG around those times and summarizes average morphology, variability and split-half consistency.
EOG事件不等于所有EEG通道被污染；锁时平均可提示相关成分，但需要结合空间分布、参考和波形复核。	An EOG event does not establish contamination of every EEG channel. Time-locked averages may indicate related components but require review of spatial distribution, reference and waveforms.
有身份明确、时钟一致且信号可用的EOG时；当前检测默认1–10Hz，只在分析副本上进行。	Requires a confirmed, usable EOG signal on the same clock. Detection defaults to 1–10 Hz and operates on an analysis copy only.
没有EOG或事件不可用时不能给出通过结论；睡眠慢眼动与任务相关眼动需要背景解释，不能把状态标签直接变为扣分。	Missing EOG or unusable events cannot produce a pass. Slow eye movements during sleep and task-related eye movements require context; state tags do not directly become score penalties.
brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_eog_events；锁时统计由BrainElecQC实现	brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_eog_events; time-locked statistics are implemented by BrainElecQC
BrainElecQC EOG事件和EEG锁时汇总	BrainElecQC EOG events and time-locked EEG summaries
直接复用MNE事件检测；BrainElecQC自建锁时证据，不运行自动眼电去除。	Reuses MNE event detection directly. BrainElecQC builds time-locked evidence without automatic ocular-artifact removal.
BrainElecQC复用MNE滤波和Hilbert包络原语，自建包络、相对功率、频谱分散度等多重门控；M03连续性问题形成保护区，有真实EMG时再检查同步支持。	BrainElecQC uses MNE filtering and Hilbert-envelope primitives with its own envelope, relative-power and spectral-dispersion criteria. M03 continuity findings define protection intervals; synchronous support is checked when real EMG is available.
无EMG支持的结果只称高频突发；有EMG支持也仍需复核。高频脑活动、工频谐波和尖锐瞬变均可能影响统计。	Without EMG support, results are described only as high-frequency bursts. Even EMG-supported candidates require review. High-frequency brain activity, line harmonics and sharp transients may affect the measures.
当前默认30–min(100,0.45×采样率)Hz有效带宽至少20Hz、选区至少10秒；应同时查看实际频带、连续性保护与参考导联。	The default band is 30–min(100, 0.45×sampling rate) Hz, with at least 20 Hz usable bandwidth and a 10-second range. Review the actual band, continuity protection and auxiliary reference channels.
频带不足或已被采集滤除时不评；不能把该方法等同于MNE固定110–140Hz肌电方法，不能将癫痫尖波或高频病理活动自动认作伪迹。	Insufficient or filtered-out bandwidth is unassessed. This is not the fixed 110–140 Hz MNE muscle method; epileptic spikes and pathological high-frequency activity must not automatically be classified as artifacts.
brainelecqc.eeg.muscle.compute_muscle_qc；MNE Raw.filter / Raw.apply_hilbert等原语	brainelecqc.eeg.muscle.compute_muscle_qc; uses MNE primitives including Raw.filter / Raw.apply_hilbert
BrainElecQC高频多门控实现	BrainElecQC multi-criterion high-frequency implementation
本平台高频频带及时长门控	Platform high-frequency band and duration requirements
BrainElecQC自有组合筛查，使用MNE底层信号处理；没有直接调用annotate_muscle_zscore。	BrainElecQC’s own combined screening uses MNE signal-processing primitives; it does not call annotate_muscle_zscore directly.
核验登记标注及来源哈希，按原始onset/duration裁剪交叠区间，并映射到原始样本时钟；保存来源标签、覆盖量和缺口。	Verify annotation and source hashes, clip overlapping intervals using original onset/duration, and map them to the original sample clock. Retain source labels, coverage and gaps.
睡眠阶段用于解释EEG状态，不是质量真值。未知覆盖不代表清醒或数据合格；R&K与AASM标签体系不能无依据合并。	Sleep stages describe EEG state, not quality ground truth. Unknown coverage does not mean wakefulness or acceptable data; R&K and AASM labels must not be merged without justification.
已有来源明确且记录对应关系已核对的sleep_stages_tsv时；HMC或Sleep-EDF配套标注可验证时间映射。	Requires a sleep_stages_tsv file with clear provenance and a verified link to the recording. HMC or Sleep-EDF companion annotations can test timeline mapping.
没有分期文件时不推测阶段；程序映射一致不证明原始人工分期准确，也不独立证明设备时钟同步。	Stages are not inferred when a staging file is absent. Consistent software mapping does not establish accurate manual staging or independently prove device-clock synchronization.
本平台睡眠分期映射与覆盖计算	Platform sleep-stage mapping and coverage calculations
PhysioNet Sleep-EDF Expanded 1.0.0：记录与分期说明	PhysioNet Sleep-EDF Expanded 1.0.0: recording and staging documentation
本项目注释核验与时间映射；不运行睡眠分期预测模型。	Platform annotation checks and timeline mapping; no sleep-stage prediction model is run.
读取已登记的事件转换表，检查数值、时长与来源哈希，计算事件与选区交叠；原始时间和裁剪后时间分别保存。	Read registered converted event tables, check values, durations and source hashes, and calculate overlap with the selected range. Store original and clipped times separately.
任务事件描述实验安排，不证明受试者完成动作、行为正确或没有伪迹；事件标签不作为M03–M06检测输入。	Task events describe the experimental schedule; they do not establish actual movement, correct behavior or absence of artifacts. Event labels are not inputs to M03–M06 detectors.
记录关联和转换规则明确的event_name事件表，包括当前ds002034及EEGMMIDB适配。	Use event_name tables with explicit recording links and conversion rules, including the current ds002034 and EEGMMIDB adapters.
当前bids_events_tsv名称不代表通用BIDS验证器；未经适配的任意BIDS事件列不能假定支持，任务背景标签不能替代事件文件。	The name bids_events_tsv does not imply a general BIDS validator. Arbitrary BIDS columns are not automatically supported, and a task-context tag cannot replace an event file.
ephys_qc.annotations.check_annotations（当前注册的bids_events_tsv适配）	ephys_qc.annotations.check_annotations (currently registered bids_events_tsv adapter)
本平台事件表契约与时间映射	Platform event-table contract and timeline mapping
BIDS EEG规范：记录元数据与事件关联	BIDS EEG specification: recording metadata and event linkage
本项目对指定事件格式的适配；没有实现完整BIDS合规检查。	A platform adapter for specified event formats, not a complete BIDS compliance checker.
读取clinical_events_tsv的onset_s、duration_s、label和label_type，核对来源哈希并报告交叠事件、样本位置与区间并集时长。	Read onset_s, duration_s, label and label_type from clinical_events_tsv; verify source hashes and report overlapping events, sample positions and union duration.
发作等临床事件不是伪迹真值；无标注不自动等于正常。事件不进入信号检测或质量评分，也不据此调整疾病阈值。	Seizures and other clinical events are not artifact ground truth; no annotation does not imply normality. Events do not enter signal detection or scoring and do not modify clinical-condition thresholds.
有官方或经授权来源、清楚的事件定义、同一记录时间轴时；例如CHB-MIT官方summary的发作区间。	Use official or authorized sources with clear event definitions on the same recording timeline, such as seizure intervals in the official CHB-MIT summary.
不能把事件表当完整临床诊断或连续正常/异常标注，也不能用病理事件监督坏段检测而仍声称独立QC。	An event table is neither a complete diagnosis nor continuous normal/abnormal labeling. Using pathological events to supervise bad-segment detection would not constitute independent QC.
本平台临床事件映射与标签隔离	Platform clinical-event mapping and label separation
PhysioNet CHB-MIT 1.0.0：发作标注说明	PhysioNet CHB-MIT 1.0.0: seizure annotation documentation
本项目临床事件注释层；不运行疾病检测算法。	Platform clinical-event annotation layer; no disease-detection algorithm is run.
读取器注册表按实际格式分派EDF/BDF、BrainVision、EEGLAB和FIF适配器；统一返回源通道、原生时钟、电压单位、标注摘要和每个配套文件的指纹。	The reader registry dispatches by actual format to EDF/BDF, BrainVision, EEGLAB or FIF adapters. Each returns source channels, native timing, voltage units, annotation summaries and fingerprints for all companion files.
结构可读只说明文件可解析。哈希能核对文件一致性，不能证明文件内容真实、设备正常或信号质量良好。	Readable structure establishes only that the file can be parsed. Hashes verify file consistency, not authenticity, device function or signal quality.
已被相应读取器核验的连续记录；先确认模态、角色和源索引，再选择同一原生时钟的分析与辅助信号。	Use for continuous recordings verified by the appropriate reader. Confirm modality, roles and source indices, then select analysis and auxiliary signals sharing one native clock.
不支持断续EDF、EEGLAB分段数据和分卷FIF；多文件记录必须完整提交。文件可读不证明模态，非头皮EEG不套用现有质控；不自动重采样。	Discontinuous EDF, epoched EEGLAB and split FIF are unsupported. Multi-file recordings must be complete. Readability does not establish modality; current QC is not applied to non-scalp EEG, and no automatic resampling is performed.
已接入结构或时间映射核验；验证对象是文件与程序契约，不能据此认定信号合格或临床有效。	Structure or timeline checks are implemented. Validation concerns files and software contracts, not signal acceptability or clinical validity.
ephys_qc.readers.inspect_recording / open_reader；EDF/BDF后端为BrainElecQC，其他首批格式使用MNE	ephys_qc.readers.inspect_recording / open_reader; BrainElecQC reads EDF/BDF; MNE reads the other initially supported formats
BrainElecQC EDF读取器	BrainElecQC EDF reader
BrainElecQC技术头检查	BrainElecQC technical header checks
EDF原始格式规范	Original EDF format specification
本平台M01与原始通道映射	Platform M01 and original channel mapping
统一读取契约封装独立适配器；新增格式只注册读取模块，不修改下游算法。	A common reading contract wraps independent adapters. New formats register a reader without modifying downstream algorithms.
2026-10-29核对本地BrainElecQC 0.1.0安装源码及固定提交f007d829712d1b824cda79409d181a3313d6a78f；同名方法不代表调用同名第三方包。	Checked against installed BrainElecQC 0.1.0 and commit f007d829712d1b824cda79409d181a3313d6a78f on 2026-10-29. A matching method name does not imply a dependency on the similarly named third-party package.
读取逐道digital/physical最小值、最大值和单位，按线性比例及偏移换算；平台只把核验后的V量纲数据交给电压阈值方法。	Read each channel’s digital/physical extrema and units, then apply linear scaling and offset. Voltage-threshold methods receive only verified values in V.
标定参数有效不等于仪器经过计量校准。错误的文件头、接线或传感器增益仍可能产生看似合理的电压。	Valid scaling parameters do not establish metrological calibration of the instrument. Incorrect headers, wiring or sensor gain may still produce plausible voltages.
单位与标定范围明确、选中EEG及辅助通道可换算为V时；端点平台检查还需保留源标定端点。	Use when units and calibration ranges are explicit and selected EEG and auxiliary channels can be converted to V. Endpoint-plateau checks also require original calibration endpoints.
单位未知、比例退化或所选通道不是电压时不能直接套用微伏阈值；不能凭通道名称猜单位。	Do not apply microvolt thresholds when units are unknown, scaling is degenerate or selected signals are not voltages. Channel names do not establish units.
BrainElecQC逐道标定与读取	BrainElecQC per-channel calibration and reading
本平台电压单位与同钟读取门控	Platform voltage-unit and shared-clock requirements
BrainElecQC按文件头实现数字值到物理值换算；本平台核验下游所需单位。	BrainElecQC converts digital to physical values using the header; the platform checks units required downstream.
根据技术头、明确登记的背景与用户参数生成稳定计划标识，补齐必要依赖，逐项记录ready、partial、blocked等适用性和原因。	Generate a stable plan ID from technical metadata, registered context and user parameters; add dependencies and record each method’s ready, partial or blocked state and reason.
计划可运行不等于检测通过。年龄、疾病、睡眠或任务背景帮助解释信号，不直接变成质量扣分阈值；缺失元数据保留未知。	A runnable plan is not a passed quality check. Age, clinical condition, sleep and task context support interpretation without becoming score penalties. Missing metadata remain unknown.
每次运行前；更换选道、时间范围、参考构型或方法参数后重新生成计划。	Generate a plan before each run and after changing channels, analysis range, reference configuration or method parameters.
不能代替读取文件或实际检测；不能把未核实的坐标、滤波史、参考方式当作已知，也不能以疾病标签推断伪迹。	Planning does not replace reading or detection. Unverified coordinates, filters and references remain unknown; clinical tags do not establish artifacts.
本平台计划与依赖	Platform planning and dependencies
本平台技术事实与背景标签	Platform technical facts and context tags
本平台方法适用性	Platform method applicability
本项目规则编排；不是外部EEG质量评分算法。	Platform rule orchestration, not an external EEG quality-scoring algorithm.
本项目2026-10-29实现快照；下列仓内路径是封装代码位置，不是外部标准或公开算法认证。	Platform implementation snapshot from 2026-10-29. Repository paths identify adapter code, not external standards or algorithm certification.
在未滤波样本上扫描连续相等值，结合逐道标定端点区分端点平台、近零平线和其他恒值段，保存原始通道及半开时间区间。	Scan unfiltered samples for consecutive equal values. Use calibration endpoints to distinguish endpoint plateaus, near-zero flat segments and other constants; retain source channels and half-open intervals.
候选是可复核的局部数据现象，不自动指认设备故障。幅度小但仍变化的信号不会仅因低幅度被认作恒值。	Candidates describe local data phenomena for review, not automatic device-failure diagnoses. Low-amplitude signals that still vary are not classified as constant solely for their amplitude.
已知采样率的连续数据；端点平台解释需源标定信息。当前最短恒值段默认0.1秒是筛查配置。	Use continuous data with a known sampling rate. Endpoint interpretation requires original calibration. The default 0.1-second minimum constant interval is a screening setting.
不把该默认时长视为统一EEG规范；本项不能覆盖所有断线、任意重复数据块或缓慢漂移。	The default duration is not a universal EEG standard. This check does not cover every disconnection, repeated block or slow drift.
已接入候选筛查；工程运行与有限样例检查不等于独立质量真值验证，尚未建立跨数据集准确率或临床验证。	Candidate screening is implemented. Successful execution and limited example checks are not validation against independent quality labels; cross-dataset accuracy and clinical validity remain unestablished.
BrainElecQC原始样本连续性实现	BrainElecQC raw-sample continuity implementation
本平台M03定位与后续保护区	Platform M03 localization and downstream protection intervals
直接调用BrainElecQC基于NumPy的自有连续性实现；没有调用EEGLAB清洗流程。	Calls BrainElecQC’s own NumPy-based continuity implementation directly; it does not invoke an EEGLAB cleaning pipeline.
BrainElecQC直接调用SciPy Welch：分段、加Hann窗并平均周期图；当前默认4秒窗、50%重叠、去常数趋势，输出V²/Hz。	BrainElecQC calls SciPy Welch: segment the data, apply Hann windows and average periodograms. Current defaults are 4-second windows, 50% overlap and constant detrending; output is in V²/Hz.
PSD是估计量，分辨率取决于实际窗长。某频段功率升高可能来自脑活动、参考、设备或伪迹，不能单独作为质量结论。	PSD is an estimate whose resolution depends on window length. Increased band power may reflect brain activity, reference, equipment or artifacts; it is not a standalone quality verdict.
电压单位、采样率和实际可测频带明确时；比较记录应对齐估计参数与采集条件。	Use when voltage units, sampling rate and measurable bandwidth are known. Match estimation parameters and acquisition conditions when comparing recordings.
不能分析Nyquist频率以上的成分；已被采集或软件滤除的频率不能由功率谱恢复，也不宜混比不同参考或滤波条件。	Components above Nyquist cannot be assessed. PSD cannot recover frequencies removed during acquisition or processing; avoid comparing incompatible reference or filter conditions.
BrainElecQC Welch参数与输出	BrainElecQC Welch parameters and outputs
直接调用SciPy算法；BrainElecQC负责参数、定位与结果组织。	Calls the SciPy algorithm directly; BrainElecQC supplies parameters, positions and result organization.
2026-10-29核对本地BrainElecQC 0.1.0安装源码及固定提交f007d829712d1b824cda79409d181a3313d6a78f；同名方法不代表调用同名第三方包。 本地SciPy 1.17.1；在线文档版本可能更高。	Checked installed BrainElecQC 0.1.0 at commit f007d829712d1b824cda79409d181a3313d6a78f on 2026-10-29. Matching names do not imply matching package dependencies. Local SciPy: 1.17.1; online documentation may describe a newer version.
BrainElecQC用SciPy DPSS窗自行计算Thomson多窗F统计量，扫描目标频率邻域，并对通道、完整时间窗和被测频率组成的检验族做Bonferroni校正。	BrainElecQC implements the Thomson multitaper F-statistic using SciPy DPSS tapers. It scans target-frequency neighborhoods and applies Bonferroni correction across channels, complete windows and tested frequencies.
显著结果支持存在近似正弦窄带成分，不直接证明电源污染或设备故障。只记录证据，不执行去工频。	Significance supports a near-sinusoidal narrow-band component, not necessarily mains contamination or device failure. Evidence is recorded without line-noise removal.
窗口足够、目标频率低于Nyquist且记录频带确实保留该频率时；当前4秒窗、1秒步长和族显著性0.01是可记录的算法配置。	Use when duration is sufficient, targets are below Nyquist and retained by the recording bandwidth. Current settings are 4-second windows, 1-second steps and family-wise significance 0.01.
低采样率或已滤除目标频率时只能报告未评或受限；不能把未检出解释为没有工频，也不能把统计显著性当质量总分。	Insufficient sampling or removed target frequencies require an unassessed or limited result. Nondetection does not prove absence of line noise, and statistical significance is not an overall quality score.
BrainElecQC Thomson F检验与多重比较	BrainElecQC Thomson F-test and multiple comparisons
已核验文件及配套文件	Verified recording and companion files
结构与来源核验	Structure and provenance checks
有效单位及逐道标定	Valid units and per-channel calibration
标定信息	Calibration information
无法评估原因	Reasons an assessment could not be made
通道选择	Channel selection
技术头	Technical header
可选实验背景	Optional experimental context
冻结计划	Frozen plan
标签与适用性	Tags and applicability
连续信号	Continuous signals
端点判断需标定	Calibration required for endpoint checks
通道和原始时间候选	Channel candidates and locations on the original timeline
电压信号	Voltage signals
PSD原值与频段	Raw PSD values and frequency bands
采样率满足待测频率	Sampling rate sufficient for the frequencies being tested
足够的分析窗口	Sufficient analysis duration
工频观察量与候选	Line-frequency measurements and candidates
足够时长和可测频带	Sufficient duration and measurable frequency range
谱拟合	Spectral fit
α功率	Alpha power
谱形与状态、年龄、疾病有关，不能直接把差异判为低质量。	Spectral shape depends on state, age and clinical condition; differences alone do not establish poor quality.
不满足拟合时长的尾窗保留未评。	Final windows shorter than the fitting requirement remain unassessed.
已声明参考比较组	Declared reference comparison groups
每组至少4道为当前实现门槛	This implementation requires at least 4 channels per group
4道门槛是当前实现条件，不是统一行业阈值。	The 4-channel minimum is an implementation requirement, not a universal industry threshold.
已配置ECG辅助导联	Configured ECG auxiliary channel
已配置EOG辅助导联	Configured EOG auxiliary channel
相同采样时钟	A shared sample clock
ECG事件及支持证据	ECG events and supporting evidence
EOG事件及支持证据	EOG events and supporting evidence
足够可测高频带	Sufficient measurable high-frequency bandwidth
M03连续性保护区	M03 continuity protection intervals
EMG用于确认性支持	EMG used as independent supporting evidence
高频候选	High-frequency candidates
已登记睡眠分期	Registered sleep stages
阶段覆盖和未知区间	Stage coverage and unknown intervals
已登记任务事件	Registered task events
事件列表及样本定位	Event list and sample positions
已登记临床事件表	Registered clinical-event table
选区事件和时长	Events and durations in the selected range
实际模块输出	Actual module outputs
未校准总分	Uncalibrated overall score
检查结果及原始选区	Check results and original analysis range
JSON证据	JSON evidence
波形图	Waveform plots
已标定为V的EEG	EEG calibrated in V
原生采样率	Native sampling rate
明确阈值及最短持续时间	Explicit thresholds and minimum duration
跨通道合并时间候选	Time candidates merged across channels
通道级候选（可能没有具体时段）	Channel candidates (possibly without specific time intervals)
电压单位核实并标定为V	Verified voltage units, calibrated in V
保留原生采样的EEG	EEG at its native sampling rate
明确平线/变化阈值及最短持续时间	Explicit flat/change thresholds and minimum duration
检查相邻样本差分，不是固定窗峰峰值或通用大振幅/漂移检测。	Checks adjacent-sample differences, not fixed-window peak-to-peak amplitude or general high amplitude/drift.
足够原生采样率	Sufficient native sampling rate
采集/预处理滤波史	Acquisition and preprocessing filter history
跨通道时间候选	Cross-channel time candidates
逐采样聚合z分数及有效性检查	Aggregated z-score at each sample and validity checks
原生采样率高于280 Hz	Native sampling rate above 280 Hz
本版至少10秒分析窗口	At least 10 seconds in this implementation
采集和滤波史需支持110–140 Hz	Acquisition and filter history must support 110–140 Hz
阈值4与间隔合并0.1秒是MNE默认值，不是国际共识阈值。	The threshold of 4 and 0.1-second gap-merging parameter are MNE defaults, not international consensus thresholds.
已标定为V的同参考EEG	EEG with a common reference configuration, calibrated in V
参考构型和比较组	Reference configuration and comparison groups
连续原生采样片段	Continuous data at the native sampling rate
通道对候选	Channel-pair candidates
固定时间段的电气距离（μV²）	Electrical distance for fixed segments (μV²)
共同或连接耳参考且仅一个完整比较组	Common or linked-ear reference with one complete comparison group
本版至少8道及10秒	At least 8 channels and 10 seconds in this implementation
采样率支持0.5–30 Hz方法滤波	Sampling rate supporting the method’s 0.5–30 Hz filter
足够比较通道	Sufficient comparison channels
原生采样连续片段	Continuous data at the native sampling rate
各道原始负LOF及其绝对值	Each channel’s original negative LOF and its absolute value
本版至少8道、10秒且通道数大于邻居数	At least 8 channels and 10 seconds, with more channels than neighbors, in this implementation
scikit-learn运行依赖	scikit-learn runtime dependency
至少20个完整固定长度段	At least 20 complete fixed-length segments
固定交叉验证配置	Fixed cross-validation configuration
本片段估计的全局峰峰值阈值（V）	Global peak-to-peak threshold estimated from this range (V)
同片段超阈值固定段候选	Fixed segments exceeding the threshold in the same analysis range
原记录时钟上的分段范围与未使用尾段	Segment boundaries on the original clock and the unused final partial segment
本版至少20个完整固定段且不少于4×cv	At least 20 complete fixed segments and at least 4×cv in this implementation
autoreject运行依赖	autoreject runtime dependency
明确固定段不是任务试次	Explicit distinction between fixed segments and task trials
比较实际信号与其他电极空间预测的一致性。	Compare measured signals with spatial predictions from other electrodes.
已核实电极坐标	Verified electrode coordinates
足够多的可用EEG通道	Sufficient usable EEG channels
可比较参考与采集条件	Comparable reference and acquisition conditions
空间坏道候选	Spatial bad-channel candidates
足够的试次/窗口	Sufficient trials or windows
明确分段规则	Explicit segmentation rules
local AutoReject拟合需已核实电极坐标	Local AutoReject fitting requires verified electrode coordinates
坏试次与通道建议	Epoch and channel candidates for review
后续接入只提取评估结果，不默认删除或插值。	Future integration will extract assessments without deleting or interpolating data by default.
对独立成分分类，辅助人工判断来源。	Classify independent components to support manual source interpretation.
足够数据和可用EEG通道	Sufficient data and usable EEG channels
已核对的坐标、秩、参考与滤波处理	Verified coordinates, rank, reference and filtering
满足模型训练条件的ICA分解	ICA decomposition consistent with the model’s training conditions
成分类别与概率	Component classes and probabilities
分类概率不是质量分，不自动移除成分。	Class probabilities are not quality scores. Components are not removed automatically.
当前模态仅保存提取信息，不运行头皮 EEG 质控。	For this modality, only extracted information is saved. Scalp EEG QC is not run.
多格式读取与来源核验	Multi-format reading and source verification
信息已保存；当前模态暂无质控配置	Information saved; no QC configuration is available for this modality
可保存提取信息；当前模态暂无质控配置。	Extracted information can be saved; no QC configuration is available for this modality.
请先读取数据文件。	Read a data file first.
· 需先补充	· Required first
· 可保留未知	· May remain unknown
手动	Manual
推荐	Recommended
已恢复读取结果，请确认信息	Intake restored; confirm the information
仅信息提取	Information extraction only
当前模态暂无已验证的质控配置。	No validated QC configuration is available for this modality.
点击开始检查	Select Start check
按数据配置检查模块	Configure checks for this data
支持配套文件包	Companion-file packages supported
单文件读取	Single-file reading
确认信息	Confirm information
其他记录	Other recordings
输入必须是本地普通文件，不能是符号链接。	The input must be a regular local file, not a symbolic link.
未注册的记录格式。支持 EDF、BDF、BrainVision、EEGLAB 和单文件 FIF。	Unsupported recording format. Supported formats are EDF, BDF, BrainVision, EEGLAB and single-file FIF.
伴随文件引用必须是同目录文件名，不能使用绝对路径、目录跳转或远程地址。	Companion references must be filenames in the same directory. Absolute paths, parent-directory traversal and remote addresses are not allowed.
伴随文件缺失、符号链接或越出包目录。	A companion file is missing, is a symbolic link or lies outside the package directory.
伴随文件扩展名与格式不符。	A companion file’s extension does not match the required format.
来源文件在读取期间发生改变。	The source file changed while being read.
来源文件哈希在读取期间发生改变。	The source file hash changed while being read.
文件不是有效的 EDF/EDF+ 或 BDF。	The file is not a valid EDF/EDF+ or BDF recording.
EDF 技术字段无效。	Invalid EDF technical fields.
EDF 通道数或头长度无效。	Invalid EDF channel count or header length.
EDF 记录时长无效；注释文件不能作为波形输入。	Invalid EDF recording duration. An annotation-only file cannot be used as waveform input.
当前读取适配器尚不支持不连续 EDF+D。	This reader does not support discontinuous EDF+D recordings.
EDF 文件头不完整。	The EDF header is incomplete.
EDF 采样率或缩放字段无效。	Invalid EDF sampling-rate or scaling fields.
EDF 每记录采样点数无效。	Invalid EDF samples per data record.
EDF 数据长度不是完整记录，可能截断。	The EDF data length is not a whole number of records; the file may be truncated.
EDF 数据长度与文件头不一致。	The EDF data length does not match its header.
BrainVision 文本头超过当前读取限制。	The BrainVision text header exceeds the reader’s size limit.
BrainVision 缺少 Common Infos。	BrainVision Common Infos are missing.
BrainVision 头与标记文件指向不同数据文件。	The BrainVision header and marker file reference different data files.
BrainVision 通道数超出当前限制。	The BrainVision channel count exceeds the current limit.
BrainVision 通道分辨率字段缺失。	BrainVision channel resolution fields are missing.
当前 MNE BrainVision 后端不能可靠处理重复通道名；保持源文件，拒绝合并或静默改名。	The current MNE BrainVision backend cannot reliably handle duplicate channel names. The source is preserved; channels will not be merged or silently renamed.
EEGLAB HDF5 外部文件链接不被允许。	EEGLAB HDF5 external-file links are not allowed.
EEGLAB HDF5 外部或虚拟数据集不被允许。	EEGLAB HDF5 external or virtual datasets are not allowed.
EEGLAB 当前只接入连续记录，不能把多个 epochs 拼成连续信号。	Only continuous EEGLAB recordings are supported. Multiple epochs cannot be concatenated into a continuous signal.
EEGLAB 通道或样本数量无效。	Invalid EEGLAB channel or sample count.
EEGLAB FDT 长度与声明的通道/样本不一致。	The EEGLAB FDT length does not match the declared channels and samples.
当前接入仅接受单文件 FIF；split FIF 引用不会自动打开。	Only single-file FIF is supported. Split-FIF references are not opened automatically.
记录的通道数、采样率或长度无效。	Invalid channel count, sampling rate or recording length.
记录含无效注释时钟。	The recording contains invalid annotation timing.
来源包含明确断点或采集缺口；分析窗口不可跨越连续段。	The source declares breaks or acquisition gaps. The analysis window must stay within one continuous segment.
MNE 适配器仅提供原始标定的 SI 数值，不伪造数字 ADC 样本。	The MNE adapter provides natively calibrated SI values only; it does not fabricate digital ADC samples.
读取窗口须位于一个已声明的原生连续段内。	The read window must lie within one declared native continuous segment.
读取通道必须是不同的有效源通道 ID。	Selected channels must have distinct valid source channel IDs.
读取窗口超过 256 MiB 限制。	The read window exceeds the 256 MiB limit.
当前执行器只支持已确认的头皮EEG模态。	The executor supports confirmed scalp EEG only.
当前执行器只支持已核验的 EDF/BDF、BrainVision、EEGLAB 和单文件 FIF。	The executor supports verified EDF/BDF, BrainVision, EEGLAB and single-file FIF recordings only.
新增格式必须先明确确认为头皮EEG，不能仅按文件类型推定模态。	Confirm scalp EEG explicitly for these formats. The modality cannot be inferred from the file type alone.
选中通道包含已声明的非头皮EEG类型，不能套用头皮EEG质控。	The selection contains declared non-scalp-EEG channels. Scalp-EEG QC cannot be applied.
所选 EEG 和辅助通道必须具有已核验的电压单位。	Selected EEG and auxiliary channels must have verified voltage units.
分析选区必须位于同一个原生连续段，不能跨越文件声明的断点或采集缺口。	The analysis range must stay within one native continuous segment and cannot cross declared breaks or acquisition gaps.
extensions只能选择已接入的可选方法。	Only implemented optional methods may be selected in extensions.
存在未接入方法的参数。	Parameters were supplied for a method that is not implemented.
确认读到哪个文件、哪些原始通道，以及样本和记录时钟是否可解释。	Verify the file and original channels, and whether the samples and recording clock can be interpreted.
确认ADC数字值能否依据文件声明换算成具有明确单位的电压。	Verify that ADC values can be converted to voltage with explicit units using the file’s calibration.
在运行前明确要检查的选区、方法、依赖，以及哪些条件已知或尚未知。	Specify the analysis range, methods, dependencies and known or unknown requirements before running.
找到非有限样本、精确恒值段及ADC端点平台等可定位的数据连续性问题。	Locate non-finite samples, exactly constant segments and plateaus at ADC endpoints.
观察各通道的频率能量分布，为工频、谱形和状态解释提供基础描述。	Describe each channel’s spectral power distribution to support interpretation of line interference, spectral shape and recording state.
在可测范围内寻找50/60Hz及其谐波附近稳定窄带成分的统计证据。	Look for statistical evidence of stable narrow-band components near 50/60 Hz and their measurable harmonics.
把谱背景、突出谱峰和实际α频带能量分开描述，减少将谱形差异直接当作坏数据的误读。	Describe the spectral background, prominent peaks and alpha-band energy separately, avoiding the assumption that spectral differences mean bad data.
在可比较的通道组内，筛查幅度异常、高频噪声、相关性偏低及掉线等坏道线索。	Screen comparable channel groups for unusual amplitude, high-frequency noise, low correlation and dropouts.
借助真实ECG导联，检查EEG中是否存在与心电事件重复锁时的成分。	Use a real ECG channel to check EEG for components repeatedly time-locked to cardiac events.
借助真实EOG导联，检查眼动或眨眼事件附近EEG中的重复锁时成分。	Use a real EOG channel to check EEG for recurring components near eye movements or blinks.
定位高频突发，并把一般高频线索与具有独立EMG支持的候选分开。	Locate high-frequency bursts and distinguish generic indicators from candidates supported by independent EMG.
把来源睡眠分期与选区对齐，明确各阶段覆盖及未知时间。	Align source sleep stages with the selected range and report stage coverage and unknown intervals.
核对所选时间内的任务事件及其原始样本位置，保留事件来源。	Check task events and their original sample positions within the selected range, retaining provenance.
把来源标注的发作等临床事件映射到选区，帮助解释病理信号与算法候选的关系。	Map annotated seizures and other clinical events to the selected range to support review of pathological signals alongside algorithm candidates.
把本次实际选定的方法结果、未评原因和失败状态放在同一份可追溯记录中。	Combine results, assessment gaps and failures of the selected methods into one traceable record.
让候选可以被人复核，并能追溯到原文件、选区、参数和软件版本。	Support manual review and trace each candidate to the original file, analysis range, parameters and software version.
用成熟库补充相邻样本突变和平线筛查，并保留时间段与通道两种输出。	Add adjacent-sample change and flat-segment screening through an established library, retaining both interval and channel outputs.
在满足高频采样条件时，补充独立于基础HF方法的全选区肌电样高频线索。	When high-frequency sampling requirements are met, add muscle-like indicators across the selected range independently of the basic HF method.
检查通道对是否异常相似，为可能的电极桥接提供线索。	Check channel pairs for unusually similar signals that may indicate electrode bridging.
根据通道间局部密度差异，补充整段波形异常通道候选。	Use differences in local density between channel waveforms to identify outlier candidates over the full selected range.
探索数据驱动的全局EEG峰峰值阈值，补充固定阈值之外的分段描述。	Explore a data-driven global EEG peak-to-peak threshold to complement fixed-threshold segment descriptions.
计划增加空间预测一致性检查，补充现有PREP非空间指标。	Planned spatial-prediction consistency checks to complement the existing non-spatial PREP measures.
计划对足够且可比较的试次或窗口，估计局部通道阈值与试次复核建议。	Planned local channel thresholds and epoch-review suggestions for sufficiently many comparable trials or windows.
计划借助ICA成分类别提示，帮助人工区分脑、眼、肌肉等可能来源。	Planned ICA component-class suggestions to support manual identification of possible brain, eye and muscle sources.
界面语言	Interface language
读取本机数据文件	Read a local data file
本机文件	Local file
多文件记录请一起打包 ZIP。	Package all files of a multi-file recording together as a ZIP archive.
数据工作台	Data workbench
上传文件后，先提取基本信息。	Upload a file to extract its basic information.
质控模块	QC modules
自动提取的信息	Automatically extracted information
文件读取	File reading
细胞外电生理	Extracellular electrophysiology
其他模态	Other modality
分析模态	Analysis modality
建议模态	Suggested modality
尚未解析	Not yet parsed
未检出标注	No annotations detected
多个原生采样率	Multiple native sampling rates
文件标注	File annotations
保留原始标签，尚未确认其含义。	Original labels are retained; their meaning has not been confirmed.
模态与通道类型依据	Evidence for modality and channel types
文件类型和通道声明不等于采集位置，分析模态需确认。	File and channel types do not establish recording locations. Confirm the analysis modality.
不使用	Unused
分析信号	Analysis signal
EOG 辅助	EOG auxiliary
ECG 辅助	ECG auxiliary
EMG 辅助	EMG auxiliary
联耳参考	Linked-ear reference
补充信息	Additional information
未知项可保留	Unknown values may remain unknown
疾病标签用于背景与复核，不自动改变质量阈值。	Clinical tags provide context for review; they do not automatically change QC thresholds.
以下角色为待确认建议。分析与辅助信号须共享采样率。	These role suggestions require confirmation. Analysis and auxiliary signals must share a sampling rate.
请核对通道角色与原生采样率。	Check channel roles and native sampling rates.
确认通道角色	Confirm channel role
参考与来源（可选）	Reference and source (optional)
来源与背景补充	Source and additional context
已核对分析模态和通道角色。	I have checked the analysis modality and channel roles.
确认不会启动检查。	Confirmation does not start a check.
请根据采集资料确认分析模态。	Confirm the analysis modality using the acquisition documentation.
请至少选择一条分析信号。	Select at least one analysis signal.
请选择非空数据文件或 ZIP，最大 512 MiB。	Select a nonempty data file or ZIP archive no larger than 512 MiB.
读取电生理文件、核对信息并生成质控方案。	Read electrophysiology files, review metadata and prepare a QC plan.
采样率未知	Sampling rate unknown
未指定分析配置	No analysis profile specified
适用性由预览计划进一步核对。	Preview the plan to check applicability.
打开模块查看说明	Open the module for details
方法	Method
未提供理由	No rationale provided
需先补充	Required first
可保留未知	May remain unknown
未提供原因	No reason provided
未提供摘要	No summary provided
请先补充必需字段，或确认输入条件。	Complete the required fields or check the input requirements.
下方显示这次运行保存的方案与结果。选择数据后可准备新的检查。	The saved plan and results for this run are shown below. Select data to prepare a new check.
MNE 相邻采样变化 / 平线	MNE adjacent-sample changes / flat segments
MNE 跨通道高频线索	MNE cross-channel high-frequency indicators
MNE 电极桥接候选	MNE electrode-bridging candidates
MNE LOF 通道离群候选	MNE LOF channel-outlier candidates
autoreject 全局阈值估计	autoreject global threshold estimation
按相邻采样点差分定位平线/变化候选，分别保留时间标注与通道建议；默认未启用peak阈值。	Use adjacent-sample differences to identify flat/change candidates, retaining time annotations and channel suggestions separately. The peak threshold is disabled by default.
用MNE默认110–140 Hz频带和跨选中EEG通道包络分数，产生探索性时间候选。	Use MNE’s default 110–140 Hz band and an envelope score across selected EEG channels to generate exploratory time candidates.
用成对电压差的方差和MNE分布拟合识别桥接候选；不等于已确认短接。	Use the variance of pairwise voltage differences and MNE distribution fitting to identify bridging candidates, not confirmed shorts.
按选中EEG波形之间的局部离群因子提供通道候选；不自动判定信号无效。	Use local outlier factors between selected EEG waveforms to flag channel candidates, without automatically declaring signals invalid.
把连续片段分成固定长度段，用全局交叉验证估计EEG峰峰值阈值；不执行剔除。	Split continuous data into fixed segments and estimate an EEG peak-to-peak threshold by global cross-validation. No data are rejected.
核对文件指纹、EDF结构、采样流与连续段。	Check the file fingerprint, EDF structure, sampling streams and continuous segments.
冻结选道、原生采样时间窗、辅助导联和参考比较组。	Freeze channel selection, native-sample analysis range, auxiliary channels and reference comparison groups.
检查非有限样本、恒值与端点平台；可选MNE平线和autoreject全局阈值。	Check non-finite samples, flat segments and endpoint plateaus, with optional MNE flat-segment and autoreject global-threshold methods.
独立计算Welch PSD、Thomson工频及FOOOF频谱特征。	Compute Welch PSD, Thomson line-frequency measures and FOOOF spectral features independently.
计算PREP非空间分项；可选MNE桥接和LOF，按各自参考及通道条件运行。	Compute non-spatial PREP indicators. Optional MNE bridging and LOF methods use their own reference and channel requirements.
独立计算ECG/EOG锁时线索和高频突发；使用M03区间作为肌电保护区。	Compute ECG/EOG-locked indicators and high-frequency bursts independently. Use M03 intervals as protection regions for muscle analysis.
读取任务、睡眠分期或临床事件表，核对范围并保留记录原始时间。	Read task, sleep-stage or clinical-event tables, check ranges and retain the original recording timeline.
汇总已选模块的执行状态、观察量和未评原因。	Summarize execution states, measurements and assessment gaps for selected modules.
生成本地HTML、波形PNG和结构化证据，等待人工复核。	Generate a local HTML report, waveform PNGs and structured evidence for manual review.
独立调度适配；方法级与数据级验证范围需分别核对，执行成功不代表质量合格。	Modules run through independent adapters. Check method-level and dataset-level validation separately; successful execution does not establish acceptable quality.
接入	Intake
计划	Planning
检查	Checks
汇总	Summary
报告	Report
已登记原始文件	Registered original file
来源指纹	Source fingerprint
技术头核对	Technical header checks
技术元信息	Technical metadata
显式配置	Explicit configuration
冻结配置	Frozen configuration
原始时钟选区	Analysis range on the original clock
原始电压	Original voltage
逐道标定	Per-channel calibration
连续性候选	Continuity candidates
样本区间	Sample intervals
可选固定段幅度阈值	Optional amplitude threshold for fixed segments
采样率与分析范围	Sampling rate and analysis range
工频候选	Line-frequency candidates
频谱拟合	Spectral fit
明确比较组	Explicit comparison groups
扩展所需参考构型	Reference configuration required by extensions
通道候选	Channel candidates
分项指标	Individual measures
可选电极对候选	Optional electrode-pair candidates
可选ECG/EOG/EMG	Optional ECG/EOG/EMG
M03连续性候选	M03 continuity candidates
辅助事件	Auxiliary events
高频突发	High-frequency bursts
EMG支持状态	EMG support status
明确类型的标注文件	Annotation file with an explicit type
选区事件	Events in the selected range
阶段覆盖或临床事件时长	Stage coverage or clinical-event duration
标注指纹	Annotation fingerprint
模块结果或未评状态	Module results or unassessed states
分项摘要	Findings summary
未校准总分说明	Uncalibrated score notice
分项结果	Individual findings
原始选区	Original analysis range
HTML报告	HTML report
波形PNG	Waveform PNG
结果JSON	Result JSON
总分未校准，固定为null；执行完成率不作为质量评分。	The overall score is uncalibrated and fixed at null. Execution completion is not a quality score.
尚无人工意见回写或审核版本提交；不自动删除原数据。	Manual review write-back and reviewed-version submission are not implemented. Original data are not automatically deleted.
任务、分期和发作标注都不是质量真值；外部同步准确性未验证。	Task, sleep-stage and seizure annotations are not quality ground truth. External synchronization accuracy has not been validated.
缺辅助导联时不能确认相应生理伪迹；不执行ICA或自动清理。	The corresponding physiological artifact cannot be confirmed without auxiliary channels. No ICA or automatic cleaning is performed.
最多120秒；不自动重参考或跨采样流对齐。	At most 120 seconds. No automatic re-referencing or alignment between sampling streams.
本版服务接入仅支持EDF；结构可读不等于科学有效。	This service version supports EDF intake only. Readable structure does not establish scientific validity.
尚未实现一般重复数据块和断续检测；平台是待复核候选。	General repeated-block and discontinuity detection is not implemented. Plateaus are candidates for review.
未实现专门漂移判定；分析范围会改变工频多重比较族。	Dedicated drift classification is not implemented. The analysis range affects the line-frequency multiple-comparison family.
EEG模块化质控工作台	QC Workbench
EEG 质控工作台	QC Workbench
数据质控	Data quality control
读取文件，了解信号质量。	Read a file to inspect its signal quality.
跳到工作台	Skip to workbench
工作台导航	Workbench navigation
上传文件	Upload file
读取文件	Read file
信息提取	File information
数据格式	Data format
格式	Format
通道数	Channels
记录时长	Recording duration
采样率	Sampling rate
模态	Modality
标注	Annotations
自动提取	Extracted automatically
待确认	Needs confirmation
疾病背景	Clinical background
年龄组	Age group
年龄分组	Age group
记录任务	Recording task
任务场景	Task context
未知	Unknown
参考构型	Reference configuration
采集参考构型	Acquisition reference
确认并推荐	Confirm and recommend
推荐质控流程	Recommended QC workflow
查看模块	View module
没有文件	No file
读取后显示	Shown after reading
质控流程	QC workflow
检查记录	Checks
方法工具箱	Method toolkit
质控标准	QC standards
中文来源	Chinese source
中文原文	Original Chinese text
连接本地服务…	Connecting to local service…
本地服务已连接	Local service connected
本地服务未连接	Local service disconnected
读取本机 EDF 文件	Read a local EDF file
读取本机文件	Read a local file
本机 EDF	Local EDF file
仅在本机处理 · 最大 512 MiB	Processed locally · Maximum 512 MiB
继续确认	Resume confirmation
框架预览	Workflow preview
上传 EDF 后，流程将按数据更新。	Upload an EDF file to adapt the workflow to your data.
上传文件后，流程将按数据更新。	Upload a file to adapt the workflow to your data.
质控模块流程图	QC module workflow
点击模块查看说明	Select a module for details
技术规范 ↗	Technical specification ↗
模块执行状态	Module execution status
配置与适用条件	Configuration and applicability
已读取记录	Registered recordings
记录	Recording
选择已登记记录	Select a registered recording
数据与可选设置	Data and optional settings
已读取文件	File read
数据来源与标签	Provenance and tags
数据来源、用途与标注边界	Data provenance, use and annotation limits
数据标签	Data tags
来源信息	Provenance
选择记录后显示来源标签。	Select a recording to view its provenance tags.
分析时段与背景	Analysis range and context
分析时段	Analysis range
单次 ≤ 120 秒	Up to 120 s per run
起点	Start
秒	s
时长	Duration
时段按原始记录的时间轴计算。	Times refer to the original recording timeline.
分析背景（可选）	Analysis context (optional)
不清楚时保留“未知”。技术标签由文件和配置生成，不在这里修改。	Keep unknown information as Unknown. Technical tags come from the file and configuration.
背景用于解释与后续分层，本版不据此修改质量阈值或打分，也不构成诊断或来源真值。	Context supports interpretation and later stratification. It does not change QC thresholds or scores and is not a diagnosis or verified ground truth.
通道、参考与配置	Channels, reference and configuration
选择记录后显示明确配置。	Select a recording to view its explicit configuration.
高级设置	Advanced settings
手动选择方法与参数	Choose methods and parameters manually
修改后会保留你的配置；重新预览计划即可继续。	Your changes are retained. Preview the updated plan to continue.
正在读取模块目录	Loading module catalog
M06 依赖 M03；规划时会自动补齐依赖，并说明原因。	M06 requires M03. Planning adds the dependency and explains why.
修改扩展参数	Edit extension parameters
JSON 按扩展 ID 分组；只写需覆盖的参数，留空对象使用方法默认值。应用后须重新预览计划，服务会核验参数。	Group JSON parameters by extension ID. Specify overrides only; an empty object uses defaults. Preview the plan again to validate changes.
扩展参数 JSON	Extension parameters (JSON)
应用参数修改	Apply parameters
手动推荐与预览	Recommendations and preview
需要回到推荐配置时，可恢复推荐方案。	Restore the recommended configuration when needed.
恢复推荐方案	Restore recommendation
采用推荐	Apply recommendation
预览执行计划	Preview execution plan
检查方案	Check plan
准备中	Preparing
确认文件后，自动准备检查方案。	Confirm the file to prepare a check plan automatically.
开始检查	Start check
方案准备好后即可开始。	Start once the plan is ready.
当前运行	Current run
等待开始	Not started
检查结果会显示在这里	Results will appear here
开始检查后，可查看进度、结果和报告。右侧保留已有运行记录。	Start a check to view progress, results and the report. Previous runs remain available in history.
已选模块的执行进度，非质量分数	Execution progress of selected modules, not a quality score
取消运行	Cancel run
打开实际报告	Open report
刷新状态	Refresh status
运行记录	Run history
刷新运行记录	Refresh run history
正在读取运行记录	Loading run history
正在读取运行记录。	Loading run history.
读取目录中	Loading catalog
按需浏览方法，查看原理、适用条件和来源。	Browse methods, their principles, requirements and sources.
检查目的	Check purpose
全部目的	All purposes
数据与元信息	Data and metadata
伪迹线索	Artifact indicators
事件与时间	Events & timing
结果与报告	Results and reporting
当前接入：头皮 EEG	Current scope: scalp EEG
仅复核已保存的位置；完整计数见模块证据。	Only saved locations are available for review; see module evidence for complete counts.
候选证据有范围限制，请展开核对。	Candidate evidence has coverage limitations. Expand to review them.
候选详情已截断；当前仅复核已保存的位置，完整计数见模块证据。	Candidate details are truncated. Only saved locations are available for review; see module evidence for complete counts.
观察区间数	Observed intervals
已存区间数	Stored intervals
未存区间数	Omitted intervals
方法目录	Method catalog
方法范围：ECoG	Method scope: ECoG
方法范围：头皮 EEG	Method scope: scalp EEG
当前记录 / 默认目录	Current record / default catalog
记录目录格式不完整。	The record inventory is incomplete.
字段与方案	Metadata and plan
确认与规划	Confirm and plan
结果汇总	Result summary
报告与复核	Report and review
读取来源文件、通道和原生时间信息。	Read source files, channels and native timing.
确认关键字段，再生成适用的检查方案。	Confirm key metadata, then prepare an applicable check plan.
检查缺失、恒值等信号完整性问题。	Check signal integrity, including missing and constant values.
描述频谱与可能的窄带干扰。	Describe the spectrum and potential narrow-band interference.
核对各通道的描述量和质量线索。	Review per-channel measurements and quality indicators.
按信号类型和辅助信息评估伪迹线索。	Assess artifact indicators according to signal type and auxiliary information.
核对事件与原始记录时间。	Check events against the original recording timeline.
汇总已完成、未评和受限的结果。	Summarize completed, unassessed and limited results.
生成证据报告，并结合波形复核。	Generate an evidence report and review it with waveforms.
读取并确认记录后，显示适用的方法与条件。	Applicable methods and requirements appear after the recording is read and confirmed.
模态建议来自文件声明，待核对	Modality suggested from file declarations; verify it
含混合通道，请选择分析组	Mixed channel types; select an analysis group
模态待确认	Modality needs confirmation
当前接入：ECoG	Current scope: ECoG
已接入头皮EEG科研检查；检测准确率与总分仍需独立验证。	Scalp EEG research checks are integrated. Detection accuracy and an overall score still require independent validation.
皮层表面脑电基础检查；不套用头皮EEG坏道或伪迹阈值。	Basic surface cortical EEG checks; scalp EEG bad-channel and artifact thresholds are not applied.
当前ECoG基础描述路线；仅声明工程执行范围，不代表伪迹准确性已验证，不迁移头皮判坏阈值。	The basic ECoG route declares execution scope only. Artifact accuracy is not validated, and scalp rejection thresholds are not transferred.
接触点描述	Contact descriptions
核对ECoG来源文件、格式结构、原生时钟及单位；模态来自明确确认。	Check ECoG source files, format structure, native timing and units. Modality requires explicit confirmation.
读取器可读不证明电极位置；只有明确确认的ECoG分析通道可进入此路线。	Reader compatibility does not establish electrode location. This route requires explicitly confirmed ECoG analysis channels.
冻结ECoG分析触点、原生时间窗和来源声明；不推断空间邻接或重新参考。	Freeze ECoG contact selection, native time bounds and source declarations. Do not infer spatial adjacency or re-reference signals.
已确认ECoG的源通道索引	Source indices of confirmed ECoG channels
原生采样率和电压单位	Native sampling rate and voltage units
明确时间范围	Explicit time range
描述非有限样本段与至少两个相邻完全相等样本的恒值段。	Describe non-finite intervals and runs of at least two adjacent samples with exactly equal values.
原始样本区间	Original sample intervals
非有限及精确恒值描述	Non-finite and exact-constant descriptions
恒值描述不是已确认伪迹；无头皮幅度或时长坏段阈值，不自动删除样本。	Constant-value intervals are not confirmed artifacts. No scalp amplitude or duration rejection threshold is used, and no samples are removed.
计算Welch PSD与已配置窄带的功率、峰值位置描述。	Calculate Welch PSD and describe power and peak locations in configured narrow bands.
PSD及单位	PSD and units
窄带描述量	Narrow-band measurements
不可测原因	Reasons a measurement is unavailable
不调用头皮FOOOF/α功率判定、Thomson阈值或肌电阈值；高频和病理活动不判坏。	Do not apply scalp FOOOF/alpha criteria, Thomson thresholds or muscle thresholds. High-frequency or pathological activity is not classified as bad.
逐触点描述有限样本数、均值、标准差、RMS与峰峰值。	Describe each contact's finite-sample count, mean, standard deviation, RMS and peak-to-peak amplitude.
原始ECoG电压	Original ECoG voltage
稳定源通道身份	Stable source-channel identity
逐触点描述统计	Per-contact descriptive statistics
不调用PREP、LOF、桥接或跨触点阈值；不从触点名推测空间关系或坏触点。	Do not apply PREP, LOF, bridging or cross-contact thresholds. Do not infer spatial relationships or bad contacts from contact names.
ECoG生理伪迹方法尚未接入，选中也明确保留未评。	Physiological artifact methods for ECoG are not integrated. They remain unassessed even if selected.
未接入原因	Reason not integrated
头皮ECG/EOG/肌电阈值不迁移至ECoG。	Scalp ECG, EOG and muscle thresholds are not transferred to ECoG.
本项目ECoG独立实现	Independent ECoG implementation in this project
明确确认为ECoG且电压和原生采样时间已核验。	ECoG modality is explicitly confirmed, with verified voltage units and native timing.
未确认模态、单位、采样时钟，或试图使用头皮判坏阈值。	Modality, units or timing are unconfirmed, or scalp rejection thresholds are being requested.
仅声明实现与工程执行范围；不宣称坏触点或伪迹准确性已验证。	Implementation and execution scope only; bad-contact and artifact accuracy are not claimed to be validated.
本项目描述性实现；不调用头皮检测流水线。	Descriptive implementation in this project; the scalp detection pipeline is not called.
非有限与精确恒值段	Non-finite and exact-constant intervals
定位非有限值及连续完全相等样本。	Locate non-finite values and consecutive samples with exactly equal values.
原时钟样本区间与数量。	Sample intervals and counts on the original clock.
至少2个相邻完全相等样本只是描述，不等于已确认伪迹。	At least two adjacent exactly equal samples are a descriptive finding, not a confirmed artifact.
ECoG Welch功率谱	ECoG Welch power spectrum
保留原始ECoG频率能量的描述。	Describe the frequency-energy distribution of the original ECoG signal.
Hann窗、50%重叠、常量去均值的Welch密度估计，单位V²/Hz。	Welch density estimate using Hann windows, 50% overlap and constant detrending, in V²/Hz.
不进行α谱模型或高频判坏；去均值只用于PSD估计，不覆盖原始信号。	No alpha-spectrum model or high-frequency rejection is applied. Detrending is used only for PSD estimation and does not overwrite the source signal.
ECoG窄带功率描述	ECoG narrow-band power description
描述配置频率附近的可测功率及峰值。	Describe measurable power and peaks near configured frequencies.
在同一PSD的±max(1Hz,频率分辨率)频带测量；不进行阈值分类。	Measure within ±max(1 Hz, frequency resolution) on the same PSD; do not classify using a threshold.
窄带峰值不证明干扰来源，不排除生理或病理活动；未自动扩展谐波。	Narrow-band peaks do not establish an interference source or exclude physiological or pathological activity. Harmonics are not added automatically.
ECoG触点描述统计	ECoG contact descriptive statistics
提供原始触点的有限样本统计。	Provide finite-sample statistics for original contacts.
各触点独立均值、标准差、RMS、峰峰值与非有限计数。	Independent per-contact mean, standard deviation, RMS, peak-to-peak amplitude and non-finite count.
没有比较组阈值，不凭幅度、相关性、触点名称或病理标签判坏。	No comparison-group threshold is used. Amplitude, correlation, contact names and pathological labels do not determine bad contacts.
已确认ECoG电压	Confirmed ECoG voltage
原生时钟和源索引	Native clock and source indices
不支持未建模的断续EDF、EEGLAB分段数据和分卷FIF；多文件须完整。文件可读不证明采集位置，ECoG须明确确认，不自动重采样。	Unmodeled discontinuous EDF, epoched EEGLAB and split FIF are unsupported; companion files must be complete. Readability does not establish acquisition location. ECoG requires explicit confirmation, with no automatic resampling.
按格式读取器核验源单位与标定，统一返回原始物理电压V；不对波形重参考、插值或重采样。	Verify source units and calibration through the format reader and return original physical voltage in V. No re-referencing, interpolation or resampling is performed.
已明确确认ECoG，分析及辅助通道电压单位可核验时。	ECoG is explicitly confirmed and voltage units can be verified for analysis and auxiliary channels.
单位未知或所选通道不是电压时不得进入ECoG分析；不凭触点名猜单位。	Unknown units or non-voltage channels prevent ECoG analysis. Units are not inferred from contact names.
按实际格式使用BrainElecQC或MNE读取器；ECoG测量不调用头皮判坏阈值。	Use BrainElecQC or MNE readers according to the format. ECoG measurements do not call scalp rejection thresholds.
先核实ECoG模态、分析通道及电压单位。	First verify ECoG modality, analysis channels and voltage units.
ECoG输入与配置	ECoG input and configuration
配置未通过ECoG入口核验；未自动移除或改写不相容参数。	The configuration failed ECoG intake checks. Incompatible parameters were not removed or changed automatically.
建议基础完整性、频谱观察与逐触点统计；不使用头皮EEG坏道或伪迹阈值。	Recommend basic integrity checks, spectral observations and per-contact statistics, without scalp EEG bad-channel or artifact thresholds.
根据已确认ECoG模态和技术信息生成基础检查计划。	Generate a basic check plan from confirmed ECoG modality and technical metadata.
逐触点结合原始波形和采集资料复核；异常幅度、谱峰或高频不自动等于坏道。	Review each contact with its original waveform and acquisition information. Unusual amplitude, spectral peaks or high frequencies do not automatically indicate a bad channel.
发作、癫痫样放电与生理高频可能是研究目标，不作为伪迹真值或扣分依据。	Seizures, epileptiform discharges and physiological high-frequency activity may be research targets; they are not artifact ground truth or grounds for score deductions.
当前为ECoG基础描述流程；不运行PREP、头皮桥接/LOF、FOOOFα指标或肌电阈值。	This is a basic descriptive ECoG workflow. It does not run PREP, scalp bridging/LOF, FOOOF alpha measures or muscle thresholds.
不根据触点名推测电极邻接、脑区、共同参考或植入位置。	Do not infer electrode adjacency, brain region, common reference or implant location from contact names.
工频附近能量只作观察量，不以固定比值自动判定污染。	Energy near line frequency is an observation only; a fixed ratio does not automatically classify contamination.
计算完成不表示信号质量合格，总分保持null；当前未校准ECoG检测准确率。	Completed computation does not establish acceptable signal quality. The overall score remains null; ECoG detection accuracy is not calibrated.
参考尚未核实；基础逐触点描述仍可运行，不进行跨触点相似性判定。	The reference is unverified. Basic per-contact descriptions can run, without cross-contact similarity judgments.
滤波史未知；谱形和工频观察只能结合源记录说明解释。	Filter history is unknown. Interpret spectral shape and line-frequency observations alongside source-record information.
尚未登记支持的事件表；文件内事件描述不自动解释为临床或质量标注。	No supported event table is registered. File event descriptions are not automatically interpreted as clinical or quality annotations.
读取与确认	Read and confirm
正在读取模块目录	Loading module catalog
ECoG 触点	ECoG contacts
分析通道	Analysis channels
参考比较组（按分析通道索引顺序配置）	Reference comparison groups (in analysis-channel index order)
未被当前配置指定为分析通道或辅助导联。	Not selected as an analysis or auxiliary channel in this configuration.
配置未明确指定分析通道索引，不能运行。	Analysis channel indices are not explicitly configured; analysis cannot start.
当前模态仅保存提取信息，不运行其他模态的质控。	Only extracted information is saved for this modality; QC from another modality is not applied.
分析通道和辅助导联必须处于相同原生采样率；请取消不同采样率的信号，不会自动重采样。	Analysis and auxiliary channels must share a native sampling rate. Deselect channels at other rates; no automatic resampling is performed.
服务尚未提供此模态的质控目录，未套用其他模态方法。	The service has not provided a QC catalog for this modality. Methods from another modality were not applied.
随模块运行	Runs with module
满足条件	When eligible
手动扩展	Manual extension
功能域未声明	Functional domain not declared
启用方式未声明	Activation not declared
适用模态	Applicable modalities
计划适用模态	Intended modalities
目录未声明计划适用模态。	The catalog does not declare intended modalities.
目录未声明适用模态。	The catalog does not declare applicable modalities.
模块内的方法按条件运行；手动扩展需明确启用。待接入方法仅供查阅。	Methods run when their requirements are met. Enable manual extensions explicitly. Planned methods are listed for reference.
当前筛选没有方法。可切换检查目的或接入状态。	No methods match these filters. Change the purpose or availability filter.
计划面向头皮 EEG；尚未接入，未完成本平台执行验证。未声明其他模态支持。	Planned for scalp EEG; not integrated or execution-validated in this platform. Support for other modalities is not declared.
当前声明的质控工程执行范围仅限头皮 EEG。读器提取其他模态元信息，不表示已验证其质控流程；通用处理思路不等于跨模态支持。	The current QC execution scope is scalp EEG. Extracting metadata from other modalities does not validate their QC workflows or establish cross-modality support.
当前已验证的工程执行范围仅限头皮 EEG，仍需满足本方法条件；不表示已验证科学准确性或其他脑电模态。	Execution has been checked for scalp EEG only, subject to this method’s requirements. This does not establish scientific accuracy or validation for other modalities.
方法类别	Method category
全部类别	All categories
通用	General
条件	Conditional
可选	Optional
接入状态	Availability
全部状态	All states
已接入	Available
待接入	Planned
连接本地服务后显示方法目录。	Connect to the local service to load the method catalog.
本地 EEG 质控	Local EEG quality control
详细介绍 ↗	Detailed introduction ↗
（新标签页）	(new tab)
关闭模块详情	Close module details
未提供	Not provided
大小未提供	Size unavailable
时间未提供	Time unavailable
流程框架	Workflow framework
就绪	Ready
等待	Pending
排队中	Queued
运行中	Running
正在取消	Cancelling
正在取消…	Cancelling…
已完成	Completed
条件受限	Limited applicability
当前不可用	Unavailable for this data
尚未接入	Not implemented
待规划	Not planned
未选择	Not selected
已跳过	Skipped
失败	Failed
已取消	Cancelled
已中断	Interrupted
已选择	Selected
固定步骤	Required step
计算完成	Calculation complete
部分可评	Partially assessable
未执行	Not run
执行失败	Execution failed
等待执行	Awaiting execution
执行状态未确认	Execution status unknown
数据接入	Data intake
数据识别	Data characterization
信号完整性	Signal integrity
频谱干扰	Spectral interference
通道质量	Channel quality
生理伪迹	Physiological artifacts
状态与事件	States and events
分项评价	Evidence summary
质控报告	QC report
数据接入与结构核验	Data intake and structure checks
数据画像与检查计划	Data characterization and check plan
频谱与干扰	Spectrum and interference
坏通道候选	Bad-channel candidates
生理伪迹线索	Physiological artifact indicators
状态和事件检查	State and event checks
分项评价与可比性	Evidence summary and comparability
报告与人工复核	Reporting and manual review
读取与识别	Intake and characterization
质量检查	Quality checks
汇总与报告	Summary and report
依赖 M03	Requires M03
查看模块详情	View module details
状态未载入	Status not loaded
运行状态尚未载入。	Run status has not been loaded.
正在提交	Submitting
等待服务确认，勿重复提交。	Awaiting service confirmation. Do not submit again.
读取中	Reading
读取文件信息后，确认通道。	Confirm the channels after reading the file information.
确认文件信息后，生成检查方案。	Confirm the file information to generate a check plan.
待读取	Awaiting file read
点击“读取文件”以继续。	Select “Read file” to continue.
准备方案	Preparing plan
方案就绪	Plan ready
待核对	Needs validation
图中颜色表示执行状态，质量结论见报告。	Colors indicate execution status. See the report for quality findings.
请先读取 EDF 文件。	Read an EDF file first.
请先读取本机文件。	Read a local file first.
请填写分析起点和时长。	Enter the analysis start time and duration.
分析起点必须是大于或等于 0 的秒数。	The start time must be at least 0 seconds.
分析时长必须大于 0 秒。	The duration must be greater than 0 seconds.
单次分析最多 120 秒，请修改时长。	The maximum duration is 120 seconds. Adjust the range.
配置未明确指定 EEG 通道索引，不能运行。	Explicit EEG channel indices are required before running.
本地服务未返回 JSON。请从工作台服务入口打开页面。	The local service did not return JSON. Open the page through the workbench service.
请求超时，提交状态尚不确定。请先刷新运行记录，确认是否已创建任务，避免重复提交。	The request timed out; submission status is unknown. Refresh run history before retrying to avoid a duplicate job.
读取或确认请求超时，状态尚不确定；不会自动重试。若已有读取编号，可恢复后确认。	The read or confirmation request timed out. Its status is unknown and it will not be retried automatically. Resume the intake if an ID is available.
本地服务响应超时，请稍后重试。	The local service timed out. Try again later.
无法连接本地服务。请确认工作台服务仍在运行，再重试。	Cannot connect to the local service. Check that it is running and try again.
当前筛选没有方法。可切换类别或接入状态。	No methods match these filters. Change the category or availability filter.
正在准备推荐方案…	Preparing recommendations…
核对数据条件后即可开始检查。	Start after the data requirements have been checked.
手动方案 · 修改已保留	Manual plan · Changes retained
方案已就绪。	The plan is ready.
开始检查时会先核对最新配置。	The latest configuration will be checked before starting.
推荐方案尚未就绪。	The recommended plan is not ready.
重新准备推荐方案	Prepare recommendations again
推荐方案已就绪	Recommended plan ready
正在核对推荐方案	Validating recommended plan
方案核对未完成	Plan validation incomplete
推荐已生成，尚未采用	Recommendation available, not yet applied
需要补充信息	More information needed
检查模块	Check modules
默认增强	Default enhancement
保留原始数据，报告候选与待复核项。	Preserve the original data and report candidates for review.
推荐理由与方法详情	Recommendation rationale and methods
复核重点	Review priorities
建议采用的方法与理由	Recommended methods and rationale
可按需添加的方法	Optional methods
当前不可用的方法	Unavailable methods
可补充字段	Optional information
解释与使用边界	Interpretation and limitations
推荐配置与原始依据	Recommended configuration and original evidence
查看方法依据	View method rationale
正在核对…	Validating…
核对手动方案	Validate manual plan
正在准备检查…	Preparing check…
正在准备推荐…	Preparing recommendation…
已采用推荐	Recommendation applied
正在核对并提交这份方案，请勿重复操作。	Validating and submitting this plan. Please do not submit again.
正在根据这份数据准备推荐方案，不会自动运行。	Preparing a recommended plan for this data. Analysis will not start automatically.
正在核对最新方案的适用条件。	Checking the requirements of the latest plan.
正在查看已有运行。选择一份数据可准备新的检查。	Viewing a previous run. Select a recording to prepare a new check.
手动方案已就绪，点击开始检查。	The manual plan is ready. Select Start check.
推荐方案已就绪，点击开始检查。	The recommended plan is ready. Select Start check.
手动修改已保留。点击开始检查后会先核对最新方案。	Manual changes are retained. The latest plan will be validated when you select Start check.
方案尚未就绪，可点击恢复推荐方案重试。	The plan is not ready. Restore the recommendation to try again.
辅助导联	Auxiliary channels
分析 EEG	Analysis EEG
当前配置未指定 ECG / EOG / EMG 辅助导联，不按名称推测。	No ECG / EOG / EMG channel is explicitly configured. Roles are not inferred here from names.
配置未提供比较组，不自动生成。	Comparison groups were not provided and are not generated automatically.
角色来自当前配置，# 为原始通道索引（从 0 开始）。同名通道按索引区分。	Roles come from the current configuration. # is the original zero-based channel index; indices distinguish duplicate names.
参考比较组（按 EEG 索引顺序配置）	Reference comparison groups (in EEG index order)
未被当前配置指定为分析 EEG 或辅助导联。	Not selected as analysis EEG or an auxiliary channel.
查看完整生效配置	View complete effective configuration
配置未提供	Configuration unavailable
未配置	Not configured
索引未匹配	Unmatched index
请调整下方选道：需要 EEG，且采样率一致。	Adjust the channels below: select EEG channels with a common sampling rate.
以下角色为按名称提出的待确认建议。	These name-based role suggestions require your confirmation.
原始信号	Original signal
技术字段	Technical fields
建议角色	Suggested role
单位未知	Unknown unit
名称、参考与背景（可选）	Name, reference and context (optional)
记录名称	Recording name
不知道时保留未知，相关方法会受限。	Keep unknown values as Unknown; related methods will be limited.
来源说明	Source description
已知实验或来源，可留空	Known experiment or source (optional)
这是头皮 EEG，使用当前识别结果。	This is scalp EEG; use the current identification.
确认并准备方案	Confirm and prepare plan
读取详情	Intake details
未知参考和背景保持未知；确认不会启动检查。	Unknown reference and context remain unknown. Confirmation does not start a check.
当前只接入头皮 EEG；请明确确认真实模态，ECoG/sEEG 等不能按头皮 EEG 登记。	Only scalp EEG is supported. Confirm the actual modality; ECoG/sEEG must not be registered as scalp EEG.
请先核对并勾选字段确认。	Review the fields and check the confirmation box first.
请至少明确选择一条 EEG 导联。	Explicitly select at least one EEG channel.
所选索引与读取结果不匹配，请重新核对。	The selected indices do not match the intake. Review the channels again.
当前 EEG 和辅助导联必须处于相同原生采样率；请取消不同采样率的信号，不会自动重采样。	Selected EEG and auxiliary channels must share a native sampling rate. Deselect channels with a different rate; no automatic resampling is performed.
请选择非空 EDF，最大 512 MiB。	Select a nonempty EDF file no larger than 512 MiB.
正在读取…	Reading…
读取结果不完整，请重试。	The intake response is incomplete. Try again.
读取完成	File read
读取未完成	File read incomplete
已恢复文件	Intake restored
文件已登记，请重新连接	File registered; reconnect to continue
已恢复读取结果，请确认选道	Intake restored; confirm the channels
正在准备…	Preparing…
服务未确认登记成功，请恢复读取状态后核对。	Registration was not confirmed. Resume the intake and check its status.
方案已就绪	Plan ready
方案未完成，请重试	Plan incomplete; try again
点击模块查看输入、输出、依赖与证据。预览计划后会显示实际适用性。	Open a module to view inputs, outputs, dependencies and evidence. Preview the plan to check applicability.
本次运行的原始计划	Original plan for this run
当前计划	Current plan
所选模块的依赖已完整，无需额外补齐。	All dependencies of the selected modules are included.
当前数据不满足以下已选方法的条件	The data do not meet the requirements of these selected methods
这些方法不会因所属模块被选中而自动满足条件。	Selecting a parent module does not satisfy its methods’ requirements.
当前参数	Current parameters
此计划没有方法级适用性记录。	This plan contains no method-level applicability record.
服务未提供具体原因	The service did not provide a reason
未提供具体原因	No reason provided
计划响应缺少 plan_id 或 nodes，未启用运行。	The plan response is missing plan_id or nodes. Running remains disabled.
高级参数有误，请展开高级设置修正。	Correct the parameter errors in Advanced settings.
任务响应缺少 id。请刷新运行记录确认任务状态。	The response is missing a job ID. Refresh run history to check submission status.
总分尚未校准	Overall score not calibrated
无已校准总分	No calibrated overall score
当前仅报告分项证据与限制，不生成整体质量分数。	Only individual findings and limitations are reported. No overall quality score is generated.
总分与跨场景权重未校准；执行完成率不表示信号质量。	The overall score and weights across contexts are not calibrated. Execution completion does not measure signal quality.
模块结果摘要	Module result summaries
服务端未提供模块摘要，请查看实际报告。	Module summaries are unavailable. See the report.
本次记录与分析范围	Recording and analysis range
产物清单	Output artifacts
模块	Module
结果	Result
实际扩展结果	Extension results
以下来自本次运行结果。计算完成不代表质量合格，候选仍需人工复核。	These are results from this run. Completed calculations do not establish acceptable quality; candidates require manual review.
未命名扩展	Unnamed extension
运行结果未提供具体原因。	The run did not provide a specific reason.
候选数量：未提供（不按 0 处理）	Candidate count: unavailable (not treated as zero)
当前摘要仅提供总数，未区分时间区间与通道建议；类型和定位以原始证据为准。	This summary provides a total only. Candidate types and locations must be checked in the original evidence.
通道对按对数计，不等于坏通道数。	Channel pairs are counted as pairs, not as bad channels.
分析分段不自动等同任务试次；固定分段或其他分段规则以原始证据为准。	Analysis segments are not necessarily task trials. See the original evidence for segmentation rules.
扩展原始结果与参数	Raw extension results and parameters
服务端暂未提供阶段说明。	The service has not provided a phase description.
等待服务端返回模块状态。	Waiting for module status from the service.
暂无运行记录。完成规划后，开始第一份分析。	No runs yet. Prepare a plan to start the first analysis.
运行记录暂不可用。点击右上角刷新重试。	Run history is unavailable. Use Refresh to try again.
当前状态	Current status
输入	Inputs
输出	Outputs
依赖模块	Dependencies
依据、证据与适用边界	Rationale, evidence and limitations
依据与证据	Rationale and evidence
适用边界与限制	Applicability and limitations
目录未提供证据；不能据此推断已经验证。	The catalog provides no validation evidence; validation must not be assumed.
目录暂未列出限制；这不表示模块没有适用条件。	No limitations are listed. This does not imply unrestricted applicability.
暂无说明	No description available
服务端目录未提供。	Not supplied by the service catalog.
目录未提供	Not supplied by the catalog
模块说明	Module introduction
模块内的方法	Methods in this module
当前目录未提供方法子项。	The catalog does not list methods for this module.
已接入的通用、条件子项随所属模块执行，不能在这里独立开关；尚未接入的子项仅展示。是否可用以计划核对为准，可选扩展需显式选择。	Available general and conditional methods run with their parent module. Planned methods are listed only. Applicability is checked by the plan; optional extensions require explicit selection.
原理、条件与来源	Principles, requirements and sources
解决什么问题	Purpose
方法如何工作	How it works
怎样解释结果	Interpretation
适合使用时	When to use
不适合使用时	When not to use
当前验证证据	Validation evidence
文档与证据来源	Documentation and evidence sources
实现来源与版本说明	Implementation and version notes
来源未命名	Unnamed source
当前目录尚未补充详细方法说明。	Detailed method documentation is not available in the current catalog.
未分类	Uncategorized
目录未提供方法说明。	No method description is available.
适用条件	Requirements
计划未提供适用性原因。	The plan did not provide an applicability reason.
开源 / 方法来源	Software and method sources
许可未提供	License not provided
本次计划参数	Parameters for this plan
方法默认参数（尚待规划）	Method defaults (not yet planned)
此运行的扩展选择	Extension selection for this run
启用这项可选扩展	Enable this optional extension
历史选择只读；要修改，请在左侧配置新分析。	Historical selections are read-only. Configure a new analysis to make changes.
可选开源扩展	Optional open-source extensions
默认关闭。选择扩展会同时选中所属模块；实际适用性以执行计划为准。	Off by default. Selecting an extension also selects its parent module; the execution plan checks applicability.
条件与来源	Requirements and sources
当前目录中的方法尚未接入，不能在此版本运行。	This method is listed but is not implemented in this version.
此计划未保存该方法的适用性，请重新规划核对。	This plan has no applicability record for the method. Prepare a new plan.
请先预览执行计划，由服务端核对当前数据与方法条件。	Preview the execution plan to check data and method requirements.
本平台	This platform
上游仓库许可待确认；仅使用本地安装包	Upstream repository license unconfirmed; using the locally installed package only
本地项目；尚未发布许可	Local project; no published license
算法论文	Algorithm paper
上游代码	Upstream code
官方文档	Official documentation
本项目封装	Platform adapter
原始论文	Original paper
本项目实现	Platform implementation
请通过本地工作台服务打开此页面；直接双击 HTML 无法连接分析 API。	Open this page through the local workbench service. Opening the HTML file directly cannot connect to the analysis API.
模块目录格式不完整，需要 inputs 与 modules 数组。	The catalog response is incomplete: inputs and modules arrays are required.
暂无已登记记录	No registered recordings
重新连接	Reconnect
数据目录尚未加载	Data catalog not loaded
等待本地服务提供模块目录。	Waiting for the module catalog from the local service.
连接本地服务后显示真实模块与计划。	Connect to the local service to view modules and plans.
连接本地服务后读取运行记录。	Connect to the local service to load run history.
推荐响应缺少标识，暂不能开始检查。	The recommendation response has no ID. Starting remains disabled.
推荐响应缺少模块、配置或计划标识，暂不能开始检查。	The recommendation response is missing modules, configuration or plan ID. Starting remains disabled.
最外层必须是按扩展 ID 分组的 JSON 对象。	The top level must be a JSON object grouped by extension ID.
参数已保留；开始检查时会核对范围与适用条件。	Parameters retained. Their ranges and requirements will be checked before starting.
所查看运行的来源与用途	Provenance and use of the displayed run
所选记录的来源与用途	Provenance and use of the selected recording
该历史计划未记录来源与用途说明；不补用当前目录信息。	This historical plan did not save provenance and use details. Current catalog data are not substituted.
来源与用途说明尚未登记。	Provenance and use details have not been registered.
查看来源资料	View source material
来源名称未提供	Source name unavailable
来源	Source
典型用途	Typical use
已有标注	Available annotations
标注边界	Annotation limitations
未提供标注说明	Annotation description unavailable
标注适用边界未说明，不推断为质量真值	Annotation limitations are unspecified; they are not assumed to be quality ground truth
所查看运行的数据标签	Data tags saved for this run
计划已记录	Saved in plan
历史计划	Historical plan
来源 / 草稿	Source / draft
人工补充（草稿，待规划）	Manually entered (draft, not yet planned)
未提供背景信息	Context not provided
该记录或历史计划没有保存数据标签。	This recording or historical plan has no saved data tags.
标签来自当前计划；未知信息会明确保留。悬停标签可查看来源。	Tags come from the current plan; unknown information remains unknown. Hover for provenance.
技术标签只读；背景可在下方补充。未知信息不自动推断。悬停标签可查看来源。	Technical tags are read-only. Context may be added below; missing information is not inferred. Hover for provenance.
未提供 / 未核实	Not provided / unverified
健康对照	Healthy control
癫痫	Epilepsy
睡眠障碍	Sleep disorder
帕金森病	Parkinson’s disease
脑卒中	Stroke
其他神经系统疾病	Other neurological condition
其他背景	Other clinical context
年龄未提供	Age not provided
新生儿	Neonate
儿童 / 青少年	Child / adolescent
成年人	Adult
老年人	Older adult
任务未提供	Task not provided
静息	Rest
睡眠记录	Sleep recording
注意任务	Attention task
运动任务	Motor execution
运动想象	Motor imagery
事件相关任务	Event-related task
其他任务	Other task
头皮 EEG	Scalp EEG
头皮EEG	Scalp EEG
模态未确认	Modality unconfirmed
格式未核验	Format unverified
分析导联	Analysis channels
采样率待核验	Sampling rate unverified
电压单位	Voltage unit
电压单位已登记	Voltage units registered
电压单位待核验	Voltage units unverified
比较组	Comparison groups
比较组未声明	Comparison groups undeclared
导联构型	Lead configuration
参考构型未核实	Reference unverified
共同参考	Common reference
连接耳参考	Linked-ear reference
双极导联	Bipolar leads
混合参考	Mixed references
状态标注	State annotations
有睡眠分期	Sleep stages available
未登记睡眠分期	No registered sleep stages
任务事件	Task events
有任务事件	Task events available
未登记任务事件	No registered task events
临床事件	Clinical events
有临床事件标注	Clinical events available
未登记临床事件	No registered clinical events
电极位置	Electrode locations
已登记位置	Locations registered
位置未核实	Locations unverified
滤波处理史	Filter history
已有处理记录	Processing history registered
滤波史未核实	Filter history unverified
EDF结构与来源指纹	EDF structure and source fingerprint
单位与电压标定	Units and voltage calibration
数据标签与检查计划	Data tags and check plan
缺失、恒值与端点平台	Missing data, flat segments and endpoint plateaus
Welch功率谱	Welch power spectrum
工频及可测谐波	Line frequency and measurable harmonics
背景谱拟合与α功率	Aperiodic spectral fit and alpha power
PREP非空间坏道线索	Non-spatial PREP bad-channel indicators
ECG锁时污染线索	ECG-locked contamination indicators
EOG锁时污染线索	EOG-locked contamination indicators
高频突发与EMG支持	High-frequency bursts and EMG support
睡眠分期时间核对	Sleep-stage timeline checks
任务事件时间核对	Task-event timeline checks
临床事件时间核对	Clinical-event timeline checks
分项汇总与未评说明	Findings and assessment gaps
证据报告	Evidence report
PyPREP空间预测 / RANSAC	PyPREP spatial prediction / RANSAC
local AutoReject试次质量估计	Local AutoReject epoch quality estimation
ICA成分 / ICLabel	ICA components / ICLabel
核对文件结构、时钟、索引与来源指纹。	Check file structure, timing, indices and the source fingerprint.
确认数字值可转换成物理电压。	Verify that digital values can be converted to physical voltage.
根据已知技术条件选择方法；背景标签用于解释。	Select methods using known technical conditions; use context tags for interpretation.
检查非有限样本、恒值区间及标定端点平台。	Check non-finite samples, constant segments and plateaus at calibration endpoints.
描述各通道频率能量分布。	Describe the distribution of power across frequencies for each channel.
在实际可测频带内检查窄带干扰。	Check narrow-band interference within the measurable frequency range.
分离背景谱与谱峰，提供研究描述量。	Separate the aperiodic spectrum from peaks to provide descriptive research measures.
结合幅度、相关、高频与掉线等分项给出候选。	Combine amplitude, correlation, high-frequency and dropout indicators to identify candidates.
利用已确认的心电导联核对EEG中的锁时成分。	Use a confirmed ECG channel to inspect time-locked components in EEG.
利用已确认的眼电导联核对相关事件。	Use a confirmed EOG channel to inspect related events.
提取高频突发，再判断是否有独立EMG支持。	Identify high-frequency bursts and check for independent EMG support.
将睡眠分期映射到原始时间轴并标出未知覆盖。	Map sleep stages to the original timeline and identify uncovered ranges.
核对本次选区事件与原始记录时间。	Check events in the selected range against the original recording timeline.
将来源标注的临床事件映射到原始记录时间。	Map annotated clinical events to the original recording timeline.
汇总实际完成、未评、失败和未选择的方法。	Summarize completed, unassessed, failed and unselected methods.
记录方法、参数、来源、范围与人工复核状态。	Record methods, parameters, provenance, analysis range and manual review status.
计算完成不等于质量合格；候选需复核。	Completed calculations do not establish acceptable quality; candidates require review.
无EMG时仅是高频线索；不等同于已确认肌电伪迹。	Without EMG, these are high-frequency indicators only, not confirmed muscle artifacts.
事件不是质量真值。	Events are not quality ground truth.
发作等病理信号不是伪迹；事件标签不输入检测器或质量分。	Pathological activity such as seizures is not automatically an artifact. Event labels are not used by detectors or quality scores.
无标注区间不自动解释为正常。	Unannotated intervals are not assumed to be normal.
适用条件初步满足，仍以实际执行与子方法结果为准。	Initial requirements are met; actual execution and method results remain authoritative.
扩展目录已登记；尚未接入和完成真实数据验收。	Listed in the catalog, but not implemented or validated on real data.
本次未选择该模块或可选增强方法。	This module or optional method was not selected.
没有确认并配置ECG导联。	No confirmed ECG channel is configured.
没有确认并配置EOG导联。	No confirmed EOG channel is configured.
可计算高频线索，但没有EMG导联支持，不能确认为肌电。	High-frequency indicators can be computed, but cannot be confirmed as muscle activity without EMG support.
采样、时长与EMG配置初步满足；仍需运行核对可用证据。	Sampling, duration and EMG requirements are initially met; execution must verify the available evidence.
全段与每个窗口分别核验频带和时长，短尾窗可能未评。	Frequency and duration requirements are checked for the full range and each window; a short final window may remain unassessed.
采样率不足以覆盖全部50/60Hz及其谐波；仅评估可测频率。	The sampling rate cannot cover all 50/60 Hz components and harmonics; only measurable frequencies are assessed.
技术头未确认全部选中通道单位；执行时必须核验物理标定。	The technical header does not confirm all selected units; physical calibration must be checked during execution.
未登记睡眠分期；不通过疾病或任务标签推测睡眠阶段。	No sleep stages are registered. Stages are not inferred from clinical or task tags.
未登记支持的事件文件；仅填写任务标签不能替代事件。	No supported event file is registered. A task tag cannot replace event annotations.
未登记临床事件文件；疾病背景标签不能替代原始事件标注。	No clinical event file is registered. Clinical context cannot replace original event annotations.
睡眠阶段会改变幅度和频谱；慢波、纺锤及阶段转变不能仅因偏离阈值就判为伪迹。	Sleep stages affect amplitude and spectra. Slow waves, spindles and stage transitions must not be classified as artifacts solely for crossing a threshold.
发作及癫痫样活动可能高幅或呈异常节律；与临床事件并排复核，不把病理活动当质量真值。	Seizures and epileptiform activity may have high amplitude or unusual rhythms. Review them alongside clinical events; pathological activity is not quality ground truth.
任务动作可改变EEG和肌电，但任务事件本身不是伪迹标签；需结合原始波形复核。	Movement can affect EEG and muscle activity, but task events are not artifact labels. Review the original waveforms.
运动想象事件标记想象任务，不证明发生了实际动作或肌电污染；需结合原始波形复核。	Motor-imagery events mark an imagined task; they do not establish actual movement or muscle contamination. Review the original waveforms.
结合原始波形、采集记录及已核实的状态背景复核候选；未登记背景保持未知。	Review candidates using original waveforms, acquisition records and verified context. Unregistered context remains unknown.
接入器核验	Verified by the intake reader
本次明确的通道索引配置	Explicit channel-index configuration for this analysis
EDF技术头与选道	EDF technical header and channel selection
配套标注登记	Registered companion annotations
辅助导联索引配置	Auxiliary-channel index configuration
数据集来源及导联登记	Dataset documentation and lead registration
数据来源说明	Data-source documentation
登记的实验场景	Registered experimental context
本次背景配置（未作为独立医学核实）	Context for this analysis (not independently medically verified)
状态标注不是质量标签。	State annotations are not quality labels.
用于解释和后续分层验证；本版不据此修改质量阈值或打分。	Used for interpretation and later stratified validation, not to change QC thresholds or scores.
来源原文	Original source text`;
  // BEGIN reviewed research methods (src/ephys_qc/research_methods.py)
  const researchPairs = [
  [
    "尚未接入；本次仅核对上游来源和登记方法，没有运行或验证算法。",
    "Not integrated. This review registers upstream sources only; the algorithm has not been run or validated here."
  ],
  [
    "仅登记拟接入的上游调用；没有复制上游算法、安装依赖或改变现有计算。",
    "Proposed upstream call only; no algorithm was copied, dependency installed, or existing computation changed."
  ],
  [
    "尚无平台执行调用；拟调用：",
    "No platform execution call; proposed API: "
  ],
  [
    "FASTER 统计坏道",
    "FASTER statistical bad channels"
  ],
  [
    "用多个统计特征寻找异常通道，补充现有PREP与LOF线索。",
    "Find channel outliers across several statistical features, complementing PREP and LOF."
  ],
  [
    "拟采用MNE-FASTER的坏道步骤：在明确分段后的EEG上计算方差、相关性、Hurst指数、峰度和可测工频特征，按特征保留候选。",
    "Use the MNE-FASTER channel step on explicitly epoched EEG: variance, correlation, Hurst exponent, kurtosis and measurable line-noise features, retaining candidates by metric."
  ],
  [
    "FASTER是成熟方法族；该Python实现不是MNE内置功能，也不等于完整FASTER流水线。统计离群不是伪迹真值。",
    "FASTER is an established method family. This Python implementation is not built into MNE and this entry is not the full FASTER pipeline. Outliers are not artifact ground truth."
  ],
  [
    "足够多且可比较的头皮EEG通道；明确分段与参考；逐项核对可测频带。",
    "Sufficient comparable scalp EEG channels, explicit epochs and reference, and measurable bands for each metric."
  ],
  [
    "按统计特征列出的通道候选",
    "Channel candidates grouped by statistical metric"
  ],
  [
    "不直接用于少通道PSG或颅内记录；不把拼接窗口当任务试次；不自动删道。上游依赖MNE内部接口，接入须做版本兼容测试。",
    "Do not directly apply to sparse PSG or intracranial recordings, treat windows as task trials, or delete channels. Upstream uses internal MNE APIs, requiring compatibility tests."
  ],
  [
    "2026-10-31核对；上游最新列出版本1.2.2，仓库最近推送2025-02-12，未归档。本平台尚未做安装兼容测试。",
    "Reviewed 2026-10-31: latest listed release 1.2.2; repository last pushed 2025-02-12, not archived. Installation compatibility is untested here."
  ],
  [
    "ASR 突发伪迹",
    "ASR artifact bursts"
  ],
  [
    "记录异常突发的候选区间及重建影响，作为可选清洗评估。",
    "Record candidate artifact bursts and reconstruction effects as an optional cleaning evaluation."
  ],
  [
    "ASR由相对干净的校准数据估计协方差与阈值，再识别偏离校准分布的子空间。clean_rawdata还包含独立的坏道与窗口处理步骤。",
    "ASR estimates covariance and thresholds from relatively clean calibration data, then identifies subspaces departing from that distribution. clean_rawdata also includes separate channel and window operations."
  ],
  [
    "这是重建或剔除工具，不能把被修改比例解释为质量分。校准段、阈值、随机性和前后差异必须保存；原始信号不覆盖。",
    "This reconstructs or rejects data; the modified fraction is not a quality score. Save calibration, thresholds, randomness and before/after differences, preserving the original."
  ],
  [
    "连续多通道头皮EEG；可说明来源的校准段；明确秩、参考、滤波及所用实现许可。",
    "Continuous multichannel scalp EEG, traceable calibration data, and explicit rank, reference, filtering and implementation licensing."
  ],
  [
    "突发候选及清洗前后差异（拟输出）",
    "Burst candidates and before/after differences (proposed)"
  ],
  [
    "不直接迁移至发作期颅内或Neuropixels数据。上游ASR文件另含UC商业使用许可说明，不能仅凭仓库GPL标识认定可直接商用。",
    "Do not directly transfer to ictal intracranial or Neuropixels recordings. ASR files contain a separate UC commercial-use notice; the repository GPL label alone does not establish commercial permission."
  ],
  [
    "仓库GPL-3.0；ASR文件另有UC使用条款，接入前逐文件核对。",
    "Repository GPL-3.0; ASR files have additional UC terms requiring file-level review."
  ],
  [
    "2026-10-31核对官方教程及源码；clean_rawdata为EEGLAB默认插件，仓库最近推送2026-09-07。本平台未安装MATLAB适配。",
    "Official tutorial and code reviewed 2026-10-31. clean_rawdata is a default EEGLAB plugin; last repository push 2026-09-07. No MATLAB adapter is installed here."
  ],
  [
    "CleanLine 工频处理评估",
    "CleanLine line-noise evaluation"
  ],
  [
    "评估正弦工频的拟合、残留和处理影响。",
    "Evaluate fitted sinusoidal line noise, residuals and processing effects."
  ],
  [
    "CleanLine用多窗谱估计和F统计量识别正弦成分，再以回归估计并移除。计划保留原始与处理副本的频谱比较。",
    "CleanLine identifies sinusoidal components using multitaper estimates and an F statistic, then estimates and removes them by regression. Preserve spectra of the original and processed copy."
  ],
  [
    "与现有Thomson工频检测有关，但当前平台没有调用CleanLine。移除工频不证明其他频段或神经信号未受影响。",
    "Related to the existing Thomson line-noise detector, but CleanLine is not currently called. Removing line noise does not prove preservation of other bands or neural signals."
  ],
  [
    "工频及谐波处于可测频带；明确窗长、频率扫描和原始处理史；MATLAB与EEGLAB环境。",
    "Measurable line frequencies and harmonics, explicit window and frequency scan settings, processing history, and MATLAB with EEGLAB."
  ],
  [
    "正弦拟合、残留PSD与处理差异（拟输出）",
    "Sinusoidal fits, residual PSD and processing differences (proposed)"
  ],
  [
    "只对副本评估，不默认去工频；谱峰不自动证明电源干扰，尚未声明颅内适用性。依赖包许可需单独核对。",
    "Evaluate a copy only, without default cleaning. Peaks do not establish power-line interference; intracranial applicability is not claimed. Review dependency licenses separately."
  ],
  [
    "cleanline.m为GPL-3.0-or-later；捆绑依赖须分别核对。",
    "cleanline.m: GPL-3.0-or-later; review bundled dependencies separately."
  ],
  [
    "2026-10-31核对；EEGLAB官方插件，仓库最近推送2025-02-07，未归档。源码许可比仓库自动识别结果更具体。",
    "Reviewed 2026-10-31: official EEGLAB plugin; last repository push 2025-02-07, not archived. Source licensing is more specific than automatic repository detection."
  ],
  [
    "Zapline-plus 自适应工频",
    "Zapline-plus adaptive line noise"
  ],
  [
    "评估随时间变化的窄带干扰及分段处理效果。",
    "Evaluate time-varying narrowband interference and chunk-wise processing."
  ],
  [
    "在ZapLine的频谱与空间分解基础上，自动寻找噪声频率、划分空间稳定片段并选择去除成分数量。",
    "Extends ZapLine spectral and spatial decomposition with noise-frequency detection, spatially stable chunks and automatic selection of removed components."
  ],
  [
    "属于清洗扩展而非独立质量标准；需比较目标频带、邻近频带和前后波形，保留原始数据。",
    "A cleaning extension, not an independent quality standard. Compare target and neighboring bands and waveforms, retaining original data."
  ],
  [
    "多通道头皮EEG；足够的稳定片段；明确频谱参数、通道组与MATLAB依赖。",
    "Multichannel scalp EEG, sufficient stable chunks, and explicit spectral settings, channel groups and MATLAB dependencies."
  ],
  [
    "噪声频率、片段、去除成分及前后谱（拟输出）",
    "Noise frequencies, chunks, removed components and before/after spectra (proposed)"
  ],
  [
    "不默认用于少通道、病理高频或Neuropixels；不能把生理窄带活动自动当作噪声。",
    "No default use for sparse channels, pathological high frequencies or Neuropixels; physiological narrowband activity must not automatically be labeled noise."
  ],
  [
    "2026-10-31核对；EEGLAB官方插件目录收录，仓库最近推送2023-04-14，未归档。更新较少，拟冻结版本做回归。",
    "Reviewed 2026-10-31: listed in the official EEGLAB plugins; last repository push 2023-04-14, not archived. Infrequent updates call for a pinned version and regression checks."
  ],
  [
    "FieldTrip 分段伪迹线索",
    "FieldTrip segment artifact evidence"
  ],
  [
    "按明确的通道组和频带检测时间区间异常。",
    "Detect interval outliers in explicitly selected channel groups and bands."
  ],
  [
    "ft_artifact_zvalue在带边界扩展的数据上提取所选特征，标准化并汇总通道证据，输出候选起止样本；检测与剔除是两个步骤。",
    "ft_artifact_zvalue extracts configured features with padding, standardizes and combines channel evidence, and returns candidate sample intervals. Detection and rejection are separate steps."
  ],
  [
    "FieldTrip用于EEG与iEEG分析，但这不证明同一频带或阈值跨模态有效。颅内拟接入只保留待复核线索，发作及HFO不能据幅度判坏。",
    "FieldTrip supports EEG and iEEG analysis, but this does not validate shared bands or thresholds. Intracranial integration would retain review candidates only; amplitude alone must not reject seizures or HFOs."
  ],
  [
    "明确原始样本坐标、通道比较组、参考、频带、边界扩展与阈值；颅内需独立样例验证。",
    "Explicit source sample coordinates, channel groups, reference, bands, padding and thresholds; intracranial use requires independent examples."
  ],
  [
    "候选起止样本与检测配置",
    "Candidate onset/offset samples and detection configuration"
  ],
  [
    "不复制官方MEG示例中的110–140Hz或跳变阈值作为EEG/iEEG默认值；不自动调用ft_rejectartifact。",
    "Do not copy the MEG tutorial 110–140 Hz band or jump thresholds as EEG/iEEG defaults; do not automatically call ft_rejectartifact."
  ],
  [
    "2026-10-31核对官方教程；仓库最近推送2026-10-22，未归档。已有方法生态不等于本平台完成MATLAB或颅内验证。",
    "Official tutorial reviewed 2026-10-31; last repository push 2026-10-22, not archived. An established ecosystem is not platform validation of MATLAB or intracranial use."
  ],
  [
    "SpikeInterface / IBL 坏道",
    "SpikeInterface / IBL bad channels"
  ],
  [
    "补充Neuropixels原始电压的坏道候选分类。",
    "Add candidate bad-channel classifications for raw Neuropixels voltage."
  ],
  [
    "detect_bad_channels提供std、mad和coherence+psd等路线；IBL路线结合沿探针的相关证据与高频PSD，输出good、noise、dead、out标签。",
    "detect_bad_channels offers std, mad and coherence+psd routes. The IBL route combines along-probe correlation evidence with high-frequency PSD, yielding good, noise, dead and out labels."
  ],
  [
    "这些是通道标签，不是分选单元质量。out是算法提出的脑外候选，不替代解剖证据；dead和out并非所有检测路线都有。",
    "These are channel labels, not sorted-unit quality. The out label is an algorithmic outside-brain candidate, not anatomical proof; dead and out are not available in every method."
  ],
  [
    "优先AP流；核实物理单位、探针几何与通道顺序；按probe/shank分别处理，固定抽样和滤波参数。",
    "Prioritize AP streams with verified physical units, geometry and channel order; process each probe/shank separately and freeze sampling and filtering settings."
  ],
  [
    "逐通道候选标签与方法配置",
    "Per-channel candidate labels and method settings"
  ],
  [
    "不把同步字混入；不将AP默认高频阈值套到LF流；未知几何时不运行coherence+psd，不默认删道或插值。",
    "Exclude synchronization words; do not apply AP high-frequency defaults to LF streams. Block coherence+psd without geometry; do not remove or interpolate channels by default."
  ],
  [
    "2026-10-31核对官方文档及实现；仓库最近推送2026-10-30，未归档。本平台尚未建立Recording适配或验证阈值。",
    "Official docs and code reviewed 2026-10-31; last repository push 2026-10-30, not archived. A Recording adapter and threshold validation are still absent here."
  ],
  [
    "调用MNE-FASTER 1.2.2的find_bad_channels。连续数据按固定段组织后参与通道统计；50/60Hz均可测时才启用line_noise。不作距离校正。",
    "Call MNE-FASTER 1.2.2 find_bad_channels on fixed continuous segments. Enable line_noise only when both 50 and 60 Hz are measurable. No reference-distance correction."
  ],
  [
    "按特征列出通道候选；固定段不是任务试次，统计离群不等于伪迹。",
    "Channel candidates by metric. Fixed segments are not task trials; statistical outliers are not artifact ground truth."
  ],
  [
    "独立适配器调用已安装的上游包或冻结源码；仅处理内存副本。兼容层和版本记录在运行证据中。",
    "Independent adapter calls installed upstream packages or pinned source on memory copies only. Execution evidence records compatibility layers and versions."
  ],
  [
    "已接入执行与报告；合成信号及公开样例用于工程回归，不代表临床准确率或质量阈值已验证。",
    "Execution and reporting integrated. Synthetic signals and public samples provide engineering regression, not clinical accuracy or validated quality thresholds."
  ],
  [
    "2026-10-31执行适配；Python包固定版本，MATLAB源码固定commit，通过Octave兼容层执行。无MATLAB对照一致性结论。",
    "Execution adapter dated 2026-10-31. Python versions and MATLAB commits are pinned; Octave uses documented compatibility shims. MATLAB equivalence is not established."
  ],
  [
    "多项统计特征筛查通道离群。",
    "Screen channel outliers across statistical features."
  ],
  [
    "ASR 重建影响评估",
    "ASR reconstruction effects"
  ],
  [
    "对副本做明确的1Hz四阶零相位高通，再调用clean_rawdata原版asr_calibrate/asr_process。必须显式确认窗口内至少30秒校准段，保留校准指纹、秩、矩阵和滤波器；lookahead=0。",
    "Apply an explicit fourth-order 1 Hz zero-phase high-pass to a copy, then call upstream asr_calibrate/asr_process. Explicitly confirm at least 30 s of calibration within the window; retain hashes, rank, matrices and filters. lookahead=0."
  ],
  [
    "保存相同高通副本之间的变化量与PSD，不把重建差异解释为伪迹比例或质量分。仅单窗口；秩不足、未确认校准或无预置谱滤波器时阻断。原始信号不覆盖。",
    "Save differences and PSD between identically high-pass-filtered copies, not artifact fractions or scores. Window only; block insufficient rank, unconfirmed calibration or missing upstream spectral filters. Preserve originals."
  ],
  [
    "满足运行规范中的通道、参考、频带与时长条件；已配置固定源码和Octave兼容运行环境。",
    "Meet the channel, reference, bandwidth and duration gates in the runtime specification; configure pinned sources and the Octave compatibility runtime."
  ],
  [
    "前后PSD、逐道变化量、输入输出指纹；不导出清洗波形。",
    "Before/after PSD, channel-wise changes and hashes; no cleaned-waveform export."
  ],
  [
    "评估明确校准条件下的ASR重建影响。",
    "Evaluate ASR reconstruction with explicit calibration."
  ],
  [
    "调用官方cleanLineNoise新实现，仅处理明确指定的一个工频。多窗谱F检验和回归由上游执行；Octave的DPSS接口使用SciPy对称L2归一化窗。",
    "Call upstream cleanLineNoise, the newer CleanLine implementation, for one specified line frequency. Upstream performs multitaper F tests and regression; the Octave DPSS bridge uses symmetric L2-normalized SciPy tapers."
  ],
  [
    "前后PSD与变化量仅描述处理影响，不证明神经信号保留。末尾不足滑窗部分不处理；不自动补谐波，不覆盖原始信号。",
    "Before/after PSD and differences describe processing effects, not neural-signal preservation. Leave the incomplete sliding-window tail unchanged; do not add harmonics or overwrite originals."
  ],
  [
    "比较工频处理前后的频谱与变化量。",
    "Compare spectra and differences before and after line-noise processing."
  ],
  [
    "Zapline-plus 工频处理评估",
    "Zapline-plus line-noise evaluation"
  ],
  [
    "调用clean_data_with_zapline_plus。明确一个工频，把当前片段作为一个固定chunk；自动选择去除成分并调整sigma，保留配置和analytics。",
    "Call clean_data_with_zapline_plus for one explicit line frequency and one fixed chunk per selected window. Adapt removed components and sigma; retain configuration and analytics."
  ],
  [
    "本版未启用自动分段；至少32秒及8个同参考通道。处理影响不是质量分，生理窄带活动也可能被改变；原始信号不覆盖。",
    "Adaptive chunking is not enabled. Require at least 32 s and eight comparable channels. Effects are not a quality score; physiological narrowband activity may also change. Preserve originals."
  ],
  [
    "固定片段内自适应处理工频，保留前后对照。",
    "Adapt line-noise processing within a fixed chunk and retain comparisons."
  ],
  [
    "FieldTrip 差分区间线索",
    "FieldTrip difference interval evidence"
  ],
  [
    "调用ft_artifact_zvalue，特征固定为相邻差分绝对值、cumulative=no；保留最大单道z值。无带通、无边界扩展；从MATLAB一基闭区间映射到原始时钟半开区间。",
    "Call ft_artifact_zvalue with absolute sample differences and cumulative=no, retaining the maximum channel z value. No band-pass or padding. Map one-based inclusive samples to half-open source-clock intervals."
  ],
  [
    "EEG、ECoG和sEEG共用这一描述性特征，不共享质量结论。病理放电也可能触发；候选不定位单道、不自动剔除。",
    "EEG, ECoG and sEEG share this descriptive feature, not quality conclusions. Pathological activity can trigger it. Intervals do not localize a channel and are not automatically rejected."
  ],
  [
    "至少10秒连续EEG/ECoG/sEEG电压及原始时钟；本版无滤波、无空间比较。",
    "At least 10 s of continuous EEG/ECoG/sEEG voltage and its source clock. This adapter uses neither filtering nor spatial comparisons."
  ],
  [
    "按相邻差分z值标记待复核区间。",
    "Mark review intervals using sample-difference z values."
  ],
  [
    "SpikeInterface AP 通道离群",
    "SpikeInterface AP channel outliers"
  ],
  [
    "调用SpikeInterface 0.104.2 detect_bad_channels的std/mad路径。输入V显式转为µV，按文件声明的shank分组，高通后固定种子抽样；不混入同步通道。",
    "Call SpikeInterface 0.104.2 detect_bad_channels with std/mad. Convert V to µV, group by file-declared shank, high-pass and sample with a fixed seed; exclude sync channels."
  ],
  [
    "只输出good/noise；good表示未超本阈值，不是通道合格，也不是分选单元质量。coherence+psd、dead/out和LF未接入。",
    "Only good/noise labels. Good means below this threshold, not a passing channel or sorted-unit quality. coherence+psd, dead/out and LF are not integrated."
  ],
  [
    "已标定的AP电压；文件声明的shank分组，每组至少8道。std/mad不使用空间坐标。",
    "Calibrated AP voltage with file-declared shank groups and at least eight channels per group. std/mad does not use spatial coordinates."
  ],
  [
    "按shank分别筛查AP通道离群。",
    "Screen AP channel outliers separately by shank."
  ],
  [
    "处理前后对照已写入报告；原始信号保留。",
    "Before/after comparisons are in the report; the original signal is preserved."
  ]
];
  // END reviewed research methods
  const explicitPairs = [...pairs.split("\n").map(line => line.split("\t")), ...researchPairs];
  // The descriptive catalogs adapt known ECoG text with these exact route labels.
  // Derive whole-phrase translations only; never replace arbitrary source text.
  const routePairs = explicitPairs.filter(([label])=>label.includes("ECoG")).flatMap(([label,english])=>[["sEEG","sEEG"],["Neuropixels AP/LF","Neuropixels AP/LF"],["Neuropixels 电压","Neuropixels voltage"]].map(([route,translation])=>[label.replaceAll("ECoG",route),english.replaceAll("ECoG",translation)]));
  const dictionary = Object.freeze(Object.fromEntries([...routePairs,...explicitPairs]));
  const keys = {
    "workbench.title": ["质控台", "QC Workbench"],
    "language.label": ["界面语言", "Interface language"],
    "source.chinese": ["中文来源", "Chinese source"],
    "source.original": ["来源原文", "Original source text"],
    "upload.read": ["读取文件", "Read file"],
    "upload.confirm": ["确认并推荐", "Confirm and recommend"],
    "workflow.preview": ["框架预览", "Workflow preview"]
  };
  const hasChinese = value => /[\u3400-\u9fff]/.test(value);
  const numeric = "[\\d,]+(?:\\.\\d+)?";
  // Rules are anchored to whole UI messages. Captured source names are kept verbatim.
  const rules = [
    [/^已识别 Units：([\d,.]+) 个单元。 Units 不属于连续电压流，不进行波形质控。$/, (_,count) => `Units identified: ${count} units. Units are not continuous-voltage streams and do not undergo waveform QC.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 必须是非负整数。$/, (_,field) => `SpikeGLX ${field} must be a non-negative integer.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 超出支持范围。$/, (_,field) => `SpikeGLX ${field} is outside the supported range.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 必须是正数。$/, (_,field) => `SpikeGLX ${field} must be positive.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 必须是有限正数。$/, (_,field) => `SpikeGLX ${field} must be finite and positive.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 需要 AP、LF、SY 三个计数。$/, (_,field) => `SpikeGLX ${field} requires three counts: AP, LF and SY.`],
    [/^SpikeGLX ([A-Za-z0-9_.]+) 表结构无效。$/, (_,field) => `The SpikeGLX ${field} table structure is invalid.`],
    [/^(.+) 共用描述性数学核，但模态、输入和参数独立核验。$/, (_,text) => `${translate(text,"en")} The descriptive mathematics is shared, with independent validation of modality, input and parameters.`],
    [/^方法范围：(头皮 EEG|ECoG|sEEG|细胞外电生理|Neuropixels AP\/LF)$/, (_,name) => `Method scope: ${dictionary[name] || name}`],
    [/^(\d+) 个 (ECoG|sEEG) 触点$/, (_,n,name) => `${n} ${name} contacts`],
    [new RegExp(`^(${numeric}) 个 (ECoG|sEEG) 触点 · (.+) Hz · 原记录 (${numeric})–(${numeric}) 秒$`), (_,n,name,rate,start,stop) => `${n} ${name} contacts · ${rate} Hz · Original recording ${start}–${stop} s`],
    [new RegExp(`^(${numeric}) 个分析通道 · (.+) Hz · 原记录 (${numeric})–(${numeric}) 秒$`), (_,n,rate,start,stop) => `${n} analysis channels · ${rate} Hz · Original recording ${start}–${stop} s`],
    [/^(头皮 EEG|ECoG|sEEG|细胞外电生理|其他模态)（待确认）$/, (_,name) => `${dictionary[name] || name} (needs confirmation)`],
    [/^查看证据限制 · (\d+) 项$/, (_,n) => `Evidence limitations · ${n}`],
    [/^(\d+) 个分析通道$/, (_,n) => `${n} analysis channels`],
    [/^(\d+) 个 ECoG 触点$/, (_,n) => `${n} ECoG contacts`],
    [/^模块依赖：(.+)$/, (_,ids) => `Module dependencies: ${ids}`],
    [/^依赖 (M0[1-9](?: · M0[1-9])*)$/, (_,ids) => `Requires ${ids}`],
    [/^正在传输 (\d+)%$/, (_,n) => `Transferring ${n}%`],
    [/^(\d+) 个模块 · (\d+) 项方法$/, (_, m, n) => `${m} modules · ${n} methods`],
    [/^(\d+) 个模块$/, (_,n) => `${n} modules`],
    [/^片段预检 · 原记录 (.+)–(.+) 秒 · 不代表整份记录。$/, (_,a,b) => `Window check · Source range ${a}–${b} s · Not a whole-recording assessment.`],
    [/^整份检查 · 记录 (.+) 秒 · 已计算 (.+) 秒 · 失败 (.+) 秒 · 未执行 (.+) 秒 · 数据间隙 (.+) 秒。计算覆盖不代表质量通过。$/, (_,a,b,c,d,e) => `Whole-recording check · Total ${a} s · Computed ${b} s · Failed ${c} s · Unexecuted ${d} s · Data gaps ${e} s. Execution coverage is not a quality pass.`],
    [/^(M0[1-9]) · 详情 ↗$/, (_, id) => `${id} · Details ↗`],
    [/^(.+) ↗$/, (_, title) => `${dictionary[title] || title} ↗`],
    [/^查看 (.+) 的依据$/, (_, name) => `View evidence for ${translate(name,"en")}`],
    [/^EDF 第 (\d+) 道缩放范围无效。$/, (_, n) => `Invalid scaling range for EDF source channel ${n}.`],
    [/^([\d,]+) 条记录$/, (_, n) => `${n} records`],
    [/^核对通道 · 已选择 (\d+) 道分析信号$/, (_, n) => `Review channels · ${n} analysis signals selected`],
    [/^核对通道 · 建议 (\d+) 道分析信号$/, (_, n) => `Review channels · ${n} analysis signals suggested`],
    [/^(ECG|EOG|EMG) 辅助导联$/, (_, role) => `${role} auxiliary channel`],
    [/^(M0[1-9]) \/ (接入|计划|检查|汇总|报告|模块说明)$/, (_, id, stage) => `${id} / ${dictionary[stage]}`],
    [/^(\d+) \/ (\d+) 项方法$/, (_, a, b) => `${a} / ${b} methods`],
    [/^(\d+) 项$/, (_, n) => `${n} items`],
    [/^(\d+) 类数据 · (\d+) 份本地记录$/, (_, a, b) => `${a} datasets · ${b} local recordings`],
    [new RegExp(`^(${numeric}) (?:个|道) EEG$`), (_, n) => `${n} EEG channels`],
    [new RegExp(`^(${numeric}) 道$`), (_, n) => `${n} channels`],
    [new RegExp(`^(${numeric}) 秒$`), (_, n) => `${n} s`],
    [new RegExp(`^耗时 (${numeric}) 秒$`), (_, n) => `Elapsed ${n} s`],
    [new RegExp(`^所选时段超出记录范围（0–(${numeric}) 秒）。$`), (_, n) => `The selected range exceeds the recording (0–${n} s).`],
    [new RegExp(`^原始时间轴 (${numeric})–(${numeric}) 秒 · 共 (${numeric}) 秒$`), (_, a, b, c) => `Original timeline ${a}–${b} s · ${c} s total`],
    [new RegExp(`^(${numeric}) 个 ECoG 触点 · (.+) Hz · 原记录 (${numeric})–(${numeric}) 秒$`), (_, a, b, c, d) => `${a} ECoG contacts · ${b} Hz · Original recording ${c}–${d} s`],
    [new RegExp(`^(${numeric}) 道 EEG · (.+) Hz · 原记录 (${numeric})–(${numeric}) 秒$`), (_, a, b, c, d) => `${a} EEG channels · ${b} Hz · Original recording ${c}–${d} s`],
    [/^查看 (\d+) 个方法的适用性与参数$/, (_, n) => `Requirements and parameters for ${n} methods`],
    [/^方法限制（(\d+) 项）$/, (_, n) => `Method limitations (${n})`],
    [/^必须先补充 · (\d+) 项$/, (_, n) => `Required information · ${n} items`],
    [/^调整通道 · (\d+) 道$/, (_, n) => `Adjust channels · ${n} channels`],
    [/^其余原始信号 · (\d+) 道$/, (_, n) => `Other original signals · ${n} channels`],
    [/^确认原始索引 (\d+) 的角色$/, (_, n) => `Confirm role of original channel index ${n}`],
    [/^建议使用 (\d+) 道 EEG(.*)$/, (_, n, aux) => `Suggested selection: ${n} EEG channels${aux}`],
    [/^当前每种辅助角色只接入一条导联；请为 ([A-Z]+) 选择一条，其余设为不使用。$/, (_, role) => `Only one channel per auxiliary role is supported. Select one ${role} channel and set the others to Unused.`],
    [/^已选模块 (\d+) \/ (\d+) 已结束(?: · (\d+) 个未选择)? · 执行进度不代表质量$/, (_, a, b, c) => `Selected modules ${a} / ${b} finished${c ? ` · ${c} not selected` : ""} · Execution progress is not quality`],
    [/^(\d+) \/ (\d+) 个已选模块已结束$/, (_, a, b) => `${a} / ${b} selected modules finished`],
    [/^(候选总数|时间候选|通道候选|通道对候选|分析分段候选)：([\d,]+)（待复核）$/, (_, type, n) => `${({候选总数:"Total candidates",时间候选:"Time candidates",通道候选:"Channel candidates",通道对候选:"Channel-pair candidates",分析分段候选:"Segment candidates"})[type]}: ${n} (review required)`],
    [/^本地服务返回 HTTP (\d+)。$/, (_, n) => `The local service returned HTTP ${n}.`],
    [/^请求失败（HTTP (\d+)）$/, (_, n) => `Request failed (HTTP ${n})`],
    [/^当前目录没有可用扩展：(.+)$/, (_, id) => `No available extension with this ID: ${id}`],
    [/^(.+) 的参数必须是 JSON 对象。$/, (_, id) => `Parameters for ${id} must be a JSON object.`],
    [/^(参数未应用|结果读取失败|取消请求失败)：(.+)$/, (_, prefix, message) => `${({参数未应用:"Parameters not applied",结果读取失败:"Could not load results",取消请求失败:"Could not cancel run"})[prefix]}: ${translate(message, "en")}`],
    [/^运行记录 · (.+)$/, (_, name) => `Run history · ${name}`],
    [/^运行：(.+)$/, (_, name) => `Run: ${name}`],
    [/^正在查看已有运行：(.+)$/, (_, name) => `Viewing previous run: ${name}`],
    [/^(.+) · 点击开始检查$/, (_, name) => `${name} · Select Start check`],
    [/^(.+) · 按数据配置检查模块$/, (_, name) => `${name} · Configure checks for this data`],
    [/^标签属于运行“(.*)”。下方背景选项仍用于新分析。$/, (_, name) => `Tags belong to run “${name}”. Context options below are for a new analysis.`],
    [/^已自动补齐依赖：([M0-9、, ]+)。自动补齐的模块会随本次计划执行。$/, (_, ids) => `Dependencies added: ${ids.replaceAll("、", ", ")}. These modules will run with this plan.`],
    [/^启用后同时选中 (M0[1-9])；开始时核对适用条件。$/, (_, id) => `Enabling also selects ${id}. Requirements are checked before starting.`],
    [/^(M0[1-9]) · 打开原理、条件与来源 ↗$/, (_, id) => `${id} · Principles, requirements and sources ↗`],
    [/^(M0[1-9]) (.+)，(.+)，查看详情$/, (_, id, name, status) => `${id} ${translate(name,"en")}, ${translate(status,"en")}, view details`],
    [/^查看 (.+)，(.+)$/, (_, name, status) => `View ${name}, ${translate(status,"en")}`],
    [/^(就绪|条件受限|已跳过|未选择) (\d+)$/, (_, status, n) => `${dictionary[status]} ${n}`],
    [/^(已配置|未配置) (EOG|ECG|EMG)$/, (_, status, role) => `${role} ${status === "已配置" ? "configured" : "not configured"}`],
    [/^未知 · (.+)$/, (_, rest) => `Unknown · ${translate(rest,"en")}`],
    [/^来源：(.+)$/, (_, rest) => `Source: ${translate(rest,"en")}`]
  ];
  function normalizeLanguage(value) { return value === "en" || value === "en-US" || value === "en-GB" ? "en" : "zh-CN"; }
  let language = "zh-CN";
  try { language = normalizeLanguage(global.localStorage?.getItem(STORAGE_KEY)); } catch (_) { /* Storage may be disabled. */ }
  try {
    const requested = new global.URLSearchParams(global.location?.search || "").get("lang");
    if (["en","zh-CN","zh"].includes(requested)) {
      language = normalizeLanguage(requested);
      try { global.localStorage?.setItem(STORAGE_KEY,language); } catch (_) { /* Keep the URL preference in memory. */ }
    }
  } catch (_) { /* URLSearchParams is optional in non-browser consumers. */ }
  function translate(value, requestedLanguage = language) {
    const raw = String(value ?? "");
    if (normalizeLanguage(requestedLanguage) !== "en") return raw;
    const text = raw.trim();
    if (!text || !hasChinese(text) || /^[\[{]/.test(text)) return raw;
    let rendered = dictionary[text];
    if (!rendered) {
      for (const [pattern, replacement] of rules) { if (pattern.test(text)) { rendered = text.replace(pattern, replacement); break; } }
    }
    // Structured system phrases are composed of independent labels. Never replace arbitrary substrings.
    if (!rendered && / · |；/.test(text)) {
      const tokens = text.split(/( · |；)/);
      const translated = tokens.map(token => token === "；" ? "; " : token === " · " ? token : translate(token,"en"));
      if (translated.some((token, index) => token !== tokens[index])) rendered = translated.join("");
    }
    if (!rendered) return raw;
    return raw.slice(0, raw.indexOf(text)) + rendered + raw.slice(raw.indexOf(text) + text.length);
  }
  function t(key, variables = {}) {
    const row = keys[key];
    const text = row ? row[language === "en" ? 1 : 0] : translate(key);
    return text.replace(/\{([A-Za-z0-9_]+)\}/g, (token, name) => Object.hasOwn(variables,name) ? String(variables[name]) : token);
  }
  const doc = global.document;
  const textSources = new WeakMap(), attributeSources = new WeakMap();
  const protectedTags = new Set(["PRE","CODE","SCRIPT","STYLE","NOSCRIPT","SVG","MATH"]);
  // The renderer puts known catalog invocation notes in PRE, alongside raw JSON
  // in other PRE elements. Only exact documented calls inside method cards are
  // localizable; keep both forms eligible so switching back restores the source.
  const documentedCallTexts = new Set(Object.entries(dictionary)
    .filter(([text]) => /^(?:brainelecqc\.|ephys_qc\.|autoreject\.get_rejection_threshold\(|计划调用(?:pyprep|autoreject|mne_icalabel)\.)/.test(text))
    .flat());
  const protectedIds = new Set(["selected-file-name","input-description","job-label"]);
  const protectedClasses = new Set(["history-name","channel-chip","source-filename","source-value","user-value"]);
  const originalContexts = ".method-documentation,.method-availability,.method-requirements,.method-io,.method-card,.toolkit-card,.dialog-evidence,.candidate-item,#candidate-evidence,#review-error,#pending-intakes,#waveform-status,#review-save-status,#module-dialog-content,#plan-details,#recommendation-content,#job-message,#job-error,#job-load-error,#intake-error,#catalog-error,#config-error,#plan-error,#recommendation-error,#intake-confirmation .result-summary li,[data-i18n-original]";
  function protectedElement(element) {
    if (!element || element.nodeType !== 1) return false;
    if (protectedIds.has(element.id)) return true;
    if (protectedTags.has(element.tagName) && !(element.tagName === "PRE" && element.closest?.(".method-card") && documentedCallTexts.has(element.textContent.trim()))) return true;
    if (element.hasAttribute("data-i18n-skip") || element.getAttribute("translate") === "no" || element.isContentEditable || element.getAttribute("contenteditable") === "true") return true;
    if ([...protectedClasses].some(name => element.classList?.contains(name))) return true;
    if (element.tagName === "OPTION" && element.closest("#input-select") && element.getAttribute("value")) return true;
    // These are raw source values in the existing renderer, not interface labels.
    if (element.matches?.("#input-usage dd,#intake-confirmation > h3,.intake-channel-table tbody td:first-child")) return true;
    return false;
  }
  function isProtected(element) {
    for (let node = element; node && node.nodeType === 1; node = node.parentElement) if (protectedElement(node)) return true;
    return false;
  }
  function renderOriginal(source, element) {
    const rendered = translate(source);
    if (language === "en" && rendered === source && hasChinese(source) && !/^[\s]*[\[{]/.test(source) && element?.closest?.(originalContexts)) return `Original text (Chinese): ${source}`;
    return rendered;
  }
  function translateText(node) {
    const parent = node.parentElement;
    if (!parent || parent.tagName === "TEXTAREA" || isProtected(parent)) return;
    const current = node.data;
    let record = textSources.get(node);
    if (!record || current !== record.rendered) record = {source:current,rendered:current};
    const explicit = parent.getAttribute("data-i18n");
    const translated = explicit && parent.childNodes.length === 1 ? t(explicit) : renderOriginal(record.source,parent);
    record.rendered = translated; textSources.set(node,record);
    if (node.data !== translated) node.data = translated;
  }
  function translateAttributes(element) {
    if (isProtected(element)) return;
    const records = attributeSources.get(element) || new Map();
    for (const attribute of ["title","aria-label","aria-valuetext","placeholder"]) {
      if (!element.hasAttribute(attribute)) continue;
      const current = element.getAttribute(attribute);
      let record = records.get(attribute);
      if (!record || current !== record.rendered) record = {source:current,rendered:current};
      const explicit = element.getAttribute(`data-i18n-${attribute}`);
      record.rendered = explicit ? t(explicit) : translate(record.source);
      records.set(attribute,record);
      if (record.rendered !== current) element.setAttribute(attribute,record.rendered);
    }
    attributeSources.set(element,records);
    // These are navigation links owned by the workbench. Source URLs, download
    // endpoints and other API paths are never rewritten. Report links are an
    // explicit exception: their language query controls the return navigation.
    if (element.tagName === "A") {
      const href = element.getAttribute("href") || "";
      if (/^\/api\/v1\/jobs\/[a-zA-Z0-9_-]{1,120}\/report(?:\?lang=(?:en|zh-CN))?$/.test(href)) {
        const target = href.split("?")[0] + (language === "en" ? "?lang=en" : "");
        if (target !== href) element.setAttribute("href",target);
        return;
      }
      const path = href.split("#")[0], fragment = href.slice(path.length);
      if (/^(?:\/en)?\/standards(?:(?:\/(?:ecog|seeg|neuropixels))?(?:\/modules\/M0[1-9])?|\/(?:overview|fields|applicability|implementation))$/.test(path) && (!fragment || /^#[\w\u3400-\u9fff%-]+$/.test(fragment))) {
        const unlocalized = path.replace(/^\/en\//,"/");
        const localized = language === "en" ? `/en${unlocalized}` : unlocalized;
        const target = localized + localizedFragment(fragment,language);
        if (target !== href) element.setAttribute("href",target);
      }
    }
  }
  const clauseFragments = [
    ["51-m01-数据接入与结构核验","51-m01-data-intake-and-structure-checks"],
    ["52-m02-数据画像与检查计划","52-m02-data-characterization-and-check-plan"],
    ["53-m03-信号完整性","53-m03-signal-integrity"],
    ["54-m04-频谱与窄带干扰","54-m04-spectrum-and-narrow-band-interference"],
    ["55-m05-通道质量候选","55-m05-channel-quality-candidates"],
    ["56-m06-生理伪迹线索","56-m06-physiological-artifact-indicators"],
    ["57-m07-状态与事件核对","57-m07-state-and-event-checks"],
    ["58-m08-分项评价与汇总","58-m08-evidence-summary-and-aggregation"],
    ["59-m09-报告与复核","59-m09-reporting-and-review"]
  ];
  function localizedFragment(fragment,lang) {
    if (!fragment) return "";
    let decoded;
    try { decoded = decodeURIComponent(fragment.slice(1)); } catch (_) { return fragment; }
    const matched = clauseFragments.find(pair => pair.includes(decoded));
    return matched ? "#" + matched[lang === "en" ? 1 : 0] : fragment;
  }
  let observer = null, scheduled = false;
  function apply(root = doc?.documentElement) {
    if (!root) return;
    function visit(node) {
      if (node.nodeType === 3) { translateText(node); return; }
      if (node.nodeType === 1) { if (isProtected(node)) return; translateAttributes(node); }
      for (const child of Array.from(node.childNodes || [])) visit(child);
    }
    visit(root);
    // Mutation records from our own text/attribute changes must not schedule another pass.
    observer?.takeRecords();
  }
  function updateLanguageControls() {
    if (!doc) return;
    doc.documentElement.setAttribute("lang",language);
    for (const control of doc.querySelectorAll("[data-language]")) control.setAttribute("aria-pressed",String(normalizeLanguage(control.getAttribute("data-language")) === language));
    observer?.takeRecords();
  }
  function setLanguage(value) {
    if (!["zh-CN","zh","en","en-US","en-GB"].includes(value)) return false;
    const next = normalizeLanguage(value), changed = next !== language;
    language = next;
    try { global.localStorage?.setItem(STORAGE_KEY,language); } catch (_) { /* Keep in-memory preference. */ }
    // A consumed ?lang= return link must not override a later explicit switch on reload.
    try {
      const query = new global.URLSearchParams(global.location?.search || "");
      if (query.has("lang") && global.history?.replaceState) {
        query.set("lang",language);
        global.history.replaceState(global.history.state,"",`${global.location.pathname || "/"}?${query}${global.location.hash || ""}`);
      }
    } catch (_) { /* Storage still retains the preference when history is unavailable. */ }
    updateLanguageControls(); apply();
    if (changed && doc && typeof global.CustomEvent === "function") doc.dispatchEvent(new global.CustomEvent(EVENT,{detail:{language,locale:language === "en" ? "en-US" : "zh-CN"}}));
    return true;
  }
  function init() {
    if (!doc) return;
    updateLanguageControls(); apply();
    doc.addEventListener("click",event => {
      const control = event.target?.closest?.("[data-language]");
      if (!control || control.disabled) return;
      const requested = control.getAttribute("data-language");
      if (["zh-CN","zh","en","en-US","en-GB"].includes(requested)) { event.preventDefault(); setLanguage(requested); }
    });
    if (typeof global.MutationObserver === "function") {
      observer = new global.MutationObserver(() => {
        if (scheduled) return;
        scheduled = true;
        (global.queueMicrotask || (callback => Promise.resolve().then(callback)))(() => { scheduled = false; apply(); });
      });
      observer.observe(doc.documentElement,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:["title","aria-label","aria-valuetext","placeholder","href","data-i18n","data-i18n-title","data-i18n-aria-label","data-i18n-placeholder"]});
    }
  }
  const api = Object.freeze({t,translate,setLanguage,getLanguage:() => language,getLocale:() => language === "en" ? "en-US" : "zh-CN",apply,STORAGE_KEY,EVENT,dictionary});
  global.QCI18n = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (doc) { if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded",init,{once:true}); else init(); }
})(typeof window !== "undefined" ? window : globalThis);
