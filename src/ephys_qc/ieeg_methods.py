"""Explicit iEEG technical candidates. Project rules, not clinical classifiers."""
from copy import deepcopy
import math

DEFAULTS = {
    'ieeg_range_plateau': {'minimum_samples': 3},
    'ieeg_group_outliers': {'threshold_z': 4., 'minimum_group_channels': 4,
                            'reference_confirmed': False},
}
IDS = frozenset(DEFAULTS)
VERSION = 'ieeg-technical-candidates/0.1'
MAX_CANDIDATE_DETAILS = 10000


def extension_specs():
    definitions = [
        ('ieeg_range_plateau', '文件量程端点平台', 'M03',
         '定位连续落在文件标定上下限的采样点，提示可能削顶。',
         ['EDF/BDF 文件标定范围', '原生电压与采样率'],
         ['触点及平台区间', '命中样本数与有效分母'],
         '逐道按文件物理上下限比较；允许四分之一量化步长的数值容差，连续至少3点才标记。',
         '文件编码范围不等于硬件ADC范围；不能仅凭此结果确认硬件饱和。不以样本最大值估计量程。',
         'https://www.edfplus.info/specs/edf.html'),
        ('ieeg_group_outliers', '分组触点幅度离群', 'M05',
         '在明确比较组内列出幅度明显偏离的触点，供复核。',
         ['逐触点比较组', '已确认组内参考可比较', '每组至少4道有限非恒值信号'],
         ['逐组尺度与逐道偏离值', '候选触点及未评组'],
         '逐道取去中位数后的RMS并取log10，再调用SciPy MAD（normal尺度）计算组内稳健z值；绝对值超过4列为候选。',
         '4道与z=4均为项目试行参数；不同组织、发作或任务活动可造成真实幅度差异，不自动判坏。MAD为0时不构造替代阈值。',
         'https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.median_abs_deviation.html'),
    ]
    rows=[]
    for id_, name, mid, purpose, inputs, outputs, how, limits, url in definitions:
        source={'name':'DBCI-QC 项目规则 / '+('EDF' if mid=='M03' else 'SciPy MAD'),
                'url':url,'license':'项目 MIT；SciPy BSD-3-Clause'}
        rows.append(dict(id=id_,name=name,module_id=mid,category='optional',description=purpose,
            research_modalities=['ecog','seeg'],supported_modalities=['ecog','seeg'],
            implementation='available',status='available',optional_extension=True,
            defaults=deepcopy(DEFAULTS[id_]),inputs=inputs,requirements=inputs,outputs=outputs,
            source=source,limitations=[limits],documentation=dict(purpose=purpose,how_it_works=how,
            interpretation=limits,when_to_use='已确认ECoG或sEEG，且本方法所需字段齐全。',
            when_not_to_use='不适用于头皮或分选单元；缺失条件保留未评。',
            upstream_call='ephys_qc.ieeg_methods.run_extension',
            implementation_origin='本项目独立规则；不是IEEG_Pipelines或ABCD算法的转写。',
            version_note=VERSION,references=[dict(title=source['name'],url=url,kind='官方文档')])) )
    return rows


def parameters(identifier, supplied=None):
    if supplied is not None and (not isinstance(supplied,dict) or set(supplied)-set(DEFAULTS[identifier])):
        raise ValueError('Only declared iEEG method parameters are accepted')
    p={**DEFAULTS[identifier],**(supplied or {})}
    for key in ('minimum_samples','minimum_group_channels'):
        if key in p and (type(p[key]) is not int or not (2 if key=='minimum_samples' else 4)<=p[key]<=10000):
            raise ValueError(key+' is outside the supported integer range')
    if 'threshold_z' in p and (type(p['threshold_z']) not in (int,float) or not math.isfinite(p['threshold_z']) or p['threshold_z']<=0):
        raise ValueError('threshold_z must be finite and positive')
    if 'reference_confirmed' in p and type(p['reference_confirmed']) is not bool:
        raise ValueError('reference_confirmed must be boolean')
    return p


def evaluate_extension(identifier,facts,params=None):
    p=parameters(identifier,params); result=dict(status='blocked',reason='',parameters=p)
    if facts.get('modality') not in {'ecog','seeg'} or facts.get('verified_voltage') is not True:
        return {**result,'reason':'需要已确认的颅内连续电压。'}
    if identifier=='ieeg_range_plateau':
        if facts.get('format') not in {'EDF','BDF'}:
            return {**result,'reason':'当前仅核验EDF/BDF文件量程；其他格式不从信号峰值推测。'}
    else:
        if not facts.get('comparison_group_labels'):
            return {**result,'reason':'需要明确的逐触点比较组，不根据通道名称推断。'}
        if not p['reference_confirmed']:
            return {**result,'status':'partial','reason':'仅计算组内测量；参考可比性未确认，不判离群。'}
    return {**result,'status':'ready','reason':'可按项目试行规则输出技术候选，需结合原始信号复核。'}


def run_extension(identifier,data_volts,sfreq,channel_names,start_seconds,params,*,facts=None):
    import numpy as np
    from scipy.stats import median_abs_deviation
    from .extensions import _data_hash
    from .modules.continuous.common import run_bounds
    facts=facts or {}; p=parameters(identifier,params)
    data=np.asarray(data_volts,dtype=float); names=list(channel_names)
    if (data.ndim!=2 or min(data.shape)<1 or len(names)!=len(data) or len(set(names))!=len(names)
            or any(not isinstance(n,str) or not n for n in names)
            or not math.isfinite(sfreq) or sfreq<=0 or not math.isfinite(start_seconds) or start_seconds<0):
        raise ValueError('Invalid channel identities, voltage array or source clock')
    duration=data.shape[1]/sfreq;digest=_data_hash(data)
    gate=evaluate_extension(identifier,facts,p)
    result=dict(schema_version='ephys-extension-result/1.0',extension_id=identifier,
        status=gate['status'],reason=gate['reason'],parameters=p,
        source={**next(s['source'] for s in extension_specs() if s['id']==identifier),'version':VERSION},
        data_sha256=digest,channel_names=names,unit='V',
        range=dict(start_seconds=start_seconds,stop_seconds=start_seconds+duration,duration_seconds=duration,
                   sampling_rate_hz=sfreq,n_samples=data.shape[1]),
        candidates=[],measurements=[],calculated=False,automatic_actions=[],input_unchanged=True,
        review_status='pending',assessed_channel_names=[])
    from pathlib import Path
    from importlib.metadata import version
    import hashlib
    result['source'].update(adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                            packages={key:version(key) for key in ('numpy','scipy')})
    observed=0
    if gate['status']=='blocked':return result
    if identifier=='ieeg_range_plateau':
        ranges=facts.get('encoding_ranges',[])
        if len(ranges)!=len(names):
            return {**result,'status':'blocked','reason':'实际读取未提供逐道文件标定端点。'}
        for i,(values,limits) in enumerate(zip(data,ranges)):
            if not limits:
                result['measurements'].append(dict(channel_name=names[i],status='unassessed'));continue
            lo,hi,step=limits['minimum_volts'],limits['maximum_volts'],limits['step_volts']
            if not all(math.isfinite(v) for v in (lo,hi,step)) or hi<=lo or step<=0:
                continue
            finite=np.isfinite(values); hit=0
            for side,endpoint in [('lower',lo),('upper',hi)]:
                mask=finite & (np.abs(values-endpoint)<=step/4)
                first,last=run_bounds(mask)
                for a,b in zip(first,last):
                    if b-a<p['minimum_samples']:continue
                    hit+=int(b-a)
                    observed+=1
                    if len(result['candidates'])<MAX_CANDIDATE_DETAILS:result['candidates'].append(dict(kind='encoding_range_plateau',endpoint=side,
                        localization='channel_interval',channel_name=names[i],channel_index=i,
                        start_seconds=start_seconds+int(a)/sfreq,stop_seconds=start_seconds+int(b)/sfreq,
                        duration_seconds=int(b-a)/sfreq,sample_count=int(b-a),action='review'))
            result['assessed_channel_names'].append(names[i])
            result['measurements'].append(dict(channel_name=names[i],status='computed',
                candidate_sample_count=hit,assessed_sample_count=int(finite.sum()),**limits))
    else:
        labels=facts['comparison_group_labels']
        if len(labels)!=len(names):raise ValueError('Group mapping does not match selected rows')
        for group in dict.fromkeys(labels):
            indices=[i for i,g in enumerate(labels) if g==group];x=data[indices]
            # Nonfinite or constant contacts are handled by M03, not silently
            # removed to change the comparison population of this detector.
            finite=np.isfinite(x).all()
            amplitudes=np.sqrt(np.mean((x-np.median(x,axis=1,keepdims=True))**2,axis=1)) if finite else np.full(len(x),np.nan)
            eligible=(finite and len(indices)>=p['minimum_group_channels'] and np.all(amplitudes>0))
            logs=np.log10(amplitudes) if eligible else None
            scale=float(median_abs_deviation(logs,scale='normal')) if eligible else None
            center=float(np.median(logs)) if eligible else None
            valid=eligible and math.isfinite(scale) and scale>1e-12 and p['reference_confirmed']
            for i,amp in zip(indices,amplitudes):
                z=float((math.log10(amp)-center)/scale) if valid else None
                result['measurements'].append(dict(channel_name=names[i],group=group,
                    centered_rms_volts=float(amp) if math.isfinite(amp) else None,
                    log10_group_median=center,log10_group_mad_normal=scale,robust_z=z,
                    status='computed' if valid else 'descriptive_only',
                    reason='' if valid else '组内参考未确认、通道不足、非有限/恒值或MAD为零'))
                if valid:
                    result['assessed_channel_names'].append(names[i])
                    if abs(z)>p['threshold_z']:
                        result['candidates'].append(dict(kind='group_amplitude_outlier',group=group,
                            localization='channel_only',channel_name=names[i],channel_index=i,
                            robust_z=z,analysis_range=[start_seconds,start_seconds+duration],action='review'))
    assessed=len(result['assessed_channel_names'])
    result.update(status='completed' if assessed==len(names) else 'partial',calculated=True,
                  candidate_channel_count=len({c['channel_name'] for c in result['candidates']}),
                  reason='技术候选已计算；不自动删道。' if assessed==len(names) else f'完成{assessed}/{len(names)}道判定；其余只保留测量或未评。')
    result['candidate_total_count']=observed if identifier=='ieeg_range_plateau' else len(result['candidates'])
    if identifier=='ieeg_range_plateau':
        result['candidate_channel_count']=sum(r.get('candidate_sample_count',0)>0 for r in result['measurements'])
    result['candidate_details_truncated']=result['candidate_total_count']>len(result['candidates'])
    if result['candidate_details_truncated']:
        result['reason']+=' 完整计数保留；详细位置达到存储上限。'
    result['input_unchanged']=_data_hash(data)==digest
    return result
