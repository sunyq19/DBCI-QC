"""Descriptive voltage report from saved window summaries, without EEG scoring."""
from html import escape
import json
from pathlib import Path
from urllib.parse import quote


def render(store, identifier, language='zh-CN'):
    from dataset_overview import recording_display
    en = language == 'en'; t = lambda a,b:b if en else a
    esc = lambda value:escape(str(value if value is not None else '—'), quote=True)
    number = lambda value: f'{value:,.3f}'.rstrip('0').rstrip('.') if isinstance(value, (int,float)) else '—'
    root = store.root/'jobs'/identifier; artifacts=root/'artifacts'; job=store.job(identifier)
    request=json.loads((root/'request.json').read_text()); item=request['input']
    window_path=artifacts/'window-results.json'
    if not window_path.is_file() or window_path.stat().st_size>8*1024*1024: return None
    windows=json.loads(window_path.read_text())
    coverage_path=artifacts/'coverage.json'
    if not coverage_path.is_file() or coverage_path.stat().st_size>8*1024*1024: return None
    coverage=json.loads(coverage_path.read_text())
    info=recording_display(store,job,item)
    web=Path(__file__).with_name('web')
    css=(web/'ui-tokens.css').read_text()+'\n'+(web/'dataset-report.css').read_text()
    url=lambda name:f'/api/v1/jobs/{identifier}/artifacts/{quote(name)}'
    modality={'ecog':'ECoG','seeg':'sEEG','extracellular':'Neuropixels'}.get(item.get('modality'),'Electrophysiology')
    duration=coverage.get('completed_seconds')
    facts=[(modality,t('模态','Modality')),(info['channels'],t('分析通道','Channels')),
           (number(duration)+' s',t('已计算时长','Computed duration')),(', '.join(number(r) for r in info['rates_hz'])+' Hz',t('采样率','Sample rate'))]
    fact_html=''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for v,k in facts)
    nonfinite=info.get('nonfinite_samples')
    psd=info.get('psd_channels')
    descriptions=[m.get('summary',{}) for w in windows for m in w.get('modules',[]) if m['id']=='M05']
    contacts=min((s.get('described_channel_count',0) for s in descriptions), default=0)
    outcome=t('数值与信号统计已生成','Numerical and signal measurements available')
    if nonfinite: outcome=t(f'发现 {nonfinite} 个非有限值，请定位复核', f'{nonfinite} non-finite samples detected; review their locations')
    if coverage.get('unexecuted_seconds',0) or coverage.get('failed_seconds',0): outcome=t('部分时段未完成检查，见执行记录','Some intervals were not checked; see execution details')
    rows=[(t('数值完整性','Numerical integrity'),t('NaN / Inf 等不能计算的数值','Non-finite samples such as NaN / Inf'), t(f'{number(nonfinite)} 个样本',f'{number(nonfinite)} samples')),
          (t('频谱与干扰','Spectra and interference'),t('逐通道功率谱；在可测频带内测量工频邻域','Per-channel PSD; line-frequency measurements within the available band'),t(f'{psd} 道已计算',f'{psd} channels measured')),
          (t('接触点统计','Contact statistics'),t('各接触点的幅度、RMS 与峰峰值','Amplitude, RMS and peak-to-peak voltage by contact'),t(f'{contacts} 道已计算',f'{contacts} contacts measured'))]
    table=''.join(f'<tr><th>{esc(name)}</th><td>{esc(method)}</td><td class="outcome">{esc(value)}</td></tr>' for name,method,value in rows)
    score_html=''
    score_file=artifacts/'method-scores.json'
    if score_file.is_file() and score_file.stat().st_size<8*1024*1024:
        scored=json.loads(score_file.read_text());score=scored.get('project_score')
        if score:
            total_weight=sum(max(0,r.get('weight',0)) for r in score['components'])
            score_rows=''.join(f'<tr><th>{esc(r["name"])}</th><td>{number(r["value"])}</td><td>{number(100*r.get("weight",0)/total_weight) if total_weight else 0}%</td><td>{esc(r["reason"])}</td></tr>' for r in score['components'])
            score_html=f'<section><h2>{t("项目自定义评分", "Project score")} · {number(score["value"])}</h2><p>{esc(score.get("missing_reason") or score["formula"])}</p><div class="table-scroll" tabindex="0" role="region" aria-label="{t("计分明细", "Score details")}"><table><thead><tr><th>{t("方法", "Method")}</th><th>/ 100</th><th>{t("计分比例", "Share")}</th><th>{t("依据", "Basis")}</th></tr></thead><tbody>{score_rows}</tbody></table></div><details class="disclosure"><summary>{t("评分版本","Scoring version")}</summary><p>{esc(score["version"])} · {esc(score["configuration_id"])}</p></details></section>'
    # Preview the already saved first-window figure. It is not whole-record evidence.
    first=windows[0] if windows else {};wid=first.get('id','')
    waveform=wid+'--waveform.png'
    preview=''
    if (artifacts/waveform).is_file():
        preview=f'<section><h2>{t("波形预览", "Waveform preview")}</h2><p class="secondary">{t("首段已保存波形；不代表全部通道和整份记录，图内标明通道与时间。", "Saved first-window preview; channel and time labels define its scope, not the entire recording.")}</p><img alt="{t("首段电压波形", "First-window voltage traces")}" src="{url(waveform)}" style="width:100%;height:auto"></section>'
    stats=''
    statsfile=artifacts/(wid+'--M05_channel_description.json')
    if statsfile.is_file() and statsfile.stat().st_size<8*1024*1024:
        channels=json.loads(statsfile.read_text()).get('channels',[])
        stats_rows=''.join(f'<tr><th>{esc(c.get("channel_name"))}</th><td>{number(c.get("rms_volts")*1e6 if isinstance(c.get("rms_volts"),(int,float)) else None)}</td><td>{number(c.get("peak_to_peak_volts")*1e6 if isinstance(c.get("peak_to_peak_volts"),(int,float)) else None)}</td></tr>' for c in channels[:10])
        stats=f'<details class="disclosure"><summary>{t("接触点测量示例", "Contact measurements")}</summary><p class="secondary">{t("首段前 10 道，保留源通道顺序；用于描述，不按幅度直接判坏。", "First 10 source-ordered channels in the first window; amplitude alone does not establish bad contacts.")}</p><div class="table-scroll" tabindex="0" role="region" aria-label="{t("接触点测量", "Contact measurements")}"><table><thead><tr><th>{t("通道", "Channel")}</th><th>RMS / µV</th><th>{t("峰峰值", "Peak-to-peak")} / µV</th></tr></thead><tbody>{stats_rows}</tbody></table></div><a href="{url(statsfile.name)}">{t("完整测量", "Full measurements")}</a></details>'
    window_rows=''.join(f'<tr><th>{esc(w["id"])}</th><td>{number(w["start_seconds"])}–{number(w["start_seconds"]+w["duration_seconds"])} s</td><td>{esc(w["status"])}</td><td><a href="{url(w["id"]+"--report.html")}">{t("原始分段报告", "Saved window report")}</a></td></tr>' for w in windows)
    note=t('已完成分段的样本已扫描；常值区间的定位明细达到保存上限，完整计数与限制保留在原始证据中。', 'Completed windows were scanned; stored constant-interval locations reached the evidence limit. Total counts and limits remain in the original evidence.') if info.get('candidate_details_truncated') else ''
    return f'''<!doctype html><html lang="{esc(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(item['label'])} · {t('记录报告','Recording report')}</title><style>{css}</style><script src="/dataset-report.js" defer></script></head><body class="dataset-report"><main><p class="eyebrow">DBCI-QC / {esc(modality)}</p><h1>{esc(item['label'])}</h1><dl class="dataset-facts">{fact_html}</dl><p class="report-conclusion">{esc(outcome)}</p><p class="secondary">{t('本报告描述技术质量，不采用头皮 EEG 坏道阈值，不给出临床合格判定或跨模态总分。', 'Technical measurements without scalp-EEG bad-channel thresholds, clinical acceptance decisions or cross-modality scores.')}</p><section><h2>{t('检查结果','Results')}</h2><p><a href="/api/v1/jobs/{identifier}/visualizations">{t('查看通道图表','Channel charts')}</a></p><div class="table-scroll" tabindex="0" role="region" aria-label="{t("检查结果", "Results")}"><table class="check-table"><tbody>{table}</tbody></table></div></section>{score_html}{preview}{stats}<details class="disclosure"><summary>{t('检查范围与执行记录','Scope and execution')}</summary><p>{t('本地文件全长','Local file duration')} {number(info['duration_seconds'])} s · {t('已计算','Computed')} {number(duration)} s · {t('未执行','Not executed')} {number(coverage.get('unexecuted_seconds'))} s · {t('来源间隙','Source gaps')} {number(coverage.get('gap_seconds'))} s</p><p>{esc(note)}</p><p>{t('相邻样本相等可能来自量化；未据此直接剔除通道。所有候选与方法状态保留，缺项不计为通过。', 'Equal adjacent values can reflect quantization; contacts are not excluded on this basis. Candidate evidence and method states are preserved; missing checks are not passes.')}</p><div class="table-scroll" tabindex="0" role="region" aria-label="{t("分段记录", "Window records")}"><table><tbody>{window_rows}</tbody></table></div><p><a href="{url('coverage.json')}">{t('覆盖明细','Coverage')}</a> · <a href="{url('window-results.json')}">{t('方法与结果','Methods and results')}</a> · <a href="{url('report.html')}">{t('运行时原始报告','Original run report')}</a></p></details><footer><span>DBCI-QC</span><button id="print-report">{t('打印 / PDF','Print / PDF')}</button></footer></main></body></html>'''
