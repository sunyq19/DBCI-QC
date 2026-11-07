(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let items=[],examples=[],limit=6,revision=0,lastLoaded=0,category='data';
  const en=()=>window.QCI18n?.getLanguage?.()==='en', t=(a,b)=>en()?b:a;
  const status={not_run:['未运行','Not run'],needs_confirmation:['待确认','Confirm information'],running:['运行中','Running'],queued:['排队中','Queued'],completed:['有检查报告','Report available'],failed:['检查失败','Failed'],interrupted:['已中断','Interrupted'],cancelled:['已取消','Cancelled']};
  function href(value){if(typeof value!=='string'||!/^\/(?:\?|datasets\?|api\/v1\/packages\/[a-zA-Z0-9_-]+\/overview\/report(?:\?|$)|api\/v1\/jobs\/[a-f0-9]{32}\/report(?:\?|$))/.test(value))return '#';const url=new URL(value,'http://localhost');url.searchParams.set('lang',en()?'en':'zh-CN');return url.pathname+url.search;}
  function renderExamples(){
    const datasets=examples.filter(r=>r.kind==='dataset');
    $('demo-reports').hidden=!datasets.length;
    $('example-shortcut').hidden=!datasets.length;
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
      return available?`<a class="demo-report" href="${esc(href(r.url))}" aria-label="${esc(label+' · '+t('查看报告','View report'))}">${content}</a>`:`<div class="demo-report unavailable" aria-disabled="true">${content}</div>`;
    }).join('');
  }
  function render(){
    const query=$('data-search').value.trim().toLowerCase();
    const rows=items.filter(r=>(r.category||'data')===category).filter(r=>[r.label,r.format,r.modality,r.kind==='dataset'?'数据集 dataset':'记录 recording'].join(' ').toLowerCase().includes(query));
    $('data-library-count').textContent=String(items.filter(r=>r.category!=='validation').length);
    $('library-data').setAttribute('aria-pressed',String(category==='data'));
    $('library-validation').setAttribute('aria-pressed',String(category==='validation'));
    $('library-category-note').hidden=category!=='validation';
    $('library-category-note').textContent=t('用于验证缺件、信息不一致和读取边界；检查发现会原样保留。','Cases for missing files, metadata differences and reader limits. Findings are preserved.');
    $('data-library-list').innerHTML=rows.slice(0,limit).map(r=>{
      const target=r.latest_run_url||r.url, action=r.latest_run_url?(r.status==='completed'?t('查看报告','View report'):t('查看运行','View run')):t('打开','Open');
      return `<div class="data-library-item ${r.available?'':'unavailable'}"><span class="data-kind">${r.kind==='dataset'?t('数据集','Dataset'):esc(r.format||t('记录','Recording'))}</span><a class="data-library-label" href="${esc(href(target))}"><strong data-i18n-skip>${esc(r.label)}</strong><small>${r.kind==='dataset'?`${r.subjects??'—'} ${t('个体','subjects')} · ${r.records??'—'} ${t('记录','recordings')}`:esc(status[r.status]?.[en()?1:0]||r.status)}${r.retention?.state==='expired'?` · ${t('副本已到期，报告保留','Upload expired; reports retained')}`:r.available?'':` · ${t('来源不可用','Source unavailable')}`} </small></a><span class="data-library-actions"><a class="data-open" href="${esc(href(target))}">${action}</a>${r.latest_run_url && r.available?`<a class="data-secondary" href="${esc(href(r.url))}">${t('打开数据','Open data')}</a>`:''}</span></div>`;
    }).join('')||`<p class="small muted">${items.length?t('暂无匹配数据','No matching data'):t('尚未上传数据。上传副本保留 7 天，报告保留。','No uploads yet. Uploaded copies are kept for 7 days; reports are retained.')}</p>`;
    $('data-library-more').hidden=rows.length<=limit;$('data-library-more').textContent=t(`显示更多（${rows.length-limit}）`,`Show more (${rows.length-limit})`);
    $('data-search').placeholder=t('搜索数据名称','Search data');renderExamples();
  }
  async function refresh(){const request=++revision;try{const response=await fetch('/api/v1/data',{cache:'no-store'});if(!response.ok)throw Error('directory');const data=await response.json();if(request!==revision)return;items=data.items;examples=data.examples||[];lastLoaded=Date.now();render();$('data-library-error').hidden=true;}catch{if(request===revision){$('data-library-error').textContent=t('数据目录暂时不可用，请重试。','Data directory unavailable. Retry.');$('data-library-error').hidden=false;if(!examples.length)$('demo-report-list').innerHTML='<p class="small muted">'+t('示例目录暂不可用，请重试。','Example directory unavailable. Retry.')+'</p><button type="button" class="text-button" data-examples-retry>'+t('重试','Retry')+'</button>';}}}
  $('demo-report-list').addEventListener('click',event=>{if(event.target.closest('[data-examples-retry]'))refresh()});
  $('data-search').addEventListener('input',()=>{limit=6;render()});
  for(const name of ['data','validation'])$('library-'+name).addEventListener('click',()=>{category=name;limit=6;render()});
  $('data-library-more').addEventListener('click',()=>{limit+=12;render()});
  $('data-library-refresh').addEventListener('click',refresh);
  window.addEventListener('qc:languagechange',render);window.addEventListener('focus',()=>{if(Date.now()-lastLoaded>30000)refresh()});
  try{$('demo-reports').open=window.localStorage.getItem('qc.examples.open')!=='false'}catch{}
  $('demo-reports').addEventListener('toggle',()=>{try{window.localStorage.setItem('qc.examples.open',String($('demo-reports').open))}catch{}});
  $('example-shortcut').addEventListener('click',()=>{$('demo-reports').open=true});
  window.QCDataLibrary={refresh};refresh();
})();
