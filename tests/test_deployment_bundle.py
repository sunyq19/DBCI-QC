"""Deployment settings must preserve temporary uploads and exclude private state."""
import importlib.util
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_deploy_bundle import validate_member

spec = importlib.util.spec_from_file_location('qc_container', ROOT / 'deploy/docker/qc_entrypoint.py')
container = importlib.util.module_from_spec(spec)
spec.loader.exec_module(container)


def test_container_uses_public_library_and_temporary_upload_policy():
    settings = container.settings_from_env({'PUBLIC_ORIGIN': 'https://qc.example.org'})
    assert settings['data_policy'] == 'public-only/1'
    assert settings['inputs'] == [] and settings['public_records'] == {}
    assert settings['deployment']['public_origin'] == 'https://qc.example.org'
    assert settings['data_dir'] == '/data/runtime'


@pytest.mark.parametrize('origin', ['*', 'https://qc.example.org/path', 'http://name:password@example.org'])
def test_container_rejects_invalid_origin(origin):
    with pytest.raises(ValueError):
        container.settings_from_env({'PUBLIC_ORIGIN': origin})


def test_public_catalog_cannot_disable_upload_isolation():
    with pytest.raises(ValueError):
        container.settings_from_env({}, {'data_policy': 'legacy'})
    settings = container.settings_from_env({}, {'public_records': {'public-id': {'url': 'https://example.org/dataset'}}})
    assert 'public-id' in settings['public_records']
    assert settings['data_policy'] == 'public-only/1'


@pytest.mark.parametrize('path', ['.local/workbench.json', 'apps/flow-editor/.env',
    'state/password.verifier', 'data/flow.sqlite', '../private', '/private', '.env.cloud'])
def test_deploy_archive_rejects_private_state(path):
    with pytest.raises(ValueError):
        validate_member(path)


def test_public_example_assets_and_environment_template_are_packaged():
    for path in ['deploy/demo.env.example', 'apps/workbench/example-cache/report.pdf',
                 'apps/flow-editor/content/module-catalog.json']:
        validate_member(path)


def test_docker_copies_nested_dependency_files_and_versions_match():
    from ephys_qc.version import __version__
    import json
    dockerfile=(ROOT/'deploy/docker/Dockerfile.qc').read_text()
    assert 'COPY requirements/ /tmp/requirements/' in dockerfile
    assert '-r drift-cpu.txt' in (ROOT/'requirements/workbench.txt').read_text()
    assert (ROOT/'requirements/drift-cpu.txt').is_file()
    for app in ['workbench','collaboration']:
        assert f'image: dbci-qc/{app}:{__version__}' in (ROOT/'compose.yaml').read_text()
    assert json.loads((ROOT/'apps/flow-editor/package.json').read_text())['version']==__version__
