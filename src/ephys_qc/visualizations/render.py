"""Read-only SVG/HTML presentation of stored QC evidence (no detector imports)."""
from html import escape
import json
import math
from urllib.parse import urlencode
from .catalog import VERSION, visualization_specs, LEI, GNOSIS, PROJECT

BANDS = ['delta','theta','alpha','beta','gamma']
BLUE, AMBER, INK, MUTED = '#2563eb', '#c77913', '#17324d', '#64748b'

def esc(x): return escape(str(x), quote=True)
def finite(x): return type(x) in (int,float) and math.isfinite(x)
def num(x): return f'{x:.3g}' if finite(x) else '未评'
def text(x,y,s,**attrs):
    a=' '.join(f'{k.replace("_","-")}="{esc(v)}"' for k,v in attrs.items())
    return f'<text x="{x}" y="{y}" {a}>{esc(s)}</text>'
def line(x1,y1,x2,y2,color='#e2e8f0',width=1):
    return f'<line x1="{x1:g}" y1="{y1:g}" x2="{x2:g}" y2="{y2:g}" stroke="{color}" stroke-width="{width}"/>'
def svg(body,h,title):
    return f'<svg role="img" aria-label="{esc(title)}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 {h}" style="font-family:system-ui,sans-serif;font-size:13px;fill:{INK}"><title>{esc(title)}</title>{body}</svg>'
def missing(reason): return f'<p class="empty">{esc(reason)}</p>'

def bars(rows,unit,*,limit=32,upper=None):
    """Rows are (channel, value, flag); all nonfinite/missing values stay missing."""
    if not rows:return missing('没有可显示的测量值。')
    rows=sorted(rows,key=lambda r:(not finite(r[1]),-r[1] if finite(r[1]) else 0,str(r[0])))
    count=len(rows);rows=rows[:limit];values=[v for _,v,_ in rows if finite(v)]
    if not values:return missing('测量值均未评，未将缺项画为零。')
    lo=min(0,min(values));hi=max(upper or 0,max(values),1e-12);span=hi-lo
    left,width=125,635;scale=lambda v:left+(v-lo)/span*width
    h=65+len(rows)*29;parts=[]
    for i in range(5):
        v=lo+span*i/4;x=scale(v);parts += [line(x,26,x,h-30),text(x,17,num(v),text_anchor='middle',fill=MUTED)]
    for i,(name,v,flag) in enumerate(rows):
        y=38+i*29;parts.append(text(112,y+14,name,text_anchor='end'))
        if finite(v):
            x0,x1=sorted((scale(0),scale(v)));color=AMBER if flag else BLUE
            parts.append(f'<rect x="{x0:g}" y="{y}" width="{max(0.6,x1-x0):g}" height="18" rx="3" fill="{color}"><title>{esc(name)}: {num(v)} {esc(unit)}</title></rect>')
        parts.append(text(775,y+14,num(v),fill=AMBER if flag else MUTED))
    parts.append(text(760,h-4,unit,text_anchor='end',fill=MUTED))
    return svg(''.join(parts),h,unit)+f'<p class="caption">{min(count,limit)} / {count} 道 · 按数值排序；橙色沿用候选标记。</p>'

def heatmap(rows,unit,*,limit=32,fixed_max=None,flags=()):
    if not rows:return missing('对应指标未生成。')
    cols=[b for b in BANDS+['full'] if any(r.get('band')==b for r in rows)]
    names=list(dict.fromkeys(r.get('channel_name') for r in rows)); count=len(names);names=names[:limit]
    table={(r.get('channel_name'),r.get('band')):r.get('value') for r in rows}
    vals=[v for v in table.values() if finite(v)]
    if not vals or not cols:return missing('对应指标没有有效数值。')
    upper=fixed_max if fixed_max is not None else max(vals)
    upper=max(upper,1e-12);cell=690/len(cols);parts=[]
    for j,b in enumerate(cols):parts.append(text(120+(j+.5)*cell,22,b,text_anchor='middle',fill=MUTED))
    for i,n in enumerate(names):
        y=35+i*30;parts.append(text(110,y+19,n,text_anchor='end',fill=AMBER if n in flags else INK))
        for j,b in enumerate(cols):
            v=table.get((n,b));ratio=max(0,min(1,v/upper)) if finite(v) else 0
            color=f'rgb({int(239-202*ratio)},{int(246-147*ratio)},{int(255-20*ratio)})' if finite(v) else '#f1f5f9'
            x=120+j*cell
            parts.append(f'<rect x="{x:g}" y="{y}" width="{cell-3:g}" height="27" rx="3" fill="{color}"/>')
            parts.append(text(x+cell/2,y+19,num(v),text_anchor='middle',fill='white' if ratio>.6 else INK))
    h=75+len(names)*30
    parts.append(text(120,h-8,f'色标：0 → {num(upper)} {unit} · 灰色/未评表示缺测',fill=MUTED))
    return svg(''.join(parts),h,unit)+f'<p class="caption">{len(names)} / {count} 道 · 保留输入通道顺序；颜色不代表质量得分。</p>'

def spectrum(frequencies,powers,names,factor):
    if not isinstance(frequencies,list) or not isinstance(powers,list):return missing('PSD 或频率轴缺失。')
    n=min(12,len(powers),len(names));curves=[]
    for name,values in zip(names[:n],powers[:n]):
        if not isinstance(values,list) or len(values)!=len(frequencies):continue
        points=[(f,10*math.log10(v*factor)) for f,v in zip(frequencies,values) if finite(f) and f>0 and finite(v) and v>0]
        if len(points)>1:curves.append((name,points))
    if not curves:return missing('没有有效的正频率 PSD。')
    xs=[p[0] for _,r in curves for p in r];ys=[p[1] for _,r in curves for p in r]
    xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
    if ymax==ymin:ymax=ymin+1
    sx=lambda x:65+(x-xmin)/(xmax-xmin)*775
    sy=lambda y:260-(y-ymin)/(ymax-ymin)*220
    parts=[text(65,18,'dB re μV²/Hz',fill=MUTED)]
    for i in range(5):
        x=xmin+(xmax-xmin)*i/4;y=ymin+(ymax-ymin)*i/4
        parts += [line(65,sy(y),840,sy(y)),text(55,sy(y)+4,num(y),text_anchor='end',fill=MUTED),text(sx(x),282,num(x),text_anchor='middle',fill=MUTED)]
    colors=['#2563eb','#0891b2','#7c3aed','#0f766e','#b45309','#475569']
    for i,(name,pts) in enumerate(curves):
        # Display-only subsampling; preserve endpoints and the saved numerical data.
        step=max(1,len(pts)//600);display=pts[::step]
        if display[-1]!=pts[-1]:display.append(pts[-1])
        coordinates=' '.join(f'{sx(x):.2f},{sy(y):.2f}' for x,y in display)
        parts.append(f'<polyline points="{coordinates}" fill="none" stroke="{colors[i%6]}" stroke-opacity=".7" stroke-width="1.4"><title>{esc(name)}</title></polyline>')
        parts.append(text(65+(i%6)*133,322+(i//6)*24,name,fill=colors[i%6]))
    parts.append(text(840,303,'Hz',text_anchor='end',fill=MUTED))
    return svg(''.join(parts),375,'通道功率谱密度')+f'<p class="caption">显示前 {n} / {len(names)} 道；悬停曲线查看通道。两条路线的处理和统计时段可能不同，不直接合并。</p>'

def timeline(candidates,start,stop,limit,total_count=None):
    rows=[c for c in candidates if finite(c.get('start_seconds')) and finite(c.get('stop_seconds')) and c['stop_seconds']>c['start_seconds']]
    if not rows:return missing('未检出带有效时间位置的候选区间。')
    if not finite(start) or not finite(stop) or stop<=start:return missing('原始记录时间范围未提供。')
    names=list(dict.fromkeys(c['channel_name'] for c in rows))[:limit]
    all_count=max(len(rows),total_count) if isinstance(total_count,int) else len(rows);rows=[c for c in rows if c['channel_name'] in names][:500]
    sx=lambda t:125+min(1,max(0,(t-start)/(stop-start)))*680;parts=[];h=65+len(names)*28
    for i in range(5):
        t=start+(stop-start)*i/4;x=sx(t);parts += [line(x,25,x,h-30),text(x,17,num(t),text_anchor='middle',fill=MUTED)]
    for i,n in enumerate(names):parts.append(text(112,45+i*28,n,text_anchor='end'))
    for c in rows:
        a,b=max(start,c['start_seconds']),min(stop,c['stop_seconds'])
        if b<=a:continue
        y=30+names.index(c['channel_name'])*28
        parts.append(f'<rect x="{sx(a):g}" y="{y}" width="{max(.8,sx(b)-sx(a)):g}" height="20" rx="3" fill="{AMBER}" opacity=".8"><title>{esc(c["channel_name"])}: {a:g}–{b:g} s</title></rect>')
    parts.append(text(805,h-4,'原始记录时间 / s',text_anchor='end',fill=MUTED))
    return svg(''.join(parts),h,'候选区间')+f'<p class="caption">显示 {len(rows)} / {all_count} 条候选；完整区间保存在检测证据中。</p>'

def ranges(rows,feature,band,limit):
    rows=[r for r in rows if r.get('feature')==feature and r.get('band')==band][:limit]
    rows=[r for r in rows if all(finite(r.get(k)) for k in ['low','high','value']) and r['low']<=r['high']]
    if not rows:return missing('此频带没有有效参考上下界。')
    lo=min(min(r['low'],r['value']) for r in rows);hi=max(max(r['high'],r['value']) for r in rows);pad=max((hi-lo)*.06,1e-12);lo-=pad;hi+=pad
    sx=lambda v:125+(v-lo)/(hi-lo)*650;parts=[];h=70+len(rows)*30
    for i in range(5):
        v=lo+(hi-lo)*i/4;x=sx(v);parts += [line(x,25,x,h-30),text(x,18,num(v),text_anchor='middle',fill=MUTED)]
    for i,r in enumerate(rows):
        y=40+i*30;flag=not r['low']<=r['value']<=r['high']
        parts += [text(112,y+5,r['channel_name'],text_anchor='end'),line(sx(r['low']),y,sx(r['high']),y,'#cbd5e1',8),f'<circle cx="{sx(r["value"]):g}" cy="{y}" r="5" fill="{AMBER if flag else BLUE}"><title>{r["value"]:g}; reference [{r["low"]:g}, {r["high"]:g}]</title></circle>',text(800,y+5,num(r['value']))]
    return svg(''.join(parts),h,feature+' '+band)+ '<p class="caption">灰线：参考范围 · 圆点：当前值 · 橙色：范围外。范围外不直接判为质量差。</p>'


def render_gallery(result,load,*,selected=None,window='',limit=32,band='alpha',asset_url=lambda n:n,back_url='',action='',embedded=False):
    """load(name) is a caller-provided allowlisted artifact reader. No path from a URL is opened here."""
    specs=visualization_specs();available={s['key'] for s in specs if s['status']=='available'}
    automatic=selected is None
    selected=[] if automatic else list(dict.fromkeys(selected))
    if set(selected)-available:raise ValueError('未知或尚未接入的可视化模块')
    if limit not in [16,32,64,128] or band not in BANDS:raise ValueError('图表参数无效')
    declared={a['name'] for a in result.get('artifacts',[])}
    windows=sorted({n[:-len('M02_selection.json')] for n in declared if n.endswith('M02_selection.json')}) or ['']
    if not window:window=windows[0]
    if window not in windows:raise ValueError('所选分析窗口不存在')
    cache={};errors=[]
    def evidence(stem):
        name=window+stem
        if name not in declared:return {}
        if name not in cache:
            try:
                cache[name]=load(name)
                if not isinstance(cache[name],dict):raise ValueError('invalid object')
            except (ValueError,TypeError,OSError,KeyError):cache[name]={};errors.append(name)
        return cache[name]
    def gnosis(key):
        module='M05' if key in ['line_length','psd_deviation'] else 'M06' if key in ['artifact','low_band','high_band'] else 'M04'
        d=evidence(f'{module}_gnosis_{key}.json')
        return d if d.get('status')=='completed' and d.get('calculated') is True else {}
    def metrics(key):return gnosis(key).get('metrics',{})
    def processing_note(data, *, spectral=False):
        """Explain saved input history without inferring an unrecorded preparation."""
        preparation=data.get('preprocessing',{})
        metric=data.get('metrics',{})
        selection=metric.get('spectral_input')
        selection_label={
            'artifact_complement':'避开候选伪差后的片段',
            'all_prepared_samples':'全部分析片段，未按伪差筛选',
        }.get(selection,'片段选择方式未记录')
        note='输入：预处理后的信号。' if data.get('input_unchanged') is True or preparation.get('source_unchanged') is True else '输入：灵犀云方法保存的分析结果。'
        if spectral:
            seconds=metric.get('effective_duration_seconds')
            note += f' 统计使用{selection_label}' + (f'，共 {seconds:g} 秒。' if finite(seconds) else '。')
        details={k:data[k] for k in ('preprocessing','parameters','notes') if data.get(k)}
        if spectral:
            details['spectral_input']=selection
            details['used_intervals']=metric.get('used_intervals')
        history=[]
        if finite(preparation.get('sampling_rate_hz')):
            history.append(f'分析采样率 {preparation["sampling_rate_hz"]:g} Hz')
        if all(finite(preparation.get(k)) for k in ('highpass_hz','lowpass_hz')):
            history.append(f'准备频带 {preparation["highpass_hz"]:g}–{preparation["lowpass_hz"]:g} Hz')
        if preparation.get('common_average') is True:history.append('准备时采用平均参考')
        if preparation.get('ica') is False:history.append('未使用 ICA')
        detail_html=('<details class="figure-details"><summary>处理与统计范围</summary>'
                     + (f'<p>{esc("；".join(history))}。</p>' if history else '')
                     + ('<p>多个片段按方法设置拼接计算，频谱曲线不用于定位原始时间。</p>' if spectral and selection=='artifact_complement' else '')
                     + f'<pre>{esc(json.dumps(details,ensure_ascii=False,indent=2))}</pre></details>') if details else ''
        return f'<p class="caption input-note">{esc(note)}</p>'+detail_html
    sources={}
    def section(title,body,source):
        if source == '连续电压':
            url='https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.welch.html'
            sources[url]='DBCI-QC 连续电压统计 / SciPy Welch'
        elif source == 'MNE':
            url='https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html'
            sources[url]='MNE annotate_amplitude'
        elif source in {'SpikeInterface','MNE spectrum_fit','FieldTrip','DBCI-QC / EDF'}:
            url={'SpikeInterface':'https://spikeinterface.readthedocs.io/en/0.104.2/api.html','MNE spectrum_fit':'https://mne.tools/stable/generated/mne.filter.notch_filter.html','FieldTrip':'https://www.fieldtriptoolbox.org/tutorial/preproc/automatic_artifact_rejection/','DBCI-QC / EDF':'https://www.edfplus.info/specs/edf.html'}[source]
            sources[url]=source
        elif source == 'DBCI-QC':
            sources[PROJECT]='DBCI-QC'
        else:
            url=GNOSIS if source=='灵犀云' else LEI
            sources[url]='GnosisNeuroDynamicSE' if url==GNOSIS else 'BrainElecQC / PREP'
        return f'<div class="figure"><div class="figure-head"><h3>{esc(title)}</h3></div>{body}</div>'
    def render(key):
        if key=='waveform':
            name=window+'waveform.png'
            if name not in declared:return missing('本窗口没有已保存的波形图；可返回报告查看候选波形。')
            return section('原始波形预览',f'<img class="waveform" src="{esc(asset_url(name))}" alt="已保存的原始波形预览"><p class="caption">起始最多15秒与前几个通道；展示范围以图中时间和通道为准。</p>','DBCI-QC')
        if key=='channel_metrics':
            d=evidence('M05_bad_channels.json');rows=d.get('channels',[]);out=''
            contacts=evidence('M05_channel_description.json').get('channels',[])
            for method,title in [('spikeinterface_coherence_psd','AP 通道分类'),('spikeinterface_lfp_neighbors','LF 邻域一致性候选')]:
                payload=evidence('M05_'+method+'.json')
                if payload.get('status')!='completed' or not payload.get('calculated'):continue
                labels=payload.get('channel_labels',[])
                mapping={c['adapter_name']:c.get('raw_name',c['adapter_name']) for c in payload.get('channel_mapping',[])}
                colors={'good':'#dce8f8','dead':'#b45309','noise':'#d97706','out':'#64748b'}
                names={'good':'未标记','dead':'失活候选','noise':'噪声候选','out':'组织外候选'}
                if method.endswith('lfp_neighbors'):names['noise']='低一致性候选'
                legend=' · '.join(names[k]+' '+str(sum(r.get('label')==k for r in labels)) for k in colors if any(r.get('label')==k for r in labels))
                parts=[]
                for i,row in enumerate(labels):
                    x=18+(i%16)*54;y=18+(i//16)*32;label=row.get('label');name=mapping.get(row.get('channel_name'),row.get('channel_name','—'))
                    parts.append(f'<rect x="{x}" y="{y}" width="48" height="25" rx="3" fill="{colors.get(label,"#f1f5f9")}"><title>{esc(name)}: {esc(names.get(label,label))}</title></rect>')
                    parts.append(text(x+24,y+17,name,text_anchor='middle',font_size='9',fill=INK if label=='good' else 'white'))
                out+=section(title,'<p class="caption">'+esc(legend)+'</p>'+svg(''.join(parts),45+math.ceil(len(labels)/16)*32,title)+'<p class="caption">按保存通道顺序排列；这是分类索引，不是解剖位置图。组织外候选默认不计分。</p>','SpikeInterface')
            if contacts:
                for field,label in [('rms_volts','触点 RMS'),('peak_to_peak_volts','触点峰峰值')]:
                    out+=section(label,bars([(c['channel_name'],c[field]*1e6 if finite(c.get(field)) else None,False) for c in contacts],'μV',limit=limit)+'<p class="caption">所选分析窗口的电压统计；幅度差异不直接判定为坏道。</p>','连续电压')
            if rows:
                for field,label,unit in [('robust_amplitude_uv','稳健幅值','μV'),('hf_ratio','高频残差比例','比例'),('low_correlation_fraction','低相关窗口占比','%')]:
                    out+=section(label,bars([(r['channel_name'],r.get(field)*100 if field=='low_correlation_fraction' and finite(r.get(field)) else r.get(field),bool(r.get('flags'))) for r in rows],unit,limit=limit),'雷佳欣 / PREP')
            g=gnosis('line_length')
            if g:
                flags={c['channel_name'] for c in g.get('candidates',[])}
                out+=section('平滑线长总量',processing_note(g)+bars([(k,v,k in flags) for k,v in g['metrics'].get('line_length_by_channel',{}).items()],'原版线长值',limit=limit),'灵犀云')
            return out or missing('先运行通道质量或灵犀云线长方法。')
        if key=='psd':
            out='';d=evidence('M04_spectral.json');p=d.get('psd',{});sel=evidence('M02_selection.json');mapping={c['channel_id']:c['raw_name'] for c in sel.get('channels',[])}
            if p.get('power_v2_hz'):
                names=[c.get('channel_name',c.get('channel_id','—')) for c in p['channels']] if 'channels' in p else [mapping.get(c,c) for c in p.get('channel_ids',[])]
                out+=section('原始输入 · Welch PSD','<p class="caption input-note">使用输入文件中的信号，此图不执行清洗。PSD 描述频率能量，不是质量分。</p>'+spectrum(p.get('frequencies_hz'),p.get('power_v2_hz'),names,1e12),'连续电压' if 'channels' in p else '雷佳欣')
            g=next((gnosis(k) for k in ['band_power','psd_deviation','reference_ranges'] if gnosis(k)),{})
            if g:
                p=g['metrics'];out+=section('分析副本 · Welch PSD',processing_note(g,spectral=True)+spectrum(p.get('frequencies_hz'),p.get('psd_uv2_hz'),g['channel_names'],1)+'<p class="caption">PSD 描述频率能量，不是质量分。处理和取样片段不同，不能将曲线更平滑直接解释为质量更好。</p>','灵犀云')
            return out or missing('先运行 PSD 相关检查。')
        if key=='interference':
            from ..report_view import line_summary
            payload=evidence('M04_spectral.json').get('line_noise',{})
            observations=payload.get('observations',[])
            mt=evidence('M04_ieeg_spectrum_fit.json');mt_html=''
            if mt.get('status')=='completed' and mt.get('calculated'):
                counts={}
                for row in mt.get('measurements',[]):
                    n=row['channel_name'];v=counts.setdefault(n,[0,0]);v[0]+=bool(row.get('detected_frequencies_hz'));v[1]+=1
                mt_html=section('多窗工频命中率',bars([(n,100*a/b,a>0) for n,(a,b) in counts.items() if b],'%',limit=limit,upper=100)+'<p class="caption">显著完整通道窗占比，不是工频幅度或污染时长。未检测尾段不补满分。</p>','MNE spectrum_fit')
            if any('band_power_v2' in c for c in observations):
                out=mt_html
                for hz in sorted({c['nominal_hz'] for c in observations if finite(c.get('nominal_hz'))}):
                    rows=[c for c in observations if c.get('nominal_hz')==hz]
                    out+=section(f'{hz:g} Hz 邻域功率',bars([(c['channel_name'],c['band_power_v2']*1e12 if c.get('status')=='computed' and finite(c.get('band_power_v2')) else None,False) for c in rows],'μV²',limit=limit)+'<p class="caption">窄带能量观察，未设置污染阈值；灰色未评不按零处理。</p>','连续电压')
                return out or missing('没有可测的工频邻域。')
            if mt_html and not payload:return mt_html
            d=line_summary(payload)
            return mt_html+section('工频命中窗 / 可评窗口',bars([(c['name'],c['percent'],bool(c['hits'])) for c in d['channels']],'%',limit=limit,upper=100),'雷佳欣')
        if key in ['artifact_burden','timeline']:
            out=''
            for m,label in [('artifact','伪差候选'),('low_band','低频异常'),('high_band','高频异常')]:
                g=gnosis(m)
                if not g:continue
                body=bars([(n,100*v if finite(v) else None,finite(v) and v>0) for n,v in g['metrics'].get('ratio_by_channel',{}).items()], '%',limit=limit,upper=100) if key=='artifact_burden' else timeline(g.get('candidates',[]),g.get('range',{}).get('start_seconds'),g.get('range',{}).get('stop_seconds'),limit)
                out+=section(label,processing_note(g)+body,'灵犀云')
            if key=='timeline':
                d=evidence('M06_muscle.json');rec=evidence('M02_selection.json').get('recording',{});start=rec.get('start_seconds');dur=rec.get('duration_seconds')
                if d:out+=section('高频突发候选',timeline(d.get('candidates',[]),start,start+dur if finite(start) and finite(dur) else None,limit,d.get('_visualization_candidate_count')),'雷佳欣')
                flat=evidence('M03_mne_amplitude.json')
                if flat.get('calculated', True) is True and flat.get('status')=='completed':
                    rows=[{**c,'channel_name':'所选通道合并'} for c in flat.get('candidates',[]) if c.get('localization')=='interval_only']
                    bounds=flat.get('range',{})
                    out+=section('平线 / 相邻变化候选' if flat.get('parameters',{}).get('peak_volts') is not None else '持续平线候选',timeline(rows,bounds.get('start_seconds'),bounds.get('stop_seconds'),limit)+'<p class="caption">时间标记是所选通道的合并区间。仅标记到通道的结果见报告检查明细。</p>','MNE')
                for filename,label,source in [('M03_ieeg_range_plateau.json','文件量程端点平台','DBCI-QC / EDF'),('M06_fieldtrip_zvalue.json','相邻跳变线索','FieldTrip'),('M04_ieeg_spectrum_fit.json','多窗工频候选','MNE spectrum_fit')]:
                    item=evidence(filename)
                    if item.get('calculated'):
                        bounds=item.get('range',{})
                        rows=[{**c,'channel_name':c.get('channel_name') or '所选通道合并'} for c in item.get('candidates',[])]
                        out+=section(label,timeline(rows,bounds.get('start_seconds'),bounds.get('stop_seconds'),limit),source)
            return out or missing('先运行对应的伪差或高频检查。')
        if key in ['band_power','band_amplitude','psd_distance']:
            method,field,unit={'band_power':('band_power','relative_power','%'),'band_amplitude':('band_amplitude','mean_amplitude_uv','μV'),'psd_distance':('psd_deviation','psd_distance','log10 PSD 距离')}[key]
            g=gnosis(method);rows=metrics(method).get(field,[])
            if key=='band_power':rows=[{**r,'value':r['value']*100 if finite(r.get('value')) else None} for r in rows]
            return section({'band_power':'相对频带功率','band_amplitude':'平均绝对幅值','psd_distance':'通道频谱距离'}[key],(processing_note(g,spectral=True) if g else '')+heatmap(rows,unit,limit=limit,fixed_max=100 if key=='band_power' else None,flags=[c['channel_name'] for c in g.get('candidates',[])]),'灵犀云')
        if key=='reference_ranges':
            rows=metrics('reference_ranges').get('reference_comparison',[])
            if not rows:return missing('先运行灵犀云参考分布对照。当前仅绘制区间；不生成虚构的群体密度曲线。')
            return processing_note(gnosis('reference_ranges'),spectral=True)+''.join(section(label+' · '+band,ranges(rows,f,band,limit),'灵犀云') for f,label in [('bpre','相对功率 / 比例'),('bpamp','幅值 / μV'),('psdist','PSD 距离')])
        return missing('尚未接入。')
    if automatic:
        if window+'waveform.png' in declared:selected.append('waveform')
        if any(window+'M05_'+k+'.json' in declared for k in ['spikeinterface_coherence_psd','spikeinterface_lfp_neighbors']) or evidence('M05_bad_channels.json').get('channels') or evidence('M05_channel_description.json').get('channels') or gnosis('line_length'):selected.append('channel_metrics')
        if window+'M04_spectral.json' in declared or gnosis('band_power') or gnosis('psd_deviation'):selected.append('psd')
        if window+'M04_spectral.json' in declared or window+'M04_ieeg_spectrum_fit.json' in declared:selected.append('interference')
        if any(gnosis(k) for k in ['artifact','low_band','high_band']):selected.extend(['artifact_burden','timeline'])
        elif window+'M04_ieeg_spectrum_fit.json' in declared or window+'M06_muscle.json' in declared or window+'M03_mne_amplitude.json' in declared:selected.append('timeline')
        for key,method in [('band_power','band_power'),('band_amplitude','band_amplitude'),('psd_distance','psd_deviation'),('reference_ranges','reference_ranges')]:
            if gnosis(method):selected.append(key)
    groups=[
        ('locations','问题定位',('timeline','interference','artifact_burden','waveform')),
        ('channels','通道比较',('channel_metrics','psd_distance')),
        ('spectra','频谱与频带',('psd','band_power','band_amplitude','reference_ranges')),
    ]
    if window+'M05_channel_description.json' in declared:
        for spec in specs:
            if spec['key']=='channel_metrics':spec.update(name='触点电压统计',description='各触点的 RMS 与峰峰值；幅度差异需结合记录背景解释。')
            if spec['key']=='interference':spec.update(name='工频邻域功率',description='测量 50 / 60 Hz 邻域能量，不直接判定为工频污染。')
    visible=[s for s in specs if s['key'] in selected]
    visible_keys={s['key'] for s in visible}
    expanded=next((key for _,_,keys in groups for key in keys if key in visible_keys),None)
    panels={}
    for spec in visible:
        try:body=render(spec['key'])
        except (ValueError,TypeError,KeyError,IndexError,OverflowError):body=missing('保存的证据结构或数值不符合该图要求；未生成图表。')
        panels[spec['key']]=f'<details class="panel" id="{spec["id"]}" {"open" if spec["key"]==expanded else ""}><summary><span class="panel-title">{esc(spec["name"])}</span></summary><div class="panel-body"><p class="panel-description">{esc(spec["description"])}</p>{body}</div></details>'
    group_html=[]
    for identifier,title,keys in groups:
        contents=[panels[k] for k in keys if k in panels]
        if not contents:continue
        group_html.append(f'<details class="chart-group" id="chart-{identifier}" {"open" if expanded in keys else ""}><summary><h2>{title}</h2><span class="chart-count">{len(contents)} 项</span></summary><div class="chart-group-body">{"".join(contents)}</div></details>')
    checkboxes=''.join(f'<label class="choice"><input type="checkbox" name="show" value="{s["key"]}" {"checked" if s["key"] in selected else ""}>{esc(s["name"])}</label>' for s in specs if s['status']=='available')
    planned=''.join(f'<p><b>{esc(s["name"])}</b> · {esc(s["conditions"])}</p>' for s in specs if s['status']=='planned')
    window_metadata={w['id']+'--':w for w in result.get('windows',[]) if isinstance(w,dict) and isinstance(w.get('id'),str)}
    def interval_label(prefix):
        rec=window_metadata.get(prefix, result.get('recording',{}) if not prefix else {})
        start,duration=rec.get('start_seconds'),rec.get('duration_seconds')
        return f'{start:g}–{start+duration:g} 秒' if finite(start) and finite(duration) and duration>0 else None
    window_options=''.join(f'<option value="{esc(w)}" {"selected" if w==window else ""}>{esc(interval_label(w) or ("当前窗口" if not w else w.rstrip("-")))}</option>' for w in windows)
    limits=''.join(f'<option {"selected" if n==limit else ""}>{n}</option>' for n in [16,32,64,128])
    bands=''.join(f'<option {"selected" if b==band else ""}>{b}</option>' for b in BANDS)
    label=result.get('recording',{});caption=f'{label.get("channel_count","—")} 道 · {label.get("sampling_rate_hz","—")} Hz'
    warning='<p class="empty">部分证据无法读取，受影响图表显示未评。</p>' if errors else ''
    period=interval_label(window)
    scope_note=(f'当前图表：原记录 {period}。' if period else '当前图表：所选分析窗口，时间范围未记录。')
    if result.get('scope')=='recording':scope_note+=' 按窗口展示，不是整份记录的汇总图。'
    embed_field='<input type="hidden" name="embedded" value="1">' if embedded else ''
    source_note=('<details class="method-sources"><summary>方法来源</summary><p>'+
                 ' · '.join(f'<a href="{url}" target="_blank" rel="noreferrer">{label}</a>' for url,label in sources.items())+
                 '</p></details>') if sources else ''
    return f'''<!doctype html><html lang="zh-CN" class="{'embedded-charts' if embedded else ''}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>结果可视化 · 质控台</title><link rel="stylesheet" href="/ui-tokens.css"><style>{CSS}</style></head><body>
<nav><a href="{esc(back_url)}" target="_top">← 返回质控报告</a><span>DBCI-QC · 图表分析</span></nav><main>
<div class="intro"><h1>图表分析</h1><p>{esc(caption)}</p><p class="scope-note">{esc(scope_note)}</p></div>
<form action="{esc(action)}" method="get" class="controls"><input type="hidden" name="configured" value="1">{embed_field}<div class="toolbar"><label class="primary-period">查看时段 <select name="window">{window_options}</select></label><span class="chart-update-status" role="status" aria-live="polite"></span><button type="submit" class="chart-refresh" aria-label="刷新图表"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7v5h-5M4 17v-5h5M6.1 6.1a8 8 0 0 1 13 2.4M4.9 15.5a8 8 0 0 0 13 2.4"/></svg><span>刷新图表</span></button></div><details class="display-options"><summary>显示选项</summary><div class="secondary-controls"><label>显示通道 <select name="limit">{limits}</select></label><label>参考频带 <select name="band">{bands}</select></label></div><div class="choices">{checkboxes}</div></details></form>
{warning}{''.join(group_html) if panels else missing('请选择至少一种图表。')}{source_note}<footer>{VERSION} · 数值和候选均来自保存的检测结果；图表配色不定义新的质量标准。</footer></main>
<script src="/visualizations.js" defer></script></body></html>'''

CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f7fc;color:#17324d;font:14px/1.65 system-ui,-apple-system,sans-serif}nav{height:66px;background:#fff;border-bottom:1px solid #dce5f2;display:flex;justify-content:space-between;align-items:center;padding:0 5vw}a{color:#2563eb;text-decoration:none}nav span,.caption,footer{color:#64748b;font-size:13px}main{max-width:1180px;margin:40px auto;padding:0 28px}h1{font-size:24px;margin:8px 0}h2{font-size:22px;margin:2px 0}h3{font-size:16px;margin:0}p{margin:8px 0}.eyebrow,header>span{font-size:11px;letter-spacing:2px;color:#5678ab}.intro{margin:0 0 26px}.intro p{color:#64748b}.controls,.panel{background:white;border:1px solid #dce5f2;border-radius:6px;margin:18px 0;padding:22px}.intro .scope-note{color:#243449;background:#eef3fb;border-left:3px solid #2459bc;padding:9px 12px}.figure-details{margin:8px 0 18px}.figure-details pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:240px;overflow:auto;background:#f5f7fa;padding:12px;font:12px/1.6 ui-monospace,monospace}.choices{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.choice{display:flex;align-items:center;gap:10px;cursor:pointer}input{accent-color:#2563eb;width:17px;height:17px}.toolbar{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-top:24px;padding-top:20px;border-top:1px solid #edf1f7}select,button{font:inherit;border-radius:8px;padding:8px 12px;border:1px solid #cad8eb;background:white}button{background:#2563eb;color:white;border:0;cursor:pointer;margin-left:auto}.panel{color:#17324d;font-size:14px}.panel>summary{display:flex;align-items:center;gap:16px;list-style:none;position:relative;padding-right:26px}.panel>summary::-webkit-details-marker{display:none}.panel>summary::after{content:"+";position:absolute;right:0;font-size:21px;color:#64748b}.panel[open]>summary::after{content:"−"}.panel-title{font-size:16px;font-weight:600;flex-shrink:0}.panel-description{color:#64748b;font-size:13px}.panel-body{padding-top:4px}summary:focus-visible,a:focus-visible{outline:2px solid #2563eb;outline-offset:4px}.figure{margin-top:24px;border-top:1px solid #e8edf6;padding-top:18px;overflow-x:auto}.figure-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.figure-head a{font-size:12px}svg{display:block;width:100%;min-width:620px;height:auto}img.waveform{width:100%;height:auto}.empty{border-radius:8px;padding:20px;background:#f7f9fc;color:#64748b}details{margin-top:20px;color:#64748b;font-size:13px}summary{cursor:pointer}footer{text-align:center;margin:32px 0}@media(max-width:760px){main{padding:0 14px;margin:24px auto}.choices{grid-template-columns:repeat(2,1fr)}.controls,.panel{padding:18px}nav span{display:none}h1{font-size:24px}.panel>summary{align-items:flex-start;flex-direction:column;gap:4px}}@media print{nav,.controls{display:none}body{background:white}main{max-width:none;padding:0}.panel{break-inside:avoid}.panel>.panel-body{display:block!important}.figure{overflow:visible}svg{min-width:0}}'''

# Compact document spacing; stable scrollbar placement when modules expand.
CSS += """html{scrollbar-gutter:stable}body{background:#fff;color:#243449}nav{height:56px;padding:0 24px}main{max-width:1200px;margin:24px auto;padding:0 24px}.intro{margin-bottom:16px}.intro h1{font-size:22px}.controls{padding:12px 16px;margin:14px 0}.toolbar{margin:0;padding:0;border:0;gap:12px}select,button{padding:5px 8px;border-radius:4px;font-size:13px}.choices{margin-top:12px;gap:8px}.panel{padding:12px 16px;margin:10px 0;border-radius:4px}.panel-title{font-size:14px}.figure{margin-top:14px;padding-top:12px}.figure-head{margin-bottom:10px}.figure-head h3{font-size:14px}.scope-note{font-size:13px}.empty{padding:12px;border-radius:4px}details{margin-top:12px}.snapshot-unavailable{color:#798495}footer{margin:20px 0;font-size:12px}"""

CSS += """.embedded-charts{scrollbar-gutter:auto}.embedded-charts body{display:flow-root;min-height:0}.embedded-charts nav,.embedded-charts footer,.embedded-charts .intro h1,.embedded-charts .intro>p:not(.scope-note){display:none}.embedded-charts main{max-width:none;margin:0;padding:0}.embedded-charts .intro{margin:0 0 10px}.embedded-charts .panel{margin:10px 0}.embedded-charts .panel-title{flex-shrink:1}"""

CSS += """
body{font-family:var(--font-ui,system-ui,sans-serif)}
.intro .scope-note{padding:0;border:0;background:none;font-size:12px;color:#64748b;margin:5px 0 0}
.controls{background:#f8fafc;border:1px solid #e2e8f0;padding:10px 12px}
.toolbar{justify-content:space-between}.primary-period{display:flex;align-items:center;gap:10px;font-weight:500}.primary-period select{min-width:160px;background:#fff;font-weight:400}
.toolbar button{margin-left:auto}.display-options{margin:9px 0 0;border-top:1px solid #e2e8f0;padding-top:8px}.display-options>summary{font-size:12px;color:#53657b}
.secondary-controls{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}.secondary-controls label{display:flex;align-items:center;gap:8px;font-size:12px}.choices{border-top:1px solid #e2e8f0;padding-top:10px}.choice{font-size:12px}
.chart-group{margin:0;border-bottom:1px solid #dfe6ef;scroll-margin-top:12px;color:#243449}
.chart-group>summary{display:flex;align-items:center;gap:10px;position:relative;list-style:none;padding:14px 28px 14px 0}
.chart-group>summary::-webkit-details-marker{display:none}.chart-group>summary::after{content:"+";position:absolute;right:4px;font-size:19px;font-weight:400;color:#64748b}.chart-group[open]>summary::after{content:"−"}
.chart-group>summary>h2{margin:0;font-size:14px;line-height:1.5;font-weight:600;color:inherit}.chart-count{font-size:12px;font-weight:400;color:#748094}
.chart-group>summary:hover{color:#2459bc}.chart-group-body{margin:0 0 14px 4px;padding-left:14px;border-left:2px solid #e8edf5}
.chart-group .panel{margin:0;border-radius:0;border:0;border-bottom:1px solid #e4eaf1;padding:11px 2px}.chart-group .panel>summary{font-size:13px}.chart-group .panel-title{font-size:13px;font-weight:500}
.chart-group .panel>summary::after{font-size:17px;right:4px}.chart-group .panel[open]>.panel-body{padding:8px 0 4px}.panel-body>.panel-description{font-size:12px;margin:0 0 8px;color:#64748b}
.panel-body>.figure:first-of-type{margin-top:0;padding-top:0;border:0}.figure-head{margin-bottom:8px}.figure-head h3{font-size:13px;font-weight:500;color:#42546b}
.figure .caption{font-size:12px}.figure-details{margin:6px 0 12px}.figure-details summary{font-size:12px}.method-sources{margin-top:16px;border-top:1px solid #e2e8f0;padding-top:10px}.method-sources summary{font-size:12px}
.embedded-charts .intro{margin-bottom:8px}.embedded-charts .panel{margin:0}.embedded-charts .chart-group{margin:0}
@media(max-width:600px){.primary-period{flex-wrap:wrap;gap:4px}.primary-period select{min-width:120px}.toolbar{gap:8px}.choices{grid-template-columns:1fr 1fr}}
"""

CSS += """
.controls{border-color:#dce5f0;background:#f7f9fc;border-radius:6px;padding:12px 14px}
.chart-update-status{font-size:12px;color:#64748b;margin-left:auto;min-width:5em;text-align:right}
.toolbar .chart-refresh{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:34px;padding:6px 12px;border:1px solid #c4d4ed;background:#fff;color:#2459bc;font-weight:500;margin-left:0;transition:background .15s,box-shadow .15s,transform .1s}
.chart-refresh svg{width:16px;height:16px;min-width:16px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.chart-refresh:hover{background:#eaf1ff;border-color:#8daee5}.chart-refresh:active{transform:translateY(1px);background:#dce9ff}.chart-refresh:focus-visible,select:focus-visible,.choice:focus-within{outline:2px solid #2563eb;outline-offset:2px}
.controls[aria-busy="true"] .chart-refresh svg{animation:chart-spin .8s linear infinite}.chart-refresh:disabled{cursor:progress;color:#466eaa;background:#edf3ff}.controls[data-update="error"] .chart-update-status{color:#ae462d}.controls[data-update="done"] .chart-update-status{color:#18705c}
.choice{padding:7px 9px;border:1px solid #dce3ed;border-radius:5px;background:#fff;transition:background .15s,border-color .15s,color .15s;user-select:none;line-height:1.4;min-height:34px}
.choice:hover{background:#eef4ff;border-color:#a8bfdf}.choice:has(input:checked){color:#174b99;background:#e9f1ff;border-color:#9bb8e8}.choice:active{background:#dce9ff}.choice input{flex:none;width:15px;height:15px;margin:0}
.panel>summary,.chart-group>summary{transition:background .15s,color .15s;border-radius:3px}.panel>summary:hover{color:#2459bc;background:#f5f8fd}.panel[open]>summary{color:#174b99}.panel>summary:active,.chart-group>summary:active{background:#eaf1fc}
@keyframes chart-spin{to{transform:rotate(360deg)}}@media(prefers-reduced-motion:reduce){.chart-refresh,.choice{transition:none}.controls[aria-busy="true"] .chart-refresh svg{animation:none}}
@media(max-width:500px){.toolbar{gap:8px}.chart-update-status{order:3;width:100%;text-align:left;min-height:0}.chart-update-status:empty{display:none}.choices{grid-template-columns:1fr}}
"""
