'use client';
import {useState,useEffect} from 'react';
import {Download,Expand,X} from 'lucide-react';
import type {FlowNode} from '../lib/flow';
import examples from '../content/visual-examples.json';
type Example={title:string;availability:'ready'|'planned';dataset:string;modality:string;format:string;details:string;sourceUrl:string;image?:string;takeaway:string;dataUrl?:string;note?:string};
const catalog=examples as Record<string,Example>;
export default function VisualExamples({node,select}:{node:FlowNode;select:(id:string)=>void}){
 const [large,setLarge]=useState(false);useEffect(()=>{if(!large)return;const close=(e:KeyboardEvent)=>{if(e.key==='Escape')setLarge(false);};window.addEventListener('keydown',close);return()=>window.removeEventListener('keydown',close);},[large]);const entry=catalog[node.id];if(!entry)return null;
 const path=(p:string)=>'./'+p.replace(/^\//,'');
 return <section className="visual-example" aria-label="可视化示例"><div className="example-heading"><strong>{entry.availability==='ready'?'示例效果':'尚未接入'}</strong><span>{entry.modality}</span></div>
 {entry.image&&<button className="example-image" onClick={()=>setLarge(true)} aria-label={'放大 '+entry.title}><img src={path(entry.image)} alt={entry.title+'：'+entry.takeaway} loading="lazy"/><Expand size={16}/></button>}
 <p className="example-takeaway">{entry.takeaway}</p><div className="example-data"><strong>{entry.dataset}</strong><span>{entry.format} · {entry.details}</span></div>
 {entry.note&&<p className="example-note">{entry.note}</p>}
 <div className="example-links">{entry.dataUrl&&<a href={path(entry.dataUrl)} download><Download size={13}/>示例测量数据</a>}{entry.sourceUrl&&<a href={entry.sourceUrl} target="_blank" rel="noreferrer">原始数据 ↗</a>}</div>
 {node.id==='VIS'&&<div className="example-gallery">{Object.entries(catalog).filter(([id])=>id!=='VIS').map(([id,e])=><button key={id} onClick={()=>select(id)}>{e.image&&<img src={path(e.image)} alt="" loading="lazy"/>}<span>{e.title}</span>{e.availability==='planned'&&<small>待接入</small>}</button>)}</div>}
 {large&&entry.image&&<div className="image-lightbox" role="dialog" aria-label={entry.title} onClick={()=>setLarge(false)}><button className="icon" aria-label="关闭效果图" onClick={()=>setLarge(false)}><X size={22}/></button><img src={path(entry.image)} alt={entry.title}/><span>{entry.takeaway}</span></div>}
 </section>;
}
