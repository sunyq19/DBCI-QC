// A completed non-EEG result must render its saved score without an EEG report view.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync('apps/workbench/web/app.js', 'utf8');
const code = source.slice(source.indexOf('  function renderResultContent()'), source.indexOf('  function scoredResultHtml('));
const container = {hidden: true, innerHTML: ''};
const workflow = {open: true}, recordSummary = {hidden: false};
const state = {result: {project_score: {value: 53.515625, components: [
  {name: '数值有效性', value: 100, weight: 30, reason: '未检出非有限值'},
  {name: '通道状态', value: 33.59375, weight: 70, reason: '邻域一致性候选'}
]}}};
const context = {state, $: id => ({'result-content': container, 'workflow-panel': workflow, 'record-summary': recordSummary}[id]), escape: String, arr: x => Array.isArray(x) ? x : [],
  numeric: x => typeof x === 'number' && Number.isFinite(x), number: (x, n) => x.toFixed(n),
  extensionResultsHtml: () => '', coverageText: () => '已检查 20 秒'};
vm.createContext(context);
vm.runInContext(code, context);
context.renderResultContent();
assert.equal(container.hidden, false);
assert.equal(workflow.open, false);
assert.equal(recordSummary.hidden, true);
assert.ok(container.innerHTML.includes('53.52'));
assert.ok(container.innerHTML.includes('30.0%') && container.innerHTML.includes('70.0%'));
assert.ok(!container.innerHTML.includes('总分尚未校准'));
state.result = {project_score: {value: null, components: [], missing_reason: '所选检查无有效分数'}};
context.renderResultContent();
assert.ok(container.innerHTML.includes('所选检查无有效分数'));
state.result = {project_score: {value: 53.515625, components: [
  {id:'lf', name:'LF', value:33.59375, weight:0},
  {id:'state', name:'通道状态', value:33.59375, weight:70, evidence_components:[{id:'lf',name:'LF',value:33.59375}]},
  {id:'numeric', name:'数值有效性', value:100, weight:30}
]}};
context.renderResultContent();
assert.ok(container.innerHTML.includes('检查结果 · 2'));
assert.ok(container.innerHTML.includes('包含检查 · 1'));
assert.ok(container.innerHTML.includes('LF · 33.59 / 100'));
assert.ok(!container.innerHTML.includes('不计入'));
console.log('Saved non-EEG score and grouped evidence rendering passed');
