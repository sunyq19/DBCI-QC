(() => {
  'use strict';
  const box = document.getElementById('temporary-session');
  if (!box) return;
  // Also relocate markup served by an older process, without restarting it
  // and discarding an in-progress temporary upload or report.
  const anchor = document.getElementById('data-library-error');
  if (!anchor) {box.remove(); return;}
  anchor.before(box);
  const en = () => document.documentElement.lang.startsWith('en') || new URLSearchParams(location.search).get('lang') === 'en';
  const t = (zh, english) => en() ? english : zh;
  let active = false, finishing = false;
  function render() {
    box.hidden = !active;
    box.replaceChildren();
    if (!active) return;
    const text = document.createElement('span');
    text.textContent = t('仅本浏览器可见，请在到期前下载报告。', 'Only visible in this browser. Download reports before expiry.');
    box.append(text);
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'text-button';
    button.textContent = t('清理本次上传', 'Clear session'); button.disabled = finishing;
    button.addEventListener('click', async () => {
      if (!confirm(t('清理当前浏览器本次会话的全部上传、报告和运行记录？请先下载需要保留的报告。', 'Clear all uploads, reports and run records in this browser session? Download any reports you need first.'))) return;
      finishing = true; render();
      try {
        const response = await fetch('/api/v1/temporary-session/finish', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
        if (!response.ok) throw Error();
        for (const key of Object.keys(sessionStorage)) if (key.startsWith('ephys-qc') || key.startsWith('qc.')) sessionStorage.removeItem(key);
        location.replace('/');
      } catch {
        finishing = false; render();
        alert(t('清理暂未完成，请重试。', 'Cleanup could not be completed. Please retry.'));
      }
    });
    box.append(button);
  }
  async function refresh() {
    try {
      const response = await fetch('/api/v1/temporary-session', {cache:'no-store'});
      if (!response.ok) return;
      const data = await response.json();
      active = Boolean(data.policy && data.active); render();
    } catch { /* The workbench connection status handles service outages. */ }
  }
  window.addEventListener('qc:temporary', refresh);
  window.addEventListener('qc:languagechange', render);
  window.QCTemporarySession = {refresh};
  refresh(); setInterval(refresh, 30000);
})();
