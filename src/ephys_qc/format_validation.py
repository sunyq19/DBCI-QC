"""Official format validators. File compliance is not a signal quality score."""
from pathlib import Path
from importlib.metadata import version
import json
import os
import subprocess
import sys
import tempfile


def nwb_spec():
    return dict(id='nwb_inspector',name='NWB Inspector 文件校验',module_id='M01',category='optional',optional_extension=True,
        documentation=nwb_documentation(),implementation='available',status='available',defaults={},research_modalities=['scalp_eeg','ecog','seeg','extracellular'],
        description='核验 NWB 文件结构及元数据，区分规范错误与最佳实践建议。',
        inputs=['本次登记的本地 NWB 文件'],requirements=['NWB 2 文件；NWB Inspector 运行依赖'],
        outputs=['结构校验错误','元数据建议','校验器和规则版本'],
        source=dict(name='NWB Inspector',url='https://nwb.org/tools/core/nwbinspector/',license='BSD-3-Clause'),
        limitations=['仅校验文件规范，不代表波形良好；不转换质量分。','在受检文件上只读运行，不上传文件。'])


def nwb_documentation():
    return dict(purpose='核查NWB结构和元数据，区分规范错误与最佳实践建议。',
        how_it_works='官方NWB Inspector只读遍历NWB文件，包含PyNWB结构验证，记录问题级别、对象位置和检查名称。',
        interpretation='规范符合性与信号质量分开；建议数量不直接证明数据可用或不可用。',
        when_to_use='本次已登记的NWB 2文件。',when_not_to_use='其他格式、读取失败、外部依赖缺失；校验器超时保留未完成。',
        validation_status='已用公开NWB文件完成工程执行验证，非临床质量认证。',
        upstream_call='nwbinspector.inspect_nwbfile(skip_validate=False)',
        references=[dict(title='NWB Inspector',url='https://nwb.org/tools/core/nwbinspector/',kind='官方文档')],
        implementation_origin='原版NWB Inspector子进程，最长180秒；不上传、不改写受检文件。',
        version_note='固定nwbinspector 0.7.2；每份结果保留校验器版本。')


def evaluate_nwb(facts,params=None):
    from importlib.util import find_spec
    if params:raise ValueError('NWB Inspector has no exposed parameters')
    reason='仅适用于NWB文件。' if str(facts.get('format','')).upper()!='NWB' else '缺少nwbinspector运行依赖。' if find_spec('nwbinspector') is None else ''
    return dict(status='blocked' if reason else 'ready',reason=reason or '可运行NWB结构与最佳实践检查。',parameters={})


def _inspect_nwb(path):
    import nwbinspector
    rows=[]
    for message in nwbinspector.inspect_nwbfile(path, skip_validate=False):
        if message is None:continue
        rows.append({k:(getattr(getattr(message,k,None),'name',None) or str(getattr(message,k,''))) for k in ('importance','severity','message','check_function_name','object_type','object_name','location')})
    return dict(schema_version='file-validation/1',validator='nwb_inspector',status='completed',
        version=version('nwbinspector'),schema_validation_included=True,issues=rows,
        error_count=sum(r['importance'] in {'PYNWB_VALIDATION','CRITICAL','ERROR'} for r in rows),
        can_output_score=False,calculated=True,candidates=[],reason=f'完成文件规范检查，共{len(rows)}条问题/建议。')


def inspect_nwb(path):
    try:
        result=subprocess.run([sys.executable,'-m','ephys_qc.format_validation','--nwb',str(Path(path).resolve())],capture_output=True,text=True,timeout=180)
        if result.returncode:raise ValueError('校验器未完成；请查看校验日志。')
        return json.loads(result.stdout)
    except (OSError,subprocess.TimeoutExpired,ValueError) as error:
        return dict(status='failed',calculated=False,can_output_score=False,reason=str(error),issues=[],candidates=[])


def inspect_bids(root):
    root=Path(root).resolve()
    if not (root/'dataset_description.json').is_file():return dict(status='not_applicable',reason='未声明为BIDS数据集。',issues=[],can_output_score=False)
    try:
        description=json.loads((root/'dataset_description.json').read_text())
        if not isinstance(description,dict):raise ValueError('dataset_description.json 必须是一个对象。')
        if not description.get('BIDSVersion'):return dict(status='not_applicable',reason='未声明BIDS版本。',issues=[],can_output_score=False)
        import bids_validator_deno
        from deno import find_deno_bin
        # Offline bundle embeds its schema; no network, subprocesses, or source writes.
        bundle=Path(bids_validator_deno.__file__).with_name('bids-validator.js')
        for base,dirs,files in os.walk(root):
            if any((Path(base)/name).is_symlink() for name in dirs+files):raise ValueError('BIDS校验不跟随数据集内的符号链接。')
        with tempfile.TemporaryDirectory(prefix='dbci-bids-') as temporary:
            env={k:v for k,v in os.environ.items() if k not in {'BIDS_SCHEMA','DENO_DIR'}}
            env.update(DENO_DIR=temporary,NO_COLOR='1')
            process=subprocess.run([os.fsdecode(find_deno_bin()),'run','--no-prompt',f'--allow-read={root},{bundle}',
                '--allow-env','--deny-net','--deny-run',str(bundle),str(root),'--format','json','--max-rows','-1'],
                capture_output=True,text=True,timeout=180,cwd=temporary,env=env)
        payload=json.loads(process.stdout)
        if not isinstance(payload,dict) or not isinstance(payload.get('issues'),(dict,list)):
            raise ValueError('BIDS校验器未返回有效结果。')
        return dict(schema_version='dataset-format-validation/1',validator='bids_validator',version=version('bids-validator-deno'),
            status='completed',calculated=True,can_output_score=False,declared_bids_version=description['BIDSVersion'],
            issues=payload['issues'],summary=payload.get('summary',{}),exit_code=process.returncode,
            reason='按校验器内置规则完成BIDS结构检查；不评定信号质量。',offline=True)
    except (OSError,ImportError,ValueError,subprocess.TimeoutExpired) as error:
        return dict(status='unassessed',calculated=False,can_output_score=False,reason=str(error),issues=[])


if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1]!='--nwb':raise SystemExit(2)
    # Upstream diagnostics stay off the JSON protocol.
    import contextlib
    with contextlib.redirect_stdout(sys.stderr):value=_inspect_nwb(sys.argv[2])
    print(json.dumps(value,ensure_ascii=False))
