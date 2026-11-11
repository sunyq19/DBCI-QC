'use client';
import {useState} from 'react';
import type {Version} from '../lib/flow-loading';

export default function DeleteVersionPanel({version,submit,cancel}:{version:Version;submit:(password:string)=>Promise<void>;cancel:()=>void}){
 const [password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 async function remove(){
  if(busy||!password)return;
  setBusy(true);setError('');const entered=password;setPassword('');
  try{await submit(entered);}catch(e){setError(e instanceof Error?e.message:'未能删除，请重试。');}finally{setBusy(false);}
 }
 return <form onSubmit={e=>{e.preventDefault();void remove();}}>
  <p>删除版本 <strong>“{version.label}”</strong>？该版本链接将失效。</p>
  <p className="subtle">当前草稿、修改历史和其他版本保留。</p>
  <label>再次输入编辑密码<input autoFocus type="password" autoComplete="off" maxLength={256} required value={password} disabled={busy} onChange={e=>setPassword(e.target.value)}/></label>
  {error&&<p className="modal-error" role="alert">{error}</p>}
  <div className="modal-actions"><button type="button" disabled={busy} onClick={cancel}>取消</button><button className="danger-primary" disabled={busy||!password}>{busy?'正在删除…':'删除版本'}</button></div>
 </form>;
}
