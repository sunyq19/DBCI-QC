'use client';
import {useState} from 'react';
import {MessageSquare,Check,Reply,Pencil,FileText} from 'lucide-react';
import {type FlowNode,type Proposal} from '../lib/flow';
import {ScoringDetails} from './scoring';
export const blankProposal=():Proposal=>({status:'draft',description:'',conditions:'',inputs:'',outputs:'',methods:'',scoring:'',decision:''});
const labels={draft:'起草中',discussing:'待讨论',agreed:'已形成意见'};
const fields:[keyof Omit<Proposal,'status'>,string,string][]=[['description','方案说明','希望解决什么问题，准备怎样调整'],['conditions','适用条件','哪些模态、数据条件下使用'],['methods','方法与参数','采用的方法、阈值或参考来源'],['scoring','计分建议','是否计分、权重与重复扣分的处理'],['inputs','输入','需要的数据和前置结果'],['outputs','输出','需要返回的测量、候选或图表'],['decision','讨论结论与待办','已确定的意见、尚需验证的问题']];
function Lines({value}:{value:string}){return <div className="collab-text">{value.split('\n').map((s,i)=><div key={i}>{/^https?:\/\/\S+$/.test(s)?<a href={s} target="_blank" rel="noreferrer">{s}</a>:s||'\u00a0'}</div>)}</div>;}
export default function CollaborationPanel({node,writable,frozen,busy,dirty,patch,select,discuss}:{node:FlowNode;writable:boolean;frozen:boolean;busy:boolean;dirty:boolean;patch:(p:Partial<FlowNode>)=>void;select:(id:string)=>void;discuss:(v:{operation:string;body?:string;threadId?:string})=>Promise<boolean>}){
 const [tab,setTab]=useState('proposal'),[body,setBody]=useState(''),[replyTo,setReplyTo]=useState(''),[reply,setReply]=useState(''),[showResolved,setShowResolved]=useState(false);
 const threads=node.discussion||[],open=threads.filter(t=>!t.resolved),proposal=node.proposal;
 function edit(key:keyof Proposal,value:string){patch({proposal:{...(proposal||blankProposal()),[key]:value}});}
 async function send(operation:string,threadId?:string){if(await discuss({operation,threadId,body:operation==='reply'?reply:body})){setBody('');setReply('');setReplyTo('');}}
 return <div className="collaboration-panel">
  <div className="collab-tabs" role="tablist" aria-label="模块协作内容">{[['proposal','方案草稿'],['discussion','批注讨论'],['implementation','当前实现']].map(([id,title])=><button key={id} id={'tab-'+id} role="tab" aria-selected={tab===id} aria-controls={'panel-'+id} onClick={()=>setTab(id)}>{title}{id==='discussion'&&open.length>0&&<span>{open.length}</span>}</button>)}</div>
  <div role="tabpanel" id={'panel-'+tab} aria-labelledby={'tab-'+tab} className="collab-panel-body">
   {tab==='proposal'&&<>
    {proposal||writable?<><div className="proposal-toolbar"><span>共同草稿</span>{writable?<select aria-label="方案讨论状态" value={proposal?.status||'draft'} onChange={e=>edit('status',e.target.value)}>{Object.entries(labels).map(([v,t])=><option key={v} value={v}>{t}</option>)}</select>:<span className="proposal-state">{labels[proposal!.status]}</span>}</div>
     {!proposal&&writable&&<div className="draft-start"><p>从当前实现开始，记录准备调整的内容。</p><button onClick={()=>patch({proposal:{...blankProposal(),description:node.description,conditions:node.conditions,inputs:node.inputs,outputs:node.outputs,methods:node.methods}})}><FileText size={15}/>复制当前说明</button></div>}
     <fieldset disabled={busy} className="proposal-fields">{fields.map(([key,title,placeholder],i)=>writable?<label key={key}>{title}<textarea aria-label={title} rows={i===0||key==='decision'?4:3} maxLength={6000} value={proposal?.[key]||''} placeholder={placeholder} onChange={e=>edit(key,e.target.value)}/></label>:proposal?.[key]?<section key={key}><h3>{title}</h3><Lines value={proposal[key]}/></section>:null)}</fieldset>
     <p className="collab-footnote">讨论稿不直接修改质控算法。形成意见后再交由开发接入。</p>
    </>:<div className="collab-empty"><Pencil size={23}/><h3>暂未起草调整方案</h3><p>可先查看当前实现，再围绕本模块提出修改意见。</p><button onClick={()=>setTab('implementation')}>查看当前实现</button></div>}
    {node.teamNotes&&<details className="legacy-notes"><summary>已有团队记录</summary><Lines value={node.teamNotes}/></details>}
   </>}
   {tab==='discussion'&&<>
    <div className="discussion-heading"><strong>{open.length} 条待处理</strong>{threads.some(t=>t.resolved)&&<label><input type="checkbox" checked={showResolved} onChange={e=>setShowResolved(e.target.checked)}/>显示已处理</label>}</div>
    {writable&&<form className="comment-composer" onSubmit={e=>{e.preventDefault();void send('comment');}}><textarea aria-label="添加批注" value={body} maxLength={4000} rows={3} onChange={e=>setBody(e.target.value)} placeholder="围绕本模块，写下问题或建议…"/><div>{dirty&&<small>请先保存方案草稿，再发布批注。</small>}<button className="primary" disabled={busy||dirty||!body.trim()}><MessageSquare size={14}/>发布批注</button></div></form>}
    {!threads.length&&<div className="collab-empty compact"><MessageSquare size={23}/><p>还没有批注。方法选择、参数和计分依据都可以在这里讨论。</p></div>}
    {!writable&&<p className="collab-footnote">{frozen?'此处保留当时的讨论；点击“基于此版修改”可继续起草。':'输入编辑密码后，可添加批注和回复。'}</p>}
    {threads.filter(t=>showResolved||!t.resolved).slice().reverse().map(t=><article className={'discussion-thread '+(t.resolved?'resolved':'')} key={t.id}><header><strong>{t.author}</strong><time>{new Date(t.createdAt).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'})}</time></header><Lines value={t.body}/>{t.replies.map(r=><div className="discussion-reply" key={r.id}><header><strong>{r.author}</strong><time>{new Date(r.createdAt).toLocaleDateString('zh-CN')}</time></header><Lines value={r.body}/></div>)}<footer>{t.resolved&&<span><Check size={13}/>已处理</span>}{writable&&<><button disabled={busy||dirty} onClick={()=>{setReplyTo(replyTo===t.id?'':t.id);setReply('');}}><Reply size={13}/>回复</button><button disabled={busy||dirty} onClick={()=>void send(t.resolved?'reopen':'resolve',t.id)}>{t.resolved?'重新讨论':'标记已处理'}</button></>}</footer>{replyTo===t.id&&writable&&<form className="reply-composer" onSubmit={e=>{e.preventDefault();void send('reply',t.id);}}><textarea aria-label="回复内容" value={reply} rows={3} maxLength={4000} onChange={e=>setReply(e.target.value)} placeholder="补充回复…"/><button disabled={busy||dirty||!reply.trim()} className="primary">发送回复</button></form>}</article>)}
   </>}
   {tab==='implementation'&&<div className="implementation"><p className="source-caption">来自质控台 · 随代码发布同步</p><Lines value={node.description||node.summary}/><ScoringDetails node={node} select={select}/>{[['conditions','启用条件'],['inputs','输入'],['outputs','输出'],['methods','方法与来源'],['notes','实现说明'],['evidence','参考资料']].map(([key,title])=>node[key as keyof FlowNode]?<details key={key}><summary>{title}</summary><Lines value={String(node[key as keyof FlowNode])}/></details>:null)}</div>}
  </div>
 </div>;
}
