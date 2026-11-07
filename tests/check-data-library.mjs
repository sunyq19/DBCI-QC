import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../apps/workbench/web/data-library.js',import.meta.url),'utf8');
const nodes=new Map(),events={};let language='zh-CN',requests=[];
const element=id=>{if(!nodes.has(id))nodes.set(id,{value:'',events:{},attrs:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.events[k]=v}});return nodes.get(id)};
const window={QCI18n:{getLanguage:()=>language},addEventListener(k,v){events[k]=v}};
const context={URL,window,document:{getElementById:element},fetch:()=>new Promise(resolve=>requests.push(resolve))};
vm.runInNewContext(source,context);
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve()};
const item=(id,extra={})=>({id,kind:'record',label:id,url:'/?input='+id,available:true,status:'not_run',...extra});
const data=[item('x',{label:'<img onerror="bad()">',url:'https://bad.test',format:'<script>'}),item('set',{kind:'dataset',url:'/datasets?package=p',subjects:2,records:5}),...Array.from({length:8},(_,i)=>item('record'+i))];
requests.shift()({ok:true,json:async()=>({items:data})});await flush();
assert.match(element('data-library-list').innerHTML,/&lt;img/);assert(!element('data-library-list').innerHTML.includes('<img'));assert(!element('data-library-list').innerHTML.includes('<script>'));assert.match(element('data-library-list').innerHTML,/&lt;script&gt;/);
assert(!element('data-library-list').innerHTML.includes('https://bad.test'));assert.match(element('data-library-list').innerHTML,/href="#"/);
assert.equal((element('data-library-list').innerHTML.match(/class="data-library-item/g)||[]).length,6);
assert.equal(element('data-library-more').hidden,false);
element('data-library-more').events.click();assert.equal((element('data-library-list').innerHTML.match(/class="data-library-item/g)||[]).length,10);
element('data-search').value='dataset';element('data-search').events.input();assert.match(element('data-library-list').innerHTML,/set/);assert(!element('data-library-list').innerHTML.includes('record0'));
language='en';events['qc:languagechange']();assert.match(element('data-library-list').innerHTML,/Dataset/);assert.match(element('data-library-list').innerHTML,/lang=en/);
element('data-search').value='';element('data-search').events.input();
const first=window.QCDataLibrary.refresh(),second=window.QCDataLibrary.refresh();
requests[1]({ok:true,json:async()=>({items:[item('newest')]})});await second;
requests[0]({ok:true,json:async()=>({items:[item('stale')]})});await first;
assert.match(element('data-library-list').innerHTML,/newest/);assert(!element('data-library-list').innerHTML.includes('stale'));
// Validation cases are explicit, not selected by outcome; normal failures stay visible.
const req=window.QCDataLibrary.refresh();requests.at(-1)({ok:true,json:async()=>({items:[
 item('ordinary-failure',{status:'failed',latest_run_url:'/?job=failed'}),
 item('ordinary-report',{status:'completed',latest_run_url:'/?job=report'}),
 item('injected-case',{category:'validation',status:'completed'})],
 examples:[{kind:'record',label:'<sample>',label_en:'Sample report',url:'/?job=report',score:88.51,scope:'recording',duration_seconds:281.66},
 {kind:'dataset',label:'<sample>',label_en:'Dataset demo',description:'双个体记录',description_en:'Two participants',formats:'EDF',url:'/datasets?package=demo',subjects:2,records:2,reported:1,available:true},
 {kind:'dataset',label:'未运行',label_en:'Ready to run',url:'/datasets?package=new',subjects:1,records:2,reported:0,available:true},
 {kind:'dataset',label:'缺文件',label_en:'Missing files',url:'/datasets?package=gone',subjects:1,records:1,reported:0,available:false}]})});await req;
assert.match(element('data-library-list').innerHTML,/ordinary-failure/);
assert.match(element('data-library-list').innerHTML,/job=report/);
assert(!element('data-library-list').innerHTML.includes('injected-case'));
assert(!element('demo-report-list').innerHTML.includes('88.51'));
assert.match(element('demo-report-list').innerHTML,/Reports 1\/2/);
assert.match(element('demo-report-list').innerHTML,/Reports 0\/2/);
assert.match(element('demo-report-list').innerHTML,/Open dataset/);
assert(!element('demo-report-list').innerHTML.includes('href="/datasets?package=gone'));
assert.match(element('demo-report-list').innerHTML,/aria-disabled="true"/);
assert.equal(element('demo-reports').hidden,false);
element('library-validation').events.click();
assert.match(element('data-library-list').innerHTML,/injected-case/);assert(!element('data-library-list').innerHTML.includes('ordinary-failure'));
assert.equal(element('library-category-note').hidden,false);
language='zh-CN';events['qc:languagechange']();assert.match(element('demo-report-list').innerHTML,/&lt;sample&gt;/);assert(!element('demo-report-list').innerHTML.includes('试行评分'));assert.match(element('demo-reports-title').textContent,/示例数据集/);assert.match(element('demo-report-list').innerHTML,/报告 1\/2/);
const missing=window.QCDataLibrary.refresh();requests.at(-1)({ok:true,json:async()=>({items:[],examples:[]})});await missing;assert.equal(element('demo-reports').hidden,true);
console.log('Data library: escaping, local links, search, pagination, language and stale responses passed. No jobs submitted.');
