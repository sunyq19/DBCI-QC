export const kinds = ['intake','base','conditional','dataset','report'] as const;
export const statuses = ['ready','trial','review','planned'] as const;
export const scopes = ['eeg','ecog','seeg','np','dataset'] as const;
export type FlowNode = {
  id:string; title:string; summary:string; kind:typeof kinds[number]; status:typeof statuses[number];
  scope:string[]; x:number; y:number; description:string; inputs:string; outputs:string;
  conditions:string; methods:string; evidence:string; notes:string; children?:FlowNode[]; entryType?:'method'|'reader'|'check'|'support'|'visualization';
};
export type FlowEdge = {id:string;source:string;target:string;label:string};
export type FlowDoc = {schemaVersion:1;title:string;subtitle:string;nodes:FlowNode[];edges:FlowEdge[]};
export const KIND_LABEL:Record<FlowNode['kind'],string>={intake:'共同步骤',base:'默认推荐',conditional:'按条件启用',dataset:'数据集检查',report:'汇总与报告'};
export const STATUS_LABEL:Record<FlowNode['status'],string>={ready:'已接入',trial:'试行',review:'待讨论',planned:'计划中'};
export const SCOPE_LABEL:Record<string,string>={eeg:'头皮 EEG',ecog:'ECoG',seeg:'sEEG',np:'Neuropixels 电压',dataset:'数据集'};
export const NODE_W=228,NODE_H=104,CANVAS_W=1500,CANVAS_H=1180;
const NODE_KEYS=['id','title','summary','kind','status','scope','x','y','description','inputs','outputs','conditions','methods','evidence','notes'];
function object(v:unknown):v is Record<string,unknown>{return typeof v==='object'&&v!==null&&!Array.isArray(v);}
function text(v:unknown,key:string,max:number,nonempty=false):asserts v is string {
  if(typeof v!=='string'||v.length>max||(nonempty&&!v.trim())||/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(v))throw new Error(`${key}格式或长度不正确`);
}
export function validateDoc(value:unknown):FlowDoc {
  if(!object(value)||value.schemaVersion!==1)throw new Error('不支持的流程图格式');
  if(Object.keys(value).some(k=>!['schemaVersion','title','subtitle','nodes','edges'].includes(k)))throw new Error('流程图含未知字段');
  text(value.title,'标题',80,true);text(value.subtitle,'说明',200);
  if(!Array.isArray(value.nodes)||value.nodes.length<1||value.nodes.length>60)throw new Error('节点数应为 1–60');
  if(!Array.isArray(value.edges)||value.edges.length>150)throw new Error('连接数最多 150');
  const ids=new Set<string>();
  let total=0;
  function checkNodes(nodes:unknown[],depth=0){if(depth>4)throw new Error('模块层级最多五层');for(const n of nodes){if(++total>250)throw new Error('模块和方法合计最多250项');
    if(!object(n)||Object.keys(n).some(k=>!NODE_KEYS.includes(k)&&!['children','entryType'].includes(k))||NODE_KEYS.some(k=>!(k in n)))throw new Error('节点字段不完整');
    text(n.id,'节点编号',80,true);
    if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(n.id)||ids.has(n.id))throw new Error('节点编号重复或不合法');ids.add(n.id);
    text(n.title,'节点名称',64,true);text(n.summary,'节点简述',52);
    for(const k of ['description','inputs','outputs','conditions','methods','evidence','notes'])text(n[k],k,6000);
    if(!kinds.includes(n.kind as typeof kinds[number])||!statuses.includes(n.status as typeof statuses[number]))throw new Error('节点类型或状态无效');
    if(!Array.isArray(n.scope)||!n.scope.length||n.scope.some(x=>!scopes.includes(x))||new Set(n.scope).size!==n.scope.length)throw new Error('适用范围无效');
    for(const [key,max]of [['x',CANVAS_W-NODE_W-20],['y',CANVAS_H-NODE_H-20]] as const){if(typeof n[key]!=='number'||!Number.isFinite(n[key])||n[key]<20||n[key]>max)throw new Error('节点坐标超出画布');}
    if(n.entryType!==undefined&&!['method','reader','check','support','visualization'].includes(n.entryType as string))throw new Error('子项类型无效');
    if(n.children!==undefined){if(!Array.isArray(n.children))throw new Error('子模块必须是数组');checkNodes(n.children,depth+1);}
  }}
  checkNodes(value.nodes);
  const topIds=new Set(value.nodes.map(n=>(n as FlowNode).id));
  const edgeIds=new Set<string>(),pairs=new Set<string>(),adj=new Map([...ids].map(id=>[id,[]as string[]]));
  for(const e of value.edges){
    if(!object(e)||Object.keys(e).some(k=>!['id','source','target','label'].includes(k)))throw new Error('连接字段无效');
    text(e.id,'连接编号',60,true);text(e.source,'起点',24,true);text(e.target,'终点',24,true);text(e.label,'连接说明',48);
    if(!topIds.has(e.source)||!topIds.has(e.target)||e.source===e.target||edgeIds.has(e.id))throw new Error('连接引用了不存在、重复或相同的节点');
    const pair=`${e.source}\0${e.target}`;if(pairs.has(pair))throw new Error('不能重复连接同一对节点');pairs.add(pair);edgeIds.add(e.id);adj.get(e.source)!.push(e.target);
  }
  const done=new Set<string>(),visiting=new Set<string>();
  function walk(id:string){if(visiting.has(id))throw new Error('流程不能形成循环依赖');if(done.has(id))return;visiting.add(id);for(const next of adj.get(id)!)walk(next);visiting.delete(id);done.add(id);}
  for(const id of ids)walk(id);
  return structuredClone(value)as FlowDoc;
}
export function isEditor(email:string|undefined|null,allowed:string|undefined){return !!email&&!!allowed&&allowed.split(/[\s,;]+/).map(s=>s.trim().toLowerCase()).filter(Boolean).includes(email.trim().toLowerCase());}
export function edgePath(a:FlowNode,b:FlowNode){
  if(Math.abs(a.y-b.y)<70){const right=b.x>a.x,sx=a.x+(right?NODE_W:0),tx=b.x+(right?0:NODE_W),y1=a.y+NODE_H/2,y2=b.y+NODE_H/2;return{d:`M${sx},${y1} C${(sx+tx)/2},${y1} ${(sx+tx)/2},${y2} ${tx},${y2}`,x:(sx+tx)/2,y:(y1+y2)/2-10};}
  const down=b.y>a.y,sx=a.x+NODE_W/2,sy=a.y+(down?NODE_H:0),tx=b.x+NODE_W/2,ty=b.y+(down?0:NODE_H);
  return{d:`M${sx},${sy} C${sx},${(sy+ty)/2} ${tx},${(sy+ty)/2} ${tx},${ty}`,x:(sx+tx)/2,y:(sy+ty)/2-8};
}
export function summarizeChanges(a:FlowDoc,b:FlowDoc){
  const old=new Map(a.nodes.map(n=>[n.id,n])),next=new Map(b.nodes.map(n=>[n.id,n]));
  const add=b.nodes.filter(n=>!old.has(n.id)).length,del=a.nodes.filter(n=>!next.has(n.id)).length,edit=b.nodes.filter(n=>old.has(n.id)&&JSON.stringify(old.get(n.id))!==JSON.stringify(n)).length;
  return[add&&`新增 ${add} 个模块`,del&&`删除 ${del} 个模块`,edit&&`修改 ${edit} 个模块`,JSON.stringify(a.edges)!==JSON.stringify(b.edges)&&'调整连接'].filter(Boolean).join('；')||'更新流程说明';
}

export function flattenNodes(nodes:FlowNode[]):FlowNode[]{return nodes.flatMap(n=>[n,...flattenNodes(n.children||[])]);}
export function findParent(nodes:FlowNode[],id:string):FlowNode|undefined{for(const n of nodes){if(n.children?.some(c=>c.id===id))return n;const p=findParent(n.children||[],id);if(p)return p;}}
export function updateNode(nodes:FlowNode[],id:string,fields:Partial<FlowNode>):FlowNode[]{return nodes.map(n=>n.id===id?{...n,...fields}:n.children?{...n,children:updateNode(n.children,id,fields)}:n);}
export function removeNode(nodes:FlowNode[],id:string):FlowNode[]{return nodes.filter(n=>n.id!==id).map(n=>n.children?{...n,children:removeNode(n.children,id)}:n);}
