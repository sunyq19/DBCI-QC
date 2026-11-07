"""Print-specific typography, tables and pagination for saved EEG reports."""
from html import escape
from io import BytesIO
import os
from pathlib import Path


def build_pdf(view, figure=None, figure_notes=(), job_id=''):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib import colors
    from reportlab.lib.utils import ImageReader
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Table, TableStyle,
                                   Spacer, PageBreak, Image)
    from reportlab.pdfgen.canvas import Canvas
    from .report_export import EXPORT_VERSION, score_rows, score_weight_label

    font = 'QC-Report-Sans'
    if font not in pdfmetrics.getRegisteredFontNames():
        for path in [os.environ.get('DBCI_QC_PDF_FONT', ''),
                     '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                     'C:/Windows/Fonts/msyh.ttc', '/System/Library/Fonts/PingFang.ttc',
                     '/usr/share/fonts/fonts-gb/GB_HT_GB18030.ttf']:
            if path and Path(path).is_file():
                try:
                    pdfmetrics.registerFont(TTFont(font, path)); break
                except Exception:
                    continue
        else:
            font = 'STSong-Light'
            if font not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(UnicodeCIDFont(font))
    ink, blue, muted, line, wash = map(colors.HexColor,
        ['#23364b', '#2459a6', '#607084', '#dce3ea', '#f2f5f8'])
    width = 511.28
    base = ParagraphStyle('body', fontName=font, fontSize=9, leading=13.5,
                          textColor=ink, wordWrap='CJK', spaceAfter=5)
    styles = dict(body=base,
        note=ParagraphStyle('note', parent=base, fontSize=7.8, leading=11.5, textColor=muted, spaceAfter=4),
        title=ParagraphStyle('title', parent=base, fontSize=21, leading=28, spaceAfter=5),
        subtitle=ParagraphStyle('subtitle', parent=base, fontSize=11, leading=16, spaceAfter=4),
        section=ParagraphStyle('section', parent=base, fontSize=11, leading=17, spaceBefore=12, spaceAfter=7, keepWithNext=True),
        cell=ParagraphStyle('cell', parent=base, fontSize=8.3, leading=12, spaceAfter=0),
        head=ParagraphStyle('head', parent=base, fontSize=7.8, leading=11, textColor=muted, spaceAfter=0),
        score=ParagraphStyle('score', parent=base, fontName='Helvetica-Bold', fontSize=32, leading=38, textColor=blue, spaceAfter=2),
        numeric=ParagraphStyle('numeric', parent=base, fontName='Helvetica', fontSize=9.5, leading=12, alignment=2, spaceAfter=0),
        weight=ParagraphStyle('weight', parent=base, fontSize=8.3, leading=12, alignment=2, textColor=muted, spaceAfter=0))
    styles['head_right'] = ParagraphStyle('head_right', parent=styles['head'], alignment=2)

    def para(value, kind='body'):
        # ReportLab's CID fallback does not cover every Unicode dash variant.
        value = str(value).replace('–', '-').replace('—', '-').replace('‑', '-')
        return Paragraph(escape(value), styles[kind])

    def table(rows, widths, numeric=(), weights=()):
        cells = [[para(value, ('head_right' if j in tuple(numeric)+tuple(weights) else 'head') if i == 0 else 'weight' if j in weights else
                  'numeric' if j in numeric and isinstance(value, (int, float)) else 'cell')
                  for j, value in enumerate(row)] for i, row in enumerate(rows)]
        # Numeric strings keep decimal places; missing values use the Chinese font.
        for i, row in enumerate(rows[1:], 1):
            for j in numeric:
                if str(row[j]).replace('.', '', 1).isdigit():
                    cells[i][j] = para(row[j], 'numeric')
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), wash),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 9),
            ('RIGHTPADDING', (0, 0), (-1, -1), 9),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LINEBELOW', (0, 0), (-1, 0), .6, line),
            ('LINEBELOW', (0, 1), (-1, -1), .35, line)]))
        for j in tuple(numeric) + tuple(weights):
            t.setStyle(TableStyle([('ALIGN', (j, 0), (j, -1), 'RIGHT')]))
        return t

    point = lambda value: '未评' if value is None else f'{value:.2f}'
    all_rows = score_rows(view); score = view['score']
    active = [r for r in all_rows if r['included']]
    supplemental = [r for r in all_rows if not r['included']]
    appendix = len(supplemental) > 3
    weighted = score.get('version', '').startswith('project-weighted/')
    gnosis = any(r['id'].startswith('gnosis_') for r in all_rows)
    route = '灵犀云扩展方案' if gnosis else '基础检查方案'
    rec = view['recording']; start = rec.get('start_seconds', 0)
    stop = start + rec.get('duration_seconds', 0)
    run_name = view.get('run_name') or view['label']
    cov = view.get('coverage', {})
    measured = active if appendix else all_rows

    class ReportCanvas(Canvas):
        # Deferred page drawing adds accurate page totals without a second analysis pass.
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs); self.pages = []
        def showPage(self):
            self.pages.append(dict(self.__dict__)); self._startPage()
        def save(self):
            total = len(self.pages)
            for state in self.pages:
                self.__dict__.update(state)
                self.saveState()
                self.setFillColor(blue); self.rect(42, 801, 3, 11, fill=1, stroke=0)
                self.setFont('Helvetica-Bold', 9); self.drawString(52, 803, 'DBCI-QC')
                self.setFillColor(muted); self.setFont(font, 8)
                self.drawRightString(553.28, 803, '数据质量检查报告')
                self.setStrokeColor(line); self.setLineWidth(.5); self.line(42, 790, 553.28, 790)
                self.line(42, 40, 553.28, 40)
                self.setFont(font, 7); self.drawString(42, 27, '项目自定义检查 · 自动候选待复核')
                self.setFont('Helvetica', 7.5); self.drawRightString(553.28, 27, f'{self._pageNumber} / {total}')
                self.restoreState(); super().showPage()
            super().save()

    out = BytesIO()
    doc = SimpleDocTemplate(out, pagesize=(595.28, 841.89), leftMargin=42, rightMargin=42,
        topMargin=66, bottomMargin=52, title=f'DBCI-QC - {run_name}', author='DBCI-QC',
        subject=f'Rule: {score["version"]}; configuration: {score.get("configuration_id", "legacy")}; report: {job_id}')
    story = [para('数据质量检查报告', 'title'), para(run_name, 'subtitle')]
    if view.get('run_name') and view['run_name'] != view['label']:
        story.append(para('数据：' + view['label'], 'note'))
    story.extend([para(route + '  /  ' + ('整份记录' if view.get('scope') == 'recording' else '指定时段'), 'note'), Spacer(1, 7)])
    facts = [('模态 / 格式', '头皮 EEG / ' + view['format']),
             ('分析通道', f'{rec.get("channel_count", "未记录")} 道'),
             ('采样率', f'{rec["sampling_rate_hz"]:g} Hz' if rec.get('sampling_rate_hz') else '未记录'),
             ('检查范围', f'{start:g}-{stop:g} 秒'),
             ('原始记录', f'{view["input_duration_seconds"]:g} 秒'),
             ('已计算时长', f'{cov["completed_seconds"]:g} / {cov["total_seconds"]:g} 秒' if cov else '见检查范围')]
    grid = Table([[[para(k, 'head'), para(v)] for k, v in facts[i:i+3]] for i in (0, 3)],
                 colWidths=[width/3]*3, hAlign='LEFT')
    grid.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0), ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story.extend([grid, Spacer(1, 10)])
    flagged = [r for r in active if r['value'] is not None and r['value'] < 100]
    if score.get('value') is None:
        finding = score.get('missing_reason') or '未设置总分或部分项目测量不足，已完成的分项结果保留。'
        finding_title = '总分未汇总'
    elif flagged:
        first = min(flagged, key=lambda r: r['value'])
        finding_title, finding = '主要发现 · ' + first['name'], first['finding']
    else:
        finding_title, finding = '检查概况', view['headline'] + '。' + view['summary']
    left = [para('综合分 / 100', 'note'), para('未评', 'subtitle') if score.get('value') is None else para(point(score['value']), 'score')]
    right = [para(finding_title, 'subtitle'), para(finding), para('分数描述本方案候选负担，不设通用合格线。', 'note')]
    hero = Table([[left, right]], colWidths=[120, width-120], hAlign='LEFT')
    hero.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eef3fa')),
        ('LINEBEFORE', (0, 0), (0, 0), 3, blue), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 10)]))
    story.append(hero)
    if cov.get('gap_seconds', 0) or cov.get('unexecuted_seconds', 0) or cov.get('failed_seconds', 0):
        story.append(para(f'范围说明：来源间隙 {cov.get("gap_seconds", 0):g} 秒；未执行 {cov.get("unexecuted_seconds", 0):g} 秒；执行失败 {cov.get("failed_seconds", 0):g} 秒。', 'note'))

    def results(rows):
        return table([['检查项目', '得分 / 100', '权重', '检查发现']] +
            [[r['name'], point(r['value']), score_weight_label(r, score), r['finding']] for r in rows],
            [132, 62, 54, width-248], numeric=(1,), weights=(2,))
    story.append(para('检查结果', 'section'))
    if active: story.append(results(active))
    else: story.append(para('未设置综合评分，分项测量如下。', 'note'))
    if supplemental and not appendix:
        story.extend([para('补充检查 · 不计入综合分', 'section'), results(supplemental)])
    elif appendix:
        story.append(para(f'另有 {len(supplemental)} 项补充检查，详见附页；不计入本方案综合分。', 'note'))
    if weighted:
        rule = '综合分 = 各项得分 × 对应权重，再相加。权重按显示精度四舍五入；各项完成后才汇总。'
    elif score.get('version') == 'eeg-basic-screen/0.1':
        rule = '旧版 v0.1：三个基础分项取平均值。'
    else:
        rule = '旧版 v0.2：逐通道异常占比按均方根汇总分项，综合分取三个分项的最低值。'
    story.extend([Spacer(1, 9), para(rule, 'note')])
    if gnosis:
        story.append(para('灵犀云分项来自分析副本；本报告的评分汇总由 DBCI-QC 提供。共同基础检查独立列示。', 'note'))

    story.extend([PageBreak(), para('问题定位与证据', 'title')])
    story.append(para('共同基础检查 · 候选位置与输入信号' if gnosis else '候选位置与输入信号', 'note'))
    locations = [['通道 / 类型', '原始时间', '定位依据']]
    for r in view.get('hf_candidates', [])[:2]:
        locations.append([f'{r["channel_name"]} / 高频突发', f'{r["start_seconds"]:g}-{r["stop_seconds"]:g} 秒', f'峰值 z = {r["peak_z_score"]:.2f}'])
    for r in view.get('line_channels', [])[:2]:
        e = r['example']
        locations.append([f'{r["name"]} / 工频', f'{e["start_seconds"]:g}-{e["stop_seconds"]:g} 秒',
                          f'{r["hits"]}/{r["total"]} 窗命中；代表频率 {e["peak_frequency_hz"]:g} Hz'])
    if len(locations) > 1:
        story.append(table(locations, [133, 110, width-243]))
        story.append(para('展示前 2 条高频候选及命中最多的 2 个工频通道；工频时间为代表窗口。', 'note'))
    else:
        story.append(para('本次未记录可展示的基础检查候选位置。', 'note'))
    if figure:
        iw, ih = ImageReader(BytesIO(figure)).getSize()
        height = min(250, width * ih / iw)
        story.extend([Spacer(1, 5), Image(BytesIO(figure), width=height*iw/ih, height=height),
                      para('阴影标出待复核区间，横轴为原始记录时间。图中示例不代表全部候选。', 'note')])
    else:
        story.extend([Spacer(1, 8), para('波形暂不可用', 'subtitle'),
                      para('已保存的定位结果仍可用于复核。原始文件可用时，可在在线报告打开对应波形。', 'note')])
    for note in figure_notes[:2]: story.append(para(note, 'note'))
    if gnosis:
        story.append(para('本页仅展示共同基础检查定位；灵犀云伪差时间轴、PSD 差异与频带图保留在在线报告的图表分析中。', 'note'))
    story.append(para('测量依据', 'section'))
    story.append(table([['检查项目', '实际测量']] + [[r['name'], r['measurement']] for r in measured], [143, width-143]))
    story.append(para('通道窗指一个通道的一个检查窗；累计通道秒为各通道时长之和。工频窗命中比例不等于整份记录的污染时长比例。', 'note'))
    if appendix:
        story.extend([PageBreak(), para('补充检查', 'title'), para('共同基础检查 · 不计入本方案综合分', 'note'), results(supplemental),
                      para('补充测量', 'section'), table([['检查项目', '实际测量']] + [[r['name'], r['measurement']] for r in supplemental], [143, width-143])])
    story.append(Spacer(1, 5))
    if weighted:
        story.append(para('分项 = 100 × (1 - 候选占比)。权重见检查结果表；缺失项目不补满分，也不重新分配权重。', 'note'))
    else: story.append(para(rule, 'note'))
    story.append(para('自动标记为待复核线索。比较不同记录时，需使用相同检查项目、输入处理状态及评分配置。', 'note'))
    revision = view.get('score_revision')
    if revision:
        story.append(para(f'本报告使用保存的展示修订；原评分 {revision["previous_version"]} 为 {point(revision["previous_value"])} 分，原始报告保留。', 'note'))
    trace = f'评分规则：{score["version"]}  ·  导出版本：{EXPORT_VERSION}'
    if job_id: trace += f'  ·  报告编号：{job_id}'
    story.extend([Spacer(1, 4), para(trace, 'note')])
    # The exact configuration stays in PDF metadata, outside the result hierarchy.
    doc.build(story, canvasmaker=ReportCanvas)
    return out.getvalue()
