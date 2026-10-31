"""Install pinned source checkouts outside the repository and configure Octave.

Run explicitly; never called by uploads, planning, or the execution service.
Requires git and an existing Octave 10.3 installation. No MATLAB licence is used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

PINS={
    'clean_rawdata':('sccn/clean_rawdata','85eab7d22f00f1ed36392c96eb0774752d62bd11'),
    'cleanline':('sccn/cleanline','117bffa6e1fbc6d042a7e75cec9e289e1aa5be72'),
    'zapline-plus':('MariusKlug/zapline-plus','f4628a32f4ec53cebfb07b1f6a8f465f44f1377a'),
    'fieldtrip':('fieldtrip/fieldtrip','02149cbf43920b87b823567b28feaa1cd9d5e6a4'),
}
SIGNAL_SHA='f5989b4f148e6f5b696a7b7ceee8c610140acf6084eb3e7eafbf0eb38df79a33'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--octave',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'.local/qc-methods.json')
    args=parser.parse_args();root=args.source_root.resolve()
    if not args.octave.is_file():raise SystemExit('Provide an installed octave-cli executable')
    if args.output.exists():raise SystemExit('Configuration exists; keep it and choose a new --output to review')
    root.mkdir(parents=True,exist_ok=True)
    for name,(repository,commit) in PINS.items():
        path=root/name
        if not path.exists():
            subprocess.run(['git','init',str(path)],check=True)
            subprocess.run(['git','-C',str(path),'remote','add','origin','https://github.com/'+repository+'.git'],check=True)
            subprocess.run(['git','-C',str(path),'fetch','--depth','1','origin',commit],check=True)
            subprocess.run(['git','-C',str(path),'checkout','--detach','FETCH_HEAD'],check=True)
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        dirty=subprocess.check_output(['git','-C',str(path),'status','--porcelain','--untracked-files=no'],text=True)
        if actual!=commit or dirty:raise SystemExit('Existing checkout differs; do not reset it: '+str(path))
    archive=root/'signal-1.4.8.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve('https://github.com/gnu-octave/octave-signal/releases/download/1.4.8/signal-1.4.8.tar.gz',archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SIGNAL_SHA:raise SystemExit('Signal archive checksum mismatch')
    if not (root/'signal-1.4.8').exists():
        with tarfile.open(archive) as bundle:bundle.extractall(root,filter='data')
    config={'octave':str(args.octave.resolve()),'source_root':str(root),
            'commits':{name:pin[1] for name,pin in PINS.items()},'signal_sha256':SIGNAL_SHA}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n')
    print('Configured:',args.output)
    print('Read docs/optional-methods-runtime.md and upstream licences before deployment or redistribution.')

if __name__=='__main__':main()
