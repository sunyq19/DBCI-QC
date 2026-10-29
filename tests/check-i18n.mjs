// DOM-level localization contracts. No browser, network, signal reads or jobs.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const source = fs.readFileSync(path.join(root, 'apps/workbench/web/i18n.js'), 'utf8');
const htmlSource = fs.readFileSync(path.join(root, 'apps/workbench/web/index.html'), 'utf8');
const tests=[]; const check=(name,run)=>tests.push([name,run]);

function harness({saved='zh-CN',storageFails=false,loading=false,search=''}={}) {
  const observers=[],microtasks=[],events=[],storage=new Map([['ephys-qc.language',saved]]);
  let mutations=0,observerDeliveries=0;
  function changed(node,type,name) {
    mutations++;
    for(const observer of observers) if(observer.target && (type!=='attributes'||observer.options.attributeFilter.includes(name))) observer.records.push({type,target:node,attributeName:name});
  }
  class Text {
    constructor(value){this.nodeType=3;this._data=value;this.parentElement=null;}
    get data(){return this._data} set data(value){this._data=value;changed(this,'characterData')}
    get textContent(){return this.data}
  }
  function simpleMatches(node,selector) {
    if(!node||node.nodeType!==1)return false;
    if(selector.endsWith(':first-child')){if(node.parentElement?.children[0]!==node)return false;selector=selector.replace(':first-child','')}
    const tag=selector.match(/^[a-z][\w-]*/i)?.[0];if(tag&&node.tagName!==tag.toUpperCase())return false;
    for(const m of selector.matchAll(/#([\w-]+)/g))if(node.id!==m[1])return false;
    for(const m of selector.matchAll(/\.([\w-]+)/g))if(!node.classList.contains(m[1]))return false;
    for(const m of selector.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g))if(!node.hasAttribute(m[1])||(m[2]!=null&&node.getAttribute(m[1])!==m[2]))return false;
    return true;
  }
  function matches(node,selector) {
    return selector.split(',').some(item=>{
      const parts=item.trim().replace(/\s*>\s*/g,' > ').split(/\s+/);let at=parts.length-1,current=node;
      if(!simpleMatches(current,parts[at--]))return false;
      while(at>=0){if(parts[at]==='>'){at--;current=current.parentElement;if(!simpleMatches(current,parts[at--]))return false}else{const desired=parts[at--];current=current.parentElement;while(current&&!simpleMatches(current,desired))current=current.parentElement;if(!current)return false}}
      return true;
    });
  }
  class Element {
    constructor(tag,attrs={}){this.nodeType=1;this.tagName=tag.toUpperCase();this.attrs={...attrs};this.parentElement=null;this.childNodes=[];this.value=attrs.value??'';this.checked=false;this.disabled=false;this.open=false;this.isContentEditable=false;this.classList={contains:name=>(this.attrs.class||'').split(/\s+/).includes(name)};}
    get id(){return this.attrs.id||''} get children(){return this.childNodes.filter(n=>n.nodeType===1)}
    get textContent(){return this.childNodes.map(n=>n.textContent).join('')}
    set textContent(value){this.childNodes=[];this.append(new Text(value));changed(this,'childList')}
    set innerHTML(_){throw new Error('Localization must not write innerHTML')}
    hasAttribute(name){return Object.hasOwn(this.attrs,name)} getAttribute(name){return this.attrs[name]??null}
    setAttribute(name,value){this.attrs[name]=String(value);changed(this,'attributes',name)}
    append(...nodes){for(const node of nodes){node.parentElement=this;this.childNodes.push(node)}changed(this,'childList');return this}
    matches(selector){return matches(this,selector)} closest(selector){for(let node=this;node;node=node.parentElement)if(matches(node,selector))return node;return null}
    querySelectorAll(selector){const result=[];function visit(node){for(const child of node.children||[]){if(matches(child,selector))result.push(child);visit(child)}}visit(this);return result}
  }
  const document={documentElement:new Element('html',{lang:'zh-CN'}),readyState:loading?'loading':'complete',listeners:new Map(),
    addEventListener(type,callback){if(!this.listeners.has(type))this.listeners.set(type,[]);this.listeners.get(type).push(callback)},
    dispatchEvent(event){events.push(event);for(const callback of this.listeners.get(event.type)||[])callback(event);return true},
    querySelectorAll(selector){return this.documentElement.querySelectorAll(selector)}};
  const head=new Element('head'),body=new Element('body');document.documentElement.append(head,body);
  document.body=body;document.head=head;
  class Observer {
    constructor(callback){this.callback=callback;this.records=[];this.target=null;observers.push(this)}
    observe(target,options){this.target=target;this.options=options}
    takeRecords(){const records=this.records;this.records=[];return records}
  }
  const window={document,MutationObserver:Observer,CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail}},
    localStorage:{getItem(key){if(storageFails)throw Error('disabled');return storage.get(key)},setItem(key,value){if(storageFails)throw Error('disabled');storage.set(key,value)}},
    queueMicrotask(callback){microtasks.push(callback)},fetch(){throw Error('Localization must not request network')},URLSearchParams,location:{hash:'#module-M03',search}};
  const context=vm.createContext({window,console,Promise});
  const element=(tag,text='',attrs={})=>{const node=new Element(tag,attrs);if(text)node.append(new Text(text));return node};
  function start(){vm.runInContext(source,context);return window.QCI18n}
  function flush(){for(let pass=0;pass<12;pass++){let worked=false;for(const observer of observers){const records=observer.takeRecords();if(records.length){worked=true;observerDeliveries++;observer.callback(records)}}while(microtasks.length){worked=true;microtasks.shift()()}if(!worked)return}throw Error('MutationObserver feedback loop')}
  return {document,body,head,element,Text,start,flush,events,storage,window,mutations:()=>mutations,deliveries:()=>observerDeliveries};
}

check('static labels, title and language preference round-trip without rebuilding DOM',()=>{
  const h=harness(),title=h.element('title','质控台'),button=h.element('button','读取文件'),label=h.element('h2','信息提取');h.head.append(title);h.body.append(button,label);
  const original=button.childNodes[0],api=h.start();api.setLanguage('en');
  assert.equal(title.textContent,'QC Workbench');assert.equal(button.textContent,'Read file');assert.equal(label.textContent,'File information');assert.equal(button.childNodes[0],original);
  assert.equal(h.document.documentElement.getAttribute('lang'),'en');assert.equal(h.storage.get(api.STORAGE_KEY),'en');
  api.setLanguage('zh-CN');assert.equal(title.textContent,'质控台');assert.equal(button.textContent,'读取文件');
});
check('saved preference and delayed initialization translate before interaction',()=>{
  const h=harness({saved:'en',loading:true});h.body.append(h.element('button','确认并推荐'));const api=h.start();
  h.document.dispatchEvent({type:'DOMContentLoaded'});assert.equal(h.body.textContent,'Confirm and recommend');assert.equal(api.getLocale(),'en-US');
});
check('storage unavailable and invalid locale are safe',()=>{
  const h=harness({storageFails:true});const api=h.start();assert.equal(api.getLanguage(),'zh-CN');assert.equal(api.setLanguage('ar'),false);assert.equal(api.setLanguage('en'),true);assert.equal(api.getLanguage(),'en');
});
check('explicit return URL language wins over stored preference and is retained',()=>{
  const h=harness({saved:'zh-CN',search:'?lang=en'}),api=h.start();assert.equal(api.getLanguage(),'en');assert.equal(h.storage.get(api.STORAGE_KEY),'en');
  assert.equal(harness({saved:'en',search:'?lang=unknown'}).start().getLanguage(),'en');
});
check('only exact internal standards routes follow language, including later module links',()=>{
  const h=harness({saved:'en'}),main=h.element('a','质控标准',{href:'/standards'}),moduleLink=h.element('a','详细介绍 ↗',{href:'/standards/modules/M03'}),external=h.element('a','Source',{href:'https://example.test/standards'}),download=h.element('a','Download',{href:'/standards.md'}),apiPath=h.element('a','API',{href:'/api/v1/jobs'}),query=h.element('a','Query',{href:'/standards?download=true'});h.body.append(main,moduleLink,external,download,apiPath,query);const api=h.start();
  assert.equal(main.getAttribute('href'),'/en/standards');assert.equal(moduleLink.getAttribute('href'),'/en/standards/modules/M03');assert.equal(external.getAttribute('href'),'https://example.test/standards');assert.equal(download.getAttribute('href'),'/standards.md');assert.equal(apiPath.getAttribute('href'),'/api/v1/jobs');assert.equal(query.getAttribute('href'),'/standards?download=true');
  moduleLink.setAttribute('href','/standards/modules/M09');h.flush();assert.equal(moduleLink.getAttribute('href'),'/en/standards/modules/M09');api.setLanguage('zh-CN');assert.equal(moduleLink.getAttribute('href'),'/standards/modules/M09');
});
check('standards anchors are retained, with nine known clauses mapped between languages',()=>{
  const h=harness({saved:'en'}),clause=h.element('a','Clause',{href:'/standards#57-m07-状态与事件核对'}),anchor=h.element('a','Anchor',{href:'/standards/modules/M03#2-inputs'}),api=h.start();h.body.append(clause,anchor);h.flush();
  assert.equal(clause.getAttribute('href'),'/en/standards#57-m07-state-and-event-checks');assert.equal(anchor.getAttribute('href'),'/en/standards/modules/M03#2-inputs');
  api.setLanguage('zh-CN');assert.equal(clause.getAttribute('href'),'/standards#57-m07-状态与事件核对');assert.equal(anchor.getAttribute('href'),'/standards/modules/M03#2-inputs');
});
check('changing language after a document return URL survives reload without losing deep link',()=>{
  const h=harness({search:'?lang=en&view=keep'}),calls=[];h.window.location.pathname='/';h.window.history={state:{keep:true},replaceState:(...args)=>calls.push(args)};const api=h.start();api.setLanguage('zh-CN');
  assert.equal(h.storage.get(api.STORAGE_KEY),'zh-CN');assert.equal(calls.at(-1)[2],'/?lang=zh-CN&view=keep#module-M03');
});
check('language controls dispatch once and never trigger unrelated actions',()=>{
  const h=harness(),zh=h.element('button','中文',{'data-language':'zh-CN'}),en=h.element('button','English',{'data-language':'en'});h.body.append(zh,en);const api=h.start();
  let prevented=0;h.document.dispatchEvent({type:'click',target:en,preventDefault(){prevented++}});
  assert.equal(api.getLanguage(),'en');assert.equal(prevented,1);assert.equal(en.getAttribute('aria-pressed'),'true');assert.equal(zh.getAttribute('aria-pressed'),'false');
  api.setLanguage('en');assert.equal(h.events.filter(e=>e.type===api.EVENT).length,1);assert.equal(h.window.location.hash,'#module-M03');
});
check('new DOM and externally changed status are translated with no observer loop',()=>{
  const h=harness({saved:'en'}),api=h.start(),status=h.element('span','运行中');h.body.append(status);h.flush();assert.equal(status.textContent,'Running');
  status.childNodes[0].data='已完成';h.flush();assert.equal(status.textContent,'Completed');
  api.setLanguage('zh-CN');h.flush();assert.equal(status.textContent,'已完成');assert(h.deliveries()<=3);
  const before=h.mutations();h.flush();assert.equal(h.mutations(),before);
});
check('filenames, source text, channel names and registered recording labels stay verbatim',()=>{
  const h=harness({saved:'en'});
  const file=h.element('h2','读取文件',{id:'selected-file-name'}),job=h.element('h3','未知',{id:'job-label'}),channel=h.element('span','疾病背景',{class:'channel-chip'}),sourceText=h.element('p','静息 / 癫痫',{id:'input-description'}),explicit=h.element('span','读取文件',{'data-i18n-skip':''});
  const select=h.element('select','',{id:'input-select'}),prompt=h.element('option','选择已登记记录',{value:''}),record=h.element('option','未知',{value:'record-1'});select.append(prompt,record);
  h.body.append(file,job,channel,sourceText,explicit,select);h.start();
  assert.equal(file.textContent,'读取文件');assert.equal(job.textContent,'未知');assert.equal(channel.textContent,'疾病背景');assert.equal(sourceText.textContent,'静息 / 癫痫');assert.equal(explicit.textContent,'读取文件');assert.equal(record.textContent,'未知');assert.equal(prompt.textContent,'Select a registered recording');
});
check('inputs, selected values, checkbox state, contenteditable and raw JSON are unchanged',()=>{
  const h=harness({saved:'en'}),input=h.element('input','',{placeholder:'已知实验或来源，可留空',value:'读取文件'}),textarea=h.element('textarea','{"记录名称":"未知"}',{placeholder:'已知实验或来源，可留空'}),editable=h.element('div','疾病背景',{contenteditable:'true'}),pre=h.element('pre','{"reason":"运行中"}'),code=h.element('code','未配置');
  const select=h.element('select','',{value:'unknown'}),option=h.element('option','未知',{value:'unknown'}),checkbox=h.element('input');checkbox.checked=true;select.append(option);
  h.body.append(input,textarea,editable,pre,code,select,checkbox);const api=h.start();
  assert.equal(input.value,'读取文件');assert.equal(input.getAttribute('placeholder'),'Known experiment or source (optional)');assert.equal(textarea.textContent,'{"记录名称":"未知"}');assert.equal(textarea.getAttribute('placeholder'),'Known experiment or source (optional)');assert.equal(editable.textContent,'疾病背景');assert.equal(pre.textContent,'{"reason":"运行中"}');assert.equal(code.textContent,'未配置');assert.equal(select.value,'unknown');assert.equal(option.getAttribute('value'),'unknown');assert.equal(option.textContent,'Unknown');assert.equal(checkbox.checked,true);
  api.setLanguage('zh-CN');assert.equal(input.value,'读取文件');assert.equal(option.textContent,'未知');assert.equal(checkbox.checked,true);
});
check('explicit keys and accessibility attributes support dynamic content',()=>{
  const h=harness({saved:'en'}),key=h.element('strong','旧标题',{'data-i18n':'workbench.title'}),button=h.element('button','×',{'aria-label':'关闭模块详情',title:'刷新运行记录'});h.body.append(key,button);const api=h.start();assert.equal(key.textContent,'QC Workbench');assert.equal(button.getAttribute('aria-label'),'Close module details');assert.equal(button.getAttribute('title'),'Refresh run history');
  button.setAttribute('title','查看模块详情');h.flush();assert.equal(button.getAttribute('title'),'View module details');api.setLanguage('zh-CN');assert.equal(button.getAttribute('title'),'查看模块详情');
});
check('dynamic count, range, progress, error and candidate messages are English',()=>{
  const api=harness().start();
  const examples=['5 / 24 项方法','5 类数据 · 11 份本地记录','64 道 EEG','所选时段超出记录范围（0–120.5 秒）。','原始时间轴 100–200 秒 · 共 100 秒','已选模块 7 / 9 已结束 · 2 个未选择 · 执行进度不代表质量','通道对候选：1,234（待复核）','查看 24 个方法的适用性与参数','参数未应用：最外层必须是按扩展 ID 分组的 JSON 对象。','M03 信号完整性，运行中，查看详情'];
  for(const text of examples)assert(!/[\u3400-\u9fff]/.test(api.translate(text,'en')),text);
  assert.equal(api.translate('运行记录 · 未知.edf','en'),'Run history · 未知.edf');assert.equal(api.translate('未知.edf · 点击开始检查','en'),'未知.edf · Select Start check');
});
check('untranslated technical source is clearly labeled, never fabricated',()=>{
  const h=harness({saved:'en'}),container=h.element('div','',{class:'method-documentation'}),text=h.element('p','尚无英文版的特殊研究说明。'),raw=h.element('pre','{"note":"尚无英文"}');container.append(text,raw);h.body.append(container);const api=h.start();
  assert.equal(text.textContent,'Original text (Chinese): 尚无英文版的特殊研究说明。');assert.equal(raw.textContent,'{"note":"尚无英文"}');api.setLanguage('zh-CN');assert.equal(text.textContent,'尚无英文版的特殊研究说明。');
});
check('known method invocation notes and reference titles translate while raw parameters and URLs do not',()=>{
  const h=harness({saved:'en'}),card=h.element('article','',{class:'method-card'});
  const original='brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_ecg_events；锁时统计由BrainElecQC实现';
  const call=h.element('pre',original),params=h.element('pre','{"description":"读取文件","peak":null,"flat":0}'),unknown=h.element('pre','用户原始说明：未知'),outside=h.element('pre',original);
  const refs=h.element('div','',{class:'method-references'}),reference=h.element('a','BrainElecQC ECG事件和EEG锁时汇总 ↗',{href:'https://example.test/source?lang=zh'});
  const protectedReference=h.element('a','BrainElecQC ECG事件和EEG锁时汇总 ↗',{'data-i18n-skip':'',href:'https://example.test/original'});
  refs.append(reference,protectedReference);card.append(call,params,unknown,refs);h.body.append(card,outside);const api=h.start();
  assert(!/[\u3400-\u9fff]/.test(call.textContent));assert(call.textContent.includes('brainelecqc.eeg.events.compute_event_qc → mne.preprocessing.find_ecg_events'));
  assert(!/[\u3400-\u9fff]/.test(reference.textContent));assert.equal(reference.getAttribute('href'),'https://example.test/source?lang=zh');
  assert.equal(params.textContent,'{"description":"读取文件","peak":null,"flat":0}');assert.equal(unknown.textContent,'用户原始说明：未知');assert.equal(outside.textContent,original);assert.equal(protectedReference.textContent,'BrainElecQC ECG事件和EEG锁时汇总 ↗');
  api.setLanguage('zh-CN');h.flush();assert.equal(call.textContent,original);assert.equal(reference.textContent,'BrainElecQC ECG事件和EEG锁时汇总 ↗');
});
check('critical new intake labels, module names, context and scientific cautions are mapped',()=>{
  const api=harness().start();
  for(const label of ['质控台','上传文件','读取文件','信息提取','数据格式','通道数','记录时长','采样率','模态','标注','自动提取','待确认','疾病背景','未知','参考构型','确认并推荐','推荐质控流程','查看模块','没有文件','读取后显示','数据接入与结构核验','数据画像与检查计划','信号完整性','频谱与干扰','坏通道候选','生理伪迹线索','状态和事件检查','分项评价与可比性','报告与人工复核','运动想象','总分尚未校准','事件不是质量真值。'])assert(!/[\u3400-\u9fff]/.test(api.translate(label,'en')),label);
  assert.equal(api.translate('EDF/BDF/BrainVision/EEGLAB/FIF/ZIP','en'),'EDF/BDF/BrainVision/EEGLAB/FIF/ZIP');
});
check('translator never mutates source objects or runs network/recommendation/job actions',()=>{
  // Catalog prose may legitimately document score.value=null. Scan executable
  // code after the literal dictionary; DOM behavior is also checked above.
  const executable=source.slice(source.indexOf('  const dictionary ='));
  assert(!/\b(?:fetch|XMLHttpRequest|WebSocket)\s*\(/.test(executable));assert(!/\.innerHTML\s*=/.test(executable));assert(!/\.(?:value|checked|selected|selectedIndex)\s*=/.test(executable));assert(!/\b(?:makeRecommendation|startJob|selectInput)\s*\(/.test(executable));
  const api=harness().start(),raw='{"input":"疾病背景","status":"运行中"}';assert.equal(api.translate(raw,'en'),raw);
});
check('current static HTML system labels have English translations',()=>{
  const api=harness().start();let cleaned=htmlSource.replace(/<(script|style|svg)[\s\S]*?<\/\1>/gi,'').replace(/<!--[\s\S]*?-->/g,'');
  const labels=[...cleaned.matchAll(/>([^<>]+)</g)].map(m=>m[1].trim()).filter(text=>/[\u3400-\u9fff]/.test(text));
  const exempt=new Set(['中文','简体中文','English','EN','中']);
  const missing=[...new Set(labels.filter(text=>!exempt.has(text)&&/[\u3400-\u9fff]/.test(api.translate(text,'en'))))];
  assert.deepEqual(missing,[],`Missing static UI translations: ${missing.join(' | ')}`);
});

let failures=0;
for(const [name,run] of tests){try{run();console.log(`PASS ${name}`)}catch(error){failures++;console.error(`FAIL ${name}\n${error.stack}`)}}
console.log(`${tests.length-failures}/${tests.length} localization checks passed`);
if(failures)process.exitCode=1;
