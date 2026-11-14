"""Small human-readable views of saved extension evidence; never reruns algorithms."""
import html
import json
import re
from pathlib import Path

NAMES={'pyprep_ransac':'RANSAC 空间预测','autoreject_epochs':'local AutoReject','ica_iclabel':'ICLabel 成分类别','dredge_lfp':'DREDge LF 漂移','nwb_inspector':'NWB 文件规范'}
CLASSES={'brain':'脑成分','muscle':'肌电','eye':'眼动','heart':'心电','line_noise':'工频','channel_noise':'通道噪声','other':'其他'}


def overview(root):
    """Keep measured extension results visible without opening the audit log."""
    root=Path(root); grouped={}; continuity=[]
    for directory in [root/'artifacts',*sorted((root/'windows').glob('*/artifacts'))]:
        for method in NAMES:
            for path in directory.glob('M??_'+method+'.json'):
                grouped.setdefault(method,[]).append(json.loads(path.read_text()))
        path=directory/'M03_continuity.json'
        if path.is_file():
            from .continuity_evidence import neuropixels_locations
            row=neuropixels_locations(json.loads(path.read_text())).get('measurement_summary')
            if row:continuity.append(row)
    rows=[]
    if continuity:
        invalid=sum(r['nonfinite_sample_count'] for r in continuity)
        flat=sum(r['constant_channel_blocks'] for r in continuity)
        maximum=max(r['max_equal_seconds'] for r in continuity)*1000
        rows.append(('数值与恒值检查',f'{invalid} 个无效采样；{flat} 个整窗恒值通道。最长重复值 {maximum:.2f} 毫秒。短暂重复仅作测量，不作为异常候选或扣分依据。'))
    for method,payloads in grouped.items():
        good=[p for p in payloads if p.get('status') in {'completed','partial'}]
        if not good: text='未完成：'+str(payloads[0].get('reason','条件不足'))
        elif method=='pyprep_ransac':
            counts=[len(p.get('candidates',[])) for p in good]
            text=f'可计分 · {len(good)} 个分析段，各段候选通道数：'+ '、'.join(map(str,counts))+'。'
        elif method=='autoreject_epochs':
            labels=[row for p in good for row in p.get('labels',[])]
            total=sum(len(row) for row in labels); bad=sum(v>0 for row in labels for v in row)
            text=f'可计分 · {bad} / {total} 个通道片段超出所估计阈值。'
        elif method=='ica_iclabel':
            text=f'仅测量 · {len(good)} 个分析段，完成 {sum(len(p.get("components",[])) for p in good)} 个独立成分的分类；概率不等于质量分。'
        elif method=='dredge_lfp':
            ranges=[r['range_um'] for p in good for r in p.get('motion',[])]
            text='仅测量 · 块内相对位移范围：'+'、'.join(f'{v:.2f} µm' for v in ranges)+'；不参与质量分。'
        else:
            issues=[r for p in good for r in p.get('issues',[])]
            errors=sum(p.get('error_count',sum(r.get('importance') in {'ERROR','CRITICAL','PYNWB_VALIDATION'} for r in p.get('issues',[]))) for p in good)
            text=f'结构检查 · {errors} 条错误，{len(issues)-errors} 条其他发现或建议；不折算信号分数。'
        rows.append((NAMES[method],text))
    if not rows:return ''
    from .report_presentation import report_section
    body='<table><thead><tr><th>检查方法</th><th>本次结果</th></tr></thead><tbody>'+''.join('<tr><th>'+html.escape(title)+'</th><td>'+html.escape(text)+'</td></tr>' for title,text in rows)+'</tbody></table>'
    return report_section('method-summary','方法结果',body,opened=True)


def render(root, *, nested=False):
    root=Path(root);sections=[];e=lambda x:html.escape(str(x))
    for directory in [root/'artifacts',*sorted((root/'windows').glob('*/artifacts'))]:
        for method,title in NAMES.items():
            files=list(directory.glob('M??_'+method+'.json'))
            if not files:continue
            p=json.loads(files[0].read_text());rows=[];headers=[]
            span=p.get('range',{});caption=f"{span.get('start_seconds',0):g}–{span.get('stop_seconds',0):g} s" if span else ''
            if p.get('status') not in {'completed','partial'}:
                sections.append(f'<details><summary>{e(title)} · 未评</summary><p>{e(p.get("reason","方法未完成"))}</p></details>');continue
            if method=='pyprep_ransac':
                headers=['通道','低相关窗口占比','候选']
                flagged={c['channel_name'] for c in p['candidates']}
                rows=[[r['channel_name'],f"{100*r['bad_window_fraction']:.1f}%",'是' if r['channel_name'] in flagged else '否'] for r in p['measurements']]
                rows.sort(key=lambda r:(r[2]!='是',r[0]))
            elif method=='autoreject_epochs':
                headers=['通道','峰峰值阈值 / µV','超阈值片段 / 受检片段']
                labels=p['labels'];n=len(labels)
                rows=[[name,f"{p['thresholds_volts'][name]*1e6:.2f}",f"{sum(row[i]>0 for row in labels)} / {n}"] for i,name in enumerate(p['channel_names'])]
            elif method=='ica_iclabel':
                headers=['成分','主要类别','概率']
                rows=[[f"IC {r['component']}",CLASSES.get(r['label'],r['label']),f"{100*r['probabilities'][r['label']]:.1f}%"] for r in p['components']]
            elif method=='dredge_lfp':
                headers=['探针杆','块内位移范围 / µm','块内参考时间 / s']
                rows=[[r['shank'],f"{r['range_um']:.2f}",f"{r['reference_seconds']:.2f}"] for r in p['motion']]
            else:
                headers=['级别','检查','发现']
                rows=[[r['importance'],r['check_function_name'],r['message']] for r in p['issues']]
            table='<div style="overflow:auto;max-height:26rem"><table><thead><tr>'+''.join(f'<th>{e(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
            if not rows:table='<p>本项未报告问题。</p>'
            note='概率不参与信号评分。' if method=='ica_iclabel' else '每个分析块独立参考；位移不参与质量评分。' if method=='dredge_lfp' else '完整分段内超阈值不等于已确认伪迹；候选可在问题定位中复核。' if method=='autoreject_epochs' else '通道候选不指定异常起止时间。' if method=='pyprep_ransac' else '结构规范错误和建议与信号质量分开。'
            sections.append(f'<details><summary>{e(title)} <span class="muted">{e(caption)}</span></summary><p>{note}</p>{table}</details>')
    if not sections:return ''
    if nested:
        return '<div id="advanced-method-results" class="report-detail-group"><h3>方法测量</h3>'+''.join(sections)+'</div>'
    from .report_presentation import report_section
    return report_section('advanced-method-results','扩展方法结果',''.join(sections),opened=False)


def append_to(report,root):
    if 'id="advanced-method-results"' in report:return report
    slot='<div id="method-evidence-slot"></div>'
    summary=overview(root)
    if summary:
        report,count=re.subn(r'(?=<details id="(?:review|locations)")',lambda _:summary,report,count=1)
        if not count:report=report.replace('</main>',summary+'</main>',1)
    if slot in report:return report.replace(slot,render(root,nested=True),1)
    nested=render(root,nested=True)
    report,inserted=re.subn(r'(<details id="details"[^>]*><summary>.*?</summary><div class="report-section-body">)',lambda m:m[0]+nested,report,count=1,flags=re.S)
    if inserted:return report
    part=render(root)
    if '<details id="checks"' in report:
        return report.replace('<details id="checks"',part+'<details id="checks"',1)
    return report.replace('</main>',part+'</main>',1) if '</main>' in report else report.replace('</body>',part+'</body>',1)
