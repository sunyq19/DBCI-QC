"""Download, verify, and derive sidecars; never changes application configuration or starts jobs."""
import subprocess,sys
from pathlib import Path
if '--help' in sys.argv:
    from dataset_paths import paths
    paths()
folder=Path(__file__).resolve().parent
for name in ('download_public.py','inspect_public.py','build_registration.py','validate_public_examples.py'):
    subprocess.run([sys.executable,'-B',str(folder/name),*sys.argv[1:]],check=True)
