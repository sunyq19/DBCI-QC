// Read-only report interaction tests. No browser or visual verification is implied.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../src/ephys_qc/dataset_qc/review_report_web.py',import.meta.url),'utf8');
const code=source.match(/SCRIPT = r'''([\s\S]*?)'''/)[1];
class Element{
  constructor(dataset={}){this.dataset=dataset;this.hidden=false;this.attrs={};this.focused=false;}
  setAttribute(k,v){this.attrs[k]=v;}focus(){this.focused=true;}scrollIntoView(){this.scrolled=true;}
  closest(selector){return selector===this.selector?this:selector==='[data-inspector]'?this.parent:null;}
}
function workspace(withRows=true){
  const tabs=['findings','retest','records','run'].map(tab=>new Element({tab}));
  tabs.forEach(e=>e.selector='[data-tab]');
  const panels=tabs.map(e=>new Element({panel:e.dataset.tab}));
  const filters=['attention','unassessed','all'].map(filter=>new Element({filter}));
  filters.forEach(e=>e.selector='[data-filter]');
  const rows=withRows?[new Element({group:'F01',status:'conflict'}),new Element({group:'F02',status:'unassessed'})]:[];
  rows.forEach(e=>e.selector='[data-group]');
  const inspectors=rows.map(r=>new Element({inspector:r.dataset.group}));
  const evidence=[new Element({recordEvidence:'F02-0'}),new Element({recordEvidence:'F02-1'})];
  const select=new Element({recordSelect:'F02'});select.selector='[data-record-select]';select.value='F02-0';select.parent=inspectors[1];
  if(inspectors[1])inspectors[1].querySelectorAll=()=>evidence;
  const empty=new Element(),listeners={};
  const lookups={'[data-tab]':tabs,'[data-panel]':panels,'[data-filter]':filters,'[data-group]':rows,'[data-inspector]':inspectors,'[data-record-select]':withRows?[select]:[]};
  const app={classList:{remove(){},add(){}},querySelectorAll:s=>lookups[s],addEventListener:(event,fn)=>listeners[event]=fn};
  vm.runInNewContext(code,{document:{getElementById:id=>id==='dataset-report'?app:empty},matchMedia:()=>({matches:true})});
  const click=target=>listeners.click({target,preventDefault(){}});
  return {tabs,panels,filters,rows,inspectors,evidence,select,empty,listeners,click};
}
let w=workspace();
assert.deepEqual(w.rows.map(r=>r.hidden),[false,true]);
assert.deepEqual(w.inspectors.map(r=>r.hidden),[false,true]);
assert.deepEqual(w.panels.map(r=>r.hidden),[false,true,true,true]);
w.click(w.filters[1]);
assert.deepEqual(w.rows.map(r=>r.hidden),[true,false]);
assert.deepEqual(w.inspectors.map(r=>r.hidden),[true,false]);
assert.deepEqual(w.evidence.map(r=>r.hidden),[false,true]);
w.select.value='F02-1';w.listeners.change({target:w.select});
assert.deepEqual(w.evidence.map(r=>r.hidden),[true,false]);
w.click(w.filters[2]);w.click(w.rows[0]);
assert.equal(w.inspectors[0].hidden,false);assert.equal(w.inspectors[0].scrolled,true);
w.click(w.tabs[1]);assert.deepEqual(w.panels.map(r=>r.hidden),[true,false,true,true]);
w.listeners.keydown({target:w.tabs[1],key:'End',preventDefault(){}});
assert.equal(w.tabs[3].focused,true);assert.equal(w.panels[3].hidden,false);
w=workspace(false);assert.equal(w.empty.hidden,false);
console.log('Dataset report: filtering, selection, evidence switching, keyboard tabs and empty result passed.');
