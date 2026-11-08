import catalog from '../content/module-catalog.json';
import baseline from '../content/catalog-v15-baseline.json';
import {type FlowDoc,type FlowNode,validateDoc} from './flow';
export const CATALOG_ID='scoring-v16';
export const CATALOG_LABEL='v1.6 · 多模态计分与权重';
export const CATALOG_NOTE='同步dev39：子方法计分属性、四模态默认方案、有效权重及同类证据合并 · 2026-11-08';
export function withCatalog(doc:FlowDoc):FlowDoc{
 const groups=catalog.modules as unknown as Record<string,FlowNode[]>;
 // Three-way refresh: replace known old catalog values, preserve member changes and positions.
 const previous=baseline as Record<string,Record<string,unknown[]>>;
 function merge(old:FlowNode[],added:FlowNode[]):FlowNode[]{return [...old.map(n=>{
  const fresh=added.find(c=>c.id===n.id);if(!fresh)return n;
  const next={...n};
  for(const key of Object.keys(fresh) as (keyof FlowNode)[]){
   if(['id','x','y','children'].includes(key))continue;
   const oldValue=n[key];
   if(oldValue===undefined||previous[n.id]?.[key]?.some(v=>JSON.stringify(v)===JSON.stringify(oldValue)))
    Object.assign(next,{[key]:fresh[key]});
  }
  // Preserve explicit score edits; fill only newly added modality contracts.
  if(fresh.scoring)next.scoring=[...(n.scoring||[]).filter(s=>next.scope.includes(s.scope)),...fresh.scoring.filter(s=>next.scope.includes(s.scope)&&!n.scoring?.some(o=>o.scope===s.scope))];
  if(fresh.children)next.children=merge(n.children||[],fresh.children);
  return next;
 }),...added.filter(n=>!old.some(o=>o.id===n.id))];}
 const additions=(catalog as unknown as {roots?:FlowNode[]}).roots||[];
 const nodes=merge(doc.nodes,additions).map(n=>groups[n.id]?{...n,children:merge(n.children||[],groups[n.id])}:n);
 const edges=[...doc.edges];
 if(!doc.nodes.some(n=>n.id==='VIS')&&nodes.some(n=>n.id==='M09')){
  let id='edge-visualization';while(edges.some(e=>e.id===id))id+='x';
  edges.push({id,source:'M09',target:'VIS',label:'读取结果 · 可选展示'});
 }
 for(const [source,target,label] of [['D03','D04','资料问题'],['D04','OVERVIEW','处理与复验结果']]){
  if(nodes.some(n=>n.id===source)&&nodes.some(n=>n.id===target)&&!edges.some(e=>e.source===source&&e.target===target)){
   let id='edge-'+source+'-'+target;while(edges.some(e=>e.id===id))id+='x';edges.push({id,source,target,label});
  }
 }
 return validateDoc({...doc,nodes,edges});
}
