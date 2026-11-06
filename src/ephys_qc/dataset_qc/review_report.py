"""D04 presentation model and HTML report. Check evidence is never rewritten."""
from collections import Counter
from datetime import datetime
import html
import json
import re

from .review import LABELS

LAYOUT_VERSION = 'dataset-review-layout/2'


def report_content(case, language='zh-CN'):
    en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    label = lambda key: LABELS.get(key, (key, key))[int(en)]
    previous = case.get('previous')
    final = case.get('final')
    summary = case['dataset_summary']
    counts = Counter(r['status'] for r in case['rows'])
    checks = summary.get('status_counts', {})
    # Aliases are local to this report; the complete identifiers remain in its appendix.
    record_ids = sorted({rid for r in case['rows'] + (previous or {}).get('rows', [])
                         for rid in r.get('records', [])})
    aliases = {rid: f'R{i:02}' for i, rid in enumerate(record_ids, 1)}
    def target_name(target):
        return aliases.get(target, target)
    suggestions = {
        'read': t('核对配套文件是否完整，并重新读取该记录。', 'Verify companion files and read the recording again.'),
        'units': t('核对源文件标定与通道表中的物理单位。', 'Reconcile source calibration with the channel-table units.'),
        'rates': t('核对文件头、通道表与配套说明中的采样率。', 'Reconcile sampling rates in the header, channel table and metadata.'),
    }
    priorities = {'needs_fix': 0, 'restricted_use': 1, 'pending': 2, 'follow_up': 3, 'acceptable_difference': 4}
    machine = {'conflict': t('资料不符', 'Mismatch'), 'review': t('待核对', 'Check needed'),
               'unassessed': t('未评', 'Unassessed'), 'pass': t('通过', 'Pass'),
               'not_applicable': t('不适用', 'Not applicable')}
    rows = []
    groups = {}
    for row in sorted(case['rows'], key=lambda r: (r['status'] == 'unassessed', priorities[r['disposition']], r['module'], r['code'], r['target'])):
        d = row.get('decision') or {}
        item = {**row, 'title': row['label_en'] if en else row['label'], 'short_target': target_name(row['target']),
                'machine': machine[row['status']], 'disposition_label': label(row['disposition']),
                'impact': d.get('impact') or t('尚未登记', 'Not recorded'),
                'action': d.get('action') or suggestions.get(row['code'], t('核对来源资料后记录处理意见。', 'Verify the source and record a decision.')),
                'owner': d.get('owner') or t('未指定', 'Unassigned'), 'note': d.get('note') or '',
                'reviewer': d.get('reviewer') or ''}
        rows.append(item)
        # Same labels alone are insufficient: keep different evidence messages and decisions separate.
        key = (row['module'], row['code'], row['status'], row['message'], row['disposition'])
        group = groups.setdefault(key, {'title': item['title'], 'module': row['module'], 'status': row['status'],
              'machine': item['machine'], 'message': row['message'], 'disposition': item['disposition_label'],
              'action': suggestions.get(row['code'], t('核对来源资料后记录处理意见。', 'Verify the source and record a decision.')),
              'rows': []})
        group['rows'].append(item)
    grouped = list(groups.values())
    for index, group in enumerate(grouped, 1):
        group['ref'] = f'F{index:02}'
        group['targets'] = list(dict.fromkeys(r['short_target'] for r in group['rows']))
    conflict = counts['conflict']; review = counts['review']; unknown = counts['unassessed']
    if conflict:
        headline = t(f'发现 {conflict} 项资料不一致', f'{conflict} metadata mismatches found')
        description = t('先核对原始资料，再确认使用范围。', 'Reconcile the source metadata before confirming the intended use.')
    elif review:
        headline = t(f'{review} 项检查需要核对', f'{review} checks need review')
        description = t('请结合原始资料确认检查结果。', 'Review these findings against the source records.')
    elif unknown:
        headline = t(f'{unknown} 项检查尚未评定', f'{unknown} checks remain unassessed')
        description = t('补齐所需信息或确认适用条件后复查。', 'Complete the required information or confirm applicability, then rerun.')
    else:
        headline = t('本次未发现待处理问题', 'No open findings in this run')
        description = t('人工审核结论单独记录。', 'The human review outcome is recorded separately.')
    delta = []
    for r in (previous or {}).get('rows', []):
        if r['change'] != 'unchanged':
            delta.append({**r, 'title': r['label_en'] if en else r['label'], 'short_target': target_name(r['target']),
                          'change_label': label(r['change']), 'before_label': machine.get(r['before'], t('无记录', 'Not recorded')),
                          'after_label': machine.get(r['after'], t('无记录', 'Not recorded'))})
    delta.sort(key=lambda r: ({'resolved': 0, 'new': 1, 'changed': 2}.get(r['change'], 3), r['module'], r['target']))
    stamp = str(case.get('checked_at', ''))
    try:
        parsed = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        offset = parsed.utcoffset()
        stamp = parsed.strftime('%Y-%m-%d %H:%M') + (' UTC' if offset is not None and offset.total_seconds() == 0 else parsed.strftime(' %z').rstrip())
    except ValueError:
        pass
    records = []
    for rid, alias in aliases.items():
        entities = dict(re.findall(r'(?:^|_)(sub|ses|task|acq|run)-([^_]+)', rid))
        records.append({'alias': alias, 'id': rid, 'subject': entities.get('sub', '—'),
                        'context': ' / '.join(entities[k] for k in ('ses', 'task', 'acq', 'run') if k in entities) or rid})
    status_note = t(f"{case['summary']['reviewed']} 项已登记意见，{case['summary']['pending']} 项待处理。",
                    f"{case['summary']['reviewed']} decisions recorded; {case['summary']['pending']} pending.")
    if final:
        status_note = f"{final['reviewer']} · {final['purpose']}"
    return {'title': t('数据集质控报告', 'Dataset quality control report'),
            'subtitle': t('审核与复验', 'Dataset review and retest report'),
            'label': case['label'], 'headline': headline, 'description': description, 'outcome': label(case['outcome']),
            'status_note': status_note, 'rows': rows, 'groups': grouped, 'delta': delta, 'records': records,
            'priority_groups': [g for g in grouped if g['status'] != 'unassessed'],
            'unknown_groups': [g for g in grouped if g['status'] == 'unassessed'],
            'counts': {'conflict': conflict, 'review': review, 'unassessed': unknown, 'pass': checks.get('pass'),
                       'not_applicable': checks.get('not_applicable'), 'total': sum(checks.values()) if checks else None},
            'checked_at': stamp, 'layout_version': LAYOUT_VERSION,
            'demo': t('工程演示 · 公开数据副本', 'Engineering demo · Public-data copy') if case.get('engineering_demo') else '',
            'boundary': t('本报告检查数据资料的一致性与完整性，人工审核仅针对声明范围。工程演示不代表医院验收。',
                          'This report covers dataset metadata consistency and completeness. Human review is scope-specific; an engineering demo is not hospital acceptance.'),
            'count_note': t('数量按检查项统计；同一记录可能对应多项检查。未评不等于不合格。',
                            'Counts refer to checks, not recordings. One recording can have several checks. Unassessed does not mean failed.')}


STYLE = '''
:root{color-scheme:light;--blue:#245cd5;--ink:#152b46;--muted:#65758c;--line:#dce4ee;--pale:#f4f7fc}
*{box-sizing:border-box}body{margin:0;background:#edf1f6;color:var(--ink);font:15px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans CJK SC",sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}button,summary,a{touch-action:manipulation}a:focus-visible,summary:focus-visible{outline:3px solid #9dbaff;outline-offset:4px}
.toolbar{max-width:1120px;margin:auto;padding:20px 28px;display:flex;justify-content:space-between;gap:16px}.download{background:var(--blue);color:white;border-radius:8px;padding:8px 18px;font-weight:600}
.sheet{max-width:1120px;margin:0 auto 40px;background:#fff;border:1px solid var(--line);box-shadow:0 12px 40px #1b33540a;border-radius:12px;overflow:hidden}
.brandline{height:5px;background:var(--blue)}.masthead{padding:28px 44px 0;display:flex;justify-content:space-between;gap:20px;font-size:12px;color:var(--muted);letter-spacing:.05em}.brand{font-weight:750;color:var(--blue);font-size:15px}
.intro{padding:25px 44px 26px}h1{font-size:32px;line-height:1.25;letter-spacing:-.02em;margin:0 0 8px}h2{font-size:21px;line-height:1.4;margin:0}h3{font-size:16px;line-height:1.5;margin:0}p{margin:0 0 8px}.subheading{font-size:14px;color:var(--muted)}.dataset-name{margin:24px 0 12px;font-weight:650;font-size:16px;overflow-wrap:anywhere}
.metadata{display:flex;gap:12px 28px;flex-wrap:wrap;color:var(--muted);font-size:13px}.metadata b{color:var(--ink);font-weight:650;margin-right:5px}.demo{display:inline-block;background:#f1f5fc;color:#496586;padding:4px 9px;border-radius:5px;font-size:11px;letter-spacing:0}
.overview{margin:0 44px 30px;background:#f4f7fd;border:1px solid #dce7fa;border-radius:10px;padding:26px 28px}.headline{font-size:25px;line-height:1.4;font-weight:700;margin:0 0 8px}.review-state{display:flex;align-items:baseline;justify-content:space-between;gap:16px;border-top:1px solid #dce4f2;margin-top:20px;padding-top:14px;font-size:13px}.review-state strong{color:var(--blue)}
.metrics{display:grid;grid-template-columns:repeat(var(--metric-count,3),minmax(0,1fr));gap:20px;margin:24px 0 16px}.metric{border-right:1px solid #dce4f2}.metric:last-child{border:0}.metric b{display:block;font-size:36px;font-weight:650;line-height:1.2;font-variant-numeric:tabular-nums;letter-spacing:-.04em}.metric span{display:block;font-size:12px;margin-top:6px;color:var(--muted)}.metric.warn b{color:#a56223}.metric.pass b{color:#315b92}.metric.unknown b{color:#65758c}
.note{font-size:12px;color:var(--muted);line-height:1.6}.section{padding:30px 44px;border-top:1px solid var(--line)}.section-head{display:flex;gap:14px;align-items:baseline;margin-bottom:18px}.section-no{font-size:13px;color:var(--blue);font-weight:650;font-variant-numeric:tabular-nums}.section-lead{color:var(--muted);font-size:13px;margin:-8px 0 18px}
.priority{display:grid;grid-template-columns:1fr 1fr;gap:16px}.priority article{padding:20px;border:1px solid var(--line);border-left:3px solid #c18b43;border-radius:8px}.priority .target{margin:8px 0 12px}.priority .count{float:right;color:#9b611f;font-size:13px;font-weight:650}.ref{color:var(--muted);font-size:11px;font-variant-numeric:tabular-nums;margin-right:8px}.target{overflow-wrap:anywhere;font-size:12px;color:var(--muted)}.action{font-size:14px}.empty{padding:20px;background:var(--pale);border-radius:8px;color:var(--muted)}
.retest-summary{display:flex;gap:14px 28px;flex-wrap:wrap;padding:16px 20px;background:#f2f7f6;border-radius:8px;font-size:13px;margin-bottom:14px}.retest-summary b{font-size:20px;margin-right:6px;color:#276459}.warning{background:#fff7eb;color:#875a23;padding:12px 16px;border-radius:6px;font-size:13px;margin-bottom:14px}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;text-align:left}th{color:var(--muted);font-weight:550;background:var(--pale);font-size:12px}th,td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}th:first-child,td:first-child{padding-left:12px}.nowrap{white-space:nowrap}.status{display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;background:#f0f3f7;color:#62738a}.status.conflict{color:#955b1e;background:#fff3e1}.status.resolved,.status.pass{color:#276459;background:#edf6f2}
details{border:1px solid var(--line);border-radius:8px;margin-top:12px;overflow:hidden}summary{padding:16px 18px;cursor:pointer;font-size:14px;font-weight:600;list-style-position:inside}summary .note{font-weight:400;margin-left:10px}details[open]>summary{border-bottom:1px solid var(--line);background:#f8fafd}.detail-body{padding:16px 20px}.finding{padding:16px 0;border-bottom:1px solid var(--line)}.finding:last-child{border-bottom:0}.finding-title{display:flex;gap:14px;justify-content:space-between;align-items:baseline;margin-bottom:8px}.finding details{border:0;margin:4px 0}.finding summary{padding:8px 0;font-size:12px;font-weight:450;color:var(--blue)}.finding details[open]>summary{background:none}.finding pre{padding:14px;background:var(--pale);white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.decision{padding:18px 20px;background:#f6f8fc;border-radius:8px;margin-top:16px}.decision dl,.trace{display:grid;grid-template-columns:130px minmax(0,1fr);gap:8px 16px;font-size:13px;margin:12px 0}.decision dt,.trace dt{color:var(--muted)}.decision dd,.trace dd{margin:0;overflow-wrap:anywhere}.footer{padding:22px 44px;border-top:1px solid var(--line);color:var(--muted);font-size:11px}.print-note{display:none}
@media(max-width:720px){.toolbar{padding:15px}.sheet{border-radius:0;border-left:0;border-right:0;margin:0}.masthead,.intro,.section,.footer{padding-left:22px;padding-right:22px}.masthead{align-items:flex-start}.overview{margin-left:22px;margin-right:22px;padding:20px}h1{font-size:27px}.headline{font-size:21px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.metric:nth-child(2){border:0}.metric b{font-size:31px}.priority{grid-template-columns:1fr}.review-state{display:block}.review-state>span{display:block;margin-top:6px}.decision dl,.trace{grid-template-columns:1fr;gap:3px}.decision dd,.trace dd{margin-bottom:8px}.metadata{gap:8px 18px}.section{padding-top:25px;padding-bottom:25px}}
@media print{body{background:white;font-size:11px}.toolbar{display:none}.sheet{max-width:none;box-shadow:none;border:0;margin:0}.masthead,.intro,.section,.footer{padding-left:0;padding-right:0}.overview{margin-left:0;margin-right:0}.section,.overview,.priority article{break-inside:avoid}.section:has(table){break-inside:auto}thead{display:table-header-group}tr{break-inside:avoid}.print-note{display:block}.brandline{height:3px}}
'''


def render_review_report(case, language='zh-CN'):
    c = report_content(case, language); en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    e = lambda value: html.escape(str(value), quote=True)
    number = lambda value: '—' if value is None else str(value)
    base = '/api/v1/package-jobs/' + case['job_id'] + '/review'
    ds = case['dataset_summary']; counts = c['counts']; prev = case.get('previous')
    def section(number, title, body, lead=''):
        return f'<section class="section"><div class="section-head"><span class="section-no">{number}</span><h2>{e(title)}</h2></div>' + (f'<p class="section-lead">{e(lead)}</p>' if lead else '') + body + '</section>'
    def table(headers, rows):
        return '<div class="table-scroll"><table><thead><tr>' + ''.join(f'<th>{e(h)}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows) + '</tbody></table></div>'
    metadata = ''.join(f'<span><b>{e(number(ds.get(key)))}</b>{e(name)}</span>' for key, name in [
        ('subjects', t('个体', 'subjects')), ('records', t('份记录', 'recordings')), ('groups', t('比较组', 'comparison groups'))])
    if 'expected_files' in ds:
        metadata += f'<span><b>{e(number(ds.get("present_files")))}/{e(ds["expected_files"])}</b>{t("文件已找到","files present")}</span>'
    metrics = [(counts['conflict'], t('资料不符', 'Mismatches'), 'warn'),
               (counts['unassessed'], t('未评', 'Unassessed'), 'unknown'), (counts['pass'], t('检查通过', 'Checks passed'), 'pass')]
    if counts['review']:
        metrics.insert(1,(counts['review'],t('待核对', 'Check needed'),'warn'))
    metrics_html = ''.join(f'<div class="metric {tone}"><b>{e(number(v))}</b><span>{e(name)}</span></div>' for v,name,tone in metrics)
    priorities = ''.join(f'<article><span class="count">{len(g["rows"])} {t("项","checks")}</span><h3><span class="ref">{g["ref"]}</span>{e(g["title"])}</h3><p class="target">{e(", ".join(g["targets"]))}</p><p class="action">{e(g["action"])}</p></article>' for g in c['priority_groups'])
    priority_section = section('01', t('优先核对', 'Priority checks'), '<div class="priority">'+priorities+'</div>' if priorities else '<p class="empty">'+t('本次没有资料不符或待核对项。','No metadata mismatches or review flags in this run.')+'</p>', t('同类发现合并展示；编号可在下方明细中定位。','Similar findings are grouped. References link them to the detailed register.'))
    retest = ''
    if prev:
        stats = ''.join(f'<span><b>{v}</b>{e(LABELS[k][int(en)])}</span>' for k,v in prev['counts'].items())
        warning = '' if prev.get('compatible') else '<p class="warning">'+t('比较范围或规则已改变，不能据此认定问题消除。','Scope or rules changed. This comparison cannot establish resolution.')+'</p>'
        changes = table([t('检查项','Check'),t('对象','Target'),t('复验变化','Change'),t('前后状态','Before / after')], [
            [e(r['title']), e(r['short_target']), f'<span class="status {e(r["change"])}">{e(r["change_label"])}</span>', e(r['before_label']+' → '+r['after_label'])] for r in c['delta']])
        retest = section('02', t('复验结果', 'Retest results'), warning+'<div class="retest-summary">'+stats+'</div>'+changes+'<p class="note" style="margin-top:12px">'+t('仅列出变化项。范围改变或未复查，不计为问题消除。','Only changed items are listed. Changed scope or omitted checks do not count as resolved.')+'</p>')
    sections = []
    for title, groups in [(t('资料不符与待核对', 'Mismatches and review flags'), c['priority_groups']), (t('未评项目', 'Unassessed checks'), c['unknown_groups'])]:
        details = []
        for g in groups:
            children = []
            for r in g['rows']:
                decision = ''
                if r['decision']:
                    decision = '<div class="decision"><dl>'+''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k,v in [
                        (t('影响 / 用途','Impact / use'),r['impact']), (t('下一步','Next step'),r['action']), (t('负责人','Owner'),r['owner']),
                        (t('处理依据','Decision basis'),r['note']), (t('审核人','Reviewer'),r['reviewer'])])+'</dl></div>'
                evidence = e(json.dumps(r.get('observed'), ensure_ascii=False, indent=2))
                children.append(f'<article class="finding"><div class="finding-title"><strong>{e(r["short_target"])}</strong><span class="status">{e(r["disposition_label"])}</span></div>{decision}<details><summary>{t("查看原始证据","Source evidence")}</summary><p>{e(r["message"])}</p><p class="target">{e(r["target"])}</p><p class="target">{e("; ".join(r.get("files",[])))}</p><pre>{evidence}</pre><p class="note">{e(r["id"])}</p></details></article>')
            details.append(f'<details><summary><span class="ref">{g["ref"]}</span>{e(g["title"])}<span class="note">{len(g["rows"])} {t("项","checks")} · {e(g["machine"])}</span></summary><div class="detail-body"><p class="note">{e(g["message"])}</p>{"".join(children)}</div></details>')
        if groups:
            sections.append('<h3>'+e(title)+'</h3>'+''.join(details))
    register = section('03' if prev else '02', t('检查明细', 'Finding register'), '<div style="display:grid;gap:22px">'+''.join('<div>'+s+'</div>' for s in sections)+'</div>' if sections else '<p class="empty">'+t('没有待处理发现。','No open findings.')+'</p>', t('按问题类型展开，查看涉及记录、处理意见与原始证据。','Expand a finding type to see affected records, decisions and source evidence.'))
    record_table = table([t('简称','Alias'),t('个体','Subject'),t('完整记录标识','Full recording identifier')], [[e(r['alias']),e(r['subject']),'<span class="target">'+e(r['id'])+'</span>'] for r in c['records']])
    trace_items = [(t('检查时间','Checked at'),c['checked_at']), (t('审核状态','Review outcome'),c['outcome']),
                  (t('规则 / 审核版本','Rules / review revision'),f'{case["rule_version"]} / r{case["revision"]}'),
                  (t('运行编号','Run ID'),case['job_id']), (t('结果指纹','Result fingerprint'),case['result_hash']),
                  (t('报告版式','Report layout'),LAYOUT_VERSION)]
    trace = '<dl class="trace">'+''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k,v in trace_items)+'</dl>'
    history = ''.join(f'<li>r{r["revision"]} · {e(r["reviewer"])} · {e(r["recorded_at"])}</li>' for r in case.get('history', []))
    appendix = section('04' if prev else '03', t('范围与追溯', 'Scope and traceability'), '<p>'+e(case['scope'])+'</p>'+trace+
                       '<details><summary>'+t('记录标识对照','Recording identifiers')+'</summary>'+record_table+'</details>'+
                       '<details><summary>'+t('审核历史','Review history')+'</summary><div class="detail-body">'+('<ul>'+history+'</ul>' if history else t('尚未登记人工审核记录。','No human review entries recorded.'))+'</div></details>')
    demo = '<span class="demo">'+e(c['demo'])+'</span>' if c['demo'] else ''
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(c['title'])}</title><style>{STYLE}</style></head><body>
<nav class="toolbar" aria-label="{t('报告导航','Report navigation')}"><a href="/datasets?job={e(case['job_id'])}&tab=review">← {t('返回质控台','Back to workbench')}</a><a class="download" href="{base}/pdf?lang={language}">{t('下载 PDF','Download PDF')}</a></nav>
<main class="sheet"><div class="brandline"></div><header class="masthead"><span class="brand">DBCI-QC</span>{demo}</header><div class="intro"><h1>{e(c['title'])}</h1><p class="subheading">{e(c['subtitle'])} · {e(c['checked_at'])}</p><p class="dataset-name">{e(c['label'])}</p><div class="metadata">{metadata}</div></div>
<section class="overview" aria-label="{t('结果概览','Result overview')}"><p class="headline">{e(c['headline'])}</p><p class="subheading">{e(c['description'])}</p><div class="metrics" style="--metric-count:{len(metrics)}">{metrics_html}</div><p class="note">{e(c['count_note'])}</p><div class="review-state"><strong>{t('人工审核','Human review')} · {e(c['outcome'])}</strong><span>{e(c['status_note'])}</span></div></section>
{priority_section}{retest}{register}{appendix}<footer class="footer">{e(c['boundary'])}</footer></main></body></html>'''


def review_pdf(case, language='zh-CN'):
    from .review_report_pdf import render_pdf
    return render_pdf(case, report_content(case, language), language)
