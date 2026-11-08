import bundled from '../content/sync-manifest.json';
import {validateManifest,type CatalogManifest} from './sync';
// Fixed first-party code channel only. Never read user-supplied URLs or subject data.
export const CATALOG_URL='https://raw.githubusercontent.com/sunyq19/DBCI-QC/main/apps/flow-editor/content/sync-manifest.json';
let cached:{until:number;manifest:CatalogManifest}|undefined;
let inFlight:Promise<CatalogManifest>|undefined;
export async function readCatalog(fetcher:typeof fetch=fetch):Promise<CatalogManifest>{
 if(cached&&cached.until>Date.now())return cached.manifest;
 if(inFlight)return inFlight;
 inFlight=(async()=>{
  const fallback=cached?.manifest||await validateManifest(bundled);
  let chosen=fallback;
  try{
   const r=await fetcher(CATALOG_URL+'?slot='+Math.floor(Date.now()/300000),{signal:AbortSignal.timeout(8000),redirect:'error',headers:{Accept:'application/json','Cache-Control':'no-cache'}});
   if(!r.ok)throw new Error('Catalog HTTP '+r.status);
   if(Number(r.headers.get('content-length'))>1500000)throw new Error('目录过大');
   const reader=r.body?.getReader();if(!reader)throw new Error('目录为空');
   const chunks:Uint8Array[]=[];let size=0;
   while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>1500000){await reader.cancel();throw new Error('目录过大');}chunks.push(value);}
   const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length;}
   const remote=await validateManifest(JSON.parse(new TextDecoder().decode(bytes)));
   if(remote.sequence>fallback.sequence||remote.sequence===fallback.sequence&&remote.id===fallback.id)chosen=remote;
  }catch(error){console.warn('Catalog sync retained the last verified version:',error instanceof Error?error.message:'read failed');}
  cached={until:Date.now()+300000,manifest:chosen};return chosen;
 })();
 try{return await inFlight;}finally{inFlight=undefined;}
}
