"""Neuropixels report: present saved voltage evidence, never rerun detectors."""
from html import escape
from pathlib import Path
from urllib.parse import quote
from ephys_qc.report_presentation import report_section, inline_charts, CSS as SECTION_CSS
from ieeg_report import read, scope, measured, EXTRA_CSS


def render(store, identifier, language='zh-CN'):
    en=language=='en';t=lambda zh,eng:eng if en else zh
    esc=lambda v:escape(str(v if v is not None else '—'),quote=True)
    num=lambda v:f'{v:,.3f}'.rstrip('0').rstrip('.') if measured(v) else '—'
    root=store.root/'jobs'/identifier;artifacts=root/'artifacts'
    request=read(root/'request.json');item=request['input'];job=store.job(identifier)
    windows,coverage,scope_file=scope(root,artifacts)
    if not windows or not coverage:return None
    acq=item.get('metadata',{}).get('acquisition',{})
    band=acq.get('stream_band') or t('频带待确认','Band unconfirmed')
    from dataset_overview import recording_display
    info=recording_display(store,job,item)
    url=lambda name:f'/api/v1/jobs/{identifier}/artifacts/{quote(name)}'
    table=lambda headers,rows:'<div class="table-scroll" tabindex="0" role="region" aria-label="'+esc(' / '.join(headers))+'"><table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    nonfinite=0;constant=[];noise=[];longest=[];method_runs=[];evidence=[];n_integrity=0;n_constant=0
    for w in windows:
        prefix=w['id']+'--' if w.get('id') else ''
        source=read(artifacts/(prefix+'M03_continuity.json'))
        rows=source.get('channels',[])
        if rows:
            n_integrity+=1;nonfinite+=sum(r['nonfinite_sample_count'] for r in rows)
            n_constant+=all('fully_constant' in r for r in rows)
            period=source.get('input_range',{})
            for r in rows:
                position=(r['channel_name'],f"{num(period.get('start_seconds'))}–{num(period.get('stop_seconds'))} s")
                if r.get('fully_constant'):constant.append((*position,t('整分析窗恒值','Constant throughout this window')))
                if r['nonfinite_sample_count']:constant.append((*position,t(f"{r['nonfinite_sample_count']} 个非有限值",f"{r['nonfinite_sample_count']} non-finite samples")))
                if measured(r.get('max_exact_constant_run_seconds')):longest.append(r['max_exact_constant_run_seconds'])
        name=prefix+'M05_spikeinterface_bad_channels.json';p=read(artifacts/name)
        if p:
            evidence.append(name)
            method_runs.append(p)
            mapping={r['adapter_name']:r for r in p.get('channel_mapping',[])}
            for c in p.get('candidates',[]):
                channel=mapping.get(c.get('channel_name'),{}).get('raw_name',c.get('channel_name'))
                ran=p.get('range',{})
                noise.append((channel,f"{num(ran.get('start_seconds'))}–{num(ran.get('stop_seconds'))} s",t('AP高离散度通道候选','AP high-dispersion channel candidate')))
    scores=read(artifacts/'method-scores.json')
    component=next((r for r in scores.get('outputs',[]) if r['id']=='spikeinterface_bad_channels'),{})
    score=component.get('value');project=scores.get('project_score')
    completed=sum(p.get('calculated') is True and p.get('status')=='completed' for p in method_runs)
    const_count=sum(r[2] in {'整分析窗恒值','Constant throughout this window'} for r in constant)
    result_rows=[
        (t('数值完整性','Numerical integrity'),t(f'{nonfinite:,} 个非有限值',f'{nonfinite:,} non-finite samples') if n_integrity else t('未评','Not assessed'),f'{n_integrity}/{len(windows)} '+t('分析段有证据','windows with evidence')),
        (t('恒值观察','Constant-run observation'),t(f'{const_count} 个通道窗整窗恒值',f'{const_count} fully constant channel-windows') if n_constant else t('历史记录未保存此汇总','Not stored in this historical run'),t('窗内最长精确恒值 ','Longest exact run within a window: ')+num(max(longest,default=None))+f' s · {n_constant}/{len(windows)} '+t('分析段有汇总','windows with summaries')),
        (t('频谱与通道统计','Spectrum and channel statistics'),t(f"{num(info.get('psd_channels'))} 道PSD · RMS、峰峰值",f"{num(info.get('psd_channels'))} PSD channels · RMS, peak-to-peak"),t('描述性测量；RMS不等于噪声地板','Descriptive; RMS is not a noise floor')),
        (t('AP通道离群','AP channel outliers'),t(f'{len(noise)} 个候选通道窗',f'{len(noise)} candidate channel-windows') if completed else t('未执行或条件不足','Not run or prerequisites missing'),t(f'{completed}/{len(windows)} 分析段完成；按shank分别计算',f'{completed}/{len(windows)} windows assessed, separately by shank') if method_runs else t('LF/LFP不套用AP参数；AP还需shank和窗口条件','AP parameters do not apply to LF/LFP; AP also requires shank and window prerequisites'))]
    results=table([t('检查项目','Check'),t('检查结果','Result'),t('解释','Interpretation')],result_rows)
    if component:
        results+='<div class="ieeg-score-panel"><div><span>'+t('AP通道离群分项','AP channel-outlier component')+'</span><strong>'+(f'{score:.2f}' if measured(score) else '—')+'<small> / 100</small></strong></div><p>'+t('未被该方法标记的通道比例；不代表神经元质量。','Channel fraction not flagged by this method; not neuronal-unit quality.')+'</p></div>'
        if not measured(score):results+='<p class="secondary">'+esc(component.get('reason'))+'</p>'
    if project:
        results+='<p>'+t('所选项目评分：','Selected-check project score: ')+num(project.get('value'))+' / 100</p>'+table([t('计分项','Component'),'/ 100',t('有效权重','Effective share')],[(r['name'],num(r.get('value')),num(100*r.get('normalized_weight',0))+'%') for r in project['components'] if r.get('configured_weight',0)>0])
    findings=constant+noise
    locations=table([t('通道','Channel'),t('检查窗口（记录时间）','Analysis window (recording time)'),t('发现','Finding')],findings[:200]) if findings else '<p>'+t('本次已执行项目没有待列出的通道候选。','No channel candidates from the checks performed.')+'</p>'
    locations+='<p class="secondary">'+t('AP离群只定位通道；窗口时间是评估范围，不是精确异常起止。','AP outliers localize channels; window times are assessment ranges, not exact artifact onsets/offsets.')+'</p>'
    if len(findings)>200:locations+='<p>'+t(f'显示前200条，共{len(findings)}条。',f'Showing 200 of {len(findings)} rows.')+'</p>'
    first=(windows[0]['id']+'--' if windows[0].get('id') else '')+'waveform.png'
    if (artifacts/first).is_file():locations+='<details class="disclosure"><summary>'+t('查看首段波形','First-window waveform')+'</summary><img class="ieeg-waveform" src="'+url(first)+'" alt="'+t('首段已保存波形，范围以图内标记为准','Saved first-window traces; labels define the preview scope')+'"></details>'
    details='<p>'+t('本页按neuropixels-qc/0.1组织已保存的原始电压证据；历史缺项不补算。没有执行分选后unit质控、漂移或跨流同步判定。','This page organizes saved voltage evidence under neuropixels-qc/0.1; historical missing checks are not recomputed. Sorted-unit QC, drift and cross-stream synchronization have not been evaluated.')+'</p>'
    details+='<p>'+t('已计算 / 本地文件时长：','Computed / local file duration: ')+num(coverage.get('completed_seconds'))+' / '+num(info['duration_seconds'])+' s · '+t('来源缺口：','Source gaps: ')+num(coverage.get('gap_seconds',0))+' s</p>'
    details+='<p>'+t('如为来源片段，本次覆盖仅指本地片段。AP离群方法内部抽样，不代表每个样本都接受了该项判定。','For source extracts, coverage applies only to the local extract. AP outlier detection samples internally; it does not classify every individual sample.')+'</p>'
    details+='<p><a href="'+('/en' if en else '')+'/standards/neuropixels">'+t('Neuropixels质控规范','Neuropixels QC specification')+'</a> · <a href="'+url(scope_file)+'">'+t('执行记录','Execution record')+'</a></p>'
    if method_runs:
        body=''.join('<p>'+esc(p.get('parameters',{}))+' · '+esc(p.get('status'))+' · '+esc(p.get('reason'))+'</p><a href="'+url(name)+'">'+t('原始证据','Saved evidence')+'</a>' for name,p in zip(evidence,method_runs))
        details+='<details class="disclosure"><summary>'+t('AP方法参数与状态','AP parameters and status')+'</summary>'+body+'</details>'
    facts=[('Neuropixels · '+str(band).upper(),t('信号流','Signal stream')),(info['channels'],t('神经通道','Neural channels')),(num(coverage.get('completed_seconds'))+' s',t('已检查时长','Checked duration')),(', '.join(num(r) for r in info['rates_hz'])+' Hz',t('采样率','Sampling rate'))]
    facthtml=''.join('<div><dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd></div>' for v,k in facts)
    outcome=t('有待复核的通道或数值','Channels or values need review') if findings else t('基础测量已完成','Basic measurements available')
    if not findings and (n_integrity != len(windows) or n_constant != len(windows)):
        outcome=t('部分检查汇总未保存，见检查结果','Some check summaries are not stored; see Results')
    if coverage.get('failed_seconds',0) or coverage.get('unexecuted_seconds',0):outcome=t('部分时段未完成','Some intervals were not completed')
    web=Path(__file__).with_name('web');css=(web/'ui-tokens.css').read_text()+(web/'dataset-report.css').read_text()+SECTION_CSS+EXTRA_CSS
    sections=report_section('results',t('检查结果','Results'),results,opened=True)+report_section('locations',t('问题定位','Review locations'),locations,opened=bool(findings))+inline_charts(f'/api/v1/jobs/{identifier}/visualizations',english=en)+report_section('details',t('报告详情','Report details'),details)
    return '<!doctype html><html lang="'+esc(language)+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(job.get('run_name') or item['label'])+'</title><style>'+css+'</style><script src="/dataset-report.js" defer></script></head><body class="dataset-report ieeg-report"><main><p class="eyebrow">DBCI-QC · Neuropixels</p><h1>'+esc(job.get('run_name') or item['label'])+'</h1><dl class="dataset-facts">'+facthtml+'</dl><p class="report-conclusion">'+outcome+'</p>'+sections+'<footer>DBCI-QC · '+t('原始电压质控，候选需复核','Voltage QC; candidates require review')+'<button id="print-report">'+t('打印 / PDF','Print / PDF')+'</button></footer></main></body></html>'
