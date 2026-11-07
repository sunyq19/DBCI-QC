(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const query=new URLSearchParams(location.search);
  let lang=query.get('lang')||localStorage.getItem('ephys-qc.language')||'zh-CN';
  let packages=[],jobs=[],selected=null,job=null,overview=null,directory=null,subject=query.get('subject')||'__all__',filter='issues',epoch=0,timer=null,opening=false,admissionPolicy=null,selectedJobId=null,issue=null,evidenceGroup=null;
  let checkedRecords=new Set(),batch=null,batchTimer=null;
  let tab=['overview','records','review'].includes(query.get('tab'))?query.get('tab'):'overview';
  const en=()=>lang==='en',t=(a,b)=>en()?b:a;
  const words={tabOverview:['总览','Overview'],tabRecords:['记录','Recordings'],tabReview:['审核与复验','Review & retest'],d04:['审核与复验','Review & retest'],brand:['质控台','QC Workbench'],standards:['质控标准','QC specifications'],backData:['返回数据','Back to data'],title:['数据集总览','Dataset overview'],intro:['查看资料问题，继续检查记录。','Review dataset issues and continue recording checks.'],source:['当前数据集','Current dataset'],choose:['数据集','Dataset'],scope:['检查设置','Check settings'],confirm:['确认检查以上记录','Check the recordings listed above'],run:['检查资料','Check dataset information'],local:['本机后台计算，保留原始文件。','Runs locally in the background; originals are preserved.'],history:['资料检查历史','Dataset check history'],historyLabel:['打开已有结果','Open a saved run'],registered:['信号报告在对应记录处查看。','Signal reports are listed with each recording.'],workflow:['检查范围','Checks included'],boundary:['先核对资料，再进入记录开展信号检查。','Check the dataset, then open recordings for signal QC.'],emptyTitle:['选择数据集以继续','Select a dataset'],emptyText:['在数据入口上传文件或打开已有数据。','Upload a file or open existing data from the data entry.'],d01:['文件与配套资料','Files and companions'],d02:['同一个体的资料','Within-subject records'],d03:['同组数据的差异','Differences within a group'],footer:['质控台 · 本地处理','QC Workbench · Local processing'],recordsTitle:['个体与记录','Subjects and recordings'],noUpload:['无需重新上传','No re-upload'],subject:['个体','Subject'],checkDetails:['检查依据与未完成项','Evidence and incomplete checks']};
  const states={ready:['可检查','Ready'],partial:['部分可检查','Partly available'],blocked:['缺少条件','Unavailable'],not_selected:['未选择','Not selected'],pending:['等待','Pending'],queued:['排队中','Queued'],running:['检查中','Running'],completed:['报告已生成','Report generated'],failed:['失败','Failed'],interrupted:['中断','Interrupted'],cancelled:['已取消','Cancelled'],cancelling:['取消中','Cancelling'],not_run:['尚未检查','Not checked'],pass:['一致','Consistent'],conflict:['需核对','Needs review'],review:['待复核','Review'],unassessed:['尚无法判断','Not yet assessable'],not_applicable:['不适用','N/A'],source_mismatch:['来源不一致','Source mismatch'],report_unavailable:['报告不可用','Report unavailable']};
  const label=s=>states[s]?.[en()?1:0]||s, tag=s=>`<span class="dataset-status ${esc(s)}">${esc(label(s))}</span>`,word=k=>words[k]?.[en()?1:0]||k;
  const active=s=>['queued','running','cancelling'].includes(s),point=x=>Number.isFinite(x)?x.toFixed(2):'—';
  function error(message){$('dataset-error').textContent=message||'';$('dataset-error').hidden=!message;}
  async function api(path,body){const response=await fetch('/api/v1'+path,{cache:'no-store',method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok)throw Error(data.error||`HTTP ${response.status}`);return data;}
  const overviewPath=()=>'/packages/'+encodeURIComponent(selected.id)+'/overview';
  const params=()=>new URLSearchParams({...selectedJobId?{job:selectedJobId}:{},lang}).toString();
  function translate(){document.documentElement.lang=lang;document.querySelectorAll('[data-text]').forEach(el=>el.textContent=word(el.dataset.text));document.querySelectorAll('[data-lang]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.lang===lang)));$('dataset-standard').href=(en()?'/en':'')+'/standards/dataset-checks';render();}
  function renderSource(){
    $('dataset-breadcrumb').textContent=selected?.label||'';
    const option=p=>`<option value="${esc(p.id)}" ${p.available?'':'disabled'}>${esc(en()?p.label_en||p.label:p.label)}${p.available?'':t(' · 不可用',' · unavailable')}</option>`;
    const groups=[['example',t('示例数据集','Example datasets')],['data',t('已导入数据','Imported data')],['validation',t('验证样例','Validation cases')]];
    $('package-select').innerHTML='<option value="">'+t('选择数据集','Select a dataset')+'</option>'+groups.map(([kind,label])=>{const rows=packages.filter(p=>(p.category||'data')===kind);return rows.length?`<optgroup label="${label}">${rows.map(option).join('')}</optgroup>`:''}).join('');$('package-select').disabled=!packages.length;$('package-select').value=selected?.id||'';
    $('package-facts').innerHTML=selected?.available?[[overview?.summary.subjects??selected.subjects,t('个体','subjects')],[overview?.summary.records??selected.records,t('记录','recordings')],[overview?.summary.expected_files??selected.files,t('文件','files')]].map(([v,k])=>`<div><b>${v}</b><small>${k}</small></div>`).join(''):'';
    $('package-description').textContent=(en()?selected?.description_en||selected?.description:selected?.description)||'';$('package-scope').textContent=overview?.scope||selected?.scope||'';
    $('package-groups').innerHTML=(overview?.comparison_groups||selected?.groups||[]).map(g=>`<div class="package-rule"><strong>${esc(g.label||g.id)}</strong><p class="small muted">${g.same_channels?t('固定通道布局','Fixed channel layout'):t('允许不同个体的通道布局不同','Layouts may differ across subjects')}</p></div>`).join('');
    $('package-admission-limits').hidden=!admissionPolicy;
    if(admissionPolicy){const bytes=admissionPolicy.max_record_bytes,recordSize=bytes>=1073741824?`${bytes/1073741824} GiB`:`${bytes/1048576} MiB`;$('package-admission-limits').textContent=t(`云端限额验证 · 每记录 ${recordSize} · 数据集 ${admissionPolicy.max_dataset_bytes/1073741824} GiB / ${admissionPolicy.max_records} 记录 / ${admissionPolicy.max_files} 文件`,`Cloud limit validation · ${recordSize} per record · ${admissionPolicy.max_dataset_bytes/1073741824} GiB / ${admissionPolicy.max_records} records / ${admissionPolicy.max_files} files per dataset`);}
    updateButton();
  }
  function updateButton(){$('package-run').disabled=!selected?.available||!$('package-confirm').checked||active(job?.status)||overview?.current_manifest===false;$('package-confirm').disabled=active(job?.status)||overview?.current_manifest===false;}
  function renderFlow(){
    $('package-status').textContent=job?label(job.status):t('未开始','Not started');
    $('dataset-flow').innerHTML=['d01','d02','d03','d04'].map((key,i)=>`<div class="dataset-node"><small>0${i+1}</small><strong>${word(key)}</strong></div>`).join('');
    $('dataset-empty').hidden=!!overview;
  }
  function renderHistory(){$('package-history').innerHTML='<option value="">'+t('当前汇总','Current summary')+'</option>'+jobs.filter(j=>j.package_id===selected?.id).map(j=>`<option value="${esc(j.id)}">${esc(label(j.status))} · ${esc(new Date(j.created_at).toLocaleString(en()?'en-GB':'zh-CN'))}</option>`).join('');$('package-history').value=selectedJobId||'';}
  function renderResult(){
    $('dataset-result').hidden=!overview;$('dataset-details').hidden=!overview;if(!overview)return;
    const s=overview.summary,f=s.file_counts,groups=overview.attention_groups||[];
    const affected=new Set(groups.flatMap(g=>g.record_ids));
    const files=f?`${f.present||0} / ${s.expected_files}`:'—';
    const title=active(job?.status)?t('正在检查资料','Checking dataset information'):!s.dataset_assessed?t('先检查资料，再查看记录结果','Check the dataset before reviewing results'):groups.length?t('有资料需要核对','Some information needs attention'):s.findings.unassessed?t('资料检查完成，部分项目尚无法判断','Dataset checks complete; some checks remain unassessed'):t('已完成的资料检查未发现需核对项','No issues found in completed dataset checks');
    const exportUrl='/api/v1'+overviewPath()+'/report?'+params();
    const warning=!overview.current_manifest?t('正在查看历史清单，打开记录请返回当前汇总。','Viewing a historical manifest. Return to the current summary to open recordings.'):null;
    const attention=groups.map(g=>`<details class="attention-item"><summary class="attention-heading"><strong>${esc(en()?g.title_en:g.title)}</strong><span>${g.record_count?`${g.record_count} ${t('份记录','recordings')}`:t('数据集资料','Dataset information')}</span></summary><p>${esc(en()?g.meaning_en:g.meaning)}</p>${g.unit_labels?.length?`<p class="attention-evidence">${g.unit_labels.slice(0,3).map(u=>`${t('文件头','Header')} ${esc(u.file_unit)} · ${t('配套表','Table')} ${esc(u.table_unit)}`).join('；')}</p>`:''}<p class="attention-next">${esc(en()?g.next_step_en:g.next_step)}</p><div class="attention-actions">${g.record_count?`<button class="text-button" data-attention="${esc(g.id)}">${t('查看相关记录','View recordings')}</button>`:''}<button class="text-button" data-evidence="${esc(g.id)}">${t('查看依据','View evidence')}</button><small>${t('建议核对人','Suggested reviewer')}：${esc(en()?g.owner_en:g.owner)}</small></div></details>`).join('');
    const subjects=overview.subjects.map(r=>`<tr><td><button class="text-button" data-record-subject="${esc(r.id)}">${esc(r.id)}</button></td><td>${r.records}</td><td>${r.reported}/${r.records}</td><td>${r.not_run}</td></tr>`).join('');
    $('dataset-result').innerHTML=`<section class="panel dataset-overview-card"><div class="section-heading"><h2>${title}</h2><button class="text-button" id="dataset-refresh">${t('刷新','Refresh')}</button></div>${warning?`<p class="data-summary-warning">${warning} <a href="/datasets?package=${encodeURIComponent(selected.id)}&lang=${lang}">${t('返回当前数据','Return to current data')}</a></p>`:''}<div class="dataset-summary"><div><b>${files}</b><small>${t('文件与清单相符','Files match inventory')}</small></div><div><b>${s.dataset_assessed?affected.size:'—'}</b><small>${t('记录需核对资料','Recordings needing review')}</small></div><div><b>${s.reported} / ${s.records}</b><small>${t('已有信号检查报告','Signal reports available')}</small></div></div>${!s.dataset_assessed?`<p class="overview-note">${t('资料检查尚未完成，请确认本次范围后开始检查。','Dataset checks are not complete. Confirm the scope and start the check.')}</p>`:''}<div class="dataset-actions">${!s.dataset_assessed&&!active(job?.status)?`<button class="button primary small-button" data-show-setup>${t('开始资料检查','Start dataset check')}</button>`:''}<a class="button ${s.dataset_assessed?'primary':'secondary'} small-button" href="${esc(exportUrl)}" target="_blank" rel="noopener">${t('汇总报告','Summary report')}</a><a href="${esc(exportUrl+'&download=1')}">${t('下载汇总','Download summary')}</a>${s.dataset_assessed?`<button class="text-button" data-open-review>${t('审核与复验','Review & retest')}</button>`:''}</div></section>${attention?`<section class="panel attention-panel"><h2>${t('需要处理的事项','Items needing attention')}</h2>${attention}</section>`:''}<details class="panel subject-summary"><summary>${t('按个体查看','Browse by subject')} · ${s.subjects}</summary><div class="dataset-scroll"><table class="dataset-table"><thead><tr>${[t('个体','Subject'),t('记录','Records'),t('已有报告','Reports'),t('尚未检查信号','Signal checks not started')].map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${subjects}</tbody></table></div></details>`;
    $('dataset-refresh')?.addEventListener('click',()=>refresh(++epoch));
    $('dataset-filters').innerHTML=[['issues',t('需要核对','Needs review')],['unassessed',t('尚无法判断','Cannot assess yet')],['all',t('全部检查','All checks')]].map(([v,k])=>`<button type="button" data-filter="${v}" aria-pressed="${filter===v}">${k}</button>`).join('');
    $('dataset-detail-note').textContent=t(`另有 ${s.findings.unassessed||0} 项检查尚无法判断；原因见下方。`,`A further ${s.findings.unassessed||0} checks could not be assessed; reasons are listed below.`);
    renderChecks();
  }
  function renderChecks(){
    const selectedGroup=overview?.attention_groups?.find(g=>g.id===evidenceGroup);
    const rows=(overview?.checks||[]).filter(r=>!selectedGroup||selectedGroup.check_ids.includes(r.id)).filter(r=>filter==='all'||filter==='issues'&&['conflict','review'].includes(r.status)||filter===r.status);
    $('dataset-checks').innerHTML=rows.length?`<table class="dataset-table"><thead><tr><th>${t('检查项','Check')}</th><th>${t('状态','Status')}</th><th>${t('证据','Evidence')}</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${r.module} · ${esc(en()?r.label_en:r.label)}<span class="target">${esc(r.target)}</span></td><td>${tag(r.status)}</td><td><details><summary>${t('展开','Open')}</summary><p>${esc(r.message)}</p><p class="target">${(r.files||[]).map(esc).join('<br>')}</p>${r.observed?`<pre>${esc(JSON.stringify(r.observed,null,2))}</pre>`:''}</details></td></tr>`).join('')}</tbody></table>`:`<p class="small muted">${overview?.summary.dataset_assessed?t('此分类没有检查项。','No checks in this category.'):t('尚未检查。','Not yet assessed.')}</p>`;
  }
  function signalHtml(signal){
    if(!signal||signal.status==='not_run')return `<small>${t('尚未检查','Not checked')}</small>`;
    const complete=signal.full_duration_computed?t('已检查全时长','Full duration checked'):signal.scope==='window'?t('仅片段','Window only'):t('尚未覆盖全时长','Full duration not covered');
    const score=signal.components?.length?`<details class="signal-metrics"><summary>${t('查看 EEG 检查指标','EEG check metrics')}</summary>${signal.components.map(p=>`<div>${esc(p.name||p.id)} · ${point(p.value)}</div>`).join('')}<small>${esc(signal.score_version)}</small></details>`:'';
    return `${tag(signal.status)}<small class="target">${complete}${signal.incomplete_modules?.length?` · ${t('部分项目未完成','Some checks incomplete')}`:''}</small>${signal.source_status==='unverified'?`<small class="target">${t('待资料检查核对来源','Source comparison pending')}</small>`:''}${score}`;
  }
  function renderRecords(){
    $('package-record-browser').hidden=!directory&&!overview;if(!directory&&!overview)return;
    const allRows=overview?.records||directory.records||[],group=overview?.attention_groups?.find(g=>g.id===issue),rows=group?allRows.filter(r=>group.record_ids.includes(r.id)):allRows,subjects=[...new Set(rows.map(r=>r.subject))];if(subject!=='__all__'&&!subjects.includes(subject))subject='__all__';
    $('package-subject').innerHTML=`<option value="__all__">${t('全部个体','All subjects')}</option>`+subjects.map(id=>`<option value="${esc(id)}">${esc(id)}</option>`).join('');$('package-subject').value=subject;
    $('record-browser-note').textContent=t('打开记录可继续检查；历史报告保留原范围和版本。','Open a recording to continue checks. Historical reports keep their scope and version.');
    $('package-records').innerHTML=`${group?`<div class="record-filter-note">${esc(en()?group.title_en:group.title)} <button class="text-button" data-clear-issue>${t('显示全部记录','Show all recordings')}</button></div>`:''}<table class="dataset-table"><thead><tr><th><input type="checkbox" data-select-records aria-label="${t('选择当前显示记录','Select visible records')}"></th><th>${t('会话 / 记录','Session / recording')}</th><th>${t('资料检查','Dataset checks')}</th><th>${t('信号检查','Signal checks')}</th><th>${t('操作','Actions')}</th></tr></thead><tbody>${rows.filter(r=>subject==='__all__'||r.subject===subject).map(r=>{
      const current=directory?.records?.find(x=>x.id===r.id),runs=current?.signal_runs||[],stale=overview&&!overview.current_manifest;
      const history=runs.length&&!stale?`<details><summary>${t('历史','History')} · ${runs.length}</summary>${runs.map(j=>`<a class="record-run-link" href="/?job=${encodeURIComponent(j.id)}&lang=${lang}">${esc(label(j.status))} · ${esc(new Date(j.created_at).toLocaleString(en()?'en-GB':'zh-CN'))}</a>`).join('')}</details>`:'';
      const relevant=(overview?.attention_groups||[]).filter(g=>g.record_ids.includes(r.id));
      const findings=!overview?.summary.dataset_assessed?t('尚未检查资料','Dataset not checked'):relevant.length?relevant.map(g=>`<span class="record-issue-title">${esc(en()?g.title_en:g.title)}</span>`).join(''):r.checks?.unassessed?t('有项目尚无法判断','Some checks cannot yet be assessed'):t('已检查项未发现问题','No issues in completed checks');
      const modalities={scalp_eeg:t('头皮 EEG','Scalp EEG'),ecog:'ECoG',seeg:'sEEG',extracellular:t('细胞外电压','Extracellular voltage')};
      return `<tr><td><input type="checkbox" data-check-record="${esc(r.id)}" aria-label="${esc(r.subject+' '+r.id)}" ${checkedRecords.has(r.id)?'checked':''} ${!current?.available||stale?'disabled':''}></td><td><strong>${esc(r.subject)} · ${t('记录','Recording')} ${allRows.findIndex(x=>x.id===r.id)+1}</strong><small class="target">${esc(modalities[r.modality]||r.modality)} · ${r.processing==='derived'?t('处理后数据','Processed data'):t('原始数据','Raw data')}</small><details class="record-file-details"><summary>${t('文件信息','File information')}</summary><span class="target">${esc(r.path)}</span><small>${esc(r.session)}</small></details></td><td>${findings}</td><td>${signalHtml(r.signal)}</td><td>${r.signal?.report_url?`<a class="button primary small-button" href="${esc(r.signal.report_url)}?lang=${lang}" target="_blank" rel="noopener">${t('查看报告','View report')}</a>`:''}<button class="text-button" data-open-record="${esc(r.id)}" ${!current?.available||opening||stale?'disabled':''}>${current?.available?t('打开记录','Open recording'):t('文件不可用','File unavailable')}</button>${history}</td></tr>`;

    }).join('')}</tbody></table>`;
  }
  function notifyReview(){document.dispatchEvent(new CustomEvent('dataset-context',{detail:{job,package_id:selected?.id,manifest_hash:selected?.manifest_hash,lang,tab}}));}
  function setTab(value,focus=false){
    tab=value;
    ['overview','records','review'].forEach(key=>{const b=$('dataset-tab-'+key);b.setAttribute('aria-selected',String(key===tab));b.setAttribute('tabindex',key===tab?'0':'-1');$('dataset-'+key+'-pane').hidden=key!==tab;});
    if(focus)$('dataset-tab-'+tab).focus();
    notifyReview();
  }
  $('dataset-tabs').addEventListener('click',event=>{const b=event.target.closest('[data-tab]');if(b)setTab(b.dataset.tab);});
  $('dataset-tabs').addEventListener('keydown',event=>{const order=['overview','records','review'];let index=order.indexOf(tab);if(event.key==='ArrowRight')index=(index+1)%3;else if(event.key==='ArrowLeft')index=(index+2)%3;else if(event.key==='Home')index=0;else if(event.key==='End')index=2;else return;event.preventDefault();setTab(order[index],true);});
  document.addEventListener('dataset-review-job',event=>loadJob(event.detail.id));
  function render(){renderSource();renderFlow();renderHistory();renderResult();renderRecords();renderBatch();setTab(tab);}
  async function refresh(expected=epoch){
    clearTimeout(timer);if(!selected?.available){render();return;}
    const id=selected.id,jobId=selectedJobId;
    try{
      const [data,records]=await Promise.all([api('/packages/'+encodeURIComponent(id)+'/overview'+(jobId?'?job='+jobId:'')),api('/packages/'+encodeURIComponent(id)+'/records')]);
      if(expected!==epoch||selected?.id!==id)return;
      overview=data;directory=records;job=data.dataset_job;
      if(job){const index=jobs.findIndex(j=>j.id===job.id);const value={...job,package_id:id,label:selected.label};if(index<0)jobs.unshift(value);else jobs[index]={...jobs[index],...value};}
      error('');render();
      if(!batch)loadBatch(id,expected);
      if(active(job?.status)||Object.entries(data.summary.signal_status_counts).some(([s,n])=>n&&active(s)))timer=setTimeout(()=>refresh(expected),1500);
    }catch(e){if(expected===epoch)error(e.message);}
  }
  async function loadJob(id){const expected=++epoch;issue=null;evidenceGroup=null;$('package-confirm').checked=false;clearTimeout(timer);try{const saved=await api('/package-jobs/'+id);if(expected!==epoch)return;selected=packages.find(p=>p.id===saved.package_id);if(!selected)throw Error(t('数据集已不在当前目录中。','Dataset is not registered.'));selectedJobId=id;job=saved;overview=null;directory=null;history.replaceState(null,'','/datasets?job='+id+'&lang='+lang+'&tab='+tab);render();await refresh(expected);}catch(e){if(expected===epoch)error(e.message);}}
  $('package-select').addEventListener('change',()=>{++epoch;clearTimeout(timer);clearTimeout(batchTimer);checkedRecords.clear();batch=null;selected=packages.find(p=>p.id===$('package-select').value);selectedJobId=null;issue=null;evidenceGroup=null;job=null;overview=null;directory=null;opening=false;$('package-confirm').checked=false;history.replaceState(null,'','/datasets?package='+encodeURIComponent(selected.id)+'&lang='+lang+'&tab='+tab);render();refresh(epoch);});
  $('package-confirm').addEventListener('change',updateButton);
  $('package-history').addEventListener('change',()=>{const id=$('package-history').value;if(id)loadJob(id);else{selectedJobId=null;history.replaceState(null,'','/datasets?package='+encodeURIComponent(selected.id)+'&lang='+lang+'&tab='+tab);refresh(++epoch);}});
  $('package-run').addEventListener('click',async()=>{const expected=++epoch;error('');$('package-run').disabled=true;try{const submitted=await api('/package-jobs',{package_id:selected.id,manifest_hash:selected.manifest_hash,confirmed:$('package-confirm').checked});if(expected!==epoch)return;selectedJobId=submitted.id;job=submitted;history.replaceState(null,'','/datasets?job='+job.id+'&lang='+lang+'&tab='+tab);await refresh(expected);}catch(e){if(expected===epoch){error(e.message);updateButton();}}});
  $('package-subject').addEventListener('change',()=>{subject=$('package-subject').value;renderRecords();});
  $('dataset-result').addEventListener('click',event=>{
    if(event.target.closest('[data-open-review]')){setTab('review');return;}
    if(event.target.closest('[data-show-setup]')){$('package-confirm').scrollIntoView?.({block:'center'});$('package-confirm').focus?.();return;}
    const attention=event.target.closest('[data-attention]'),evidence=event.target.closest('[data-evidence]'),button=event.target.closest('[data-record-subject]');
    if(attention){setTab('records');issue=attention.dataset.attention;subject='__all__';renderRecords();$('package-record-browser').scrollIntoView?.({block:'start'});}
    else if(evidence){setTab('overview');evidenceGroup=evidence.dataset.evidence;filter='issues';renderResult();$('dataset-details').open=true;$('dataset-details').scrollIntoView?.({block:'start'});}
    else if(button){setTab('records');issue=null;subject=button.dataset.recordSubject;renderRecords();$('package-record-browser').scrollIntoView?.({block:'start'});$('package-subject').focus?.();}
  });
  $('dataset-filters').addEventListener('click',event=>{const button=event.target.closest('[data-filter]');if(button){evidenceGroup=null;filter=button.dataset.filter;renderResult();}});
  $('package-records').addEventListener('click',async event=>{if(event.target.matches?.('[data-check-record],[data-select-records]'))return;if(event.target.closest('[data-clear-issue]')){issue=null;renderRecords();return;}const button=event.target.closest('[data-open-record]');if(!button||button.disabled||opening||!directory)return;const expected=epoch,id=selected.id;opening=true;renderRecords();error('');try{const intake=await api('/package-record-intakes',{package_id:id,record_id:button.dataset.openRecord,manifest_hash:directory.manifest_hash});if(expected!==epoch||selected?.id!==id)return;location.href='/?intake='+encodeURIComponent(intake.id)+'&lang='+lang;}catch(e){if(expected===epoch)error(e.message);}finally{if(expected===epoch){opening=false;renderRecords();}}});

  function renderBatch(){
    const box=$('batch-controls');if(!box)return;
    box.hidden=!directory||overview?.current_manifest===false;
    const rows=batch?.records||[],ready=rows.filter(r=>r.status==='ready').length;
    const status=batch?.status==='preview'?t('确认批量方案','Confirm batch plan'):batch?t('后台批次','Background batch'):'';
    box.innerHTML=`<div class="dataset-actions"><span>${checkedRecords.size} ${t('份已选','selected')}</span><button class="button primary small-button" data-batch-preview ${!checkedRecords.size||active(batch?.status)?'disabled':''}>${t('批量检查信号','Batch signal QC')}</button><button class="text-button" data-compare-reports ${checkedRecords.size<2?'disabled':''}>${t('比较报告','Compare reports')}</button></div>${batch?`<section class="batch-progress"><h3>${status} · ${batch.status==='preview'?ready+'/'+rows.length:(batch.finished||0)+'/'+(batch.runnable||0)}</h3><p class="small muted">${batch.scope==='recording'?t('整份记录 · 按已确认信息生成方案 · 依次后台运行','Full recordings · confirmed information · sequential background execution'):t('预览片段','Preview windows')}${batch.status==='interrupted'?t(' · 服务曾中断，请重新预览剩余记录',' · Interrupted; re-plan remaining recordings'):''}</p><details ${batch.status==='preview'?'open':''}><summary>${t('记录与方法','Recordings and methods')}</summary>${rows.map(r=>`<div class="batch-record"><b>${esc(r.record_id)}</b><span>${r.status==='ready'?t('可运行','Ready'):r.status==='unavailable'?t('需先确认','Confirmation needed'):label(r.status)}</span>${r.reason?`<small>${esc(r.reason)}</small>`:''}${r.request?`<small>${esc(r.request.selected_modules.join(' · '))} · ${esc(r.request.plan_id.slice(0,10))}</small><details><summary>${t('方法与参数','Methods and settings')}</summary>${(r.methods||[]).map(m=>`<p>${esc(m.name)} · ${esc(label(m.status))}<small>${esc(m.reason)}</small></p>`).join('')}<pre>${esc(JSON.stringify(r.request.qc_config,null,2))}</pre></details>`:''}${r.report_url?`<a href="${esc(r.report_url)}" target="_blank" rel="noopener">${t('报告','Report')}</a>`:''}</div>`).join('')}</details>${batch.status==='preview'?`<button class="button primary small-button" data-batch-submit ${!ready?'disabled':''}>${t('启动以上可运行记录','Start runnable recordings')}</button>`:active(batch.status)?`<button class="text-button" data-batch-cancel>${t('停止本批次','Stop this batch')}</button>`:`<small>${esc(label(batch.status))}</small>`}</section>`:''}`;
  }
  async function loadBatch(packageId,expected){try{const data=await api('/batches?package='+encodeURIComponent(packageId));if(expected!==epoch||selected?.id!==packageId||batch)return;batch=data.batches[0]||null;renderBatch();if(active(batch?.status))pollBatch();}catch(e){if(expected===epoch)error(e.message);}}
  async function pollBatch(){clearTimeout(batchTimer);if(!batch||!active(batch.status))return;const id=batch.id,pid=selected.id;try{const data=await api('/batches/'+id);if(batch?.id!==id||selected?.id!==pid)return;batch=data;renderBatch();if(active(batch.status))batchTimer=setTimeout(pollBatch,1500);else refresh(++epoch);}catch(e){error(e.message);}}
  $('package-records').addEventListener('change',event=>{
    if(event.target.matches('[data-select-records]')){$('package-records').querySelectorAll('[data-check-record]:not(:disabled)').forEach(c=>{c.checked=event.target.checked;c.checked?checkedRecords.add(c.dataset.checkRecord):checkedRecords.delete(c.dataset.checkRecord);});}
    else if(event.target.dataset.checkRecord){const id=event.target.dataset.checkRecord;event.target.checked?checkedRecords.add(id):checkedRecords.delete(id);}
    renderBatch();
  });
  $('batch-controls').addEventListener('click',async event=>{
    const button=event.target.closest('button');if(!button||button.disabled)return;
    const pid=selected.id;button.disabled=true;error('');
    try{
      if(button.hasAttribute('data-batch-preview')){const value=await api('/batch-previews',{package_id:pid,manifest_hash:directory.manifest_hash,record_ids:[...checkedRecords],scope:'recording'});if(selected?.id!==pid)return;batch=value;}
      else if(button.hasAttribute('data-batch-submit')){batch=await api('/batches',{preview_id:batch.id,preview_hash:batch.preview_hash,confirmed:true});pollBatch();}
      else if(button.hasAttribute('data-batch-cancel')){batch=await api('/batches/'+batch.id+'/cancel',{});pollBatch();}
      else if(button.hasAttribute('data-compare-reports')){const ids=[...checkedRecords].map(id=>directory.records.find(r=>r.id===id)?.signal_runs?.find(j=>j.status==='completed')?.id);if(ids.some(id=>!id))throw Error(t('每份所选记录都需要先生成报告。','Each selected recording needs a completed report.'));location.href='/comparisons?jobs='+ids.join(',')+'&lang='+lang+'&tab='+tab;}
    }catch(e){error(e.message);}finally{renderBatch();}
  });

  document.querySelectorAll('[data-lang]').forEach(b=>b.addEventListener('click',()=>{lang=b.dataset.lang;localStorage.setItem('ephys-qc.language',lang);translate();}));
  async function init(){try{const data=await api('/packages');packages=data.packages;jobs=data.jobs;admissionPolicy=data.admission_policy||null;selected=packages.find(p=>p.id===query.get('package'))||packages.find(p=>p.available)||packages[0]||null;translate();const id=query.get('job');if(id&&/^[a-f0-9]{32}$/.test(id))await loadJob(id);else await refresh(epoch);}catch(e){error(e.message);}}
  translate();init();
})();
