export const kinds = ['intake','base','conditional','dataset','report'] as const;
export const statuses = ['ready','trial','review','planned'] as const;
export const scopes = ['eeg','ecog','seeg','np','dataset'] as const;
export const scoreRoles = ['default','optional','measurement','unavailable'] as const;
export const SCORE_LABEL = {default:'默认计分',optional:'可选计分',measurement:'仅测量',unavailable:'未接入'};
export type Scoring = {scope:string;role:typeof scoreRoles[number];canOutputScore:boolean;outputs:string[];weight:string;rule:string;limited:string;version:string};
export type Proposal = {status:'draft'|'discussing'|'agreed';description:string;conditions:string;inputs:string;outputs:string;methods:string;scoring:string;decision:string};
export type DiscussionMessage = {id:string;author:string;body:string;createdAt:string};
export type Discussion = DiscussionMessage & {resolved:boolean;replies:DiscussionMessage[]};
export type Attachment={id:string;name:string;size:number;mime:string};
export type Sketch={title:string;body:string;hidden?:boolean;positioned?:boolean};
export type FlowNode = {
  id:string; title:string; summary:string; kind:typeof kinds[number]; status:typeof statuses[number];
  scope:string[]; x:number; y:number; description:string; inputs:string; outputs:string;
  conditions:string; methods:string; evidence:string; notes:string; children?:FlowNode[]; entryType?:'method'|'reader'|'check'|'support'|'visualization';scoring?:Scoring[];sourceManaged?:boolean;teamNotes?:string;proposal?:Proposal;discussion?:Discussion[];sketch?:Sketch;attachments?:Attachment[];
};
export type FlowEdge = {id:string;source:string;target:string;label:string};
export type FlowDoc = {schemaVersion:1;title:string;subtitle:string;nodes:FlowNode[];edges:FlowEdge[];drawing?:{edges:FlowEdge[]};catalog?:{id:string;sequence:number;sourceVersion:string;sourceCommit:string}};
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
  if(Object.keys(value).some(k=>!['schemaVersion','title','subtitle','nodes','edges','catalog','drawing'].includes(k)))throw new Error('流程图含未知字段');
  text(value.title,'标题',80,true);text(value.subtitle,'说明',200);
  if(!Array.isArray(value.nodes)||value.nodes.length<1||value.nodes.length>60)throw new Error('节点数应为 1–60');
  if(!Array.isArray(value.edges)||value.edges.length>150)throw new Error('连接数最多 150');
  if(value.catalog!==undefined){const c=value.catalog;if(!object(c)||Object.keys(c).sort().join(',')!=='id,sequence,sourceCommit,sourceVersion'||typeof c.id!=='string'||!/^catalog-[a-f0-9]{64}$/.test(c.id)||!Number.isSafeInteger(c.sequence)||Number(c.sequence)<1||typeof c.sourceCommit!=='string'||!/^([a-f0-9]{40}|local)$/.test(c.sourceCommit))throw new Error('目录来源无效');text(c.sourceVersion,'软件版本',80,true);}
  const ids=new Set<string>();
  let total=0;
  function checkNodes(nodes:unknown[],depth=0){if(depth>4)throw new Error('模块层级最多五层');for(const n of nodes){if(++total>250)throw new Error('模块和方法合计最多250项');
    if(!object(n)||Object.keys(n).some(k=>!NODE_KEYS.includes(k)&&!['children','entryType','scoring','sourceManaged','teamNotes','proposal','discussion','sketch','attachments'].includes(k))||NODE_KEYS.some(k=>!(k in n)))throw new Error('节点字段不完整');
    text(n.id,'节点编号',80,true);
    if(!/^[A-Za-z][A-Za-z0-9_-]*$/.test(n.id)||ids.has(n.id))throw new Error('节点编号重复或不合法');ids.add(n.id);
    text(n.title,'节点名称',64,true);text(n.summary,'节点简述',52);
    for(const k of ['description','inputs','outputs','conditions','methods','evidence','notes'])text(n[k],k,6000);
    if(!kinds.includes(n.kind as typeof kinds[number])||!statuses.includes(n.status as typeof statuses[number]))throw new Error('节点类型或状态无效');
    if(!Array.isArray(n.scope)||!n.scope.length||n.scope.some(x=>!scopes.includes(x))||new Set(n.scope).size!==n.scope.length)throw new Error('适用范围无效');
    for(const [key,max]of [['x',CANVAS_W-NODE_W-20],['y',CANVAS_H-NODE_H-20]] as const){if(typeof n[key]!=='number'||!Number.isFinite(n[key])||n[key]<20||n[key]>max)throw new Error('节点坐标超出画布');}
    if(n.entryType!==undefined&&!['method','reader','check','support','visualization'].includes(n.entryType as string))throw new Error('子项类型无效');
    if(n.scoring!==undefined){
      if(!Array.isArray(n.scoring)||n.scoring.length>5)throw new Error('计分属性格式错误');
      const seen=new Set();
      for(const s of n.scoring){
        if(!object(s)||Object.keys(s).sort().join(',')!==['scope','role','canOutputScore','outputs','weight','rule','limited','version'].sort().join(',')||!n.scope.includes(s.scope)||seen.has(s.scope)||!scoreRoles.includes(s.role as typeof scoreRoles[number])||typeof s.canOutputScore!=='boolean')throw new Error('计分属性无效或模态重复');
        seen.add(s.scope);
        if(!Array.isArray(s.outputs)||s.outputs.length>12)throw new Error('计分输出无效');
        for(const o of s.outputs)text(o,'计分输出',180,true);
        for(const k of ['weight','rule','limited','version'])text(s[k],k,1800);
        if((s.role==='default'||s.role==='optional')!==s.canOutputScore)throw new Error('计分角色与输出能力不一致');
        if(n.status==='planned'&&s.role!=='unavailable')throw new Error('未接入方法不能声明已接入计分');
      }
    }
    if(n.sketch!==undefined){const d=n.sketch;if(!object(d)||Object.keys(d).some(k=>!['title','body','hidden','positioned'].includes(k)))throw new Error('草稿格式不正确');text(d.title,'模块标题',64);text(d.body,'模块正文',20000);if(d.hidden!==undefined&&typeof d.hidden!=='boolean')throw new Error('隐藏标记无效');if(d.positioned!==undefined&&typeof d.positioned!=='boolean')throw new Error('位置标记无效');}
    if(n.attachments!==undefined){if(!Array.isArray(n.attachments)||n.attachments.length>10)throw new Error('每个模块最多10个附件');const seen=new Set();for(const f of n.attachments){if(!object(f)||Object.keys(f).sort().join(',')!=='id,mime,name,size'||typeof f.id!=='string'||!/^[a-f0-9-]{36}$/.test(f.id)||seen.has(f.id)||!Number.isSafeInteger(f.size)||Number(f.size)<1||Number(f.size)>10485760)throw new Error('附件信息无效');text(f.name,'附件名称',180,true);text(f.mime,'附件类型',120,true);seen.add(f.id);}}
    if(n.teamNotes!==undefined)text(n.teamNotes,'团队说明',20000);
    if(n.sourceManaged!==undefined&&typeof n.sourceManaged!=='boolean')throw new Error('来源标记无效');
    if(n.proposal!==undefined){
      const p=n.proposal, keys=['status','description','conditions','inputs','outputs','methods','scoring','decision'];
      if(!object(p)||Object.keys(p).sort().join(',')!==keys.sort().join(',')||!['draft','discussing','agreed'].includes(String(p.status)))throw new Error('方案草稿格式无效');
      for(const k of keys.filter(k=>k!=='status'))text(p[k],'方案草稿',6000);
    }
    if(n.discussion!==undefined){
      if(!Array.isArray(n.discussion)||n.discussion.length>100)throw new Error('每个模块最多100条讨论');
      const messageIds=new Set();
      const checkMessage=(m:unknown,thread=false)=>{
        if(!object(m)||Object.keys(m).sort().join(',')!==(thread?['id','author','body','createdAt','resolved','replies']:['id','author','body','createdAt']).sort().join(','))throw new Error('讨论格式无效');
        text(m.id,'批注编号',80,true);text(m.author,'署名',60,true);text(m.body,'批注内容',4000,true);text(m.createdAt,'记录时间',40,true);
        if(messageIds.has(m.id)||!Number.isFinite(Date.parse(m.createdAt as string)))throw new Error('批注编号或时间无效');messageIds.add(m.id);
      };
      for(const t of n.discussion){checkMessage(t,true);if(typeof t.resolved!=='boolean'||!Array.isArray(t.replies)||t.replies.length>100)throw new Error('讨论回复无效');for(const r of t.replies)checkMessage(r);}
    }
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
  if(value.drawing!==undefined){const d=value.drawing;if(!object(d)||Object.keys(d).join(',')!=='edges'||!Array.isArray(d.edges)||d.edges.length>250)throw new Error('草稿连接无效');const pairs=new Set(),edgeIds=new Set();for(const e of d.edges){if(!object(e)||Object.keys(e).sort().join(',')!=='id,label,source,target')throw new Error('草稿连线字段无效');text(e.id,'连接编号',60,true);text(e.source,'起点',80,true);text(e.target,'终点',80,true);text(e.label,'连线说明',80);const pair=e.source+'>'+e.target;if(!ids.has(e.source as string)||!ids.has(e.target as string)||e.source===e.target||pairs.has(pair)||edgeIds.has(e.id))throw new Error('连接起点和终点无效或重复');pairs.add(pair);edgeIds.add(e.id);}}
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
  return[add&&`新增 ${add} 个模块`,del&&`删除 ${del} 个模块`,edit&&`修改 ${edit} 个模块`,JSON.stringify(drawingEdges(a))!==JSON.stringify(drawingEdges(b))&&'调整连接'].filter(Boolean).join('；')||'更新流程说明';
}

export function flattenNodes(nodes:FlowNode[]):FlowNode[]{return nodes.flatMap(n=>[n,...flattenNodes(n.children||[])]);}
export function findParent(nodes:FlowNode[],id:string):FlowNode|undefined{for(const n of nodes){if(n.children?.some(c=>c.id===id))return n;const p=findParent(n.children||[],id);if(p)return p;}}
export function updateNode(nodes:FlowNode[],id:string,fields:Partial<FlowNode>):FlowNode[]{return nodes.map(n=>n.id===id?{...n,...fields}:n.children?{...n,children:updateNode(n.children,id,fields)}:n);}
export function removeNode(nodes:FlowNode[],id:string):FlowNode[]{return nodes.filter(n=>n.id!==id).map(n=>n.children?{...n,children:removeNode(n.children,id)}:n);}

export function nodeTitle(n:FlowNode){return n.sketch?.title||n.title;}
export function nodeBody(n:FlowNode){if(n.sketch)return n.sketch.body;if(n.proposal){const p=n.proposal;return [[p.description,''],[p.conditions,'适用条件'],[p.methods,'方法与参数'],[p.scoring,'计分建议'],[p.inputs,'输入'],[p.outputs,'输出'],[p.decision,'讨论结论']].filter(([v])=>v).map(([v,t])=>t?t+'：'+v:v).join('\n\n');}return n.description||n.summary;}
export function sketchFor(n:FlowNode){return n.sketch||{title:n.title,body:nodeBody(n)};}
export function drawingEdges(doc:FlowDoc){return doc.drawing?.edges||doc.edges;}
export function displayNodes(nodes:FlowNode[]):FlowNode[]{return nodes.filter(n=>!n.sketch?.hidden).map(n=>({...n,title:nodeTitle(n),summary:nodeBody(n).split('\n')[0].slice(0,52),children:n.children?displayNodes(n.children):undefined}));}
