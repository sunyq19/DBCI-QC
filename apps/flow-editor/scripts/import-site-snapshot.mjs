import {readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {openDatabase} from '../self-host/storage.mjs';
const [source,target]=process.argv.slice(2);if(!source||!target)throw new Error('Usage: import-site-snapshot.mjs export-directory database-file');
if(existsSync(target))throw new Error('Refusing to overwrite an existing database');
const read=name=>JSON.parse(readFileSync(path.join(source,name),'utf8'));
const history=read('history.json'),metadata=read('revisions-meta.json'),versions=read('versions.json');
const records=history.revisions.map(row=>{
 const snapshot=read(`revision-${row.revision}.json`),document=JSON.stringify(snapshot.doc),hash=createHash('sha256').update(document).digest('hex');
 const meta=metadata.find(m=>m.revision===row.revision);
 if(!meta||hash!==row.hash||hash!==snapshot.hash||hash!==meta.hash)throw new Error(`Revision ${row.revision}: hash mismatch`);
 return {...meta,document};
});
if(Math.max(...records.map(r=>r.revision))!==history.latestRevision)throw new Error('Incomplete revision history');
const db=openDatabase(target,'drizzle');db.sql.exec('BEGIN IMMEDIATE');
try{
 for(const r of records)db.sql.prepare('INSERT INTO flow_revisions (revision,document,hash,author_id,note,created_at,based_on_revision) VALUES (?,?,?,?,?,?,?)').run(r.revision,r.document,r.hash,r.author_id,r.note,r.created_at,r.based_on_revision??null);
 for(const v of versions)db.sql.prepare('INSERT INTO flow_versions (id,label,revision,note,author_id,created_at) VALUES (?,?,?,?,?,?)').run(v.id,v.label,v.revision,v.note,v.author_id,v.created_at);
 db.sql.exec('COMMIT');db.sql.exec('PRAGMA wal_checkpoint(TRUNCATE)');
}catch(e){db.sql.exec('ROLLBACK');throw e;}finally{db.close();}
console.log(`Imported ${records.length} verified revisions and ${versions.length} fixed versions`);
