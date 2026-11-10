"""M07: Source-clock annotation context, separate from quality labels."""
from ..annotations import check_annotations

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    record = context.record
    row = context.row
    state = context.state
    save = context.save
    from ..method_selection import selected
    method = {'sleep_stages_tsv':'sleep_timeline','bids_events_tsv':'task_timeline','clinical_events_tsv':'clinical_timeline'}.get(record['annotation'].get('format'))
    if method and not selected(context.config, method):
        row.update(status='skipped', reason='未选择与当前标注类型对应的检查。')
        return row
    payload = check_annotations(record["annotation"], state["start"], state["recording"]["duration_seconds"],
                                state["fs"], record["metadata"]["duration_seconds"], state["first"])
    save("M07_annotations.json", payload)
    row["status"] = payload["status"]
    row["summary"] = {k: payload[k] for k in ("format", "label_scope", "total_rows", "selected_count", "stage_seconds", "covered_seconds", "uncovered_intervals", "issues", "quality_ground_truth")}
    row['summary']['clinical_event_seconds'] = payload.get('clinical_event_seconds')
    row["reason"] = "按原记录时钟核对事件/状态；未用作信号质量标签或检测输入"

    return row
