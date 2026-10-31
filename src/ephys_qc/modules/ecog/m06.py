"""Optional research evidence only; no scalp physiological-artifact fallback."""

def run(context):
    context.row["summary"] = {"base_artifact_classifier": "not_implemented"}
    context.row["reason"] = "仅执行显式选择的研究扩展；生理伪迹分类未实现。"
    return context.row
