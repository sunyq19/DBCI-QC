"""Assemble dataset examples from already downloaded public samples.

This command never downloads data or alters the source samples. It requires the
existing attention-demo and ieeg-package entries. Output manifests describe only
the explicitly selected files, not completeness of the upstream studies.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import zipfile


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2) + '\n'
    if path.exists() and path.read_text() != data:
        raise ValueError(f'Refusing to overwrite different example content: {path}')
    path.write_text(data)


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if digest(source) != digest(target):
            raise ValueError(f'Existing example changed: {target}')
    else:
        shutil.copy2(source, target)


def freeze_extra(root, manifest, paths, identifier, subject='dataset'):
    for name in paths:
        path = root / name
        manifest['files'].append({'path': name, 'size_bytes': path.stat().st_size,
                                  'digest': {'algorithm': 'sha256', 'value': digest(path)}})
    manifest['items'].append({'id': identifier, 'subject': subject, 'category': 'recording_package',
                              'requirement': 'required', 'files': paths})


def subset(config, output, modality):
    source = json.loads(Path(config['expectations']).read_text())
    manifest = copy.deepcopy(source)
    records = [r for r in manifest['consistency']['records'] if r['modality'] == modality]
    subjects = {r['subject'] for r in records}
    manifest['items'] = [i for i in manifest['items'] if i['subject'] in subjects | {'dataset'}]
    paths = {p for i in manifest['items'] for p in i.get('files', [])}
    manifest['files'] = [f for f in manifest['files'] if f['path'] in paths]
    manifest['recordings'] = [r for r in manifest['recordings'] if r['path'] in {x['path'] for x in records}]
    manifest['consistency']['records'] = records
    manifest['consistency']['groups'] = [g for g in manifest['consistency']['groups'] if g['id'] in {r['group'] for r in records}]
    for name in paths:
        copy_file(Path(config['root']) / name, output / name)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--samples-root', type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text())
    packages = {p['id']: p for p in settings['packages']}
    if not {'attention-demo', 'ieeg-package'} <= packages.keys():
        raise ValueError('Prepare the public attention-demo and ieeg-package sources first.')
    base = args.samples_root / '示例数据集'
    new = []

    def register(identifier, label, description, root, manifest):
        write(root / '.qc' / 'consistency-plan.json', manifest)
        write(root / '来源与范围.json', {'scope': manifest['scope'], 'source': manifest.get('source'),
              'records': [r['path'] for r in manifest['recordings']],
              'note': '来源文件保持不变。仅对列出的公开样本核验；缺少的独立元数据不由信号头反向生成。'})
        new.append(dict(id=identifier, label=label, description=description, root=str(root),
                        expectations=str(root / '.qc' / 'consistency-plan.json')))

    root = base / '02_ECoG_临床记录'
    manifest = subset(packages['ieeg-package'], root, 'ecog')
    manifest['scope'] = 'OpenNeuro ds003029 v1.0.7 的两名 ECoG 受试者，各三份发作记录及原配套表；仅评估此公开子集。'
    register('example-ecog', 'ECoG · 临床记录', '两位受试者的六份发作记录。', root, manifest)

    root = base / '03_sEEG_EDF与FIF'
    manifest = dict(schema_version='package-expectations/1', files=[], items=[], recordings=[],
        consistency={'schema_version': 'dataset-consistency-plan/1', 'records': [], 'groups': [],
                     'basis': '独立来源分组；缺少的独立通道表保持未评，不从文件头反向构造。'})
    mne = args.samples_root / 'sEEG' / '01_深部电极_MNE'
    paths = ['mne/MNE_sEEG_sample_ieeg.fif', 'mne/来源.json']
    copy_file(mne / 'MNE_sEEG_sample_ieeg.fif', root / paths[0])
    copy_file(mne / '来源.json', root / paths[1])
    freeze_extra(root, manifest, paths, 'mne:recording_package', 'mne-sample')
    manifest['recordings'].append({'path': paths[0]})
    manifest['consistency']['records'].append(dict(id='mne-seeg', path=paths[0], subject='mne-sample',
        session='sample', modality='seeg', processing='derived', group='mne-seeg'))
    manifest['consistency']['groups'].append(dict(id='mne-seeg', label='MNE sEEG · 公开样本',
        same_channels=False, same_rates=True, same_units=True, same_reference=False))
    manifest['source'] = {'sources': json.loads((mne / '来源.json').read_text())['sources']}
    sample = args.samples_root / 'sEEG' / '04_临床发作_HUP060'
    provenance = json.loads((sample / '来源.json').read_text())
    prefix = Path('hup') / 'sub-HUP060' / 'ses-presurgery' / 'ieeg'
    edf = next(sample.glob('*.edf'))
    copy_file(edf, root / prefix / edf.name)
    paths = [(prefix / edf.name).as_posix()]
    for name, content in provenance['sidecars'].items():
        if Path(name).name != name:
            raise ValueError('Unsafe provenance sidecar name')
        target = root / prefix / name
        if target.exists() and target.read_text() != content:
            raise ValueError('Sidecar changed')
        target.write_text(content)
        paths.append((prefix / name).as_posix())
    copy_file(sample / '来源.json', root / 'hup' / '来源.json')
    paths.append('hup/来源.json')
    freeze_extra(root, manifest, paths, 'HUP060:recording_package', 'sub-HUP060')
    path = (prefix / edf.name).as_posix()
    manifest['recordings'].append({'path': path})
    manifest['consistency']['records'].append(dict(id='hup060-ictal-run01', path=path,
        subject='sub-HUP060', session='ses-presurgery', modality='seeg', processing='raw', group='hup-seeg',
        channels_tsv=path.replace('_ieeg.edf', '_channels.tsv'), metadata_json=[path.replace('.edf', '.json')],
        events={'path': path.replace('_ieeg.edf', '_events.tsv'), 'mode': 'seconds'}))
    manifest['consistency']['groups'].append(dict(id='hup-seeg', label='HUP sEEG · 独立来源',
        same_channels=False, same_rates=True, same_units=True, same_reference=True))
    manifest['source']['sources'].append({k: provenance[k] for k in
                          ('name', 'url', 'version_doi', 'license', 'git_revision')})
    manifest['scope'] = 'MNE 公开 sEEG 片段与 ds004100/HUP060 发作记录各一份；按来源分组，不视作同一实验队列或完整原始数据集。'
    register('example-seeg', 'sEEG · 临床记录', '两份深部电极记录，保留各自来源。', root, manifest)

    root = base / '04_Neuropixels_AP与LF'
    manifest = dict(schema_version='package-expectations/1',
        source={'name': 'Human Neuropixels public crops', 'url': 'https://zenodo.org/records/5899237', 'license': 'CC0-1.0'},
        scope='三名受试者的公开裁剪片段：Pt01 LF 400–420秒、Pt02 AP 300–304秒、Pt03 AP 60–62秒。完整检查仅指各片段全长，不代表完整原记录；AP/LF 分组。',
        files=[], items=[], recordings=[], consistency={'schema_version': 'dataset-consistency-plan/1',
            'records': [], 'groups': [], 'basis': '按来源声明的 AP/LF 分组，允许不同受试者接触点布局不同；不生成缺失的独立通道表。'})
    for folder, subject, band in [('01_人类AP记录_Pt03', 'Pt03', 'ap'), ('02_人类LF记录_Pt01', 'Pt01', 'lf'), ('03_人类AP记录_Pt02', 'Pt02', 'ap')]:
        sample = args.samples_root / 'Neuropixels' / folder
        prefix = Path(subject)
        paths = []
        with zipfile.ZipFile(next(sample.glob('*.zip'))) as archive:
            for info in archive.infolist():
                if Path(info.filename).name != info.filename or Path(info.filename).suffix not in {'.bin', '.meta'}:
                    raise ValueError('Unexpected SpikeGLX archive member')
                target = root / prefix / info.filename
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    with archive.open(info) as source, target.open('wb') as dest:
                        shutil.copyfileobj(source, dest)
                with archive.open(info) as source:
                    if hashlib.file_digest(source, 'sha256').hexdigest() != digest(target):
                        raise ValueError('Extracted data differs from archive')
                paths.append((prefix / info.filename).as_posix())
        copy_file(sample / '来源.json', root / prefix / '来源.json')
        paths.append((prefix / '来源.json').as_posix())
        freeze_extra(root, manifest, paths, subject + ':crop', subject)
        signal = next(p for p in paths if p.endswith('.bin'))
        manifest['recordings'].append({'path': signal})
        manifest['consistency']['records'].append(dict(id=subject + '-' + band, path=signal,
            subject=subject, session='crop', modality='extracellular', processing='derived', group=band))
    for band in ['ap', 'lf']:
        manifest['consistency']['groups'].append(dict(id=band, label=band.upper() + ' 电压片段',
            same_channels=False, same_rates=True, same_units=True, same_reference=False))
    register('example-neuropixels', 'Neuropixels · AP / LF', '三份人类记录片段，按 AP / LF 分组。', root, manifest)

    settings['packages'] = [p for p in settings['packages'] if p['id'] not in {p['id'] for p in new}] + new
    specs = [('attention-demo', '头皮 EEG', 'Scalp EEG', '注意任务 · 两位受试者', 'Attention task · two participants', 'EDF'),
             ('example-ecog', 'ECoG', 'ECoG', '临床发作 · 每人三份记录', 'Clinical seizures · three recordings per participant', 'BrainVision'),
             ('example-seeg', 'sEEG', 'sEEG', '深部电极 · 两个公开来源', 'Depth electrodes · two public sources', 'EDF / FIF'),
             ('example-neuropixels', 'Neuropixels', 'Neuropixels', '人类电压片段 · AP / LF', 'Human voltage excerpts · AP / LF', 'SpikeGLX')]
    settings['demo_examples'] = [dict(id=pid, kind='dataset', package_id=pid, label=label, label_en=en,
        description=desc, description_en=den, formats=fmt) for pid, label, en, desc, den, fmt in specs]
    backup = args.config.with_name(args.config.name + '.before-dataset-examples')
    if not backup.exists(): shutil.copy2(args.config, backup)
    temp = args.config.with_suffix('.tmp')
    temp.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + '\n')
    temp.replace(args.config)
    print(json.dumps({'created': [p['root'] for p in new], 'examples': [s[0] for s in specs]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
