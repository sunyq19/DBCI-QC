(() => {
  'use strict';
  const $=id=>document.getElementById(id), esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let items=[],examples=[],limit=6,revision=0,category='data';
  const en=()=>window.QCI18n?.getLanguage?.()==='en', t=(a,b)=>en()?b:a;
  const status={not_run:['未运行','Not run'],needs_confirmation:['待确认','Confirm information'],running:['运行中','Running'],queued:['排队中','Queued'],completed:['有检查报告','Report available'],failed:['检查失败','Failed'],interrupted:['已中断','Interrupted'],cancelled:['已取消','Cancelled']};
  function href(value){if(typeof value!=='string'||!/^\/(?:\?|datasets\?)/.test(value))return '#';const url=new URL(value,'http://localhost');url.searchParams.set('lang',en()?'en':'zh-CN');return url.pathname+url.search;}
  function renderExamples(){
    $('demo-reports').hidden=!examples.length;
    $('demo-reports-title').textContent=t('示例报告','Example reports');
    $('demo-reports-caption').textContent=t('先看已完成的结果，也可以上传自己的数据。','Explore completed results, or upload your own data.');
    $('demo-report-list').innerHTML=examples.map(r=>{
      const record=r.kind==='record',value=record&&Number.isFinite(r.score)?r.score.toFixed(2):null;
      const scope=r.scope==='recording'?t('整份检查','Full recording'):t('片段检查','Window check');
      const detail=record?`${scope}${r.scope==='recording'&&Number.isFinite(r.duration_seconds)?` · ${r.duration_seconds.toFixed(1)} s`:''}`:t(`${r.subjects} 个体 · ${r.reported}/${r.records} 份报告`,`${r.subjects} subjects · ${r.reported}/${r.records} reports`);
      const note=record?t('总分、分项与异常位置','Score, components and findings'):r.attention_categories?t(`${r.attention_categories} 类资料问题保留在汇总中`,`${r.attention_categories} metadata issue categories retained`):t('资料检查与逐份信号报告','Dataset checks and recording reports');
      return `<a class="demo-report" href="${esc(href(r.url))}"><span class="demo-report-copy"><strong>${esc(en()?r.label_en||r.label:r.label)}</strong><span>${esc(detail)}</span><small>${esc(note)}</small></span><span class="demo-report-end">${value?`<b>${value}</b><small>${t('试行评分','Trial score')}</small>`:''}<span>${t('查看报告','View report')}</span></span></a>`;
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
      return `<div class="data-library-item ${r.available?'':'unavailable'}"><span class="data-kind">${r.kind==='dataset'?t('数据集','Dataset'):esc(r.format||t('记录','Recording'))}</span><a class="data-library-label" href="${esc(href(target))}"><strong data-i18n-skip>${esc(r.label)}</strong><small>${r.kind==='dataset'?`${r.subjects??'—'} ${t('个体','subjects')} · ${r.records??'—'} ${t('记录','recordings')}`:esc(status[r.status]?.[en()?1:0]||r.status)}${r.available?'':` · ${t('来源不可用','Source unavailable')}`}</small></a><span class="data-library-actions"><a class="data-open" href="${esc(href(target))}">${action}</a>${r.latest_run_url?`<a class="data-secondary" href="${esc(href(r.url))}">${t('打开数据','Open data')}</a>`:''}</span></div>`;
    }).join('')||`<p class="small muted">${t('暂无匹配数据','No matching data')}</p>`;
    $('data-library-more').hidden=rows.length<=limit;$('data-library-more').textContent=t(`显示更多（${rows.length-limit}）`,`Show more (${rows.length-limit})`);
    $('data-search').placeholder=t('搜索数据名称','Search data');renderExamples();
  }
  async function refresh(){const request=++revision;try{const response=await fetch('/api/v1/data',{cache:'no-store'});if(!response.ok)throw Error('directory');const data=await response.json();if(request!==revision)return;items=data.items;examples=data.examples||[];render();$('data-library-error').hidden=true;}catch{if(request===revision){$('data-library-error').textContent=t('数据目录暂时不可用，请重试。','Data directory unavailable. Retry.');$('data-library-error').hidden=false;}}}
  $('data-search').addEventListener('input',()=>{limit=6;render()});
  for(const name of ['data','validation'])$('library-'+name).addEventListener('click',()=>{category=name;limit=6;render()});
  $('data-library-more').addEventListener('click',()=>{limit+=12;render()});
  $('data-library-refresh').addEventListener('click',refresh);
  window.addEventListener('qc:languagechange',render);window.addEventListener('focus',refresh);
  window.QCDataLibrary={refresh};refresh();
})();
