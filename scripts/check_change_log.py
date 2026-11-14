"""Require a changelog entry alongside behavior, interface or default changes."""
import argparse
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREFIXES = ('src/ephys_qc/', 'apps/workbench/', 'requirements/', 'deploy/')
FILES = {'pyproject.toml', 'compose.yaml', 'deploy.sh'}


def check(base, head='HEAD', *, root=REPO):
    # A new branch has no prior commit to compare with.
    if not base or set(base) == {'0'}:
        print('No prior revision; changelog check starts with the next change.')
        return
    changed = subprocess.check_output(
        ['git', 'diff', '--name-only', base, head, '--'], cwd=root, text=True).splitlines()
    guarded = [p for p in changed if p.startswith(PREFIXES) or p in FILES]
    if guarded and 'CHANGELOG.md' not in changed:
        raise ValueError('Update CHANGELOG.md with behavior, defaults, compatibility and validation for: '
                         + ', '.join(guarded[:8]))
    print(f'Changelog check passed ({len(guarded)} implementation/configuration files).')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', default='HEAD')
    args = parser.parse_args()
    try:
        check(args.base, args.head)
    except ValueError as error:
        raise SystemExit(str(error)) from error
