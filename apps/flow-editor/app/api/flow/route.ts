import { env } from 'cloudflare:workers';
import { AppError,readFlow,saveFlow,freezeFlow,ensureHierarchy,syncCatalog,discussFlow,forkFlow } from '../../../lib/repository';
import {readCatalog,catalogStatus} from '../../../lib/catalog-source';
import {editorFor,allowedOrigin,withCors,preflight} from '../../../lib/access';
export const OPTIONS=preflight;
export const dynamic='force-dynamic';
const response=(value:unknown,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}});
function db(){if(!env.DB)throw new AppError('存储服务暂时不可用',503);return env.DB;}
function failure(e:unknown){if(e instanceof AppError)return response({error:e.message},e.status);if(e instanceof SyntaxError)return response({error:'请求格式不正确'},400);console.error('Flow request failed',e instanceof Error?e.message:'unknown');return response({error:'暂时未能完成，请保留当前修改后重试'},500);}
export async function GET(request:Request){try{
  const u=new URL(request.url),v=u.searchParams.get('version'),r=u.searchParams.get('revision');
  if(v&&(!/^[A-Za-z0-9_-]{1,80}$/.test(v)||r))throw new AppError('版本参数不正确');
  if(r&&(!/^\d+$/.test(r)||!Number.isSafeInteger(Number(r))||Number(r)<1))throw new AppError('历史记录编号不正确');
  await ensureHierarchy(db());
  if(!v&&!r)await syncCatalog(db(),await readCatalog());
  const data=await readFlow(db(),{version:v,revision:r?Number(r):null,head:u.searchParams.has('head'),history:u.searchParams.has('history')});
  const result=response({...data,...(!v&&!r?{catalogSync:catalogStatus()}:{})});
  if(request.headers.get('origin')==='https://sunyq19.github.io'){result.headers.set('Access-Control-Allow-Origin','https://sunyq19.github.io');result.headers.set('Vary','Origin');}
  return result;
}catch(e){return withCors(request,failure(e));}}
export async function POST(request:Request){try{
  const respond=(value:unknown,status=200)=>withCors(request,response(value,status));
  if(!allowedOrigin(request))return respond({error:'仅接受本协作页发起的修改'},403);
  const actor=await editorFor(request,db(),(env as unknown as Record<string,string>).FLOW_EDIT_PASSWORD_VERIFIER);
  if(!actor)return respond({error:'请先输入编辑密码'},401);
  if(!request.headers.get('content-type')?.startsWith('application/json'))throw new AppError('需要 JSON 请求');
  const raw=await request.text();if(new TextEncoder().encode(raw).length>2000000)throw new AppError('内容超出 2 MB 限制',413);
  const body=JSON.parse(raw);
  if(!body||typeof body!=='object')throw new AppError('请求内容不正确');
  if(['save','fork','freeze','discuss'].includes(body.action))await syncCatalog(db(),await readCatalog());
  if(body.action==='save'){
    let doc;try{const {validateDoc}=await import('../../../lib/flow');doc=validateDoc(body.doc);}catch(e){throw new AppError(e instanceof Error?e.message:'流程图无效');}
    return respond(await saveFlow(db(),body.baseRevision,doc,body.note,actor.id));
  }
  if(body.action==='fork')return respond(await forkFlow(db(),body.sourceRevision,body.expectedHead,body.doc,body.note,actor.id,await readCatalog()));
  if(body.action==='freeze')return respond(await freezeFlow(db(),body.revision,body.label,body.note??'',actor.id));
  if(body.action==='discuss')return respond(await discussFlow(db(),body,actor));
  throw new AppError('不支持的操作');
}catch(e){return withCors(request,failure(e));}}
