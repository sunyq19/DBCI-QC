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
    description = (example.get('description_en') if en else example.get('description')) or ''
    groups = data.get('attention_groups', [])
    present = (summary.get('file_counts') or {}).get('present', 0)
    dataset_done = summary['dataset_assessed']
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
    fact_html = ''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for v, k in facts)
    primary = t(f'{summary["reported"]} 份信号报告已生成', f'{summary["reported"]} signal reports available')
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
         t('EEG：完整性、频谱、通道及伪迹；其他模态：完整性、频谱和接触点统计', 'EEG: integrity, spectra, channels and artifacts. Other modalities: integrity, spectra and contact statistics'),
         t(f'{summary["reported"]} / {len(records)} 份报告', f'{summary["reported"]} / {len(records)} reports'))]
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
        record_rows.append(f'<tr><th>{esc(record["subject"])}<small>{esc(record["id"])}</small></th><td>{esc(info)}<small>{esc(coverage)}</small></td><td>{esc(" · ".join(pieces))}</td><td>{button}</td></tr>')

    # Unknowns remain in the audit, grouped by check type instead of amplified
    # into a wall of warnings for every record and downstream dependency.
    missing = defaultdict(list)
    for check in data['findings']:
        if check['status'] == 'unassessed': missing[check['code']].append(check)
    missing_rows = ''.join(f'<tr><th>{esc(label(rows[0]))}</th><td>{esc(rows[0].get("message"))}</td><td>{len(rows)}</td></tr>' for rows in missing.values())
    optional = f'<details class="disclosure"><summary>{t("本次未核对的资料", "Metadata not assessed")} · {len(missing)} {t("类", "types")}</summary><p class="secondary">{t("包括缺少配套表、无法唯一匹配或没有同组重复记录的检查；未计为通过，也不等于信号质量差。", "Includes absent companion tables, ambiguous mappings and groups without repeated recordings. These checks are not passes and do not imply poor signal quality.")}</p><div class="table-scroll"><table><tbody>{missing_rows}</tbody></table></div></details>' if missing else ''
    audit_rows = ''.join(f'<tr><td>{esc(c["module"])}</td><th>{esc(label(c))}</th><td>{esc(c["target"])}</td><td>{esc(c["status"])}</td><td>{esc(c.get("message"))}</td></tr>' for c in data['checks'])
    group_rows = ''
    for group in data['comparison_groups']:
        fields = [t(zh, eng) for key, zh, eng in [('same_channels', '通道', 'channels'), ('same_rates', '采样率', 'sample rates'), ('same_units', '单位', 'units'), ('same_reference', '参考', 'reference')] if group.get(key)]
        field_text = ', '.join(fields) or t('仅记录分组', 'Group only')
        group_rows += f'<li><strong>{esc(group.get("label", group["id"]))}</strong> · {esc(field_text)}</li>'
    scope_note = t('仅代表这些公开样本；不代表原始研究的完整数据集。', 'These public samples do not represent the complete upstream study.') if example else ''
    non_eeg = any(r['modality'] != 'scalp_eeg' for r in records)
    method_note = t('ECoG、sEEG、Neuropixels 当前提供技术描述，不套用头皮 EEG 的判坏阈值；相邻恒值可能来自量化，不直接判为坏道。', 'ECoG, sEEG and Neuropixels currently receive technical measurements without scalp-EEG rejection thresholds. Adjacent equal values can reflect quantization, not bad channels.') if non_eeg else t('工频与伪迹是待复核线索。缺少参考构型或辅助导联时，对应检查不会自动判为通过。', 'Interference and artifact detections are review candidates. Checks requiring unknown references or absent auxiliary channels are not counted as passes.')
    return f'''<!doctype html><html lang="{esc(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · {t('数据集报告','Dataset report')}</title><style>{css}</style><script src="/dataset-report.js" defer></script></head><body class="dataset-report">
+<header class="report-header"><a href="/#demo-reports">← {t('质控台','Workbench')}</a><span>{t('数据集报告','Dataset report')}</span><nav><a href="?lang={'zh-CN' if en else 'en'}{('&amp;job=' + esc(data['dataset_job']['id'])) if data.get('dataset_job') else ''}">{'中文' if en else 'EN'}</a><button id="print-report">{t('打印 / PDF','Print / PDF')}</button></nav></header>
+<main><div class="report-title"><div><p class="eyebrow">DBCI-QC / {t('公开样本示例' if example else '数据集检查', 'Public sample' if example else 'Dataset QC')}</p><h1>{esc(title)}</h1><p class="secondary">{esc(description)}</p></div></div>
+<dl class="dataset-facts">{fact_html}</dl><p class="report-conclusion">{esc(primary)}</p>
+<section id="checks"><h2>{t('检查了什么','Checks performed')}</h2><div class="table-scroll"><table class="check-table"><tbody>{check_html}</tbody></table></div></section>
+{('<section id="findings"><h2>'+t('需要核对','Needs review')+'</h2>'+''.join(attention)+'</section>') if attention else ''}
+<section id="recordings"><h2>{t('逐份结果','Recording results')} <span>{len(records)}</span></h2><p class="secondary">{esc(method_note)}</p><div class="table-scroll"><table class="record-table"><thead><tr><th>{t('个体 / 记录','Subject / recording')}</th><th>{t('检查范围','Scope')}</th><th>{t('信号结果摘要','Signal findings')}</th><th></th></tr></thead><tbody>{''.join(record_rows)}</tbody></table></div></section>
+{optional}<details class="disclosure"><summary>{t('检查范围与来源','Scope and sources')}</summary><p>{esc(data['scope'])}</p><p>{esc(scope_note)}</p><p>{' · '.join(source_links)}</p><h3>{t('比较组及核对字段','Groups and compared fields')}</h3><ul>{group_rows}</ul><p>{t('未计算跨个体或跨模态总分；本页未进行人工核验。','No score is pooled across subjects or modalities. This page is not a human review.')}</p></details>
+<details class="disclosure"><summary>{t('完整检查记录','Full audit trail')}</summary><div class="table-scroll"><table><tbody>{audit_rows}</tbody></table></div><p class="secondary">{t('清单指纹','Manifest fingerprint')}: {esc(data['manifest_hash'])}<br>{t('检查任务','Dataset run')}: {esc((data.get('dataset_job') or {}).get('id'))}</p></details>
+<footer>{t('依据已保存的检查结果；打开页面不会重新运行算法。','Based on saved checks; opening this page does not rerun the algorithms.')} <a href="/datasets?package={package}">{t('进入检查工作区','Open dataset workspace')}</a></footer></main></body></html>'''.replace('\n+', '\n')
