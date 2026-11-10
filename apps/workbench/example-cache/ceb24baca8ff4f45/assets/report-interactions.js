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

// A stable inspector pairs each candidate with its waveform.
let findingRequest = 0;
const findingLinks = [...document.querySelectorAll('[data-finding]')];
const findingImage = document.getElementById('finding-image');
const findingPanel = document.getElementById('finding-preview');
const findingStatus = document.getElementById('finding-status');
const reportText = (zh,en) => document.documentElement?.lang === 'en' ? en : zh;
function findingState(state, message='') {
  if(!findingPanel || !findingStatus)return;
  findingPanel.dataset.state=state;
  findingPanel.setAttribute('aria-busy', String(state==='loading'));
  findingStatus.textContent=message;
}
if(findingImage && findingPanel && !document.getElementById('finding-filters')) {
  findingImage.addEventListener('load',()=>{if(!findingRequest&&findingPanel.dataset.interactive!=='ready')findingState('ready');});
  findingImage.addEventListener('error',()=>{if(!findingRequest&&findingPanel.dataset.interactive!=='ready')findingState('error',reportText('波形暂不可用，请重新选择。','Waveform unavailable. Select a finding again.'));});
  if(!findingImage.complete)findingState('loading',reportText('正在载入波形…','Loading waveform…'));
  else if(!findingImage.naturalWidth)findingState('error',reportText('波形暂不可用，请重新选择。','Waveform unavailable. Select a finding again.'));
}
findingLinks.forEach(link => {
  link.addEventListener('click', event => {
    if (!findingImage || !findingPanel || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const request = ++findingRequest, pending = new Image();
    document.getElementById('finding-title').textContent = link.dataset.title;
    const measure=document.getElementById('finding-measure'),position=document.getElementById('finding-position');
    if(measure)measure.textContent=link.dataset.measure||'';
    if(position)position.textContent=link.dataset.position||'';
    findingState('loading',reportText('正在载入波形…','Loading waveform…'));
    findingLinks.forEach(other=>other.setAttribute('aria-current',String(other===link)));
    if(window.qcWaveformViewer?.select(link))return;
    // Scroll only when selecting; a late image must never pull the page away.
    if(window.matchMedia?.('(max-width: 760px)')?.matches)findingPanel.scrollIntoView({block:'nearest',behavior:'instant'});
    pending.onload = () => {
      if(request !== findingRequest||findingPanel.dataset.interactive==='ready')return;
      findingImage.src=pending.src;findingImage.alt=link.dataset.title;
      findingState('ready');
    };
    pending.onerror = () => {
      if(request === findingRequest&&findingPanel.dataset.interactive!=='ready')findingState('error',reportText('此段波形未能载入，请重新点击或选择其他候选。','Could not load this waveform. Retry or select another finding.'));
    };
    pending.src=link.href;
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
