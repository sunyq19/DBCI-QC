import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync,readFileSync,writeFileSync} from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {pbkdf2Sync,randomBytes} from 'node:crypto';
import {request as httpRequest} from 'node:http';
import {openDatabase,diskBucket} from '../self-host/storage.mjs';
test('persistent database, atomic batch rollback and attachments',async()=>{
 const root=mkdtempSync(path.join(os.tmpdir(),'flow-storage-'));let db=openDatabase(path.join(root,'flow.sqlite'),'drizzle');
 try{
  await assert.rejects(()=>db.batch([db.prepare('INSERT INTO flow_unlock_attempts VALUES (?,?,?)').bind('x',1,1),db.prepare('INSERT INTO flow_unlock_attempts VALUES (?,?,?)').bind('x',1,1)]));
  assert.equal(await db.prepare('SELECT * FROM flow_unlock_attempts WHERE client_hash=?').bind('x').first(),null);
  await db.prepare('INSERT INTO flow_unlock_attempts VALUES (?,?,?)').bind('x',1,2).run();db.close();db=openDatabase(path.join(root,'flow.sqlite'),'drizzle');assert.equal((await db.prepare('SELECT * FROM flow_unlock_attempts').first()).attempts,2);
  const bucket=diskBucket(path.join(root,'files')),key='module-files/'+crypto.randomUUID();await bucket.put(key,Buffer.from('attachment'));assert.equal(Buffer.from((await bucket.get(key)).body).toString(),'attachment');await bucket.delete(key);assert.equal(await bucket.get(key),null);await assert.rejects(()=>bucket.get('../secret'));
 }finally{db.close();rmSync(root,{recursive:true,force:true});}
});
for(const publicOrigin of [undefined,'https://qc.example.test']) test(`self-host ${publicOrigin||'local HTTP'}: unlock, save, conflict, freeze, fork, attachment and restart`,async()=>{
 const root=mkdtempSync(path.join(os.tmpdir(),'flow-http-')),salt=randomBytes(16),password='self-host-test-only';
 writeFileSync(path.join(root,'verifier'),'pbkdf2:100000:'+salt.toString('hex')+':'+pbkdf2Sync(password,salt,100000,32,'sha256').toString('hex'),{mode:0o600});
 const base='http://127.0.0.1:19871',origin=publicOrigin||base;let child,token;
 const request=async(p,init={})=>{
  const webRequest=new Request(base+p,init),body=webRequest.body?Buffer.from(await webRequest.arrayBuffer()):undefined;
  const headers=Object.fromEntries(webRequest.headers);headers.host=new URL(origin).host;
  return new Promise((resolve,reject)=>{
   const call=httpRequest(base+p,{method:webRequest.method,headers},response=>{
    const chunks=[];response.on('data',c=>chunks.push(c));response.on('end',()=>resolve(new Response(Buffer.concat(chunks),{status:response.statusCode,headers:response.headers})));response.on('error',reject);
   });call.on('error',reject);call.end(body);
  });
 };
 async function start(){child=spawn(process.execPath,['server.mjs'],{cwd:path.resolve('dist-self-host'),env:{...process.env,FLOW_DATA_DIR:root,FLOW_PASSWORD_FILE:path.join(root,'verifier'),FLOW_PORT:'19871',FLOW_PUBLIC_ORIGIN:publicOrigin||''},stdio:['ignore','pipe','pipe']});await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Server startup timeout')),5000);child.stdout.on('data',()=>{clearTimeout(timer);resolve()});child.on('exit',code=>reject(new Error('Server exited '+code)));});}
 async function stop(){const p=new Promise(r=>child.on('exit',r));child.kill();await p;}
 const get=async p=>{const r=await request(p);assert.equal(r.status,200);return r.json()};
 const post=async(p,body,source=origin)=>request(p,{method:'POST',headers:{Origin:source,'Content-Type':'application/json',...(token?{'X-Flow-Editor':token}:{})},body:JSON.stringify(body)});
 try{
  await start();
  if(publicOrigin)assert.equal((await fetch(base+'/api/flow',{headers:{'X-Forwarded-Host':'qc.example.test','X-Forwarded-Proto':'https'}})).status,403);
  assert.equal((await request('/flow/')).status,200);const current=await get('/api/flow');
  assert.equal((await post('/api/flow',{action:'freeze',revision:current.revision,label:'Denied'})).status,401);
  assert.equal((await post('/api/access',{action:'unlock',password},'http://evil.test')).status,403);
  const login=await post('/api/access',{action:'unlock',password,label:'Test'});assert.equal(login.status,200);token=(await login.json()).token;
  let doc=structuredClone(current.doc);doc.nodes[0].teamNotes='Persistent collaboration note';
  let r=await post('/api/flow',{action:'save',baseRevision:current.revision,doc,note:'Self-host verification'});assert.equal(r.status,200,await r.clone().text());const saved=await r.json();
  assert.equal((await post('/api/flow',{action:'save',baseRevision:current.revision,doc,note:'Stale'})).status,409);
  r=await post('/api/flow',{action:'freeze',revision:saved.revision,label:'Test fixed version'});assert.equal(r.status,200);const fixed=await r.json();
  const form=new FormData();form.set('file',new Blob(['test attachment']), 'example.txt');r=await request('/api/attachments',{method:'POST',headers:{Origin:origin,'X-Flow-Editor':token},body:form});assert.equal(r.status,200);const file=await r.json();assert.equal(await (await request('/api/attachments?id='+file.id)).text(),'test attachment');
  r=await post('/api/flow',{action:'fork',sourceRevision:saved.revision,expectedHead:saved.revision,doc,note:'Branch from saved version'});assert.equal(r.status,200);
  await stop();await start();const persisted=await get('/api/flow?version='+fixed.id);assert.equal(persisted.doc.nodes[0].teamNotes,'Persistent collaboration note');assert.equal(persisted.revision,saved.revision);assert.equal((await get('/api/flow')).revision,saved.revision+1);
 }finally{if(child?.exitCode===null)await stop();rmSync(root,{recursive:true,force:true});}
});
