import test from 'node:test';
import {CATALOG_ID,CATALOG_LABEL,withCatalog} from '../lib/catalog';
import {flattenNodes} from '../lib/flow';
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
 assert.equal(all.filter(n=>n.entryType==='method'&&n.status!=='planned').length,49);
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
 assert.equal((await readFlow(db,{version:CATALOG_ID})as any).hash,current.hash);
 await saveFlow(db,3,{...current.doc,nodes:edited},'继续维护子方法','editor');await ensureHierarchy(db);
 assert.equal((await readFlow(db)as any).revision,4);assert.equal((await readFlow(db,{version:CATALOG_ID})as any).revision,3);
});
test('malformed and excessively deep children cannot enter shared storage',async()=>{
 const {withCatalog}=await import('../lib/catalog');
 const duplicate=withCatalog(seed);duplicate.nodes[0].children=[duplicate.nodes[1]];assert.throws(()=>validateDoc(duplicate));
 const deep=structuredClone(seed);let n=deep.nodes[0];for(let i=0;i<6;i++){n.children=[{...structuredClone(seed.nodes[0]),id:'deep'+i}];n=n.children[0];}assert.throws(()=>validateDoc(deep),/层级/);
});
test('catalog version labels cannot collide with an existing member version',async()=>{
 const {ensureHierarchy}=await import('../lib/repository');const db=database();await initialize(db);await freezeFlow(db,1,CATALOG_LABEL,'member version','editor');await ensureHierarchy(db);await ensureHierarchy(db);assert.equal((await readFlow(db)as any).revision,2);assert.equal((await readFlow(db,{version:CATALOG_ID})as any).version.label,CATALOG_LABEL+' · r2');
});

test('static release files are valid and content hashes match; public publishing cannot save drafts',async()=>{
 const {staticResponse}=await import('../lib/static-reader');const {readFileSync}=await import('node:fs');const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));
 for(const release of pub.releases){validateDoc(release.doc);assert.equal(release.hash,await digest(release.doc));}
 const g=globalThis as any;g.window={__FLOW_PUBLICATION__:pub};
 try{
  assert.equal((staticResponse('/api/session') as any).canEdit,false);
  assert.equal((staticResponse('/api/flow') as any).version.id,CATALOG_ID);
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
 assert.equal(flattenNodes(doc.nodes).filter(n=>n.entryType==='method'&&n.status==='ready').length,49);
 assert.ok(doc.edges.some(e=>e.source==='M09'&&e.target==='VIS'));
 assert.deepEqual(withCatalog(doc),doc);assert.equal(JSON.stringify(old),before);
});

test('D04 expands into four implemented supports without changing earlier fixed releases',async()=>{
 const {withCatalog}=await import('../lib/catalog');
 const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));
 const before=pub.releases.find((r:any)=>r.id==='workflow-v14');
 const doc=withCatalog(before.doc),root=doc.nodes.find(n=>n.id==='D04')!;
 assert.equal(root.children?.length,4);assert.ok(root.children?.every(n=>n.entryType==='support'&&n.status==='ready'));
 assert.match(root.notes,/3项消除/);assert.match(root.notes,/无医院验收/);
 assert.equal(before.hash,await digest(before.doc));assert.ok(!before.doc.nodes.some((n:any)=>n.id==='D04'));
 assert.ok(doc.edges.some(e=>e.source==='D03'&&e.target==='D04'));
 assert.deepEqual(withCatalog(doc),doc);
});

test('all current submodules have per-modality roles, including different defaults for the same method',()=>{
 const nodes=flattenNodes(withCatalog(seed).nodes);
 for(const n of nodes){assert.deepEqual(n.scoring?.map(s=>s.scope),n.scope,n.id);for(const s of n.scoring!){assert.equal(s.canOutputScore,['default','optional'].includes(s.role));if(n.status==='planned')assert.equal(s.role,'unavailable');}}
 const get=(id:string,scope:string)=>nodes.find(n=>n.id===id)!.scoring!.find(s=>s.scope===scope)!;
 assert.equal(get('f_mne_amplitude','eeg').role,'optional');assert.equal(get('f_mne_amplitude','ecog').role,'default');assert.equal(get('f_mne_amplitude','seeg').role,'default');
 assert.equal(get('f_gnosis_psd_deviation','eeg').role,'optional');assert.equal(get('f_gnosis_band_power','eeg').role,'measurement');
 assert.equal(get('f_spikeinterface_bad_channels','np').role,'default');assert.match(get('f_spikeinterface_bad_channels','np').rule,/不用于LF/);
 assert.equal(get('f_aggregate','eeg').role,'measurement');assert.equal(get('f_aggregate','np').role,'default');
 assert.match(get('f_neuropixels_continuity','np').weight,/30%.*70%/);
 assert.match(get('f_fieldtrip_zvalue','seeg').weight,/不再单独加权/);
 assert.match(get('score_weight','eeg').limited,/有效得分为0仍参与/);
 assert.match(get('score_eeg','eeg').limited,/未做所有EEG方法之间的统一去重/);
});

test('scoring migration updates stale defaults, retains member edits, and never rewrites frozen v1.5',async()=>{
 const pub=JSON.parse(readFileSync('content/releases/publication.json','utf8'));
 const old=structuredClone(pub.releases.find((r:any)=>r.id==='review-v15'));
 const before=JSON.stringify(old);const edited=structuredClone(old.doc);
 edited.nodes.find((n:any)=>n.id==='M05').description='团队修改的说明';
 const doc=withCatalog(edited);
 assert.equal(doc.nodes.find(n=>n.id==='M05')?.description,'团队修改的说明');
 assert.equal(doc.nodes.find(n=>n.id==='M08')?.status,'trial');assert.doesNotMatch(doc.nodes.find(n=>n.id==='M08')!.notes,/23.37/);
 const mne=flattenNodes(doc.nodes).find(n=>n.id==='f_mne_amplitude')!;mne.scoring![0].weight='团队建议：先验证';
 assert.equal(flattenNodes(withCatalog(doc).nodes).find(n=>n.id==='f_mne_amplitude')!.scoring![0].weight,'团队建议：先验证');
 assert.equal(JSON.stringify(old),before);assert.equal(old.hash,await digest(old.doc));assert.deepEqual(withCatalog(doc),doc);
});

test('score contracts reject invalid roles, ambiguous modalities and false capabilities',()=>{
 for(const mutate of [(s:any)=>s.role='invalid',(s:any)=>s.scope='dataset',(s:any)=>s.canOutputScore=false,(s:any)=>s.weight='a'.repeat(1801)]){
  const doc=withCatalog(seed);const s=flattenNodes(doc.nodes).find(n=>n.id==='f_continuity')!.scoring![0];mutate(s);assert.throws(()=>validateDoc(doc));
 }
 const doc=withCatalog(seed);const n=flattenNodes(doc.nodes).find(n=>n.id==='f_continuity')!;n.scoring!.push(n.scoring![0]);assert.throws(()=>validateDoc(doc));
});

import {catalogHash,mergeCatalog,validateManifest,type CatalogManifest} from '../lib/sync';
import {syncCatalog,checkSourceFields} from '../lib/repository';
const sourceManifest=JSON.parse(readFileSync('content/sync-manifest.json','utf8')) as CatalogManifest;
async function revised(change:(doc:any)=>void){const next=structuredClone(sourceManifest);next.sequence++;change(next.doc);next.id='catalog-'+await catalogHash(next.doc,next.sourceVersion);return await validateManifest(next);}
test('generated source is validated; digest changes cannot be concealed',async()=>{
 await validateManifest(sourceManifest);
 const bad=structuredClone(sourceManifest);bad.doc.nodes[0].description+='changed';await assert.rejects(()=>validateManifest(bad),/校验/);
});
test('source upgrades add and move methods, update rules, preserve team annotations, and retire removed nodes',async()=>{
 const first=mergeCatalog(withCatalog(seed),sourceManifest);
 const n=flattenNodes(first.nodes).find(n=>n.id==='f_continuity')!;n.teamNotes='团队说明：补充测试依据';n.x=80;
 const modified=await revised(doc=>{
  const original=flattenNodes(doc.nodes).find(n=>n.id==='f_continuity')!;
  original.scoring![0].weight='新规则：50%';original.description='新的实现说明';
  const parent=doc.nodes.find((n:any)=>n.children?.some((c:any)=>c.id===original.id));parent.children=parent.children.filter((c:any)=>c.id!==original.id);
  doc.nodes.find((n:any)=>n.id==='M04').children.push(original,{...structuredClone(original),id:'f_added',title:'新方法'});
  doc.nodes.find((n:any)=>n.id==='M06').children=doc.nodes.find((n:any)=>n.id==='M06').children.filter((c:any)=>c.id!=='f_hf_burst');
 });
 const second=mergeCatalog(first,modified),nodes=flattenNodes(second.nodes),updated=nodes.find(n=>n.id==='f_continuity')!;
 assert.equal(updated.teamNotes,'团队说明：补充测试依据');assert.equal(updated.scoring![0].weight,'新规则：50%');assert.equal(updated.description,'新的实现说明');assert.equal(updated.x,80);
 assert.equal(nodes.filter(n=>n.id==='f_continuity').length,1);assert.ok(nodes.find(n=>n.id==='f_added'));
 assert.equal(nodes.find(n=>n.id==='f_hf_burst')?.status,'planned');assert.ok(nodes.find(n=>n.id==='f_hf_burst')?.scoring?.every(s=>s.role==='unavailable'));
 assert.deepEqual(mergeCatalog(second,modified),second);assert.deepEqual(mergeCatalog(second,sourceManifest),second);
});
test('legacy member descriptions and score proposals move into notes, not the active rules',()=>{
 const doc=withCatalog(seed);const n=flattenNodes(doc.nodes).find(n=>n.id==='f_mne_amplitude')!;
 n.description='成员写的说明';n.scoring![0].weight='团队建议改为80%';
 const migrated=flattenNodes(mergeCatalog(doc,sourceManifest).nodes).find(n=>n.id===n.id&&n.id==='f_mne_amplitude')!;
 assert.match(migrated.teamNotes!,/成员写的说明/);assert.match(migrated.teamNotes!,/团队建议改为80%/);assert.notEqual(migrated.scoring![0].weight,'团队建议改为80%');
});
test('two source updates preserve notes and frozen versions; concurrent edits are detected',async()=>{
 const db=database();await initialize(db);await ensureCatalog();
 async function ensureCatalog(){await syncCatalog(db,sourceManifest);}
 let state:any=await readFlow(db);const rev=state.revision;const first=state.hash;
 state.doc.nodes[0].teamNotes='团队确认记录';await saveFlow(db,rev,state.doc,'补充团队记录','editor');
 const fixed=await freezeFlow(db,rev+1,'同步前固定版','保留','editor');const frozen:any=await readFlow(db,{version:fixed.id});
 const next=await revised(doc=>doc.nodes[0].description='新版描述');await Promise.all([syncCatalog(db,next),syncCatalog(db,next)]);
 state=await readFlow(db);assert.equal(state.revision,rev+2);assert.equal(state.doc.nodes[0].teamNotes,'团队确认记录');assert.equal(state.doc.nodes[0].description,'新版描述');assert.notEqual(state.hash,first);
 assert.equal((await readFlow(db,{version:fixed.id}) as any).hash,frozen.hash);assert.deepEqual((await readFlow(db,{version:'baseline-v1'})as any).doc,seed);
 const conflicting=structuredClone(state.doc);conflicting.nodes[0].title='改写实现';assert.throws(()=>checkSourceFields(state.doc,conflicting),/质控台同步/);
 const noteOnly=structuredClone(state.doc);noteOnly.nodes[0].teamNotes+='，允许补充';checkSourceFields(state.doc,noteOnly);
 await assert.rejects(()=>saveFlow(db,rev+1,noteOnly,'旧页面保存','editor'),{status:409});
 await syncCatalog(db,sourceManifest);assert.equal((await readFlow(db)as any).hash,state.hash);
});
test('invalid remote metadata falls back to bundled source without breaking the page',async()=>{
 const {readCatalog}=await import('../lib/catalog-source');
 const value=await readCatalog(async()=>new Response('{"schemaVersion":999}',{status:200}) as any);
 assert.equal(value.id,sourceManifest.id);
});
