"""Reproducible scoring checks on seeded signals and frozen local job evidence.

Run with the scientific environment. Outputs are validation evidence, never
expert labels or a clinical-performance benchmark. No source job is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--job',action='append',type=Path,default=[])
    args=parser.parse_args()
    from ephys_qc.scoring import burden_score, SCORE_VERSION
    from ephys_qc.report_aggregate import channel_evidence
    from ephys_qc.report_view import build_report_view, line_summary
    import numpy as np
    from brainelecqc.eeg.continuity import compute_continuity_qc
    from brainelecqc.eeg.spectral import compute_spectral_qc
    from brainelecqc.eeg.muscle import compute_muscle_qc
    sfreq=500; t=np.arange(30*sfreq)/sfreq
    rng=np.random.default_rng(20261031)
    base=rng.normal(0,8e-6,(4,len(t)))+5e-6*np.sin(2*np.pi*10*t)
    ids=[f'synthetic:{c}' for c in range(4)]
    result={'version':SCORE_VERSION,'seed':20261031,'sampling_rate_hz':sfreq,
            'duration_seconds':30,'channels':4,'claim':'engineering_sensitivity_not_expert_calibration',
            'synthetic':[],'real_jobs':[]}
    for kind,seconds in [('line',s) for s in (0,6,12,24)]+[('constant',s) for s in (2,6,12)]:
        data=base.copy();stop=int(seconds*sfreq)
        if kind=='line':data[0,:stop]+=20e-6*np.sin(2*np.pi*60*t[:stop])
        else:data[0,:stop]=0
        cont=compute_continuity_qc(data,sfreq,ids)
        spectral=compute_spectral_qc(data,sfreq,ids)
        hf=compute_muscle_qc(data,sfreq,ids,excluded_intervals=cont['candidates'])
        score=burden_score(channel_evidence(cont,line_summary(spectral['line_noise']),hf['channels']),4)
        row={'kind':kind,'injected_seconds':seconds,'amplitude_volts':20e-6 if kind=='line' else None,
             'value':score['value'],'components':[{k:p[k] for k in ('id','value','numerator','denominator')} for p in score['components']]}
        result['synthetic'].append(row)
        print(kind,seconds,score['value'],flush=True)
    for root in args.job:
        raw=(root/'result.json').read_bytes(); data=json.loads(raw)
        view=build_report_view(data,root/'artifacts',root.name)
        parts=view['score']['components']
        old=sum(100*p['numerator']/p['denominator'] for p in parts)/3 if all(p['value'] is not None for p in parts) else None
        result['real_jobs'].append({'job_id':root.name,'source_result_sha256':hashlib.sha256(raw).hexdigest(),
            'v01_same_evidence':old,'v02':view['score']['value'],'scope':view['scope'],
            'components':[{k:p[k] for k in ('id','value','rms_burden','worst_channel')} for p in parts]})
        assert (root/'result.json').read_bytes()==raw
        print(root.name,old,view['score']['value'],flush=True)
    for kind in ('line','constant'):
        vals=[r['value'] for r in result['synthetic'] if r['kind']==kind]
        result[kind+'_observed_nonincreasing']=all(v is not None for v in vals) and all(a>=b for a,b in zip(vals,vals[1:]))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))


if __name__=='__main__':main()
