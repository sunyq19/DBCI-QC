"""Compact, actionable presentation of saved findings. No score computation."""
from html import escape
import math
import re
from urllib.parse import urlencode


def report_section(identifier, title, content, *, opened=False, extra_class='', attributes=''):
    """One heading/disclosure pattern for every top-level report section."""
    classes='report-section'+(' '+extra_class if extra_class else '')
    return (f'<details id="{identifier}" class="{classes}"{" open" if opened else ""}{attributes}>'
            f'<summary><h2>{escape(title)}</h2></summary><div class="report-section-body">{content}</div></details>')


def inline_charts(url, *, english=False):
    """A report section; figures load only when this section is expanded."""
    src=url+('&' if '?' in url else '?')+urlencode({'embedded':'1'})
    title='Charts' if english else '图表分析'
    loading='Loading charts…' if english else '正在载入图表…'
    content=f'<p data-chart-status role="status">{loading}</p><iframe data-chart-src="{escape(src,quote=True)}" title="{title}" class="report-chart-frame" scrolling="no"></iframe>'
    return report_section('charts',title,content,extra_class='report-chart-section',attributes=' data-report-charts')


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
    return evidence_figure(selected, workspace, compact=True)


def waveform_controls():
    return '''<div id="wave-controls" hidden>
<div class="wave-toolbar"><div class="wave-time-controls"><button type="button" id="wave-prev" aria-label="向前查看" title="向前查看（左方向键）">‹</button><div class="wave-zoom" role="group" aria-label="时间缩放"><button type="button" id="wave-zoom-out" aria-label="缩小，查看更多时间" title="缩小，查看更多时间">−</button><output id="wave-span" aria-label="显示时长">10 s</output><button type="button" id="wave-zoom-in" aria-label="放大，查看细节" title="放大，查看细节">+</button></div><button type="button" id="wave-next" aria-label="向后查看" title="向后查看（右方向键）">›</button><button type="button" id="wave-reset">回到候选</button></div>
<div class="wave-channel-picker"><button type="button" id="wave-channels-toggle" aria-expanded="false" aria-controls="wave-channel-menu">对照通道 <span id="wave-channel-count">1 / 15</span></button><div id="wave-channel-menu" hidden><label for="wave-search">选择对照通道 · 最多 15 道</label><input id="wave-search" type="search" placeholder="搜索通道" autocomplete="off"><div id="wave-channel-options"></div></div></div></div>
<div class="wave-navigator"><div class="wave-navigation-labels"><span id="wave-range"></span><span class="wave-gesture-hint">拖动查看 · 滚轮缩放</span></div><div class="wave-timeline"><span id="wave-segment-start"></span><input type="range" id="wave-position" min="0" max="1" step="0.001" value="0" aria-label="拖动查看前后时间"><span id="wave-segment-end"></span></div></div></div>
<p id="wave-notice" class="wave-notice" role="status" hidden></p>'''


def location_inspector(base, fallback='', *, english=False):
    """One async location workspace for every modality; sources stay on disk."""
    esc = lambda v: escape(str(v), quote=True)
    if not fallback:
        fallback = ('<div class="finding-workspace"><div class="finding-sidebar">'
            '<div class="finding-list-label">候选位置</div><div class="finding-list" role="region" aria-label="候选位置列表"></div></div>'
            f'<div class="finding-preview" id="finding-preview" data-waveform-base="{esc(base)}" data-state="ready">'
            '<div class="figure-heading"><h3 id="finding-title">选择检查位置</h3><span id="finding-position"></span></div>'
            '<p id="finding-measure"></p>'+waveform_controls()+
            '<div class="finding-stage"><img id="finding-image" hidden alt=""><p id="finding-status" role="status"></p></div>'
            '<p class="finding-caption"></p></div></div>')
    html = ('<div class="finding-inspector"><button type="button" id="finding-fullscreen" class="finding-fullscreen" aria-pressed="false" title="全屏查看问题定位"><svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M7 3H3v4m10-4h4v4M3 13v4h4m10-4v4h-4"/></svg><span>全屏</span></button><div id="finding-filters" class="finding-filters" aria-label="检查项筛选">'
            '<span role="status">正在载入检查位置…</span></div>'
            '<p id="finding-index-notice" class="finding-index-notice" role="status" hidden></p>'+fallback+'</div>')
    if english:
        for zh, en in {
            '全屏查看问题定位':'Expand review locations', '全屏':'Full screen',
            '正在载入检查位置…':'Loading check locations…', '检查项筛选':'Filter checks',
            '候选位置列表':'Candidate locations', '候选位置':'Locations', '选择检查位置':'Select a location',
            '向前查看（左方向键）':'Previous interval (left arrow)', '向后查看（右方向键）':'Next interval (right arrow)',
            '向前查看':'Previous interval', '向后查看':'Next interval', '时间缩放':'Time zoom',
            '缩小，查看更多时间':'Zoom out', '放大，查看细节':'Zoom in', '显示时长':'Visible duration',
            '回到候选':'Return to candidate', '选择对照通道 · 最多 15 道':'Compare up to 15 channels',
            '对照通道':'Compare channels', '搜索通道':'Search channels',
            '拖动查看前后时间':'Drag to pan', '拖动查看 · 滚轮缩放':'Drag to pan · scroll to zoom',
        }.items(): html=html.replace(zh,en)
    return html



def compact_report(report, view, *, focus_url=None, visualization_url=None, waveform_url=None):
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
    if visualization_url:
        actions=actions.replace(f'href="{esc(visualization_url)}"','href="#charts"')
    facts = re.search(r'<div class="facts">(.*?)</div>', header, re.S).group(1)
    scope = re.search(r'<p class="scope">([^<]*检查[^<]*)</p>', header)
    failures = ''.join(re.findall(r'<p class="failure">.*?</p>', header, re.S))
    score = view['score']
    version_label='项目自定义 v'+score['version'].split('/')[-1] if score['version'].startswith('project-weighted/') else '项目试行 v'+score['version'].split('/')[-1]
    route = '灵犀云扩展方案' if any(p['id'].startswith('gnosis_') for p in score['components']) else '基础检查方案'
    overview = f'''<header id="overview" class="report-overview"><div class="report-title"><div><p class="eyebrow">{route}</p><h1>{esc(view.get('run_name') or '信号质量报告')}</h1><p class="filename">{esc(view['label'])}</p></div><div class="report-actions">{actions}</div></div>
<div class="report-summary"><div class="report-total"><span>综合分</span><strong>{points(score['value'])}<small> / 100</small></strong></div><div class="report-conclusion"><h2>{headline}</h2><p>{conclusion}</p>{failures}</div></div><div class="facts">{facts}{'<span>'+scope[1]+'</span>' if scope else ''}</div></header>'''
    from .report_export import exclusion_note
    if exclusion_note(score):
        overview=overview.replace('</header>', '<p class="muted">'+esc(exclusion_note(score))+'</p></header>')
    checks = section('score-table')
    # Put channel/time drill-downs in the detail section, after the actionable findings.
    extra = ''
    marker = '<!-- score-supplemental -->'
    if marker in checks:
        at = checks.index(marker); extra, checks = checks[at:], checks[:at]
    checks=re.sub(r'<h2>.*?</h2>','',checks,count=1,flags=re.S)
    original_review = section('review')
    # The old evidence panel is superseded by per-finding waveforms.
    original_review = re.sub(r'<h3>对应候选波形</h3>.*?</p>', '', original_review, flags=re.S)
    original_review = original_review.replace('<h2>重点复核</h2>', '')
    targets = focus_targets(view)
    rows = []
    for i,c in enumerate(targets):
        title = f'{c["channel_name"]} · {c["label"]} · {c["start_seconds"]:g}–{c["stop_seconds"]:g} 秒'
        measure = c['finding'] + (' · 代表窗口' if c['kind'] == 'line' else ' · 候选片段')
        contents=f'<span class="finding-item-top"><strong>{esc(c["channel_name"])}</strong><span>{c["start_seconds"]:g}–{c["stop_seconds"]:g} 秒</span></span><small>{esc(c["finding"])}</small>'
        if i == 0 or c['kind'] != targets[i-1]['kind']:
            rows.append(f'<div class="finding-group-label">{esc(c["label"])}</div>')
        rows.append((f'<a class="finding-item" href="{esc(focus_url(i))}" data-finding="{i}" data-channel-id="{esc(c["channel_id"])}" data-start="{c["start_seconds"]:g}" data-stop="{c["stop_seconds"]:g}" data-title="{esc(title)}" data-measure="{esc(measure)}" data-position="{i+1} / {len(targets)}" aria-controls="finding-preview" aria-current="{str(i == 0).lower()}" aria-label="{esc(title)}">{contents}</a>' if focus_url else f'<div class="finding-item">{contents}</div>'))
    preview = ''
    if rows and focus_url:
        c=targets[0];title=f'{c["channel_name"]} · {c["label"]} · {c["start_seconds"]:g}–{c["stop_seconds"]:g} 秒'
        measure = c['finding'] + (' · 代表窗口' if c['kind'] == 'line' else ' · 候选片段')
        preview=f'<div class="finding-preview" id="finding-preview" data-state="ready" aria-busy="false"><div class="figure-heading"><h3 id="finding-title">{esc(title)}</h3><span id="finding-position">1 / {len(targets)}</span></div><p id="finding-measure">{esc(measure)}</p><div class="finding-stage"><img id="finding-image" src="{esc(focus_url(0))}" alt="{esc(title)}"><p id="finding-status" role="status" aria-live="polite"></p></div><p class="finding-caption"><span class="candidate-swatch" aria-hidden="true"></span>候选区间<span>原始记录时间（秒）</span></p></div>'
        if waveform_url:
            preview=preview.replace('id="finding-preview"',f'id="finding-preview" data-waveform-base="{esc(waveform_url)}"')
            preview=preview.replace('<div class="finding-stage">',waveform_controls()+'<div class="finding-stage">')
    locator = ('<div class="finding-workspace"><div class="finding-sidebar"><div class="finding-list-label">候选位置<span>点击切换波形</span></div><div class="finding-list" role="region" aria-label="候选位置列表" tabindex="0">'+''.join(rows)+'</div></div>'+preview+'</div>' if rows else '<p>本次没有带通道和时间位置的候选。其他测量见检查结果。</p>')

    if waveform_url:
        locator=location_inspector(waveform_url, locator if rows else '')
    review = report_section('review','问题定位',locator,opened=True)
    charts = ''
    if visualization_url:
        charts=inline_charts(visualization_url)
    scoring=re.sub(r'<h2>.*?</h2>','',section('scoring'),count=1,flags=re.S)
    detail_body=f'<div class="report-details-body"><div class="report-detail-group"><h3>结果明细</h3><details><summary>完整候选列表</summary>{original_review}</details>{extra}</div><div class="report-detail-group"><h3>检查依据</h3><details><summary>执行项目与说明</summary>{section("checks").replace("<h2>方法与检查明细</h2>","")}</details><details id="scoring"><summary>评分组成与计算方法</summary><p>{esc(version_label)}</p>{scoring}</details><div id="report-archive-slot"></div></div></div>'
    details=report_section('checks','报告详情',detail_body,extra_class='report-details-section')
    aside='<aside><strong>质控报告</strong><nav><a href="#overview">报告概览</a><a href="#score-table">检查结果</a><a href="#review">问题定位</a>'+('<a href="#charts">图表分析</a>' if charts else '')+'<a href="#checks">报告详情</a><a href="/standards/eeg-report">质控标准</a></nav></aside>'
    results=report_section('score-table','检查结果',checks,opened=True)
    body=f'<div class="shell">{aside}<main>{overview}{results}{review}{charts}{details}<footer>DBCI-QC · 项目检查结果，候选需复核</footer></main></div>'
    head=report[:report.index('</head>')]
    explorer = '<link rel="stylesheet" href="/waveform-explorer.css"><script src="/waveform-explorer.js" defer></script>' if waveform_url else ''
    return head+f'<style>{CSS}</style><script src="/report-interactions.js" defer></script>{explorer}</head><body>{body}</body></html>'


CSS = """
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
.result-points{font-size:16px}.table-wrap{max-width:100%;overflow-x:auto;scrollbar-width:thin}
#score-table .table-wrap>table th:first-child{width:22%}#score-table .table-wrap>table th:nth-child(2){width:17%}#score-table .table-wrap>table th:nth-child(3){width:13%}
.result-weight{white-space:nowrap;color:#42546b;font-variant-numeric:tabular-nums}
.finding-workspace{display:grid;grid-template-columns:220px minmax(0,1fr);height:354px;overflow:hidden;border:1px solid #dce3ec;border-radius:6px;background:#fff}
.finding-sidebar{min-width:0;min-height:0;background:#f7f9fc;border-right:1px solid #dce3ec;display:flex;flex-direction:column}
.finding-list-label{display:flex;justify-content:space-between;align-items:center;padding:12px 12px 8px;font-size:12px;font-weight:500;color:#42546b}.finding-list-label span{font-size:11px;color:#748094;font-weight:400}
.finding-list{overflow:auto;min-height:0;padding:0 6px 8px;scrollbar-width:thin;scrollbar-color:#c0cbd9 transparent;scrollbar-gutter:stable}
.finding-group-label{font-size:11px;font-weight:500;color:#64748b;padding:9px 7px 5px}
.finding-item{display:block;margin:2px 0;padding:8px 9px;border-radius:4px;color:#34465d;text-decoration:none;border-left:2px solid transparent}
.finding-item:hover,.finding-item:focus-visible{background:#eaf0f8;text-decoration:none;outline-offset:-2px}
.finding-item[aria-current="true"]{background:#e4edfc;border-left-color:#2459bc;color:#174894}
.finding-item-top{display:flex;align-items:baseline;justify-content:space-between;gap:8px}.finding-item-top strong{font-size:13px;font-weight:600;overflow-wrap:anywhere}.finding-item-top span{font-size:11px;white-space:nowrap;font-variant-numeric:tabular-nums}
.finding-item small{display:block;font-size:11px;color:#64748b;margin-top:2px}.finding-item[aria-current="true"] small{color:#4b6587}
.finding-preview{position:static;min-width:0;min-height:0;display:flex;flex-direction:column;padding:15px 16px 10px;background:#fff;scroll-margin-top:16px}
.figure-heading{display:flex;align-items:baseline;justify-content:space-between;gap:8px;min-height:24px}
.finding-preview .figure-heading h3{font-size:13px;font-weight:600;line-height:1.5;margin:0;color:#243449;overflow-wrap:anywhere}.figure-heading>span{font-size:11px;color:#7b8798;white-space:nowrap;font-variant-numeric:tabular-nums}
#finding-measure{font-size:12px;color:#64748b;margin:3px 0 6px;min-height:18px}
.finding-stage{flex:1;min-height:0;position:relative;display:grid;place-items:center;background:#fff}
.finding-stage #finding-image{width:100%;height:100%;min-height:0;object-fit:contain;grid-area:1/1;display:block}
.finding-stage #finding-status{grid-area:1/1;margin:0;padding:12px;text-align:center;color:#52647d;font-size:13px;z-index:1}.finding-stage #finding-status:empty{display:none}
.finding-preview[data-state="loading"] #finding-image,.finding-preview[data-state="error"] #finding-image{opacity:0}
.finding-preview[data-state="loading"] #finding-status::before{content:"";display:inline-block;width:12px;height:12px;border:2px solid #d9e3f3;border-top-color:#2459bc;border-radius:50%;margin-right:8px;vertical-align:-2px;animation:finding-spin .8s linear infinite}
.finding-caption{display:flex;align-items:center;gap:5px;font-size:11px;color:#748094;margin:5px 0 0}.finding-caption>span:last-child{margin-left:auto}.candidate-swatch{width:10px;height:7px;background:#f7dfaf;display:inline-block}
.shell main>details.report-section{border:0;border-bottom:1px solid #dfe5ed;padding:0;margin:0;border-radius:0;background:none}
.shell main>details.report-section>summary{box-sizing:border-box;display:flex;align-items:center;gap:12px;min-height:52px;padding:14px 0;margin:0;color:#243449;cursor:pointer;list-style:none}
.shell main>details.report-section>summary>h2{font:600 16px/24px var(--font-ui,system-ui,sans-serif);color:inherit;padding:0;margin:0}
.shell main>details.report-section>summary::after{content:'+';margin-left:auto;flex:none;color:#748094;font:400 18px/24px var(--font-ui,system-ui,sans-serif)}
.shell main>details.report-section[open]>summary::after{content:'−'}
.shell main>details.report-section>summary::-webkit-details-marker{display:none}
.shell main>details.report-section>summary:hover{color:#2459bc}
.shell main>details.report-section>summary:focus-visible{outline:2px solid #8bade2;outline-offset:2px;border-radius:3px}
.report-section>.report-section-body{padding:0 0 18px}
.report-section-body>p:first-child{margin-top:0}
.report-chart-frame{width:100%;height:180px;border:0;display:block;margin:4px 0 14px}.report-chart-section [data-chart-status]{font-size:13px;color:#5b687b}
.report-details-body{padding:0}.report-detail-group{padding:10px 14px;background:#f8fafc;border:1px solid #e6ebf1;border-radius:4px;margin:0 0 10px}
.report-details-body .report-detail-group>h3{font-size:12px;font-weight:600;color:#64748b;margin:0 0 6px}
.report-detail-group details{padding:8px 0;margin:0;border-top:1px solid #e3e9f0}.report-details-body .report-detail-group summary{font-size:13px;color:#34465d;min-height:22px}
.report-detail-group details[open]>summary{margin-bottom:8px}.report-detail-group details details{margin-left:10px;border-top:0}.report-detail-group h2{font-size:14px}.report-detail-group h3{font-size:13px}
section>p.muted{font-size:12px;margin:0 0 10px}.scope,.footnote{font-size:12px}pre{font-size:12px}.failure{font-size:13px;padding:8px 10px}footer{font-size:12px;margin-top:18px}section[id],details[id]{scroll-margin-top:20px}
@keyframes finding-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.finding-preview[data-state="loading"] #finding-status::before{animation:none}}
@media(max-width:1050px){.finding-workspace{grid-template-columns:195px minmax(0,1fr)}.finding-preview{padding:12px 10px 10px}}
@media(max-width:900px){.shell{display:block;padding:18px 16px}.shell aside{margin-bottom:18px}.shell aside nav{display:flex;flex-wrap:wrap;margin-top:8px;gap:8px 16px}.report-title{flex-wrap:wrap}}
@media(max-width:760px){.finding-workspace{display:flex;flex-direction:column;height:auto}.finding-preview{order:-1;height:276px;flex:none}.finding-sidebar{border-right:0;border-top:1px solid #dce3ec}.finding-list{max-height:200px}.finding-item-top span{font-size:12px}.finding-list-label{padding-bottom:4px}}
@media(max-width:600px){.report-summary{grid-template-columns:1fr;gap:12px}.report-total{border:0}.figure-heading>span{font-size:11px}.finding-caption{font-size:10px}}
@media print{.report-actions,aside,script{display:none}.shell{display:block;max-width:none;padding:0}.report-summary{grid-template-columns:180px 1fr}.finding-workspace{height:auto;display:block;overflow:visible;break-inside:avoid}.finding-sidebar{display:none}.finding-preview{display:block}.finding-stage{display:block}.finding-stage #finding-image{height:auto;opacity:1!important}#finding-status{display:none!important}.report-details-body{padding:0}.report-detail-group{background:#fff}}
"""

from .score_presentation import CSS as SCORE_CSS
CSS += SCORE_CSS
