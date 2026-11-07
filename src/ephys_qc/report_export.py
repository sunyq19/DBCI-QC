"""Portable EEG summary exports derived from the same versioned report view."""
from io import BytesIO
from pathlib import Path
from html import escape
import json
import os
import threading

EXPORT_VERSION = 'eeg-pdf/1.2'
_RENDER_LOCK = threading.RLock()


def score_rows(view):
    """Scores and deductions share exactly the same denominators as the UI."""
    descriptions = [
        f'非有限值 {view["finite"]["nonfinite"]}；恒值 {view["finite"]["constant"]} 个样本',
        f'{view["line"]["hits"]} / {view["line"]["total"]} 个通道窗命中',
        f'{view["score"]["hf_candidate_channel_seconds"]:g} / {view["score"]["hf_valid_channel_seconds"]:g} 通道秒为候选',
    ]
    rows=[]
    units={'channels':'通道','channel_seconds':'通道秒','channel_samples':'通道样本','channel_windows':'通道窗',
           'channel_block_seconds':'通道块秒','samples':'有效样本','epochs':'片段','seconds':'秒'}
    amount=lambda v:'—' if v is None else f'{v:g}'
    for c in view['score']['components']:
        key=c['id'];core=['integrity','line_noise','hf_burst']
        d=descriptions[core.index(key)] if key in core else f"{amount(c.get('candidate_amount'))} / {amount(c.get('assessed_amount'))} {units.get(c.get('unit'),c.get('unit',''))} 为候选"
        if c['value'] is None:reason=c.get('reason') or '有效测量不足，未计分'
        elif 'candidate_fraction' in c:reason=f"候选占比 {100*c['candidate_fraction']:.2f}%；权重 {c['weight']:g}；"+d
        else:reason=f"通道异常占比 RMS {100*c.get('rms_burden',0):.2f}%；"+d
        rows.append(dict(name=c['name'],value=c['value'],deduction=None if c['value'] is None else 100-c['value'],reason=reason))
    return rows


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
    """Two summary pages plus optional score appendix; no score recalculation."""
    from reportlab.pdfgen import canvas
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
        out=BytesIO(); c=canvas.Canvas(out,pagesize=(595.28,841.89),invariant=1)
        c.setTitle(f'DBCI-QC - {view["label"]}'); c.setAuthor('DBCI-QC')
        ink=colors.HexColor('#19314c'); blue=colors.HexColor('#245ad3');muted=colors.HexColor('#687b92')
        style=ParagraphStyle('body',fontName=font,fontSize=10,leading=16,textColor=ink,wordWrap='CJK')
        def text(s,x,y,size=11,color=ink):
            c.setFillColor(color);c.setFont(font,size);c.drawString(x,y,str(s))
        def paragraph(s,x,y,width=507,size=10,color=ink):
            st=ParagraphStyle('p',parent=style,fontSize=size,leading=size*1.55,textColor=color)
            p=Paragraph(escape(str(s)),st); _,h=p.wrap(width,1000);p.drawOn(c,x,y-h);return y-h
        def header(title,page):
            c.setFillColor(blue);c.rect(0,819,595.28,23,fill=1,stroke=0)
            text('DBCI-QC   质控报告',44,780,19);text(title,44,751,11,muted)
            c.setStrokeColor(colors.HexColor('#dfe7f2'));c.line(44,731,551,731)
            text(f'{EXPORT_VERSION}   /   {view["score"]["version"]}',44,35,8,muted)
            text(str(page),530,35,9,muted)
        def table(rows,y,widths):
            values=[[Paragraph(escape(str(v)),style) for v in row] for row in rows]
            t=Table(values,colWidths=widths,repeatRows=1)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3ff')),
                ('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
                ('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),
                ('LINEBELOW',(0,0),(-1,-1),.5,colors.HexColor('#dfe7f2'))]))
            _,h=t.wrap(507,700);t.drawOn(c,44,y-h);return y-h
        point=lambda v:'未评' if v is None else f'{v:.2f}'
        header('01  整份记录评分与结果' if view.get('scope')=='recording' else '01  选区评分与结果',1)
        y=paragraph(view['label'],44,710,size=11)
        rec=view['recording'];start=rec.get('start_seconds',0);stop=start+rec.get('duration_seconds',0)
        y=paragraph(f'{view["format"]}   /   头皮 EEG   /   {rec.get("channel_count")} 道   /   {rec.get("sampling_rate_hz"):g} Hz',44,y-12,color=muted)
        y=paragraph(f'本次检查 {start:g}-{stop:g} 秒；原记录 {view["input_duration_seconds"]:g} 秒。',44,y-6,color=muted)
        text(point(view['score']['value']),44,y-75,51,blue);text('/ 100',217,y-72,16,muted)
        text(view['score']['name'],326,y-32,14);text('项目自定义 v'+view['score']['version'].split('/')[-1] if view['score']['version'].startswith('project-weighted/') else '项目试行 v0.2',326,y-57,11,blue)
        y=y-108
        y=paragraph(view['headline']+'。'+view['summary'],44,y,size=12)
        if view['priority']: y=paragraph(view['priority'],44,y-7,color=muted)
        low=view.get('local_quality',{}).get('lowest')
        if low and low['lowest_component']['value']<100:
            y=paragraph(f'局部关注：{low["name"]} / {low["lowest_component"]["name"]} {low["lowest_component"]["value"]:.2f} 分。',44,y-6,size=10,color=blue)
        rows=[['检查项','得分 / 100','扣分','测量与扣分原因']]
        rows += [[r['name'],point(r['value']),point(r['deduction']),r['reason']] for r in score_rows(view)[:3]]
        y=table(rows,y-20,[96,86,60,265])
        y=paragraph(view['score'].get('formula','分项 = 100 × (1 - 通道异常占比的均方根)；总分取最低分项。缺项不出总分。'),44,y-16,size=9,color=muted)
        if view.get('coverage'):
            cov=view['coverage'];y=paragraph(f'整份覆盖：已计算 {cov["completed_seconds"]:g}/{cov["total_seconds"]:g} 秒；间隙 {cov["gap_seconds"]:g} 秒。先逐通道汇总，再评分。',44,y-9,size=9,color=muted)
        revision=view.get('score_revision')
        if revision:
            y=paragraph(f'按当前规则重算；运行时 {revision["previous_version"]} 为 {point(revision["previous_value"])} 分，原文件保留。',44,y-8,size=8,color=muted)
        y=paragraph('补充检查',44,y-20,size=13)
        extra=[r for r in view['checks'] if r['name'] in {'通道一致性','心电锁时','眼电锁时','文件标注','补充检查'}]
        for r in extra:
            y=paragraph(f'{r["name"]}：{r["state"]}。{r["value"]}',44,y-5,size=9,color=muted)
        y=paragraph('说明：项目试行评分，未设合格线。扩展计分项见附页，按所存权重纳入总分。',44,y-13,size=9,color=muted)
        if y<57: raise ValueError('PDF summary exceeds the fixed page layout')
        c.showPage();header('02  问题定位与复核',2)
        rows=[['类型 / 通道','原始时间','复核依据']]
        for r in view['hf_candidates'][:2]:
            rows.append([f'高频突发 / {r["channel_name"]}',f'{r["start_seconds"]:g}-{r["stop_seconds"]:g} s',f'峰值 z = {r["peak_z_score"]:.2f}'])
        for r in view['line_channels'][:2]:
            e=r['example']; rows.append([f'工频 / {r["name"]}',f'{e["start_seconds"]:g}-{e["stop_seconds"]:g} s',f'{r["hits"]}/{r["total"]} 窗命中；代表窗 {e["peak_frequency_hz"]:g} Hz'])
        y=table(rows,709,[160,135,212])
        y=paragraph('展示前 2 条高频候选及命中最多的 2 个工频通道；完整候选见在线报告与检测证据。',44,y-12,size=9,color=muted)
        if figure:
            im=ImageReader(BytesIO(figure));iw,ih=im.getSize();h=min(228,507*ih/iw);w=h*iw/ih
            c.drawImage(im,44,y-16-h,width=w,height=h);y-=h+24
            y=paragraph('阴影为检测候选区间。波形为对应原始信号的显示抽稀，未清洗、未重参考。',44,y,size=9,color=muted)
        else:
            y=paragraph('本次无可展示的候选波形。',44,y-15,size=10,color=muted)
        for n in figure_notes[:2]: y=paragraph(n,44,y-6,size=9,color=muted)
        y=paragraph('人工复核',44,y-18,size=13)
        y=paragraph('结论：____________________    复核人 / 日期：____________________',44,y-10,size=10)
        y=paragraph('意见：____________________________________________________',44,y-14,size=10)
        y=paragraph('追溯信息',44,y-24,size=11)
        y=paragraph(f'任务 {job_id or "未登记"}；规则 {view["score"]["version"]}。',44,y-8,size=8,color=muted)
        y=paragraph(f'计划 {view.get("plan_id") or "未登记"}；检测证据与参数保存在本次任务中。',44,y-4,size=8,color=muted)
        if y<57: raise ValueError('PDF content exceeds the fixed page layout')
        extras=score_rows(view)[3:]
        for offset in range(0,len(extras),6):
            c.showPage();header('扩展方法评分与权重',3+offset//6)
            rows=[['检查项','得分 / 100','扣分','测量与扣分原因']]
            rows += [[r['name'],point(r['value']),point(r['deduction']),r['reason']] for r in extras[offset:offset+6]]
            y=table(rows,709,[112,80,50,265])
            y=paragraph('权重为 0 的项目只展示分项。各方法的有效分母不同；缺项不补满分，不自动改变权重。',44,y-16,size=9,color=muted)
            if y<57:raise ValueError('PDF scoring appendix exceeds page layout')
        c.save();return out.getvalue()
