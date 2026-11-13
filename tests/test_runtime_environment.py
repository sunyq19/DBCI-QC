"""Guard the venv/base-Python regression and both sides of the worker boundary."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest
from ephys_qc import runtime_environment as runtime

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('run_local', ROOT / 'scripts/run_local.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_launcher_keeps_venv_symlink_and_ignores_calling_python(tmp_path):
    python = tmp_path / '.venv/bin/python'
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    (tmp_path / '.venv/pyvenv.cfg').write_text('include-system-site-packages = false\n')
    with patch.object(launcher.sys, 'executable', '/wrong/python'):
        command = launcher.server_command(tmp_path, tmp_path / 'workbench.json')
    assert command[0] == str(python)
    assert command[0] != str(python.resolve())


def test_launcher_does_not_fall_back_to_system_python(tmp_path):
    with pytest.raises(RuntimeError, match='setup_local.py'):
        launcher.server_command(tmp_path, tmp_path / 'workbench.json')


def test_inherited_python_settings_cannot_redirect_launch():
    with patch.dict(os.environ, {'PYTHONHOME': '/wrong', 'PYTHONPATH': '/wrong',
                                'DBCI_QC_GNOSIS_CONFIG': '/custom/gnosis.json'}):
        env = runtime.isolated_environment()
    assert 'PYTHONHOME' not in env and 'PYTHONPATH' not in env
    assert env['PYTHONNOUSERSITE'] == '1'
    assert env['DBCI_QC_GNOSIS_CONFIG'] == '/custom/gnosis.json'


def test_missing_mne_is_actionable_and_does_not_pass():
    def import_module(name):
        if name == 'mne':
            raise ModuleNotFoundError("No module named 'mne'")
    with patch.object(runtime.importlib, 'import_module', side_effect=import_module), \
         patch.object(runtime.importlib.metadata, 'version', return_value='test'):
        with pytest.raises(RuntimeError, match="No module named 'mne'") as error:
            runtime.validate_runtime()
    assert 'setup_local.py' in str(error.value)


def test_worker_with_same_binary_but_different_environment_is_checked(tmp_path):
    worker = tmp_path / 'worker-python'
    worker.symlink_to(sys.executable)
    current = {'ok': True, 'python': sys.executable, 'errors': []}
    bad = {'ok': False, 'python': str(worker), 'errors': ['mne missing']}
    with patch.object(runtime, 'probe', return_value=current), \
         patch.object(runtime.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, json.dumps(bad))) as run:
        with pytest.raises(RuntimeError, match='mne missing'):
            runtime.validate_runtime(str(worker))
    assert run.call_args.args[0][0] == str(worker)


def test_actual_empty_environment_rejected_before_binding_or_state_changes(tmp_path):
    # This is the original failure mode: code imports, but MNE is absent.
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(tmp_path / 'empty')], check=True)
    python = tmp_path / 'empty/bin/python'
    config = tmp_path / 'workbench.json'
    data = tmp_path / 'runtime'
    config.write_text(json.dumps({'python': str(python), 'data_dir': str(data), 'inputs': [], 'profiles': []}))
    process = subprocess.run([str(python), str(ROOT / 'apps/workbench/server.py'), '--config', str(config)],
                             env=runtime.isolated_environment(), capture_output=True, text=True, timeout=30)
    assert process.returncode != 0
    assert "No module named 'mne'" in process.stderr
    assert 'setup_local.py' in process.stderr
    assert not data.exists()
