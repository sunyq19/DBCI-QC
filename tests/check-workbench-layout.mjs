// Static HTML/CSS contracts only. No browser, HTTP requests, or analysis jobs.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(root, 'apps/workbench/web/index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'apps/workbench/web/styles.css'), 'utf8');
const source = fs.readFileSync(path.join(root, 'apps/workbench/web/app.js'), 'utf8');
const voidTags = new Set(['area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr']);
const document = {tag:'document',attrs:{},parent:null,children:[]};
const stack = [document], nodes = [];
for (const match of html.matchAll(/<!--[\s\S]*?-->|<![^>]*>|<\/?[A-Za-z][^>]*>/g)) {
  const token = match[0];
  if (token.startsWith('<!')) continue;
  if (token.startsWith('</')) {
    const tag = /^<\/([^\s>]+)/.exec(token)[1].toLowerCase();
    assert.equal(stack.at(-1).tag, tag, `Balanced HTML closing tag: ${tag}`);
    stack.pop(); continue;
  }
  const tag = /^<([^\s/>]+)/.exec(token)[1].toLowerCase(), attrs = {};
  const body = token.slice(tag.length+1, token.length-1).replace(/\/$/, '');
  for (const m of body.matchAll(/([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s]+)))?/g)) attrs[m[1]] = m[2] ?? m[3] ?? m[4] ?? '';
  const node = {tag,attrs,parent:stack.at(-1),children:[],offset:match.index};
  node.parent.children.push(node); nodes.push(node);
  if (!voidTags.has(tag) && !token.endsWith('/>')) stack.push(node);
}
assert.equal(stack.length, 1, 'HTML tags are balanced');
const byId = id => nodes.find(node => node.attrs.id === id);
const hasClass = (node, name) => (node?.attrs.class || '').split(/\s+/).includes(name);
const ancestors = node => {const out=[];for(let p=node?.parent;p;p=p.parent)out.push(p);return out};
const containing = (node, parent) => ancestors(node).includes(parent);
const rules = [];
function collectRules(text, media = []) {
  let cursor=0;
  while(cursor<text.length) {
    const open=text.indexOf('{',cursor);if(open<0)break;
    const head=text.slice(cursor,open).trim();let depth=1,end=open+1;
    for(;end<text.length&&depth;end++){if(text[end]==='{')depth++;else if(text[end]==='}')depth--}
    assert.equal(depth,0,`Balanced CSS block: ${head.slice(0,60)}`);
    const body=text.slice(open+1,end-1);cursor=end;
    if(head.startsWith('@media'))collectRules(body,[...media,head.slice(6).trim()]);
    else if(!head.startsWith('@')) {
      const declarations={};
      for(const declaration of body.split(';')){const colon=declaration.indexOf(':');if(colon>=0)declarations[declaration.slice(0,colon).trim()]=declaration.slice(colon+1).trim()}
      for(const selector of head.split(','))rules.push({selector:selector.trim(),media,declarations});
    }
  }
}
collectRules(css.replace(/\/\*[\s\S]*?\*\//g,''));
function simpleMatches(selector,node) {
  if(!node || /[\[:+~]/.test(selector))return false;
  const tag=/^[a-z][\w-]*/i.exec(selector)?.[0];if(tag&&node.tag!==tag.toLowerCase())return false;
  for(const id of selector.matchAll(/#([\w-]+)/g))if(node.attrs.id!==id[1])return false;
  for(const cls of selector.matchAll(/\.([\w-]+)/g))if(!hasClass(node,cls[1]))return false;
  return true;
}
function selectorMatches(selector,node) {
  const parts=selector.replace(/\s*>\s*/g,' > ').split(/\s+/);let at=parts.length-1,current=node;
  if(!simpleMatches(parts[at--],current))return false;
  while(at>=0){if(parts[at]==='>'){at--;current=current.parent;if(!simpleMatches(parts[at--],current))return false}else{const wanted=parts[at--];current=current.parent;while(current&&!simpleMatches(wanted,current))current=current.parent;if(!current)return false}}
  return true;
}
function mediaMatches(media,width) {
  return media.every(query => {
    if(/print|prefers-/.test(query))return false;
    for(const m of query.matchAll(/\((min|max)-width\s*:\s*([\d.]+)px\)/g))if(m[1]==='min'?width<+m[2]:width>+m[2])return false;
    return true;
  });
}
function style(node,width) {
  const values={},priority={};
  for(const rule of rules) {
    if(!mediaMatches(rule.media,width)||!selectorMatches(rule.selector,node))continue;
    const specificity=(rule.selector.match(/#/g)||[]).length*100+(rule.selector.match(/\./g)||[]).length*10+(rule.selector.match(/(?:^|\s|>)\s*[a-z][\w-]*/gi)||[]).length;
    for(const [key,raw]of Object.entries(rule.declarations)) {
      const rank=specificity+(raw.includes('!important')?10000:0);
      if(!(key in priority)||rank>=priority[key]){values[key]=raw.replace(/\s*!important\s*$/,'');priority[key]=rank}
    }
  }
  return values;
}
const tests=[];const check=(name,run)=>tests.push([name,run]);
const layout=nodes.find(node=>hasClass(node,'studio-layout'));
const upload=byId('upload-panel'),pipeline=byId('pipeline-section'),controls=nodes.find(node=>hasClass(node,'studio-controls'));
check('single IDs and three distinct studio regions',()=>{
  const ids=nodes.map(n=>n.attrs.id).filter(Boolean);assert.equal(ids.length,new Set(ids).size);
  assert(layout,'studio-layout exists');assert(upload);assert(pipeline);assert(controls);
  for(const area of [upload,pipeline,controls])assert.equal(area.parent,layout,'Each studio region is a direct layout child');
});
check('pipeline is an independent permanently visible aside',()=>{
  assert.equal(pipeline.tag,'aside');assert(!containing(pipeline,byId('analysis-workspace')));assert(!containing(pipeline,controls));
  for(const node of [pipeline,...ancestors(pipeline)]){assert.notEqual(node.tag,'details');assert(!Object.hasOwn(node.attrs,'hidden'))}
  assert(containing(byId('pipeline'),pipeline));assert(containing(byId('pipeline-title'),pipeline));
});
check('upload stays available before the conditional analysis workspace',()=>{
  assert(!containing(upload,byId('analysis-workspace')));assert(!Object.hasOwn(upload.attrs,'hidden'));
  assert(containing(byId('analysis-workspace'),controls));assert(containing(byId('run-button'),controls));assert.equal(byId('run-button').attrs.disabled,'');
  assert(containing(byId('intake-file'),upload));assert(containing(byId('intake-confirmation'),pipeline));assert(containing(byId('record-summary'),pipeline));
});
check('pipeline title is a heading, not a disclosure toggle',()=>{
  assert(/^h[1-6]$/.test(byId('pipeline-title').tag));assert(html.slice(byId('pipeline-title').offset).startsWith(`<${byId('pipeline-title').tag}`));
  assert(source.includes('框架预览'));assert(source.includes('读取与识别'));assert(source.includes('质量检查'));assert(source.includes('汇总与报告'));
});
check('desktop studio uses a two-column grid with a spanning graph rail',()=>{
  const box=style(layout,1400),rail=style(pipeline,1400);assert.equal(box.display,'grid');assert(box['grid-template-columns']&&box['grid-template-columns']!=='1fr');
  const span=rail['grid-row']||'';const areas=box['grid-template-areas']||'';
  assert(/span\s+2|1\s*\/\s*3/.test(span)||(/pipeline/.test(areas)&&(areas.match(/pipeline/g)||[]).length>=2),'Graph spans upload and controls rows');
});
check('desktop rail has bounded viewport height and its own vertical scrolling',()=>{
  const rail=style(pipeline,1400);assert.equal(rail.position,'sticky');assert.equal(rail.top,'24px');assert.equal((rail['max-height']||'').replace(/\s/g,''),'calc(100dvh-48px)');assert.equal(rail['overflow-y']||rail.overflow,'auto');
});
check('tablet and phone remove sticky clipping and keep upload-graph-controls order',()=>{
  for(const width of [1000,768,420]){
    const box=style(layout,width),rail=style(pipeline,width);assert.notEqual(rail.position,'sticky',`Nonsticky at ${width}px`);assert(['none','unset','initial'].includes(rail['max-height']||'none'));assert(!['auto','scroll','hidden'].includes(rail['overflow-y']||rail.overflow||'visible'));
    assert(box.display==='flex'||['1fr','minmax(0,1fr)'].includes((box['grid-template-columns']||'').replace(/\s/g,'')),'Single column on smaller screens');
    if(box.display==='flex')assert.equal(box['flex-direction'],'column');
    const sorted=[upload,pipeline,controls].map(node=>({node,order:Number(style(node,width).order||0)})).sort((a,b)=>a.order-b.order||a.node.offset-b.node.offset).map(row=>row.node);
    assert.deepEqual(sorted,[upload,pipeline,controls],`Reading order at ${width}px`);
  }
});
check('flow grids and nodes can shrink without inherited fixed horizontal widths',()=>{
  const flow={tag:'div',attrs:{class:'flow-nodes flow-checks'},parent:pipeline};
  const node={tag:'button',attrs:{class:'pipeline-node framework'},parent:flow};
  for(const width of [1400,1000,768,420]){
    const flowStyle=style(flow,width),nodeStyle=style(node,width),canvas=style(byId('pipeline'),width);
    assert.equal(flowStyle.display,'grid');assert.equal(flowStyle['min-width'],'0');assert.equal(nodeStyle['min-width'],'0');assert.equal(nodeStyle['max-width'],'none');assert.equal(canvas.overflow,'visible');
    assert(!/minmax\(\s*\d+px/.test(flowStyle['grid-template-columns']||''),'Track minimum does not force a fixed pixel overflow');
  }
  assert.equal(style(flow,420)['grid-template-columns'].replace(/\s/g,''),'repeat(2,minmax(0,1fr))');
});
check('persistent graph does not expose analysis actions before confirmation',()=>{
  for(const id of ['run-button','recommend-button','apply-recommendation-button','plan-button'])assert(!containing(byId(id),pipeline));
  assert(containing(byId('plan-details'),pipeline),'Only plan explanation belongs in the graph rail');
  assert.equal(byId('plan-details').parent.tag,'details','Lengthy plan content remains optional');
});
check('layout changes preserve the safe module documentation entry',()=>{
  assert.equal(byId('module-details-link').attrs.target,'_blank');assert((byId('module-details-link').attrs.rel||'').split(/\s+/).includes('noopener'));assert(source.includes('window.addEventListener("hashchange",openModuleFromHash)'));
});
for(const[name,run]of tests){run();console.log(`PASS ${name}`)}
console.log(`${tests.length} static layout contracts passed. This is not browser geometry, keyboard, or visual validation.`);
