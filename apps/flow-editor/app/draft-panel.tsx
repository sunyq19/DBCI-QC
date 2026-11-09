'use client';
import {useRef,useState} from 'react';
import {Paperclip,FileText,ArrowUpRight,X,MessageSquare,Trash2} from 'lucide-react';
import {type FlowNode,type Attachment,nodeTitle,nodeBody,sketchFor} from '../lib/flow';
import {apiUrl} from '../lib/public-client';
import {editorHeaders} from '../lib/collaboration-client';
import {ScoringDetails} from './scoring';
import VisualExamples from './visual-examples';
export default function DraftPanel({node,writable,busy,patch,select,remove,discuss,connect,beginEditing}:{node:FlowNode;writable:boolean;busy:boolean;patch:(p:Partial<FlowNode>)=>void;select:(id:string)=>void;remove:()=>void;discuss:(v:{operation:string;body?:string;threadId?:string})=>Promise<boolean>;connect:()=>void;beginEditing:()=>void}){
 const [uploading,setUploading]=useState(false),[error,setError]=useState(''),[comment,setComment]=useState('');const picker=useRef<HTMLInputElement>(null),target=useRef(node.id);target.current=node.id;
 function edit(key:'title'|'body',value:string){patch({sketch:{...sketchFor(node),[key]:value}});}
 async function upload(files:FileList|null){if(!files?.length)return;if((node.attachments?.length||0)+files.length>10){setError('每个模块最多10个附件');return;}setUploading(true);setError('');const id=node.id,added:Attachment[]=[];
  try{for(const file of Array.from(files)){if(file.size>10485760)throw new Error('单个附件不能超过10 MB');const form=new FormData();form.append('file',file);const response=await fetch(apiUrl('/api/attachments'),{method:'POST',headers:editorHeaders(),body:form});const result=await response.json() as Attachment&{error?:string};if(!response.ok)throw new Error(result.error||'上传失败');added.push(result);}
  }catch(e){setError((e as Error).message);}finally{if(target.current===id&&added.length)patch({attachments:[...(node.attachments||[]),...added]});setUploading(false);if(picker.current)picker.current.value='';}}
 const attachments=node.attachments||[],threads=node.discussion||[];
 return <div className="draft-panel">
  <div className="draft-heading"><span>{node.id} · 模块草稿</span><button className="icon" onClick={connect} disabled={!writable||busy} title="连接到其他模块" aria-label="连接当前模块"><ArrowUpRight size={18}/></button></div>
  {writable?<><input className="draft-title" aria-label="模块标题" maxLength={64} value={node.sketch?.title??node.title} onChange={e=>edit('title',e.target.value)} placeholder="模块标题"/><VisualExamples node={node} select={select}/><textarea className="draft-body" aria-label="模块正文" maxLength={20000} value={nodeBody(node)} onChange={e=>edit('body',e.target.value)} placeholder="在这里写想法、步骤或待确认的问题…"/></>:<><h2>{nodeTitle(node)}</h2><VisualExamples node={node} select={select}/><div className="draft-read-text" onDoubleClick={beginEditing}>{nodeBody(node)||'暂无文字'}</div><button className="edit-here" onClick={beginEditing}>编辑这个模块</button></>}
  <div className="attachment-heading"><strong>附件 {attachments.length||''}</strong>{writable&&<button onClick={()=>picker.current?.click()} disabled={busy||uploading||attachments.length>=10}><Paperclip size={15}/>{uploading?'上传中…':'添加附件'}</button>}</div>
  <input ref={picker} type="file" multiple hidden accept=".png,.jpg,.jpeg,.webp,.pdf,.docx,.pptx,.xlsx,.md,.txt,.csv,.json,.zip" onChange={e=>void upload(e.target.files)}/>
  {!attachments.length&&<div className="attachment-empty">图片、文档或资料 · 每个10 MB</div>}
  {error&&<p className="modal-error" role="alert">{error}</p>}
  <div className="attachment-list">{attachments.map(f=><div className="attachment" key={f.id}>{f.mime.startsWith('image/')?<a href={apiUrl('/api/attachments?id='+f.id)} target="_blank" rel="noreferrer"><img src={apiUrl('/api/attachments?id='+f.id+'&preview=1')} alt={f.name} loading="lazy"/></a>:<FileText size={19}/>}<a href={apiUrl('/api/attachments?id='+f.id)} target="_blank" rel="noreferrer"><strong>{f.name}</strong><small>{(f.size/1024).toFixed(0)} KB</small></a>{writable&&<button className="icon" aria-label={'移除附件 '+f.name} disabled={uploading} onClick={()=>patch({attachments:attachments.filter(a=>a.id!==f.id)})}><X size={14}/></button>}</div>)}</div>
  {writable&&<p className="attachment-caption">保存后随本版本分享。</p>}
  <details className="draft-discussions"><summary><MessageSquare size={15}/>批注 {threads.length?`· ${threads.length}`:''}</summary>{writable&&<form onSubmit={async e=>{e.preventDefault();if(await discuss({operation:'comment',body:comment}))setComment('');}}><textarea aria-label="添加批注" rows={2} maxLength={4000} value={comment} onChange={e=>setComment(e.target.value)} placeholder="写一句建议…"/><button disabled={busy||!comment.trim()}>发送</button></form>}{!threads.length&&<p className="subtle">暂无批注</p>}{threads.slice().reverse().map(t=><div className="short-comment" key={t.id}><div><strong>{t.author}</strong><time>{new Date(t.createdAt).toLocaleDateString('zh-CN')}</time>{t.resolved&&<span>已处理</span>}</div><p>{t.body}</p>{t.replies.map(r=><p key={r.id}>{r.author}：{r.body}</p>)}{writable&&<button className="text-button" disabled={busy} onClick={()=>void discuss({operation:t.resolved?'reopen':'resolve',threadId:t.id})}>{t.resolved?'重新打开':'标记已处理'}</button>}</div>)}</details>
  <details className="draft-reference"><summary>参考说明</summary><p className="source-caption">质控台当前实现，供起草时参考</p><p>{node.description}</p>{[['conditions','使用条件'],['inputs','输入'],['outputs','输出'],['methods','方法来源'],['evidence','依据']].map(([key,title])=>node[key as keyof FlowNode]?<div key={key}><h3>{title}</h3><p>{String(node[key as keyof FlowNode])}</p></div>:null)}<ScoringDetails node={node} select={select}/>{node.teamNotes&&<p>{node.teamNotes}</p>}</details>
  {writable&&<button className="remove-module" onClick={remove}><Trash2 size={14}/>移出此稿</button>}
 </div>;
}
