"""Check the raw files needed by the published examples without running QC.

python scripts/check_example_sources.py --config /data/workbench.json --checksums
The config may also be a public-catalog.json with example_review_sources only.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'apps/workbench/example-cache'


def check(config, cache=ROOT, checksums=False):
    cache = Path(config.get('example_cache_dir') or cache)
    manifest = json.loads((cache / 'manifest.json').read_text())
    configured = config.get('example_review_sources', {})
    files, problems, sources = {}, [], set()
    for name in manifest['files']:
        if not name.startswith('review/') or not name.endswith('.json'):
            continue
        saved = json.loads((cache / manifest['release'] / name).read_text())
        source = saved['source']; digest = source['source_sha256']
        if digest in sources:
            continue
        sources.add(digest)
        primary = configured.get(digest)
        if not primary:
            problems.append(f'{name}: 未配置示例源文件 ({digest[:12]})')
            continue
        primary = Path(primary)
        members = source.get('source_files') or [{'name': primary.name, 'sha256': digest}]
        if not primary.is_file():
            problems.append(f'{primary}: 主文件不存在')
        for member in members:
            leaf = member['name']
            if Path(leaf).name != leaf or leaf in {'.', '..'}:
                problems.append(f'{name}: 无效的配套文件名')
                continue
            path = primary.parent / leaf
            key = (str(path), member['sha256'])
            if key in files:
                continue
            files[key] = None
            if not path.is_file():
                problems.append(f'{path}: 缺少文件')
            elif checksums:
                with path.open('rb') as handle:
                    actual = hashlib.file_digest(handle, 'sha256').hexdigest()
                if actual != member['sha256']:
                    problems.append(f'{path}: 文件内容与报告不匹配')
    return dict(release=manifest['release'], examples=len(manifest['examples']),
                recordings=len(sources), files=len(files), checksums=checksums, problems=problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--checksums', action='store_true')
    args = parser.parse_args()
    result = check(json.loads(args.config.read_text()), checksums=args.checksums)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result['problems'] else 0)


if __name__ == '__main__':
    main()
