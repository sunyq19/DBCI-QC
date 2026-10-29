"""M04: Spectral measurements and explicit unassessed conditions."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    from brainelecqc.eeg.spectral import compute_spectral_qc
    payload = compute_spectral_qc(*_args(state), **_origin(state), config=methods.get("spectral"))
    save("M04_spectral.json", payload)
    line = payload["line_noise"]
    row["summary"] = {"line_status": line["status"], "line_observation_count": len(line["observations"]),
                      "line_flagged_observations": sum(r["flagged"] for r in line["observations"]),
                      "full_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["full"]}),
                      "window_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["windows"]}),
                      "drift_assessment": "not_implemented"}
    if line["status"] != "computed" or any(r["status"] != "computed" for scope in ("full", "windows") for r in payload["parameterization"][scope]):
        row.update(status="partial", reason="部分工频/频谱指标未能评估，详见方法结果")

    return row
