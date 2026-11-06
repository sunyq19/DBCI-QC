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
workflow_support=[
 ('M02','processing_scope','处理史与检查范围','首次读入可确认高通、低通和陷波声明；未知保持未知。','已声明滤除的目标频率未评；当前信号结果不能证明清洗前质量。','src/ephys_qc/processing_history.py'),
 ('M09','review_workspace','候选复核与局部PSD','选择候选查看原始时段的波形及Welch PSD，记录接受、驳回或待定。','涵盖基础方法及灵犀云候选；PSD在原生采样上计算，人工决定不覆盖算法证据。','apps/workbench/review_workspace.py'),
 ('OVERVIEW','signal_batch','批量后台信号检查','勾选记录、预览方案、确认后依次运行；批次关联各记录报告，可停止。','仅运行已确认的记录；缺信息逐份说明。服务中断保留历史，需重新预览后启动。','apps/workbench/batch_jobs.py'),
 ('M08','comparison','同条件报告比较','并排查看分项、有效测量量及试行总分；按配置和版本分组。','当前支持EEG；核对模态、通道、参考、处理史、范围、参数及执行版本。未知不声称可比，不做跨组排名。','src/ephys_qc/comparison.py')]
for parent,key,title,description,condition,path in workflow_support:
 catalog.setdefault(parent,[]).append(node('support_'+key,title,['eeg','dataset'],kind='report' if parent in ['M08','M09','OVERVIEW'] else 'intake',entry='support',summary='2026-11-06 接入',description=description,inputs='已确认的记录或已保存的结果',outputs='范围说明、可追溯结果或复核记录',conditions=condition,evidence=base+path+'\n'+base+'docs/design/eeg-workflow-v1.md'))
gnosis_url='https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE'
for parent in ['M04','M05','M06']:
 leaves=[n for n in catalog[parent] if n['id'].startswith('f_gnosis_')]
 catalog[parent]=[n for n in catalog[parent] if n not in leaves]
 catalog[parent].append(node('group_gnosis_'+parent,'灵犀云 · 可选方法',['eeg'],kind='conditional',entry='support',summary='逐项勾选 · 不并入基础评分',description='每个子方法可在质控台单独选择；未选择的同组方法不会执行。必要的副本准备或片段筛选会在详情中列明。',inputs='已确认的头皮EEG及单一比较组',outputs='子方法测量和候选；保留原始输入',conditions='原示例为静息态头皮EEG。先核对参考、单位、可测频带和时长。',methods='原版SignalQualityEval 3.0.0；独立Python 3.12执行环境。',evidence=gnosis_url+'\n'+base+'docs/gnosis-methods.md',notes='网页编辑的是设计说明；实际执行在质控台的可选扩展中勾选。',children=leaves))
catalog['M02'].append(node('support_gnosis_prepare','灵犀云 · 分析副本准备',['eeg'],kind='conditional',entry='support',summary='选择灵犀云子方法时按参数执行',description='为被选方法准备自己的副本：最高256Hz、1–70Hz及平均参考。原始信号和PREP等其他路线的输入保持不变。',inputs='原始V信号；已确认参考比较组',outputs='只供本方法使用的分析副本及处理记录',conditions='子方法prepare_copy=true时内部执行；关闭需已核实输入频带和采样率。ICA不在这一准备步骤中。',methods='SignalQualityEval.tools.utils.preprocess_raw',evidence=gnosis_url,notes='默认不执行Notebook中的自动ICA和线长候选删道；两者改变后续判断，需另外确认。'))
from ephys_qc.visualizations import visualization_specs
catalog['VIS']=[]
for v in visualization_specs():
 catalog['VIS'].append(node(v['id'],v['name'],v['scope'],kind='report',entry='visualization',status='planned' if v['status']=='planned' else 'ready',summary='独立选择图表',description=v['description'],inputs='已保存的检查结果；依赖 '+ '、'.join(v['dependencies']),outputs='统一配色的可选图表；保留单位、时间范围和缺测状态',conditions=v['conditions'],methods=v['implementation'],evidence='\n'.join(v['sources']+[base+'docs/visualizations.md']),notes='选择图表不会启动算法、改写候选或改变评分。来源指指标/展示思路，图形由本平台绘制。'))
visual_root=node('VIS','结果可视化',['eeg'],kind='report',entry='support',summary='统一展示层 · 按需要选图',description='雷佳欣路线与灵犀云路线的图表集中在同一层级。按图的用途选择；来源保留在详情里。',inputs='已保存的单份或分窗质控结果',outputs='波形、频谱、通道指标、候选时间与频带图',conditions='仅渲染已有证据；缺少依赖时提示先运行对应检查。当前图表适配头皮EEG。',methods='DBCI-QC 可视化插件登记与SVG渲染；无需重新计算QC。',evidence=base+'docs/visualizations.md',notes='地形图待坐标接入，雷达图待尺度规则确认。当前不伪造坐标和参考分布。')
visual_root.update(x=1110,y=1020)
review_root=node('D04','审核与复验',['dataset'],kind='dataset',entry='support',summary='影响与用途 · 处理意见 · 修正后对比',description='在资料检查之后登记问题影响和下一步，形成有版本的本地审核记录。修正后对比同一检查的变化。',inputs='D01–D03结果、冻结清单、可选基线审核版本',outputs='处理清单、项目结论、复验变化、HTML/PDF',conditions='资料检查已完成。未评和范围变化不能算问题消除；最终结论须显式确认。',methods='dataset-review/1',evidence=base+'docs/design/dataset-review-v1.md',notes='已用ds003029公开副本验证：采样率异常产生3项关联问题，恢复后3项消除。无医院验收、认证签名或增量重算。')
review_root.update(x=65,y=1020)
catalog['D04']=[]
for key,title,desc,condition in [
 ('decisions','问题处理意见','记录需整改、限定用途、登记跟踪或已说明差异，以及影响、依据、下一步和负责人。','绑定检查结果和文件证据；修改不覆盖程序状态或信号分数。'),
 ('outcome','显式审核结论','有需整改项时确认整改要求；其他情况先处理全部待处理项，再确认项目结论。','人工填写人自行声明，不是经认证电子签名。每次保存追加版本。'),
 ('retest','修正前后复验','固定基线检查及审核版本，比较消除、新增、证据变化、未复查和范围变化。','只有同范围同规则重新检查为一致才算消除。最终结论不继承。'),
 ('report','审核报告与导出','总览、记录、审核与复验分层查看；导出HTML和PDF，保留全部事项及追溯。','公开演示标注模拟意见。原始路径和填写信息尚未自动脱敏。')]:
 catalog['D04'].append(node('support_dataset_'+key,title,['dataset'],kind='dataset',entry='support',summary='D04 首版',description=desc,inputs='完成的资料检查与已登记处理记录',outputs='可追溯的处理和复验结果',conditions=condition,methods='dataset-review/1',evidence=base+'src/ephys_qc/dataset_qc/review.py'+'\n'+base+'docs/design/dataset-review-v1.md'))
files=['src/ephys_qc/visualizations/catalog.py','src/ephys_qc/visualizations/render.py','src/ephys_qc/method_registry.py','src/ephys_qc/readers/__init__.py','src/ephys_qc/research_runtime.py','src/ephys_qc/descriptive_catalog.py','src/ephys_qc/gnosis_catalog.py','src/ephys_qc/gnosis_runtime.py','src/ephys_qc/gnosis_worker.py','docs/dataset-checks.md','src/ephys_qc/processing_history.py','src/ephys_qc/comparison.py','apps/workbench/batch_jobs.py','apps/workbench/review_workspace.py','src/ephys_qc/dataset_qc/review.py','src/ephys_qc/dataset_qc/review_report.py','apps/workbench/package_reviews.py']
out={'catalogVersion':'2026-11-06.5','roots':[visual_root,review_root],'sourceFiles':{f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files},'modules':catalog}
Path('content/module-catalog.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print('Methods:',len(collected),'implemented:',sum(n['status']!='planned' for n in collected.values()),'readers:',len(reader_parent['children']),'dataset checks:',sum(len(catalog[k]) for k in ['D01','D02','D03']))
