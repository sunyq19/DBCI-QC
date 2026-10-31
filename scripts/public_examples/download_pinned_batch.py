"""Download a bounded, SHA-256-pinned public data manifest outside the repo.

This only acquires files. It never edits source recordings, selects algorithms,
registers workbench inputs, or runs QC. Failed partial files are retained.
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--data-root', required=True, type=Path)
    p.add_argument('--receipt', required=True, type=Path)
    p.add_argument('--offline', action='store_true')
    args = p.parse_args()
    repo = Path(__file__).resolve().parents[2]
    root = args.data_root.resolve()
    if root == repo or repo in root.parents:
        p.error('Signal data must stay outside the source repository')
    spec = json.loads(args.manifest.read_text())
    files = spec['files']
    if not files or sum(row['bytes'] for row in files) > 1024 ** 3:
        p.error('Manifest must be nonempty and fit the 1 GiB budget')
    seen = set()
    for row in files:
        rel = Path(row['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or str(rel) in seen:
            p.error('Unsafe or duplicate destination')
        seen.add(str(rel))
        if row['bytes'] < 0 or len(row['sha256']) != 64 or not row['url'].startswith('https://'):
            p.error('Every file needs a positive size, SHA-256, and HTTPS source')

    def fetch(row):
        path = root / row['relative_path']
        result = {**row, 'path': str(path)}
        try:
            if path.is_symlink() or root not in path.resolve().parents:
                raise ValueError('Destination escapes data root or is a symbolic link')
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                operation = 'reused_verified'
            else:
                if args.offline:
                    raise FileNotFoundError('Missing offline file')
                temporary = path.with_name(path.name + '.partial')
                request = urllib.request.Request(row['url'], headers={'User-Agent': 'DBCI-QC-pinned-batch/1'})
                with urllib.request.urlopen(request, timeout=60) as response, temporary.open('xb') as stream:
                    total = 0
                    while block := response.read(1024 * 1024):
                        total += len(block)
                        if total > row['bytes']:
                            raise ValueError('Download exceeded pinned size')
                        stream.write(block)
                if temporary.stat().st_size != row['bytes'] or digest(temporary) != row['sha256']:
                    raise ValueError('Downloaded bytes differ from pinned source')
                temporary.rename(path)
                operation = 'downloaded'
            if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
                raise ValueError('Existing file differs from pinned source; no overwrite')
            result.update(operation=operation, verified=True)
            if row.get('role') == 'signal':
                print(operation, row['relative_path'], row['bytes'], flush=True)
        except Exception as error:
            result.update(verified=False, error=f'{type(error).__name__}: {error}')
            print('FAILED', row['relative_path'], result['error'], flush=True)
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(fetch, files))
    receipt = {'manifest_sha256': digest(args.manifest), 'files': results,
               'verified': sum(bool(row['verified']) for row in results),
               'bytes_verified': sum(row['bytes'] for row in results if row['verified'])}
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in receipt.items() if k != 'files'}), flush=True)
    if not all(row['verified'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
