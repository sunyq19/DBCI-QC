"""Fetch pinned public reader fixtures into a fresh local folder, or verify copies.

No sample is republished. See the registry for separate source/license limits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile

REPO = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify-only', action='store_true', help='Read existing copies; no network or writes')
    args = parser.parse_args()
    output = args.output.resolve()
    registry = json.loads((REPO / 'datasets/reader-samples.json').read_text())
    if output.is_relative_to(REPO):
        raise SystemExit('Keep signal files outside the repository.')
    if args.verify_only:
        if not output.is_dir():
            raise SystemExit('The sample directory does not exist.')
    else:
        output.mkdir(parents=True, exist_ok=False)
    for row in registry['files']:
        path = output / row['relative_path']
        if args.verify_only:
            data = path.read_bytes()
        else:
            with urllib.request.urlopen(row['source_url'], timeout=60) as response:
                data = response.read(row['expected_bytes'] + 1)
        if len(data) != row['expected_bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Source bytes do not match pinned registry: ' + row['relative_path'])
        if not args.verify_only:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    for row in registry['archives']:
        path = output / row['relative_path']
        folder = Path(row['relative_path']).stem
        if not args.verify_only:
            with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED) as archive:
                for member in row['members']:
                    info = zipfile.ZipInfo(member, date_time=(2026, 10, 29, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, (output / folder / member).read_bytes())
        # ZIP container metadata may vary; the source members must not.
        with zipfile.ZipFile(path) as archive:
            if sorted(archive.namelist()) != sorted(row['members']):
                raise ValueError('Unexpected archive members: ' + path.name)
            for member in row['members']:
                if archive.read(member) != (output / folder / member).read_bytes():
                    raise ValueError('Archive changed source bytes: ' + member)
        row.update(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    if not args.verify_only:
        registry['zip_bytes'] = sum(row['bytes'] for row in registry['archives'])
        (output / 'manifest.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': True, 'source_files': len(registry['files']),
                      'archives': len(registry['archives']), 'verify_only': args.verify_only}))


if __name__ == '__main__':
    main()
