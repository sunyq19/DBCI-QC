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
function harness(fetchImpl = async()=>{throw new Error("Unexpected API request in pure JS test")}, {selected = true, hash = "", search = "", serverInputs = false} = {}) {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id,{_value:"",get value(){return this._value},set value(value){this._value=String(value)},textContent:"",innerHTML:"",hidden:false,disabled:false,open:false,style:{},attrs:{},events:new Map(),firstElementChild:{style:{}},lastElementChild:{textContent:""},addEventListener(type,handler){if(!this.events.has(type))this.events.set(type,[]);this.events.get(type).push(handler)},dispatch(type,event={}){for(const handler of this.events.get(type)||[])handler(event)},removeAttribute(key){delete this.attrs[key]},setAttribute(key,value){this.attrs[key]=value},querySelectorAll(){return[]},scrollIntoView(){},showModal(){this.open=true},close(){if(!this.open)return;this.open=false;this.dispatch("close",{target:this})}});
    return elements.get(id);
  };
  ids.forEach(get);
  const storage = new Map();
  const location = {protocol:"http:",pathname:"/",search,hash}, windowEvents = new Map();
  const history = {state:null,replacements:[],replaceState(state,_title,value){this.state=state;this.replacements.push(value);const url=new URL(value,"http://localhost");Object.assign(location,{pathname:url.pathname,search:url.search,hash:url.hash})}};
  const context = {document:{getElementById:get,addEventListener(){}},window:{history,addEventListener(type,handler){if(!windowEvents.has(type))windowEvents.set(type,[]);windowEvents.get(type).push(handler)},matchMedia:()=>({matches:true}),sessionStorage:{getItem:key=>storage.get(key)||null,setItem:(key,value)=>storage.set(key,value),removeItem:key=>storage.delete(key)}},location,fetch:(url,options)=>url === "/api/v1/inputs" && !serverInputs ? Promise.resolve(response({inputs:context.window.contract.state.catalog.inputs})) : fetchImpl(url,options),AbortController,setTimeout,clearTimeout,URL,console};
  const names = "state,currentConfig,body,fingerprint,validPlan,selectInput,setExtension,setModuleSelected,setContext,renderDataTags,renderInputUsage,renderExtensions,extensionMethods,methodCardsHtml,methodPlanHtml,methodApplicability,visualNodes,executionProgress,renderResult,safeSourceUrl,moduleStandardsUrl,moduleFromHash,openModuleFromHash,moduleDialogClosed,showModule,renderPipeline,updateActions,toolkitMethods,renderToolkit,methodDocumentationHtml,makeRecommendation,applyRecommendation,recommendationValid,renderRecommendation,applyParameters,invalidatePlan,intakeRole,intakeConfirmation,renderIntake,renderExtraction,streamSummaryHtml,needsStreamSelection,selectIntakeStream,annotationText,uploadIntake,pendingIntakeId,confirmIntake,prepareRecommendedPlan,makePlan,startJob,selectJob,loadCatalog,renderExamplePresets,chooseLocalFile,clearInputDraft,renderVisibility,restoreIntake,setScope,saveDraft,savedDraft,restoreDraft,discardDraft,applyConfiguration,jobLocation,setJobLocation,restoreNavigation,cloneJobConfiguration,coverageText,resetReviewWorkspace,renderCandidateList,renderWaveform,loadWaveform,saveReview,beginInputRevision,cancelInputRevision,selectCandidate,evidenceLinks,runSummary,clearPoll,listPendingIntakes,openReviewWorkspace,renderRecordingProgress,revisionMetadataChanges,ensureCatalog,browseMethods,hasExecutionContext,applyIntakeModalitySuggestion,inputModality,jobModality,visibleInputs,moduleOrder,defaultSelectedModules,renderModalityNavigation,renderHistory,renderRegisteredInputs,selectRecord,revealNavigationTarget";
  const instrumented = source.replace("  loadCatalog();\n})();",`  window.contract = {${names}};\n})();`);
  assert.notEqual(instrumented,source,"Harness replaces startup; no API requests execute");
  vm.runInNewContext(instrumented,context);
  const test = context.window.contract;
  test.state.catalog=fixtureCatalog();if(selected)test.selectInput("input-0",{autoPrepare:false});else test.updateActions();
  return {...test,selectInput:(id,options={autoPrepare:false})=>test.selectInput(id,options),get,location,history,storage,setHash(value){location.hash=value;for(const handler of windowEvents.get("hashchange")||[])handler({type:"hashchange"})}};
}
function modalityCatalog(modality = "scalp_eeg") {
  const catalog = fixtureCatalog(), ecog = modality === "ecog";
  catalog.active_modality = modality;
  catalog.overview_url = ecog ? "/standards/ecog" : "/standards";
  catalog.modalities = [{id:"scalp_eeg",label:"头皮 EEG",qc_supported:true},{id:"ecog",label:"ECoG",qc_supported:true,scope_note:"ECoG 基础检查"},{id:"seeg",label:"sEEG",qc_supported:false}];
  catalog.workflow = {groups:[{id:"intake",label:"读取与确认",module_ids:["M01","M02"]},{id:"checks",label:"质量检查",module_ids:["M03","M04","M05","M06","M07"]},{id:"report",label:"结果与报告",module_ids:["M08","M09"]}],default_selected_modules:ecog?["M03","M04","M05"]:["M03","M04","M05","M06","M07"]};
  for (const module of catalog.modules) {
    module.required = ["M01","M02","M08","M09"].includes(module.id);
    module.selectable = !(ecog && module.id === "M06");
    module.documentation_url = `${catalog.overview_url}/modules/${module.id}`;
    module.name = `${ecog ? "ECoG" : "Scalp"} ${module.id}`;
    module.methods = ecog ? module.id === "M06" ? [] : [rawMethod(`ecog_${module.id}`,"basic",{supported_modalities:["ecog"]})] : module.methods.map(method => ({...method,supported_modalities:method.implementation === "planned"?[]:["scalp_eeg"],intended_modalities:["scalp_eeg"]}));
  }
  catalog.inputs.forEach((input,index) => { input.modality = modality;input.id = `${modality}-${index}`;input.label = `${modality} record ${index}`;input.default_config.method_config.extensions=[]; });
  return catalog;
}
function fourCatalog(modality="scalp_eeg") {
  const invasive=modality!=="scalp_eeg",catalog=modalityCatalog(invasive?"ecog":"scalp_eeg");
  const routes={scalp_eeg:"/standards",ecog:"/standards/ecog",seeg:"/standards/seeg",extracellular:"/standards/neuropixels"};
  const labels={scalp_eeg:"头皮 EEG",ecog:"ECoG",seeg:"sEEG",extracellular:"Neuropixels AP/LF"};
  catalog.active_modality=modality;catalog.overview_url=routes[modality];
  catalog.modalities=Object.entries(labels).map(([id,label])=>({id,label,qc_supported:true}));
  catalog.modules.forEach(module=>{module.documentation_url=`${routes[modality]}/modules/${module.id}`;module.name=`${labels[modality]} ${module.id}`;if(invasive)module.methods=module.methods.map(method=>({...method,id:`${modality}_${module.id}`,supported_modalities:[modality]}));});
  catalog.inputs.forEach((input,index)=>{input.id=`${modality}-${index}`;input.modality=modality;input.label=`${modality} record ${index}`;input.profile_id=({scalp_eeg:"scalp-eeg/1",ecog:"ecog-basic/1",seeg:"seeg-basic/1",extracellular:"neuropixels-raw/1"})[modality];
    if(modality==="extracellular")input.metadata={...input.metadata,format:"SpikeGLX",acquisition:{stream_band:index?"lf":"ap",probe_type:"NP1.0"},channels:[{index:0,name:"AP0",sampling_rate_hz:index?2500:30000,unit:"uV",channel_type:"neuropixels",channel_type_source:"file_declared"}]};
  });return catalog;
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
check("method activation labels preserve dependent execution and only supported switches",()=>{
  const t=harness();const three=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M03")),six=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M06"));
  assert(three.includes("随模块运行"));assert(six.includes("满足条件"));assert(six.includes("手动扩展"));assert(six.includes("尚未接入"));
  assert.equal((three.match(/type="checkbox"/g)||[]).length,1);assert.equal((six.match(/type="checkbox"/g)||[]).length,1);assert(six.includes("手动扩展需明确启用"));
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
check("Toolkit filters purpose and availability without changing configuration or legacy choices",()=>{
  const t=harness(),before=t.fingerprint();assert.equal(t.toolkitMethods("artifacts","available").length,2);assert.equal(t.toolkitMethods("artifacts","planned")[0].id,"future_check");
  t.get("toolkit-category").value="artifacts";t.get("toolkit-implementation").value="available";t.renderToolkit();const markup=t.get("toolkit-methods").innerHTML;
  assert(markup.includes("conditional_check"));assert(!markup.includes("mne_amplitude"));assert(markup.includes("按条件启用"));assert(markup.includes("可选增强"));assert(!markup.includes(">条件<"));assert.equal(t.fingerprint(),before);
});
check("Toolkit groups methods under modules and three stages; planned methods require explicit browsing",()=>{
  const t=harness();for(const module of t.state.catalog.modules)if(!module.methods.length)module.methods.push(rawMethod(`method_${module.id}`,"basic"));
  t.get("toolkit-category").value="all";t.get("toolkit-implementation").value="all";t.renderToolkit();const markup=t.get("toolkit-methods").innerHTML;
  const stages=[...markup.matchAll(/data-toolkit-stage="([^"]+)"/g)].map(match=>match[1]);assert.deepEqual(stages,["intake","checks","report"]);
  const modules=[...markup.matchAll(/data-toolkit-module="([^"]+)"/g)].map(match=>match[1]);assert.deepEqual(modules,["M01","M02","M03","M04","M05","M06","M07","M08","M09"]);
  assert.equal((markup.match(/class="toolkit-card"/g)||[]).length,t.toolkitMethods("all","all").length);
  assert(markup.includes("future_check"));assert(!markup.includes("测试用方法说明"),"Long method descriptions stay in details");
  assert(!/>通用<|>条件<|>可选</.test(markup));assert(!markup.includes('type="checkbox"'),"Browsing purposes does not become an execution selector");
});
check("Default toolbox shows integrated methods and exact method details without changing a plan",()=>{
  const t=harness(), before=t.fingerprint();t.renderToolkit();const markup=t.get("toolkit-methods").innerHTML;
  assert(!markup.includes("future_check"));assert(markup.includes('data-method-id="mne_amplitude"'));
  assert(!/class="toolkit-module"[^>]* open/.test(markup));
  t.showModule("M03",{catalog:t.state.catalog,modality:"scalp_eeg",browsing:true,methodId:"mne_amplitude"});
  const detail=t.get("module-dialog-content").innerHTML;
  assert(detail.includes("mne_amplitude"));assert(!detail.includes("方法 basic_check"));assert(detail.includes('class="method-more" open'));
  assert(detail.includes("https://example.test/method"));assert(detail.includes('data-method-parent="M03"'));assert(!detail.includes('type="checkbox"'));
  assert.equal(t.fingerprint(),before);assert.equal(t.get("module-dialog-title").textContent,"方法 mne_amplitude");
});
check("The three-stage framework remains stable before and after reading a file",()=>{
  const t=harness(undefined,{selected:false});t.renderPipeline();const before=t.get("pipeline").innerHTML;
  assert.equal((before.match(/class="flow-stage"/g)||[]).length,3);
  t.selectInput("input-0");t.renderPipeline();assert.equal((t.get("pipeline").innerHTML.match(/class="flow-stage"/g)||[]).length,3);
});
check("Catalog domain and activation metadata remain separate from supported modality",()=>{
  const t=harness(),module=t.state.catalog.modules.find(m=>m.id==="M03"),method=module.methods[0];
  Object.assign(method,{domain:"signal_integrity",domain_label:"信号完整性",activation:"with_module",activation_label:"随模块运行",supported_modalities:["scalp_eeg"],scope_note:"仅头皮 EEG；<script>不能扩大范围</script>"});
  const detail=t.methodCardsHtml(module);assert(detail.includes("随模块运行"));assert(detail.includes("适用模态"));assert(detail.includes("头皮 EEG"));assert(detail.includes("&lt;script&gt;"));assert(!detail.includes("<script>"));
  assert(/<details class="method-more"><summary>原理、条件与来源<\/summary>/.test(detail));
  assert(!/class="method-more" open/.test(detail));assert(!detail.includes(">通用<"));
  const other=t.state.catalog.modules.find(m=>m.id==="M06");assert(t.methodCardsHtml(other).includes("目录未声明适用模态。"),"Legacy catalog does not acquire modality claims");
  method.domain="reporting";method.domain_label="结果与报告";assert(t.toolkitMethods("reporting","available").some(row=>row.id===method.id),"Explicit server domain takes precedence over compatibility fallback");
});
check("Declared domain ordering and new method domains populate filters without an execution-side effect",()=>{
  const t=harness(),before=t.fingerprint();t.state.catalog.method_domains=[{id:"artifacts",label:"伪迹线索"},{id:"signal_integrity",label:"信号完整性"}];
  t.state.catalog.modules.find(m=>m.id==="M07").methods.push(rawMethod("future_domain","optional",{implementation:"planned",domain:"new_domain",domain_label:"未来功能域"}));
  t.get("toolkit-category").value="new_domain";t.get("toolkit-implementation").value="all";t.renderToolkit();const choices=t.get("toolkit-category").innerHTML;
  assert(choices.indexOf('value="artifacts"')<choices.indexOf('value="signal_integrity"'));assert(choices.includes('value="new_domain"'));assert.equal(t.get("toolkit-category").value,"new_domain");
  assert(t.get("toolkit-methods").innerHTML.includes("future_domain"));assert.equal(t.fingerprint(),before);
  t.get("toolkit-category").value="removed_domain";t.renderToolkit();assert.equal(t.get("toolkit-category").value,"all");
});
check("Planned method modality is an intended target, never advertised as supported",()=>{
  const t=harness(),module=t.state.catalog.modules.find(m=>m.id==="M06"),future=module.methods.find(m=>m.id==="future_check");
  Object.assign(future,{supported_modalities:[],intended_modalities:["scalp_eeg"],scope_note:"计划面向头皮 EEG；尚未接入。"});
  let cards=t.methodCardsHtml({id:"M06",methods:[future]});assert(cards.includes("计划适用模态"));assert(cards.includes("头皮 EEG"));assert(!cards.includes("<h5>适用模态</h5>"));assert(!cards.includes('type="checkbox"'));
  delete future.intended_modalities;future.supported_modalities=["ecog"];cards=t.methodCardsHtml({id:"M06",methods:[future]});assert(cards.includes("目录未声明计划适用模态。"));assert(!cards.includes("ECoG"));
});
check("Purpose browsing in history does not alter frozen plan or unlock extension switches",()=>{
  const t=harness();t.state.mode="job";t.state.job={id:"frozen",plan:{qc_config:{method_config:{extensions:["mne_amplitude"]}}}};const before=JSON.stringify(t.state.job);
  t.get("toolkit-category").value="signal_integrity";t.renderToolkit();const cards=t.methodCardsHtml(t.state.catalog.modules.find(m=>m.id==="M03"));
  assert(/data-extension="mne_amplitude" checked disabled/.test(cards));assert.equal(JSON.stringify(t.state.job),before);assert(t.get("toolkit-methods").innerHTML.includes("mne_amplitude"));
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
  assert(overview.includes("必须确认模态"));assert(overview.includes("1 个分析通道"));assert(markup.includes("检查模块"));assert(markup.includes("默认增强"));assert(!overview.includes("检查模块"));assert(!overview.includes("默认增强"));assert(!overview.includes("先核对波形"));assert(markup.includes("<li>先核对波形</li><li>再复核候选</li>"));assert(!overview.includes("&quot;先核对波形&quot;"));assert.equal(t.fingerprint(),before);
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
  const dynamic=["effective-config","retry-catalog-button","intake-modality","intake-reference","intake-confirmed","intake-label","intake-source-note","intake-confirm-button","intake-modality-note","intake-channel-summary","revision-annotation","revision-verified","revision-highpass","revision-lowpass","revision-processing-note","window-page","window-state-details"];
  for(const match of source.matchAll(/\$\("([^"]+)"\)/g))assert(ids.includes(match[1])||dynamic.includes(match[1]),`Missing element ${match[1]}`);
  for(const field of fields)assert(ids.includes(`context-${field}`));
});
check("module links and fragments accept only exact M01 to M09 IDs",()=>{
  const t=harness(undefined,{selected:false});
  for(let n=1;n<=9;n++){const id=`M0${n}`;assert.equal(t.moduleStandardsUrl(id),`/standards/modules/${id}`);assert.equal(t.moduleFromHash(`#module-${id}`),id)}
  for(const id of ["M00","M10","m01","M01/../../jobs","M01?run=1","M01\" onclick=\"bad","",null])assert.equal(t.moduleStandardsUrl(id),null);
  assert.equal(t.moduleStandardsUrl("M03",{modules:[{id:"M03",documentation_url:"undefined/modules/M03"}]},"unknown"),null);
  for(const hash of ["#module-M00","#module-M10","#module-m01","#module-%4D01","#module-M01/","#module-M01?run=1","#module-M01\n","#module-M01-extra","#other","",null])assert.equal(t.moduleFromHash(hash),null);
});
check("all nine module deep links open after an empty catalog without selecting or running",async()=>{
  for(let n=1;n<=9;n++){
    const id=`M0${n}`,calls=[],catalog=fixtureCatalog();catalog.inputs=[];
    const t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/catalog"))return response(catalog);if(url.endsWith("/jobs")&&!options.method)return response({jobs:[]});throw new Error(`Unexpected ${url}`)},{selected:false,hash:`#module-${id}`});
    t.state.catalog=null;assert(await t.loadCatalog());assert(t.get("module-dialog").open);assert.equal(t.state.dialogModule,id);assert.equal(t.get("module-details-link").attrs.href,"/standards/overview");assert.equal(t.state.input,null);assert.equal(t.state.recommendation,null);assert.equal(t.state.plan,null);assert.equal(t.state.job,null);assert(t.get("analysis-workspace").hidden);assert(t.get("run-button").disabled);assert.deepEqual(calls.map(([url])=>url),["/api/v1/catalog","/api/v1/jobs"]);
  }
});
check("hash changes only read module information and preserve the current draft",()=>{
  const t=harness();t.setExtension("mne_amplitude",true);t.setContext("task","attention");t.state.plan={plan_id:"kept",nodes:[]};t.state.planKey=t.fingerprint();
  const before=t.fingerprint(),plan=t.state.plan,epoch=t.state.draftEpoch;
  t.setHash("#module-M03");assert.equal(t.state.dialogModule,"M03");t.setHash("#module-M09");assert.equal(t.state.dialogModule,"M09");assert.equal(t.fingerprint(),before);assert.equal(t.state.plan,plan);assert.equal(t.state.draftEpoch,epoch);assert.equal(t.state.job,null);assert.equal(t.state.recommendation,null);assert.equal(t.get("module-details-link").attrs.href,"/standards/modules/M09");
});
check("hash received before catalog readiness is applied only to the latest fragment",async()=>{
  const wait=deferred(),calls=[];const t=harness(async(url)=>{calls.push(url);return url.endsWith("/catalog")?wait.promise:response({jobs:[]})},{selected:false,hash:"#module-M01"});
  t.state.catalog=null;const pending=t.loadCatalog();t.setHash("#module-M06");assert(t.get("module-dialog").open);assert.equal(t.get("module-details-link").attrs.href,"/standards/overview");wait.resolve(response(fixtureCatalog()));await pending;assert.equal(t.state.dialogModule,"M06");assert.equal(t.state.input,null);assert.deepEqual(calls,["/api/v1/catalog","/api/v1/jobs"]);
});
check("invalid deep links and forged catalog IDs cannot open or produce links",async()=>{
  const catalog=fixtureCatalog();catalog.modules.push({id:"M01/../../jobs",name:"invalid"});
  const t=harness(async(url)=>response(url.endsWith("/catalog")?catalog:{jobs:[]}),{selected:false,hash:"#module-M99"});await t.loadCatalog();assert(!t.get("module-dialog").open);assert.equal(t.state.input,null);
  t.showModule("M01/../../jobs");assert(!t.get("module-dialog").open);assert.equal(t.get("module-details-link").attrs.href,undefined);
  t.setHash("#module-M02");t.setHash("#module-M02?run=1");assert.equal(t.state.dialogModule,"M02");assert.equal(t.get("module-details-link").attrs.href,"/standards/overview");
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
  t.state.catalog=null;t.renderPipeline();assert.equal((t.get("pipeline").innerHTML.match(/data-detail=/g)||[]).length,9);assert(t.visualNodes().every(node=>node.status==="framework"));assert(t.get("run-button").disabled);
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
check("modalities absent from the catalog remain extraction-only after manual edits and create no plan or job",async()=>{
  for(const modality of ["seeg","ecog","extracellular","other","unknown"]){
    const calls=[],t=harness(async(url,options={})=>{calls.push([url,options]);return response({recommendation_id:"unsupported",status:"unsupported",can_apply:false,reason:"No QC route for this modality"})});
    t.state.input.modality=modality;t.state.recommendation={status:"unsupported",can_apply:false};t.updateActions();
    t.setContext("disease","other");assert.equal(t.state.recommendation,null);assert(t.state.manualDraft);
    t.get("start-seconds").value="10";t.invalidatePlan();t.setExtension("mne_amplitude",true);
    assert(t.get("run-button").disabled);assert(t.get("plan-button").disabled);assert(!t.get("recommend-button").disabled);
    assert.equal(t.get("pipeline-state").textContent,"仅信息提取");assert(t.get("action-hint").textContent.includes("不运行其他模态"));
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
check("candidate truncation evidence survives waveform refreshes and is separate from transient errors",async()=>{
  const warning={code:"candidate_details_truncated",artifact:"M03_continuity.json",reason:"候选详情已截断；当前仅复核已保存的位置，完整计数见模块证据。",observed_interval_count:150,stored_interval_count:50,omitted_interval_count:100},calls=[];
  const t=harness(async url=>{calls.push(url);if(url.endsWith("/candidates"))return response({candidates:[],warnings:[warning]});if(url.endsWith("/review"))return response({version:0,decisions:{},warnings:[{...warning}]});return response({start_seconds:0,stop_seconds:5,channels:[]})});
  t.state.job={id:"bounded",status:"completed",plan:{input_metadata:t.state.input.metadata,qc_config:t.currentConfig()}};t.get("waveform-channels").querySelectorAll=()=>[{checked:true,dataset:{waveformChannel:"0"}}];await t.openReviewWorkspace("job");
  const markup=t.get("review-evidence-notice").innerHTML;assert(!t.get("review-evidence-notice").hidden);assert(markup.includes("仅复核已保存的位置"));assert(markup.includes("M03_continuity.json"));assert.equal(t.state.reviewWarnings.length,1);for(const text of ["观察区间数","已存区间数","未存区间数","150","50","100"])assert(markup.includes(text));assert(t.get("review-error").hidden);assert(!/<details[^>]* open/.test(markup));
  t.get("review-error").textContent="transient waveform error";t.get("review-error").hidden=false;await t.loadWaveform();assert(t.get("review-error").hidden);assert.equal(t.get("review-evidence-notice").innerHTML,markup);assert(!t.get("review-evidence-notice").hidden);assert.equal(calls.filter(url=>url.includes("/waveform?")).length,2);
  await t.selectJob("next",{id:"next",status:"failed",plan:{},modules:[]});assert(t.get("review-evidence-notice").hidden);assert.equal(t.get("review-evidence-notice").innerHTML,"");assert.equal(t.state.reviewWarnings.length,0);assert.equal(t.state.workspace,null);
});
check("late candidate evidence cannot leak into a newly selected input",async()=>{
  const wait=deferred(),t=harness(async url=>url.endsWith("/candidates")?wait.promise:response({version:0,decisions:{}}));t.state.job={id:"old",status:"completed",plan:{input_metadata:t.state.input.metadata,qc_config:t.currentConfig()}};
  const pending=t.openReviewWorkspace("job");await t.selectInput("input-1");wait.resolve(response({candidates:[],warnings:[{code:"candidate_details_truncated",artifact:"old.json",reason:"old details"}]}));await pending;
  assert(t.get("review-evidence-notice").hidden);assert.equal(t.state.reviewWarnings.length,0);assert.equal(t.state.workspace,null);assert.equal(t.state.input.id,"input-1");
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
check("legacy ECoG URL remains read-only while the landing graph and standards link stay neutral",async()=>{
  const catalog=modalityCatalog("ecog"),calls=[],t=harness(async url=>{calls.push(url);return response(url.includes("catalog")?catalog:{jobs:[]})},{selected:false,search:"?lang=en&modality=ecog",hash:"#module-M03"});t.state.catalog=null;assert(await t.loadCatalog());
  assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert(!t.hasExecutionContext());assert.equal(t.get("standards-link").attrs.href,"/standards/overview");assert.equal(t.get("module-details-link").attrs.href,"/standards/ecog/modules/M03");assert(t.get("pipeline").innerHTML.includes("字段与方案"));assert(!t.get("pipeline").innerHTML.includes("尚未接入"));assert(t.visualNodes().every(node=>node.status==="framework"));assert(!html.includes('id="modality-tabs"'));assert(t.get("run-button").disabled);assert(!calls.some(url=>/recommend|\/plan/.test(url)));
});
check("all registered records and histories are visible without a modality navigation choice",async()=>{
  const scalp=modalityCatalog(),ecog=modalityCatalog("ecog"),records=[...scalp.inputs,...ecog.inputs],jobs=[{id:"s",label:"Scalp saved",input_modality:"scalp_eeg",status:"completed"},{id:"e",label:"ECoG saved",input_modality:"ecog",status:"completed"}],calls=[];
  const t=harness(async url=>{calls.push(url);return response(url==="/api/v1/inputs"?{inputs:records}:url==="/api/v1/jobs"?{jobs}:scalp)},{selected:false,serverInputs:true});t.state.catalog=null;assert(await t.loadCatalog());
  assert.equal(t.visibleInputs().length,4);for(const record of records)assert(t.get("input-select").innerHTML.includes(record.id));assert(t.get("history-list").innerHTML.includes("Scalp saved"));assert(t.get("history-list").innerHTML.includes("ECoG saved"));assert.equal(t.state.input,null);assert(calls.includes("/api/v1/inputs"));
});
check("record selection automatically activates its confirmed catalog and excludes incompatible scalp methods",async()=>{
  const ecog=modalityCatalog("ecog"),scalp=modalityCatalog(),t=harness(async url=>response(ecog),{selected:false});t.state.catalog=scalp;t.state.records=[...scalp.inputs,...ecog.inputs];await t.selectInput("scalp_eeg-0");t.setExtension("mne_muscle",true);await t.selectInput("ecog-0");
  assert.equal(t.state.activeModality,"ecog");assert.equal(t.state.input.id,"ecog-0");assert.deepEqual([...t.state.selected],["M03","M04","M05"]);assert.equal(t.state.extensions.size,0);assert.equal(t.extensionMethods().length,0);assert(!t.body().selected_modules.includes("M06"));assert(!t.body().selected_modules.includes("M07"));assert(t.get("channel-count").textContent.includes("ECoG"));assert.equal(t.get("standards-link").attrs.href,"/standards/ecog");assert.equal(t.state.plan,null);assert(!t.state.loadingRecord);
});
check("late catalog activation cannot replace a newer record or freshly selected file",async()=>{
  for(const next of ["record","file"]){const wait=deferred(),t=harness(()=>wait.promise,{selected:false});t.state.catalog=modalityCatalog();t.state.records=[...t.state.catalog.inputs,...modalityCatalog("ecog").inputs];const pending=t.selectInput("ecog-0");
    if(next==="record")await t.selectInput("scalp_eeg-1");else{t.get("intake-file").files=[{name:"new.fif",size:100}];t.chooseLocalFile();}
    wait.resolve(response(modalityCatalog("ecog")));await pending;assert.equal(t.state.activeModality,"scalp_eeg");assert.equal(t.state.input?.id,next==="record"?"scalp_eeg-1":undefined);assert.equal(t.state.plan,null);assert(!t.state.loadingRecord);if(next==="file")assert(t.state.filePending);
  }
});
check("all-modality latest draft is discoverable and restores through automatic catalog activation",async()=>{
  const t=harness(async()=>response(modalityCatalog("ecog")),{selected:false});t.state.catalog=modalityCatalog();t.state.records=[...t.state.catalog.inputs,...modalityCatalog("ecog").inputs];await t.selectInput("ecog-0");t.get("start-seconds").value=17;t.saveDraft();t.clearInputDraft();t.state.activeModality="scalp_eeg";t.state.catalog=modalityCatalog();
  assert.equal(t.savedDraft().modality,"ecog");await t.restoreDraft();assert.equal(t.state.input.id,"ecog-0");assert.equal(t.state.activeModality,"ecog");assert.equal(t.get("start-seconds").value,"17");assert.equal(t.state.plan,null);assert(t.state.manualDraft);
});
check("cloning rejects frozen modality mismatches before changing the record",()=>{
  const t=harness(undefined,{selected:false});t.state.activeModality="ecog";t.state.catalog=modalityCatalog("ecog");t.selectInput("ecog-0");const before=t.fingerprint();assert.throws(()=>t.applyConfiguration({input_id:"ecog-0",input_modality:{value:"scalp_eeg"},selected_modules:["M03"],qc_config:t.currentConfig()}),/原记录或配置不可用/);assert.equal(t.fingerprint(),before);
});
check("catalog failure blocks record execution without borrowing another modality",async()=>{
  const t=harness(async()=>response(fixtureCatalog()),{selected:false});t.state.catalog=modalityCatalog();t.state.records=[...t.state.catalog.inputs,...modalityCatalog("ecog").inputs];assert.equal(await t.selectInput("ecog-0"),false);assert.equal(t.state.input,null);assert(t.get("catalog-error").textContent.includes("未套用其他模态"));assert(t.get("run-button").disabled);assert(t.visualNodes().every(node=>node.status==="framework"));
});
check("job deep link uses its frozen modality and keeps all histories accessible",async()=>{
  const job={id:"ecog-job",input_modality:"ecog",label:"ECoG saved",status:"failed",plan:{selected_modules:["M01","M02","M03","M08","M09"],nodes:[],qc_config:{selection:{eeg_indices:[0]},method_config:{extensions:[]}}},modules:[{id:"M03",status:"partial"}]},before=JSON.stringify(job);
  const t=harness(async url=>response(url.includes("catalog")?modalityCatalog("ecog"):job),{selected:false,search:"?lang=en&modality=scalp_eeg&job=ecog-job",hash:"#module-M03"});t.state.catalog=modalityCatalog();t.state.history=[job,{id:"scalp-old",label:"Scalp saved",input_modality:"scalp_eeg",status:"completed"}];await t.selectJob("ecog-job");assert.equal(t.state.activeModality,"ecog");assert.equal(JSON.stringify(job),before);assert(t.location.search.includes("job=ecog-job"));assert(t.location.search.includes("lang=en"));assert.equal(t.location.hash,"#module-M03");assert.equal(t.get("module-details-link").attrs.href,"/standards/ecog/modules/M03");assert(t.get("history-list").innerHTML.includes("Scalp saved"));assert(t.get("history-list").innerHTML.includes("ECoG saved"));assert(t.get("run-button").disabled);
});
check("toolbox modality browsing does not change active input configuration or its plan",async()=>{
  const t=harness(async()=>response(modalityCatalog("ecog")),{selected:false});t.state.catalog=modalityCatalog();t.state.modalityChoices=t.state.catalog.modalities;await t.selectInput("scalp_eeg-0");t.setExtension("mne_muscle",true);t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();const before=t.fingerprint(),plan=t.state.plan;
  assert(await t.browseMethods("ecog"));assert.equal(t.state.activeModality,"scalp_eeg");assert.equal(t.fingerprint(),before);assert.equal(t.state.plan,plan);assert(t.get("toolkit-methods").innerHTML.includes("ecog_M03"));assert(!t.get("toolkit-methods").innerHTML.includes("mne_muscle"));t.showModule("M03",{catalog:t.state.browseCatalog,modality:"ecog",browsing:true});assert.equal(t.get("module-details-link").attrs.href,"/standards/ecog/modules/M03");assert(!t.get("module-dialog-content").innerHTML.includes('type="checkbox"'));assert.equal(t.fingerprint(),before);await t.browseMethods("current");assert(t.toolkitMethods("all","all").some(method=>method.id==="mne_muscle"));
});
check("file-declared modality is a suggestion requiring explicit confirmation and mixed groups are deliberate",()=>{
  const t=harness(undefined,{selected:false});t.state.catalog=modalityCatalog();t.state.intake={id:"declared",metadata:{channels:[{index:0,name:"ECOG1",sampling_rate_hz:100},{index:1,name:"EEG1",sampling_rate_hz:100},{index:2,name:"MISC",sampling_rate_hz:100}]},suggestions:{modality:"ecog",eeg_indices:[0],reference_indices:{},modality_evidence:{status:"file_declared",reason:"ECoG declared by source",source:"FIF"}}};t.renderIntake();assert(t.get("intake-confirmation").innerHTML.includes('value="ecog" selected'));assert(!t.get("intake-confirmed").checked);assert.equal(t.state.input,null);
  t.state.intake.suggestions={modality:"unknown",eeg_indices:[],reference_indices:{},modality_evidence:{status:"mixed",reason:"Multiple declared types",channel_groups:[{modality:"ecog",indices:[0]},{modality:"scalp_eeg",indices:[1]}]}};t.renderIntake();assert(t.get("intake-confirmation").innerHTML.includes('value="unknown" selected'));const roles=[0,1,2].map(index=>({dataset:{intakeChannel:String(index)},value:"unused"}));t.get("intake-confirmation").querySelectorAll=()=>roles;t.get("intake-confirmed").checked=true;t.applyIntakeModalitySuggestion("ecog");assert.deepEqual(roles.map(role=>role.value),["eeg","unused","unused"]);assert(!t.get("intake-confirmed").checked);t.applyIntakeModalitySuggestion("scalp_eeg");assert.deepEqual(roles.map(role=>role.value),["unused","eeg","unused"]);t.applyIntakeModalitySuggestion("unknown");assert(roles.every(role=>role.value==="unused"));assert.equal(t.state.input,null);assert.equal(t.state.plan,null);
});
check("confirmation preserves intake metadata while automatically preparing the appropriate catalog",async()=>{
  const record=modalityCatalog("ecog").inputs[0],calls=[];let t;t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/confirm"))return response({status:"registered",input:record});if(url.includes("catalog"))return response(modalityCatalog("ecog"));if(url.endsWith("/recommend"))return response(recommendationFixture(t,{qc_config:t.currentConfig(),selected_modules:["M01","M02","M03","M04","M05","M08","M09"],recommended_methods:[]}));if(url.endsWith("/plan"))return response(planFixture(JSON.parse(options.body)));throw Error(url)},{selected:false});t.state.catalog=modalityCatalog();t.state.intake={id:"new-ecog",filename:"record.fif",status:"needs_confirmation",metadata:record.metadata};t.state.filePending=true;t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"}];t.get("intake-modality").value="ecog";t.get("intake-reference").value="unknown";t.get("intake-confirmed").checked=true;await t.confirmIntake();assert.equal(t.state.intake.id,"new-ecog");assert.equal(t.state.intake.status,"registered");assert.equal(t.state.input.id,record.id);assert(t.validPlan());assert(!t.get("run-button").disabled);assert(!calls.some(([url])=>url==="/api/v1/jobs"));
});
check("inspection-only intake can be confirmed and restored without requesting an unsupported QC catalog",async()=>{
  const record=modalityCatalog().inputs[0];record.id="seeg-record";record.modality="seeg";const calls=[],t=harness(async(url,options={})=>{calls.push([url,options]);if(url.endsWith("/confirm"))return response({status:"registered",input:record});if(url==="/api/v1/intakes/seeg-intake")return response({id:"seeg-intake",status:"registered",input_id:record.id,input_modality:"seeg"});if(url==="/api/v1/inputs/seeg-record")return response(record);throw Error(url)},{selected:false});t.state.catalog=modalityCatalog();
  t.state.intake={id:"seeg-intake",metadata:record.metadata};t.get("intake-confirmation").querySelectorAll=()=>[{dataset:{intakeChannel:"0"},value:"eeg"}];t.get("intake-modality").value="seeg";t.get("intake-reference").value="unknown";t.get("intake-confirmed").checked=true;await t.confirmIntake();assert.equal(t.state.input.modality,"seeg");assert(t.get("run-button").disabled);assert.equal(t.get("pipeline-state").textContent,"仅信息提取");assert.equal(t.state.plan,null);assert(t.get("intake-status").textContent.includes("信息已保存"));
  await t.restoreIntake("seeg-intake");assert.equal(t.state.input.id,"seeg-record");assert(t.get("run-button").disabled);assert(!calls.some(([url])=>/catalog|recommend|\/plan|\/jobs/.test(url)));
});
check("stale cross-catalog configuration restore cannot overwrite a newer selection of the same record",async()=>{
  const old=deferred(),fresh=deferred();let calls=0;
  const t=harness(()=>++calls===1?old.promise:fresh.promise,{selected:false});t.state.catalog=modalityCatalog();const ecog=modalityCatalog("ecog");t.state.records=[...t.state.catalog.inputs,...ecog.inputs];
  const config={input_id:"ecog-0",modality:"ecog",selected_modules:["M01","M02","M03","M08","M09"],qc_config:structuredClone(ecog.inputs[0].default_config)};config.qc_config.selection.start_seconds=99;
  const restoring=t.applyConfiguration(config);await t.selectInput("scalp_eeg-1");const selecting=t.selectInput("ecog-0");fresh.resolve(response(ecog));await selecting;t.get("start-seconds").value=42;t.invalidatePlan();
  old.resolve(response(ecog));assert.equal(await restoring,false);assert.equal(t.state.input.id,"ecog-0");assert.equal(t.get("start-seconds").value,"42");assert.equal(t.state.plan,null);
});
check("pending extraction identifies only file-declared modality suggestions and never implies confirmation",()=>{
  const t=harness(undefined,{selected:false}),meta={format:"FIF",duration_seconds:10,channels:[{index:0,name:"ECOG1",sampling_rate_hz:100}],modality_evidence:{source:"source.channel_types",requires_confirmation:true}};
  t.state.intake={id:"pending",status:"needs_confirmation",metadata:meta,suggestions:{modality:"ecog",modality_evidence:{status:"file_declared",source:"source.channel_types"}}};t.renderExtraction();let markup=t.get("record-summary").innerHTML;
  assert(markup.includes("建议模态"));assert(markup.includes("ECoG（待确认）"));assert(markup.includes("source.channel_types"));assert(markup.includes("分析模态需确认"));assert.equal(t.state.input,null);assert.equal(t.state.plan,null);
  t.state.intake.suggestions.modality_evidence.status="unknown";t.renderExtraction();markup=t.get("record-summary").innerHTML;assert(!markup.includes("建议模态"));assert(markup.includes("<dd>待确认</dd>"));
  t.state.intake.suggestions.modality_evidence.status="mixed";t.renderExtraction();assert(!t.get("record-summary").innerHTML.includes("建议模态"));
  t.state.input={id:"confirmed",modality:"scalp_eeg",metadata:meta};t.renderExtraction();markup=t.get("record-summary").innerHTML;assert(markup.includes("分析模态"));assert(markup.includes("<dd>头皮 EEG</dd>"));assert(!markup.includes("ECoG（待确认）"));
  t.state.mode="job";t.state.job={id:"frozen",plan:{input_modality:{value:"ecog"},input_metadata:meta}};t.renderExtraction();markup=t.get("record-summary").innerHTML;assert(markup.includes("<dd>ECoG</dd>"));assert(!markup.includes("建议模态"));
});
check("an explicit file choice wins over startup navigation recovery while history is loading",async()=>{
  const wait=deferred(),calls=[];const t=harness(async url=>{calls.push(url);if(url.includes("catalog"))return response(modalityCatalog());if(url.endsWith("/jobs"))return wait.promise;throw Error(url)},{selected:false,search:"?job=old-job"});t.state.catalog=null;
  const loading=t.loadCatalog();for(let n=0;n<12;n++)await Promise.resolve();t.get("intake-file").files=[{name:"chosen.fif",size:100}];t.chooseLocalFile();wait.resolve(response({jobs:[]}));await loading;
  assert(t.state.filePending);assert.equal(t.state.input,null);assert.equal(t.state.job,null);assert(!calls.includes("/api/v1/jobs/old-job"));assert.equal(t.state.navigationRestored,true);
});
check("four confirmed modalities use their own catalogs, contact labels and safe documentation routes",async()=>{
  const ids=["scalp_eeg","ecog","seeg","extracellular"],catalogs=Object.fromEntries(ids.map(id=>[id,fourCatalog(id)]));
  const t=harness(async url=>response(catalogs[new URL(url,"http://localhost").searchParams.get("modality")||"scalp_eeg"]),{selected:false});t.state.catalog=catalogs.scalp_eeg;t.state.records=ids.flatMap(id=>catalogs[id].inputs);
  for(const id of ids){await t.selectInput(`${id}-0`);t.renderToolkit();assert.equal(t.state.activeModality,id);assert.equal(t.state.input.id,`${id}-0`);assert.equal(t.get("standards-link").attrs.href,catalogs[id].overview_url);assert.equal(t.moduleStandardsUrl("M03"),catalogs[id].overview_url+"/modules/M03");
    if(id!=="scalp_eeg"){assert.deepEqual([...t.state.selected],["M03","M04","M05"]);assert.equal(t.state.extensions.size,0);assert(!t.body().selected_modules.includes("M06"));assert(!t.body().selected_modules.includes("M07"));assert(t.toolkitMethods("all","all").every(method=>method.supported_modalities.includes(id)));}
    assert.equal(t.get("toolkit-modality").textContent,`方法范围：${catalogs[id].modalities.find(row=>row.id===id).label}`);assert(!t.get("recommendation-content").innerHTML.includes("道 EEG"));
  }
  assert(t.get("record-summary").innerHTML.includes("信号频带"));assert(t.get("record-summary").innerHTML.includes("<dd>AP</dd>"));assert(t.get("record-summary").innerHTML.includes("NP1.0"));assert(t.get("channel-count").textContent.includes("分析通道"));
  const module=t.state.catalog.modules.find(row=>row.id==="M03");module.documentation_url="/standards/seeg/modules/M03";assert.equal(t.moduleStandardsUrl("M03"),null);module.documentation_url="/standards/neuropixels/modules/M03?run=1";assert.equal(t.moduleStandardsUrl("M03"),null);
});
check("legacy sEEG and extracellular URLs only browse the matching catalog on the neutral landing",async()=>{
  for(const id of ["seeg","extracellular"]){const catalog=fourCatalog(id),calls=[];const t=harness(async url=>{calls.push(url);return response(url.includes("catalog")?catalog:{jobs:[]})},{selected:false,search:`?lang=en&modality=${id}`,hash:"#module-M04"});t.state.catalog=null;assert(await t.loadCatalog());assert.equal(t.state.activeModality,id);assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert.equal(t.get("standards-link").attrs.href,"/standards/overview");assert.equal(t.get("module-details-link").attrs.href,catalog.overview_url+"/modules/M04");assert(t.visualNodes().every(node=>node.status==="framework"));assert(!calls.some(url=>/recommend|\/plan/.test(url)));}
});
check("all four modality drafts are discoverable and discarded without changing unrelated session data",async()=>{
  const modalities=["scalp_eeg","ecog","seeg","extracellular"],catalogs=Object.fromEntries(modalities.map(id=>[id,fourCatalog(id)]));
  const t=harness(async url=>response(catalogs[new URL(url,"http://localhost").searchParams.get("modality")||"scalp_eeg"]),{selected:false});t.state.catalog=catalogs.scalp_eeg;t.state.records=modalities.flatMap(id=>catalogs[id].inputs);t.storage.set("unrelated","keep");
  for(const [index,id] of modalities.entries()){await t.selectInput(`${id}-0`);t.get("start-seconds").value=index+10;t.saveDraft();const key=id==="scalp_eeg"?"ephys-qc.draft.v1":`ephys-qc.draft.v1.${id}`;const saved=JSON.parse(t.storage.get(key));saved.updated_at=`2026-10-30T00:00:0${index}Z`;t.storage.set(key,JSON.stringify(saved));assert.equal(saved.modality,id);}
  for(const [index,id] of modalities.entries()){const key=id==="scalp_eeg"?"ephys-qc.draft.v1":`ephys-qc.draft.v1.${id}`,saved=JSON.parse(t.storage.get(key));saved.updated_at=`2026-10-30T00:00:0${index}Z`;t.storage.set(key,JSON.stringify(saved));}
  t.storage.delete("ephys-qc.draft.v1.latest");t.clearInputDraft();t.state.activeModality="scalp_eeg";t.state.catalog=catalogs.scalp_eeg;assert.equal(t.savedDraft().modality,"extracellular");await t.restoreDraft();assert.equal(t.state.input.modality,"extracellular");assert.equal(t.get("start-seconds").value,"13");assert.equal(t.state.plan,null);t.discardDraft();assert.equal(t.savedDraft(),null);assert.equal(t.storage.get("unrelated"),"keep");for(const key of t.storage.keys())assert(!key.startsWith("ephys-qc.draft.v1"));
});
check("toolbox browsing across four modalities is independent from the active plan",async()=>{
  const modalities=["scalp_eeg","ecog","seeg","extracellular"],catalogs=Object.fromEntries(modalities.map(id=>[id,fourCatalog(id)]));const t=harness(async url=>response(catalogs[new URL(url,"http://localhost").searchParams.get("modality")||"scalp_eeg"]),{selected:false});t.state.catalog=catalogs.scalp_eeg;t.state.records=modalities.flatMap(id=>catalogs[id].inputs);await t.selectInput("seeg-0");t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();const before=t.fingerprint(),plan=t.state.plan;
  for(const id of modalities){assert(await t.browseMethods(id));assert.equal(t.fingerprint(),before);assert.equal(t.state.plan,plan);assert.equal(t.state.activeModality,"seeg");t.showModule("M03",{catalog:t.state.browseCatalog,modality:id,browsing:true});assert.equal(t.get("module-details-link").attrs.href,catalogs[id].overview_url+"/modules/M03");assert(!t.get("module-dialog-content").innerHTML.includes('type="checkbox"'));}
});
check("Neuropixels AP/LF evidence is displayed without inferring sorted spikes or auto-confirming",()=>{
  const t=harness(undefined,{selected:false});t.state.catalog=fourCatalog();
  for(const band of ["ap","lf"]){t.state.intake={id:band,status:"needs_confirmation",metadata:{format:"SpikeGLX",acquisition:{stream_band:band,probe_type:21},channels:[{index:0,name:"signal",sampling_rate_hz:band==="ap"?30000:2500,unit:"uV",channel_type:"neuropixels",channel_type_source:"file_declared"}]},suggestions:{modality:"extracellular",eeg_indices:[0],reference_indices:{},modality_evidence:{status:"file_declared",source:"source.channel_types",reason:"SpikeGLX raw stream"}}};t.renderIntake();const summary=t.get("record-summary").innerHTML;assert(summary.includes(`<dd>${band.toUpperCase()}</dd>`));assert(summary.includes("<dd>21</dd>"));assert(summary.includes("细胞外电生理（待确认）"));assert(!/spikes|已分选/.test(summary));assert(!t.get("intake-confirmed").checked);assert.equal(t.state.input,null);assert(t.get("intake-modality-note").textContent.includes("SpikeGLX AP/LF"));const background=t.get("intake-confirmation").innerHTML.match(/<details class="intake-context intake-background"[^>]*>([\s\S]*?)<\/details>/);assert(background);assert(!background[0].startsWith('<details class="intake-context intake-background" open'));for(const field of fields)assert(background[1].includes(`intake-context-${field}`));}
  delete t.state.intake.metadata.acquisition;t.renderExtraction();assert(!t.get("record-summary").innerHTML.includes("信号频带"));assert(!t.get("record-summary").innerHTML.includes("探针型号"));
});
check("extracellular directory support does not override the backend rejection of other extracellular recordings",async()=>{
  let calls=0;const t=harness(async url=>{calls++;assert(url.endsWith("/recommend"));return response({recommendation_id:"unsupported-extracellular",status:"unsupported",can_apply:false,reason:"Only verified SpikeGLX raw AP/LF is supported",qc_config:null,selected_modules:[],missing_fields:[]})},{selected:false});t.state.catalog=fourCatalog("extracellular");t.state.activeModality="extracellular";delete t.state.catalog.inputs[0].metadata.acquisition;await t.selectInput("extracellular-0",{autoPrepare:true});assert.equal(calls,1);assert.equal(t.state.plan,null);assert(t.get("run-button").disabled);assert(t.get("recommendation-content").innerHTML.includes("Only verified SpikeGLX"));assert.equal(t.state.job,null);
});
check("file-declared digital sync channels cannot become neural or physiological analysis roles",()=>{
  const t=harness(undefined,{selected:false});t.state.catalog=fourCatalog();t.state.intake={id:"sync",metadata:{channels:[{index:0,name:"AP0",sampling_rate_hz:30000,unit:"uV",channel_type:"neuropixels",channel_type_source:"file_declared"},{index:1,name:"ECG_named_sync",sampling_rate_hz:30000,unit:"bits",channel_type:"stim",channel_type_source:"file_declared",stream_band:"sync"}]},suggestions:{modality:"extracellular",eeg_indices:[0,1],reference_indices:{ecg:1},modality_evidence:{status:"file_declared"}}};t.renderIntake();assert.equal(t.intakeRole(1,t.state.intake.suggestions),"unused");assert(t.get("intake-confirmation").innerHTML.includes("同步 / 数字通道（不分析）"));
  const fields={modality:"extracellular",reference_scheme:"unknown",confirmed:true,context_tags:{disease:"unknown",age_group:"unknown",task:"unknown"}};for(const role of ["eeg","ecg","eog","emg"])assert.throws(()=>t.intakeConfirmation([{index:0,role:"eeg"},{index:1,role}],fields),/同步 \/ 数字通道不能/);const request=t.intakeConfirmation([{index:0,role:"eeg"},{index:1,role:"unused"}],fields);assert.deepEqual([...request.eeg_indices],[0]);assert.deepEqual(Object.keys(request.reference_indices),[]);
});
check("refreshing generated registered options preserves selection and original labels",async()=>{
  const t=harness(undefined,{selected:false});t.state.catalog=fourCatalog("scalp_eeg");t.state.records=t.state.catalog.inputs;t.state.records[0].label="原始文件名.flac";await t.selectInput("scalp_eeg-0");const before=t.fingerprint();t.renderRegisteredInputs();assert.equal(t.get("input-select").value,"scalp_eeg-0");assert(t.get("input-select").innerHTML.includes("原始文件名.flac"));assert.equal(t.fingerprint(),before);
});
check("unpaired SpikeGLX META and direct BIN failures remain explicit and never retry or plan",async()=>{
  for(const [name,error] of [["record.ap.meta","SpikeGLX须将同名.ap.bin/.ap.meta或.lf.bin/.lf.meta一起打包ZIP，不能单独提交META。"],["record.ap.bin","请选择已支持格式；SpikeGLX的单流BIN和META必须一起打包ZIP。"],["missing-pair.zip","SpikeGLX配套缺失：META须对应同名AP或LF BIN。"]]){
    const calls=[],t=harness(async(url,options)=>{calls.push([url,options.method]);return {...response({error}),ok:false,status:400}});t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.get("intake-file").files=[{name,size:2048}];await t.uploadIntake();assert.deepEqual(calls,[["/api/v1/intakes","POST"]]);assert.equal(t.get("intake-error").textContent,error);assert.equal(t.get("intake-status").textContent,"读取未完成");assert.equal(t.state.intake,null);assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert(t.get("run-button").disabled);assert(!t.state.intakeBusy);assert.equal(t.get("intake-file").files[0].name,name);
  }
});
function nwbIntake(selected = null) {
  const available_streams=[{stream_id:"/acquisition/raw",name:"Raw",object_type:"ElectricalSeries",status:"available",sample_count:10000,channel_count:2,sampling_rate_hz:1000,duration_seconds:10},{stream_id:"/processing/ecephys/LFP/lfp",name:"LFP",container_type:"LFP",object_type:"ElectricalSeries",status:"available",sample_count:1000,channel_count:1,sampling_rate_hz:100,duration_seconds:10},{stream_id:"/acquisition/irregular",name:"Irregular <signal>",object_type:"ElectricalSeries",status:"unsupported",reason:"Irregular clock"}];
  return {id:"nwb/intake",status:"needs_confirmation",filename:"sample.nwb",metadata:{format:"NWB",nwb:{version:"2.8.0",units_present:true,units_count:3,electrical_series_count:3},available_streams,selected_stream_id:selected,channels:selected?[{index:7,name:selected.includes("LFP")?"LFP7":"RAW7",unit:"uV",sampling_rate_hz:selected.includes("LFP")?100:1000,channel_type:"ecog",channel_type_source:"file_declared"}]:[],duration_seconds:selected?10:null},suggestions:{modality:selected?"ecog":"unknown",eeg_indices:selected?[7]:[],reference_indices:{},modality_evidence:{status:selected?"file_declared":"unknown"}}};
}
check("NWB multistream extraction blocks confirmation and distinguishes unsupported streams and Units",()=>{
  const t=harness(undefined,{selected:false});t.state.intake=nwbIntake();t.state.filePending=true;t.renderIntake();t.updateActions();const rendered=t.get("record-summary").innerHTML;
  assert(rendered.includes('id="intake-stream"'));assert(rendered.includes("先选择信号"));assert(rendered.includes("Units 不属于连续电压流"));assert(rendered.includes("Irregular &lt;signal&gt;"));assert(/value="\/acquisition\/irregular"[^>]*disabled/.test(rendered));assert(!rendered.includes('value="Units"'));assert(t.get("intake-confirmation").hidden);assert.equal(t.get("intake-confirmation").innerHTML,"");assert.throws(()=>t.intakeConfirmation([],{modality:"ecog",confirmed:true}),/先选择/);assert(t.get("run-button").disabled);
});
check("NWB stream selection resets roles and plans without confirming, recommending or creating jobs",async()=>{
  const calls=[],t=harness(async(url,options)=>{calls.push([url,options.method,JSON.parse(options.body)]);return response(nwbIntake("/processing/ecephys/LFP/lfp"))});t.state.intake=nwbIntake("/acquisition/raw");t.state.filePending=true;t.state.plan=planFixture(t.body());t.state.planKey=t.fingerprint();t.get("intake-confirmed").checked=true;
  assert(await t.selectIntakeStream("/processing/ecephys/LFP/lfp"));assert.deepEqual(calls,[["/api/v1/intakes/nwb%2Fintake/stream","POST",{stream_id:"/processing/ecephys/LFP/lfp"}]]);assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert.equal(t.state.job,null);assert.equal(t.state.recommendation,null);assert.equal(t.state.intake.metadata.channels[0].index,7);assert.equal(t.intakeRole(7,t.state.intake.suggestions),"eeg");assert(!t.get("intake-confirmed").checked);assert(!t.state.intakeBusy);assert.equal(t.state.intake.status,"needs_confirmation");assert(t.get("run-button").disabled);
});
check("File picker preserves raw names, allows replacement, and never starts processing on selection",()=>{
  const t=harness(undefined,{selected:false});t.updateActions();assert(t.get("file-picker-name").hidden);
  t.get("intake-file").files=[{name:"临床记录 <1>.nwb",size:1024}];t.chooseLocalFile();
  assert.equal(t.get("file-picker-title").textContent,"已选择文件");assert(t.get("file-picker-name").textContent.includes("临床记录 <1>.nwb"));assert(!t.get("file-picker-name").hidden);assert.equal(t.state.intake,null);assert.equal(t.state.job,null);assert(t.get("run-button").disabled);
  t.get("intake-file").files=[];t.chooseLocalFile();assert.equal(t.get("file-picker-title").textContent,"选择本机文件");assert(t.get("file-picker-name").hidden);assert(t.get("intake-upload-button").disabled);
});
check("Header disclosure navigation only reveals its target and preserves the analysis plan",()=>{
  const t=harness(), before=t.fingerprint();t.state.plan=planFixture(t.body());t.state.planKey=before;const plan=t.state.plan;
  for(const id of ["toolkit-section","run-history-panel","registered-records"]){t.get(id).open=false;assert(t.revealNavigationTarget("#"+id));assert(t.get(id).open);}
  assert(!t.revealNavigationTarget("#module-M03"));assert(!t.revealNavigationTarget("/standards/overview"));assert.equal(t.fingerprint(),before);assert.equal(t.state.plan,plan);assert(t.validPlan());
});
check("A direct toolkit link opens its disclosure after initial catalog loading",async()=>{
  const t=harness(async url=>response(url.includes("catalog")?fixtureCatalog():{jobs:[]}),{selected:false,hash:"#toolkit-section"});
  t.get("toolkit-section").open=false;assert(await t.loadCatalog());assert(t.get("toolkit-section").open);assert.equal(t.state.input,null);assert.equal(t.state.plan,null);assert(t.get("run-button").disabled);
});
check("NWB stream requests are serialized and late replies cannot overwrite a new file",async()=>{
  let resolve,calls=0;const t=harness(async()=>{calls++;return new Promise(done=>resolve=done)},{selected:false});t.state.intake=nwbIntake("/acquisition/raw");t.state.filePending=true;const pending=t.selectIntakeStream("/processing/ecephys/LFP/lfp");assert(t.state.intakeBusy);assert(t.needsStreamSelection());assert(t.get("record-summary").innerHTML.includes("待选信号"));assert(!t.get("intake-confirmed").checked);assert.equal(t.state.intake.metadata.channels.length,0);assert(t.get("record-summary").innerHTML.includes('id="intake-stream" disabled'));assert.equal(await t.selectIntakeStream("/acquisition/raw"),false);assert.equal(calls,1);
  t.get("intake-file").files=[{name:"new.edf",size:10}];t.chooseLocalFile();resolve(response(nwbIntake("/processing/ecephys/LFP/lfp")));assert.equal(await pending,false);assert.equal(t.state.intake,null);assert.equal(t.state.plan,null);assert(t.get("file-picker-name").textContent.includes("new.edf"));assert.equal(t.get("intake-status").textContent,"");assert(!t.state.intakeBusy);
});
check("NWB stream failures block stale confirmation and are not automatically retried",async()=>{
  for(const malformed of [false,true]){let calls=0;const t=harness(async()=>{calls++;return malformed?response(nwbIntake("/acquisition/raw")):{...response({error:"Unavailable stream"}),ok:false,status:400}},{selected:false});t.state.intake=nwbIntake("/acquisition/raw");t.state.filePending=true;assert.equal(await t.selectIntakeStream("/processing/ecephys/LFP/lfp"),false);assert.equal(calls,1);assert(t.needsStreamSelection());assert(!t.get("intake-error").hidden);assert(t.get("intake-confirmation").hidden);assert(!t.state.intakeBusy);assert.equal(t.state.plan,null);}
});
check("NWB single streams stay unconfirmed and frozen or revision records cannot change streams",async()=>{
  const t=harness(undefined,{selected:false});t.state.intake=nwbIntake("/acquisition/raw");t.state.intake.metadata.available_streams=[t.state.intake.metadata.available_streams[0]];t.renderIntake();assert(!t.get("record-summary").innerHTML.includes('id="intake-stream"'));assert(t.get("record-summary").innerHTML.includes("当前信号"));assert(!t.get("intake-confirmed").checked);assert.equal(t.state.input,null);
  for(const mode of ["registered","revision","job"]){t.state.mode=mode==="job"?"job":"draft";t.state.intake=nwbIntake("/acquisition/raw");t.state.intake.status=mode;t.state.revisionInput=mode==="revision"?{id:"record"}:null;assert.equal(await t.selectIntakeStream("/processing/ecephys/LFP/lfp"),false);const frozen=t.streamSummaryHtml({metadata:t.state.intake.metadata},false);assert(!frozen.includes('id="intake-stream"'));assert(frozen.includes("切换信号需重新读取"));}
});
check("NWB confirmation freezes the selected stream and never adds it to ordinary formats or metadata revisions",()=>{
  const t=harness(undefined,{selected:false}),fields={modality:"ecog",confirmed:true,reference_scheme:"unknown",context_tags:{}};t.state.intake=nwbIntake("/acquisition/raw");const roles=[{index:7,role:"eeg"}];assert.equal(t.intakeConfirmation(roles,fields).selected_stream_id,"/acquisition/raw");t.state.revisionInput={id:"registered"};assert(!Object.hasOwn(t.intakeConfirmation(roles,fields),"selected_stream_id"));t.state.revisionInput=null;t.state.intake.metadata.format="EDF";delete t.state.intake.metadata.available_streams;delete t.state.intake.metadata.selected_stream_id;assert(!Object.hasOwn(t.intakeConfirmation(roles,fields),"selected_stream_id"));
});
check("NWB processing container and probe evidence are shown without declaring a raw stream or filter",()=>{
  const t=harness(undefined,{selected:false});t.state.intake=nwbIntake("/processing/ecephys/LFP/lfp");t.state.intake.metadata.acquisition={system:"NWB",stream_band:"lf",source_container:"processing",probe_model:"Neuropixels 1.0",filtering_declaration:"unknown"};t.renderIntake();const summary=t.get("record-summary").innerHTML;assert(summary.includes("信号频带"));assert(summary.includes("<dd>LF</dd>"));assert(summary.includes("<dd>processing</dd>"));assert(summary.includes("<dd>Neuropixels 1.0</dd>"));assert(!summary.includes("原始数据流"));assert(!summary.includes("已滤波"));
});
check("NWB unextracted events are not presented as absent annotations",()=>{
  const t=harness(undefined,{selected:false});t.state.intake=nwbIntake("/acquisition/raw");t.state.intake.metadata.annotations={extraction_status:"not_extracted",count:null,available:null,time_reference:"not_mapped_to_selected_series"};assert.equal(t.annotationText(t.state.intake.metadata),"尚未提取");t.renderIntake();const summary=t.get("record-summary").innerHTML;assert(summary.includes("尚未提取"));assert(summary.includes("文件可能含事件；尚未映射到所选信号。"));assert(!summary.includes("未检出标注"));const before=JSON.stringify(t.state.intake);assert.equal(t.annotationText({format:"NWB",annotations:{count:0}}),"提取状态未记录");assert.equal(t.annotationText({format:"NWB"}),"提取状态未记录");assert.equal(JSON.stringify(t.state.intake),before);assert.equal(t.annotationText({annotations:{count:0}}),"未检出标注");assert.equal(t.annotationText({annotations:{count:2}}),"2 条记录");
});
check("NWB Units-only and unsupported-stream files never create waveform confirmation",()=>{
  const t=harness(undefined,{selected:false});for(const streams of [[],[nwbIntake().metadata.available_streams[2]]]){t.state.intake=nwbIntake();t.state.intake.metadata.available_streams=streams;t.state.intake.metadata.nwb.units_count=0;t.renderIntake();t.updateActions();assert(t.get("record-summary").innerHTML.includes("未找到可用的连续电压流"));assert(t.get("record-summary").innerHTML.includes("已识别 Units：0"));assert(t.get("intake-confirmation").hidden);assert(t.get("run-button").disabled);assert(!t.get("record-summary").innerHTML.includes('id="intake-stream"'));}
});
if(process.env.QC_CATALOG_FIXTURE)check("actual four-route catalogs and registered metadata work without network mutations or planning",async()=>{
  const fixture=JSON.parse(fs.readFileSync(process.env.QC_CATALOG_FIXTURE,"utf8")),catalogs=fixture.catalogs,records=fixture.inputs,calls=[];
  const t=harness(async(url,options={})=>{calls.push([url,options.method||"GET"]);assert(!options.method || options.method==="GET");if(url==="/api/v1/inputs")return response({inputs:records});if(url==="/api/v1/jobs")return response({jobs:[]});const requested=new URL(url,"http://localhost");if(requested.pathname==="/api/v1/catalog")return response(catalogs[requested.searchParams.get("modality")||"scalp_eeg"]);throw Error(`Unexpected request ${url}`)},{selected:false,serverInputs:true});t.state.catalog=null;assert(await t.loadCatalog());assert.equal(t.state.input,null);assert.equal(t.visibleInputs().length,records.length);
  for(const modality of ["scalp_eeg","ecog","seeg","extracellular"]){const subset=records.filter(record=>record.modality===modality);assert(subset.length,`Real registered metadata for ${modality}`);
    for(const record of subset){await t.selectInput(record.id);assert.equal(t.state.input.id,record.id);assert.equal(t.state.activeModality,modality);assert.equal(t.state.plan,null);assert.equal(t.moduleStandardsUrl("M03"),catalogs[modality].overview_url+"/modules/M03");assert(t.toolkitMethods("all","all").every(method=>(method.implementation==="planned"?method.intended_modalities:method.supported_modalities).includes(modality)));
      if(modality!=="scalp_eeg")assert(!t.body().selected_modules.includes("M06"));if(record.metadata?.acquisition){const summary=t.get("record-summary").innerHTML,acquisition=record.metadata.acquisition;if(["ap","lf"].includes(acquisition.stream_band))assert(summary.includes(`<dd>${acquisition.stream_band.toUpperCase()}</dd>`));if(acquisition.probe_type!=null || acquisition.probe_model!=null)assert(summary.includes("探针型号"));if(["acquisition","processing"].includes(acquisition.source_container))assert(summary.includes(`<dd>${acquisition.source_container}</dd>`));}if(record.metadata?.available_streams){assert(!t.get("record-summary").innerHTML.includes('id="intake-stream"'));assert(record.metadata.selected_stream_id,"Registered NWB has frozen stream");}
    }
  }
  for(const intake of fixture.intakes||[]){t.clearInputDraft();t.state.intake=intake;t.renderIntake();assert(!t.get("intake-confirmed").checked);assert.equal(t.state.input,null);if(Array.isArray(intake.metadata.available_streams)){const summary=t.get("record-summary").innerHTML;if(intake.metadata.available_streams.length>1)assert(summary.includes('id="intake-stream"'));if(!intake.metadata.selected_stream_id)assert(t.get("intake-confirmation").hidden);if(intake.metadata.nwb?.units_present)assert(summary.includes("Units 不属于连续电压流"));}for(const channel of intake.metadata.channels){if(channel.channel_type_source==="file_declared"&&channel.channel_type==="stim")assert.equal(t.intakeRole(channel.index,intake.suggestions),"unused");}}
  assert(calls.every(([url,method])=>method==="GET"&&!/recommend|\/plan/.test(url)));assert.equal(t.state.job,null);
});
let failures=0;
for(const [name,run] of tests){try{await run();console.log(`PASS ${name}`)}catch(error){failures++;console.error(`FAIL ${name}\n${error.stack}`)}}
console.log(`${tests.length-failures}/${tests.length} pure JavaScript checks passed. Visual/browser behavior is not tested.`);
if(failures)process.exitCode=1;
