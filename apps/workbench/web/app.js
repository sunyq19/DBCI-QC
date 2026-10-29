"use strict";

(() => {
  const API = "/api/v1";
  const OPTIONAL = ["M03", "M04", "M05", "M06", "M07"];
  const FIXED = ["M01", "M02", "M08", "M09"];
  const ORDER = ["M01", "M02", ...OPTIONAL, "M08", "M09"];
  const MODULE_LABELS = {M01:"文件读取",M02:"数据识别",M03:"信号完整性",M04:"频谱干扰",M05:"通道质量",M06:"生理伪迹",M07:"状态与事件",M08:"分项评价",M09:"质控报告"};
  const MODALITY_LABELS = {unknown:"待确认",scalp_eeg:"头皮 EEG",ecog:"ECoG",seeg:"sEEG",extracellular:"细胞外电生理",other:"其他模态"};
  const CONTEXT_FIELDS = {disease:"疾病背景",age_group:"年龄组",task:"记录任务"};
  const METHOD_CATEGORY = {basic:"通用",conditional:"条件",optional:"可选"};
  const ACTIVE = new Set(["queued", "running", "cancelling"]);
  const FINISHED_MODULES = new Set(["completed", "partial", "skipped", "failed"]);
  const STATUS = {framework:"流程框架",ready:"就绪",pending:"等待",queued:"排队中",running:"运行中",cancelling:"正在取消",completed:"已完成",partial:"条件受限",blocked:"当前不可用",planned:"尚未接入",unplanned:"待规划",not_selected:"未选择",skipped:"已跳过",failed:"失败",cancelled:"已取消",interrupted:"已中断",selected:"已选择",required:"固定步骤",unselected:"未选择"};
  const $ = id => document.getElementById(id);
  const escape = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
  const clone = value => JSON.parse(JSON.stringify(value));
  const pretty = value => typeof value === "string" ? value : JSON.stringify(value, null, 2);
  const arr = value => Array.isArray(value) ? value : [];
  const state = {catalog:null,input:null,draftConfig:null,selected:new Set(OPTIONAL),extensions:new Set(),contextTags:{disease:"unknown",age_group:"unknown",task:"unknown"},initialContext:{},dialogModule:null,plan:null,planKey:null,planning:false,submitting:false,cancelling:false,job:null,result:null,mode:"draft",history:[],pollTimer:null,jobRequest:0,resultRequest:0,resultJobId:null,pollFailures:0,historyBusy:false,loadingCatalog:false,recommendation:null,recommendationKey:null,recommending:false,recommendationApplied:false,recommendationStale:false,intake:null,intakeBusy:false,draftEpoch:0,planRequest:0,manualDraft:false,parameterDirty:false,filePending:false,intakeRequest:0,catalogRequest:0,boardKey:null};
  Object.assign(state,{scope:"window",parentJobId:null,revisionInput:null,navigationRestored:false,workspace:null,workspaceRequest:0,waveformRequest:0,waveform:null,candidates:[],candidateId:null,candidateLimit:100,review:null,reviewBusy:false,reviewDrafts:{},cloneBusy:false,uploadAbort:null});
  const DRAFT_KEY = "ephys-qc.draft.v1";

  function numeric(value) { return typeof value === "number" && Number.isFinite(value); }
  function number(value, decimals = 1) { return numeric(value) ? value.toLocaleString(window.QCI18n?.getLanguage() || "zh-CN", {maximumFractionDigits:decimals}) : "未提供"; }
  function size(value) { if (!numeric(value)) return "大小未提供"; return value < 1024 * 1024 ? `${number(value / 1024)} KiB` : `${number(value / 1024 / 1024)} MiB`; }
  function date(value) { const d = new Date(value); return Number.isNaN(d.valueOf()) ? String(value || "时间未提供") : d.toLocaleString(window.QCI18n?.getLanguage() || "zh-CN", {month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false}); }
  function statusTag(status) { const known = Object.hasOwn(STATUS, status); return `<span class="tag ${known ? escape(status) : "subtle"}">${escape(STATUS[status] || status || "未提供")}</span>`; }
  function setError(id, message) { $(id).textContent = message || ""; $(id).hidden = !message; }
  function setConnection(online, text) { const el = $("connection-status"); el.className = `connection ${online ? "online" : "offline"}`; el.lastElementChild.textContent = text || (online ? "本地服务已连接" : "本地服务未连接"); }

  async function api(path, options = {}) {
    const {timeoutMs = 20000,binary = false,...requestOptions} = options;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(`${API}${path}`, {cache:"no-store",...requestOptions,signal:controller.signal,headers:{"Accept":"application/json",...(options.body ? {"Content-Type":binary ? "application/octet-stream" : "application/json"} : {}),...options.headers}});
      const type = response.headers.get("content-type") || "";
      let data;
      if (type.includes("json")) data = await response.json();
      else {
        const body = await response.text();
        try { data = JSON.parse(body); }
        catch { throw new Error(response.ok ? "本地服务未返回 JSON。请从工作台服务入口打开页面。" : `本地服务返回 HTTP ${response.status}。`); }
      }
      if (!response.ok) { const error = new Error(data.error || `请求失败（HTTP ${response.status}）`); error.status = response.status; throw error; }
      setConnection(true);
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error(options.method === "POST" && path === "/jobs" ? "请求超时，提交状态尚不确定。请先刷新运行记录，确认是否已创建任务，避免重复提交。" : path.startsWith("/intakes") ? "读取或确认请求超时，状态尚不确定；不会自动重试。若已有读取编号，可恢复后确认。" : "本地服务响应超时，请稍后重试。");
      if (error instanceof TypeError) { setConnection(false); throw new Error("无法连接本地服务。请确认工作台服务仍在运行，再重试。"); }
      throw error;
    } finally { clearTimeout(timer); }
  }

  function currentConfig() {
    if (!state.input) return null;
    const config = clone(state.draftConfig || state.input.default_config || {});
    config.selection = {...(config.selection || {}),start_seconds:Number($("start-seconds").value),duration_seconds:Number($("duration-seconds").value)};
    config.context_tags = {...state.contextTags};
    config.method_config = {...(config.method_config || {}),extensions:[...state.extensions].sort()};
    config.scope = state.scope;
    return config;
  }

  function validation() {
    if (!state.input) return "请先读取数据文件。";
    if (state.input.availability?.status === "unavailable") return state.input.availability.reason || "来源文件当前不可用。";
    if (state.scope === "recording") return arr(currentConfig()?.selection?.eeg_indices).length ? null : "配置未明确指定 EEG 通道索引，不能运行。";
    if (!$("start-seconds").value.trim() || !$("duration-seconds").value.trim()) return "请填写分析起点和时长。";
    const start = Number($("start-seconds").value), duration = Number($("duration-seconds").value);
    if (!Number.isFinite(start) || start < 0) return "分析起点必须是大于或等于 0 的秒数。";
    if (!Number.isFinite(duration) || duration <= 0) return "分析时长必须大于 0 秒。";
    if (duration > 120) return "单次分析最多 120 秒，请修改时长。";
    const total = state.input.metadata?.duration_seconds;
    if (numeric(total) && (start >= total || start + duration > total + 1e-7)) return `所选时段超出记录范围（0–${number(total,3)} 秒）。`;
    if (!arr(currentConfig()?.selection?.eeg_indices).length) return "配置未明确指定 EEG 通道索引，不能运行。";
    return null;
  }

  function body() {
    return {input_id:state.input.id,selected_modules:ORDER.filter(id => FIXED.includes(id) || state.selected.has(id)),qc_config:currentConfig()};
  }
  function unsupportedInput() {
    // This is a property of the recording, not of a disposable recommendation.
    // Retain legacy records without a modality field; new intake requires one.
    return typeof state.input?.modality === "string" && state.input.modality !== "scalp_eeg";
  }
  function fingerprint() { return state.input ? JSON.stringify(body()) : null; }
  function validPlan() { return state.plan && state.planKey === fingerprint(); }
  function activePlan() { return state.mode === "job" ? state.job?.plan || null : validPlan() ? state.plan : null; }

  function allMethods() {
    return arr(state.catalog?.modules).flatMap(module => arr(module.methods).map(method => ({...method,module_id:module.id,module_name:module.name})));
  }
  function extensionMethods() { return allMethods().filter(method => method.optional_extension && method.implementation === "available"); }
  function safeSourceUrl(value) {
    try { const url = new URL(value); return ["https:","http:"].includes(url.protocol) ? url.href : null; }
    catch { return null; }
  }

  function moduleStandardsUrl(id) { return ORDER.includes(id) ? `/standards/modules/${id}` : null; }
  function moduleFromHash(hash) {
    const id = typeof hash === "string" && hash.startsWith("#module-") ? hash.slice(8) : null;
    return ORDER.includes(id) ? id : null;
  }
  function openModuleFromHash() {
    const id = moduleFromHash(location.hash);
    if (id) showModule(id);
  }
  function moduleDialogClosed() {
    // A queued close event must not clear a dialog that has already reopened.
    if ($("module-dialog").open) return;
    state.dialogModule = null;
    // Replace only our own fragment, without navigating away or emitting hashchange.
    if (moduleFromHash(location.hash)) window.history.replaceState(window.history.state,"",`${location.pathname}${location.search}`);
  }

  function toolkitMethods(category = $("toolkit-category").value, implementation = $("toolkit-implementation").value) {
    return allMethods().filter(method => (!category || category === "all" || method.category === category) && (!implementation || implementation === "all" || method.implementation === implementation));
  }

  function renderToolkit() {
    const methods = toolkitMethods();
    $("toolkit-count").textContent = `${methods.length} / ${allMethods().length} 项方法`;
    $("toolkit-methods").innerHTML = methods.length ? methods.map(method => `<button class="toolkit-card" data-detail="${escape(method.module_id)}"><span class="toolkit-card-top"><span class="tag method-category ${escape(method.category)}">${escape(METHOD_CATEGORY[method.category] || "未分类")}</span><span class="small muted">${method.implementation === "available" ? "已接入" : "待接入"}</span></span><strong>${escape(method.name)}</strong><span>${escape(method.documentation?.purpose || method.description || "打开模块查看说明")}</span><small>${escape(method.module_id)} · 打开原理、条件与来源 ↗</small></button>`).join("") : '<p class="small muted">当前筛选没有方法。可切换类别或接入状态。</p>';
  }

  function recommendationValid() { return Boolean(state.recommendation && state.recommendationKey === fingerprint()); }

  function recommendationList(title, methods) {
    return arr(methods).length ? `<details class="recommendation-list recommendation-fold"><summary>${escape(title)} <span class="tag subtle">${methods.length} 项</span></summary>${methods.map(method => `<div><strong>${escape(method.name || method.id || "方法")}</strong><span class="small muted"> ${escape(method.module_id || "")}</span><p>${escape(method.reason || "未提供理由")}</p>${method.module_id ? `<button class="text-button" data-detail="${escape(method.module_id)}">查看方法依据 ↗</button>` : ""}</div>`).join("")}</details>` : "";
  }

  function renderRecommendation() {
    const recommendation = state.recommendation, container = $("recommendation-content");
    if (state.mode === "job") {
      container.innerHTML = `<p class="recommendation-summary">正在查看已有运行：${escape(state.job?.label || state.job?.id || "读取中")}</p><p class="small muted">下方显示这次运行保存的方案与结果。选择数据后可准备新的检查。</p>`;
      return;
    }
    if (unsupportedInput()) {
      container.innerHTML = '<p class="recommendation-summary">仅信息提取</p><p class="small muted">当前模态仅保存提取信息，不运行头皮 EEG 质控。</p>';
      return;
    }
    const config = currentConfig(), selection = config?.selection || {}, indices = arr(selection.eeg_indices);
    const rates = [...new Set(arr(state.input?.metadata?.channels).filter(channel => indices.includes(channel.index)).map(channel => channel.sampling_rate_hz).filter(numeric))];
    const facts = state.input ? `<p class="small muted">${indices.length} 道 EEG · ${rates.map(rate => number(rate)).join(" / ") || "未知"} Hz · 原记录 ${number(selection.start_seconds,3)}–${number(selection.start_seconds + selection.duration_seconds,3)} 秒</p>` : "";
    if (!recommendation || !recommendationValid()) {
      container.innerHTML = facts + (state.recommending ? '<p class="recommendation-summary">正在准备推荐方案…</p><p class="small muted">核对数据条件后即可开始检查。</p>' : state.manualDraft ? `<p class="recommendation-summary">手动方案 · 修改已保留</p><p class="small muted">${validPlan() ? "方案已就绪。" : "开始检查时会先核对最新配置。"}</p><button class="text-button" data-reset-recommend>恢复推荐方案</button>` : '<p class="small muted">推荐方案尚未就绪。</p><button class="text-button" data-reset-recommend>重新准备推荐方案</button>');
      return;
    }
    const missing = arr(recommendation.missing_fields), blocking = missing.filter(field => field.blocking), optionalMissing = missing.filter(field => !field.blocking);
    const missingHtml = fields => fields.map(field => `<div><strong>${escape(field.label || field.key)} ${field.blocking ? "· 需先补充" : "· 可保留未知"}</strong><p>${escape(field.reason || "未提供原因")}</p></div>`).join("");
    const selectedModules = arr(recommendation.selected_modules).filter(id => OPTIONAL.includes(id)).map(id => arr(state.catalog?.modules).find(module => module.id === id)?.name || id);
    const enhanced = arr(recommendation.qc_config?.method_config?.extensions).map(id => allMethods().find(method => method.id === id)?.name || id);
    const focus = Array.isArray(recommendation.review_focus) ? recommendation.review_focus : recommendation.review_focus ? [recommendation.review_focus] : [];
    container.innerHTML = `${facts}<p class="recommendation-summary">${recommendation.can_apply ? state.recommendationApplied ? validPlan() ? "推荐方案已就绪" : state.planning || state.recommending ? "正在核对推荐方案" : "方案核对未完成" : "推荐已生成，尚未采用" : "需要补充信息"}</p>${state.recommendationApplied && !validPlan() && !state.planning && !state.recommending ? '<button class="text-button" data-reset-recommend>重新准备推荐方案</button>' : ""}${recommendation.can_apply ? '<p class="small muted">保留原始数据，报告候选与待复核项。</p>' : `<div class="notice warning">${escape(recommendation.reason || recommendation.summary || "请先补充必需字段，或确认输入条件。")}</div>`}${blocking.length ? `<section class="recommendation-list missing-fields"><h3>必须先补充 · ${blocking.length} 项</h3>${missingHtml(blocking)}</section>` : ""}<details class="recommendation-fold"><summary>推荐理由与方法详情</summary>${selectedModules.length || enhanced.length ? `<div class="recommendation-combination">${selectedModules.length ? `<p><span>检查模块</span>${escape(selectedModules.join(" · "))}</p>` : ""}${enhanced.length ? `<p><span>默认增强</span>${escape(enhanced.join(" · "))}</p>` : ""}</div>` : ""}<p>${escape(pretty(recommendation.summary || recommendation.reason || "未提供摘要"))}</p>${focus.length ? `<section class="recommendation-focus"><h3>复核重点</h3><ul>${focus.map(item => `<li>${escape(pretty(item))}</li>`).join("")}</ul></section>` : ""}${recommendationList("建议采用的方法与理由",recommendation.recommended_methods)}${recommendationList("可按需添加的方法",recommendation.optional_methods)}${recommendationList("当前不可用的方法",recommendation.blocked_methods)}${optionalMissing.length ? `<details class="recommendation-list recommendation-fold missing-fields"><summary>可补充字段 <span class="tag subtle">${optionalMissing.length} 项</span></summary>${missingHtml(optionalMissing)}</details>` : ""}${arr(recommendation.cautions).length ? `<details class="recommendation-fold recommendation-cautions"><summary>解释与使用边界 <span class="tag subtle">${recommendation.cautions.length} 项</span></summary><ul>${recommendation.cautions.map(item => `<li>${escape(pretty(item))}</li>`).join("")}</ul></details>` : ""}<details class="result-summary"><summary>推荐配置与原始依据</summary><pre>${escape(pretty(recommendation))}</pre></details></details>`;
  }

  // Every draft change advances an epoch, including A → B → A input switches.
  // Fingerprints alone cannot protect against an older response for the same input.
  function cancelDraftRequests() {
    ++state.draftEpoch; ++state.planRequest;
    state.recommending = false; state.planning = false;
  }

  async function prepareRecommendedPlan() {
    if (!state.input || state.submitting) return false;
    if (state.parameterDirty && !applyParameters()) { setError("plan-error","高级参数有误，请展开高级设置修正。"); $("advanced-settings").open = true; return false; }
    invalidatePlan({manual:false});
    return makeRecommendation({autoApply:true});
  }

  async function makeRecommendation({autoApply = false} = {}) {
    if (validation() || state.recommending || state.submitting || state.planning || state.mode !== "draft") return false;
    const epoch = state.draftEpoch, key = fingerprint(), request = {input_id:state.input.id,qc_config:currentConfig()};
    const current = () => epoch === state.draftEpoch && state.mode === "draft";
    state.recommending = true; setError("recommendation-error",null); renderRecommendation(); updateActions();
    try {
      const recommendation = await api("/recommend",{method:"POST",body:JSON.stringify(request)});
      if (!current() || fingerprint() !== key) return false;
      if (!recommendation.recommendation_id) throw new Error("推荐响应缺少标识，暂不能开始检查。");
      if (recommendation.can_apply === true && (!Array.isArray(recommendation.selected_modules) || !recommendation.qc_config || !recommendation.plan_id)) throw new Error("推荐响应缺少模块、配置或计划标识，暂不能开始检查。");
      state.recommendation = recommendation; state.recommendationKey = key; state.recommendationApplied = false; state.recommendationStale = false;
      if (autoApply && recommendation.can_apply === true && applyRecommendation()) return await makePlan();
      return recommendation.can_apply === true;
    } catch(error) { if (current()) setError("recommendation-error",error.message); return false; }
    finally { if (current()) { state.recommending = false; renderRecommendation(); updateActions(); } }
  }

  function syncParameterEditor() {
    state.parameterDirty = false;
    $("extension-parameters").value = pretty(currentConfig()?.method_config?.extension_parameters || {});
    setError("parameter-error",null); $("parameter-status").textContent = "";
  }

  function applyRecommendation() {
    if (!recommendationValid() || state.recommendation.can_apply !== true || state.recommendationApplied || state.planning || state.submitting) return false;
    const recommendation = state.recommendation, config = clone(recommendation.qc_config);
    state.draftConfig = config;
    state.selected = new Set(arr(recommendation.selected_modules).filter(id => OPTIONAL.includes(id)));
    state.extensions = new Set(arr(config.method_config?.extensions));
    state.contextTags = {...state.contextTags,...config.context_tags};
    $("start-seconds").value = config.selection?.start_seconds ?? $("start-seconds").value;
    $("duration-seconds").value = config.selection?.duration_seconds ?? $("duration-seconds").value;
    state.manualDraft = false; state.recommendationApplied = true; state.recommendationKey = fingerprint();
    renderContextEditors(); renderModuleOptions(); renderChannelConfig(); syncParameterEditor(); invalidatePlan({keepRecommendation:true,manual:false,cancelPending:false});
    return true;
  }

  function applyParameters() {
    if (!state.input || state.submitting) return false;
    try {
      const value = JSON.parse($("extension-parameters").value);
      if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("最外层必须是按扩展 ID 分组的 JSON 对象。");
      const ids = new Set(extensionMethods().map(method => method.id));
      for (const [id,params] of Object.entries(value)) {
        if (!ids.has(id)) throw new Error(`当前目录没有可用扩展：${id}`);
        if (!params || typeof params !== "object" || Array.isArray(params)) throw new Error(`${id} 的参数必须是 JSON 对象。`);
      }
      state.draftConfig = currentConfig(); state.draftConfig.method_config.extension_parameters = value;
      state.parameterDirty = false; invalidatePlan(); setError("parameter-error",null); $("parameter-status").textContent = "参数已保留；开始检查时会核对范围与适用条件。"; return true;
    } catch(error) { setError("parameter-error",`参数未应用：${error.message}`); return false; }
  }

  function renderInputUsage() {
    const container = $("input-usage"), plan = activePlan(), historical = state.mode === "job";
    container.hidden = !state.input && !historical;
    if (container.hidden) { container.innerHTML = ""; return; }
    const provenance = historical ? plan?.input_provenance : plan?.input_provenance ?? state.input?.provenance;
    const usage = historical ? plan?.input_data_usage : plan?.input_data_usage ?? state.input?.data_usage;
    const title = historical ? "所查看运行的来源与用途" : "所选记录的来源与用途";
    if (!provenance && !usage) {
      container.innerHTML = `<h3>${title}</h3><p class="small muted">${historical ? "该历史计划未记录来源与用途说明；不补用当前目录信息。" : "来源与用途说明尚未登记。"}</p>`;
      return;
    }
    const text = (value,fallback) => typeof value === "string" && value.trim() ? value : Array.isArray(value) && value.length ? value.map(item => String(item)).join("；") : fallback;
    const url = safeSourceUrl(provenance?.url), name = text(provenance?.name,url ? "查看来源资料" : "来源名称未提供");
    const extras = [provenance?.version ? `版本 ${text(provenance.version,"未提供")}` : "",provenance?.license ? `许可 ${text(provenance.license,"未提供")}` : ""].filter(Boolean);
    container.innerHTML = `<h3>${title}</h3>${historical ? `<p class="small muted">运行：${escape(state.job?.label || state.job?.id || "")}</p>` : ""}<dl><div><dt>来源</dt><dd>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(name)} ↗</a>` : escape(name)}${extras.length ? `<span class="source-meta">${escape(extras.join(" · "))}</span>` : ""}</dd></div><div><dt>典型用途</dt><dd>${escape(text(usage?.typical_use,"未提供"))}</dd></div><div><dt>已有标注</dt><dd>${escape(text(usage?.annotations,"未提供标注说明"))}</dd></div><div class="annotation-limit"><dt>标注边界</dt><dd>${escape(text(usage?.annotation_limits,"标注适用边界未说明，不推断为质量真值"))}</dd></div></dl>`;
  }

  function resetInputContext(input) {
    state.draftConfig = clone(input.default_config || {});
    const defaults = input.default_config?.context_tags || {};
    const sourceTask = arr(input.data_tags).find(tag => tag.key === "task" && tag.status === "known");
    state.contextTags = {disease:defaults.disease ?? "unknown",age_group:defaults.age_group ?? "unknown",task:defaults.task ?? sourceTask?.value ?? "unknown"};
    state.initialContext = {...state.contextTags};
    state.selected = new Set(OPTIONAL); state.extensions = new Set(arr(state.draftConfig.method_config?.extensions));
    state.scope = state.draftConfig.scope === "recording" ? "recording" : "window"; state.parentJobId = null;
    $("extension-selection-note").hidden = true;
    $("extension-selection-note").textContent = "";
  }

  function renderContextEditors() {
    for (const field of Object.keys(CONTEXT_FIELDS)) {
      const choices = arr(state.catalog?.context_tag_options?.[field]);
      const options = choices.some(option => option.value === "unknown") ? choices.slice() : [{value:"unknown",label:"未知"},...choices];
      const value = state.contextTags[field] ?? "unknown";
      if (!options.some(option => option.value === value)) {
        const source = arr(state.input?.data_tags).find(tag => tag.key === field && tag.value === value);
        options.push({value,label:source?.display || source?.value || value});
      }
      const select = $(`context-${field}`);
      select.innerHTML = options.map(option => `<option value="${escape(option.value)}">${escape(option.label)}</option>`).join("");
      select.value = value; select.disabled = !state.input || !choices.length;
    }
  }

  function contextLabel(field, value) {
    return arr(state.catalog?.context_tag_options?.[field]).find(option => option.value === value)?.label || (value === "unknown" ? "未知" : value);
  }

  function draftDataTags() {
    const tags = arr(state.input?.data_tags).map(tag => ({...tag}));
    for (const [field,label] of Object.entries(CONTEXT_FIELDS)) {
      const value = state.contextTags[field] ?? "unknown", existing = tags.find(tag => tag.key === field);
      const changed = value !== state.initialContext[field];
      if (existing && !changed) continue;
      const tag = {key:field,label,value,display:contextLabel(field,value),kind:"context",status:value === "unknown" ? "unknown" : "known",source:changed ? "人工补充（草稿，待规划）" : "未提供背景信息"};
      if (existing) Object.assign(existing,tag); else tags.push(tag);
    }
    return tags;
  }

  function renderDataTags() {
    const plan = activePlan(), planned = Array.isArray(plan?.data_tags);
    const tags = planned ? plan.data_tags : state.mode === "job" ? [] : draftDataTags();
    $("data-tags-title").textContent = state.mode === "job" ? "所查看运行的数据标签" : "数据标签";
    $("data-tags-source").textContent = planned ? "计划已记录" : state.mode === "job" ? "历史计划" : "来源 / 草稿";
    $("input-data-tags").innerHTML = tags.length ? tags.map(tag => {
      const unknown = tag.status === "unknown" || tag.value == null || tag.value === "unknown";
      const display = unknown ? (tag.display && tag.display !== "未知" ? `未知 · ${tag.display}` : "未知") : tag.display ?? (typeof tag.value === "object" ? pretty(tag.value) : String(tag.value));
      const title = [`来源：${pretty(tag.source || "未提供")}`,tag.note].filter(Boolean).join("；");
      return `<span class="data-tag ${tag.kind === "context" ? "context" : "technical"} ${unknown ? "unknown" : ""}" title="${escape(title)}"><span class="tag-key">${escape(tag.label || tag.key)}</span><span>${escape(display)}</span></span>`;
    }).join("") : '<p class="small muted">该记录或历史计划没有保存数据标签。</p>';
    $("data-tags-note").textContent = state.mode === "job" ? `标签属于运行“${state.job?.label || state.job?.id || ""}”。下方背景选项仍用于新分析。` : planned ? "标签来自当前计划；未知信息会明确保留。悬停标签可查看来源。" : "技术标签只读；背景可在下方补充。未知信息不自动推断。悬停标签可查看来源。";
  }

  function methodApplicability(method, plan = activePlan()) {
    const saved = arr(plan?.method_applicability).find(item => item.id === method.id && (!item.module_id || item.module_id === method.module_id));
    if (saved) return saved;
    if (method.implementation !== "available") return {status:"planned",reason:"当前目录中的方法尚未接入，不能在此版本运行。",selected:false};
    return {status:"unplanned",reason:plan ? "此计划未保存该方法的适用性，请重新规划核对。" : "请先预览执行计划，由服务端核对当前数据与方法条件。",selected:false};
  }

  function renderExtensions() {
    const methods = extensionMethods(), container = $("extension-options");
    container.hidden = !methods.length;
    if (!methods.length) { container.innerHTML = ""; return; }
    container.innerHTML = '<h3>可选开源扩展</h3><p class="muted">默认关闭。选择扩展会同时选中所属模块；实际适用性以执行计划为准。</p>' + methods.map(method => {
      const applicability = methodApplicability(method,state.mode === "draft" ? activePlan() : null);
      return `<div class="extension-option"><label class="extension-check" for="extension-${escape(method.id)}"><input id="extension-${escape(method.id)}" type="checkbox" data-extension="${escape(method.id)}" ${state.extensions.has(method.id) ? "checked" : ""}><span>${escape(method.name)}</span></label><p>${escape(method.module_id)} · ${escape(method.description)}</p><div class="extension-info">${statusTag(applicability.status)}<button data-detail="${escape(method.module_id)}">条件与来源 ↗</button></div></div>`;
    }).join("");
  }

  function setExtension(id, checked) {
    const method = extensionMethods().find(item => item.id === id);
    if (!method || !state.input || state.submitting) return;
    if (checked) { state.extensions.add(id); state.selected.add(method.module_id); }
    else state.extensions.delete(id);
    $("extension-selection-note").hidden = false;
    $("extension-selection-note").textContent = checked ? `已选择 ${method.name}，同时选中 ${method.module_id}。依赖和条件将在规划时核对。` : `已关闭 ${method.name}；所属模块的其他方法仍按模块选择执行。`;
    renderModuleOptions(); invalidatePlan();
  }

  function setModuleSelected(id, checked) {
    if (state.submitting) return;
    if (checked) state.selected.add(id);
    else {
      state.selected.delete(id);
      const removed = extensionMethods().filter(method => method.module_id === id && state.extensions.has(method.id));
      removed.forEach(method => state.extensions.delete(method.id));
      if (removed.length) { $("extension-selection-note").hidden = false; $("extension-selection-note").textContent = `取消 ${id} 时，已同时关闭其可选扩展：${removed.map(method => method.name).join("、")}。`; }
    }
    invalidatePlan();
  }

  function setContext(field, value) {
    if (!Object.hasOwn(CONTEXT_FIELDS,field) || state.submitting) return;
    state.contextTags[field] = value; invalidatePlan();
  }

  function updateActions() {
    const invalid = validation(), busy = state.planning || state.submitting || state.recommending || state.intakeBusy;
    $("plan-button").disabled = Boolean(invalid || busy || !state.catalog || unsupportedInput());
    $("run-button").disabled = Boolean(invalid || busy || unsupportedInput() || state.filePending || (!validPlan() && !state.manualDraft) || state.mode !== "draft");
    $("plan-button").innerHTML = state.planning ? '<span class="spinner" aria-hidden="true"></span> 正在核对…' : "核对手动方案";
    $("run-button").innerHTML = state.submitting ? '<span class="spinner" aria-hidden="true"></span> 正在准备检查…' : '<span aria-hidden="true">▶</span> 开始检查';
    $("recommend-button").disabled = Boolean(invalid || busy || !state.catalog);
    $("recommend-button").innerHTML = state.recommending ? '<span class="spinner" aria-hidden="true"></span> 正在准备推荐…' : "恢复推荐方案";
    $("apply-recommendation-button").disabled = Boolean(busy || unsupportedInput() || !recommendationValid() || state.recommendation?.can_apply !== true || state.recommendationApplied);
    $("apply-recommendation-button").textContent = state.recommendationApplied ? "已采用推荐" : "采用推荐";
    $("apply-parameters-button").disabled = !state.input || busy;
    $("input-select").disabled = state.submitting || state.intakeBusy || !arr(state.catalog?.inputs).length;
    for (const id of ["start-seconds","duration-seconds","extension-parameters"]) $(id).disabled = state.submitting || !state.input;
    for (const field of Object.keys(CONTEXT_FIELDS)) $(`context-${field}`).disabled = state.submitting || !state.input;
    $("intake-upload-button").disabled = !$("intake-file").files?.length || state.intakeBusy || !state.catalog || state.submitting;
    $("intake-file").disabled = state.submitting;
    $("intake-restore-button").disabled = state.intakeBusy || state.submitting;
    $("revise-input-button").disabled = !state.input || busy || state.mode !== "draft";
    $("preview-input-button").disabled = !state.input || busy;
    $("scope-window").checked = state.scope === "window"; $("scope-recording").checked = state.scope === "recording";
    for (const id of ["scope-window","scope-recording"]) $(id).disabled = !state.input || busy || state.mode !== "draft";
    if (state.scope === "recording") { $("start-seconds").disabled = true; $("duration-seconds").disabled = true; }
    $("scope-description").textContent = state.scope === "recording" ? "整份检查按有界窗口逐段执行；数据间隙与未完成部分单独报告。" : "快速预检仅检查所选时段，不代表整份记录。";
    renderVisibility();
    renderExtraction();
    renderPipeline();
    $("action-hint").textContent = invalid || (state.submitting ? "正在核对并提交这份方案，请勿重复操作。" : state.recommending ? "正在根据这份数据准备推荐方案，不会自动运行。" : state.planning ? "正在核对最新方案的适用条件。" : state.mode === "job" ? "正在查看已有运行。选择一份数据可准备新的检查。" : validPlan() ? `${state.manualDraft ? "手动" : "推荐"}方案已就绪，点击开始检查。` : state.manualDraft ? "手动修改已保留。点击开始检查后会先核对最新方案。" : "方案尚未就绪，可点击恢复推荐方案重试。");
    if (state.mode === "draft" && unsupportedInput()) $("action-hint").textContent = "当前模态仅保存提取信息，不运行头皮 EEG 质控。";
  }

  function updateWindow() {
    const error = validation();
    setError("config-error", state.input ? error : null);
    const config = currentConfig();
    $("window-preview").textContent = config && !error ? `原始时间轴 ${number(config.selection.start_seconds,3)}–${number(config.selection.start_seconds + config.selection.duration_seconds,3)} 秒 · 共 ${number(config.selection.duration_seconds,3)} 秒` : "时段按原始记录的时间轴计算。";
    const json = $("effective-config");
    if (json) json.textContent = pretty(config);
    updateActions();
  }

  function clearJobView() {
    clearPoll(); ++state.jobRequest; ++state.resultRequest;
    state.job = null; state.result = null; state.resultJobId = null;
    resetReviewWorkspace();
    renderJob(); renderResult(); renderHistory();
  }

  function invalidatePlan({keepRecommendation = false,manual = true,cancelPending = true} = {}) {
    if (state.submitting) return;
    if (cancelPending) cancelDraftRequests();
    if (state.mode === "job") clearJobView();
    state.plan = null; state.planKey = null; state.mode = "draft"; state.manualDraft = manual;
    if (!keepRecommendation) {
      state.recommendationStale = state.recommendationStale || Boolean(state.recommendation);
      state.recommendation = null; state.recommendationKey = null; state.recommendationApplied = false;
      setError("recommendation-error",null);
    }
    setError("plan-error",null);
    updateWindow(); renderPipeline(); renderPlan(); renderRecommendation(); refreshOpenDialog();
    if (manual) saveDraft();
  }

  function channelChip(index, role = "") {
    const channel = arr(state.input?.metadata?.channels).find(c => c.index === index);
    return `<span class="channel-chip ${role}"><span>#${escape(index)}</span>${escape(channel?.name ?? "索引未匹配")}</span>`;
  }
  function channelList(indices, role) { return arr(indices).length ? `<div class="chip-list">${indices.map(i => channelChip(i,role)).join("")}</div>` : '<p class="muted">配置未提供 / 未配置</p>'; }

  function renderChannelConfig() {
    const config = currentConfig() || {}, selection = config.selection || {}, groups = config.method_config?.comparison_groups;
    const eegIndices = arr(selection.eeg_indices), auxiliary = selection.reference_indices || {};
    $("channel-count").textContent = `${eegIndices.length} 个 EEG`;
    const auxiliaryEntries = Object.entries(auxiliary).filter(([, index]) => Number.isInteger(index));
    const auxiliaryHtml = auxiliaryEntries.length ? auxiliaryEntries.map(([role,index]) => `<div class="config-section"><h4>${escape(role.toUpperCase())} 辅助导联</h4>${channelList([index],"reference")}</div>`).join("") : '<div class="config-section"><h4>辅助导联</h4><p class="muted">当前配置未指定 ECG / EOG / EMG 辅助导联，不按名称推测。</p></div>';
    let groupHtml = '<p class="muted">配置未提供比较组，不自动生成。</p>';
    if (Array.isArray(groups) && groups.length === eegIndices.length && groups.every(group => typeof group === "string")) {
      const grouped = new Map();
      groups.forEach((group,index) => { if (!grouped.has(group)) grouped.set(group,[]); grouped.get(group).push(eegIndices[index]); });
      groupHtml = [...grouped.entries()].map(([group,indices]) => `<div class="config-section"><h4>${escape(group)} · ${indices.length} 道</h4>${channelList(indices)}</div>`).join("");
    } else if (groups != null) groupHtml = `<pre class="config-json">${escape(pretty(groups))}</pre>`;
    const used = new Set([...eegIndices,...auxiliaryEntries.map(([,index]) => index)]);
    const unused = arr(state.input.metadata?.channels).filter(channel => !used.has(channel.index)).map(channel => channel.index);
    $("channel-config").innerHTML = `<p class="muted small">角色来自当前配置，# 为原始通道索引（从 0 开始）。同名通道按索引区分。</p><div class="config-section"><h4>分析 EEG</h4>${channelList(eegIndices)}</div>${auxiliaryHtml}<div class="config-section"><h4>参考比较组（按 EEG 索引顺序配置）</h4>${groupHtml}</div>${unused.length ? `<details class="config-section"><summary>其余原始信号 · ${unused.length} 道</summary><p class="muted small">未被当前配置指定为分析 EEG 或辅助导联。</p>${channelList(unused)}</details>` : ""}<details><summary>查看完整生效配置</summary><pre id="effective-config" class="config-json">${escape(pretty(currentConfig()))}</pre></details>`;
  }

  function selectInput(id, {autoPrepare = true,fromIntake = false} = {}) {
    if (state.submitting || (state.intakeBusy && !fromIntake)) { $("input-select").value = state.input?.id || ""; return Promise.resolve(false); }
    const next = arr(state.catalog?.inputs).find(input => input.id === id);
    if (!next) { clearInputDraft(); return Promise.resolve(false); }
    if (!fromIntake) { ++state.intakeRequest; state.intake = null; pendingIntakeId(null); $("intake-file").value = ""; renderIntake(); }
    state.filePending = false; state.input = next;
    state.revisionInput = null; setJobLocation(null);
    $("input-select").value = state.input.id; clearJobView();
    const input = state.input, meta = input.metadata || {}, selection = input.default_config?.selection || {};
    resetInputContext(input); renderContextEditors();
    $("selected-file-name").textContent = input.label || input.id;
    $("input-description").textContent = input.description || "该记录未提供说明。";
    const rates = [...new Set(arr(meta.channels).map(channel => channel.sampling_rate_hz).filter(numeric))];
    $("input-facts").innerHTML = [meta.format || "EDF",size(meta.size_bytes),`${arr(meta.channels).length} 道`,rates.length ? `${rates.map(rate => number(rate)).join(" / ")} Hz` : "采样率未知"].map(fact => `<span class="fact">${escape(fact)}</span>`).join("");
    const profile = arr(state.catalog.profiles).find(p => p.id === input.profile_id);
    $("profile-info").hidden = false;
    $("profile-info").innerHTML = `<strong>${escape(profile?.name || input.profile_id || "未指定分析配置")}</strong>${escape(profile?.description || "适用性由预览计划进一步核对。")}`;
    $("start-seconds").value = selection.start_seconds ?? "";
    $("duration-seconds").value = selection.duration_seconds ?? "";
    $("start-seconds").disabled = false; $("duration-seconds").disabled = false;
    if (numeric(meta.duration_seconds)) $("start-seconds").max = meta.duration_seconds;
    else $("start-seconds").removeAttribute("max");
    renderChannelConfig(); renderModuleOptions(); syncParameterEditor(); renderExamplePresets();
    invalidatePlan({manual:false});
    return autoPrepare ? makeRecommendation({autoApply:true}) : Promise.resolve(false);
  }

  function renderExamplePresets() {
    // Registered records are a secondary dropdown, never the first step.
    $("example-presets").innerHTML = ""; $("example-presets").hidden = true;
  }

  function renderVisibility() {
    const historical = state.mode === "job", selected = Boolean(state.input) && !state.filePending;
    $("analysis-workspace").hidden = !historical && !selected;
    $("input-metadata").hidden = historical || !selected;
    $("run-history-panel").hidden = !historical && !state.history.length;
    if (historical) $("run-history-panel").open = true;
    $("example-presets").hidden = true;
    $("intake-confirmation").hidden = historical || !state.intake || state.intake.status === "registered";
  }

  function clearInputDraft() {
    setJobLocation(null);
    cancelDraftRequests(); state.mode = "draft"; state.input = null; state.draftConfig = null;
    state.plan = null; state.planKey = null; state.manualDraft = false; state.parameterDirty = false;
    state.recommendation = null; state.recommendationKey = null; state.recommendationApplied = false; state.recommendationStale = false;
    state.selected = new Set(OPTIONAL); state.extensions = new Set();
    state.contextTags = {disease:"unknown",age_group:"unknown",task:"unknown"};
    state.scope = "window"; state.parentJobId = null; state.revisionInput = null;
    $("input-select").value = ""; $("start-seconds").value = ""; $("duration-seconds").value = "";
    $("extension-parameters").value = "{}"; $("selected-file-name").textContent = "";
    $("input-facts").innerHTML = ""; $("channel-config").innerHTML = "";
    $("advanced-settings").open = false; $("run-history-panel").open = false;
    if ($("module-dialog").open) $("module-dialog").close(); state.dialogModule = null;
    for (const id of ["plan-error","recommendation-error","config-error","parameter-error"]) setError(id,null);
    clearJobView(); updateActions(); renderRecommendation();
  }

  function chooseLocalFile() {
    if (state.submitting) return;
    if (state.uploadAbort) state.uploadAbort();
    ++state.intakeRequest; state.intakeBusy = false; state.intake = null; pendingIntakeId(null);
    const file = $("intake-file").files?.[0]; state.filePending = Boolean(file);
    clearInputDraft(); renderIntake(); setError("intake-error",null);
    $("registered-records").open = false;
    $("intake-status").textContent = file ? `${file.name} · ${size(file.size)}` : "";
  }

  function pendingIntakeId(value) {
    try {
      if (value === null) window.sessionStorage.removeItem("eeg-qc-pending-intake");
      else if (typeof value === "string") window.sessionStorage.setItem("eeg-qc-pending-intake",value);
      return window.sessionStorage.getItem("eeg-qc-pending-intake");
    } catch { return null; }
  }

  function intakeRole(index, suggestions) {
    const auxiliary = Object.entries(suggestions?.reference_indices || {}).find(([,value]) => value === index);
    return auxiliary?.[0] || (arr(suggestions?.eeg_indices).includes(index) ? "eeg" : "unused");
  }

  function selectOptions(options, selected) { return options.map(([value,label]) => `<option value="${escape(value)}" ${value === selected ? "selected" : ""}>${escape(label)}</option>`).join(""); }

  function annotationText(meta) {
    const info = meta?.annotations;
    if (!info || info.count == null) return "尚未解析";
    return info.count > 0 ? `${number(info.count,0)} 条记录` : "未检出标注";
  }

  function renderExtraction() {
    const history = state.mode === "job";
    const frozenModality = state.job?.plan?.input_modality;
    const source = history ? (state.job?.plan?.input_metadata ? {metadata:state.job.plan.input_metadata,label:state.job.label,modality:typeof frozenModality === 'string' ? frozenModality : frozenModality?.value} : null) : state.filePending ? state.intake : state.input || state.intake;
    const box = $("record-summary"), meta = source?.metadata;
    box.hidden = !meta;
    const key = history ? `job:${state.job?.id || "loading"}` : state.input && !state.filePending ? `input:${state.input.id}` : state.intake ? `intake:${state.intake.id}` : "empty";
    if (key !== state.boardKey) { $("workflow-panel").open = !meta || history || Boolean(state.input && !state.filePending); state.boardKey = key; }
    if (!meta) { box.innerHTML = ""; return; }
    const rates = [...new Set(arr(meta.channels).map(c => c.sampling_rate_hz).filter(numeric))];
    const modality = typeof source.modality === "string" ? source.modality : "unknown";
    const facts = [["数据格式",meta.format || "未知"],["通道数",number(arr(meta.channels).length,0)],["记录时长",`${number(meta.duration_seconds,2)} s`],["采样率",rates.length <= 3 ? rates.map(rate => number(rate,2)).join(" / ") + " Hz" : "多个原生采样率"],["分析模态",MODALITY_LABELS[modality] || modality],["标注",annotationText(meta)]];
    const kinds = arr(meta.annotations?.kinds), evidence = meta.modality_evidence;
    const markup = `<div class="extraction-heading"><span class="tag subtle">自动提取</span><span class="small muted" data-i18n-skip>${escape(meta.reader_id || "")}</span></div><h3 class="extraction-filename" data-i18n-skip>${escape(source.filename || source.label || "已读取文件")}</h3><dl class="extraction-grid">${facts.map(([label,value]) => `<div><dt>${label}</dt><dd>${escape(value)}</dd></div>`).join("")}</dl>${kinds.length ? `<details class="extraction-details"><summary>文件标注</summary><p class="small muted">保留原始标签，尚未确认其含义。</p><div class="annotation-labels" data-i18n-skip>${kinds.slice(0,12).map(label=>`<span>${escape(label)}</span>`).join("")}</div></details>` : ""}${evidence ? `<details class="extraction-details"><summary>模态与通道类型依据</summary><p class="small muted">文件类型和通道声明不等于采集位置，分析模态需确认。</p><pre data-i18n-skip>${escape(pretty(evidence))}</pre></details>` : ""}`;
    if (box.innerHTML !== markup) box.innerHTML = markup;
  }

  function renderIntake() {
    const intake = state.intake, container = $("intake-confirmation");
    $("intake-restore-button").hidden = !pendingIntakeId();
    container.hidden = state.mode === "job" || !intake || intake.status === "registered";
    if (container.hidden) { container.innerHTML = ""; renderExtraction(); return; }
    const meta = intake.metadata || {}, suggestions = intake.suggestions || {}, channels = arr(meta.channels);
    const roles = [["unused","不使用"],["eeg","分析信号"],["eog","EOG 辅助"],["ecg","ECG 辅助"],["emg","EMG 辅助"]];
    const references = [["unknown","未知"],["common_reference","共同参考"],["linked_ears","联耳参考"],["bipolar","双极导联"],["mixed","混合参考"]];
    const proposed = channels.filter(channel => intakeRole(channel.index,suggestions) !== "unused"), rates = [...new Set(proposed.map(channel => channel.sampling_rate_hz))];
    const count = channels.filter(channel => intakeRole(channel.index,suggestions) === "eeg").length;
    const correction = !count || rates.length !== 1;
    const fields = Object.entries(CONTEXT_FIELDS).map(([field,label])=>`<label class="metadata-field"><span>${label}</span><select id="intake-context-${field}">${selectOptions(arr(state.catalog?.context_tag_options?.[field]).map(option=>[option.value,option.label]),suggestions.context_tags?.[field] || "unknown")}</select></label>`).join("");
    container.innerHTML = `<div class="confirmation-heading"><h3>补充信息</h3><span class="small muted">背景可留未知</span></div><div class="metadata-fields"><label class="metadata-field"><span>分析模态 <b>*</b></span><select id="intake-modality">${selectOptions(Object.entries(MODALITY_LABELS),"unknown")}</select></label>${fields}</div><p class="small muted context-note">疾病标签用于背景与复核，不自动改变质量阈值。</p><details class="intake-context" ${correction ? "open" : ""}><summary>核对通道 · 建议 ${count} 道分析信号</summary><p class="small muted">以下角色为待确认建议。分析与辅助信号须共享采样率。</p>${correction ? '<div class="notice warning">请核对通道角色与原生采样率。</div>' : ""}<div class="intake-channel-table"><table><thead><tr><th>原始信号</th><th>技术字段</th><th>建议角色</th></tr></thead><tbody>${channels.map(channel=>`<tr><td data-i18n-skip><strong>#${escape(channel.index)} ${escape(channel.name)}</strong></td><td data-i18n-skip>${number(channel.sampling_rate_hz)} Hz<br>${escape(channel.unit || "?")}</td><td><select data-intake-channel="${escape(channel.index)}" aria-label="确认通道角色">${selectOptions(roles,intakeRole(channel.index,suggestions))}</select></td></tr>`).join("")}</tbody></table></div></details><details class="intake-context"><summary>参考与来源（可选）</summary><label class="field-label" for="intake-reference">参考构型</label><select id="intake-reference">${selectOptions(references,suggestions.reference_scheme || "unknown")}</select><label class="field-label" for="intake-label">记录名称</label><input id="intake-label" type="text" value="${escape(intake.filename || "")}" maxlength="160"><label class="field-label" for="intake-source-note">来源与背景补充</label><textarea id="intake-source-note" rows="3" maxlength="2000" placeholder="已知实验或来源，可留空"></textarea></details><label class="intake-consent"><input id="intake-confirmed" type="checkbox"><span>已核对分析模态和通道角色。</span></label><p id="intake-modality-note" class="small muted"></p><button id="intake-confirm-button" class="button primary">确认并推荐</button><details class="result-summary"><summary>读取详情</summary><p class="small muted">确认不会启动检查。</p>${arr(intake.warnings).length?`<ul>${intake.warnings.map(item=>`<li>${escape(pretty(item))}</li>`).join("")}</ul>`:""}<pre data-i18n-skip>${escape(pretty(intake))}</pre></details>`;
    renderRevisionFields(); renderExtraction();
  }

  function intakeConfirmation(roles, fields) {
    if (!state.intake?.id) throw new Error("请先读取本机文件。");
    if (!Object.hasOwn(MODALITY_LABELS,fields.modality) || fields.modality === "unknown") throw new Error("请根据采集资料确认分析模态。");
    if (!fields.confirmed) throw new Error("请先核对并勾选字段确认。");
    const eeg = [], auxiliary = {};
    for (const {index,role} of roles) {
      if (role === "eeg") eeg.push(index);
      else if (["ecg","eog","emg"].includes(role)) {
        if (Object.hasOwn(auxiliary,role)) throw new Error(`当前每种辅助角色只接入一条导联；请为 ${role.toUpperCase()} 选择一条，其余设为不使用。`);
        auxiliary[role] = index;
      }
    }
    if (!eeg.length) throw new Error("请至少选择一条分析信号。");
    const channels = arr(state.intake.metadata?.channels), indices = [...eeg,...Object.values(auxiliary)];
    const selected = indices.map(index => channels.find(channel => channel.index === index));
    if (selected.some(channel => !channel)) throw new Error("所选索引与读取结果不匹配，请重新核对。");
    const rates = new Set(selected.map(channel => channel.sampling_rate_hz));
    if (rates.size !== 1) throw new Error("当前 EEG 和辅助导联必须处于相同原生采样率；请取消不同采样率的信号，不会自动重采样。");
    return {modality:fields.modality,reference_scheme:fields.reference_scheme,eeg_indices:eeg,reference_indices:auxiliary,context_tags:fields.context_tags,label:fields.label,source_note:fields.source_note,confirmed:true};
  }

  function beginInputRevision() {
    const input = state.input; if (!input || state.submitting || state.intakeBusy || state.mode !== "draft") return;
    cancelDraftRequests(); state.revisionInput=input; state.filePending=true;
    state.intake={id:input.id,status:"revision",filename:input.label || input.id,metadata:input.metadata,suggestions:{...(input.default_config?.selection || {}),reference_scheme:input.reference_scheme || "unknown",context_tags:state.contextTags}};
    renderIntake(); updateActions(); $("pipeline-section").scrollIntoView({block:"start"});
  }
  function cancelInputRevision() {
    if (!state.revisionInput || state.intakeBusy) return; state.revisionInput=null; state.intake=null; state.filePending=false; renderIntake(); updateActions();
  }
  function renderRevisionFields() {
    const input=state.revisionInput; if (!input) return;
    const preprocessing=input.preprocessing || {}, mapping=input.annotation_mapping;
    $("intake-modality").value=input.modality || "unknown";
    $("intake-source-note").value=input.description || "";
    $("intake-confirmation").innerHTML += `<details class="intake-context"><summary>预处理与标注映射</summary><p class="small muted">只填写有来源证据的信息；未知值留空。保存为新版本，不改写历史运行。</p><label class="intake-consent"><input id="revision-verified" type="checkbox" ${preprocessing.verified === true ? "checked" : ""}> 已核实滤波声明</label><div class="metadata-fields"><label class="metadata-field"><span>高通（Hz）</span><input id="revision-highpass" type="number" min="0" step="any" value="${numeric(preprocessing.highpass_hz)?preprocessing.highpass_hz:""}"></label><label class="metadata-field"><span>低通（Hz）</span><input id="revision-lowpass" type="number" min="0" step="any" value="${numeric(preprocessing.lowpass_hz)?preprocessing.lowpass_hz:""}"></label></div><label class="field-label" for="revision-processing-note">处理史与证据</label><textarea id="revision-processing-note" rows="2" data-i18n-skip>${escape(preprocessing.note || "")}</textarea><label class="field-label" for="revision-annotation">标注映射 JSON（可留空）</label><p class="small muted">kind 为 task、sleep_stage 或 clinical_event；labels 将原标签映射到确认含义，confirmed 必须为 true。标签不是质量真值。</p><textarea id="revision-annotation" rows="4" spellcheck="false" data-i18n-skip>${mapping?escape(pretty(mapping)):""}</textarea></details><button id="cancel-revision-button" class="button ghost small-button">取消更正</button>`;
    // Replacing markup above rebuilds the form; restore the explicit source values.
    $("intake-modality").value=input.modality || "unknown";
    $("intake-source-note").value=input.description || "";
    $("intake-confirm-button").textContent="保存新版本并推荐";
  }

  function revisionMetadataChanges(input, fields) {
    // Omission preserves source declarations and externally registered annotations.
    // Only an explicit edit may replace these independent metadata fields.
    const changes = {}, original = input.preprocessing || {};
    const frequency = text => { text=String(text || "").trim(); if(!text)return null; const value=Number(text); if(!Number.isFinite(value)||value<0)throw new Error("滤波频率必须是非负数或留空。"); return value; };
    const preprocessing = {verified:fields.verified === true,highpass_hz:frequency(fields.highpass),lowpass_hz:frequency(fields.lowpass),note:String(fields.note || "").trim()};
    const initial = {verified:original.verified === true,highpass_hz:numeric(original.highpass_hz)?original.highpass_hz:null,lowpass_hz:numeric(original.lowpass_hz)?original.lowpass_hz:null,note:String(original.note || "").trim()};
    if(JSON.stringify(preprocessing)!==JSON.stringify(initial))changes.preprocessing=preprocessing;
    const mapping = String(fields.annotation || "").trim(), initialMapping = input.annotation_mapping ? pretty(input.annotation_mapping).trim() : "";
    if(mapping!==initialMapping) { try { const value=mapping?JSON.parse(mapping):null; if(value!==null || initialMapping)changes.annotation_mapping=value; } catch { throw new Error("标注映射必须是合法 JSON，或留空。"); } }
    return changes;
  }

  async function uploadIntake() {
    const file = $("intake-file").files?.[0];
    if (!file || state.intakeBusy || state.submitting) return;
    chooseLocalFile(); const request = state.intakeRequest;
    if (!file.size || file.size > 512 * 1024 * 1024) { setError("intake-error","请选择非空数据文件或 ZIP，最大 512 MiB。"); return; }
    state.intakeBusy = true; $("intake-status").textContent = "正在读取…"; updateActions();
    try {
      const intake = await receiveFile(file,request);
      if (request !== state.intakeRequest) return;
      if (!intake.id || !intake.metadata || !Array.isArray(intake.metadata.channels)) throw new Error("读取结果不完整，请重试。");
      state.intake = intake; pendingIntakeId(intake.id); renderIntake();
      $("intake-status").textContent = "读取完成";
    } catch(error) { if (request === state.intakeRequest) { setError("intake-error",error.message); $("intake-status").textContent = "读取未完成"; } }
    finally { if (request === state.intakeRequest) { state.intakeBusy = false; state.uploadAbort=null; $("cancel-read-button").hidden=true; updateActions(); } }
  }

  function receiveFile(file,request) {
    if (typeof XMLHttpRequest !== "function") return api("/intakes",{method:"POST",body:file,binary:true,timeoutMs:120000,headers:{"X-Filename":encodeURIComponent(file.name)}});
    return new Promise((resolve,reject)=>{
      const xhr=new XMLHttpRequest(); xhr.open("POST",`${API}/intakes`); xhr.timeout=120000;
      xhr.setRequestHeader("Content-Type","application/octet-stream"); xhr.setRequestHeader("Accept","application/json"); xhr.setRequestHeader("X-Filename",encodeURIComponent(file.name));
      state.uploadAbort=()=>xhr.abort(); $("cancel-read-button").hidden=false;
      xhr.upload.onprogress=event=>{if(request===state.intakeRequest)$("intake-status").textContent=event.lengthComputable?`正在传输 ${Math.round(event.loaded/event.total*100)}%` : "正在传输文件…";};
      xhr.upload.onload=()=>{if(request===state.intakeRequest)$("intake-status").textContent="传输完成，正在解包和读取结构…";};
      xhr.onload=()=>{try{const data=JSON.parse(xhr.responseText);if(xhr.status<200||xhr.status>=300)throw new Error(data.error||`请求失败（HTTP ${xhr.status}）`);setConnection(true);resolve(data);}catch(error){reject(error);}};
      xhr.onerror=()=>reject(new Error("读取连接中断。可通过“恢复已读取文件”查询已接收记录。"));
      xhr.ontimeout=()=>reject(new Error("读取超时。可通过“恢复已读取文件”查询结果；请勿立即重复上传。"));
      xhr.onabort=()=>reject(new Error("已取消等待。服务可能保留已接收的本机副本，可查询已读取文件。"));
      xhr.send(file);
    });
  }
  async function listPendingIntakes() {
    const box=$("pending-intakes");box.hidden=false;box.innerHTML='<p class="small muted">正在查询待确认记录…</p>';
    try {const data=await api("/intakes");box.innerHTML=arr(data.intakes).length?arr(data.intakes).map(item=>`<button class="pending-intake" data-restore-intake="${escape(item.id)}"><strong data-i18n-skip>${escape(item.filename || item.id)}</strong><span>${escape(date(item.received_at))} · ${escape(size(item.metadata?.size_bytes))}</span></button>`).join(""):'<p class="small muted">没有待确认记录。</p>';}
    catch(error){box.innerHTML=`<p class="field-error">${escape(error.message)}</p>`;}
  }

  async function restoreIntake(requestedId = null) {
    const id = typeof requestedId === "string" ? requestedId : pendingIntakeId(); if (!id || state.intakeBusy || state.submitting) return;
    pendingIntakeId(id); $("pending-intakes").hidden=true;
    const request = ++state.intakeRequest; state.filePending = true; state.intake = null; clearInputDraft(); renderIntake();
    state.intakeBusy = true; setError("intake-error",null); updateActions();
    try {
      const intake = await api(`/intakes/${encodeURIComponent(id)}`);
      if (request !== state.intakeRequest) return;
      state.intake = intake;
      if (intake.status === "registered" && intake.input_id) {
        pendingIntakeId(null); renderIntake(); const loaded = await loadCatalog(intake.input_id,{intakeRequest:request});
        if (request === state.intakeRequest) $("intake-status").textContent = loaded ? "已恢复文件" : "文件已登记，请重新连接";
      } else { renderIntake(); $("intake-status").textContent = "已恢复读取结果，请确认信息"; }
    }
    catch(error) { if (request === state.intakeRequest) setError("intake-error",error.message); }
    finally { if (request === state.intakeRequest) { state.intakeBusy = false; updateActions(); } }
  }

  async function confirmIntake() {
    if (state.intakeBusy || !state.intake || state.submitting) return;
    let request;
    try {
      const roles = [...$("intake-confirmation").querySelectorAll("[data-intake-channel]")].map(select => ({index:Number(select.dataset.intakeChannel),role:select.value}));
      const context = Object.fromEntries(Object.keys(CONTEXT_FIELDS).map(field => [field,$(`intake-context-${field}`).value || "unknown"]));
      request = intakeConfirmation(roles,{modality:$("intake-modality").value,reference_scheme:$("intake-reference").value,confirmed:$("intake-confirmed").checked,context_tags:context,label:$("intake-label").value.trim(),source_note:$("intake-source-note").value.trim()});
      if (state.revisionInput) {
        request.base_revision = state.revisionInput.record_revision || 1;
        Object.assign(request,revisionMetadataChanges(state.revisionInput,{verified:$("revision-verified").checked,highpass:$("revision-highpass").value,lowpass:$("revision-lowpass").value,note:$("revision-processing-note").value,annotation:$("revision-annotation").value}));
      }
    } catch(error) { setError("intake-error",error.message); return; }
    const intakeRequest = state.intakeRequest, intakeId = state.intake.id;
    state.intakeBusy = true; $("intake-confirm-button").disabled = true; setError("intake-error",null); $("intake-status").textContent = "正在准备…"; updateActions();
    try {
      const response = await api(state.revisionInput ? `/inputs/${encodeURIComponent(state.revisionInput.id)}/revisions` : `/intakes/${encodeURIComponent(intakeId)}/confirm`,{method:"POST",body:JSON.stringify(request)});
      if (intakeRequest !== state.intakeRequest) return;
      if (response.status !== "registered" || !response.input?.id) throw new Error("服务未确认登记成功，请恢复读取状态后核对。");
      state.intake = {...state.intake,status:"registered"}; pendingIntakeId(null); renderIntake();
      const loaded = await loadCatalog(response.input.id,{intakeRequest});
      if (intakeRequest === state.intakeRequest) $("intake-status").textContent = loaded ? validPlan() ? "方案已就绪" : state.recommendation?.status === "unsupported" ? "信息已保存；当前模态暂无质控配置" : "方案未完成，请重试" : "文件已登记，请重新连接";
      if (loaded && intakeRequest === state.intakeRequest && validPlan()) { $("analysis-workspace").scrollIntoView({block:"start"}); $("run-button").focus?.({preventScroll:true}); }
    } catch(error) { if (intakeRequest === state.intakeRequest) { setError("intake-error",error.message); if ($("intake-confirm-button")) $("intake-confirm-button").disabled = false; } }
    finally { if (intakeRequest === state.intakeRequest) { state.intakeBusy = false; updateActions(); } }
  }

  function renderModuleOptions() {
    const modules = arr(state.catalog.modules);
    $("module-options").innerHTML = OPTIONAL.map(id => {
      const module = modules.find(item => item.id === id);
      if (!module) return "";
      return `<div class="module-option"><input type="checkbox" id="option-${id}" data-module="${id}" ${state.selected.has(id) ? "checked" : ""}><label for="option-${id}"><code>${id}</code><span>${escape(module.name)}</span></label><button class="module-help" data-detail="${id}" aria-label="查看 ${escape(module.name)} 的依据">i</button></div>`;
    }).join("") + `<p class="fixed-modules">固定步骤：${FIXED.map(id => `<span>${id} ${escape(modules.find(m => m.id === id)?.name || "")}</span>`).join(" · ")}</p>`;
    $("module-options").querySelectorAll("input").forEach(input => input.addEventListener("change", () => setModuleSelected(input.dataset.module,input.checked)));
  }

  // Keep the service payload unchanged: unselected is a presentation state,
  // distinct from a selected module skipped because its conditions were unmet.
  function displayStatus(module, plan) {
    const selected = plan?.selected_modules;
    const id = module.id || module.module_id;
    return Array.isArray(selected) && !selected.includes(id) ? "unselected" : module.status;
  }

  function planDisplayNodes(plan) {
    return arr(plan?.nodes).map(node => ({...node,source_status:node.status,status:displayStatus(node,plan)}));
  }

  function executionProgress(job) {
    const modules = arr(job.modules);
    const selected = new Set(Array.isArray(job.plan?.selected_modules) ? job.plan.selected_modules : modules.map(module => module.id));
    const finished = modules.filter(module => selected.has(module.id) && FINISHED_MODULES.has(module.status)).length;
    return {finished,total:selected.size,percent:selected.size ? Math.round(finished / selected.size * 100) : 0,unselected:modules.filter(module => !selected.has(module.id)).length};
  }

  function visualNodes() {
    if (state.mode === "job" && !state.job) return arr(state.catalog?.modules).map(module => ({...module,status:"pending"}));
    if (state.mode === "job" && state.job) {
      const jobModules = arr(state.job.modules);
      return arr(state.catalog?.modules).map(module => {
        const result = jobModules.find(m => m.id === module.id);
        const planned = arr(state.job.plan?.nodes).find(m => m.id === module.id);
        const node = {...module,...planned,...result,status:result?.status || (planned ? (planned.status === "skipped" ? "skipped" : "pending") : "unselected")};
        return {...node,source_status:result?.status || planned?.status,status:displayStatus(node,state.job.plan)};
      });
    }
    if (!state.input || state.filePending) return ORDER.map(id => ({...arr(state.catalog?.modules).find(module => module.id === id),id,status:"framework"}));
    if (unsupportedInput() || state.recommendation?.status === "unsupported") return arr(state.catalog?.modules).map(module=>({...module,status:"unplanned"}));
    if (validPlan()) return planDisplayNodes(state.plan);
    return arr(state.catalog?.modules).map(module => ({...module,status:FIXED.includes(module.id) ? "required" : state.selected.has(module.id) ? "selected" : "unselected"}));
  }

  function nodeHtml(id, nodes) {
    const module = arr(state.catalog?.modules).find(item => item.id === id);
    const node = nodes.find(item => item.id === id) || {...module,status:"unselected"};
    const status = node.status || "pending", css = status === "unselected" ? "skipped" : status;
    return `<button class="pipeline-node ${escape(css)}" data-detail="${escape(id)}" ${module ? "" : "disabled"} aria-label="${escape(id)} ${escape(node.name || module?.name || MODULE_LABELS[id])}，${escape(STATUS[status] || status)}，查看详情" title="${escape(node.reason || "查看模块详情")}"><span class="node-top"><span class="node-id">${escape(id)}</span>${status === "framework" ? '<span class="node-link" aria-hidden="true">↗</span>' : `<span class="node-state">${escape(STATUS[status] || status)}</span>`}</span><span class="node-name">${escape(MODULE_LABELS[id])}</span>${id === "M06" ? '<span class="node-dependency">依赖 M03</span>' : ""}</button>`;
  }

  function renderPipeline() {
    const nodes = visualNodes();
    const groups = [["01","读取与识别",["M01","M02"]],["02","质量检查",OPTIONAL],["03","汇总与报告",["M08","M09"]]];
    const markup = groups.map(([number,title,ids],index) => `${index ? '<div class="flow-connector" aria-hidden="true">↓</div>' : ""}<section class="flow-stage"><h3><span>${number}</span>${title}</h3><div class="flow-nodes ${index === 1 ? "flow-checks" : "flow-pair"}">${ids.map(id => nodeHtml(id,nodes)).join("")}</div></section>`).join("");
    if ($("pipeline").innerHTML !== markup) {
      const focusedId = document.activeElement?.closest?.("#pipeline [data-detail]")?.getAttribute("data-detail");
      $("pipeline").innerHTML = markup;
      if (ORDER.includes(focusedId)) $("pipeline").querySelector(`[data-detail="${focusedId}"]`)?.focus({preventScroll:true});
    }
    const historical = state.mode === "job", hasInput = Boolean(state.input) && !state.filePending;
    $("pipeline-title").textContent = historical ? "检查记录" : state.intake || state.input ? "信息提取" : "数据工作台";
    let label = "框架预览", caption = "上传文件后，先提取基本信息。", style = "subtle";
    if (historical) {
      label = state.job ? STATUS[state.job.status] || state.job.status : "状态未载入";
      caption = state.job ? `运行记录 · ${state.job.label || state.job.id}` : "运行状态尚未载入。";
      style = state.job && Object.hasOwn(STATUS,state.job.status) ? state.job.status : "subtle";
    } else if (state.submitting) {
      label = "正在提交"; caption = "等待服务确认，勿重复提交。";
    } else if (!hasInput) {
      if (state.intakeBusy) { label = "读取中"; caption = "读取文件信息后，确认通道。"; }
      else if (state.intake && state.intake.status !== "registered") { label = "待确认"; caption = "确认文件信息后，生成检查方案。"; }
      else if (state.filePending) { label = "待读取"; caption = "点击“读取文件”以继续。"; }
    } else if (unsupportedInput() || state.recommendation?.status === "unsupported") {
      label = "仅信息提取"; caption = "当前模态暂无已验证的质控配置。";
    } else {
      label = state.recommending || state.planning ? "准备方案" : validPlan() ? "方案就绪" : "待核对";
      caption = `${state.input.label || state.input.id} · ${validPlan() ? "点击开始检查" : "按数据配置检查模块"}`;
      style = validPlan() ? "ready" : "subtle";
    }
    for (const id of ["pipeline-state","plan-state"]) { $(id).className = `tag ${style}`; $(id).textContent = label; }
    $("pipeline-caption").textContent = caption;
    $("pipeline-legend").hidden = !historical || !state.job;
    $("pipeline-legend").textContent = "图中颜色表示执行状态，质量结论见报告。";
    $("plan-disclosure").hidden = !(historical ? state.job?.plan : validPlan());
  }

  function renderPlan() {
    renderDataTags(); renderInputUsage(); renderExtensions();
    const plan = state.mode === "job" ? state.job?.plan : state.plan;
    if (!plan) { $("plan-details").innerHTML = '<p class="muted">点击模块查看输入、输出、依赖与证据。预览计划后会显示实际适用性。</p>'; return; }
    const nodes = planDisplayNodes(plan), counts = ["ready","partial","skipped","unselected"].map(status => ({status,count:nodes.filter(node => node.status === status).length}));
    const auto = arr(plan.auto_added_modules);
    $("plan-details").innerHTML = `<div class="plan-summary">${counts.map(({status,count}) => `<span class="tag ${status}">${STATUS[status]} ${count}</span>`).join("")}</div><p class="small muted">${state.mode === "job" ? "本次运行的原始计划" : "当前计划"} · ${escape(plan.plan_id || "")}</p>${auto.length ? `<p class="dependency-summary">已自动补齐依赖：${auto.map(item => escape(typeof item === "string" ? item : pretty(item))).join("、")}。自动补齐的模块会随本次计划执行。</p>` : '<p class="small muted">所选模块的依赖已完整，无需额外补齐。</p>'}${arr(plan.warnings).length ? `<ul>${plan.warnings.map(warning => `<li>${escape(pretty(warning))}</li>`).join("")}</ul>` : ""}${methodPlanHtml(plan)}`;
  }

  function methodPlanHtml(plan) {
    const applicability = arr(plan.method_applicability);
    if (!applicability.length) return '<p class="small muted">此计划没有方法级适用性记录。</p>';
    const methods = allMethods(), blocked = applicability.filter(method => method.status === "blocked" && method.selected);
    const name = item => methods.find(method => method.id === item.id && method.module_id === item.module_id)?.name || item.id;
    return `${blocked.length ? `<div class="notice warning"><strong>当前数据不满足以下已选方法的条件</strong><ul>${blocked.map(item => `<li>${escape(item.module_id)} · ${escape(name(item))}：${escape(item.reason || "服务未提供具体原因")}</li>`).join("")}</ul><p>这些方法不会因所属模块被选中而自动满足条件。</p></div>` : ""}<details class="method-plan-details"><summary>查看 ${applicability.length} 个方法的适用性与参数</summary>${applicability.map(item => `<div class="method-plan-row"><div class="method-plan-row-head"><span>${escape(item.module_id)} · ${escape(name(item))}</span>${statusTag(item.status)}</div><p>${escape(item.reason || "未提供具体原因")}</p>${item.parameters != null ? `<details class="result-summary"><summary>当前参数</summary><pre>${escape(pretty(item.parameters))}</pre></details>` : ""}</div>`).join("")}</details>`;
  }

  async function makePlan({forStart = false} = {}) {
    if (unsupportedInput() || validation() || state.planning || (state.submitting && !forStart)) return false;
    if (state.mode === "job") invalidatePlan();
    const requestBody = body(), key = JSON.stringify(requestBody), epoch = state.draftEpoch, request = ++state.planRequest;
    const current = () => request === state.planRequest && epoch === state.draftEpoch && state.mode === "draft" && fingerprint() === key;
    state.planning = true; state.mode = "draft"; setError("plan-error",null); updateActions();
    try {
      const plan = await api("/plan", {method:"POST",body:JSON.stringify(requestBody)});
      if (!current()) return false;
      if (!plan.plan_id || !Array.isArray(plan.nodes)) throw new Error("计划响应缺少 plan_id 或 nodes，未启用运行。");
      state.plan = plan; state.planKey = key;
      return true;
    } catch(error) { if (current()) { state.plan = null; state.planKey = null; setError("plan-error",error.message); } return false; }
    finally { if (request === state.planRequest && epoch === state.draftEpoch) { state.planning = false; renderPipeline(); renderPlan(); renderRecommendation(); updateActions(); refreshOpenDialog(); } }
  }

  async function startJob() {
    if (unsupportedInput() || validation() || state.filePending || state.intakeBusy || state.submitting || state.recommending || state.planning || state.mode !== "draft" || (!validPlan() && !state.manualDraft)) return;
    if (state.parameterDirty && !applyParameters()) { setError("plan-error","高级参数有误，请展开高级设置修正。"); $("advanced-settings").open = true; return; }
    const epoch = state.draftEpoch, key = fingerprint();
    state.submitting = true; setError("plan-error",null); updateActions(); renderExamplePresets();
    try {
      if (!validPlan() && !await makePlan({forStart:true})) return;
      if (epoch !== state.draftEpoch || key !== fingerprint() || !validPlan() || state.mode !== "draft") return;
      const requestBody = {...body(),plan_id:state.plan.plan_id};
      if (state.parentJobId) requestBody.parent_job_id=state.parentJobId;
      const job = await api("/jobs", {method:"POST",body:JSON.stringify(requestBody)});
      if (!job.id) throw new Error("任务响应缺少 id。请刷新运行记录确认任务状态。");
      await selectJob(job.id,job);
      discardDraft();
      await loadHistory();
      $("runs-section").scrollIntoView({behavior:window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",block:"start"});
    } catch(error) { setError("plan-error",error.message); await loadHistory(); }
    finally { state.submitting = false; updateActions(); renderExamplePresets(); }
  }

  function renderJob() {
    const job = state.job;
    $("job-empty").hidden = Boolean(job); $("job-content").hidden = !job;
    if (!job) { $("job-status").className = "tag subtle"; $("job-status").textContent = "等待开始"; $("recording-progress").hidden=true; updateActions(); return; }
    const tag = $("job-status"); tag.className = `tag ${Object.hasOwn(STATUS,job.status) ? job.status : "subtle"}`; tag.textContent = STATUS[job.status] || job.status;
    $("job-label").textContent = job.label || job.id;
    $("job-created").textContent = date(job.created_at);
    $("job-message").textContent = [job.phase,job.message].filter(Boolean).join(" · ") || "服务端暂未提供阶段说明。";
    const modules = arr(job.modules), progress = executionProgress(job);
    $("job-progress").setAttribute("aria-valuenow",progress.percent); $("job-progress").setAttribute("aria-valuetext",`${progress.finished} / ${progress.total} 个已选模块已结束`); $("job-progress").firstElementChild.style.width = `${progress.percent}%`;
    $("job-progress-label").textContent = `已选模块 ${progress.finished} / ${progress.total} 已结束${progress.unselected ? ` · ${progress.unselected} 个未选择` : ""} · 执行进度不代表质量`;
    $("job-modules").innerHTML = modules.length ? modules.map(module => `<div class="job-module"><div class="job-module-head"><code>${escape(module.id)}</code>${statusTag(displayStatus(module,job.plan))}</div><div class="job-module-name">${escape(module.name || module.id)}</div>${module.reason || module.message ? `<p>${escape([module.reason,module.message].filter(Boolean).join(" · "))}</p>` : ""}${displayStatus(module,job.plan) !== "unselected" && numeric(module.duration_seconds) ? `<p>耗时 ${number(module.duration_seconds,2)} 秒</p>` : ""}</div>`).join("") : '<p class="small muted">等待服务端返回模块状态。</p>';
    setError("job-error",job.error ? pretty(job.error) : null);
    $("cancel-button").hidden = !ACTIVE.has(job.status); $("cancel-button").disabled = state.cancelling || job.status === "cancelling"; $("cancel-button").textContent = state.cancelling || job.status === "cancelling" ? "正在取消…" : "取消运行";
    // The report link appears only after a real completed result has been read.
    $("report-link").hidden = !(job.status === "completed" && state.resultJobId === job.id && state.result);
    $("report-link").href = `${API}/jobs/${encodeURIComponent(job.id)}/report`;
    $("job-permalink").href = jobLocation(job.id);
    $("clone-job-button").disabled = state.cloneBusy || state.submitting || ACTIVE.has(job.status);
    $("open-review-button").hidden = !(job.status === "completed" && state.resultJobId === job.id);
    renderRecordingProgress();
    renderPipeline(); renderPlan(); updateActions();
  }

  function renderResult() {
    const result = state.result, container = $("result-content");
    container.hidden = !result;
    if (!result) { container.innerHTML = ""; return; }
    const score = result.score || {};
    container.innerHTML = `<div class="score-card"><div class="score-value" aria-label="无已校准总分">—</div><div><strong>总分尚未校准</strong><p>${escape(score.reason || "当前仅报告分项证据与限制，不生成整体质量分数。")}</p></div></div>${arr(result.warnings).length ? `<ul class="result-warnings">${result.warnings.map(warning => `<li>${escape(pretty(warning))}</li>`).join("")}</ul>` : ""}${extensionResultsHtml(result)}<h3>模块结果摘要</h3>${arr(result.modules).length ? result.modules.map(module => `<details class="result-summary"><summary>${escape(module.id || module.module_id || "模块")} · ${escape(module.name || "结果")} ${module.status ? statusTag(displayStatus(module,state.job?.plan)) : ""}</summary><pre>${escape(pretty(module))}</pre></details>`).join("") : '<p class="small muted">服务端未提供模块摘要，请查看实际报告。</p>'}${result.recording ? `<details class="result-summary"><summary>本次记录与分析范围</summary><pre>${escape(pretty(result.recording))}</pre></details>` : ""}${result.artifacts ? `<details class="result-summary"><summary>产物清单</summary><pre>${escape(pretty(result.artifacts))}</pre></details>` : ""}`;
    container.innerHTML = `<p class="coverage-summary">${escape(coverageText(result))}</p>` + container.innerHTML;
  }

  function extensionResultsHtml(result) {
    const extensions = arr(result.extensions);
    if (!extensions.length) return "";
    const labels = {completed:"计算完成",partial:"部分可评",skipped:"未执行",failed:"执行失败",running:"运行中",pending:"等待执行",queued:"等待执行",cancelled:"已取消",interrupted:"已中断"};
    const count = value => Number.isInteger(value) && value >= 0;
    return `<section class="extension-results" aria-label="实际扩展结果"><h3>实际扩展结果</h3><p class="small muted">以下来自本次运行结果。计算完成不代表质量合格，候选仍需人工复核。</p>${extensions.map(entry => {
      const confirmedStatus = Object.hasOwn(labels,entry.status), counts = [];
      const intervalCount = count(entry.candidate_interval_count) ? entry.candidate_interval_count : entry.time_candidate_count;
      const channelCount = count(entry.candidate_channel_count) ? entry.candidate_channel_count : entry.channel_candidate_count;
      const pairCount = entry.candidate_pair_count, epochCount = entry.candidate_epoch_count;
      if (count(entry.candidate_count)) counts.push(`候选总数：${number(entry.candidate_count,0)}（待复核）`);
      if (count(intervalCount)) counts.push(`时间候选：${number(intervalCount,0)}（待复核）`);
      if (count(channelCount)) counts.push(`通道候选：${number(channelCount,0)}（待复核）`);
      if (count(pairCount)) counts.push(`通道对候选：${number(pairCount,0)}（待复核）`);
      if (count(epochCount)) counts.push(`分析分段候选：${number(epochCount,0)}（待复核）`);
      const totalOnly = count(entry.candidate_count) && ![intervalCount,channelCount,pairCount,epochCount].some(count);
      return `<article class="extension-result-card"><div class="extension-result-heading"><h4>${escape(entry.name || entry.id || "未命名扩展")}</h4><span class="tag ${confirmedStatus ? escape(entry.status) : "pending"}">${escape(labels[entry.status] || "执行状态未确认")}</span></div><p class="extension-result-reason">${escape(entry.reason || "运行结果未提供具体原因。")}</p><p class="extension-result-count">${escape(counts.length ? counts.join(" · ") : "候选数量：未提供（不按 0 处理）")}</p>${totalOnly ? '<p class="small muted">当前摘要仅提供总数，未区分时间区间与通道建议；类型和定位以原始证据为准。</p>' : ""}${count(pairCount) ? '<p class="small muted">通道对按对数计，不等于坏通道数。</p>' : ""}${count(epochCount) ? '<p class="small muted">分析分段不自动等同任务试次；固定分段或其他分段规则以原始证据为准。</p>' : ""}<details class="result-summary"><summary>扩展原始结果与参数${entry.module_id ? ` · ${escape(entry.module_id)}` : ""}</summary><pre>${escape(pretty(entry))}</pre></details></article>`;
    }).join("")}</section>`;
  }

  // Drafts store only configuration and identifiers, never waveform samples.
  function savedDraft() {
    try { const raw = window.sessionStorage.getItem(DRAFT_KEY); const value = raw && JSON.parse(raw); return value?.version === 1 && typeof value.input_id === "string" && value.qc_config && Array.isArray(value.selected_modules) ? value : null; }
    catch { return null; }
  }
  function saveDraft() {
    if (!state.input || state.mode !== "draft" || state.filePending || state.revisionInput) return;
    try { window.sessionStorage.setItem(DRAFT_KEY,JSON.stringify({version:1,input_id:state.input.id,selected_modules:body().selected_modules,qc_config:currentConfig(),parent_job_id:state.parentJobId,parameter_dirty:state.parameterDirty,parameter_text:$("extension-parameters").value,updated_at:new Date().toISOString()})); }
    catch { /* An unavailable session store does not prevent checking data. */ }
  }
  function discardDraft() { try { window.sessionStorage.removeItem(DRAFT_KEY); } catch {} $("draft-recovery").hidden = true; }
  function applyConfiguration(config) {
    const input = arr(state.catalog?.inputs).find(item => item.id === config.input_id);
    if (!input || !config.qc_config || !Array.isArray(config.selected_modules)) throw new Error("原记录或配置不可用，无法恢复这份方案。");
    selectInput(input.id,{autoPrepare:false});
    state.draftConfig = clone(config.qc_config); state.scope = config.qc_config.scope === "recording" ? "recording" : "window";
    state.selected = new Set(config.selected_modules.filter(id => OPTIONAL.includes(id)));
    state.extensions = new Set(arr(config.qc_config.method_config?.extensions));
    state.contextTags = {...state.contextTags,...(config.qc_config.context_tags || {})};
    state.parentJobId = typeof config.parent_job_id === "string" ? config.parent_job_id : null;
    const selection = config.qc_config.selection || {};
    $("start-seconds").value = state.scope === "recording" ? 0 : selection.start_seconds ?? 0;
    $("duration-seconds").value = state.scope === "recording" ? Math.min(120,input.metadata?.duration_seconds || 120) : selection.duration_seconds ?? Math.min(120,input.metadata?.duration_seconds || 120);
    renderContextEditors(); renderChannelConfig(); renderModuleOptions(); syncParameterEditor();
    if(config.parameter_dirty === true && typeof config.parameter_text === "string"){ $("extension-parameters").value=config.parameter_text;state.parameterDirty=true; }
    invalidatePlan();
    $("draft-recovery").hidden = true;
  }
  function restoreDraft() { const draft = savedDraft(); if (!draft) return; try { applyConfiguration(draft); } catch(error) { setError("catalog-error",error.message); } }
  function setScope(scope) { if (!["window","recording"].includes(scope) || state.submitting || state.mode !== "draft") return; state.scope = scope; if(scope==="window"&&Number($("duration-seconds").value)>120)$("duration-seconds").value=120; invalidatePlan(); }
  function jobLocation(id) {
    const url = new URL(`${location.pathname || "/"}${location.search || ""}`,"http://localhost");
    if (id) url.searchParams.set("job",id); else url.searchParams.delete("job");
    return `${url.pathname}${url.search}${location.hash || ""}`;
  }
  function setJobLocation(id) { const target = jobLocation(id); if (target !== `${location.pathname}${location.search}${location.hash}`) window.history.replaceState(window.history.state,"",target); }
  async function restoreNavigation() {
    if (state.navigationRestored) return; state.navigationRestored = true;
    const id = new URL(`${location.pathname}${location.search}`,"http://localhost").searchParams.get("job");
    if (id && /^[a-zA-Z0-9_-]{1,120}$/.test(id)) { await selectJob(id); return; }
    $("draft-recovery").hidden = !savedDraft();
  }
  async function cloneJobConfiguration() {
    if (!state.job || state.cloneBusy || state.submitting) return;
    const id = state.job.id; state.cloneBusy = true; $("clone-job-button").disabled = true; setError("job-load-error",null);
    try { const config = await api(`/jobs/${encodeURIComponent(id)}/configuration`); if (state.job?.id === id) { applyConfiguration({...config,parent_job_id:config.parent_job_id || id}); $("analysis-workspace").scrollIntoView({block:"start"}); } }
    catch(error) { setError("job-load-error",error.message); }
    finally { state.cloneBusy = false; $("clone-job-button").disabled = false; }
  }
  function coverageText(result = state.result) {
    const coverage = result?.coverage || state.job?.recording_progress?.coverage || state.job?.coverage;
    if (coverage) return `整份检查 · 记录 ${number(coverage.total_seconds,2)} 秒 · 已计算 ${number(coverage.completed_seconds,2)} 秒 · 失败 ${number(coverage.failed_seconds,2)} 秒 · 未执行 ${number(coverage.unexecuted_seconds,2)} 秒 · 数据间隙 ${number(coverage.gap_seconds,2)} 秒。计算覆盖不代表质量通过。`;
    const plan = state.job?.plan, selection = plan?.qc_config?.selection || {};
    return plan ? `片段预检 · 原记录 ${number(selection.start_seconds,2)}–${number((selection.start_seconds || 0) + (selection.duration_seconds || 0),2)} 秒 · 不代表整份记录。` : "仅波形预览，尚未执行质控。";
  }
  function renderRecordingProgress() {
    const progress=state.job?.recording_progress || (state.result?.coverage?state.result:null),box=$("recording-progress");
    box.hidden=!progress?.coverage; if(box.hidden){box.innerHTML="";return;}
    const coverage=progress.coverage,windows=arr(progress.windows),page=Math.max(0,Math.min(Math.ceil(windows.length/60)-1,Number($("window-page")?.value)||0)),expanded=$("window-state-details")?.open === true;
    const interrupted=["cancelled","interrupted","failed"].includes(state.job?.status),pct=numeric(coverage.execution_percent)?Math.max(0,Math.min(100,coverage.execution_percent)):0;
    const pages=Array.from({length:Math.ceil(windows.length/60)},(_,i)=>`<option value="${i}" ${i===page?"selected":""}>${i*60+1}–${Math.min(windows.length,(i+1)*60)}</option>`).join("");
    const windowStatus=row=>interrupted&&["running","pending","queued"].includes(row.status)?"未完成":STATUS[row.status] || (row.status==="not_run"?"未执行":row.status || "未提供");
    box.innerHTML=`<p class="coverage-summary">${escape(coverageText())}</p><p class="small muted">${interrupted?"任务已停止；上次正在执行的窗口按未完成显示。":"执行覆盖反映已计算时长，不是质量分数。"} ${numeric(coverage.running_seconds)?`${number(coverage.running_seconds,2)} s · ${interrupted?"停止时未完成":"正在执行"}`:""}</p><div class="progress-track" role="progressbar" aria-label="执行覆盖，非质量分数" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${pct}"><span style="width:${pct}%"></span></div><p class="small muted">${escape("所选检查均完成范围")} · ${number(coverage.fully_assessed_seconds,2)} s</p><details id="window-state-details" ${expanded?"open":""}><summary>逐窗执行记录 · ${windows.length}</summary>${pages?`<label class="window-page-label">窗口 <select id="window-page">${pages}</select></label>`:""}<div class="window-status-list">${windows.slice(page*60,(page+1)*60).map(row=>`<div class="window-chip ${["completed","partial","failed"].includes(row.status)?row.status:"pending"}"><strong data-i18n-skip>${escape(row.id)}</strong><span>${number(row.start_seconds,2)}–${number(row.start_seconds+row.duration_seconds,2)} s</span><span>${escape(windowStatus(row))}</span></div>`).join("")}</div></details>`;
  }
  function resetReviewWorkspace() {
    stashReviewDraft();
    ++state.workspaceRequest; ++state.waveformRequest; state.workspace = null; state.waveform = null; state.candidates = []; state.candidateId = null; state.review = null;
    $("review-workspace").hidden = true; $("candidate-detail").hidden = true; $("waveform-plot").innerHTML = "";
  }
  function reviewState(candidate) { return state.review?.decisions?.[candidate.id]?.decision || candidate.status || "pending"; }
  function reviewStatusLabel(value) { return ({pending:"待复核",accepted:"接受候选",rejected:"驳回候选",uncertain:"待定"})[value] || "待复核"; }
  function renderCandidateList() {
    const filter = $("candidate-filter").value || "all", module = $("candidate-module").value || "all", candidates = state.candidates.filter(row => (filter === "all" || reviewState(row) === filter) && (module === "all" || row.module_id === module));
    $("candidate-count").textContent = `${candidates.length} / ${state.candidates.length}`;
    const visible = candidates.slice(0,state.candidateLimit);
    $("candidate-list").innerHTML = visible.length ? visible.map(row => `<button class="candidate-item ${row.id === state.candidateId ? "active" : ""}" data-candidate="${escape(row.id)}"><span class="candidate-item-heading"><strong>${escape(row.module_id || "")} · ${escape(row.method || "候选")}</strong><span>${reviewStatusLabel(reviewState(row))}</span></span><span data-i18n-skip>${escape(arr(row.channel_names).join(" · ") || arr(row.channel_indices).map(index=>`#${index}`).join(" · "))}</span><small>${row.localization === "interval" && numeric(row.start_seconds) && numeric(row.stop_seconds) ? `${number(row.start_seconds,3)}–${number(row.stop_seconds,3)} s` : row.localization === "whole_window" ? "仅整窗定位" : "定位未提供"}</small><span>${escape(row.reason || "待检查原始证据")}</span></button>`).join("") + (candidates.length > visible.length ? '<button class="button ghost small-button" data-more-candidates>显示更多候选</button>' : "") : '<p class="small muted">当前筛选没有候选。没有候选不代表数据质量通过。</p>';
  }
  function workspaceChannels() { return arr(state.workspace?.channels); }
  function waveformSegments(indices) {
    const rates=[...new Set(workspaceChannels().filter(channel=>indices.includes(channel.index)).map(channel=>channel.sampling_rate_hz).filter(numeric))];
    if(rates.length!==1 || rates[0]<=0)return [];
    return arr(state.workspace?.segments).filter(row=>numeric(row.recording_start_seconds)&&numeric(row.start_sample)&&numeric(row.stop_sample)).map(row=>({start:row.recording_start_seconds,stop:row.recording_start_seconds+(row.stop_sample-row.start_sample)/rates[0]}));
  }
  function selectedWaveformChannels() { return [...$("waveform-channels").querySelectorAll("input[data-waveform-channel]")].filter(input=>input.checked).map(input=>Number(input.dataset.waveformChannel)); }
  function renderWaveformChannels(selected) {
    const chosen = new Set(selected);
    $("waveform-channels").innerHTML = workspaceChannels().map(channel=>`<label><input type="checkbox" data-waveform-channel="${escape(channel.index)}" ${chosen.has(channel.index) ? "checked" : ""}><span data-i18n-skip>#${escape(channel.index)} ${escape(channel.name)}</span></label>`).join("");
  }
  async function openReviewWorkspace(kind = "job") {
    const source = kind === "job" ? state.job : state.input;
    if (!source || state.submitting) return;
    resetReviewWorkspace(); const request = ++state.workspaceRequest;
    const meta = kind === "job" ? source.plan?.input_metadata || {} : source.metadata || {};
    const selection = kind === "job" ? source.plan?.qc_config?.selection || {} : currentConfig()?.selection || {};
    state.workspace = {kind,id:source.id,label:source.label || source.id,channels:arr(meta.channels),total_seconds:meta.duration_seconds,segments:arr(meta.continuous_segments)};
    $("review-workspace").hidden = false; $("review-source").textContent = state.workspace.label;
    $("candidate-sidebar").hidden = kind !== "job"; $("candidate-detail").hidden = true;
    $("candidate-module").innerHTML='<option value="all">全部模块</option>'+ORDER.map(id=>`<option value="${id}">${id} · ${MODULE_LABELS[id]}</option>`).join(""); $("candidate-module").value="all";
    $("coverage-summary").textContent = kind === "job" ? coverageText() : "仅波形预览，尚未执行质控。";
    $("waveform-start").value = selection.start_seconds || 0; $("waveform-duration").value = "5";
    renderWaveformChannels(arr(selection.eeg_indices).slice(0,8)); setError("review-error",null);
    $("review-workspace").scrollIntoView({block:"start"});
    if (kind === "job") {
      $("candidate-list").innerHTML = '<p class="small muted">正在读取候选与复核记录…</p>';
      try {
        const [catalog,review] = await Promise.all([api(`/jobs/${encodeURIComponent(source.id)}/candidates`),api(`/jobs/${encodeURIComponent(source.id)}/review`)]);
        if (request !== state.workspaceRequest) return;
        state.candidates = arr(catalog.candidates); state.review = review; state.candidateLimit = 100; renderCandidateList();
        if (arr(catalog.warnings).length) setError("review-error",catalog.warnings.map(pretty).join(" · "));
      } catch(error) { if (request === state.workspaceRequest) { setError("review-error",error.message); $("candidate-list").innerHTML = '<p class="small muted">候选读取未完成，可重新打开复核。</p>'; } }
    }
    if (request === state.workspaceRequest) await loadWaveform();
  }
  function candidateById(id) { return state.candidates.find(row=>row.id === id); }
  function stashReviewDraft() {
    if(state.workspace?.kind === "job" && state.candidateId)state.reviewDrafts[`${state.workspace.id}:${state.candidateId}`]={decision:$("review-decision").value,reviewer:$("review-reviewer").value,note:$("review-note").value};
  }
  function evidenceLinks(candidate) {
    const links = arr(candidate.evidence).concat(candidate.evidence && !Array.isArray(candidate.evidence) ? [candidate.evidence] : []);
    return links.map(entry => {
      const artifact=typeof entry === "object"&&entry?entry.artifact:null;
      const url = typeof entry === "string" ? entry : entry.url || (typeof artifact === "string"&&/^[A-Za-z0-9_.-]+$/.test(artifact)&&!['.','..'].includes(artifact)?`/api/v1/jobs/${encodeURIComponent(state.workspace?.id || "")}/artifacts/${encodeURIComponent(artifact)}`:null);
      const safe = typeof url === "string" && state.workspace?.kind === "job" && url.startsWith(`/api/v1/jobs/${encodeURIComponent(state.workspace.id)}/artifacts/`) && !/[<>"\s]/.test(url) ? url : null;
      return safe ? `<a href="${escape(safe)}" target="_blank" rel="noopener noreferrer">原始证据 ↗</a>` : "";
    }).join(" · ");
  }
  async function selectCandidate(id) {
    const candidate = candidateById(id); if (!candidate || state.reviewBusy) return;
    stashReviewDraft();
    state.candidateId = id; renderCandidateList(); $("candidate-detail").hidden = false;
    const decision = state.reviewDrafts[`${state.workspace?.id}:${id}`] || state.review?.decisions?.[id] || {};
    $("review-decision").value = decision.decision || "uncertain"; $("review-reviewer").value = decision.reviewer || ""; $("review-note").value = decision.note || "";
    $("review-save-status").textContent = "";
    $("candidate-evidence").innerHTML = `<h3>${escape(candidate.module_id || "")} · ${escape(candidate.method || "候选")}</h3><p>${escape(candidate.reason || "待检查原始证据")}</p><p class="small muted">${candidate.localization === "interval" ? "标记区间为算法候选，需结合原始波形复核。" : "此候选没有精确异常起止；当前波形仅作为上下文。"}</p>${evidenceLinks(candidate)}<details><summary>候选原始依据</summary><pre data-i18n-skip>${escape(pretty(candidate))}</pre></details>`;
    const indices = arr(candidate.channel_indices).filter(index=>workspaceChannels().some(channel=>channel.index === index));
    if (indices.length) renderWaveformChannels(indices.slice(0,16));
    if (numeric(candidate.start_seconds)) { const segment=waveformSegments(indices.length?indices:selectedWaveformChannels()).find(row=>candidate.start_seconds>=row.start&&candidate.start_seconds<row.stop); $("waveform-start").value = Math.max(segment?.start || 0,candidate.start_seconds - (candidate.localization === "interval" ? 1 : 0)); }
    await loadWaveform();
  }
  async function loadWaveform() {
    const workspace = state.workspace; if (!workspace) return;
    const indices = selectedWaveformChannels(), start = Number($("waveform-start").value), duration = Number($("waveform-duration").value);
    if (!indices.length || indices.length > 16 || !Number.isFinite(start) || start < 0 || !Number.isFinite(duration) || duration <= 0 || duration > 10) { setError("review-error","请选择 1–16 道信号、非负起点和不超过 10 秒的显示时长。"); return; }
    const total = workspace.total_seconds; let bounded = numeric(total) ? Math.min(duration,total - start) : duration;
    const segments=waveformSegments(indices);
    if(segments.length){const segment=segments.find(row=>start>=row.start&&start<row.stop);if(!segment){setError("review-error","显示起点位于数据间隙或有效段之外，请调整起点。");return;}bounded=Math.min(bounded,segment.stop-start);}
    if (bounded <= 0) { setError("review-error","显示起点超出记录范围。"); return; }
    const request = ++state.waveformRequest, workspaceRequest = state.workspaceRequest;
    $("waveform-status").textContent = "正在读取波形…"; $("waveform-load-button").disabled = true; setError("review-error",null);
    const route = workspace.kind === "job" ? "jobs" : "inputs";
    try {
      const data = await api(`/${route}/${encodeURIComponent(workspace.id)}/waveform?start_seconds=${encodeURIComponent(start)}&duration_seconds=${encodeURIComponent(bounded)}&channel_indices=${indices.join(",")}&max_points=1600`);
      if (request !== state.waveformRequest || workspaceRequest !== state.workspaceRequest) return;
      state.waveform = data; $("waveform-start").value=data.start_seconds; renderWaveform();
    } catch(error) { if (request === state.waveformRequest && workspaceRequest === state.workspaceRequest) { state.waveform = null; $("waveform-plot").innerHTML = ""; setError("review-error",error.message); $("waveform-status").textContent = "波形读取未完成"; } }
    finally { if (request === state.waveformRequest) $("waveform-load-button").disabled = false; }
  }
  function renderWaveform() {
    const data = state.waveform; if (!data) return;
    const channels = arr(data.channels).slice(0,16), start = data.start_seconds, stop = data.stop_seconds;
    if (!numeric(start) || !numeric(stop) || stop <= start) { setError("review-error","波形时间范围无效。"); return; }
    const width = 1000, left = 135, right = 20, rowHeight = 82, height = Math.max(1,channels.length)*rowHeight+40, gain = Number($("waveform-gain").value) || 1;
    const x = time => left + (time-start)/(stop-start)*(width-left-right);
    const candidate = candidateById(state.candidateId), canMark = candidate?.localization === "interval" && numeric(candidate.start_seconds) && numeric(candidate.stop_seconds);
    const a = canMark ? Math.max(start,candidate.start_seconds) : 0, b = canMark ? Math.min(stop,candidate.stop_seconds) : 0;
    const mark = canMark && b>a ? `<rect x="${x(a)}" y="0" width="${x(b)-x(a)}" height="${height-28}" fill="#2563eb" opacity="0.08"/>` : "";
    const scales=new Map();
    for(const channel of channels){const key=channel.unit || `unknown:${channel.source_index}`,values=arr(channel.values).slice(0,2000).filter(numeric);const magnitude=values.length?Math.max(...values.map(Math.abs)):0;scales.set(key,Math.max(scales.get(key)||0,magnitude));}
    const paths = channels.map((channel,index)=>{
      const times = arr(channel.times_seconds).slice(0,2000), values = arr(channel.values).slice(0,2000), finite = values.filter(numeric), baseline = index*rowHeight+rowHeight/2;
      if (!finite.length) return `<text x="8" y="${baseline}">${escape(channel.name || channel.source_index)} · ${escape(window.QCI18n?.translate("无有限采样") || "无有限采样")}</text>`;
      const scale=scales.get(channel.unit || `unknown:${channel.source_index}`)||1,limit=scale/gain;
      let drawing = false,clipped=0; const points = [];
      for (let i=0;i<Math.min(times.length,values.length,2000);i++) { if (!numeric(times[i]) || !numeric(values[i]) || times[i]<start || times[i]>stop) { drawing=false; continue; } if(Math.abs(values[i])>limit)clipped++; const y=baseline-Math.max(-limit,Math.min(limit,values[i]))/scale*28*gain; points.push(`${drawing?"L":"M"}${x(times[i]).toFixed(2)},${y.toFixed(2)}`); drawing=true; }
      const clipLabel=clipped?`<text x="${left+8}" y="${index*rowHeight+11}" class="waveform-clipped">${escape(window.QCI18n?.translate("显示裁切") || "显示裁切")} · ${clipped}</text>`:"";
      return `<line x1="${left}" x2="${width-right}" y1="${baseline}" y2="${baseline}" stroke="#cbd5e1"/><text x="8" y="${baseline-8}" class="waveform-label">#${escape(channel.source_index)} ${escape(channel.name)}</text><text x="8" y="${baseline+10}" class="waveform-unit">±${escape(Number(limit).toPrecision(3))} ${escape(channel.unit || "?")}</text><path data-source-index="${escape(channel.source_index)}" d="${points.join(" ")}" fill="none" stroke="${clipped?"#b45309":"#2563eb"}" stroke-width="1"/>${clipLabel}`;
    }).join("");
    const ticks = Array.from({length:6},(_,i)=>{const t=start+(stop-start)*i/5;return `<text x="${x(t)}" y="${height-5}" text-anchor="middle" class="waveform-unit">${t.toFixed(2)} s</text>`;}).join("");
    $("waveform-plot").innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escape(window.QCI18n?.translate("原始信号波形") || "原始信号波形")}">${mark}${paths}${ticks}</svg>`;
    $("waveform-status").textContent = `${number(start,3)}–${number(stop,3)} s · ${channels.length} 道 · ${data.display_method || "显示方法未提供"} · 同单位共用幅度标尺 · 以零为中心`;
  }
  function shiftWaveform(direction) { if (!state.workspace) return; const duration=Number($("waveform-duration").value)||5; const max=numeric(state.workspace.total_seconds)?Math.max(0,state.workspace.total_seconds-duration):Infinity; $("waveform-start").value=Math.max(0,Math.min(max,(Number($("waveform-start").value)||0)+direction*duration)); return loadWaveform(); }
  async function saveReview() {
    const workspace=state.workspace,candidate=candidateById(state.candidateId); if (!workspace || workspace.kind !== "job" || !candidate || state.reviewBusy || !state.review) return;
    const decision=$("review-decision").value,reviewer=$("review-reviewer").value.trim(),note=$("review-note").value.trim();
    if (!["accepted","rejected","uncertain"].includes(decision) || !reviewer) { setError("review-error","请选择复核结论并填写审核人。"); return; }
    const request=state.workspaceRequest; state.reviewBusy=true; $("save-review-button").disabled=true; setError("review-error",null);
    try {
      const review=await api(`/jobs/${encodeURIComponent(workspace.id)}/review`,{method:"POST",body:JSON.stringify({expected_version:state.review.version,candidate_id:candidate.id,decision,note,reviewer})});
      if (request!==state.workspaceRequest) return;
      state.review=review; renderCandidateList(); $("review-save-status").textContent="复核已保存；原始检测结果保持不变。";
      delete state.reviewDrafts[`${workspace.id}:${candidate.id}`];
    } catch(error) {
      if (request!==state.workspaceRequest) return;
      if (error.status===409) { try { const latest=await api(`/jobs/${encodeURIComponent(workspace.id)}/review`); if(request===state.workspaceRequest){state.review=latest;renderCandidateList();} } catch {} setError("review-error","复核记录已被更新。你的输入已保留，请核对最新记录后再保存。"); }
      else setError("review-error",error.message);
    } finally { state.reviewBusy=false; $("save-review-button").disabled=false; }
  }

  function clearPoll() { if (state.pollTimer) clearTimeout(state.pollTimer); state.pollTimer = null; }
  function schedulePoll(delay = 1800) {
    clearPoll();
    if (!state.job || !ACTIVE.has(state.job.status)) return;
    const id = state.job.id;
    state.pollTimer = setTimeout(() => { if (state.job?.id === id) refreshJob(true); },delay);
  }

  async function loadResult(id) {
    const request = ++state.resultRequest;
    try {
      const result = await api(`/jobs/${encodeURIComponent(id)}/result`);
      if (request !== state.resultRequest || state.job?.id !== id) return;
      state.result = result; state.resultJobId = id;
      renderResult(); renderJob();
    } catch(error) { if (request === state.resultRequest && state.job?.id === id) setError("job-load-error",`结果读取失败：${error.message}`); }
  }

  async function selectJob(id, provided) {
    if ((state.submitting || state.intakeBusy) && !provided) return;
    saveDraft(); cancelDraftRequests();
    clearPoll(); const request = ++state.jobRequest; ++state.resultRequest;
    state.job = null; state.result = null; state.resultJobId = null; state.mode = "job";
    setError("job-load-error",null); renderResult(); renderJob(); renderPipeline(); renderPlan(); renderRecommendation(); updateActions();
    $("job-status").className = "tag subtle"; $("job-status").textContent = "正在读取…";
    try {
      const job = provided || await api(`/jobs/${encodeURIComponent(id)}`);
      if (request !== state.jobRequest) return;
      state.job = job; state.pollFailures = 0; renderJob(); renderHistory(); renderRecommendation();
      setJobLocation(job.id);
      if (job.status === "completed") await loadResult(job.id);
      schedulePoll();
    } catch(error) { if (request === state.jobRequest) { setError("job-load-error",error.message); renderJob(); schedulePoll(5000); } }
  }

  async function refreshJob(fromPoll = false) {
    if (!state.job) return;
    const id = state.job.id, request = ++state.jobRequest;
    if (!fromPoll) $("refresh-job-button").disabled = true;
    try {
      const job = await api(`/jobs/${encodeURIComponent(id)}`);
      if (request !== state.jobRequest || state.job?.id !== id) return;
      const changed = state.job.status !== job.status;
      state.job = job; state.pollFailures = 0; setError("job-load-error",null); renderJob();
      if (job.status === "completed" && state.resultJobId !== id) await loadResult(id);
      if (changed || !fromPoll) await loadHistory();
      schedulePoll();
    } catch(error) {
      if (request !== state.jobRequest) return;
      state.pollFailures += 1;
      setError("job-load-error",`${error.message}${fromPoll ? " 将自动重试；页面保留最近一次已知状态。" : ""}`);
      schedulePoll(Math.min(15000,3000 * state.pollFailures));
    } finally { if (!fromPoll) $("refresh-job-button").disabled = false; }
  }

  async function cancelJob() {
    if (!state.job || !ACTIVE.has(state.job.status) || state.cancelling) return;
    const id = state.job.id; state.cancelling = true; renderJob(); setError("job-load-error",null);
    try {
      await api(`/jobs/${encodeURIComponent(id)}/cancel`, {method:"POST",body:"{}"});
      if (state.job?.id === id) await refreshJob();
      await loadHistory();
    } catch(error) { setError("job-load-error",`取消请求失败：${error.message}`); }
    finally { state.cancelling = false; renderJob(); }
  }

  function renderHistory() {
    const jobs = state.history; renderVisibility();
    $("history-list").innerHTML = jobs.length ? jobs.map(job => `<button class="history-item ${state.job?.id === job.id ? "active" : ""}" data-job="${escape(job.id)}" aria-label="查看 ${escape(job.label || job.id)}，${escape(STATUS[job.status] || job.status)}"><div class="history-item-top"><span class="history-name">${escape(job.label || job.id)}</span>${statusTag(job.status)}</div><div class="history-meta">${escape(date(job.created_at))} · <span data-i18n-skip>${escape(String(job.id || "").slice(-8))}</span></div><div class="history-config">${escape(runSummary(job))}</div></button>`).join("") : '<div class="empty-state"><p>暂无运行记录。完成规划后，开始第一份分析。</p></div>';
  }

  function runSummary(job) {
    const scope=job.scope || job.plan?.scope || job.plan?.qc_config?.scope,selection=job.plan?.qc_config?.selection;
    const fields=[scope === "recording" ? "整份检查" : scope === "window" || selection ? "快速预检" : "范围未提供"];
    if(selection && numeric(selection.start_seconds)&&numeric(selection.duration_seconds)&&scope!=="recording")fields.push(`${number(selection.start_seconds,2)}–${number(selection.start_seconds+selection.duration_seconds,2)} s`);
    const modules=arr(job.plan?.selected_modules || job.selected_modules);if(modules.length)fields.push(`${modules.length} 个模块`);
    if(job.parent_job_id)fields.push("复制配置运行");
    return fields.join(" · ");
  }

  async function loadHistory() {
    if (state.historyBusy) return;
    state.historyBusy = true; $("refresh-history-button").disabled = true; setError("history-error",null);
    try {
      const data = await api("/jobs"); state.history = arr(data.jobs).slice().sort((a,b) => new Date(b.created_at) - new Date(a.created_at)); renderHistory();
    } catch(error) { setError("history-error",error.message); if (!state.history.length) $("history-list").innerHTML = '<p class="small muted">运行记录暂不可用。点击右上角刷新重试。</p>'; }
    finally { state.historyBusy = false; $("refresh-history-button").disabled = false; }
  }

  function listSection(title, values) { const items = Array.isArray(values) ? values : values != null ? [values] : []; return `<section class="dialog-section"><h3>${escape(title)}</h3>${items.length ? `<ul>${items.map(item => `<li>${escape(pretty(item))}</li>`).join("")}</ul>` : '<p class="muted">服务端目录未提供。</p>'}</section>`; }
  function methodList(values) { return arr(values).length ? `<ul>${values.map(value => `<li>${escape(pretty(value))}</li>`).join("")}</ul>` : '<p class="small muted">目录未提供</p>'; }

  function methodDocumentationHtml(method) {
    const documentation = method.documentation;
    if (!documentation || typeof documentation !== "object") return '<p class="small muted">当前目录尚未补充详细方法说明。</p>';
    const sections = [["purpose","解决什么问题"],["how_it_works","方法如何工作"],["interpretation","怎样解释结果"],["when_to_use","适合使用时"],["when_not_to_use","不适合使用时"],["validation_status","当前验证证据"]];
    const explanation = sections.filter(([key]) => documentation[key] != null).map(([key,title]) => `<div><h5>${title}</h5>${Array.isArray(documentation[key]) ? methodList(documentation[key]) : `<p>${escape(pretty(documentation[key]))}</p>`}</div>`).join("");
    const references = arr(documentation.references).map(reference => {
      const url = safeSourceUrl(reference.url), title = reference.title || reference.url || "来源未命名";
      return `<li>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(title)} ↗</a>` : `<span>${escape(title)}${reference.url && reference.url !== title ? ` · ${escape(reference.url)}` : ""}</span>`}${reference.kind ? `<span class="small muted"> · ${escape(reference.kind)}</span>` : ""}</li>`;
    }).join("");
    return `<div class="method-documentation">${explanation}</div>${references ? `<div class="method-references"><h5>文档与证据来源</h5><ul>${references}</ul></div>` : ""}${documentation.upstream_call || documentation.implementation_origin || documentation.version_note ? `<details><summary>实现来源与版本说明</summary>${documentation.implementation_origin ? `<p>${escape(pretty(documentation.implementation_origin))}</p>` : ""}${documentation.upstream_call ? `<pre>${escape(pretty(documentation.upstream_call))}</pre>` : ""}${documentation.version_note ? `<p>${escape(pretty(documentation.version_note))}</p>` : ""}</details>` : ""}`;
  }

  function methodCardsHtml(module) {
    const methods = arr(module.methods).map(method => ({...method,module_id:module.id}));
    if (!methods.length) return '<section class="method-section"><h3>模块内的方法</h3><p>当前目录未提供方法子项。</p></section>';
    const plan = activePlan(), historical = state.mode === "job";
    return `<section class="method-section"><h3>模块内的方法 <span class="tag subtle">${methods.length} 项</span></h3><p>已接入的通用、条件子项随所属模块执行，不能在这里独立开关；尚未接入的子项仅展示。是否可用以计划核对为准，可选扩展需显式选择。</p>${methods.map(method => {
      const applicability = methodApplicability(method,plan), source = method.source || {}, url = safeSourceUrl(source.url);
      const switchable = method.optional_extension && method.implementation === "available";
      const historicalSelected = arr(plan?.qc_config?.method_config?.extensions).includes(method.id) || Boolean(applicability.selected);
      const selected = historical ? historicalSelected : state.extensions.has(method.id);
      return `<article class="method-card"><div class="method-card-head"><div><h4>${escape(method.name)}</h4><div class="method-tags"><span class="tag method-category ${escape(method.category)}">${escape(METHOD_CATEGORY[method.category] || "未分类")}</span><span class="tag subtle">${method.implementation === "available" ? "已接入" : "尚未接入"}</span></div></div>${statusTag(applicability.status)}</div><p>${escape(method.description || "目录未提供方法说明。")}</p><details class="method-more"><summary>原理、条件与来源</summary>${methodDocumentationHtml(method)}<div class="method-io"><div><h5>输入</h5>${methodList(method.inputs)}</div><div><h5>输出</h5>${methodList(method.outputs)}</div></div><div class="method-requirements"><h5>适用条件</h5>${methodList(method.requirements)}</div><div class="method-availability ${escape(applicability.status)}">${escape(applicability.reason || "计划未提供适用性原因。")}</div><div class="method-source"><span>开源 / 方法来源</span>${url ? `<a href="${escape(url)}" target="_blank" rel="noopener noreferrer">${escape(source.name || url)} ↗</a>` : `<span>${escape(source.name || "目录未提供")}</span>`}${source.license ? `<span class="source-license">${escape(pretty(source.license))}</span>` : '<span>许可未提供</span>'}</div>${arr(method.limitations).length ? `<details><summary>方法限制（${method.limitations.length} 项）</summary>${methodList(method.limitations)}</details>` : ""}${applicability.parameters != null || method.defaults != null ? `<details><summary>${applicability.parameters != null ? "本次计划参数" : "方法默认参数（尚待规划）"}</summary><pre>${escape(pretty(applicability.parameters ?? method.defaults))}</pre></details>` : ""}</details>${switchable ? `<div class="method-toggle"><label class="extension-check" for="dialog-extension-${escape(method.id)}"><input id="dialog-extension-${escape(method.id)}" type="checkbox" data-extension="${escape(method.id)}" ${selected ? "checked" : ""} ${historical ? "disabled" : ""}><span>${historical ? "此运行的扩展选择" : "启用这项可选扩展"}</span></label><p>${historical ? "历史选择只读；要修改，请在左侧配置新分析。" : `启用后同时选中 ${escape(module.id)}；开始时核对适用条件。`}</p></div>` : ""}</article>`;
    }).join("")}</section>`;
  }

  function refreshOpenDialog() { if ($("module-dialog").open && state.dialogModule) showModule(state.dialogModule); }
  function showModule(id) {
    const detailsUrl = moduleStandardsUrl(id);
    if (!detailsUrl) return;
    const module = arr(state.catalog?.modules).find(item => item.id === id);
    if (!module) return;
    state.dialogModule = id;
    const node = visualNodes().find(item => item.id === id);
    $("module-dialog-id").textContent = `${module.id} / ${module.stage || "模块说明"}`;
    $("module-dialog-title").textContent = module.name;
    $("module-details-link").setAttribute("href",detailsUrl);
    $("module-details-link").hidden = false;
    $("module-dialog-content").innerHTML = `<p>${escape(module.description || "暂无说明")}</p>${node ? `<section class="dialog-section"><h3>当前状态</h3>${statusTag(node.status)}${node.source_status && node.source_status !== node.status ? `<p class="small muted">服务原始状态：${escape(node.source_status)}；此处按实际选择集合区分显示。</p>` : ""}${node.reason ? `<p>${escape(node.reason)}</p>` : ""}${node.message ? `<p>${escape(node.message)}</p>` : ""}</section>` : ""}${listSection("输入",module.inputs)}${listSection("输出",module.outputs)}${listSection("依赖模块",module.dependencies)}<details class="dialog-section dialog-evidence"><summary>依据、证据与适用边界</summary><h3>依据与证据</h3><p>${escape(pretty(module.evidence || "目录未提供证据；不能据此推断已经验证。"))}</p><section class="dialog-section dialog-limitations"><h3>适用边界与限制</h3>${arr(module.limitations).length ? `<ul>${module.limitations.map(limit => `<li>${escape(pretty(limit))}</li>`).join("")}</ul>` : '<p>目录暂未列出限制；这不表示模块没有适用条件。</p>'}</section></details>`;
    if (id === "M01") {
      const readers = arr(state.catalog?.capabilities?.intake?.readers);
      $("module-dialog-content").innerHTML += `<section class="dialog-section"><h3>独立读取模块</h3><div class="reader-cards">${readers.map(reader=>`<article class="reader-card"><strong data-i18n-skip>${escape(reader.name || reader.id)}</strong><p data-i18n-skip>${escape(arr(reader.extensions).join(" · "))}</p><p>${reader.multifile ? "支持配套文件包" : "单文件读取"}</p>${arr(reader.limitations).length ? `<details><summary>读取范围</summary><ul>${reader.limitations.map(limit=>`<li>${escape(limit)}</li>`).join("")}</ul></details>`:""}</article>`).join("")}</div></section>`;
    }
    if (state.mode === "job" && state.job) {
      const artifacts=arr(state.result?.artifacts).filter(item=>typeof item.name==="string"&&item.name.toLowerCase().includes(id.toLowerCase()));
      const links=artifacts.map(item=>`<a href="${API}/jobs/${encodeURIComponent(state.job.id)}/artifacts/${encodeURIComponent(item.name)}" target="_blank" rel="noopener noreferrer" data-i18n-skip>${escape(item.name)}</a>`).join(" · ");
      $("module-dialog-content").innerHTML += `<section class="dialog-section run-evidence"><h3>本次运行证据</h3>${state.result ? `<button class="text-button" data-review-module="${id}">查看本次候选</button><a class="text-button" href="${API}/jobs/${encodeURIComponent(state.job.id)}/report" target="_blank" rel="noopener noreferrer">打开实际报告 ↗</a>` : '<p class="small muted">本次结果尚未就绪。</p>'}${links ? `<p>${links}</p>` : ""}</section>`;
    }
    $("module-dialog-content").innerHTML += `<details class="module-background"><summary>算法介绍与适用条件</summary>${methodCardsHtml(module)}</details>`;
    if (!$("module-dialog").open) $("module-dialog").showModal();
  }

  async function loadCatalog(preferredId = null, {intakeRequest = null} = {}) {
    const request = ++state.catalogRequest;
    state.loadingCatalog = true; setError("catalog-error",null);
    try {
      if (location.protocol === "file:") throw new Error("请通过本地工作台服务打开此页面；直接双击 HTML 无法连接分析 API。");
      const catalog = await api("/catalog");
      if (request !== state.catalogRequest) return false;
      if (!Array.isArray(catalog.inputs) || !Array.isArray(catalog.modules)) throw new Error("模块目录格式不完整，需要 inputs 与 modules 数组。");
      state.catalog = catalog;
      const datasets = new Set(catalog.inputs.map(input => input.dataset_id));
      $("catalog-scope").textContent = `${datasets.size} 类数据 · ${catalog.inputs.length} 份本地记录`;
      $("service-version").textContent = `${catalog.service || "Local EEG QC"} · API ${catalog.api_version || "v1"}`;
      $("service-version").hidden = false; if(catalog.version)$("service-version").textContent=`${catalog.version} · API ${catalog.api_version || "v1"}`;
      const grouped = new Map();
      catalog.inputs.forEach(input => { const group = input.dataset_id || "其他记录"; if (!grouped.has(group)) grouped.set(group,[]); grouped.get(group).push(input); });
      $("input-select").innerHTML = '<option value="">选择已登记记录</option>' + (catalog.inputs.length ? [...grouped.entries()].map(([group,inputs]) => `<optgroup label="${escape(group)}">${inputs.map(input => `<option value="${escape(input.id)}">${escape(input.label || input.id)}</option>`).join("")}</optgroup>`).join("") : '<option disabled>暂无已登记记录</option>');
      $("input-select").disabled = !catalog.inputs.length;
      renderModuleOptions(); renderPipeline(); renderToolkit();
      renderExamplePresets();
      const maySelect = intakeRequest == null || intakeRequest === state.intakeRequest;
      const selectedId = typeof preferredId === "string" && catalog.inputs.some(input => input.id === preferredId) ? preferredId : null;
      if (selectedId && maySelect) await selectInput(selectedId,{fromIntake:intakeRequest != null});
      else { $("input-select").value = state.input?.id || ""; updateActions(); }
      openModuleFromHash();
      await loadHistory();
      // Historical jobs remain in the history list; only an explicit click changes views.
      await restoreNavigation();
      $("intake-restore-button").hidden = !pendingIntakeId(); updateActions();
      return true;
    } catch(error) {
      if (request !== state.catalogRequest) return false;
      setConnection(false);
      $("catalog-error").hidden = false; $("catalog-error").innerHTML = `${escape(error.message)} <button id="retry-catalog-button">重新连接</button>`;
      $("retry-catalog-button").addEventListener("click",loadCatalog);
      $("input-select").innerHTML = '<option>数据目录尚未加载</option>';
      $("module-options").innerHTML = '<p class="small muted">等待本地服务提供模块目录。</p>';
      $("pipeline").innerHTML = '<div class="empty-state"><p>连接本地服务后显示真实模块与计划。</p></div>';
      $("history-list").innerHTML = '<p class="small muted">连接本地服务后读取运行记录。</p>';
      updateActions();
      return false;
    } finally { if (request === state.catalogRequest) state.loadingCatalog = false; }
  }

  $("input-select").addEventListener("change",event => selectInput(event.target.value));
  $("toolkit-category").addEventListener("change",renderToolkit);
  $("toolkit-implementation").addEventListener("change",renderToolkit);
  $("recommend-button").addEventListener("click",prepareRecommendedPlan);
  $("apply-recommendation-button").addEventListener("click",async () => { if (applyRecommendation()) await makePlan(); });
  $("apply-parameters-button").addEventListener("click",applyParameters);
  $("intake-file").addEventListener("change",chooseLocalFile);
  $("intake-upload-button").addEventListener("click",uploadIntake);
  $("intake-restore-button").addEventListener("click",restoreIntake);
  $("pending-intakes-button").addEventListener("click",listPendingIntakes);
  $("cancel-read-button").addEventListener("click",()=>state.uploadAbort?.());
  $("extension-parameters").addEventListener("input",() => { state.parameterDirty = true; invalidatePlan(); });
  $("start-seconds").addEventListener("input",() => invalidatePlan());
  $("duration-seconds").addEventListener("input",() => invalidatePlan());
  for (const field of Object.keys(CONTEXT_FIELDS)) $(`context-${field}`).addEventListener("change",event => setContext(field,event.target.value));
  $("plan-button").addEventListener("click",async () => { if (state.parameterDirty && !applyParameters()) return; await makePlan(); });
  $("run-button").addEventListener("click",startJob);
  $("refresh-history-button").addEventListener("click",loadHistory);
  $("refresh-job-button").addEventListener("click",() => refreshJob());
  $("cancel-button").addEventListener("click",cancelJob);
  $("restore-draft-button").addEventListener("click",restoreDraft);
  $("discard-draft-button").addEventListener("click",discardDraft);
  $("revise-input-button").addEventListener("click",beginInputRevision);
  $("preview-input-button").addEventListener("click",()=>openReviewWorkspace("input"));
  $("scope-window").addEventListener("change",()=>setScope("window"));
  $("scope-recording").addEventListener("change",()=>setScope("recording"));
  $("clone-job-button").addEventListener("click",cloneJobConfiguration);
  $("open-review-button").addEventListener("click",()=>openReviewWorkspace("job"));
  $("close-review-button").addEventListener("click",resetReviewWorkspace);
  $("candidate-filter").addEventListener("change",()=>{state.candidateLimit=100;renderCandidateList();});
  $("candidate-module").addEventListener("change",()=>{state.candidateLimit=100;renderCandidateList();});
  $("waveform-load-button").addEventListener("click",loadWaveform);
  $("waveform-prev-button").addEventListener("click",()=>shiftWaveform(-1));
  $("waveform-next-button").addEventListener("click",()=>shiftWaveform(1));
  $("waveform-duration").addEventListener("change",loadWaveform);
  $("waveform-gain").addEventListener("change",renderWaveform);
  $("save-review-button").addEventListener("click",saveReview);
  $("close-dialog-button").addEventListener("click",() => $("module-dialog").close());
  $("module-dialog").addEventListener("close",moduleDialogClosed);
  $("module-dialog").addEventListener("click",event => { if (event.target === $("module-dialog")) { const box = event.target.getBoundingClientRect(); if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) event.target.close(); } });
  document.addEventListener("click",event => { if (event.target.closest("[data-reset-recommend]")) prepareRecommendedPlan(); const example = event.target.closest("[data-example]"); if (example && !example.disabled) selectInput(example.dataset.example); const detail = event.target.closest("[data-detail]"); if (detail) showModule(detail.dataset.detail); const history = event.target.closest("[data-job]"); if (history) selectJob(history.dataset.job); if (event.target.closest("#intake-confirm-button")) confirmIntake(); });
  document.addEventListener("click",event=>{const candidate=event.target.closest("[data-candidate]");if(candidate)selectCandidate(candidate.dataset.candidate);if(event.target.closest("[data-more-candidates]")){state.candidateLimit+=100;renderCandidateList();}if(event.target.closest("#cancel-revision-button"))cancelInputRevision();const pending=event.target.closest("[data-restore-intake]");if(pending)restoreIntake(pending.dataset.restoreIntake);});
  document.addEventListener("click",async event=>{const button=event.target.closest("[data-review-module]");if(button&&ORDER.includes(button.dataset.reviewModule)){$("module-dialog").close();await openReviewWorkspace("job");$("candidate-module").value=button.dataset.reviewModule;renderCandidateList();}});
  document.addEventListener("change",event => { if (event.target.id === "intake-modality") { const supported = event.target.value === "scalp_eeg"; $("intake-modality-note").textContent = event.target.value === "unknown" || supported ? "" : "可保存提取信息；当前模态暂无质控配置。"; $("intake-confirm-button").textContent = supported ? "确认并推荐" : "确认信息"; } const input = event.target.closest("[data-extension]"); if (input && !input.disabled) setExtension(input.dataset.extension,input.checked); });
  document.addEventListener("change",event=>{if(event.target.id==="window-page")renderRecordingProgress();});
  document.addEventListener("qc:languagechange",renderWaveform);
  document.addEventListener("visibilitychange",() => { if (!document.hidden && state.job && ACTIVE.has(state.job.status)) refreshJob(); });
  window.addEventListener("beforeunload",clearPoll);
  window.addEventListener("beforeunload",saveDraft);
  window.addEventListener("hashchange",openModuleFromHash);
  renderPipeline();
  loadCatalog();
})();
