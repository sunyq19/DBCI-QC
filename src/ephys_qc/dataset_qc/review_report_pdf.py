"""Print layout for D04 reports; consumes the same content model as HTML."""
import html
from io import BytesIO
import os
from pathlib import Path
import threading

from .review import LABELS

_PDF_LOCK = threading.RLock()


def render_pdf(case, content, language):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas as canvas_module
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, PageBreak

    c = content; en = language == 'en'; t = lambda zh, eng: eng if en else zh
    width = 511.28
    with _PDF_LOCK:
        font = 'DatasetQC-Text-v2'
        if font not in pdfmetrics.getRegisteredFontNames():
            candidates = [os.environ.get('DBCI_QC_PDF_FONT', ''), '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                          '/usr/share/fonts/fonts-gb/GB_HT_GB18030.ttf', 'C:/Windows/Fonts/msyh.ttc']
            for name in candidates:
                if name and Path(name).is_file():
                    try:
                        pdfmetrics.registerFont(TTFont(font, name)); break
                    except Exception:
                        continue
            else:
                font = 'STSong-Light'
                if font not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(UnicodeCIDFont(font))
        # Use a real bold Latin face for the numbers; avoid synthetic bold CJK.
        number_font = 'Helvetica-Bold'
        number_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        if Path(number_path).is_file():
            number_font = 'DatasetQC-Numbers'
            if number_font not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(number_font, number_path))
        blue = colors.HexColor('#245cd5'); ink = colors.HexColor('#152b46'); muted = colors.HexColor('#65758c')
        line = colors.HexColor('#dce4ee'); pale = colors.HexColor('#f4f7fc'); amber = colors.HexColor('#a56223')
        body = ParagraphStyle('body', fontName=font, fontSize=10, leading=16, textColor=ink, wordWrap=None if en else 'CJK', spaceAfter=0)
        small = ParagraphStyle('small', parent=body, fontSize=8, leading=12, textColor=muted)
        cell = ParagraphStyle('cell', parent=body, fontSize=8.5, leading=13)
        heading = ParagraphStyle('heading', parent=body, fontSize=16, leading=24, spaceBefore=20, spaceAfter=12, keepWithNext=True)
        title = ParagraphStyle('title', parent=body, fontSize=25, leading=33, spaceAfter=8)
        sub = ParagraphStyle('subtitle', parent=body, fontSize=10, leading=16, textColor=muted, spaceAfter=20)
        number = ParagraphStyle('number', parent=body, fontName=number_font, fontSize=26, leading=33, textColor=blue)
        def p(value, style=body):
            return Paragraph(html.escape(str(value)), style)
        def section(n, text):
            return Paragraph(f'<font color="#245cd5" size="10">{n}</font>　{html.escape(text)}', heading)
        def table(headers, rows, widths, padding=6):
            data = [[p(h, small) for h in headers]] + rows
            result = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
            result.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'), ('BACKGROUND', (0,0), (-1,0), pale),
                ('LINEBELOW', (0,0), (-1,0), .6, line), ('LINEBELOW', (0,1), (-1,-1), .35, line),
                ('LEFTPADDING',(0,0),(-1,-1),9), ('RIGHTPADDING',(0,0),(-1,-1),9),
                ('TOPPADDING',(0,0),(-1,-1),padding), ('BOTTOMPADDING',(0,0),(-1,-1),padding)]))
            return result
        def box(flowables, background=pale, padding=18):
            result = Table([[flowables]], colWidths=[width], hAlign='LEFT')
            result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),background), ('BOX',(0,0),(-1,-1),.5,line),
                ('LEFTPADDING',(0,0),(-1,-1),padding), ('RIGHTPADDING',(0,0),(-1,-1),padding),
                ('TOPPADDING',(0,0),(-1,-1),padding), ('BOTTOMPADDING',(0,0),(-1,-1),padding)]))
            return result
        num = lambda value: '—' if value is None else str(value)
        ds = case['dataset_summary']; counts = c['counts']; prev = case.get('previous')
        story = [p(c['title'], title), p(c['subtitle']+'  /  '+c['checked_at'], sub), p(c['label']), Spacer(1,10)]
        context = [(ds.get('subjects'), t('个体','subjects')), (ds.get('records'), t('份记录','recordings')),
                   (ds.get('groups'), t('比较组','comparison groups'))]
        context_text = '   ·   '.join(f'{num(v)} {name}' for v,name in context)
        if 'expected_files' in ds:
            context_text += t(f"   ·   文件 {num(ds.get('present_files'))}/{ds['expected_files']} 已找到",
                              f"   ·   Files present {num(ds.get('present_files'))}/{ds['expected_files']}")
        story.extend([p(context_text,small),Spacer(1,21)])
        headline = ParagraphStyle('headline', parent=body, fontSize=18, leading=27, spaceAfter=6)
        metrics = [(counts['conflict'], t('资料不符','Mismatches'), amber),
                   (counts['unassessed'], t('未评','Unassessed'), muted), (counts['pass'], t('检查通过','Checks passed'), blue)]
        if counts['review']:
            metrics.insert(1,(counts['review'],t('待核对','Check needed'),ink))
        metric_data = []
        for value, name, color in metrics:
            style = ParagraphStyle('metric-'+name, parent=number, textColor=color)
            metric_data.append([p(num(value),style), p(name,small)])
        metrics_table = Table([metric_data], colWidths=[(width-36)/len(metrics)]*len(metrics))
        metrics_table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),
            ('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
        story.append(box([p(c['headline'],headline),p(c['description'],small),Spacer(1,16),metrics_table,
                          Spacer(1,13),p(c['count_note'],small)]))
        story.extend([Spacer(1,14),p(t('人工审核：','Human review: ')+c['outcome']),p(c['status_note'],small)])
        priorities = c['priority_groups']
        story.append(section('01', t('优先核对','Priority checks')))
        if priorities:
            # A short front page; all groups remain in the detailed register.
            def preview_targets(g):
                names = ', '.join(g['targets'][:6])
                if len(g['targets']) > 6:
                    names += t(f" 等 {len(g['targets'])} 个对象", f"; {len(g['targets'])} targets in total")
                return names
            data = [[p(g['ref']+'  '+g['title'],cell),p(preview_targets(g),small),
                     p(g['action'],cell)] for g in priorities[:3]]
            story.append(table([t('检查项','Check'),t('涉及对象','Affected targets'),t('建议处理','Suggested action')],data,[124,136,width-260]))
            if len(priorities)>3:
                story.extend([Spacer(1,6),p(t(f'其余 {len(priorities)-3} 类见检查明细。',f'{len(priorities)-3} further types are listed in the register.'),small)])
        else:
            story.append(p(t('本次没有资料不符或待核对项。','No metadata mismatches or review flags in this run.'),body))
        if prev:
            story.append(section('02',t('复验摘要','Retest summary')))
            if not prev.get('compatible'):
                story.append(p(t('范围或规则有变化，本次不能判定问题消除。','Scope or rules changed; this comparison cannot establish resolution.'),body))
            ordered = ('resolved','new','changed','unchanged','not_rechecked','scope_changed')
            parts = [f"{prev['counts'][key]} {LABELS[key][int(en)]}" for key in ordered if prev['counts'].get(key)]
            story.append(p('   /   '.join(parts)))
            story.extend([Spacer(1,8),p(t('仅在同一范围与规则下重新检查通过，才记为“复验已消除”。',
                                        'Resolution requires a passing recheck under the same scope and rules.'),small)])
        if c['counts']['unassessed']:
            story.extend([Spacer(1,16),p(t(f"另有 {c['counts']['unassessed']} 项未评，需补充资料或确认比较条件。",
                                          f"A further {c['counts']['unassessed']} checks need information or applicable comparison conditions."),small)])

        # Page 2 starts the detailed, complete register. Identical findings share one row.
        if c['rows']:
            story.extend([PageBreak(),p(t('检查明细','Finding register'),title),p(t('同类项目合并展示，全部检查对象保留。','Similar findings are grouped; every affected target is retained.'),sub)])
            data = []
            for g in c['groups']:
                # Bound each row's height while retaining every target in large datasets.
                for start in range(0,len(g['targets']),12):
                    first = start == 0
                    status_style = ParagraphStyle('status',parent=small,textColor=amber if g['status']=='conflict' else muted)
                    data.append([p(g['ref'],small),p(g['title'],cell),
                                 p(str(len(g['rows'])) if first else '—',cell),p(', '.join(g['targets'][start:start+12]),small),
                                 p(g['machine'],status_style),p(g['disposition'],small)])
            story.append(table([t('编号','Ref'),t('检查项','Check'),t('项数','N'),t('涉及对象','Targets'),t('程序结果','Result'),t('处理状态','Decision')],
                               data,[36,97,38,202,65,width-438]))
            story.extend([Spacer(1,14),p(t('R 编号仅为本报告的阅读简称，完整标识见后页。测量值、配套文件与逐项证据保留在 HTML 报告。',
                                           'R aliases are local to this report; full identifiers follow. Measurements, companion files and item-level evidence remain in the HTML report.'),small)])

        # Explicit appendix keeps technical provenance out of the front-page conclusion.
        if c['rows'] or prev:
            story.extend([PageBreak(),p(t('复验与审核记录','Retest and review records'),title),p(t('保留处理依据与版本，便于复查。','Decision basis and versions are retained for follow-up.'),sub)])
        if prev:
            story.append(p(t('复验变化','Retest changes'),heading))
            if c['delta']:
                data = [[p(r['title'],cell),p(r['short_target'],small),p(r['change_label'],small),
                         p(r['before_label']+' → '+r['after_label'],small)] for r in c['delta']]
                story.append(table([t('检查项','Check'),t('对象','Target'),t('变化','Change'),t('前后状态','Before / after')],data,[135,155,105,width-395]))
            else:
                story.append(p(t('没有发生变化的检查项。','No changed checks.')))
        decisions = [r for r in c['rows'] if r['decision']]
        if decisions:
            story.append(p(t('已登记的处理意见','Recorded decisions'),heading))
            for r in decisions:
                story.append(KeepTogether([p(r['title']+' · '+r['short_target']),p(r['disposition_label'],small)]))
                for key,value in [(t('影响 / 用途','Impact / use'),r['impact']), (t('下一步','Next step'),r['action']),
                                  (t('处理依据','Decision basis'),r['note']), (t('负责人 / 审核人','Owner / reviewer'),r['owner']+' / '+r['reviewer'])]:
                    story.extend([Spacer(1,5),p(key+'：'+value,cell)])
        elif not prev and c['rows']:
            story.append(p(t('尚未登记人工处理意见。','No human decisions recorded.')))
        if decisions:
            story.extend([PageBreak(),p(t('记录与追溯','Identifiers and provenance'),title)])
        if c['records']:
            story.append(p(t('记录标识对照','Recording identifiers'),heading))
            data = [[p(r['alias'],cell),p(r['id'],small)] for r in c['records']]
            story.append(table([t('简称','Alias'),t('完整记录标识','Full recording identifier')],data,[45,width-45]))
        trace = [p(t('范围与追溯','Scope and traceability'),heading),p(case['scope'],small),Spacer(1,8)]
        pairs = [(t('审核结论','Review outcome'),c['outcome']), (t('规则 / 审核版本','Rules / review revision'),case['rule_version']+f' / r{case["revision"]}'),
                 (t('运行编号','Run ID'),case['job_id']), (t('结果指纹','Result fingerprint'),case['result_hash']),
                 (t('版式版本','Layout version'),c['layout_version'])]
        if prev:
            pairs.insert(3,(t('对照运行','Baseline run'),prev.get('job_id','—')))
        if case.get('final'):
            pairs.insert(1,(t('确认人 / 时间','Confirmed by / at'),case['final']['reviewer']+' / '+case['final']['recorded_at']))
        for key,value in pairs:
            trace.append(p(key+'：'+value,small))
        trace.extend([Spacer(1,6),p(c['boundary'],small)])
        # Keep the heading with its first text; let long provenance flow normally.
        story.extend(trace)
        output = BytesIO()
        doc = SimpleDocTemplate(output,pagesize=(595.28,841.89),leftMargin=42,rightMargin=42,topMargin=65,bottomMargin=52,
                                title=c['title'],author='DBCI-QC')
        class NumberedCanvas(canvas_module.Canvas):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs);self.states=[]
            def showPage(self):
                self.states.append(dict(self.__dict__));self._startPage()
            def save(self):
                total=len(self.states)
                for state in self.states:
                    self.__dict__.update(state)
                    self.saveState();self.setStrokeColor(line);self.setLineWidth(.5);self.line(42,39,553.28,39)
                    self.setFillColor(muted);self.setFont(font,7.5)
                    self.drawString(42,25,case['job_id'][:8].upper()+'  /  '+c['checked_at'])
                    self.drawRightString(553.28,25,f'{self._pageNumber} / {total}')
                    self.restoreState();super().showPage()
                super().save()
        def page(canvas, document):
            canvas.saveState();canvas.setFillColor(blue);canvas.rect(42,810,23,3,fill=1,stroke=0)
            canvas.setFont('Helvetica-Bold',10);canvas.drawString(72,805,'DBCI-QC')
            canvas.setFillColor(muted);canvas.setFont(font,8)
            canvas.drawRightString(553.28,805,c['demo'] or c['subtitle'])
            canvas.restoreState()
        doc.build(story,onFirstPage=page,onLaterPages=page,canvasmaker=NumberedCanvas)
        return output.getvalue()
