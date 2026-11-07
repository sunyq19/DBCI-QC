"""Portable EEG summary exports derived from the same versioned report view."""
from io import BytesIO
from pathlib import Path
import json
import threading

EXPORT_VERSION = 'eeg-pdf/1.4'
_RENDER_LOCK = threading.RLock()


def score_rows(view):
    """Separate readable findings, raw measurements and score composition.

    This is a presentation adapter: it never changes a score or denominator.
    """
    amount = lambda v: '未记录' if v is None else f'{v:,.2f}'.rstrip('0').rstrip('.') if not float(v).is_integer() else f'{v:,.0f}'
    descriptions = [
        f'无效数值 {amount(view["finite"]["nonfinite"])} 个；持续恒值 {amount(view["finite"]["constant"])} 个采样点',
        f'{amount(view["line"]["hits"])} / {amount(view["line"]["total"])} 个通道检查窗被标记',
        f'各通道候选时长合计 {amount(view["score"]["hf_candidate_channel_seconds"])} 秒 / 有效检查时长合计 {amount(view["score"]["hf_valid_channel_seconds"])} 秒',
    ]
    rows=[]
    units={'channels':'个通道','channel_seconds':'秒（各通道累加）','channel_samples':'个采样点（各通道累加）','channel_windows':'个通道检查窗',
           'channel_block_seconds':'通道与分析块的累计秒数','samples':'个有效采样点','epochs':'个片段','seconds':'秒'}
    meanings={'channel_samples':'采样点被标记为无效或持续恒值', 'channel_windows':'通道检查窗检出工频候选',
              'channel_seconds':'累计通道时长被标记', 'channels':'通道被标记为候选',
              'samples':'有效采样点被标记', 'epochs':'检查片段被标记', 'seconds':'已检查时长被标记'}
    weighted=view['score'].get('version','').startswith('project-weighted/')
    total_weight=sum(c.get('weight',0) for c in view['score']['components'] if c.get('weight',0)>0)
    for c in view['score']['components']:
        key=c['id'];core=['integrity','line_noise','hf_burst']
        d=descriptions[core.index(key)] if key in core else f"{amount(c.get('candidate_amount'))} / {amount(c.get('assessed_amount'))} {units.get(c.get('unit'),c.get('unit',''))} 为候选"
        if c['value'] is None:
            finding=c.get('reason') or '有效测量不足，未计分'
            reason=finding
            if c.get('candidate_amount') is None or c.get('assessed_amount') is None:
                d='未形成完整测量；已完成分段的证据保留。'
            missing=[]
            for window in view.get('window_scores',[]):
                part=next((p for p in window.get('components',[]) if p.get('id')==key),None)
                if part is not None and part.get('value') is None:
                    missing.append((window,part))
            if missing:
                spans='、'.join(f'{w["start_seconds"]:g}–{w["start_seconds"]+w["duration_seconds"]:g} 秒' for w,_ in missing[:2])
                detail=missing[0][1].get('reason','有效测量不足')
                if 'Degenerate band statistic' in detail:detail='高频统计未得到有效结果'
                elif '持续时间>10秒' in detail:detail='没有连续超过 10 秒的干净片段'
                finding=spans+'：'+detail
                if len(missing)>2:finding+=f'；另有 {len(missing)-2} 个未评分段'
                d=f'已完成 {len(view["window_scores"])-len(missing)} / {len(view["window_scores"])} 个分析分段；整份分项未汇总。'
        elif c.get('candidate_fraction') is not None or view['score'].get('version')=='eeg-basic-screen/0.1':
            pct=100*c['candidate_fraction'] if c.get('candidate_fraction') is not None else 100-c['value']
            percent='<0.01%' if 0<pct<.01 else f'{pct:.2f}%'
            if pct==0:
                finding='未检出无效或持续恒值采样' if key=='integrity' else '本项未检出候选'
            elif c.get('unit')=='channel_block_seconds':
                finding=f'分段通道候选占比 {percent}（按分析时长汇总）'
            else:
                finding=f'{percent} 的'+meanings.get(c.get('unit'),'有效检查量被标记为候选')
            if pct>0 and key=='line_noise' and view['line'].get('affected_channels') is not None:
                finding+=f'，涉及 {view["line"]["affected_channels"]} 个通道'
            elif pct>0 and key=='hf_burst' and view.get('hf_candidate_count') is not None:
                finding+=f'，共 {view["hf_candidate_count"]} 段候选'
            reason=f'候选占比 {pct:.2f}%；'+d
        else:
            finding=f'通道候选负担 {100*c.get("rms_burden",0):.2f}%（旧版均方根汇总）'
            reason=finding+'；'+d
        weight=c.get('weight',0)
        rows.append(dict(id=key,name=c['name'],value=c['value'],deduction=None if c['value'] is None else 100-c['value'],
                         finding=finding,measurement=d,reason=reason,included=weight>0 if weighted else True,
                         share=weight/total_weight if weighted and total_weight>0 else None))
    return rows


def score_weight_label(row, score):
    """Display the saved configured share, including missing and excluded checks."""
    if score.get('version', '').startswith('project-weighted/'):
        return f"{row['share'] * 100:.1f}%" if row.get('included') and row.get('share') is not None else '不计入'
    if score.get('version') == 'eeg-basic-screen/0.1':
        return f"{100 / len(score['components']):.1f}%"
    return '—'  # A minimum-of-components score has no additive weights.


def score_composition(score):
    """Human-readable proportions; missing components keep their configured share."""
    if score.get('version')=='eeg-basic-screen/0.1':
        return '三个基础分项同等计入，总分为三项的平均分（旧版 v0.1）。'
    if not score.get('version','').startswith('project-weighted/'):
        return '总分取三个基础分项中的最低分。'
    active=[p for p in score['components'] if p.get('weight',0)>0]
    if not active:
        return '本次仅展示分项，未设置总分。'
    if len({p['weight'] for p in active})==1:
        return f'{len(active)} 项同等计入，总分为这些分项的平均分。'
    return f'总分由 {len(active)} 个分项按设定比例汇总。'


def display_checks(view):
    """Display actual per-window measurement coverage without editing saved results."""
    windows=view.get('window_scores',[])
    names={p['name']:p['id'] for p in view['score']['components']}
    result=[]
    for original in view.get('checks',[]):
        row=dict(original);key=names.get(row.get('name'))
        if windows and key:
            complete=[w for w in windows if any(p.get('id')==key and p.get('value') is not None for p in w.get('components',[]))]
            seconds=sum(w['duration_seconds'] for w in complete)
            row['value']=f'{len(complete)}/{len(windows)} 个窗口可计分，{seconds:g} 秒'
        result.append(row)
    return result


def evidence_figure(view, workspace):
    """First two HF candidates, or two line candidates; source indices never inferred.

    Every request re-verifies the frozen input via the bounded waveform reader.
    Missing source data suppress the panel, not the report or its original score.
    """
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    selected = next((n for n in view['artifacts'] if n.endswith('--M02_selection.json')), 'M02_selection.json') if view.get('scope') == 'recording' else 'M02_selection.json'
    selection = json.loads((workspace.root / 'artifacts' / selected).read_text())
    channels = {c['channel_id']: c for c in selection['channels']}
    chosen = [dict(c, label='HF candidate') for c in view['hf_candidates'][:2]]
    if not chosen:
        chosen = [dict(c['example'], channel_id=c['channel_id'], channel_name=c['name'], label='Line candidate')
                  for c in view['line_channels'][:2]]
    if not chosen:
        return None, []
    panels, notes = [], []
    for c in chosen:
        try:
            source = channels[c['channel_id']]['source_index']
            start = max(float(view['recording']['start_seconds']), c['start_seconds']-2)
            end = min(view['recording']['start_seconds']+view['recording']['duration_seconds'], start+8)
            wave = workspace.waveform(start_seconds=start, duration_seconds=end-start, channel_indices=[source], max_points=2000)
            if not wave.get('frozen_source_verified'):
                raise ValueError('Frozen source not verified')
            panels.append((c,wave['channels'][0]))
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            notes.append(f'{c["channel_name"]} 对应波形暂不可用，请检查原始文件与冻结来源是否一致。')
    if not panels:
        return None, notes
    # Matplotlib font and renderer state are shared by HTTP worker threads.
    with _RENDER_LOCK:
        fig = Figure(figsize=(10, 2.1*len(panels)), dpi=160, layout='constrained')
        FigureCanvasAgg(fig)
        for i,(c,w) in enumerate(panels):
            ax=fig.add_subplot(len(panels),1,i+1)
            ax.plot(w['times_seconds'],w['values'],color='#245ad3',linewidth=.65)
            ax.axvspan(c['start_seconds'],c['stop_seconds'],color='#f1ba58',alpha=.28)
            ax.set_title(f'{c["channel_name"]}  |  {c["label"]}: {c["start_seconds"]:g}-{c["stop_seconds"]:g} s',loc='left',fontsize=11)
            ax.set_ylabel(w['unit']); ax.set_xlabel('Original recording time (s)')
            ax.grid(alpha=.15); ax.spines[['top','right']].set_visible(False)
        buffer=BytesIO();fig.savefig(buffer,format='png',facecolor='white')
    return buffer.getvalue(),notes


def pdf_bytes(view, figure=None, figure_notes=(), job_id=''):
    """A compact print report from saved results; no scoring or detector changes."""
    from .pdf_layout import build_pdf
    with _RENDER_LOCK:
        return build_pdf(view, figure, figure_notes, job_id)
