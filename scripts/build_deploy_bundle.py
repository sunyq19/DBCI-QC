"""Build a source deployment archive from one Git commit, never from private runtime files."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def validate_member(name):
    parts = Path(name).parts
    forbidden = {'.git', '.local', '.venv', 'node_modules', '.wrangler',
                 'runtime', '__pycache__', '.pytest_cache'}
    if (name.startswith('/') or '..' in parts or set(parts) & forbidden or
            any(p == '.env' or p.startswith('.env.') for p in parts) or
            name.endswith(('.sqlite', '.sqlite-wal', '.sqlite-shm', '.verifier', '.pem', '.key',
                           '.edf', '.bdf', '.nwb', '.fif', '.set', '.fdt', '.bin'))):
        raise ValueError('Private or generated path in release: ' + name)


def build(output, ref='HEAD'):
    commit = subprocess.check_output(['git', 'rev-parse', '--verify', ref + '^{commit}'], cwd=ROOT, text=True).strip()
    version_source = subprocess.check_output(['git', 'show', commit + ':src/ephys_qc/version.py'], cwd=ROOT, text=True)
    version = re.search(r'__version__\s*=\s*[\"\']([^\"\']+)', version_source).group(1)
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('A numbered release is required')
    source = subprocess.check_output(['git', 'archive', '--format=tar', commit], cwd=ROOT)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    filename = output / f'DBCI-QC-{version}-deploy.tar.gz'
    if filename.exists():
        raise FileExistsError(filename)
    prefix = f'DBCI-QC-{version}/'
    metadata = {'version': version, 'commit': commit, 'kind': 'source-deployment',
                'requires': 'Linux, Docker Engine and Compose v2.20+; Internet for initial build',
                'includes': ['QC workbench', 'module collaboration', 'public report snapshots'],
                'excludes': ['raw recordings', 'user uploads', 'team drafts', 'passwords', 'prebuilt images']}
    with tarfile.open(fileobj=io.BytesIO(source)) as original, tarfile.open(filename, 'w:gz') as archive:
        for member in original:
            validate_member(member.name)
            if member.issym() or member.islnk():
                raise ValueError('Release must not contain symlinks: ' + member.name)
            stream = original.extractfile(member) if member.isfile() else None
            member.name = prefix + member.name
            archive.addfile(member, stream)
        payload = (json.dumps(metadata, ensure_ascii=False, indent=2) + '\n').encode()
        member = tarfile.TarInfo(prefix + 'RELEASE.json')
        member.size, member.mode = len(payload), 0o644
        archive.addfile(member, io.BytesIO(payload))
    digest = hashlib.sha256(filename.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {filename.name}\n')
    print(json.dumps({'file': str(filename), 'sha256': digest, **metadata}, ensure_ascii=False, indent=2))
    return filename


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ref', default='HEAD')
    args = parser.parse_args()
    build(args.output, args.ref)
