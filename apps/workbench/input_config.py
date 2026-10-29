"""Technical inventory entry points; scientific readers are imported on demand."""
from pathlib import Path
import sys

_SRC = str(Path(__file__).resolve().parents[2] / 'src')
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def edf_metadata(path):
    """Legacy lightweight EDF/BDF header checks: standard library only."""
    from ephys_qc.readers.edf_header import inspect_header
    return inspect_header(path)


def inspect_recording(path):
    """Full multi-format inventory; use the configured scientific interpreter."""
    from ephys_qc.readers import inspect_recording as inspect
    return inspect(path)


def list_readers():
    from ephys_qc.readers import list_readers as readers
    return readers()
