"""Installation must preserve existing configuration and use the venv interpreter."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_local', Path(__file__).resolve().parents[1] / 'scripts/setup_local.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SetupTests(unittest.TestCase):
    def test_venv_symlink_is_not_resolved_to_base_python(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            python = root / '.venv/bin/python'
            python.parent.mkdir(parents=True)
            python.symlink_to(sys.executable)
            target, created = installer.write_config(root, python, root / '.local/runtime', 18769)
            settings = json.loads(target.read_text())
            self.assertTrue(created)
            self.assertEqual(settings['python'], str(python))
            self.assertEqual(settings['port'], 18769)
            self.assertTrue(Path(settings['data_dir']).is_absolute())

    def test_repeat_setup_preserves_config_bytes_and_registered_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target, _ = installer.write_config(root, root / '.venv/bin/python', root / 'data', 18769)
            existing = {'port': 19999, 'python': '/custom/python', 'data_dir': '/custom/runtime',
                        'inputs': [{'id': 'existing'}], 'profiles': []}
            raw = json.dumps(existing).encode()
            target.write_bytes(raw)
            _, created = installer.write_config(root, root / '.venv/bin/python', root / 'other', 8769)
            self.assertFalse(created)
            self.assertEqual(target.read_bytes(), raw)

    def test_failed_install_does_not_create_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(installer.sys, 'version_info', (3, 11)), \
                 patch.object(installer.shutil, 'which', return_value='/usr/bin/git'), \
                 patch.object(installer.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'pip')):
                with self.assertRaises(subprocess.CalledProcessError):
                    installer.setup(root, root / 'runtime', 8769)
            self.assertFalse((root / '.local/workbench.json').exists())


if __name__ == '__main__':
    unittest.main()
