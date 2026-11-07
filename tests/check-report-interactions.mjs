// Interaction checks without browser automation or a running service.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const requests=[];
const classes=()=>({values:new Set(),add(x){this.values.add(x)},remove(x){this.values.delete(x)}});
const rows=[{classList:classes()},{classList:classes()}];
const links=rows.map((row,i)=>({href:`/finding-${i}.png`,dataset:{title:`C${i} · 1–3 秒`},closest:()=>row,addEventListener(_,fn){this.click=fn}}));
const nodes={
 'finding-image':{src:'original.png'},'finding-title':{textContent:''},'finding-status':{textContent:''},
 'finding-preview':{scrollIntoView(){this.scrolled=true}},
};
const outer={tagName:'DETAILS',open:false,parentElement:null};
const target={tagName:'DETAILS',open:false,parentElement:outer,scrollIntoView(){this.scrolled=true}};
nodes.scoring=target;
const handlers={};
const context={document:{querySelectorAll(s){return s==='[data-finding]'?links:rows.filter(r=>r.classList.values.has('is-selected'))},getElementById(id){return nodes[id]}},
 window:{addEventListener(name,fn){handlers[name]=fn}},location:{hash:''},Image:class{constructor(){requests.push(this)}}};
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
