// Score-table markup and callback contract; full weight state lives in check-ui-contract.mjs.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('apps/workbench/web/app.js','utf8');
const code=source.slice(source.indexOf('  function renderScoringControls()'),source.indexOf('  // Keep the service payload'));
const rows=[{id:'ieeg_numeric_integrity',name:'数值有效性',module_id:'M03',weight:30,condition:'ready'},
 {id:'ieeg_signal_stability',name:'信号稳定性',module_id:'M03',weight:70,condition:'ready'}];
let controls=[];const calls=[];
const box={querySelector(){return null},querySelectorAll(selector){return selector==='[data-score-weight]'?controls:[]},set innerHTML(html){this.html=html;controls=[];
 for(const match of html.matchAll(/<input[^>]*data-score-weight="([^"]+)"[^>]*value="([^"]*)"[^>]*>/g))controls.push({dataset:{scoreWeight:match[1]},value:match[2],handlers:{},addEventListener(k,v){this.handlers[k]=v},setCustomValidity(s){this.error=s},reportValidity(){}});
}};
const state={input:{modality:'ecog'},mode:'draft'};
const context={state,$:()=>box,unsupportedInput:()=>false,escape:String,scoreConfigurationModel:()=>({rows,weights:{ieeg_numeric_integrity:30,ieeg_signal_stability:70},total:100,effectiveTotal:100,intracranial:true,grouped:false}),updateScorePercent:(...args)=>calls.push(args)};
vm.createContext(context);vm.runInContext(code,context);context.renderScoringControls();
assert.deepEqual(controls.map(c=>c.dataset.scoreWeight),['ieeg_numeric_integrity','ieeg_signal_stability']);
assert.ok(box.html.includes('/standards/ieeg-scoring'));
controls[0].value='50';controls[0].handlers.change();assert.deepEqual(calls[0],['ieeg_numeric_integrity',50,false]);
controls[0].value='101';controls[0].handlers.change();assert.equal(calls.length,1);assert.ok(controls[0].error);
state.mode='job';context.renderScoringControls();assert.equal(box.html,'');
console.log('iEEG scoring table and delegated weight edits passed');
