"""Versioned, evidence-derived report views; no detector or raw-result mutation."""
import hashlib
import html
import json
import math
from pathlib import Path

VIEW_VERSION = 'eeg-report-view/3'

def ratio(numerator, denominator):
    return 100 * numerator / denominator if denominator else None


def integrity_summary(payload):
    rows = payload.get('measurements', [])
    required = ('finite_sample_count', 'nonfinite_sample_count', 'constant_sample_count')
    measured = [r for r in rows if all(isinstance(r.get(k), int) and r[k] >= 0 for k in required)]
    if not measured:
        return dict(total=0, finite=None, nonfinite=None, constant=None,
                    finite_percent=None, constant_percent=None, measured_channels=0,
                    finite_outside_constant=None)
    finite, nonfinite, constant = (sum(r[k] for r in measured) for k in required)
    total = finite + nonfinite
    if constant > total:
        raise ValueError('Constant sample count exceeds assessed sample count')
    good = [r.get('finite_outside_constant_sample_count') for r in measured]
    clean = sum(good) if all(isinstance(x, int) and 0 <= x <= r['finite_sample_count']
                            for x, r in zip(good, measured)) else None
    return dict(total=total, finite=finite, nonfinite=nonfinite, constant=constant,
                finite_percent=ratio(finite, total), constant_percent=ratio(constant, total),
                measured_channels=len(measured), finite_outside_constant=clean)


def line_summary(payload):
    """Count channel-windows once across frequency targets; not artifact duration."""
    valid = [o for o in payload.get('observations', []) if o.get('status') == 'computed']
    seen, hits, by_channel, examples = set(), set(), {}, {}
    for row in valid:
        channel = row.get('channel_id')
        if channel is None:
            channel = ('index', row['channel_index'])
        # Use actual interval boundaries, avoiding a window-index collision.
        key = (channel, row['start_sample'], row['stop_sample'])
        seen.add(key)
        entry = by_channel.setdefault(channel, dict(name=row['channel_name'], windows=set(), hits=set()))
        entry['windows'].add(key)
        if row.get('flagged'):
            hits.add(key)
            entry['hits'].add(key)
            old = examples.get(channel)
            if old is None or row.get('amplitude_uv', 0) > old.get('amplitude_uv', 0):
                examples[channel] = row
    channels = [dict(channel_id=key, name=v['name'], total=len(v['windows']), hits=len(v['hits']),
                     percent=ratio(len(v['hits']), len(v['windows'])), example=examples.get(key))
                for key, v in by_channel.items()]
    channels.sort(key=lambda r: (-r['hits'], r['name']))
    return dict(total=len(seen), hits=len(hits), percent=ratio(len(hits), len(seen)),
                observed_frequency_rows=len(valid), flagged_frequency_rows=sum(bool(r.get('flagged')) for r in valid),
                assessed_channels=len(channels), affected_channels=sum(bool(c['hits']) for c in channels), channels=channels)


def trial_score(finite, line, hf_rows, expected_channels):
    """Legacy v0.1 arithmetic retained for archived previews; not the current score."""
    def component(key, name, good, total, measured, unit):
        available = (expected_channels > 0 and measured == expected_channels and
                     all(isinstance(v, (int, float)) and math.isfinite(v) for v in (good, total))
                     and total > 0 and 0 <= good <= total)
        return dict(id=key, name=name, value=ratio(good, total) if available else None,
                    numerator=good, denominator=total, unit=unit, weight=1 / 3,
                    assessed_channels=measured)
    hf_valid = [c for c in hf_rows if c.get('status') == 'ok' and
                all(isinstance(c.get(k), (int, float)) and math.isfinite(c[k])
                    for k in ('valid_seconds', 'candidate_seconds')) and
                0 <= c['candidate_seconds'] <= c['valid_seconds'] and c['valid_seconds'] > 0]
    valid_seconds = sum(c['valid_seconds'] for c in hf_valid)
    candidate_seconds = sum(c['candidate_seconds'] for c in hf_valid)
    components = [
        component('integrity', '信号完整性', finite.get('finite_outside_constant'),
                  finite['total'], finite['measured_channels'], 'channel_samples'),
        component('line_noise', '工频干扰', line['total'] - line['hits'],
                  line['total'], line['assessed_channels'], 'channel_windows'),
        component('hf_burst', '高频突发', valid_seconds - candidate_seconds,
                  valid_seconds, len(hf_valid), 'channel_seconds'),
    ]
    values = [c['value'] for c in components]
    return dict(version='eeg-basic-screen/0.1', name='EEG 基础质控评分', status='project_trial',
                value=sum(values) / 3 if all(v is not None for v in values) else None,
                components=components, hf_valid_channel_seconds=valid_seconds,
                hf_candidate_channel_seconds=candidate_seconds)


def build_report_view(result, artifacts, label='', *, artifact_prefix=''):
    """Derive the same compact view for new and historical EEG window reports.

    Only declared artifacts of evaluated modules may contribute. Missing optional
    evidence remains local to its check. This view never replaces result.score.
    """
    if result.get('scope') == 'recording':
        from .report_aggregate import build_recording_view
        return build_recording_view(result, artifacts, label)
    if result.get('analysis_profile') != 'scalp-eeg/1' or result.get('scope') != 'window':
        return None
    artifacts = Path(artifacts).resolve()
    declared = {a['name'] for a in result.get('artifacts', [])}
    modules = {m['id']: m for m in result.get('modules', [])}
    fingerprints, evidence_errors = {}, []

    def load(mid, name):
        if modules.get(mid, {}).get('status') not in {'completed', 'partial'} or name not in declared:
            return {}
        path = (artifacts / (artifact_prefix + name)).resolve()
        if not path.is_relative_to(artifacts):
            evidence_errors.append(f'{mid}：证据路径不可用')
            return {}
        try:
            raw = path.read_bytes()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('Expected an object')
            fingerprints[artifact_prefix + name] = hashlib.sha256(raw).hexdigest()
            return data
        except (OSError, ValueError):
            evidence_errors.append(f'{mid}：证据文件不可用')
            return {}

    continuity = load('M03', 'M03_continuity.json')
    spectral = load('M04', 'M04_spectral.json')
    bad = load('M05', 'M05_bad_channels.json')
    muscle = load('M06', 'M06_muscle.json')
    finite = integrity_summary(continuity)
    line = line_summary(spectral.get('line_noise', {}))
    hf_rows = muscle.get('channels', []) if muscle.get('status') in {'ok', 'partial_channels'} else []
    hf_valid = [c for c in hf_rows if c.get('status') == 'ok' and c.get('valid_seconds', 0) > 0]
    hf_candidates = muscle.get('candidates', []) if hf_valid else None
    recording = result.get('recording', {})
    from .report_aggregate import channel_evidence, local_summary
    from .scoring import burden_score, score_revision
    per_channel = channel_evidence(continuity, line, hf_rows)
    score = burden_score(per_channel, recording.get('channel_count', 0))
    groups = bad.get('groups', [])
    eligible = {cid for g in groups if g.get('thresholds_active') for cid in g.get('channel_ids', [])}
    bad_count = len(bad.get('candidates', [])) if eligible else None
    adc = sum(c.get('calibration_status') == 'complete' for c in continuity.get('measurements', []))
    meta = result.get('input_metadata', {})
    annotations = meta.get('annotations', {})
    hf_count = len(hf_candidates) if hf_candidates is not None else None
    hf_channels = len({c['channel_id'] for c in hf_candidates}) if hf_candidates is not None else None
    parts = []
    if line['hits']:
        parts.append(f'工频候选涉及 {line["affected_channels"]} 个通道')
    if hf_count:
        parts.append(f'高频突发有 {hf_count} 条候选区间')
    if finite['nonfinite'] or finite['constant']:
        parts.append('检出非有限值或恒值采样')
    if bad_count:
        parts.append(f'组内异常候选 {bad_count} 道')
    failed = [m['id'] for m in modules.values() if m.get('status') == 'failed']
    headline = ('检出待复核线索' if parts else '基础检查未检出候选'
                if score['value'] is not None else '已完成部分检查')
    if failed or evidence_errors:
        headline = '部分检查未完成'
    summary = '；'.join(parts) + '。' if parts else '具体测量值与执行情况见下方。'
    lead_channels = [c for c in line['channels'][:2] if c['hits']]
    priority = '；'.join(f'{c["name"]} 命中 {c["hits"]}/{c["total"]} 窗' for c in lead_channels)
    checks = []

    def check(name, value, state, source, note=''):
        checks.append(dict(name=name, value=value, state=state, artifact=source if source in declared else None, note=note))

    def count(value):
        return '未评' if value is None else f'{value:,}'

    check('非有限值', f'{count(finite["nonfinite"])} 个样本',
          '未评' if finite['nonfinite'] is None else '需复核' if finite['nonfinite'] else '未检出', 'M03_continuity.json')
    check('恒值采样', f'{count(finite["constant"])} 个样本',
          '未评' if finite['constant'] is None else '需复核' if finite['constant'] else '未检出', 'M03_continuity.json')
    check('工频干扰', f'{line["hits"]:,}/{line["total"]:,} 个通道窗' if line['total'] else '无有效测量',
          '需复核' if line['hits'] else '未检出' if line['total'] else '未评', 'M04_spectral.json', '跨目标频带去重；窗占比不等于污染时长。')
    check('功率谱', f'{len(spectral.get("psd", {}).get("channel_ids", []))} 道',
          '已计算' if spectral.get('psd') else '未评', 'M04_spectral.json')
    check('通道一致性', f'{len(bad.get("channels", []))} 道已测，{len(eligible)} 道启用组内判据',
          '需复核' if bad_count else '未检出' if eligible else '待确认参考分组', 'M05_bad_channels.json')
    check('高频突发', f'{count(hf_count)} 条通道区间',
          '需复核' if hf_count else '未检出' if hf_count == 0 else '未评', 'M06_muscle.json', '候选保留为高频线索，不直接确认肌电来源。')
    events = modules.get('M06', {}).get('summary', {}).get('events', {})
    for role, name in [('ecg', '心电锁时'), ('eog', '眼电锁时')]:
        event = events.get(role, {})
        available = event.get('status') in {'computed', 'no_events'}
        check(name, f'{event.get("event_count", 0)} 个辅助事件' if available else '本次未形成结果',
              '已计算' if available else '未评', 'M06_auxiliary_events.json')
    check('文件标注', f'{annotations.get("count", "未知")} 条 · {", ".join(annotations.get("kinds", [])) or "未登记类型"}',
          '已读取' if annotations.get('available') else '未提供', 'M01_input.json')
    extra = []
    if len(eligible) < recording.get('channel_count', 0):
        extra.append('部分参考分组待确认；已保留通道描述量，未启用分组不能据空列表认定无坏道。')
    if adc < finite['measured_channels']:
        extra.append('部分 ADC 端点未提供，端点饱和检查未完成；非有限值与恒值结果保留。')
    if any(events.get(role, {}).get('status') not in {'computed', 'no_events'} for role in ('ecg', 'eog')):
        extra.append('辅助锁时检查未齐备；不影响本版三项基础评分。')
    for mid in failed:
        extra.append(f'{mid} 执行失败：{modules[mid].get("reason", "请查看运行日志")}')
    extra.extend(evidence_errors)
    return dict(channel_evidence=per_channel, local_quality=local_summary(per_channel),score_revision=score_revision(result,score),schema_version=VIEW_VERSION, label=label, headline=headline, summary=summary,
                priority=f'工频优先复核：{priority}。' if priority else '', scope='window',
                recording=recording, format=meta.get('format'), input_duration_seconds=meta.get('duration_seconds'),
                score=score, checks=checks, notes=extra, failures=failed,
                finite=finite, line={k:v for k,v in line.items() if k != 'channels'},
                line_channels=[c for c in line['channels'] if c['hits']][:100],
                hf_candidates=(hf_candidates or [])[:100], hf_candidate_count=hf_count, hf_affected_channels=hf_channels,
                bad_candidate_count=bad_count, evidence_errors=evidence_errors,
                parameters={'continuity': continuity.get('parameters', {}), 'line_noise': spectral.get('line_noise', {}).get('settings', {}),
                            'line_multiplicity': spectral.get('line_noise', {}).get('multiplicity', {}), 'hf_burst': muscle.get('parameters', {})},
                source_fingerprints=fingerprints, plan_id=result.get('plan_id'), source_sha256=result.get('source_sha256'),
                warnings=result.get('warnings', []), modules=result.get('modules', []), extensions=result.get('extensions', []),
                artifacts=[a['name'] for a in result.get('artifacts', [])])


def render_report_view(view, evidence_url=None, pdf_url=None):
    """Standalone report with local artifact links; the server rewrites those links."""
    esc = lambda value: html.escape(str(value), quote=True)
    number = lambda value: '—' if value is None else f'{value:g}'
    points = lambda value: '—' if value is None else f'{value:.2f}'
    score, rec, line = view['score'], view['recording'], view['line']
    start, duration = rec.get('start_seconds'), rec.get('duration_seconds')
    stop = start + duration if isinstance(start, (int, float)) and isinstance(duration, (int, float)) else None
    def link(name, title):
        return f'<a href="{esc(name)}">{esc(title)}</a>' if name in view['artifacts'] else ''
    local = view.get('local_quality', {})
    lowest = local.get('lowest')
    local_note = (f'<p class="scope">局部关注：{esc(lowest["name"])} · {esc(lowest["lowest_component"]["name"])} {points(lowest["lowest_component"]["value"])} / 100。总分与局部问题同时查看。</p>' if lowest and lowest['lowest_component']['value'] < 100 else '')
    channel_rows = ''.join('<tr><th>'+esc(c['name'])+'</th>'+''.join('<td>'+points(p['value'])+'</td>' for p in c['components'])+'</tr>' for c in local.get('channels',[])[:100])
    local_table = f'<details><summary>按通道查看分项</summary><p class="muted">按最低分项排序；通道分项为未命中占比，总体分项使用均方根。最多显示 100 道，完整结果见结构化报告。</p><div class="table-wrap"><table><thead><tr><th>通道</th><th>完整性</th><th>工频</th><th>高频突发</th></tr></thead><tbody>{channel_rows}</tbody></table></div></details>' if channel_rows else ''
    worst_window=view.get('lowest_window')
    if worst_window and worst_window['value']<100:
        local_note += f'<p class="muted">最低分时段：{worst_window["start_seconds"]:g}–{worst_window["start_seconds"]+worst_window["duration_seconds"]:g} 秒 · {points(worst_window["value"])} / 100。</p>'
    cov = view.get('coverage')
    scope_label = f'整份检查 · {number(start)}–{number(stop)} 秒' if cov else f'选区检查 · {number(start)}–{number(stop)} 秒'
    coverage_note = f'<p class="muted">已计算 {cov["completed_seconds"]:g} / {cov["total_seconds"]:g} 秒；来源间隙 {cov["gap_seconds"]:g} 秒；未执行 {cov["unexecuted_seconds"]:g} 秒。计算覆盖不等于质量得分。</p>' if cov else ''
    window_rows = ''.join(f'<tr><th>{number(w["start_seconds"])}–{number(w["start_seconds"]+w["duration_seconds"])} s</th><td>{points(w["value"])}</td><td>{link(w.get("report_artifact"),"原始逐窗报告")}</td></tr>' for w in view.get('window_scores',[])[:200])
    time_table = f'<details><summary>按时段查看分数 · {len(view.get("window_scores",[]))} 个窗口</summary><p class="muted">分段独立检测，逐通道汇总分子分母后评分。下表按 v0.2 计算；链接保留运行时原始报告。展示前 200 窗。</p><table><thead><tr><th>原始时间</th><th>基础初评分</th><th>证据</th></tr></thead><tbody>{window_rows}</tbody></table></details>' if window_rows else ''
    descriptions = [
        f'非有限值 {number(view["finite"]["nonfinite"])} · 恒值 {number(view["finite"]["constant"])} 个样本',
        f'{line["hits"]}/{line["total"]} 通道窗命中 · 涉及 {line["affected_channels"]} 道' if line['total'] else '暂无有效测量',
        f'{number(view["hf_candidate_count"])} 条候选区间 · 涉及 {number(view["hf_affected_channels"])} 道',
    ]
    cards = ''.join(f'<article><span>{esc(c["name"])}</span><strong>{points(c["value"])}<small> / 100</small></strong>'
                    f'<div class="track"><i style="width:{c["value"] or 0:.3f}%"></i></div><p>{esc(d)}</p></article>'
                    for c,d in zip(score['components'], descriptions))
    hf_rows = ''.join(f'<tr><th>{esc(c["channel_name"])}</th><td>{c["start_seconds"]:.2f}–{c["stop_seconds"]:.2f} s</td>'
                      f'<td>{c["peak_z_score"]:.2f}</td><td>{link(c.get("evidence_artifact", "M06_muscle.json"), "检测证据")}</td></tr>' for c in view['hf_candidates'])
    line_rows = ''
    for c in view['line_channels']:
        e = c['example']
        line_rows += f'<tr><th>{esc(c["name"])}</th><td>{c["hits"]}/{c["total"]}（{c["percent"]:.2f}%）</td><td>{e["start_seconds"]:g}–{e["stop_seconds"]:g} s</td><td>{e["peak_frequency_hz"]:g} Hz / {e["amplitude_uv"]:.2f} µV</td></tr>'
    check_rows = ''.join(f'<tr><th>{esc(c["name"])}</th><td>{esc(c["state"])}</td><td>{esc(c["value"])}</td><td>{esc(c["note"])} {link(c["artifact"], "证据")}</td></tr>' for c in view['checks'])
    notes = ''.join(f'<li>{esc(n)}</li>' for n in view['notes'])
    failures = f'<p class="failure">{esc("；".join(view["failures"] + view["evidence_errors"]))} · 部分检查未完成，请查看检查明细。</p>' if view['failures'] or view['evidence_errors'] else ''
    # Every candidate remains accessible in the original evidence if display is capped.
    truncation = '<p class="muted">表格最多展示 100 条；完整候选见检测证据。</p>' if (view['hf_candidate_count'] or 0)>100 or line['affected_channels']>100 else ''
    from .report_export import score_rows
    score_table = ''.join(f'<tr><th>{esc(r["name"])}</th><td>{points(r["value"])}</td><td>{points(r["deduction"])}</td><td>{esc(r["reason"])}</td></tr>' for r in score_rows(view))
    evidence = f'<h3>对应候选波形</h3><img loading="lazy" src="{esc(evidence_url)}" alt="对应原始信号，阴影为候选区间"><p class="muted">展示前 2 条高频候选；无高频候选时展示工频候选。阴影为候选区间，原始信号未清洗。原文件不可用时保留检测结果，波形暂不可用。</p>' if evidence_url and (view['hf_candidates'] or view['line_channels']) else ''
    download = f'<a class="tag" href="{esc(pdf_url)}" download>下载 PDF</a>' if pdf_url else ''
    waveform = ('<details><summary>查看起始波形</summary><p class="muted">前几个选中通道、选区起始最多 15 秒。候选时间以表格为准。</p><img src="waveform.png" alt="原始选区起始波形"></details>') if 'waveform.png' in view['artifacts'] else ''
    raw = esc(json.dumps({k:view[k] for k in ('parameters','source_fingerprints','plan_id','source_sha256','modules','extensions','warnings')}, ensure_ascii=False,indent=2,allow_nan=False))
    revision = view.get('score_revision')
    revision_note = (f'<p class="muted">本页按 v0.2 从原始证据重算；运行时 {esc(revision["previous_version"])} 为 {points(revision["previous_value"])} 分，原文件保留。</p>' if revision else '')
    primary_evidence = ' · '.join(filter(None, [link('eeg-assessment.json','检查词条'),link('eeg-rules.json','规则快照'),link('environment.json','运行环境')]))
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(view['label'])} · 质控报告</title><style>
    :root{{--blue:#245ad3;--ink:#19314c;--muted:#687b92;--line:#dfe7f2}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:#f5f7fc;color:var(--ink);font:15px/1.65 system-ui,"Noto Sans CJK SC",sans-serif}}a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}.shell{{display:grid;grid-template-columns:160px minmax(0,1100px);gap:32px;max-width:1360px;margin:auto;padding:30px 24px}}aside{{position:sticky;top:24px;height:max-content}}aside strong{{font-size:22px}}aside nav{{display:grid;gap:14px;margin-top:28px}}aside nav a{{color:var(--muted)}}main{{min-width:0}}header,section{{background:white;border:1px solid var(--line);border-radius:14px;padding:26px 30px;margin-bottom:22px}}h1{{font-size:25px;line-height:1.4;margin:0 0 10px}}h2{{font-size:21px;margin:0 0 20px}}h3{{font-size:16px}}p{{margin:8px 0}}.muted,small{{color:var(--muted)}}.filename{{font-size:13px;overflow-wrap:anywhere;color:var(--muted)}}.tag{{display:inline-block;border-radius:5px;background:#edf3ff;color:var(--blue);font-size:12px;padding:3px 9px}}.hero{{display:flex;align-items:center;gap:30px;margin:24px 0}}.score{{min-width:185px;border-right:1px solid var(--line);padding-right:28px}}.score span,.score small{{display:block;font-size:12px}}.score strong{{font-size:62px;color:var(--blue);line-height:1.35;font-variant-numeric:tabular-nums;letter-spacing:-2px}}.facts{{display:flex;flex-wrap:wrap;gap:8px 20px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:13px}}.scope{{background:#f0f5ff;color:#365b92;padding:8px 12px;border-radius:6px;font-size:13px;margin-top:14px}}.scores{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px;border-top:1px solid var(--line);padding-top:22px;margin-top:22px}}.scores article>span{{font-size:13px}}.scores strong{{display:block;font-size:30px;font-variant-numeric:tabular-nums;margin-top:5px}}.scores small{{font-size:12px;font-weight:400}}.scores p{{font-size:12px;color:var(--muted)}}.track{{height:4px;background:#e9eef7;border-radius:3px;margin:12px 0}}.track i{{display:block;height:100%;background:var(--blue);border-radius:3px}}.footnote{{font-size:12px;color:var(--muted);margin-top:18px}}details{{border-top:1px solid var(--line);padding-top:16px;margin-top:18px}}summary{{cursor:pointer;color:var(--blue);font-size:14px}}.table-wrap{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:13px;min-width:540px}}th,td{{padding:12px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}thead th{{color:var(--muted);font-weight:500;background:#f8faff}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fc;padding:16px;font:12px/1.6 monospace;max-height:460px;overflow:auto}}img{{max-width:100%}}.failure{{padding:12px;border-radius:6px;background:#fff1f0;color:#a43732}}footer{{font-size:12px;color:var(--muted);padding:0 0 24px}}@media(max-width:900px){{.shell{{display:block;padding:16px 12px}}aside{{position:static;margin-bottom:18px}}aside nav{{display:flex;flex-wrap:wrap;gap:16px;margin-top:12px}}header,section{{padding:22px 18px}}}}@media(max-width:620px){{.hero{{display:block}}.score{{border-right:0;border-bottom:1px solid var(--line);padding:0 0 16px;margin-bottom:18px}}.scores{{grid-template-columns:1fr}}}}@media print{{aside{{display:none}}.shell{{display:block;padding:0}}body{{background:white}}header,section{{break-inside:avoid}}}}
    </style></head><body><div class="shell"><aside><strong>质控报告</strong><nav><a href="#overview">评分概览</a><a href="#score-table">结果总表</a><a href="#review">重点复核</a><a href="#checks">检查明细</a><a href="#scoring">评分依据</a><a href="/standards/eeg-report">质控标准</a></nav></aside><main>
    <header id="overview">{download} <span class="tag">项目试行 v0.2</span><p class="filename">{esc(view['label'])}</p><div class="hero"><div class="score"><span>EEG 基础质控评分</span><strong>{points(score['value'])}</strong><small>/ 100 · 取最低分项</small></div><div><h1>{esc(view['headline'])}</h1><p>{esc(view['summary'])}</p><p class="muted">{esc(view['priority'])}</p></div></div>{failures}
    <div class="facts"><span>头皮 EEG · {esc(view['format'] or '未登记格式')}</span><span>{number(rec.get('channel_count'))} 道 · {number(rec.get('sampling_rate_hz'))} Hz</span><span>原记录 {number(view['input_duration_seconds'])} s</span></div><p class="scope">{scope_label}</p>{coverage_note}{local_note}{revision_note}<div class="scores">{cards}</div><p class="footnote">分数概括三项基础检查的候选负担，局部异常仍需复核。项目试行指标，尚未经过专家校准。</p></header>
    <section id="score-table"><h2>结果总表</h2><div class="table-wrap"><table><thead><tr><th>检查项</th><th>得分 / 100</th><th>扣分</th><th>测量与扣分原因</th></tr></thead><tbody>{score_table}</tbody></table></div>{local_table}{time_table}</section><section id="review"><h2>重点复核</h2>{evidence}<h3>高频突发 · {number(view['hf_candidate_count'])} 条候选区间</h3><div class="table-wrap"><table><thead><tr><th>通道</th><th>原始时间</th><th>峰值 z</th><th>证据</th></tr></thead><tbody>{hf_rows or '<tr><td colspan="4">暂无可展示候选；是否已完成检查见明细。</td></tr>'}</tbody></table></div>
    <details><summary>工频候选 · {line['affected_channels'] if line['total'] else '未评'} 个通道，展开查看</summary><p class="muted">按命中窗数排序；每道列出幅度最大的代表窗口。</p><div class="table-wrap"><table><thead><tr><th>通道</th><th>命中窗</th><th>代表窗口</th><th>频率 / 幅度</th></tr></thead><tbody>{line_rows or '<tr><td colspan="4">暂无可展示候选。</td></tr>'}</tbody></table></div><p>{link('candidate-index.json' if cov else 'M04_spectral.json','完整工频证据')}</p></details>{truncation}{waveform}</section>
    <section id="checks"><h2>检查明细</h2><details><summary>全部检查结果</summary><div class="table-wrap"><table><thead><tr><th>检查项</th><th>结果</th><th>测量值</th><th>说明</th></tr></thead><tbody>{check_rows}</tbody></table></div></details><details><summary>补充信息与执行说明</summary><ul>{notes or '<li>无新增补充条件。</li>'}</ul></details></section>
    <section id="scoring"><h2>评分依据</h2><p class="muted">每通道计算异常占比，分项按均方根汇总，总分取最低分项。</p><details><summary>查看 v0.2 计算方法</summary><ul><li>每通道异常占比 p：非有限或恒值样本 / 样本数；工频命中窗 / 有效窗；高频候选时长 / 有效时长。</li><li>分项 = 100 × [1 − √(各通道 p² 的平均值)]。持续集中于少数通道的问题会得到体现。</li><li>总分 = 三个分项的最低值。其他满分项不抵消问题，也不重复累计多方法扣分。</li><li>缺少任一必需分项或通道证据，不生成总分。整份记录先逐通道汇总原始分子分母，不平均窗口分数。</li></ul><p>本次高频候选 {score['hf_candidate_channel_seconds']:g} 通道秒 / 有效 {score['hf_valid_channel_seconds']:g} 通道秒。工频跨频带去重，重叠窗不换算为污染时长。</p><p>此分数衡量三类候选的负担和集中程度，不是可用数据百分比；没有合格线，不区分已经命中之后的幅度严重性。其他检查另列，不被当作已通过。</p><p><a href="/standards/eeg-scoring">完整评分规则与算例</a></p></details><details><summary>方法参数与原始证据</summary><p>{primary_evidence}</p><pre>{raw}</pre><pre>{esc(json.dumps(score,ensure_ascii=False,indent=2,allow_nan=False))}</pre></details></section><footer>{VIEW_VERSION} · {esc(score['version'])} · 来源检测结果保留 · 自动候选待人工复核</footer></main></div></body></html>'''
