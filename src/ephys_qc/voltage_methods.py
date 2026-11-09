"""Original MNE/SpikeInterface detectors, with explicit voltage/geometry gates.

No source filtering, guessed contact positions or anatomical classifications.
"""
from copy import deepcopy
import math

DEFAULTS = {
    'ieeg_spectrum_fit': {'line_frequencies_hz': [50.,60.], 'window_seconds': 4., 'p_value': .01, 'tolerance_hz': 1.},
    'ieeg_mne_lof': {'n_neighbors': 10, 'threshold': 1.5, 'reference_confirmed': False},
    'spikeinterface_coherence_psd': {'psd_hf_threshold': .02, 'dead_channel_threshold': -.5,
        'noisy_channel_threshold': 1., 'outside_channel_threshold': -.75, 'include_outside': False,
        'n_neighbors': 11, 'chunk_seconds': .3, 'num_chunks': 20, 'seed': 0},
    'spikeinterface_lfp_neighbors': {'r2_threshold': .9, 'radius_um': 30.,
        'chunk_seconds': 1., 'num_chunks': 20, 'seed': 0},
}
IDS = frozenset(DEFAULTS)
NP_IDS = frozenset(k for k in IDS if k.startswith('spikeinterface_'))


def extension_specs():
    rows = [
        ('ieeg_spectrum_fit','MNE 多窗工频检测','M04',['seeg','ecog'],
         '用多窗 F 检验定位工频附近的稳定窄带成分，保留触点和时间窗。',
         ['原生电压','目标工频仍在可测频带内','至少4秒'],
         '调用 MNE spectrum_fit 的原版检测内核；独立4秒窗，p=0.01按上游窗口采样点数校正，仅收集所选工频±1Hz，每通道窗命中多个频率只记一次。',
         '默认检查50/60Hz基频；显著窄带不是设备故障诊断。已声明滤除的频率未评。使用MNE私有内核，版本和函数签名须通过验收。',
         'MNE-Python','https://mne.tools/stable/generated/mne.filter.notch_filter.html','BSD-3-Clause',
         'mne.filter._get_window_thresh / _mt_spectrum_remove'),
        ('ieeg_mne_lof','MNE 分组触点 LOF','M05',['seeg','ecog'],
         '在已确认可比较的一组触点中寻找波形离群触点。',
         ['明确的逐触点比较组','参考可比性已确认','各组通道数大于邻居数'],
         '每组独立调用 MNE find_bad_channels_lof；保留原版LOF分数、候选和参考分组。',
         '默认可选、不自动启用。脑区差异或病理活动也可离群；1.5是方法初值，不是颅内脑电合格线。',
         'MNE-Python','https://mne.tools/stable/generated/mne.preprocessing.find_bad_channels_lof.html','BSD-3-Clause',
         'mne.preprocessing.find_bad_channels_lof'),
        ('spikeinterface_coherence_psd','IBL 相干与高频噪声','M05',['extracellular'],
         '区分 AP 失活、噪声和组织外候选通道。',
         ['AP电压与正确标定','来源可追溯的探针位置和shank','每杆至少12道'],
         '原版 SpikeInterface coherence+psd；每杆独立按探针深度排序，300Hz高通副本，抽样投票返回good/dead/noise/out。',
         'dead/noise参与通道并集；out默认只展示，可明确启用。组织外标签不是解剖定位。超过三分之一候选时保留警告。',
         'SpikeInterface / IBL','https://spikeinterface.readthedocs.io/en/0.104.2/api.html','MIT',
         'spikeinterface.preprocessing.detect_bad_channels(method="coherence+psd")'),
        ('spikeinterface_lfp_neighbors','SpikeInterface LF 邻域一致性','M05',['extracellular'],
         '检查 LF/LFP 通道与邻近触点的波形一致性。',
         ['LF/LFP电压','以微米为单位的来源探针位置','每道在指定半径内有邻居'],
         '原版 neighborhood_r2：各道与邻域中位信号的相关系数平方，抽样中位数低于0.9列为候选；不应用AP高通。',
         '真实局部活动也可降低一致性。无邻居的通道不伪装通过；当前整项未评。半径30微米是上游默认，可调整。',
         'SpikeInterface','https://spikeinterface.readthedocs.io/en/0.104.2/api.html','MIT',
         'spikeinterface.preprocessing.detect_bad_channels(method="neighborhood_r2")'),
    ]
    return [dict(id=k,name=name,module_id=mid,category='optional',description=desc,
        supported_modalities=modes,research_modalities=modes,implementation='available',status='available',
        optional_extension=True,defaults=deepcopy(DEFAULTS[k]),inputs=conditions,requirements=conditions,
        outputs=['候选、逐道证据与适用条件','可追溯的分项得分'],limitations=[limit],
        source=dict(name=source,url=url,license=license),documentation=dict(purpose=desc,how_it_works=how,
            interpretation=limit,when_to_use='满足本方法输入条件时。',when_not_to_use='缺少标定、分组或几何条件时不推断。',
            upstream_call=call,implementation_origin='调用上游原版；本项目只负责输入适配、定位和计分。',
            version_note='voltage-methods/1',references=[dict(title=source,url=url,kind='官方文档')]))
        for k,name,mid,modes,desc,conditions,how,limit,source,url,license,call in rows]


def parameters(identifier, supplied=None):
    if supplied is not None and (not isinstance(supplied,dict) or set(supplied)-set(DEFAULTS[identifier])):
        raise ValueError('Unknown voltage method parameters')
    p={**DEFAULTS[identifier],**(supplied or {})}
    for k,v in p.items():
        if k=='line_frequencies_hz':
            if not isinstance(v,list) or not 1<=len(v)<=8 or any(type(x) not in (int,float) or not math.isfinite(x) or x<=0 for x in v) or len(set(v))!=len(v):raise ValueError('Invalid target frequencies')
        elif k in {'include_outside','reference_confirmed'}:
            if type(v) is not bool: raise ValueError(k+' must be boolean')
        elif type(v) not in (int,float) or not math.isfinite(v): raise ValueError(k+' must be finite')
        elif k in {'seed','num_chunks','n_neighbors'}:
            if type(v) is not int or not (0 if k=='seed' else 2)<=v<=(2**31-1 if k=='seed' else 100): raise ValueError(k+' outside range')
        elif k in {'dead_channel_threshold','outside_channel_threshold'}:
            if not -2<=v<0:raise ValueError(k+' outside range')
        elif v<=0:raise ValueError(k+' must be positive')
    if 'p_value' in p and not 0<p['p_value']<1:raise ValueError('Invalid p value')
    if 'r2_threshold' in p and p['r2_threshold']>1:raise ValueError('Invalid r2 threshold')
    if 'window_seconds' in p and not 2<=p['window_seconds']<=10:raise ValueError('Window must be 2–10 seconds')
    if 'chunk_seconds' in p and not .05<=p['chunk_seconds']<=2:raise ValueError('Chunk must be .05–2 seconds')
    return p


def line_targets(facts,p):
    low=facts.get('preprocessing_highpass_hz') or 0
    high=min(facts['sampling_rate_hz']/2,facts.get('preprocessing_lowpass_hz') or math.inf)
    tol=p['tolerance_hz'];notches=facts.get('preprocessing_notch_hz',[])
    return [f for f in p['line_frequencies_hz'] if low<f-tol and f+tol<high and not any(abs(v-f)<=tol for v in notches)]


def evaluate_extension(identifier, facts, params=None):
    p=parameters(identifier,params);r=dict(status='blocked',reason='',parameters=p)
    def stop(reason):return {**r,'reason':reason}
    spec=next(s for s in extension_specs() if s['id']==identifier)
    if facts.get('modality') not in spec['supported_modalities'] or facts.get('verified_voltage') is not True:
        return stop('需要已确认的适用模态与电压单位。')
    fs=facts.get('sampling_rate_hz');seconds=facts.get('window_seconds');n=facts.get('n_eeg')
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (fs,seconds,n)):
        return stop('缺少采样率、通道数或检查时长。')
    if seconds>120 or n*seconds*fs*8>256*1024**2:return stop('按不超过120秒、256MiB输入分块执行。')
    if identifier=='ieeg_spectrum_fit':
        if seconds<p['window_seconds']:return stop('时长不足一个完整多窗检测窗口。')
        if not line_targets(facts,p):return stop('目标工频超出可测频带或已声明滤除，此项未评。')
    elif identifier=='ieeg_mne_lof':
        groups=facts.get('comparison_group_labels')
        if not p['reference_confirmed'] or not isinstance(groups,list) or len(groups)!=n or any(g is None or g=='' for g in groups):
            return stop('需明确逐触点比较组并确认参考可比性。')
        if any(groups.count(g)<=p['n_neighbors'] for g in set(groups)):return stop('每个比较组须多于设定邻居数。')
        if seconds<2:return stop('触点比较至少需要2秒。')
    else:
        band=facts.get('stream_band');groups=facts.get('probe_shanks');geom=facts.get('probe_positions_um')
        if identifier=='spikeinterface_coherence_psd' and (band!='ap' or fs<=1000):return stop('仅AP流且采样率支持300Hz高通。')
        if identifier=='spikeinterface_lfp_neighbors' and band not in {'lf','lfp'}:return stop('仅LF/LFP流；不把相关性规则套到AP。')
        if seconds<2*p['chunk_seconds']:return stop('至少需要两个抽样窗。')
        if not isinstance(groups,list) or len(groups)!=n or any(type(g) is not int or g<0 for g in groups):return stop('缺少逐道shank映射。')
        if not isinstance(geom,list) or len(geom)!=n or any(not isinstance(x,list) or len(x)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in x) for x in geom):return stop('缺少由来源探针定义解析的微米坐标。')
        if identifier=='spikeinterface_coherence_psd' and any(groups.count(g)<=p['n_neighbors'] for g in set(groups)):return stop('每杆通道数须大于邻居数。')
        if identifier=='spikeinterface_lfp_neighbors':
            for i,xy in enumerate(geom):
                if not any(i!=j and groups[i]==groups[j] and 0<math.dist(xy,z)<p['radius_um'] for j,z in enumerate(geom)):
                    return stop('部分通道在所选半径内无邻居；请核对选道和探针位置。')
    return {**r,'status':'ready','reason':'调用原版方法输出复核候选；参数为项目初值。'}


def run_extension(identifier,data_volts,sfreq,channel_names,start_seconds,params,*,facts=None):
    import numpy as np
    import hashlib,inspect,warnings
    from pathlib import Path
    from importlib.metadata import version
    from .extensions import _data_hash
    p=parameters(identifier,params);facts=facts or {};gate=evaluate_extension(identifier,facts,p)
    x=np.asarray(data_volts,dtype=float);names=list(channel_names);fs=float(sfreq);start=float(start_seconds)
    if x.ndim!=2 or min(x.shape)<1 or len(names)!=len(x) or len(set(names))!=len(names) or not math.isfinite(fs) or fs<=0 or not math.isfinite(start):raise ValueError('Invalid source array or identity')
    digest=_data_hash(x);duration=x.shape[1]/fs
    r=dict(schema_version='ephys-extension-result/1.0',extension_id=identifier,status=gate['status'],reason=gate['reason'],
        parameters=p,source=deepcopy(next(s['source'] for s in extension_specs() if s['id']==identifier)),
        range=dict(start_seconds=start,stop_seconds=start+duration,duration_seconds=duration,sampling_rate_hz=fs,n_samples=x.shape[1]),
        channel_names=names,unit='V',candidates=[],measurements=[],calculated=False,input_unchanged=True,automatic_actions=[],data_sha256=digest)
    if gate['status']=='blocked':return r
    if not np.isfinite(x).all():return {**r,'status':'blocked','reason':'非有限值须先复核，不填补后检测。'}
    if facts['n_eeg']!=len(x) or not math.isclose(facts['sampling_rate_hz'],fs) or not math.isclose(facts['window_seconds'],duration,abs_tol=.5/fs):raise ValueError('Source facts mismatch')
    def channel(i,label):return dict(kind=identifier+'_'+label,localization='channel_only',channel_index=i,channel_name=names[i],label=label,analysis_range=[start,start+duration],action='review')
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if identifier=='ieeg_spectrum_fit':
                from mne.filter import _get_window_thresh, _mt_spectrum_remove
                from functools import partial
                fn=_mt_spectrum_remove;package='mne'
                expected=('x','sfreq','line_freqs','notch_widths','window_fun','threshold','get_thresh')
                if tuple(inspect.signature(fn).parameters)!=expected:
                    raise ValueError('Unsupported MNE spectrum_fit kernel signature')
                targets=line_targets(facts,p)
                r['tested_frequencies_hz']=targets
                r['excluded_frequencies_hz']=[v for v in p['line_frequencies_hz'] if v not in targets]
                length=round(p['window_seconds']*fs);get=partial(_get_window_thresh,sfreq=fs,mt_bandwidth=None,p_value=p['p_value'])
                wt,threshold=get(length);rows=[]
                for i,values in enumerate(x):
                    for a in range(0,len(values)-length+1,length):
                        _,freqs=fn(values[a:a+length].copy(),fs,None,None,wt,threshold,get)
                        hit=[float(f) for f in freqs if any(abs(f-target)<=p['tolerance_hz'] for target in targets)]
                        rows.append(dict(channel_name=names[i],start_seconds=start+a/fs,stop_seconds=start+(a+length)/fs,detected_frequencies_hz=hit))
                        if hit:r['candidates'].append(dict(kind='line_frequency_candidate',localization='channel_interval',channel_index=i,channel_name=names[i],start_seconds=start+a/fs,stop_seconds=start+(a+length)/fs,frequencies_hz=hit,action='review'))
                r.update(measurements=rows,assessed_windows=len(rows),candidate_windows=len(r['candidates']),unused_tail_seconds=duration-(x.shape[1]//length)*length/fs)
            elif identifier=='ieeg_mne_lof':
                import mne
                from mne.preprocessing import find_bad_channels_lof
                fn=find_bad_channels_lof;package='mne';groups=facts['comparison_group_labels'];scores=[]
                for g in dict.fromkeys(groups):
                    ids=[i for i,v in enumerate(groups) if v==g];raw=mne.io.RawArray(x[ids].copy(),mne.create_info([names[i] for i in ids],fs,facts['modality']),verbose=False)
                    bad,values=fn(raw,n_neighbors=p['n_neighbors'],threshold=p['threshold'],picks=list(range(len(ids))),return_scores=True,verbose=False)
                    if not np.isfinite(values).all():raise ValueError('Degenerate LOF scores')
                    scores.extend(dict(channel_name=names[i],negative_outlier_factor=float(v),group=g) for i,v in zip(ids,values))
                    r['candidates'].extend(channel(i,'outlier') for i in ids if names[i] in bad)
                r.update(channel_scores=scores,bad_channels=[c['channel_name'] for c in r['candidates']])
            else:
                from spikeinterface import NumpyRecording
                from spikeinterface.preprocessing import detect_bad_channels
                fn=detect_bad_channels;package='spikeinterface';groups=facts['probe_shanks'];labels=['unassessed']*len(names)
                for g in sorted(set(groups)):
                    ids=[i for i,v in enumerate(groups) if v==g];values=x[ids].T.copy()*1e6
                    if np.median(np.std(values,axis=0))<=0:raise ValueError('Degenerate shank signal')
                    rec=NumpyRecording(values,fs,channel_ids=np.array(ids));rec.set_channel_gains(1.);rec.set_channel_offsets(0.)
                    rec.set_channel_locations(np.asarray(facts['probe_positions_um'])[ids])
                    kw=dict(chunk_duration_s=p['chunk_seconds'],num_random_chunks=p['num_chunks'],seed=p['seed'])
                    if identifier=='spikeinterface_coherence_psd':
                        kw.update(method='coherence+psd',psd_hf_threshold=p['psd_hf_threshold'],dead_channel_threshold=p['dead_channel_threshold'],noisy_channel_threshold=p['noisy_channel_threshold'],outside_channel_threshold=p['outside_channel_threshold'],n_neighbors=p['n_neighbors'],highpass_filter_cutoff=300.,direction='y')
                    else:
                        # Original SI defaults apply a 300Hz high-pass even to LF unless explicitly disabled.
                        rec.annotate(is_filtered=True)
                        kw.update(method='neighborhood_r2',neighborhood_r2_threshold=p['r2_threshold'],neighborhood_r2_radius_um=p['radius_um'])
                    _,found=fn(rec,**kw)
                    if len(found)!=len(ids) or not set(found)<={'good','dead','noise','out'}:raise ValueError('Unexpected original detector output')
                    for i,v in zip(ids,found):labels[i]=str(v)
                r['channel_labels']=[dict(channel_name=n,label=labels[i],shank=groups[i]) for i,n in enumerate(names)]
                used={'dead','noise'}|({'out'} if p.get('include_outside') else set())
                r['candidates']=[channel(i,v) for i,v in enumerate(labels) if v in used]
                r['outside_candidates']=[channel(i,v) for i,v in enumerate(labels) if v=='out']
                r['scored_labels']=sorted(used);r['processing_applied_to_detector_copy']=['300 Hz high-pass'] if identifier=='spikeinterface_coherence_psd' else []
        r['source'].update(version=version(package),function=fn.__module__+'.'+fn.__name__,implementation_sha256=hashlib.sha256(Path(inspect.getsourcefile(inspect.unwrap(fn))).read_bytes()).hexdigest())
        r.update(calculated=True,status='completed',reason='检查完成；候选可定位复核。',warnings=list(dict.fromkeys(str(w.message) for w in caught)))
        r['candidate_channel_count']=len({c['channel_name'] for c in r['candidates']})
    except Exception as error:r.update(status='failed',reason=f'{type(error).__name__}: {error}',calculated=False,candidates=[])
    if _data_hash(x)!=digest:raise RuntimeError('Original voltage changed')
    return r
