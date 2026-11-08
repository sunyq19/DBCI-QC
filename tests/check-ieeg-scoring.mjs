// Exercise the score editor without browser or network access.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('apps/workbench/web/app.js','utf8');
const code=source.slice(source.indexOf('  function renderScoringControls()'),source.indexOf('  function renderModuleOptions()'));
const specs=[{id:'ieeg_numeric_integrity',name:'数值有效性',module_id:'M03',method_id:'ieeg_numeric_integrity',reducer:'ieeg_numeric'},
 {id:'ieeg_signal_stability',name:'信号稳定性',module_id:'M03',method_id:'mne_amplitude',reducer:'ieeg_stability'},
 {id:'mne_amplitude_channels',name:'原始通道候选',module_id:'M03',method_id:'mne_amplitude',reducer:'channels'}];
let controls=[];
const box={querySelector(){return null},querySelectorAll(){return controls},set innerHTML(html){this.html=html;controls=[];
 for(const match of html.matchAll(/<input[^>]*data-score-weight="([^"]+)"[^>]*value="([^"]*)"[^>]*>/g))controls.push({dataset:{scoreWeight:match[1]},value:match[2],handlers:{},addEventListener(k,v){this.handlers[k]=v},setCustomValidity(){},reportValidity(){}});
}};
const state={input:{modality:'ecog'},mode:'draft',selected:new Set(),extensions:new Set(),draftConfig:{scoring:{version:'project-weighted/1.2',preset:'ecog-basic-score/0.1',weights:{ieeg_numeric_integrity:30,ieeg_signal_stability:70}}}};
const context={state,$:()=>box,inputModality:i=>i.modality,scoringOutputs:()=>specs,currentConfig:()=>structuredClone(state.draftConfig),numeric:Number.isFinite,escape:String,clone:structuredClone,scoreShareLabel:(w,t)=>String(w/t),invalidatePlan(){},renderModuleOptions(){}};
vm.createContext(context);vm.runInContext(code,context);context.renderScoringControls();
assert.deepEqual(controls.map(c=>c.dataset.scoreWeight),['ieeg_numeric_integrity','ieeg_signal_stability'],'Do not offer duplicate raw evidence weights in the default preset');
assert.ok(box.html.includes('/standards/ieeg-scoring'));
controls[0].value='50';controls[0].handlers.change();
assert.equal(state.draftConfig.scoring.weights.ieeg_numeric_integrity,50);
assert.equal(state.draftConfig.scoring.preset,'ecog-basic-score/0.1');
assert.equal(state.extensions.size,0,'The numerical measurement is built in, not an extension');
context.renderScoringControls();controls[1].value='50';controls[1].handlers.change();
assert.ok(state.extensions.has('mne_amplitude'));assert.ok(state.selected.has('M03'));
assert.deepEqual({...state.draftConfig.scoring.weights},{ieeg_numeric_integrity:50,ieeg_signal_stability:50});
state.mode='job';context.renderScoringControls();assert.match(box.html,/value="50" disabled/);
console.log('iEEG scoring editor behavior passed');
