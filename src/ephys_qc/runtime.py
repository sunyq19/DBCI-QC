"""Independent method scheduling over immutable, native-clock source windows."""
import gc
import hashlib
import html
import importlib.metadata
import importlib.util
import json
import math
import os
from pathlib import Path
import time

from .annotations import check_annotations, file_sha256
from .planning import build_plan, catalog
from .tagging import data_facts
from collections import Counter


def _extension_status(observed, applicability):
    """An eligibility caveat never downgrades a failed computation to partial."""
    if observed == 'blocked':
        return 'skipped'
    if observed not in {'completed', 'partial'}:
        return 'failed'
    return 'partial' if applicability == 'partial' or observed == 'partial' else 'completed'


def _extension_channel_mapping(channels):
    """Unique adapter names keep repeated labels as distinct source channels."""
    counts = Counter(channel['raw_name'] for channel in channels)
    names = [channel['raw_name'] if counts[channel['raw_name']] == 1 else
             f"{channel['raw_name']} [source {channel['source_index']}]" for channel in channels]
    if len(set(names)) != len(names):
        names = [channel['channel_id'] for channel in channels]
    if len(set(names)) != len(names):
        raise ValueError('Reader channel IDs are not unique')
    return [{'analysis_index': i, 'adapter_name': name, 'channel_id': channel['channel_id'],
             'raw_name': channel['raw_name'], 'source_index': channel['source_index']}
            for i, (channel, name) in enumerate(zip(channels, names))]


def _safe(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(v) for v in value]
    if hasattr(value, "tolist"):
        return _safe(value.tolist())
    if hasattr(value, "item"):
        return _safe(value.item())
    raise TypeError(f"Unsupported result value: {type(value).__name__}")


def _write_json(path, value):
    path.write_text(json.dumps(_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _read_window(state, config):
    selection = config["selection"]
    wanted = selection["eeg_indices"] + list(selection["reference_indices"].values())
    streams = [s for s in state["description"]["streams"]
               if set(wanted).issubset({c["source_index"] for c in s["channels"]})
               and (not selection.get("stream_id") or s["stream_id"] == selection["stream_id"])]
    if len(streams) != 1:
        raise ValueError("Selected channels must belong to one native sampling stream")
    stream = streams[0]
    fs = stream["sampling_frequency_hz"]
    start, length = selection["start_seconds"], selection["duration_seconds"]
    segments = [s for s in stream["segments"]
                if s["recording_start_seconds"] <= start and
                start + length <= s["recording_start_seconds"] + (s["stop_sample"] - s["start_sample"]) / fs + 1e-9
                and (not selection.get("segment_id") or s["segment_id"] == selection["segment_id"])]
    if len(segments) != 1:
        raise ValueError("Selected interval must stay inside one continuous source segment")
    segment = segments[0]
    first = segment["start_sample"] + round((start - segment["recording_start_seconds"]) * fs)
    stop = first + round(length * fs)
    by_index = {c["source_index"]: c for c in stream["channels"]}
    selected = [by_index[i] for i in selection["eeg_indices"]]
    references = {k: by_index[i] for k, i in selection["reference_indices"].items()}
    ordered = selected + list(references.values())
    if any(c.get("unit") != "V" for c in ordered):
        raise ValueError("Every selected EEG/auxiliary channel must have a verified voltage calibration")
    # This public reader uses original indices and calibration. No full-file import
    # or teacher pipeline is called, and no annotation/status affects the samples.
    values = state["reader"].read_window(stream["stream_id"], segment["segment_id"],
                                        [c["channel_id"] for c in ordered], first, stop, "physical")
    import numpy as np
    state['data_sha256'] = hashlib.sha256(np.ascontiguousarray(values, dtype='<f8').tobytes()).hexdigest()
    state.update(data=values[:len(selected)], channels=selected,
                 references={k: values[len(selected) + i] for i, k in enumerate(references)},
                 reference_channels={k: {"channel_id": c["channel_id"], "raw_name": c["raw_name"],
                                         "source_index": c["source_index"]} for k, c in references.items()},
                 fs=fs, first=first,
                 start=segment["recording_start_seconds"] + (first - segment["start_sample"]) / fs)
    state["recording"] = {"channel_count": len(selected), "sampling_rate_hz": fs,
                          "start_seconds": state["start"], "duration_seconds": (stop - first) / fs,
                          "start_sample": first, "stop_sample": stop, "unit": "V",
                          "channel_names": [c["raw_name"] for c in selected],
                          "source_indices": [c["source_index"] for c in selected]}
    return {"selection": selection, "recording": state["recording"],
            "channels": selected, "reference_channels": state["reference_channels"],
            "comparison_groups": config["method_config"].get("comparison_groups"),
            'data_sha256': state['data_sha256'], 'data_hash_encoding': 'ordered EEG then auxiliary, little-endian float64, channel-major SI values',
            "processing_applied": [], "quality_labels_used_for_detection": False}


def _args(state):
    return (state["data"], state["fs"], [c["channel_id"] for c in state["channels"]],
            [c["raw_name"] for c in state["channels"]])


def _origin(state):
    return {"start_sample": state["first"], "start_seconds": state["start"]}


def _waveform(state, path, config_dir):
    os.environ.setdefault("MPLCONFIGDIR", str(config_dir))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    values = state["data"]
    n_channels = min(6, len(values))
    n_samples = min(values.shape[1], round(state["fs"] * 15))
    step = max(1, n_samples // 3000)
    times = state["start"] + np.arange(0, n_samples, step) / state["fs"]
    fig, axes = plt.subplots(n_channels, 1, figsize=(12, max(3, n_channels * 1.1)), sharex=True, squeeze=False)
    for i, ax in enumerate(axes[:, 0]):
        ax.plot(times, values[i, :n_samples:step] * 1e6, lw=.65, color="#156c83")
        ax.set_ylabel(state["channels"][i]["raw_name"] + "\nuV", fontsize=8)
        ax.grid(alpha=.18)
    axes[-1, 0].set_xlabel("Original recording time (seconds)")
    fig.suptitle("Original calibrated signal — first selected channels; display sampling only", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return {"channel_names": [c["raw_name"] for c in state["channels"][:n_channels]],
            "start_seconds": state["start"], "duration_seconds": n_samples / state["fs"],
            "display_stride_samples": step, "unit": "uV", "analysis_downsampled": False}


def _report(result, label, path):
    escape = lambda value: html.escape(str(value), quote=True)
    number = lambda value: f"{value:g}" if isinstance(value, (int, float)) else "待核对"
    status_names = {"completed": "完成", "partial": "部分可评", "skipped": "跳过", "failed": "失败"}

    def sentence(row):
        values = row["summary"] if isinstance(row["summary"], dict) else {}
        if row["status"] in {"skipped", "failed"}:
            return row["reason"]
        mid = row["id"]
        if mid == "M01":
            return f"已核对来源指纹与文件结构，识别 {values.get('header_signal_count', '—')} 个头记录通道、{values.get('stream_count', '—')} 个采样流。"
        if mid == "M02":
            aux = {"ecg": "心电", "eog": "眼电", "emg": "肌电"}
            roles = "、".join(aux.get(k, k) for k in values.get("auxiliary_roles", [])) or "未提供"
            return f"已按原始时钟读取 {values.get('channel_count', '—')} 个选中通道；辅助导联：{roles}。保持原参考和原生采样率。"
        if mid == "M03":
            return f"记录 {values.get('candidate_count', 0)} 个连续性待复核区间。检查包括平线和恒值平台；一般重复数据块尚未实现。"
        if mid == "M04":
            count = values.get("line_flagged_observations", 0)
            return f"工频检查记录 {count} 个命中窗观测（重叠窗不等于独立伪迹段）；PSD与谱拟合证据已保存。未实现专门漂移判定。"
        if mid == "M05":
            names = values.get("candidate_channels", [])
            named = "、".join(names[:12]) + (f"等 {len(names)} 道" if len(names) > 12 else "")
            finding = f"待复核通道：{named}。" if names else "当前规则未产生通道候选。"
            inactive = sum(not g.get("thresholds_active", False) for g in values.get("groups", []))
            return finding + (f"{inactive} 个比较组未启用组内阈值，保留描述量。" if inactive else "已保留分项依据；候选不等于最终坏道结论。")
        if mid == "M06":
            statuses = {"missing_reference": "缺辅助导联", "constant_reference": "辅助信号恒值", "insufficient_duration": "时长不足", "insufficient_sampling_rate": "采样率不足", "no_complete_epochs": "无完整锁时片段"}
            parts = []
            for kind, title in (("ecg", "心电"), ("eog", "眼电")):
                item = values.get("events", {}).get(kind, {})
                state = item.get("status")
                detail = f"{item.get('event_count', 0)} 个辅助事件" if state in {"computed", "no_events"} else statuses.get(state, "未评估")
                parts.append(f"{title}：{detail}")
            return "；".join(parts) + f"。高频候选 {values.get('high_frequency_candidate_count', 0)} 段，其中 {values.get('emg_supported_count', 0)} 段有同步EMG支持。"
        if mid == "M07":
            stages = values.get("stage_seconds", {})
            if values.get('format') == 'clinical_events_tsv':
                return f"当前选区包含 {values.get('selected_count', 0)} 个来源临床事件，区间合计 {number(values.get('clinical_event_seconds'))} 秒。发作等病理活动不是伪迹真值，不据此扣质量分。"
            if stages:
                distribution = "，".join(f"{name} {number(seconds)} 秒" for name, seconds in stages.items())
                return f"当前选区睡眠阶段：{distribution}。阶段时间沿用原记录；睡眠阶段不表示信号质量。"
            return f"当前选区包含 {values.get('selected_count', 0)} 个来源事件（全表 {values.get('total_rows', 0)} 行）。保留原记录时间，实验事件不作为伪迹真值。"
        if mid == "M08":
            return "已汇总分项结果、缺失条件和未评原因。总分未校准，保持空值；不将执行完成率解释为质量分。"
        if mid == "M09":
            return "报告及证据已保存在本地。原始数据保留；人工意见由工作台独立留版本，不覆盖检测结果。"
        return row["reason"]

    blocks = []
    for row in result["modules"]:
        links = " · ".join(f'<a href="{escape(name)}">{escape(name)}</a>' for name in row["artifacts"])
        summary = json.dumps(row["summary"], ensure_ascii=False, indent=2, allow_nan=False)
        reason = f'<p class="note">{escape(row["reason"])}</p>' if row["status"] == "partial" else ""
        extra = ''.join(f'<li><b>{escape(e["name"])}</b> · {escape(status_names.get(e["status"], e["status"]))}：{escape(e["reason"])}</li>'
                        for e in row.get('summary', {}).get('extensions', []))
        extra = f'<h3>本次选择的开源增强</h3><ul>{extra}</ul>' if extra else ''
        blocks.append(f'<section><div class="module-heading"><h2><span class="module-id">{escape(row["id"])}</span> {escape(row["name"])}</h2>'
                      f'<span class="badge {escape(row["status"])}">{escape(status_names.get(row["status"], row["status"]))}</span></div>'
                      f'<p>{escape(sentence(row))}</p>{reason}{extra}<p class="muted">计算耗时 {row["duration_seconds"]:.3f} 秒</p>'
                      f'<details><summary>查看结构化测量摘要</summary><pre>{escape(summary)}</pre></details>'
                      f'<p class="evidence">证据：{links or "无新增文件"}</p></section>')
    image = '<figure><img src="waveform.png" alt="原始选区波形"><figcaption>前6个选中通道的前15秒；图形展示不改变分析输入。</figcaption></figure>' if any(a["name"] == "waveform.png" for a in result["artifacts"]) else ""
    warnings = "".join(f"<li>{escape(w)}</li>" for w in result["warnings"])
    recording = result["recording"]
    first, duration = recording.get("start_seconds"), recording.get("duration_seconds")
    stop = first + duration if isinstance(first, (int, float)) and isinstance(duration, (int, float)) else None
    identity = json.dumps({"source_sha256": result["source_sha256"], "plan_id": result["plan_id"],
                           'data_tags': result.get('data_tags', []),
                           'input_provenance': result.get('input_provenance', {}), 'input_data_usage': result.get('input_data_usage', {}),
                           "recording": recording, "qc_config": result.get("qc_config", {})}, ensure_ascii=False, indent=2, allow_nan=False)
    notices = f'<details class="notices"><summary>查看适用性提示（{len(result["warnings"])}项）</summary><ul>{warnings}</ul></details>' if warnings else ""
    body = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(label)} — EEG QC</title><style>body{{font:16px/1.65 system-ui,sans-serif;color:#183348;background:#f4f7f8;margin:0}}main{{max-width:1100px;margin:auto;padding:32px}}section,header,figure{{background:white;border:1px solid #d8e3e7;border-radius:12px;padding:22px;margin:18px 0}}h1{{font-size:28px;margin:8px 0 22px}}h2{{font-size:20px;margin:0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.6 monospace;background:#f3f6f7;padding:16px;border-radius:8px}}img{{max-width:100%}}a{{color:#126f89}}.status{{background:#fff3d6;padding:12px;border-radius:8px}}.facts{{display:flex;gap:14px;flex-wrap:wrap}}.facts span{{background:#edf5f6;padding:12px 18px;border-radius:8px}}.module-heading{{display:flex;align-items:center;justify-content:space-between;gap:15px}}.module-id,.muted,figcaption{{color:#627780;font-size:13px}}.badge{{font-size:13px;white-space:nowrap;padding:3px 10px;border-radius:20px;background:#ecf2f4}}.completed{{background:#e5f3ee;color:#245d49}}.partial{{background:#fff0cc;color:#78550c}}.failed{{background:#fce5e4;color:#9c3832}}details{{margin:14px 0}}summary{{cursor:pointer;color:#356779}}.note{{border-left:3px solid #d9ae50;padding-left:12px;color:#735a24}}.evidence{{font-size:13px;overflow-wrap:anywhere}}footer{{color:#627780;font-size:13px;padding:12px}}@media(max-width:650px){{main{{padding:12px}}section,header,figure{{padding:16px}}h1{{font-size:23px}}}}</style><main>
<header><p class="muted">独立模块 EEG 质控 · 本地结果</p><h1>{escape(label)}</h1><div class="facts"><span><b>{escape(recording.get('channel_count', '—'))}</b> 个选中通道</span><span><b>{number(recording.get('sampling_rate_hz'))}</b> Hz</span><span>原始时间 <b>{number(first)}–{number(stop)}</b> 秒</span></div><p class="status">总分未校准 · 待人工复核。各模块的“完成”仅表示计算完成，不表示数据质量合格。</p>{notices}<details><summary>查看来源指纹、选道与运行配置</summary><pre>{escape(identity)}</pre></details></header>
{image}{''.join(blocks)}<footer>检测仅提供待复核证据；保留原始数据。任务事件与睡眠阶段不是质量标签。人工意见在工作台独立留版本，本检测报告保持不变。</footer></main></html>'''
    path.write_text(body, encoding="utf-8")


def execute(request, job_dir, emit):
    supplied = request.get('plan') or {} if isinstance(request, dict) else {}
    config = request.get('qc_config', supplied.get('qc_config')) if isinstance(request, dict) else None
    scope = (config or {}).get('scope', request.get('input', {}).get('default_config', {}).get('scope', 'window')) if isinstance(request, dict) else 'window'
    if scope == 'recording':
        from .whole_record import execute_recording
        return execute_recording(request, job_dir, emit)
    return _execute_window(request, job_dir, emit)


def _execute_window(request, job_dir, emit, *, source_context=None, cancel_requested=None):
    if not isinstance(request, dict) or not callable(emit):
        raise ValueError("run_job requires a request and an emit callback")
    record = request["input"]
    supplied = request.get("plan")
    selected = request.get("selected_modules")
    if selected is None and supplied:
        selected = supplied["selected_modules"]
    config = request.get("qc_config", supplied.get("qc_config") if supplied else None)
    plan = build_plan(record, selected, config)
    if supplied and supplied.get("plan_id") != plan["plan_id"]:
        raise ValueError("Submitted plan differs from input, selected modules or configuration")
    # Preserve the caller-visible auto-added list after verifying the stable identity.
    if supplied:
        plan = {**plan, "auto_added_modules": supplied.get("auto_added_modules", [])}
    root = Path(job_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "result.json").exists():
        raise FileExistsError("A completed result already exists; use a new job directory")
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    source = Path(record["source_path"])
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Job outputs must be separate from the original input file")
    result = {"schema_version": "ephys-result/1.3", "plan_id": plan["plan_id"], 'scope': 'window',
              "recording": {"channel_count": 0, "sampling_rate_hz": None,
                            "start_seconds": plan["qc_config"]["selection"]["start_seconds"],
                            "duration_seconds": plan["qc_config"]["selection"]["duration_seconds"]},
              "score": {"value": None, "label": "未校准", "reason": "总分与跨场景权重未校准；执行完成率不表示信号质量。"},
              "modules": [], "review_status": "pending", "source_sha256": None,
              "artifacts": [], "warnings": list(plan["warnings"]), "report_path": "artifacts/report.html",
              "selected_modules": plan["selected_modules"], "qc_config": plan["qc_config"],
              'data_tags': plan['data_tags'], 'method_applicability': plan['method_applicability'], 'extensions': [],
              'input_provenance': plan['input_provenance'], 'input_data_usage': plan['input_data_usage'],
              'input_metadata': plan['input_metadata'], 'input_modality': plan['input_modality'],
              'input_lineage': plan.get('input_lineage', {})}
    state, statuses = {}, {}
    config = plan["qc_config"]
    methods = config["method_config"]
    _write_json(artifacts / "plan.json", plan)
    versions = {}
    for name in ("brainelecqc", "numpy", "scipy", "mne", "fooof", "matplotlib"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    method_sources = {}
    for name in ("continuity", "spectral", "bad_channels", "events", "muscle"):
        try:
            spec = importlib.util.find_spec("brainelecqc.eeg." + name)
            method_sources[name] = {"file": str(spec.origin), "sha256": file_sha256(spec.origin)} if spec and spec.origin else None
        except (ImportError, ValueError, OSError):
            method_sources[name] = None
    from .version import __version__
    _write_json(artifacts / "environment.json", {"packages": versions, "implementation": "ephys_qc/" + __version__, "adapter": "independent_public_function_calls", "method_sources": method_sources})

    def save(name, payload, row):
        _write_json(artifacts / name, payload)
        row["artifacts"].append(name)

    def record_unrun_extras(mid, row):
        from .extensions import extension_specs
        done = {entry['id'] for entry in result['extensions']}
        for spec in extension_specs():
            id_ = spec['id']
            if spec['module_id'] != mid or id_ not in methods.get('extensions', []) or id_ in done:
                continue
            entry = {'id': id_, 'name': spec['name'], 'module_id': mid, 'status': 'skipped',
                     'reason': '未运行：所属模块或上游未完成。' + row['reason'],
                     'parameters': methods['extension_parameters'][id_],
                     'artifact': mid + '_' + id_ + '.json'}
            save(entry['artifact'], {**entry, 'calculated': False, 'candidates': []}, row)
            result['extensions'].append(entry)
            row['summary'].setdefault('extensions', []).append(entry)

    def run_extras(mid, row):
        from .extensions import extension_specs, evaluate_extension, run_extension
        specs = {s['id']: s for s in extension_specs()}
        facts = data_facts(record, config)
        facts.update(sampling_rate_hz=state['fs'], n_eeg=len(state['channels']),
                     window_seconds=state['recording']['duration_seconds'], verified_voltage=True)
        channel_mapping = _extension_channel_mapping(state['channels'])
        for id_ in methods.get('extensions', []):
            spec = specs[id_]
            if spec['module_id'] != mid:
                continue
            gate = evaluate_extension(id_, facts, methods.get('extension_parameters', {}).get(id_))
            filename = mid + '_' + id_ + '.json'
            entry = {'id': id_, 'name': spec['name'], 'module_id': mid, 'status': 'skipped',
                     'reason': gate['reason'], 'parameters': gate['parameters'], 'artifact': filename}
            try:
                if gate['status'] == 'blocked':
                    detail = {**entry, 'candidates': [], 'calculated': False, 'applicability': gate}
                    if row['status'] == 'completed':
                        row.update(status='partial', reason='已选增强方法有条件不足的未评项；基础检查结果保留。')
                else:
                    emit(mid, 'running', '正在执行可选增强：' + spec['name'])
                    detail = run_extension(id_, state['data'], state['fs'], [c['adapter_name'] for c in channel_mapping],
                                           state['start'], gate['parameters'], facts=facts)
                    observed = detail.get('status', 'failed')
                    # A planning caveat cannot hide an actual calculation failure.
                    entry['status'] = _extension_status(observed, gate['status'])
                    entry['candidate_count'] = len(detail.get('candidates', []))
                    for count_key in ('candidate_interval_count', 'candidate_channel_count', 'candidate_pair_count', 'candidate_epoch_count'):
                        if count_key in detail:
                            entry[count_key] = detail[count_key]
                    entry['reason'] = detail.get('reason', gate['reason'])
                    if gate['status'] == 'partial':
                        entry['reason'] += '；' + gate['reason']
                    detail['applicability'] = gate
                    detail['context_tags'] = config['context_tags']
                    detail['channel_mapping'] = channel_mapping
                    if entry['status'] != 'completed' and row['status'] == 'completed':
                        row.update(status='partial', reason='增强方法存在适用限制或未评项，详见子项。')
            except Exception as error:
                entry.update(status='failed', reason=f'{type(error).__name__}: {error}')
                detail = {**entry, 'calculated': False}
                if row['status'] == 'completed':
                    row.update(status='partial', reason='可选增强执行失败；已完成的基础检查结果保留。')
                result['warnings'].append(spec['name'] + ': ' + entry['reason'])
            save(filename, detail, row)
            result['extensions'].append(entry)
            row['summary'].setdefault('extensions', []).append(entry)

    for node in plan["nodes"]:
        if cancel_requested and cancel_requested():
            from .whole_record import RecordingCancelled
            raise RecordingCancelled('Recording job cancellation requested')
        mid = node["id"]
        row = {"id": mid, "name": node["name"], "status": "skipped", "reason": node["reason"],
               "summary": {}, "duration_seconds": 0.0, "artifacts": []}
        result["modules"].append(row)
        if node["status"] == "skipped":
            record_unrun_extras(mid, row)
            statuses[mid] = "skipped"
            emit(mid, "skipped", row["reason"])
            continue
        blockers = [d for d in node["depends_on"] if statuses.get(d) in {"failed", "skipped"}]
        if blockers and mid not in {"M08", "M09"}:
            row["reason"] = "所需计算未完成：" + ", ".join(blockers)
            record_unrun_extras(mid, row)
            statuses[mid] = "skipped"
            emit(mid, "skipped", row["reason"])
            continue
        emit(mid, "running", "正在执行独立节点")
        started = time.perf_counter()
        row["status"] = "partial" if node["status"] == "partial" else "completed"
        try:
            if mid == "M01":
                if not source.is_file():
                    raise ValueError("This workbench requires an existing registered source file")
                digest = source_context['sha256'] if source_context else file_sha256(source)
                result["source_sha256"] = digest
                if record.get("expected_sha256") and digest != record["expected_sha256"]:
                    raise ValueError("Source SHA-256 disagrees with the registered input")
                from .readers import open_reader
                state["reader"] = source_context['reader'] if source_context else open_reader(source, str(record["id"]))
                state['reader'].assert_unchanged()
                state["description"] = state["reader"].describe()
                manifest = state['description']['source_files']
                if record.get('expected_source_files') is not None:
                    expected = {str(Path(item['path']).resolve()): item['sha256'] for item in record['expected_source_files']}
                    observed = {item['path']: item['sha256'] for item in manifest}
                    if len(expected) != len(record['expected_source_files']) or expected != observed:
                        raise ValueError('Source package files/hashes disagree with the registered input')
                elif record.get('metadata', {}).get('source_files'):
                    expected = {item['name']: item['sha256'] for item in record['metadata']['source_files']}
                    observed = {item['name']: item['sha256'] for item in manifest}
                    if expected != observed:
                        raise ValueError('Source package files/hashes disagree with the inspected metadata')
                result['source_files'] = [{k: v for k, v in item.items() if k != 'path'} for item in manifest]
                if state['description']['format'] in {'EDF', 'BDF'}:
                    if source_context and 'header' in source_context:
                        header = source_context['header']
                    else:
                        from brainelecqc.eeg.header_qc import inspect_input_header
                        header = inspect_input_header(source, expected_sha256=digest)
                        if source_context is not None:
                            source_context['header'] = header
                else:
                    header = {'status': 'pass', 'format': state['description']['format'],
                              'structural_checks': 'format reader decoded metadata and validated companion references',
                              'adc_endpoint_calibration': 'unavailable', 'scientific_validity': 'not_assessed'}
                # Teacher header auto-points are not propagated into platform scoring.
                save("M01_input.json", {"source_sha256": digest, "header": header,
                                        "streams": state["description"]["streams"],
                                        "reader_version": state["description"]["reader_version"],
                                        'reader_id': state['description']['reader_id'],
                                        'backend_version': state['description'].get('backend_version'),
                                        'source_files': result['source_files'], 'clock': state['description']['clock'],
                                        'annotations': state['description']['annotations'],
                                        "warnings": state["description"]["warnings"]}, row)
                row["summary"] = {"source_sha256": digest, "stream_count": len(state["description"]["streams"]),
                                  "header_signal_count": state["description"]["header_channel_count"],
                                  "header_status": header["status"],
                                  "reader_warnings": state["description"]["warnings"]}
                if state["description"]["warnings"] or header["status"] != "pass":
                    row.update(status="partial", reason="可读取，但存在需要复核的格式、时间或结构警告")
            elif mid == "M02":
                payload = _read_window(state, config)
                payload['data_tags'] = result['data_tags']
                payload['method_applicability'] = result['method_applicability']
                result["recording"] = state["recording"]
                result['data_sha256'] = state['data_sha256']
                save("M02_selection.json", payload, row)
                row["summary"] = {**state["recording"], "auxiliary_roles": list(state["references"]),
                                  "raw_signal_mutation": False, "quality_labels_used_for_detection": False}
            elif mid == "M03":
                from brainelecqc.eeg.continuity import compute_continuity_qc
                payload = compute_continuity_qc(*_args(state), **_origin(state), channels=state["channels"], config=methods.get("continuity"))
                state["continuity_candidates"] = payload["candidates"]
                save("M03_continuity.json", payload, row)
                row["summary"] = {"candidate_count": len(payload["candidates"]),
                                  "kinds": sorted({r["kind"] for r in payload["candidates"]}),
                                  "automatic_exclusions": 0, "repeated_block_assessment": "not_implemented"}
                if any(c.get('physical_min') is None or c.get('physical_max') is None or
                       c.get('digital_to_physical_scale') is None for c in state['channels']):
                    row['summary']['adc_endpoint_assessment'] = 'unavailable_for_some_channels'
                    row.update(status='partial', reason='恒值检查已执行；部分格式没有提供 ADC 量程端点，端点平台判定未评。')
            elif mid == "M04":
                from brainelecqc.eeg.spectral import compute_spectral_qc
                payload = compute_spectral_qc(*_args(state), **_origin(state), config=methods.get("spectral"))
                save("M04_spectral.json", payload, row)
                line = payload["line_noise"]
                row["summary"] = {"line_status": line["status"], "line_observation_count": len(line["observations"]),
                                  "line_flagged_observations": sum(r["flagged"] for r in line["observations"]),
                                  "full_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["full"]}),
                                  "window_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["windows"]}),
                                  "drift_assessment": "not_implemented"}
                if line["status"] != "computed" or any(r["status"] != "computed" for scope in ("full", "windows") for r in payload["parameterization"][scope]):
                    row.update(status="partial", reason="部分工频/频谱指标未能评估，详见方法结果")
            elif mid == "M05":
                from brainelecqc.eeg.bad_channels import compute_bad_channels
                payload = compute_bad_channels(*_args(state), **_origin(state), groups=methods.get("comparison_groups"), config=methods.get("bad_channels"))
                save("M05_bad_channels.json", payload, row)
                row["summary"] = {"candidate_count": len(payload["candidates"]),
                                  "candidate_channels": [c["channel_name"] for c in payload["channels"] if c["flags"]],
                                  "groups": [{k: g[k] for k in ("group_id", "usable_channel_count", "thresholds_active", "status")} for g in payload["groups"]],
                                  "quality_labels_used_for_detection": False,
                                  "spatial_prediction": "not_implemented", "bridging": "see_optional_extensions"}
                if any(not g["thresholds_active"] for g in payload["groups"]):
                    row.update(status="partial", reason="部分比较组不适用队列阈值；描述量仍保留")
            elif mid == "M06":
                from brainelecqc.eeg.events import compute_event_qc
                from brainelecqc.eeg.muscle import compute_muscle_qc
                aux = {"references": state["references"], "reference_channels": state["reference_channels"]}
                events = compute_event_qc(*_args(state), **_origin(state), **aux, config=methods.get("events"))
                save("M06_auxiliary_events.json", events, row)
                payload = compute_muscle_qc(*_args(state), **_origin(state), **aux, config=methods.get("muscle"),
                                            excluded_intervals=state["continuity_candidates"])
                save("M06_muscle.json", payload, row)
                row["summary"] = {"events": {k: {"status": b["status"], "event_count": b["detected_event_count"]} for k, b in events["by_kind"].items()},
                                  "muscle_status": payload["status"], "emg_reference_status": payload["reference"]["status"],
                                  "high_frequency_candidate_count": len(payload["candidates"]),
                                  "emg_supported_count": sum(c["kind"] == "emg_supported_burst" for c in payload["candidates"]),
                                  "continuity_guard_applied": True}
                if any(b["status"] not in {"computed", "no_events"} for b in events["by_kind"].values()) or payload["reference"]["status"] != "ok" or payload["status"] != "ok":
                    row.update(status="partial", reason="部分生理伪迹缺少可用辅助证据；一般高频突发不等于已确认肌电")
                del events
            elif mid == "M07":
                payload = check_annotations(record["annotation"], state["start"], state["recording"]["duration_seconds"],
                                            state["fs"], record["metadata"]["duration_seconds"], state["first"])
                save("M07_annotations.json", payload, row)
                row["status"] = payload["status"]
                row["summary"] = {k: payload[k] for k in ("format", "label_scope", "total_rows", "selected_count", "stage_seconds", "covered_seconds", "uncovered_intervals", "issues", "quality_ground_truth")}
                row['summary']['clinical_event_seconds'] = payload.get('clinical_event_seconds')
                row["reason"] = "按原记录时钟核对事件/状态；未用作信号质量标签或检测输入"
            elif mid == "M08":
                if result["source_sha256"]:
                    unchanged = True if source_context else file_sha256(source) == result["source_sha256"]
                    if state.get('reader'):
                        state['reader'].assert_unchanged(hashes=not bool(source_context))
                    if not unchanged:
                        raise ValueError("Original source changed during this run; results cannot be accepted")
                else:
                    unchanged = None
                row["summary"] = {"score": result["score"], "source_unchanged": unchanged,
                                  "module_assessments": [{"id": m["id"], "status": m["status"], "reason": m["reason"], "summary": m["summary"]} for m in result["modules"] if m["id"] != "M08"],
                                  "missing_capabilities": ["空间坏道预测", "local AutoReject", "ICA/ICLabel", "一般重复数据块"],
                                  "execution_status_is_not_quality": True}
                if any(m["status"] in {"partial", "failed"} for m in result["modules"] if m["id"] != "M08"):
                    row.update(status="partial", reason="部分方法未评或执行失败；保留分项结论，不生成总分")
                save("M08_assessment.json", row["summary"], row)
            elif mid == "M09":
                if "data" in state:
                    try:
                        display = _waveform(state, artifacts / "waveform.png", root / ".matplotlib")
                        row["artifacts"].append("waveform.png")
                        save("waveform_selection.json", display, row)
                    except Exception as error:
                        row.update(status="partial", reason="结构化结果已保留，波形图生成失败：" + str(error))
                        result["warnings"].append(row["reason"])
                else:
                    row.update(status="partial", reason="信号未成功加载，报告只保留失败与未评原因")
                row["artifacts"].append("report.html")
                row["summary"] = {"review_status": "pending", "human_review_writeback": "separate_versioned_review_store",
                                  "report": "report.html", "raw_signal_preserved": True}
            if mid in {'M03', 'M05', 'M06'}:
                run_extras(mid, row)
            row["duration_seconds"] = time.perf_counter() - started
        except Exception as error:
            row.update(status="failed", reason=f"{type(error).__name__}: {error}", duration_seconds=time.perf_counter() - started)
            row["summary"] = {"error_type": type(error).__name__, "message": str(error)}
            result["warnings"].append(f"{mid}: {row['reason']}")
            save(mid + "_error.json", row["summary"], row)
            record_unrun_extras(mid, row)
        statuses[mid] = row["status"]
        emit(mid, row["status"], row["reason"])
        # Serialized per-module details are not retained by the aggregator.
        if "payload" in locals():
            del payload
        gc.collect()
    if state.get('reader') and not source_context:
        state['reader'].close()
    result["status"] = "failed" if any(statuses.get(k) == "failed" for k in ("M01", "M02", "M08")) else "partial" if any(v in {"partial", "failed"} for v in statuses.values()) else "completed"
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    result = _safe(result)
    result["artifacts"] = [{"name": p.name, "bytes": p.stat().st_size,
                            "kind": "image" if p.suffix == ".png" else "json" if p.suffix == ".json" else "report"}
                           for p in sorted(artifacts.iterdir()) if p.is_file() and p.name != "report.html"]
    _report(result, record.get("label", record["id"]), artifacts / "report.html")
    result["artifacts"].append({"name": "report.html", "bytes": (artifacts / "report.html").stat().st_size, "kind": "report"})
    _write_json(root / "result.json", result)
    return result
