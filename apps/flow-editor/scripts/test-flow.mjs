import {build} from 'esbuild';
import {mkdir} from 'node:fs/promises';
import {spawnSync} from 'node:child_process';
await mkdir('outputs',{recursive:true});
await build({entryPoints:['tests/flow.test.ts'],outfile:'outputs/flow-test.mjs',platform:'node',format:'esm',bundle:true});
const run=spawnSync(process.execPath,['--test','outputs/flow-test.mjs'],{stdio:'inherit'});process.exit(run.status??1);
