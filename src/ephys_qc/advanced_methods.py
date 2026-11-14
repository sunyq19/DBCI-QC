"""Read-only upstream adapters. Coordinates are source metadata, never label guesses."""
from copy import deepcopy
from importlib.util import find_spec
import math

DEFAULTS = {
    'pyprep_ransac': {'n_samples': 50, 'sample_prop': .25, 'corr_thresh': .75, 'frac_bad': .4, 'corr_window_secs': 5., 'random_state': 0},
    'autoreject_epochs': {'epoch_duration_seconds': 2., 'cv': 5, 'random_state': 0},
    'ica_iclabel': {'max_components': 20, 'random_state': 0},
    'dredge_lfp': {'max_disp_um': 100., 'mincorr': .8},
}
IDS = frozenset(DEFAULTS)
ROWS = [
 ('pyprep_ransac','PyPREP 空间预测 / RANSAC','M05','scalp_eeg',
  '比较实测波形与其他电极的空间预测，寻找难以预测的通道。',
  ['头皮 EEG；16–256道、至少30秒、采样率至少100 Hz', '文件内完整且不重复的头坐标（米）；已确认共同参考或连接耳参考'],
  ['通道候选','逐道预测相关及异常窗口占比','可选通道占比分数'],
  'PyPREP','https://pyprep.readthedocs.io/en/stable/generated/pyprep.NoisyChannels.html','MIT',
  '先按原版排查偏差、相关及掉线再进行空间预测；已排除的通道不计为预测通过。'),
 ('autoreject_epochs','local AutoReject 分段与通道','M03','scalp_eeg',
  '交叉验证学习各通道峰峰值阈值，给出哪些通道在哪个片段超阈值。',
  ['头皮 EEG；8–256道；至少20个完整分段，且不少于4倍交叉验证折数','默认2秒分段；文件内有效头坐标；非双极或混合参考'],
  ['逐道峰峰值阈值','片段×通道标签','整段剔除建议','可选通道片段占比分数'],
  'autoreject','https://autoreject.github.io/stable/auto_examples/plot_auto_repair.html','BSD-3-Clause',
  '连续数据按固定2秒分段，不冒充任务试次；仅fit/get_reject_log，不执行修复、插值或删除。'),
 ('ica_iclabel','ICA 成分类别 / ICLabel','M06','scalp_eeg',
  '在分析副本上分解 ICA，给出脑、眼动、肌电、心电等成分类别及概率。',
  ['头皮 EEG；8–256道、至少60秒；采样率高于200 Hz','文件内有效头坐标；非双极/混合参考；已知低通小于100 Hz时不运行'],
  ['七类成分概率','分解秩与成分数','分析副本处理记录'],
  'MNE-ICALabel','https://mne.tools/mne-icalabel/stable/generated/examples/00_iclabel.html','BSD-3-Clause',
  '副本平均参考、1–100Hz滤波、extended-infomax；最多20成分。概率不是质量分，不自动移除成分；未知处理史须复核适用性。'),
 ('dredge_lfp','DREDge LF 探针漂移','M05','extracellular',
  '估计 LF/LFP 沿探针深度的相对位移，辅助查看记录稳定性。',
  ['Neuropixels LF/LFP；至少16道、10秒、采样率高于250 Hz','来源探针位置和shank，每杆至少16道及8个深度'],
  ['每杆相对位移曲线（µm）','位移范围','处理参数和参考区块'],
  'SpikeInterface / DREDge','https://spikeinterface.readthedocs.io/en/latest/how_to/drift_with_lfp.html','MIT',
  '每个分析块独立估计刚性位移；块间零点不能拼成绝对位移。仅测量，不做漂移校正或自动扣分；AP流程不适用。'),
]


def extension_specs():
    rows = [dict(id=k,name=name,module_id=mid,category='optional',optional_extension=True,
        implementation='available',status='available',research_modalities=[mod],description=desc,
        inputs=req,requirements=req,outputs=out,defaults=deepcopy(DEFAULTS[k]),
        source=dict(name=src,url=url,license=lic),limitations=[note,
        '默认关闭。阈值与运行范围为方法/项目配置，尚非专家审核的合格标准。'])
        for k,name,mid,mod,desc,req,out,src,url,lic,note in ROWS]
    calls={'pyprep_ransac':'pyprep.NoisyChannels.find_bad_by_ransac','autoreject_epochs':'autoreject.AutoReject.fit / get_reject_log','ica_iclabel':'mne.preprocessing.ICA.fit / mne_icalabel.iclabel.iclabel_label_components','dredge_lfp':'spikeinterface.sortingcomponents.motion.estimate_motion(method=dredge_lfp)'}
    for row in rows:
        row['documentation']=dict(purpose=row['description'],how_it_works=row['limitations'][0],interpretation='候选与测量需要结合原信号复核；不是专家认定的合格线。',when_to_use='；'.join(row['requirements']),when_not_to_use='条件不足或其他模态；不得补造坐标、滤波史或量程。',upstream_call=calls[row['id']],references=[dict(title=row['source']['name'],url=row['source']['url'],kind='官方文档'),dict(title='本项目适配接口',url='src/ephys_qc/advanced_methods.py',kind='本项目封装')],implementation_origin='直接调用固定版本的上游实现，平台仅做条件检查和结果适配。',validation_status='公开数据工程执行已验证；检测准确性尚未独立验证。',version_note='实现及依赖版本写入每次方法结果；接口约定见 docs/design/public-methods-v1.md。')
    return rows


def parameters(identifier, supplied=None):
    p=deepcopy(DEFAULTS[identifier])
    if supplied is not None and (not isinstance(supplied,dict) or set(supplied)-set(p)):
        raise ValueError('Unknown method parameters')
    p.update(supplied or {})
    for k,v in p.items():
        if type(v) not in (int,float) or not math.isfinite(v) or v<0: raise ValueError('Invalid parameter: '+k)
    for k in ('n_samples','cv','max_components','random_state'):
        if k in p and type(p[k]) is not int: raise ValueError(k+' must be integer')
    if not 0<=p.get('random_state',0)<2**32: raise ValueError('Invalid random_state')
    if identifier=='pyprep_ransac' and not (10<=p['n_samples']<=100 and .1<=p['sample_prop']<=.5 and 0<p['corr_thresh']<1 and 0<p['frac_bad']<1 and 1<=p['corr_window_secs']<=10): raise ValueError('RANSAC parameters out of range')
    if identifier=='autoreject_epochs' and not (1<=p['epoch_duration_seconds']<=10 and 2<=p['cv']<=10): raise ValueError('AutoReject parameters out of range')
    if identifier=='ica_iclabel' and not 4<=p['max_components']<=32: raise ValueError('max_components must be 4–32')
    if identifier=='dredge_lfp' and not (10<=p['max_disp_um']<=500 and 0<p['mincorr']<1): raise ValueError('DREDge parameters out of range')
    return p


def valid_positions(positions,n,dimensions=3):
    return (isinstance(positions,list) and len(positions)==n and n>0 and
        all(isinstance(v,(list,tuple)) and len(v)==dimensions and
            all(type(x) in (int,float) and math.isfinite(x) for x in v) and
            (dimensions!=3 or .01<sum(x*x for x in v)**.5<.3) for v in positions) and
        len({tuple(v) for v in positions})==n)


def evaluate_extension(identifier,facts,params=None):
    p=parameters(identifier,params); result=dict(status='blocked',parameters=p,reason='')
    def no(s):return {**result,'reason':s}
    facts=facts if isinstance(facts,dict) else {}
    n=facts.get('n_eeg',0); fs=facts.get('sampling_rate_hz') or 0; seconds=facts.get('window_seconds') or 0
    if not facts.get('verified_voltage'):return no('需要已核实的电压单位。')
    mod='extracellular' if identifier=='dredge_lfp' else 'scalp_eeg'
    if facts.get('modality')!=mod:return no('该方法不适用于当前模态。')
    if seconds>120:return no('整份检查按最多120秒分析块运行；请使用整份检查入口。')
    dependency={'pyprep_ransac':'pyprep','autoreject_epochs':'autoreject','ica_iclabel':'mne_icalabel','dredge_lfp':'torch'}[identifier]
    if find_spec(dependency) is None:return no('运行环境缺少 '+dependency+'；安装后可使用。')
    if identifier=='dredge_lfp':
        if str(facts.get('stream_band','')).upper() not in {'LF','LFP'}:return no('仅用于已确认的LF/LFP流；AP需独立的峰检测漂移流程。')
        pos=facts.get('probe_positions_um',[]);shanks=facts.get('probe_shanks',[])
        if not valid_positions(pos,n,2) or len(shanks)!=n or any(v is None for v in shanks):return no('缺少完整的来源探针位置或shank。')
        if fs<=250 or seconds<10 or n<16:return no('至少16道、10秒，且原采样率高于250Hz。')
        for shank in set(shanks):
            sub=[pos[i][1] for i,s in enumerate(shanks) if s==shank]
            if len(sub)<16 or len(set(sub))<8:return no('每杆至少16道、8个不同深度。')
    else:
        if n>256:return no('本版空间EEG方法最多分析256道。')
        if not valid_positions(facts.get('electrode_positions_m'),n) or facts.get('electrode_coordinate_frame')!='head':return no('需要文件中完整、有效的头坐标（米）；不按通道名补坐标。')
        if facts.get('reference_scheme') in {'bipolar','mixed'}:return no('空间头皮方法不用于双极或混合参考。')
        if identifier=='pyprep_ransac':
            if facts.get('reference_scheme') not in {'common_reference','linked_ears'}:return no('先确认共同参考或连接耳参考。')
            if n<16 or seconds<max(30,3*p['corr_window_secs']) or fs<100:return no('至少16道、30秒、100Hz。')
        if identifier=='autoreject_epochs' and (n<8 or math.floor(seconds/p['epoch_duration_seconds'])<max(20,4*p['cv'])):return no('至少8道和20个完整分段（且不少于4×交叉验证折数）。')
        if identifier=='ica_iclabel':
            if n<8 or seconds<60 or fs<=200:return no('至少8道、60秒，采样率高于200Hz。')
            if facts.get('preprocessing_lowpass_hz') is not None and facts['preprocessing_lowpass_hz']<100:return no('已知低通小于100Hz，不满足ICLabel训练频带。')
            if find_spec('onnxruntime') is None:return no('缺少ICLabel推理依赖onnxruntime。')
    return {**result,'status':'ready','reason':'条件满足；在副本上计算，保留原始输入。'}


def run_extension(identifier,data_volts,sfreq,channel_names,start_seconds,parameters,*,facts=None):
    import numpy as np
    from importlib.metadata import version
    from .extra_methods import _base_result,_epochs
    facts=deepcopy(facts or {});p=globals()['parameters'](identifier,parameters)
    x=np.array(data_volts,dtype=float,copy=True); names=list(channel_names);fs=float(sfreq)
    if x.ndim!=2 or len(names)!=len(x) or len(set(names))!=len(names) or not np.isfinite(x).all():raise ValueError('需要有限、唯一通道身份的通道×采样数组。')
    facts.update(n_eeg=len(x),sampling_rate_hz=fs,window_seconds=x.shape[1]/fs)
    verdict=evaluate_extension(identifier,facts,p)
    if verdict['status']=='blocked':return dict(status='blocked',calculated=False,reason=verdict['reason'],candidates=[])
    out=_base_result('autoreject_global',x,fs,names,start_seconds,p,verdict)
    spec=next(s for s in extension_specs() if s['id']==identifier)
    out.update(extension_id=identifier,source=spec['source'],status='completed',calculated=True,measurements=[])
    out['source']['version']=version({'pyprep_ransac':'pyprep','autoreject_epochs':'autoreject','ica_iclabel':'mne-icalabel','dredge_lfp':'spikeinterface'}[identifier])
    out['notes']=spec['limitations']; out['automatic_actions']=[]
    if identifier=='dredge_lfp':
        return _drift(out,x,fs,names,facts,p,start_seconds)
    import mne
    info=mne.create_info(names,fs,ch_types='eeg')
    info.set_montage(mne.channels.make_dig_montage(ch_pos=dict(zip(names,facts['electrode_positions_m'])),coord_frame='head'))
    raw=mne.io.RawArray(x,info,verbose=False)
    if identifier=='pyprep_ransac':
        from pyprep import NoisyChannels
        detector=NoisyChannels(raw,random_state=p['random_state'],reject_by_annotation=None)
        detector.find_bad_by_deviation();detector.find_bad_by_correlation()
        detector.find_bad_by_ransac(**{k:v for k,v in p.items() if k!='random_state'})
        excluded=set(detector.bad_by_nan+detector.bad_by_flat)
        assessed=[n for n in names if n not in excluded]
        correlations=detector._extra_info['bad_by_ransac']['ransac_correlations']
        fractions=detector._extra_info['bad_by_ransac']['bad_window_fractions']
        # PyPREP fills dropped channels with correlation 1; those are not valid RANSAC observations.
        out['assessed_channel_names']=assessed;out['unassessed_channel_names']=sorted(excluded)
        if excluded:out.update(status='partial',reason='部分通道未参与空间预测；保留测量，本项不计入综合分。')
        out['predictor_exclusions']=sorted(set(detector.bad_by_deviation+detector.bad_by_correlation+detector.bad_by_dropout)|excluded)
        out['channel_names']=assessed
        out['measurements']=[dict(channel_name=n,bad_window_fraction=float(fractions[i]),correlations=correlations[:,i].tolist()) for i,n in enumerate(names) if n in assessed]
        out['candidates']=[dict(channel_name=n,localization='channel_only',kind='spatial_prediction',analysis_range=[start_seconds,start_seconds+x.shape[1]/fs]) for n in detector.bad_by_ransac if n in assessed]
        out['preprocessing']={'pipeline':'PyPREP detrend and internal lowpass; original data unchanged'}
    elif identifier=='autoreject_epochs':
        from autoreject import AutoReject
        values,seg=_epochs(x,fs,p['epoch_duration_seconds'],start_seconds)
        epochs=mne.EpochsArray(values,info,verbose=False)
        ar=AutoReject(n_interpolate=[1,4],consensus=[.25,.5,.75,1.],cv=p['cv'],random_state=p['random_state'],n_jobs=1,verbose=False)
        ar.fit(epochs);log=ar.get_reject_log(epochs)
        if not np.isfinite(log.labels).all():raise ValueError('AutoReject存在未评通道，不输出完整分数。')
        out.update(segmentation=seg,labels=log.labels.astype(int).tolist(),bad_epochs=log.bad_epochs.tolist(),thresholds_volts={n:float(v) for n,v in ar.threshes_.items()})
        for e,c in zip(*np.where(log.labels>0)):
            interval=seg['ranges'][int(e)]
            out['candidates'].append(dict(channel_name=names[c],epoch_index=int(e),localization='channel_interval',kind='local_amplitude',start_seconds=interval['start_seconds'],stop_seconds=interval['stop_seconds']))
        out['metrics']={'candidate_channel_epochs':int((log.labels>0).sum()),'assessed_channel_epochs':int(log.labels.size),'bad_epochs':int(log.bad_epochs.sum())}
    else:
        from mne_icalabel.iclabel import iclabel_label_components
        raw.filter(1.,100.,verbose=False);raw.set_eeg_reference('average',projection=False,verbose=False)
        rank=int(mne.compute_rank(raw,rank=None,verbose=False)['eeg']);components=min(rank,p['max_components'])
        if components<4:raise ValueError('有效秩不足4，无法进行本版ICA分类。')
        ica=mne.preprocessing.ICA(n_components=components,method='infomax',fit_params={'extended':True},random_state=p['random_state'],max_iter=512)
        ica.fit(raw,verbose=False)
        probs=iclabel_label_components(raw,ica,inplace=False,backend='onnx')
        classes=['brain','muscle','eye','heart','line_noise','channel_noise','other']
        if probs.shape!=(components,7) or not np.isfinite(probs).all():raise ValueError('成分概率不完整。')
        out['components']=[dict(component=i,label=classes[int(np.argmax(row))],probabilities=dict(zip(classes,map(float,row)))) for i,row in enumerate(probs)]
        out['preprocessing']={'reference':'average','filter_hz':[1,100],'ica':'extended-infomax','rank':rank,'components':components,'max_iter':512,'n_iter':int(ica.n_iter_),'source_processing_known':bool(facts.get('preprocessing_verified'))}
        out['reason']='已完成成分分类；概率仅用于复核，不换算质量分。'
    out['candidate_channel_count']=len({c['channel_name'] for c in out['candidates']})
    out['candidate_interval_count']=sum('start_seconds' in c for c in out['candidates'])
    return out


def _drift(out,x,fs,names,facts,p,start):
    import numpy as np
    import torch
    import spikeinterface as si
    import spikeinterface.preprocessing as sp
    from spikeinterface.sortingcomponents.motion import estimate_motion
    torch.set_num_threads(1)
    pos=np.asarray(facts['probe_positions_um']);shanks=np.asarray(facts['probe_shanks'])
    traces=[]
    for shank in sorted(set(shanks)):
        ids=np.where(shanks==shank)[0]
        recording=si.NumpyRecording([x[ids].T.astype('float32')],sampling_frequency=fs)
        recording.set_channel_locations(pos[ids]);recording.set_channel_gains(1e6);recording.set_channel_offsets(0.)
        # Materialize this complete analysis block before resampling: a short
        # default filter margin is unsafe for LF high-pass filtering.
        filtered_lazy=sp.bandpass_filter(recording,freq_min=.5,freq_max=100.,ignore_low_freq_error=True,margin_ms=10000.)
        filtered=si.NumpyRecording([filtered_lazy.get_traces()],sampling_frequency=fs)
        filtered.set_channel_locations(pos[ids])
        resampled=sp.resample(filtered,resample_rate=250)
        averaged=sp.average_across_direction(resampled,direction='y')
        motion=estimate_motion(averaged,method='dredge_lfp',rigid=True,direction='y',chunk_len_s=2.,max_disp_um=p['max_disp_um'],mincorr=p['mincorr'],device='cpu',progress_bar=False)
        d=np.asarray(motion.displacement[0]).ravel();t=np.asarray(motion.temporal_bins_s[0])
        if not len(d) or not np.isfinite(d).all():raise ValueError('DREDge未返回有效位移。')
        # Use a declared within-block origin. Never stitch independent origins.
        d=d-d[0]
        traces.append(dict(shank=int(shank),time_seconds=(t+start).tolist(),displacement_um=d.tolist(),range_um=float(np.ptp(d)),reference_seconds=float(t[0]+start)))
    out.update(motion=traces,preprocessing={'filter_hz':[.5,100.],'resample_hz':250,'average_equal_depth':True,'phase_shift_applied':False,'registration':'rigid_per_shank_per_block'},reason='已输出块内相对位移；尚无通用扣分阈值。')
    return out
