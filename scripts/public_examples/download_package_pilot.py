"""Download pinned, subject-complete public subsets for package QC (stdlib + git).

Payloads come from public S3, but must match the selected Git snapshot's annex
size and digest. Never infer snapshot identity from the current bucket key alone.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request

SOURCES = {
    'ds003555': ('1.0.1', 'cbeed2aa8c473016e44d6875a6621cf0bedd82be', ['sub-06', 'sub-19']),
    'ds003029': ('1.0.7', '03569e3d523565b0bd9a87aef6220efda20e94b5', ['sub-ummc003', 'sub-ummc006', 'sub-umf004']),
}


def hashes(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(block); md5.update(block)
    return {'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def download(dataset, base):
    version, commit, subjects = SOURCES[dataset]
    target = base / f'{dataset}-v{version}-package-pilot'
    target.mkdir(parents=True, exist_ok=False)
    provenance = target / '.qc'; provenance.mkdir()
    with tempfile.TemporaryDirectory(prefix='dbci-public-metadata-') as temp:
        repo = Path(temp) / dataset
        subprocess.run(['git', 'clone', '--quiet', '--depth', '1', '--branch', version,
                        f'https://github.com/OpenNeuroDatasets/{dataset}.git', str(repo)], check=True)
        actual = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != commit:
            raise ValueError('Snapshot commit differs from the pinned selection')
        paths = subprocess.check_output(['git', '-C', str(repo), 'ls-files', '-z']).decode().split('\0')
        paths = [p for p in paths if p and not p.startswith(('.git', '.datalad/'))]
        selected = [p for p in paths if '/' not in p or p.split('/')[0] in subjects or
                    (p.startswith('derivatives/') and (p.count('/') == 1 or p.split('/')[1] in subjects))]
        source = {'dataset_id': dataset, 'version': version, 'commit': commit,
                  'url': f'https://openneuro.org/datasets/{dataset}/versions/{version}',
                  'license': json.loads((repo / 'dataset_description.json').read_text())['License']}
        manifest = {'schema_version': 'package-expectations/1', 'source': source,
                    'scope': '公开数据的受试者子集：' + '、'.join(subjects) + '；保留所选受试者全部已发布记录及配套表，不代表全数据集。',
                    'files': [], 'items': [], 'recordings': []}
        # Freeze expectations before fetching any payload, including missing files.
        for name in selected:
            p = repo / name
            if p.is_symlink():
                match = re.search(r'(SHA256E?|MD5E?)-s(\d+)--([0-9a-f]+)', os.readlink(p))
                if not match:
                    raise ValueError(f'Unsupported annex key: {name}')
                algorithm = 'sha256' if match[1].startswith('SHA256') else 'md5'
                spec = {'path': name, 'size_bytes': int(match[2]),
                        'digest': {'algorithm': algorithm, 'value': match[3]}}
            else:
                spec = {'path': name, 'size_bytes': p.stat().st_size,
                        'digest': {'algorithm': 'sha256', 'value': hashes(p)['sha256']}}
            manifest['files'].append(spec)
            if name.endswith(('.edf', '.vhdr')):
                manifest['recordings'].append({'path': name})
        groups = {}
        for name in selected:
            parts = name.split('/')
            subject = next((s for s in parts if s.startswith('sub-')), 'dataset')
            category = 'derived_eeg' if name.startswith('derivatives/sub-') else ('recording_package' if subject != 'dataset' else 'shared_metadata')
            groups.setdefault((subject, category), []).append(name)
        for (subject, category), names in sorted(groups.items()):
            manifest['items'].append({'id': subject + ':' + category, 'subject': subject,
                                      'category': category, 'requirement': 'required', 'files': names})
        (provenance / 'expectations.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        (provenance / 'published-file-list.json').write_text(json.dumps({'source': source, 'paths': paths}, indent=2) + '\n')
        received = []
        for spec in manifest['files']:
            name = spec['path']; src = repo / name; dest = target / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                url = 'https://s3.amazonaws.com/openneuro.org/' + dataset + '/' + urllib.parse.quote(name, safe='/')
                part = dest.with_name(dest.name + '.part')
                print(f'Download {dataset}/{name} ({spec["size_bytes"] / 1e6:.1f} MB)', flush=True)
                with urllib.request.urlopen(url, timeout=90) as response, part.open('xb') as out:
                    shutil.copyfileobj(response, out, 1024 * 1024)
                digests = hashes(part)
                if part.stat().st_size != spec['size_bytes'] or digests[spec['digest']['algorithm']] != spec['digest']['value']:
                    raise ValueError(f'Snapshot content mismatch: {name}; partial file retained')
                part.rename(dest)
            else:
                shutil.copyfile(src, dest); digests = hashes(dest)
            received.append({'path': name, 'size_bytes': dest.stat().st_size, 'sha256': digests['sha256']})
            (provenance / 'download-receipt.json').write_text(json.dumps({'source': source, 'files': received}, indent=2) + '\n')
        (target / 'README_SAMPLE.md').write_text(
            f'# {dataset} 公开数据演示子集\n\n来源：{source["url"]}\n\n'
            f'许可：{source["license"]}。版本提交：`{commit}`。原作者与引用见原始 `README`、`dataset_description.json`。\n\n'
            f'{manifest["scope"]}\n\n'
            '根目录 participants.tsv 保留上游全表，因此行数不是本次下载人数。原目录、原始元数据不改写。\n\n'
            '`.qc/expectations.json` 是下载前冻结的检查清单；`published-file-list.json` 是该版本发布文件索引；'
            '`download-receipt.json` 保存本地 SHA-256。大文件逐一匹配快照中的大小和 MD5/SHA-256。\n\n'
            '这是公开数据，不是华山医院提供的病例数据。文件齐全不代表信号质量合格。\n\n' +
            ('`sub-*` 为原始记录；`derivatives/sub-*` 为 N3 睡眠的双极重参考片段。HFO 标记是病理研究标记，不能作为伪迹真值。\n'
             if dataset == 'ds003555' else
             '包含 ECoG 与 sEEG，按记录的 acq 实体区分。上游未提供精确电极坐标及对应 MRI/CT，不能验证影像配准。\n'), encoding='utf-8')
        print(json.dumps({'dataset': dataset, 'path': str(target), 'files': len(received),
                          'recordings': len(manifest['recordings']), 'bytes': sum(f['size_bytes'] for f in received)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Parent folder; dataset folders must not exist')
    parser.add_argument('--dataset', choices=list(SOURCES), action='append')
    args = parser.parse_args()
    for ds in args.dataset or list(SOURCES):
        download(ds, args.output.resolve())
