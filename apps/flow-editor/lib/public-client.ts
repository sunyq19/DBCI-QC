import navigation from '../config/navigation.json';
import {HANDOFF_TTL,publicQuery,validateHandoff} from './handoff';
const PENDING='dbci-flow-pending',ACCESS='dbci-flow-editor-ui';
export function publicFrontend(){return typeof window!=='undefined'&&location.origin===new URL(navigation.flowUrl).origin;}
export function flowBase(){return publicFrontend()?new URL(navigation.flowUrl).pathname:'/';}
export function apiUrl(path:string){return publicFrontend()?new URL(path,navigation.serviceUrl).href:path;}
export function displaySession(){
 try{const value=JSON.parse(sessionStorage.getItem(ACCESS)||'null');if(value&&Date.now()-value.at<8*60*60*1000)return {signedIn:!!value.signedIn,canEdit:!!value.canEdit,email:null};}catch{}
 return {signedIn:false,canEdit:false,email:null};
}
export function consumeReturn(){
 const prefix='#flow-result=';if(!publicFrontend()||!location.hash.startsWith(prefix))return null;
 try{
  const result=JSON.parse(decodeURIComponent(location.hash.slice(prefix.length)));
  const pending=JSON.parse(sessionStorage.getItem(PENDING)||'null');
  history.replaceState(null,'',location.pathname+location.search);
  if(!pending||result.state!==pending.state||Date.now()-pending.created>HANDOFF_TTL)return null;
  sessionStorage.removeItem(PENDING);
  sessionStorage.setItem(ACCESS,JSON.stringify({signedIn:!!result.signedIn,canEdit:!!result.canEdit,at:Date.now()}));
  return {result,recovery:pending.recovery};
 }catch{return null;}
}
export function beginLogin(logout=false){
 const state=crypto.randomUUID();sessionStorage.setItem(PENDING,JSON.stringify({state,created:Date.now()}));
 const callback='/flow-handoff?'+new URLSearchParams({mode:logout?'logout':'login',state,view:publicQuery(location.search)});
 const url=new URL(logout?'/signout-with-chatgpt':'/flow-handoff',navigation.serviceUrl);
 if(logout)url.searchParams.set('return_to',callback);else url.search=new URLSearchParams({mode:'login',state,view:publicQuery(location.search)}).toString();
 location.assign(url.href);
}
export function submitPublicWrite(payload:Record<string,unknown>,recovery:unknown){
 const envelope=validateHandoff({state:crypto.randomUUID(),created:Date.now(),query:location.search,payload});
 // UI hint only: the server rechecks identity/allowlist on EVERY write.
 sessionStorage.setItem(PENDING,JSON.stringify({...envelope,recovery}));
 const form=document.createElement('form');form.method='POST';form.action=new URL('/flow-handoff',navigation.serviceUrl).href;
 const input=document.createElement('input');input.type='hidden';input.name='envelope';input.value=JSON.stringify(envelope);form.appendChild(input);document.body.appendChild(form);form.submit();
}
