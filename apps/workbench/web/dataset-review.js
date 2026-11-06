/* D04 UI adapter. Machine evidence and human decisions remain independent. */
(() => {
  'use strict';
  const root=document.getElementById('dataset-review');
  let context={},value=null,key='',ticket=0,busy=false,editing=null,filter='pending',message='';
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const t=(zh,en)=>context.lang==='en'?en:zh;
  const labels={pending:['待处理','Pending'],needs_fix:['需整改','Needs correction'],restricted_use:['限定用途','Restricted use'],follow_up:['登记跟踪','Follow up'],acceptable_difference:['已说明差异','Explained difference'],pending_review:['待审核','Awaiting review'],blocked:['需整改后复验','Correction and retest required'],conditional:['限定用途使用','Use with restrictions'],accepted:['本次范围内已审核','Reviewed within this scope'],resolved:['复验已消除','Resolved on retest'],new:['新增待处理','New finding'],unchanged:['仍存在','Still present'],changed:['证据有变化','Evidence changed'],not_rechecked:['本次未复查','Not rechecked'],scope_changed:['范围或规则改变','Scope or rules changed'],conflict:['资料不符','Mismatch'],review:['待核对','Review'],unassessed:['未评','Unassessed'],pass:['一致','Consistent']};
  const label=k=>labels[k]?.[context.lang==='en'?1:0]||k;
  const title=r=>context.lang==='en'?r.label_en:r.label;
  const base=()=>'/api/v1/package-jobs/'+context.job.id+'/review';
  const badge=(k)=>`<span class="review-badge ${esc(k)}">${esc(label(k))}</span>`;
  async function api(url,body){const response=await fetch(url,{cache:'no-store',method:body?'POST':'GET',headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});const data=await response.json();if(!response.ok){const e=Error(data.error||`HTTP ${response.status}`);e.status=response.status;throw e;}return data;}
  function status(){const box=document.getElementById('review-message');if(box){box.textContent=message;box.hidden=!message;}}
  function form(row){
    const d=row.decision||{};
    const field=(name,zh,en,wide=false,multiline=false)=>`<label class="${wide?'wide':''}">${t(zh,en)}${multiline?`<textarea name="${name}" maxlength="2000" required>${esc(d[name]||'')}</textarea>`:`<input name="${name}" maxlength="100" value="${esc(d[name]||'')}" ${name==='owner'?'':'required'}>`}</label>`;
    return `<section class="review-editor"><div class="review-toolbar"><h3>${t('记录处理意见','Record a decision')} · ${esc(title(row))}</h3><button class="text-button" data-review-close>${t('收起','Close')}</button></div><p class="review-target">${esc(row.target)}</p><form data-review-save>
    <div class="review-form-grid"><label>${t('处理方式','Disposition')}<select name="disposition">${['needs_fix','restricted_use','follow_up','acceptable_difference'].map(k=>`<option value="${k}" ${d.disposition===k?'selected':''}>${label(k)}</option>`).join('')}</select></label>${field('reviewer','填写人（自行声明）','Reviewer (self-declared)')}
    ${field('impact','影响或允许的用途','Impact or permitted use',true,true)}${field('note','判断依据','Decision basis',true,true)}
    <label class="wide">${t('下一步','Next step')}<textarea name="action" maxlength="2000">${esc(d.action||'')}</textarea></label>${field('owner','负责人','Owner')}
    </div><p class="review-note">${t('需整改、限定用途和登记跟踪均需填写下一步与负责人。','A next step and owner are required for corrections, restrictions and follow-up.')}</p><button class="button primary small-button" ${busy?'disabled':''}>${t('保存意见','Save decision')}</button></form></section>`;
  }
  function render(){
    if(!context.job||context.job.status!=='completed'){
      root.innerHTML=`<section class="panel"><h2>${t('完成资料检查后开展审核','Review after dataset checks')}</h2><p class="review-note">${t('先确认左侧范围并运行“检查资料”。','Confirm the scope on the left and run dataset checks.')}</p></section>`;return;
    }
    if(!value){root.innerHTML=`<section class="panel"><p>${t('正在读取审核记录…','Loading review…')}</p><p id="review-message" role="status" class="review-message" hidden></p><button class="text-button" data-review-refresh>${t('重新读取','Reload')}</button></section>`;status();return;}
    const url=base(),final=value.final,prev=value.previous;
    const rows=value.rows.filter(r=>filter==='all'||filter==='pending'&&r.disposition==='pending'||filter==='reviewed'&&r.disposition!=='pending').sort((a,b)=>(a.status==='unassessed')-(b.status==='unassessed'));
    const changeRows=(prev?.rows||[]).filter(r=>r.change!=='unchanged');
    const delta=prev?`<section class="panel"><div class="review-toolbar"><h3>${t('本次复验变化','Changes on retest')}</h3><a class="small" href="/datasets?job=${esc(prev.job_id)}&tab=review&lang=${context.lang}">${t('查看上次','Previous run')}</a></div><p class="review-note">${Object.entries(prev.counts).map(([k,n])=>`${label(k)} ${n}`).join(' · ')}</p>${changeRows.length?`<div class="dataset-scroll review-changes"><table class="dataset-table"><thead><tr><th>${t('检查项','Check')}</th><th>${t('对象','Target')}</th><th>${t('变化','Change')}</th></tr></thead><tbody>${changeRows.map(r=>`<tr><td>${esc(title(r))}</td><td>${esc(r.target)}</td><td>${badge(r.change)}</td></tr>`).join('')}</tbody></table></div>`:''}<p class="review-note">${t('只有相同规则、相同范围内重新检查为一致，才计为已消除。','Resolved requires a passing recheck with the same rules and scope.')}</p></section>`:'';
    const issues=rows.map(r=>`<details class="review-issue"><summary><span class="review-issue-copy"><strong>${esc(title(r))}</strong><small class="review-target">${esc(r.target)}</small></span>${badge(r.disposition)}</summary><div class="review-evidence"><p>${esc(r.message)}</p><small>${label(r.status)}</small>${r.decision?`<p>${esc(r.decision.impact)}</p><p>${esc(r.decision.action)}</p>`:''}<details><summary>${t('测量值与文件','Measurements and files')}</summary><p class="review-target">${(r.files||[]).map(esc).join('<br>')}</p><pre>${esc(JSON.stringify(r.observed,null,2))}</pre></details></div><button class="text-button" data-review-edit="${esc(r.id)}">${r.decision?t('修改处理意见','Edit decision'):t('记录处理意见','Record decision')}</button></details>`).join('');
    const row=value.rows.find(r=>r.id===editing);
    root.innerHTML=`<section class="panel"><div class="review-heading"><div><h2>${label(value.outcome)}</h2><p>${final?`${esc(final.reviewer)} · r${value.revision}`:t('逐项说明影响，再确认本次结论。','Record the impact of each finding, then confirm the outcome.')}</p></div><button class="text-button" data-review-refresh>${t('刷新','Refresh')}</button></div>${value.engineering_demo?`<p class="review-demo">${t('公开数据副本 · 工程演示','Public-data copy · Engineering demo')}</p>`:''}<div class="review-stats"><div><b>${value.summary.pending}</b><small>${t('待处理','Pending decisions')}</small></div><div><b>${value.summary.needs_fix}</b><small>${t('已登记需整改','Corrections registered')}</small></div><div><b>${prev?.counts?.resolved||0}</b><small>${t('复验已消除','Resolved on retest')}</small></div></div><div class="review-actions"><a class="button primary small-button" href="${url}/report?lang=${context.lang}" target="_blank" rel="noopener">${t('审核报告','Review report')}</a><a href="${url}/pdf?lang=${context.lang}">${t('下载 PDF','Download PDF')}</a><button class="text-button" data-review-retest ${busy?'disabled':''}>${t('重新检查并对比','Recheck and compare')}</button></div><p class="review-note">${t('修正本地资料后，可与本次结果对比。每次结果和审核历史分别保存。','After correcting local files, compare against this run. Results and review revisions are retained separately.')}</p><p id="review-message" role="status" class="review-message" hidden></p></section>
    ${delta}<section class="panel"><div class="review-toolbar"><h3>${t('处理清单','Action register')}</h3><select id="review-filter" aria-label="${t('处理状态','Decision status')}">${[['pending',t('待处理','Pending')],['reviewed',t('已记录意见','With a decision')],['all',t('全部','All')]].map(([k,v])=>`<option value="${k}" ${filter===k?'selected':''}>${v}</option>`).join('')}</select></div><p class="review-note">${t(`共 ${value.summary.findings} 项，其中 ${value.summary.unassessed} 项因证据不足未评。`,` ${value.summary.findings} findings, including ${value.summary.unassessed} unassessed checks.`)}</p>${issues||`<p class="review-note">${t('此分类没有待处理事项。','No findings in this category.')}</p>`}${row?form(row):''}
    <details class="review-confirm"><summary>${t('确认本次结论','Confirm review outcome')}</summary><p class="review-note">${t('有需整改项时可确认整改要求；其余情况需先处理所有待处理项。结论仅用于当前声明范围。','A correction-required decision may be confirmed immediately; otherwise address all pending items first. The outcome applies only to the declared scope.')}</p><p>${t('按现有意见：','Based on current decisions: ')}${label(value.proposed_outcome)}</p><form data-review-finalize><div class="review-form-grid"><label>${t('填写人（自行声明）','Reviewer (self-declared)')}<input name="reviewer" maxlength="100" required></label><label>${t('本次审核用途','Purpose of this review')}<input name="purpose" maxlength="2000" required></label></div><div class="review-actions"><button class="button primary small-button" ${busy||value.proposed_outcome==='pending_review'?'disabled':''}>${t('确认并保存结论','Confirm and save outcome')}</button></div></form></details>
    </section><details class="panel review-history"><summary>${t('审核历史','Review history')} · ${value.history.length}</summary><ul>${value.history.map(r=>`<li>r${r.revision} · ${esc(r.reviewer)} · ${esc(r.recorded_at)}${r.final?' · '+label(r.final.outcome):''}</li>`).join('')}</ul><p class="review-note">${t('这是本地处理记录，不是医院验收或经认证的电子签名。','These local review records are not hospital acceptance or authenticated electronic signatures.')}</p></details>`;
    status();
  }
  async function load(force=false){
    const next=[context.job?.id,context.job?.status,context.lang].join(':');
    if(!force&&next===key){return;}
    key=next;const expected=++ticket;value=null;editing=null;message='';busy=false;render();
    if(context.job?.status!=='completed')return;
    try{const result=await api(base());if(expected!==ticket)return;value=result;render();}
    catch(e){if(expected===ticket){message=e.message;status();}}
  }
  document.addEventListener('dataset-context',event=>{
    const prior=context.job?.id;context=event.detail;
    if(prior!==context.job?.id){ticket++;key='';value=null;editing=null;busy=false;message='';}
    if(context.tab==='review')load();
  });
  root.addEventListener('change',event=>{if(event.target.id==='review-filter'){filter=event.target.value;editing=null;render();}});
  root.addEventListener('click',async event=>{
    const b=event.target.closest('button');if(!b||b.disabled||busy)return;
    if(b.hasAttribute('data-review-refresh')){await load(true);return;}
    if(b.hasAttribute('data-review-edit')){editing=b.dataset.reviewEdit;render();root.querySelector('.review-editor')?.scrollIntoView({block:'center',behavior:'smooth'});return;}
    if(b.hasAttribute('data-review-close')){editing=null;render();return;}
    if(b.hasAttribute('data-review-retest')){
      const expected=ticket;busy=true;b.disabled=true;message='';status();
      try{const result=await api('/api/v1/package-jobs',{package_id:context.package_id,manifest_hash:context.manifest_hash,confirmed:true,baseline_job_id:context.job.id});if(expected!==ticket)return;document.dispatchEvent(new CustomEvent('dataset-review-job',{detail:{id:result.id}}));}
      catch(e){if(expected===ticket){message=e.message;status();}}
      finally{if(expected===ticket){busy=false;b.disabled=false;}}
    }
  });
  root.addEventListener('submit',async event=>{
    const form=event.target;if(!form.matches('[data-review-save],[data-review-finalize]'))return;event.preventDefault();if(busy||!value)return;
    const inputs=new FormData(form),finalize=form.hasAttribute('data-review-finalize');
    const body={expected_revision:value.revision,result_hash:value.result_hash,reviewer:inputs.get('reviewer'),changes:[],finalize};
    if(finalize)body.purpose=inputs.get('purpose');
    else{const row=value.rows.find(r=>r.id===editing);if(!row)return;body.changes=[{check_id:row.id,evidence_id:row.evidence_id,...Object.fromEntries(['disposition','impact','note','action','owner'].map(k=>[k,inputs.get(k)]))}];}
    const expected=ticket;busy=true;form.querySelector('button').disabled=true;message='';status();
    try{const result=await api(base(),body);if(expected!==ticket)return;value=result;editing=null;message=t('已保存，历史版本保留。','Saved. Previous revisions are retained.');busy=false;render();}
    catch(e){if(expected===ticket){message=e.status===409?t('记录已被更新。请先复制未保存内容，再点击刷新。','The record changed. Copy your unsaved text, then refresh.'):e.message;status();}}
    finally{if(expected===ticket){busy=false;form.querySelector('button').disabled=false;}}
  });
})();
