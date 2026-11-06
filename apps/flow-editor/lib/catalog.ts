import catalog from '../content/module-catalog.json';
import {type FlowDoc,type FlowNode,validateDoc} from './flow';
export const CATALOG_ID='visualization-v13';
export const CATALOG_LABEL='v1.3 · 统一可视化层';
export const CATALOG_NOTE='加入独立可视化层，按用途选择图表并标注来源 · 2026-11-06.3';
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
 return validateDoc({...doc,nodes,edges});
}
