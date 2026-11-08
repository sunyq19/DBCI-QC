import navigation from '../config/navigation.json';

// This is navigation, not a new authentication/session system. No access token
// leaves Sites. Every write still runs through the authenticated /api/flow POST.
export const HANDOFF_KEY='dbci-flow-handoff';
export const HANDOFF_TTL=15*60*1000;
export function validState(value:unknown):value is string{return typeof value==='string'&&/^[a-f0-9-]{36}$/.test(value);}
export function publicQuery(value:unknown):string {
 const q=new URLSearchParams(typeof value==='string'?value:''),out=new URLSearchParams();
 const v=q.get('version'),r=q.get('revision');
 if(v&&/^[A-Za-z0-9_-]{1,80}$/.test(v))out.set('version',v);
 else if(r&&/^[1-9][0-9]{0,10}$/.test(r))out.set('revision',r);
 return out.toString();
}
export function resultUrl(state:string,result:Record<string,unknown>,query=''):string{
 if(!validState(state))throw new Error('请求标识无效');
 const target=new URL(navigation.flowUrl);target.search=publicQuery(query);
 target.hash='flow-result='+encodeURIComponent(JSON.stringify({state,...result}));
 return target.href;
}
export function validateHandoff(value:unknown,now=Date.now()){
 const e=value as {state:string;created:number;query:string;payload:Record<string,unknown>};
 if(!e||!validState(e.state)||!Number.isFinite(e.created)||now-e.created>HANDOFF_TTL||e.created>now+60000)throw new Error('保存请求已过期，请返回页面重试');
 if(!e.payload||!['save','freeze'].includes(String(e.payload.action)))throw new Error('不支持的操作');
 if(new TextEncoder().encode(JSON.stringify(e.payload)).length>512000)throw new Error('内容超出 500 KB 限制');
 return {...e,query:publicQuery(e.query)};
}
export function scriptJson(value:unknown){return JSON.stringify(value).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');}
