// In-memory UI state test. Does not launch or simulate an actual browser render.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code=fs.readFileSync('apps/workbench/web/waveform-explorer.js','utf8');
const created=[];
class N{
 constructor(tag='div'){this.tag=tag;this.children=[];this.attrs={};this.dataset={};this.handlers={};this.style={setProperty(){}};this.classes=new Set();this.classList={add:(v)=>this.classes.add(v),remove:(v)=>this.classes.delete(v),toggle:(v,on)=>on?this.classes.add(v):this.classes.delete(v),contains:(v)=>this.classes.has(v)};this.clientWidth=800;this.clientHeight=270;this.value='';created.push(this);}
 append(...n){this.children.push(...n);}
 replaceChildren(...n){this.children=n;}
 setAttribute(k,v){this.attrs[k]=String(v);}getAttribute(k){return this.attrs[k];}removeAttribute(k){delete this.attrs[k];}
 addEventListener(k,f){this.handlers[k]=f;}fire(k,e={}){this.handlers[k]?.(e);}
 focus(){document.activeElement=this;}getBoundingClientRect(){return {width:800,height:270,left:0};}
}
const ids=['finding-fullscreen','finding-preview','finding-filters','finding-index-notice','finding-image','finding-status','finding-title','finding-position','finding-measure',
 'wave-controls','wave-notice','wave-span','wave-position','wave-prev','wave-next','wave-zoom-in','wave-zoom-out','wave-reset','wave-range',
 'wave-segment-start','wave-segment-end','wave-channel-count','wave-channel-options','wave-search','wave-channel-menu','wave-channels-toggle'];
const nodes=Object.fromEntries(ids.map(id=>{const n=new N();n.id=id;return[id,n];}));
const inspector=new N(),fullLabel=new N();nodes['finding-fullscreen'].querySelector=()=>fullLabel;
const stage=new N(),workspace=new N(),sidebar=new N(),list=new N(),listLabel=new N(),caption=new N();
workspace.querySelector=s=>s==='.finding-sidebar'?sidebar:list;sidebar.querySelector=()=>listLabel;
nodes['finding-preview'].querySelector=s=>s==='.finding-stage'?stage:caption;nodes['finding-preview'].closest=s=>s==='.finding-inspector'?inspector:workspace;nodes['finding-preview'].dataset.waveformBase='/test';
const get=id=>created.find(n=>n.id===id);
const document={body:{style:{overflow:'auto'}},activeElement:null,handlers:{},documentElement:{lang:'zh-CN'},getElementById:get,querySelectorAll:()=>[],createElement:tag=>new N(tag),createElementNS:(_,tag)=>new N(tag),addEventListener(k,f){(this.handlers[k]??=[]).push(f);}};
const index={warnings:[],methods:[{id:'hf',label:'高频突发',label_en:'HF',color:'#8b5bb5',location_count:2},{id:'low',label:'低频异常',color:'#24968a',location_count:1}],channels:[{id:'a',name:'FP2',source_index:7},{id:'b',name:'AF4',source_index:2}],findings:[
 {id:'1',method:'hf',channels:['a'],start:15,stop:16.5,localization:'interval'},
 {id:'2',method:'hf',channels:['b'],start:15,stop:16.5,localization:'interval'},
 {id:'3',method:'low',channels:['b'],start:14,stop:17,localization:'interval'}]};
index.methods.push({id:'psd',label:'频谱差异',color:'#7f7953',location_count:1},
 {id:'integrity',label:'信号完整性',color:'#b45309',location_count:1});
index.methods.push({id:'empty',label:'无候选检查',color:'#42546b',location_count:0});
index.default_method_ids=['hf','low','psd','integrity'];
index.findings.push({id:'4',method:'psd',channels:['b'],start:0,stop:120,localization:'channel'},
 {id:'5',method:'integrity',channels:['a'],start:13,stop:18,localization:'interval'});
const reads=[];let failSource=false;
const runtime={document,URLSearchParams,console,setTimeout,clearTimeout,window:null,fetch:async url=>{
 reads.push(url);
 if(url.endsWith('finding-locations'))return {ok:true,json:async()=>index};
 if(url.endsWith('waveform-context'))return {ok:!failSource,json:async()=>({limits:{max_channels:15,max_seconds:60,max_read_bytes:67108864},streams:[{stream_id:'s',sampling_rate_hz:500,segments:[{start_seconds:0,stop_seconds:800}],channels:[{channel_id:'a',name:'FP2',source_index:7},{channel_id:'b',name:'AF4',source_index:2},...Array.from({length:18},(_,i)=>({channel_id:'extra'+i,name:'C'+i,source_index:20+i}))]}]})};
 const p=new URL(url,'http://local').searchParams,start=Number(p.get('start_seconds')),span=Number(p.get('duration_seconds'));
 return {ok:true,json:async()=>({frozen_source_verified:true,channels:p.get('channel_indices').split(',').map(id=>({channel_id:id==='7'?'a':'b',source_index:Number(id),name:id==='7'?'FP2':'AF4',unit:'µV',values:[0,10,0],times_seconds:[start,start+span/2,start+span]}))})};
}};runtime.window=runtime;
vm.runInNewContext(code,runtime);
const tick=()=>new Promise(resolve=>setImmediate(resolve));await tick();await tick();
assert.equal(list.children.length,4,'Every saved interval shown initially, including unscored checks');
assert(!get('finding-filters').children[2].open,'Checks without locations initially folded');
const rangeBefore=get('wave-range').textContent,readsBefore=reads.length;
get('finding-fullscreen').fire('click');await tick();
assert(inspector.classList.contains('finding-is-fullscreen'));assert.equal(get('finding-fullscreen').getAttribute('aria-pressed'),'true');
assert.equal(fullLabel.textContent,'退出全屏');assert.equal(document.body.style.overflow,'hidden');
for(const handler of document.handlers.keydown)handler({key:'Escape',preventDefault(){}});await tick();
assert(!inspector.classList.contains('finding-is-fullscreen'));assert.equal(document.body.style.overflow,'auto');
assert.equal(get('wave-range').textContent,rangeBefore);assert.equal(reads.length,readsBefore,'Fullscreen never refetches signals or changes the interval');
// Native browser full screen and browser-managed Escape use the same state.
inspector.requestFullscreen=async()=>{document.fullscreenElement=inspector;for(const h of document.handlers.fullscreenchange)h();};
document.exitFullscreen=async()=>{document.fullscreenElement=null;for(const h of document.handlers.fullscreenchange)h();};
get('finding-fullscreen').fire('click');await tick();assert.equal(document.fullscreenElement,inspector);
get('finding-fullscreen').fire('click');await tick();assert(!inspector.classList.contains('finding-is-fullscreen'));

assert.equal(get('finding-title').textContent,'FP2 · 高频突发');
const boxes=()=>get('finding-filters').children[1].children.map(n=>n.children[0]);
const channelBox=get('wave-channel-options').children[1].children[0];channelBox.checked=true;channelBox.fire('change');await tick();
const svg=created.find(n=>n.id==='wave-plot');
assert(svg.innerHTML.includes('data-mark-channel="b"'),'Comparison channel must show its existing detection');
assert(svg.innerHTML.includes('data-mark-method="low"'),'Simultaneous other-check overlays visible');
assert(svg.innerHTML.includes('data-mark-method="integrity"'),'Unscored findings are visible by default');
get('finding-kinds').children[1].fire('click');await tick();
assert.equal(list.children.length,1,'Channel results are separate from precise intervals');
assert.equal(get('finding-title').textContent,'AF4 · 频谱差异');
assert(get('finding-measure').textContent.includes('分析范围 0–120 s'));
assert(get('finding-measure').textContent.includes('未定位异常时刻'));
assert(!svg.innerHTML.includes('data-mark-method="psd"')&&!svg.innerHTML.includes('<circle'));
get('finding-kinds').children[0].fire('click');await tick();
const extraBox=get('finding-filters').children[2].children[1].children[0].children[0];extraBox.checked=true;extraBox.fire('change');
assert.equal(list.children.length,4);assert(svg.innerHTML.includes('data-mark-method="integrity"'));
assert(!svg.innerHTML.includes('data-mark-method="empty"'),'No locations are invented for empty checks');
boxes()[3].checked=false;boxes()[3].fire('change');
assert.equal(list.children.length,3);assert(!svg.innerHTML.includes('data-mark-method="integrity"'));
get('finding-filters').children[0].children[1].fire('click');await tick();
assert.equal(list.children.length,4);assert(svg.innerHTML.includes('data-mark-method="integrity"'));
const again=get('wave-channel-options').children[1].children[0];again.checked=true;again.fire('change');await tick();
boxes()[1].checked=false;boxes()[1].fire('change');
assert.equal(list.children.length,3);assert(!svg.innerHTML.includes('data-mark-method="low"'));
const readCount=reads.length;
get('finding-filters').children[0].children[2].fire('click');
assert(!svg.innerHTML.includes('data-mark-channel'),'Hide all removes all lane annotations');
assert.equal(reads.length,readCount,'Filters do not run QC or reload native waveforms');
get('finding-filters').children[0].children[1].fire('click');
assert.equal(list.children.length,4);assert(svg.innerHTML.includes('data-mark-method="low"'));
get('finding-search').value='AF4';get('finding-search').fire('input');assert.equal(list.children.length,2);
list.children[1].fire('click');await tick();assert.equal(get('finding-title').textContent,'AF4 · 低频异常');
assert(get('finding-measure').textContent.includes('14–17'));
assert.equal(reads.filter(u=>u.endsWith('finding-locations')).length,1);
for(let i=0;i<15;i++){const box=get('wave-channel-options').children[i].children[0];if(!box.checked){box.checked=true;box.fire('change');await tick();}}
assert.equal(get('wave-channel-count').textContent,'15 / 15');
assert(get('wave-channel-options').children[15].children[0].disabled,'Sixteenth lane cannot be added');
const selectedBox=get('wave-channel-options').children[4].children[0];selectedBox.checked=false;selectedBox.fire('change');await tick();
assert.equal(get('wave-channel-count').textContent,'14 / 15');assert(!get('wave-channel-options').children[15].children[0].disabled);
console.log('PASS all candidates default on, manual filtering and reset, empty checks, channel vs interval scopes, fullscreen and 15-channel comparison');
