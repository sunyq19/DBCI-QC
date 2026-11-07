"""Portable EEG summary exports derived from the same versioned report view."""
from io import BytesIO
from pathlib import Path
from html import escape
import json
import os
import threading

EXPORT_VERSION = 'eeg-pdf/1.3'
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
    """Paginated results, review evidence and composition; never recalculate scores."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import Paragraph, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    with _RENDER_LOCK:
        font='QC-CJK'
        if font not in pdfmetrics.getRegisteredFontNames():
            candidates=[os.environ.get('DBCI_QC_PDF_FONT',''), '/usr/share/fonts/fonts-gb/GB_HT_GB18030.ttf',
                        'C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc']
            for filename in candidates:
                if filename and Path(filename).is_file():
                    try:
                        pdfmetrics.registerFont(TTFont(font,filename)); break
                    except Exception:
                        continue
            else:
                font='STSong-Light'
                if font not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(UnicodeCIDFont(font))
        from reportlab.platypus import SimpleDocTemplate, Spacer, PageBreak, Image
        out=BytesIO()
        doc=SimpleDocTemplate(out,pagesize=(595.28,841.89),leftMargin=44,rightMargin=44,
            topMargin=74,bottomMargin=55,title=f'DBCI-QC - {view["label"]}',author='DBCI-QC')
        ink=colors.HexColor('#243449');blue=colors.HexColor('#2459bc');muted=colors.HexColor('#5b687b')
        base=ParagraphStyle('body',fontName=font,fontSize=10,leading=16,textColor=ink,wordWrap='CJK',spaceAfter=7)
        styles={'body':base,
            'note':ParagraphStyle('note',parent=base,fontSize=8.5,leading=13,textColor=muted),
            'title':ParagraphStyle('title',parent=base,fontSize=18,leading=26,spaceAfter=14),
            'heading':ParagraphStyle('heading',parent=base,fontSize=13,leading=20,spaceBefore=12,spaceAfter=8,keepWithNext=True),
            'score':ParagraphStyle('score',parent=base,fontSize=39,leading=47,textColor=blue),
            'cell':ParagraphStyle('cell',parent=base,fontSize=9,leading=14,spaceAfter=0)}
        def para(value,kind='body'):
            return Paragraph(escape(str(value)),styles[kind])
        def table(rows,widths):
            values=[[para(value,'cell') for value in row] for row in rows]
            result=Table(values,colWidths=widths,repeatRows=1,hAlign='LEFT')
            result.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#f1f4f9')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),8),
                ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),
                ('BOTTOMPADDING',(0,0),(-1,-1),8),
                ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dfe5ed'))]))
            return result
        def frame(c,document):
            c.saveState();c.setFillColor(ink);c.setFont(font,13);c.drawString(44,802,'DBCI-QC  /  质控报告')
            c.setStrokeColor(colors.HexColor('#dfe5ed'));c.line(44,786,551,786)
            c.setFillColor(muted);c.setFont(font,7.5)
            c.drawString(44,30,f'{EXPORT_VERSION}  /  {view["score"]["version"]}')
            c.drawRightString(551,30,str(document.page));c.restoreState()
        point=lambda value:'未评' if value is None else f'{value:.2f}'
        score=view['score'];all_rows=score_rows(view);active=[r for r in all_rows if r['included']]
        supplemental=[r for r in all_rows if not r['included']]
        appendix=bool(len(all_rows)>8 and supplemental)
        weighted=score.get('version','').startswith('project-weighted/')
        gnosis=any(r['id'].startswith('gnosis_') for r in all_rows)
        route='灵犀云扩展方案（保留共同基础检查）' if gnosis else '基础检查方案'
        story=[para('01  检查结果','title'),para(view['label']),para(route,'note')]
        rec=view['recording'];start=rec.get('start_seconds',0);stop=start+rec.get('duration_seconds',0)
        story.append(para(f'{view["format"]} · 头皮 EEG · {rec.get("channel_count")} 通道 · {rec.get("sampling_rate_hz"):g} Hz','note'))
        story.append(para(f'本次检查 {start:g}-{stop:g} 秒；原记录 {view["input_duration_seconds"]:g} 秒。','note'))
        hero=Table([[[para('总分 / 100','note'),para('未汇总' if score['value'] is None else point(score['value']),'score')],para(score_composition(score)+' 本次为项目试行评分，未设合格线。')]],colWidths=[154,353])
        hero.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
        story.extend([Spacer(1,10),hero])
        if score.get('value') is None and score.get('missing_reason'):
            story.append(para('整份总分未汇总：'+score['missing_reason']+'。已完成的分项结果保留。'))
        flagged=[r for r in active if r['value'] is not None and r['value']<100]
        if flagged:
            first=min(flagged,key=lambda r:r['value'])
            story.append(para('主要发现：'+first['name']+'，'+first['finding']+'。'))
        elif any(r['value'] is None for r in active):
            story.append(para('部分项目未评分。'+score.get('missing_reason','请查看测量明细。')))
        else:
            story.append(para(view['headline']+'。'+view['summary']))
        if view.get('coverage'):
            cov=view['coverage']
            story.append(para(f'已计算 {cov["completed_seconds"]:g}/{cov["total_seconds"]:g} 秒；来源间隙 {cov["gap_seconds"]:g} 秒。','note'))
        story.append(para('计分项目' if weighted else '基础分项','heading'))
        if active:
            story.append(table([['检查项目','分项 / 100','检查发现']]+[[r['name'],point(r['value']),r['finding']] for r in active],[125,67,315]))
        else:story.append(para('本次未设置总分，已完成的分项见下方。','note'))
        if supplemental and not appendix:
            story.extend([para('其他检查 · 不计入总分','heading'),table([['检查项目','分项 / 100','检查发现']]+[[r['name'],point(r['value']),r['finding']] for r in supplemental],[125,67,315])])
        elif appendix:
            story.append(para(f'另有 {len(supplemental)} 项共同基础检查，结果见附录；不计入本方案总分。','note'))
        story.append(para('分数越低，表示该方法标记的候选负担越大。候选仍需结合原始信号复核。','note'))
        story.extend([PageBreak(),para('02  问题定位与图表','title')])
        if gnosis:
            story.append(para('本页波形与位置来自共同基础检查。灵犀云线长、伪差时间轴、PSD差异与频带热图见在线“查看图表”。'))
        locations=[['类型 / 通道','原始时间','复核依据']]
        for r in view['hf_candidates'][:2]:
            locations.append([f'高频突发 / {r["channel_name"]}',f'{r["start_seconds"]:g}-{r["stop_seconds"]:g} s',f'峰值 z = {r["peak_z_score"]:.2f}'])
        for r in view['line_channels'][:2]:
            e=r['example'];locations.append([f'工频 / {r["name"]}',f'{e["start_seconds"]:g}-{e["stop_seconds"]:g} s',f'{r["hits"]}/{r["total"]} 个检查窗命中；代表频率 {e["peak_frequency_hz"]:g} Hz'])
        if len(locations)>1:story.append(table(locations,[155,117,235]))
        else:story.append(para('本次没有可展示的基础检查候选位置。','note'))
        story.append(para('展示前2条高频候选及命中最多的2个工频通道；完整候选保留在在线报告。','note'))
        if figure:
            im=ImageReader(BytesIO(figure));iw,ih=im.getSize();height=min(228,507*ih/iw)
            story.extend([Spacer(1,8),Image(BytesIO(figure),width=height*iw/ih,height=height),
                          para('阴影为候选区间；显示原始信号，未清洗、未重参考。','note')])
        else:story.append(para('对应原始波形暂不可用，检测结果仍保留。','note'))
        for note in figure_notes[:2]:story.append(para(note,'note'))
        story.extend([para('复核记录','heading'),para('结论：__________________    复核人 / 日期：__________________'),
                      para('意见：__________________________________________________'),
                      PageBreak(),para('03  总分组成与测量依据','title'),para(score_composition(score))])
        if weighted and active:
            story.append(table([['计分项目','占总分','分项 / 100']]+[[r['name'],f'{100*r["share"]:.1f}%',point(r['value'])] for r in active],[300,103,104]))
            story.append(para('分项 = 100 ×（1 - 候选占比）；总分 = 各分项 × 对应占比，再相加。比例按显示精度四舍五入。','note'))
        elif not weighted:
            legacy=('旧版 v0.1：分项 = 100 ×（1 - 候选量 / 有效检查量）；总分为三项的平均分。'
                    if score.get('version')=='eeg-basic-screen/0.1' else
                    '旧版 v0.2：逐通道候选占比按均方根汇总分项，总分取最低分项。')
            story.append(para(legacy,'note'))
        measured=active if appendix else all_rows
        story.extend([para('实际测量','heading'),table([['检查项目','实际测量']]+[[r['name'],r['measurement']] for r in measured],[140,367]),
            para('通道检查窗是一个通道的一个时间窗；累计通道时长是各通道秒数之和。工频命中窗占比不能直接当成整份记录受干扰的时长占比。','note'),
            para('计分项目缺失或范围未完成，不补满分、不重新分配比例。比较结果时应使用相同方法、处理状态和计分配置。','note')])
        if gnosis:story.append(para('灵犀云方法在分析副本上执行，具体滤波、参考和取段参数见在线图表。这里的分项汇总由DBCI-QC提供，并非灵犀云官方总分。','note'))
        revision=view.get('score_revision')
        if revision:story.append(para(f'本次为展示修订；运行时 {revision["previous_version"]} 为 {point(revision["previous_value"])} 分，原文件保留。','note'))
        story.extend([para('来源与追溯','heading'),para(f'任务 {job_id or "未登记"}；规则 {score["version"]}；配置 {score.get("configuration_id","旧版固定规则")}。','note'),
            para('方法来源：BrainElecQC / DBCI-QC'+(' / GnosisNeuroDynamicSE' if gnosis else ''),'note')])
        if job_id:
            story.append(para(f'本地报告：/api/v1/jobs/{job_id}/report','note'))
            story.append(para(f'图表：/api/v1/jobs/{job_id}/visualizations','note'))
        if appendix:
            story.extend([PageBreak(),para('附录  其他检查','title'),para('以下结果不计入本方案总分。原始输入的共同基础检查独立保留。'),
                table([['检查项目','分项 / 100','检查发现']]+[[r['name'],point(r['value']),r['finding']] for r in supplemental],[125,67,315]),
                para('实际测量','heading'),table([['检查项目','实际测量']]+[[r['name'],r['measurement']] for r in supplemental],[140,367])])
        doc.build(story,onFirstPage=frame,onLaterPages=frame)
        return out.getvalue()
