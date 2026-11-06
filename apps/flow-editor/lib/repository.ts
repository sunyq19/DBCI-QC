import {withCatalog,CATALOG_ID,CATALOG_NOTE} from './catalog';
import { seed } from './seed';
import { validateDoc, type FlowDoc } from './flow';
export const SAVE_SQL = `INSERT INTO flow_revisions (revision, document, hash, author_id, note, created_at)
 SELECT ?,?,?,?,?,? WHERE (SELECT COALESCE(MAX(revision),0) FROM flow_revisions)=? RETURNING revision`;
export const FREEZE_SQL = `INSERT INTO flow_versions (id,label,revision,note,author_id,created_at)
 SELECT ?,?,?,?,?,? WHERE (SELECT MAX(revision) FROM flow_revisions)=? RETURNING id`;
export class AppError extends Error { constructor(message:string, public status=400){super(message);} }
export async function digest(doc:FlowDoc){const data=new TextEncoder().encode(JSON.stringify(doc));return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');}
type Revision={revision:number;document:string;hash:string;note:string;created_at:string};
type Version={id:string;label:string;revision:number;note:string;created_at:string};
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
  if(opts.history){return{latestRevision:latest!.revision,revisions:(await db.prepare('SELECT revision,hash,note,created_at FROM flow_revisions ORDER BY revision DESC LIMIT 100').all()).results};}
  let version:Version|null=null,rev=opts.revision||latest!.revision;
  if(opts.version){version=await db.prepare('SELECT id,label,revision,note,created_at FROM flow_versions WHERE id=?').bind(opts.version).first<Version>();if(!version)throw new AppError('固定版本不存在',404);rev=version.revision;}
  const r=await db.prepare('SELECT revision,document,hash,note,created_at FROM flow_revisions WHERE revision=?').bind(rev).first<Revision>();
  if(!r)throw new AppError('历史记录不存在',404);
  const versions=(await db.prepare('SELECT id,label,revision,note,created_at FROM flow_versions ORDER BY created_at DESC,id DESC').all<Version>()).results;
  return{doc:JSON.parse(r.document),revision:r.revision,hash:r.hash,note:r.note,createdAt:r.created_at,version,latestRevision:latest!.revision,versions,view:opts.version?'version':opts.revision?'history':'draft'};
}
export async function saveFlow(db:D1Database,base:number,doc:unknown,note:string,authorId:string){
  if(!Number.isSafeInteger(base)||base<1)throw new AppError('保存基准版本无效');
  if(typeof note!=='string'||note.trim().length<1||note.length>300)throw new AppError('请填写 1–300 字的修改说明');
  const valid=validateDoc(doc),hash=await digest(valid),revision=base+1,now=new Date().toISOString();
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
  const baseLabel='v1.1 · 模块层级';let label=baseLabel;let suffix=head.revision+1;while(await db.prepare('SELECT id FROM flow_versions WHERE label=?').bind(label).first())label=baseLabel+' · r'+suffix++;
  await db.batch([
   db.prepare(`INSERT INTO flow_revisions (revision,document,hash,author_id,note,created_at)
    SELECT ?,?,?,?,?,? WHERE (SELECT MAX(revision) FROM flow_revisions)=?
    AND NOT EXISTS (SELECT 1 FROM flow_versions WHERE id=?)`).bind(head.revision+1,JSON.stringify(doc),hash,'system',CATALOG_NOTE,now,head.revision,CATALOG_ID),
   db.prepare(`INSERT OR IGNORE INTO flow_versions (id,label,revision,note,author_id,created_at)
    SELECT ?,?,revision,?,?,? FROM flow_revisions WHERE revision=? AND hash=? AND note=?`).bind(CATALOG_ID,label,CATALOG_NOTE,'system',now,head.revision+1,hash,CATALOG_NOTE),
  ]);
 }
}
