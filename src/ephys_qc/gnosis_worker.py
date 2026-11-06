"""Python 3.12 worker; original SignalQualityEval calls, no algorithm rewrite.

Used only by the trusted local runner. Inputs/outputs stay in a temporary folder.
"""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys
import warnings


def merge_intervals(rows, duration):
    import math
    clipped=[]
    for row in rows:
        a,b=map(float,row)
        if not math.isfinite(a) or not math.isfinite(b) or b<a:
            raise ValueError('Invalid upstream time interval')
        a,b=max(0.,a),min(duration,b)
        if b>a: clipped.append([a,b])
    result=[]
    for a,b in sorted(clipped):
        if result and a<=result[-1][1]: result[-1][1]=max(b,result[-1][1])
        else: result.append([a,b])
    return result


def compute(request, data):
    import numpy as np
    import mne
    import pandas as pd
    import SignalQualityEval
    from SignalQualityEval.tools import utils, powersg
    from eegaux.preprocessing import set_RFN
    if sys.version_info[:2]!=(3,12): raise ValueError('CPython 3.12 required')
    versions={k:metadata.version(k) for k in ['SignalQualityEval','eegaux','eegext','mne','numpy','scipy','pandas']}
    required={'SignalQualityEval':'3.0.0','eegaux':'2.0.9','eegext':'2.1.9','mne':'1.12.1','numpy':'2.4.6','scipy':'1.18.0','pandas':'2.3.3'}
    if versions!=required: raise ValueError('Gnosis environment differs from the verified package versions')
    # Same compatibility alias used by the upstream Notebook with NumPy 2.4.
    if not hasattr(np,'trapz'): np.trapz=np.trapezoid
    mne.set_log_level('ERROR')
    identifier, fs, names, start, p=(request[k] for k in ['id','fs','names','start','parameters'])
    raw=mne.io.RawArray(data.copy(),mne.create_info(names,fs,'eeg'),verbose='ERROR')
    calls=[]
    def call(function,*args,**kwargs):
        calls.append(function.__module__+'.'+function.__name__)
        return function(*args,**kwargs)
    if p['prepare_copy']:
        prepared=call(utils.preprocess_raw,raw.copy(),pick_channels=names,resample=min(256,fs),l_freq=1,h_freq=70,kind_flag=False)
    else:
        prepared=raw.copy()
        # The parent gate requires explicitly verified 1–70 Hz input history.
        with prepared.info._unlock():
            prepared.info['highpass']=1.;prepared.info['lowpass']=70.
    fs2=float(prepared.info['sfreq']);duration=prepared.n_times/fs2; source_duration=data.shape[1]/fs
    out=dict(status='completed',reason='灵犀云原版可选方法计算完成，结果不计入基础总分。',calculated=True,
        candidates=[],candidate_channel_count=0,candidate_interval_count=0,notes=[],metrics={},
        preprocessing=dict(prepared_copy=p['prepare_copy'],sampling_rate_hz=fs2,highpass_hz=1.,lowpass_hz=70.,
            common_average=p['prepare_copy'],ica=False,excluded_channels=[],source_unchanged=True),
        dependencies=[],upstream_calls=calls,
        upstream=dict(packages=versions,module_sha256={m.__name__:hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in [utils,powersg]},
                      worker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    def add_channel(name,kind):
        if name not in names: raise ValueError('Unknown upstream channel')
        out['candidates'].append(dict(kind=kind,localization='channel_only',scope='channel',channel_index=names.index(name),channel_name=name,
            start_seconds=None,stop_seconds=None,analysis_range=[start,start+source_duration],action='review'))
    def add_intervals(mapping,kind):
        if set(mapping)-set(names): raise ValueError('Unknown upstream channel')
        ratios={}
        for name in names:
            if name not in mapping:
                ratios[name]=None;continue
            intervals=merge_intervals(mapping[name],min(duration,source_duration))
            ratios[name]=sum(b-a for a,b in intervals)/source_duration
            for a,b in intervals:
                out['candidates'].append(dict(kind=kind,localization='channel_interval',scope='channel',channel_index=names.index(name),channel_name=name,
                    start_seconds=start+a,stop_seconds=start+b,duration_seconds=b-a,action='review'))
        out['metrics']['ratio_by_channel']=ratios
    def artifact():
        intervals,by_channel=call(utils.get_Artifact,prepared.copy(),on_ch=names,win_len=1,min_duration=.5)
        return merge_intervals(intervals,min(duration,source_duration)),by_channel
    def feature_rows(frame,prefix,bands):
        rows=[]
        for name in names:
            for band in bands:
                v=float(frame.at[0,f'{prefix}_{name}_{band}'])
                if not np.isfinite(v): raise ValueError('Nonfinite upstream feature')
                rows.append(dict(channel_name=name,band=band,value=v))
        return rows
    if identifier=='gnosis_line_length':
        bad=call(utils.get_bad_channels,prepared.copy(),start=0,thresh=p['threshold'],mode='both')
        values=call(utils.cal_linelength_sum,utils.common_average(prepared.get_data()),mode='v1')
        if not np.isfinite(values).all(): raise ValueError('Degenerate line length')
        out['metrics']['line_length_by_channel']={name:float(v) for name,v in zip(names,values)}
        for name in bad: add_channel(str(name),'gnosis_line_length')
        out['notes'].append('未按Notebook自动从后续检测移除线长候选；各项使用用户确认的通道组。')
    elif identifier=='gnosis_artifact':
        intervals,by_channel=artifact();add_intervals(by_channel,identifier)
        out['metrics']['global_intervals']=[[start+a,start+b] for a,b in intervals]
        out['metrics']['global_ratio']=sum(b-a for a,b in intervals)/source_duration
        out['notes'].append('原版内部150μV、0.1秒窗及1秒合并间隔；原版会推断幅值单位并在副本上降采样/陷波。')
    elif identifier in {'gnosis_low_band','gnosis_high_band'}:
        band=(1,13) if identifier=='gnosis_low_band' else (13,40)
        filtered=prepared.copy();call(set_RFN,filtered,None,*band)
        filtered.apply_function(utils.common_average,channel_wise=False)
        # Verify the actual upstream statistic, not just an empty interval list.
        ratios=call(utils.get_power_ratio,filtered.get_data(),fs2,win=1,scale=1e6)
        if not np.isfinite(ratios).all(): raise ValueError('Degenerate band statistic')
        mapping=call(utils.get_abnormal_inertvals,filtered.get_data(),fs2,win=1,scale=1e6,ch_names=names,max_tol_gap=0,thresh=p['threshold'])
        add_intervals(mapping,identifier)
        out['metrics']['band_hz']=list(band)
        out['metrics']['analysis_window_seconds']=1.
        out['metrics']['step_seconds']=.5
    else:
        if p['exclude_artifacts']:
            intervals,_=artifact();clean=[];left=0.
            for a,b in intervals:
                if a-left>10:clean.append([left,a])
                left=b
            if duration-left>10:clean.append([left,duration])
            out['dependencies'].append('gnosis_artifact')
            if not clean: return {**out,'status':'blocked','calculated':False,'reason':'伪差补集中没有持续时间>10秒的片段；本项未评，不记为0或满分。'}
        else: clean=[[0.,duration]]
        x=prepared.get_data()
        uv=np.concatenate([x[:,int(a*fs2):int(b*fs2)] for a,b in clean],axis=-1)*1e6
        out['metrics'].update(used_intervals=[[start+a,start+b] for a,b in clean],effective_duration_seconds=uv.shape[1]/fs2,
            spectral_input='artifact_complement' if p['exclude_artifacts'] else 'all_prepared_samples')
        out['notes'].append('频域输入按原版拼接片段，接缝可能影响频谱/滤波；不把拼接坐标当成原始时间。')
        bands=list(powersg.filter_bands)
        features={}
        if identifier!='gnosis_band_amplitude':
            psd,freqs=call(powersg.cal_psd_freq,uv,fs2,fmin=1,fmax=40)
            if not np.isfinite(psd).all() or np.any(psd<=0):raise ValueError('PSD must be finite and positive')
            out['metrics']['frequencies_hz']=freqs.tolist()
            out['metrics']['psd_uv2_hz']=psd.tolist()
        if identifier in {'gnosis_band_power','gnosis_reference_ranges'}:
            features['bpre']=call(powersg.bands_repower,psd,freqs,names)
            out['metrics']['relative_power']=feature_rows(features['bpre'],'bpre',bands)
        if identifier in {'gnosis_band_amplitude','gnosis_reference_ranges'}:
            features['bpamp']=call(powersg.bands_amp,uv,fs2,names)
            out['metrics']['mean_amplitude_uv']=feature_rows(features['bpamp'],'bpamp',bands)
        if identifier in {'gnosis_psd_deviation','gnosis_reference_ranges'}:
            bad,features['psdist']=call(powersg.detect_bad_channels_psd,psd,freqs,names,threshold=p.get('threshold',3),detect_band='full')
            out['metrics']['psd_distance']=feature_rows(features['psdist'],'psdist',bands+['full'])
            if identifier=='gnosis_psd_deviation':
                for name in bad: add_channel(str(name),identifier)
        if identifier=='gnosis_reference_ranges':
            path=Path(SignalQualityEval.__file__).parent/'Standard'/'threshold_statisitic.csv'
            table=pd.read_csv(path).set_index(['feature','band']);comparisons=[]
            for feature,frame in features.items():
                for row in feature_rows(frame,feature,bands):
                    low,high=map(float,table.loc[(feature,row['band']),['thresh_low','thresh_high']])
                    comparisons.append({**row,'feature':feature,'low':low,'high':high,'comparison':'below' if row['value']<low else 'above' if row['value']>high else 'within'})
            out['metrics']['reference_comparison']=comparisons
            out['upstream']['reference_table_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            out['notes'].append('参考库的人群/设备适配性尚待提供方确认；范围外不等于质量差，未生成雷达归一化质量分。')
    out['candidate_channel_count']=len({c['channel_name'] for c in out['candidates']})
    out['candidate_interval_count']=sum(c.get('start_seconds') is not None for c in out['candidates'])
    return out


def main(folder):
    import numpy as np
    request=json.loads((folder/'request.json').read_text())
    x=np.load(folder/'input.npy',allow_pickle=False)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        try: result=compute(request,x)
        except Exception as e:
            result=dict(status='failed',reason=f'原版方法未完成：{type(e).__name__}: {e}',calculated=False,candidates=[],notes=[])
        result.setdefault('notes',[]).extend(sorted({str(w.message) for w in caught}))
    (folder/'output.json').write_text(json.dumps(result,ensure_ascii=False,allow_nan=False))


if __name__=='__main__': main(Path(sys.argv[1]))
