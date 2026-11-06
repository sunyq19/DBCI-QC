import {execFileSync} from 'node:child_process';
import {mkdtemp, readdir, rm, cp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const app = fileURLToPath(new URL('..', import.meta.url));
const git = (args, cwd = app) => execFileSync('git', args, {cwd, encoding:'utf8'}).trim();
const root = git(['rev-parse', '--show-toplevel']);
if (git(['status', '--porcelain', '--', 'apps/flow-editor'], root)) {
  throw new Error('Commit the flow-editor source before publishing.');
}
const commit = git(['rev-parse', 'HEAD']);
const remote = git(['remote', 'get-url', 'origin']);
const name = git(['config', 'user.name']);
const email = git(['config', 'user.email']);
execFileSync(process.execPath, ['scripts/build-pages.mjs'], {
  cwd:app, stdio:'inherit', env:{...process.env, GITHUB_SHA:commit},
});
const staging = await mkdtemp(join(tmpdir(), 'dbci-flow-pages-'));
try {
  git(['init', '--initial-branch=gh-pages'], staging);
  git(['config', 'user.name', name], staging);
  git(['config', 'user.email', email], staging);
  git(['remote', 'add', 'origin', remote], staging);
  if (git(['ls-remote', '--heads', 'origin', 'gh-pages'], staging)) {
    git(['fetch', '--depth=1', 'origin', 'gh-pages'], staging);
    git(['reset', '--hard', 'FETCH_HEAD'], staging);
  }
  for (const item of await readdir(staging)) {
    if (item !== '.git') await rm(join(staging,item), {recursive:true, force:true});
  }
  await cp(resolve(app, 'dist-pages'), staging, {recursive:true});
  git(['add', '--all'], staging);
  if (!git(['diff', '--cached', '--name-only'], staging)) {
    console.log('Published files already match this source commit.');
  } else {
    git(['commit', '-m', `Publish QC flow from ${commit}`], staging);
    execFileSync('git', ['push', 'origin', 'HEAD:gh-pages'], {cwd:staging, stdio:'inherit'});
    console.log('Published branch updated: https://sunyq19.github.io/DBCI-QC/');
  }
} finally {
  await rm(staging, {recursive:true, force:true});
}
