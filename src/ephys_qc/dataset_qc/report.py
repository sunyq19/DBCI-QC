"""Standalone dataset reports. Nothing is sent to an external service."""
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
from .consistency import evaluate_dataset

NAMES = {'D01': ('完整性', 'Completeness'), 'D02': ('个体一致性', 'Individual consistency'), 'D03': ('数据集一致性', 'Dataset consistency')}
STATUS = {'pass': ('一致', 'Consistent'), 'conflict': ('冲突', 'Conflict'), 'review': ('待复核', 'Review'),
          'unassessed': ('未评', 'Unassessed'), 'not_applicable': ('不适用', 'Not applicable')}


def render_dataset_report(result, lang='zh-CN'):
    en = lang == 'en'; e = lambda v: html.escape(str(v)); tr = lambda a,b: b if en else a
    s=result['summary']; c=s['status_counts']
    cards=''.join(f'<article><span>{mid} · {NAMES[mid][int(en)]}</span><h2>{sum(m["counts"].get(k,0) for k in ("conflict","review"))}</h2><p>{tr("冲突 / 待复核项","Conflicts / review items")}</p><small>{m["counts"].get("unassessed",0)} {tr("项未评","unassessed")}</small></article>' for m in result['modules'] for mid in [m['id']])
    groups=''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in (g['label'],g['subjects'],g['records'],', '.join(map(str,g['channel_counts']))))+'</tr>' for g in result['groups'])
    subjects=''.join('<tr>'+''.join(f'<td>{e(v)}</td>' for v in (r['id'],r['records'],r['sessions'],r['status_counts'].get('conflict',0),r['status_counts'].get('review',0),r['status_counts'].get('unassessed',0)))+'</tr>' for r in result['subjects'])
    checks=[]
    for row in sorted(result['checks'],key=lambda r: {'conflict':0,'review':1,'unassessed':2,'pass':3,'not_applicable':4}[r['status']]):
        observed=e(json.dumps(row['observed'],ensure_ascii=False,indent=2)) if row['observed'] is not None else ''
        files='<br>'.join(e(p) for p in row['files'])
        checks.append(f'<tr><td>{e(row["module"])}</td><td>{e(row["label_en"] if en else row["label"])}</td><td><span class="{row["status"]}">{STATUS[row["status"]][int(en)]}</span></td><td>{e(row["target"])}</td><td><details><summary>{tr("证据","Evidence")}</summary><p>{e(row["message"])}</p><p>{files}</p><pre>{observed}</pre></details></td></tr>')
    return f'''<!doctype html><html lang="{lang}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{tr('数据集质检报告','Dataset QC report')}</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;color:#18324d;background:#f4f7fc;margin:0;padding:32px}}main{{max-width:1200px;margin:auto}}h1{{font-size:30px;margin:6px 0}}h2{{font-size:21px}}.muted,small{{color:#63758b}}section,article{{background:#fff;border:1px solid #dde6f2;border-radius:16px;padding:24px;margin:16px 0}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}article h2{{font-size:32px;color:#2459c6;margin:8px 0}}table{{width:100%;border-collapse:collapse}}th,td{{padding:12px;border-bottom:1px solid #e5ebf4;text-align:left;overflow-wrap:anywhere}}th{{background:#f4f7fc}}.scroll{{overflow:auto}}pre{{font-size:12px;white-space:pre-wrap;max-height:350px;overflow:auto}}a,summary{{color:#2459c6}}summary{{cursor:pointer}}.conflict{{color:#b42318}}.review{{color:#9a6200}}.unassessed{{color:#63758b}}.pass{{color:#18774b}}@media(max-width:760px){{body{{padding:14px}}.cards{{grid-template-columns:1fr}}}}@media print{{body{{padding:0}}details{{break-inside:avoid}}}}</style>
<main><p class="muted">DBCI-QC · {e(result['rule_version'])}</p><h1>{tr('数据集质检报告','Dataset QC report')}</h1><p>{e(result['scope'])}</p><p><b>{s['present_files']}/{s['expected_files']}</b> {tr('文件','files')} · <b>{s['subjects']}</b> {tr('人','subjects')} · <b>{s['records']}</b> {tr('份记录','recordings')} · <b>{s['groups']}</b> {tr('个比较组','comparison groups')}</p>
<div class="cards">{cards}</div><p class="muted">{tr('冲突、待复核、未评分别记录，不折算为脑电信号质量分。','Conflicts, review items and unassessed checks are separate; no signal-quality score is assigned.')}</p>
<section><h2>{tr('按个体查看','By subject')}</h2><div class="scroll"><table><tr>{''.join('<th>'+v+'</th>' for v in (["Subject","Recordings","Sessions","Conflicts","Review","Unassessed"] if en else ['个体','记录','会话','冲突','待复核','未评']))}</tr>{subjects}</table></div></section>
<section><h2>{tr('比较组','Comparison groups')}</h2><div class="scroll"><table><tr>{''.join('<th>'+v+'</th>' for v in (["Group","Subjects","Recordings","Channel counts"] if en else ['比较组','人数','记录数','通道数']))}</tr>{groups}</table></div></section>
<section><h2>{tr('检查明细','Check details')}</h2><div class="scroll"><table><tr>{''.join('<th>'+v+'</th>' for v in (["Module","Check","Status","Target","Evidence"] if en else ['模块','检查项','状态','对象','依据']))}</tr>{''.join(checks)}</table></div></section>
<p class="muted">{tr('范围：文件与配套表一致性；不证明真实身份、信号质量或临床适用性。','Scope: consistency of files and accompanying tables, not identity, signal quality or clinical suitability.')}<br>{e(result['checked_at'])}</p></main></html>'''


def run_dataset_qc(root, manifest, output_dir, *, progress=None):
    if Path(root).is_symlink() or Path(output_dir).is_symlink(): raise ValueError('不能使用目录符号链接。')
    source, output=Path(root).resolve(),Path(output_dir).resolve()
    if source==output or source in output.parents or output in source.parents: raise ValueError('输出须与来源分开。')
    if output.exists(): raise FileExistsError('输出目录已存在，请新建。')
    frozen=json.loads(json.dumps(manifest,ensure_ascii=False,allow_nan=False))
    result=evaluate_dataset(source,frozen,progress=progress)
    result['expectations_sha256']=__import__('hashlib').sha256(json.dumps(frozen,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    output.mkdir(parents=True,exist_ok=False)
    for name,value in [('result.json',result),('expectations.json',frozen)]:
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for lang,name in [('zh-CN','report.html'),('en','report.en.html')]:
        (output/name).write_text(render_dataset_report(result,lang),encoding='utf-8')
    return result
