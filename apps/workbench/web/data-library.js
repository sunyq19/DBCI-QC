(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let publicOnly=false,items=[],examples=[],limit=6,revision=0,lastLoaded=0,category='data',archived=false,busy=false;
  let cached=false;try{const data=JSON.parse($('example-cache')?.textContent||'null');if(data){if(!cached)examples=data.examples||[];cached=true;}}catch{}
  const en=()=>window.QCI18n?.getLanguage?.()==='en', t=(a,b)=>en()?b:a;
  const status={not_run:['未运行','Not run'],needs_confirmation:['待确认','Confirm information'],running:['运行中','Running'],queued:['排队中','Queued'],completed:['有检查报告','Report available'],failed:['检查失败','Failed'],interrupted:['已中断','Interrupted'],cancelled:['已取消','Cancelled']};
  const reportId=report=>report.archive_id||(report.job_id?'report:'+report.job_id:null);
  const rowReports=row=>row.workflow_groups?.length?row.workflow_groups.flatMap(g=>g.runs):row.recent_reports||[];
  const isArchived=(report,row)=>Boolean(report.archived??row.archived);
  const archivedReports=row=>rowReports(row).filter(report=>isArchived(report,row));
  function menuButton(action,id,label,group=false){return `<button type="button" ${action==='delete'?'class="library-danger"':''} data-library-action="${action}" data-id="${esc(id)}" ${group?'data-library-group="true"':''} ${busy?'disabled':''}>${label}</button>`;}
  function visibleRow(row){
    const keep=report=>isArchived(report,row)===archived;
    return {...row,recent_reports:(row.recent_reports||[]).filter(keep),workflow_groups:(row.workflow_groups||[]).flatMap(group=>{
      const runs=group.runs.filter(keep);if(!runs.length)return [];
      const sameLatest=reportId(group.latest)===reportId(runs[0]);
      return [{...group,runs,latest:sameLatest?group.latest:runs[0],...sameLatest?{}:{label:runs[0].label,label_en:runs[0].label_en}}];
    })};
  }
  function href(value){if(typeof value!=='string'||!/^\/(?:\?|examples\/[a-f0-9]{16}\/[a-zA-Z0-9_./-]+|datasets\?|api\/v1\/packages\/[a-zA-Z0-9_-]+\/overview\/report(?:\?|$)|api\/v1\/jobs\/[a-f0-9]{32}\/(?:report|visualizations)(?:\?|$))/.test(value))return '#';const url=new URL(value,'http://localhost');url.searchParams.set('lang',en()?'en':'zh-CN');return url.pathname+url.search;}
  function sourceMarkup(value){
    if(!value)return '';
    const rows=value.sources||[value];
    const links=rows.map(row=>{
      const url=row.url||row.dataset_url||'',name=row.name||row.dataset||row.dataset_id||'',rawVersion=row.version||row.snapshot||row.version_doi||'',version=/^[a-f0-9]{32,64}$/i.test(rawVersion)?'':rawVersion.replace(/^doi:.*\.v(?=[0-9])/, '');
      let safe=false;try{const parsed=new URL(url);safe=['https:','http:'].includes(parsed.protocol)&&!parsed.username&&!parsed.password;}catch{}
      return name&&safe?`<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" data-i18n-skip>${esc(name)}${version?' · '+esc(version):''}</a> <span data-i18n-skip>${esc(row.license||'')}</span>`:'';
    }).filter(Boolean);
    return links.length?`<div class="public-source">${t('来源：','Source: ')}${links.join(' · ')}</div>`:'';
  }
  function reportRows(reports){
    return `<div class="data-library-reports" aria-label="${t('最近的检查报告','Recent QC reports')}">${reports.map(report=>{
      const stamp=new Date(report.created_at);
      const time=Number.isNaN(stamp.valueOf())?'':stamp.toLocaleString(en()?'en-GB':'zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
      const id=reportId(report),label=en()?report.label_en||report.label:report.label;
      const actions=archived?menuButton('restore',id,t('恢复','Restore'))+menuButton('delete',id,t('彻底删除','Delete permanently')):menuButton('archive',id,t('归档','Archive'));
      const menu=id&&!['running','queued','cancelling'].includes(report.status)?`<details class="library-entry-menu library-report-menu"><summary aria-label="${esc(t('报告操作：','Report actions: ')+label+' · '+time)}">⋯</summary><div>${actions}</div></details>`:'';
      return `<div class="library-report-row"><span class="library-report-name"><strong data-i18n-skip>${esc(label)}</strong><time datetime="${esc(report.created_at)}">${esc(time)}</time></span><span class="library-report-links"><a href="${esc(href(report.url))}">${report.report_available===false?t('查看运行','View run'):t('查看报告','View report')}</a></span>${menu}</div>`;
    }).join('')}</div>`;
  }
  function workflowRows(groups){
    const groupMarkup=group=>{
      const latest=group.latest, runs=group.runs||[];
      const scope=group.scope==='recording'?t('整份检查','Full recording'):t('片段检查','Selected interval');
      const duration=Number.isFinite(group.duration_seconds)?` · ${Number(group.duration_seconds.toFixed(2))}${t(' 秒',' s')}`:'';
      const meta=[scope+duration,group.channels?t(`${group.channels} 通道`,`${group.channels} channels`):'',group.requirements_unmet?t('方案条件未满足','Workflow requirements unmet'):group.scored_items?t(`已选 ${group.scored_items} 项计分`,`${group.scored_items} scoring checks selected`):''].filter(Boolean).join(' · ');
      return `<section class="library-workflow">${reportRows([{...latest,label:group.label,label_en:group.label_en}])}<p class="library-workflow-meta">${esc(meta)}${group.current_confirmation===false?' · '+t('此前确认配置','Previous confirmation'):''}${latest.status!=='completed'?' · '+esc(status[latest.status]?.[en()?1:0]||latest.status):''}</p>${runs.length>1?`<details class="library-workflow-history"><summary>${t('历次运行','Previous runs')} · ${runs.length-1}</summary>${reportRows(runs.slice(1))}</details>`:''}</section>`;
    };
    // Keep the newest distinct routes visible; repeated configurations cannot
    // push the other comparison route out of the compact data card.
    const primary=[],families=new Set();
    for(const group of groups){
      const family=group.method_family||group.id;
      if(primary.length<3&&!families.has(family)&&!group.requirements_unmet&&group.current_confirmation!==false){primary.push(group);families.add(family);}
    }
    if(!primary.length&&groups.length)primary.push(groups[0]);
    const other=groups.filter(g=>!primary.includes(g));
    return `<div class="data-library-workflows">${primary.map(groupMarkup).join('')}${other.length?`<details class="library-more-workflows"><summary>${t('其他配置与历史方案','Other configurations and past workflows')} · ${other.length}</summary>${other.map(groupMarkup).join('')}</details>`:''}</div>`;
  }
  function renderExamples(){
    const datasets=examples.filter(r=>r.kind==='dataset');
    $('demo-reports').hidden=!datasets.length;
    $('demo-reports-count').textContent=String(datasets.length);
    $('demo-reports-title').textContent=t('示例数据集','Example datasets');
    $('demo-reports').setAttribute('aria-label',t('示例数据集','Example datasets'));
    $('demo-reports-caption').textContent=t('四类公开样本，点击查看检查结果。','Four public sample collections. Open their results directly.');
    $('demo-report-list').innerHTML=datasets.map(r=>{
      const available=r.available!==false;
      const reports=r.status==='report_unavailable'?t('报告暂不可用','Reports unavailable'):t(`报告 ${r.reported||0}/${r.records||0}`,`Reports ${r.reported||0}/${r.records||0}`);
      const description=en()?r.description_en||r.description:r.description;
      const label=en()?r.label_en||r.label:r.label;
      const meta=t(`${r.subjects??'—'} 个体 · ${r.records??'—'} 份记录`,`${r.subjects??'—'} subjects · ${r.records??'—'} recordings`);
      const content=`<span class="demo-report-copy"><strong>${esc(label)}${r.formats?`<small class="example-format">${esc(r.formats)}</small>`:''}</strong>${description?`<span>${esc(description)}</span>`:''}<small>${esc(meta)} · ${esc(reports)}</small></span><span class="demo-report-end">${available?t('查看报告','View report'):t('文件不可用','Files unavailable')}</span>`;
      return `<div class="public-example">${available?`<a class="demo-report" href="${esc(href(en()?r.url_en||r.url:r.url))}" aria-label="${esc(label+' · '+t('查看报告','View report'))}">${content}</a>`:`<div class="demo-report unavailable" aria-disabled="true">${content}</div>`}${sourceMarkup(r.source)}</div>`;
    }).join('');
  }
  function render(){
    const query=$('data-search').value.trim().toLowerCase();
    const rows=items.filter(r=>(archived?(r.archived||archivedReports(r).length):!r.archived)&&(r.category||'data')===category).filter(r=>[r.label,r.format,r.modality,r.kind==='dataset'?'数据集 dataset':'记录 recording'].join(' ').toLowerCase().includes(query)).map(visibleRow);
    const archivedCount=items.reduce((n,r)=>n+Math.max(archivedReports(r).length,r.archived?1:0),0);
    $('data-library-count').textContent=String(items.filter(r=>!r.archived&&r.category!=='validation').length);
    $('library-active').textContent=t('当前','Active');$('library-active').setAttribute('aria-pressed',String(!archived));
    $('library-archived').textContent=t(`归档${archivedCount?' · '+archivedCount:''}`,`Archive${archivedCount?' · '+archivedCount:''}`);$('library-archived').setAttribute('aria-pressed',String(archived));
    $('library-empty-archive').hidden=!archived||!archivedCount;$('library-empty-archive').disabled=busy;$('library-empty-archive').textContent=t('清空归档','Empty archive');
    $('library-data').setAttribute('aria-pressed',String(category==='data'));
    $('library-validation').setAttribute('aria-pressed',String(category==='validation'));
    $('library-category-note').hidden=category!=='validation';
    $('library-category-note').textContent=t('用于验证缺件、信息不一致和读取边界；检查发现会原样保留。','Cases for missing files, metadata differences and reader limits. Findings are preserved.');
    $('data-library-list').innerHTML=rows.slice(0,limit).map(r=>{
      const reports=Array.isArray(r.recent_reports)?r.recent_reports:[];
      const workflows=Array.isArray(r.workflow_groups)?r.workflow_groups:[];
      const target=r.available?r.url:r.latest_run_url||r.url;
      const reportsMarkup=workflows.length?workflowRows(workflows):`${reports.length?reportRows(reports.slice(0,2)):''}${reports.length>2?`<details class="data-library-older"><summary>${t('更早的报告','Earlier reports')} · ${reports.length-2}</summary>${reportRows(reports.slice(2))}</details>`:''}`;
      const actions=archived?menuButton('restore',r.id,t('恢复全部','Restore all'),true)+menuButton('delete',r.id,t('删除本组归档','Delete this archive group'),true):menuButton('archive',r.id,t('归档全部','Archive all'));
      const noCurrent=!archived&&!reports.length&&!workflows.length&&r.archived_reports>0;
      const label=`<strong data-i18n-skip>${esc(r.label)}</strong><small>${r.kind==='dataset'?`${r.subjects??'—'} ${t('个体','subjects')} · ${r.records??'—'} ${t('记录','recordings')}`:workflows.length?t(`${workflows.length} 套方案 · ${workflows.reduce((n,g)=>n+g.runs.length,0)} 次运行`,`${workflows.length} workflows · ${workflows.reduce((n,g)=>n+g.runs.length,0)} runs`):noCurrent?t('报告均已归档','All reports archived'):esc(status[r.status]?.[en()?1:0]||r.status)}${r.retention?.state==='expired'?` · ${t('副本已到期，报告保留','Upload expired; reports retained')}`:r.available?'':` · ${t('来源不可用','Source unavailable')}`}</small>`;
      return `<div class="data-library-item ${r.available?'':'unavailable'}"><span class="data-kind">${r.kind==='dataset'?t('数据集','Dataset'):esc(r.format||t('记录','Recording'))}</span>${archived?`<div class="data-library-label">${label}</div>`:`<a class="data-library-label" href="${esc(href(target))}">${label}</a>`}<details class="library-entry-menu"><summary aria-label="${esc(t('数据操作：','Data actions: ')+r.label)}">⋯</summary><div>${actions}</div></details>${sourceMarkup(r.source)}${reportsMarkup}</div>`;
    }).join('')||`<p class="small muted">${archived?t('归档为空。','Archive is empty.'):items.some(r=>!r.archived)?t('暂无匹配数据','No matching data'):publicOnly?t('暂无已登记的公开数据。上传仅用于本次检查。','No registered public data. Uploads are temporary.'):t('尚未上传数据。上传副本保留 7 天，报告保留。','No uploads yet. Uploaded copies are kept for 7 days; reports are retained.')}</p>`;
    $('data-library-more').hidden=rows.length<=limit;$('data-library-more').textContent=t(`显示更多（${rows.length-limit}）`,`Show more (${rows.length-limit})`);
    $('data-search').placeholder=t('搜索数据名称','Search data');renderExamples();
  }
  async function mutate(action,selection){
    if(busy)return;busy=true;render();$('data-library-error').hidden=true;$('data-library-message').hidden=true;
    const post=async(name,body)=>{
      const response=await fetch('/api/v1/data/'+name,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      const data=await response.json();if(!response.ok)throw Error(data.error||t('操作失败，请重试。','Action failed. Retry.'));return data;
    };
    try{
      let result;
      if(action==='delete'){
        const preview=await post('delete-preview',selection);
        const name=preview.items===1?`“${preview.labels[0]}”`:t(`${preview.items} 项归档数据`,`${preview.items} archived items`);
        const message=preview.reports_only?t(`彻底删除${name}？\n将删除 ${preview.runs} 次检查的报告、图表及结果文件。输入数据和其他报告保留。此操作无法恢复。`,`Permanently delete ${name}?\nThis removes ${preview.runs} reports, charts and result files. Input data and other reports are kept. This cannot be undone.`):t(`彻底删除${name}？\n将一并删除 ${preview.runs} 次检查的记录、报告和平台保存的文件副本。此操作无法恢复。`,`Permanently delete ${name}?\nThis removes ${preview.runs} runs, their reports and stored upload copies. This cannot be undone.`);
        if(!window.confirm(message))return;
        result=await post('delete',{...selection,token:preview.token,confirmed:true});
      }else result=await post(action,selection);
      await refresh();
      if(window.dispatchEvent)window.dispatchEvent(new CustomEvent('qc:librarychange',{detail:result}));
      $('data-library-message').textContent=result.cleanup_pending?t('记录已删除，部分文件将在后台继续清理。','Records deleted; remaining files will be cleaned in the background.'):action==='archive'?t('已移至归档，可在归档中恢复。','Moved to archive. You can restore it there.'):action==='restore'?t('已恢复到当前数据。','Restored to active data.'):t('已彻底删除。','Permanently deleted.');
      $('data-library-message').hidden=false;
    }catch(error){$('data-library-error').textContent=error.message;$('data-library-error').hidden=false;}
    finally{busy=false;render();}
  }
  async function refresh(){
    const request=++revision;
    try{
      const response=await fetch('/api/v1/data',{cache:'no-store'});
      if(!response.ok)throw Error('directory');
      const data=await response.json();if(request!==revision)return;
      publicOnly=Boolean(data.public_only);items=data.items;if(!cached)examples=data.examples||[];
      if(!lastLoaded&&items.length)$('data-library').open=true;
      lastLoaded=Date.now();render();$('data-library-error').hidden=true;
    }catch{
      if(request===revision){
        $('data-library-error').textContent=t('数据目录暂时不可用，请重试。','Data directory unavailable. Retry.');
        $('data-library-error').hidden=false;
        if(!lastLoaded){$('data-library-list').innerHTML='';$('data-library-more').hidden=true;}
        if(!examples.length)$('demo-report-list').innerHTML='<p class="small muted">'+t('示例目录暂不可用，请重试。','Example directory unavailable. Retry.')+'</p><button type="button" class="text-button" data-examples-retry>'+t('重试','Retry')+'</button>';
      }
    }
  }
  $('demo-report-list').addEventListener('click',event=>{if(event.target.closest('[data-examples-retry]'))refresh()});
  $('data-search').addEventListener('input',()=>{limit=6;render()});
  for(const name of ['active','archived'])$('library-'+name).addEventListener('click',event=>{event?.preventDefault();event?.stopPropagation();$('data-library').open=true;archived=name==='archived';category='data';limit=6;$('data-search').value='';$('data-library-message').hidden=true;render()});
  $('data-library-list').addEventListener('click',event=>{const button=event.target.closest('[data-library-action]');if(button){event.preventDefault();let ids=[button.dataset.id];if(button.dataset.libraryGroup){const row=items.find(r=>r.id===button.dataset.id);if(!row)return;if(!row.archived)ids=[...new Set(archivedReports(row).map(reportId).filter(Boolean))];}mutate(button.dataset.libraryAction,{ids})}});
  $('library-empty-archive').addEventListener('click',()=>mutate('delete',{all_archived:true}));
  for(const name of ['data','validation'])$('library-'+name).addEventListener('click',()=>{category=name;limit=6;render()});
  $('data-library-more').addEventListener('click',()=>{limit+=12;render()});
  window.addEventListener('qc:languagechange',render);window.addEventListener('focus',()=>{if(Date.now()-lastLoaded>30000)refresh()});
  try{$('demo-reports').open=window.localStorage.getItem('qc.examples.open')!=='false'}catch{}
  $('demo-reports').addEventListener('toggle',()=>{try{window.localStorage.setItem('qc.examples.open',String($('demo-reports').open))}catch{}});
  window.QCDataLibrary={refresh};renderExamples();refresh();
})();
