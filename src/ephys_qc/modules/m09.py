"""M09: Read-only waveform evidence and human-readable report rendering."""
import html
import json
import os

from .context import ModuleContext


def waveform(state, path, config_dir):
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


def render_report(result, label, path):
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


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    artifacts = context.artifacts
    result = context.result
    root = context.root
    row = context.row
    state = context.state
    save = context.save
    if "data" in state:
        try:
            display = waveform(state, artifacts / "waveform.png", root / ".matplotlib")
            row["artifacts"].append("waveform.png")
            save("waveform_selection.json", display)
        except Exception as error:
            row.update(status="partial", reason="结构化结果已保留，波形图生成失败：" + str(error))
            result["warnings"].append(row["reason"])
    else:
        row.update(status="partial", reason="信号未成功加载，报告只保留失败与未评原因")
    row["artifacts"].append("report.html")
    row["summary"] = {"review_status": "pending", "human_review_writeback": "separate_versioned_review_store",
                      "report": "report.html", "raw_signal_preserved": True}

    return row
