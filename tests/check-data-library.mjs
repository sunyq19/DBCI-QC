import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../apps/workbench/web/data-library.js',import.meta.url),'utf8');
const nodes=new Map(),events={};let language='zh-CN',requests=[];
const element=id=>{if(id==='data-library-refresh')return null;if(!nodes.has(id))nodes.set(id,{value:'',events:{},dataset:{},attrs:{},removeAttribute(k){delete this.attrs[k]},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.events[k]=v}});return nodes.get(id)};
const window={QCI18n:{getLanguage:()=>language},addEventListener(k,v){events[k]=v}};
const context={URL,setTimeout:()=>1,clearTimeout(){},window,document:{getElementById:element},fetch:()=>new Promise(resolve=>requests.push(resolve))};
vm.runInNewContext(source,context);
const flush=async()=>{for(let i=0;i<10;i++)await Promise.resolve()};
// A failed initial request must not leave a permanent loading indicator.
element('data-library-list').innerHTML='<p>正在加载数据…</p>';
requests.shift()({ok:false});await flush();
assert.equal(element('data-library-list').innerHTML,'');
assert.equal(element('data-library-error').hidden,false);
assert.equal(element('data-library-more').hidden,true);
window.QCDataLibrary.refresh();
const item=(id,extra={})=>({id,kind:'record',label:id,url:'/?input='+id,available:true,status:'not_run',...extra});
const data=[item('x',{label:'<img onerror="bad()">',url:'https://bad.test',format:'<script>'}),item('set',{kind:'dataset',url:'/datasets?package=p',subjects:2,records:5}),...Array.from({length:8},(_,i)=>item('record'+i))];
requests.shift()({ok:true,json:async()=>({items:data})});await flush();
assert.match(element('data-library-list').innerHTML,/&lt;img/);assert(!element('data-library-list').innerHTML.includes('<img'));assert(!element('data-library-list').innerHTML.includes('<script>'));assert.match(element('data-library-list').innerHTML,/&lt;script&gt;/);
assert(!element('data-library-list').innerHTML.includes('https://bad.test'));assert.match(element('data-library-list').innerHTML,/href="#"/);
assert.equal((element('data-library-list').innerHTML.match(/class="data-library-item/g)||[]).length,6);
assert.equal(element('data-library-more').hidden,false);
// A later outage preserves the previously loaded directory.
const loadedMarkup=element('data-library-list').innerHTML;
const laterFailure=window.QCDataLibrary.refresh();requests.shift()({ok:false});await laterFailure;
assert.equal(element('data-library-list').innerHTML,loadedMarkup);
assert.equal(element('data-library-error').hidden,false);
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
 {kind:'dataset',label:'<sample>',label_en:'Dataset demo',description:'双个体记录',description_en:'Two participants',formats:'EDF',url:'/api/v1/packages/demo/overview/report',subjects:2,records:2,reported:1,available:true},
 {kind:'dataset',label:'未运行',label_en:'Ready to run',url:'/datasets?package=new',subjects:1,records:2,reported:0,available:true},
 {kind:'dataset',label:'缺文件',label_en:'Missing files',url:'/datasets?package=gone',subjects:1,records:1,reported:0,available:false}]})});await req;
assert.match(element('data-library-list').innerHTML,/ordinary-failure/);
assert.match(element('data-library-list').innerHTML,/input=ordinary-report/);
assert(!element('data-library-list').innerHTML.includes('injected-case'));
assert(!element('demo-report-list').innerHTML.includes('88.51'));
assert.match(element('demo-report-list').innerHTML,/Reports 1\/2/);
assert.match(element('demo-report-list').innerHTML,/Reports 0\/2/);
assert.match(element('demo-report-list').innerHTML,/View report/);
assert.match(element('demo-report-list').innerHTML,/href="\/api\/v1\/packages\/demo\/overview\/report\?lang=en"/);
assert(!element('demo-report-list').innerHTML.includes('href="/datasets?package=gone'));
assert.match(element('demo-report-list').innerHTML,/aria-disabled="true"/);
assert.equal(element('demo-reports').hidden,false);
element('library-validation').events.click();
assert.match(element('data-library-list').innerHTML,/injected-case/);assert(!element('data-library-list').innerHTML.includes('ordinary-failure'));
assert.equal(element('library-category-note').hidden,false);
language='zh-CN';events['qc:languagechange']();assert.match(element('demo-report-list').innerHTML,/&lt;sample&gt;/);assert(!element('demo-report-list').innerHTML.includes('试行评分'));assert.match(element('demo-reports-title').textContent,/示例数据集/);assert.match(element('demo-report-list').innerHTML,/报告 1\/2/);
const missing=window.QCDataLibrary.refresh();requests.at(-1)({ok:true,json:async()=>({items:[],examples:[]})});await missing;assert.equal(element('demo-reports').hidden,true);
console.log('Data library: escaping, local links, search, pagination, language and stale responses passed. No jobs submitted.');

assert.match(element('data-library-list').innerHTML, /No uploads yet|尚未上传数据/);
// Cached examples render synchronously, even if personal data never respond.
const cachedNodes=new Map(),cachedEvents={};let resolvePrivate;
const cachedElement=id=>{if(id==='data-library-refresh')return null;if(!cachedNodes.has(id))cachedNodes.set(id,{value:'',events:{},dataset:{},removeAttribute(){},setAttribute(){},addEventListener(k,v){this.events[k]=v}});return cachedNodes.get(id)};
const frozen={schema_version:'example-cache/1',examples:[{kind:'dataset',label:'缓存 EEG',label_en:'Cached EEG',subjects:2,records:2,reported:2,available:true,url:'/examples/0123456789abcdef/datasets/eeg.zh-CN.html',url_en:'/examples/0123456789abcdef/datasets/eeg.en.html'}]};
cachedElement('example-cache').textContent=JSON.stringify(frozen);
let cacheLanguage='zh-CN';
const cachedWindow={QCI18n:{getLanguage:()=>cacheLanguage},addEventListener(k,v){cachedEvents[k]=v}};
vm.runInNewContext(source,{URL,setTimeout:()=>1,clearTimeout(){},window:cachedWindow,document:{getElementById:cachedElement},fetch:()=>new Promise(resolve=>resolvePrivate=resolve)});
assert.match(cachedElement('demo-report-list').innerHTML,/缓存 EEG/);
assert.match(cachedElement('demo-report-list').innerHTML,/href="\/examples\/0123456789abcdef\/datasets\/eeg.zh-CN.html/);
resolvePrivate({ok:false});await flush();
assert.match(cachedElement('demo-report-list').innerHTML,/缓存 EEG/);
assert.equal(cachedElement('data-library-list').innerHTML,'');
cachedWindow.QCDataLibrary.refresh();
resolvePrivate({ok:true,json:async()=>({items:[],examples:[]})});await flush();
assert.match(cachedElement('demo-report-list').innerHTML,/缓存 EEG/);
cacheLanguage='en';cachedEvents['qc:languagechange']();
assert.match(cachedElement('demo-report-list').innerHTML,/eeg.en.html/);
console.log('Published cache renders before fetch and survives failed or empty personal responses.');

// Completed alternatives are children of the original data, not example links.
language='zh-CN';element('library-data').events.click();
const personal=window.QCDataLibrary.refresh();
const recent=[['a'.repeat(32),'推荐方案','Recommended workflow'],['b'.repeat(32),'灵犀云方案','Gnosis workflow']].map(([id,label,label_en])=>({
  job_id:id,label,label_en,created_at:'2026-11-07T04:27:00Z',url:`/api/v1/jobs/${id}/report`,visualizations_url:`/api/v1/jobs/${id}/visualizations`}));
requests.at(-1)({ok:true,json:async()=>({items:[item('eeg',{status:'completed',recent_reports:recent})],examples:[]})});await personal;
let grouped=element('data-library-list').innerHTML;
assert.equal((grouped.match(/class="data-library-item/g)||[]).length,1);
assert.equal((grouped.match(/class="library-report-row/g)||[]).length,2);
assert.match(grouped,/推荐方案/);assert.match(grouped,/灵犀云方案/);
assert(!grouped.includes('Recommended workflow'));assert(!grouped.includes('/examples/'));
for(const row of recent){assert(grouped.includes(row.url+'?lang=zh-CN'));assert(!grouped.includes(row.visualizations_url));assert(grouped.includes(`href="/?configure=${row.job_id}&amp;lang=zh-CN"`));}
assert.equal((grouped.match(/class="library-report-name library-config-link"/g)||[]).length,2);
assert(!grouped.includes('data-library-actions'));
assert(!grouped.includes('打开数据'));
assert.match(grouped,/href="\/\?input=eeg&amp;lang=zh-CN"/);
language='en';events['qc:languagechange']();grouped=element('data-library-list').innerHTML;
assert.match(grouped,/Recommended workflow/);assert(!grouped.includes('推荐方案'));
console.log('Personal data groups saved reports and charts, with one active language.');

// Data -> configuration -> runs: repeated runs do not create duplicate schemes.
language='zh-CN';
const hierarchy=window.QCDataLibrary.refresh();
const current={...recent[0],report_available:true,status:'completed'};
const previous={...current,job_id:'c'.repeat(32),label:'此前运行',url:`/api/v1/jobs/${'c'.repeat(32)}/report`};
const workflows=[
 {id:'basic',label:'基础方案',label_en:'Basic workflow',method_family:'basic',scope:'recording',duration_seconds:61,channels:64,scored_items:3,current_confirmation:true,latest:current,runs:[current,previous]},
 {id:'failed',label:'<old config>',label_en:'Old config',method_family:'basic',scope:'window',current_confirmation:true,latest:{...previous,status:'failed',report_available:false},runs:[previous]},
 {id:'gnosis',label:'灵犀云方案',label_en:'Gnosis workflow',method_family:'gnosis',scope:'recording',duration_seconds:61,channels:64,scored_items:5,current_confirmation:true,latest:{...recent[1],report_available:true,status:'completed'},runs:[recent[1]]}
];
requests.at(-1)({ok:true,json:async()=>({items:[item('paired',{workflow_groups:workflows})]})});await hierarchy;
const hierarchyHtml=element('data-library-list').innerHTML;
assert.equal((hierarchyHtml.match(/class="data-library-item/g)||[]).length,1);
assert.match(hierarchyHtml,/3 套方案 · 4 次运行/);
assert.match(hierarchyHtml,/历次运行/);
assert.match(hierarchyHtml,/3 项计分/);
const firstLayer=hierarchyHtml.split('<details class="library-more-workflows">')[0];
assert.match(firstLayer,/基础方案/);assert.match(firstLayer,/灵犀云方案/);
assert(!firstLayer.includes('old config'));
assert.match(hierarchyHtml,/&lt;old config&gt;/);
assert.match(hierarchyHtml,/查看运行/);
assert(!hierarchyHtml.includes('workflow:'));
console.log('Workflow grouping keeps alternative routes visible and previous runs expandable.');

// Non-public installations retain the existing persistent server archive.
const archiveNodes=new Map(),archiveEvents={},archiveRequests=[];let confirmationAccepted=false,confirmations=[];
const browserValues=new Map();
const localStorage={getItem:key=>browserValues.get(key)||null,setItem:(key,value)=>browserValues.set(key,value)};
const archiveElement=id=>{if(!archiveNodes.has(id))archiveNodes.set(id,{value:'',events:{},dataset:{},attrs:{},setAttribute(k,v){this.attrs[k]=v},addEventListener(k,v){this.events[k]=v}});return archiveNodes.get(id)};
const archiveWindow={localStorage,QCI18n:{getLanguage:()=> 'zh-CN'},addEventListener(k,v){archiveEvents[k]=v},confirm(message){confirmations.push(message);return confirmationAccepted}};
vm.runInNewContext(source,{URL,setTimeout:()=>1,clearTimeout(){},window:archiveWindow,document:{getElementById:archiveElement},fetch:(url,options)=>new Promise(resolve=>archiveRequests.push({url,body:options?.body?JSON.parse(options.body):null,resolve}))});
const archiveFixture=[item('record:a',{label:'保留的数据'}),item('record:b',{label:'归档的数据',archived:true,recent_reports:[{label:'已存报告',url:'/api/v1/jobs/'+ 'b'.repeat(32)+'/report'}]})];
archiveRequests.shift().resolve({ok:true,json:async()=>({items:archiveFixture})});await flush();
assert.match(archiveElement('data-library-list').innerHTML,/保留的数据/);
assert(!archiveElement('data-library-list').innerHTML.includes('归档的数据'));
assert.equal(archiveElement('data-library-count').textContent,'1');
assert.match(archiveElement('library-archived').textContent,/归档 · 1/);
archiveElement('library-archived').events.click();
assert.match(archiveElement('data-library-list').innerHTML,/归档的数据/);
assert.match(archiveElement('data-library-list').innerHTML,/data-library-action="restore"/);
assert.match(archiveElement('data-library-list').innerHTML,/data-library-action="delete"/);
assert(!archiveElement('data-library-list').innerHTML.includes('<a class="data-library-label"'));
assert.equal(archiveElement('library-empty-archive').hidden,false);
archiveElement('library-empty-archive').events.click();
let action=archiveRequests.shift();assert.equal(action.url,'/api/v1/data/delete-preview');assert.equal(action.body.all_archived,true);
action.resolve({ok:true,json:async()=>({items:1,labels:['归档的数据'],runs:3,token:'saved-preview'})});await flush();
assert.equal(archiveRequests.length,0);assert.match(confirmations[0],/3 次检查/); // Cancel sends no deletion.
confirmationAccepted=true;archiveElement('library-empty-archive').events.click();
action=archiveRequests.shift();action.resolve({ok:true,json:async()=>({items:1,labels:['归档的数据'],runs:3,token:'saved-preview'})});await flush();
action=archiveRequests.shift();assert.equal(action.url,'/api/v1/data/delete');assert.equal(action.body.token,'saved-preview');assert.equal(action.body.confirmed,true);
action.resolve({ok:true,json:async()=>({status:'deleted',input_ids:['b']})});await flush();
action=archiveRequests.shift();assert.equal(action.url,'/api/v1/data');action.resolve({ok:true,json:async()=>({items:archiveFixture.slice(0,1)})});await flush();
assert.match(archiveElement('data-library-list').innerHTML,/归档为空/);assert.equal(archiveElement('library-empty-archive').hidden,true);
archiveElement('library-active').events.click();
const archiveClick=()=>archiveElement('data-library-list').events.click({preventDefault(){},target:{closest:()=>({dataset:{libraryAction:'archive',id:'record:a'}})}});
archiveClick();action=archiveRequests.shift();assert.equal(action.url,'/api/v1/data/archive');assert.equal(action.body.ids[0],'record:a');
action.resolve({ok:false,json:async()=>({error:'数据仍有检查在运行'})});await flush();
assert.match(archiveElement('data-library-error').textContent,/运行/);assert.match(archiveElement('data-library-list').innerHTML,/保留的数据/);
console.log('Archive tabs, report access, exact delete preview, confirmation cancellation, server errors and independent active data passed.');

// The smallest archive unit is one saved run, including a workflow's history.
const aRun={...recent[0],archive_id:'report:'+recent[0].job_id,archived:false,status:'completed'};
const bRun={...recent[1],archive_id:'report:'+recent[1].job_id,archived:true,status:'completed'};
const cRun={...aRun,job_id:'c'.repeat(32),archive_id:'report:'+'c'.repeat(32),label:'更早的独立报告',archived:false,url:'/api/v1/jobs/'+'c'.repeat(32)+'/report'};
const partial={...item('record:partial',{label:'同一份 EEG'}),archived_reports:1,active_reports:2,workflow_groups:[
 {id:'same-workflow',label:bRun.label,label_en:bRun.label_en,method_family:'basic',latest:bRun,runs:[bRun,aRun,cRun]}
]};
const partialRefresh=archiveWindow.QCDataLibrary.refresh();
archiveRequests.shift().resolve({ok:true,json:async()=>({items:[partial]})});await partialRefresh;
let partialHtml=archiveElement('data-library-list').innerHTML;
assert(partialHtml.includes(aRun.url));assert(partialHtml.includes(cRun.url));assert(!partialHtml.includes(bRun.url));
assert(partialHtml.includes(`/?configure=${cRun.job_id}&amp;lang=zh-CN`));
assert.match(partialHtml,/data-id="report:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/);
assert.match(partialHtml,/历次运行/);
assert.equal(archiveElement('data-library-count').textContent,'1');
archiveElement('library-archived').events.click();
partialHtml=archiveElement('data-library-list').innerHTML;
assert(partialHtml.includes(bRun.url));assert(!partialHtml.includes(aRun.url));assert(!partialHtml.includes(cRun.url));
assert.match(partialHtml,/同一份 EEG/);assert.match(partialHtml,/data-library-action="restore" data-id="report:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"/);
const clickPartial=(action,id,group=false)=>archiveElement('data-library-list').events.click({preventDefault(){},target:{closest:()=>({dataset:{libraryAction:action,id,...group?{libraryGroup:'true'}:{}}})}});
// Group restore in a partial archive acts on just that group's archived reports.
clickPartial('restore',partial.id,true);action=archiveRequests.shift();
assert.equal(action.url,'/api/v1/data/restore');assert.deepEqual(action.body.ids,[bRun.archive_id]);
action.resolve({ok:true,json:async()=>({status:'restored',job_ids:[bRun.job_id],input_ids:[]})});await flush();
action=archiveRequests.shift();action.resolve({ok:true,json:async()=>({items:[partial]})});await flush();
// Deleting a report previews only its results, not its source data or siblings.
confirmationAccepted=false;clickPartial('delete',bRun.archive_id);action=archiveRequests.shift();
assert.deepEqual(action.body.ids,[bRun.archive_id]);
action.resolve({ok:true,json:async()=>({reports_only:true,items:1,labels:[bRun.label],runs:1,records:0,token:'one-report'})});await flush();
assert.match(confirmations.at(-1),/输入数据和其他报告保留/);assert.equal(archiveRequests.length,0);
archiveElement('library-active').events.click();clickPartial('archive',cRun.archive_id);action=archiveRequests.shift();
assert.deepEqual(action.body.ids,[cRun.archive_id]);
action.resolve({ok:false,json:async()=>({error:'test only'})});await flush();
console.log('Individual reports and same-workflow history split across current/archive; group actions and deletion preserve source data.');

// Public reports can be organized in this browser, without shared mutations.
const locked=archiveWindow.QCDataLibrary.refresh();
const lockedSource={name:'Long public dataset title',url:'https://openneuro.org/datasets/ds004100/versions/1.1.3',version:'1.1.3',license:'CC0'};
const publicFixture={...item('public-eeg'),source:lockedSource,workflow_groups:[{id:'public-route',label:'基础方案',method_family:'basic',latest:aRun,runs:[aRun,cRun]}]};
archiveRequests.shift().resolve({ok:true,json:async()=>({public_only:true,items:[publicFixture],examples:[{...frozen.examples[0],id:'public-example'}]})});await locked;
const lockedHtml=archiveElement('data-library-list').innerHTML;
assert.match(lockedHtml,/data-library-action="archive" data-id="report:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/);
assert(!lockedHtml.includes('data-library-action="delete"'));assert(!lockedHtml.includes('data-library-action="delete-temporary"'));
assert(lockedHtml.includes(aRun.url));assert(lockedHtml.includes('OpenNeuro · ds004100<span'));
assert(lockedHtml.includes('<details class="public-source-details">'));assert(lockedHtml.includes('1.1.3 · CC0'));
assert.equal(archiveElement('library-active').hidden,false);assert.equal(archiveElement('library-archived').hidden,false);
assert.equal(archiveElement('library-empty-archive').hidden,true);
assert(!archiveElement('demo-report-list').innerHTML.includes('delete-example'));
assert(!archiveElement('demo-report-list').innerHTML.includes('example-entry-menu'));
clickPartial('archive','record:public-eeg');await flush();assert.equal(archiveRequests.length,0);
clickPartial('archive',aRun.archive_id);await flush();assert.equal(archiveRequests.length,0);
assert(!archiveElement('data-library-list').innerHTML.includes(aRun.url));
assert(archiveElement('data-library-list').innerHTML.includes(cRun.url));
assert.equal(archiveElement('data-library-count').textContent,'1');
assert.match(archiveElement('library-archived').textContent,/归档 · 1/);
assert.deepEqual(JSON.parse(browserValues.get('qc.library.archived-reports.v1')),[aRun.archive_id]);
archiveElement('library-archived').events.click();
assert(archiveElement('data-library-list').innerHTML.includes(aRun.url));
assert(!archiveElement('data-library-list').innerHTML.includes(cRun.url));
assert.match(archiveElement('data-library-list').innerHTML,/data-library-action="restore"/);
assert(!archiveElement('data-library-list').innerHTML.includes('data-library-action="delete"'));
clickPartial('delete',aRun.archive_id);await flush();assert.equal(archiveRequests.length,0);
const archiveReload=archiveWindow.QCDataLibrary.refresh();
archiveRequests.shift().resolve({ok:true,json:async()=>({public_only:true,items:[publicFixture]})});await archiveReload;
assert(archiveElement('data-library-list').innerHTML.includes(aRun.url));
clickPartial('restore',aRun.archive_id);await flush();assert.equal(archiveRequests.length,0);
assert.match(archiveElement('data-library-list').innerHTML,/归档为空/);
archiveElement('library-active').events.click();
assert(archiveElement('data-library-list').innerHTML.includes(aRun.url));
// A local-storage change from another tab updates the same browser's archive.
localStorage.setItem('qc.library.archived-reports.v1',JSON.stringify([aRun.archive_id,cRun.archive_id]));
archiveEvents.storage({key:'qc.library.archived-reports.v1'});
assert.match(archiveElement('data-library-list').innerHTML,/报告均已归档/);
assert.equal(archiveElement('library-archived').hidden,false);
// A new page instance restores the archive from IDs, not retained data copies.
const reopenedNodes=new Map(),reopenedRequests=[];
const reopenedElement=id=>{if(!reopenedNodes.has(id))reopenedNodes.set(id,{value:'',events:{},dataset:{},setAttribute(){},addEventListener(k,v){this.events[k]=v}});return reopenedNodes.get(id)};
const reopenedWindow={localStorage,QCI18n:{getLanguage:()=> 'zh-CN'},addEventListener(){}};
vm.runInNewContext(source,{URL,window:reopenedWindow,document:{getElementById:reopenedElement},fetch:()=>new Promise(resolve=>reopenedRequests.push(resolve))});
reopenedRequests.shift()({ok:true,json:async()=>({public_only:true,items:[publicFixture]})});await flush();
assert.match(reopenedElement('data-library-list').innerHTML,/报告均已归档/);
reopenedElement('library-archived').events.click();
assert(reopenedElement('data-library-list').innerHTML.includes(aRun.url));
assert(reopenedElement('data-library-list').innerHTML.includes(cRun.url));
console.log('Public report archive and restore persist by browser; shared deletion stays protected; example menus stay hidden.');

// Temporary entries live alongside public data, but only owned entries get password-free deletion.
const tempNodes=new Map(),tempRequests=[],tempEvents={};let tick;
const tempElement=id=>{if(!tempNodes.has(id))tempNodes.set(id,{value:'',events:{},dataset:{},setAttribute(){},addEventListener(k,v){this.events[k]=v}});return tempNodes.get(id)};
tempElement('example-cache').textContent=JSON.stringify(frozen);
const tempValues=new Map(),tempStorage={getItem:key=>tempValues.get(key)||null,setItem:(key,value)=>tempValues.set(key,value)};
const tempWindow={localStorage:tempStorage,QCI18n:{getLanguage:()=> 'zh-CN'},addEventListener(k,v){tempEvents[k]=v},setInterval(fn){tick=fn},confirm:()=>true};
vm.runInNewContext(source,{URL,window:tempWindow,document:{getElementById:tempElement},fetch:(url,options)=>new Promise(resolve=>tempRequests.push({url,body:options?.body?JSON.parse(options.body):null,resolve}))});
const now=Date.now(),own=item('record:mine',{label:'临时测试 EDF',temporary:true,retention:{phase:'idle',expires_at:new Date(now+1800000).toISOString(),server_now:new Date(now).toISOString()},recent_reports:[{...aRun,temporary:true}]});
tempRequests.shift().resolve({ok:true,json:async()=>({public_only:true,items:[own,item('record:public')],examples:frozen.examples,examples_authoritative:true})});await flush();
let temporaryHtml=tempElement('data-library-list').innerHTML;
assert.match(temporaryHtml,/library-expiry/);assert.match(temporaryHtml,/30分钟后清理/);assert.match(temporaryHtml,/仅本浏览器可见/);
assert.match(temporaryHtml,/data-library-action="delete-temporary" data-id="record:mine"/);
assert.match(temporaryHtml,/data-library-action="delete-temporary" data-id="report:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"/);
assert(!temporaryHtml.includes('data-id="record:public"'));assert(temporaryHtml.includes('data-library-action="archive"'));
tempElement('data-library-list').events.click({preventDefault(){},target:{closest:()=>({dataset:{libraryAction:'archive',id:aRun.archive_id}})}});
assert.equal(tempRequests.length,0);
tempElement('library-archived').events.click();
assert.match(tempElement('data-library-list').innerHTML,/30分钟后清理/);
assert.match(tempElement('data-library-list').innerHTML,/data-library-action="delete-temporary"/);
assert.match(tempElement('data-library-list').innerHTML,/data-library-action="restore"/);
tempElement('data-library-list').events.click({preventDefault(){},target:{closest:()=>({dataset:{libraryAction:'delete-temporary',id:'report:'+aRun.job_id}})}});
let deletion=tempRequests.shift();assert.equal(deletion.url,'/api/v1/data/delete-temporary');assert.equal(deletion.body.confirmed,true);assert(!('password' in deletion.body));
deletion.resolve({ok:true,json:async()=>({status:'cleared'})});await flush();
// An authoritative empty example catalog must remove previously cached cards.
tempRequests.shift().resolve({ok:true,json:async()=>({public_only:true,items:[],examples:[],examples_authoritative:true})});await flush();
assert.equal(tempElement('demo-reports').hidden,true);
assert.match(tempElement('data-library-message').textContent,/已删除/);
assert.match(tempElement('data-library-list').innerHTML,/归档为空/);
console.log('Temporary data: server countdown, owned report deletion without password, protected public rows and withdrawn cached examples passed.');

// Both section counts occupy the same position immediately before the disclosure icon.
const index=fs.readFileSync(new URL('../apps/workbench/web/index.html',import.meta.url),'utf8');
for(const id of ['demo-reports-count','data-library-count'])assert.match(index,new RegExp(`<span id="${id}" class="tag subtle rail-count">[^<]*</span></summary>`));
assert(!index.includes('class="library-heading"'));
console.log('Example and personal library counts share the same header alignment.');
