import {env} from 'cloudflare:workers';
import {AppError} from '../../../lib/repository';
import {editorFor,allowedOrigin,json,preflight,accessFailure,withCors} from '../../../lib/access';
export const dynamic='force-dynamic';
export const OPTIONS=preflight;
const LIMIT=10*1024*1024;
const types:Record<string,string>={png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',webp:'image/webp',pdf:'application/pdf',txt:'text/plain',md:'text/plain',csv:'text/csv',json:'application/json',docx:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',pptx:'application/vnd.openxmlformats-officedocument.presentationml.presentation',xlsx:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',zip:'application/zip'};
function resources(){const e=env as unknown as {DB:D1Database;BUCKET:R2Bucket;FLOW_EDIT_PASSWORD_VERIFIER?:string};if(!e.DB||!e.BUCKET)throw new AppError('附件存储暂不可用',503);return e;}
export async function POST(request:Request){try{
 if(!allowedOrigin(request))throw new AppError('仅接受协作页面的上传',403);
 const {DB,BUCKET,FLOW_EDIT_PASSWORD_VERIFIER}=resources(),actor=await editorFor(request,DB,FLOW_EDIT_PASSWORD_VERIFIER);if(!actor)throw new AppError('请先输入编辑密码',401);
 if(!request.headers.get('content-type')?.startsWith('multipart/form-data'))throw new AppError('请选择附件');
 if(Number(request.headers.get('content-length')||0)>LIMIT+16384)throw new AppError('单个附件不能超过10 MB',413);
 // Bound the body even if the client omits Content-Length.
 const reader=request.body?.getReader();if(!reader)throw new AppError('附件为空');const chunks:Uint8Array[]=[];let size=0;
 while(true){const part=await reader.read();if(part.done)break;size+=part.value.byteLength;if(size>LIMIT+16384){await reader.cancel();throw new AppError('单个附件不能超过10 MB',413);}chunks.push(part.value);}
 const raw=new Uint8Array(size);let offset=0;for(const c of chunks){raw.set(c,offset);offset+=c.byteLength;}
 const form=await new Response(raw,{headers:{'Content-Type':request.headers.get('content-type')!}}).formData();const file=form.get('file');
 if(!file||typeof file==='string'||!file.size)throw new AppError('请选择非空附件');if(file.size>LIMIT)throw new AppError('单个附件不能超过10 MB',413);
 const name=file.name.split(/[\\/]/).pop()!.replace(/[\u0000-\u001f\u007f]/g,'').slice(0,180),ext=name.split('.').pop()!.toLowerCase(),mime=types[ext];if(!mime)throw new AppError('支持图片、PDF、Office文档、文本、CSV及ZIP');
 const id=crypto.randomUUID(),key='module-files/'+id;
 await BUCKET.put(key,await file.arrayBuffer(),{httpMetadata:{contentType:mime}});
 try{await DB.prepare('INSERT INTO flow_attachments (id,name,size,mime,storage_key,created_at,author_id) VALUES (?,?,?,?,?,?,?)').bind(id,name,file.size,mime,key,new Date().toISOString(),actor.id).run();}catch(e){await BUCKET.delete(key);throw e;}
 return json(request,{id,name,size:file.size,mime});
}catch(e){return accessFailure(request,e);}}
export async function GET(request:Request){try{
 const {DB,BUCKET}=resources(),url=new URL(request.url),id=url.searchParams.get('id')||'';if(!/^[a-f0-9-]{36}$/.test(id))throw new AppError('附件不存在',404);
 const file=await DB.prepare('SELECT name,size,mime,storage_key FROM flow_attachments WHERE id=?').bind(id).first<{name:string;size:number;mime:string;storage_key:string}>();if(!file)throw new AppError('附件不存在',404);
 const object=await BUCKET.get(file.storage_key);if(!object)throw new AppError('附件暂不可用',404);
 const inline=url.searchParams.get('preview')==='1'&&['image/png','image/jpeg','image/webp'].includes(file.mime);
 return withCors(request,new Response(object.body,{headers:{'Content-Type':file.mime,'Content-Length':String(file.size),'Content-Disposition':`${inline?'inline':'attachment'}; filename*=UTF-8''${encodeURIComponent(file.name)}`,'Cache-Control':'public, max-age=31536000, immutable','X-Content-Type-Options':'nosniff','Content-Security-Policy':"default-src 'none'; sandbox"}}));
}catch(e){return accessFailure(request,e);}}
