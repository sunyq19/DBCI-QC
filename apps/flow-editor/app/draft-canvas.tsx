'use client';
import {useRef,useState,useEffect,useLayoutEffect} from 'react';
import {Minus,Plus,Maximize2,ArrowLeft} from 'lucide-react';
import {type FlowDoc,type FlowNode,displayNodes,drawingEdges,nodeTitle,flattenNodes,sketchFor,edgePath,NODE_W,NODE_H,CANVAS_W,CANVAS_H} from '../lib/flow';
import {clampScale,wheelPixels,wheelScale} from '../lib/canvas-zoom';
export default function DraftCanvas({doc,selected,select,inspect,writable,patch,checkpoint,connect,linkFrom,setLinkFrom,selectedEdge,setSelectedEdge,inspectEdge,add,level,setLevel}:{doc:FlowDoc;selected:string;select:(id:string)=>void;inspect:(id:string)=>void;writable:boolean;patch:(id:string,p:Partial<FlowNode>)=>void;checkpoint:()=>void;connect:(source:string,target:string)=>void;linkFrom:string;setLinkFrom:(id:string)=>void;selectedEdge:string;setSelectedEdge:(id:string)=>void;inspectEdge:(id:string)=>void;add:(parent?:string,position?:{x:number;y:number})=>void;level:string;setLevel:(id:string)=>void}){
 const svg=useRef<SVGSVGElement>(null),rail=useRef<HTMLDivElement>(null),wire=useRef<{source:string;start:[number,number]}|null>(null);
 const [scale,setScale]=useState(.78),[pointer,setPointer]=useState<[number,number]|null>(null),autoFit=useRef(true);
 const scaleNow=useRef(scale),zoomAnchor=useRef<{x:number;y:number;clientX:number;clientY:number}|null>(null);
 const drag=useRef<{id:string;pointerId:number;x:number;y:number;nodeX:number;nodeY:number;moved:boolean}|null>(null),draggedNode=useRef(false);
 const [dragging,setDragging]=useState(false);
 const all=flattenNodes(doc.nodes),parent=all.find(n=>n.id===level),raw=level?parent?.children||[]:doc.nodes;
 const nodes=displayNodes(raw).map((n,i)=>level&&!n.sketch?.positioned?{...n,x:70+(i%4)*320,y:70+Math.floor(i/4)*170}:n),index=new Map(nodes.map(n=>[n.id,n]));
 const edges=drawingEdges(doc).filter(e=>index.has(e.source)&&index.has(e.target));
 const fit=()=>{if(rail.current)setScale(Math.max(.4,Math.min(1,(rail.current.clientWidth-36)/CANVAS_W)));};
 useEffect(()=>{fit();const observer=new ResizeObserver(()=>{if(autoFit.current)fit();});if(rail.current)observer.observe(rail.current);return()=>observer.disconnect();},[]);
 useEffect(()=>{rail.current?.scrollTo({top:0,left:0});},[level]);
 useEffect(()=>{if(!linkFrom){wire.current=null;setPointer(null);}},[linkFrom]);
 useLayoutEffect(()=>{
  scaleNow.current=scale;const anchor=zoomAnchor.current,container=rail.current,rect=svg.current?.getBoundingClientRect();
  if(anchor&&container&&rect){container.scrollLeft+=rect.left+anchor.x*scale-anchor.clientX;container.scrollTop+=rect.top+anchor.y*scale-anchor.clientY;}
  zoomAnchor.current=null;
 },[scale]);
 function zoom(next:number,clientX?:number,clientY?:number){
  const container=rail.current,rect=svg.current?.getBoundingClientRect();if(!container||!rect||next===scaleNow.current)return;
  const bounds=container.getBoundingClientRect(),x=clientX??bounds.left+container.clientWidth/2,y=clientY??bounds.top+container.clientHeight/2;
  zoomAnchor.current={x:(x-rect.left)/scaleNow.current,y:(y-rect.top)/scaleNow.current,clientX:x,clientY:y};autoFit.current=false;setScale(next);
 }
 useEffect(()=>{
  const container=rail.current;if(!container)return;
  let frame=0,pixels=0,x=0,y=0;
  const wheel=(e:WheelEvent)=>{
   if(!e.ctrlKey)return;
   // Cancel browser page zoom only over this canvas; ordinary wheel scrolling is native.
   e.preventDefault();e.stopPropagation();if(wire.current||drag.current)return;
   pixels+=wheelPixels(e.deltaY,e.deltaMode,container.clientHeight);x=e.clientX;y=e.clientY;
   if(!frame)frame=requestAnimationFrame(()=>{frame=0;zoom(wheelScale(scaleNow.current,pixels),x,y);pixels=0;});
  };
  container.addEventListener('wheel',wheel,{passive:false});
  return()=>{container.removeEventListener('wheel',wheel);cancelAnimationFrame(frame);};
 },[]);
 function point(e:{clientX:number;clientY:number}){const matrix=svg.current?.getScreenCTM();return matrix?new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse()):null;}
 function addAtBlank(e:React.MouseEvent){
  if(!writable||e.button!==0||(e.target as Element).closest('.graph-node,.graph-edge,button,[role="button"]'))return;
  const bounds=rail.current?.getBoundingClientRect();
  if(!bounds||e.clientX>=bounds.left+rail.current!.clientLeft+rail.current!.clientWidth||e.clientY>=bounds.top+rail.current!.clientTop+rail.current!.clientHeight)return;
  const p=point(e);if(!p)return;
  e.preventDefault();e.stopPropagation();
  add(level||undefined,{x:Math.round(Math.max(20,Math.min(CANVAS_W-NODE_W-20,p.x-NODE_W/2))),y:Math.round(Math.max(20,Math.min(CANVAS_H-NODE_H-20,p.y-NODE_H/2)))});
 }
 function startNode(e:React.PointerEvent,n:FlowNode){
  if(e.button!==0||!e.isPrimary)return;
  draggedNode.current=false;
  if(linkFrom){select(n.id);return;}
  const wasSelected=selected===n.id;select(n.id);
  if(!writable||!wasSelected)return;
  const p=point(e);if(!p)return;
  drag.current={id:n.id,pointerId:e.pointerId,x:p.x,y:p.y,nodeX:n.x,nodeY:n.y,moved:false};
 }
 function stopNodeDrag(){
  const active=drag.current;drag.current=null;setDragging(false);
  if(active&&svg.current?.hasPointerCapture(active.pointerId))svg.current.releasePointerCapture(active.pointerId);
 }
 useEffect(()=>{window.addEventListener('blur',stopNodeDrag);return()=>window.removeEventListener('blur',stopNodeDrag);},[]);
 function move(e:React.PointerEvent){
  const p=point(e);if(!p)return;
  if(wire.current){setPointer([p.x,p.y]);return;}
  const active=drag.current;if(!active||!writable||active.pointerId!==e.pointerId)return;
  if(!active.moved){
   if(Math.hypot(p.x-active.x,p.y-active.y)*scaleNow.current<3)return;
   svg.current?.setPointerCapture(e.pointerId);checkpoint();active.moved=true;draggedNode.current=true;setDragging(true);
  }
  e.preventDefault();
  patch(active.id,{sketch:{...sketchFor(all.find(n=>n.id===active.id)!),positioned:true},x:Math.round(Math.max(20,Math.min(CANVAS_W-NODE_W-20,active.nodeX+p.x-active.x))),y:Math.round(Math.max(20,Math.min(CANVAS_H-NODE_H-20,active.nodeY+p.y-active.y)))});
 }
 function finish(e:React.PointerEvent){const w=wire.current;if(w){const p=point(e),target=p&&nodes.find(n=>p.x>=n.x-8&&p.x<=n.x+NODE_W+8&&p.y>=n.y-8&&p.y<=n.y+NODE_H+8&&n.id!==w.source);if(target){connect(w.source,target.id);setLinkFrom('');}wire.current=null;setPointer(null);}stopNodeDrag();}
 function startWire(e:React.PointerEvent,n:FlowNode){e.stopPropagation();if(!writable)return;setLinkFrom(n.id);wire.current={source:n.id,start:[n.x+NODE_W,n.y+NODE_H/2]};e.currentTarget.setPointerCapture(e.pointerId);setPointer(wire.current.start);}
 return <div className="draft-canvas">
  <div className="canvas-context">{parent?<button onClick={()=>setLevel('')}><ArrowLeft size={14}/>全部模块</button>:<span>{writable?'单击选中，再拖动模块 · 双击查看详情':'单击选中模块 · 双击查看详情'}</span>}{parent&&<strong>{nodeTitle(parent)}</strong>}{writable&&<button onClick={()=>add(level||undefined)}><Plus size={14}/>{parent?'子模块':'模块'}</button>}</div>
  <div className="canvas-scroll" ref={rail} onDragStart={e=>e.preventDefault()} onDoubleClick={addAtBlank}>
   <svg ref={svg} className={'flow-svg '+(writable?'editable ':'')+(dragging?'dragging':'')} aria-label="可编辑流程画布" width={CANVAS_W*scale} height={CANVAS_H*scale} viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`} onPointerMove={move} onPointerUp={finish} onPointerLeave={()=>{if(drag.current&&!drag.current.moved)stopNodeDrag();}} onLostPointerCapture={()=>{if(drag.current?.moved)stopNodeDrag();}} onPointerCancel={()=>{wire.current=null;setPointer(null);stopNodeDrag();}}>
    <defs><marker id="draft-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M0 0L9 4.5L0 9" fill="#7890b1"/></marker></defs>
    {edges.map(e=>{const a=index.get(e.source)!,b=index.get(e.target)!;let p=edgePath(a,b);if(Math.abs(a.y-b.y)<70&&Math.abs(a.x-b.x)>NODE_W+180){const right=b.x>a.x,sx=a.x+(right?NODE_W:0),tx=b.x+(right?0:NODE_W),sy=a.y+NODE_H/2,ty=b.y+NODE_H/2,top=Math.max(12,Math.min(a.y,b.y)-30),d=right?1:-1;p={d:`M${sx},${sy} C${sx+24*d},${sy} ${sx+24*d},${top} ${sx+48*d},${top} L${tx-48*d},${top} C${tx-24*d},${top} ${tx-24*d},${ty} ${tx},${ty}`,x:(sx+tx)/2,y:top-6};}return <g className={'graph-edge '+(selectedEdge===e.id?'selected':'')} key={e.id} role="button" tabIndex={0} aria-label={'连接 '+nodeTitle(index.get(e.source)!)+' 到 '+nodeTitle(index.get(e.target)!)} aria-pressed={selectedEdge===e.id} onClick={()=>setSelectedEdge(e.id)} onDoubleClick={event=>{event.stopPropagation();inspectEdge(e.id);}} onKeyDown={event=>{if(event.key==='Enter'){event.preventDefault();inspectEdge(e.id);}else if(event.key===' '){event.preventDefault();setSelectedEdge(e.id);}}}><path d={p.d} className="edge-hit"/><path d={p.d} className="edge-line" markerEnd="url(#draft-arrow)"/>{e.label&&<text x={p.x} y={p.y} className="edge-label" textAnchor="middle">{e.label}</text>}</g>;})}
    {wire.current&&pointer&&<path d={`M${wire.current.start[0]},${wire.current.start[1]} L${pointer[0]},${pointer[1]}`} className="wire-preview"/>}
    {nodes.map(n=><g key={n.id} role="button" tabIndex={0} aria-label={'选择 '+n.title} aria-pressed={selected===n.id} className={'graph-node '+(selected===n.id?'selected ':'')+(linkFrom===n.id?'link-source':'')} transform={`translate(${n.x},${n.y})`} onPointerDown={e=>startNode(e,n)} onDoubleClick={e=>{e.stopPropagation();if(!draggedNode.current)inspect(n.id);}} onKeyDown={e=>{if(e.target!==e.currentTarget)return;if(e.key==='Enter'){e.preventDefault();inspect(n.id);}else if(e.key===' '){e.preventDefault();select(n.id);}else if(writable&&selected===n.id&&['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)){e.preventDefault();checkpoint();patch(n.id,{sketch:{...sketchFor(all.find(v=>v.id===n.id)!),positioned:true},x:Math.min(CANVAS_W-NODE_W-20,Math.max(20,n.x+(e.key==='ArrowRight'?10:e.key==='ArrowLeft'?-10:0))),y:Math.min(CANVAS_H-NODE_H-20,Math.max(20,n.y+(e.key==='ArrowDown'?10:e.key==='ArrowUp'?-10:0)))});}}}>
     <rect width={NODE_W} height={NODE_H} rx="10" className="node-shape"/>
     <foreignObject x="15" y="12" width={NODE_W-30} height={NODE_H-20}><div className="node-inner"><div className="node-code">{n.id}<span>{n.attachments?.length?'附件 '+n.attachments.length:''}</span></div><strong>{n.title}</strong><small>{n.summary}</small></div></foreignObject>
     {!!n.children?.length&&<g className="canvas-children" role="button" tabIndex={0} aria-label={'展开 '+n.title+' 的子模块'} onPointerDown={e=>e.stopPropagation()} onDoubleClick={e=>e.stopPropagation()} onClick={e=>{e.stopPropagation();setLevel(n.id);}} onKeyDown={e=>{if(e.key==='Enter'){e.stopPropagation();setLevel(n.id);}}}><rect x={NODE_W-55} y={-10} width="55" height="23" rx="5"/><text x={NODE_W-27} y="6" textAnchor="middle">{n.children.length} 项 ＋</text></g>}
     {writable&&<circle className="connection-handle" cx={NODE_W} cy={NODE_H/2} r="8" role="button" tabIndex={0} aria-label={'从 '+n.title+' 连线'} onPointerDown={e=>startWire(e,n)} onDoubleClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Enter'){e.stopPropagation();setLinkFrom(n.id);}}}/>}
    </g>)}
   </svg>
  </div>
  <div className="canvas-footer"><span>{linkFrom?'点击目标模块完成连线':writable?'空白处：单击取消选中 · 双击新建模块 · Ctrl + 滚轮缩放':'点击空白处取消选中 · Ctrl + 滚轮缩放'}</span><div className="zoom-controls"><button className="icon" aria-label="缩小" title="缩小" onClick={()=>zoom(clampScale(scaleNow.current-.1))}><Minus size={16}/></button><span aria-live="polite" aria-label="画布缩放比例">{Math.round(scale*100)}%</span><button className="icon" aria-label="放大" title="放大" onClick={()=>zoom(clampScale(scaleNow.current+.1))}><Plus size={16}/></button><button className="icon" aria-label="适应宽度" title="适应宽度" onClick={()=>{autoFit.current=true;zoomAnchor.current=null;fit();}}><Maximize2 size={16}/></button></div></div>
 </div>;
}
