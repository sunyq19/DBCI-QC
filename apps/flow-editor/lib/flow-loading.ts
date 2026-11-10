import {validateDoc,type FlowDoc} from './flow';

export type Version={id:string;label:string;revision:number;note:string;created_at:string};
export type Snapshot={doc:FlowDoc;revision:number;hash:string;note:string;createdAt:string;version:Version|null;latestRevision:number;versions:Version[];view:'draft'|'version'|'history'|'published'};

// A code-derived publication is never a collaborative revision. In particular,
// it must not silently replace a requested fixed version or be saved as head.
export function publishedSnapshot(manifest:{doc:unknown;id:string;sourceVersion:string}):Snapshot {
 return {doc:validateDoc(manifest.doc),revision:0,hash:manifest.id,note:manifest.sourceVersion,createdAt:'',version:null,latestRevision:0,versions:[],view:'published'};
}
export function initialSnapshot(published:Snapshot|undefined,search:string):Snapshot|null {
 const query=new URLSearchParams(search);
 return published&&!query.has('version')&&!query.has('revision')?published:null;
}
export function flowErrorMessage(error:unknown):string {
 if(error instanceof TypeError||(error as {name?:string})?.name==='AbortError'||(error as {name?:string})?.name==='TimeoutError')return '协作服务连接失败，请重试。模块发布版仍可查看。';
 return error instanceof Error?error.message:'暂时未能完成，请重试。';
}
export async function fetchFlowJson<T>(url:string,options:RequestInit={},fetcher:typeof fetch=fetch,timeout=10000):Promise<T> {
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeout);
 try {
  const response=await fetcher(url,{cache:'no-store',...options,signal:controller.signal});
  if(!response.headers.get('content-type')?.includes('application/json'))throw new Error('协作服务暂不可达，请稍后重试。');
  const value=await response.json() as T&{error?:string};
  if(!response.ok)throw Object.assign(new Error(value.error||'协作服务暂不可达，请稍后重试。'),{status:response.status});
  return value;
 }catch(error){
  if(error instanceof TypeError||controller.signal.aborted)throw new Error('协作服务连接失败，请重试。模块发布版仍可查看。');
  throw error;
 }finally{clearTimeout(timer);}
}
