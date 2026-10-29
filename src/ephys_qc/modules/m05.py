"""M05: Channel-quality candidates within configured comparison groups."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    from brainelecqc.eeg.bad_channels import compute_bad_channels
    payload = compute_bad_channels(*_args(state), **_origin(state), groups=methods.get("comparison_groups"), config=methods.get("bad_channels"))
    save("M05_bad_channels.json", payload)
    row["summary"] = {"candidate_count": len(payload["candidates"]),
                      "candidate_channels": [c["channel_name"] for c in payload["channels"] if c["flags"]],
                      "groups": [{k: g[k] for k in ("group_id", "usable_channel_count", "thresholds_active", "status")} for g in payload["groups"]],
                      "quality_labels_used_for_detection": False,
                      "spatial_prediction": "not_implemented", "bridging": "see_optional_extensions"}
    if any(not g["thresholds_active"] for g in payload["groups"]):
        row.update(status="partial", reason="部分比较组不适用队列阈值；描述量仍保留")

    return row
