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
