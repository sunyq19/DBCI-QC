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
