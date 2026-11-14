"""Assemble provenance-backed demo manifests and run the ordinary QC workers.

The build uses an isolated runtime. Publishing into the live workbench is a
separate step after all reports have passed validation.
"""
import argparse
import copy
import json
from pathlib import Path
import shutil
import sys
import time

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench'),str(REPO/'scripts')]
from prepare_eight_datasets import DEFAULT_ROOT,sha,save
from prepare_local_example_datasets import freeze_extra

SPECS={
 'example-seeg':('03_sEEG_HUP同来源队列','sEEG · 临床发作','sEEG · Clinical seizures','两位受试者 · 同一研究','Two participants · one study','EDF','seeg',dict(name='HUP iEEG Epilepsy Dataset',url='https://openneuro.org/datasets/ds004100/versions/1.1.3',version='1.1.3',license='CC0')),
 'example-rest-eeg':('05_EEG_睁眼静息','EEG · 睁眼静息','EEG · Eyes-open rest','两位受试者 · 灵犀云方案','Two participants · Gnosis workflow','EEGLAB','scalp_eeg',dict(name='Rest eyes open · ds004584',url='https://openneuro.org/datasets/ds004584/versions/1.0.0',version='1.0.0',license='CC0')),
 'example-sleep-eeg':('06_EEG_睡眠多导','EEG · 睡眠多导','EEG · Sleep PSG','两位受试者 · 辅助导联与分期','Two participants · auxiliary leads and sleep stages','EDF','scalp_eeg',dict(name='HMC Sleep Staging Database',url='https://physionet.org/content/hmc-sleep-staging/1.1/',version='1.1',license='CC-BY-4.0')),
 'example-speech-ecog':('07_ECoG_语音任务','ECoG · 语音任务','ECoG · Speech','两位受试者 · NWB 连续电压','Two participants · continuous voltage in NWB','NWB','ecog',dict(name='Speech articulation · DANDI 000019',url='https://dandiarchive.org/dandiset/000019/0.220126.2148',version='0.220126.2148',license='CC-BY-4.0')),
 'example-mouse-neuropixels':('08_Neuropixels_小鼠LFP','Neuropixels · 小鼠 LFP','Neuropixels · Mouse LFP','两只小鼠 · 每只 60 秒片段','Two mice · 60-second excerpts','NWB','extracellular',dict(name='Allen Visual Coding · DANDI 000021',url='https://dandiarchive.org/dandiset/000021/0.251116.2246',version='0.251116.2246',license='CC-BY-4.0')),
}

def make_manifest(pid,root,source):
    spec=SPECS[pid];modality=spec[6]
    extensions=('.set',) if pid=='example-rest-eeg' else ('.edf',) if pid in {'example-seeg','example-sleep-eeg'} else ('.nwb',)
    signals=sorted(p for p in root.rglob('*') if p.suffix in extensions and 'sleepscoring' not in p.name and not any(x.startswith('.') for x in p.relative_to(root).parts))
    assert len(signals)==2,(pid,signals)
    scope=spec[3]+'；仅核验本目录列出的公开子集，不代表完整原研究。'
    if pid=='example-mouse-neuropixels':scope+='来自上游已预处理的连续 LFP；只裁剪，不再滤波或重采样；不是 AP 或分选后的神经元。'
    m=dict(schema_version='package-expectations/1',source=source,scope=scope,files=[],items=[],recordings=[],consistency=dict(schema_version='dataset-consistency-plan/1',records=[],groups=[],basis='来源版本与所选文件固定。不同植入个体不要求相同电极布局；未提供的独立字段保持未评。'))
    allfiles=[p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and not any(x.startswith('.') for x in p.relative_to(root).parts) and p.name!='来源与范围.json']
    for i,p in enumerate(signals):
        name=p.relative_to(root).as_posix();stem=p.stem
        subject=(next((v for v in p.parent.parts if v.startswith('sub-')),None) or (stem.split('_')[0] if stem.startswith('sub-') else stem))
        related=[n for n in allfiles if (subject in n or (pid=='example-sleep-eeg' and p.stem in n))]
        if name not in related:related.append(name)
        freeze_extra(root,m,related,subject+':selected-recording',subject)
        session=next((part for part in p.parts if part.startswith('ses-')),None)
        if session is None:session=next((part for part in stem.split('_') if part.startswith('ses-')),'selected-recording')
        r=dict(id=stem,path=name,subject=subject,session=session,modality=modality,processing='derived' if pid=='example-mouse-neuropixels' else 'raw',group='source-cohort')
        prefix=stem.rsplit('_',1)[0]
        channel=p.with_name(prefix+'_channels.tsv');event=p.with_name(prefix+'_events.tsv');meta=p.with_suffix('.json')
        if channel.exists():r['channels_tsv']=channel.relative_to(root).as_posix()
        if event.exists():r['events']={'path':event.relative_to(root).as_posix(),'mode':'seconds'}
        if meta.exists():r['metadata_json']=[meta.relative_to(root).as_posix()]
        if (root/'participants.tsv').exists():r['participants_tsv']='participants.tsv'
        scans=root/subject/session/(subject+'_'+session+'_scans.tsv')
        if scans.exists():r['scans_tsv']=scans.relative_to(root).as_posix()
        m['consistency']['records'].append(r);m['recordings'].append({'path':name})
    used={f['path'] for f in m['files']};remaining=[n for n in allfiles if n not in used]
    if remaining:freeze_extra(root,m,remaining,'dataset:source-documentation')
    m['consistency']['groups']=[dict(id='source-cohort',label=spec[1],same_channels=modality=='scalp_eeg',same_rates=pid!='example-speech-ecog',same_units=True,same_reference=False)]
    from ephys_qc.dataset_qc.consistency import validate_consistency
    validate_consistency(m)
    save(root/'.qc/consistency-plan.json',m)
    save(root/'来源与范围.json',dict(source=source,scope=scope,records=[r['path'] for r in m['recordings']]))
    return dict(id=pid,label=spec[1],description=spec[3],root=str(root),expectations=str(root/'.qc/consistency-plan.json'))

def prepare(args):
    original=json.loads(args.config.read_text());settings=copy.deepcopy(original)
    root=args.root/'06_EEG_睡眠多导';root.mkdir(parents=True,exist_ok=True)
    for rid in ['hmc-sn061','hmc-sn062']:
        item=next(i for i in original['inputs'] if i['id']==rid);p=Path(item['source_path']);target=root/p.name
        if not target.exists():shutil.copy2(p,target)
        assert sha(target)==item['expected_sha256']
        ann=item['annotation']
        for key in ['path','source_path']:
            p=Path(ann[key]);t=root/p.name
            if not t.exists():shutil.copy2(p,t)
            assert sha(t)==sha(p)
        save(root/(p.stem.split('_')[0]+'-source.json'),dict(source=item['provenance'],source_sha256=item['expected_sha256'],annotation=ann))
    settings.update(data_dir=str(args.runtime),inputs=[],packages=[],demo_examples=[],demo_comparisons=[],public_records={},public_packages={},temporary_workspace=True)
    for pid in args.package or list(SPECS):
        if pid=='example-ecog':
            settings['packages'].append(next(p for p in original['packages'] if p['id']==pid))
            settings['demo_examples'].append(next(e for e in original['demo_examples'] if e['id']==pid))
            settings['public_packages'][pid]=original['public_packages'][pid]
            continue
        spec=SPECS[pid];r=args.root/spec[0];source=spec[-1]
        settings['packages'].append(make_manifest(pid,r,source));settings['public_packages'][pid]=source
        settings['demo_examples'].append(dict(id=pid,kind='dataset',package_id=pid,label=spec[1],label_en=spec[2],description=spec[3],description_en=spec[4],formats=spec[5],modality=spec[6]))
    save(args.output,settings)

def run(args):
    from server import Store
    from ephys_qc.recommendations import recommend
    from ephys_qc.core import build_plan
    from package_jobs import fingerprint
    settings=json.loads(args.output.read_text());store=Store(settings)
    original=json.loads(args.config.read_text())
    receipts=[]
    for p in settings['packages']:
        m=json.loads(Path(p['expectations']).read_text());mh=fingerprint(m)
        previous=[j for j in store.packages.jobs.values() if j['package_id']==p['id'] and j['manifest_hash']==mh and j['status']=='completed']
        if not previous:store.packages.submit(dict(package_id=p['id'],manifest_hash=mh,confirmed=True))
        for r in m['consistency']['records']:
            if args.record and r['id'] not in args.record:
                continue
            old=[j for j in store.jobs.values() if (j.get('dataset_context') or {}).get('package_id')==p['id'] and (j.get('dataset_context') or {}).get('record_id')==r['id'] and (j.get('dataset_context') or {}).get('manifest_hash')==mh and j['status']=='completed']
            old=[j for j in old if j.get('plan',{}).get('qc_config',{}).get('scope')=='recording' and j['plan']['qc_config'].get('scoring')]
            if old and not args.force:
                print('reuse',p['id'],r['id'],old[-1]['id'],flush=True);continue
            value=store.open_package_record(dict(package_id=p['id'],record_id=r['id'],manifest_hash=mh))
            md=value['metadata'];channels=md['channels'];pid=p['id'];n=len(channels)
            indices=list(range(n));refs={};reference='unknown'
            if pid=='example-sleep-eeg':indices=list(range(4));refs=dict(emg=4,eog=5,ecg=7);reference='mixed'
            if pid=='example-rest-eeg':reference='common_reference'
            # Exclude only source-declared auxiliary/non-voltage channels.
            if pid in {'example-seeg','example-ecog'}:
                import csv
                rows=list(csv.DictReader((Path(p['root'])/r['channels_tsv']).open(),delimiter='\t'))
                seeg={x['name'] for x in rows if x.get('type','').upper()==r['modality'].upper()}
                if pid=='example-seeg':
                    import math
                    electrodes=next((Path(p['root'])/r['path']).parent.glob('*electrodes.tsv'))
                    positions=list(csv.DictReader(electrodes.open(encoding='utf-8-sig'),delimiter='\t'))
                    def localized(row):
                        try:return all(math.isfinite(float(row[k])) for k in ('x','y','z'))
                        except (ValueError,KeyError):return False
                    # These HUP channel tables label even EKG/scalp leads as SEEG.
                    # Select the source-localized implanted contacts, keeping both
                    # good and bad quality labels. Never select by detector score.
                    seeg &= {row['name'] for row in positions if localized(row)}
                indices=[c['index'] for c in channels if c['name'] in seeg]
                assert indices,'No source-declared SEEG channels'
            body=dict(confirmed=True,modality=r['modality'],reference_scheme=reference,eeg_indices=indices,reference_indices=refs,label=r['subject']+' · '+p['label'],source_note=m['scope'])
            if pid=='example-seeg':
                body['source_note']+=' 仅分析来源电极表中有定位坐标的植入触点；保留其 good/bad 标签，不纳入混列的头皮与 EKG 导联。'
            if md['format']=='NWB':body['selected_stream_id']=md['selected_stream_id']
            result=store.confirm_intake(value['id'],body);item=store.inputs[result['input']['id']]
            item.update(provenance=m['source'],modality_source='固定公开版本的来源资料与信号对象确认。')
            if pid=='example-rest-eeg':
                item['reference_evidence']='ds004584 v1.0.0 EEG JSON declares EEGReference=Pz.'
                item['default_config']['method_config']['comparison_groups']=['Pz']*n
            if pid=='example-sleep-eeg':
                prior=next(i for i in original['inputs'] if i['id']==('hmc-sn061' if 'SN061' in r['path'] else 'hmc-sn062'))
                item['annotation']=copy.deepcopy(prior['annotation'])
                for key in ['path','source_path']:item['annotation'][key]=str(Path(p['root'])/Path(item['annotation'][key]).name)
                item['default_config']['method_config']['comparison_groups']=['M1','M1','M1','M2']
            save(store.intakes.root/value['id']/'record.json',item)
            qc=copy.deepcopy(item['default_config']);qc.update(scope='recording',recording_options=dict(window_seconds=120,expensive_methods='run'))
            proposed=recommend(item,qc,reset_methods=True)
            assert proposed['can_apply'],proposed
            qc=proposed['qc_config']
            if pid=='example-rest-eeg':
                from ephys_qc.gnosis_catalog import IDS
                qc['method_config']['extensions']=sorted(set(qc['method_config'].get('extensions',[]))|IDS)
                qc['scoring']=dict(version='project-weighted/1.2',weights={key:20 for key in ['gnosis_line_length','gnosis_artifact','gnosis_low_band','gnosis_high_band','gnosis_psd_deviation']})
            plan=build_plan(item,proposed['selected_modules'],qc)
            assert plan['qc_config']['scope']=='recording' and plan['qc_config'].get('scoring')
            name='灵犀云 · 全记录' if pid=='example-rest-eeg' else '基础方案 · 全记录'
            job=store.submit(dict(input_id=item['id'],selected_modules=plan['selected_modules'],qc_config=plan['qc_config'],plan_id=plan['plan_id'],run_name=name))
            print('submitted',pid,r['id'],job['id'],flush=True)
            last=None
            while store.job(job['id'])['status'] not in {'completed','failed','cancelled'} or job['id'] in store.processes:
                j=store.job(job['id']);status=(j['status'],j.get('phase'),j.get('message'))
                if status!=last:print(pid,r['id'],status,flush=True);last=status
                time.sleep(2)
            j=store.job(job['id']);print('finished',j['id'],j['status'],flush=True)
            if j['status']!='completed':raise RuntimeError(j.get('error',j))
            receipts.append(dict(package_id=pid,record_id=r['id'],job_id=j['id']))
            save(Path(settings['data_dir'])/'build-receipts.json',receipts)
    store.packages.queue.join();store.queue.join()
    print('ALL REQUESTED RUNS COMPLETE',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--config',type=Path,default=REPO/'.local/workbench.json');p.add_argument('--root',type=Path,default=DEFAULT_ROOT);p.add_argument('--runtime',type=Path,default=DEFAULT_ROOT/'.build-20261113');p.add_argument('--output',type=Path,default=REPO/'.local/eight-examples/staged.json');p.add_argument('--package',action='append',choices=[*SPECS,'example-ecog']);p.add_argument('--record',action='append');p.add_argument('--force',action='store_true');a=p.parse_args()
    (prepare if a.action=='prepare' else run)(a)
