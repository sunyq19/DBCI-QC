"""Read-only SVG/HTML presentation of stored QC evidence (no detector imports)."""
from html import escape
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

def timeline(candidates,start,stop,limit):
    rows=[c for c in candidates if finite(c.get('start_seconds')) and finite(c.get('stop_seconds')) and c['stop_seconds']>c['start_seconds']]
    if not rows:return missing('未检出带有效时间位置的候选区间。')
    if not finite(start) or not finite(stop) or stop<=start:return missing('原始记录时间范围未提供。')
    names=list(dict.fromkeys(c['channel_name'] for c in rows))[:limit]
    all_count=len(rows);rows=[c for c in rows if c['channel_name'] in names][:500]
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


def render_gallery(result,load,*,selected=None,window='',limit=32,band='alpha',asset_url=lambda n:n,back_url='',action=''):
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
    def section(title,body,source):
        url=GNOSIS if source=='灵犀云' else LEI
        return f'<div class="figure"><div class="figure-head"><h3>{esc(title)}</h3><a href="{url}" target="_blank" rel="noreferrer">{esc(source)}</a></div>{body}</div>'
    def render(key):
        if key=='waveform':
            name=window+'waveform.png'
            if name not in declared:return missing('本窗口没有已保存的波形图；可返回报告查看候选波形。')
            return section('原始波形预览',f'<img class="waveform" src="{esc(asset_url(name))}" alt="已保存的原始波形预览"><p class="caption">起始最多15秒与前几个通道；完整候选位置见异常时间轴。</p>','雷佳欣 / DBCI-QC')
        if key=='channel_metrics':
            d=evidence('M05_bad_channels.json');rows=d.get('channels',[]);out=''
            if rows:
                for field,label,unit in [('robust_amplitude_uv','稳健幅值','μV'),('hf_ratio','高频残差比例','比例'),('low_correlation_fraction','低相关窗口占比','%')]:
                    out+=section(label,bars([(r['channel_name'],r.get(field)*100 if field=='low_correlation_fraction' and finite(r.get(field)) else r.get(field),bool(r.get('flags'))) for r in rows],unit,limit=limit),'雷佳欣 / PREP')
            g=gnosis('line_length')
            if g:
                flags={c['channel_name'] for c in g.get('candidates',[])}
                out+=section('平滑线长总量',bars([(k,v,k in flags) for k,v in g['metrics'].get('line_length_by_channel',{}).items()],'原版线长值',limit=limit),'灵犀云')
            return out or missing('先运行通道质量或灵犀云线长方法。')
        if key=='psd':
            out='';d=evidence('M04_spectral.json');p=d.get('psd',{});sel=evidence('M02_selection.json');mapping={c['channel_id']:c['raw_name'] for c in sel.get('channels',[])}
            if p.get('power_v2_hz'):
                out+=section('原始输入 · Welch PSD',spectrum(p.get('frequencies_hz'),p.get('power_v2_hz'),[mapping.get(c,c) for c in p.get('channel_ids',[])],1e12),'雷佳欣')
            g=next((gnosis(k) for k in ['band_power','psd_deviation','reference_ranges'] if gnosis(k)),{})
            if g:
                p=g['metrics'];out+=section('分析副本 · Welch PSD',spectrum(p.get('frequencies_hz'),p.get('psd_uv2_hz'),g['channel_names'],1)+f'<p class="caption">统计时长 {num(p.get("effective_duration_seconds"))} 秒；片段选择：{esc(p.get("spectral_input",""))}。</p>','灵犀云')
            return out or missing('先运行 PSD 相关检查。')
        if key=='interference':
            from ..report_view import line_summary
            d=line_summary(evidence('M04_spectral.json').get('line_noise',{}))
            return section('工频命中窗 / 可评窗口',bars([(c['name'],c['percent'],bool(c['hits'])) for c in d['channels']],'%',limit=limit,upper=100),'雷佳欣')
        if key in ['artifact_burden','timeline']:
            out=''
            for m,label in [('artifact','伪差候选'),('low_band','低频异常'),('high_band','高频异常')]:
                g=gnosis(m)
                if not g:continue
                body=bars([(n,100*v if finite(v) else None,finite(v) and v>0) for n,v in g['metrics'].get('ratio_by_channel',{}).items()], '%',limit=limit,upper=100) if key=='artifact_burden' else timeline(g.get('candidates',[]),g.get('range',{}).get('start_seconds'),g.get('range',{}).get('stop_seconds'),limit)
                out+=section(label,body,'灵犀云')
            if key=='timeline':
                d=evidence('M06_muscle.json');rec=evidence('M02_selection.json').get('recording',{});start=rec.get('start_seconds');dur=rec.get('duration_seconds')
                if d:out+=section('高频突发候选',timeline(d.get('candidates',[]),start,start+dur if finite(start) and finite(dur) else None,limit),'雷佳欣')
            return out or missing('先运行对应的伪差或高频检查。')
        if key in ['band_power','band_amplitude','psd_distance']:
            method,field,unit={'band_power':('band_power','relative_power','%'),'band_amplitude':('band_amplitude','mean_amplitude_uv','μV'),'psd_distance':('psd_deviation','psd_distance','log10 PSD 距离')}[key]
            g=gnosis(method);rows=metrics(method).get(field,[])
            if key=='band_power':rows=[{**r,'value':r['value']*100 if finite(r.get('value')) else None} for r in rows]
            return section({'band_power':'相对频带功率','band_amplitude':'平均绝对幅值','psd_distance':'通道频谱距离'}[key],heatmap(rows,unit,limit=limit,fixed_max=100 if key=='band_power' else None,flags=[c['channel_name'] for c in g.get('candidates',[])]),'灵犀云')
        if key=='reference_ranges':
            rows=metrics('reference_ranges').get('reference_comparison',[])
            if not rows:return missing('先运行灵犀云参考分布对照。当前仅绘制区间；不生成虚构的群体密度曲线。')
            return ''.join(section(label+' · '+band,ranges(rows,f,band,limit),'灵犀云') for f,label in [('bpre','相对功率 / 比例'),('bpamp','幅值 / μV'),('psdist','PSD 距离')])
        return missing('尚未接入。')
    if automatic:
        if window+'waveform.png' in declared:selected.append('waveform')
        if evidence('M05_bad_channels.json').get('channels') or gnosis('line_length'):selected.append('channel_metrics')
        if evidence('M04_spectral.json').get('psd') or gnosis('band_power') or gnosis('psd_deviation'):selected.append('psd')
        if evidence('M04_spectral.json').get('line_noise',{}).get('observations'):selected.append('interference')
        if any(gnosis(k) for k in ['artifact','low_band','high_band']):selected.extend(['artifact_burden','timeline'])
        elif evidence('M06_muscle.json').get('candidates'):selected.append('timeline')
        for key,method in [('band_power','band_power'),('band_amplitude','band_amplitude'),('psd_distance','psd_deviation'),('reference_ranges','reference_ranges')]:
            if gnosis(method):selected.append(key)
    panels=[]
    for s in specs:
        if s['key'] not in selected:continue
        try:body=render(s['key'])
        except (ValueError,TypeError,KeyError,IndexError,OverflowError):body=missing('保存的证据结构或数值不符合该图要求；未生成图表。')
        panels.append(f'<section class="panel" id="{s["id"]}"><header><span>{s["id"].replace("viz_","").upper()}</span><h2>{esc(s["name"])}</h2><p>{esc(s["description"])}</p></header>{body}</section>')
    checkboxes=''.join(f'<label class="choice"><input type="checkbox" name="show" value="{s["key"]}" {"checked" if s["key"] in selected else ""}>{esc(s["name"])}</label>' for s in specs if s['status']=='available')
    planned=''.join(f'<p><b>{esc(s["name"])}</b> · {esc(s["conditions"])}</p>' for s in specs if s['status']=='planned')
    window_options=''.join(f'<option value="{esc(w)}" {"selected" if w==window else ""}>{"当前窗口" if not w else esc(w.rstrip("-"))}</option>' for w in windows)
    limits=''.join(f'<option {"selected" if n==limit else ""}>{n}</option>' for n in [16,32,64,128])
    bands=''.join(f'<option {"selected" if b==band else ""}>{b}</option>' for b in BANDS)
    label=result.get('recording',{});caption=f'{label.get("channel_count","—")} 道 · {label.get("sampling_rate_hz","—")} Hz'
    warning='<p class="empty">部分证据无法读取，受影响图表显示未评。</p>' if errors else ''
    scope_note='整份报告按窗口显示原始证据，不将各窗频谱或时间比例简单平均。' if result.get('scope')=='recording' else '展示本次分析窗口的已保存结果。'
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>结果可视化 · 质控台</title><style>{CSS}</style><body>
<nav><a href="{esc(back_url)}">← 返回质控报告</a><span>DBCI-QC · 结果可视化</span></nav><main>
<div class="intro"><span class="eyebrow">VISUALIZATION</span><h1>选择您要看的图</h1><p>{esc(caption)} · {esc(scope_note)}</p><p>读取已有结果，切换图表不会重新质控或改变分数。</p></div>
<form action="{esc(action)}" method="get" class="controls"><input type="hidden" name="configured" value="1"><div class="choices">{checkboxes}</div><div class="toolbar"><label>分析窗口 <select name="window">{window_options}</select></label><label>最多显示通道 <select name="limit">{limits}</select></label><label>参考对照频带 <select name="band">{bands}</select></label><button>更新图表</button></div><details><summary>待接入的图</summary>{planned}</details></form>
{warning}{''.join(panels) if panels else missing('请选择至少一种图表。')}<footer>{VERSION} · 数值和候选均来自保存的检测结果；图表配色不定义新的质量标准。</footer></main></body></html>'''

CSS='''*{box-sizing:border-box}body{margin:0;background:#f4f7fc;color:#17324d;font:15px/1.65 system-ui,-apple-system,sans-serif}nav{height:66px;background:#fff;border-bottom:1px solid #dce5f2;display:flex;justify-content:space-between;align-items:center;padding:0 5vw}a{color:#2563eb;text-decoration:none}nav span,.caption,footer{color:#64748b;font-size:13px}main{max-width:1180px;margin:40px auto;padding:0 28px}h1{font-size:32px;margin:8px 0}h2{font-size:22px;margin:2px 0}h3{font-size:16px;margin:0}p{margin:8px 0}.eyebrow,header>span{font-size:11px;letter-spacing:2px;color:#5678ab}.intro{margin:0 0 26px}.intro p{color:#64748b}.controls,.panel{background:white;border:1px solid #dce5f2;border-radius:16px;margin:22px 0;padding:26px}.choices{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.choice{display:flex;align-items:center;gap:10px;cursor:pointer}input{accent-color:#2563eb;width:17px;height:17px}.toolbar{display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-top:24px;padding-top:20px;border-top:1px solid #edf1f7}select,button{font:inherit;border-radius:8px;padding:8px 12px;border:1px solid #cad8eb;background:white}button{background:#2563eb;color:white;border:0;cursor:pointer;margin-left:auto}.panel header p{color:#64748b;font-size:14px}.figure{margin-top:24px;border-top:1px solid #e8edf6;padding-top:18px;overflow-x:auto}.figure-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.figure-head a{font-size:12px}svg{display:block;width:100%;min-width:620px;height:auto}img.waveform{width:100%;height:auto}.empty{border-radius:8px;padding:20px;background:#f7f9fc;color:#64748b}details{margin-top:20px;color:#64748b;font-size:13px}summary{cursor:pointer}footer{text-align:center;margin:32px 0}@media(max-width:760px){main{padding:0 14px;margin:24px auto}.choices{grid-template-columns:repeat(2,1fr)}.controls,.panel{padding:18px}nav span{display:none}h1{font-size:27px}}@media print{nav,.controls{display:none}body{background:white}main{max-width:none;padding:0}.panel{break-inside:avoid}.figure{overflow:visible}svg{min-width:0}}'''
