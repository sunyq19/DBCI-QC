import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import {validateDoc,flattenNodes,updateNode,nodeBody,displayNodes} from '../lib/flow';
import {readFlow,saveFlow,freezeFlow,syncCatalog,forkFlow} from '../lib/repository';
import {catalogHash} from '../lib/sync';
import {makePasswordVerifier,unlockEditing} from '../lib/access';
import {POST,GET} from '../app/api/attachments/route';
import {env} from './helpers/identity';
const manifest=JSON.parse(readFileSync('content/sync-manifest.json','utf8'));
function database(){const sql=new DatabaseSync(':memory:');for(const f of readdirSync('drizzle').filter(f=>f.endsWith('.sql')).sort())sql.exec(readFileSync('drizzle/'+f,'utf8'));function prepare(query:string,args:any[]=[]):any{return{bind(...v:any[]){return prepare(query,v)},async first(){return sql.prepare(query).get(...args)||null},async all(){return{results:sql.prepare(query).all(...args)}},async run(){return{meta:sql.prepare(query).run(...args)}}}}return {prepare,async batch(ss:any[]){return Promise.all(ss.map(s=>s.run()))}} as D1Database;}
const origin='https://sunyq19.github.io',base='https://dbci-qc-flow.leoleoleoleoli.chatgpt.site/api/attachments';
test('direct sketches and child connections survive sync, freeze and historical fork',async()=>{
 const db=database();await syncCatalog(db,manifest);let s:any=await readFlow(db);const a='viz_waveform',b='viz_psd';
 s.doc.nodes=updateNode(s.doc.nodes,a,{sketch:{title:'波形展示讨论稿',body:'直接写步骤\n附加说明',positioned:true},x:300,y:400});
 s.doc.drawing={edges:[{id:'loop1',source:a,target:b,label:'对照'},{id:'loop2',source:b,target:a,label:'复核'}]};validateDoc(s.doc);
 await saveFlow(db,s.revision,s.doc,'编辑草稿','test');s=await readFlow(db);const v=await freezeFlow(db,s.revision,'画布讨论版','','test');const fixed:any=await readFlow(db,{version:v.id});
 const next=structuredClone(manifest);next.sequence++;next.doc.nodes[0].description='新增实现描述';next.id='catalog-'+await catalogHash(next.doc,next.sourceVersion);await syncCatalog(db,next);
 const synced:any=await readFlow(db);assert.equal(nodeBody(flattenNodes(synced.doc.nodes).find(n=>n.id===a)!),'直接写步骤\n附加说明');assert.deepEqual(synced.doc.drawing,fixed.doc.drawing);
 const fork=await forkFlow(db,fixed.revision,synced.revision,fixed.doc,'由旧版继续','test',next);assert.deepEqual(fork.doc.drawing,fixed.doc.drawing);assert.equal(flattenNodes(fork.doc.nodes).find(n=>n.id===a)!.x,300);assert.equal((await readFlow(db,{version:v.id})as any).hash,fixed.hash);
 const hidden=updateNode(fork.doc.nodes,a,{sketch:{title:'',body:'',hidden:true}});assert.ok(!flattenNodes(displayNodes(hidden)).some(n=>n.id===a));assert.ok(flattenNodes(hidden).some(n=>n.id===a));
 const bad=structuredClone(fork.doc);bad.drawing!.edges[0].target='missing';assert.throws(()=>validateDoc(bad));
});
test('attachments require editing, validate files and survive removal from later drafts',async()=>{
 const db=database(),objects=new Map<string,ArrayBuffer>(),verifier=await makePasswordVerifier('fixture-password');Object.assign(env,{DB:db,FLOW_EDIT_PASSWORD_VERIFIER:verifier,BUCKET:{async put(k:string,v:ArrayBuffer){objects.set(k,v)},async get(k:string){return objects.has(k)?{body:objects.get(k)}:null},async delete(k:string){objects.delete(k)}}});
 const request=(token?:string,name='示例.csv',content='channel,value\nCPz,12',o=origin)=>{const form=new FormData();form.set('file',new File([content],name));return new Request(base,{method:'POST',headers:{Origin:o,...(token?{'X-Flow-Editor':token}:{})},body:form});};
 assert.equal((await POST(request())).status,401);assert.equal(objects.size,0);
 const auth=await unlockEditing(new Request(base,{headers:{Origin:origin}}),db,verifier,'fixture-password','测试');
 assert.equal((await POST(request(auth.token,'x.html'))).status,400);assert.equal((await POST(request(auth.token,'x.csv','',origin))).status,400);assert.equal((await POST(request(auth.token,'x.csv','a','https://evil.test'))).status,403);
 assert.equal((await POST(request(auth.token,'large.csv','x'.repeat(10485761)))).status,413);
 const uploaded=await POST(request(auth.token));assert.equal(uploaded.status,200);const file:any=await uploaded.json();assert.equal(objects.size,1);
 const downloaded=await GET(new Request(base+'?id='+file.id+'&preview=1'));assert.equal(downloaded.status,200);assert.match(downloaded.headers.get('Content-Disposition')!,/^attachment/);assert.match(await downloaded.text(),/CPz,12/);assert.equal((await GET(new Request(base+'?id=invalid'))).status,404);
 await syncCatalog(db,manifest);let s:any=await readFlow(db);const id=s.doc.nodes[0].id;s.doc.nodes=updateNode(s.doc.nodes,id,{attachments:[file]});await saveFlow(db,s.revision,s.doc,'附上资料','test');s=await readFlow(db);const fixed=await freezeFlow(db,s.revision,'附件版','','test');
 const forged=structuredClone(s.doc);forged.nodes[0].attachments[0].name='伪造.txt';await assert.rejects(()=>saveFlow(db,s.revision,forged,'伪造','test'),/附件不存在/);
 s.doc.nodes=updateNode(s.doc.nodes,id,{attachments:[]});await saveFlow(db,s.revision,s.doc,'移出附件','test');const old:any=await readFlow(db,{version:fixed.id});assert.equal(old.doc.nodes[0].attachments[0].id,file.id);assert.equal((await GET(new Request(base+'?id='+file.id))).status,200);
});
test('visual examples link actual image and measurement files, planned modules have no fabricated image',()=>{
 const examples=JSON.parse(readFileSync('content/visual-examples.json','utf8'));let ready=0;for(const [id,e]of Object.entries(examples)as any){if(e.availability==='planned'){assert.equal(e.image,undefined);continue;}if(id!=='VIS')ready++;assert.match(e.sourceUrl,/openneuro/);assert.ok(readFileSync('public/'+e.image).length>1000);if(id!=='VIS')assert.ok(readFileSync('public/'+e.dataUrl,'utf8').split('\n').length>2);}assert.equal(ready,10);
});
