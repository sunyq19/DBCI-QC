"""Small HTTP adapter for batch execution and saved-report comparisons."""
import html
import json
import re
from urllib.parse import parse_qs, urlsplit
from ephys_qc.comparison import comparison_row, compare


def build_comparison(store, ids):
    if not 2 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(not re.fullmatch('[a-f0-9]{32}', i) for i in ids):
        raise ValueError('请选择 2–100 份不同的已完成报告。')
    rows = []
    for identifier in ids:
        job = store.job(identifier)
        result = store.result(identifier, compact=True)
        view = result.get('report_view')
        if not view:
            raise ValueError('当前分项比较仅支持 EEG 报告。')
        root = store.root / 'jobs' / identifier
        request = json.loads((root / 'request.json').read_text())
        environments = []
        for a in result.get('artifacts', []):
            name = a['name']
            if name == 'environment.json' or re.fullmatch('w[0-9]+--environment.json', name):
                path = root / 'artifacts' / name
                if path.is_file():
                    environments.append(json.loads(path.read_text()))
        rows.append(comparison_row(job, request, view, environments))
    return compare(rows)


def render_comparison(data, language='zh-CN'):
    e = html.escape
    en = language == 'en'
    t = lambda zh, english: english if en else zh
    def number(value):
        return t('未评', 'Unassessed') if value is None else f'{value:.2f}'
    sections = []
    for i, group in enumerate(data['groups'], 1):
        heading = t('同条件比较','Matched conditions') if group['comparable'] else t('单独展示 · 条件未齐或尚无同组报告','Separate results · unmatched or incomplete conditions')
        rows = []
        for row in group['rows']:
            parts = {c['id']: c for c in row['components']}
            cells = []
            for key in ('integrity', 'line_noise', 'hf_burst'):
                c = parts.get(key, {})
                amount = c['denominator'] - c['numerator'] if c.get('denominator') is not None and c.get('numerator') is not None else None
                cells.append(f'<td><b>{number(c.get("value"))}</b><small>{t("候选量 / 有效量","Candidate / assessed amount")} {number(amount)} / {number(c.get("denominator"))} {e(c.get("unit") or "")}</small></td>')
            rows.append(f'<tr><td><a href="{e(row["report_url"])}">{e(row["label"])}</a><small>{e(t("；".join(row["unknown"]), "Required conditions unconfirmed" if row["unknown"] else ""))}</small></td>{"".join(cells)}<td>{number(row["score"])}<small>{e(row["score_version"] or "无评分版本")}</small></td></tr>')
        condition = json.dumps(group['conditions'], ensure_ascii=False, indent=2)
        sections.append(f'<section class="panel"><h2>{i}. {heading}</h2><div class="table-scroll"><table><thead><tr><th>{t("记录","Recording")}</th><th>{t("完整性","Integrity")}</th><th>{t("工频","Line noise")}</th><th>{t("高频突发","HF bursts")}</th><th>{t("试行总分","Trial total")}</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div><details><summary>{t("比较条件与版本","Conditions and versions")}</summary><pre>{e(condition)}</pre></details></section>')
    page = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>报告比较 · 质控台</title><link rel="stylesheet" href="/styles.css"><style>main{max-width:1200px;margin:30px auto;padding:24px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:16px;border-bottom:1px solid #dee7f3}small{display:block;color:#687b92;font-size:12px;margin-top:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}.table-scroll{overflow:auto}</style><main><a href="/">← 返回质控台</a><h1>报告比较</h1><p>'+e(data['interpretation'])+'</p>'+''.join(sections)+'</main></html>'
    if en:
        page=page.replace('lang="zh-CN"','lang="en"').replace('报告比较','Report comparison').replace('质控台','QC Workbench').replace('← 返回','← Back to ').replace(e(data['interpretation']), 'Project trial metrics under matched conditions only. Missing results stay unassessed. No cross-group ranking.')
    return page


def dispatch(handler, path):
    if not (path.startswith('/api/v1/batch') or path in {'/comparisons', '/api/v1/comparisons'}):
        return False
    store = handler.store
    if handler.command == 'POST':
        if path == '/api/v1/batch-previews':
            handler.json(store.batches.preview(handler.body()), 201); return True
        if path == '/api/v1/batches':
            handler.json(store.batches.submit(handler.body()), 202); return True
        match = re.fullmatch(r'/api/v1/batches/([a-f0-9]{32})/cancel', path)
        if match:
            handler.body(); handler.json(store.batches.cancel(match[1])); return True
    if handler.command == 'GET':
        query = parse_qs(urlsplit(handler.path).query)
        if path == '/api/v1/batches':
            if set(query) - {'package'}: raise ValueError('批次参数无效。')
            handler.json({'batches': store.batches.catalog(query.get('package', [None])[0])}); return True
        match = re.fullmatch(r'/api/v1/batches/([a-f0-9]{32})', path)
        if match:
            handler.json(store.batches.get(match[1])); return True
        if path in {'/comparisons', '/api/v1/comparisons'}:
            if 'jobs' not in query or set(query) - {'jobs','lang'} or len(query['jobs']) != 1: raise ValueError('请选择报告。')
            data = build_comparison(store, query['jobs'][0].split(','))
            if path.startswith('/api'): handler.json(data)
            else: handler.send_bytes(render_comparison(data, query.get('lang',['zh-CN'])[0]).encode(), 'text/html; charset=utf-8')
            return True
    return False
