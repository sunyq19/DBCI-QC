"""Read-only dataset result workspace. PDF typography lives in its own renderer."""
from collections import Counter
import html
import json

from .review import LABELS

WEB_VERSION = 'dataset-result-web/3'

CSS = r'''
:root{color-scheme:light;--ink:#252b34;--sub:#68717e;--line:#e4e7ec;--blue:#2459bc;--wash:#f7f8fa}
*{box-sizing:border-box}body{margin:0;color:var(--ink);background:#fff;font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}button,input,select{font:inherit;color:inherit}button,a,summary,select{touch-action:manipulation}button{cursor:pointer}button:focus-visible,a:focus-visible,summary:focus-visible,select:focus-visible{outline:2px solid #8caeea;outline-offset:3px}[hidden]{display:none!important}
.appbar{position:sticky;top:0;z-index:5;background:#fff;height:56px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 32px;gap:24px}.brand{color:var(--ink);font-size:15px;font-weight:600;display:inline-flex;align-items:center;gap:9px}.brand svg{width:23px;height:23px;color:var(--blue)}.crumb{display:flex;align-items:center;gap:18px}.crumb>span{font-size:13px;color:var(--sub)}.bar-right{display:flex;align-items:center;gap:18px;font-size:12px;color:var(--sub)}.language{display:flex;gap:10px}.language [aria-current=page]{color:var(--ink);font-weight:600}
main{max-width:1440px;padding:30px 36px 22px;margin:auto}.record-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px}.record-head h1{font-size:22px;line-height:1.4;font-weight:600;margin:0 0 10px;overflow-wrap:anywhere}.record-meta{display:flex;gap:8px 22px;flex-wrap:wrap;color:var(--sub);font-size:12px}.record-meta strong{font-weight:500;color:var(--ink)}.actions{display:flex;gap:8px;flex-shrink:0}.action{display:inline-flex;align-items:center;justify-content:center;height:33px;padding:0 13px;border:1px solid #ccd2da;border-radius:5px;font-size:13px;font-weight:500;color:var(--ink);background:white}.action:hover{text-decoration:none;background:var(--wash);border-color:#aeb8c6}.action.primary{color:var(--blue);border-color:#bdcdec}.record-status{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:20px 0 0;padding:13px 0;border-top:1px solid var(--line);font-size:12px}.check-summary{display:flex;gap:22px;flex-wrap:wrap}.check-summary b{font-size:14px;font-weight:600;font-variant-numeric:tabular-nums;margin-left:5px}.minor{color:var(--sub)}.demo{font-size:11px;color:var(--sub)}
.dot:before{content:'';display:inline-block;vertical-align:middle;width:5px;height:5px;margin-right:7px;border-radius:50%;background:#8b949f}.dot.conflict:before,.dot.review:before{background:#b87825}.dot.pass:before,.dot.resolved:before{background:#43816a}.state{font-size:12px;white-space:nowrap;color:var(--sub)}.state.conflict{color:#95611e}.state.resolved{color:#39735e}
.section-nav{display:flex;gap:28px;border-bottom:1px solid #dce1e8;margin:9px 0 0}.section-nav a{display:flex;gap:8px;align-items:center;padding:13px 0;color:var(--sub);border-bottom:2px solid transparent;font-size:13px}.section-nav a:hover{text-decoration:none;color:var(--ink)}.section-nav a[aria-selected=true]{color:var(--ink);border-color:var(--blue);font-weight:600}.nav-count{font-size:11px;font-variant-numeric:tabular-nums;color:var(--sub);font-weight:400}.panel{padding-top:20px;min-width:0}.panel h2{font-size:16px;font-weight:600;margin:0 0 16px}.js .panel-title{display:none}.filters{display:flex;align-items:center;gap:6px;margin:0 0 16px}.filters button{border:0;background:transparent;padding:5px 10px;color:var(--sub);font-size:12px;border-radius:4px}.filters button[aria-pressed=true]{background:#edf2fa;color:#274f91}.filters span{margin-left:6px;font-variant-numeric:tabular-nums}.filter-context{margin-left:auto;color:var(--sub);font-size:12px}
.findings-layout{display:grid;grid-template-columns:minmax(390px,1.35fr) minmax(330px,1fr);border:1px solid var(--line);border-radius:5px;min-height:380px;align-items:start}.issue-list{min-width:0}.list-header,.issue-row{display:grid;grid-template-columns:minmax(160px,1fr) 100px 60px;gap:14px;align-items:center}.list-header{height:34px;background:var(--wash);padding:0 18px;color:var(--sub);font-size:11px;border-bottom:1px solid var(--line)}.issue-row{width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);padding:14px 18px;background:white;min-height:64px}.issue-row:last-of-type{border-bottom:0}.issue-row:hover{background:#f8f9fb}.issue-row[aria-pressed=true]{background:#f0f4fa;box-shadow:inset 2px 0 var(--blue)}.issue-row .name{display:block;font-size:13px;font-weight:500}.issue-row .detail{display:block;font-size:11px;color:var(--sub);margin-top:4px;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;max-width:420px}.issue-count{text-align:right;font-size:12px;font-variant-numeric:tabular-nums;color:var(--sub)}
.inspector{border-left:1px solid var(--line);padding:22px 24px;min-width:0;min-height:380px;align-self:stretch}.inspector h3{font-size:16px;line-height:1.45;font-weight:600;margin:0}.inspector-heading{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:5px}.inspector-meta{font-size:11px;color:var(--sub);margin:0 0 19px}.inspector .message{font-size:13px;line-height:1.7;margin:14px 0;overflow-wrap:anywhere}.inspector h4{font-size:12px;font-weight:500;color:var(--sub);margin:20px 0 7px}.record-picker{display:flex;align-items:center;gap:12px;margin:18px 0 8px;font-size:12px}.record-picker select{min-width:0;flex:1;border:1px solid #d5dbe3;background:white;border-radius:4px;padding:6px 9px;font-size:12px}.record-id{font-size:11px;color:var(--sub);overflow-wrap:anywhere;line-height:1.65;margin:8px 0}.advice{border-left:2px solid #dce3ec;padding-left:12px;font-size:13px;line-height:1.7;margin:8px 0 20px}.decision-data{display:grid;grid-template-columns:74px minmax(0,1fr);gap:8px 12px;font-size:12px;margin:12px 0}.decision-data dt{color:var(--sub)}.decision-data dd{margin:0;overflow-wrap:anywhere}
details{margin-top:14px;border-top:1px solid var(--line)}summary{font-size:12px;color:var(--sub);cursor:pointer;padding:12px 0;list-style:none;display:flex;justify-content:space-between;gap:12px}summary::-webkit-details-marker{display:none}summary:after{content:'+';font-size:16px;color:#768291}details[open]>summary:after{content:'−'}pre{font:11px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--wash);padding:12px;max-height:340px;overflow:auto;border-radius:3px}details ul{padding-left:16px;font-size:11px;color:var(--sub)}details li{margin-bottom:6px;overflow-wrap:anywhere}.empty{padding:28px 20px;color:var(--sub);font-size:13px}.fineprint{font-size:11px;color:var(--sub);margin:13px 0 0;line-height:1.7}.retest-strip{display:flex;gap:24px;flex-wrap:wrap;font-size:13px;margin:0 0 18px}.retest-strip b{font-weight:600;margin-right:5px}.warning{border-left:2px solid #bd8b45;padding:8px 12px;color:#8e642c;font-size:12px;margin:0 0 15px}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;text-align:left;font-size:12px}th{background:var(--wash);color:var(--sub);font-size:11px;font-weight:400}th,td{padding:11px 14px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}td:first-child{font-weight:500}.measurements{margin:12px 0}.measurements th,.measurements td{padding:8px 10px}.metadata-table{max-width:920px}.metadata-table td:first-child{width:150px;color:var(--sub);font-weight:400}.metadata-table td:last-child{overflow-wrap:anywhere}.record-table td:last-child{font-size:11px;color:var(--sub)}.footer{display:flex;justify-content:space-between;gap:20px;margin-top:22px;border-top:1px solid var(--line);padding-top:13px;font-size:11px;color:var(--sub)}.footer p{margin:0;max-width:850px}.no-js{font-size:12px;color:var(--sub)}.no-script .inspector-panel{margin-bottom:28px}.js-only{display:none}.js .filters,.js .record-picker{display:flex}.js .list-header,.js .issue-row{display:grid}
@media(min-width:1100px){.inspector{position:sticky;top:74px;max-height:calc(100vh - 92px);overflow-y:auto;scrollbar-width:thin}}
@media(max-width:980px){main{padding:24px}.appbar{padding:0 24px}.findings-layout{grid-template-columns:minmax(300px,1fr) minmax(300px,1fr)}.inspector{padding:18px}.list-header,.issue-row{grid-template-columns:minmax(100px,1fr) 76px 36px;gap:9px;padding-left:14px;padding-right:14px}.filter-context{display:none}}
@media(max-width:700px){.appbar{padding:0 16px;height:49px}.crumb{gap:12px}.crumb>span{display:none}.bar-right{gap:12px}.bar-right .demo{display:none}main{padding:22px 16px}.record-head{display:block}.record-head h1{font-size:19px}.actions{margin-top:16px}.record-meta{gap:7px 14px}.record-status{margin-top:16px}.check-summary{gap:14px}.section-nav{gap:22px;overflow:auto}.section-nav a{white-space:nowrap}.findings-layout{display:block;border:0}.issue-list{border:1px solid var(--line);border-radius:4px;overflow:hidden}.inspector{border:0;border-top:1px solid var(--line);padding:22px 0;min-height:0;margin-top:20px}.inspector-panel{scroll-margin-top:68px}.issue-row{min-height:59px}.footer{display:block}.footer>span{display:block;margin-top:7px}.filters{gap:1px}.filters button{padding:5px 8px}}
@media print{.appbar,.actions,.filters,.section-nav,.js-only{display:none!important}main{max-width:none;padding:0}.js .panel[hidden],.js .inspector-panel[hidden],.js .record-evidence[hidden]{display:block!important}.findings-layout{display:block;border:0}.inspector{border:0;position:static;max-height:none;overflow:visible;padding:20px 0}.record-head h1{font-size:20px}.panel{break-before:auto}thead{display:table-header-group}tr{break-inside:avoid}.issue-row{display:none}.footer{font-size:9px}}
'''

SCRIPT = r'''
(() => {
  'use strict';
  const app=document.getElementById('dataset-report');
  if(!app)return;
  const tabs=[...app.querySelectorAll('[data-tab]')];
  const panels=[...app.querySelectorAll('[data-panel]')];
  const filters=[...app.querySelectorAll('[data-filter]')];
  const rows=[...app.querySelectorAll('[data-group]')];
  const inspectors=[...app.querySelectorAll('[data-inspector]')];
  const empty=document.getElementById('findings-empty');
  let selected=rows[0]?.dataset.group;
  function inspect(id,scroll=false){
    selected=id;
    rows.forEach(r=>r.setAttribute('aria-pressed',String(r.dataset.group===id)));
    inspectors.forEach(p=>{p.hidden=p.dataset.inspector!==id;});
    const panel=inspectors.find(p=>!p.hidden);
    if(scroll&&matchMedia('(max-width:700px)').matches)panel?.scrollIntoView({block:'start',behavior:'smooth'});
  }
  function filter(key){
    filters.forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.filter===key)));
    rows.forEach(r=>{r.hidden=key!=='all'&&(key==='unassessed'?r.dataset.status!=='unassessed':r.dataset.status==='unassessed');});
    const visible=rows.filter(r=>!r.hidden);
    if(empty)empty.hidden=visible.length>0;
    inspect(visible.find(r=>r.dataset.group===selected)?.dataset.group||visible[0]?.dataset.group);
  }
  function tab(id){
    if(!panels.some(p=>p.dataset.panel===id))return;
    tabs.forEach(a=>{const active=a.dataset.tab===id;a.setAttribute('aria-selected',String(active));a.tabIndex=active?0:-1;});
    panels.forEach(p=>{p.hidden=p.dataset.panel!==id;});
  }
  app.addEventListener('click',event=>{
    const a=event.target.closest('[data-tab]');
    if(a){event.preventDefault();tab(a.dataset.tab);return;}
    const b=event.target.closest('[data-filter]');
    if(b){filter(b.dataset.filter);return;}
    const row=event.target.closest('[data-group]');
    if(row)inspect(row.dataset.group,true);
  });
  app.addEventListener('keydown',event=>{
    const current=event.target.closest('[data-tab]');
    if(!current||!['ArrowRight','ArrowLeft','Home','End'].includes(event.key))return;
    event.preventDefault();const i=tabs.indexOf(current);
    const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(i+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
    tab(tabs[next].dataset.tab);tabs[next].focus();
  });
  app.addEventListener('change',event=>{
    const select=event.target.closest('[data-record-select]');
    if(!select)return;
    const panel=select.closest('[data-inspector]');
    panel.querySelectorAll('[data-record-evidence]').forEach(p=>{p.hidden=p.dataset.recordEvidence!==select.value;});
  });
  app.classList.remove('no-script');app.classList.add('js');
  app.querySelectorAll('[data-record-select]').forEach(select=>{
    select.closest('[data-inspector]').querySelectorAll('[data-record-evidence]').forEach(p=>{p.hidden=p.dataset.recordEvidence!==select.value;});
  });
  filter(rows.some(r=>r.dataset.status!=='unassessed')?'attention':'all');
  tab('findings');
})();
'''


def render_html(case, c, language, *, standalone=False):
    en = language == 'en'; t = lambda zh, english: english if en else zh
    e = lambda value: html.escape(str(value), quote=True)
    ds = case['dataset_summary']; counts = c['counts']; prev = case.get('previous')
    job = e(case['job_id']); review_url = f'/datasets?job={job}&tab=review&lang={language}'
    base = f'/api/v1/package-jobs/{job}/review'
    number = lambda value: '—' if value is None else str(value)
    def table(headers, rows, class_name=''):
        return f'<div class="table-scroll"><table class="{class_name}"><thead><tr>'+''.join(f'<th scope="col">{e(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    def measurement(row):
        obs = row.get('observed')
        if row['code'] != 'units' or not isinstance(obs,dict) or not isinstance(obs.get('conflicts'),list):
            return ''
        valid = [x for x in obs['conflicts'] if isinstance(x,dict) and all(k in x for k in ('file','table','channel'))]
        if not valid:
            return ''
        pairs = Counter((str(x['file']),str(x['table'])) for x in valid)
        return table([t('文件标定','File calibration'),t('通道表','Channel table'),t('涉及通道','Channels')],
                     [[e(a),e(b),str(n)] for (a,b),n in pairs.items()],'measurements')
    aliases = {r['alias']:r for r in c['records']}
    def target_preview(g):
        names = ', '.join(g['targets'][:4])
        if len(g['targets'])>4:
            names += t(f' 等 {len(g["targets"])} 个对象', f'; {len(g["targets"])} targets')
        return names
    issue_rows=[]; inspectors=[]
    for g in c['groups']:
        ref=g['ref']
        issue_rows.append(f'<button type="button" class="issue-row js-only" data-group="{ref}" data-status="{g["status"]}" aria-controls="inspector-{ref}" aria-pressed="false"><span><span class="name">{e(g["title"])}</span><span class="detail">{e(target_preview(g))}</span></span><span class="state dot {g["status"]}">{e(g["machine"])}</span><span class="issue-count">{len(g["rows"])}</span></button>')
        evidence=[]; options=[]
        for index,row in enumerate(g['rows']):
            key=f'{ref}-{index}'
            descriptor=aliases.get(row['short_target'],{})
            option=row['short_target']+(' · '+descriptor['subject'] if descriptor else '')
            options.append(f'<option value="{key}">{e(option)}</option>')
            decision=''
            if row.get('decision'):
                fields=[(t('处理状态','Decision'),row['disposition_label']),(t('影响 / 用途','Impact / use'),row['impact']),
                        (t('下一步','Next step'),row['action']),(t('依据','Basis'),row['note']),
                        (t('负责人','Owner'),row['owner']),(t('填写人','Reviewer'),row['reviewer'])]
                decision='<h4>'+t('已登记意见','Recorded decision')+'</h4><dl class="decision-data">'+''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k,v in fields)+'</dl>'
            files=''.join(f'<li>{e(f)}</li>' for f in row.get('files',[]))
            raw=e(json.dumps(row.get('observed'),ensure_ascii=False,indent=2))
            evidence.append(f'<section class="record-evidence" data-record-evidence="{key}" aria-label="{e(option)}"><p class="record-id">{e(row["target"])}</p><p class="message">{e(row["message"])}</p>{measurement(row)}{decision}<details><summary>{t("原始证据","Source evidence")}</summary><ul>{files}</ul><pre>{raw}</pre><p class="record-id">{e(row["id"])}</p></details></section>')
        selector=f'<label class="record-picker js-only" for="record-{ref}">{t("记录","Record")}<select id="record-{ref}" data-record-select="{ref}">{"".join(options)}</select></label>' if len(g['rows'])>1 else ''
        action='' if standalone else f'<a class="action primary" href="{review_url}">{t("进入审核","Open review")}</a>'
        inspectors.append(f'<section class="inspector-panel" id="inspector-{ref}" data-inspector="{ref}" aria-label="{e(g["title"])}"><div class="inspector-heading"><h3>{e(g["title"])}</h3><span class="state dot {g["status"]}">{e(g["machine"])}</span></div><p class="inspector-meta">{g["module"]} · {len(g["rows"])} {t("项检查","checks")}</p>{selector}{"".join(evidence)}<h4>{t("建议核对","Suggested check")}</h4><p class="advice">{e(g["action"])}</p>{action}</section>')
    n_attention=counts['conflict']+counts['review']
    filters=''.join(f'<button type="button" data-filter="{key}" aria-pressed="false">{e(name)}<span>{value}</span></button>' for key,name,value in [
        ('attention',t('需核对','Needs checking'),n_attention),('unassessed',t('未评','Unassessed'),counts['unassessed']),('all',t('全部问题','All findings'),len(c['rows']))])
    findings=f'''<section class="panel" id="findings" data-panel="findings" role="tabpanel" aria-labelledby="tab-findings"><h2 class="panel-title">{t("检查问题","Findings")}</h2><div class="filters js-only" role="group" aria-label="{t("筛选检查结果","Filter findings")}">{filters}<span class="filter-context">{t("按问题类型归并","Grouped by finding type")}</span></div><div class="findings-layout"><div class="issue-list"><div class="list-header js-only"><span>{t("检查项","Check")}</span><span>{t("结果","Result")}</span><span class="issue-count">{t("项数","Count")}</span></div>{"".join(issue_rows)}<p class="empty" id="findings-empty"{' hidden' if c['groups'] else ''}>{t("没有此类问题。","No findings in this category.")}</p><noscript><p class="empty">{t("下方保留全部检查明细；启用 JavaScript 可切换问题。","All details are listed below. Enable JavaScript for interactive selection.")}</p></noscript></div><aside class="inspector" aria-label="{t("问题详情","Finding details")}">{"".join(inspectors) or '<p class="empty">'+t('本次没有待处理发现。','No open findings in this run.')+'</p>'}</aside></div><p class="fineprint">{e(c["count_note"])}</p></section>'''
    retest=''
    if prev:
        stats=''.join(f'<span><b>{n}</b>{e(LABELS[k][int(en)])}</span>' for k,n in prev['counts'].items())
        warning='' if prev.get('compatible') else '<p class="warning">'+t('本次范围或规则有变化，不能据此认定问题消除。','Scope or rules changed; this comparison cannot establish resolution.')+'</p>'
        changes=table([t('检查项','Check'),t('对象','Target'),t('变化','Change'),t('前后结果','Before / after')],[
            [e(r['title']),e(r['short_target']),f'<span class="state {r["change"]}">{e(r["change_label"])}</span>',e(r['before_label']+' → '+r['after_label'])] for r in c['delta']])
        retest=f'<section class="panel" id="retest" data-panel="retest" role="tabpanel" aria-labelledby="tab-retest"><h2 class="panel-title">{t("复验变化","Retest changes")}</h2>{warning}<div class="retest-strip">{stats}</div>{changes}<p class="fineprint">{t("仅列变化项；未复查或范围改变，不计为问题消除。","Only changed checks are listed. Omitted checks or changed scopes do not count as resolved.")}</p></section>'
    records_table=table([t('简称','Alias'),t('个体','Subject'),t('记录标识','Recording identifier')],[[e(r['alias']),e(r['subject']),e(r['id'])] for r in c['records']],'record-table')
    records=f'<section class="panel" id="records" data-panel="records" role="tabpanel" aria-labelledby="tab-records"><h2 class="panel-title">{t("涉及记录","Referenced recordings")}</h2>{records_table}<p class="fineprint">{t("R 编号仅用于本报告；表内保留完整记录标识。","R aliases are local to this report; full recording identifiers are retained here.")}</p></section>'
    trace=[(t('检查范围','Scope'),case['scope']),(t('解释范围','Interpretation'),c['boundary']),(t('检查时间','Checked at'),c['checked_at']),
           (t('审核状态','Review outcome'),c['outcome']+' · '+c['status_note']),(t('规则版本','Rule version'),case['rule_version']),
           (t('审核版本','Review revision'),'r'+str(case['revision'])),(t('运行编号','Run ID'),case['job_id']),
           (t('结果指纹','Result fingerprint'),case['result_hash']),(t('网页版本','Web version'),WEB_VERSION)]
    if prev:trace.append((t('对照运行','Baseline run'),prev.get('job_id','—')))
    history=table([t('版本','Revision'),t('填写人','Reviewer'),t('时间','Time')],[[f'r{r["revision"]}',e(r['reviewer']),e(r['recorded_at'])] for r in case.get('history',[])])
    run=f'<section class="panel" id="run" data-panel="run" role="tabpanel" aria-labelledby="tab-run"><h2 class="panel-title">{t("运行信息","Run information")}</h2>'+table([t('字段','Field'),t('内容','Value')],[[e(k),e(v)] for k,v in trace],'metadata-table')+('<details><summary>'+t('审核历史','Review history')+'</summary>'+history+'</details>' if case.get('history') else '')+'</section>'
    nav=[('findings',t('检查问题','Findings'),len(c['rows']))]
    if prev:nav.append(('retest',t('复验变化','Retest changes'),len(c['delta'])))
    nav.extend([('records',t('涉及记录','Recordings'),len(c['records'])),('run',t('运行信息','Run details'),None)])
    nav_html=''.join(f'<a id="tab-{key}" href="#{key}" data-tab="{key}" role="tab" aria-controls="{key}" aria-selected="false">{e(name)}'+(f'<span class="nav-count">{n}</span>' if n is not None else '')+'</a>' for key,name,n in nav)
    meta=[(ds.get('subjects'),t('个体','subjects')),(ds.get('records'),t('份记录','recordings')),(ds.get('groups'),t('比较组','comparison groups'))]
    metadata=''.join(f'<span><strong>{e(number(v))}</strong> {e(name)}</span>' for v,name in meta)
    if 'expected_files' in ds:metadata+=f'<span>{t("文件","Files")} <strong>{e(number(ds.get("present_files")))}/{ds["expected_files"]}</strong></span>'
    metadata+=f'<span>{e(c["checked_at"])}</span>'
    summaries=[('conflict',t('资料不符','Mismatches'),counts['conflict']),('unassessed',t('未评','Unassessed'),counts['unassessed']),('pass',t('通过','Passed'),counts['pass'])]
    if counts['review']:summaries.insert(1,('review',t('待核对','Check needed'),counts['review']))
    if counts['not_applicable']:summaries.append(('not_applicable',t('不适用','Not applicable'),counts['not_applicable']))
    summary_html=''.join(f'<span class="dot {state}">{e(name)}<b>{e(number(n))}</b></span>' for state,name,n in summaries)
    actions='' if standalone else f'<div class="actions"><a class="action" href="{base}/pdf?lang={language}">{t("下载 PDF","Download PDF")}</a><a class="action primary" href="{review_url}">{t("审核与复验","Review and retest")}</a></div>'
    lang='' if standalone else '<div class="language">'+''.join(f'<a href="{base}/report?lang={lng}"'+(' aria-current="page"' if lng==language else '')+f'>{name}</a>' for lng,name in [('zh-CN','中文'),('en','EN')])+'</div>'
    logo='<svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M2 13h5l3-8 4 15 3-10 2 3h3" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    script=f'<script defer>{SCRIPT}</script>' if standalone else '<script src="/dataset-review-report.js" defer></script>'
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(c['label'])} · {t('检查结果','Check results')}</title><style>{CSS}</style></head><body>
<header class="appbar"><div class="crumb"><a class="brand" href="{'#' if standalone else '/'}">{logo}{t('质控台','Quality control')}</a><span>{t('数据集 / 检查结果','Dataset / Results')}</span></div><div class="bar-right">{'<span class="demo">'+e(c['demo'])+'</span>' if c['demo'] else ''}{lang}</div></header>
<main id="dataset-report" class="no-script"><div class="record-head"><div><h1>{e(c['label'])}</h1><div class="record-meta">{metadata}</div></div>{actions}</div><div class="record-status"><div class="check-summary">{summary_html}</div><span class="minor">{t('人工审核','Human review')} · {e(c['outcome'])}</span></div><nav class="section-nav" role="tablist" aria-label="{t('结果内容','Result sections')}">{nav_html}</nav>{findings}{retest}{records}{run}<footer class="footer"><p>{t('本地处理 · 数据集资料检查','Local processing · Dataset metadata checks')}</p><span>{e(case['rule_version'])}</span></footer></main>{script}</body></html>'''
