"""Compact intracranial reports from saved measurements; no new QC decisions."""
from html import escape
import json
import math
from pathlib import Path
from urllib.parse import quote
from ephys_qc.report_presentation import report_section, inline_charts, CSS as SECTION_CSS


def read(path):
    if not path.is_file() or path.stat().st_size > 16*1024**2:
        return {}
    return json.loads(path.read_text())


def measured(value):
    return type(value) in (float, int) and math.isfinite(value)


def scope(root, artifacts):
    windows=read(artifacts/'window-results.json');coverage=read(artifacts/'coverage.json')
    if isinstance(windows,list) and coverage:
        return windows,coverage,'window-results.json'
    selection=read(artifacts/'M02_selection.json')
    recording=selection.get('recording',{})
    duration,start=recording.get('duration_seconds'),recording.get('start_seconds')
    if not measured(duration) or not measured(start):return [],{},''
    # Stream module summaries, without retaining the review index or spectra.
    import ijson
    with (root/'result.json').open('rb') as stream:
        modules=[{k:m[k] for k in ('id','status','summary') if k in m}
                 for m in ijson.items(stream,'modules.item',use_float=True)]
    return ([{'id':'','start_seconds':start,'duration_seconds':duration,'modules':modules}],
            {'completed_seconds':duration},'M02_selection.json')


def collect(artifacts, windows):
    """Aggregate disjoint saved windows by stable contact identity, never labels."""
    contacts = {}; flats = []; done = 0; failures = []; complete_samples = 0; invalid = 0
    extra={key:dict(windows=0,candidates=[],candidate_count=0,measurements=[],reasons=[],artifacts=[])
           for key in ('ieeg_range_plateau','ieeg_group_outliers','fieldtrip_zvalue','ieeg_spectrum_fit','ieeg_mne_lof')}
    for window in windows:
        prefix = window['id']+'--' if window.get('id') else ''
        stats = read(artifacts/(prefix+'M05_channel_description.json'))
        for row in stats.get('channels', []):
            count=row.get('sample_count',0); finite=row.get('finite_sample_count',0)
            complete_samples+=count; invalid+=row.get('nonfinite_sample_count',0)
            identity=row['channel_id']
            contact=contacts.setdefault(identity, {'id':identity,'name':row['channel_name'],
                'source_index':row.get('source_index'), 'squares':0.,'finite':0,'nonfinite':0,
                'p2p':None,'windows':0})
            contact['nonfinite']+=row.get('nonfinite_sample_count',0)
            if measured(row.get('rms_volts')) and finite:
                contact['squares']+=row['rms_volts']**2*finite
                contact['finite']+=finite;contact['windows']+=1
            if measured(row.get('peak_to_peak_volts')):
                contact['p2p']=max(contact['p2p'] or 0,row['peak_to_peak_volts'])
        flat=read(artifacts/(prefix+'M03_mne_amplitude.json'))
        if flat.get('status')=='completed' and flat.get('calculated', True) is True:
            done+=1
            mapping={c['adapter_name']:c for c in flat.get('channel_mapping',[])}
            for candidate in flat.get('candidates',[]):
                name=candidate.get('channel_name')
                c=mapping.get(name,{})
                flats.append({**candidate,'name':c.get('raw_name',name),
                    'channel_id':c.get('channel_id',name), 'window':window,
                    'parameters':flat.get('parameters',{})})
        elif flat:
            failures.append(flat.get('reason') or flat.get('status','未完成'))
        for key,summary in extra.items():
            mid={'ieeg_range_plateau':'M03','ieeg_group_outliers':'M05','fieldtrip_zvalue':'M06','ieeg_spectrum_fit':'M04','ieeg_mne_lof':'M05'}[key]
            filename=prefix+mid+'_'+key+'.json'; payload=read(artifacts/filename)
            if not payload:continue
            summary['artifacts'].append(filename)
            mapping={c['adapter_name']:c for c in payload.get('channel_mapping',[])}
            if payload.get('calculated') and payload.get('status') in {'completed','partial'}:
                summary['windows']+=1
                summary['candidate_count']+=payload.get('candidate_total_count',len(payload.get('candidates',[])))
                summary['measurements']+=payload.get('measurements',[])
                for c in payload.get('candidates',[]):
                    channel=mapping.get(c.get('channel_name'),{})
                    summary['candidates'].append({**c,'name':channel.get('raw_name',c.get('channel_name')),
                        'channel_id':channel.get('channel_id',c.get('channel_name')),'window':window,'method':key})
            if payload.get('status')!='completed':summary['reasons'].append(payload.get('reason','未完成'))
    for contact in contacts.values():
        contact['rms']=math.sqrt(contact['squares']/contact['finite']) if contact['finite'] else None
    return dict(contacts=list(contacts.values()), flats=flats, flat_windows=done,
                flat_failures=failures, sample_count=complete_samples, nonfinite=invalid,extra=extra)


def render(store, identifier, language='zh-CN'):
    en=language=='en'; t=lambda zh,eng:eng if en else zh
    esc=lambda value:escape(str(value if value is not None else '—'),quote=True)
    num=lambda value:f'{value:,.3f}'.rstrip('0').rstrip('.') if measured(value) else '—'
    root=store.root/'jobs'/identifier; artifacts=root/'artifacts'
    request=read(root/'request.json');item=request['input'];job=store.job(identifier)
    windows,coverage,scope_artifact=scope(root,artifacts)
    if not windows or not coverage:return None
    data=collect(artifacts,windows);contacts=data['contacts'];flats=data['flats']
    configs=request.get('qc_config',request.get('plan',{}).get('qc_config',{}));methods=configs.get('method_config',{})
    flatparams=methods.get('extension_parameters',{}).get('mne_amplitude',{})
    peak_enabled=flatparams.get('peak_volts') is not None
    flat_name=t('平线与相邻跳变','Flatness and adjacent changes') if peak_enabled else t('持续平线','Sustained flatness')
    bad={c['channel_id'] for c in flats if c.get('localization')=='channel_only'}
    intervals=[c for c in flats if c.get('localization')=='interval_only']
    nflat=data['flat_windows'];allflat=nflat==len(windows)
    from dataset_overview import recording_display
    info=recording_display(store,job,item)
    modality={'seeg':'sEEG','ecog':'ECoG'}[item['modality']]
    url=lambda name:f'/api/v1/jobs/{identifier}/artifacts/{quote(name)}'
    state=t('基础检查已完成','Basic checks complete')
    if coverage.get('unexecuted_seconds',0) or coverage.get('failed_seconds',0):
        state=t('部分时段未完成','Some intervals were not completed')
    elif data['nonfinite'] or flats or any(s['candidates'] for s in data['extra'].values()):
        state=t('有待复核的信号片段','Signal findings to review')
    flat_result=t(f'{len(bad)} 道 · {len(intervals)} 条区间',f'{len(bad)} contacts · {len(intervals)} intervals') if nflat else t('未完成','Not assessed')
    if nflat and not allflat:flat_result+=t(f'（{nflat}/{len(windows)} 段已检查）',f' ({nflat}/{len(windows)} windows checked)')
    spectral=[m.get('summary',{}) for w in windows for m in w.get('modules',[]) if m.get('id')=='M04']
    psd_min=min((r.get('psd_computed_channel_count',0) for r in spectral),default=None)
    spec_count=sum(r.get('line_computed_observation_count',0) for r in spectral)
    rows=[
        (t('数值完整性','Numerical integrity'),t(f'{data["nonfinite"]:,} 个非有限值',f'{data["nonfinite"]:,} non-finite samples') if contacts else t('未评','Not assessed'),t('检查 NaN / Inf；短暂重复采样值另存明细，不直接判为坏道。','Check NaN / Inf. Short runs of equal samples remain descriptive evidence.')),
        (flat_name,flat_result,t('MNE 持续相邻差值检测；通道候选和时间候选分别保留。','Original MNE consecutive-difference detection; contact and interval candidates are kept separately.')),
        (t('功率谱密度','Power spectral density'),t(f'每段至少 {num(psd_min)} 道',f'At least {num(psd_min)} contacts per window'),t('Welch PSD；查看频率能量分布，不套用头皮 EEG 的频谱阈值。','Welch PSD describes spectral energy without scalp-EEG thresholds.')),
        (t('工频邻域','Line-frequency neighborhoods'),t(f'{spec_count} 组有效测量',f'{spec_count} valid measurements'),t('测量各触点的 50 / 60 Hz 邻域功率；不将谱峰自动判为噪声。','Measure 50 / 60 Hz band power; a peak is not automatically noise.')),
        (t('触点统计','Contact statistics'),t(f'{len(contacts)} 道',f'{len(contacts)} contacts'),t('RMS、峰峰值及非有限值计数；用于定位和比较。','RMS, peak-to-peak voltage and non-finite counts for review.')),
    ]
    labels={'ieeg_spectrum_fit':t('多窗工频候选','Multitaper line candidates'),'ieeg_mne_lof':t('分组触点 LOF','Grouped contact LOF'),'ieeg_range_plateau':t('量程端点平台','Encoding-limit plateaus'),
            'ieeg_group_outliers':t('分组触点离群','Within-group outliers'),
            'fieldtrip_zvalue':t('相邻跳变线索','Adjacent-change candidates')}
    explanations={'ieeg_spectrum_fit':t('原版MNE多窗F检验；显示命中触点与完整4秒窗，不足一窗的尾段不计为通过。','Original MNE F-test; contact and full-window evidence. Short tails are not counted as passing.'),'ieeg_mne_lof':t('原版MNE，按明确比较组独立运行；离群不等于坏道。','Original MNE, independently within confirmed comparison groups; outliers need review.'),'ieeg_range_plateau':t('连续至少3点落在文件标定端点；提示可能削顶，不等同于硬件饱和。','Runs at file encoding limits; possible clipping, not proven hardware saturation.'),
        'ieeg_group_outliers':t('仅在明确的比较组内评估；参考未确认的组只保留测量。','Compare only declared groups; unconfirmed reference groups remain descriptive.'),
        'fieldtrip_zvalue':t('原版 FieldTrip 相邻差分 z 值；发作及刺激也可能触发，须复核。','Original FieldTrip sample-difference z values; seizures or stimulation can also trigger candidates.')}
    additional=[]
    for key,s in data['extra'].items():
        if not s['artifacts']:continue
        candidates=s['candidates'];additional+=candidates
        count=t(f'{s["candidate_count"]} 条候选 · {s["windows"]}/{len(windows)} 段计算',f'{s["candidate_count"]} candidates · {s["windows"]}/{len(windows)} windows computed') if s['windows'] else t('未完成','Not assessed')
        if key=='fieldtrip_zvalue' and s['windows']:
            seconds=sum(c['stop_seconds']-c['start_seconds'] for c in candidates)
            count=t(f'{len(candidates)} 段 · 累计 {num(seconds)} 秒',f'{len(candidates)} intervals · {num(seconds)} s total')
        if key=='ieeg_group_outliers':
            valid=sum(r.get('status')=='computed' for r in s['measurements'])
            if not valid:count=t('仅测量，未判离群','Measurements only; no classification')
        rows.append((labels[key],count,explanations[key]))
    events=[m for w in windows for m in w.get('modules',[]) if m.get('id')=='M07' and m.get('status') not in {'not_selected','skipped'}]
    if events:rows.append((t('事件与时间','Events and time'),t(f'{len(events)} 段已执行',f'{len(events)} windows checked'),t('核对已登记事件表的时间范围；不识别发作或病理活动。','Check registered event times, without classifying seizures or pathological activity.')))
    table=lambda headers,body:('<div class="table-scroll" tabindex="0" role="region" aria-label="'+esc(' / '.join(headers))+'"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+body+'</tbody></table></div>')
    results=table([t('检查项目','Check'),t('检查结果','Result'),t('解释','Interpretation')],''.join('<tr>'+''.join('<td>'+esc(c)+'</td>' for c in row)+'</tr>' for row in rows))
    finding_rows=[]
    all_candidates=flats+additional
    for c in all_candidates[:200]:
        w=c['window'];a=c.get('start_seconds');b=c.get('stop_seconds')
        channel=c.get('name') or t('所选通道合并','Across selected contacts')
        period=f'{num(a)}–{num(b)} s' if measured(a) and measured(b) else f'{num(w["start_seconds"])}–{num(w["start_seconds"]+w["duration_seconds"])} s'
        label=t('通道候选；列出检查窗口','Contact candidate; analysis window shown') if c.get('localization')=='channel_only' else t('持续平线区间','Sustained-flat interval')
        if c.get('kind')=='BAD_peak':label=t('相邻跳变区间','Adjacent-change interval')
        if c.get('method'):label=labels[c['method']]
        finding_rows.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (channel,period,label))+'</tr>')
    headings=[t('位置','Location'),t('原始记录时间','Original time'),t('发现','Finding')]
    findings=table(headings,''.join(finding_rows[:len(flats)])) if flats else '<p>'+t('本次已执行的平线检查未检出候选。','No sustained-flat candidates in the assessed windows.')+'</p>' if nflat else '<p>'+t('尚无持续平线检查结果。','No sustained-flat results are available.')+'</p>'
    if additional:
        findings+='<details class="disclosure"><summary>'+t(f'增强方法候选 · {len(additional)} 条',f'Additional-method candidates · {len(additional)}')+'</summary>'+table(headings,''.join(finding_rows[len(flats):]))+'</details>'
    if data['nonfinite']:
        findings+='<p>'+t('存在非有限值，查看下方触点统计定位通道。','Non-finite values found; see contact statistics below.')+'</p>'
    if len(all_candidates)>200:
        findings+='<p class="secondary">'+t(f'显示前200条，共{len(all_candidates)}条；完整位置见报告详情中的证据文件。',f'Showing 200 of {len(all_candidates)} candidates; full positions are in the saved evidence under Report details.')+'</p>'
    omitted=sum(s['candidate_count']-len(s['candidates']) for s in data['extra'].values())
    if omitted:
        findings+='<p class="secondary">'+t(f'另有{omitted}条位置因证据存储预算未逐条保存；完整计数已保留。',f'Another {omitted} positions were not stored individually due to the evidence budget; full counts are retained.')+'</p>'
    if not allflat:
        findings+='<p class="secondary">'+t(f'持续平线完成 {nflat}/{len(windows)} 个窗口；未检查部分不计为正常。',f'Flatness assessed in {nflat}/{len(windows)} windows; missing checks are not passes.')+'</p>'
    # Expose an actual saved waveform, with its original scope, inside the report.
    prefix=windows[0]['id']+'--' if windows and windows[0].get('id') else ''
    wave=prefix+'waveform.png'
    if (artifacts/wave).is_file():
        findings+=f'<details class="disclosure"><summary>{t("查看首段波形","First-window waveform")}</summary><img class="ieeg-waveform" src="{url(wave)}" alt="{t("保存的首段波形","Saved first-window traces")}"><p class="secondary">{t("展示通道与时间以图中标记为准。","Channel and time labels define the preview scope.")}</p></details>'
    statsrows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (c['name'],c['source_index'],num(c['rms']*1e6 if measured(c['rms']) else None),num(c['p2p']*1e6 if measured(c['p2p']) else None),c['nonfinite']))+'</tr>' for c in contacts)
    stats='<p class="secondary">'+t('RMS 按有效样本数合并；峰峰值列出各分析窗的最大值。保持源通道顺序，不按幅度自动判坏。','RMS pooled by finite sample count; peak-to-peak is the maximum window value. Source order is preserved; amplitude alone does not label bad contacts.')+'</p>'+table([t('触点','Contact'),t('源索引','Source index'),'RMS / μV',t('最大窗峰峰值 / μV','Max window peak-to-peak / μV'),'NaN / Inf'],statsrows)
    stats='<details class="disclosure ieeg-contacts"><summary>'+t('逐触点测量','Contact measurements')+'</summary>'+stats+'</details>'
    explanation=t('默认输出分项测量与复核位置，不设置颅内信号的统一合格线。发作活动与生理高频不自动扣分。','Default output is measurements and review locations, without a universal intracranial pass threshold. Seizure activity and physiological high frequencies are not automatically penalized.')
    background=t('sEEG 按深部触点分析；电极杆、参考和解剖位置须由采集资料提供。','sEEG analysis is contact-wise; shaft, reference and anatomical context require acquisition metadata.') if item['modality']=='seeg' else t('ECoG 按表面触点分析；网格、条带和参考关系须由采集资料提供。','ECoG analysis is contact-wise; grid, strip and reference relationships require acquisition metadata.')
    details=f'<p>{background}</p><p>{t("不根据通道名推测邻接关系。","Adjacency is not inferred from contact names.")}</p><p>{t("持续平线参数","Flatness parameters")}: {esc(flatparams or t("本次未配置","Not configured"))}</p><p class="secondary">'+t('基础方案的 50 ms 设置参考 MNE-BIDS 检视流程；5% 用于 MNE 将候选归为通道或时间段，仍需复核。','The baseline 50 ms setting follows MNE-BIDS inspection; MNE uses 5% to route findings to contacts or intervals, still requiring review.')+'</p>'
    details+=f'<p><a href="/standards/{item["modality"]}">{t("方案与依据","Scheme and basis")}</a> · <a href="{url(scope_artifact)}">{t("检查范围与记录","Scope and records")}</a> · <a href="{url("report.html")}">{t("运行时报告","Original run report")}</a></p>'
    if data['flat_failures']:details+='<p>'+esc('；'.join(dict.fromkeys(data['flat_failures'])))+'</p>'
    for key,s in data['extra'].items():
        if not s['artifacts']:continue
        links=' · '.join(f'<a href="{url(name)}">{t("分段","Window")} {i+1}</a>' for i,name in enumerate(s['artifacts']))
        details+='<details class="disclosure"><summary>'+labels[key]+'</summary><p>'+explanations[key]+'</p><p>'+esc(methods.get('extension_parameters',{}).get(key,{}))+'</p><p>'+esc('；'.join(dict.fromkeys(s['reasons'])))+'</p>'+links+'</details>'
    score_html='';score=read(artifacts/'method-scores.json').get('project_score')
    if score:
        from ephys_qc.ieeg_scoring import NUMERIC, STABILITY
        from ephys_qc.score_presentation import score_tree
        grouped=bool(score.get('preset')) or any(r['id']==STABILITY and r.get('configured_weight',0)>0 for r in score['components'])
        primary=[r for r in score['components'] if r.get('configured_weight',r.get('weight',0))>0 or grouped and r['id'] in {NUMERIC,STABILITY}]
        names={NUMERIC:t('数值有效性','Numerical validity'),STABILITY:t('信号稳定性','Signal stability')}
        total=f"{score['value']:.2f}" if measured(score.get('value')) else '—'
        label=modality+' '+t('基础评分','basic score') if score.get('preset') else t('项目自定义评分','Project score')
        score_html=f'<div class="ieeg-score-panel"><div><span>{label}</span><strong>{total}<small> / 100</small></strong></div><p>'+(t('子项按权重汇总；分数仅反映已执行的检查。','Children use weighted aggregation; the score covers the checks performed.') if any(r.get('aggregation')=='weighted_child_mean' for r in score['components']) else t('相关检查合并计一次；分数仅反映已执行的检查。','Related checks count once; the score covers the checks performed.'))+'</p></div>'+score_tree(primary, modality=item['modality'], english=en, names=names, total_available=measured(score.get('value')))
        if score.get('missing_reason'):score_html+='<p class="secondary">'+esc(score['missing_reason'])+'</p>'
        details+='<p>'+t('评分版本','Scoring version')+': '+esc(score.get('preset') or score['version'])+'</p><p>'+(t('数值有效性只计算NaN/Inf；稳定性按有效子项的权重平均，之后按两个分项的有效权重汇总。权重为项目设置，尚未经专家校准。','Numerical validity counts NaN/Inf only. Stability is the weighted mean of valid child checks; the two components are then weighted. Weights are project settings, not expert-calibrated.') if any(r.get('aggregation')=='weighted_child_mean' for r in score['components']) else t('数值有效性只计算NaN/Inf；相关信号候选取最低分作为稳定性，之后按两个分项的有效权重平均。这是项目初版，尚未经专家校准。','Numerical validity counts NaN/Inf only. Stability takes the minimum related check score; the two components are then weighted. This project draft is not expert-calibrated.'))+'</p><p><a href="'+('/en' if en else '')+'/standards/ieeg-scoring">'+t('颅内评分规则','Intracranial scoring rules')+'</a></p>'
    initial_window=all_candidates[0]['window']['id']+'--' if all_candidates and all_candidates[0]['window'].get('id') else ''
    charts_url=f'/api/v1/jobs/{identifier}/visualizations'+('?window='+quote(initial_window) if initial_window else '')
    facts=[(modality,t('模态','Modality')),(info['channels'],t('分析触点','Contacts')),(num(coverage.get('completed_seconds'))+' s',t('已检查时长','Checked duration')),(', '.join(num(r) for r in info['rates_hz'])+' Hz',t('采样率','Sampling rate'))]
    facthtml=''.join(f'<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>' for v,k in facts)
    web=Path(__file__).with_name('web');css=(web/'ui-tokens.css').read_text()+(web/'dataset-report.css').read_text()+SECTION_CSS+EXTRA_CSS
    return f'''<!doctype html><html lang="{esc(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(job.get('run_name') or item['label'])}</title><style>{css}</style><script src="/dataset-report.js" defer></script></head><body class="dataset-report ieeg-report"><main><p class="eyebrow">DBCI-QC · {modality} {t('基础方案','basic scheme')}</p><h1>{esc(job.get('run_name') or item['label'])}</h1><p class="secondary">{esc(item['label'])}</p><dl class="dataset-facts">{facthtml}</dl><div class="ieeg-result"><strong>{state}</strong><span>{flat_name}：{flat_result}</span></div><p class="secondary">{explanation}</p><ol class="ieeg-flow"><li>{t('读取与确认','Read and confirm')}</li><li>{t('完整性与量程','Integrity and range')}</li><li>{t('频谱、触点与跳变','Spectra, contacts and transients')}</li><li>{t('汇总与复核','Summarize and review')}</li></ol>{report_section('results',t('检查结果','Results'),score_html+results,opened=True)}{report_section('locations',t('问题定位','Review locations'),findings,opened=bool(all_candidates or data['nonfinite']))}{inline_charts(charts_url,english=en)}{report_section('details',t('报告详情','Report details'),stats+details)}<footer>DBCI-QC · {t('基础方案试用版，候选需复核','Basic trial scheme; candidates require review')}<button id="print-report">{t('打印 / PDF','Print / PDF')}</button></footer></main></body></html>'''


EXTRA_CSS='''
.ieeg-score-panel{display:flex;align-items:center;gap:24px;padding:18px 0}.ieeg-score-panel>div{min-width:160px}.ieeg-score-panel span{display:block;font-size:13px;color:#52637a}.ieeg-score-panel strong{display:block;font-size:38px;line-height:1.4;color:#2459bc;font-variant-numeric:tabular-nums}.ieeg-score-panel small{font-size:13px;font-weight:400;color:#52637a}.ieeg-score-panel p{font-size:13px;color:#52637a;max-width:380px}@media(max-width:600px){.ieeg-score-panel{flex-wrap:wrap;gap:4px}}
.ieeg-report main>.report-section{margin:0;padding:0;border-bottom:1px solid #dfe5ed}.ieeg-report main>.report-section>summary{padding:14px 0;min-height:52px}.ieeg-report main>.report-section>summary>h2{font:600 16px/24px var(--font-ui,system-ui,sans-serif);margin:0}.ieeg-report main>.report-section>summary:hover{color:#2459bc}.ieeg-report main{max-width:1120px;margin:24px auto;padding:0 28px 32px}.ieeg-report .dataset-facts{margin:16px 0;padding:14px 0;border-bottom:1px solid #dfe5ed;gap:16px}.ieeg-report .dataset-facts dd{font-size:19px}.ieeg-report table{table-layout:auto}.ieeg-report th,.ieeg-report td{padding:10px 12px}.ieeg-report td:first-child{white-space:nowrap}.ieeg-report .ieeg-result{display:flex;align-items:baseline;gap:18px;padding:8px 0}.ieeg-result strong{font-size:17px}.ieeg-result span{font-size:13px;color:#42546b}.ieeg-report main>.secondary{font-size:12px}.ieeg-flow{display:flex;list-style:none;margin:16px 0 22px;padding:0;flex-wrap:wrap;gap:0}.ieeg-flow li{font-size:12px;color:#28538b;background:#eef3fb;padding:7px 12px}.ieeg-flow li+li:before{content:'→';margin-right:12px;color:#7893b9}.ieeg-flow li:first-child{border-radius:4px 0 0 4px}.ieeg-flow li:last-child{border-radius:0 4px 4px 0}.ieeg-waveform{width:100%;height:auto}.ieeg-contacts .table-scroll{max-height:420px;overflow:auto}.ieeg-contacts thead{position:sticky;top:0;background:white}.ieeg-report .disclosure{margin:8px 0;padding:12px 0}.ieeg-report footer{display:flex;align-items:center;justify-content:space-between;margin-top:20px;font-size:12px;color:#64748b}.ieeg-report .report-section-body>p{font-size:13px}.ieeg-report .ieeg-result span{font-variant-numeric:tabular-nums}@media(max-width:600px){.ieeg-report main{padding:0 16px 24px}.ieeg-report .dataset-facts{grid-template-columns:repeat(2,1fr)}.ieeg-result{flex-wrap:wrap;gap:4px!important}}@media print{.ieeg-flow{display:none}.ieeg-report .ieeg-contacts .table-scroll{max-height:none;overflow:visible}.ieeg-report table{min-width:0}.ieeg-report .report-section-body{display:block!important}}
'''
