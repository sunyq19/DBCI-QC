import csv,hashlib,json,re,sys
from pathlib import Path
from dataset_paths import paths
args=paths()
ROOT=args.repo_root
WORK=args.evidence_dir
BASE=args.data_root
inspections=json.loads((WORK/'technical_inspection.json').read_text())
downloads=json.loads((WORK/'download_manifest.json').read_text())
def dump(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tsv(p,columns,rows):
 with p.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,delimiter='\t',fieldnames=columns);w.writeheader();w.writerows(rows)
# Validate every official downloadable file that occurs in the provider's checksum list.
verified=[]
for directory in ['eegmmidb-1.0.0-expansion','sleep-edfx-1.0.0-sc4001','chbmit-1.0.0-chb01']:
 d=BASE/directory;checks={line.split(maxsplit=1)[1].lstrip('*'):line.split()[0] for line in (d/'_provenance/official_SHA256SUMS.txt').read_text().splitlines() if line.strip()}
 for item in downloads:
  p=Path(item['path'])
  if d not in p.parents:continue
  remote=item['url'].split('/1.0.0/')[-1] if '/files/' in item['url'] else None
  if remote in checks:
   actual=sha(p);assert checks[remote]==actual,(p,actual)
   verified.append({'path':str(p),'official_relative_path':remote,'sha256':actual,'official_match':True})
# Existing bundle record is reused in place and separately checked against the fresh official manifest.
if args.existing_r02:verified.append({'path':inspections[0]['path'],'official_relative_path':'S001/S001R02.edf','sha256':inspections[0]['expected_sha256'],'official_match':True,'operation':'reused_original_bundle'})
# Sleep annotations: preserve R&K stages, original EDF+ timing, and all original rows.
sleep_dir=BASE/'sleep-edfx-1.0.0-sc4001';sleep_source=sleep_dir/'SC4001EC-Hypnogram.edf';sleep_tsv=sleep_dir/'SC4001_state_intervals.derived.tsv'
raw=json.loads((WORK/'SC4001EC-Hypnogram.annotations.json').read_text());duration=inspections[2]['metadata']['duration_seconds']
mapping={'Sleep stage W':'W','Sleep stage R':'REM','Sleep stage 1':'R&K 1','Sleep stage 2':'R&K 2','Sleep stage 3':'R&K 3','Sleep stage 4':'R&K 4','Movement time':'Movement','Sleep stage ?':'Unknown'}
stages=[];excluded=[]
for num,x in enumerate(raw,1):
 left=max(0,x['onset_s']);right=min(duration,x['onset_s']+x['duration_s'])
 if right<=left:excluded.append({'source_annotation':num,**x,'reason':'outside_recorded_waveform'});continue
 stages.append({'onset_s':left,'duration_s':right-left,'end_s':right,'stage':mapping.get(x['label'],x['label']),'label_type':'sleep_state_RK1968','source_label':x['label'],'source_annotation':num})
tsv(sleep_tsv,['onset_s','duration_s','end_s','stage','label_type','source_label','source_annotation'],stages)
dump(sleep_dir/'SC4001_annotations.original_extracted.json',raw)
dump(sleep_dir/'SC4001_annotation_derivation.json',{'source_path':str(sleep_source),'source_sha256':sha(sleep_source),'derived_path':str(sleep_tsv),'derived_sha256':sha(sleep_tsv),'method':'MNE read_annotations; intersect intervals with actual PSG duration; preserve original R&K stage 3 and 4 separately','waveform_duration_seconds':duration,'raw_rows':len(raw),'derived_rows':len(stages),'excluded_rows':excluded,'clock_check':'PSG and Hypnogram EDF start-date/start-time byte fields agree; no absolute dates copied','quality_ground_truth':False,'used_for_signal_detection':False})
# Task code meanings come from the official archived run protocol, not from waveform inference.
eeg_dir=BASE/'eegmmidb-1.0.0-expansion';task_source=eeg_dir/'S001R03.edf';task_tsv=eeg_dir/'S001R03_task_events.derived.tsv'
rawtask=json.loads((WORK/'S001R03.annotations.json').read_text());taskmap={'T0':'rest','T1':'left_fist_motor_execution','T2':'right_fist_motor_execution'}
taskrows=[{'onset':x['onset_s'],'duration':x['duration_s'],'event_name':taskmap[x['label']],'event_value':x['label']} for x in rawtask]
tsv(task_tsv,['onset','duration','event_name','event_value'],taskrows)
dump(eeg_dir/'S001R03_annotation_derivation.json',{'source_path':str(task_source),'source_sha256':sha(task_source),'derived_path':str(task_tsv),'derived_sha256':sha(task_tsv),'mapping':taskmap,'mapping_source':'https://archive.physionet.org/physiobank/database/eegmmidb/','source_rows':len(rawtask),'method':'MNE read_annotations from original EDF+; preserve onset and duration, decode labels for run 03 only','format_limit':'bids_events_tsv is the existing table adapter name, not a claim that this dataset is BIDS-compliant','quality_ground_truth':False,'used_for_signal_detection':False})
# Clinical seizure events remain separate from artifact truth and task events.
chb_dir=BASE/'chbmit-1.0.0-chb01';summary=chb_dir/'chb01-summary.txt';clinical_tsv=chb_dir/'chb01_03_clinical_events.derived.tsv'
section=summary.read_text().split('File Name: chb01_03.edf\n',1)[1].split('\nFile Name:',1)[0]
start=int(re.search(r'Seizure Start Time: (\d+) seconds',section)[1]);stop=int(re.search(r'Seizure End Time: (\d+) seconds',section)[1]);assert (start,stop)==(2996,3036)
tsv(clinical_tsv,['onset_s','duration_s','label','label_type'],[{'onset_s':start,'duration_s':stop-start,'label':'seizure','label_type':'seizure'}])
dump(chb_dir/'chb01_03_annotation_derivation.json',{'source_path':str(summary),'source_sha256':sha(summary),'source_file_section':'chb01_03.edf','derived_path':str(clinical_tsv),'derived_sha256':sha(clinical_tsv),'events':[{'onset_s':start,'end_s':stop,'duration_s':stop-start,'label_type':'seizure'}],'method':'parse only the matching EDF file section; seconds are relative to that EDF start','quality_ground_truth':False,'used_for_signal_detection':False,'unlabelled_interval_meaning':'outside the annotated seizure; does not establish absence of artifacts, interictal activity, or other clinical features'})
profiles=[{'id':'multichannel_motor_execution','name':'多通道真实运动 EEG','description':'官方任务事件；真实左右握拳。参考未知时不启用同参考跨道阈值。'},{'id':'sparse_bipolar_sleep','name':'双极少导联睡眠 EEG','description':'两道100 Hz EEG和同钟EOG；1 Hz肌电包络不混入分析。'},{'id':'bipolar_clinical_eeg','name':'双极临床 EEG','description':'双极构型、临床发作事件与质量标签分开。'}]
inputs=[]
base_notes={'quality_labels':'not_available','coordinates':'not_provided_or_inferred','raw_modified':False,'automated_cleaning':False}
def record(i,id_,label,dataset,profile,desc,indices,refs,start,length,context,reference,provenance,usage):
 info=inspections[i]
 row={'id':id_,'label':label,'dataset_id':dataset,'profile_id':profile,'description':desc,'source_path':info['path'],'expected_sha256':info['expected_sha256'],'metadata':info['metadata'],'reference_scheme':reference,'verified_electrode_coordinates':False,'verified_epochs':False,'preprocessing':{'verified':False},'default_config':{'selection':{'eeg_indices':indices,'reference_indices':refs,'start_seconds':start,'duration_seconds':length},'method_config':{'comparison_groups':None},'context_tags':context},'provenance':provenance,'data_usage':usage,'scientific_limits':dict(base_notes)}
 row.update(modality='scalp_eeg',modality_source='公开数据集资料确认头皮EEG；非由扩展名推断。')
 inputs.append(row);return row
pe={'name':'PhysioNet EEG Motor Movement/Imagery Dataset','url':'https://physionet.org/content/eegmmidb/1.0.0/','version':'1.0.0','license':'Open Data Commons Attribution License v1.0 (ODC-By-1.0)'}
r02_origin='复用指定的已有EDF' if args.existing_r02 else '来自本次数据目录的官方EDF'
r=record(0,'eegmmidb-s001r02','EEGMMIDB · S001 闭眼静息','eegmmidb-1.0.0','adult_multichannel_rest',f'64道160 Hz，闭眼基线；{r02_origin}，未推测年龄、疾病或具体参考电极。',list(range(64)),{},0,61,{'disease':'unknown','age_group':'unknown','task':'rest'},'unknown',dict(pe),{'typical_use':'闭眼静息与已有睁眼基线的状态对照；方法适用性检查。','annotations':'运行02闭眼条件由官方实验协议给出。','annotation_limits':'实验条件不是质量真值；未提供人工坏道/伪迹区间。'})
r['reference_evidence']='已核对的官方数据页及EDF头未明确具体采集参考；comparison_groups=null。'
r['context_evidence']={'task':'官方旧站 Experimental Protocol，第2次运行为闭眼基线；未据此推测年龄或疾病。','url':'https://archive.physionet.org/physiobank/database/eegmmidb/'}
r['preprocessing']['note']='EDF prefilter=HP:0Hz LP:0Hz N:0Hz；不将占位0解释成有效无限通带或已知处理史。'
r=record(1,'eegmmidb-s001r03','EEGMMIDB · S001 真实左右握拳','eegmmidb-1.0.0','multichannel_motor_execution','64道160 Hz，运行03为实际左右手握拳，非运动想象。原文件125秒，默认只读前120秒。',list(range(64)),{},0,120,{'disease':'unknown','age_group':'unknown','task':'motor'},'unknown',dict(pe),{'typical_use':'真实运动任务及任务时序的质量描述；与静息场景对照。','annotations':'EDF+含30个T0/T1/T2区间，按运行03解码为休息/左握拳/右握拳。','annotation_limits':'任务时段不等于运动伪迹；事件表适配不代表BIDS合规或质量真值。'})
r['annotation']={'format':'bids_events_tsv','path':str(task_tsv),'source_path':str(task_source),'label_scope':'task_events_not_quality'}
r['reference_evidence']='官方数据页未明确具体采集参考；comparison_groups=null。'
r['context_evidence']={'task':'官方旧站运行列表第3项为实际左右手握拳；T1/T2按此运行解释。','url':'https://archive.physionet.org/physiobank/database/eegmmidb/'}
r['preprocessing']['note']='EDF prefilter=HP:0Hz LP:0Hz N:0Hz；不能据此确认高频保留。'
r=record(2,'sleep-edfx-sc4001','Sleep-EDF · SC4001 双极睡眠转变','sleep-edfx-1.0.0','sparse_bipolar_sleep','2道双极EEG和同钟EOG均100 Hz；其余辅助信号1 Hz，不重采样、不混为原始EMG。默认30600–30720秒覆盖W到R&K 1。',[0,1],{'eog':2},30600,120,{'disease':'healthy_control','age_group':'adult','task':'sleep'},'bipolar',{'name':'PhysioNet Sleep-EDF Database Expanded','url':'https://physionet.org/content/sleep-edfx/1.0.0/','version':'1.0.0','license':'Open Data Commons Attribution License v1.0 (ODC-By-1.0)'},{'typical_use':'少导联、双极睡眠记录与原生多采样率输入的适用性检查。','annotations':'人工R&K 1968分期；默认窗口W 30秒、stage 1 90秒。','annotation_limits':'睡眠阶段及Movement标签不等于逐通道伪迹真值；R&K 3/4不自动合并为AASM N3。'})
r['annotation']={'format':'sleep_stages_tsv','path':str(sleep_tsv),'source_path':str(sleep_source),'label_scope':'sleep_state_not_quality'}
r['reference_evidence']='官方数据说明及EDF逐道标签明确Fpz-Cz、Pz-Oz，属于不同双极导联；不声明同参考比较组。'
r['context_evidence']={'disease':'官方SC睡眠年龄研究纳入健康参与者；此处为研究招募背景，非平台作出的诊断。','age_group':'公开EDF人口学字段年龄33岁，仅保存adult分组。','task':'官方SC睡眠记录及配套人工分期。','url':'https://physionet.org/content/sleep-edfx/1.0.0/'}
r['preprocessing']['note']='EEG头记录HP:0.5Hz LP:100Hz [enhanced cassette BW]；这是采集端声明，100 Hz采样实际Nyquist=50 Hz，不等于可用100 Hz频带。EMG头明确整流低通，是1 Hz包络。'
r['selection_evidence']={'selected_eeg':[{'source_index':0,'name':'EEG Fpz-Cz'},{'source_index':1,'name':'EEG Pz-Oz'}],'auxiliary_eog':{'source_index':2,'name':'EOG horizontal','sampling_rate_hz':100},'not_selected':{'source_indices':[3,4,5,6],'reason':'原生1 Hz；呼吸/整流EMG包络/温度/事件标记，不作为100 Hz电压EEG辅助输入。'}}
r=record(3,'chbmit-chb01-03','CHB-MIT · chb01_03 发作区间','chbmit-1.0.0','bipolar_clinical_eeg','23条双极EEG，256 Hz。默认2990–3090秒包含官方2996–3036秒发作；临床事件只作报告背景。',list(range(23)),{},2990,100,{'disease':'epilepsy','age_group':'child','task':'unknown'},'bipolar',{'name':'PhysioNet CHB-MIT Scalp EEG Database','url':'https://physionet.org/content/chbmit/1.0.0/','version':'1.0.0','license':'Open Data Commons Attribution License v1.0 (ODC-By-1.0)'},{'typical_use':'临床发作背景下的质量描述与生理活动/伪迹边界核查。','annotations':'官方summary给出2996–3036秒的一次发作；clinical_events_tsv独立派生。','annotation_limits':'发作不是伪迹；0–100秒没有该发作标注也不能当无伪迹真值。疾病标签不改变检测阈值。'})
r['annotation']={'format':'clinical_events_tsv','path':str(clinical_tsv),'source_path':str(summary),'label_scope':'clinical_events_not_quality'}
r['reference_evidence']='官方chb01-summary.txt及EDF标签列出双极链，不存在统一公共参考；comparison_groups=null。'
r['context_evidence']={'disease':'官方数据集为难治性癫痫/发作监测记录。','age_group':'官方SUBJECT-INFO中chb01年龄11岁，仅登记child。','task':'未将临床监测臆测为静息、睡眠或实验任务。','url':'https://physionet.org/content/chbmit/1.0.0/','age_source_url':'https://physionet.org/files/chbmit/1.0.0/SUBJECT-INFO'}
r['preprocessing']['note']='EDF prefilter字段为空；具体滤波处理史未知。'
r['selection_evidence']={'source_indices':list(range(23)),'rule':'保持全部23个源导联的索引身份，无自动去重、合并或重参考。','duplicate_labels':[{'name':'T8-P8','source_indices':[14,22],'note':'标签重复不证明信号完全相同；两条身份保留，不做公共参考跨道阈值。'}],'reverse_pair':[{'labels':['T7-P7','P7-T7'],'source_indices':[2,18],'note':'反向双极构型，不能当作独立公共参考电极。'}]}
for item in inputs:
 if item.get('annotation'):
  item['annotation']['expected_sha256']=sha(item['annotation']['path'])
  item['annotation']['source_expected_sha256']=sha(item['annotation']['source_path'])
dump(WORK/'registration_additions.json',{'inputs':inputs,'profiles':profiles})
dump(WORK/'official_hash_verification.json',verified)
# Per-dataset download manifest includes local derivations and provenance but no copies of original reused EDF.
for directory in ['eegmmidb-1.0.0-expansion','sleep-edfx-1.0.0-sc4001','chbmit-1.0.0-chb01']:
 d=BASE/directory;rows=[x for x in downloads if d in Path(x['path']).parents]
 if directory.startswith('eegmmidb') and args.existing_r02:rows.append({'path':inspections[0]['path'],'url':'https://physionet.org/files/eegmmidb/1.0.0/S001/S001R02.edf','sha256':inspections[0]['expected_sha256'],'bytes':inspections[0]['metadata']['size_bytes'],'operation':'reused_original_bundle','official_hash_verified':True})
 for p in sorted(d.glob('*.derived.tsv')):rows.append({'path':str(p),'role':'derived_annotations_not_quality','bytes':p.stat().st_size,'sha256':sha(p)})
 dump(d/'_provenance/download_manifest.json',rows)
 local=[{'path':str(p.relative_to(d)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(d.rglob('*')) if p.is_file() and p.name not in {'local_manifest.json','SHA256SUMS.local.txt'}]
 dump(d/'_provenance/local_manifest.json',local)
 (d/'_provenance/SHA256SUMS.local.txt').write_text(''.join(f"{x['sha256']}  {x['path']}\n" for x in local))
stats={'new_registered_records':4,'reused_waveform_records':int(bool(args.existing_r02)),'new_waveform_records':3 if args.existing_r02 else 4,'new_annotation_edf':1,'downloaded_original_and_documentation_files':len(downloads),'downloaded_bytes':sum(x['bytes'] for x in downloads),'official_checks_passed':len(verified),'derived_annotation_tables':3,'default_windows':{r['id']:r['default_config']['selection'] for r in inputs},'no_runtime_jobs_created':True,'original_files_modified':False,'registration_path':str(WORK/'registration_additions.json')}
dump(WORK/'collection_summary.json',stats)
print(json.dumps({k:v for k,v in stats.items() if k!='default_windows'},ensure_ascii=False,indent=2))
