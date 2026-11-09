'use client';
import {useEffect,useState} from 'react';
import navigation from '../config/navigation.json';
import {acceptEditorLink,forgetEditor} from '../lib/collaboration-client';
import {apiUrl} from '../lib/public-client';
import {editorHeaders} from '../lib/collaboration-client';
type Member={id:string;label:string;role:string;created_at:string;revoked_at:string|null};
async function access(path='',body?:unknown){const r=await fetch(apiUrl('/api/access'+path),{method:body?'POST':'GET',headers:{...editorHeaders(),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,cache:'no-store'});const d=await r.json() as {error?:string;links:Member[];token:string};if(!r.ok)throw new Error(d.error||'暂时未能完成');return d;}
export default function AccessPanel({canManage,canEdit,refresh}:{canManage:boolean;canEdit:boolean;refresh:()=>Promise<void>}){
 const [members,setMembers]=useState<Member[]>([]),[name,setName]=useState(''),[newLink,setNewLink]=useState(''),[input,setInput]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[copied,setCopied]=useState(false);
 async function load(){try{setMembers((await access('?members=1')).links);}catch(e){setError((e as Error).message);}}
 useEffect(()=>{if(canManage)void load();},[canManage]);
 async function create(){setBusy(true);setError('');try{const result=await access('',{action:'create',label:name.trim()});setNewLink(navigation.flowUrl+'#edit='+result.token);setName('');setCopied(false);await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 async function revoke(id:string){if(!confirm('停用后，此链接将不能继续编辑。已有讨论与版本会保留。'))return;setBusy(true);try{await access('',{action:'revoke',id});setNewLink('');await load();}catch(e){setError((e as Error).message);}finally{setBusy(false);}}
 return <div className="access-panel">{error&&<p role="alert" className="modal-error">{error}</p>}
  {canManage?<><p>按成员生成编辑链接，不需要注册账号。收到链接的人可以修改草稿、批注和固定版本。</p><form onSubmit={e=>{e.preventDefault();void create();}}><label>成员称呼<input autoFocus value={name} maxLength={60} placeholder="用于批注署名，例如：王老师" onChange={e=>setName(e.target.value)}/></label><button className="primary" disabled={busy||!name.trim()}>生成编辑链接</button></form>{newLink&&<section className="private-link"><label>仅发送给对应成员<input readOnly value={newLink} onFocus={e=>e.target.select()}/></label><button onClick={()=>void navigator.clipboard.writeText(newLink).then(()=>setCopied(true)).catch(()=>setError('请选中上面的链接复制'))}>{copied?'已复制':'复制编辑链接'}</button><small>链接仅在本次生成时显示，请勿放在公开页面。</small></section>}<h3>编辑成员</h3>{members.map(m=><div className="member-row" key={m.id}><span><strong>{m.label}</strong><small>{m.role==='owner'?'维护者':m.revoked_at?'已停用':'可编辑'}</small></span>{m.role!=='owner'&&!m.revoked_at&&<button disabled={busy} onClick={()=>void revoke(m.id)}>停用</button>}</div>)}</>:!canEdit?<><p>公开链接用于查看。维护者向指定成员发送编辑链接，打开后即可在同一页面参与，不需要登录。</p><form onSubmit={e=>{e.preventDefault();setError('');try{acceptEditorLink(input,navigation.flowUrl);setInput('');void refresh().catch(e=>setError(e.message));}catch(e){setError((e as Error).message);}}}><label>已有成员编辑链接<input type="password" autoComplete="off" value={input} onChange={e=>setInput(e.target.value)} placeholder="粘贴维护者提供的链接"/></label><button className="primary" disabled={!input.trim()}>开始协作</button></form></>:<p>当前可直接编辑草稿、添加批注、保存和固定版本。</p>}
  {canEdit&&<button className="text-button leave-edit" onClick={()=>{forgetEditor();void refresh();}}>退出本次编辑</button>}
 </div>;
}
