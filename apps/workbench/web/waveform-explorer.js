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
  function plot(wave,state,candidate,width=800,height=270) {
    const left=74,right=10,top=8,bottom=27,w=width-left-right;
    const n=wave.channels.length,row=(height-top-bottom)/n;
    const ranges=scales(wave.channels),x=t=>left+(t-state.start)/state.span*w;
    let out=`<defs><clipPath id="wave-clip"><rect x="${left}" y="0" width="${w}" height="${height-bottom}"/></clipPath></defs>`;
    for(let j=0;j<=5;j++) {
      const t=state.start+state.span*j/5,px=x(t);
      out+=`<line x1="${px}" x2="${px}" y1="${top}" y2="${height-bottom}" stroke="#edf1f6"/><text x="${px}" y="${height-7}" text-anchor="middle" class="wave-tick">${fmt(t)}</text>`;
    }
    wave.channels.forEach((c,i)=>{
      const y0=top+i*row+5,h=row-14,[lo,hi]=ranges[c.unit];
      const y=v=>y0+h-(v-lo)/(hi-lo)*h,selected=c.channel_id===candidate.id;
      const a=clamp(x(candidate.start),left,width-right),b=clamp(x(candidate.stop),left,width-right);
      if(selected&&b>a)out+=`<rect x="${a}" y="${y0}" width="${b-a}" height="${h}" fill="#f8e4bc"/>`;
      out+=`<text x="4" y="${y0+13}" class="wave-channel-name" fill="${selected?'#2459bc':'#42546b'}">${esc(c.name)}</text>`;
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
    return out;
  }
  const api={viewport,pan,zoom,navigation,scales,plot};
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(!root.document)return;
  root.QCWaveformGeometry=api;
  const doc=root.document,panel=doc.getElementById('finding-preview');
  if(!panel?.dataset.waveformBase)return;
  const $=id=>doc.getElementById(id),t=(zh,en)=>doc.documentElement.lang==='en'?en:zh;
  const base=panel.dataset.waveformBase,links=[...doc.querySelectorAll('[data-finding]')];
  const stage=panel.querySelector('.finding-stage'),controls=$('wave-controls'),notice=$('wave-notice');
  const image=$('finding-image'),status=$('finding-status'),spanLabel=$('wave-span'),position=$('wave-position');
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
    const width=Math.max(320,stage.clientWidth||800),height=Math.max(240,stage.clientHeight||270);
    svg.setAttribute('viewBox',`0 0 ${width} ${height}`);
    svg.innerHTML=plot(wave,state,candidate,width,height)+`<g id="wave-cursor" visibility="hidden" pointer-events="none"><line y1="8" y2="${height-27}" stroke="#91a5c3" stroke-dasharray="3 3"/><text y="${height-30}" class="wave-tick" text-anchor="end"></text></g>`;
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
      info.limits.max_read_bytes/(selected.length*stream.sampling_rate_hz*8));
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
      notice.append(retry,saved);
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
    if(!info)return false;
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
    sliding=false;nav=null;
    comparisons=comparisons.filter(i=>i!==c.source_index&&stream.channels.some(c=>c.source_index===i));
    selected=[c.source_index,...comparisons].slice(0,info.limits.max_channels);
    const span=sizes(Math.max(10,stop-start+4));
    state=viewport((start+stop)/2-span/2,span,segment);
    $('finding-title').textContent=link.dataset.title;$('finding-measure').textContent=link.dataset.measure;
    $('finding-position').textContent=link.dataset.position;
    links.forEach(l=>l.setAttribute('aria-current',String(l===link)));
    controls.hidden=false;panel.closest('.finding-workspace').classList.add('has-waveform-explorer');
    panel.dataset.interactive='ready';image.src=link.href;image.alt=link.dataset.title;
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
    const anchor=((e.clientX-rect.left)/rect.width*width-74)/(width-84);
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
        const px=clamp((e.clientX-rect.left)/rect.width*width,74,width-10);
        cursor.setAttribute('visibility','visible');
        const line=cursor.querySelector('line'),text=cursor.querySelector('text');
        line.setAttribute('x1',px);line.setAttribute('x2',px);
        text.setAttribute('x',Math.max(120,px-5));text.textContent=fmt(state.start+(px-74)/(width-84)*state.span)+' s';
      }
      return;
    }
    state=pan(drag.state,e.clientX-drag.x,Math.max(1,stage.clientWidth-84),segment);
    activity('moving');sync();render();
  });
  function endDrag(e) {
    if(!drag)return;drag=null;svg.classList.remove('is-dragging');
    if(svg.hasPointerCapture(e.pointerId))svg.releasePointerCapture(e.pointerId);load();
  }
  svg.addEventListener('pointerup',endDrag);svg.addEventListener('pointercancel',endDrag);
  svg.addEventListener('pointerleave',()=>{$('wave-cursor')?.setAttribute('visibility','hidden');});
  if(root.ResizeObserver)new ResizeObserver(()=>{if(state)sync();render();}).observe(stage);
  readJSON(`${base}/waveform-context`).then(data=>{
    info=data;select(links.find(l=>l.getAttribute('aria-current')==='true')||links[0]);
    const caption=panel.querySelector('.finding-caption');
    if(caption)caption.innerHTML='<span class="candidate-swatch" aria-hidden="true"></span>'+t('候选通道标记区间 · 同单位共用幅度刻度','Candidate channel interval · shared scale per unit')+'<span>'+t('原始时间（秒）','Recording time (s)')+'</span>';
  }).catch(()=>message(t('原始记录暂不可用，当前展示已保存的候选波形。','Original recording unavailable; showing the saved candidate waveform.')));
})(typeof window==='undefined'?globalThis:window);
