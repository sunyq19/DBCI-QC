// Editor behavior only: no browser or QC execution.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync('apps/workbench/web/app.js','utf8');
const code=source.slice(source.indexOf('  function renderIeegGroups()'),source.indexOf('  function setExtension('));
const controls={}, box={hidden:false};
let inputs=[], renders=0, invalidations=0;
const fields={dataset:{},contains(node){return inputs.includes(node)},
 set innerHTML(value){this.html=value;renders++;inputs=[];
  for(const tag of value.matchAll(/<input\b[^>]*>/g)){
   const s=tag[0], key=/data-ieeg-group="(\d+)"/.exec(s)?.[1];
   const input={value:/value="([^"]*)"/.exec(s)?.[1]||'',checked:/\schecked\b/.test(s),handlers:{},addEventListener(k,v){this.handlers[k]=v}};
   if(key!==undefined)input.dataset={ieegGroup:key};else controls['ieeg-reference-confirmed']=input;
   inputs.push(input);
  }
  controls['ieeg-group-status']={textContent:''};
 },querySelectorAll(selector){return selector==='input'?inputs:inputs.filter(i=>i.dataset)}};
const state={input:{id:'source',metadata:{channels:[{index:7,name:'X'},{index:2,name:'X'}]}},mode:'draft',activeModality:'seeg',extensions:new Set(['ieeg_group_outliers']),
 draftConfig:{selection:{eeg_indices:[7,2]},method_config:{comparison_groups:{'source:ch:2':'group B','source:ch:7':'group A'},extension_parameters:{ieeg_group_outliers:{threshold_z:5,reference_confirmed:true}}}}};
const document={activeElement:null};
Object.assign(controls,{'ieeg-groups':box,'ieeg-group-fields':fields});
const context={state,document,$:id=>controls[id],arr:value=>Array.isArray(value)?value:[],escape:String,
 currentConfig:()=>structuredClone(state.draftConfig),syncParameterEditor(){},renderChannelConfig(){},
 invalidatePlan(){invalidations++;context.renderIeegGroups();}};
vm.createContext(context);vm.runInContext(code,context);context.renderIeegGroups();
assert.deepEqual(inputs.filter(i=>i.dataset).map(i=>i.value),['group A','group B'],'Map groups by source identity, not dictionary or channel-name order');
const target=inputs[0];document.activeElement=target;target.value='changed';const mounted=renders;target.handlers.change({target});
assert.equal(renders,mounted,'Changing a group must preserve focused fields and tab navigation');
assert.deepEqual(Array.from(state.draftConfig.method_config.comparison_groups),['changed','group B']);
assert.equal(state.draftConfig.method_config.extension_parameters.ieeg_group_outliers.reference_confirmed,false,'Changing a group revokes the prior comparability confirmation');
assert.equal(state.draftConfig.method_config.extension_parameters.ieeg_group_outliers.threshold_z,5,'Preserve custom thresholds');
const check=controls['ieeg-reference-confirmed'];document.activeElement=check;check.checked=true;check.handlers.change({target:check});
assert.equal(state.draftConfig.method_config.extension_parameters.ieeg_group_outliers.reference_confirmed,true);
assert.equal(invalidations,2);
state.submitting=true;target.value='ignored';target.handlers.change({target});assert.equal(invalidations,2,'Frozen submission config cannot be edited');
state.submitting=false;state.mode='job';context.renderIeegGroups();assert.equal(box.hidden,true,'Historical runs have no mutable group editor');
state.mode='draft';state.activeModality='scalp_eeg';context.renderIeegGroups();assert.equal(box.hidden,true,'Intracranial editor must not appear for scalp EEG');
console.log('iEEG group editor behavior passed');
