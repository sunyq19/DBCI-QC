"""Workbench adapter for result snapshots. Source data are not reread on page polling."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

from ephys_qc.dataset_qc.overview import aggregate_overview
from package_jobs import fingerprint


def source_match(item, source_root, dataset_result):
    if not dataset_result: return 'unverified'
    files = {f['path']: f for f in dataset_result['inventory']['files']}
    expected = item.get('expected_source_files') or []
    if not expected: return 'unverified'
    for file in expected:
        try: name = Path(file['path']).relative_to(Path(source_root)).as_posix()
        except (ValueError, TypeError): return 'mismatch'
        actual = files.get(name)
        if not actual or not actual.get('sha256'): return 'mismatch'
        if actual['sha256'] != file.get('sha256'): return 'mismatch'
    return 'matched'


def build_overview(store, package_id, job_id=None):
    package, current = store.packages._plan(package_id)
    manifest, dataset_result, dataset_job = current, None, None
    root = package['root']
    with store.packages.lock:
        jobs = copy.deepcopy(list(store.packages.jobs.values()))
    if job_id:
        dataset_job = store.packages.get(job_id)
        if dataset_job['package_id'] != package_id: raise ValueError('报告不属于当前数据集。')
        request = json.loads((store.packages.root / job_id / 'request.json').read_text())
        manifest, root = request['expectations'], request['source_root']
    else:
        eligible = [j for j in jobs if j['package_id'] == package_id and j['manifest_hash'] == fingerprint(current)]
        dataset_job = max(eligible, key=lambda j: j['created_at']) if eligible else None
    if dataset_job and dataset_job['status'] == 'completed':
        dataset_result = json.loads(store.packages.artifact(dataset_job['id'], 'result.json').read_text())
        request = json.loads((store.packages.root / dataset_job['id'] / 'request.json').read_text())
        root = request['source_root']
    manifest_hash = fingerprint(manifest)
    with store.lock:
        signal_jobs = copy.deepcopy(list(store.jobs.values()))
    selected = {}
    for job in signal_jobs:
        context = job.get('dataset_context') or {}
        if context.get('package_id') != package_id or context.get('manifest_hash') != manifest_hash: continue
        rid = context.get('record_id')
        if rid not in selected or job['created_at'] > selected[rid]['created_at']: selected[rid] = job
    signals = {}
    for rid, job in selected.items():
        signal = {'job': job}
        try:
            item = json.loads((store.root / 'jobs' / job['id'] / 'request.json').read_text())['input']
            signal['source_status'] = source_match(item, root, dataset_result)
            if job['status'] == 'completed': signal['result'] = store.result(job['id'], compact=True)
        except (OSError, ValueError, KeyError, TypeError):
            signal['result_error'] = True
        signals[rid] = signal
    result = aggregate_overview(manifest, dataset_job, dataset_result, signals)
    result.update(package_id=package_id, label=package['label'], manifest_hash=manifest_hash,
                  current_manifest=manifest_hash == fingerprint(current), generated_at=datetime.now(timezone.utc).isoformat(),
                  result_basis='saved_source_fingerprints', signal_jobs=[j['id'] for j in selected.values()])
    return result


def render_overview(data, language='zh-CN'):
    """Self-contained, printable export of the current summary snapshot."""
    from html import escape
    en=language=='en'
    t=lambda a,b:b if en else a
    esc=lambda x:escape(str(x if x is not None else '—'),quote=True)
    labels={'not_run':t('未运行','Not run'),'completed':t('已生成报告','Report generated'),
            'running':t('运行中','Running'),'queued':t('排队中','Queued'),'failed':t('失败','Failed'),
            'interrupted':t('中断','Interrupted'),'cancelled':t('已取消','Cancelled'),
            'source_mismatch':t('来源不一致，需复验','Source mismatch; rerun required'),
            'report_unavailable':t('报告不可用','Report unavailable')}
    def signal(row):
        s=row['signal'];text=labels.get(s['status'],s['status'])
        if s.get('full_duration_computed'):text+=t(' · 整段已计算',' · Full duration computed')
        elif s.get('scope')=='window':text+=t(' · 片段',' · Window only')
        if s.get('incomplete_modules'):text+=t(' · 部分项目未评',' · Some checks unassessed')
        return text
    def score(row):
        s=row['signal'];v=s.get('score')
        text=f'{v:.2f}' if v is not None else '—'
        parts='; '.join(f"{p.get('name',p.get('id',''))}: {p['value']:.2f}" if p.get('value') is not None else f"{p.get('name','')}: —" for p in s.get('components',[]))
        return esc(text)+(f'<small>{esc(parts)} · {esc(s.get("score_version"))}</small>' if parts else '')
    summary=data['summary'];files=summary['file_counts'];groups=data.get('attention_groups',[])
    affected={rid for g in groups for rid in g['record_ids']}
    counts=(f"{files.get('present',0)}/{summary['expected_files']}" if files is not None else t('未检查','Not checked'))
    cards=[(counts,t('文件与清单相符','Files match inventory')),
           (len(affected) if summary['dataset_assessed'] else '—',t('记录需核对资料','Recordings needing review')),
           (f"{summary['reported']}/{summary['records']}",t('信号报告','Signal reports'))]
    card_html=''.join(f'<div><strong>{esc(v)}</strong><span>{esc(k)}</span></div>' for v,k in cards)
    attention=''.join(f'<article class="attention"><h3>{esc(g["title_en"] if en else g["title"])} · {esc(g["record_count"])} {t("份记录","recordings")}</h3><p>{esc(g["meaning_en"] if en else g["meaning"])}</p><p>{esc(g["next_step_en"] if en else g["next_step"])}</p><small>{t("建议核对人","Suggested reviewer")}: {esc(g["owner_en"] if en else g["owner"])}</small></article>' for g in groups)
    rows=''.join(f'<tr><td>{esc(r["subject"])}</td><td>{esc(r["session"])}<small>{esc(r["path"])}</small></td><td>{esc(r["modality"])}<small>{esc(r["processing"])}</small></td><td>{esc(r["checks"].get("conflict",0))} / {esc(r["checks"].get("review",0))} / {esc(r["checks"].get("unassessed",0))}</td><td>{esc(signal(r))}</td><td>{score(r)}</td><td>{esc(r["signal"].get("job_id"))}</td></tr>' for r in data['records'])
    status_labels={'conflict':t('需核对','Needs review'),'review':t('待复核','Review'),'unassessed':t('尚无法判断','Not yet assessable')}
    findings=''.join(f'<tr><td>{esc(c["module"])} · {esc(c["label_en"] if en else c["label"])}</td><td>{esc(status_labels.get(c["status"],c["status"]))}</td><td>{esc(c["target"])}</td><td>{esc(c["message"])}<small>{esc("; ".join(c.get("files",[])))}</small></td></tr>' for c in data['findings'])
    return f'''<!doctype html><html lang="{esc(language)}"><meta charset="utf-8"><title>{esc(data['label'])} · {t('数据集汇总','Dataset summary')}</title>
<style>body{{font:14px/1.6 system-ui,sans-serif;color:#20344f;background:#f5f7fb;margin:0}}main{{max-width:1280px;margin:30px auto;padding:28px;background:white;border-radius:16px}}h1{{font-size:26px}}h2{{font-size:19px;margin-top:30px}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.cards div{{background:#f1f5fd;padding:18px;border-radius:10px}}.cards strong{{display:block;font-size:28px;color:#245ad3}}span,small,.note{{color:#64748b}}small{{display:block;font-size:12px;overflow-wrap:anywhere}}table{{width:100%;border-collapse:collapse;font-size:12px}}td,th{{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #dce5f2;overflow-wrap:anywhere;max-width:300px}}.scroll{{overflow:auto}}a{{color:#245ad3}}@media print{{main{{margin:0;padding:0}}body{{background:white}}a{{display:none}}thead{{display:table-header-group}}tr{{break-inside:avoid}}}}@media(max-width:700px){{main{{padding:16px}}.cards{{grid-template-columns:1fr 1fr}}}}</style>
<main><a href="/datasets?package={esc(data['package_id'])}">{t('返回数据集','Back to dataset')}</a><h1>{esc(data['label'])}</h1><p>{esc(data['scope'])}</p><p class="note">{esc(data['generated_at'])} · {esc(data['schema_version'])}</p><div class="cards">{card_html}</div>
<p class="note">{t('按已保存结果汇总。整段计算覆盖不是质量合格率；分数逐记录列出，不计算跨个体总分。','Summarizes saved results. Execution coverage is not quality. Scores remain per recording; there is no cohort score.')}</p>
{('<h2>'+t('需要处理的事项','Items needing attention')+'</h2>'+attention) if attention else ''}
<h2>{t('记录结果','Recording results')}</h2><div class="scroll"><table><thead><tr>{''.join('<th>'+x+'</th>' for x in [t('个体','Subject'),t('会话 / 记录','Session / recording'),t('模态','Modality'),t('需核对 / 待复核 / 尚无法判断','Needs review / review / unassessed'),t('信号检查','Signal QC'),t('EEG 分数 / 分项','EEG score / components'),t('信号任务','Signal run')])}</tr></thead><tbody>{rows}</tbody></table></div>
<h2>{t('资料检查明细','Dataset findings')}</h2><div class="scroll"><table><thead><tr><th>{t('检查','Check')}</th><th>{t('状态','Status')}</th><th>{t('对象','Target')}</th><th>{t('证据','Evidence')}</th></tr></thead><tbody>{findings or '<tr><td>—</td></tr>'}</tbody></table></div>
<p class="note">{t('清单指纹','Manifest fingerprint')}: {esc(data['manifest_hash'])}<br>{t('资料检查任务','Dataset run')}: {esc((data.get('dataset_job') or {}).get('id'))}<br>{t('仅核对已保存来源指纹，导出时未重新读取原数据。','Saved source fingerprints are compared; raw data are not reread during export.')}</p></main></html>'''
