'use strict';

function expandFigure(hash) {
  const panel = document.getElementById(hash.slice(1));
  if (!panel?.matches('.chart-group, details.panel')) return;
  // Retain existing shared links while normal browsing uses nested disclosures.
  for (let node = panel; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') node.open = true;
  }
  if (panel.matches('.chart-group')) {
    const first = panel.querySelector('details.panel');
    if (first) first.open = true;
  }
  panel.scrollIntoView({block:'start'});
}

if (window.location.hash) expandFigure(window.location.hash);
window.addEventListener('hashchange', () => expandFigure(window.location.hash));

// Let the surrounding report scroll as one document, including expanded plots.
if (document.documentElement.classList.contains('embedded-charts') && window.parent !== window) {
  const main = document.querySelector('main');
  const reportHeight = () => window.parent.postMessage({type:'qc-chart-height',height:Math.ceil(main.getBoundingClientRect().height)+16},window.location.origin);
  new ResizeObserver(reportHeight).observe(main);
  window.addEventListener('load', reportHeight);
  reportHeight();
}

// Replace saved-evidence charts in place. A failed refresh leaves the old plots visible.
const chartMain = document.querySelector('main');
let refreshing = false;
chartMain?.addEventListener('change', event => {
  const form = event.target.closest('form.controls');
  if (!form || refreshing) return;
  form.dataset.update = 'changed';
  form.querySelector('.chart-update-status').textContent = '点击刷新以应用';
});
chartMain?.addEventListener('submit', async event => {
  const form = event.target.closest('form.controls');
  if (!form) return;
  event.preventDefault();
  if (refreshing) return;
  const target = new URL(form.action, window.location.href);
  if (target.origin !== window.location.origin) return;
  target.search = new URLSearchParams(new FormData(form)).toString();
  const open = new Map([...chartMain.querySelectorAll('details[id]')].map(node => [node.id,node.open]));
  const optionsOpen = form.querySelector('.display-options')?.open;
  const button = form.querySelector('.chart-refresh');
  const status = form.querySelector('.chart-update-status');
  refreshing = true;
  form.setAttribute('aria-busy','true');
  form.dataset.update = 'loading';
  button.disabled = true;
  button.querySelector('span').textContent = '更新中';
  status.textContent = '正在读取图表';
  const controls = [...form.querySelectorAll('input, select')];
  controls.forEach(node => {node.disabled = true;});
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), 30000);
  try {
    const response = await fetch(target, {signal:timeout.signal, credentials:'same-origin'});
    if (!response.ok) throw new Error('chart response');
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const next = page.querySelector('main');
    if (!next?.querySelector('form.controls')) throw new Error('chart content');
    chartMain.replaceChildren(...next.childNodes);
    for (const [id,expanded] of open) {
      const node = document.getElementById(id);
      if (node?.tagName === 'DETAILS') node.open = expanded;
    }
    const updated = chartMain.querySelector('form.controls');
    updated.querySelector('.display-options').open = Boolean(optionsOpen);
    updated.dataset.update = 'done';
    updated.querySelector('.chart-update-status').textContent = '已更新';
    updated.querySelector('.chart-refresh').focus({preventScroll:true});
    window.history.replaceState(null,'',target.pathname+target.search+window.location.hash);
  } catch (error) {
    form.dataset.update = 'error';
    status.textContent = '未更新，请重试';
    button.querySelector('span').textContent = '重试';
    button.disabled = false;
    controls.forEach(node => {node.disabled = false;});
    form.removeAttribute('aria-busy');
  } finally {
    clearTimeout(timer);
    refreshing = false;
  }
});
