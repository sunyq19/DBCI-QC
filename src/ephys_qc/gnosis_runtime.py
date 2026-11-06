"""Bounded subprocess bridge to separately installed vendor wheels."""
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

from .gnosis_catalog import IDS, SOURCE, extension_specs


def parameters(identifier, supplied=None):
    if identifier not in IDS:
        raise ValueError('Unknown Gnosis method')
    default = next(s['defaults'] for s in extension_specs() if s['id'] == identifier)
    if supplied is not None and (not isinstance(supplied, dict) or set(supplied)-set(default)):
        raise ValueError('Only declared Gnosis parameters are accepted')
    p = {**default, **deepcopy(supplied or {})}
    for k,v in p.items():
        if k in {'prepare_copy','exclude_artifacts'}:
            if type(v) is not bool:
                raise ValueError(k+' must be boolean')
        elif type(v) not in {int,float} or not math.isfinite(v) or not 0 < v <= 100:
            raise ValueError(k+' must be a finite number in (0,100]')
    return p


def evaluate_extension(identifier, facts, params=None):
    p = parameters(identifier, params)
    out = dict(status='blocked', reason='', parameters=p)
    def blocked(reason): return {**out, 'reason':reason}
    if not isinstance(facts,dict) or facts.get('modality') != 'scalp_eeg' or facts.get('verified_voltage') is not True:
        return blocked('仅用于已确认单位V的头皮EEG。')
    fs, seconds, n = (facts.get(k) for k in ('sampling_rate_hz','window_seconds','n_eeg'))
    if any(type(v) not in {int,float} or not math.isfinite(v) for v in (fs,seconds,n)):
        return blocked('缺少有效采样率、时长或通道数。')
    if type(n) is not int or not 3 <= n <= 128 or not 12 <= seconds <= 120 or not 140 < fs <= 10000 or n*seconds*fs*8 > 256*1024**2:
        return blocked('本适配支持3–128道、12–120秒、采样率>140Hz且输入不超过256MiB。')
    groups=facts.get('comparison_groups')
    if facts.get('reference_scheme') not in {'common_reference','linked_ears'} or not isinstance(groups,dict) or len(groups)!=1 or list(groups.values()) != [n]:
        return blocked('请确认共同/连接耳参考，并把所选通道声明为同一比较组。')
    hp,lp=facts.get('preprocessing_highpass_hz'),facts.get('preprocessing_lowpass_hz')
    for v in (hp,lp):
        if v is not None and (type(v) not in {int,float} or not math.isfinite(v) or v<0):
            return blocked('滤波史频率无效。')
    if (hp is not None and hp>1) or (lp is not None and lp<70):
        return blocked('当前首版按原示例1–70Hz准备数据，已知源滤波范围不足。')
    if not p['prepare_copy'] and (fs>256 or not facts.get('preprocessing_verified') or hp != 1 or lp != 70):
        return blocked('关闭副本准备需先确认输入≤256Hz、1–70Hz及处理史；参考仍由各原版方法按需处理。')
    return {**out,'status':'ready','reason':'可选原版方法；在分析副本上运行，测量和候选不计入基础总分。'}


def settings():
    root=Path(__file__).resolve().parents[2]
    path=Path(os.environ.get('DBCI_QC_GNOSIS_CONFIG',root/'.local/gnosis-runtime.json'))
    c=json.loads(path.read_text())
    if set(c)!={'python'} or not isinstance(c['python'],str) or not Path(c['python']).is_absolute() or not os.access(c['python'],os.X_OK):
        raise ValueError('Configure an absolute Gnosis Python executable')
    return c


def run_extension(identifier,data_volts,sfreq,channel_names,start_seconds,params,*,facts=None):
    import numpy as np
    from .extensions import _data_hash
    p=parameters(identifier,params)
    x=np.asarray(data_volts)
    if x.ndim!=2 or not x.size or x.dtype.kind not in 'fiu' or not np.isfinite(x).all():
        raise ValueError('Expected finite channel-by-sample voltage')
    names=list(channel_names)
    if len(names)!=len(x) or any(not isinstance(n,str) or not n for n in names) or len(set(names))!=len(names):
        raise ValueError('Distinct channel names must match rows')
    if type(sfreq) not in {int,float} or not math.isfinite(sfreq) or sfreq<=0 or type(start_seconds) not in {int,float} or not math.isfinite(start_seconds) or start_seconds<0:
        raise ValueError('Invalid source clock')
    gate=evaluate_extension(identifier,facts,p)
    digest=_data_hash(x)
    result=dict(schema_version='ephys-extension-result/1.0',extension_id=identifier,status=gate['status'],reason=gate['reason'],parameters=p,
        source=deepcopy(SOURCE),data_sha256=digest,channel_names=names,unit='V',calculated=False,
        range=dict(start_seconds=start_seconds,stop_seconds=start_seconds+x.shape[1]/sfreq,duration_seconds=x.shape[1]/sfreq,sampling_rate_hz=sfreq,n_samples=x.shape[1]),
        candidates=[],notes=[],automatic_actions=[],input_unchanged=True,review_status='pending')
    if gate['status']=='blocked': return result
    if facts['n_eeg']!=len(x) or facts['sampling_rate_hz']!=sfreq or not math.isclose(facts['window_seconds'],x.shape[1]/sfreq,abs_tol=.5/sfreq):
        return {**result,'status':'blocked','reason':'已声明事实与实际数据不一致。'}
    if np.any(np.ptp(x,axis=1)==0):
        return {**result,'status':'blocked','reason':'存在恒值通道，统计可能退化；先核对完整性结果。'}
    try: c=settings()
    except (OSError,ValueError,TypeError):
        return {**result,'status':'blocked','reason':'尚未安装/配置灵犀云Python 3.12运行环境。'}
    with tempfile.TemporaryDirectory(prefix='dbci-gnosis-') as td:
        folder=Path(td); np.save(folder/'input.npy',np.asarray(x,dtype=float),allow_pickle=False)
        (folder/'request.json').write_text(json.dumps(dict(id=identifier,fs=sfreq,names=names,start=start_seconds,parameters=p)))
        env={**os.environ,'MPLBACKEND':'Agg','OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1','MKL_NUM_THREADS':'1'}
        job=subprocess.run([c['python'],str(Path(__file__).with_name('gnosis_worker.py')),td],capture_output=True,text=True,env=env,timeout=180)
        if job.returncode or not (folder/'output.json').is_file():
            return {**result,'status':'failed','reason':'原版执行进程未完成；请核对运行环境，未把空结果解释为通过。'}
        detail=json.loads((folder/'output.json').read_text())
    result.update(detail)
    result['input_unchanged']=_data_hash(x)==digest
    if not result['input_unchanged']: raise RuntimeError('Input changed unexpectedly')
    return result
