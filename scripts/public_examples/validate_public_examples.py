"""Read-only 0.1-second probes plus planning/annotation checks; no runtime jobs."""
import copy,hashlib,json,sys
from pathlib import Path
from dataset_paths import paths
args=paths();sys.path.insert(0,str(args.repo_root/'src'))
from ephys_qc.planning import build_plan
from ephys_qc.annotations import check_annotations
from ephys_qc.runtime import _read_window
from brainelecqc.readers.edf import EdfBdfReader
w=args.evidence_dir;regs=json.loads((w/'registration_additions.json').read_text());checks=[]
for r in regs['inputs']:
    p=build_plan(r);sel=p['qc_config']['selection']
    assert sel['duration_seconds']<=120
    assert hashlib.sha256(Path(r['source_path']).read_bytes()).hexdigest()==r['expected_sha256']
    assert r['reference_scheme'] in {'bipolar','unknown'} and r['default_config']['method_config']['comparison_groups'] is None
    reader=EdfBdfReader(r['source_path'],r['id']);description=reader.describe()
    state={'reader':reader,'description':description}
    short=copy.deepcopy(p['qc_config']);short['selection']['duration_seconds']=0.1
    payload=_read_window(state,short)
    result={'id':r['id'],'plan_id':p['plan_id'],'source_hash_match':True,'selection_duration_seconds':sel['duration_seconds'],'all_selected_channels_same_native_sampling_clock':True,'probe_requested_seconds':0.1,'probe_actual_seconds':payload['recording']['duration_seconds'],'read_probe_shape':list(state['data'].shape),'actual_sampling_rate_hz':state['fs'],'actual_units':payload['recording']['unit'],'stream_count':len(description['streams']),'reader_warnings':description.get('warnings',[]),'quality_ground_truth':False}
    if r.get('annotation'):
        a=check_annotations(r['annotation'],sel['start_seconds'],sel['duration_seconds'],state['fs'],r['metadata']['duration_seconds'])
        result['annotation']={k:a[k] for k in ['format','status','total_rows','selected_count','stage_seconds','covered_seconds','uncovered_intervals','issues','quality_ground_truth','used_for_signal_detection']}
        assert not a['quality_ground_truth'] and not a['used_for_signal_detection']
        assert not a['issues'],a['issues']
        if r['id']=='sleep-edfx-sc4001':assert a['stage_seconds']=={'W':30.0,'R&K 1':90.0}
        if r['id']=='chbmit-chb01-03':assert a['selected_count']==1 and a['events'][0]['selected_start_seconds']==2996 and a['events'][0]['selected_stop_seconds']==3036
    checks.append(result)
    print(r['id'],'read_probe',result['read_probe_shape'],'fs',state['fs'],'annotation',result.get('annotation',{}).get('status'))
base=args.data_root/'sleep-edfx-1.0.0-sc4001'
with (base/'SC4001E0-PSG.edf').open('rb') as f:x=f.read(256)
with (base/'SC4001EC-Hypnogram.edf').open('rb') as f:y=f.read(256)
assert x[168:184]==y[168:184]
(w/'validation.json').write_text(json.dumps({'records':checks,'sleep_clock_header_matches':True,'runtime_jobs_created':0,'signal_processing_or_modification':False},ensure_ascii=False,indent=2)+'\n')
