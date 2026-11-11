import {withCatalog,CATALOG_ID,CATALOG_LABEL,CATALOG_NOTE} from './catalog';
import { seed } from './seed';
import { validateDoc, flattenNodes, updateNode, type FlowDoc } from './flow';
export const SAVE_SQL = `INSERT INTO flow_revisions (revision, document, hash, author_id, note, created_at, based_on_revision)
 SELECT ?,?,?,?,?,?,(SELECT MAX(revision) FROM flow_revisions) WHERE (SELECT COALESCE(MAX(revision),0) FROM flow_revisions)=? RETURNING revision`;
export const FREEZE_SQL = `INSERT INTO flow_versions (id,label,revision,note,author_id,created_at)
 SELECT ?,?,?,?,?,? WHERE (SELECT MAX(revision) FROM flow_revisions)=? RETURNING id`;
export class AppError extends Error { constructor(message:string, public status=400){super(message);} }
export async function digest(doc:FlowDoc){const data=new TextEncoder().encode(JSON.stringify(doc));return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');}
type Revision={revision:number;document:string;hash:string;note:string;created_at:string;based_on_revision:number|null};
type Version={id:string;label:string;revision:number;note:string;created_at:string;canDelete?:boolean};
const VERSION_FIELDS="id,label,revision,note,created_at,CASE WHEN author_id IN ('system','catalog-sync') THEN 0 ELSE 1 END AS canDelete";
export async function initialize(db:D1Database){
  if(await db.prepare('SELECT revision FROM flow_revisions LIMIT 1').first())return;
  const at='2026-11-06T00:00:00.000Z',hash=await digest(seed);
  await db.batch([
    db.prepare('INSERT OR IGNORE INTO flow_revisions (revision,document,hash,author_id,note,created_at) VALUES (1,?,?,?,?,?)').bind(JSON.stringify(seed),hash,'system','初始模块路由；评分待讨论',at),
    db.prepare('INSERT OR IGNORE INTO flow_versions (id,label,revision,note,author_id,created_at) VALUES (?,?,1,?,?,?)').bind('baseline-v1','v1.0','模块设计基线；固定版本不代表质量判据已审核','system',at),
  ]);
}
export async function readFlow(db:D1Database,opts:{version?:string|null;revision?:number|null;head?:boolean;history?:boolean}={}){
  await initialize(db);
  const latest=await db.prepare('SELECT MAX(revision) AS revision FROM flow_revisions').first<{revision:number}>();
  if(opts.head)return{latestRevision:latest!.revision};
  if(opts.history){return{latestRevision:latest!.revision,revisions:(await db.prepare('SELECT revision,hash,note,created_at,based_on_revision FROM flow_revisions ORDER BY revision DESC LIMIT 100').all()).results};}
  let version:Version|null=null,rev=opts.revision||latest!.revision;
  if(opts.version){version=await db.prepare(`SELECT ${VERSION_FIELDS} FROM flow_versions WHERE id=?`).bind(opts.version).first<Version>();if(!version)throw new AppError('版本不存在或已删除',404);version.canDelete=Boolean(version.canDelete);rev=version.revision;}
  const r=await db.prepare('SELECT revision,document,hash,note,created_at,based_on_revision FROM flow_revisions WHERE revision=?').bind(rev).first<Revision>();
  if(!r)throw new AppError('历史记录不存在',404);
  const versions=(await db.prepare(`SELECT ${VERSION_FIELDS} FROM flow_versions ORDER BY created_at DESC,id DESC`).all<Version>()).results.map(v=>({...v,canDelete:Boolean(v.canDelete)}));
  return{doc:JSON.parse(r.document),revision:r.revision,hash:r.hash,note:r.note,createdAt:r.created_at,basedOnRevision:r.based_on_revision,version,latestRevision:latest!.revision,versions,view:opts.version?'version':opts.revision?'history':'draft'};
}

// Delete the named bookmark, never the document revision or another snapshot.
export async function deleteVersion(db:D1Database,id:unknown,revision:unknown,authorId:string){
  if(typeof id!=='string'||!Number.isSafeInteger(revision)||Number(revision)<1)throw new AppError('删除目标无效');
  const version=await db.prepare('SELECT * FROM flow_versions WHERE id=?').bind(id).first<{id:string;label:string;revision:number;author_id:string}>();
  if(!version)throw new AppError('版本不存在或已删除',404);
  if(['system','catalog-sync'].includes(version.author_id))throw new AppError('系统基线版本不能删除',403);
  if(version.revision!==revision)throw new AppError('版本信息已变化，请重新打开后删除',409);
  const result=await db.batch([
    db.prepare(`INSERT INTO flow_version_deletions (id,label,revision,deleted_by,deleted_at)
      SELECT id,label,revision,?,? FROM flow_versions WHERE id=? AND revision=? AND author_id NOT IN ('system','catalog-sync')`)
      .bind(authorId,new Date().toISOString(),id,revision),
    db.prepare("DELETE FROM flow_versions WHERE id=? AND revision=? AND author_id NOT IN ('system','catalog-sync') RETURNING id").bind(id,revision),
  ]);
  if(!result[1].results?.length)throw new AppError('版本已经删除',404);
  return {deleted:true,id};
}
export async function saveFlow(db:D1Database,base:number,doc:unknown,note:string,authorId:string,allowDiscussion=false){
  if(!Number.isSafeInteger(base)||base<1)throw new AppError('保存基准版本无效');
  if(typeof note!=='string'||note.trim().length<1||note.length>300)throw new AppError('请填写 1–300 字的修改说明');
  const current=await db.prepare('SELECT document FROM flow_revisions ORDER BY revision DESC LIMIT 1').first<Revision>();
  if(current)checkSourceFields(JSON.parse(current.document),validateDoc(doc));
  const valid=validateDoc(doc);
  if(!allowDiscussion&&current)checkDiscussionFields(JSON.parse(current.document),valid);
  if(new TextEncoder().encode(JSON.stringify(valid)).length>1800000)throw new AppError('协作内容已达容量限制，请导出备份后联系维护者',413);
  await checkAttachments(db,valid);
  const hash=await digest(valid),revision=base+1,now=new Date().toISOString();
  const saved=await db.prepare(SAVE_SQL).bind(revision,JSON.stringify(valid),hash,authorId,note.trim(),now,base).first();
  if(!saved)throw new AppError('其他成员已保存新修改。您的修改仍保留，请先查看新版，再合并或导出。',409);
  return{revision,hash,createdAt:now};
}
export async function freezeFlow(db:D1Database,revision:number,label:string,note:string,authorId:string){
  if(!Number.isSafeInteger(revision)||revision<1)throw new AppError('版本无效');
  if(typeof label!=='string'||!label.trim()||label.length>40||/[\u0000-\u001f]/.test(label))throw new AppError('版本名称应为 1–40 字');
  if(typeof note!=='string'||note.length>300)throw new AppError('版本说明最多 300 字');
  if(await db.prepare('SELECT id FROM flow_versions WHERE label=?').bind(label.trim()).first())throw new AppError('此版本名称已使用，请换一个名称',409);
  const id=crypto.randomUUID(),now=new Date().toISOString();
  try{
    const saved=await db.prepare(FREEZE_SQL).bind(id,label.trim(),revision,note.trim(),authorId,now,revision).first();
    if(!saved)throw new AppError('草稿已经更新，请加载最新草稿后再固定版本',409);
  }catch(e){if(e instanceof AppError)throw e;if(String(e).includes('UNIQUE'))throw new AppError('此版本名称已使用',409);throw e;}
  return{id,label:label.trim(),revision,note:note.trim(),created_at:now};
}

// Append one content revision on upgrade. Fixed snapshots and concurrent member saves are preserved.
export async function ensureHierarchy(db:D1Database){
 await initialize(db);
 for(let attempt=0;attempt<3;attempt++){
  if(await db.prepare('SELECT id FROM flow_versions WHERE id=?').bind(CATALOG_ID).first())return;
  const head=await db.prepare('SELECT revision,document FROM flow_revisions ORDER BY revision DESC LIMIT 1').first<Revision>();
  if(!head)return;
  const doc=withCatalog(JSON.parse(head.document)),hash=await digest(doc),now=new Date().toISOString();
  const baseLabel=CATALOG_LABEL;let label=baseLabel;let suffix=head.revision+1;while(await db.prepare('SELECT id FROM flow_versions WHERE label=?').bind(label).first())label=baseLabel+' · r'+suffix++;
  await db.batch([
   db.prepare(`INSERT INTO flow_revisions (revision,document,hash,author_id,note,created_at)
    SELECT ?,?,?,?,?,? WHERE (SELECT MAX(revision) FROM flow_revisions)=?
    AND NOT EXISTS (SELECT 1 FROM flow_versions WHERE id=?)`).bind(head.revision+1,JSON.stringify(doc),hash,'system',CATALOG_NOTE,now,head.revision,CATALOG_ID),
   db.prepare(`INSERT OR IGNORE INTO flow_versions (id,label,revision,note,author_id,created_at)
    SELECT ?,?,revision,?,?,? FROM flow_revisions WHERE revision=? AND hash=? AND note=?`).bind(CATALOG_ID,label,CATALOG_NOTE,'system',now,head.revision+1,hash,CATALOG_NOTE),
  ]);
 }
}

export async function syncCatalog(db:D1Database,manifest:import('./sync').CatalogManifest){
 const {mergeCatalog}=await import('./sync');await initialize(db);
 for(let attempt=0;attempt<4;attempt++){
  const head=await db.prepare('SELECT revision,document FROM flow_revisions ORDER BY revision DESC LIMIT 1').first<Revision>();
  if(!head)return;
  const old=JSON.parse(head.document) as FlowDoc;
  if(old.catalog?.id===manifest.id&&old.catalog.sequence===manifest.sequence||old.catalog&&old.catalog.sequence>manifest.sequence)return;
  const doc=mergeCatalog(old,manifest),hash=await digest(doc),now=new Date().toISOString();
  const note='自动同步质控目录 · '+manifest.sourceVersion+' · 发布 '+manifest.sequence+'；团队说明保留';
  const saved=await db.prepare(SAVE_SQL).bind(head.revision+1,JSON.stringify(doc),hash,'catalog-sync',note,now,head.revision).first();
  if(saved)return;
 }
 throw new AppError('目录正在更新，请稍后重试',409);
}
export function checkSourceFields(current:FlowDoc,incoming:FlowDoc){
 if(!current.catalog)return;
 if(JSON.stringify(incoming.catalog)!==JSON.stringify(current.catalog))throw new AppError('目录已经更新，请加载新版后编辑团队说明',409);
 const index=new Map(flattenNodes(incoming.nodes).map(n=>[n.id,n]));
 for(const n of flattenNodes(current.nodes).filter(n=>n.sourceManaged)){
  const next=index.get(n.id);if(!next)throw new AppError('已接入模块由质控台维护；请在团队说明中提出调整建议');
  for(const k of Object.keys(n).filter(k=>!['children','x','y','teamNotes','proposal','discussion','sketch','attachments'].includes(k))){
   if(JSON.stringify(n[k as keyof typeof n])!==JSON.stringify(next[k as keyof typeof next]))throw new AppError('模块和评分规则由质控台同步，不能在网页中另改一套；请填写团队说明');
  }
 }
}

// Comments are stamped and appended by the server; saved snapshots contain the full discussion.
export async function discussFlow(db:D1Database,body:{baseRevision:number;nodeId:string;operation:string;body?:string;threadId?:string},actor:{id:string;label:string}){
  const current=await readFlow(db) as {doc:FlowDoc;revision:number};
  if(body.baseRevision!==current.revision)throw new AppError('草稿已有更新。请先加载新版，输入的批注会保留。',409);
  const node=flattenNodes(current.doc.nodes).find(n=>n.id===body.nodeId);if(!node)throw new AppError('模块不存在',404);
  const list=structuredClone(node.discussion||[]),now=new Date().toISOString();
  const message=()=>{if(typeof body.body!=='string'||!body.body.trim()||body.body.length>4000)throw new AppError('批注应为1–4000字');return{id:crypto.randomUUID(),author:actor.label,body:body.body.trim(),createdAt:now};};
  if(body.operation==='comment')list.push({...message(),resolved:false,replies:[]});
  else {const thread=list.find(t=>t.id===body.threadId);if(!thread)throw new AppError('讨论不存在',404);
    if(body.operation==='reply')thread.replies.push(message());
    else if(body.operation==='resolve')thread.resolved=true;
    else if(body.operation==='reopen')thread.resolved=false;
    else throw new AppError('不支持的讨论操作');
  }
  const doc={...current.doc,nodes:updateNode(current.doc.nodes,node.id,{discussion:list})};
  return saveFlow(db,current.revision,doc,actor.label+' · '+node.title+' · '+({comment:'添加批注',reply:'回复讨论',resolve:'标记已处理',reopen:'重新讨论'}[body.operation]||'讨论'),actor.id,true);
}

function checkDiscussionFields(beforeDoc:FlowDoc,afterDoc:FlowDoc){
 const before=new Map(flattenNodes(beforeDoc.nodes).map(n=>[n.id,n.discussion]));
 const after=new Map(flattenNodes(afterDoc.nodes).map(n=>[n.id,n.discussion]));
 for(const id of new Set([...before.keys(),...after.keys()]))if(JSON.stringify(before.get(id))!==JSON.stringify(after.get(id)))throw new AppError('批注通过讨论区发布，不能通过导入或草稿改写');
}
// Copy an immutable snapshot into a new head, while retaining its parent and current implementation.
export async function forkFlow(db:D1Database,sourceRevision:number,expectedHead:number,doc:unknown,note:string,authorId:string,manifest:import('./sync').CatalogManifest){
 if(!Number.isSafeInteger(sourceRevision)||sourceRevision<1||!Number.isSafeInteger(expectedHead)||expectedHead<1)throw new AppError('来源或保存基准版本无效');
 if(typeof note!=='string'||!note.trim()||note.length>300)throw new AppError('请填写 1–300 字的修改说明');
 const source=await db.prepare('SELECT document FROM flow_revisions WHERE revision=?').bind(sourceRevision).first<Revision>();
 if(!source)throw new AppError('来源版本不存在',404);
 const original=JSON.parse(source.document),incoming=validateDoc(doc);
 checkSourceFields(original,incoming);checkDiscussionFields(original,incoming);
 const {mergeCatalog}=await import('./sync');const valid=validateDoc(mergeCatalog(incoming,manifest));
 const document=JSON.stringify(valid);if(new TextEncoder().encode(document).length>1800000)throw new AppError('协作内容已达容量限制，请导出备份后联系维护者',413);
 await checkAttachments(db,valid);
 const revision=expectedHead+1,hash=await digest(valid),createdAt=new Date().toISOString();
 const saved=await db.prepare(`INSERT INTO flow_revisions (revision,document,hash,author_id,note,created_at,based_on_revision)
 SELECT ?,?,?,?,?,?,? WHERE (SELECT MAX(revision) FROM flow_revisions)=? RETURNING revision`).bind(revision,document,hash,authorId,note.trim(),createdAt,sourceRevision,expectedHead).first();
 if(!saved)throw new AppError('其他成员已保存新修改。当前起草内容仍保留，请先查看新版再合并。',409);
 return{revision,hash,createdAt,doc:valid,basedOnRevision:sourceRevision};
}

async function checkAttachments(db:D1Database,doc:FlowDoc){
 const files=new Map(flattenNodes(doc.nodes).flatMap(n=>(n.attachments||[]).map(f=>[f.id,f] as const)));
 for(const f of files.values()){const row=await db.prepare('SELECT name,size,mime FROM flow_attachments WHERE id=?').bind(f.id).first<{name:string;size:number;mime:string}>();if(!row||row.name!==f.name||row.size!==f.size||row.mime!==f.mime)throw new AppError('附件不存在或信息已改变，请重新添加');}
}
