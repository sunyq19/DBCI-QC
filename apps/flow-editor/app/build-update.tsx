'use client';
import {useEffect,useState} from 'react';

export default function BuildUpdate({dirty}:{dirty:boolean}){
 const [latest,setLatest]=useState('');
 useEffect(()=>{
  const current=document.querySelector<HTMLMetaElement>('meta[name="flow-build"]')?.content;
  if(!current)return;
  const controller=new AbortController();let checking=false;
  async function check(){
   if(checking||document.hidden)return;
   checking=true;
   try{
    const url=new URL('build.json',location.href);url.searchParams.set('check',String(Date.now()));
    const response=await fetch(url,{cache:'no-store',signal:controller.signal});
    if(response.ok){const value=await response.json();if(value&&typeof value==='object'&&'build'in value&&typeof value.build==='string'&&value.build!==current)setLatest(value.build);}
   }catch{}finally{checking=false;}
  }
  void check();window.addEventListener('focus',check);
  const timer=setInterval(check,60000);
  return()=>{controller.abort();clearInterval(timer);window.removeEventListener('focus',check);};
 },[]);
 if(!latest)return null;
 return <div className="notice build-update" role="status"><span>{dirty?'页面已更新，请先保存修改再刷新。':'页面已更新，可刷新使用。'}</span><button disabled={dirty} onClick={()=>{const url=new URL(location.href);url.searchParams.set('ui',latest);location.replace(url.href);}}>刷新页面</button></div>;
}
