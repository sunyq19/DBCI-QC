"""Physical M01–M09 implementations, independent of the workbench UI.

``module_specs`` exposes the actual importable entrypoints without importing
scientific dependencies. Direct handlers consume ``ModuleContext``; public
callers should use the toolkit so that planning, dependencies and evidence are
preserved.
"""
from importlib import import_module

from .context import ModuleContext


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


def module_specs() -> list[dict]:
    """Return independent-file entrypoints and their shared-state contracts."""
    return [{"id": mid, "entrypoint": f"ephys_qc.modules.{mid.lower()}:run",
             "required_state": list(required), "provides_state": list(provided)}
            for mid, (required, provided) in _STATE.items()]


def get_handler(module_id: str):
    """Resolve an allowlisted handler lazily; never run a complete pipeline."""
    if module_id not in _STATE:
        raise ValueError(f"Unknown module: {module_id}")
    return import_module(f".{module_id.lower()}", __name__).run


def run_module(module_id: str, context: ModuleContext) -> dict:
    """Execute one physical implementation; failures propagate to the scheduler."""
    return get_handler(module_id)(context)


__all__ = ["ModuleContext", "module_specs", "get_handler", "run_module"]
