// Exercise page state transitions without browser access or a live HTTP service.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const root = new URL('../apps/workbench/web/', import.meta.url);
const html = fs.readFileSync(new URL('datasets.html', root), 'utf8');
const source = fs.readFileSync(new URL('datasets.js', root), 'utf8');
const ids = [...html.matchAll(/id="([^"]+)"/g)].map(m=>m[1]);
assert.equal(new Set(ids).size, ids.length);
const pack = id=>({id,label:id,available:true,subjects:2,records:4,files:12,scope:'selected only',manifest_hash:'hash-'+id,groups:[]});
const check={id:'check1',module:'D02',code:'rates',label:'采样率',label_en:'Sampling rates',status:'conflict',target:'<img onerror=alert(1)>',message:'evidence',files:['<script>'],observed:{rate:500}};
const attention={id:'rates-conflict',code:'rates',record_ids:['r1'],record_count:1,check_ids:['check1'],title:'采样率记录不一致',title_en:'Sampling-rate descriptions differ',meaning:'文件与配套表的描述不同。',meaning_en:'Descriptions differ.',next_step:'核对采集记录。',next_step_en:'Verify source records.',owner:'数据提供方',owner_en:'Data provider',unit_labels:[]};
const recordRows=[{id:'r1',subject:'sub-01',session:'none',path:'sub-01/run.edf',modality:'scalp_eeg',processing:'raw',checks:{conflict:1},signal:{status:'not_run'}},{id:'r2',subject:'sub-02',session:'s2',path:'sub-02/run.edf',modality:'ecog',processing:'raw',checks:{},signal:{status:'not_run'}}];
function result(id,assessed=false,historical=false){return {package_id:id,current_manifest:!historical,scope:'selected only',comparison_groups:[],
  dataset_job:assessed?{id:'a'.repeat(32),status:'completed',created_at:'2026-11-06'}:null,
  summary:{subjects:2,records:2,expected_files:12,file_counts:assessed?{present:12}:null,dataset_assessed:assessed,findings:assessed?{conflict:1}:{},reported:0,full_duration_computed:0,signal_status_counts:{not_run:2}},module_counts:{},attention_groups:assessed?[attention]:[],
  subjects:recordRows.map(r=>({id:r.subject,records:1,findings:r.checks.conflict||0,reported:0,not_run:1})),records:recordRows,checks:assessed?[check]:[]};}
function fixture(admissionPolicy=null,search=''){
  const element=(dataset={})=>({dataset,innerHTML:'',textContent:'',disabled:false,hidden:false,checked:false,value:'',attrs:{},events:{},
    setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.events[k]=v},querySelectorAll(){return []}});
  const nodes=new Map([...ids,'dataset-refresh'].map(id=>[id,element()]));
  const langs=[element({lang:'zh-CN'}),element({lang:'en'})];
  const textNodes=[...html.matchAll(/data-text="([^"]+)"/g)].map(m=>element({text:m[1]}));
  let finishPost;const requests=[];
  const context={URLSearchParams,location:{search},localStorage:{getItem:()=>null,setItem:()=>{}},
    document:{documentElement:{},getElementById:id=>{assert(nodes.has(id),id);return nodes.get(id)},querySelectorAll:selector=>selector==='[data-lang]'?langs:textNodes},
    history:{replaceState(...args){context.url=args[2]}},clearTimeout(){},setTimeout(){},
    fetch:async(url,options)=>{requests.push({url,options});let value;
      if(url.includes('/batches?'))value={batches:[]};
      else if(url.endsWith('/records'))value={manifest_hash:'hash-'+url.split('/').at(-2),records:[{id:'r1',subject:'sub-01',session:'none',path:'sub-01/run.edf',modality:'scalp_eeg',available:true,signal_runs:[]},{id:'r2',subject:'sub-02',session:'s2',path:'sub-02/run.edf',modality:'ecog',available:false,signal_runs:[]}]};
      else if(url.endsWith('/packages'))value={packages:[pack('A'),pack('B')],jobs:[],admission_policy:admissionPolicy};
      else if(options.method==='POST')value=await new Promise(resolve=>{finishPost=resolve});
      else if(url.includes('/overview'))value=result(url.split('/')[4],url.includes('?job='),search.includes('job='));
      else value={id:'a'.repeat(32),package_id:'A',status:'completed',manifest_hash:'hash-A',created_at:'2026-11-06',modules:[]};
      return {ok:true,json:async()=>value};}};
  vm.runInNewContext(source,context);
  return {nodes,langs,requests,context,resolvePost:value=>finishPost(value)};
}
const flush=async()=>{for(let i=0;i<80;i++)await Promise.resolve()};
let f=fixture();await flush();
assert.equal(f.nodes.get('package-admission-limits').hidden,true,'Local dataset mode has no cloud dataset restriction');
assert.equal(f.nodes.get('package-run').disabled,true,'Unconfirmed scope cannot start');
f.nodes.get('package-confirm').checked=true;f.nodes.get('package-confirm').events.change();
assert.equal(f.nodes.get('package-run').disabled,false);
let run=f.nodes.get('package-run').events.click();await flush();
const body=JSON.parse(f.requests.at(-1).options.body);
assert.deepEqual(body,{package_id:'A',manifest_hash:'hash-A',confirmed:true});
f.resolvePost({id:'a'.repeat(32)});await run;await flush();
assert.match(f.nodes.get('dataset-result').innerHTML,/汇总报告/);
assert.match(f.nodes.get('dataset-checks').innerHTML,/&lt;img/);
assert(!f.nodes.get('dataset-checks').innerHTML.includes('<script>'));
assert.match(f.nodes.get('dataset-result').innerHTML,/采样率记录不一致/);
assert.match(f.nodes.get('dataset-result').innerHTML,/数据提供方/);
assert(!f.nodes.get('dataset-result').innerHTML.includes('资料冲突'));
f.nodes.get('dataset-result').events.click({target:{closest:s=>s==='[data-attention]'?{dataset:{attention:'rates-conflict'}}:null}});
assert(f.nodes.get('package-records').innerHTML.includes('sub-01/run.edf'));
assert(!f.nodes.get('package-records').innerHTML.includes('sub-02/run.edf'),'Issue action filters only affected recordings');
f.nodes.get('package-records').events.click({target:{closest:s=>s==='[data-clear-issue]'?{}:null}});
assert(f.nodes.get('package-records').innerHTML.includes('sub-02/run.edf'));
f.nodes.get('dataset-result').events.click({target:{closest:s=>s==='[data-evidence]'?{dataset:{evidence:'rates-conflict'}}:null}});
assert.equal(f.nodes.get('dataset-details').open,true);
f.langs[1].events.click();assert.match(f.nodes.get('dataset-result').innerHTML,/Summary report/);
assert.match(f.nodes.get('dataset-checks').innerHTML,/Sampling rates/);
f=fixture();await flush();f.nodes.get('package-confirm').checked=true;
run=f.nodes.get('package-run').events.click();await flush();
f.nodes.get('package-select').value='B';f.nodes.get('package-select').events.change();
f.resolvePost({id:'a'.repeat(32)});await run;await flush();
assert.equal(f.nodes.get('package-select').value,'B','Late POST response must not switch selected package');
assert.equal(f.nodes.get('dataset-result').hidden,false);
assert.equal(f.nodes.get('dataset-breadcrumb').textContent,'B');
assert.match(f.nodes.get('dataset-result').innerHTML,/尚未完成/);
assert.equal(f.nodes.get('package-confirm').checked,false);
assert.equal(f.requests.filter(r=>r.url.includes('/package-jobs/')).length,0,'Stale response is not loaded');
f=fixture({max_record_bytes:536870912,max_dataset_bytes:5368709120,max_records:100,max_files:5000});await flush();
assert.equal(f.nodes.get('package-admission-limits').hidden,false);
assert.match(f.nodes.get('package-admission-limits').textContent,/512 MiB.*5 GiB.*100.*5000/);
f.langs[1].events.click();assert.match(f.nodes.get('package-admission-limits').textContent,/Cloud limit validation/);
f=fixture({max_record_bytes:1073741824,max_dataset_bytes:5368709120,max_records:100,max_files:5000});await flush();
assert.match(f.nodes.get('package-admission-limits').textContent,/每记录 1 GiB.*数据集 5 GiB/);
f=fixture({max_record_bytes:2147483648,max_dataset_bytes:5368709120,max_records:100,max_files:5000});await flush();
assert.match(f.nodes.get('package-admission-limits').textContent,/每记录 2 GiB.*数据集 5 GiB/);
f.langs[1].events.click();assert.match(f.nodes.get('package-admission-limits').textContent,/2 GiB per record/);
f=fixture({max_record_bytes:2147483648,max_dataset_bytes:10737418240,max_records:100,max_files:5000});await flush();
assert.match(f.nodes.get('package-admission-limits').textContent,/每记录 2 GiB.*数据集 10 GiB/);
f.langs[1].events.click();assert.match(f.nodes.get('package-admission-limits').textContent,/10 GiB/);
f=fixture();await flush();
assert.equal(f.nodes.get('package-record-browser').hidden,false);
assert.match(f.nodes.get('package-records').innerHTML,/sub-01\/run.edf/);
assert(f.nodes.get('package-records').innerHTML.includes('sub-02/run.edf'),'All subjects are visible by default');
f.nodes.get('package-subject').value='sub-02';f.nodes.get('package-subject').events.change();
assert.match(f.nodes.get('package-records').innerHTML,/sub-02\/run.edf/);
assert.match(f.nodes.get('package-records').innerHTML,/disabled/);
f.nodes.get('package-subject').value='sub-01';f.nodes.get('package-subject').events.change();
let opening=f.nodes.get('package-records').events.click({target:{closest:selector=>selector==='[data-open-record]'?{dataset:{openRecord:'r1'},disabled:false}:null}});await flush();
assert.deepEqual(JSON.parse(f.requests.at(-1).options.body),{package_id:'A',record_id:'r1',manifest_hash:'hash-A'});
f.resolvePost({id:'c'.repeat(32)});await opening;
assert.equal(f.context.location.href,'/?intake='+'c'.repeat(32)+'&lang=zh-CN');
f=fixture();await flush();
opening=f.nodes.get('package-records').events.click({target:{closest:selector=>selector==='[data-open-record]'?{dataset:{openRecord:'r1'},disabled:false}:null}});await flush();
f.nodes.get('package-select').value='B';f.nodes.get('package-select').events.change();await flush();
f.resolvePost({id:'d'.repeat(32)});await opening;
assert.equal(f.context.location.href,undefined,'Stale record opening cannot redirect another dataset');
console.log('Dataset UI state checks passed: confirmation, submit, result, escaping, language and stale response. No browser or network used.');

f=fixture(null,'?job='+'a'.repeat(32));await flush();
assert.match(f.nodes.get('dataset-result').innerHTML,/历史清单/);
assert.match(f.nodes.get('package-records').innerHTML,/disabled/);
assert.match(f.nodes.get('dataset-result').innerHTML,/download=1/);
assert.equal(f.requests.filter(r=>r.options.method==='POST').length,0,'Navigation never submits jobs');

assert(html.indexOf('id="dataset-result"')<html.indexOf('class="panel dataset-flow-panel"'),'Results precede implementation flow');
assert.match(html,/<details id="dataset-details"[^>]*hidden>/);
assert(!/<details id="dataset-details"[^>]*\bopen\b/.test(html));
console.log('Action-first layout and issue-to-record/evidence navigation passed.');

assert.match(fs.readFileSync(new URL('../apps/workbench/web/datasets.js',import.meta.url),'utf8'), /<details class="attention-item"><summary/);
console.log('Dataset issue names remain visible while their explanations are opt-in.');
