"""Create explicit comparison plans for the two pinned public package pilots.

Only metadata mapping is dataset-specific. The actual checks are shared D01–D03.
Writes a new local plan; never edits source tables or the download manifest.
"""
import argparse
import json
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'src'))
from ephys_qc.dataset_qc.consistency import entities, validate_consistency


def prepare(root):
    root=Path(root); plan=json.loads((root/'.qc/expectations.json').read_text())
    dataset=plan['source']['dataset_id']
    if dataset not in {'ds003555','ds003029'}: raise ValueError('This helper only maps the two documented public pilots')
    files={f['path'] for f in plan['files']}; records=[]; groups={}
    for i,rec in enumerate(plan['recordings']):
        path=rec['path']; p=Path(path); ent={k:next(iter(v)) for k,v in entities(path).items() if len(v)==1}
        subject='sub-'+ent['sub']; session='ses-'+ent['ses']; derived=path.startswith('derivatives/')
        modality='scalp_eeg' if dataset=='ds003555' else ent['acq']
        group=modality+('-derived' if derived else '-raw')
        prefix=p.name.rsplit('_',1)[0]
        row={'id':prefix+('-derived' if derived else '-raw'),'path':path,'subject':subject,'session':session,
             'modality':modality,'processing':'derived' if derived else 'raw','group':group,
             'channels_tsv':(p.parent/(prefix+'_channels.tsv')).as_posix(),'participants_tsv':'participants.tsv','metadata_json':[]}
        sessions=(('derivatives/' if derived else '')+subject+'/'+subject+'_sessions.tsv')
        if sessions in files:row['sessions_tsv']=sessions
        scans=(p.parent.parent/(subject+'_'+session+'_scans.tsv')).as_posix()
        if scans in files:row['scans_tsv']=scans
        metadata=p.with_suffix('.json').as_posix()
        if metadata in files:row['metadata_json']=[metadata]
        elif dataset=='ds003555' and not derived:row['metadata_json']=['task-hfo_eeg.json']
        event=(p.parent/(prefix+'_events.tsv')).as_posix()
        if event in files:
            row['events']={'path':event,'mode':'indices' if dataset=='ds003555' else 'seconds'}
            if dataset=='ds003555':row['events']['origin']=None # Original description does not specify 0/1 indexing.
        records.append(row)
        groups[group]={'id':group,'label':{'scalp_eeg':'头皮 EEG','ecog':'ECoG','seeg':'sEEG'}[modality]+(' · 派生片段' if derived else ' · 原始记录'),
                       'same_channels':modality=='scalp_eeg','same_rates':True,'same_units':True,'same_reference':True}
    plan['consistency']={'schema_version':'dataset-consistency-plan/1','records':records,'groups':list(groups.values()),
                         'basis':'按固定公开数据说明分组；头皮 EEG 固定导联；不同患者颅内通道布局允许不同；原始/派生分开。'}
    validate_consistency(plan)
    return plan


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('root',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    with args.output.open('x',encoding='utf-8') as f:json.dump(prepare(args.root),f,ensure_ascii=False,indent=2);f.write('\n')
