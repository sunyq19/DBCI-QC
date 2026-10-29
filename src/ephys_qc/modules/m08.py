"""M08: Assessment aggregation and final source-integrity verification."""
from ..annotations import file_sha256

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    result = context.result
    row = context.row
    source = context.source
    source_context = context.source_context
    state = context.state
    save = context.save
    if result["source_sha256"]:
        unchanged = True if source_context else file_sha256(source) == result["source_sha256"]
        if state.get('reader'):
            state['reader'].assert_unchanged(hashes=not bool(source_context))
        if not unchanged:
            raise ValueError("Original source changed during this run; results cannot be accepted")
    else:
        unchanged = None
    row["summary"] = {"score": result["score"], "source_unchanged": unchanged,
                      "module_assessments": [{"id": m["id"], "status": m["status"], "reason": m["reason"], "summary": m["summary"]} for m in result["modules"] if m["id"] != "M08"],
                      "missing_capabilities": ["空间坏道预测", "local AutoReject", "ICA/ICLabel", "一般重复数据块"],
                      "execution_status_is_not_quality": True}
    if any(m["status"] in {"partial", "failed"} for m in result["modules"] if m["id"] != "M08"):
        row.update(status="partial", reason="部分方法未评或执行失败；保留分项结论，不生成总分")
    save("M08_assessment.json", row["summary"])

    return row
