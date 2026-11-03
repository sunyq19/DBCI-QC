"""Build a read-only EEG report design preview from an existing window job.

ARCHIVED v0.1 presentation prototype; not the current scoring or report writer.
It never writes into the job. The separate trial index is a project-defined
descriptive score, not a calibrated or externally standardized quality rating.
"""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil


# Historical v0.1 arithmetic retained for reproducing the original prototype.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.report_view import ratio, integrity_summary, line_summary, trial_score


def build_model(job):
    job = Path(job).resolve()
    result = json.loads((job / 'result.json').read_text())
    if result.get('analysis_profile') != 'scalp-eeg/1' or result.get('scope') != 'window':
        raise ValueError('This design preview currently requires a scalp EEG window result')
    modules = {m['id']: m for m in result['modules']}
    declared = {a['name'] for a in result['artifacts']}
    payloads, fingerprints = {}, {}
    names = {'M03': 'M03_continuity.json', 'M04': 'M04_spectral.json',
             'M05': 'M05_bad_channels.json', 'M06': 'M06_muscle.json'}
    for mid, name in names.items():
        if modules.get(mid, {}).get('status') not in {'completed', 'partial'} or name not in declared:
            raise ValueError(f'{mid} has no evaluated artifact; this example must not manufacture zero findings')
        path = job / 'artifacts' / name
        raw = path.read_bytes()
        payloads[mid] = json.loads(raw)
        fingerprints[name] = hashlib.sha256(raw).hexdigest()
    fingerprints['result.json'] = hashlib.sha256((job / 'result.json').read_bytes()).hexdigest()
    data = payloads
    finite = integrity_summary(data['M03'])
    line = line_summary(data['M04']['line_noise'])
    muscle = data['M06']
    valid_hf = [c for c in muscle.get('channels', []) if c.get('status') == 'ok' and c.get('valid_seconds', 0) > 0]
    hf = muscle.get('candidates', []) if muscle.get('status') in {'ok', 'partial_channels'} and valid_hf else None
    groups = data['M05'].get('groups', [])
    # One reference group can be unavailable while another remains eligible.
    eligible = {cid for g in groups if g.get('thresholds_active') for cid in g.get('channel_ids', [])}
    bad_candidates = data['M05'].get('candidates', []) if eligible else None
    info = result['input_metadata']
    rec = result['recording']
    return dict(version='report-view/2-design', label=json.loads((job / 'job.json').read_text())['label'],
                job_id=job.name, input_metadata=info, recording=rec,
                finite=finite, line=line, hf_candidates=hf, hf_assessed_channels=len(valid_hf),
                hf_reference_status=muscle.get('reference', {}).get('status'),
                hf_parameters=muscle.get('parameters', {}),
                bad_candidate_count=len(bad_candidates) if bad_candidates is not None else None,
                eligible_group_channels=len(eligible), described_channels=len(data['M05'].get('channels', [])),
                channel_measurements=data['M05'].get('channels', []),
                adc_assessed_channels=sum(c.get('calibration_status') == 'complete' for c in data['M03'].get('measurements', [])),
                continuity_parameters=data['M03'].get('parameters', {}),
                psd_channels=len(data['M04'].get('psd', {}).get('channel_ids', [])),
                line_settings=data['M04']['line_noise'].get('settings', {}),
                line_multiplicity=data['M04']['line_noise'].get('multiplicity', {}),
                line_targets=data['M04']['line_noise'].get('targets', []),
                modules={k: {'status': v['status'], 'reason': v.get('reason'), 'summary': v.get('summary')} for k, v in modules.items()},
                source_fingerprints=fingerprints, quality_score=None,
                trial_score=trial_score(finite, line, valid_hf if hf is not None else [], rec['channel_count']))


def render(model, *, waveform_available=False):
    esc = lambda value: html.escape(str(value), quote=True)
    num = lambda value: '未评' if value is None else f'{value:,.0f}'
    percent = lambda value: '未评' if value is None else f'{value:.2f}%'
    points = lambda value: '—' if value is None else f'{value:.2f}'
    f, line, rec, meta = (model[k] for k in ('finite', 'line', 'recording', 'input_metadata'))
    hf = model['hf_candidates']
    jid = model['job_id']
    base = f'http://127.0.0.1:8769/api/v1/jobs/{jid}' if re.fullmatch(r'[a-f0-9]{32}', jid) else ''
    evidence = lambda name, label='原始证据': f'<a href="{esc(base)}/artifacts/{esc(name)}">{esc(label)}</a>' if base else esc(name)
    start, duration = rec['start_seconds'], rec['duration_seconds']
    total_duration = meta.get('duration_seconds')
    total_text = f'{total_duration:g}' if total_duration else '未登记'
    hf_channels = len({c['channel_id'] for c in hf}) if hf is not None else None
    has_candidates = line['hits'] or hf
    headline = '检出待复核线索' if has_candidates else '已评项目未检出候选'
    hf_text = f'{len(hf)} 条高频候选通道区间' if hf is not None else '高频检查未评'
    lead = (f'工频线索涉及 {line["affected_channels"]} 个通道；{hf_text}。'
            if line['total'] else hf_text + '。')
    priority = '；'.join(f'{c["name"]} 命中 {c["hits"]}/{c["total"]} 窗'
                        for c in line['channels'][:2] if c['hits'])
    priority = f'工频优先复核：{priority}。' if priority else '按下方通道与时间查看检测结果。'
    score = model['trial_score']
    evidence_notes = [
        f'非有限值 {num(f["nonfinite"])} · 恒值 {num(f["constant"])} 个样本',
        f'{line["hits"]:,} / {line["total"]:,} 通道窗命中 · 涉及 {line["affected_channels"]} 道',
        f'{num(len(hf) if hf is not None else None)} 条候选区间 · 涉及 {num(hf_channels)} 道',
    ]
    score_cards = ''.join(
        f'<div><span>{esc(c["name"])}</span><strong>{points(c["value"])}<em> / 100</em></strong>'
        f'<div class="track"><i style="width:{c["value"] if c["value"] is not None else 0:.3f}%"></i></div>'
        f'<small>{esc(note)}</small></div>'
        for c, note in zip(score['components'], evidence_notes))
    badge = lambda text, kind='neutral': f'<span class="badge {kind}">{esc(text)}</span>'
    def check(name, state, value, detail, source=None, kind='neutral'):
        return (f'<tr><th>{esc(name)}</th><td>{badge(state,kind)}</td><td class="value">{esc(value)}</td>'
                f'<td>{esc(detail)}'+ (f' {evidence(source)}' if source else '') + '</td></tr>')
    domains = []
    def domain(title, note, rows):
        domains.append(f'<div class="domain"><h3>{title}</h3><p class="muted">{note}</p><div class="table-wrap"><table><thead><tr><th>检查</th><th>结论</th><th>测量结果</th><th>解释与证据</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    domain('01 信号完整性', '非有限值、恒值和 ADC 端点分别判断。',
           check('非有限采样','未检出' if f['nonfinite']==0 else '需复核',f'{num(f["nonfinite"])} / {num(f["total"])} 样本',f'有限采样占比 {percent(f["finite_percent"])}。','M03_continuity.json',kind='measured')+
           check('恒值采样','未检出' if f['constant']==0 else '需复核',percent(f['constant_percent']),f'{num(f["constant"])} / {num(f["total"])} 样本；最短持续 {model["continuity_parameters"].get("min_constant_seconds", "—")} 秒。','M03_continuity.json',kind='measured')+
           check('ADC 端点平台','未评' if not model['adc_assessed_channels'] else '见证据',f'{model["adc_assessed_channels"]} 道可判定','本例未登记量程端点；不影响上面两项已经得到的结果。','M03_continuity.json'))
    domain('02 频谱与工频', '同一通道、同一时间窗在多个频带的命中只计一次。',
           check('工频线索','需复核' if line['hits'] else '未检出',f'{line["affected_channels"]} / {line["assessed_channels"]} 通道',f'{line["hits"]:,} / {line["total"]:,} 个通道窗命中（{percent(line["percent"])}）；不是污染时长。','M04_spectral.json',kind='review' if line['hits'] else 'measured')+
           check('功率谱','已计算',f'{model["psd_channels"]} 通道','保留 Welch PSD 和谱模型。谱峰、alpha 功率用于描述，不直接判坏。','M04_spectral.json',kind='measured'))
    domain('03 通道一致性', '描述量可以计算，组内异常判定还需要有效参考分组。',
           check('幅度与相关性描述','已计算',f'{model["described_channels"]} 通道','逐通道原始幅度、稳健幅度、高频比和低相关窗占比可展开查看。','M05_bad_channels.json',kind='measured')+
           check('组内异常候选','待补充' if not model['eligible_group_channels'] else '见证据',f'{model["eligible_group_channels"]} 道启用组内判据','本例未确认参考分组；不能把空候选列表解释为没有坏道。','M05_bad_channels.json'))
    events = model['modules']['M06'].get('summary', {}).get('events', {})
    event_rows = ''
    for role, title in [('ecg','心电锁时'),('eog','眼电锁时')]:
        item=events.get(role,{})
        available=item.get('status') in {'computed','no_events'}
        event_rows += check(title,'已计算' if available else '未评',num(item.get('event_count'))+' 个辅助事件' if available else '未配置辅助导联',
                            '辅助事件数量不等于受污染 EEG 片段数。' if available else '只影响这一锁时方法，不影响一般高频检测。','M06_auxiliary_events.json')
    domain('04 生理伪迹线索', '高频突发是待复核现象；本例没有同步 EMG 确认。',
           check('高频突发','需复核' if hf else ('未检出' if hf is not None else '未评'),f'{num(len(hf) if hf is not None else None)} 条通道区间',f'涉及 {num(hf_channels)} 道；按原始时间定位，不把跨通道重叠区间计为独立事件。','M06_muscle.json',kind='review' if hf else 'neutral')+event_rows)
    annotations = meta.get('annotations', {})
    domain('05 标注与时间', '读取到标注与执行标注分析是两件事。',
           check('文件标注','已读取',f'{annotations.get("count", "未知")} 条',f'类型：{", ".join(annotations.get("kinds", [])) or "未登记"}。boundary 不解释为任务事件。','M01_input.json',kind='measured')+
           check('标注时间核对','未选择' if model['modules'].get('M07',{}).get('status')=='skipped' else '见证据','本次未形成标注分析结论','有任务或睡眠标注时可单独启用；未选择不作为信号异常。'))
    hf_rows=''.join(f'<tr><th>{esc(c["channel_name"])}</th><td>{c["start_seconds"]:.2f}–{c["stop_seconds"]:.2f} s</td><td>{c["peak_z_score"]:.2f}</td><td>{c["max_power_ratio"]:.2f}</td><td>{evidence("M06_muscle.json")}</td></tr>' for c in hf or [])
    line_rows=''
    for c in line['channels']:
        if not c['hits']: continue
        x=c['example']
        line_rows += f'<tr><th>{esc(c["name"])}</th><td>{c["hits"]} / {c["total"]}</td><td>{percent(c["percent"])}</td><td>{x["start_seconds"]:g}–{x["stop_seconds"]:g} s</td><td>{x["peak_frequency_hz"]:g} Hz / {x["amplitude_uv"]:.2f} µV</td></tr>'
    channel_rows=''.join(f'<tr><th>{esc(c["channel_name"])}</th><td>{c.get("raw_std_uv",0):.2f}</td><td>{c.get("robust_amplitude_uv",0):.2f}</td><td>{percent(100*c["low_correlation_fraction"]) if c.get("low_correlation_fraction") is not None else "未评"}</td></tr>' for c in model['channel_measurements'])
    notes = [
        ('参考分组未确认','通道组内异常判定','幅度等描述量已保留','核对源文件参考方式，确认哪些通道可在同一组比较。'),
        ('ADC 量程未提供','端点平台/饱和判定','非有限值和恒值检查已完成','有设备量程或数字/物理端点信息时补充；不凭波形最大值猜测。'),
        ('ECG/EOG 未配置','对应辅助锁时方法','一般高频突发检测仍可报告','文件确有辅助导联时确认其角色；没有则保留未评。'),
        ('EMG 未配置','肌电来源确认','已列出高频突发位置','结合原始波形与实验记录复核；不直接确认肌电污染。'),
    ]
    missing=''.join('<tr>'+''.join(f'<td>{esc(v)}</td>' for v in row)+'</tr>' for row in notes)
    methods = json.dumps({k:model[k] for k in ['line_settings','line_multiplicity','continuity_parameters','hf_parameters','source_fingerprints']},ensure_ascii=False,indent=2)
    waveform = '<details><summary>查看原报告的起始波形</summary><p class="muted">该图只显示前几个通道的 0–15 秒，未展示上方 37 秒附近的候选，不作为这些候选的波形证据。</p><img src="waveform.png" alt="原报告的起始选区波形"></details>' if waveform_available else ''
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>质控报告显示样稿</title><style>
    :root{{--blue:#245ad3;--ink:#19314c;--muted:#64748b;--line:#e1e8f2}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth;scroll-padding-top:24px}}body{{margin:0;background:#f5f7fc;color:var(--ink);font:15px/1.65 system-ui,"Noto Sans CJK SC",sans-serif}}a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}.shell{{display:grid;grid-template-columns:190px minmax(0,1100px);gap:40px;max-width:1390px;margin:auto;padding:34px 24px}}aside{{position:sticky;top:30px;height:max-content}}aside strong{{font-size:22px}}aside nav{{display:grid;gap:8px;margin-top:32px}}aside a{{padding:8px 0;color:var(--muted)}}main{{min-width:0}}h1{{font-size:34px;line-height:1.25;margin:10px 0 14px}}h2{{font-size:23px;margin:0 0 18px}}h3{{font-size:17px;margin:0 0 4px}}p{{margin:8px 0}}.muted,small{{color:var(--muted)}}.design{{font-size:12px;letter-spacing:.04em;color:var(--blue)}}.scope{{display:flex;flex-wrap:wrap;gap:10px 22px;border-top:1px solid var(--line);padding-top:18px;margin-top:22px}}.scope-note{{margin-top:12px;padding:10px 14px;background:#edf3ff;border-radius:6px;color:#365580;font-size:13px}}header,section{{background:white;border:1px solid var(--line);border-radius:12px;padding:26px 30px;margin-bottom:22px}}.kpis{{display:grid;grid-template-columns:repeat(4,1fr);margin-top:24px;padding-top:22px;border-top:1px solid var(--line);gap:14px}}.kpis strong{{display:block;font-size:30px;line-height:1.4;color:var(--ink)}}.kpis span,.kpis small{{display:block;font-size:12px}}.kpis small{{margin-top:5px}}.badge{{display:inline-block;border-radius:4px;padding:3px 8px;background:#eef2f7;color:#5f7088;font-size:12px;white-space:nowrap}}.badge.review{{color:#94621b;background:#fff4df}}.badge.measured{{color:#245bb3;background:#edf3ff}}.domain{{margin:24px 0 32px}}.domain:last-child{{margin-bottom:0}}.domain>p{{font-size:13px}}table{{width:100%;border-collapse:collapse;line-height:1.6;font-size:13px}}th,td{{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line);vertical-align:top}}thead th{{color:var(--muted);font-weight:500;background:#f8faff}}tbody th{{font-weight:600;min-width:105px}}td.value{{font-variant-numeric:tabular-nums;min-width:140px}}.table-wrap{{overflow-x:auto}}.table-wrap table{{min-width:610px}}details{{margin-top:18px;border-top:1px solid var(--line);padding-top:16px}}summary{{cursor:pointer;color:var(--blue);font-weight:500}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f9fc;padding:16px;font:12px/1.6 monospace;max-height:500px;overflow:auto}}img{{max-width:100%;margin-top:12px}}footer{{color:var(--muted);font-size:12px;padding:10px 0 26px}}.score-note{{font-size:13px;color:var(--muted);margin-top:20px}}.filename{{font-size:13px;color:var(--muted);overflow-wrap:anywhere}}@media(max-width:900px){{.shell{{display:block;padding:18px 12px}}aside{{position:static;margin-bottom:20px}}aside nav{{display:flex;flex-wrap:wrap;gap:14px;margin-top:10px}}header,section{{padding:22px 18px}}.kpis{{grid-template-columns:repeat(2,1fr)}}h1{{font-size:28px}}}}@media print{{aside,.design{{display:none}}.shell{{display:block;padding:0}}body{{background:white}}header,section{{break-inside:avoid}}a{{color:inherit}}}}
    .hero{{display:flex;gap:36px;align-items:center;margin:22px 0}}.score-block{{min-width:185px;border-right:1px solid var(--line);padding-right:34px}}.score-block>span{{display:block;font-size:13px;color:var(--muted)}}.score-block strong{{font-size:62px;line-height:1.3;letter-spacing:-2px;color:var(--blue);font-variant-numeric:tabular-nums}}.score-block small{{display:block}}.hero h1{{font-size:25px}}.kpis{{grid-template-columns:repeat(3,1fr);gap:28px}}.kpis em{{font-style:normal;font-size:12px;font-weight:400;color:var(--muted)}}.track{{height:4px;background:#e9eef7;border-radius:3px;margin:12px 0}}.track i{{display:block;height:100%;background:var(--blue);border-radius:3px}}.compact-note{{font-size:13px;color:var(--muted);margin-top:18px}}section>details:first-of-type{{margin-top:0;border-top:0;padding-top:0}}@media(max-width:620px){{.hero{{display:block}}.score-block{{border-right:0;border-bottom:1px solid var(--line);padding:0 0 16px;margin-bottom:18px}}.kpis{{grid-template-columns:1fr;gap:20px}}}}
    </style></head><body><div class="shell"><aside><strong>质控报告</strong><p class="muted">EEG · 初版</p><nav><a href="#overview">评分概览</a><a href="#review">重点复核</a><a href="#domains">检查明细</a><a href="#methods">评分依据</a></nav></aside><main>
    <header id="overview"><div class="design">显示样稿 · 项目试行评分 v0.1</div><p class="filename">{esc(model['label'])}</p>
    <div class="hero"><div class="score-block"><span>EEG 基础初评分</span><strong>{points(score['value'])}</strong><small>/ 100 · 三项等权平均</small></div><div><h1>{headline}</h1><p>{esc(lead)}</p><p class="muted">{esc(priority)}</p></div></div>
    <div class="scope"><span>头皮 EEG · {esc(meta['format'])}</span><span>{rec['channel_count']} 道 · {rec['sampling_rate_hz']:g} Hz</span><span>分析 {start:g}–{start+duration:g} s</span><span>原记录 {total_text} s</span></div>
    <div class="scope-note">快速预检 · 仅评价本次 {start:g}–{start+duration:g} 秒选区</div>
    <div class="kpis">{score_cards}</div>
    <p class="score-note">分数概括三项基础检查的候选负担；局部异常仍需复核。项目试行指标，尚未经过专家校准。</p></header>
    <section id="review"><h2>重点复核</h2><h3>高频突发 · {num(len(hf) if hf is not None else None)} 条候选区间</h3><p class="muted">按通道与原始时间定位。</p><div class="table-wrap"><table><thead><tr><th>通道</th><th>原始时间</th><th>峰值 z</th><th>最大功率比</th><th>证据</th></tr></thead><tbody>{hf_rows or '<tr><td colspan="5">本次没有可展示的高频候选。</td></tr>'}</tbody></table></div>
    <details><summary>工频候选 · {line['affected_channels']} 个通道，展开查看位置</summary><p class="muted">按命中窗数排序；每道列出幅度最大的代表窗口。</p><div class="table-wrap"><table><thead><tr><th>通道</th><th>命中 / 有效窗</th><th>命中窗占比</th><th>代表窗口</th><th>频率 / 幅度</th></tr></thead><tbody>{line_rows or '<tr><td colspan="5">有效观测未产生工频候选。</td></tr>'}</tbody></table></div></details>
    <details><summary>展开全部 {model['described_channels']} 道的幅度与相关性描述</summary><p class="muted">以下为测量值；本例未启用组内异常阈值，不能按该表直接判坏。</p><div class="table-wrap"><table><thead><tr><th>通道</th><th>原始标准差 µV</th><th>稳健幅度 µV</th><th>低相关窗占比</th></tr></thead><tbody>{channel_rows}</tbody></table></div></details>{waveform}</section>
    <section id="domains"><h2>检查明细</h2><details><summary>全部检查结果 · 完整性、频谱、通道、伪迹、标注</summary>{''.join(domains)}</details><details id="missing"><summary>补充信息 · 参考分组与辅助检查</summary><p class="muted">本例参考分组、ADC 端点及辅助导联未确认，相关检查单独保留。它们不属于本版三项评分范围。</p><div class="table-wrap"><table><thead><tr><th>缺少条件</th><th>影响范围</th><th>已有结果</th><th>下一步</th></tr></thead><tbody>{missing}</tbody></table></div><p class="muted">标注分析本次未选择。文件有 boundary 标记，位置需单独核对。</p></details></section>
    <section id="methods"><h2>评分依据</h2><p class="muted">固定三项、等权平均。分数越高，表示这三项检查的候选负担越低。</p><details><summary>查看 v0.1 计算方法</summary><ul><li>信号完整性 = 有限且非恒值样本数 / 已检查样本数 × 100。</li><li>工频干扰 =（1 − 命中通道窗数 / 有效通道窗数）× 100。</li><li>高频突发 =（1 − 候选通道秒数 / 有效通道秒数）× 100。</li><li>总分 = 三项分数的算术平均。缺少任一评分项时保留分项，不计算总分。</li></ul><p>本例高频候选共 {score['hf_candidate_channel_seconds']:g} 通道秒，有效观测 {score['hf_valid_channel_seconds']:g} 通道秒。工频跨频带去重后为 {line['hits']:,}/{line['total']:,} 个通道窗；重叠窗不换算为污染时长。</p><p>这是项目自定的基础筛查指数，不是行业通用质量分或可用数据百分比。暂不设置及格线；同一方法配置、版本和检查范围下比较。</p></details><details><summary>参数与证据</summary><p>{evidence('eeg-assessment.json','检查词条')} · {evidence('eeg-rules.json','规则快照')} · {evidence('environment.json','运行环境')}</p><pre>{esc(methods)}</pre></details></section>
    <footer>显示设计 report-view/2-design · 原任务及检测产物未修改 · 未替换正式报告 · 不作临床诊断</footer></main></div></body></html>'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    job, out=args.job.resolve(), args.output.resolve()
    if out == job or job in out.parents or out in job.parents:
        raise ValueError('Preview must be outside the frozen job directory')
    model=build_model(job)
    out.mkdir(parents=True,exist_ok=True)
    wave=job/'artifacts/waveform.png'
    if wave.is_file(): shutil.copyfile(wave,out/'waveform.png')
    (out/'measurements.json').write_text(json.dumps(model,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (out/'index.html').write_text(render(model,waveform_available=wave.is_file()),encoding='utf-8')
    print(out/'index.html')


if __name__ == '__main__':
    main()
