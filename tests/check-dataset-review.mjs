// State/contract verification. This does not claim browser visual verification.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const code=fs.readFileSync(new URL('../apps/workbench/web/dataset-review.js',import.meta.url),'utf8');
const id='a'.repeat(32);
const row={id:'r1',label:'采样率',label_en:'Rates',target:'<script>target</script>',message:'<img onerror=x>',status:'conflict',disposition:'pending',evidence_id:'e1',files:[],observed:{rate:500}};
const sample={job_id:id,package_id:'p',revision:0,result_hash:'hash1',rows:[row],summary:{pending:1,findings:1,needs_fix:0,unassessed:0},outcome:'pending_review',proposed_outcome:'pending_review',history:[],engineering_demo:true};
const flush=async()=>{for(let i=0;i<60;i++)await Promise.resolve()};
function fixture(){
  const events={},calls=[],pending=[],message={textContent:'',hidden:true};
  const root={innerHTML:'',events:{},addEventListener(k,f){this.events[k]=f},querySelector(){return {scrollIntoView(){}}}};
  const context={FormData:class{constructor(form){this.form=form}get(k){return this.form.values[k]??''}},
    CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail}},
    document:{getElementById:k=>k==='dataset-review'?root:message,addEventListener(k,f){events[k]=f},dispatchEvent(e){events[e.type]?.(e)}},
    fetch:(url,options)=>new Promise(resolve=>{calls.push({url,options});pending.push((data,status=200)=>resolve({ok:status===200||status===201,status,json:async()=>data}));})};
  vm.runInNewContext(code,context);
  const emit=(overrides={})=>events['dataset-context']({detail:{job:{id,status:'completed'},package_id:'p',manifest_hash:'latest',lang:'zh-CN',tab:'review',...overrides}});
  const click=(attr,dataset={})=>root.events.click({target:{closest:()=>({disabled:false,dataset,hasAttribute:a=>a===attr})}});
  const submit=(values,finalize=false)=>{const button={disabled:false};return root.events.submit({preventDefault(){},target:{values,matches:()=>true,hasAttribute:()=>finalize,querySelector:()=>button}})};
  return {root,events,calls,pending,message,emit,click,submit};
}
let f=fixture();f.emit({tab:'overview'});assert.equal(f.calls.length,0,'Hidden review tab does not fetch');
f.emit();f.pending.shift()(sample);await flush();assert.match(f.root.innerHTML,/下载 PDF/);assert.match(f.root.innerHTML,/工程演示/);
assert.match(f.root.innerHTML,/&lt;script&gt;/);assert(!f.root.innerHTML.includes('<img onerror=x>'));
f.emit();assert.equal(f.calls.length,1,'Polling the same run does not reset a draft');
await f.click('data-review-edit',{reviewEdit:'r1'});assert.match(f.root.innerHTML,/data-review-save/);
const values={reviewer:'Tester',disposition:'needs_fix',impact:'Timing',note:'Source evidence',action:'Restore',owner:'Owner'};
let save=f.submit(values);await flush();
const sent=JSON.parse(f.calls.at(-1).options.body);
assert.equal(sent.expected_revision,0);assert.equal(sent.result_hash,'hash1');assert.equal(sent.changes[0].evidence_id,'e1');assert.equal(sent.finalize,false);
f.pending.shift()({error:'changed'},409);await save;assert.match(f.message.textContent,/复制未保存/);assert.match(f.root.innerHTML,/data-review-save/,'Conflict retains editable form');
save=f.submit(values);f.pending.shift()({...sample,revision:1,rows:[{...row,disposition:'needs_fix',decision:values}],summary:{...sample.summary,pending:0,needs_fix:1},proposed_outcome:'blocked'},201);await save;
assert.match(f.root.innerHTML,/需整改后复验/);assert.match(f.message.textContent,/已保存/);
const retest=f.click('data-review-retest');await flush();assert.deepEqual(JSON.parse(f.calls.at(-1).options.body),{package_id:'p',manifest_hash:'latest',confirmed:true,baseline_job_id:id});
let submitted=null;f.events['dataset-review-job']=e=>submitted=e.detail;
f.pending.shift()({id:'b'.repeat(32)});await retest;assert.equal(submitted.id,'b'.repeat(32));
f=fixture();f.emit();f.emit({job:{id:'c'.repeat(32),status:'completed'}});
f.pending.shift()(sample);await flush();assert(!f.root.innerHTML.includes('data-review-save'),'Old run response must not populate the new run');
f.pending.shift()({...sample,job_id:'c'.repeat(32)});await flush();assert.match(f.root.innerHTML,new RegExp('c'.repeat(32)+'/review'));
f.emit({job:{id:'c'.repeat(32),status:'completed'},lang:'en'});f.pending.shift()({...sample,job_id:'c'.repeat(32)});await flush();assert.match(f.root.innerHTML,/Review report/);assert.match(f.root.innerHTML,/Rates/);
console.log('D04 UI passed: lazy loading, evidence/version binding, save conflicts, retest submission, stale responses and language.');
