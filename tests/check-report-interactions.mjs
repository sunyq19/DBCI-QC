// Interaction checks without browser automation or a running service.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const requests=[];
const classes=()=>({values:new Set(),add(x){this.values.add(x)},remove(x){this.values.delete(x)}});
const rows=[{classList:classes()},{classList:classes()}];
const links=rows.map((row,i)=>({href:`/finding-${i}.png`,textContent:'查看波形',dataset:{title:`C${i} · 1–3 秒`},closest:()=>row,addEventListener(_,fn){this.click=fn}}));
const nodes={
 'finding-image':{src:'original.png'},'finding-title':{textContent:''},'finding-status':{textContent:''},
 'finding-preview':{scrollIntoView(){this.scrolled=true}},
};
const outer={tagName:'DETAILS',open:false,parentElement:null};
const target={tagName:'DETAILS',open:false,parentElement:outer,scrollIntoView(){this.scrolled=true}};
nodes.scoring=target;
const handlers={};
const chartStatus={hidden:false}, frame={dataset:{chartSrc:'/charts?embedded=1'},style:{},contentWindow:{},getAttribute(){return this.src},addEventListener(name,fn){this[name]=fn}};
const chartSection={tagName:'DETAILS',open:false,scrollIntoView(){},querySelector(s){return s==='iframe'?frame:chartStatus},addEventListener(name,fn){this[name]=fn}};
nodes.charts=chartSection;
const chartLink={hash:'#charts',addEventListener(name,fn){this[name]=fn}};
const context={document:{querySelectorAll(s){return s==='a[href^="#"]'?[chartLink]:s==='[data-report-charts]'?[chartSection]:s==='[data-finding]'?links:rows.filter(r=>r.classList.values.has('is-selected'))},getElementById(id){return nodes[id]}},
 window:{addEventListener(name,fn){handlers[name]=fn}},location:{hash:'',origin:'http://local'},Image:class{constructor(){requests.push(this)}}};
vm.runInNewContext(fs.readFileSync('apps/workbench/web/report-interactions.js','utf8'),context);
let prevented=0;
links[0].click({preventDefault(){prevented++}});
links[1].click({preventDefault(){prevented++}});
assert.equal(prevented,2);assert.equal(requests.length,2);
requests[0].onload();assert.equal(nodes['finding-image'].src,'original.png','A late first request cannot overwrite the new selection');
requests[1].onload();assert.equal(nodes['finding-image'].src,'/finding-1.png');
assert.equal(nodes['finding-title'].textContent,'C1 · 1–3 秒');assert.equal(nodes['finding-status'].textContent,'');
assert(rows[1].classList.values.has('is-selected'));assert(!rows[0].classList.values.has('is-selected'));
links[0].click({ctrlKey:true,preventDefault(){throw Error('Must preserve new-tab action')}});assert.equal(requests.length,2);
links[0].click({preventDefault(){}});requests[2].onerror();assert(nodes['finding-status'].textContent.includes('暂不可用'));
context.location.hash='#scoring';handlers.hashchange();assert(target.open&&outer.open&&target.scrolled);
console.log('PASS selected finding image, loading/error feedback, stale request guard, new-tab action and nested anchor expansion');
assert.equal(frame.src,undefined,'Closed charts must not trigger evidence reads');
chartSection.open=true;chartSection.toggle();assert.equal(frame.src,'/charts?embedded=1');
frame.load();assert.equal(chartStatus.hidden,true);
handlers.message({origin:'http://other',source:frame.contentWindow,data:{type:'qc-chart-height',height:900}});assert.equal(frame.style.height,undefined);
handlers.message({origin:'http://local',source:{},data:{type:'qc-chart-height',height:900}});assert.equal(frame.style.height,undefined);
handlers.message({origin:'http://local',source:frame.contentWindow,data:{type:'qc-chart-height',height:900}});assert.equal(frame.style.height,'900px');
handlers.message({origin:'http://local',source:frame.contentWindow,data:{type:'qc-chart-height',height:NaN}});assert.equal(frame.style.height,'900px');
context.location.hash='#charts';chartSection.open=false;chartLink.click();assert(chartSection.open,'The same anchor must reopen a collapsed chart section');
console.log('PASS report charts load on expansion and resize only from the matching local frame');
links[0].click({preventDefault(){}});links[0].click({preventDefault(){}});
requests[3].onload();requests[4].onload();
assert.equal(links[0].textContent,'查看波形','Repeated clicks must restore the original label');
