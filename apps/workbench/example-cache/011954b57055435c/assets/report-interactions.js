'use strict';

// Charts are a report section. Defer evidence reads until it is opened.
const chartSections = [...document.querySelectorAll('[data-report-charts]')];
chartSections.forEach(section => {
  const frame = section.querySelector('iframe');
  const status = section.querySelector('[data-chart-status]');
  section.addEventListener('toggle', () => {
    if (section.open && !frame.getAttribute('src')) frame.src = frame.dataset.chartSrc;
  });
  frame.addEventListener('load', () => {
    if (frame.getAttribute('src')) status.hidden = true;
  });
});
window.addEventListener('message', event => {
  if (event.origin !== location.origin || event.data?.type !== 'qc-chart-height') return;
  const height = event.data.height;
  if (!Number.isFinite(height) || height < 1 || height > 100000) return;
  for (const section of chartSections) {
    const frame = section.querySelector('iframe');
    if (event.source === frame.contentWindow) frame.style.height = Math.ceil(height) + 'px';
  }
});

// Links still open the selected image if JavaScript is unavailable.
let findingRequest = 0;
document.querySelectorAll('[data-finding]').forEach(link => {
  link.addEventListener('click', event => {
    const image = document.getElementById('finding-image');
    const panel = document.getElementById('finding-preview');
    const status = document.getElementById('finding-status');
    if (!image || !panel || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const request = ++findingRequest, pending = new Image();
    status.textContent = '正在载入波形…';
    // Show the loading state at the preview immediately, even below a long table.
    panel.scrollIntoView({block:'nearest', behavior:'instant'});
    const oldText = link.dataset.idleLabel || (link.dataset.idleLabel = link.textContent);
    link.textContent = '载入中…';
    document.querySelectorAll('.finding-table .is-selected').forEach(row => row.classList.remove('is-selected'));
    link.closest('tr')?.classList.add('is-selected');
    pending.onload = () => {
      link.textContent = oldText;
      if (request !== findingRequest) return;
      image.src = pending.src;
      image.alt = link.dataset.title;
      document.getElementById('finding-title').textContent = link.dataset.title;
      status.textContent = '';
      panel.scrollIntoView({block:'nearest', behavior:'instant'});
    };
    pending.onerror = () => {
      link.textContent = oldText;
      if (request === findingRequest) status.textContent = '此段波形暂不可用，通道与时间位置仍见上表。';
    };
    pending.src = link.href;
  });
});

// Anchor links must reveal their target when it lives inside a closed disclosure.
function revealReportTarget(hash) {
  const target = document.getElementById((typeof hash === 'string' ? hash : location.hash).slice(1));
  if (!target) return;
  for (let node = target; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') node.open = true;
  }
  target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange', revealReportTarget);
document.querySelectorAll('a[href^="#"]').forEach(link => {
  link.addEventListener('click', () => revealReportTarget(link.hash));
});
if (location.hash) revealReportTarget();
