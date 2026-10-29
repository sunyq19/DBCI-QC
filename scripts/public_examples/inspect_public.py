import hashlib,importlib.util,json,re,sys
from pathlib import Path
from dataset_paths import paths
args=paths()
ROOT=args.repo_root
WORK=args.evidence_dir
spec=importlib.util.spec_from_file_location('input_config',ROOT/'apps/workbench/input_config.py');ic=importlib.util.module_from_spec(spec);spec.loader.exec_module(ic)
base=args.data_root
old=args.existing_r02 or base/'eegmmidb-1.0.0-expansion/S001R02.edf'
inputs=[('eegmmidb-1.0.0-expansion',old,'S001/S001R02.edf'),('eegmmidb-1.0.0-expansion',base/'eegmmidb-1.0.0-expansion/S001R03.edf','S001/S001R03.edf'),('sleep-edfx-1.0.0-sc4001',base/'sleep-edfx-1.0.0-sc4001/SC4001E0-PSG.edf','sleep-cassette/SC4001E0-PSG.edf'),('chbmit-1.0.0-chb01',base/'chbmit-1.0.0-chb01/chb01_03.edf','chb01/chb01_03.edf')]
allmeta=[]
for directory,p,remote in inputs:
    manifest=(base/directory/'_provenance/official_SHA256SUMS.txt').read_text()
    checks={row.split(maxsplit=1)[1].lstrip('*'):row.split()[0] for row in manifest.splitlines() if row.strip()}
    digest=hashlib.sha256(p.read_bytes()).hexdigest();assert digest==checks[remote],(p,digest,checks.get(remote))
    metadata=ic.edf_metadata(p)
    with p.open('rb') as f:
        h=f.read(256);n=int(h[252:256]);block=f.read(256*n)
    field=lambda offset,width:[block[offset*n+i*width:offset*n+(i+1)*width].decode('latin1').strip() for i in range(n)]
    details={'path':str(p),'official_relative_path':remote,'expected_sha256':digest,'official_hash_verified':True,'metadata':metadata,'prefilter':field(136,80),'transducer':field(16,80)}
    allmeta.append(details)
    print(p.name,'bytes',p.stat().st_size,'duration',metadata['duration_seconds'],'sha',digest)
    if len(metadata['channels'])<30: print('channels',metadata['channels'])
    print('prefilter',sorted(set(details['prefilter'])))
(WORK/'technical_inspection.json').write_text(json.dumps(allmeta,ensure_ascii=False,indent=2)+'\n')
print((base/'chbmit-1.0.0-chb01/chb01-summary.txt').read_text()[:1600])
import mne
for p in [base/'sleep-edfx-1.0.0-sc4001/SC4001EC-Hypnogram.edf',base/'eegmmidb-1.0.0-expansion/S001R03.edf']:
    a=mne.read_annotations(p)
    print(p.name,'annotations',len(a),'first',list(zip(a.onset,a.duration,a.description))[:16])
    (WORK/(p.stem+'.annotations.json')).write_text(json.dumps([{'onset_s':float(o),'duration_s':float(d),'label':str(l)} for o,d,l in zip(a.onset,a.duration,a.description)],ensure_ascii=False,indent=2)+'\n')
