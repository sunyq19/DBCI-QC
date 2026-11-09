import {env} from 'cloudflare:workers';
import {AppError} from '../../../lib/repository';
import {editorFor,allowedOrigin,json,preflight,accessFailure,createLink,revokeLink} from '../../../lib/access';
export const dynamic='force-dynamic';
export const OPTIONS=preflight;
const db=()=>{if(!env.DB)throw new AppError('存储服务暂时不可用',503);return env.DB;};
const bootstrap=()=> (env as unknown as Record<string,string>).FLOW_OWNER_TOKEN_HASH;
export async function GET(request:Request){try{
 const editor=await editorFor(request,db(),bootstrap());
 if(new URL(request.url).searchParams.has('members')){
  if(editor?.role!=='owner')throw new AppError('仅维护者可以管理编辑链接',403);
  const links=(await db().prepare('SELECT id,label,role,created_at,revoked_at FROM flow_access_links ORDER BY created_at DESC').all()).results;
  return json(request,{links});
 }
 return json(request,{canEdit:!!editor,canManage:editor?.role==='owner',label:editor?.label||''});
}catch(e){return accessFailure(request,e);}}
export async function POST(request:Request){try{
 if(!allowedOrigin(request))throw new AppError('仅接受协作页面的请求',403);
 const editor=await editorFor(request,db(),bootstrap());if(editor?.role!=='owner')throw new AppError('仅维护者可以管理编辑链接',403);
 if(!request.headers.get('content-type')?.startsWith('application/json'))throw new AppError('请求格式不正确');
 const raw=await request.text();if(raw.length>2000)throw new AppError('请求过长');const body=JSON.parse(raw);
 if(body.action==='create')return json(request,await createLink(db(),body.label));
 if(body.action==='revoke')return json(request,await revokeLink(db(),body.id));
 throw new AppError('不支持的操作');
}catch(e){return accessFailure(request,e);}}
