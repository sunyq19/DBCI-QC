"""Prepare the November public demo expansion from pinned upstream releases.

Raw files and receipts stay outside Git. Existing identical files are reused;
upstream files are never edited. Dataset manifests define the selected subset.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import requests

REPO = Path(__file__).resolve().parents[2]
DEFAULT_ROOT = REPO / '.local' / 'public-examples'
METADATA_COMMITS = {
    'ds004584': '261510fd9780d738a77fee52b906b3d56b69b74e',
    'ds004100': 'da07f99bcd7a801f86191eceb2d35b0520c55d1a',
}

def save(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def sha(p, alg='sha256'):
    with p.open('rb') as f: return hashlib.file_digest(f, alg).hexdigest()

def fetch(url, dest, size, digest, algorithm='sha256'):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        assert dest.stat().st_size == size and sha(dest, algorithm) == digest, dest
        return
    part = dest.with_name(dest.name+'.part')
    for attempt in range(3):
        try:
            with requests.get(url, stream=True, timeout=(30, 120)) as r:
                r.raise_for_status()
                with part.open('wb') as f:
                    received = 0
                    for b in r.iter_content(1024*1024):
                        received += len(b)
                        if received > size: raise ValueError('Download exceeds frozen size')
                        f.write(b)
            assert part.stat().st_size == size and sha(part, algorithm) == digest, dest
            part.replace(dest)
            print('verified',dest.name,size,flush=True)
            return
        except (requests.RequestException, AssertionError):
            if attempt == 2: raise

def openneuro(ds, subjects, root, metadata, predicate=None):
    repo = metadata/ds
    if not repo.exists():
        metadata.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--filter=blob:none', '--no-checkout',
                        f'https://github.com/OpenNeuroDatasets/{ds}.git', str(repo)], check=True)
        subprocess.run(['git', '-C', str(repo), 'checkout', '--detach', METADATA_COMMITS[ds]], check=True)
    commit = subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != METADATA_COMMITS[ds]:
        raise ValueError(f'{ds}: metadata checkout differs from the pinned public version')
    paths = subprocess.check_output(['git','-C',str(repo),'ls-files'],text=True).splitlines()
    selected = [p for p in paths if (('/' not in p and not p.startswith('.')) or p.split('/')[0] in subjects)]
    if predicate: selected = [p for p in selected if predicate(p)]
    tasks=[]
    for name in selected:
        src,dest=repo/name,root/name
        if src.is_symlink():
            m=re.search(r'(SHA256E?|MD5E?)-s(\d+)--([0-9a-f]+)',os.readlink(src));assert m,name
            tasks.append((f'https://s3.amazonaws.com/openneuro.org/{ds}/{name}',dest,int(m[2]),m[3], 'sha256' if m[1].startswith('SHA') else 'md5'))
        elif src.is_file():
            dest.parent.mkdir(parents=True,exist_ok=True)
            if dest.exists(): assert sha(dest)==sha(src)
            else: shutil.copy2(src,dest)
    with concurrent.futures.ThreadPoolExecutor(3) as pool:
        for f in [pool.submit(fetch,*args) for args in tasks]:f.result()
    return selected

def dandi_file(ds,version,asset,root):
    from prepare_nwb_examples import metadata
    r=requests.get(f'https://api.dandiarchive.org/api/dandisets/{ds}/versions/{version}/assets/{asset}/',timeout=60)
    r.raise_for_status();m=r.json()
    spec=dict(id=Path(m['path']).stem,dandiset=ds,version=version,asset=asset,size=m['contentSize'],sha256=m['digest']['dandi:sha2-256'])
    # metadata and checksum receipts are retained next to the recordings.
    root.mkdir(parents=True,exist_ok=True);(root/'originals').mkdir(exist_ok=True)
    metadata(spec,root)
    target=root/'originals'/Path(m['path']).name
    fetch(f'https://api.dandiarchive.org/api/assets/{asset}/download/',target,spec['size'],spec['sha256'])
    save(root/'provenance'/(spec['id']+'-receipt.json'),dict(spec,source_path=m['path'],complete_original=True))
    return target

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=DEFAULT_ROOT);p.add_argument('--metadata',type=Path,default=REPO/'.local/eight-examples');p.add_argument('--part',choices=['openneuro','ecog'],required=True);a=p.parse_args()
    if a.part=='openneuro':
        openneuro('ds004584',['sub-001','sub-002'],a.root/'05_EEG_睁眼静息',a.metadata)
        # Two participants, one published seizure record each; not the full study.
        def selected(n):
            return not n.endswith(('.edf','.tsv','.json')) or '/' not in n or '_task-' not in n or '_task-ictal_acq-seeg_run-01_' in n
        openneuro('ds004100',['sub-HUP060','sub-HUP112'],a.root/'03_sEEG_HUP同来源队列',a.metadata,selected)
    else:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures=[pool.submit(dandi_file,'000019','0.220126.2148',asset,a.root/'07_ECoG_语音任务') for asset in ['4e4287f2-b557-4f30-a2d6-932f18c3e915','b4c0421e-6eff-4594-a963-83ba39029145']]
            for f in futures: print('complete',f.result(),flush=True)

if __name__=='__main__':main()
