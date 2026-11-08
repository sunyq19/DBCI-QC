import {validateDoc,type FlowDoc} from './flow';
type Release={id:string;label:string;revision:number;note:string;created_at:string;doc:FlowDoc;hash:string};
export type Publication={releases:Release[];editorUrl:string;repositoryUrl:string;sourceCommit?:string};
declare global {interface Window {__FLOW_PUBLICATION__?:Publication}}
export const publication=()=>typeof window==='undefined'?undefined:window.__FLOW_PUBLICATION__;
export function staticResponse(url:string,options?:RequestInit):unknown{
 const p=publication();if(!p)throw new Error('No static publication');
 if(options?.method&&options.method!=='GET')throw new Error('此处为发布版，请从“协作编辑”进入共同草稿。');
 if(url==='/api/session')return{signedIn:false,canEdit:false,email:null};
 const query=new URL(url,'https://local.invalid').searchParams;
 const latest=p.releases[p.releases.length-1];
 if(query.has('head'))return{latestRevision:latest.revision};
 if(query.has('history'))return{latestRevision:latest.revision,revisions:[...p.releases].reverse().map(r=>({revision:r.revision,hash:r.hash,note:r.note,created_at:r.created_at}))};
 const id=query.get('version'),rev=query.get('revision');
 const r=id?p.releases.find(v=>v.id===id):rev?p.releases.find(v=>v.revision===Number(rev)):latest;
 if(!r)throw new Error('此版本尚未发布到 GitHub，请查看已发布版本或进入协作页。');
 const version={id:r.id,label:r.label,revision:r.revision,note:r.note,created_at:r.created_at};
 return{doc:r.doc,revision:r.revision,hash:r.hash,note:r.note,createdAt:r.created_at,version,latestRevision:latest.revision,versions:[...p.releases].reverse().map(({doc,hash,...v})=>v),view:'version'};
}

// The public viewer reads the same draft and fixed versions as the shared editor.
// On network failure it clearly falls back to the bundled immutable release.
export async function sharedResponse(url:string,options?:RequestInit):Promise<unknown>{
 const p=publication();if(!p)throw new Error('No publication');
 if(url==='/api/session'||options?.method&&options.method!=='GET')return staticResponse(url,options);
 try{
  const r=await fetch(new URL(url,p.editorUrl),{credentials:'omit',cache:'no-store',signal:AbortSignal.timeout(6000)});
  if(!r.ok)throw new Error('Shared reader unavailable');
  const value=await r.json() as Record<string,unknown>;if(value.doc)validateDoc(value.doc);return value;
 }catch{
  const value=staticResponse(url,options) as Record<string,unknown>;
  return {...value,offline:true};
 }
}
