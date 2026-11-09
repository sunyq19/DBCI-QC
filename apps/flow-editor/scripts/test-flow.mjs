import {build} from 'esbuild';
import {mkdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
await mkdir('outputs',{recursive:true});
const files=['flow','handoff','collaboration','canvas'];
for(const name of files)await build({entryPoints:[`tests/${name}.test.ts`],outfile:`outputs/${name}-test.mjs`,platform:'node',format:'esm',bundle:true,alias:{'cloudflare:workers':'./tests/helpers/identity.ts','next/headers':'./tests/helpers/identity.ts','next/navigation':'./tests/helpers/identity.ts'}});
const run=spawnSync(process.execPath,['--test',...files.map(n=>`outputs/${n}-test.mjs`)],{stdio:'inherit'});process.exit(run.status??1);
