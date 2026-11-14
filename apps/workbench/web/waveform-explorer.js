'use strict';

// Small native-clock viewer; changes the viewport only, never detector evidence.
(function(root) {
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt=x=>Number(x).toFixed(2).replace(/\.?0+$/,'');
  function viewport(start,span,segment) {
    span=Math.min(Math.max(span,.001),segment.stop_seconds-segment.start_seconds);
    return {start:clamp(start,segment.start_seconds,segment.stop_seconds-span),span};
  }
  function pan(state,pixels,width,segment) {
    return viewport(state.start-pixels/Math.max(width,1)*state.span,state.span,segment);
  }
  function zoom(state,span,segment,anchor=.5) {
    return viewport(state.start+(state.span-span)*clamp(anchor,0,1),span,segment);
  }
  function navigation(state,segment,previous) {
    const a=segment.start_seconds,b=Math.max(a,segment.stop_seconds-state.span);
    // Keep the rail stable between gestures; its scale follows the view, not
    // the recording duration. Moving past its ends reveals the next stretch.
    if(previous&&previous.span===state.span&&state.start>=previous.min&&state.start<=previous.max)return previous;
    const length=Math.min(b-a,state.span*4);
    const min=clamp(state.start-length/2,a,b-length);
    return {min,max:min+length,step:Math.max(.001,state.span/1000),span:state.span};
  }
  function scales(channels) {
    const ranges={};
    for(const c of channels) {
      const r=ranges[c.unit]||(ranges[c.unit]=[Infinity,-Infinity]);
      for(const v of c.values)if(Number.isFinite(v)){r[0]=Math.min(r[0],v);r[1]=Math.max(r[1],v);}
    }
    for(const unit of Object.keys(ranges)) {
      let [a,b]=ranges[unit];
      if(!Number.isFinite(a)){a=-1;b=1;}
      const pad=Math.max((b-a)*.06,Math.max(Math.abs(a),Math.abs(b))*.01)||1;
      ranges[unit]=[a-pad,b+pad];
    }
    return ranges;
  }
  function plotHeight(channelCount,available=270) {
    return Math.max(240,available,channelCount*44+35);
  }
  function plotLayout(channels,width=800) {
    const longest=Math.max(3,...(channels||[]).map(c=>String(c.name||'').length));
    const nameWidth=Math.min(Math.max(30,longest*7.5),Math.max(30,Math.min(170,width*.28)));
    const left=nameWidth+60,right=10;
    return {left,right,nameWidth,w:width-left-right};
  }
  function plot(wave,state,candidate,width=800,height=270,annotations=null) {
    const {left,right,nameWidth,w}=plotLayout(wave.channels,width),top=8,bottom=27;
    const n=wave.channels.length,row=(height-top-bottom)/n;
    const ranges=scales(wave.channels),x=t=>left+(t-state.start)/state.span*w;
    let out=`<defs><clipPath id="wave-label-clip"><rect x="0" y="0" width="${nameWidth}" height="${height}"/></clipPath><clipPath id="wave-clip"><rect x="${left}" y="0" width="${w}" height="${height-bottom}"/></clipPath></defs>`;
    for(let j=0;j<=5;j++) {
      const t=state.start+state.span*j/5,px=x(t);
      out+=`<line x1="${px}" x2="${px}" y1="${top}" y2="${height-bottom}" stroke="#edf1f6"/><text x="${px}" y="${height-7}" text-anchor="middle" class="wave-tick">${fmt(t)}</text>`;
    }
    wave.channels.forEach((c,i)=>{
      const y0=top+i*row+5,h=row-14,[lo,hi]=ranges[c.unit];
      const y=v=>y0+h-(v-lo)/(hi-lo)*h,selected=c.channel_id===candidate.id;
      const marks=annotations===null ? (selected?[{start:candidate.start,stop:candidate.stop,color:'#f8e4bc',method:'selected',label:'候选区间',localization:'interval'}]:[]) : annotations.filter(r=>r.channels.includes(c.channel_id)&&r.stop>state.start&&r.start<state.start+state.span);
      const timed=marks.filter(r=>r.localization==='interval');
      const types=[...new Set(timed.map(r=>r.method))];
      for(const r of timed){
        const a=clamp(x(r.start),left,width-right),b=clamp(x(r.stop),left,width-right);
        if(b<=a)continue;
        const lane=types.indexOf(r.method),stripe=Math.min(3,Math.max(1,h*.24/Math.max(1,types.length)));
        out+=`<g data-mark-channel="${esc(c.channel_id)}" data-mark-method="${esc(r.method)}"><title>${esc(r.label)} · ${fmt(r.start)}–${fmt(r.stop)} s</title><rect x="${a}" y="${y0}" width="${b-a}" height="${h}" fill="${r.color}" fill-opacity="${annotations===null?1:.10}"/><rect x="${a}" y="${y0+h-(lane+1)*(stripe+1)}" width="${b-a}" height="${stripe}" fill="${r.color}"/></g>`;
      }
      // Aggregate channel findings have no localized time. Keep them in the
      // channel-results list, never paint a dot or interval on the waveform.
      out+=`<text x="4" y="${y0+13}" clip-path="url(#wave-label-clip)" class="wave-channel-name" fill="${selected?'#2459bc':'#42546b'}"><title>${esc(c.name)}</title>${esc(c.name)}</text>`;
      out+=`<text x="4" y="${y0+26}" class="wave-unit">${esc(c.unit)}</text>`;
      // All lanes of the same unit use exactly the same amplitude range.
      out+=`<text x="${left-5}" y="${y0+8}" text-anchor="end" class="wave-scale">${Number(hi).toPrecision(3)}</text><text x="${left-5}" y="${y0+h}" text-anchor="end" class="wave-scale">${Number(lo).toPrecision(3)}</text>`;
      if(lo<0&&hi>0)out+=`<line x1="${left}" x2="${width-right}" y1="${y(0)}" y2="${y(0)}" stroke="#e1e7ef"/>`;
      let d='',pen=false;
      c.values.forEach((v,k)=>{
        if(!Number.isFinite(v)){pen=false;return;}
        d+=(pen?'L':'M')+x(c.times_seconds[k]).toFixed(2)+','+y(v).toFixed(2);pen=true;
      });
      out+=`<path d="${d}" clip-path="url(#wave-clip)" stroke="${selected?'#2459bc':'#586d87'}" fill="none" stroke-width=".8" vector-effect="non-scaling-stroke"/>`;
      out+=`<line x1="${left}" x2="${width-right}" y1="${y0+h+5}" y2="${y0+h+5}" stroke="#e6ebf2"/>`;
    });
    if(annotations){
      const aggregate=annotations.filter(r=>r.localization==='group_interval'&&r.channels.some(id=>wave.channels.some(c=>c.channel_id===id))&&r.stop>state.start&&r.start<state.start+state.span);
      const types=[...new Set(aggregate.map(r=>r.method))];
      for(const r of aggregate){const a=clamp(x(r.start),left,width-right),b=clamp(x(r.stop),left,width-right);
        out+=`<rect data-group-mark="${esc(r.method)}" x="${a}" y="${types.indexOf(r.method)*3}" width="${Math.max(0,b-a)}" height="2" fill="${r.color}"><title>${esc(r.label)} · 通道组区间，未定位单道</title></rect>`;
      }
    }
    return out;
  }
  function comparisonIndices(finding,channels,limit=15){
    const ids=new Set((finding?.comparison?.neighbors||[]).map(r=>r.channel_id));
    return channels.filter(c=>ids.has(c.channel_id)).map(c=>c.source_index).slice(0,limit-1);
  }
  const api={viewport,pan,zoom,navigation,scales,plot,plotHeight,plotLayout,comparisonIndices};
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root.document)return;
  root.QCWaveformGeometry=api;
  const doc=root.document,panel=doc.getElementById('finding-preview');
  if(!panel?.dataset.waveformBase)return;
  const $=id=>doc.getElementById(id),t=(zh,en)=>doc.documentElement.lang==='en'?en:zh;
  const base=panel.dataset.waveformBase;let links=[...doc.querySelectorAll('[data-finding]')];
  const filters=$('finding-filters');let locationIndex=null,activeMethods=new Set(),annotations=null,activeLocation=null,listPage=0,locationKind='interval',extrasOpen=false;
  const stage=panel.querySelector('.finding-stage'),controls=$('wave-controls'),notice=$('wave-notice');
  const image=$('finding-image'),status=$('finding-status'),spanLabel=$('wave-span'),position=$('wave-position');
  const comparisonNote=doc.createElement('div');comparisonNote.className='finding-comparison';comparisonNote.hidden=true;
  controls.before(comparisonNote);
  const svg=doc.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.id='wave-plot';svg.setAttribute('role','img');svg.setAttribute('tabindex','0');
  svg.setAttribute('aria-label',t('波形对照；左右拖动或使用方向键查看前后','Aligned waveforms; drag or use arrow keys to pan'));
  svg.setAttribute('hidden','');stage.append(svg);
  let info,stream,segment,candidate,state,wave,selected=[],comparisons=[],sequence=0,drag,inFlight=false,pending=false;
  let sliding=false,nav,loadTimer;
  const cache=new Map();
  function message(text=''){notice.textContent=text;notice.hidden=!text;}
  function activity(mode,text='') {
    panel.dataset.state=mode;panel.setAttribute('aria-busy',String(mode==='loading'));status.textContent=text;
  }
  function render() {
    if(!wave||!state)return;
    const width=Math.max(320,stage.clientWidth||800),height=plotHeight(wave.channels.length,stage.clientHeight||270);
    svg.style.height=`${height}px`;
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    svg.innerHTML=plot(wave,state,candidate,width,height,annotations)+`<g id="wave-cursor" visibility="hidden" pointer-events="none"><line y1="8" y2="${height-27}" stroke="#91a5c3" stroke-dasharray="3 3"/><text y="${height-30}" class="wave-tick" text-anchor="end"></text></g>`;
  }
  function sync() {
    $('wave-range').textContent=`${fmt(state.start)}–${fmt(state.start+state.span)} s`;
    if(!sliding)nav=navigation(state,segment,nav);
    position.min=nav.min;position.max=nav.max;position.step=nav.step;
    position.value=state.start;position.disabled=Number(position.max)===Number(position.min);
    position.style.setProperty('--wave-thumb-width',`${Math.max(16,(position.clientWidth||240)*state.span/(nav.max-nav.min+state.span))}px`);
    position.setAttribute('aria-valuetext',`${fmt(state.start)}–${fmt(state.start+state.span)} s`);
    $('wave-segment-start').textContent=`${fmt(nav.min)} s`;
    $('wave-segment-end').textContent=`${fmt(nav.max+state.span)} s`;
    spanLabel.textContent=`${fmt(state.span)} s`;
    const bounds=spanBounds();
    $('wave-zoom-in').disabled=state.span<=bounds.min+1e-6;
    $('wave-zoom-out').disabled=state.span>=bounds.max-1e-6;
    $('wave-prev').disabled=state.start<=segment.start_seconds+1e-6;
    $('wave-next').disabled=state.start+state.span>=segment.stop_seconds-1e-6;
    $('wave-channel-count').textContent=`${selected.length} / ${info.limits.max_channels}`;
  }
  function spanBounds() {
    const max=Math.min(info.limits.max_seconds,segment.stop_seconds-segment.start_seconds,
      Math.floor(info.limits.max_read_bytes/(selected.length*8))/stream.sampling_rate_hz);
    return {min:Math.min(1,max),max};
  }
  function sizes(desired=state?.span||10) {
    const bounds=spanBounds();return clamp(desired,bounds.min,bounds.max);
  }
  async function readJSON(url,signal) {
    const response=await fetch(url,{signal,cache:'no-store'});
    if(!response.ok)throw new Error('waveform-unavailable');
    return response.json();
  }
  function invalidate() {
    ++sequence;pending=false;clearTimeout(loadTimer);
  }
  async function load() {
    invalidate();const token=sequence;
    if(info?.waveform_available===false){
      wave=null;svg.setAttribute('hidden','');image.hidden=true;controls.hidden=true;
      activity('unavailable',t('此服务未配置对应的示例信号文件。','This server has no waveform source configured for this example.'));
      message(t('已保存的检查位置仍可筛选；报告与图表不受影响。','Saved locations remain filterable; reports and figures are available.'));
      return;
    }
    activity('loading',t('正在载入波形…','Loading waveforms…'));message();sync();
    // One read at a time. Repeated navigation replaces the next request instead
    // of starting concurrent native reads that an HTTP abort cannot cancel.
    if(inFlight){pending=true;return;}
    inFlight=true;
    const query=new URLSearchParams({start_seconds:state.start.toFixed(6),duration_seconds:state.span.toFixed(6),
      channel_indices:selected.join(','),max_points:'2000'});
    const key=query.toString();
    try {
      const data=cache.get(key)||await readJSON(`${base}/waveform-window?${key}`);
      if(token!==sequence)return;
      if(!data.frozen_source_verified||!data.channels?.length)throw new Error('unverified');
      if(cache.size>=12)cache.delete(cache.keys().next().value);cache.set(key,data);
      wave=data;
      image.hidden=true;svg.removeAttribute('hidden');panel.dataset.waveReady='true';
      render();sync();activity('ready');
      const checked=info.checked_range;
      if(checked&&Number.isFinite(checked.duration_seconds)&&(state.start<checked.start_seconds-1e-6||state.start+state.span>checked.start_seconds+checked.duration_seconds+1e-6))
        message(t('当前视窗包含本次检查范围以外的原始波形。','This view includes original signal outside the checked interval.'));
    }catch(error) {
      if(token!==sequence||error.name==='AbortError')return;
      activity('error',t('该时段暂不能读取。可重试，或查看已保存的候选波形。','This interval is unavailable. Retry or view the saved candidate.'));
      message(t('调整时间或通道后可重试；报告和已保存的波形仍保留。','Adjust time or channels to retry; the saved report remains available.'));
      const retry=doc.createElement('button'),saved=doc.createElement('a');
      retry.type='button';retry.textContent=t('重试','Retry');retry.addEventListener('click',load);
      saved.href=links.find(l=>l.getAttribute('aria-current')==='true')?.href||image.src;
      saved.textContent=t('查看保存片段','Saved snapshot');saved.target='_blank';saved.rel='noopener';
      notice.append(retry);if(saved.href&&!saved.href.endsWith('#review')&&!saved.href.endsWith('#locations'))notice.append(saved);
    }finally {
      inFlight=false;
      if(pending&&!drag){pending=false;load();}
    }
  }
  function channelMenu() {
    const search=$('wave-search').value.trim().toLowerCase(),container=$('wave-channel-options');
    container.replaceChildren();
    for(const c of stream.channels.filter(c=>c.name.toLowerCase().includes(search))) {
      const label=doc.createElement('label'),box=doc.createElement('input'),text=doc.createElement('span');
      box.type='checkbox';box.checked=selected.includes(c.source_index);
      box.disabled=c.channel_id===candidate.id||(!box.checked&&selected.length>=info.limits.max_channels);
      text.textContent=c.name+(c.channel_id===candidate.id?t(' · 候选',' · Candidate'):'');
      box.addEventListener('change',()=>{
        comparisons=box.checked?[...comparisons,c.source_index]:comparisons.filter(i=>i!==c.source_index);
        selected=[candidate.source,...comparisons.filter(i=>i!==candidate.source)].slice(0,info.limits.max_channels);
        state=zoom(state,sizes(),segment);channelMenu();load();
      });
      label.append(box,text);container.append(label);
    }
  }
  function select(link) {
    if(!info||!link)return false;
    const id=link.dataset.channelId;
    const next=info.streams.find(s=>s.channels.some(c=>c.channel_id===id));
    const start=Number(link.dataset.start),stop=Number(link.dataset.stop);
    const seg=next?.segments.find(s=>s.start_seconds<=start&&start<s.stop_seconds);
    if(!next||!seg||!Number.isFinite(start)||!Number.isFinite(stop)){
      invalidate();controls.hidden=true;svg.setAttribute('hidden','');image.hidden=false;
      delete panel.dataset.waveReady;delete panel.dataset.interactive;
      panel.closest('.finding-workspace').classList.remove('has-waveform-explorer');
      message(t('该候选未匹配到可浏览的原始通道，展示保存片段。','Channel unavailable for browsing; showing the saved snapshot.'));
      return false;
    }
    const c=next.channels.find(c=>c.channel_id===id);
    if(stream?.stream_id!==next.stream_id)comparisons=[];
    stream=next;segment=seg;candidate={id,source:c.source_index,start,stop};
    const finding=locationIndex?.findings.find(r=>r.id===link.dataset.locationId);
    if(finding?.comparison?.neighbors?.length)comparisons=comparisonIndices(finding,stream.channels,info.limits.max_channels);
    sliding=false;nav=null;
    comparisons=comparisons.filter(i=>i!==c.source_index&&stream.channels.some(c=>c.source_index===i));
    selected=[c.source_index,...comparisons].slice(0,info.limits.max_channels);
    const channelOnly=link.dataset.localization==='channel';
    const span=sizes(channelOnly?10:Math.max(10,Math.min(30,stop-start+4)));
    state=viewport(channelOnly?start:start+(Math.min(stop-start,span)-span)/2,span,segment);
    $('finding-title').textContent=link.dataset.title;$('finding-measure').textContent=link.dataset.measure;
    $('finding-position').textContent=link.dataset.position;
    links.forEach(l=>l.setAttribute('aria-current',String(l===link)));
    controls.hidden=false;panel.closest('.finding-workspace').classList.add('has-waveform-explorer');
    panel.dataset.interactive='ready';if(link.href&&!link.dataset.locationId)image.src=link.href;else image.removeAttribute('src');image.alt=link.dataset.title;
    channelMenu();load();return true;
  }
  root.qcWaveformViewer={select};
  function move(direction) {
    state=viewport(state.start+direction*state.span*.5,state.span,segment);load();
  }
  function rescale(factor,anchor=.5) {
    if(!state||drag)return;
    const next=zoom(state,sizes(state.span*factor),segment,anchor);
    if(next.start===state.start&&next.span===state.span)return;
    invalidate();state=next;nav=null;
    activity('moving');sync();render();
    loadTimer=setTimeout(load,120);
  }
  $('wave-prev').addEventListener('click',()=>move(-1));$('wave-next').addEventListener('click',()=>move(1));
  $('wave-reset').addEventListener('click',()=>{
    state=viewport((candidate.start+candidate.stop)/2-state.span/2,state.span,segment);nav=null;load();
  });
  $('wave-zoom-in').addEventListener('click',()=>rescale(.5));
  $('wave-zoom-out').addEventListener('click',()=>rescale(2));
  position.addEventListener('input',()=>{
    sliding=true;invalidate();state=viewport(clamp(Number(position.value),nav.min,nav.max),state.span,segment);activity('moving');sync();render();
  });
  position.addEventListener('change',()=>{
    sliding=false;
    if(state.start<=nav.min+nav.step||state.start>=nav.max-nav.step)nav=null;
    load();
  });
  $('wave-channels-toggle').addEventListener('click',()=>{
    const menu=$('wave-channel-menu');menu.hidden=!menu.hidden;
    $('wave-channels-toggle').setAttribute('aria-expanded',String(!menu.hidden));
    if(!menu.hidden)$('wave-search').focus();
  });
  $('wave-search').addEventListener('input',channelMenu);
  doc.addEventListener('click',e=>{
    if(!e.target.closest('.wave-channel-picker')){
      $('wave-channel-menu').hidden=true;$('wave-channels-toggle').setAttribute('aria-expanded','false');
    }
  });
  doc.addEventListener('keydown',e=>{if(e.key==='Escape'){
    $('wave-channel-menu').hidden=true;$('wave-channels-toggle').setAttribute('aria-expanded','false');
  }});
  svg.addEventListener('keydown',e=>{
    if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();move(e.key==='ArrowLeft'?-1:1);}
    if(['+','=','-'].includes(e.key)){e.preventDefault();rescale(e.key==='-'?2:.5);}
  });
  svg.setAttribute('title',t('左右拖动查看前后；滚轮放大或缩小时间范围','Drag to pan; scroll to zoom the time range'));
  svg.addEventListener('wheel',e=>{
    if(!state||drag||e.ctrlKey||e.metaKey)return;
    e.preventDefault();
    const rect=svg.getBoundingClientRect(),width=Math.max(320,stage.clientWidth||800);
    const layout=plotLayout(wave?.channels,width);
    const anchor=((e.clientX-rect.left)/rect.width*width-layout.left)/layout.w;
    const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?rect.height:1);
    rescale(Math.exp(clamp(delta,-160,160)*.003),anchor);
  },{passive:false});
  svg.addEventListener('pointerdown',e=>{
    if(e.button!==0||!state)return;
    invalidate();drag={x:e.clientX,state:{...state}};
    svg.focus({preventScroll:true});
    svg.setPointerCapture(e.pointerId);svg.classList.add('is-dragging');
  });
  svg.addEventListener('pointermove',e=>{
    if(!drag){
      const cursor=$('wave-cursor');
      if(cursor&&state){
        const rect=svg.getBoundingClientRect(),width=Math.max(320,stage.clientWidth||800);
        const layout=plotLayout(wave?.channels,width);
        const px=clamp((e.clientX-rect.left)/rect.width*width,layout.left,width-10);
        cursor.setAttribute('visibility','visible');
        const line=cursor.querySelector('line'),text=cursor.querySelector('text');
        line.setAttribute('x1',px);line.setAttribute('x2',px);
        text.setAttribute('x',Math.max(120,px-5));text.textContent=fmt(state.start+(px-layout.left)/layout.w*state.span)+' s';
      }
      return;
    }
    state=pan(drag.state,e.clientX-drag.x,plotLayout(wave?.channels,Math.max(320,stage.clientWidth||800)).w,segment);
    activity('moving');sync();render();
  });
  function endDrag(e) {
    if(!drag)return;drag=null;svg.classList.remove('is-dragging');
    if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);load();
  }
  svg.addEventListener('pointerup',endDrag);svg.addEventListener('pointercancel',endDrag);
  svg.addEventListener('pointerleave',()=>{$('wave-cursor')?.setAttribute('visibility','hidden');});
  if(root.ResizeObserver)new ResizeObserver(()=>{if(state)sync();render();}).observe(stage);
  const inspector=panel.closest('.finding-inspector'),fullButton=$('finding-fullscreen');
  let expanded=false,previousOverflow='',focusBeforeExpand=null;
  function fullscreenState(on){
    if(!inspector||expanded===on)return;
    expanded=on;
    if(on){previousOverflow=doc.body.style.overflow;focusBeforeExpand=doc.activeElement;doc.body.style.overflow='hidden';}
    else{doc.body.style.overflow=previousOverflow;}
    inspector.classList.toggle('finding-is-fullscreen',on);
    fullButton.setAttribute('aria-pressed',String(on));
    fullButton.setAttribute('title',on?t('退出全屏（Esc）','Exit full screen (Esc)'):t('全屏查看问题定位','Expand review locations'));
    fullButton.querySelector('span').textContent=on?t('退出全屏','Exit full screen'):t('全屏','Full screen');
    if(on)fullButton.focus({preventScroll:true});else (focusBeforeExpand||fullButton).focus({preventScroll:true});
    if(state)sync();render();
  }
  async function leaveFullscreen(){
    if(doc.fullscreenElement===inspector&&doc.exitFullscreen){
      try{await doc.exitFullscreen();}catch{/* Viewport fallback can still close. */}
    }
    fullscreenState(false);
  }
  if(inspector&&fullButton){
    fullButton.addEventListener('click',async()=>{
      if(expanded){await leaveFullscreen();return;}
      fullscreenState(true);
      if(inspector.requestFullscreen){
        try{await inspector.requestFullscreen();}catch{/* Remain expanded within the page. */}
      }
    });
    doc.addEventListener('fullscreenchange',()=>{
      if(doc.fullscreenElement===inspector)fullscreenState(true);
      else if(expanded)fullscreenState(false);
    });
    doc.addEventListener('keydown',e=>{
      if(!expanded)return;
      if(e.key==='Escape'){e.preventDefault();leaveFullscreen();return;}
      if(e.key!=='Tab')return;
      const focusable=[...inspector.querySelectorAll('button,input,a[href],[tabindex="0"]')].filter(el=>!el.disabled&&!el.hidden&&el.getClientRects().length);
      if(!focusable.length)return;
      const first=focusable[0],last=focusable[focusable.length-1];
      if(e.shiftKey&&doc.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey&&doc.activeElement===last){e.preventDefault();first.focus();}
    });
  }
  function selectedLocations(){
    return (locationIndex?.findings||[]).filter(r=>activeMethods.has(r.method));
  }
  function visibleLocations(){
    const search=($('finding-search')?.value||'').trim().toLowerCase();
    const names=new Map(locationIndex.channels.map(c=>[c.id,c.name]));
    return selectedLocations().filter(r=>(r.localization==='channel')===(locationKind==='channel')&&
      (!search||r.channels.some(id=>(names.get(id)||'').toLowerCase().includes(search))));
  }
  function clearLocation(){
    activeLocation=null;
    comparisonNote.hidden=true;
    $('finding-title').textContent=t('波形浏览','Waveform');
    $('finding-measure').textContent=t('当前筛选下没有选中的检查结果。','No finding selected under these filters.');
  }
  function refreshLocations(){
    listPage=0;updateAnnotations();
    const selected=selectedLocations();
    if(!selected.some(r=>(r.localization==='channel')===(locationKind==='channel'))&&selected.length)
      locationKind=selected[0].localization==='channel'?'channel':'interval';
    const rows=visibleLocations();
    if(!rows.some(r=>r.id===activeLocation)){
      if(rows.length){chooseLocation(rows[0]);return;}
      clearLocation();
    }
    renderLocationList();
  }
  function updateAnnotations(){
    const methods=new Map(locationIndex.methods.map(m=>[m.id,m]));
    annotations=selectedLocations().map(r=>({...r,color:methods.get(r.method).color,label:t(methods.get(r.method).label,methods.get(r.method).label_en)}));
    render();
  }
  function chooseLocation(row){
    activeLocation=row.id;
    const ids=row.channels,channel=info?.streams.flatMap(s=>s.channels).find(c=>ids.includes(c.channel_id));
    const method=locationIndex.methods.find(m=>m.id===row.method),names=new Map(locationIndex.channels.map(c=>[c.id,c.name]));
    const label=t(method.label,method.label_en);
    const scope=row.localization==='channel'?t('通道级结果','Channel-level finding'):row.localization==='group_interval'?t('通道组异常区间','Channel-group interval'):t('异常区间','Flagged interval');
    const title=(row.localization==='group_interval'?t('通道组','Channel group'):ids.map(id=>names.get(id)||id).join(' / '))+' · '+label;
    const proxy={dataset:{channelId:channel?.channel_id||ids[0],start:String(row.start),stop:String(row.stop),title,
      measure:(row.localization==='channel'?t('分析范围 ','Analysis range ')+`${fmt(row.start)}–${fmt(row.stop)} s · `:'')+scope+(row.localization==='channel'?'':` · ${fmt(row.start)}–${fmt(row.stop)} s`),position:'',localization:row.localization,locationId:row.id},href:''};
    $('finding-title').textContent=title;$('finding-measure').textContent=proxy.dataset.measure;
    comparisonNote.replaceChildren();comparisonNote.hidden=row.localization!=='channel';
    if(row.localization==='channel'){
      const note=doc.createElement('p');
      note.textContent=t('本项判断通道整体特征，不能据此认定每一秒都异常。','This check evaluates the channel as a whole; it does not identify abnormal moments.');
      comparisonNote.append(note);
      const evidence=row.comparison;
      if(evidence?.kind==='lf_neighborhood'){
        const summary=doc.createElement('div');summary.className='finding-comparison-summary';
        summary.textContent=t(`判定：邻域一致性低于 ${evidence.threshold??'—'} · 同一针柄 ${evidence.radius_um} μm 内`,
          `Decision: neighborhood agreement below ${evidence.threshold??'—'} · same shank, within ${evidence.radius_um} μm`);
        comparisonNote.prepend(summary);
        const neighbors=doc.createElement('div');neighbors.className='finding-neighbors';
        const label=doc.createElement('span');label.textContent=t('判定邻居','Detector neighbors');neighbors.append(label);
        for(const n of evidence.neighbors){
          const tag=doc.createElement('span');tag.className='finding-neighbor'+(n.label==='noise'?' is-flagged':'');
          tag.textContent=n.name+(n.label==='noise'?t(' · 也被标记',' · flagged'):'');tag.title=`${n.distance_um} μm`;neighbors.append(tag);
        }
        if(!evidence.neighbors.length)neighbors.append(t('未保存可用的邻域位置','No usable saved neighbor positions'));
        comparisonNote.append(neighbors);
        const detail=doc.createElement('details'),head=doc.createElement('summary'),body=doc.createElement('p');
        head.textContent=t('判定说明','Decision details');
        body.textContent=t('逐个抽样窗口比较本通道与邻居的中位波形，取相关系数的中位数后平方（R²）。原版接口仅保存分类，未保存逐通道 R²；下方波形用于人工对照，不是该统计量。',
          'The detector compares each sampled chunk with the median neighbor trace, then squares the median correlation (R²). The original interface saved labels, not per-channel R². The waveforms below are for visual review, not that statistic.');
        detail.append(head,body);comparisonNote.append(detail);
      }
    }
    if(!select(proxy)){
      invalidate();wave=null;svg.setAttribute('hidden','');image.hidden=true;controls.hidden=true;
      activity('error',t('该位置的原始波形暂不可用。检测位置仍保留。','Original waveform unavailable; saved locations remain listed.'));
    }
    renderLocationList();
  }
  function renderLocationList(){
    const list=panel.closest('.finding-workspace').querySelector('.finding-list');
    const names=new Map(locationIndex.channels.map(c=>[c.id,c.name]));
    const methods=new Map(locationIndex.methods.map(m=>[m.id,m]));
    const rows=visibleLocations();
    const notice=$('finding-index-notice');notice.hidden=!locationIndex.warnings.some(r=>activeMethods.has(r.method));
    notice.textContent=t('部分所选检查缺少完整定位信息；完整计数见检查结果。','Some selected checks have incomplete locations; see results for full counts.');
    const kinds=$('finding-kinds');kinds.replaceChildren();
    for(const [kind,label,en] of [['interval','异常时段','Intervals'],['channel','通道比较','Channels']]){
      const count=selectedLocations().filter(r=>(r.localization==='channel')===(kind==='channel')).length;
      const button=doc.createElement('button');button.type='button';button.dataset.kind=kind;
      button.textContent=t(label,en)+` ${count}`;button.setAttribute('aria-pressed',String(locationKind===kind));
      button.addEventListener('click',()=>{locationKind=kind;listPage=0;const first=visibleLocations()[0];if(first)chooseLocation(first);else{clearLocation();renderLocationList();}});kinds.append(button);
    }
    const size=40,pages=Math.max(1,Math.ceil(rows.length/size));listPage=Math.min(listPage,pages-1);
    list.replaceChildren();links=[];
    for(const row of rows.slice(listPage*size,(listPage+1)*size)){
      const m=methods.get(row.method),button=doc.createElement('button');button.type='button';button.className='finding-item finding-location';
      button.setAttribute('aria-current',String(row.id===activeLocation));button.dataset.locationId=row.id;
      const name=row.localization==='group_interval'?t('通道组','Channel group'):row.channels.map(id=>names.get(id)||id).join(' / ');
      const time=(row.localization==='channel'?t('检查范围 ','Checked '):'')+fmt(row.start)+'–'+fmt(row.stop)+' s';
      const marker=row.localization==='channel'?'':`<i style="background:${m.color}"></i>`;
      button.innerHTML=`<span class="finding-item-top"><strong>${esc(name)}</strong><span>${time}</span></span><small>${marker}${esc(t(m.label,m.label_en))}</small>`;
      button.addEventListener('click',()=>chooseLocation(row));list.append(button);
    }
    if(!rows.length){const note=doc.createElement('p');note.className='finding-empty';note.textContent=!locationIndex.findings.length?t('本次未记录可定位的异常候选。','No localized findings were recorded.'):activeMethods.size?t('当前筛选下没有已保存的位置。','No saved locations match these filters.'):t('已隐藏全部标记。','All annotations are hidden.');list.append(note);}
    const paging=$('finding-pagination');paging.replaceChildren();
    const prev=doc.createElement('button'),next=doc.createElement('button'),counter=doc.createElement('span');
    prev.type=next.type='button';prev.textContent='‹';next.textContent='›';prev.setAttribute('aria-label',t('上一页候选','Previous findings'));next.setAttribute('aria-label',t('下一页候选','Next findings'));
    prev.disabled=listPage===0;next.disabled=listPage===pages-1;counter.textContent=rows.length?`${listPage+1} / ${pages} · ${rows.length}`:'0';
    prev.addEventListener('click',()=>{listPage--;renderLocationList();list.scrollTop=0;});next.addEventListener('click',()=>{listPage++;renderLocationList();list.scrollTop=0;});paging.append(prev,counter,next);
  }
  function renderFilters(){
    filters.replaceChildren();
    const heading=doc.createElement('div');heading.className='finding-filter-heading';
    const title=doc.createElement('strong');title.textContent=t('候选检查项','Checks with findings');heading.append(title);
    const all=doc.createElement('button'),none=doc.createElement('button');all.type=none.type='button';all.textContent=t('全部显示','Show all');none.textContent=t('全部隐藏','Hide all');
    function apply(){renderFilters();refreshLocations();}
    all.addEventListener('click',()=>{activeMethods=new Set(locationIndex.default_method_ids);apply();});none.addEventListener('click',()=>{activeMethods.clear();apply();});heading.append(all,none);filters.append(heading);
    function optionsFor(methods){
      const options=doc.createElement('div');options.className='finding-filter-options';
      for(const m of methods){
        const timed=locationIndex.findings.some(r=>r.method===m.id&&r.localization!=='channel');
        const label=doc.createElement('label'),box=doc.createElement('input'),text=doc.createElement('span');box.type='checkbox';box.checked=activeMethods.has(m.id);box.dataset.method=m.id;box.style.accentColor=timed?m.color:'#2459bc';
        text.innerHTML=(timed?`<i style="background:${m.color}"></i>`:'')+`${esc(t(m.label,m.label_en))}<small>${m.location_count}${m.unavailable_blocks?t(' · 部分未读取',' · incomplete'):''}</small>`;
        box.addEventListener('change',()=>{if(box.checked)activeMethods.add(m.id);else activeMethods.delete(m.id);refreshLocations();});label.append(box,text);options.append(label);
      }
      return options;
    }
    const primary=new Set(locationIndex.default_method_ids);
    filters.append(optionsFor(locationIndex.methods.filter(m=>primary.has(m.id))));
    const others=locationIndex.methods.filter(m=>!primary.has(m.id));
    if(others.length){
      const extra=doc.createElement('details'),summary=doc.createElement('summary');extra.className='finding-extra-checks';extra.open=extrasOpen;
      summary.textContent=t('无定位结果的检查','Checks without locations')+` · ${others.length}`;
      extra.addEventListener('toggle',()=>{extrasOpen=extra.open;});extra.append(summary,optionsFor(others));
      filters.append(extra);
    }
  }
  function startLocations(data){
    locationIndex=data;data.default_method_ids??=data.methods.filter(m=>data.findings.some(r=>r.method===m.id)).map(m=>m.id);activeMethods=new Set(data.default_method_ids);
    const workspace=panel.closest('.finding-workspace');
    if(!data.findings.length){
      renderFilters();workspace.hidden=true;
      if(fullButton)fullButton.hidden=true;
      const empty=doc.createElement('p');empty.className='finding-empty';
      empty.textContent=t('本次未记录异常区间或通道候选。','No interval or channel findings were recorded.');filters.append(empty);return;
    }
    const sidebar=workspace.querySelector('.finding-sidebar');
    const kinds=doc.createElement('div');kinds.id='finding-kinds';kinds.className='finding-kinds';kinds.setAttribute('aria-label',t('定位类型','Finding scope'));sidebar.append(kinds);
    const search=doc.createElement('input');search.type='search';search.id='finding-search';search.placeholder=t('筛选通道','Filter channels');search.setAttribute('aria-label',search.placeholder);search.addEventListener('input',refreshLocations);
    sidebar.querySelector('.finding-list-label').replaceChildren(search);
    const pagination=doc.createElement('div');pagination.id='finding-pagination';pagination.className='finding-pagination';sidebar.append(pagination);
    const old=links.find(l=>l.getAttribute('aria-current')==='true');
    renderFilters();updateAnnotations();renderLocationList();
    const rows=selectedLocations();
    const first=rows.find(r=>r.localization!=='channel'&&r.channels.includes(old?.dataset.channelId)&&r.start<=Number(old.dataset.start)&&r.stop>=Number(old.dataset.stop))||rows.find(r=>r.localization!=='channel')||rows[0];
    if(first)locationKind=first.localization==='channel'?'channel':'interval';
    if(first)chooseLocation(first);else{clearLocation();image.hidden=true;activity('ready',t('本次没有已保存的候选位置。','No candidate locations were saved for this run.'));}
  }
  const contextPromise=readJSON(`${base}/waveform-context`).then(data=>{info=data;return true;}).catch(()=>false);
  if(filters){
    Promise.all([contextPromise,readJSON(`${base}/finding-locations`)]).then(([,data])=>{
      const caption=panel.querySelector('.finding-caption');
      if(caption)caption.textContent=t('同单位使用相同幅度刻度','Same amplitude scale for matching units');
      startLocations(data);
    }).catch(()=>{
      filters.textContent=t('检查位置暂未载入','Locations could not be loaded');
      const retry=doc.createElement('button');retry.type='button';retry.textContent=t('重试','Retry');retry.addEventListener('click',()=>root.location.reload());filters.append(retry);
      if(info)select(links.find(l=>l.getAttribute('aria-current')==='true')||links[0]);
      message(t('当前仅展示保存的少量示例，不代表完整候选。','Only saved examples are shown, not the complete findings.'));
    });
  }else contextPromise.then(ok=>{
    if(ok)select(links.find(l=>l.getAttribute('aria-current')==='true')||links[0]);
    else message(t('原始记录暂不可用，当前展示已保存的候选波形。','Original recording unavailable; showing the saved candidate waveform.'));
  });
})(typeof window==='undefined'?globalThis:window);
