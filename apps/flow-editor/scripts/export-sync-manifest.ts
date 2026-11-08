import {readFileSync,writeFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import catalog from '../content/module-catalog.json';
import {withCatalog} from '../lib/catalog';
import {seed} from '../lib/seed';
import {catalogHash,validateManifest} from '../lib/sync';
const doc=withCatalog(seed),sourceVersion=catalog.catalogVersion;
const id='catalog-'+await catalogHash(doc,sourceVersion);
let old;try{old=await validateManifest(JSON.parse(readFileSync('content/sync-manifest.json','utf8')));}catch{}
const sourceCommit=process.env.GITHUB_SHA||'local';
const manifest=old?.id===id&&(old.sourceCommit!=='local'||sourceCommit==='local')?old:{schemaVersion:1,id,sequence:(old?.sequence||0)+1,sourceVersion,sourceCommit,doc};
await validateManifest(manifest);
writeFileSync('content/sync-manifest.json',JSON.stringify(manifest,null,2)+'\n');
console.log(`Catalog ${manifest.sequence}: ${sourceVersion}, ${doc.nodes.length} root modules`);
