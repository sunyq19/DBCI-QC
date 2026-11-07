'use strict';

function expandFigure(hash) {
  const panel = document.getElementById(hash.slice(1));
  if (panel?.matches('details.panel')) {
    panel.open = true;
    panel.scrollIntoView({block:'start'});
  }
}

document.querySelectorAll('[data-panel-link]').forEach(link => {
  link.addEventListener('click', () => expandFigure(link.hash));
});
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
