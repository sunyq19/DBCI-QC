import {AppError} from './repository';
import navigation from '../config/navigation.json';
export type Editor={id:string;label:string;role:'editor'};
export const publicOrigin=new URL(navigation.flowUrl).origin;
export const SESSION_MS=8*60*60*1000;
const hex=(bytes:ArrayBuffer)=>Array.from(new Uint8Array(bytes),v=>v.toString(16).padStart(2,'0')).join('');
export async function tokenHash(token:string){return hex(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(token)));}
export function newToken(){return btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(32)))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');}
export async function makePasswordVerifier(password:string){const salt=crypto.getRandomValues(new Uint8Array(16));const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits']);const value=await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations:100000,hash:'SHA-256'},key,256);return 'pbkdf2:100000:'+hex(salt.buffer)+':'+hex(value);}
async function passwordMatches(password:string,verifier:string){const parts=/^pbkdf2:100000:([a-f0-9]{32}):([a-f0-9]{64})$/.exec(verifier);if(!parts)throw new AppError('编辑密码暂未配置',503);const salt=Uint8Array.from(parts[1].match(/../g)!,h=>parseInt(h,16));const key=await crypto.subtle.importKey('raw',new TextEncoder().encode(password),'PBKDF2',false,['deriveBits']);const actual=hex(await crypto.subtle.deriveBits({name:'PBKDF2',salt,iterations:100000,hash:'SHA-256'},key,256));let difference=0;for(let i=0;i<actual.length;i++)difference|=actual.charCodeAt(i)^parts[2].charCodeAt(i);return difference===0;}
export function allowedOrigin(request:Request){const origin=request.headers.get('origin');return origin===publicOrigin||origin===new URL(request.url).origin;}
export function json(request:Request,value:unknown,status=200){return withCors(request,Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}}));}
export function withCors(request:Request,response:Response){if(request.headers.get('origin')===publicOrigin){response.headers.set('Access-Control-Allow-Origin',publicOrigin);response.headers.set('Vary','Origin');}return response;}
export function preflight(request:Request){if(!allowedOrigin(request))return json(request,{error:'来源不受支持'},403);const r=withCors(request,new Response(null,{status:204}));r.headers.set('Access-Control-Allow-Methods','GET, POST, OPTIONS');r.headers.set('Access-Control-Allow-Headers','X-Flow-Editor, Content-Type');r.headers.set('Access-Control-Max-Age','600');return r;}
export async function editorFor(request:Request,db:D1Database,verifier?:string,now=Date.now()):Promise<Editor|null>{
 const token=request.headers.get('x-flow-editor');if(!token)return null;
 if(!/^[A-Za-z0-9_-]{43}$/.test(token)||!verifier)throw new AppError('编辑已结束，请重新输入密码',401);
 const hash=await tokenHash(token);
 const row=await db.prepare('SELECT label FROM flow_edit_sessions WHERE token_hash=? AND expires_at>? AND password_version=?').bind(hash,now,await tokenHash(verifier)).first<{label:string}>();
 if(!row)throw new AppError('编辑已结束，请重新输入密码',401);
 return{id:'session:'+hash.slice(0,20),label:row.label,role:'editor'};
}
export async function unlockEditing(request:Request,db:D1Database,verifier:string|undefined,password:unknown,label:unknown,now=Date.now()){
 if(!verifier)throw new AppError('编辑密码暂未配置',503);
 if(typeof password!=='string'||!password||password.length>256)throw new AppError('请输入编辑密码');
 if(label!==undefined&&(typeof label!=='string'||label.length>40||/[\u0000-\u001f]/.test(label)))throw new AppError('署名最多40字');
 const key=await tokenHash('flow-edit:'+ (request.headers.get('cf-connecting-ip')||'unknown'));
 const window=Math.floor(now/900000);
 const attempt=await db.prepare(`INSERT INTO flow_unlock_attempts (client_hash,window_id,attempts) VALUES (?,?,1)
 ON CONFLICT(client_hash) DO UPDATE SET window_id=excluded.window_id,attempts=CASE WHEN window_id=excluded.window_id THEN attempts+1 ELSE 1 END RETURNING attempts`).bind(key,window).first<{attempts:number}>();
 if((attempt?.attempts||0)>12)throw new AppError('尝试次数过多，请15分钟后再试',429);
 if(!await passwordMatches(password,verifier))throw new AppError('密码不正确',401);
 const token=newToken(),name=typeof label==='string'&&label.trim()?label.trim():'协作成员';
 await db.batch([
  db.prepare('INSERT INTO flow_edit_sessions (token_hash,label,expires_at,password_version) VALUES (?,?,?,?)').bind(await tokenHash(token),name,now+SESSION_MS,await tokenHash(verifier)),
  db.prepare('UPDATE flow_unlock_attempts SET attempts=0 WHERE client_hash=?').bind(key),
  db.prepare('DELETE FROM flow_edit_sessions WHERE expires_at<=?').bind(now),
  db.prepare('DELETE FROM flow_unlock_attempts WHERE window_id<?').bind(window-4),
 ]);
 return{token,label:name,canEdit:true,expiresAt:now+SESSION_MS};
}
export async function lockEditing(request:Request,db:D1Database){const token=request.headers.get('x-flow-editor');if(token)await db.prepare('DELETE FROM flow_edit_sessions WHERE token_hash=?').bind(await tokenHash(token)).run();return{ok:true};}
export function accessFailure(request:Request,e:unknown){return json(request,{error:e instanceof AppError?e.message:'暂时未能完成，请保留修改后重试'},e instanceof AppError?e.status:500);}
