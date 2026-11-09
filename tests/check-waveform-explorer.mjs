// Pure geometry and simulated UI/network tests; not browser visual acceptance.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code=fs.readFileSync('apps/workbench/web/waveform-explorer.js','utf8');
const geometry={module:{exports:{}}};vm.runInNewContext(code,geometry);
const g=geometry.module.exports,segment={start_seconds:3.5,stop_seconds:103.5};
assert.equal(g.viewport(-3,10,segment).start,3.5);
assert.equal(g.viewport(102,10,segment).start,93.5);
assert.equal(g.viewport(3.5,120,segment).span,100);
assert.equal(g.pan({start:40,span:10},100,1000,segment).start,39);
assert.equal(g.pan({start:40,span:1},100,1000,segment).start,39.9);
assert.equal(g.pan({start:40,span:60},100,1000,segment).start,34);
assert.equal(g.zoom({start:40,span:10},30,segment).start,30);
const anchored=g.zoom({start:40,span:10},5,segment,.8);
assert.equal(anchored.start+anchored.span*.8,48,'Zoom holds the point under the pointer still');
const longSegment={start_seconds:0,stop_seconds:21600};
const nearby=g.navigation({start:10800,span:10},longSegment);
assert.equal(nearby.max-nearby.min,40,'Six-hour records still use a local 40-second slider at 10-second zoom');
assert.equal(g.navigation({start:10805,span:10},longSegment,nearby),nearby,'Releasing a drag inside the rail must not recenter or move the thumb');
const closer=g.navigation({start:10800,span:1},longSegment,nearby);
assert.equal(closer.max-closer.min,4,'Zooming in automatically refines the rail');
assert.equal(g.navigation({start:0,span:10},longSegment).min,0);
assert.equal(g.navigation({start:21590,span:10},longSegment).max,21590);
const waveform={channels:[{channel_id:'a',name:'F2<script>',unit:'µV',times_seconds:[41,42,43,44],values:[1,null,100,-50]},
 {channel_id:'b',name:'FP1',unit:'µV',times_seconds:[41,42,43,44],values:[2,3,4,5]},
 {channel_id:'c',name:'MEG',unit:'T',times_seconds:[41,42,43,44],values:[1e-12,2e-12,3e-12,4e-12]}]};
const ranges=g.scales(waveform.channels);assert(ranges['µV'][0]<-50&&ranges['µV'][1]>100);
assert(ranges.T[1]<ranges['µV'][1]);
const markup=g.plot(waveform,{start:40,span:10},{id:'a',start:43,stop:47});
assert.equal((markup.match(/data-mark-channel="a"/g)||[]).length,1,'Legacy snapshot has only its known channel interval');
assert(markup.includes('F2&lt;script&gt;')&&!markup.includes('<script>'));
assert(!markup.includes('NaN')&&!markup.includes('Infinity'));
assert((markup.match(/M/g)||[]).length>=4,'Missing samples break a line instead of drawing through them');

const annotations=[
 {channels:['a'],start:43,stop:47,method:'hf',color:'#8b5bb5',label:'HF',localization:'interval'},
 {channels:['b'],start:43,stop:47,method:'hf',color:'#8b5bb5',label:'HF',localization:'interval'},
 {channels:['b'],start:44,stop:48,method:'line',color:'#b77908',label:'Line',localization:'interval'},
 {channels:['b'],start:40,stop:50,method:'lof',color:'#477882',label:'LOF',localization:'channel'},
 {channels:['a','b'],start:42,stop:44,method:'jump',color:'#bd525d',label:'Group',localization:'group_interval'},
 {channels:['c'],start:70,stop:80,method:'hf',color:'#8b5bb5',label:'HF',localization:'interval'}];
const allMarks=g.plot(waveform,{start:40,span:10},{id:'a',start:43,stop:47},800,270,annotations);
assert.equal((allMarks.match(/data-mark-channel="b"/g)||[]).length,2,'Both checks shade the comparison channel');
assert(allMarks.includes('data-group-mark="jump"'),'Group evidence has its own band, never per-channel blame');
assert(!allMarks.includes('data-mark-channel="c"'),'Out-of-view findings are clipped');
assert(!allMarks.includes('data-mark-method="lof"'),'Channel-only findings are not time intervals');
const hidden=g.plot(waveform,{start:40,span:10},{id:'a',start:43,stop:47},800,270,[]);
assert(!hidden.includes('data-mark-channel'),'Hide all removes even the primary candidate shading');
const hfOnly=g.plot(waveform,{start:40,span:10},{id:'a',start:43,stop:47},800,270,annotations.filter(r=>r.method==='hf'));
assert(!hfOnly.includes('data-mark-method="line"')&&hfOnly.includes('data-mark-channel="b"'));

class Node {
  constructor(tag='div'){this.tagName=tag.toUpperCase();this.dataset={};this.attrs={};this.children=[];this.handlers={};this.value='';this.hidden=false;this.classList={add(){},remove(){}};this.style={setProperty(k,v){this[k]=v;}};this.clientWidth=800;this.clientHeight=270;}
  addEventListener(n,fn){this.handlers[n]=fn;}
  fire(n,e={}){return this.handlers[n]?.(e);}
  setAttribute(k,v){this.attrs[k]=String(v);}
  getAttribute(k){return this.attrs[k];}
  removeAttribute(k){delete this.attrs[k];}
  replaceChildren(...nodes){this.children=nodes;}
  append(...nodes){this.children.push(...nodes);}
  focus(){}
  getBoundingClientRect(){return {left:0,width:this.clientWidth,height:this.clientHeight};}
  setPointerCapture(){}
  hasPointerCapture(){return false;}
}
const ids=['finding-preview','finding-image','finding-status','finding-title','finding-position','finding-measure',
 'wave-controls','wave-notice','wave-span','wave-position','wave-prev','wave-next','wave-zoom-in','wave-zoom-out','wave-reset','wave-range',
 'wave-segment-start','wave-segment-end','wave-channel-count','wave-channel-options','wave-search','wave-channel-menu','wave-channels-toggle'];
const nodes=Object.fromEntries(ids.map(id=>[id,new Node()]));
const stage=new Node(),wrapper=new Node(),caption=new Node();
const panel=nodes['finding-preview'];panel.dataset.waveformBase='/api/v1/jobs/test';
panel.querySelector=s=>s==='.finding-stage'?stage:caption;panel.closest=()=>wrapper;
nodes['wave-controls'].hidden=true;
const link=new Node('a');link.href='/saved-0.png';link.dataset={channelId:'a',start:'43',stop:'47',title:'F2 · 43–47 秒',measure:'候选',position:'1 / 1'};link.setAttribute('aria-current','true');
const document={documentElement:{lang:'zh-CN'},getElementById:id=>nodes[id],querySelectorAll:()=>[link],handlers:{},
 createElement:tag=>new Node(tag),createElementNS:(_,tag)=>{const n=new Node(tag);if(tag==='svg')nodes.svg=n;return n;},
 addEventListener(n,fn){this.handlers[n]=fn;}};
const reads=[];
const timers=new Map();let timerId=0;
const context={document,window:null,URLSearchParams,fetch:(url)=>new Promise(resolve=>reads.push({url,resolve})),console,
 setTimeout(fn){timers.set(++timerId,fn);return timerId;},clearTimeout(id){timers.delete(id);}};
context.window=context;
vm.runInNewContext(code,context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const settleZoom=async()=>{const callbacks=[...timers.values()];timers.clear();callbacks.forEach(fn=>fn());await tick();};
const answer=async(data,ok=true)=>{const req=reads.shift();assert(req);req.resolve({ok,json:async()=>data});await tick();return req;};
assert(reads[0].url.endsWith('waveform-context'));
await answer({frozen_source_verified:true,limits:{max_channels:6,max_seconds:60,max_points:2000,max_read_bytes:67108864},streams:[{
 stream_id:'s',sampling_rate_hz:500,segments:[{start_seconds:0,stop_seconds:733}],channels:[
 {source_index:7,channel_id:'a',name:'F2',unit:'V'},{source_index:2,channel_id:'b',name:'FP1',unit:'V'},
 {source_index:8,channel_id:'c',name:'F3',unit:'V'}]}]});
assert(reads[0].url.includes('start_seconds=40.000000'));
assert(reads[0].url.includes('channel_indices=7'));
const resolveWave=async()=>{
 const p=new URL(reads[0].url,'http://local').searchParams,start=Number(p.get('start_seconds')),span=Number(p.get('duration_seconds'));
 const selected=p.get('channel_indices').split(',').map(Number);
 await answer({frozen_source_verified:true,start_seconds:start,stop_seconds:start+span,duration_seconds:span,
 channels:selected.map(index=>({source_index:index,channel_id:index===7?'a':index===2?'b':'c',name:index===7?'F2':index===2?'FP1':'F3',unit:'µV',times_seconds:[start,start+span/2,start+span-.01],values:[0,100,-20]}))});
};
await resolveWave();assert.equal(panel.dataset.state,'ready');assert.equal(nodes['finding-image'].hidden,true);
assert.equal(Number(nodes['wave-position'].max)-Number(nodes['wave-position'].min),40);
assert.equal(nodes['wave-controls'].hidden,false);assert.equal(nodes['wave-range'].textContent,'40–50 s');
const fp1=nodes['wave-channel-options'].children[1].children[0];fp1.checked=true;fp1.fire('change');
assert(reads[0].url.includes('channel_indices=7%2C2'));await resolveWave();
assert(nodes.svg.innerHTML.includes('FP1'));assert.equal(nodes['wave-channel-count'].textContent,'2 / 6');
nodes['wave-zoom-out'].fire('click');nodes['wave-zoom-out'].fire('click');
assert.equal(reads.length,0,'Zoom redraws immediately and batches the source read until the gesture settles');
assert.equal(nodes['wave-span'].textContent,'40 s');
await settleZoom();assert(reads[0].url.includes('start_seconds=25.000000'));await resolveWave();
nodes['wave-next'].fire('click');assert.equal(reads.length,1);
nodes['wave-next'].fire('click');nodes['wave-next'].fire('click');assert.equal(reads.length,1,'Repeated actions must not spawn concurrent source reads');
await resolveWave();assert.equal(reads.length,1,'Only the latest requested position is queued');
assert(reads[0].url.includes('start_seconds=85.000000'));await resolveWave();
assert.equal(nodes['wave-range'].textContent,'85–125 s');
const railMin=Number(nodes['wave-position'].min),railMax=Number(nodes['wave-position'].max);
nodes['wave-position'].value='90';nodes['wave-position'].fire('input');
assert.equal(reads.length,0,'Dragging a position slider does not immediately fetch');
assert.equal(nodes['wave-range'].textContent,'90–130 s');
nodes['wave-position'].fire('change');await resolveWave();
assert.equal(Number(nodes['wave-position'].min),railMin);assert.equal(Number(nodes['wave-position'].max),railMax);
nodes.svg.fire('pointerdown',{button:0,clientX:100,pointerId:1});
nodes.svg.fire('pointermove',{clientX:200});assert.equal(reads.length,0,'Dragging the chart only changes the viewport');
nodes.svg.fire('pointerup',{pointerId:1});
const p=new URL(reads[0].url,'http://local').searchParams;
assert(Math.abs(Number(p.get('start_seconds'))-(90-100/716*40))<1e-5);await resolveWave();
let prevented=false;
nodes.svg.fire('wheel',{deltaY:-100,deltaMode:0,clientX:432,preventDefault(){prevented=true;}});
assert(prevented);assert(Number.parseFloat(nodes['wave-span'].textContent)<40);
await settleZoom();await resolveWave();
const previous=nodes['wave-span'].textContent;
nodes.svg.fire('wheel',{ctrlKey:true,deltaY:-100,preventDefault(){throw Error('Keep browser zoom available');}});
assert.equal(nodes['wave-span'].textContent,previous);
nodes['wave-reset'].fire('click');await tick();if(reads.length)await resolveWave();
const [a,b]=nodes['wave-range'].textContent.replace(' s','').split('–').map(Number);assert(Math.abs((a+b)/2-45)<.01,'Reset restores the candidate center at the selected zoom');
nodes['wave-prev'].fire('click');await answer({},false);assert.equal(panel.dataset.state,'error');
assert(nodes['wave-notice'].textContent.includes('重试'));assert.equal(nodes['wave-notice'].children.at(-1).href,'/saved-0.png');
console.log('PASS native-time pan/zoom/boundaries, shared scaling, missing gaps, safe labels, 2-channel alignment, serial reads, stale responses, dragging, reset and error fallback');
