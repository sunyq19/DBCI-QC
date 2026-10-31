"""Physical M01–M09 implementations, independent of the workbench UI.

``module_specs`` exposes the actual importable entrypoints without importing
scientific dependencies. Direct handlers consume ``ModuleContext``; public
callers should use the toolkit so that planning, dependencies and evidence are
preserved.
"""
from importlib import import_module

from .context import ModuleContext
from ..modalities import ROUTES, DESCRIPTIVE, route


_STATE = {
    "M01": ((), ("reader", "description")),
    "M02": (("reader", "description"), ("data", "data_sha256", "channels", "references",
             "reference_channels", "fs", "first", "start", "recording")),
    "M03": (("data", "fs", "channels", "first", "start"), ("continuity_candidates",)),
    "M04": (("data", "fs", "channels", "first", "start"), ()),
    "M05": (("data", "fs", "channels", "first", "start"), ()),
    "M06": (("data", "fs", "channels", "first", "start", "references",
             "reference_channels", "continuity_candidates"), ()),
    "M07": (("start", "recording", "fs", "first"), ()),
    # M08/M09 intentionally tolerate absent state after an upstream failure.
    "M08": ((), ()),
    "M09": ((), ()),
}


def module_specs(modality='scalp_eeg') -> list[dict]:
    """Return independent-file entrypoints and their shared-state contracts."""
    if modality not in ROUTES:
        raise ValueError('Unsupported QC modality: ' + str(modality))
    return [{"id": mid, "entrypoint": f"ephys_qc.modules.{(route(modality)['key'] + '.' if modality in DESCRIPTIVE and mid in {'M03','M04','M05','M06'} else '')}{mid.lower()}:run",
             "required_state": list(required), "provides_state": list(provided)}
            for mid, (required, provided) in _STATE.items()]


def get_handler(module_id: str, modality='scalp_eeg'):
    """Resolve an allowlisted handler lazily; never run a complete pipeline."""
    if module_id not in _STATE:
        raise ValueError(f"Unknown module: {module_id}")
    if modality not in ROUTES:
        raise ValueError('Unsupported QC modality: ' + str(modality))
    prefix = route(modality)['key'] + '.' if modality in DESCRIPTIVE and module_id in {'M03','M04','M05','M06'} else ''
    return import_module(f".{prefix}{module_id.lower()}", __name__).run


def run_module(module_id: str, context: ModuleContext) -> dict:
    """Execute one physical implementation; failures propagate to the scheduler."""
    return get_handler(module_id, context.record.get('modality', 'scalp_eeg'))(context)


__all__ = ["ModuleContext", "module_specs", "get_handler", "run_module"]
