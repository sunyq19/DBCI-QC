"""Shared CLI paths for the public-data preparation scripts."""
import argparse
from pathlib import Path

def paths():
    parser=argparse.ArgumentParser(description="Prepare four public EEG examples without jobs, cleaning, or source modification")
    parser.add_argument('--data-root',type=Path,required=True,help='External directory for original public downloads and derived label sidecars')
    parser.add_argument('--evidence-dir',type=Path,required=True,help='External directory for manifests, registration draft, and audit output')
    parser.add_argument('--repo-root',type=Path,required=True,help='Path containing apps/workbench/input_config.py')
    parser.add_argument('--existing-r02',type=Path,help='Optional existing S001R02.edf to verify and reuse without copying')
    args=parser.parse_args()
    args.data_root=args.data_root.expanduser().resolve()
    args.evidence_dir=args.evidence_dir.expanduser().resolve()
    args.repo_root=args.repo_root.expanduser().resolve()
    if args.existing_r02:
        args.existing_r02=args.existing_r02.expanduser().resolve()
        if not args.existing_r02.is_file():parser.error('--existing-r02 does not exist')
    args.data_root.mkdir(parents=True,exist_ok=True)
    args.evidence_dir.mkdir(parents=True,exist_ok=True)
    return args
