import catalog from '../content/module-catalog.json';
import {type FlowDoc,type FlowNode,validateDoc} from './flow';
export const CATALOG_ID='review-v15';
export const CATALOG_LABEL='v1.5 · 数据集审核与复验';
export const CATALOG_NOTE='加入D04：影响与用途、处理意见、固定版本、复验变化及PDF · 2026-11-06.5';
export function withCatalog(doc:FlowDoc):FlowDoc{
 const groups=catalog.modules as unknown as Record<string,FlowNode[]>;
 // Existing node descriptions and member edits survive; only missing child IDs are added.
 function merge(old:FlowNode[],added:FlowNode[]):FlowNode[]{return [...old.map(n=>{const fresh=added.find(c=>c.id===n.id);return fresh?.children?{...n,children:merge(n.children||[],fresh.children)}:n;}),...added.filter(n=>!old.some(o=>o.id===n.id))];}
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
