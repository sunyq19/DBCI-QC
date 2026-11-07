'use strict';

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
    status.textContent = '正在读取该通道的波形…';
    document.querySelectorAll('.finding-table .is-selected').forEach(row => row.classList.remove('is-selected'));
    link.closest('tr')?.classList.add('is-selected');
    pending.onload = () => {
      if (request !== findingRequest) return;
      image.src = pending.src;
      image.alt = link.dataset.title;
      document.getElementById('finding-title').textContent = link.dataset.title;
      status.textContent = '';
      panel.scrollIntoView({block:'nearest', behavior:'instant'});
    };
    pending.onerror = () => {
      if (request === findingRequest) status.textContent = '此段波形暂不可用，通道与时间位置仍见上表。';
    };
    pending.src = link.href;
  });
});

// Anchor links must reveal their target when it lives inside a closed disclosure.
function revealReportTarget() {
  const target = document.getElementById(location.hash.slice(1));
  if (!target) return;
  for (let node = target; node; node = node.parentElement) {
    if (node.tagName === 'DETAILS') node.open = true;
  }
  target.scrollIntoView({block:'start'});
}
window.addEventListener('hashchange', revealReportTarget);
if (location.hash) revealReportTarget();
