"""Prepare three additional real EDF examples; never edits workbench config.

S002R01 may be reused from the original public bundle. S002R04 and the SC4011
PSG/hypnogram are downloaded unchanged from fixed official PhysioNet versions.
Run validate_recommended_examples.py separately for actual signal processing.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import urllib.request


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_tsv(path, fields, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--evidence-dir", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--existing-s002r01", type=Path, help="Reuse and verify an original public S002R01.edf without copying")
    args = parser.parse_args()
    data, evidence, repo = [p.expanduser().resolve() for p in (args.data_root, args.evidence_dir, args.repo_root)]
    data.mkdir(parents=True, exist_ok=True)
    evidence.mkdir(parents=True, exist_ok=True)
    manifest, checks, downloaded = [], [], 0
    maximum = 150 * 1024 * 1024

    def get(url, path, role, expected=None):
        nonlocal downloaded
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            operation = "reused_existing"
        else:
            temporary = path.with_name(path.name + ".partial")
            request = urllib.request.Request(url, headers={"User-Agent": "EEG-QC-public-example-preparation/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response, temporary.open("wb") as output:
                length = response.headers.get("Content-Length")
                if length and downloaded + int(length) > maximum:
                    raise ValueError("Additional download budget exceeds 150 MiB")
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    downloaded += len(block)
                    if downloaded > maximum:
                        raise ValueError("Additional download budget exceeds 150 MiB")
                    output.write(block)
            if expected and digest(temporary) != expected:
                raise ValueError("Official SHA256 mismatch for " + path.name)
            temporary.rename(path)
            operation = "downloaded"
        actual = digest(path)
        if expected and actual != expected:
            raise ValueError("Existing file does not match official SHA256: " + str(path))
        row = {"url": url, "path": str(path), "role": role, "operation": operation,
               "bytes": path.stat().st_size, "sha256": actual, "official_hash_verified": bool(expected)}
        manifest.append(row)
        if expected:
            checks.append({**row, "official_expected_sha256": expected})
        print(operation, path.name, path.stat().st_size, flush=True)
        return path

    tables, directories = {}, {}
    for slug, directory in (("eegmmidb", "eegmmidb-1.0.0-s002"), ("sleep-edfx", "sleep-edfx-1.0.0-sc4011")):
        folder = data / directory
        directories[slug] = folder
        base = "https://physionet.org/"
        get(f"{base}content/{slug}/1.0.0/", folder / "_provenance/official_dataset_page.html", "official_description")
        get(f"{base}content/{slug}/view-license/1.0.0/", folder / "_provenance/license-ODC-By-1.0.html", "official_license")
        checksum_path = get(f"{base}files/{slug}/1.0.0/SHA256SUMS.txt", folder / "_provenance/official_SHA256SUMS.txt", "official_checksum")
        tables[slug] = {row.split(maxsplit=1)[1].lstrip("*"): row.split()[0]
                        for row in checksum_path.read_text().splitlines() if row.strip()}
    get("https://archive.physionet.org/physiobank/database/eegmmidb/",
        directories["eegmmidb"] / "_provenance/official_run_protocol.html", "official_run_protocol")

    def original(slug, relative, existing=None):
        url = f"https://physionet.org/files/{slug}/1.0.0/{relative}"
        path = existing.expanduser().resolve() if existing else directories[slug] / Path(relative).name
        if existing and not path.is_file():
            raise ValueError("--existing-s002r01 must name an existing file")
        return get(url, path, "original_waveform" if relative.endswith("PSG.edf") or "S002" in relative else "original_annotation", tables[slug][relative])

    r01 = original("eegmmidb", "S002/S002R01.edf", args.existing_s002r01)
    r04 = original("eegmmidb", "S002/S002R04.edf")
    psg = original("sleep-edfx", "sleep-cassette/SC4011E0-PSG.edf")
    hypnogram = original("sleep-edfx", "sleep-cassette/SC4011EH-Hypnogram.edf")
    spec = importlib.util.spec_from_file_location("public_input_config", repo / "apps/workbench/input_config.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    metadata = {str(p): module.edf_metadata(p) for p in (r01, r04, psg)}
    dump(evidence / "technical_inspection.json", [{"path": str(p), "sha256": digest(p), "metadata": metadata[str(p)]} for p in (r01, r04, psg)])

    import mne
    task_annotations = mne.read_annotations(r04)
    event_mapping = {"T0": "rest", "T1": "left_fist_motor_imagery", "T2": "right_fist_motor_imagery"}
    task_rows = [{"onset": float(o), "duration": float(d), "event_name": event_mapping[str(label)], "event_value": str(label)}
                 for o, d, label in zip(task_annotations.onset, task_annotations.duration, task_annotations.description)]
    task_tsv = directories["eegmmidb"] / "S002R04_task_events.derived.tsv"
    write_tsv(task_tsv, ["onset", "duration", "event_name", "event_value"], task_rows)
    task_derivation = {"source_path": str(r04), "source_sha256": digest(r04), "derived_path": str(task_tsv),
                       "derived_sha256": digest(task_tsv), "source_rows": len(task_rows), "mapping": event_mapping,
                       "mapping_source": "https://archive.physionet.org/physiobank/database/eegmmidb/",
                       "method": "MNE read_annotations, preserve original onset/duration; run 04 is motor imagery, not physical execution",
                       "quality_ground_truth": False, "used_for_signal_detection": False}
    dump(directories["eegmmidb"] / "S002R04_annotation_derivation.json", task_derivation)

    # Check only synchronization fields; never copy the EDF subject header into evidence.
    with psg.open("rb") as stream:
        clock_psg = stream.read(256)[168:184]
    with hypnogram.open("rb") as stream:
        clock_labels = stream.read(256)[168:184]
    if clock_psg != clock_labels:
        raise ValueError("PSG and hypnogram start clocks differ; no silent offset correction")
    sleep_annotations = mne.read_annotations(hypnogram)
    raw_rows = [{"onset_s": float(o), "duration_s": float(d), "source_label": str(label)}
                for o, d, label in zip(sleep_annotations.onset, sleep_annotations.duration, sleep_annotations.description)]
    stage_mapping = {"Sleep stage W": "W", "Sleep stage R": "REM", "Sleep stage 1": "R&K 1", "Sleep stage 2": "R&K 2",
                     "Sleep stage 3": "R&K 3", "Sleep stage 4": "R&K 4", "Movement time": "Movement", "Sleep stage ?": "Unknown"}
    sleep_rows, excluded = [], []
    length = metadata[str(psg)]["duration_seconds"]
    for number, row in enumerate(raw_rows, 1):
        left, right = max(0, row["onset_s"]), min(length, row["onset_s"] + row["duration_s"])
        if right <= left:
            excluded.append({**row, "source_annotation": number, "reason": "outside_recorded_waveform"})
            continue
        sleep_rows.append({"onset_s": left, "duration_s": right - left, "end_s": right,
                           "stage": stage_mapping[row["source_label"]], "label_type": "sleep_state_RK1968",
                           "source_label": row["source_label"], "source_annotation": number})
    # Pick the first fully annotated REM interval with >=120s, not a signal-quality-selected window.
    candidates = [row for row in sleep_rows if row["stage"] == "REM" and row["duration_s"] >= 120]
    if not candidates:
        raise ValueError("No 120s REM interval; inspect annotations rather than silently changing the example")
    start = candidates[0]["onset_s"]
    sleep_tsv = directories["sleep-edfx"] / "SC4011_state_intervals.derived.tsv"
    write_tsv(sleep_tsv, ["onset_s", "duration_s", "end_s", "stage", "label_type", "source_label", "source_annotation"], sleep_rows)
    dump(directories["sleep-edfx"] / "SC4011_annotations.original_extracted.json", raw_rows)
    dump(directories["sleep-edfx"] / "SC4011_annotation_derivation.json", {
        "source_path": str(hypnogram), "source_sha256": digest(hypnogram), "derived_path": str(sleep_tsv),
        "derived_sha256": digest(sleep_tsv), "raw_rows": len(raw_rows), "derived_rows": len(sleep_rows),
        "excluded_rows": excluded, "psg_and_hypnogram_start_clock_match": True,
        "waveform_duration_seconds": length, "default_window_rule": "first source-labelled REM interval lasting at least 120 seconds",
        "default_start_seconds": start, "method": "MNE read_annotations; clip to waveform; retain R&K 3 and 4 separately",
        "quality_ground_truth": False, "used_for_signal_detection": False})

    def annotation(path, source, format_, scope):
        return {"path": str(path), "source_path": str(source), "format": format_, "label_scope": scope,
                "expected_sha256": digest(path), "source_expected_sha256": digest(source)}

    def record(path, identifier, label, profile, dataset, indices, refs, onset, duration, task, reference, description):
        return {"id": identifier, "label": label, "profile_id": profile, "dataset_id": dataset, "description": description,
                "source_path": str(path), "expected_sha256": digest(path), "metadata": metadata[str(path)],
                "modality": "scalp_eeg", "modality_source": "公开数据集说明确认头皮EEG；不从扩展名推断。",
                "reference_scheme": reference, "verified_electrode_coordinates": False, "verified_epochs": False,
                "preprocessing": {"verified": False, "note": "采集及软件处理史未完整核实；不从采样率推断实际保留频带。"},
                "default_config": {"selection": {"eeg_indices": indices, "reference_indices": refs, "start_seconds": onset, "duration_seconds": duration},
                                   "method_config": {"comparison_groups": None},
                                   "context_tags": {"disease": "unknown", "age_group": "unknown", "task": task}},
                "scientific_limits": {"quality_labels": "not_available", "coordinates": "not_provided_or_inferred",
                                      "raw_modified": False, "automated_cleaning": False}}

    a = record(r01, "eegmmidb-s002r01", "EEGMMIDB · S002 睁眼静息", "adult_multichannel_rest", "eegmmidb-1.0.0",
               list(range(64)), {}, 0, min(120, metadata[str(r01)]["duration_seconds"]), "rest", "unknown",
               "另一参与者S002的64道160 Hz睁眼基线；复用或下载原始记录，年龄、疾病和具体参考未核实。")
    b = record(r04, "eegmmidb-s002r04", "EEGMMIDB · S002 左右握拳想象", "multichannel_motor_imagery", "eegmmidb-1.0.0",
               list(range(64)), {}, 0, 120, "motor_imagery", "unknown",
               "同一S002参与者的左右握拳想象，非真实动作；与S002R01为不同记录，不能当两名独立参与者。")
    b["annotation"] = annotation(task_tsv, r04, "bids_events_tsv", "task_events_not_quality")
    for row in (a, b):
        row["provenance"] = {"name": "PhysioNet EEG Motor Movement/Imagery Dataset", "url": "https://physionet.org/content/eegmmidb/1.0.0/",
                             "version": "1.0.0", "license": "Open Data Commons Attribution License v1.0 (ODC-By-1.0)"}
        row["reference_evidence"] = "官方资料和技术头未核实具体采集参考；不因同一文件含64道而声明共同参考组。"
        row["context_evidence"] = {"task": "官方运行列表：01为睁眼基线，04为左右握拳想象。年龄及疾病保持unknown。", "url": "https://archive.physionet.org/physiobank/database/eegmmidb/"}
        row["selection_evidence"] = {"rule": "官方说明64条EEG；技术头核验源索引0–63均160 Hz电压信号，注释通道不作EEG。", "eeg_source_indices": list(range(64))}
    a["data_usage"] = {"typical_use": "不同参与者的睁眼基线，检查固定配置是否仍可解释。", "annotations": "官方运行01睁眼条件；无人工质量标签。", "annotation_limits": "实验条件不是伪迹真值；无辅助导联、参考及处理史保持未知。"}
    b["data_usage"] = {"typical_use": "第二位参与者握拳想象任务，检查事件时间轴与质控描述。", "annotations": f"原始EDF+的{len(task_rows)}个T0/T1/T2区间，按运行04解码为休息/左握拳想象/右握拳想象。", "annotation_limits": "任务区间不等于运动伪迹；S002的两次运行不能计作两名独立参与者。"}
    c = record(psg, "sleep-edfx-sc4011", "Sleep-EDF · SC4011 REM睡眠", "sparse_bipolar_sleep", "sleep-edfx-1.0.0",
               [0, 1], {"eog": 2}, start, 120, "sleep", "bipolar",
               f"另一参与者SC4011，2条100 Hz双极EEG及同钟EOG；默认{start:g}–{start+120:g}秒为来源标注REM。")
    c["default_config"]["context_tags"]["disease"] = "healthy_control"
    c["annotation"] = annotation(sleep_tsv, hypnogram, "sleep_stages_tsv", "sleep_state_not_quality")
    c["provenance"] = {"name": "PhysioNet Sleep-EDF Database Expanded", "url": "https://physionet.org/content/sleep-edfx/1.0.0/",
                         "version": "1.0.0", "license": "Open Data Commons Attribution License v1.0 (ODC-By-1.0)"}
    c["context_evidence"] = {"disease": "官方SC队列为健康参与者睡眠研究；研究招募背景，不是本平台诊断。", "age_group": "本次不从队列年龄范围推断个体年龄，保留unknown。", "task": "官方SC睡眠记录，REM来自配套人工R&K分期。", "url": c["provenance"]["url"]}
    c["reference_evidence"] = "官方说明和EDF标签明确Fpz-Cz、Pz-Oz双极构型；不建立共同参考比较组。"
    c["selection_evidence"] = {"eeg_source_indices": [0, 1], "eog_source_index": 2,
                                 "rule": "仅选同为100 Hz的EEG与EOG；1 Hz EMG包络、呼吸、温度及marker不冒充原始同钟辅助导联。"}
    c["data_usage"] = {"typical_use": "另一参与者REM睡眠，补充已有清醒到浅睡转变例子。", "annotations": f"人工R&K分期；默认{start:g}–{start+120:g}秒为REM 120秒。", "annotation_limits": "REM不是伪迹标签；1 Hz整流EMG包络不用于原始EMG支持；不宣称整夜质控。"}
    records = [a, b, c]
    for row in records:
        selected = row["default_config"]["selection"]
        by_index = {channel["index"]: channel for channel in row["metadata"]["channels"]}
        indices = selected["eeg_indices"] + list(selected["reference_indices"].values())
        assert len({by_index[i]["sampling_rate_hz"] for i in indices}) == 1
        assert selected["start_seconds"] + selected["duration_seconds"] <= row["metadata"]["duration_seconds"]
    dump(evidence / "registration_additions.json", {"inputs": records, "profiles": [{"id": "multichannel_motor_imagery", "name": "多通道运动想象 EEG", "description": "明确来自运行04的左右握拳想象事件；不把想象提示当真实运动或伪迹标签。"}]})
    dump(evidence / "download_manifest.json", manifest)
    dump(evidence / "official_hash_verification.json", checks)
    summary = {"records": 3, "additional_participants": 2, "participant_caution": "S002R01/R04 are one participant, not two",
               "newly_downloaded_bytes_this_run": downloaded, "official_hash_checks": len(checks),
               "reused_waveform_records": sum(x["operation"] == "reused_existing" and x["role"] == "original_waveform" for x in checks),
               "derived_annotation_tables": 2, "original_files_modified": False,
               "runtime_jobs_created_by_preparation": 0, "registration_manifest": str(evidence / "registration_additions.json")}
    dump(evidence / "collection_summary.json", summary)
    for folder in directories.values():
        relevant = [row for row in manifest if folder in Path(row["path"]).parents]
        dump(folder / "_provenance/download_manifest.json", relevant)
        local = [{"path": str(p.relative_to(folder)), "bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(folder.rglob("*"))
                 if p.is_file() and p.name not in {"local_manifest.json", "SHA256SUMS.local.txt"}]
        dump(folder / "_provenance/local_manifest.json", local)
        (folder / "_provenance/SHA256SUMS.local.txt").write_text("".join(f"{r['sha256']}  {r['path']}\n" for r in local), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
