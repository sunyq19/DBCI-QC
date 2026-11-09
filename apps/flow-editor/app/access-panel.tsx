'use client';
import {useState} from 'react';
import {forgetEditor,saveEditorSession,editorHeaders} from '../lib/collaboration-client';
import {apiUrl} from '../lib/public-client';
export default function AccessPanel({canEdit,refresh,close}:{canEdit:boolean;refresh:()=>Promise<void>;close:()=>void}){
 const [password,setPassword]=useState(''),[name,setName]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function submit(lock=false){setBusy(true);setError('');try{
  const r=await fetch(apiUrl('/api/access'),{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json',...(lock?editorHeaders():{})},body:JSON.stringify(lock?{action:'lock'}:{action:'unlock',password,label:name})});const data=await r.json() as {error?:string;token:string};
  if(!r.ok)throw new Error(data.error||'暂时未能完成');
  setPassword('');if(lock)forgetEditor();else saveEditorSession(data.token);await refresh();close();
 }catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <div className="access-panel">{error&&<p role="alert" className="modal-error">{error}</p>}{canEdit?<><p>当前可修改方案、添加批注和保存版本。</p><button disabled={busy} onClick={()=>void submit(true)}>结束编辑</button></>:<form onSubmit={e=>{e.preventDefault();void submit();}}><label>编辑密码<input autoFocus type="password" autoComplete="current-password" value={password} maxLength={256} onChange={e=>setPassword(e.target.value)} placeholder="输入密码即可编辑"/></label><label className="signature-field">署名（可选）<input autoComplete="nickname" value={name} maxLength={40} onChange={e=>setName(e.target.value)} placeholder="用于批注，例如：王老师"/></label><button className="primary" disabled={busy||!password}>{busy?'正在验证…':'开始编辑'}</button></form>}</div>;
}
