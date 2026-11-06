"""Run the original Gnosis optional leaves on an explicitly supplied local sample.

Usage: python scripts/validate_gnosis.py FILE --output LOCAL_DIR [--seconds 30]
This is an adapter smoke test, not an expert-labelled accuracy benchmark.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ephys_qc.gnosis_catalog import IDS
from ephys_qc.gnosis_runtime import run_extension

def main():
    import mne
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=float,default=30)
    a=p.parse_args()
    reader={'.edf':mne.io.read_raw_edf,'.bdf':mne.io.read_raw_bdf,'.set':mne.io.read_raw_eeglab}[a.file.suffix.lower()]
    raw=reader(a.file,preload=False,verbose='ERROR')
    eeg=mne.pick_types(raw.info,eeg=True,exclude=[])
    n=min(round(a.seconds*raw.info['sfreq']),raw.n_times)
    data=raw.get_data(picks=eeg,start=0,stop=n);names=[raw.ch_names[i] for i in eeg];fs=float(raw.info['sfreq'])
    facts=dict(modality='scalp_eeg',verified_voltage=True,n_eeg=len(eeg),sampling_rate_hz=fs,window_seconds=n/fs,
               reference_scheme='common_reference',comparison_groups={'test_cohort':len(eeg)})
    a.output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for method in sorted(IDS):
        result=run_extension(method,data,fs,names,0.,{},facts=facts)
        (a.output/(method+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
        row={k:result.get(k) for k in ['extension_id','status','reason','calculated','candidate_channel_count','candidate_interval_count','input_unchanged']}
        row['effective_seconds']=result.get('metrics',{}).get('effective_duration_seconds')
        rows.append(row);print(method,row['status'],row['candidate_channel_count'],row['effective_seconds'],flush=True)
    summary=dict(source_file=a.file.name,source_sha256=hashlib.sha256(a.file.read_bytes()).hexdigest(),sampling_rate_hz=fs,channels=len(eeg),seconds=n/fs,
                 assumption='接口验收统一声明比较组；不作为来源参考方式确认或准确率验证。',results=rows)
    (a.output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
