import {env} from 'cloudflare:workers';
import {AppError} from '../../../lib/repository';
import {editorFor,allowedOrigin,json,preflight,accessFailure,unlockEditing,lockEditing} from '../../../lib/access';
export const dynamic='force-dynamic';
export const OPTIONS=preflight;
const db=()=>{if(!env.DB)throw new AppError('存储服务暂时不可用',503);return env.DB;};
const verifier=()=> (env as unknown as Record<string,string>).FLOW_EDIT_PASSWORD_VERIFIER;
export async function GET(request:Request){try{const editor=await editorFor(request,db(),verifier());return json(request,{canEdit:!!editor,label:editor?.label||''});}catch(e){return accessFailure(request,e);}}
export async function POST(request:Request){try{
 if(!allowedOrigin(request))throw new AppError('仅接受协作页面的请求',403);
 if(!request.headers.get('content-type')?.startsWith('application/json'))throw new AppError('请求格式不正确');
 const raw=await request.text();if(raw.length>2000)throw new AppError('请求过长');const body=JSON.parse(raw);
 if(body.action==='unlock')return json(request,await unlockEditing(request,db(),verifier(),body.password,body.label));
 if(body.action==='lock')return json(request,await lockEditing(request,db()));
 throw new AppError('不支持的操作');
}catch(e){return accessFailure(request,e);}}
