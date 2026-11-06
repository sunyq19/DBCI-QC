"""Prepare the two-record ds002034 pilot for the dataset-to-signal demo.

Requires the downloaded, pinned v1.0.3 pilot and its provenance manifest.
Copies source bytes without repairs; source metadata discrepancies remain visible.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.dataset_qc.consistency import validate_consistency


def prepare(source, destination):
    source, destination = Path(source), Path(destination)
    if destination.exists():
        raise FileExistsError('Use a new directory; existing sources are never overwritten.')
    provenance = json.loads((source / '_provenance/manifest.json').read_text())
    if (provenance['dataset'], provenance['snapshot']) != ('ds002034', '1.0.3'):
        raise ValueError('Expected the pinned ds002034 1.0.3 pilot.')
    files = []
    for row in provenance['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts or (source / relative).is_symlink():
            raise ValueError('Unsafe source path')
        path = source / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Source does not match the original download manifest: ' + row['path'])
        files.append({'path': row['path'], 'size_bytes': row['actual_bytes'],
                      'digest': {'algorithm': 'sha256', 'value': row['sha256']}})
    records = []
    for subject in ('sub-01', 'sub-02'):
        prefix = f'{subject}/ses-01/eeg/{subject}_ses-01_task-offline_run-01'
        records.append({'id': subject + '-offline-run01', 'path': prefix + '_eeg.edf',
                        'subject': subject, 'session': 'ses-01', 'modality': 'scalp_eeg',
                        'processing': 'raw', 'group': 'offline',
                        'channels_tsv': prefix + '_channels.tsv', 'participants_tsv': 'participants.tsv',
                        'scans_tsv': f'{subject}/ses-01/{subject}_ses-01_scans.tsv',
                        'metadata_json': [prefix + '_eeg.json'],
                        'events': {'path': prefix + '_events.tsv', 'mode': 'seconds'}})
    plan = {'schema_version': 'package-expectations/1',
            'source': {k: provenance[k] for k in ('dataset', 'snapshot', 'snapshot_commit', 'dataset_url', 'license')},
            'scope': 'OpenNeuro ds002034 v1.0.3：sub-01、sub-02 的 ses-01 / offline / run-01 两份完整记录。'
                     '仅检查这两份记录及已下载配套文件，不代表原研究的全部个体或全部运行。',
            'files': files, 'recordings': [{'path': r['path']} for r in records],
            'items': [{'id': 'selected-pilot', 'requirement': 'required', 'files': [f['path'] for f in files]}],
            'consistency': {'schema_version': 'dataset-consistency-plan/1', 'records': records,
                            'groups': [{'id': 'offline', 'label': '同任务 EEG · offline / run-01',
                                        'same_channels': True, 'same_rates': True,
                                        'same_units': True, 'same_reference': True}],
                            'basis': '同一公开研究、同一会话编号与任务；来源表保持原样。原表 REF 重名等问题不得静默修复。'}}
    validate_consistency(plan)
    shutil.copytree(source, destination)
    for row in files:
        if hashlib.sha256((destination / row['path']).read_bytes()).hexdigest() != row['digest']['value']:
            raise ValueError('Copied bytes differ from the pinned source')
    (destination / '.qc').mkdir(exist_ok=True)
    (destination / '.qc/consistency-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n')
    (destination / '演示说明.txt').write_text(
        '完整流程演示：2 个体、2 份原始 EDF，分别为 733 秒和 753 秒。\n'
        '来源：' + provenance['dataset_url'] + '\n'
        '从原下载清单校验后复制，18 个源文件逐字节保留；下载记录位于 _provenance。\n'
        '原始 channels.tsv 包含两个同名 REF，文件使用 REF1/REF2，且另有 Status 通道。\n'
        '这是需要核对的来源表信息，不等于所有信号不可读。信号检查明确选择 62 条 EEG，排除 REF1/REF2/Status。\n'
        '每人仅选择一份记录，不能展示同一个体多次采集的比较；同组比较受原始通道表完整性限制。\n'
        '报告保留全部发现与未评项，不把这些记录当作“无异常真值”。\n', encoding='utf-8')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    plan = prepare(args.source, args.destination)
    print(json.dumps({'directory': str(args.destination), 'files': len(plan['files']),
                      'recordings': len(plan['recordings'])}, ensure_ascii=False))
