"""Compact, actionable presentation of saved findings. No score computation."""
from html import escape
import math
import re


def focus_targets(view):
    """Bounded examples with recorded identities and times, never guessed indices."""
    targets = []
    for row in view.get('line_channels', [])[:5]:
        c = row.get('example') or {}
        targets.append(dict(c, channel_id=row.get('channel_id'), channel_name=row.get('name'),
                            kind='line', label='工频干扰',
                            finding=f'{row.get("percent", 0):.1f}% 检查窗命中'))
    for row in view.get('hf_candidates', [])[:5]:
        targets.append(dict(row, kind='hf', label='高频突发', finding='短时高频活动'))
    valid = []
    for row in targets:
        a, b = row.get('start_seconds'), row.get('stop_seconds')
        if row.get('channel_id') and all(isinstance(n, (int, float)) and math.isfinite(n) for n in (a,b)) and b>a:
            valid.append(row)
    return valid


def focused_figure(view, workspace, index):
    from .report_export import evidence_figure
    rows = focus_targets(view)
    if not 0 <= index < len(rows):
        raise KeyError('Unknown finding')
    c = rows[index]
    # Reuse the source-verified bounded reader with exactly this selected finding.
    selected = dict(view, hf_candidates=[], line_channels=[])
    if c['kind'] == 'hf':
        selected['hf_candidates'] = [c]
    else:
        selected['line_channels'] = [dict(channel_id=c['channel_id'], name=c['channel_name'], example=c)]
    return evidence_figure(selected, workspace)


def compact_report(report, view, *, focus_url=None, visualization_url=None):
    """Reorganize renderer-owned sections; technical details remain downloadable."""
    def section(identifier):
        return re.search(r'<section id="'+identifier+r'">(.*?)</section>', report, re.S).group(1)
    esc = lambda v: escape(str(v), quote=True)
    num = lambda v: '—' if v is None else f'{v:g}'
    points = lambda v: '—' if v is None else f'{v:.2f}'
    header = re.search(r'<header id="overview">(.*?)</header>', report, re.S).group(1)
    headline = re.search(r'<h1>(.*?)</h1>', header, re.S).group(1)
    conclusion = re.search(r'<h1>.*?</h1><p>(.*?)</p>', header, re.S).group(1)
    actions = ''.join(re.findall(r'<a class="tag".*?</a>', header))
    facts = re.search(r'<div class="facts">(.*?)</div>', header, re.S).group(1)
    scope = re.search(r'<p class="scope">([^<]*检查[^<]*)</p>', header)
    failures = ''.join(re.findall(r'<p class="failure">.*?</p>', header, re.S))
    score = view['score']
    from .report_export import score_composition
    version_label='项目自定义 v'+score['version'].split('/')[-1] if score['version'].startswith('project-weighted/') else '项目试行 v'+score['version'].split('/')[-1]
    route = '灵犀云扩展方案' if any(p['id'].startswith('gnosis_') for p in score['components']) else '基础检查方案'
    overview = f'''<header id="overview" class="report-overview"><div class="report-title"><div><p class="eyebrow">{route}</p><h1>信号质量报告</h1><p class="filename">{esc(view['label'])}</p></div><div class="report-actions">{actions}</div></div>
<div class="report-summary"><div class="report-total"><span>综合分</span><strong>{points(score['value'])}<small> / 100</small></strong><span>{esc(score_composition(score))}</span></div><div class="report-conclusion"><h2>{headline}</h2><p>{conclusion}</p>{failures}</div></div><div class="facts">{facts}{'<span>'+scope[1]+'</span>' if scope else ''}</div></header>'''
    checks = section('score-table')
    # Put channel/time drill-downs in the detail section, after the actionable findings.
    extra = ''
    marker = '<details><summary>按通道'
    if marker in checks:
        at = checks.index(marker); extra, checks = checks[at:], checks[:at]
    original_review = section('review')
    # The old evidence panel is superseded by per-finding waveforms.
    original_review = re.sub(r'<h3>对应候选波形</h3>.*?</p>', '', original_review, flags=re.S)
    original_review = original_review.replace('<h2>重点复核</h2>', '')
    targets = focus_targets(view)
    rows = []
    for i,c in enumerate(targets):
        title = f'{c["channel_name"]} · {c["label"]} · {c["start_seconds"]:g}–{c["stop_seconds"]:g} 秒'
        button = (f'<a class="finding-action" href="{esc(focus_url(i))}" data-finding="{i}" data-title="{esc(title)}" aria-controls="finding-preview">查看波形</a>' if focus_url else '')
        rows.append(f'<tr><th>{esc(c["channel_name"])}</th><td>{esc(c["label"])}<small>{esc(c["finding"])}</small></td><td>{c["start_seconds"]:g}–{c["stop_seconds"]:g} s</td><td>{button}</td></tr>')
    preview = ''
    if rows and focus_url:
        c=targets[0];title=f'{c["channel_name"]} · {c["label"]} · {c["start_seconds"]:g}–{c["stop_seconds"]:g} 秒'
        preview=f'<div class="finding-preview" id="finding-preview"><div class="figure-heading"><h3 id="finding-title">{esc(title)}</h3><span>阴影标出待复核区间</span></div><img id="finding-image" src="{esc(focus_url(0))}" alt="{esc(title)}"><p id="finding-status" role="status" aria-live="polite"></p></div>'
    locator = ('<p class="muted">点击“查看波形”定位下列区间。工频列出代表窗口，高频列出候选片段。</p><div class="table-wrap"><table class="finding-table"><thead><tr><th>通道</th><th>检查发现</th><th>记录时间</th><th></th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'+preview if rows else '<p>本次没有带通道和时间位置的候选。其他测量见检查结果。</p>')
    if '灵犀' in route:
        locator='<p class="muted">以下为共同基础检查定位。灵犀云异常区间见下方图表。</p>'+locator
    review = f'<section id="review"><h2>问题定位</h2>{locator}<details><summary>完整候选列表与测量</summary>{original_review}</details>{extra}</section>'
    charts = ''
    if visualization_url:
        links=[('viz_interference','工频分布','哪些通道受到影响'),('viz_timeline','异常时间轴','异常集中在哪些时段'),('viz_psd','频谱对照','查看各通道的频率能量')]
        artifacts=view.get('artifacts',[])
        links=[link for link in links if any(name.endswith('M04_spectral.json') for name in artifacts) if link[0]!='viz_timeline'] + ([links[1]] if any(name.endswith('M06_muscle.json') or name.endswith('M06_gnosis_artifact.json') for name in artifacts) else [])
        charts='<section id="charts"><h2>图表分析</h2><div class="report-chart-links">'+''.join(f'<a href="{esc(visualization_url)}#{key}"><strong>{title}</strong><span>{hint}</span></a>' for key,title,hint in links)+'</div></section>'
    details=f'<section id="checks"><h2>方法与依据</h2><details><summary>执行项目与说明</summary>{section("checks").replace("<h2>方法与检查明细</h2>","")}</details><details id="scoring"><summary>评分组成与计算方法</summary><p>{esc(version_label)}</p>{section("scoring")}</details></section>'
    aside='<aside><strong>质控报告</strong><nav><a href="#overview">报告概览</a><a href="#score-table">检查结果</a><a href="#review">问题定位</a>'+('<a href="#charts">图表分析</a>' if charts else '')+'<a href="#checks">方法与依据</a><a href="/standards/eeg-report">质控标准</a></nav></aside>'
    body=f'<div class="shell">{aside}<main>{overview}<section id="score-table">{checks}</section>{review}{charts}{details}<footer>DBCI-QC · 项目检查结果，候选需复核</footer></main></div>'
    head=report[:report.index('</head>')]
    return head+f'<style>{CSS}</style><script src="/report-interactions.js" defer></script></head><body>{body}</body></html>'


CSS='''
html{scrollbar-gutter:stable;scroll-behavior:auto}body{background:#fff;font:14px/1.6 var(--font-ui,system-ui,sans-serif);color:#243449}
.shell{grid-template-columns:148px minmax(0,1fr);max-width:1280px;padding:24px 28px;gap:28px}
main{min-width:0}aside strong{font-size:16px}aside nav{gap:12px;font-size:13px;margin-top:18px}
header,section{border:0;border-radius:0;padding:0 0 18px;margin:0 0 18px;border-bottom:1px solid #dfe5ed}
h1{font-size:22px;margin:0}h2{font-size:16px;margin:0 0 10px}h3{font-size:14px;margin:0}p{margin:6px 0}
.report-title{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}.eyebrow{font-size:12px;color:#5b687b;margin:0 0 4px}
.report-actions{display:flex;gap:8px;flex-wrap:wrap;flex:none}.report-actions .tag{border:1px solid #ccd2da;border-radius:4px;background:#fff;padding:5px 10px;margin:0;font-size:13px}
.report-summary{display:grid;grid-template-columns:180px minmax(0,1fr);gap:20px;margin:16px 0;align-items:center}
.report-total{border-right:1px solid #dfe5ed;padding-right:16px}.report-total>span{display:block;font-size:12px;color:#5b687b}.report-total strong{font-size:32px;font-weight:600;color:#2459bc;line-height:1.4}.report-total small{font-size:13px;font-weight:400;color:#5b687b}
.report-conclusion{border:0;background:none;padding:0;margin:0}.report-conclusion h2{margin:0 0 6px}.report-conclusion p{font-size:13px}
.facts{margin:0;padding-top:10px;gap:5px 18px;font-size:12px}.filename{margin-top:4px;font-size:13px}
table{table-layout:fixed;font-size:13px;min-width:480px}th,td{padding:9px 10px;overflow-wrap:anywhere}th{font-weight:500}thead th{background:#f5f7fa;font-size:12px}td small{display:block;font-size:12px}
.result-points{font-size:16px}.table-wrap{max-width:100%;overflow-x:auto;scrollbar-width:thin}.finding-table th:first-child{width:16%}.finding-table td:nth-child(2){width:40%}.finding-table td:last-child{width:90px;text-align:right}
.finding-table tr.is-selected{background:#eef3fb}.finding-action{white-space:nowrap}.finding-preview{border:1px solid #dfe5ed;padding:12px;margin-top:12px;background:#fff;scroll-margin-top:20px}.figure-heading{display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:8px}.figure-heading span{font-size:12px;color:#5b687b}.finding-preview img{display:block;width:100%;height:auto;min-height:120px;aspect-ratio:100/21;object-fit:contain}.finding-preview p:empty{display:none}.finding-preview p{font-size:12px;color:#5b687b}
.report-chart-links{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.report-chart-links a{border:1px solid #dfe5ed;padding:10px 12px;border-radius:4px;display:grid;gap:2px}.report-chart-links a:hover{background:#eef3fb;text-decoration:none}.report-chart-links strong{font-size:13px;font-weight:500}.report-chart-links span{font-size:12px;color:#5b687b}
details{margin-top:10px;padding-top:10px}summary{font-size:13px}section>p.muted{font-size:12px;margin:0 0 10px}.scope,.footnote{font-size:12px}pre{font-size:12px}.failure{font-size:13px;padding:8px 10px}footer{font-size:12px;margin-top:12px}section[id],details[id]{scroll-margin-top:20px}
@media(max-width:900px){.shell{display:block;padding:18px 16px}.shell aside{margin-bottom:18px}.shell aside nav{display:flex;flex-wrap:wrap;margin-top:8px;gap:8px 16px}.report-title{flex-wrap:wrap}}
@media(max-width:600px){.report-summary{grid-template-columns:1fr;gap:12px}.report-total{border:0}.report-chart-links{grid-template-columns:1fr}.finding-preview img{min-height:80px}}
@media print{.report-actions,aside,.finding-action,script{display:none}.shell{display:block;max-width:none;padding:0}details>summary{color:#243449}.report-summary{grid-template-columns:180px 1fr}.finding-preview{break-inside:avoid}}
'''
