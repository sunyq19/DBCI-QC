import legacy from '../content/catalog-legacy-values.json';
import {validateDoc,flattenNodes,type FlowDoc,type FlowNode} from './flow';
export type CatalogManifest={schemaVersion:1;id:string;sequence:number;sourceVersion:string;sourceCommit:string;doc:FlowDoc};
export function canonical(value:unknown):string{
 if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
 if(value&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonical((value as Record<string,unknown>)[k])).join(',')+'}';
 return JSON.stringify(value);
}
export async function catalogHash(doc:FlowDoc,sourceVersion:string){
 const bytes=new TextEncoder().encode(canonical({doc,sourceVersion}));
 return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
}
export async function validateManifest(value:unknown):Promise<CatalogManifest>{
 const v=value as CatalogManifest;
 if(!v||v.schemaVersion!==1||!Number.isSafeInteger(v.sequence)||v.sequence<1||typeof v.sourceVersion!=='string'||v.sourceVersion.length>80||!v.sourceVersion||typeof v.sourceCommit!=='string'||!/^([a-f0-9]{40}|local)$/.test(v.sourceCommit))throw new Error('目录格式无效');
 const doc=validateDoc(v.doc);
 if(doc.drawing||doc.catalog||flattenNodes(doc.nodes).some(n=>n.teamNotes!==undefined||n.sourceManaged!==undefined||n.proposal!==undefined||n.discussion!==undefined||n.sketch!==undefined||n.attachments!==undefined))throw new Error('目录不能携带协作内容');
 if(v.id!=='catalog-'+await catalogHash(doc,v.sourceVersion))throw new Error('目录校验失败');
 return {...v,doc};
}
const legacyValues=legacy as Record<string,Record<string,unknown[]>>;
const labels:Record<string,string>={title:'名称',description:'说明',conditions:'启用条件',notes:'原团队备注',scoring:'原评分建议',summary:'简述'};
// Source facts are replaced by ID. Team notes, member-created nodes and positioning survive.
export function mergeCatalog(doc:FlowDoc,manifest:CatalogManifest):FlowDoc{
 if(doc.catalog&&doc.catalog.sequence>manifest.sequence)return doc;
 if(doc.catalog?.sequence===manifest.sequence&&doc.catalog.id!==manifest.id)throw new Error('相同发布序号的目录内容不一致');
 const before=new Map(flattenNodes(doc.nodes).map(n=>[n.id,n]));
 const sourceIds=new Set(flattenNodes(manifest.doc.nodes).map(n=>n.id));
 function retire(n:FlowNode):FlowNode{
  if(!n.sourceManaged)return {...n,children:n.children?.filter(c=>!sourceIds.has(c.id)).map(retire)};
  return {...n,status:'planned',summary:'已从当前目录移除 · 保留团队记录',scoring:n.scoring?.map(s=>({...s,role:'unavailable',canOutputScore:false,weight:'不计入',rule:'当前发布版已移除此项，历史说明保留。'})),children:n.children?.filter(c=>!sourceIds.has(c.id)).map(retire)};
 }
 function merge(fresh:FlowNode):FlowNode{
  const old=before.get(fresh.id);let teamNotes=old?.teamNotes||'';
  // Preserve legacy direct edits as clearly separated notes, never as executable rules.
  if(old&&!old.sourceManaged){
   const edits=Object.keys(fresh).filter(k=>!['id','x','y','children','sourceManaged','teamNotes','proposal','discussion','sketch','attachments'].includes(k)&&old[k as keyof FlowNode]!==undefined&&canonical(old[k as keyof FlowNode])!==canonical(fresh[k as keyof FlowNode])&&!legacyValues[old.id]?.[k]?.some(v=>canonical(v)===canonical(old[k as keyof FlowNode])));
   if(edits.length)teamNotes+=(teamNotes?'\n\n':'')+'迁移保留的团队修改：\n'+edits.map(k=>(labels[k]||k)+'：'+(typeof old[k as keyof FlowNode]==='string'?old[k as keyof FlowNode]:JSON.stringify(old[k as keyof FlowNode]))).join('\n');
  }
  const children=[...(fresh.children||[]).map(merge),...(old?.children||[]).filter(c=>!sourceIds.has(c.id)).map(retire)];
  return {...fresh,x:old?.x??fresh.x,y:old?.y??fresh.y,sourceManaged:true,teamNotes,...(old?.sketch?{sketch:old.sketch}:{}),...(old?.attachments?{attachments:old.attachments}:{}),...(old?.proposal?{proposal:old.proposal}:{}),...(old?.discussion?{discussion:old.discussion}:{}),...(children.length?{children}:{})};
 }
 const nodes=[...manifest.doc.nodes.map(merge),...doc.nodes.filter(n=>!sourceIds.has(n.id)).map(retire)];
 const topIds=new Set(nodes.map(n=>n.id));
 const edges=[...manifest.doc.edges];
 for(const edge of doc.edges)if(topIds.has(edge.source)&&topIds.has(edge.target)&&!edges.some(e=>e.id===edge.id||e.source===edge.source&&e.target===edge.target))edges.push(edge);
 // An existing member connection may conflict with new upstream routing; keep it in old revisions.
 let result={...doc,nodes,edges,catalog:{id:manifest.id,sequence:manifest.sequence,sourceVersion:manifest.sourceVersion,sourceCommit:manifest.sourceCommit}};
 try{return validateDoc(result);}catch{result={...result,edges:manifest.doc.edges};return validateDoc(result);}
}
