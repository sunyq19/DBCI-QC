// Saved-chart interaction checks without opening a browser or computing detectors.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const handlers={}, requests=[];
const makeForm=()=>{
 const status={textContent:''},span={textContent:'刷新图表'},button={disabled:false,querySelector:()=>span,focus(){this.focused=true}},select={disabled:false},options={open:true};
 return {action:'http://local/charts',dataset:{},attrs:{},status,button,select,options,
  closest(){return this},setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]},
  querySelector(s){return {'.chart-update-status':status,'.chart-refresh':button,'.display-options':options}[s]},
  querySelectorAll(){return [select]}};
};
let form=makeForm(), nextForm;
const panel={id:'chart-spectra',tagName:'DETAILS',open:false};
const main={children:['old plots'],addEventListener(k,v){handlers[k]=v},querySelectorAll(){return [panel]},
 querySelector(){return form},replaceChildren(...children){this.children=children;form=nextForm;panel.open=true}};
const window={location:{origin:'http://local',href:'http://local/charts',hash:''},history:{replaceState(...args){this.last=args}},addEventListener(){}};
const context={URL,URLSearchParams,AbortController,window,document:{documentElement:{classList:{contains:()=>false}},querySelector:()=>main,getElementById:()=>panel},
 setTimeout:()=>1,clearTimeout(){},fetch:()=>new Promise(resolve=>requests.push(resolve)),
 FormData:class{*[Symbol.iterator](){yield ['configured','1'];yield ['show','psd'];}},
 DOMParser:class{parseFromString(){nextForm=makeForm();return {querySelector:()=>({childNodes:['new plots'],querySelector:()=>nextForm})}}}};
vm.runInNewContext(fs.readFileSync('apps/workbench/web/visualizations.js','utf8'),context);
handlers.change({target:form});assert.equal(form.status.textContent,'点击刷新以应用');
const submit=()=>handlers.submit({target:form,preventDefault(){}});
const failure=submit();assert.equal(form.dataset.update,'loading');assert.equal(form.button.disabled,true);
await submit();assert.equal(requests.length,1,'Double clicks must not submit twice');
requests.shift()({ok:false});await failure;
assert.deepEqual(main.children,['old plots']);assert.equal(form.dataset.update,'error');assert.equal(form.button.disabled,false);assert.equal(form.select.disabled,false);
const success=submit();requests.shift()({ok:true,text:async()=>'<main>charts</main>'});await success;
assert.deepEqual(main.children,['new plots']);assert.equal(form.dataset.update,'done');assert.equal(form.status.textContent,'已更新');assert.equal(form.options.open,true);assert.equal(panel.open,false,'Keep expanded/collapsed state');
assert.equal(form.button.focused,true);assert.match(window.history.last[2],/show=psd/);
console.log('PASS chart refresh loading, selection, duplicate click guard, failure preservation and disclosure state');
