import test from 'node:test';
import assert from 'node:assert/strict';
import manifest from '../content/sync-manifest.json';
import {publishedSnapshot,initialSnapshot,fetchFlowJson} from '../lib/flow-loading';
import {browserId} from '../lib/browser-id';
test('bundled view is read-only and never substitutes a fixed or historical version',()=>{
 const published=publishedSnapshot(manifest);assert.equal(published.view,'published');assert.equal(published.revision,0);
 assert.equal(initialSnapshot(published,''),published);assert.equal(initialSnapshot(published,'?version=baseline-v1'),null);assert.equal(initialSnapshot(published,'?revision=2'),null);
});
test('failed backend requests are readable; conflict status and successful data survive',async()=>{
 await assert.rejects(()=>fetchFlowJson('/api/flow',{},(async()=>{throw new TypeError('Failed to fetch')}) as typeof fetch),/协作服务连接失败/);
 await assert.rejects(()=>fetchFlowJson('/api/flow',{},(async()=>new Response('<html>proxy error</html>')) as typeof fetch),/暂不可达/);
 await assert.rejects(()=>fetchFlowJson('/api/flow',{},(async()=>Response.json({error:'草稿更新'},{status:409})) as typeof fetch),{status:409,message:'草稿更新'});
 assert.deepEqual(await fetchFlowJson('/api/flow',{},(async()=>Response.json({revision:14})) as typeof fetch),{revision:14});
});
test('browser IDs use getRandomValues on HTTP intranet pages',()=>{
 const ids=Array.from({length:100},()=>browserId());assert.equal(new Set(ids).size,100);for(const id of ids)assert.match(id,/^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/);
});
