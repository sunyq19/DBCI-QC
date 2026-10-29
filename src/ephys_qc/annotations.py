"""Independent label ingestion; labels never enter signal detectors."""
import csv
import hashlib
import math
from pathlib import Path


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_annotations(annotation, start_seconds, duration_seconds, sampling_rate_hz,
                      recording_duration_seconds=None, start_sample=None):
    """Check declared TSVs, retaining global times and exposing unlabelled spans.

    Only selected overlaps receive EEG sample mappings. Point events use
    start <= onset < stop. Neither tasks nor sleep stages imply EEG quality.
    """
    if not isinstance(annotation, dict) or annotation.get("format") not in {"sleep_stages_tsv", "bids_events_tsv", "clinical_events_tsv"}:
        raise ValueError("Unsupported annotation format")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (start_seconds, duration_seconds, sampling_rate_hz)) or start_seconds < 0 or duration_seconds <= 0 or sampling_rate_hz <= 0:
        raise ValueError("Annotation interval and sample rate must be finite and valid")
    path = Path(annotation["path"])
    before = file_sha256(path)
    if annotation.get('expected_sha256') and before != annotation['expected_sha256']:
        raise ValueError('Annotation SHA-256 disagrees with the registered source')
    stop_seconds = start_seconds + duration_seconds
    origin_sample = round(start_seconds * sampling_rate_hz) if start_sample is None else start_sample
    kind = annotation["format"]
    issues, selected, valid_rows, stages = [], [], 0, {}
    last_onset = -math.inf
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        required = ({"onset_s", "duration_s", "stage"} if kind == "sleep_stages_tsv" else
                    {"onset_s", "duration_s", "label", "label_type"} if kind == "clinical_events_tsv" else
                    {"onset", "duration", "event_name"})
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Annotation table is missing required fields: " + ", ".join(sorted(required)))
        total_rows = 0
        for line, row in enumerate(reader, 2):
            total_rows += 1
            try:
                onset = float(row["onset"] if kind == "bids_events_tsv" else row["onset_s"])
                duration = float(row["duration"] if kind == "bids_events_tsv" else row["duration_s"])
                if not math.isfinite(onset) or not math.isfinite(duration) or onset < 0 or duration < 0:
                    raise ValueError("negative or nonfinite time")
                if kind == "sleep_stages_tsv" and duration <= 0:
                    raise ValueError("sleep stage must have a positive duration")
                if kind == "sleep_stages_tsv" and row.get("end_s") not in {None, ""}:
                    end = float(row["end_s"])
                    if not math.isfinite(end) or abs(end - onset - duration) > 1e-6:
                        raise ValueError("end_s disagrees with onset_s + duration_s")
            except (ValueError, TypeError):
                issues.append({"line": line, "reason": "无效时间字段，未映射此行"})
                continue
            if onset < last_onset:
                issues.append({"line": line, "reason": "标注未按原始时间排序"})
            last_onset = onset
            if recording_duration_seconds is not None and (onset > recording_duration_seconds or onset + duration > recording_duration_seconds + 1e-6):
                issues.append({"line": line, "reason": "标注超出登记的记录长度"})
            valid_rows += 1
            overlaps = start_seconds <= onset < stop_seconds if duration == 0 else onset < stop_seconds and onset + duration > start_seconds
            if not overlaps:
                continue
            left, right = max(start_seconds, onset), min(stop_seconds, onset + duration)
            if duration == 0:
                right = left
            label = row["stage"] if kind == "sleep_stages_tsv" else row["label"] if kind == "clinical_events_tsv" else row["event_name"]
            item = {"source_line": line, "onset_seconds": onset, "duration_seconds": duration,
                    "end_seconds": onset + duration, "label": label,
                    "selected_start_seconds": left, "selected_stop_seconds": right,
                    "start_sample": origin_sample + round((left - start_seconds) * sampling_rate_hz),
                    "stop_sample": origin_sample + round((right - start_seconds) * sampling_rate_hz),
                    "label_scope": annotation.get("label_scope", "unconfirmed_not_quality")}
            if kind == "bids_events_tsv":
                item["event_value"] = row.get("event_value")
            elif kind == "sleep_stages_tsv":
                item["label_type"] = row.get("label_type", "sleep_state")
                stages[label] = stages.get(label, 0.0) + right - left
            else:
                item['label_type'] = row['label_type']
            selected.append(item)
    merged = []
    if kind in {"sleep_stages_tsv", "clinical_events_tsv"}:
        for left, right in sorted((r["selected_start_seconds"], r["selected_stop_seconds"]) for r in selected):
            if kind == 'sleep_stages_tsv' and merged and left < merged[-1][1]:
                issues.append({"reason": "选区内存在重叠睡眠阶段，需人工复核"})
            if merged and left <= merged[-1][1]:
                merged[-1][1] = max(right, merged[-1][1])
            else:
                merged.append([left, right])
    uncovered, cursor = [], start_seconds
    for left, right in merged if kind == 'sleep_stages_tsv' else []:
        if left > cursor:
            uncovered.append({"start_seconds": cursor, "stop_seconds": left, "label": "unknown"})
        cursor = max(cursor, right)
    if kind == "sleep_stages_tsv" and cursor < stop_seconds:
        uncovered.append({"start_seconds": cursor, "stop_seconds": stop_seconds, "label": "unknown"})
    after = file_sha256(path)
    if before != after:
        raise ValueError("Annotation file changed during reading")
    sources = [{"name": path.name, "sha256": before, "role": "ingested_annotation"}]
    if annotation.get("source_path"):
        original = Path(annotation["source_path"])
        original_hash = file_sha256(original)
        if annotation.get('source_expected_sha256') and original_hash != annotation['source_expected_sha256']:
            raise ValueError('Original annotation source SHA-256 disagrees with registration')
        sources.append({"name": original.name, "sha256": original_hash, "role": "declared_original_label_source"})
    return {"schema_version": "ephys-annotations/1.1", "format": kind,
            "status": "partial" if issues or uncovered else "completed",
            "label_scope": annotation.get("label_scope", "unconfirmed_not_quality"),
            "sources": sources, "source_unchanged": True, "total_rows": total_rows,
            "valid_rows": valid_rows, "selected_count": len(selected), "events": selected,
            "stage_seconds": stages, "uncovered_intervals": uncovered,
            "input_range": {"start_seconds": start_seconds, "stop_seconds": stop_seconds,
                            "start_sample": origin_sample, "stop_sample": origin_sample + round(duration_seconds * sampling_rate_hz)},
            "covered_seconds": sum(b - a for a, b in merged) if kind == "sleep_stages_tsv" else None,
            'clinical_event_seconds': sum(b - a for a, b in merged) if kind == 'clinical_events_tsv' else None,
            'unlabelled_means_normal': False,
            "issues": issues, "used_for_signal_detection": False, "quality_ground_truth": False,
            "synchronization": "按提供方原始记录秒时间映射；未独立验证硬件同步准确性"}
