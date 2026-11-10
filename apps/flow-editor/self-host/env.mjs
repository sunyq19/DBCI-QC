import {readFileSync} from 'node:fs';
import path from 'node:path';
import {openDatabase,diskBucket} from './storage.mjs';
const root=process.env.FLOW_DATA_DIR;
if(!root)throw new Error('FLOW_DATA_DIR must point to persistent storage');
const secret=process.env.FLOW_PASSWORD_FILE;
export const env={DB:openDatabase(path.join(root,'flow.sqlite'),path.resolve('drizzle')),BUCKET:diskBucket(path.join(root,'attachments')),FLOW_EDIT_PASSWORD_VERIFIER:secret?readFileSync(secret,'utf8').trim():undefined};
