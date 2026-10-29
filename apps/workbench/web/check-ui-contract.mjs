// Pure JavaScript state/markup checks. No browser, network, or analysis jobs.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import {fileURLToPath} from "node:url";
import path from "node:path";
const directory = path.dirname(fileURLToPath(import.meta.url));
const source = fs.readFileSync(path.join(directory,"app.js"),"utf8");
const html = fs.readFileSync(path.join(directory,"index.html"),"utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
assert.equal(ids.length,new Set(ids).size,"Static HTML IDs are unique");
const fields = ["disease","age_group","task"];
const rawMethod = (id,category,extra={}) => ({id,name:`方法 ${id}`,category,description:"测试用方法说明",inputs:["原始数据"],outputs:["候选"],requirements:["明确配置"],source:{name:"Source",url:"https://example.test/method",license:"BSD-3-Clause"},implementation:"available",limitations:["仍需复核"],optional_extension:false,...extra});
function fixtureCatalog() {
  const modules = ["M01","M02","M03","M04","M05","M06","M07","M08","M09"].map(id => ({id,name:`模块 ${id}`,methods:[],inputs:[],outputs:[],dependencies:[],limitations:[]}));
  modules.find(m=>m.id==="M03").methods=[rawMethod("basic_check","basic"),rawMethod("mne_amplitude","optional",{optional_extension:true,defaults:{flat:0}})];
  modules.find(m=>m.id==="M06").methods=[rawMethod("conditional_check","conditional"),rawMethod("mne_muscle","optional",{optional_extension:true}),rawMethod("future_check","optional",{implementation:"planned",optional_extension:true})];
  const inputs = ["rest","attention"].map((task,index) => ({id:`input-${index}`,label:`输入 ${index}`,profile_id:"profile",metadata:{duration_seconds:300,channels:[{index:0,name:"EEG",sampling_rate_hz:160,unit:"uV"}],size_bytes:100},description:"fixture",data_tags:[{key:"sampling_rate_hz",label:"采样率",value:160,display:"160 Hz",kind:"technical",source:"技术头",status:"known"},{key:"coordinates",label:"坐标",value:null,display:"位置未核实",kind:"technical",source:"来源未提供",status:"unknown"},{key:"task",label:"任务",value:task,display:task,kind:"context",source:"来源任务",status:"known"}],default_config:{selection:{eeg_indices:[0],reference_indices:{},start_seconds:0,duration_seconds:30},context_tags:{disease:"unknown",age_group:"unknown",task},method_config:{comparison_groups:["ref"],preserved_option:{a:1}}}}));
  return {modules,inputs,profiles:[{id:"profile",name:"配置"}],context_tag_options:{disease:[{value:"unknown",label:"未知"},{value:"other",label:"其他"}],age_group:[{value:"unknown",label:"未知"},{value:"adult",label:"成人"}],task:[{value:"unknown",label:"未知"},{value:"rest",label:"静息"},{value:"attention",label:"注意任务"}]}};
}
function harness(fetchImpl = async()=>{throw new Error("Unexpected API request in pure JS test")}, {selected = true, hash = ""} = {}) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id,{_value:"",get value(){return this._value},set value(value){this._value=String(value)},textContent:"",innerHTML:"",hidden:false,disabled:false,open:false,style:{},attrs:{},events:new Map(),firstElementChild:{style:{}},lastElementChild:{textContent:""},addEventListener(type,handler){if(!this.events.has(type))this.events.set(type,[]);this.events.get(type).push(handler)},dispatch(type,event={}){for(const handler of this.events.get(type)||[])handler(event)},removeAttribute(key){delete this.attrs[key]},setAttribute(key,value){this.attrs[key]=value},querySelectorAll(){return[]},scrollIntoView(){},showModal(){this.open=true},close(){if(!this.open)return;this.open=false;this.dispatch("close",{target:this})}});
    return elements.get(id);
  };
  ids.forEach(get);
  const storage = new Map();
  const location = {protocol:"http:",pathname:"/",search:"",hash}, windowEvents = new Map();
  const history = {state:null,replacements:[],replaceState(state,_title,value){this.state=state;this.replacements.push(value);const url=new URL(value,"http://localhost");Object.assign(location,{pathname:url.pathname,search:url.search,hash:url.hash})}};
  const context = {document:{getElementById:get,addEventListener(){}},window:{history,addEventListener(type,handler){if(!windowEvents.has(type))windowEvents.set(type,[]);windowEvents.get(type).push(handler)},matchMedia:()=>({matches:true}),sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}},location,fetch:fetchImpl,AbortController,setTimeout,clearTimeout,URL,console};
  const names = "state,currentConfig,body,fingerprint,validPlan,selectInput,setExtension,setModuleSelected,setContext,renderDataTags,renderInputUsage,renderExtensions,extensionMethods,methodCardsHtml,methodPlanHtml,methodApplicability,visualNodes,executionProgress,renderResult,safeSourceUrl,moduleStandardsUrl,moduleFromHash,openModuleFromHash,moduleDialogClosed,showModule,renderPipeline,updateActions,toolkitMethods,renderToolkit,methodDocumentationHtml,makeRecommendation,applyRecommendation,recommendationValid,renderRecommendation,applyParameters,invalidatePlan,intakeRole,intakeConfirmation,renderIntake,renderExtraction,annotationText,uploadIntake,pendingIntakeId,confirmIntake,prepareRecommendedPlan,makePlan,startJob,selectJob,loadCatalog,renderExamplePresets,chooseLocalFile,clearInputDraft,renderVisibility,restoreIntake,setScope,saveDraft,savedDraft,restoreDraft,discardDraft,applyConfiguration,jobLocation,setJobLocation,restoreNavigation,cloneJobConfiguration,coverageText,resetReviewWorkspace,renderCandidateList,renderWaveform,loadWaveform,saveReview,beginInputRevision,cancelInputRevision,selectCandidate,evidenceLinks,runSummary,clearPoll,listPendingIntakes,openReviewWorkspace,renderRecordingProgress,revisionMetadataChanges";
  const instrumented = source.replace("  loadCatalog();\n})();",`  window.contract = {${names}};\n})();`);
  assert.notEqual(instrumented,source,"Harness replaces startup; no API requests execute");
  vm.runInNewContext(instrumented,context);
  const test = context.window.contract;
  test.state.catalog=fixtureCatalog();if(selected)test.selectInput("input-0",{autoPrepare:false});else test.updateActions();
  return {...test,selectInput:(id,options={autoPrepare:false})=>test.selectInput(id,options),get,location,history,storage,setHash(value){location.hash=value;for(const handler of windowEvents.get("hashchange")||[])handler({type:"hashchange"})}};
}
const tests = [];
function check(name,run) { tests.push([name,run]); }
check("complete config copied; background defaults and extensions explicit",()=>{
  const t=harness(), config=t.currentConfig();
  assert.equal(JSON.stringify(config.context_tags),'\u007b"disease":"unknown","age_group":"unknown","task":"rest"}');
  assert.equal(JSON.stringify(config.method_config.extensions),"[]");
  config.method_config.preserved_option.a=2;
  assert.equal(t.state.input.default_config.method_config.preserved_option.a,1);
});
check("extension selects parent, invalidates plan, and is removed with parent",()=>{
  const t=harness();t.state.selected.delete("M06");t.state.plan={plan_id:"old"};t.state.planKey=t.fingerprint();
  t.setExtension("mne_muscle",true);
  assert(t.state.selected.has("M06"));assert(t.state.extensions.has("mne_muscle"));assert.equal(t.state.plan,null);
  t.setModuleSelected("M06",false);assert(!t.state.extensions.has("mne_muscle"));
  t.setExtension("future_check",true);assert(!t.state.extensions.has("future_check"));
});
check("new available optional methods dynamically render and select their parents",()=>{
  const t=harness();
  for(const [id,parent] of [["mne_bridge","M05"],["mne_lof","M05"],["autoreject_global","M03"]])t.state.catalog.modules.find(module=>module.id===parent).methods.push(rawMethod(id,"optional",{optional_extension:true}));
  assert.equal(t.extensionMethods().length,5);t.state.selected.clear();t.renderExtensions();
  for(const [id,parent] of [["mne_bridge","M05"],["mne_lof","M05"],["autoreject_global","M03"]]){
    assert(t.get("extension-options").innerHTML.includes(`data-extension="${id}"`));
    assert(t.methodCardsHtml(t.state.catalog.modules.find(module=>module.id===parent)).includes(`data-extension="${id}"`));
    t.setExtension(id,true);assert(t.state.selected.has(parent));assert(t.currentConfig().method_config.extensions.includes(id));
  }
  t.setModuleSelected("M05",false);assert(!t.state.extensions.has("mne_bridge"));assert(!t.state.extensions.has("mne_lof"));assert(t.state.extensions.has("autoreject_global"));
  t.state.catalog.modules.find(module=>module.id==="M07").methods.push(rawMethod("catalog_added_future_id","optional",{optional_extension:true}));
  t.setExtension("catalog_added_future_id",true);assert(t.state.selected.has("M07"));assert(t.state.extensions.has("catalog_added_future_id"));
});
check("changing input resets extensions and manual context to source defaults",()=>{
  const t=harness();t.setExtension("mne_amplitude",true);t.setContext("disease","other");t.setContext("age_group","adult");t.selectInput("input-1");
  assert.equal(t.state.extensions.size,0);assert.equal(t.state.contextTags.disease,"unknown");assert.equal(t.state.contextTags.age_group,"unknown");assert.equal(t.state.contextTags.task,"attention");
});
check("each additional dataset restores its own explicit background without cross-record leakage",()=>{
  const t=harness();
  for(const [id,task] of [["closed-eye","rest"],["motor","motor"],["sleep-edf","sleep"],["chb-mit","unknown"]]){
    const input=JSON.parse(JSON.stringify(t.state.catalog.inputs[0]));input.id=id;input.label=id;input.default_config.context_tags={disease:"unknown",age_group:"unknown",task};input.data_tags.find(tag=>tag.key==="task").value=task;input.description="This fixture description must not infer a clinical diagnosis or age";t.state.catalog.inputs.push(input);
  }
  t.state.catalog.context_tag_options.task.push({value:"motor",label:"运动"},{value:"sleep",label:"睡眠"});
  const before=JSON.stringify(t.state.catalog.inputs);
  for(const [id,task] of [["closed-eye","rest"],["motor","motor"],["sleep-edf","sleep"],["chb-mit","unknown"]]){
    t.setExtension("mne_amplitude",true);t.setContext("disease","other");t.setContext("age_group","adult");t.selectInput(id);
    assert.equal(t.state.extensions.size,0);assert.equal(t.state.contextTags.task,task);assert.equal(t.state.contextTags.disease,"unknown");assert.equal(t.state.contextTags.age_group,"unknown");assert.equal(t.state.plan,null);
  }
  assert.equal(JSON.stringify(t.state.catalog.inputs),before);
});
check("context changes invalidate plan; technical fields cannot be edited",()=>{
  const t=harness();t.state.plan={plan_id:"old"};t.state.planKey=t.fingerprint();t.setContext("task","attention");assert.equal(t.state.plan,null);
  t.setContext("sampling_rate_hz",512);assert(!Object.hasOwn(t.state.contextTags,"sampling_rate_hz"));
  assert(t.get("input-data-tags").innerHTML.includes("160 Hz"));assert(t.get("input-data-tags").innerHTML.includes("未知 · 位置未核实"));assert(t.get("input-data-tags").innerHTML.includes("人工补充"));
});
check("plan tags take precedence; history never borrows current input tags",()=>{
  const t=harness();t.state.plan={plan_id:"p",data_tags:[{key:"task",label:"任务",value:"sleep",display:"睡眠（计划）",status:"known",kind:"context"}]};t.state.planKey=t.fingerprint();t.renderDataTags();assert(t.get("input-data-tags").innerHTML.includes("睡眠（计划）"));assert(!t.get("input-data-tags").innerHTML.includes("160 Hz"));
  t.state.mode="job";t.state.job={id:"old",plan:{}};t.renderDataTags();assert(t.get("input-data-tags").innerHTML.includes("没有保存数据标签"));assert(!t.get("input-data-tags").innerHTML.includes("160 Hz"));
});
check("input source and use show declared provenance, annotation limits and safe links",()=>{
  const t=harness();t.state.input.provenance={name:"公开实验来源",url:"https://example.test/dataset",version:"1.0",license:"CC0"};t.state.input.data_usage={typical_use:"静息流程检查",annotations:"实验任务标签",annotation_limits:"任务标签不是伪迹真值"};t.renderInputUsage();
  const markup=t.get("input-usage").innerHTML;for(const text of ["公开实验来源","静息流程检查","实验任务标签","任务标签不是伪迹真值","CC0"])assert(markup.includes(text));assert(markup.includes('href="https://example.test/dataset"'));
  t.state.input.provenance.url="javascript:alert(1)";t.state.input.provenance.name="<img src=x>";t.renderInputUsage();assert(!t.get("input-usage").innerHTML.includes('href="javascript:'));assert(t.get("input-usage").innerHTML.includes("&lt;img"));
});
check("historical provenance is frozen and absent fields never borrow current catalog",()=>{
  const t=harness();t.state.input.provenance={name:"当前目录来源",url:"https://example.test/current"};t.state.input.data_usage={typical_use:"当前用途"};
  t.state.mode="job";t.state.job={id:"historic",plan:{input_provenance:{name:"运行时来源",url:"https://example.test/frozen"},input_data_usage:{typical_use:"运行时用途",annotations:"已冻结标注",annotation_limits:"冻结边界"}}};
  const before=JSON.stringify(t.state.job.plan);t.renderInputUsage();let markup=t.get("input-usage").innerHTML;assert(markup.includes("运行时来源"));assert(markup.includes("已冻结标注"));assert(!markup.includes("当前目录来源"));
  t.state.job.plan={};t.renderInputUsage();markup=t.get("input-usage").innerHTML;assert(markup.includes("该历史计划未记录"));assert(!markup.includes("当前目录来源"));
  t.state.job.plan=JSON.parse(before);const saved=t.state.job;t.selectInput("input-1");assert.equal(JSON.stringify(saved.plan),before);assert.equal(t.state.job,null);assert.equal(t.state.mode,"draft");
});
check("a valid plan displays its frozen source instead of later catalog metadata",()=>{
  const t=harness();t.state.input.provenance={name:"当前来源"};t.state.plan={plan_id:"frozen",input_provenance:{name:"规划时来源"},input_data_usage:{typical_use:"规划时用途",annotations:"规划时标注",annotation_limits:"规划时边界"}};t.state.planKey=t.fingerprint();
  t.renderInputUsage();assert(t.get("input-usage").innerHTML.includes("规划时来源"));assert(!t.get("input-usage").innerHTML.includes("当前来源"));
  t.state.input.provenance.name="随后变更的来源";t.renderInputUsage();assert(t.get("input-usage").innerHTML.includes("规划时来源"));assert(!t.get("input-usage").innerHTML.includes("随后变更"));
});
check("method categories preserve dependent execution and only supported switches",()=>{
  const t=harness();const three=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M03")),six=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M06"));
  assert(three.includes("通用"));assert(six.includes("条件"));assert(six.includes("可选"));assert(six.includes("尚未接入"));
  assert.equal((three.match(/type="checkbox"/g)||[]).length,1);assert.equal((six.match(/type="checkbox"/g)||[]).length,1);assert(six.includes("不能在这里独立开关"));
});
check("method blocked state exposes the actual reason and parameters",()=>{
  const t=harness();const plan={plan_id:"p",method_applicability:[{id:"mne_muscle",module_id:"M06",status:"blocked",selected:true,reason:"采样率不足",parameters:{filter_freq:[110,140]}}]};
  t.state.plan=plan;t.state.planKey=t.fingerprint();const cards=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M06"));assert(cards.includes("当前不可用"));assert(cards.includes("采样率不足"));assert(cards.includes("110"));
  const preview=t.methodPlanHtml(plan);assert(preview.includes("当前数据不满足"));assert(preview.includes("采样率不足"));
});
check("historical extension switches reflect saved choices and are read only",()=>{
  const t=harness();t.state.mode="job";t.state.job={id:"j",plan:{qc_config:{method_config:{extensions:["mne_amplitude"]}}}};
  const cards=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M03"));assert(/data-extension="mne_amplitude" checked disabled/.test(cards));assert(cards.includes("历史选择只读"));
});
check("source links allow only HTTP(S); method metadata is escaped",()=>{
  const t=harness();assert.equal(t.safeSourceUrl("javascript:alert(1)"),null);assert.equal(t.safeSourceUrl("data:text/html,hello"),null);
  const module=t.state.catalog.modules.find(m=>m.id==="M03");module.methods[0].name='<img src=x onerror="bad">';module.methods[0].source.url="javascript:bad()";
  const cards=t.methodCardsHtml(module);assert(!cards.includes("<img"));assert(cards.includes("&lt;img"));assert(!cards.includes('href="javascript:'));
});
check("unselected modules never advance the selected-module progress",()=>{
  const t=harness();const selected=["M01","M02","M03","M08","M09"];
  const modules=t.state.catalog.modules.map(m=>({id:m.id,status:selected.includes(m.id)?m.id==="M01"?"completed":"pending":"skipped",reason:selected.includes(m.id)?"":"用户未选择此模块"}));
  t.state.mode="job";t.state.job={plan:{selected_modules:selected,nodes:modules},modules};const p=t.executionProgress(t.state.job);assert.equal(p.total,5);assert.equal(p.percent,20);
  for(const id of ["M04","M05","M06","M07"])assert.equal(t.visualNodes().find(m=>m.id===id).status,"unselected");
});
check("result raw JSON stays available and total score stays uncalibrated",()=>{
  const t=harness();t.state.result={score:{value:99},modules:[{id:"M03",status:"completed",example:"raw retained"}]};t.renderResult();const rendered=t.get("result-content").innerHTML;assert(rendered.includes("raw retained"));assert(rendered.includes("总分尚未校准"));assert(!rendered.includes("99"));
});
check("actual extension summary shows status, reason, counts and raw details",()=>{
  const t=harness();t.state.result={extensions:[{id:"mne_amplitude",name:"MNE 相邻采样变化 / 平线",module_id:"M03",status:"completed",reason:"计算完成，不自动删除",candidate_count:1,parameters:{flat_volts:0}},{id:"mne_muscle",name:"MNE 高频线索",module_id:"M06",status:"skipped",reason:"采样率不足"}]};t.renderResult();
  const markup=t.get("result-content").innerHTML;assert(markup.includes("实际扩展结果"));assert(markup.includes("计算完成"));assert(markup.includes("未执行"));assert(markup.includes("采样率不足"));assert(markup.includes("候选总数：1（待复核）"));assert(markup.includes("未区分时间区间与通道建议"));assert(markup.includes("候选数量：未提供（不按 0 处理）"));assert(markup.includes("flat_volts"));
});
check("zero and typed candidate counts retain their distinct meanings",()=>{
  const t=harness();t.state.result={extensions:[{id:"zero",status:"completed",candidate_count:0},{id:"typed",status:"partial",time_candidate_count:2,channel_candidate_count:3}]};t.renderResult();
  const markup=t.get("result-content").innerHTML;assert(markup.includes("候选总数：0（待复核）"));assert(markup.includes("时间候选：2（待复核）"));assert(markup.includes("通道候选：3（待复核）"));assert(!markup.includes("候选总数：5"));assert(markup.includes("计算完成不代表质量合格"));
});
check("canonical interval/channel fields take precedence over older aliases",()=>{
  const t=harness();t.state.result={extensions:[{id:"canonical",status:"completed",candidate_interval_count:1,time_candidate_count:9,candidate_channel_count:2,channel_candidate_count:7}]};t.renderResult();
  const markup=t.get("result-content").innerHTML;assert(markup.includes("时间候选：1（待复核）"));assert(markup.includes("通道候选：2（待复核）"));assert(!markup.includes("时间候选：9"));assert(!markup.includes("通道候选：7"));
});
check("bridge pairs and analysis segments are not renamed channels or task trials",()=>{
  const t=harness();t.state.result={extensions:[{id:"mne_bridge",status:"completed",candidate_count:2,candidate_pair_count:2},{id:"autoreject_global",status:"partial",candidate_epoch_count:3}]};t.renderResult();
  const markup=t.get("result-content").innerHTML;assert(markup.includes("通道对候选：2（待复核）"));assert(markup.includes("分析分段候选：3（待复核）"));assert(markup.includes("不等于坏通道数"));assert(markup.includes("分析分段不自动等同任务试次"));assert(!markup.includes("通道候选：2"));assert(!markup.includes("任务试次：3"));assert(!markup.includes("当前摘要仅提供总数"));assert(!markup.includes("候选总数：5"));
});
check("old results do not borrow extensions from the current plan",()=>{
  const t=harness();t.state.plan={method_applicability:[{id:"mne_amplitude",status:"ready",selected:true}],qc_config:{method_config:{extensions:["mne_amplitude"]}}};t.state.result={modules:[]};t.renderResult();assert(!t.get("result-content").innerHTML.includes("实际扩展结果"));
  t.state.result={extensions:[],modules:[]};t.renderResult();assert(!t.get("result-content").innerHTML.includes("实际扩展结果"));
});
check("a planning ready state is never rendered as executed",()=>{
  const t=harness();t.state.result={extensions:[{id:"mne_amplitude",status:"ready",reason:"fixture planning state"}]};t.renderResult();const markup=t.get("result-content").innerHTML;assert(markup.includes("执行状态未确认"));assert(!markup.includes('class="tag completed"'));
});
const response = value => ({ok:true,status:200,headers:{get:()=>"application/json"},json:async()=>value});
function recommendationFixture(t, extra={}) {
  const config=JSON.parse(JSON.stringify(t.currentConfig()));config.method_config.extensions=["mne_amplitude"];config.method_config.extension_parameters={mne_amplitude:{flat_volts:0,min_duration_seconds:0.2}};
  return {schema_version:"test",recommendation_id:"r1",plan_id:"preview-only",policy_version:"p1",status:"ready",can_apply:true,summary:"建议基础检查",selected_modules:["M01","M02","M03","M08","M09"],qc_config:config,recommended_methods:[{id:"mne_amplitude",module_id:"M03",name:"平线",reason:"显式零差分候选"}],optional_methods:[],blocked_methods:[],missing_fields:[],cautions:["候选需复核"],...extra};
}
check("Toolkit filters category and availability without changing configuration",()=>{
  const t=harness(),before=t.fingerprint();assert.equal(t.toolkitMethods("optional","available").length,2);assert.equal(t.toolkitMethods("optional","planned")[0].id,"future_check");
  t.get("toolkit-category").value="conditional";t.get("toolkit-implementation").value="available";t.renderToolkit();assert(t.get("toolkit-methods").innerHTML.includes("conditional_check"));assert(!t.get("toolkit-methods").innerHTML.includes("mne_amplitude"));assert.equal(t.fingerprint(),before);
});
check("rich documentation escapes source content and keeps repository paths non-clickable",()=>{
  const t=harness(),markup=t.methodDocumentationHtml({documentation:{purpose:"<img src=x>",how_it_works:"算法机制",interpretation:"候选需复核",when_to_use:["明确配置"],when_not_to_use:"参考未知",validation_status:"未完成临床验证",upstream_call:"module.function",implementation_origin:"本项目封装",version_note:"fixture",references:[{title:"官方",url:"https://example.test/docs",kind:"官方文档"},{title:"源码",url:"src/ephys_qc/runtime.py",kind:"本项目封装"},{title:"危险",url:"javascript:alert(1)"}]}});
  for(const text of ["方法如何工作","怎样解释结果","当前验证证据","算法机制","未完成临床验证","src/ephys_qc/runtime.py"])assert(markup.includes(text));assert(!markup.includes("<img"));assert(!markup.includes('href="src/'));assert(!markup.includes('href="javascript:'));assert(markup.includes('href="https://example.test/docs"'));
});
check("generating recommendations does not overwrite choices; adoption requires another plan",async()=>{
  let t,requests=[];t=harness(async(url,options)=>{requests.push([url,JSON.parse(options.body)]);return response(recommendationFixture(t))});
  t.setExtension("mne_muscle",true);const before=t.fingerprint();await t.makeRecommendation();assert.equal(t.fingerprint(),before);assert(t.recommendationValid());assert.equal(requests[0][0],"/api/v1/recommend");assert(!Object.hasOwn(requests[0][1],"selected_modules"));
  t.applyRecommendation();assert(t.state.recommendationApplied);assert.equal(t.state.selected.size,1);assert(t.state.selected.has("M03"));assert(t.state.extensions.has("mne_amplitude"));assert(!t.state.extensions.has("mne_muscle"));assert.equal(t.currentConfig().method_config.extension_parameters.mne_amplitude.min_duration_seconds,0.2);assert.equal(t.state.plan,null);assert(t.get("run-button").disabled);
});
check("manual changes invalidate recommendation but retain explicit parameters and choices",()=>{
  const t=harness();t.state.recommendation=recommendationFixture(t);t.state.recommendationKey=t.fingerprint();t.applyRecommendation();
  t.setExtension("mne_muscle",true);assert.equal(t.state.recommendation,null);assert(t.state.extensions.has("mne_muscle"));assert.equal(t.currentConfig().method_config.extension_parameters.mne_amplitude.min_duration_seconds,0.2);assert(t.get("recommendation-content").innerHTML.includes("修改已保留"));
  t.get("extension-parameters").value='{"mne_amplitude":{"flat_volts":0.000001}}';t.applyParameters();assert.equal(t.currentConfig().method_config.extension_parameters.mne_amplitude.flat_volts,0.000001);
  const previous=t.fingerprint();t.get("extension-parameters").value='{"unsupported":{}}';t.applyParameters();assert.equal(t.fingerprint(),previous);assert(t.get("parameter-error").textContent.includes("未应用"));
  t.selectInput("input-1");assert.equal(t.currentConfig().method_config.extension_parameters,undefined);assert.equal(t.state.extensions.size,0);
});
check("recommendation cannot apply when service says needs input, or response is stale",async()=>{
  const t=harness();t.state.recommendation=recommendationFixture(t,{can_apply:false,status:"needs_input",reason:"需确认模态",missing_fields:[{key:"modality",label:"模态",reason:"必须明确",blocking:true}]});t.state.recommendationKey=t.fingerprint();const before=t.fingerprint();t.renderRecommendation();t.applyRecommendation();assert.equal(t.fingerprint(),before);assert(t.get("recommendation-content").innerHTML.includes("需先补充"));
  let resolveFetch;const q=harness(()=>new Promise(resolve=>{resolveFetch=resolve}));const pending=q.makeRecommendation();q.setContext("task","attention");resolveFetch(response(recommendationFixture(q)));await pending;assert.equal(q.state.recommendation,null);assert.equal(q.get("recommendation-error").textContent,"");
});
check("needs-input and unsupported recommendations may omit runnable config",async()=>{
  for(const status of ["needs_input","unsupported"]){
    let t;t=harness(async()=>response(recommendationFixture(t,{status,can_apply:false,qc_config:null,plan_id:null,selected_modules:[],summary:"需要补充输入信息",missing_fields:[{key:"modality",label:"模态",reason:"读取后确认模态",blocking:true}]})));
    const before=t.fingerprint();await t.makeRecommendation();assert.equal(t.state.recommendation.status,status);assert(!t.get("recommendation-error").textContent);assert(t.get("recommendation-content").innerHTML.includes("需要补充输入信息"));assert(t.get("recommendation-content").innerHTML.includes("读取后确认模态"));assert(t.get("apply-recommendation-button").disabled);t.applyRecommendation();assert.equal(t.fingerprint(),before);
  }
});
check("recommendation overview stays compact while every reason remains in closed details",()=>{
  const t=harness(),hash="a".repeat(64),policy="fixture-policy-hidden";
  const recommendation=recommendationFixture(t,{recommendation_id:hash,policy_version:policy,recommended_methods:Array.from({length:16},(_,index)=>({id:`method-${index}`,module_id:"M03",name:`建议方法 ${index}`,reason:`完整建议理由 ${index}`})),optional_methods:[{id:"optional",name:"可选项",reason:"可选理由"}],blocked_methods:[{id:"blocked",name:"阻断项",reason:"不适用理由"}],missing_fields:[{key:"modality",label:"模态",reason:"必须确认模态",blocking:true},{key:"coordinates",label:"坐标",reason:"坐标未核实",blocking:false}],cautions:["一般注意事项完整保留"],review_focus:["先核对波形","再复核候选"]});
  t.state.recommendation=recommendation;t.state.recommendationKey=t.fingerprint();const before=t.fingerprint();t.renderRecommendation();const markup=t.get("recommendation-content").innerHTML,overview=markup.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g,"");
  assert(markup.includes('建议采用的方法与理由 <span class="tag subtle">16 项</span>'));assert(markup.includes('可补充字段 <span class="tag subtle">1 项</span>'));assert(!/<details\b[^>]*\bopen(?:\s|=|>)/.test(markup));
  for(const text of ["完整建议理由 15","可选理由","不适用理由","坐标未核实","一般注意事项完整保留",hash,policy]){assert(markup.includes(text));assert(!overview.includes(text));}
  assert(overview.includes("必须确认模态"));assert(overview.includes("1 道 EEG"));assert(markup.includes("检查模块"));assert(markup.includes("默认增强"));assert(!overview.includes("检查模块"));assert(!overview.includes("默认增强"));assert(!overview.includes("先核对波形"));assert(markup.includes("<li>先核对波形</li><li>再复核候选</li>"));assert(!overview.includes("&quot;先核对波形&quot;"));assert.equal(t.fingerprint(),before);
});
check("intake confirms explicit roles, retains source indices and refuses mixed clocks",()=>{
  const t=harness();t.state.intake={id:"read1",metadata:{channels:[{index:0,name:"same",sampling_rate_hz:100},{index:1,name:"same",sampling_rate_hz:100},{index:2,name:"EOG",sampling_rate_hz:100},{index:3,name:"EMG",sampling_rate_hz:1}]}};
  const fields={modality:"scalp_eeg",reference_scheme:"unknown",confirmed:true,context_tags:{disease:"unknown",age_group:"unknown",task:"unknown"}};
  const selected=[{index:0,role:"eeg"},{index:1,role:"eeg"},{index:2,role:"eog"},{index:3,role:"unused"}];const result=t.intakeConfirmation(selected,fields);assert.equal(JSON.stringify(result.eeg_indices),"[0,1]");assert.equal(result.reference_indices.eog,2);assert.equal(result.reference_scheme,"unknown");assert.equal(result.context_tags.disease,"unknown");
  assert.throws(()=>t.intakeConfirmation(selected,{...fields,confirmed:false}),/勾选/);assert.equal(t.intakeConfirmation(selected,{...fields,modality:"seeg"}).modality,"seeg");assert.throws(()=>t.intakeConfirmation(selected,{...fields,modality:"unknown"}),/分析模态/);assert.throws(()=>t.intakeConfirmation([...selected,{index:3,role:"emg"}],fields),/原生采样率/);assert.throws(()=>t.intakeConfirmation([{index:0,role:"eeg"},{index:1,role:"eog"},{index:2,role:"eog"}],fields),/一条/);
});
check("intake roles remain unconfirmed suggestions; actual upload uses local binary contract only",async()=>{
  const calls=[],intake={id:"read-1",status:"needs_confirmation",filename:"测试.edf",metadata:{duration_seconds:30,channels:[{index:0,name:"EEG",unit:"uV",sampling_rate_hz:160}]},suggestions:{eeg_indices:[0],reference_indices:{},reference_scheme:"unknown",context_tags:{disease:"unknown",age_group:"unknown",task:"unknown"}}};
  const t=harness(async(url,options)=>{calls.push([url,options]);return response(intake)});const file={name:"测试.edf",size:1024};t.get("intake-file").files=[file];await t.uploadIntake();
  assert.equal(calls.length,1);assert.equal(calls[0][0],"/api/v1/intakes");assert.equal(calls[0][1].body,file);assert.equal(calls[0][1].headers["Content-Type"],"application/octet-stream");assert.equal(calls[0][1].headers["X-Filename"],encodeURIComponent(file.name));assert.equal(t.pendingIntakeId(),"read-1");
  const markup=t.get("intake-confirmation").innerHTML;assert(markup.includes('value="unknown" selected'));assert(!markup.includes('id="intake-confirmed" type="checkbox" checked'));assert((markup + t.get("record-summary").innerHTML).includes("160 Hz"));assert(markup.includes("待确认建议"));assert.equal(t.state.input,null);assert(t.get("analysis-workspace").hidden);assert(t.get("run-button").disabled);
});
check("confirming intake selects input and automatically prepares without starting a job",async()=>{
  const calls=[],catalog=fixtureCatalog(),input=JSON.parse(JSON.stringify(catalog.inputs[1]));input.id="uploaded-record";input.label="已确认文件";catalog.inputs.push(input);
  let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url==="/api/v1/recommend")return response(recommendationFixture(t));if(url==="/api/v1/plan")return response(planFixture(JSON.parse(options.body)));if(url==="/api/v1/intakes/read-2/confirm")return response({status:"registered",input});if(url==="/api/v1/catalog")return response(catalog);if(url==="/api/v1/jobs"&&!options.method)return response({jobs:[]});throw new Error(`Unexpected ${url}`)});
  t.state.intake={id:"read-2",status:"needs_confirmation",metadata:input.metadata};t.pendingIntakeId("read-2");t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"}];t.get("intake-modality").value="scalp_eeg";t.get("intake-reference").value="unknown";t.get("intake-confirmed").checked=true;t.get("intake-label").value="已确认文件";t.get("intake-source-note").value="已核实来源";
  await t.confirmIntake();assert.equal(t.state.input.id,"uploaded-record");assert.equal(t.get("input-select").value,"uploaded-record");assert.equal(t.pendingIntakeId(),null);assert.equal(t.state.intake.status,"registered");const writes=calls.filter(([,options])=>options.method==="POST");assert.equal(writes.length,3);assert.equal(JSON.parse(writes[0][1].body).confirmed,true);assert(t.validPlan());assert(t.state.recommendationApplied);assert.equal(t.state.job,null);assert(!writes.some(([url])=>url==="/api/v1/jobs"));
});
function planFixture(request, extra={}) {
  return {plan_id:"plan-fixture",selected_modules:request.selected_modules,qc_config:request.qc_config,nodes:fixtureCatalog().modules.map(module=>({...module,status:request.selected_modules.includes(module.id)?"ready":"skipped"})),...extra};
}
function deferred() { let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}; }
check("selecting an input automatically recommends, adopts, and plans, but never creates a job",async()=>{
  const calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/recommend"))return response(recommendationFixture(t));if(url.endsWith("/plan"))return response(planFixture(JSON.parse(options.body)));throw new Error(`Unexpected ${url}`)});
  await t.selectInput("input-1",{autoPrepare:true});assert.equal(calls.map(([url])=>url).join(","),"/api/v1/recommend,/api/v1/plan");assert(t.validPlan());assert(t.state.recommendationApplied);assert(!t.state.manualDraft);assert(!t.get("run-button").disabled);assert.equal(t.state.job,null);assert(t.get("recommendation-content").innerHTML.includes("推荐方案已就绪"));
});
check("initial catalog leaves a file-first landing and makes only catalog and history requests",async()=>{
  const calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/catalog"))return response(fixtureCatalog());if(url.endsWith("/jobs")&&!options.method)return response({jobs:[{id:"older-running",status:"running"}]});throw new Error(`Unexpected ${url}`)},{selected:false});
  assert(await t.loadCatalog());assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert.equal(t.state.recommendation,null);assert.equal(t.state.mode,"draft");assert.equal(t.state.job,null);assert.equal(t.get("input-select").value,"");assert(t.get("analysis-workspace").hidden);assert(t.get("input-metadata").hidden);assert(!t.get("run-history-panel").open);assert(t.get("run-button").disabled);assert.deepEqual(calls.map(([url])=>url),["/api/v1/catalog","/api/v1/jobs"]);
});
check("A to B to A rejects older recommendation responses using an epoch even when fingerprints match",async()=>{
  const pending=[];let t;t=harness((url,options)=>{if(url.endsWith("/recommend")){const d=deferred();pending.push({d,rec:recommendationFixture(t)});return d.promise}if(url.endsWith("/plan"))return Promise.resolve(response(planFixture(JSON.parse(options.body))));throw new Error("Unexpected job")});
  const a=t.selectInput("input-0",{autoPrepare:true}),b=t.selectInput("input-1",{autoPrepare:true}),a2=t.selectInput("input-0",{autoPrepare:true});assert(t.get("run-button").disabled);
  pending[0].d.resolve(response({...pending[0].rec,recommendation_id:"obsolete-A"}));await a;assert.equal(t.state.recommendation,null);assert(t.state.recommending);
  pending[2].d.resolve(response({...pending[2].rec,recommendation_id:"latest-A"}));await a2;assert.equal(t.state.recommendation.recommendation_id,"latest-A");assert(t.validPlan());
  pending[1].d.resolve(response({...pending[1].rec,recommendation_id:"obsolete-B"}));await b;assert.equal(t.state.recommendation.recommendation_id,"latest-A");assert(!t.get("run-button").disabled);
});
check("late plan success and late failure cannot replace a newly selected input plan",async()=>{
  const pending=[];let t;t=harness(async(url,options)=>{if(url.endsWith("/recommend"))return response(recommendationFixture(t));if(url.endsWith("/plan")){const d=deferred();pending.push({d,request:JSON.parse(options.body)});return d.promise}throw new Error("Unexpected")});
  const a=t.selectInput("input-0",{autoPrepare:true});await new Promise(resolve=>setImmediate(resolve));
  const b=t.selectInput("input-1",{autoPrepare:true});await new Promise(resolve=>setImmediate(resolve));
  pending[1].d.resolve(response(planFixture(pending[1].request,{plan_id:"latest"})));await b;
  pending[0].d.reject(new Error("old request failed"));await a;assert.equal(t.state.plan.plan_id,"latest");assert.equal(t.get("plan-error").textContent,"");assert(t.validPlan());
});
check("manual edits during auto preparation preserve choices and discard late automatic recommendations",async()=>{
  const wait=deferred();let t;t=harness(()=>wait.promise);const pending=t.selectInput("input-0",{autoPrepare:true});const rec=recommendationFixture(t);
  t.setExtension("mne_muscle",true);t.setContext("disease","other");assert(t.state.manualDraft);const key=t.fingerprint();wait.resolve(response(rec));await pending;
  assert.equal(t.fingerprint(),key);assert(t.state.extensions.has("mne_muscle"));assert.equal(t.state.recommendation,null);assert(!t.state.recommending);assert(!t.get("run-button").disabled);assert(t.get("recommendation-content").innerHTML.includes("恢复推荐方案"));
});
check("failed, blocked, unsupported and malformed auto recommendations never enable default Start",async()=>{
  for(const result of [new Error("offline"),{can_apply:false,status:"needs_input"},{can_apply:false,status:"unsupported"},{can_apply:true,qc_config:null}]){
    const calls=[];let t;t=harness(async(url)=>{calls.push(url);if(result instanceof Error)throw result;return response(recommendationFixture(t,result))});await t.selectInput("input-0",{autoPrepare:true});assert(t.get("run-button").disabled);await t.startJob();assert.deepEqual(calls,["/api/v1/recommend"]);assert.equal(t.state.job,null);
  }
});
check("a failed automatic plan keeps Start blocked until reset or explicit manual changes",async()=>{
  let t;t=harness(async(url)=>{if(url.endsWith("/recommend"))return response(recommendationFixture(t));throw new Error("plan unavailable")});await t.selectInput("input-0",{autoPrepare:true});assert(t.get("run-button").disabled);assert(!t.state.manualDraft);assert(t.get("plan-error").textContent.includes("plan unavailable"));assert(t.get("recommendation-content").innerHTML.includes("方案核对未完成"));assert(t.get("recommendation-content").innerHTML.includes("data-reset-recommend"));assert(!t.get("recommendation-content").innerHTML.includes("正在核对推荐方案"));
});
check("one explicit Start replans a manual draft and submits exactly once",async()=>{
  const calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/plan"))return response(planFixture(JSON.parse(options.body)));if(url.endsWith("/jobs")&&options.method==="POST")return response({id:"new-job",status:"failed",plan:t.state.plan,modules:[]});if(url.endsWith("/jobs"))return response({jobs:[]});throw new Error(`Unexpected ${url}`)});
  t.setModuleSelected("M07",false);t.get("start-seconds").value="10";t.invalidatePlan();await t.startJob();assert.equal(calls.filter(([url,opt])=>url.endsWith("/jobs")&&opt.method==="POST").length,1);assert.equal(calls[0][0],"/api/v1/plan");const request=JSON.parse(calls[1][1].body);assert.equal(request.qc_config.selection.start_seconds,10);assert(!request.selected_modules.includes("M07"));assert.equal(request.plan_id,"plan-fixture");assert.equal(t.state.mode,"job");
});
check("Start locks input switching and repeat clicks while a manual plan is pending",async()=>{
  const wait=deferred(),calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/plan"))return wait.promise;if(url.endsWith("/jobs")&&options.method)return response({id:"j",status:"failed",plan:t.state.plan,modules:[]});return response({jobs:[]})});
  t.setContext("task","attention");const pending=t.startJob();assert(t.get("run-button").disabled);await t.selectInput("input-1",{autoPrepare:true});await t.startJob();assert.equal(t.state.input.id,"input-0");assert.equal(calls.length,1);wait.resolve(response(planFixture(JSON.parse(calls[0][1].body))));await pending;assert.equal(calls.filter(([url,opt])=>url.endsWith("/jobs")&&opt.method).length,1);
});
check("failed manual planning and unapplied invalid JSON cannot create a job",async()=>{
  const calls=[];const t=harness(async(url)=>{calls.push(url);throw new Error("invalid plan")});t.setContext("task","attention");await t.startJob();assert.deepEqual(calls,["/api/v1/plan"]);
  t.state.parameterDirty=true;t.get("extension-parameters").value="{";await t.startJob();assert.deepEqual(calls,["/api/v1/plan"]);assert(t.get("parameter-error").textContent.includes("未应用"));assert(t.get("plan-error").textContent.includes("高级参数有误"));assert(t.get("advanced-settings").open);
});
check("history selection invalidates pending preparation and never adopts current draft into the saved plan",async()=>{
  const wait=deferred();let t;t=harness(()=>wait.promise);const pending=t.selectInput("input-1",{autoPrepare:true});const rec=recommendationFixture(t);await t.selectJob("history",{id:"history",label:"历史记录",status:"failed",plan:{plan_id:"saved",nodes:[],selected_modules:[]},modules:[]});wait.resolve(response(rec));await pending;assert.equal(t.state.mode,"job");assert.equal(t.state.job.plan.plan_id,"saved");assert.equal(t.state.recommendation,null);assert(t.get("run-button").disabled);assert(t.get("recommendation-content").innerHTML.includes("已有运行：历史记录"));
});
check("reset recommendation is explicit, replaces method choices, and preserves chosen window",async()=>{
  let t;t=harness(async(url,options)=>url.endsWith("/recommend")?response(recommendationFixture(t)):response(planFixture(JSON.parse(options.body))));t.setExtension("mne_muscle",true);t.get("start-seconds").value="15";t.invalidatePlan();await t.prepareRecommendedPlan();assert(!t.state.manualDraft);assert(t.state.extensions.has("mne_amplitude"));assert(!t.state.extensions.has("mne_muscle"));assert.equal(t.currentConfig().selection.start_seconds,15);assert(t.validPlan());
});
check("method details stay closed while module input output and dependencies stay visible",()=>{
  const t=harness();t.showModule("M03");const html=t.get("module-dialog-content").innerHTML;assert(html.includes("输入"));assert(html.includes("输出"));assert(html.includes("依赖模块"));assert(html.includes('<details class="method-more"><summary>原理、条件与来源</summary>'));assert(!/<details\b[^>]*\bopen(?:\s|=|>)/.test(html));
});
check("intake suggestions require an explicit modality and role confirmation",()=>{
  const t=harness();t.state.intake={id:"x",metadata:{channels:[{index:0,name:"EEG",sampling_rate_hz:100}]},suggestions:{eeg_indices:[0],reference_indices:{}}};t.renderIntake();const html=t.get("intake-confirmation").innerHTML;assert(html.includes('value="eeg" selected'));assert(html.includes('<select id="intake-modality">'));assert(html.includes('value="unknown" selected'));assert(!html.includes('type="hidden" value="scalp_eeg"'));assert(!/<details\b[^>]*\bopen(?:\s|=|>)/.test(html));assert(!/id="intake-confirmed"[^>]*checked/.test(html));assert(html.includes("已核对分析模态和通道角色"));assert(html.includes("未知"));
  t.state.intake.suggestions.eeg_indices=[];t.renderIntake();assert(/<details\b[^>]*\bopen(?:\s|=|>)/.test(t.get("intake-confirmation").innerHTML));
});
check("pending history requests show no current draft evidence and cannot overwrite an input switch",async()=>{
  const wait=deferred();const t=harness(()=>wait.promise);t.state.plan={plan_id:"draft",input_provenance:{name:"draft source"},nodes:[],selected_modules:["M03"]};t.state.planKey=t.fingerprint();
  const pending=t.selectJob("old");assert.equal(t.state.job,null);assert(t.get("input-usage").innerHTML.includes("该历史计划未记录"));assert(!t.get("input-usage").innerHTML.includes("draft source"));assert(!t.visualNodes().some(node=>node.status==="ready"));
  await t.selectInput("input-1");wait.resolve(response({id:"old",label:"旧任务",status:"failed",plan:{plan_id:"old"},modules:[]}));await pending;assert.equal(t.state.mode,"draft");assert.equal(t.state.job,null);assert.equal(t.state.input.id,"input-1");
});
check("registered records remain secondary and curated cards are not rendered",()=>{
  const t=harness();t.renderExamplePresets();assert.equal(t.get("example-presets").innerHTML,"");assert(t.get("example-presets").hidden);
});
check("choosing a new local file immediately clears old draft and result before reading",async()=>{
  const calls=[];const t=harness(async(url)=>{calls.push(url);throw new Error("No automatic calls expected")});t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.state.job={id:"old-job",status:"completed",plan:t.state.plan};t.state.result={modules:[]};
  t.get("intake-file").files=[{name:"fresh.edf",size:4096}];t.chooseLocalFile();assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert.equal(t.state.job,null);assert.equal(t.state.result,null);assert(t.state.filePending);assert(t.get("analysis-workspace").hidden);assert(t.get("input-metadata").hidden);assert(t.get("run-button").disabled);await t.startJob();assert.deepEqual(calls,[]);
});
check("new local file invalidates a prior automatic recommendation response",async()=>{
  const wait=deferred();let t;t=harness(()=>wait.promise);const old=t.selectInput("input-1",{autoPrepare:true}),rec=recommendationFixture(t);t.get("intake-file").files=[{name:"fresh.edf",size:4096}];t.chooseLocalFile();wait.resolve(response(rec));await old;assert.equal(t.state.input,null);assert.equal(t.state.recommendation,null);assert.equal(t.state.plan,null);assert(t.get("run-button").disabled);assert(t.get("analysis-workspace").hidden);
});
check("reading a fresh generic file cannot use a previous input or start before explicit confirmation",async()=>{
  const calls=[],intake={id:"generic-file",status:"needs_confirmation",filename:"my-recording.edf",metadata:{format:"EDF",size_bytes:2048,duration_seconds:30,channels:[{index:0,name:"EEG A",sampling_rate_hz:100},{index:2,name:"EEG B",sampling_rate_hz:100}]},suggestions:{eeg_indices:[0,2],reference_indices:{},reference_scheme:"unknown"}};
  const t=harness(async(url,options)=>{calls.push([url,options]);return response(intake)});t.get("intake-file").files=[{name:"my-recording.edf",size:2048}];await t.uploadIntake();assert.equal(t.state.input,null);assert(t.state.filePending);assert(t.get("analysis-workspace").hidden);assert(!t.get("intake-confirmation").hidden);assert(t.get("run-button").disabled);await t.startJob();assert.equal(calls.length,1);assert.equal(calls[0][0],"/api/v1/intakes");assert.equal(t.state.job,null);
  t.get("intake-modality").value="scalp_eeg";t.get("intake-confirmed").checked=false;await t.confirmIntake();assert.equal(calls.length,1);assert(t.get("intake-error").textContent.includes("勾选"));assert.equal(t.state.input,null);
});
check("failed file read leaves no prior draft available to run",async()=>{
  const t=harness(async()=>{throw new Error("file invalid")});t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.get("intake-file").files=[{name:"invalid.edf",size:10}];await t.uploadIntake();assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert.equal(t.state.intake,null);assert(t.get("run-button").disabled);assert(t.get("analysis-workspace").hidden);assert(t.get("intake-error").textContent.includes("file invalid"));
});
check("late file reads cannot replace a newer pending file",async()=>{
  const requests=[];const t=harness(()=>{const d=deferred();requests.push(d);return d.promise});t.get("intake-file").files=[{name:"a.edf",size:100}];const a=t.uploadIntake();t.get("intake-file").files=[{name:"b.edf",size:100}];t.chooseLocalFile();const b=t.uploadIntake();
  const meta={duration_seconds:30,channels:[{index:0,name:"EEG",sampling_rate_hz:100}]};requests[1].resolve(response({id:"b",filename:"b.edf",status:"needs_confirmation",metadata:meta,suggestions:{eeg_indices:[0]}}));await b;requests[0].resolve(response({id:"a",filename:"a.edf",status:"needs_confirmation",metadata:meta,suggestions:{eeg_indices:[0]}}));await a;assert.equal(t.state.intake.id,"b");assert.equal(t.pendingIntakeId(),"b");assert.equal(t.state.input,null);assert(t.get("run-button").disabled);
});
check("late confirmation cannot auto-select an older file after a new file choice",async()=>{
  const wait=deferred(),calls=[];const t=harness((url)=>{calls.push(url);return wait.promise});t.state.intake={id:"a",metadata:{channels:[{index:0,sampling_rate_hz:100}]}};t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"}];t.get("intake-modality").value="scalp_eeg";t.get("intake-confirmed").checked=true;t.get("intake-reference").value="unknown";
  const pending=t.confirmIntake();t.get("intake-file").files=[{name:"new.edf",size:100}];t.chooseLocalFile();wait.resolve(response({status:"registered",input:{id:"old-registered"}}));await pending;assert.deepEqual(calls,["/api/v1/intakes/a/confirm"]);assert.equal(t.state.input,null);assert.equal(t.state.intake,null);assert(t.state.filePending);assert(t.get("analysis-workspace").hidden);
});
check("an unrecognized local filename follows read-confirm-recommend-plan without borrowing example metadata",async()=>{
  const calls=[],catalog=fixtureCatalog(),metadata={format:"EDF",duration_seconds:80,size_bytes:2048,channels:[{index:0,name:"A",sampling_rate_hz:100,unit:"uV"},{index:2,name:"B",sampling_rate_hz:100,unit:"uV"}]};
  const intake={id:"fresh-intake",status:"needs_confirmation",filename:"my-lab-file.edf",metadata,suggestions:{eeg_indices:[0,2],reference_indices:{},reference_scheme:"unknown"}};
  const input={id:"local-new-uuid",label:"my-lab-file.edf",metadata,default_config:{selection:{eeg_indices:[0,2],reference_indices:{},start_seconds:0,duration_seconds:60},context_tags:{disease:"unknown",age_group:"unknown",task:"unknown"},method_config:{comparison_groups:null}}};
  let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url==="/api/v1/intakes")return response(intake);if(url.endsWith("/confirm")){catalog.inputs.push(input);return response({status:"registered",input})}if(url.endsWith("/catalog"))return response(catalog);if(url.endsWith("/recommend"))return response(recommendationFixture(t));if(url.endsWith("/plan"))return response(planFixture(JSON.parse(options.body)));if(url.endsWith("/jobs")&&!options.method)return response({jobs:[]});throw new Error(`Unexpected ${url}`)},{selected:false});
  t.get("intake-file").files=[{name:"my-lab-file.edf",size:2048}];await t.uploadIntake();assert(t.get("analysis-workspace").hidden);assert.equal(t.state.input,null);
  t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"},{dataset:{intakeChannel:"2"},value:"eeg"}];t.get("intake-modality").value="scalp_eeg";t.get("intake-reference").value="unknown";t.get("intake-confirmed").checked=true;t.get("intake-label").value="my-lab-file.edf";
  await t.confirmIntake();assert.equal(t.state.input.id,"local-new-uuid");assert.equal(JSON.stringify(t.currentConfig().selection.eeg_indices),"[0,2]");assert.equal(t.currentConfig().context_tags.disease,"unknown");assert.equal(t.currentConfig().method_config.comparison_groups,null);assert(t.validPlan());assert(!t.get("analysis-workspace").hidden);assert(!t.get("input-metadata").hidden);assert(!t.get("run-button").disabled);assert.equal(t.state.job,null);assert(!calls.some(([url,options])=>url==="/api/v1/jobs"&&options.method));assert.equal(t.get("selected-file-name").textContent,"my-lab-file.edf");
});
check("a late catalog response cannot choose a previously confirmed file after a new selection",async()=>{
  const wait=deferred();const t=harness(async(url)=>url.endsWith("/catalog")?wait.promise:response({jobs:[]}));t.state.intakeRequest=1;t.state.intakeBusy=true;t.state.intake={id:"a",status:"registered"};const pending=t.loadCatalog("input-0",{intakeRequest:1});t.get("intake-file").files=[{name:"next.edf",size:100}];t.chooseLocalFile();wait.resolve(response(fixtureCatalog()));await pending;assert.equal(t.state.input,null);assert(t.state.filePending);assert(t.get("analysis-workspace").hidden);assert(t.get("run-button").disabled);
});
check("static field and DOM references stay consistent",()=>{
  const dynamic=["effective-config","retry-catalog-button","intake-modality","intake-reference","intake-confirmed","intake-label","intake-source-note","intake-confirm-button","intake-modality-note","revision-annotation","revision-verified","revision-highpass","revision-lowpass","revision-processing-note","window-page","window-state-details"];
  for(const match of source.matchAll(/\$\("([^"]+)"\)/g))assert(ids.includes(match[1])||dynamic.includes(match[1]),`Missing element ${match[1]}`);
  for(const field of fields)assert(ids.includes(`context-${field}`));
});
check("module links and fragments accept only exact M01 to M09 IDs",()=>{
  const t=harness(undefined,{selected:false});
  for(let n=1;n<=9;n++){const id=`M0${n}`;assert.equal(t.moduleStandardsUrl(id),`/standards/modules/${id}`);assert.equal(t.moduleFromHash(`#module-${id}`),id)}
  for(const id of ["M00","M10","m01","M01/../../jobs","M01?run=1","M01\" onclick=\"bad","",null])assert.equal(t.moduleStandardsUrl(id),null);
  for(const hash of ["#module-M00","#module-M10","#module-m01","#module-%4D01","#module-M01/","#module-M01?run=1","#module-M01\n","#module-M01-extra","#other","",null])assert.equal(t.moduleFromHash(hash),null);
});
check("all nine module deep links open after an empty catalog without selecting or running",async()=>{
  for(let n=1;n<=9;n++){
    const id=`M0${n}`,calls=[],catalog=fixtureCatalog();catalog.inputs=[];
    const t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/catalog"))return response(catalog);if(url.endsWith("/jobs")&&!options.method)return response({jobs:[]});throw new Error(`Unexpected ${url}`)},{selected:false,hash:`#module-${id}`});
    t.state.catalog=null;assert(await t.loadCatalog());assert(t.get("module-dialog").open);assert.equal(t.state.dialogModule,id);assert.equal(t.get("module-details-link").attrs.href,`/standards/modules/${id}`);assert.equal(t.state.input,null);assert.equal(t.state.recommendation,null);assert.equal(t.state.plan,null);assert.equal(t.state.job,null);assert(t.get("analysis-workspace").hidden);assert(t.get("run-button").disabled);assert.deepEqual(calls.map(([url])=>url),["/api/v1/catalog","/api/v1/jobs"]);
  }
});
check("hash changes only read module information and preserve the current draft",()=>{
  const t=harness();t.setExtension("mne_amplitude",true);t.setContext("task","attention");t.state.plan={plan_id:"kept",nodes:[]};t.state.planKey=t.fingerprint();
  const before=t.fingerprint(),plan=t.state.plan,epoch=t.state.draftEpoch;
  t.setHash("#module-M03");assert.equal(t.state.dialogModule,"M03");t.setHash("#module-M09");assert.equal(t.state.dialogModule,"M09");assert.equal(t.fingerprint(),before);assert.equal(t.state.plan,plan);assert.equal(t.state.draftEpoch,epoch);assert.equal(t.state.job,null);assert.equal(t.state.recommendation,null);assert.equal(t.get("module-details-link").attrs.href,"/standards/modules/M09");
});
check("hash received before catalog readiness is applied only to the latest fragment",async()=>{
  const wait=deferred(),calls=[];const t=harness(async(url)=>{calls.push(url);return url.endsWith("/catalog")?wait.promise:response({jobs:[]})},{selected:false,hash:"#module-M01"});
  t.state.catalog=null;const pending=t.loadCatalog();t.setHash("#module-M06");assert(!t.get("module-dialog").open);wait.resolve(response(fixtureCatalog()));await pending;assert.equal(t.state.dialogModule,"M06");assert.equal(t.state.input,null);assert.deepEqual(calls,["/api/v1/catalog","/api/v1/jobs"]);
});
check("invalid deep links and forged catalog IDs cannot open or produce links",async()=>{
  const catalog=fixtureCatalog();catalog.modules.push({id:"M01/../../jobs",name:"invalid"});
  const t=harness(async(url)=>response(url.endsWith("/catalog")?catalog:{jobs:[]}),{selected:false,hash:"#module-M99"});await t.loadCatalog();assert(!t.get("module-dialog").open);assert.equal(t.state.input,null);
  t.showModule("M01/../../jobs");assert(!t.get("module-dialog").open);assert.equal(t.get("module-details-link").attrs.href,undefined);
  t.setHash("#module-M02");t.setHash("#module-M02?run=1");assert.equal(t.state.dialogModule,"M02");assert.equal(t.get("module-details-link").attrs.href,"/standards/modules/M02");
});
check("closing a deep-linked dialog clears only its fragment without history navigation or loops",()=>{
  const t=harness(undefined,{selected:false});t.location.search="?view=local";t.setHash("#module-M04");t.get("close-dialog-button").dispatch("click");assert(!t.get("module-dialog").open);assert.equal(t.state.dialogModule,null);assert.equal(t.location.hash,"");assert.equal(t.location.search,"?view=local");assert.deepEqual(t.history.replacements,["/?view=local"]);
  t.moduleDialogClosed();assert.equal(t.history.replacements.length,1);
  t.setHash("#module-M08");t.setHash("#unrelated-section");t.get("module-dialog").close();assert.equal(t.location.hash,"#unrelated-section");assert.equal(t.history.replacements.length,1);
});
check("a queued close event does not clear a newly opened module",()=>{
  const t=harness(undefined,{selected:false});t.setHash("#module-M01");t.get("module-dialog").open=false;t.setHash("#module-M03");t.moduleDialogClosed();assert(t.get("module-dialog").open);assert.equal(t.state.dialogModule,"M03");assert.equal(t.location.hash,"#module-M03");assert.equal(t.history.replacements.length,0);
});
check("detailed module link is outside collapsed content and preserves the draft tab",()=>{
  const match=html.match(/<a\b[^>]*id="module-details-link"[^>]*>.*?<\/a>/);assert(match);assert(match[0].includes('target="_blank"'));assert(match[0].includes('rel="noopener noreferrer"'));assert(match[0].includes("详细介绍"));assert(html.indexOf('id="module-details-link"')<html.indexOf('id="module-dialog-content"'));assert(!match[0].includes("data-detail="));
});
check("empty intake exposes nine neutral modules without choosing or planning",()=>{
  const t=harness(undefined,{selected:false});
  assert.equal(t.visualNodes().length,9);assert(t.visualNodes().every(node=>node.status==="framework"));
  assert.equal(t.get("pipeline-state").textContent,"框架预览");assert(t.get("pipeline-caption").textContent.includes("上传文件"));
  assert.equal((t.get("pipeline").innerHTML.match(/data-detail=/g)||[]).length,9);
  assert(!t.get("pipeline").innerHTML.includes("已选择"));assert(!t.get("pipeline").innerHTML.includes("就绪"));assert(t.get("plan-disclosure").hidden);
  t.state.catalog=null;t.renderPipeline();assert.equal((t.get("pipeline").innerHTML.match(/ disabled /g)||[]).length,9);
});
check("reading and confirming never imply that quality checks have executed",()=>{
  const t=harness(undefined,{selected:false});t.state.filePending=true;t.state.intakeBusy=true;t.updateActions();assert.equal(t.get("pipeline-state").textContent,"读取中");
  t.state.intakeBusy=false;t.state.intake={id:"read",status:"received"};t.updateActions();assert.equal(t.get("pipeline-state").textContent,"待确认");assert(t.visualNodes().every(node=>node.status==="framework"));assert(t.get("run-button").disabled);
});
check("choosing a new file clears completed graph, label, and historical legend",()=>{
  const t=harness();t.state.mode="job";t.state.job={id:"old",label:"old-private-label",status:"completed",plan:{selected_modules:["M01","M02","M08","M09"]},modules:[{id:"M01",status:"completed"}]};t.updateActions();assert.equal(t.get("pipeline-state").textContent,"已完成");
  t.get("intake-file").files=[{name:"new.edf",size:4096}];t.chooseLocalFile();assert.equal(t.get("pipeline-state").textContent,"待读取");assert(!t.get("pipeline-caption").textContent.includes("old-private-label"));assert(!t.get("pipeline").innerHTML.includes("已完成"));assert(t.get("pipeline-legend").hidden);assert(t.get("plan-disclosure").hidden);
  t.get("intake-file").files=[];t.chooseLocalFile();assert.equal(t.get("pipeline-state").textContent,"框架预览");
});
check("planning has a preparation label and never an execution label",()=>{
  const t=harness();t.state.recommending=true;t.updateActions();assert.equal(t.get("pipeline-state").textContent,"准备方案");assert(!t.get("pipeline").innerHTML.includes("运行中"));
  t.state.recommending=false;t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.updateActions();assert.equal(t.get("pipeline-state").textContent,"方案就绪");assert(!t.get("plan-disclosure").hidden);assert(t.get("pipeline-legend").hidden);
});
check("submission replaces the ready prompt until the service confirms a job",()=>{
  const t=harness();t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.state.submitting=true;t.updateActions();assert.equal(t.get("pipeline-state").textContent,"正在提交");assert(!t.get("pipeline-caption").textContent.includes("点击开始检查"));assert(t.get("run-button").disabled);
});
check("history loading never borrows the draft name or plan",()=>{
  const t=harness();t.state.mode="job";t.state.job=null;t.updateActions();assert.equal(t.get("pipeline-state").textContent,"状态未载入");assert(!t.get("pipeline-caption").textContent.includes("输入 0"));assert(t.visualNodes().every(node=>node.status==="pending"));assert(t.get("plan-disclosure").hidden);
});
check("graph preserves historical selection, actual states and escaped labels",()=>{
  const t=harness();t.state.mode="job";t.state.job={id:"h",label:"<img src=x>",status:"partial",plan:{selected_modules:["M01","M02","M03","M08","M09"]},modules:[{id:"M03",status:"partial",reason:"<script>bad</script>"},{id:"M04",status:"skipped"}]};t.updateActions();assert.equal(t.get("pipeline-state").textContent,"条件受限");assert(!t.get("pipeline").innerHTML.includes("<script>"));assert.equal(t.visualNodes().find(n=>n.id==="M04").status,"unselected");assert.equal(t.visualNodes().find(n=>n.id==="M03").status,"partial");assert(!t.get("pipeline-legend").hidden);
});
check("extraction shows file facts and separates annotation absence from unknown parsing",()=>{
  const t=harness(undefined,{selected:false});t.state.filePending=true;t.state.intake={id:"new",filename:"私有<script>.set",metadata:{format:"EEGLAB",duration_seconds:31.25,channels:[{index:0,name:"FP1",sampling_rate_hz:250}],annotations:{available:true,count:3,kinds:["<img src=x>","trigger"]},reader_id:"mne_eeglab"}};t.renderExtraction();
  let markup=t.get("record-summary").innerHTML;for(const text of ["EEGLAB","31.25 s","250 Hz","3 条记录","待确认"])assert(markup.includes(text));assert(markup.includes("&lt;script&gt;"));assert(!markup.includes("<img src=x>"));assert(!t.get("record-summary").hidden);assert(!t.get("workflow-panel").open);
  assert.equal(t.annotationText({annotations:{count:null}}),"尚未解析");assert.equal(t.annotationText({annotations:{count:0}}),"未检出标注");
});
check("historical extraction never borrows a new file header or unconfirmed form",()=>{
  const t=harness();t.state.intake={id:"pending",status:"needs_confirmation",filename:"current-secret"};t.state.mode="job";t.state.job={id:"old",plan:{}};t.updateActions();assert(t.get("record-summary").hidden);assert(t.get("intake-confirmation").hidden);assert(!t.get("record-summary").innerHTML.includes("current-secret"));
  t.state.job.plan={input_metadata:{format:"BDF",duration_seconds:42,channels:[],annotations:{count:0}},input_modality:{value:"scalp_eeg",source:"user_confirmed"}};t.renderExtraction();assert(t.get("record-summary").innerHTML.includes("BDF"));assert(t.get("record-summary").innerHTML.includes("42 s"));
});
check("unsupported modality preserves extracted information but never produces a runnable plan",async()=>{
  const t=harness();t.state.input.modality="seeg";t.state.recommendation={status:"unsupported",can_apply:false};t.updateActions();assert.equal(t.get("pipeline-state").textContent,"仅信息提取");assert(t.get("run-button").disabled);assert(t.visualNodes().every(n=>n.status==="unplanned"));assert(!t.get("record-summary").hidden);
});
check("non-scalp modality remains extraction-only after manual edits and creates no plan or job",async()=>{
  for(const modality of ["seeg","ecog","extracellular","other","unknown"]){
    const calls=[],t=harness(async(url,options={})=>{calls.push([url,options]);return response({recommendation_id:"unsupported",status:"unsupported",can_apply:false,reason:"No QC route for this modality"})});
    t.state.input.modality=modality;t.state.recommendation={status:"unsupported",can_apply:false};t.updateActions();
    t.setContext("disease","other");assert.equal(t.state.recommendation,null);assert(t.state.manualDraft);
    t.get("start-seconds").value="10";t.invalidatePlan();t.setExtension("mne_amplitude",true);
    assert(t.get("run-button").disabled);assert(t.get("plan-button").disabled);assert(!t.get("recommend-button").disabled);
    assert.equal(t.get("pipeline-state").textContent,"仅信息提取");assert(t.get("action-hint").textContent.includes("不运行头皮 EEG"));
    assert(t.visualNodes().every(node=>node.status==="unplanned"));assert(t.get("recommendation-content").innerHTML.includes("仅信息提取"));assert(!t.get("recommendation-content").innerHTML.includes("开始检查时会先核对"));assert(!t.get("record-summary").hidden);
    assert.equal(await t.makePlan(),false);await t.startJob();assert.equal(calls.length,0);
    await t.makeRecommendation();assert.deepEqual(calls.map(([url])=>url),["/api/v1/recommend"]);assert(t.get("run-button").disabled);
    // Viewing a saved run must still use that run's statuses, not the draft's modality.
    t.state.mode="job";t.state.job={id:"past",status:"completed",plan:{selected_modules:["M01"]},modules:[{id:"M01",status:"completed"}]};t.updateActions();
    assert.equal(t.get("pipeline-state").textContent,"已完成");assert.equal(t.visualNodes().find(node=>node.id==="M01").status,"completed");
  }
});
check("recording scope uses the full-record contract while window scope retains its bounded validation",()=>{
  const t=harness(),before=JSON.stringify(t.state.input.default_config);t.get("duration-seconds").value=250;t.setScope("recording");assert.equal(t.currentConfig().scope,"recording");assert(t.get("start-seconds").disabled);assert(t.get("duration-seconds").disabled);assert(!t.get("run-button").disabled);assert.equal(JSON.stringify(t.state.input.default_config),before);t.setScope("window");assert.equal(t.get("duration-seconds").value,"120");assert(!t.get("duration-seconds").disabled);
});
check("configuration drafts restore without recommendations or analysis and preserve source lineage",()=>{
  const t=harness();t.setExtension("mne_amplitude",true);t.get("start-seconds").value=80;t.setContext("task","attention");t.state.parentJobId="parent";t.saveDraft();const saved=t.savedDraft();assert.equal(saved.qc_config.selection.start_seconds,80);assert.equal(saved.parent_job_id,"parent");assert(!JSON.stringify(saved).includes("waveform"));t.selectInput("input-1");t.applyConfiguration(saved);assert.equal(t.state.input.id,"input-0");assert(t.state.extensions.has("mne_amplitude"));assert.equal(t.state.parentJobId,"parent");assert.equal(t.state.mode,"draft");assert.equal(t.state.plan,null);t.discardDraft();assert.equal(t.savedDraft(),null);
});
check("clone fetches a saved configuration and does not create a job or rerun recommendation",async()=>{
  const calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);return response({input_id:"input-1",selected_modules:["M01","M02","M04","M08","M09"],qc_config:t.state.catalog.inputs[1].default_config,parent_job_id:"original"})});t.state.mode="job";t.state.job={id:"original",status:"completed"};await t.cloneJobConfiguration();assert.equal(calls.length,1);assert(calls[0][0].endsWith("/configuration"));assert.equal(t.state.input.id,"input-1");assert.deepEqual([...t.state.selected],["M04"]);assert.equal(t.state.parentJobId,"original");assert.equal(t.state.plan,null);assert.equal(t.state.job,null);
});
check("stable job links preserve language and restore only the selected saved job",async()=>{
  const calls=[];const t=harness(async(url)=>{calls.push(url);return response({id:"stable-job",status:"failed",plan:{},modules:[]})},{selected:false});t.location.search="?lang=en&job=stable-job";assert(t.jobLocation("other").includes("lang=en"));await t.restoreNavigation();assert.equal(t.state.job.id,"stable-job");assert.equal(calls.length,1);assert(calls[0].endsWith("/stable-job"));assert(t.location.search.includes("job=stable-job"));t.selectInput("input-0");assert(!t.location.search.includes("job="));assert(t.location.search.includes("lang=en"));
});
check("record revision is explicit and cancelling keeps the original immutable",()=>{
  const t=harness(),before=JSON.stringify(t.state.input);t.state.input.modality="scalp_eeg";t.state.input.record_revision=2;const original=JSON.stringify(t.state.input);t.beginInputRevision();assert.equal(t.state.revisionInput.record_revision,2);assert(t.state.filePending);assert(t.get("run-button").disabled);assert(t.get("intake-confirmation").innerHTML.includes("保存为新版本"));assert.equal(t.get("intake-modality").value,"scalp_eeg");t.cancelInputRevision();assert.equal(JSON.stringify(t.state.input),original);assert(!t.state.filePending);assert.equal(t.state.revisionInput,null);
});
check("unavailable records cannot be run even after switching to whole-record scope",()=>{
  const t=harness();t.state.input.availability={status:"unavailable",reason:"source missing"};t.setScope("recording");assert(t.get("run-button").disabled);assert.equal(t.get("action-hint").textContent,"source missing");
});
check("coverage describes execution and keeps gaps and unexecuted duration explicit",()=>{
  const t=harness();t.state.result={coverage:{total_seconds:300,completed_seconds:120,failed_seconds:60,unexecuted_seconds:100,gap_seconds:20}};const text=t.coverageText();for(const expected of ["300","120","60","100","20","不代表质量通过"])assert(text.includes(expected));assert(!text.includes("合格"));
});
check("candidate filtering preserves whole-window localization and distinct review states",()=>{
  const t=harness();t.state.candidates=[{id:"a",module_id:"M05",method:"LOF",channel_indices:[4],channel_names:["<Cz>"],localization:"whole_window",start_seconds:30,stop_seconds:120,status:"pending"},{id:"b",module_id:"M03",method:"flat",localization:"interval",start_seconds:42,stop_seconds:43,status:"pending"}];t.state.review={version:1,decisions:{a:{decision:"rejected"}}};t.get("candidate-filter").value="all";t.get("candidate-module").value="all";t.renderCandidateList();let markup=t.get("candidate-list").innerHTML;assert(markup.includes("仅整窗定位"));assert(!markup.includes("30–120"));assert(markup.includes("&lt;Cz&gt;"));assert(markup.includes("驳回候选"));t.get("candidate-filter").value="pending";t.renderCandidateList();assert(!t.get("candidate-list").innerHTML.includes('data-candidate="a"'));assert(t.get("candidate-list").innerHTML.includes('data-candidate="b"'));
});
check("waveform requests are bounded and stale responses cannot replace a newer view",async()=>{
  const first=deferred(),calls=[];const t=harness(async(url)=>{calls.push(url);return calls.length===1?first.promise:response({start_seconds:10,stop_seconds:15,channels:[]})});t.state.workspace={kind:"input",id:"source",total_seconds:300};t.get("waveform-channels").querySelectorAll=()=>[{checked:true,dataset:{waveformChannel:"0"}}];t.get("waveform-start").value=0;t.get("waveform-duration").value=20;await t.loadWaveform();assert.equal(calls.length,0);t.get("waveform-duration").value=5;const pending=t.loadWaveform();t.get("waveform-start").value=10;await t.loadWaveform();first.resolve(response({start_seconds:0,stop_seconds:5,channels:[]}));await pending;assert.equal(t.state.waveform.start_seconds,10);assert(calls[1].includes("max_points=1600"));assert(calls[1].includes("channel_indices=0"));
});
check("waveform highlights only actual interval localization and escapes source channel names",()=>{
  const t=harness();t.state.waveform={start_seconds:0,stop_seconds:5,channels:[{source_index:82,name:"<channel>",unit:"µV",times_seconds:[0,1,2,3],values:[0,2,-2,0]}]};t.state.candidates=[{id:"candidate",localization:"whole_window",start_seconds:1,stop_seconds:2}];t.state.candidateId="candidate";t.get("waveform-gain").value=1;t.renderWaveform();assert(!t.get("waveform-plot").innerHTML.includes("<rect"));assert(t.get("waveform-plot").innerHTML.includes("#82 &lt;channel&gt;"));t.state.candidates[0].localization="interval";t.renderWaveform();assert(t.get("waveform-plot").innerHTML.includes("<rect"));
});
check("candidate evidence links are restricted to same-job artifacts and valid basenames",()=>{
  const t=harness();t.state.workspace={kind:"job",id:"job"};assert(t.evidenceLinks({evidence:{artifact:"w000001--M03_continuity.json"}}).includes("/api/v1/jobs/job/artifacts/w000001--M03_continuity.json"));assert.equal(t.evidenceLinks({evidence:{artifact:"../secret"}}),"");assert.equal(t.evidenceLinks({evidence:{url:"javascript:alert(1)"}}),"");assert.equal(t.evidenceLinks({evidence:{url:"/api/v1/jobs/other/artifacts/a.json"}}),"");
});
check("review conflicts retain edits and refresh version without automatically overwriting",async()=>{
  const calls=[];const t=harness(async(url,options={})=>{calls.push([url,options]);return options.method?{...response({error:"version conflict"}),ok:false,status:409}:response({version:4,decisions:{a:{decision:"rejected",note:"other"}}})});t.state.workspace={kind:"job",id:"job"};t.state.candidates=[{id:"a",localization:"unknown"}];t.state.candidateId="a";t.state.review={version:3,decisions:{}};t.get("review-decision").value="accepted";t.get("review-reviewer").value="Reviewer";t.get("review-note").value="my note";await t.saveReview();assert.equal(calls.length,2);assert.equal(JSON.parse(calls[0][1].body).expected_version,3);assert.equal(t.state.review.version,4);assert.equal(t.get("review-note").value,"my note");assert(t.get("review-error").textContent.includes("已被更新"));assert.equal(calls.filter(([,o])=>o.method).length,1);
});
check("same-unit waveforms retain amplitude ratios and DC offset, with explicit display clipping",()=>{
  const t=harness();t.state.waveform={start_seconds:0,stop_seconds:1,channels:[{source_index:0,name:"small",unit:"µV",times_seconds:[0,1],values:[0,1]},{source_index:1,name:"large",unit:"µV",times_seconds:[0,1],values:[0,10]},{source_index:2,name:"DC",unit:"µV",times_seconds:[0,1],values:[5,5]}]};t.get("waveform-gain").value=1;t.renderWaveform();const html=t.get("waveform-plot").innerHTML;const y=index=>Number(new RegExp(`data-source-index="${index}" d="[^"]*L[\\d.]+,([\\d.]+)`).exec(html)[1]);assert(Math.abs((123-y(1))/(41-y(0))-10)<0.001);assert.equal(y(2),191);assert.equal((html.match(/±10.0 µV/g)||[]).length,3);assert(!html.includes("waveform-clipped"));t.get("waveform-gain").value=4;t.renderWaveform();assert(t.get("waveform-plot").innerHTML.includes('class="waveform-clipped"'));assert(t.get("waveform-plot").innerHTML.includes("显示裁切"));assert.deepEqual([...t.state.waveform.channels[1].values],[0,10]);
});
check("candidate pre-context clamps to its actual segment and manual gap starts remain errors",async()=>{
  const calls=[];const t=harness(async(url)=>{calls.push(url);return response({start_seconds:10,stop_seconds:15,channels:[]})});t.state.workspace={kind:"job",id:"job",total_seconds:20,channels:[{index:0,name:"EEG",sampling_rate_hz:100}],segments:[{start_sample:1000,stop_sample:1500,recording_start_seconds:10}]};t.state.candidates=[{id:"a",module_id:"M03",localization:"interval",channel_indices:[0],start_seconds:10.2,stop_seconds:10.4}];t.get("waveform-channels").querySelectorAll=()=>[{checked:true,dataset:{waveformChannel:"0"}}];t.get("waveform-duration").value=5;await t.selectCandidate("a");assert(calls[0].includes("start_seconds=10&"));t.get("waveform-start").value=9;await t.loadWaveform();assert.equal(calls.length,1);assert(t.get("review-error").textContent.includes("间隙"));t.get("waveform-start").value=14;await t.loadWaveform();assert(calls[1].includes("duration_seconds=1&"));
});
check("cancelled whole-record progress exposes unfinished windows without treating stale running as complete",()=>{
  const t=harness();t.state.job={id:"cancelled",status:"cancelled",recording_progress:{status:"running",coverage:{total_seconds:300,completed_seconds:120,failed_seconds:0,unexecuted_seconds:60,running_seconds:120,gap_seconds:0,execution_percent:40,fully_assessed_seconds:0},windows:[{id:"w1",start_seconds:0,duration_seconds:120,status:"completed"},{id:"w2",start_seconds:120,duration_seconds:120,status:"running"}]}};t.renderRecordingProgress();const html=t.get("recording-progress").innerHTML;assert(html.includes("任务已停止"));assert(html.includes("未完成"));assert(html.includes('aria-valuenow="40"'));assert(!html.includes(">运行中<"));assert(html.includes("所选检查均完成范围"));
});
check("reference-only revisions omit untouched preprocessing and hidden external annotations",async()=>{
  let posted;const t=harness(async(_url,options)=>{posted=JSON.parse(options.body);return {...response({error:"stop after capture"}),ok:false,status:400}});
  t.state.input.modality="scalp_eeg";t.state.input.record_revision=3;t.state.input.preprocessing={verified:true,highpass_hz:0.1,lowpass_hz:70,note:"Header declaration",source:"file_header_declaration"};
  t.state.input.annotation={format:"sleep_stages_tsv",path:"external-source.tsv",expected_sha256:"preserved"};const before=JSON.stringify(t.state.input);t.beginInputRevision();
  t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"}];t.get("intake-modality").value="scalp_eeg";t.get("intake-reference").value="common_reference";t.get("intake-confirmed").checked=true;t.get("intake-label").value="same record";t.get("revision-verified").checked=true;t.get("revision-highpass").value="0.10";t.get("revision-lowpass").value="70";t.get("revision-processing-note").value="Header declaration";t.get("revision-annotation").value="";
  await t.confirmIntake();assert.equal(posted.base_revision,3);assert.equal(posted.reference_scheme,"common_reference");assert(!Object.hasOwn(posted,"preprocessing"));assert(!Object.hasOwn(posted,"annotation_mapping"));assert.equal(JSON.stringify(t.state.input),before);
});
check("only edited metadata is submitted and clearing an existing mapping is explicit",()=>{
  const t=harness(),mapping={kind:"task",labels:{T1:"left hand"},confirmed:true},input={preprocessing:{verified:true,highpass_hz:0.1,lowpass_hz:70,note:"Header",source:"file_header_declaration"},annotation_mapping:mapping},before=JSON.stringify(input);
  const fields={verified:true,highpass:"0.1",lowpass:"70",note:"Header",annotation:JSON.stringify(mapping,null,2)};
  assert.equal(JSON.stringify(t.revisionMetadataChanges(input,fields)),"{}");
  const cleared=t.revisionMetadataChanges(input,{...fields,annotation:""});assert(Object.hasOwn(cleared,"annotation_mapping"));assert.equal(cleared.annotation_mapping,null);assert(!Object.hasOwn(cleared,"preprocessing"));
  const changed=t.revisionMetadataChanges(input,{...fields,lowpass:"60",note:"Verified acquisition sheet"});assert.equal(changed.preprocessing.lowpass_hz,60);assert(!Object.hasOwn(changed,"annotation_mapping"));
  const absent={};assert.equal(JSON.stringify(t.revisionMetadataChanges(absent,{verified:false,highpass:"",lowpass:"",note:"",annotation:""})),"{}");assert.equal(JSON.stringify(t.revisionMetadataChanges(absent,{verified:false,annotation:"null"})),"{}");
  assert.equal(JSON.stringify(input),before);assert.throws(()=>t.revisionMetadataChanges(input,{...fields,annotation:"{"}),/JSON/);
});
for(const [name,run] of tests){await run();console.log(`PASS ${name}`)}
console.log(`${tests.length} pure JavaScript checks passed. Visual/browser behavior is not tested.`);
