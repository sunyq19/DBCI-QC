"""Actually run each recommended pipeline in isolated output directories.

Does not start a service, edit registration, or alter originals. An existing
completed job is never overwritten. This is engineering validation, not accuracy.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import time


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-id", action="append", help="Validate only these registered records; default is every record")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo_root.resolve() / "src"))
    from ephys_qc.recommendations import recommend
    from ephys_qc.core import build_plan, run_job
    output = args.output.expanduser().resolve()
    if output.exists():
        raise ValueError("Use a new validation directory to preserve previous evidence")
    output.mkdir(parents=True)
    records = json.loads(args.registration.read_text())["inputs"]
    if args.input_id:
        unknown = set(args.input_id) - {record["id"] for record in records}
        if unknown:
            raise ValueError("Unknown input ids: " + ", ".join(sorted(unknown)))
        records = [record for record in records if record["id"] in args.input_id]
    runs = []
    for record in records:
        paths = [record["source_path"]]
        if record.get("annotation"):
            paths += [record["annotation"]["path"], record["annotation"]["source_path"]]
        before = {p: digest(p) for p in sorted(set(paths))}
        assert before[record["source_path"]] == record["expected_sha256"]
        proposed = recommend(record)
        assert proposed["can_apply"], proposed
        plan = build_plan(record, proposed["selected_modules"], proposed["qc_config"])
        assert plan["plan_id"] == proposed["plan_id"]
        job = output / record["id"]
        job.mkdir()
        dump(job / "recommendation.json", proposed)
        dump(job / "input.registration.json", record)
        events = []

        def emit(module_id, status, reason):
            events.append({"module_id": module_id, "status": status, "reason": reason})
            dump(job / "events.json", events)
            print(record["id"], module_id, status, reason, flush=True)

        started = time.monotonic()
        result = run_job({"input": deepcopy(record), "plan": plan}, job, emit)
        after = {p: digest(p) for p in before}
        assert after == before, "Original or annotation changed"
        assert result["plan_id"] == plan["plan_id"]
        assert result["score"]["value"] is None
        assert result["review_status"] == "pending"
        assert result["source_sha256"] == before[record["source_path"]]
        assert (job / "artifacts/report.html").is_file()
        assert not any(row["status"] == "failed" for row in result["modules"]), result["modules"]
        summaries = {row["id"]: row for row in result["modules"]}
        assert summaries["M08"]["summary"]["source_unchanged"]
        annotations = job / "artifacts/M07_annotations.json"
        annotation_check = None
        if annotations.exists():
            value = json.loads(annotations.read_text())
            assert not value["quality_ground_truth"] and not value["used_for_signal_detection"]
            annotation_check = {key: value.get(key) for key in ("format", "status", "selected_count", "stage_seconds", "covered_seconds", "issues")}
            if record["id"] == "sleep-edfx-sc4011":
                assert value["stage_seconds"] == {"REM": 120.0}
        runs.append({"input_id": record["id"], "result_path": str(job / "result.json"), "report_path": str(job / "artifacts/report.html"),
                     "recommendation_id": proposed["recommendation_id"], "plan_id": plan["plan_id"], "status": result["status"],
                     "selected_modules": result["selected_modules"], "recording": result["recording"],
                     "module_statuses": {row["id"]: row["status"] for row in result["modules"]}, "extensions": result["extensions"],
                     "annotation": annotation_check, "duration_seconds": time.monotonic() - started,
                     "originals_before_sha256": before, "originals_after_sha256": after, "originals_unchanged": True,
                     "quality_score": None, "review_status": result["review_status"], "warnings": result["warnings"]})
        dump(output / "validation_summary.json", {"runs": runs, "all_requested_records_finished": len(runs) == len(records),
                                                   "clinical_accuracy_validated": False, "signal_processing_executed": True,
                                                   "service_used": False, "registration_changed": False})
    print("Validation summary:", output / "validation_summary.json", flush=True)


if __name__ == "__main__":
    main()
