'use client';
import {useRef,useState,useEffect} from 'react';
import {Minus,Plus,Maximize2,ArrowLeft} from 'lucide-react';
import {type FlowDoc,type FlowNode,displayNodes,drawingEdges,nodeTitle,flattenNodes,sketchFor,edgePath,NODE_W,NODE_H,CANVAS_W,CANVAS_H} from '../lib/flow';
export default function DraftCanvas({doc,selected,select,writable,patch,checkpoint,connect,linkFrom,setLinkFrom,selectedEdge,setSelectedEdge,add,level,setLevel}:{doc:FlowDoc;selected:string;select:(id:string)=>void;writable:boolean;patch:(id:string,p:Partial<FlowNode>)=>void;checkpoint:()=>void;connect:(source:string,target:string)=>void;linkFrom:string;setLinkFrom:(id:string)=>void;selectedEdge:string;setSelectedEdge:(id:string)=>void;add:(parent?:string)=>void;level:string;setLevel:(id:string)=>void}){
 const svg=useRef<SVGSVGElement>(null),rail=useRef<HTMLDivElement>(null),drag=useRef<{id:string;x:number;y:number;nodeX:number;nodeY:number;moved:boolean}|null>(null),wire=useRef<{source:string;start:[number,number]}|null>(null);
 const [scale,setScale]=useState(.78),[pointer,setPointer]=useState<[number,number]|null>(null);
 const all=flattenNodes(doc.nodes),parent=all.find(n=>n.id===level),raw=level?parent?.children||[]:doc.nodes;
 const nodes=displayNodes(raw).map((n,i)=>level&&!n.sketch?.positioned?{...n,x:70+(i%4)*320,y:70+Math.floor(i/4)*170}:n),index=new Map(nodes.map(n=>[n.id,n]));
 const edges=drawingEdges(doc).filter(e=>index.has(e.source)&&index.has(e.target));
 const fit=()=>{if(rail.current)setScale(Math.max(.4,Math.min(1,(rail.current.clientWidth-36)/CANVAS_W)));};
 useEffect(()=>{fit();},[]);
 function point(e:React.PointerEvent){const matrix=svg.current?.getScreenCTM();return matrix?new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse()):null;}
 function start(e:React.PointerEvent,n:FlowNode){if(e.button!==0)return;if(linkFrom){select(n.id);return;}select(n.id);if(!writable)return;const p=point(e);if(!p)return;e.currentTarget.setPointerCapture(e.pointerId);drag.current={id:n.id,x:p.x,y:p.y,nodeX:n.x,nodeY:n.y,moved:false};}
 function move(e:React.PointerEvent){const p=point(e);if(!p)return;if(wire.current){setPointer([p.x,p.y]);return;}const d=drag.current;if(!d||!writable)return;if(!d.moved&&Math.hypot(p.x-d.x,p.y-d.y)>3){checkpoint();d.moved=true;}if(d.moved)patch(d.id,{sketch:{...sketchFor(all.find(n=>n.id===d.id)!),positioned:true},x:Math.round(Math.max(20,Math.min(CANVAS_W-NODE_W-20,d.nodeX+p.x-d.x))),y:Math.round(Math.max(20,Math.min(CANVAS_H-NODE_H-20,d.nodeY+p.y-d.y)))});}
 function finish(e:React.PointerEvent){const w=wire.current;if(w){const p=point(e),target=p&&nodes.find(n=>p.x>=n.x-8&&p.x<=n.x+NODE_W+8&&p.y>=n.y-8&&p.y<=n.y+NODE_H+8&&n.id!==w.source);if(target){connect(w.source,target.id);setLinkFrom('');}wire.current=null;setPointer(null);}drag.current=null;}
 function startWire(e:React.PointerEvent,n:FlowNode){e.stopPropagation();if(!writable)return;setLinkFrom(n.id);wire.current={source:n.id,start:[n.x+NODE_W,n.y+NODE_H/2]};e.currentTarget.setPointerCapture(e.pointerId);setPointer(wire.current.start);}
 return <div className="draft-canvas">
  <div className="canvas-context">{parent?<button onClick={()=>setLevel('')}><ArrowLeft size={14}/>全部模块</button>:<span>拖动模块调整位置 · 从右侧圆点拉出连线</span>}{parent&&<strong>{nodeTitle(parent)}</strong>}{writable&&<button onClick={()=>add(level||undefined)}><Plus size={14}/>{parent?'子模块':'模块'}</button>}</div>
  <div className="canvas-scroll" ref={rail} onDragStart={e=>e.preventDefault()}>
   <svg ref={svg} className={'flow-svg '+(writable?'editable':'')} aria-label="可编辑流程画布" width={CANVAS_W*scale} height={CANVAS_H*scale} viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} onPointerMove={move} onPointerUp={finish} onPointerCancel={()=>{drag.current=null;wire.current=null;setPointer(null);}} onDoubleClick={e=>{if(e.target===e.currentTarget&&writable)add(level||undefined);}}>
    <defs><marker id="draft-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9" fill="#7890b1"/></marker></defs>
    {edges.map(e=>{const p=edgePath(index.get(e.source)!,index.get(e.target)!);return <g className={'graph-edge '+(selectedEdge===e.id?'selected':'')} key={e.id} role="button" tabIndex={0} aria-label={'连接 '+nodeTitle(index.get(e.source)!)+' 到 '+nodeTitle(index.get(e.target)!)} onClick={()=>setSelectedEdge(e.id)} onKeyDown={event=>{if(event.key==='Enter')setSelectedEdge(e.id);}}><path d={p.d} className="edge-hit"/><path d={p.d} className="edge-line" markerEnd="url(#draft-arrow)"/>{e.label&&<text x={p.x} y={p.y} className="edge-label" textAnchor="middle">{e.label}</text>}</g>;})}
    {wire.current&&pointer&&<path d={`M${wire.current.start[0]},${wire.current.start[1]} L${pointer[0]},${pointer[1]}`} className="wire-preview"/>}
    {nodes.map(n=><g key={n.id} role="button" tabIndex={0} aria-label={'编辑 '+n.title} className={'graph-node '+(selected===n.id?'selected ':'')+(linkFrom===n.id?'link-source':'')} transform={`translate(${n.x},${n.y})`} onPointerDown={e=>start(e,n)} onKeyDown={e=>{if(e.key==='Enter'){select(n.id);}else if(writable&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();checkpoint();patch(n.id,{sketch:{...sketchFor(all.find(v=>v.id===n.id)!),positioned:true},x:Math.min(CANVAS_W-NODE_W-20,Math.max(20,n.x+(e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0))),y:Math.min(CANVAS_H-NODE_H-20,Math.max(20,n.y+(e.key==='ArrowDown'?10:e.key==='ArrowUp'?-10:0)))});}}}>
     <rect width={NODE_W} height={NODE_H} rx="10" className="node-shape"/>
     <foreignObject x="15" y="12" width={NODE_W-30} height={NODE_H-20}><div className="node-inner"><div className="node-code">{n.id}<span>{n.attachments?.length?'附件 '+n.attachments.length:''}</span></div><strong>{n.title}</strong><small>{n.summary}</small></div></foreignObject>
     {!!n.children?.length&&<g className="canvas-children" role="button" tabIndex={0} aria-label={'展开 '+n.title+' 的子模块'} onPointerDown={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();setLevel(n.id);}} onKeyDown={e=>{if(e.key==='Enter')setLevel(n.id);}}><rect x={NODE_W-55} y={-10} width="55" height="23" rx="5"/><text x={NODE_W-27} y="6" textAnchor="middle">{n.children.length} 项 ＋</text></g>}
     {writable&&<circle className="connection-handle" cx={NODE_W} cy={NODE_H/2} r="8" role="button" tabIndex={0} aria-label={'从 '+n.title+' 连线'} onPointerDown={e=>startWire(e,n)} onKeyDown={e=>{if(e.key==='Enter')setLinkFrom(n.id);}}/>}
    </g>)}
   </svg>
  </div>
  <div className="canvas-footer"><span>{linkFrom?'点击目标模块完成连线':'选中连线可修改文字或删除'}</span><div className="zoom-controls"><button className="icon" aria-label="缩小" onClick={()=>setScale(v=>Math.max(.3,v-.1))}><Minus size={16}/></button><span>{Math.round(scale*100)}%</span><button className="icon" aria-label="放大" onClick={()=>setScale(v=>Math.min(1.5,v+.1))}><Plus size={16}/></button><button className="icon" aria-label="适应宽度" onClick={fit}><Maximize2 size={16}/></button></div></div>
 </div>;
}
