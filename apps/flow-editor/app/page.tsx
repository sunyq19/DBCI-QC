import {redirect} from 'next/navigation';
import navigation from '../config/navigation.json';
import {publicQuery} from '../lib/handoff';
export default async function Page({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}){
 const values=await searchParams;const query=new URLSearchParams();
 for(const key of ['version','revision'])if(typeof values?.[key]==='string')query.set(key,values[key] as string);
 const target=new URL(navigation.flowUrl);target.search=publicQuery(query.toString());
 redirect(target.href);
}
