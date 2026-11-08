'use client';
import {type FlowNode,type Scoring,SCORE_LABEL,SCOPE_LABEL,scoreRoles} from '../lib/flow';

export function nodeScoring(node:FlowNode,filter='all'):Scoring[]{
 return node.scope.filter(s=>filter==='all'||s===filter).map(scope=>node.scoring?.find(s=>s.scope===scope)||{
  scope,role:node.status==='planned'?'unavailable':'measurement',canOutputScore:false,outputs:[],weight:'未声明独立计分权重',rule:'此历史版本或成员新增项尚未登记计分接口；请核对后维护。',limited:'未登记的分数不自动计入。',version:'未登记'
 });
}
export function ScoringBadges({node,filter='all'}:{node:FlowNode;filter?:string}){
 if(!node.scoring&&node.status!=='planned')return <span className="score-badge measurement">计分属性未登记</span>;
 const scores=nodeScoring(node,filter),roles=[...new Set(scores.map(s=>s.role))];
 if(!roles.length)return null;
 return <span className="scoring-badges">{roles.map(role=><span className={'score-badge '+role} key={role} title={scores.filter(s=>s.role===role).map(s=>SCOPE_LABEL[s.scope]+': '+s.weight).join('\n')}>{SCORE_LABEL[role]}{roles.length>1&&<span> · {scores.filter(s=>s.role===role).map(s=>({eeg:'EEG',ecog:'ECoG',seeg:'sEEG',np:'NP',dataset:'数据集'}[s.scope])).join('/')}</span>}</span>)}</span>;
}
export function scoringSummary(node:FlowNode,filter='all'){
 if(node.children?.length||!node.scoring)return node.summary;
 const roles=[...new Set(nodeScoring(node,filter).map(s=>s.role))];
 if(roles.length>1)return '按模态采用不同计分角色';
 return roles[0]==='default'?'推荐方案启用 · 需满足条件':roles[0]==='optional'?'可加入评分 · 默认不计入':node.summary;
}
export function ScoringDetails({node,filter='all',select}:{node:FlowNode;filter?:string;select?:(id:string)=>void}){
 if(node.children?.length){
  const children=node.children.filter(n=>(filter==='all'||n.scope.includes(filter))&&(node.id!=='M08'||n.id.startsWith('score_')));
  return <section className="scoring-detail"><h3>{node.id==='M08'?'默认方案与权重':'子项计分属性'}</h3><div className="score-child-list">{children.map(n=><button key={n.id} onClick={()=>select?.(n.id)}><strong>{n.title}</strong>{node.id==='M08'?<span>{n.summary}</span>:n.children?.length?<span>展开后逐项查看</span>:<ScoringBadges node={n} filter={filter}/>}</button>)}</div><p className="score-note">点击子项查看公式、条件与受限项处理。当前方案为项目试行，尚未专家审核。</p></section>;
 }
 if(!node.scoring&&node.status!=='planned')return <p className="score-note">此版本尚未登记计分属性。查看最新版本获取当前接口与默认方案。</p>;
 const scores=nodeScoring(node,filter);
 return <section className="scoring-detail" aria-label="计分属性"><h3>计分属性</h3>{scores.map(s=><div className="score-contract" key={s.scope}><header><strong>{SCOPE_LABEL[s.scope]}</strong><span className={'score-badge '+s.role}>{SCORE_LABEL[s.role]}</span></header><p className="score-weight">{s.weight}</p><p>{s.rule}</p>{s.outputs.length>0&&<details><summary>分数输出 · {s.outputs.length}</summary><ul>{s.outputs.map(o=><li key={o}>{o.split(' · ')[0]}</li>)}</ul></details>}<details><summary>受限与版本</summary><p>{s.limited}</p><small>{s.version}</small></details></div>)}<p className="score-note">“仅测量”也包括资料检查、流程支持与图表，不单独扣分。计分标签表示方案角色，执行仍需满足条件。</p></section>;
}
export function ScoringEditor({node,onChange}:{node:FlowNode;onChange:(scoring:Scoring[])=>void}){
 const scores=nodeScoring(node);
 function patch(scope:string,fields:Partial<Scoring>){onChange(scores.map(s=>s.scope===scope?{...s,...fields}:s));}
 return <details className="scoring-editor"><summary>设计提案 · 计分建议</summary><p className="score-note">此项由成员提出，尚未登记到质控台；计分建议不代表已实现。</p>{scores.map(s=><div key={s.scope}><h4>{SCOPE_LABEL[s.scope]}</h4><label>计分角色<select aria-label={SCOPE_LABEL[s.scope]+'计分角色'} value={s.role} onChange={e=>{const role=e.target.value as Scoring['role'];patch(s.scope,{role,canOutputScore:role==='default'||role==='optional'});}}>{scoreRoles.map(r=><option key={r} value={r} disabled={node.status==='planned'&&r!=='unavailable'}>{SCORE_LABEL[r]}</option>)}</select></label>{(['weight','rule','limited','version'] as const).map((key,i)=><label key={key}>{['权重 / 所属合并项','计算与去重规则','受限项处理','规则版本'][i]}<textarea maxLength={1800} rows={3} value={s[key]} onChange={e=>patch(s.scope,{[key]:e.target.value})}/></label>)}<label>输出分项（每行一个）<textarea rows={3} value={s.outputs.join('\n')} onChange={e=>patch(s.scope,{outputs:e.target.value.split('\n').filter(Boolean)})}/></label></div>)}</details>;
}
