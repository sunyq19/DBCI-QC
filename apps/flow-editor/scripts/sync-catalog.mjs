import {execFileSync} from 'node:child_process';
import {build} from 'esbuild';
import {mkdir} from 'node:fs/promises';
execFileSync(process.env.PYTHON||'python3',['scripts/import-qc-catalog.py','../..'],{stdio:'inherit'});
await mkdir('outputs',{recursive:true});
await build({entryPoints:['scripts/export-sync-manifest.ts'],bundle:true,platform:'node',format:'esm',outfile:'outputs/export-sync.mjs'});
execFileSync(process.execPath,['outputs/export-sync.mjs'],{stdio:'inherit'});
