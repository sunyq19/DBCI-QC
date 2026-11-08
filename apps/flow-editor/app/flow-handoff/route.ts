import {env} from 'cloudflare:workers';
import {getChatGPTUser,chatGPTSignInPath} from '../chatgpt-auth';
import {isEditor} from '../../lib/flow';
import navigation from '../../config/navigation.json';
import {HANDOFF_KEY,HANDOFF_TTL,validState,publicQuery,resultUrl,validateHandoff,scriptJson} from '../../lib/handoff';
export const dynamic='force-dynamic';

function page(script:string){
 const nonce=crypto.randomUUID();
 return new Response(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>DBCI-QC · 模块流程</title><body><p>正在返回模块流程…</p><script nonce="${nonce}">${script}</script></body></html>`,{headers:{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','Content-Security-Policy':`default-src 'none'; script-src 'nonce-${nonce}'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'`}});
}
function back(state:string,result:Record<string,unknown>,query=''){return page(`location.replace(${scriptJson(resultUrl(state,result,query))});`);}

export async function POST(request:Request){
 // Only the configured public frontend can stage a write; staging never writes
 // the database. First-party navigation obtains the existing Lax auth cookie.
 if(request.headers.get('origin')!==new URL(navigation.flowUrl).origin)return new Response('Forbidden',{status:403});
 if(!request.headers.get('content-type')?.startsWith('application/x-www-form-urlencoded'))return new Response('Unsupported content type',{status:415});
 const raw=await request.text();if(raw.length>3500000)return new Response('Request too large',{status:413});
 try{
  const envelope=validateHandoff(JSON.parse(new URLSearchParams(raw).get('envelope')||''));
  const next='/flow-handoff?mode=write&state='+envelope.state;
  return page(`try{sessionStorage.setItem(${scriptJson(HANDOFF_KEY)},${scriptJson(JSON.stringify(envelope))});location.replace(${scriptJson(next)});}catch{location.replace(${scriptJson(resultUrl(envelope.state,{error:'浏览器无法暂存修改，请保留草稿后重试'},envelope.query))});}`);
 }catch{return new Response('Invalid or expired request',{status:400});}
}

export async function GET(request:Request){
 const u=new URL(request.url),state=u.searchParams.get('state'),mode=u.searchParams.get('mode'),query=publicQuery(u.searchParams.get('view'));
 if(!validState(state)||!['login','logout','write'].includes(mode||''))return new Response('Invalid request',{status:400});
 if(mode==='logout')return back(state,{signedIn:false,canEdit:false,action:'logout'},query);
 const user=await getChatGPTUser();
 if(!user)return Response.redirect(new URL(chatGPTSignInPath(u.pathname+u.search),request.url),302);
 const canEdit=isEditor(user.email,env.FLOW_EDITOR_EMAILS);
 if(mode==='login')return back(state,{signedIn:true,canEdit,action:'login'},query);
 if(!canEdit)return back(state,{signedIn:true,canEdit:false,error:'当前账号只有查看权限'});
 // Writes execute on the service origin under the existing authenticated session.
 // The returned fragment contains only public result/status, never credentials.
 return page(`(async()=>{
 const key=${scriptJson(HANDOFF_KEY)},state=${scriptJson(state)},target=${scriptJson(navigation.flowUrl)};
 let entry;let result={signedIn:true,canEdit:true};
 try{
  entry=JSON.parse(sessionStorage.getItem(key)||'null');
  if(!entry||entry.state!==state||Date.now()-entry.created>${HANDOFF_TTL}||entry.created>Date.now()+60000)throw new Error('保存请求已过期，请返回页面重试');
  sessionStorage.removeItem(key);
  const r=await fetch('/api/flow',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(entry.payload)});
  const data=await r.json();if(!r.ok)throw new Error(data.error||'保存失败，请重试');
  result={...result,action:entry.payload.action,revision:data.revision,version:entry.payload.action==='freeze'?data.id:undefined};
 }catch(e){result.error=e.message||'保存失败，请重试';}
 const url=new URL(target);if(result.error&&entry?.query)url.search=entry.query;
 if(result.version)url.searchParams.set('version',result.version);
 url.hash='flow-result='+encodeURIComponent(JSON.stringify({state,...result}));location.replace(url.href);
})()`);
}
