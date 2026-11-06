"""Readable D04 HTML and PDF exports from the same frozen review case."""
import html
from io import BytesIO
import os
from pathlib import Path
import threading
from .review import LABELS

_PDF_LOCK = threading.RLock()


def report_content(case, language='zh-CN'):
    en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    label = lambda key: LABELS.get(key, (key, key))[int(en)]
    final = case.get('final')
    previous = case.get('previous')
    cards = [(case['dataset_summary']['records'], t('份记录', 'recordings')),
             (case['summary']['pending'], t('项待处理', 'pending decisions')),
             (case['summary']['needs_fix'], t('项需整改', 'corrections required')),
             ((previous or {}).get('counts', {}).get('resolved', 0), t('项复验消除', 'resolved on retest'))]
    rows = []
    priorities = {'needs_fix': 0, 'restricted_use': 1, 'pending': 2, 'follow_up': 3, 'acceptable_difference': 4}
    machine = {'conflict': t('资料不符', 'Mismatch'), 'review': t('待核对', 'Review'), 'unassessed': t('未评', 'Unassessed')}
    for row in sorted(case['rows'], key=lambda r: (priorities[r['disposition']], r['status'] == 'unassessed', r['module'], r['target'])):
        d = row.get('decision') or {}
        rows.append({'title': row['label_en'] if en else row['label'], 'target': row['target'],
                     'module': row['module'], 'machine': machine[row['status']], 'disposition': label(row['disposition']),
                     'message': row['message'], 'files': row.get('files', []), 'observed': row.get('observed'),
                     'impact': d.get('impact') or t('待确认', 'To confirm'),
                     'action': d.get('action') or t('核对来源资料并记录处理依据。', 'Verify the source and record the decision basis.'),
                     'owner': d.get('owner') or t('未指定', 'Unassigned'), 'note': d.get('note') or '',
                     'reviewer': d.get('reviewer') or '', 'disposition_key': row['disposition']})
    delta = []
    if previous:
        delta = [{**r, 'title': r['label_en'] if en else r['label'], 'change_label': label(r['change'])}
                 for r in previous['rows'] if r['change'] != 'unchanged']
    return {'title': t('数据集审核与复验报告', 'Dataset review and retest report'), 'label': case['label'],
            'outcome': label(case['outcome']), 'cards': cards, 'rows': rows, 'delta': delta,
            'status_note': (t('尚未确认本次审核结论。', 'The review outcome has not been confirmed.') if not final else
                            f"{final['reviewer']} · {final['recorded_at']} · {final['purpose']}"),
            'demo': t('工程演示 · 使用公开数据副本及模拟处理记录', 'Engineering demo: public-data copy and simulated review entries') if case.get('engineering_demo') else '',
            'boundary': t('程序检查、人工处理与信号评分分别保留。这里的审核仅针对声明范围，不代表医院验收或真实身份认证。',
                          'Machine checks, human decisions and signal scores remain separate. This local review is scope-specific, not hospital acceptance or verified identity.'),
            'unassessed_note': t(f"仍有 {case['summary']['unassessed']} 项程序检查未评；登记用途或跟踪意见不会把它们改成通过。",
                                f"{case['summary']['unassessed']} machine checks remain unassessed; review notes do not turn them into passes.")}


def render_review_report(case, language='zh-CN'):
    import json
    c = report_content(case, language); en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    e = lambda x: html.escape(str(x), quote=True)
    base = '/api/v1/package-jobs/' + case['job_id'] + '/review'
    cards = ''.join(f'<div><b>{e(value)}</b><span>{e(name)}</span></div>' for value, name in c['cards'])
    rows = ''.join(f'''<article class="finding"><div class="finding-head"><h3>{e(r['title'])}</h3><span class="badge {e(r['disposition_key'])}">{e(r['disposition'])}</span></div>
<p class="target">{e(r['module'])} · {e(r['target'])} · {e(r['machine'])}</p>
<dl><dt>{t('影响 / 允许用途','Impact / permitted use')}</dt><dd>{e(r['impact'])}</dd><dt>{t('下一步','Next step')}</dt><dd>{e(r['action'])}</dd><dt>{t('负责人','Owner')}</dt><dd>{e(r['owner'])}</dd></dl>
{('<p class="note">'+e(r['note'])+'</p>') if r['note'] else ''}
<details><summary>{t('程序证据','Machine evidence')}</summary><p>{e(r['message'])}</p><p class="target">{e('; '.join(r['files']))}</p><pre>{e(json.dumps(r['observed'], ensure_ascii=False, indent=2))}</pre></details></article>''' for r in c['rows'])
    prev = case.get('previous'); delta = ''
    if prev:
        changes = ''.join(f'<tr><td>{e(r["title"])}</td><td>{e(r["target"])}</td><td>{e(r["change_label"])}</td><td>{e(r["before"])} → {e(r["after"])}</td></tr>' for r in c['delta'])
        counts = ' · '.join(f'{LABELS[k][int(en)]} {v}' for k, v in prev['counts'].items())
        delta = f'<section><h2>{t("复验变化","Retest changes")}</h2><p>{e(counts)}</p><p class="muted">{t("未复查或范围改变，不计为问题消除。","Missing checks or a changed scope do not count as resolved.")}</p><div class="table-scroll"><table><thead><tr><th>{t("检查项","Check")}</th><th>{t("对象","Target")}</th><th>{t("变化","Change")}</th><th>{t("程序状态","Machine status")}</th></tr></thead><tbody>{changes or "<tr><td>—</td></tr>"}</tbody></table></div></section>'
    history = ''.join(f'<li>r{r["revision"]} · {e(r["reviewer"])} · {e(r["recorded_at"])}</li>' for r in case.get('history', []))
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(c['title'])}</title>
<style>body{{margin:0;background:#f4f7fc;color:#203650;font:15px/1.65 system-ui,sans-serif}}main{{max-width:1040px;margin:32px auto;padding:0 24px 40px}}nav{{display:flex;justify-content:space-between;gap:16px;margin-bottom:26px}}a{{color:#245cd5;text-decoration:none}}section{{background:white;border:1px solid #dfe7f2;border-radius:18px;padding:30px;margin-bottom:22px}}h1{{font-size:28px;margin:8px 0}}h2{{font-size:20px;margin:0 0 16px}}h3{{font-size:16px;margin:0}}p{{margin:8px 0}}.eyebrow,.muted,.target{{color:#708099;font-size:13px}}.target{{overflow-wrap:anywhere}}.outcome{{font-size:24px;font-weight:650;color:#245cd5;margin:22px 0 8px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;border-top:1px solid #e5ebf4;margin-top:24px;padding-top:24px}}.cards b{{font-size:30px;display:block;font-variant-numeric:tabular-nums}}.cards span{{font-size:13px;color:#708099}}.demo{{background:#edf3ff;color:#245cd5;border-radius:7px;padding:8px 12px;font-size:13px}}.finding{{padding:22px 0;border-top:1px solid #e5ebf4}}.finding-head{{display:flex;justify-content:space-between;gap:16px}}.badge{{padding:3px 8px;background:#eff3f8;color:#526985;border-radius:6px;white-space:nowrap;font-size:12px}}.needs_fix{{background:#fff0eb;color:#ad4b27}}.restricted_use{{background:#fff7e5;color:#96631b}}.note{{background:#f5f8fc;padding:10px 14px;border-radius:7px;font-size:13px}}dl{{display:grid;grid-template-columns:135px 1fr;gap:6px 16px;font-size:14px}}dt{{color:#708099}}dd{{margin:0;overflow-wrap:anywhere}}summary{{color:#315a90;cursor:pointer}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#f5f8fc;padding:12px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:10px;border-bottom:1px solid #e1e9f3;text-align:left;overflow-wrap:anywhere}}.table-scroll{{overflow:auto}}@media(max-width:640px){{main{{padding:0 14px}}section{{padding:20px}}.cards{{grid-template-columns:repeat(2,1fr)}}dl{{grid-template-columns:1fr}}h1{{font-size:23px}}}}@media print{{body{{background:white}}nav{{display:none}}main{{margin:0;padding:0}}section{{border:0;padding:12px 0}}h2,h3{{break-after:avoid}}thead{{display:table-header-group}}}}</style></head><body><main>
<nav><a href="/datasets?job={case['job_id']}&tab=review">← {t('返回数据集','Back to dataset')}</a><a href="{base}/pdf?lang={language}">{t('下载 PDF','Download PDF')}</a></nav>
<section><p class="eyebrow">DBCI-QC · D04</p><h1>{e(c['title'])}</h1><p>{e(c['label'])}</p>{('<p class="demo">'+e(c['demo'])+'</p>') if c['demo'] else ''}<div class="outcome">{e(c['outcome'])}</div><p>{e(c['status_note'])}</p><p class="muted">{e(case['scope'])}</p><div class="cards">{cards}</div></section>
{delta}<section><h2>{t('处理清单','Action register')}</h2><p class="muted">{e(c['unassessed_note'])}</p>{rows or '<p>'+t('本次范围内没有待处理的程序发现。','No machine findings need a decision within this scope.')+'</p>'}</section>
<section><h2>{t('范围与追溯','Scope and traceability')}</h2><p>{e(c['boundary'])}</p><p class="target">{e(case['schema_version'])} · {e(case['rule_version'])} · r{case['revision']}<br>{case['job_id']}<br>{e(case['checked_at'])}</p><details><summary>{t('审核历史','Review history')}</summary><ul>{history}</ul></details></section></main></body></html>'''


def review_pdf(case, language='zh-CN'):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
    c = report_content(case, language); en = language == 'en'; t = lambda a,b: b if en else a
    with _PDF_LOCK:
        font = 'DatasetQC-CJK'
        if font not in pdfmetrics.getRegisteredFontNames():
            for filename in [os.environ.get('DBCI_QC_PDF_FONT', ''), '/usr/share/fonts/fonts-gb/GB_HT_GB18030.ttf', 'C:/Windows/Fonts/msyh.ttc']:
                if filename and Path(filename).is_file():
                    try: pdfmetrics.registerFont(TTFont(font, filename)); break
                    except Exception: continue
            else:
                font = 'STSong-Light'
                if font not in pdfmetrics.getRegisteredFontNames(): pdfmetrics.registerFont(UnicodeCIDFont(font))
        blue = colors.HexColor('#245cd5'); ink = colors.HexColor('#203650'); muted = colors.HexColor('#687c96')
        body = ParagraphStyle('body', fontName=font, fontSize=10, leading=16, textColor=ink, wordWrap='CJK', spaceAfter=7)
        small = ParagraphStyle('small', parent=body, fontSize=8, leading=12, textColor=muted)
        h1 = ParagraphStyle('h1', parent=body, fontSize=22, leading=31, spaceAfter=16)
        h2 = ParagraphStyle('h2', parent=body, fontSize=14, leading=21, spaceBefore=14, spaceAfter=10, keepWithNext=True)
        def p(value, style=body): return Paragraph(html.escape(str(value)), style)
        output = BytesIO()
        doc = SimpleDocTemplate(output, pagesize=(595.28,841.89), leftMargin=42, rightMargin=42, topMargin=54, bottomMargin=48,
                                title=c['title'], author='DBCI-QC')
        story = [p(c['title'], h1), p(c['label']), p(c['demo'], small) if c['demo'] else Spacer(1,1),
                 p(c['outcome'], h2), p(c['status_note']), p(case['scope'], small)]
        cards = Table([[p(f'{v}  {name}') for v,name in c['cards']]], colWidths=[127.8]*4)
        cards.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#edf3ff')),('VALIGN',(0,0),(-1,-1),'TOP'),
                                  ('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
        story.extend([Spacer(1,10), cards, Spacer(1,10), p(c['unassessed_note'], small)])
        prev = case.get('previous')
        if prev:
            story.append(p(t('复验变化','Retest changes'),h2))
            story.append(p(' · '.join(f'{LABELS[k][int(en)]} {v}' for k,v in prev['counts'].items())))
            for r in c['delta'][:12]:
                story.append(p(f"{r['title']} / {r['target']} / {r['change_label']}",small))
            if len(c['delta']) > 12: story.append(p(t('其余变化见完整 HTML 报告。','Additional changes are available in the full HTML report.'), small))
            story.append(p(t('范围改变或未复查，不计为问题消除。','Changed scopes or omitted checks do not count as resolved.'), small))
        reviewed = [r for r in c['rows'] if r['note']]
        if reviewed:
            story.append(p(t('已登记的处理意见','Recorded decisions'),h2))
        for r in reviewed:
            story.append(KeepTogether([p(r['title']+' / '+r['disposition'],h2),p(r['target'],small)]))
            story.extend([p(t('影响：','Impact: ')+r['impact']),p(t('下一步：','Next step: ')+r['action']),
                          p(t('负责人：','Owner: ')+r['owner'],small),p(r['note'],small)])
        story.append(p(t('全部待处理事项','All findings'),h2))
        if c['rows']:
            import re
            story.append(p(t('对象显示个体及运行编号；完整路径与测量值见配套 HTML。未评项表示证据不足。',
                             'Targets show subject and run identifiers; full paths and measurements are in the HTML. Unassessed means insufficient evidence.'),small))
            head = [t('检查项','Check'),t('对象','Target'),t('程序结果','Machine result'),t('人工处理','Decision')]
            data = [[p(v,small) for v in head]]
            for r in c['rows']:
                short = re.sub(r'_ses-[^_ /]+_task-[^_ /]+_acq-', ' / ', r['target']).replace('_run-', ' / run-')
                short = short.removesuffix('-raw').removesuffix('-derived')
                data.append([p(r['module']+' '+r['title'],small),p(short,small),p(r['machine'],small),p(r['disposition'],small)])
            table = Table(data, colWidths=[115,240,77,79], repeatRows=1, hAlign='LEFT')
            table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf3ff')),
                ('LINEBELOW',(0,0),(-1,-1),.4,colors.HexColor('#dfe7f2')),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
            story.append(table)
        else: story.append(p(t('本次范围内没有待处理的程序发现。','No machine findings need a decision in this scope.')))
        story.append(KeepTogether([p(t('范围与追溯','Scope and traceability'),h2),p(c['boundary'],small),
                      p(f"{case['schema_version']} / {case['rule_version']} / r{case['revision']}",small),
                      p(case['job_id']+' / '+case['checked_at'],small)]))
        def page(canvas, document):
            canvas.saveState();canvas.setFillColor(blue);canvas.rect(0,833,595.28,9,fill=1,stroke=0)
            canvas.setFillColor(muted);canvas.setFont(font,8);canvas.drawString(42,28,'DBCI-QC / D04');canvas.drawRightString(553,28,str(document.page));canvas.restoreState()
        doc.build(story,onFirstPage=page,onLaterPages=page)
        return output.getvalue()
