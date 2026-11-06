"""Snapshot registered implementation metadata; never read subject data.
Usage: python3 scripts/import-qc-catalog.py /path/to/ephys-qc
"""
import sys, json, hashlib
from pathlib import Path
repo=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(repo/'src'))
from ephys_qc.method_registry import methods
from ephys_qc.readers import list_readers
modes={'scalp_eeg':'eeg','ecog':'ecog','seeg':'seeg','extracellular':'np'}
base='https://github.com/sunyq19/DBCI-QC/blob/main/'
def node(id,title,scope,kind='base',status='ready',entry='method',**kw):
 return dict(id=id,title=title,summary=kw.pop('summary',''),kind=kind,status=status,scope=scope,x=20,y=20,description='',inputs='',outputs='',conditions='',methods='',evidence='',notes='',entryType=entry,**{})|kw
catalog={}; collected={}
for mode,scope in modes.items():
 for m in methods(mode):
  key=m['id']
  if key in collected:
   collected[key]['scope'].append(scope); continue
  d=m.get('documentation',{}); source=m.get('source',{})
  n=node('f_'+key,m['name'],[scope],kind='conditional' if m['category']!='basic' else 'base',status='planned' if m['implementation']=='planned' else 'ready',summary={'basic':'随模块运行','conditional':'满足条件时运行','optional':'手动选择'}[m['category']],description=m['description'],inputs='\n'.join(m['inputs']),outputs='\n'.join(m['outputs']),conditions='\n'.join(m['requirements'])+('\n'+d['when_to_use'] if d.get('when_to_use') else ''),methods='\n'.join(x for x in [source.get('name',''),d.get('how_it_works',''),d.get('upstream_call','')] if x),evidence='\n'.join(x for x in [source.get('url',''),base+'src/ephys_qc/method_registry.py'] if x),notes='\n'.join(m.get('limitations',[])))
  collected[key]=n; catalog.setdefault(m['module_id'],[]).append(n)
reader_parent=collected['edf_reader']; reader_parent['children']=[]
for r in list_readers():
 reader_parent['children'].append(node('r_'+r['id'],r['name'],(['np'] if r['id']=='native_spikeglx' else ['eeg','ecog','seeg','np']),kind='intake',entry='reader',summary=' / '.join(r['formats']),description='按文件格式调用独立读取器，保留原生采样时钟。格式本身不确定分析模态。',inputs='、'.join(r['extensions'])+('及配套文件' if r['multifile'] else ''),outputs='通道、原生采样率、时长、单位、可用流与标注信息',conditions='\n'.join(r['limitations']),methods=r['id'],evidence=base+'src/ephys_qc/readers/__init__.py'))
# The public project specification provides the exact implemented dataset checks.
for line in (repo/'docs/dataset-checks.md').read_text().splitlines():
 if not line.startswith('| D'): continue
 p=[s.strip() for s in line.strip('|').split('|')]; parent,title,condition,limitation=p
 n=node('d_'+parent+'_'+str(len(catalog.get(parent,[]))+1),title,['dataset'],kind='dataset',entry='check',summary='资料核对',description=condition,inputs='已确认的数据包、应有清单及对应配套表',outputs='检查状态、受影响记录、测量值及位置',conditions=condition,notes=limitation,methods='dataset-consistency/0.1',evidence=base+'docs/dataset-checks.md')
 catalog.setdefault(parent,[]).append(n)
# Supporting implemented workflow capabilities, separate from algorithm counts.
extras=[
 ('INPUT','admission','接入范围与大小核验','单文件和记录组受限接入；数据集先核验完整目录与方案。','单文件 2 GiB、数据集 10 GiB；记录及配套文件还受组合限额约束。','src/ephys_qc/admission.py'),
 ('M02','whole_record','整份记录后台检查','按原生时钟分段执行并汇总整份文件结果。','以整份检查方案运行；方法对各窗口分别核对适用性。','src/ephys_qc/whole_record.py'),
 ('OVERVIEW','overview','数据集报告汇总','按个体和记录汇总资料问题，关联已有单份信号报告。','不会自动启动数据集里每份文件的信号任务，也不平均不同模态分数。','src/ephys_qc/dataset_qc/overview.py')]
for parent,key,title,desc,condition,path in extras:
 catalog.setdefault(parent,[]).append(node('support_'+key,title,['dataset'] if parent=='OVERVIEW' else list(modes.values())+['dataset'],kind='intake' if parent=='INPUT' else 'report',entry='support',summary='执行与汇总',description=desc,inputs='已确认的记录或数据包',outputs='接入证据或执行结果',conditions=condition,evidence=base+path))
files=['src/ephys_qc/method_registry.py','src/ephys_qc/readers/__init__.py','src/ephys_qc/research_runtime.py','src/ephys_qc/descriptive_catalog.py','docs/dataset-checks.md']
out={'catalogVersion':'2026-11-06.1','sourceFiles':{f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files},'modules':catalog}
Path('content/module-catalog.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Methods:',len(collected),'implemented:',sum(n['status']!='planned' for n in collected.values()),'readers:',len(reader_parent['children']),'dataset checks:',sum(len(catalog[k]) for k in ['D01','D02','D03']))
