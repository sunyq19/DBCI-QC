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
                      "missing_capabilities": (["ECoG伪迹分类", "触点空间关系核验", "临床质量准确性验证", "一般重复数据块"]
                                               if context.record.get('modality') == 'ecog' else
                                               ['sEEG伪迹分类', '杆内邻接和双极关系核验', '病理与伪迹独立标签'] if context.record.get('modality') == 'seeg' else
                                               ['spike sorting与单元质量', 'AP峰定位漂移', '跨流同步和采样相位补偿', '跨数据集阈值验证'] if context.record.get('modality') == 'extracellular' else
                                               ["独立真值准确性验证", "专家审核阈值", "一般重复数据块"]),
                      "execution_status_is_not_quality": True}
    if any(m["status"] in {"partial", "failed"} for m in result["modules"] if m["id"] != "M08"):
        row.update(status="partial", reason="部分检查含格式、适用性或执行提示；详见检查明细")
    save("M08_assessment.json", row["summary"])

    return row
