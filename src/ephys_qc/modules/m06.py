"""M06: Auxiliary events and muscle evidence with continuity guards."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    from brainelecqc.eeg.events import compute_event_qc
    from brainelecqc.eeg.muscle import compute_muscle_qc
    aux = {"references": state["references"], "reference_channels": state["reference_channels"]}
    events = compute_event_qc(*_args(state), **_origin(state), **aux, config=methods.get("events"))
    save("M06_auxiliary_events.json", events)
    payload = compute_muscle_qc(*_args(state), **_origin(state), **aux, config=methods.get("muscle"),
                                excluded_intervals=state["continuity_candidates"])
    save("M06_muscle.json", payload)
    row["summary"] = {"events": {k: {"status": b["status"], "event_count": b["detected_event_count"]} for k, b in events["by_kind"].items()},
                      "muscle_status": payload["status"], "emg_reference_status": payload["reference"]["status"],
                      "high_frequency_candidate_count": len(payload["candidates"]),
                      "emg_supported_count": sum(c["kind"] == "emg_supported_burst" for c in payload["candidates"]),
                      "continuity_guard_applied": True}
    if any(b["status"] not in {"computed", "no_events"} for b in events["by_kind"].values()) or payload["reference"]["status"] != "ok" or payload["status"] != "ok":
        row.update(status="partial", reason="部分生理伪迹缺少可用辅助证据；一般高频突发不等于已确认肌电")
    del events

    return row
