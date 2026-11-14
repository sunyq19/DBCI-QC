"""Readable dataset report over frozen evidence, separate from the editor UI."""
from collections import defaultdict
from html import escape
from pathlib import Path
import re


def render(data, language='zh-CN'):
    web = Path(__file__).with_name('web')
    css = (web / 'ui-tokens.css').read_text() + '\n' + (web / 'dataset-report.css').read_text()
    en = language == 'en'
    t = lambda zh, eng: eng if en else zh
    esc = lambda value: escape(str('—' if value is None else value), quote=True)
    number = lambda value: f'{value:,.2f}'.rstrip('0').rstrip('.') if isinstance(value, (int, float)) else '—'
    label = lambda row: row.get('label_en', row.get('label', row.get('code'))) if en else row.get('label', row.get('code'))
    package = esc(data['package_id']); summary = data['summary']; records = data['records']
    example = data.get('example') or {}
    title = (example.get('label_en') if en else example.get('label')) or data['label']
    run_name = (data.get('dataset_job') or {}).get('run_name')
    source_title = title
    title = run_name or title
    description = (example.get('description_en') if en else example.get('description')) or ''
    groups = data.get('attention_groups', [])
    present = (summary.get('file_counts') or {}).get('present', 0)
    dataset_done = summary['dataset_assessed']
    metadata_only = dataset_done and bool(records) and all(r['signal']['status']=='not_run' for r in records)
    durations = [(r.get('display') or {}).get('duration_seconds') for r in records]
    total_duration = sum(durations) if durations and all(isinstance(v, (int, float)) for v in durations) else None
    formats = ' / '.join(sorted({r.get('display', {}).get('format') for r in records if r.get('display', {}).get('format')}))
    sources = data.get('source') or {}
    source_rows = sources.get('sources', [sources]) if isinstance(sources, dict) else []
    source_links = []
    for source in source_rows:
        if not isinstance(source, dict): continue
        url = source.get('url', '')
        name = source.get('name') or source.get('dataset') or url
        if re.match(r'^https?://[^\s<>]+$', url):
            source_links.append(f'<a href="{esc(url)}" rel="noreferrer">{esc(name)}</a>')
    files_value = f'{present} / {summary["expected_files"]}' if dataset_done else '—'
    facts = [(summary['subjects'], t('个体', 'Subjects')), (len(records), t('记录', 'Recordings')),
             (number(total_duration) + ' s', t('样本总时长', 'Sample duration')),
             (formats or '—', t('文件格式', 'Formats'))]
    if metadata_only: facts=facts[:2]+[(files_value,t('文件与清单相符','Files match inventory'))]
    fact_html = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for v, k in facts)
    primary = t(f'{summary["reported"]} 份信号报告已生成', f'{summary["reported"]} signal reports available')
    if metadata_only: primary=t('数据集资料检查已完成','Dataset metadata checks completed')
    if groups: primary += t(f' · {len(groups)} 类资料问题需核对', f' · {len(groups)} metadata issues to review')
    elif dataset_done: primary += t(' · 已核对资料未发现不一致', ' · No mismatches in assessed metadata')
    else: primary += t(' · 资料尚未检查', ' · Metadata not yet checked')

    def module_outcome(mid):
        counts = data['module_counts'].get(mid, {})
        if not counts: return t('未检查', 'Not checked')
        problems = counts.get('conflict', 0) + counts.get('review', 0)
        if problems: return t(f'{problems} 项需核对', f'{problems} checks need review')
        if counts.get('pass'): return t(f'{counts["pass"]} 项一致', f'{counts["pass"]} checks agree')
        return t('配套资料不足', 'Insufficient companion metadata')

    check_rows = [
        ('D01', t('文件完整性', 'File completeness'), t('清单中的文件是否齐全，记录能否读取', 'Expected files present; recordings readable'),
         (t(f'{files_value} 个文件与清单相符', f'{files_value} files match the inventory') if dataset_done else t('未检查', 'Not checked'))),
        ('D02', t('个体资料核对', 'Within-subject metadata'), t('编号、通道表、单位、采样率和事件时间', 'Identifiers, channel table, units, sample rates and event timing'), module_outcome('D02')),
        ('D03', t('同组记录比较', 'Within-group comparison'), t('按声明的比较组核对；不同来源、模态或 AP/LF 不混比', 'Compare declared groups; keep sources, modalities and AP/LF separate'), module_outcome('D03')),
        ('M03–M07', t('信号检查', 'Signal checks'),
         t('按模态和所选方案检查完整性、频谱、通道及伪迹', 'Integrity, spectra, channels and artifacts according to modality and selected methods'),
         t(f'{summary["reported"]} / {len(records)} 份报告', f'{summary["reported"]} / {len(records)} reports'))]
    if metadata_only:check_rows=check_rows[:-1]
    check_html = ''.join(f'<tr><th><small>{esc(mid)}</small>{esc(name)}</th><td>{esc(purpose)}</td><td class="outcome">{esc(outcome)}</td></tr>' for mid, name, purpose, outcome in check_rows)

    attention = []
    for group in groups:
        matching = [c for c in data['checks'] if c['id'] in group['check_ids']]
        duplicates = sorted({n for c in matching for n in (c.get('observed') or {}).get('duplicate_names', [])})
        detail = (' · '.join(f'{v["file_unit"]} / {v["table_unit"]}' for v in group.get('unit_labels', [])))
        if duplicates: detail = t('重复名称：', 'Repeated names: ') + ', '.join(duplicates)
        heading = group['title_en'] if en else group['title']
        body = group['meaning_en'] if en else group['meaning']
        step = group['next_step_en'] if en else group['next_step']
        attention.append(f'<article class="finding"><h3>{esc(heading)} <span>{group["record_count"]} {t("份记录", "recordings")}</span></h3><p>{esc(body)} {esc(detail)}</p><p class="secondary">{esc(step)}</p></article>')

    record_rows = []
    for record in records:
        if metadata_only:
            counts=record['checks'];needs=counts.get('conflict',0)+counts.get('review',0)
            outcome=t('有资料项需核对','Metadata needs review') if needs else t('核对结果见明细','See check details')
            record_rows.append(f'<tr><th>{esc(record["subject"])}</th><td>{esc(record["id"])}</td><td>{esc(record["modality"])}</td><td>{outcome}</td></tr>')
            continue
        display = record.get('display', {}); sig = record['signal']; url = sig.get('report_url', '') or ''
        valid_link = bool(re.fullmatch('/api/v1/jobs/[a-f0-9]{32}/report', url))
        button = (f'<a class="report-link" href="{esc(url)}?lang={esc(language)}">{t("查看报告", "View report")}</a>' if valid_link
                  else f'<span class="secondary">{t("尚无报告", "No report yet")}</span>')
        status = {'source_mismatch': t('来源不一致，需复验', 'Source mismatch; rerun'),
                  'failed': t('检查失败', 'Check failed'), 'report_unavailable': t('报告不可用', 'Report unavailable'),
                  'not_run': t('未运行', 'Not run')}.get(sig['status'])
        pieces = []
        if status: pieces.append(status)
        elif display.get('summary_available'):
            if record['modality'] == 'scalp_eeg':
                pieces.append(t('检出窄带成分' if display.get('line_detected') else '未检出窄带候选',
                                'Narrowband candidates detected' if display.get('line_detected') else 'No narrowband candidates detected'))
                pieces.append(t(f'高频突发 {display.get("hf_candidates", 0)} 段', f'{display.get("hf_candidates", 0)} high-frequency intervals'))
            else:
                if display.get('nonfinite_samples') is not None:
                    pieces.append(t(f'NaN / Inf {display["nonfinite_samples"]} 点', f'{display["nonfinite_samples"]} NaN / Inf samples'))
                if display.get('psd_channels'): pieces.append(t(f'PSD {display["psd_channels"]} 道', f'PSD: {display["psd_channels"]} channels'))
        else: pieces.append(t('结果见逐份报告', 'See recording report'))
        coverage = t('已检查样本全长', 'Full sample checked') if sig.get('full_duration_computed') else t('检查范围见报告', 'See report for coverage')
        rates = ', '.join(number(rate) for rate in display.get('rates_hz', []))
        info = ' · '.join(filter(None, [display.get('format'), (t(f'{display["channels"]} 道', f'{display["channels"]} channels') if display.get('channels') else ''), rates + ' Hz' if rates else '', number(display.get('duration_seconds')) + ' s']))
        score = sig.get('score')
        scored = f'<strong>{t("本方案评分", "Workflow score")} {score:.2f} / 100</strong><small>{esc(" · ".join(pieces))}</small>' if not status and isinstance(score, (int, float)) else esc(' · '.join(pieces))
        record_rows.append(f'<tr><th>{esc(record["subject"])}<small>{esc(record["id"])}</small></th><td>{esc(info)}<small>{esc(coverage)}</small></td><td>{scored}</td><td>{button}</td></tr>')

    # Unknowns remain in the audit, grouped by check type instead of amplified
    # into a wall of warnings for every record and downstream dependency.
    missing = defaultdict(list)
    for check in data['findings']:
        if check['status'] == 'unassessed': missing[check['code']].append(check)
    missing_rows = ''.join(f'<tr><th>{esc(label(rows[0]))}</th><td>{esc(rows[0].get("message"))}</td><td>{len(rows)}</td></tr>' for rows in missing.values())
    optional = f'<details class="disclosure"><summary>{t("本次未核对的资料", "Metadata not assessed")} · {len(missing)} {t("类", "types")}</summary><p class="secondary">{t("包括缺少配套表、无法唯一匹配或没有同组重复记录的检查；未计为通过，也不等于信号质量差。", "Includes absent companion tables, ambiguous mappings and groups without repeated recordings. These checks are not passes and do not imply poor signal quality.")}</p><div class="table-scroll" tabindex="0" role="region" aria-label="{t("未核对资料", "Unassessed metadata")}"><table><tbody>{missing_rows}</tbody></table></div></details>' if missing else ''
    bids=data.get('format_validation',{}).get('bids',{})
    bids_rows=[c for c in data['checks'] if c['code']=='bids_validator' and isinstance(c.get('observed'),dict)]
    bids_section=''
    if bids_rows:
        errors=sum(c['observed']['occurrences'] for c in bids_rows if c['observed']['severity']=='error')
        warnings=sum(c['observed']['occurrences'] for c in bids_rows if c['observed']['severity']=='warning')
        rows=''
        for c in bids_rows:
            detail=''.join(f'<tr><td>{esc(i.get("location"))}</td><td>{esc(i.get("subCode") or i.get("message") or i.get("code"))}</td></tr>' for i in c['observed']['details'])
            rows+=f'<details class="disclosure"><summary>{esc(c["message"])}</summary><div class="table-scroll"><table><tbody>{detail}</tbody></table></div></details>'
        bids_section=f'<section id="bids"><h2>{t("BIDS 格式校验","BIDS format validation")}</h2><p>{t(f"{errors} 处错误 · {warnings} 条建议，按 {len(bids_rows)} 类规则归并。",f"{errors} errors · {warnings} recommendations, grouped into {len(bids_rows)} rule categories.")}</p><p class="secondary">{t("这里检查文件组织与配套说明，不等于波形质量差；建议不等于错误。", "These findings concern files and metadata; recommendations are not errors or signal-quality failures.")}</p><p class="secondary">BIDS {esc(bids.get("declared_bids_version","—"))} · Validator {esc(bids.get("version","—"))}</p>{rows}</section>'
    audit_rows = ''.join(f'<tr><td>{esc(c["module"])}</td><th>{esc(label(c))}</th><td>{esc(c["target"])}</td><td>{esc(c["status"])}</td><td>{esc(c.get("message"))}</td></tr>' for c in data['checks'])
    group_rows = ''
    for group in data['comparison_groups']:
        fields = [t(zh, eng) for key, zh, eng in [('same_channels', '通道', 'channels'), ('same_rates', '采样率', 'sample rates'), ('same_units', '单位', 'units'), ('same_reference', '参考', 'reference')] if group.get(key)]
        field_text = ', '.join(fields) or t('仅记录分组', 'Group only')
        group_rows += f'<li><strong>{esc(group.get("label", group["id"]))}</strong> · {esc(field_text)}</li>'
    scope_note = t('仅代表这些公开样本；不代表原始研究的完整数据集。', 'These public samples do not represent the complete upstream study.') if example else ''
    method_note = t('逐份显示本方案评分，分项与权重见报告。不同模态或检查方案的分数不直接比较；未评项目不计入。', 'Scores belong to each recording and workflow; see the report for components and weights. Do not compare unlike modalities or workflows. Unassessed items are excluded.') if any(r['signal'].get('score') is not None for r in records) else t('各模态按适用方法检查，结果见逐份报告；未评项目不计为通过。', 'Each modality uses applicable methods; see recording reports. Unassessed items are not passes.')
    recording_title=t('逐份结果','Recording results')
    recording_headers=[t('个体 / 记录','Subject / recording'),t('检查范围','Scope'),t('信号结果摘要','Signal findings'),'']
    if metadata_only:
        recording_title=t('纳入检查的记录','Included recordings')
        recording_headers=[t('个体','Subject'),t('记录','Recording'),t('模态','Modality'),t('资料核对','Metadata checks')]
        method_note=t('本次仅核对文件与配套资料，未运行逐份信号检查。','This run checked files and metadata; individual signal checks were not requested.')
    recording_heads=''.join(f'<th>{esc(h)}</th>' for h in recording_headers)
    return f'''<!doctype html><html lang="{esc(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · {t('数据集报告','Dataset report')}</title><style>{css}</style><script src="/dataset-report.js" defer></script></head><body class="dataset-report">
+<header class="report-header"><a href="/#demo-reports">← {t('质控台','Workbench')}</a><span>{t('数据集报告','Dataset report')}</span><nav><a href="?lang={'zh-CN' if en else 'en'}{('&amp;job=' + esc(data['dataset_job']['id'])) if data.get('dataset_job') else ''}">{'中文' if en else 'EN'}</a><button id="print-report">{t('打印 / PDF','Print / PDF')}</button></nav></header>
+<main><div class="report-title"><div><p class="eyebrow">DBCI-QC / {t('公开样本示例' if example else '数据集检查', 'Public sample' if example else 'Dataset QC')}</p><h1>{esc(title)}</h1><p class="secondary">{esc(source_title) + ' · ' if run_name else ''}{esc(description)}</p></div></div>
+<dl class="dataset-facts">{fact_html}</dl><p class="report-conclusion">{esc(primary)}</p>
+<section id="checks"><h2>{t('检查了什么','Checks performed')}</h2><div class="table-scroll" tabindex="0" role="region" aria-label="{t('检查结果', 'Check results')}"><table class="check-table"><tbody>{check_html}</tbody></table></div></section>
+{('<section id="findings"><h2>'+t('需要核对','Needs review')+'</h2>'+''.join(attention)+'</section>') if attention else ''}
+{bids_section}<section id="recordings"><h2>{recording_title} <span>{len(records)}</span></h2><p class="secondary">{esc(method_note)}</p><div class="table-scroll" tabindex="0" role="region" aria-label="{t('逐份结果', 'Recording results')}"><table class="record-table"><thead><tr>{recording_heads}</tr></thead><tbody>{''.join(record_rows)}</tbody></table></div></section>
+{optional}<details class="disclosure"><summary>{t('检查范围与来源','Scope and sources')}</summary><p>{esc(data['scope'])}</p><p>{esc(scope_note)}</p><p>{' · '.join(source_links)}</p><h3>{t('比较组及核对字段','Groups and compared fields')}</h3><ul>{group_rows}</ul><p>{t('未计算跨个体或跨模态总分；本页未进行人工核验。','No score is pooled across subjects or modalities. This page is not a human review.')}</p></details>
+<details class="disclosure"><summary>{t('完整检查记录','Full audit trail')}</summary><div class="table-scroll" tabindex="0" role="region" aria-label="{t('检查记录', 'Audit trail')}"><table><tbody>{audit_rows}</tbody></table></div><p class="secondary">{t('清单指纹','Manifest fingerprint')}: {esc(data['manifest_hash'])}<br>{t('检查任务','Dataset run')}: {esc((data.get('dataset_job') or {}).get('id'))}</p></details>
+<footer>{t('依据已保存的检查结果；打开页面不会重新运行算法。','Based on saved checks; opening this page does not rerun the algorithms.')} <a href="/datasets?package={package}">{t('进入检查工作区','Open dataset workspace')}</a></footer></main></body></html>'''.replace('\n+', '\n')
