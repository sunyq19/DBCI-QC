import {AppError} from './repository';
import navigation from '../config/navigation.json';
export type Editor={id:string;label:string;role:'owner'|'editor'};
export const publicOrigin=new URL(navigation.flowUrl).origin;
export async function tokenHash(token:string){const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token));return Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');}
export function newToken(){return btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');}
export function allowedOrigin(request:Request){const origin=request.headers.get('origin');return origin===publicOrigin||origin===new URL(request.url).origin;}
export function json(request:Request,value:unknown,status=200){return withCors(request,Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}}));}
export function withCors(request:Request,response:Response){if(request.headers.get('origin')===publicOrigin){response.headers.set('Access-Control-Allow-Origin',publicOrigin);response.headers.set('Vary','Origin');}return response;}
export function preflight(request:Request){if(!allowedOrigin(request))return json(request,{error:'来源不受支持'},403);const r=withCors(request,new Response(null,{status:204}));r.headers.set('Access-Control-Allow-Methods','GET, POST, OPTIONS');r.headers.set('Access-Control-Allow-Headers','X-Flow-Editor, Content-Type');r.headers.set('Access-Control-Max-Age','600');return r;}
export async function editorFor(request:Request,db:D1Database,bootstrapHash?:string):Promise<Editor|null>{
 const auth=request.headers.get('x-flow-editor');if(!auth)return null;
 const token=/^([A-Za-z0-9_-]{43})$/.exec(auth)?.[1];if(!token)throw new AppError('编辑链接无效，请重新打开成员编辑链接',401);
 const hash=await tokenHash(token);
 // Only the seeded owner's secret can initialize this row. Revoked rows are never recreated.
 if(bootstrapHash&&hash===bootstrapHash)await db.prepare('INSERT OR IGNORE INTO flow_access_links (id,token_hash,label,role,created_at) VALUES (?,?,?,?,?)').bind('owner',hash,'项目维护者','owner',new Date().toISOString()).run();
 const row=await db.prepare('SELECT id,label,role FROM flow_access_links WHERE token_hash=? AND revoked_at IS NULL').bind(hash).first<Editor>();
 if(!row)throw new AppError('此编辑链接已失效。仍可查看内容，请向维护者获取新的链接。',401);
 return row;
}
export async function createLink(db:D1Database,label:unknown){
 if(typeof label!=='string'||!label.trim()||label.length>60||/[\u0000-\u001f]/.test(label))throw new AppError('请填写1–60字的成员称呼');
 const count=await db.prepare("SELECT COUNT(*) AS n FROM flow_access_links WHERE revoked_at IS NULL").first<{n:number}>();if((count?.n||0)>=100)throw new AppError('最多保留100个有效编辑链接，请先停用不再使用的链接');
 const token=newToken(),id=crypto.randomUUID(),at=new Date().toISOString();
 await db.prepare('INSERT INTO flow_access_links (id,token_hash,label,role,created_at) VALUES (?,?,?,?,?)').bind(id,await tokenHash(token),label.trim(),'editor',at).run();
 return{id,label:label.trim(),token,created_at:at};
}
export async function revokeLink(db:D1Database,id:unknown){if(typeof id!=='string'||id==='owner')throw new AppError('不能在这里停用维护者入口');await db.prepare('UPDATE flow_access_links SET revoked_at=? WHERE id=? AND revoked_at IS NULL').bind(new Date().toISOString(),id).run();return{ok:true};}
export function accessFailure(request:Request,e:unknown){return json(request,{error:e instanceof AppError?e.message:'暂时未能完成，请保留修改后重试'},e instanceof AppError?e.status:500);}
