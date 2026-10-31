// Execute the exact served document script with a small DOM model; no browser or network.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const source = fs.readFileSync(new URL('../apps/workbench/standards_page.py', import.meta.url), 'utf8');
const script = source.match(/NAVIGATION_SCRIPT = r"""([\s\S]*?)"""/)[1];
let passed = 0;
function test(name, run) { run(); passed++; console.log(`ok ${passed} - ${name}`); }

function fixture({referrer = 'http://localhost:8769/', length = 2, hash = '', ids = ['scope', 'inputs', 'detail', 'evaluation']} = {}) {
  const events = new Map(), windowEvents = new Map(), frames = [];
  const calls = {back: 0, assigned: [], printed: 0};
  const makeNode = (extra = {}) => ({nodeType: 1, isContentEditable: false, closest: () => null, ...extra});
  const button = () => {
    const handlers = new Map();
    return makeNode({handlers, addEventListener: (name, fn) => handlers.set(name, fn)});
  };
  const back = button(), print = button();
  const rootBranch = {open: true, dataset: {}, parentElement: null};
  const chapterBranch = {open: false, dataset: {tocSection: ids[0]}, parentElement: {closest: () => rootBranch}};
  const clauseBranch = {open: false, dataset: {tocSection: ids[1]}, parentElement: {closest: () => chapterBranch}};
  const links = ids.map((id, i) => {
    const node = button(), attrs = new Map();
    return Object.assign(node, {dataset: {tocLink: id}, attrs,
      closest: selector => selector === 'details' ? (i === 0 ? chapterBranch : i < 3 ? clauseBranch : rootBranch) : null,
      setAttribute: (name, value) => attrs.set(name, value), removeAttribute: name => attrs.delete(name)});
  });
  const positions = ids.map((_, i) => 200 + i * 200);
  const headings = ids.map((id, i) => ({id, getBoundingClientRect: () => ({top: positions[i]})}));
  const location = {origin: 'http://localhost:8769', hash,
    href: 'http://localhost:8769/standards' + hash, assign: value => calls.assigned.push(value)};
  const history = {length, back: () => calls.back++};
  const document = {referrer, activeElement: null, documentElement: {scrollHeight: 3000},
    getElementById: id => id === 'return-workbench' ? back : print,
    querySelectorAll: selector => selector === '[data-toc-link]' ? links : headings,
    querySelector: () => ({getBoundingClientRect: () => ({bottom: 90})}),
    addEventListener: (name, fn) => events.set(name, fn)};
  const window = {scrollY: 0, innerHeight: 900, print: () => calls.printed++,
    addEventListener: (name, fn) => windowEvents.set(name, fn)};
  vm.runInNewContext(script, {document, window, location, history, URL,
    requestAnimationFrame: fn => frames.push(fn)}, {filename: 'standards-navigation.js'});
  const event = (extra = {}) => ({key: 'q', altKey: true, ctrlKey: false, metaKey: false,
    shiftKey: false, repeat: false, target: makeNode(), prevented: false,
    preventDefault() { this.prevented = true; }, ...extra});
  const key = extra => { const e = event(extra); events.get('keydown')(e); return e; };
  const click = extra => { const e = event({altKey: false, ...extra}); back.handlers.get('click')(e); return e; };
  const flush = () => { while (frames.length) frames.shift()(); };
  return {document, window, location, history, calls, events, windowEvents, frames,
    back, print, links, positions, rootBranch, chapterBranch, clauseBranch, key, click, flush, makeNode};
}

test('Alt+Q on the initial entry uses real history back to preserve workbench state', () => {
  const f = fixture();
  assert.equal(f.key().prevented, true);
  assert.equal(f.calls.back, 1);
  assert.deepEqual(f.calls.assigned, []);
});
test('Direct visits, external referrers, other document referrers and empty history use root fallback', () => {
  for (const options of [{referrer: ''}, {referrer: 'https://elsewhere.test/'},
    {referrer: 'http://localhost:8769/standards'}, {length: 1}, {referrer: 'not a URL'}]) {
    const f = fixture(options); f.key();
    assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, ['/']);
  }
});
test('Hash navigation cannot turn the workbench shortcut into previous-clause navigation', () => {
  const f = fixture();
  f.location.hash = '#inputs'; f.location.href += '#inputs'; f.history.length++;
  f.windowEvents.get('hashchange')();
  f.location.hash = '#detail'; f.location.href = 'http://localhost:8769/standards#detail'; f.history.length++;
  f.windowEvents.get('hashchange')(); f.key();
  assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, ['/']);
});
test('Either a changed href or changed history length conservatively uses root fallback', () => {
  for (const change of [f => f.location.href += '#inputs', f => f.history.length++]) {
    const f = fixture(); change(f); f.click();
    assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, ['/']);
  }
});
test('Normal return link uses the same guard while modified clicks remain native', () => {
  const f = fixture(); assert.equal(f.click().prevented, true); assert.equal(f.calls.back, 1);
  for (const modifier of ['altKey', 'ctrlKey', 'metaKey', 'shiftKey']) {
    const g = fixture(); assert.equal(g.click({[modifier]: true}).prevented, false);
    assert.equal(g.calls.back, 0); assert.deepEqual(g.calls.assigned, []);
  }
});
test('Keyboard handling requires Alt+Q and refuses modified or repeated shortcuts', () => {
  for (const extra of [{altKey: false}, {key: 'x'}, {ctrlKey: true}, {metaKey: true}, {shiftKey: true}, {repeat: true}]) {
    const f = fixture(); assert.equal(f.key(extra).prevented, false); assert.equal(f.calls.back, 0);
  }
  const f = fixture(); f.key({key: 'Q'}); assert.equal(f.calls.back, 1);
});
test('Inputs, editable ancestors, active controls and shadow composed paths suppress the shortcut', () => {
  for (const kind of ['input', 'textarea', 'select', '[role="textbox"]', 'contenteditable']) {
    const f = fixture();
    const target = f.makeNode({closest: selector => { assert.ok(selector.includes(kind)); return {}; }});
    assert.equal(f.key({target}).prevented, false); assert.equal(f.calls.back, 0);
  }
  for (const place of ['target', 'active', 'path', 'text']) {
    const f = fixture(), editable = f.makeNode({isContentEditable: true}), extra = {};
    if (place === 'active') f.document.activeElement = editable;
    else if (place === 'path') extra.composedPath = () => [editable];
    else if (place === 'text') extra.target = {nodeType: 3, parentElement: editable};
    else extra.target = editable;
    f.key(extra); assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, []);
  }
});
test('All IME signals suppress return until composition ends', () => {
  for (const extra of [{isComposing: true}, {keyCode: 229}]) {
    const f = fixture(); assert.equal(f.key(extra).prevented, false); assert.equal(f.calls.back, 0);
  }
  const f = fixture(); f.events.get('compositionstart')(); f.key(); assert.equal(f.calls.back, 0);
  f.events.get('compositionend')(); f.key(); assert.equal(f.calls.back, 1);
});
test('Print invokes the browser print operation without navigation', () => {
  const f = fixture(); f.print.handlers.get('click')();
  assert.equal(f.calls.printed, 1); assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, []);
});
test('Scroll selects the current clause and expands its actual ancestor branches', () => {
  const f = fixture(); f.positions.splice(0, 4, -200, -100, 90, 500); f.flush();
  assert.equal(f.links[2].attrs.get('aria-current'), 'location');
  assert.equal(f.links.filter(link => link.attrs.has('aria-current')).length, 1);
  assert.equal(f.chapterBranch.open, true); assert.equal(f.clauseBranch.open, true);
  f.positions.splice(0, 4, -300, -200, -100, 80); f.windowEvents.get('scroll')(); f.flush();
  assert.equal(f.links[3].attrs.get('aria-current'), 'location');
  assert.equal(f.links[2].attrs.has('aria-current'), false);
  assert.equal(f.chapterBranch.open, false); assert.equal(f.clauseBranch.open, false);
  assert.equal(f.location.hash, ''); assert.equal(f.history.length, 2);
});
test('Initial chapter overview remains compact instead of exposing all subordinate clauses', () => {
  const f = fixture(); f.flush();
  assert.equal(f.links[0].attrs.get('aria-current'), 'location');
  assert.equal(f.rootBranch.open, true);
  assert.equal(f.chapterBranch.open, false); assert.equal(f.clauseBranch.open, false);
});
test('Only necessary ancestors open for section selection and manual expansions remain available', () => {
  const f = fixture(); f.links[1].handlers.get('click')();
  assert.equal(f.chapterBranch.open, true); assert.equal(f.clauseBranch.open, false);
  const g = fixture(); g.chapterBranch.open = true;
  g.positions.splice(0, 4, -200, -100, 90, 500); g.flush();
  assert.equal(g.clauseBranch.open, true);
  g.positions.splice(0, 4, -300, -200, -100, 80); g.windowEvents.get('scroll')(); g.flush();
  assert.equal(g.chapterBranch.open, true); assert.equal(g.clauseBranch.open, false);
});
test('Scroll updates are frame-throttled and bottom of page selects the final clause', () => {
  const f = fixture();
  f.windowEvents.get('scroll')(); f.windowEvents.get('resize')(); assert.equal(f.frames.length, 1);
  f.window.scrollY = 2100; f.flush();
  assert.equal(f.links.at(-1).attrs.get('aria-current'), 'location');
});
test('Encoded Chinese anchors, clicked clauses and malformed fragments are handled safely', () => {
  const f = fixture({ids: ['范围', '输入'], hash: '#%E8%BE%93%E5%85%A5'});
  assert.equal(f.links[1].attrs.get('aria-current'), 'location');
  f.links[0].handlers.get('click')(); assert.equal(f.links[0].attrs.get('aria-current'), 'location');
  f.location.hash = '#%invalid'; assert.doesNotThrow(() => f.windowEvents.get('hashchange')());
  f.flush(); assert.equal(f.calls.back, 0); assert.deepEqual(f.calls.assigned, []);
});
test('A page with no secondary headings retains return and print operations', () => {
  const f = fixture({ids: []}); assert.doesNotThrow(f.flush); f.key(); assert.equal(f.calls.back, 1);
});

console.log(`${passed} document navigation contracts passed; no browser or network used.`);

// Direct visits must retain the selected ECoG route and language.
for (const href of ['/?modality=ecog', '/?modality=ecog&lang=en']) {
  const f = fixture({referrer: ''}); f.back.getAttribute = () => href;
  f.click(); assert.deepEqual(f.calls.assigned, [href]);
}
console.log('ECoG direct-return routes preserve modality and language.');
