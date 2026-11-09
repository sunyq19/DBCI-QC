import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import {validateDoc,flattenNodes,updateNode,type Proposal} from '../lib/flow';
import {initialize,readFlow,saveFlow,freezeFlow,discussFlow,syncCatalog,forkFlow} from '../lib/repository';
import {newToken,tokenHash,editorFor,makePasswordVerifier,unlockEditing,lockEditing,SESSION_MS,preflight} from '../lib/access';
import {catalogHash,mergeCatalog} from '../lib/sync';
const manifest=JSON.parse(readFileSync('content/sync-manifest.json','utf8'));
function database(){const sql=new DatabaseSync(':memory:');for(const f of readdirSync('drizzle').filter(f=>f.endsWith('.sql')).sort())sql.exec(readFileSync('drizzle/'+f,'utf8'));function prepare(query:string,args:any[]=[]):any{return{bind(...values:any[]){return prepare(query,values)},async first(){return sql.prepare(query).get(...args)||null},async all(){return {results:sql.prepare(query).all(...args)}},async run(){return {meta:sql.prepare(query).run(...args)}}}}return{prepare,async batch(ss:any[]){return Promise.all(ss.map(s=>s.run()))}} as D1Database;}
const proposal:Proposal={status:'discussing',description:'改进当前方法的适用条件',conditions:'EEG',inputs:'电压',outputs:'候选通道',methods:'保留现有方法供对比',scoring:'权重待讨论',decision:''};
const actor={id:'test-editor',label:'测试成员'};
const req=(token?:string,origin='https://sunyq19.github.io')=>new Request('https://dbci-qc-flow.leoleoleoleoli.chatgpt.site/api/flow',{headers:{Origin:origin,...(token?{'X-Flow-Editor':token}:{})}});
test('password unlock issues hashed expiring sessions; legacy links, expired and rotated sessions fail',async()=>{
 const db=database(),password='test-only-password',verifier=await makePasswordVerifier(password),now=Date.now();
 assert.equal(await editorFor(req(),db,verifier),null);
 await assert.rejects(()=>unlockEditing(req(),db,verifier,'wrong','测试',now),{status:401});
 const session=await unlockEditing(req(),db,verifier,password,'测试',now);
 assert.equal((await editorFor(req(session.token),db,verifier,now))?.label,'测试');
 const stored=JSON.stringify(await db.prepare('SELECT * FROM flow_edit_sessions').all());assert.ok(!stored.includes(session.token));assert.ok(!stored.includes(password));
 await assert.rejects(()=>editorFor(req(session.token),db,verifier,now+SESSION_MS),{status:401});
 const rotated=await makePasswordVerifier('rotated');await assert.rejects(()=>editorFor(req(session.token),db,rotated,now),{status:401});
 const legacy=newToken();await db.prepare('INSERT INTO flow_access_links (id,token_hash,label,role,created_at) VALUES (?,?,?,?,?)').bind('old',await tokenHash(legacy),'旧链接','editor',new Date().toISOString()).run();
 await assert.rejects(()=>editorFor(req(legacy),db,verifier,now),{status:401});
 await lockEditing(req(session.token),db);await assert.rejects(()=>editorFor(req(session.token),db,verifier,now),{status:401});
});
test('incorrect passwords are rate limited and recover in the next window',async()=>{
 const db=database(),verifier=await makePasswordVerifier('test-only'),now=1800000;
 for(let i=0;i<12;i++)await assert.rejects(()=>unlockEditing(req(),db,verifier,'bad','',now),{status:401});
 await assert.rejects(()=>unlockEditing(req(),db,verifier,'test-only','',now),{status:429});
 assert.equal((await unlockEditing(req(),db,verifier,'test-only','',now+900000)).label,'协作成员');
});
test('preflight only trusts the exact frontend or same-origin',()=>{assert.equal(preflight(req()).status,204);assert.equal(preflight(req(undefined,'https://sunyq19.github.io.evil.test')).status,403);assert.equal(preflight(req(undefined,'null')).status,403);assert.equal(preflight(req()).headers.get('Access-Control-Allow-Headers'),'X-Flow-Editor, Content-Type');});
test('proposals, comments, replies and resolutions are frozen together; code sync preserves them',async()=>{const db=database();await initialize(db);await syncCatalog(db,manifest);let state:any=await readFlow(db);const id='f_continuity';state.doc.nodes=updateNode(state.doc.nodes,id,{proposal});await saveFlow(db,state.revision,state.doc,'起草方案',actor.id);state=await readFlow(db);await discussFlow(db,{baseRevision:state.revision,nodeId:id,operation:'comment',body:'请补充断续记录的处理依据'},actor);state=await readFlow(db);const thread=flattenNodes(state.doc.nodes).find(n=>n.id===id)!.discussion![0];assert.equal(thread.author,actor.label);await discussFlow(db,{baseRevision:state.revision,nodeId:id,operation:'reply',threadId:thread.id,body:'已列入待验证项目'},actor);state=await readFlow(db);const fixed=await freezeFlow(db,state.revision,'协作讨论版','包括草稿和讨论',actor.id);const frozen:any=await readFlow(db,{version:fixed.id});await discussFlow(db,{baseRevision:state.revision,nodeId:id,operation:'resolve',threadId:thread.id},actor);state=await readFlow(db);const next=structuredClone(manifest);next.sequence++;next.doc.nodes[0].description='新版实现';next.id='catalog-'+await catalogHash(next.doc,next.sourceVersion);await syncCatalog(db,next);state=await readFlow(db);const node=flattenNodes(state.doc.nodes).find(n=>n.id===id)!;assert.deepEqual(node.proposal,proposal);assert.equal(node.discussion![0].resolved,true);assert.equal(node.discussion![0].replies[0].body,'已列入待验证项目');assert.equal((await readFlow(db,{version:fixed.id}) as any).hash,frozen.hash);assert.equal(flattenNodes(frozen.doc.nodes).find(n=>n.id===id)!.discussion![0].resolved,false);});
test('public document saves cannot forge, overwrite or delete discussion authors and messages',async()=>{const db=database();await initialize(db);let state:any=await readFlow(db);const id=state.doc.nodes[0].id;await discussFlow(db,{baseRevision:state.revision,nodeId:id,operation:'comment',body:'保留的讨论'},actor);state=await readFlow(db);const changed=structuredClone(state.doc);changed.nodes[0].discussion[0].author='伪造身份';await assert.rejects(()=>saveFlow(db,state.revision,changed,'修改',actor.id),/批注通过/);delete changed.nodes[0].discussion;await assert.rejects(()=>saveFlow(db,state.revision,changed,'删除',actor.id),/批注通过/);await assert.rejects(()=>discussFlow(db,{baseRevision:1,nodeId:id,operation:'reply',body:'旧页面'},actor),{status:409});});
test('untrusted payloads, duplicate messages and malformed proposals are rejected',async()=>{const db=database();await initialize(db);const state:any=await readFlow(db);state.doc.nodes[0].proposal={...proposal,execute:'rm'};assert.throws(()=>validateDoc(state.doc));delete state.doc.nodes[0].proposal;state.doc.nodes[0].teamNotes=12;assert.throws(()=>validateDoc(state.doc));await assert.rejects(()=>discussFlow(db,{baseRevision:1,nodeId:state.doc.nodes[0].id,operation:'comment',body:'a'.repeat(4001)},actor));});
test('retired then restored modules keep collaborative material without reverting current code',()=>{const initial=mergeCatalog(manifest.doc,manifest);const original=initial.nodes[0];original.proposal=proposal;original.discussion=[];const changed=structuredClone(manifest);changed.sequence++;changed.doc.nodes[0].description='新实现';const result=mergeCatalog(initial,changed);assert.deepEqual(result.nodes[0].proposal,proposal);assert.equal(result.nodes[0].description,'新实现');});

import {env,setIdentity} from './helpers/identity';
import {POST as postFlow} from '../app/api/flow/route';
import {POST as postAccess} from '../app/api/access/route';
test('API rejects anonymous and cross-origin writes, unlocks by password, and locks sessions',async()=>{
 const db=database();(env as any).DB=db;(env as any).FLOW_EDIT_PASSWORD_VERIFIER=await makePasswordVerifier('api-test');setIdentity('editor@example.test');
 const post=(route:string,data:any,t?:string,origin='https://sunyq19.github.io')=>new Request('https://dbci-qc-flow.leoleoleoleoli.chatgpt.site/api/'+route,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json',...(t?{'X-Flow-Editor':t}:{})},body:JSON.stringify(data)});
 let response=await postFlow(post('flow',{action:'freeze',canEdit:true,revision:1,label:'forged'}));assert.equal(response.status,401);assert.equal(response.headers.get('Access-Control-Allow-Origin'),'https://sunyq19.github.io');
 response=await postFlow(post('flow',{action:'freeze',revision:1,label:'old-account'},undefined,'https://dbci-qc-flow.leoleoleoleoli.chatgpt.site'));assert.equal(response.status,401);
 response=await postAccess(post('access',{action:'unlock',password:'wrong'}));assert.equal(response.status,401);
 response=await postAccess(post('access',{action:'unlock',password:'api-test'},undefined,'https://evil.test'));assert.equal(response.status,403);
 response=await postAccess(post('access',{action:'unlock',password:'api-test',label:'测试成员'}));assert.equal(response.status,200);const {token}=await response.json() as {token:string};
 await initialize(db);await syncCatalog(db,manifest);const current:any=await readFlow(db);
 response=await postFlow(post('flow',{action:'discuss',baseRevision:current.revision,nodeId:current.doc.nodes[0].id,operation:'comment',body:'API验证'},token));assert.equal(response.status,200,await response.text());
 response=await postFlow(post('flow',{action:'fork',sourceRevision:current.revision,expectedHead:current.revision+1,doc:current.doc,note:'从旧版本起草'},token));assert.equal(response.status,200,await response.text());
 response=await postAccess(post('access',{action:'lock'},token));assert.equal(response.status,200);
 response=await postFlow(post('flow',{action:'freeze',revision:current.revision+2,label:'locked'},token));assert.equal(response.status,401);
});
test('fork an earlier fixed version; preserve original and intervening history, comments and lineage',async()=>{
 const db=database();await initialize(db);await syncCatalog(db,manifest);let state:any=await readFlow(db);const id='f_continuity';
 state.doc.nodes=updateNode(state.doc.nodes,id,{proposal});await saveFlow(db,state.revision,state.doc,'方案A',actor.id);state=await readFlow(db);
 await discussFlow(db,{baseRevision:state.revision,nodeId:id,operation:'comment',body:'版本A的讨论'},actor);state=await readFlow(db);
 const fixed=await freezeFlow(db,state.revision,'A','',actor.id),source:any=await readFlow(db,{version:fixed.id});
 state.doc.nodes=updateNode(state.doc.nodes,id,{proposal:{...proposal,description:'版本B'}});await saveFlow(db,state.revision,state.doc,'方案B',actor.id);const later:any=await readFlow(db);
 const incoming=structuredClone(source.doc);incoming.nodes=updateNode(incoming.nodes,id,{proposal:{...proposal,description:'从A起草C'}});
 const result=await forkFlow(db,source.revision,later.revision,incoming,'基于A起草C',actor.id,manifest);
 assert.equal(result.revision,later.revision+1);assert.equal(result.basedOnRevision,source.revision);
 assert.equal((await readFlow(db) as any).basedOnRevision,source.revision);
 assert.equal((await readFlow(db,{version:fixed.id}) as any).hash,source.hash);assert.equal((await readFlow(db,{revision:later.revision}) as any).hash,later.hash);
 const node=flattenNodes(result.doc.nodes).find(n=>n.id===id)!;assert.equal(node.proposal!.description,'从A起草C');assert.deepEqual(node.discussion,flattenNodes(source.doc.nodes).find(n=>n.id===id)!.discussion);
 const v=await freezeFlow(db,result.revision,'C','',actor.id);assert.equal((await readFlow(db,{version:v.id}) as any).revision,result.revision);
});
test('fork checks concurrency, provenance, source fields and discussion authors',async()=>{
 const db=database();await initialize(db);await syncCatalog(db,manifest);const source:any=await readFlow(db);await saveFlow(db,source.revision,source.doc,'并发保存',actor.id);
 await assert.rejects(()=>forkFlow(db,source.revision,source.revision,source.doc,'旧基准',actor.id,manifest),{status:409});
 await assert.rejects(()=>forkFlow(db,9999,source.revision+1,source.doc,'无来源',actor.id,manifest),{status:404});
 const forged=structuredClone(source.doc);forged.nodes[0].description='绕过实现保护';await assert.rejects(()=>forkFlow(db,source.revision,source.revision+1,forged,'改实现',actor.id,manifest),/质控台同步/);
 const messages=structuredClone(source.doc);messages.nodes[0].discussion=[{id:'forged',author:'别人',body:'伪造批注',createdAt:new Date().toISOString(),resolved:false,replies:[]}];await assert.rejects(()=>forkFlow(db,source.revision,source.revision+1,messages,'改批注',actor.id,manifest),/批注通过/);
 assert.equal((await readFlow(db,{head:true})).latestRevision,source.revision+1);
});
test('legacy versions can seed a new draft with current implementations and retained notes',async()=>{
 const db=database();await initialize(db);const old:any=await readFlow(db,{version:'baseline-v1'});await syncCatalog(db,manifest);const current:any=await readFlow(db);
 old.doc.nodes[0].proposal=proposal;
 const result=await forkFlow(db,old.revision,current.revision,old.doc,'从初版起草',actor.id,manifest);
 assert.equal(result.doc.catalog?.id,manifest.id);assert.deepEqual(result.doc.nodes[0].proposal,proposal);assert.equal(result.doc.nodes[0].description,manifest.doc.nodes[0].description);
 assert.equal((await readFlow(db,{version:'baseline-v1'}) as any).hash,old.hash);
});
