import test from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync} from 'node:fs';
import {seed} from '../lib/seed';
import {validateDoc,isEditor} from '../lib/flow';
import {initialize,readFlow,saveFlow,freezeFlow,digest} from '../lib/repository';
function database(){
 const sql=new DatabaseSync(':memory:');sql.exec(readFileSync('drizzle/0000_high_moonstone.sql','utf8'));
 function prepare(query:string,args:unknown[]=[]):any{return{bind(...values:unknown[]){return prepare(query,values);},async first(){return sql.prepare(query).get(...args as any[])||null;},async all(){return{results:sql.prepare(query).all(...args as any[])};},async run(){return{meta:sql.prepare(query).run(...args as any[])};}};}
 return{prepare,async batch(statements:any[]){sql.exec('BEGIN');try{const r=[];for(const s of statements)r.push(await s.run());sql.exec('COMMIT');return r;}catch(e){sql.exec('ROLLBACK');throw e;}}} as unknown as D1Database;
}
test('initial graph is a bounded DAG with scoring explicitly under review',()=>{const d=validateDoc(seed);assert.equal(d.nodes.length,14);assert.equal(d.nodes.find(n=>n.id==='M08')?.status,'review');assert.match(d.nodes.find(n=>n.id==='M08')!.notes,/23.37/);});
test('invalid references, duplicate ids, loops and unsafe coordinates are rejected',()=>{
 for(const mutate of [(d:any)=>d.edges.push({id:'bad',source:'M09',target:'M01',label:''}),(d:any)=>d.edges[0].target='missing',(d:any)=>d.nodes.push(d.nodes[0]),(d:any)=>d.nodes[0].x=Infinity,(d:any)=>d.nodes[0].scope=['arbitrary'],(d:any)=>d.nodes[0].code='alert(1)']){const d=structuredClone(seed);mutate(d);assert.throws(()=>validateDoc(d));}
});
test('email allowlist is exact; anonymous and nonmembers cannot edit',()=>{assert.equal(isEditor(null,'a@test.io'),false);assert.equal(isEditor('a@test.io',undefined),false);assert.equal(isEditor('a@test.io.evil','a@test.io'),false);assert.equal(isEditor('A@TEST.IO','a@test.io, b@test.io'),true);assert.equal(isEditor('a@test.io','*'),false);});
test('initial release persists, excludes private identity, and has a content hash',async()=>{const db=database();await initialize(db);const state:any=await readFlow(db,{version:'baseline-v1'});assert.equal(state.revision,1);assert.equal(state.hash,await digest(state.doc));assert.equal(state.version.label,'v1.0');assert.ok(!('author_id'in state.version));await initialize(db);assert.deepEqual(await readFlow(db,{head:true}),{latestRevision:1});});
test('simultaneous saves cannot silently overwrite each other',async()=>{const db=database();await initialize(db);const a=structuredClone(seed),b=structuredClone(seed);a.nodes[0].title='A';b.nodes[0].title='B';const results=await Promise.allSettled([saveFlow(db,1,a,'A修改','private-a'),saveFlow(db,1,b,'B修改','private-b')]);assert.equal(results.filter(r=>r.status==='fulfilled').length,1);const failed:any=results.find(r=>r.status==='rejected');assert.equal(failed.reason.status,409);assert.deepEqual(await readFlow(db,{head:true}),{latestRevision:2});assert.ok(!JSON.stringify(await readFlow(db,{history:true})).includes('private-'));});
test('frozen link is immutable; later changes and restore append history',async()=>{const db=database();await initialize(db);const d=structuredClone(seed);d.title='第一轮讨论';await saveFlow(db,1,d,'修改标题','private-a');const v=await freezeFlow(db,2,'v1.1','固定本次讨论','private-a');d.title='第二轮讨论';await saveFlow(db,2,d,'继续修改','private-a');const frozen:any=await readFlow(db,{version:v.id});assert.equal(frozen.doc.title,'第一轮讨论');assert.equal(frozen.revision,2);await saveFlow(db,3,frozen.doc,'恢复旧版为新草稿','private-a');const state:any=await readFlow(db);assert.equal(state.revision,4);assert.equal(state.doc.title,'第一轮讨论');assert.equal((await readFlow(db,{version:'baseline-v1'})as any).doc.title,seed.title);});
test('freeze rejects stale revisions and duplicate labels',async()=>{const db=database();await initialize(db);await saveFlow(db,1,seed,'版本记录','editor');await assert.rejects(()=>freezeFlow(db,1,'v2','','editor'),{status:409});await assert.rejects(()=>freezeFlow(db,2,'v1.0','','editor'),{status:409});});
test('unknown snapshots fail explicitly and malformed saves add no history',async()=>{const db=database();await initialize(db);await assert.rejects(()=>readFlow(db,{version:'unknown'}),{status:404});await assert.rejects(()=>saveFlow(db,1,{},'坏输入','editor'));await assert.rejects(()=>saveFlow(db,1,seed,'','editor'));assert.deepEqual(await readFlow(db,{head:true}),{latestRevision:1});});

test('hierarchy upgrade covers the registry and preserves every fixed snapshot and existing edit',async()=>{
 const {withCatalog}=await import('../lib/catalog');const {flattenNodes,updateNode,removeNode}=await import('../lib/flow');const {ensureHierarchy}=await import('../lib/repository');
 const d=withCatalog(seed),all=flattenNodes(d.nodes);
 assert.equal(all.filter(n=>n.entryType==='method'&&n.status!=='planned').length,47);
 assert.equal(all.filter(n=>n.entryType==='method'&&n.status==='planned').length,3);
 assert.equal(all.filter(n=>n.entryType==='reader').length,6);
 assert.equal(all.filter(n=>n.entryType==='check').length,11);
 assert.equal(new Set(all.map(n=>n.id)).size,all.length);
 assert.equal(all.find(n=>n.id==='f_spikeinterface_bad_channels')?.scope.join(','),'np');
 assert.deepEqual(all.find(n=>n.id==='f_fieldtrip_zvalue')?.scope,['eeg','ecog','seeg']);
 const edited=updateNode(d.nodes,'f_prep_nonspatial',{title:'团队修改 PREP'});
 assert.equal(flattenNodes(edited).find(n=>n.id==='f_prep_nonspatial')?.title,'团队修改 PREP');
 assert.ok(!flattenNodes(removeNode(d.nodes,'f_edf_reader')).some(n=>n.entryType==='reader'));
 const db=database();await initialize(db);const old=structuredClone(seed);old.nodes[1].title='成员保留的标题';await saveFlow(db,1,old,'成员先修改','editor');
 await Promise.all([ensureHierarchy(db),ensureHierarchy(db)]);const current:any=await readFlow(db);
 assert.equal(current.revision,3);assert.equal(current.doc.nodes[1].title,'成员保留的标题');
 assert.deepEqual((await readFlow(db,{version:'baseline-v1'})as any).doc,seed);
 assert.equal((await readFlow(db,{version:'visualization-v13'})as any).hash,current.hash);
 await saveFlow(db,3,{...current.doc,nodes:edited},'继续维护子方法','editor');await ensureHierarchy(db);
 assert.equal((await readFlow(db)as any).revision,4);assert.equal((await readFlow(db,{version:'visualization-v13'})as any).revision,3);
});
test('malformed and excessively deep children cannot enter shared storage',async()=>{
 const {withCatalog}=await import('../lib/catalog');
 const duplicate=withCatalog(seed);duplicate.nodes[0].children=[duplicate.nodes[1]];assert.throws(()=>validateDoc(duplicate));
 const deep=structuredClone(seed);let n=deep.nodes[0];for(let i=0;i<6;i++){n.children=[{...structuredClone(seed.nodes[0]),id:'deep'+i}];n=n.children[0];}assert.throws(()=>validateDoc(deep),/层级/);
});
test('catalog version labels cannot collide with an existing member version',async()=>{
 const {ensureHierarchy}=await import('../lib/repository');const db=database();await initialize(db);await freezeFlow(db,1,'v1.3 · 统一可视化层','member version','editor');await ensureHierarchy(db);await ensureHierarchy(db);assert.equal((await readFlow(db)as any).revision,2);assert.equal((await readFlow(db,{version:'visualization-v13'})as any).version.label,'v1.3 · 统一可视化层 · r2');
});

test('static release files are valid and content hashes match; public publishing cannot save drafts',async()=>{
 const {staticResponse}=await import('../lib/static-reader');const {readFileSync}=await import('node:fs');const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));
 for(const release of pub.releases){validateDoc(release.doc);assert.equal(release.hash,await digest(release.doc));}
 const g=globalThis as any;g.window={__FLOW_PUBLICATION__:pub};
 try{
  assert.equal((staticResponse('/api/session') as any).canEdit,false);
  assert.equal((staticResponse('/api/flow') as any).version.id,'visualization-v13');
  assert.equal((staticResponse('/api/flow?version=baseline-v1') as any).doc.nodes.length,14);
  assert.throws(()=>staticResponse('/api/flow',{method:'POST'}),/发布版/);
  assert.throws(()=>staticResponse('/api/flow?version=missing'),/尚未发布/);
 }finally{delete g.window;}
});


test('Gnosis migration preserves the published v1.1 snapshot and member edits',async()=>{
 const {flattenNodes,updateNode}=await import('../lib/flow');const {ensureHierarchy}=await import('../lib/repository');
 const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));const old=pub.releases.find((r:any)=>r.id==='hierarchy-v11');
 const db=database();await initialize(db);await saveFlow(db,1,old.doc,'existing catalog','editor');const fixed=await freezeFlow(db,2,'v1.1 · 模块层级','','editor');
 const edited={...old.doc,nodes:updateNode(old.doc.nodes,'f_prep_nonspatial',{title:'成员的PREP说明'})};await saveFlow(db,2,edited,'member edit','editor');
 await ensureHierarchy(db);const next:any=await readFlow(db);const nodes=flattenNodes(next.doc.nodes);const leaves=nodes.filter(n=>n.id.startsWith('f_gnosis_'));
 assert.equal(leaves.length,8);assert.equal(nodes.find(n=>n.id==='f_prep_nonspatial')?.title,'成员的PREP说明');
 assert.equal((await readFlow(db,{version:fixed.id}) as any).hash,old.hash);
 for(const n of leaves){assert.match(JSON.stringify(n),/https:\/\/github.com\/Gnosis-Neurodynamics\/GnosisNeuroDynamicSE/);assert.deepEqual(n.scope,['eeg']);}
 assert.equal(nodes.filter(n=>n.id.startsWith('group_gnosis_')).length,3);
});


test('visualizations have one separate hierarchy and do not count as QC algorithms',async()=>{
 const {withCatalog}=await import('../lib/catalog');const {flattenNodes}=await import('../lib/flow');
 const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));const old=pub.releases.find((r:any)=>r.id==='gnosis-v12');
 const before=JSON.stringify(old);const doc=withCatalog(old.doc);const root=doc.nodes.find(n=>n.id==='VIS')!;
 assert.equal(root.children?.length,12);assert.equal(root.children?.filter(n=>n.status==='ready').length,10);
 assert.equal(flattenNodes(doc.nodes).filter(n=>n.entryType==='visualization').length,12);
 assert.equal(flattenNodes(doc.nodes).filter(n=>n.entryType==='method'&&n.status==='ready').length,47);
 assert.ok(doc.edges.some(e=>e.source==='M09'&&e.target==='VIS'));
 assert.deepEqual(withCatalog(doc),doc);assert.equal(JSON.stringify(old),before);
});
