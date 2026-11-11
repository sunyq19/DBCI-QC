(() => {
  'use strict';
  const box = document.getElementById('temporary-session');
  if (!box) return;
  const en = () => document.documentElement.lang.startsWith('en') || new URLSearchParams(location.search).get('lang') === 'en';
  const t = (zh, english) => en() ? english : zh;
  let active = false, finishing = false;
  function render() {
    box.hidden = false;
    box.style.cssText = 'margin:12px 0;padding:12px 16px;border-left:3px solid #2563eb;background:#f3f7fc;font:14px/1.6 system-ui;color:#334155';
    box.replaceChildren();
    const text = document.createElement('span');
    text.textContent = active
      ? t('本次上传仅当前浏览器可见。完成后 1 小时清理，请及时下载报告。', 'This upload is private to this browser. Download the report within 1 hour of completion.')
      : t('上传仅作临时检查，不加入“我的数据”。', 'Uploads are temporary and are not added to My Data.');
    box.append(text);
    if (!active) return;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'text-button';
    button.style.cssText = 'margin-left:12px;color:#1d4ed8;cursor:pointer';
    button.textContent = t('结束并清理', 'Finish and clear'); button.disabled = finishing;
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
      if (!data.policy) {box.hidden = true; return;}
      active = data.active; render();
    } catch { /* The workbench connection status handles service outages. */ }
  }
  window.addEventListener('qc:temporary', refresh);
  window.addEventListener('qc:languagechange', render);
  window.QCTemporarySession = {refresh};
  refresh(); setInterval(refresh, 30000);
})();
