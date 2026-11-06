import catalog from '../content/module-catalog.json';
import {type FlowDoc,type FlowNode,validateDoc} from './flow';
export const CATALOG_ID='gnosis-v12';
export const CATALOG_LABEL='v1.2 · 灵犀云可选方法';
export const CATALOG_NOTE='加入灵犀云8项原版可选方法、内部依赖与来源 · 2026-11-06.2';
export function withCatalog(doc:FlowDoc):FlowDoc{
 const groups=catalog.modules as unknown as Record<string,FlowNode[]>;
 // Existing node descriptions and member edits survive; only missing child IDs are added.
 function merge(old:FlowNode[],added:FlowNode[]):FlowNode[]{return [...old.map(n=>{const fresh=added.find(c=>c.id===n.id);return fresh?.children?{...n,children:merge(n.children||[],fresh.children)}:n;}),...added.filter(n=>!old.some(o=>o.id===n.id))];}
 return validateDoc({...doc,nodes:doc.nodes.map(n=>groups[n.id]?{...n,children:merge(n.children||[],groups[n.id])}:n)});
}
