"""Run the installed BrainElecQC baseline on registered public pilot records.

This is a validation utility, not the platform scheduler. Input JSON supplies
explicit paths and technical channel selection. Human labels never enter QC.
Outputs and imported copies must be outside this repository and data sources.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import traceback


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def run(case, folder, figures):
    import numpy as np
    import mne
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["font.family"] = ["Noto Sans CJK SC", "DejaVu Sans"]
    from brainelecqc.config import storage_context
    from brainelecqc.contracts import descriptor
    from brainelecqc.db import init_db
    from brainelecqc.recordings import import_recording
    from brainelecqc.eeg.input import read_eeg_input
    from brainelecqc.eeg.pipeline import run_eeg_qc, validate_qc_config
    from brainelecqc.eeg.export import export_eeg_qc
    from brainelecqc.eeg.continuity import compute_continuity_qc
    from brainelecqc.eeg.spectral import compute_spectral_qc

    started = time.monotonic()
    source = Path(case["source_path"]).resolve()
    before = digest(source)
    if case.get("expected_sha256") and before != case["expected_sha256"]:
        raise ValueError("Input hash differs from registered source")
    selection, features, policy, methods = validate_qc_config(case["qc_config"])
    save(folder / "request.json", case)
    with storage_context(folder / "store"):
        init_db()
        record, _ = import_recording(descriptor({"label": case["id"], "modality": "eeg"}), paths=[source])
        inp = read_eeg_input(record["input_artifact_id"], **selection)
        data, meta = inp["data_volts"], inp["metadata"]
        sfreq = meta["sampling_frequency_hz"]
        raw = mne.io.read_raw_edf(source, preload=False, verbose="ERROR")
        picked = list(selection["eeg_indices"])
        start = meta["start_sample"]
        n_check = min(data.shape[1], int(sfreq))
        other = raw.get_data(picks=picked, start=start, stop=start+n_check)
        error = float(np.max(np.abs(other-data[:, :n_check])))
        if other.shape != data[:, :n_check].shape or not np.allclose(other, data[:, :n_check], rtol=1e-9, atol=1e-12):
            raise AssertionError("Independent reader voltage comparison failed")
        if len(set(c["channel_id"] for c in inp["channels"])) != len(picked):
            raise AssertionError("Channel IDs are not unique")
        raw.close()

        result = run_eeg_qc(record["input_artifact_id"], feature_config=features,
                            policy_config=policy, method_config=methods, **selection)
        if not np.array_equal(data, result["raw_data_volts"]):
            raise AssertionError("Baseline input changed between read and run")
        output = folder / "artifacts"
        export_eeg_qc(result, output, figures=figures, title=case["id"],
                      display_start_seconds=selection["start_seconds"],
                      display_duration_seconds=min(15, selection["duration_seconds"]))

        score = json.loads((output / "quality_score.json").read_text())
        required = ["review_report.md", "quality_score.json", "manifest.json", "channels.tsv"]
        if not all((output / f).is_file() for f in required):
            raise AssertionError("Required result artifacts missing")
        if not all(r.get("auto_points") is None for r in score["rows"]
                   if r.get("assessment_status") in {"unavailable", "unassessed", "not_assessed", "skipped"}):
            raise AssertionError("Unassessed row received a score")
        scored_rows = [r for r in score["rows"] if r.get("assessment_status") == "scored"]
        if sum(r["max_points"] for r in scored_rows) != score["assessed_max"]:
            raise AssertionError("Assessed score denominator inconsistent")
        if sum(r["auto_points"] for r in scored_rows) != score["auto_total"]:
            raise AssertionError("Score numerator inconsistent")
        m = result["method_results"]
        summary = {
            "case_id": case["id"], "status": "passed", "source_sha256": before,
            "reader_check": {"samples_per_channel": n_check, "max_absolute_error_volts": error},
            "shape": list(data.shape), "sampling_rate_hz": sfreq,
            "analysis_start_seconds": meta["recording_start_seconds"],
            "analysis_duration_seconds": data.shape[1]/sfreq,
            "comparison_groups": methods["comparison_groups"],
            "computed_backend_method_keys": list(m),
            "bad_channel_groups": m["bad_channels"]["groups"],
            "bad_channel_candidates": m["bad_channels"]["candidates"],
            "continuity_candidate_count": len(m["continuity"]["candidates"]),
            "line_noise_status": m["spectral"]["line_noise"]["status"],
            "line_flagged_observation_count": sum(bool(x["flagged"]) for x in m["spectral"]["line_noise"]["observations"]),
            "score_rows": [{k:r.get(k) for k in ("dimension_id", "assessment_status", "auto_points", "max_points", "score_reason")} for r in score["rows"]],
            "backend_score_100": score["score_100"],
            "assessed_weight": score["assessed_max"], "pending_weight": score["pending_max"],
            "review_status": result["manifest"]["review_status"],
            "raw_samples_retained": bool(np.all(result["keep_mask"])),
            "reports_present": required,
            "png_count": len(list(output.glob("*.png"))),
            "performance_validated": False,
            "scope": "Backend pilot and data-contract checks; not a new modular scheduler or clinical validation"
        }
        if case.get("inject_checks"):
            # Known faults are added only to copies, and never relabeled as real artifacts.
            test = data[:4, :int(min(30, data.shape[1]/sfreq)*sfreq)].copy()
            ids = [c["channel_id"] for c in inp["channels"][:4]]
            names = [c["raw_name"] for c in inp["channels"][:4]]
            clean_copy = test.copy()
            test[0, int(10*sfreq):int(12*sfreq)] = 0
            flat = compute_continuity_qc(test, sfreq, ids, names)
            flat_hit = [x for x in flat["candidates"] if x["channel_id"] == ids[0]
                        and x["kind"] == "near_zero_flatline"
                        and x["start_sample"] <= int(10*sfreq)
                        and x["stop_sample"] >= int(12*sfreq)]
            line_data = clean_copy.copy()
            line_data[0] += 100e-6*np.sin(2*np.pi*50*np.arange(line_data.shape[1])/sfreq)
            line = compute_spectral_qc(line_data, sfreq, ids, names)
            line_hits = [x for x in line["line_noise"]["observations"]
                         if x["channel_id"] == ids[0] and x["nominal_hz"] == 50 and x["flagged"]]
            injection = {"source_case": case["id"], "kind": "known_fault_injection_on_copy",
                         "flatline": {"channel_id":ids[0],"start_seconds":10,"stop_seconds":12,"detected":bool(flat_hit)},
                         "line_noise": {"channel_id":ids[0],"frequency_hz":50,"peak_amplitude_volts":100e-6,"flagged_windows":len(line_hits)},
                         "not_natural_artifact_accuracy": True}
            save(folder / "injection-checks.json", injection)
            summary["injection_checks"] = injection
            if not flat_hit or not line_hits:
                summary["status"] = "needs_review"
        if digest(source) != before:
            raise AssertionError("Source hash changed")
        summary["source_unchanged"] = True
        summary["elapsed_seconds"] = round(time.monotonic()-started, 3)
        save(folder / "summary.json", summary)
        return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--figures", action="store_true")
    args = p.parse_args()
    cases = json.loads(args.cases.read_text())
    out = args.output.resolve()
    repo = Path(__file__).resolve().parents[1]
    if out == repo or repo in out.parents or out.exists():
        p.error("Choose a new output directory outside the repository")
    for case in cases:
        src = Path(case["source_path"]).resolve()
        if src == out or out in src.parents or src.parent in out.parents:
            p.error("Output must be separate from source directory")
        if not case["id"] or Path(case["id"]).name != case["id"] or case["id"] in {".", ".."}:
            p.error("Invalid case identifier")
    out.mkdir(parents=True)
    save(out / "environment.json", {n:importlib.metadata.version(n) for n in ["brainelecqc","numpy","scipy","mne","fooof"]})
    summaries = []
    for case in cases:
        folder = out / case["id"]
        folder.mkdir()
        print("RUN", case["id"], flush=True)
        try:
            s = run(case, folder, args.figures)
        except Exception as exc:
            s = {"case_id":case["id"],"status":"failed","error":str(exc)}
            (folder / "error.txt").write_text(traceback.format_exc())
        summaries.append(s)
        save(out / "summary.json", summaries)
        print("RESULT", case["id"], s["status"], flush=True)
    if any(s["status"] != "passed" for s in summaries):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
