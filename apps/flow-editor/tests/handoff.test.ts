import test from 'node:test';
import assert from 'node:assert/strict';
import {validateHandoff,resultUrl,publicQuery,scriptJson,HANDOFF_TTL} from '../lib/handoff';
import {POST,GET} from '../app/flow-handoff/route';
import {setIdentity} from './helpers/identity';
const state='01234567-89ab-cdef-0123-456789abcdef';
const origin='https://sunyq19.github.io';
const service='https://dbci-qc-flow.leoleoleoleoli.chatgpt.site';
const envelope=()=>({state,created:Date.now(),query:'?version=scoring-v16&redirect=https://evil.test',payload:{action:'save',baseRevision:9,doc:{},note:'example'}});
test('public return URLs retain versions, reject redirect injection and carry no credentials',()=>{
 const url=new URL(resultUrl(state,{signedIn:true,canEdit:true},envelope().query));
 assert.equal(url.origin,origin);assert.equal(url.pathname,'/DBCI-QC/');assert.equal(url.search,'?version=scoring-v16');
 assert.equal(publicQuery('?revision=9&version=//evil.test'),'revision=9');assert.throws(()=>resultUrl('bad',{}));
 assert.equal(scriptJson('</script><script>bad</script>').includes('<'),false);
});
test('expired, unbounded and unsupported handoffs fail before staging',()=>{
 assert.throws(()=>validateHandoff({...envelope(),created:Date.now()-HANDOFF_TTL-1000}));
 assert.throws(()=>validateHandoff({...envelope(),payload:{action:'delete'}}));
 assert.throws(()=>validateHandoff({...envelope(),payload:{action:'save',doc:'a'.repeat(512000)}}));
});
test('untrusted origins cannot stage writes, including absent or null origin',async()=>{
 for(const value of [null,'null','https://sunyq19.github.io.evil.test','https://evil.test']){
 const r=await POST(new Request(service+'/flow-handoff',{method:'POST',headers:{...(value?{Origin:value}:{}),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({envelope:JSON.stringify(envelope())})}));assert.equal(r.status,403);
 }
});
test('staging uses bounded tab storage, safe script encoding, no database write',async()=>{
 const e=envelope();e.payload.note='</script><script>alert(1)</script>';
 const r=await POST(new Request(service+'/flow-handoff',{method:'POST',headers:{Origin:origin,'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({envelope:JSON.stringify(e)})}));
 const html=await r.text();assert.equal(r.status,200);assert.match(html,/sessionStorage/);assert.match(html,/flow-handoff\?mode=write/);assert.doesNotMatch(html,/<script>alert/);assert.doesNotMatch(html,/fetch\(/);assert.match(r.headers.get('Content-Security-Policy')!,/frame-ancestors 'none'/);
});
test('first-party write handoff retains hosted sign-in and exact editor allowlist',async()=>{
 setIdentity(null);let r=await GET(new Request(service+'/flow-handoff?mode=write&state='+state));
 assert.equal(r.status,302);assert.match(r.headers.get('location')!,/\/signin-with-chatgpt\?return_to=/);
 setIdentity('other@example.test');r=await GET(new Request(service+'/flow-handoff?mode=write&state='+state));assert.doesNotMatch(await r.text(),/fetch\('/);
 setIdentity('editor@example.test');r=await GET(new Request(service+'/flow-handoff?mode=write&state='+state));const html=await r.text();assert.match(html,/fetch\('\/api\/flow'/);assert.match(html,/entry.state!==state/);assert.doesNotMatch(html,/editor@example.test|authenticated-user|access_token|Bearer/);
});
test('login returns a display hint only; writes are never authorized by client flags',async()=>{
 setIdentity('editor@example.test');let r=await GET(new Request(service+'/flow-handoff?mode=login&state='+state+'&view=version%3Dscoring-v16'));const html=await r.text();assert.match(html,/sunyq19.github.io\/DBCI-QC\//);assert.doesNotMatch(html,/editor@example.test|access_token|Bearer/);
 setIdentity(null);r=await GET(new Request(service+'/flow-handoff?mode=write&state='+state+'&canEdit=true'));assert.equal(r.status,302);
});
