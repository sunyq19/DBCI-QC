"""Exercise the changelog gate against real revision pairs."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('check_change_log', Path(__file__).resolve().parents[1] / 'scripts/check_change_log.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.fixture
def history(tmp_path):
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=tmp_path, text=True).strip()
    git('init', '-q')
    git('config', 'user.name', 'Test')
    git('config', 'user.email', 'test@example.invalid')
    (tmp_path / 'README.md').write_text('base')
    git('add', '.')
    git('commit', '-qm', 'base')
    return tmp_path, git, git('rev-parse', 'HEAD')


@pytest.mark.parametrize('path', ['src/ephys_qc/recommendations.py', 'apps/workbench/intake.py',
                                 'requirements/workbench.txt', 'compose.yaml', 'deploy/Dockerfile'])
def test_behavior_change_requires_changelog(history, path):
    root, git, base = history
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('changed')
    git('add', '.')
    git('commit', '-qm', 'change')
    with pytest.raises(ValueError, match='CHANGELOG.md'):
        gate.check(base, root=root)
    (root / 'CHANGELOG.md').write_text('New behavior, compatibility and validation.')
    git('add', 'CHANGELOG.md')
    git('commit', '-qm', 'document')
    gate.check(base, root=root)


def test_documentation_only_and_initial_branch(history):
    root, git, base = history
    (root / 'README.md').write_text('documentation correction')
    git('add', '.')
    git('commit', '-qm', 'docs')
    gate.check(base, root=root)
    gate.check('0' * 40, root=root)
