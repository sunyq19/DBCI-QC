"""Internal module boundary; no web service or scientific package is imported.

The scheduler owns dependency resolution, status events, exception handling and
artifact serialization. Each handler receives the frozen request/configuration,
updates only its documented shared-state outputs and result row, then returns
that row. ``record``, ``plan`` and ``config`` are read-only by convention. Signal
arrays are calibrated source values and must not be modified by a handler.

``result`` carries cross-module evidence used by M01/M02/M08/M09. ``state`` owns
the reader and loaded window (M01/M02) and the continuity guard (M03). A handler
does not close a shared reader: its lifecycle belongs to the scheduler.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ModuleContext:
    record: dict
    plan: dict
    config: dict
    state: dict
    result: dict
    row: dict
    source: Path
    root: Path
    artifacts: Path
    write_artifact: Callable[[str, Any, dict], None]
    source_context: dict | None = None

    def save(self, name: str, payload: Any) -> None:
        """Persist evidence through the scheduler and attach it to this row."""
        self.write_artifact(name, payload, self.row)


def backend_args(state):
    """Immutable signal values, native rate and stable source-channel identity."""
    return (state["data"], state["fs"], [c["channel_id"] for c in state["channels"]],
            [c["raw_name"] for c in state["channels"]])


def source_origin(state):
    """Use the original source clock once, without rebasing each window."""
    return {"start_sample": state["first"], "start_seconds": state["start"]}
