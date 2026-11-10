import {DatabaseSync} from 'node:sqlite';
import {mkdirSync,readFileSync,readdirSync,existsSync} from 'node:fs';
import {readFile,writeFile,rename,unlink} from 'node:fs/promises';
import path from 'node:path';

// Preserve the existing route/repository contracts on a single-host deployment.
export function openDatabase(file,migrations){
 mkdirSync(path.dirname(file),{recursive:true,mode:0o700});
 const sql=new DatabaseSync(file);
 sql.exec('PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; PRAGMA busy_timeout=5000; CREATE TABLE IF NOT EXISTS self_host_migrations (name TEXT PRIMARY KEY)');
 for(const name of readdirSync(migrations).filter(n=>n.endsWith('.sql')).sort()){
  if(sql.prepare('SELECT name FROM self_host_migrations WHERE name=?').get(name))continue;
  sql.exec('BEGIN IMMEDIATE');
  try{sql.exec(readFileSync(path.join(migrations,name),'utf8'));sql.prepare('INSERT INTO self_host_migrations VALUES (?)').run(name);sql.exec('COMMIT');}catch(e){sql.exec('ROLLBACK');throw e;}
 }
 function prepare(query,args=[]){
  const statement=()=>sql.prepare(query);
  return {bind(...values){return prepare(query,values)},
   first:async(column)=>{const row=statement().get(...args);return row?(column?row[column]:row):null},
   all:async()=>({results:statement().all(...args),success:true}),
   run:async()=>({meta:statement().run(...args),success:true}),
   execute(){const s=statement();return s.columns().length?{results:s.all(...args),success:true}:{meta:s.run(...args),success:true}}};
 }
 return {prepare,async batch(statements){sql.exec('BEGIN IMMEDIATE');try{const results=statements.map(s=>s.execute());sql.exec('COMMIT');return results;}catch(e){sql.exec('ROLLBACK');throw e;}},close(){sql.close()},sql};
}
export function diskBucket(root){
 mkdirSync(root,{recursive:true,mode:0o700});
 function filename(key){if(!/^module-files\/[a-f0-9-]{36}$/.test(key))throw new Error('Invalid attachment key');return path.join(root,key.split('/')[1]);}
 return {async put(key,value){const p=filename(key),tmp=p+'.'+crypto.randomUUID()+'.tmp';await writeFile(tmp,Buffer.from(value),{mode:0o600});await rename(tmp,p);},async get(key){const p=filename(key);if(!existsSync(p))return null;return{body:await readFile(p)};},async delete(key){try{await unlink(filename(key))}catch(e){if(e.code!=='ENOENT')throw e;}}};
}
