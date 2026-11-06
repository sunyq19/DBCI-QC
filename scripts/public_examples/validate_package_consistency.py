"""Replay real public data plus labelled missing/conflicting/corrected copies.

Requires the two pinned packages from download_package_pilot.py. Sources remain
unchanged. Outputs are local and must use fresh directories.
"""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))
sys.path.insert(0, str(Path(__file__).parent))
from ephys_qc.dataset_qc import run_dataset_qc
from prepare_package_consistency import prepare


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def statuses(result, code):
    return [r['status'] for r in result['checks'] if r['code'] == code]


def run(public_root, cases_root, reports_root):
    public_root, cases_root, reports_root = map(Path, (public_root, cases_root, reports_root))
    if cases_root.exists() or reports_root.exists(): raise FileExistsError('Use fresh case and report directories')
    cases_root.mkdir(parents=True); reports_root.mkdir(parents=True)
    results = {}; sources = {}; original_hashes = {}
    for folder in ('ds003555-v1.0.1-package-pilot', 'ds003029-v1.0.7-package-pilot'):
        root = public_root / folder; plan = prepare(root)
        sources[folder] = (root, plan)
        original_hashes[folder] = {f['path']: hashlib.sha256((root / f['path']).read_bytes()).hexdigest() for f in plan['files']}
        results[folder] = run_dataset_qc(root, plan, reports_root / folder)
        print(folder, results[folder]['summary'], flush=True)
    root, original = sources['ds003029-v1.0.7-package-pilot']
    chosen = next(r for r in original['consistency']['records'] if r['subject'] == 'sub-ummc003')
    table = chosen['channels_tsv']
    descriptions = {
        '01-缺件': '人工测试副本：删除一个 channels.tsv；不是上游原始数据。',
        '02-采样率冲突': '人工测试副本：将一份 ECoG 的通道表采样率全部改为 500 Hz，文件头不变；不是上游原始数据。',
        '03-修正后复验': '人工测试副本：从采样率冲突副本恢复原通道表后复验。上游原有单位及 sEEG 结构问题保留。'}
    for key, description in descriptions.items():
        destination = cases_root / key
        shutil.copytree(cases_root / '02-采样率冲突' if key.startswith('03') else root, destination,
                        ignore=shutil.ignore_patterns('.git'))
        plan = copy.deepcopy(original); plan['scope'] = description + ' ' + original['scope']
        plan['controlled_case'] = {'description': description, 'affected_file': table,
                                   'upstream_table_sha256': original_hashes['ds003029-v1.0.7-package-pilot'][table]}
        target = destination / table
        if key.startswith('01'):
            target.unlink()  # Keep the original expected manifest: a deliberate missing file.
        elif key.startswith('02'):
            with target.open(newline='', encoding='utf-8') as handle:
                reader = csv.DictReader(handle, delimiter='\t'); fields = reader.fieldnames; rows = list(reader)
            if 'sampling_frequency' not in fields: raise ValueError('Expected a sampling_frequency column')
            for row in rows: row['sampling_frequency'] = '500'
            with target.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.DictWriter(handle, fieldnames=fields, delimiter='\t', lineterminator='\n'); writer.writeheader(); writer.writerows(rows)
            expected = next(f for f in plan['files'] if f['path'] == table)
            expected.update(size_bytes=target.stat().st_size, digest={'algorithm': 'sha256', 'value': hashlib.sha256(target.read_bytes()).hexdigest()})
        else:
            shutil.copy2(root / table, target)
        save(destination / '.qc/consistency-plan.json', plan)
        (destination / 'README_CASE.md').write_text('# 人工异常与复验演示\n\n' + description + '\n\n涉及文件：`' + table + '`\n\n原始公开数据与下载清单均保留。检查清单仅为本副本冻结；不冒充上游文件指纹。\n', encoding='utf-8')
        result = results[key] = run_dataset_qc(destination, plan, reports_root / key)
        print(key, result['summary'], flush=True)
    baseline = results['ds003029-v1.0.7-package-pilot']
    assert statuses(baseline, 'individual_rates') == ['pass', 'pass']
    assert 'conflict' not in statuses(baseline, 'cohort_rates')
    assert results['01-缺件']['summary']['present_files'] == baseline['summary']['present_files'] - 1
    assert 'conflict' in statuses(results['02-采样率冲突'], 'individual_rates')
    assert 'conflict' in statuses(results['02-采样率冲突'], 'cohort_rates')
    # Restoration must remove injected findings, not hide upstream issues.
    for code in {r['code'] for r in baseline['checks']}:
        assert statuses(results['03-修正后复验'], code) == statuses(baseline, code), code
    for folder, (source, plan) in sources.items():
        for path, digest in original_hashes[folder].items():
            assert hashlib.sha256((source / path).read_bytes()).hexdigest() == digest, path
    save(reports_root / 'acceptance.json', {'accepted': True, 'source_files_unchanged': True,
         'cases': {k: v['summary'] for k, v in results.items()},
         'assertions': ['missing file detected', 'within-subject rate conflict detected', 'cohort rate conflict detected',
                        'restored copy matches all baseline check statuses', 'all 100 original source files unchanged']})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-root', required=True); parser.add_argument('--cases-root', required=True); parser.add_argument('--reports-root', required=True)
    args = parser.parse_args(); run(args.public_root, args.cases_root, args.reports_root)
