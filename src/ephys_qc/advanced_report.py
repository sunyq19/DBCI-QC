"""Small human-readable views of saved extension evidence; never reruns algorithms."""
import html
import json
from pathlib import Path

NAMES={'pyprep_ransac':'RANSAC 空间预测','autoreject_epochs':'local AutoReject','ica_iclabel':'ICLabel 成分类别','dredge_lfp':'DREDge LF 漂移','nwb_inspector':'NWB 文件规范'}
CLASSES={'brain':'脑成分','muscle':'肌电','eye':'眼动','heart':'心电','line_noise':'工频','channel_noise':'通道噪声','other':'其他'}


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
    if slot in report:return report.replace(slot,render(root,nested=True),1)
    part=render(root)
    return report.replace('</main>',part+'</main>',1) if '</main>' in report else report.replace('</body>',part+'</body>',1)
