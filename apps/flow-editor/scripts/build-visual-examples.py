#!/usr/bin/env python3
"""Build public visualization examples from saved, real ds002034 QC evidence.

No detector is rerun; no private paths or record identifiers are exported.
Usage: python build-visual-examples.py --artifacts PATH --edf PATH
The artifact directory must contain the 0-120 s w000001 evidence from
OpenNeuro ds002034 v1.0.3, sub-01/ses-01/offline/run-01.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import mne

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from ephys_qc.visualizations.evidence import read_evidence
from ephys_qc.report_view import line_summary

p=argparse.ArgumentParser();p.add_argument('--artifacts', type=Path, required=True);p.add_argument('--edf',type=Path,required=True);args=p.parse_args()
OUT=ROOT/'apps/flow-editor/public/visual-examples';OUT.mkdir(parents=True, exist_ok=True)
CONTENT=ROOT/'apps/flow-editor/content/visual-examples.json'
SOURCE='https://openneuro.org/datasets/ds002034/versions/1.0.3'
SAMPLE='ds002034 / sub-01 · 注意任务'
SAMPLE_ID='ds002034-v1.0.3_sub-01_ses-01_task-offline_run-01'
EXPECTED='7edb1d6b813cf0b9c33e1b627f3181f8a9a2fb56603d6be3aca0879281a45f2e'
BLUE='#285bb5';AMBER='#c28526';INK='#253449';MUTED='#64748b';TEAL='#168a88';GRID='#e7edf4'
BANDS=['delta','theta','alpha','beta','gamma'];BAND_LABELS=['δ','θ','α','β','γ']
for font in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc']:
 if Path(font).exists():
  font_manager.fontManager.addfont(font);plt.rcParams['font.family']=font_manager.FontProperties(fname=font).get_name();break
plt.rcParams.update({'font.size':10,'axes.titlesize':11,'axes.labelsize':10,'axes.edgecolor':'#cad5e3','text.color':INK,'axes.labelcolor':MUTED,'xtick.color':MUTED,'ytick.color':INK,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white','savefig.facecolor':'white','axes.unicode_minus':False})
assert hashlib.sha256(args.edf.read_bytes()).hexdigest()==EXPECTED, 'Use the verified public EDF file only'
def ev(name):
 path=args.artifacts/('w000001--'+name+'.json')
 return read_evidence(path) if name in ('M04_spectral','M06_muscle') else json.loads(path.read_text())
g={name:ev(prefix+name) for name,prefix in [('band_power','M04_gnosis_'),('band_amplitude','M04_gnosis_'),('reference_ranges','M04_gnosis_'),('psd_deviation','M05_gnosis_'),('line_length','M05_gnosis_'),('artifact','M06_gnosis_'),('low_band','M06_gnosis_'),('high_band','M06_gnosis_')]}
assert all(x['calculated'] and x['status']=='completed' for x in g.values())
assert all(x['range']['start_seconds']==0 and x['range']['stop_seconds']==120 for x in g.values())
spectral=ev('M04_spectral');prep=ev('M05_bad_channels');muscle=ev('M06_muscle');lines=line_summary(spectral['line_noise'])
names=g['band_power']['channel_names'];assert len(names)==62
chosen=['FP1','FPz','FP2','F7','F3','Fz','F4','F8','T7','C3','Cz','C4','T8','Pz','O1','O2']
base={'availability':'ready','dataset':SAMPLE,'modality':'头皮 EEG','format':'EDF','sourceUrl':SOURCE}
manifest={}
def add(key,title,details,takeaway,note='',data=True):
 manifest[key]={**base,'title':title,'details':details,'image':f'visual-examples/{key}.png','takeaway':takeaway}
 if data:manifest[key]['dataUrl']=f'visual-examples/{key}.csv'
 if note:manifest[key]['note']=note

def export_csv(key,rows):
 rows=[{'dataset':SAMPLE_ID,'analysis_start_s':0,'analysis_stop_s':120,**r} for r in rows]
 if not rows:raise ValueError(key)
 with (OUT/f'{key}.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def figure(title,subtitle,nrows=1,ncols=1,figsize=(10,5.8)):
 fig,axes=plt.subplots(nrows,ncols,figsize=figsize,squeeze=False)
 fig.text(.075,.956,title,fontsize=16,weight='bold',va='top')
 fig.text(.075,.900,subtitle,fontsize=9,color=MUTED,va='top')
 fig.subplots_adjust(left=.095,right=.96,top=.81,bottom=.15,hspace=.52,wspace=.30)
 return fig,axes

def finish(fig,key,footer):
 fig.text(.075,.035,footer,fontsize=8.5,color=MUTED,va='bottom')
 fig.savefig(OUT/f'{key}.png',dpi=135,bbox_inches='tight',pad_inches=.18);plt.close(fig)

def clean(ax):
 ax.grid(axis='x',color=GRID,linewidth=.7);ax.set_axisbelow(True);ax.tick_params(axis='both',length=0,pad=5)

def hbars(ax,rows,label,color=BLUE,xlim=None):
 y=np.arange(len(rows));ax.barh(y,[r[1] for r in rows],height=.60,color=color)
 ax.set_yticks(y,[r[0] for r in rows]);ax.invert_yaxis();ax.set_xlabel(label);clean(ax)
 if xlim:ax.set_xlim(*xlim)

# 1. Original waveform with a saved BrainElecQC candidate; no QC recomputation.
raw=mne.io.read_raw_edf(args.edf,preload=False,verbose='ERROR');sf=float(raw.info['sfreq']);assert sf==512
c=next(c for c in muscle['candidates'] if c['channel_name']=='O2');start=max(0,c['start_seconds']-2);stop=c['stop_seconds']+2
wave_names=['O2','O1','Pz'];a=round(start*sf);b=round(stop*sf);vals=raw.get_data(picks=wave_names,start=a,stop=b)*1e6;times=np.arange(a,b)/sf
fig,axes=figure('同一时间，比较三个通道','原记录波形 · 512 Hz · 着色区间来自已保存的高频突发候选',nrows=3,figsize=(10,6.3))
for ax,n,v in zip(axes[:,0],wave_names,vals):
 ax.plot(times,v,color=BLUE,lw=.65);ax.axvspan(c['start_seconds'],c['stop_seconds'],color=AMBER,alpha=.18)
 ax.set_ylabel(n+'\nμV',rotation=0,ha='right',va='center');ax.set_xlim(start,stop);ax.grid(color=GRID,lw=.6);ax.tick_params(length=0)
axes[-1,0].set_xlabel('原记录时间（秒）')
finish(fig,'viz_waveform','示例区间：O2，4.50–5.75 秒；候选需要复核，邻近通道用于对照。')
export_csv('viz_waveform',[{'time_s':float(t),'channel':n,'voltage_uv':float(v),'candidate_start_s':c['start_seconds'],'candidate_stop_s':c['stop_seconds']} for n,arr in zip(wave_names,vals) for t,v in zip(times,arr)])
add('viz_waveform','波形与候选标记','62 道 · 512 Hz；展示 O2、O1、Pz 的 2.50–7.75 秒原始波形。','着色区间对应 O2 的高频候选；同一时刻的其他通道可以一起看。','这里是已保存结果的静态示例；质控台中的波形查看器支持时间移动与通道比较。')

# 2. Separate metrics and units: PREP amplitude and Gnosis line length.
amp=sorted([(r['channel_name'],r['robust_amplitude_uv']) for r in prep['channels']],key=lambda x:-x[1])[:12]
ll=sorted(g['line_length']['metrics']['line_length_by_channel'].items(),key=lambda x:-x[1])[:12]
fig,axes=figure('同一个通道，可以从不同指标比较','0–120 秒 · 两种算法分别展示 · 各取数值最大的 12 / 62 道',ncols=2)
hbars(axes[0,0],amp,'稳健幅值（μV）');axes[0,0].set_title('PREP · 稳健幅值',loc='left',pad=12)
hbars(axes[0,1],ll,'原版线长值',TEAL);axes[0,1].set_title('灵犀云 · 平滑线长',loc='left',pad=12)
finish(fig,'viz_channel_metrics','数值较大不直接等于坏道。量纲不同的指标不相加、不共用纵轴。')
export_csv('viz_channel_metrics',[{'method':method,'channel':n,'value':float(v),'unit':unit} for method,rows,unit in [('PREP amplitude',amp,'uV'),('Gnosis line length',ll,'upstream line-length units')] for n,v in rows])
add('viz_channel_metrics','通道指标比较','0–120 秒；分别展示 PREP 稳健幅值和灵犀云线长，各取前 12 道。','各指标保留自己的单位，帮助找到需要进一步查看的通道。','灵犀云方法使用 256 Hz、1–70 Hz、平均参考的分析副本；PREP 指标按其原流程计算。')

# 3. PSD uses saved spectra; show both routes with honest independent domains.
fig,axes=figure('功率谱密度：能量集中在哪些频率','同一份 EEG、同一分析窗口；输入信号与分析副本分别展示',ncols=2)
psd_names=['Fz','Cz','Pz','O2'];colors=[BLUE,TEAL,'#8059b7',AMBER];rows=[]
for ax,route,f,power,unitfactor,lo,hi in [(axes[0,0],'输入信号',np.asarray(spectral['psd']['frequencies_hz']),np.asarray(spectral['psd']['power_v2_hz']),1e12,1,80),(axes[0,1],'灵犀云分析副本',np.asarray(g['band_power']['metrics']['frequencies_hz']),np.asarray(g['band_power']['metrics']['psd_uv2_hz']),1,1,40)]:
 mask=(f>=lo)&(f<=hi)
 for n,color in zip(psd_names,colors):
  i=names.index(n);v=power[i]*unitfactor;d=10*np.log10(v[mask]);ax.plot(f[mask],d,color=color,lw=1.25,label=n)
  rows.extend({'route':route,'channel':n,'frequency_hz':float(ff),'power_uv2_per_hz':float(pp),'display_db_re_uv2_per_hz':float(dd)} for ff,pp,dd in zip(f[mask],v[mask],d))
 ax.set_xlim(lo,hi);ax.set_title(route,loc='left',pad=12);ax.set_xlabel('频率（Hz）');ax.set_ylabel('dB re μV²/Hz');ax.grid(color=GRID,lw=.6);ax.legend(frameon=False,ncol=2,fontsize=8,loc='upper right')
finish(fig,'viz_psd','输入信号：120 秒；灵犀云：排除候选后保留 98.68 秒。曲线平滑不代表质量更好。')
export_csv('viz_psd',rows)
add('viz_psd','功率谱密度','0–120 秒 · Fz、Cz、Pz、O2；同时展示输入信号与灵犀云分析副本的保存结果。','可查看窄带峰与各频率能量；PSD 本身不是质量分数。','两条路线的滤波、参考和选段不同，不能把曲线变化直接视为清洗效果。')

# 4. Line-noise detections: merged by channel and window using production semantics.
line_rows=sorted(lines['channels'],key=lambda x:-x['percent'])[:12]
fig,axes=figure('工频候选分布到哪些通道','0–120 秒 · 命中比例最高的 12 / 62 道')
hbars(axes[0,0],[(r['name'],r['percent']) for r in line_rows],'命中检查窗 / 可评检查窗（%）',AMBER,(0,100))
for y,r in enumerate(line_rows):axes[0,0].text(r['percent']+1,y,f"{r['hits']}/{r['total']}",va='center',fontsize=8,color=MUTED)
finish(fig,'viz_interference','同一通道窗中多个目标频率命中只计一次；窗口命中比例不等于污染时长。')
export_csv('viz_interference',[{'channel':r['name'],'hit_windows':r['hits'],'assessed_windows':r['total'],'hit_percent':r['percent']} for r in line_rows])
add('viz_interference','工频命中比例','0–120 秒；显示命中比例最高的 12 道，每道 117 个可评检查窗。','图旁保留命中窗数，能看到高比例具体发生在哪些通道。','统计可测工频及谐波；相邻检查窗有重叠，不能解释成同等比例的污染时间。')

# 5. Gnosis artifact burden — three independent outputs, no duplicate sum.
methods=[('artifact','伪差候选',BLUE),('low_band','低频异常',TEAL),('high_band','高频异常',AMBER)]
burden_names=sorted(names,key=lambda n:-max(g[m]['metrics']['ratio_by_channel'][n] for m,_,_ in methods))[:10]
fig,axes=figure('异常时间占比：先看集中在哪些通道','0–120 秒 · 按三类候选的最大占比排序，展示 10 / 62 道')
ax=axes[0,0];y=np.arange(len(burden_names))
for i,(method,label,color) in enumerate(methods):ax.barh(y+(i-1)*.23,[100*g[method]['metrics']['ratio_by_channel'][n] for n in burden_names],height=.21,color=color,label=label)
ax.set_yticks(y,burden_names);ax.invert_yaxis();ax.set_xlabel('该通道候选区间占比（%）');clean(ax);ax.legend(frameon=False,ncol=3,loc='lower right',fontsize=8)
finish(fig,'viz_artifact_burden','三种检测独立展示，候选可能重叠；不将三项比例简单相加。')
export_csv('viz_artifact_burden',[{'channel':n,'method':m,'candidate_time_percent':100*g[m]['metrics']['ratio_by_channel'][n]} for n in burden_names for m,_,_ in methods])
add('viz_artifact_burden','异常时间占比','灵犀云分析副本 · 0–120 秒；展示伪差、低频与高频异常占比。','一眼定位候选负担较高的通道，再看原始波形。','三类候选可能重叠，图中分别呈现，不重复相加。')

# 6. Time localization from saved interval list; source-time axis retained.
timeline_rows=g['high_band']['candidates'];totals={}
for r in timeline_rows:totals[r['channel_name']]=totals.get(r['channel_name'],0)+r['stop_seconds']-r['start_seconds']
tl_names=sorted(totals,key=lambda n:-totals[n])[:10];shown=[r for r in timeline_rows if r['channel_name'] in tl_names]
fig,axes=figure('异常时间轴：具体在哪个时段出现','灵犀云高频异常 · 原记录 0–120 秒 · 候选累计时长最高的 10 道')
ax=axes[0,0]
for i,n in enumerate(tl_names):
 for r in shown:
  if r['channel_name']==n:ax.broken_barh([(r['start_seconds'],r['stop_seconds']-r['start_seconds'])],(i-.26,.52),facecolors=AMBER)
ax.set_yticks(range(len(tl_names)),tl_names);ax.invert_yaxis();ax.set_xlim(0,120);ax.set_xlabel('原记录时间（秒）');clean(ax)
finish(fig,'viz_timeline','每条色带均对应已保存的候选起止时间；空白只表示此方法未标记该时段。')
export_csv('viz_timeline',[{'method':'gnosis_high_band','channel':r['channel_name'],'candidate_start_s':r['start_seconds'],'candidate_stop_s':r['stop_seconds']} for r in shown])
add('viz_timeline','异常时间轴','灵犀云高频异常 · 0–120 秒；展示候选累计时长最高的 10 道。','色带直接回答“哪条通道、哪个时间段”，方便定位复核。','仅显示这一个检测方法的候选，空白不代表已证明完全无异常。')

# 7-9. Read stored channel x frequency-band values; retain exact CSV numbers.
def matrix(key,method,field,title,unit,factor=1,cols=BANDS,labels=BAND_LABELS,vmax=None,flagged=()):
 source=g[method]['metrics'][field];table={(r['channel_name'],r['band']):r['value']*factor for r in source}
 mat=np.array([[table[n,b] for b in cols] for n in chosen],dtype=float)
 fig,axes=figure(title,'灵犀云分析副本 · 0–120 秒内保留 98.68 秒 · 选取 16 / 62 道',figsize=(10,6.6));ax=axes[0,0]
 im=ax.imshow(mat,aspect='auto',cmap='Blues',vmin=0,vmax=vmax if vmax is not None else np.max(mat));ax.set_xticks(range(len(cols)),labels);ax.xaxis.tick_top();ax.set_yticks(range(len(chosen)),chosen);ax.tick_params(length=0);ax.spines[['left','bottom']].set_visible(False)
 maxval=vmax or float(np.max(mat))
 for i in range(len(chosen)):
  for j in range(len(cols)):ax.text(j,i,f'{mat[i,j]:.1f}' if factor==100 else f'{mat[i,j]:.2f}',ha='center',va='center',fontsize=8,color='white' if mat[i,j]/maxval>.6 else INK)
 for tick in ax.get_yticklabels():
  if tick.get_text() in flagged:tick.set_color(AMBER);tick.set_weight('bold')
 cb=fig.colorbar(im,ax=ax,fraction=.025,pad=.04);cb.set_label(unit,fontsize=9);cb.outline.set_visible(False)
 finish(fig,key,'颜色表示测量值大小，不是质量分。'+('橙色通道名沿用已保存的 PSD 差异候选。' if flagged else '各频带分别显示。'))
 export_csv(key,[{'channel':n,'band':b,'value':float(table[n,b]),'unit':unit,'psd_candidate':n in flagged} for n in chosen for b in cols])

matrix('viz_band_power','band_power','relative_power','不同通道的能量分布','%',factor=100,vmax=100)
add('viz_band_power','相对频带功率','灵犀云 · 16 道 × 5 个频带；使用候选排除后保留的 98.68 秒。','同一色标 0–100%，看各通道的频带能量构成。','相对功率是测量结果，不直接代表通道好坏。')
matrix('viz_band_amplitude','band_amplitude','mean_amplitude_uv','不同频带的平均幅值','μV')
add('viz_band_amplitude','频带平均幅值','灵犀云 · 16 道 × 5 个频带；平均绝对幅值，单位 μV。','与相对功率互补：这里保留绝对幅值大小。','与参考范围比较时，需匹配采集、参考和预处理条件。')
flags=[r['channel_name'] for r in g['psd_deviation']['candidates']]
matrix('viz_psd_distance','psd_deviation','psd_distance','哪些通道的频谱与其他通道不同','log10 PSD 距离',cols=BANDS+['full'],labels=BAND_LABELS+['全频'],flagged=flags)
add('viz_psd_distance','PSD 通道差异','灵犀云 · 16 道 × 6 类频带；T7 在本窗口被标记为候选。','同时保留距离数值与候选标记，能看出差异来自哪个频带。','通道频谱不同不等于一定是坏道，仍需结合位置与任务解释。')

# 10. Actual upstream reference bounds; never invented population KDE.
reference=[r for r in g['reference_ranges']['metrics']['reference_comparison'] if r['feature']=='bpre' and r['band']=='alpha' and r['channel_name'] in chosen]
reference.sort(key=lambda r:chosen.index(r['channel_name']))
fig,axes=figure('α 频带：当前值与参考区间对照','灵犀云参考表 · 相对功率 · 选取 16 / 62 道',figsize=(10,6.1));ax=axes[0,0]
for i,r in enumerate(reference):
 ax.plot([r['low']*100,r['high']*100],[i,i],color='#c5d2e3',lw=5,solid_capstyle='round');ax.scatter(r['value']*100,i,s=27,color=BLUE if r['comparison']=='within' else AMBER,zorder=3)
ax.set_yticks(range(len(reference)),[r['channel_name'] for r in reference]);ax.invert_yaxis();ax.set_xlabel('α 相对功率（%）');clean(ax)
finish(fig,'viz_reference_ranges','灰线为原版参考范围，点为当前测量；超出参考范围不能直接判为质量不合格。')
export_csv('viz_reference_ranges',[{'channel':r['channel_name'],'feature':'relative_alpha_power','value_percent':r['value']*100,'reference_low_percent':r['low']*100,'reference_high_percent':r['high']*100,'comparison':r['comparison']} for r in reference])
add('viz_reference_ranges','参考范围对照','灵犀云参考表 · α 相对功率；展示 16 道的测量值与原版区间。','既能看到当前数值，也能看它在参考区间中的位置。','参考群体与本数据的适配性尚需审核；本图用于观察，不定义通用合格线。')

# Overview uses the same real series, without embedding mock artwork.
fig,axes=figure('可视化：从测量结果定位到原始信号','同一公开 EEG 样例 · 10 类已接入展示 · 2 类规划中',nrows=2,ncols=2,figsize=(10,7.5));fig.subplots_adjust(top=.82,bottom=.14,hspace=.75,wspace=.27)
ax=axes[0,0];ax.plot(times,vals[0],color=BLUE,lw=.65);ax.axvspan(c['start_seconds'],c['stop_seconds'],color=AMBER,alpha=.18);ax.set_title('波形与候选 · O2',loc='left');ax.set_xlabel('原记录时间 / 秒');ax.set_ylabel('μV');ax.grid(color=GRID,lw=.5)
ax=axes[0,1];r=line_rows[:5];hbars(ax,[(x['name'],x['percent']) for x in r],'命中检查窗 / %',AMBER,(0,100));ax.set_title('通道分布 · 工频候选',loc='left')
ax=axes[1,0];freq=np.asarray(g['band_power']['metrics']['frequencies_hz']);powers=np.asarray(g['band_power']['metrics']['psd_uv2_hz']);
for n,color in zip(psd_names,colors):ax.plot(freq,10*np.log10(powers[names.index(n)]),color=color,lw=1,label=n)
ax.set_title('频谱 · 灵犀云分析副本',loc='left');ax.set_xlabel('Hz');ax.set_ylabel('dB re μV²/Hz');ax.grid(color=GRID,lw=.5);ax.legend(frameon=False,ncol=2,fontsize=7)
ax=axes[1,1];small=chosen[:6];table={(r['channel_name'],r['band']):r['value']*100 for r in g['band_power']['metrics']['relative_power']};im=ax.imshow([[table[n,b] for b in BANDS] for n in small],aspect='auto',vmin=0,vmax=100,cmap='Blues');ax.set_yticks(range(6),small);ax.set_xticks(range(5),BAND_LABELS);ax.set_title('频带能量 · 相对功率',loc='left');fig.colorbar(im,ax=ax,fraction=.025,pad=.04,label='%')
finish(fig,'VIS','数据：OpenNeuro ds002034 v1.0.3 · 所有图来自真实测量；可视化不改写检测结果。')
add('VIS','可视化总览','OpenNeuro 公开注意任务 EEG · 62 道 · 512 Hz · 示例分析窗口 0–120 秒。','按波形、通道、时间与频谱查看同一份数据；点开子模块可看单项示例和测量表。','10 项已有真实结果；脑地形图与雷达图仍在规划中。',data=False)
for key,title,details,takeaway in [('viz_topography','脑地形图','尚未接入。需要可靠的电极坐标、坐标系及通道对应表。','当前不展示估计电极位置生成的效果；待接入后用可核验坐标的公开 EEG 补齐示例。'),('viz_radar','多指标轮廓图','尚未接入。需要先确定各指标的方向、量纲和归一化规则。','不把不同量纲拼成一个雷达图；待指标口径明确后补充真实效果。')]:
 manifest[key]={'title':title,'availability':'planned','dataset':'待补充适用的公开示例','modality':'头皮 EEG','format':'待确定','details':details,'takeaway':takeaway,'sourceUrl':''}
CONTENT.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
# Public-only provenance. No raw participant tables, local paths, logs, or auth data.
readme='''# 可视化模块的公开数据示例

这些图片是模块协作页的静态示例。数值来自已完成的真实质检结果；未重新运行检测、未为制造效果添加噪声、未改变评分。

## 数据来源

- OpenNeuro **ds002034 v1.0.3**，CC0。
- https://openneuro.org/datasets/ds002034/versions/1.0.3
- DOI: https://doi.org/10.18112/openneuro.ds002034.v1.0.3
- 原数据记录：`sub-01/ses-01/eeg/sub-01_ses-01_task-offline_run-01_eeg.edf`。
- 实验：隐性注意任务；本图使用 62 个已选择的头皮 EEG 通道、512 Hz，原记录共 733 秒。
- 图中分析窗口：原记录 0–120 秒。只导出图表所示的少量测量值和波形片段，不分发完整 EDF、受试者表或本机路径。
- 原文件 SHA-256：`'''+EXPECTED+'''`。
- 数据作者：Christoph Schneider、Michael Pereira、Luca Tonin、José del R. Millán。
- 相关论文：https://doi.org/10.1007/s10548-019-00725-9
- This data was obtained from the Open Neuro database.

## 实际处理与图表范围

- 工频图：沿用 BrainElecQC 的已保存检查结果；同一道同一检查窗的多个频率命中只计一次。比例是窗口命中比例，不是污染时长。
- 波形图：直接读取公开 EDF 中 O2、O1、Pz 的 2.50–7.75 秒电压值；着色区间 O2 4.50–5.75 秒来自已保存高频突发候选。未为了绘图重新滤波。
- PREP 指标：显示已保存的稳健幅值；线长图显示灵犀云原版线长数值。两项不合并、不共用单位。
- 灵犀云分析副本：256 Hz、1–70 Hz、共同平均参考、无 ICA；输入文件不变。
- 灵犀云频谱相关图：从本窗口中排除候选片段后，保留 13.880–45.715、51.940–102.030、103.245–120.000 秒，按采样点计实际 98.68359375 秒。
- 原版保存的 PSD 范围为 1–40 Hz；频带列沿用原算法定义，gamma 仅表示该可测频带内的部分，不表示完整高频活动。
- 相对功率乘以 100 后显示为百分数；PSD 转换为 dB re μV²/Hz；其他指标保持原保存数值。
- 原记录输入 PSD 展示 1–80 Hz；与灵犀云分析副本 PSD 分开呈现。不能将曲线变化直接解释为清洗提高质量。
- 参考图使用原版参考上下界，不绘制虚构的群体密度曲线；超界不直接等于质量不合格。
- 时间轴与占比图独立显示检测方法；候选可能重叠，不能简单相加。
- 各图明确给出显示的通道子集；CSV 只包含实际绘制的样本和测量值，带公共记录编号与分析窗口。

## 方法来源

- BrainElecQC: https://github.com/Jlei61/BrainElecQC
- GnosisNeuroDynamicSE: https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE
- 当前质控台可视化代码：`src/ephys_qc/visualizations/`。

## 可用性

10 个子模块及 VIS 总览有真实图片和结果。脑地形图、雷达图仍为规划项，没有伪造预览：前者需要可信电极坐标，后者需要指标方向与归一化定义。

## 复现

仓库脚本 `apps/flow-editor/scripts/build-visual-examples.py` 接收 `--artifacts`（包含 `w000001--` 结果的目录）和 `--edf`（上述公开原始文件）两个参数。脚本校验原文件哈希、方法完成状态、时间窗与通道数，再从已保存证据绘图。图片与 CSV 均不包含本机绝对路径或运行日志。
'''
(OUT/'README.md').write_text(readme)
print(json.dumps({'entries':len(manifest),'ready':sum(x['availability']=='ready' for x in manifest.values()),'planned':sum(x['availability']=='planned' for x in manifest.values()),'output_bytes':sum(x.stat().st_size for x in OUT.iterdir() if x.is_file())},ensure_ascii=False))
