'use client';
import {ScoringBadges,scoringSummary} from './scoring';
import {Plus,Minus,ArrowDown,Search,X} from 'lucide-react';
import {type FlowDoc,type FlowNode,flattenNodes,SCOPE_LABEL} from '../lib/flow';
export function visibleBranch(node:FlowNode,filter:string,query:string):boolean{
 const applicable=filter==='all'||node.scope.includes(filter);
 const match=[node.title,node.id,node.summary].join(' ').toLowerCase().includes(query.trim().toLowerCase());
 return (applicable&&match)||(node.children||[]).some(n=>visibleBranch(n,filter,query));
}
export default function Hierarchy({doc,selected,select,expanded,toggle,setExpanded,filter,query,setQuery}:{doc:FlowDoc;selected:string;select:(id:string)=>void;expanded:Set<string>;toggle:(id:string)=>void;setExpanded:(ids:Set<string>)=>void;filter:string;query:string;setQuery:(s:string)=>void}){
 const all=flattenNodes(doc.nodes),methods=all.filter(n=>n.entryType==='method'),available=methods.filter(n=>n.status!=='planned');
 function branch(n:FlowNode,depth=0,localQuery=query){
  if(!visibleBranch(n,filter,localQuery))return null;
  const ownMatch=[n.title,n.id,n.summary].join(' ').toLowerCase().includes(localQuery.trim().toLowerCase());
  const childQuery=ownMatch?'':localQuery;
  const children=(n.children||[]).filter(c=>visibleBranch(c,filter,childQuery));
  const open=expanded.has(n.id)||!!query.trim();
  const planned=children.filter(c=>c.status==='planned'),ready=children.filter(c=>c.status!=='planned');
  return <div key={n.id} className={`branch depth-${Math.min(depth,2)} ${n.id===selected?'selected':''} ${n.status==='planned'?'planned':''} ${n.status==='review'?'review':''}`} data-node={n.id}>
   <div className="branch-line">
    <button className="branch-label" onClick={()=>select(n.id)} aria-label={`查看 ${n.title}`}><span className="branch-code">{depth===0?n.id:n.entryType==='reader'?'读取器':n.entryType==='check'?'检查项':n.entryType==='support'?'执行支持':n.entryType==='visualization'?'图表':'方法'}{n.status==='review'&&<em>待讨论</em>}</span><strong>{n.title}</strong>{(n.proposal||n.discussion?.some(t=>!t.resolved))&&<span className="collab-marker">{n.proposal?'有方案草稿':''}{n.discussion?.some(t=>!t.resolved)?' · '+n.discussion.filter(t=>!t.resolved).length+'条讨论':''}</span>}{depth>0&&!n.children?.length&&<ScoringBadges node={n} filter={filter}/ >}{depth===0&&<small>{n.summary}</small>}{depth>0&&<small>{n.status==='planned'?'尚未接入':scoringSummary(n,filter)}{n.scope.length<4&&n.scope[0]!=='dataset'&&<span className="method-scope"> · {n.scope.map(s=>SCOPE_LABEL[s]?.replace(' 电压','')).join(' / ')}</span>}</small>}</button>
    {!!children.length&&<button className="branch-toggle" aria-label={`${open?'收起':'展开'} ${n.title}`} aria-expanded={open} onClick={()=>toggle(n.id)}><span>{children.length}</span>{open?<Minus size={15}/>:<Plus size={15}/>}</button>}
    {!children.length&&depth===0&&<span className="leaf-label">查看说明</span>}
   </div>
   {open&&!!children.length&&<div className="branch-children">{ready.map(c=>branch(c,depth+1,childQuery))}{planned.length>0&&<details className="planned-group" open={query.trim()?true:undefined}><summary>待接入 · {planned.length}</summary>{planned.map(c=>branch(c,depth+1,childQuery))}</details>}</div>}
  </div>;
 }
 const roots=(ids:string[])=>ids.map(id=>doc.nodes.find(n=>n.id===id)).filter((n):n is FlowNode=>!!n&&visibleBranch(n,filter,query));
 const known=['INPUT','M01','M02','M03','M04','M05','M06','M07','M08','M09','D01','D02','D03','D04','OVERVIEW','VIS'];
 const start=roots(['INPUT','M01','M02']),signal=roots(['M03','M04','M05','M06','M07']),dataset=roots(['D01','D02','D03','D04']),end=roots(['M08','M09','OVERVIEW']);
 const visuals=roots(['VIS']);
 const extra=doc.nodes.filter(n=>!known.includes(n.id)&&visibleBranch(n,filter,query));
 const total=doc.nodes.filter(n=>/^M\d|^D\d|^VIS$/.test(n.id)).length;
 return <div className="hierarchy-view">
  <div className="hierarchy-controls"><div className="search-box"><Search size={16}/><input aria-label="查找模块或方法" placeholder="查找模块或方法" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button className="icon" aria-label="清除搜索" onClick={()=>setQuery('')}><X size={14}/></button>}</div><div className="expand-actions"><button onClick={()=>setExpanded(new Set(all.filter(n=>n.children?.length).map(n=>n.id)))}>展开全部</button><button onClick={()=>{setQuery('');setExpanded(new Set());}}>收起全部</button></div></div>
  <div className="catalog-summary"><strong>{total} 个功能模块</strong><span>{available.length} 项已接入方法</span><span>{all.filter(n=>n.entryType==='reader').length} 个读取器</span><span>{all.filter(n=>n.entryType==='visualization'&&n.status!=='planned').length} 种图表</span><span>{all.filter(n=>n.entryType==='check').length} 项资料检查</span></div>
  <div className="scoring-legend"><span className="score-badge default">默认计分</span><span className="score-badge optional">可选计分</span><span className="score-badge measurement">仅测量</span><span className="score-badge unavailable">未接入</span><button onClick={()=>select('M08')}>方案与权重</button></div>
  <div className="hierarchy-scroll">
   {start.length>0&&<section className="flow-stage"><header><b>01</b><h2>读取与确认</h2><span>统一入口</span></header><div className="stage-modules">{start.map(n=>branch(n))}</div></section>}
   {(signal.length>0||dataset.length>0)&&<><div className="stage-arrow"><ArrowDown size={18}/></div><section className="flow-stage"><header><b>02</b><h2>按对象开展检查</h2><span>两条路线，可配合使用</span></header><div className={`branch-lanes ${!dataset.length||!signal.length?'single':''}`}>
    {signal.length>0&&<div className="flow-lane"><h3><span className="lane-dot"/>单份记录<small>模态决定内部方法</small></h3>{signal.map(n=>branch(n))}</div>}
    {dataset.length>0&&<div className="flow-lane dataset-lane"><h3><span className="lane-dot"/>数据集<small>有清单、映射与比较组</small></h3>{dataset.map(n=>branch(n))}</div>}
   </div></section></>}
   {end.length>0&&<><div className="stage-arrow"><ArrowDown size={18}/></div><section className="flow-stage"><header><b>03</b><h2>汇总与报告</h2><span>定位问题与待复核项</span></header><div className="stage-modules">{end.map(n=>branch(n))}</div></section></>}
   {visuals.length>0&&<section className="flow-stage"><header><b>04</b><h2>可视化</h2><span>读取已有结果 · 按需要选图</span></header>{visuals.map(n=>branch(n))}</section>}
   {extra.length>0&&<section className="flow-stage extra-stage"><header><b>+</b><h2>新增模块</h2></header>{extra.map(n=>branch(n))}</section>}
   {!start.length&&!signal.length&&!dataset.length&&!end.length&&!visuals.length&&!extra.length&&<div className="no-match">没有找到匹配的模块或方法。</div>}
   <p className="hierarchy-note">展开层级找到方法，点击名称编辑方案、参与讨论。</p>
  </div>
 </div>;
}
