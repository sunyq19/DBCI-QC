/* Run titles are presentation metadata, separate from file names and QC settings. */
(() => {
  function suggest(label, scope='recording', stamp=new Date(), language='zh-CN') {
    const stem=Array.from(String(label || (language==='en'?'Data':'数据')).replace(/\.(edf|bdf|vhdr|set|fif|nwb|bin|meta|zip)$/i,'').replace(/[\p{Cc}\p{Cf}\p{Cs}]/gu,'')).slice(0,72).join('');
    const kind=({recording:['整份检查','Full recording'],window:['片段检查','Window check'],dataset:['资料检查','Dataset check']})[scope] || ['质检','QC'];
    const pad=n=>String(n).padStart(2,'0'), d=new Date(stamp);
    return `${stem} · ${kind[language==='en'?1:0]} · ${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
  window.QCRunNames={suggest};
})();
