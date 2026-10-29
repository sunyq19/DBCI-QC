"""M03: Continuity candidates; does not remove or repair samples."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    from brainelecqc.eeg.continuity import compute_continuity_qc
    payload = compute_continuity_qc(*_args(state), **_origin(state), channels=state["channels"], config=methods.get("continuity"))
    state["continuity_candidates"] = payload["candidates"]
    save("M03_continuity.json", payload)
    row["summary"] = {"candidate_count": len(payload["candidates"]),
                      "kinds": sorted({r["kind"] for r in payload["candidates"]}),
                      "automatic_exclusions": 0, "repeated_block_assessment": "not_implemented"}
    if any(c.get('physical_min') is None or c.get('physical_max') is None or
           c.get('digital_to_physical_scale') is None for c in state['channels']):
        row['summary']['adc_endpoint_assessment'] = 'unavailable_for_some_channels'
        row.update(status='partial', reason='恒值检查已执行；部分格式没有提供 ADC 量程端点，端点平台判定未评。')

    return row
