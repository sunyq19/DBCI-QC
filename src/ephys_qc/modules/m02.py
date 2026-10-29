"""M02: Native-clock window selection and calibrated voltage loading."""
import hashlib

from .context import ModuleContext


def read_window(state, config):
    selection = config["selection"]
    wanted = selection["eeg_indices"] + list(selection["reference_indices"].values())
    streams = [s for s in state["description"]["streams"]
               if set(wanted).issubset({c["source_index"] for c in s["channels"]})
               and (not selection.get("stream_id") or s["stream_id"] == selection["stream_id"])]
    if len(streams) != 1:
        raise ValueError("Selected channels must belong to one native sampling stream")
    stream = streams[0]
    fs = stream["sampling_frequency_hz"]
    start, length = selection["start_seconds"], selection["duration_seconds"]
    segments = [s for s in stream["segments"]
                if s["recording_start_seconds"] <= start and
                start + length <= s["recording_start_seconds"] + (s["stop_sample"] - s["start_sample"]) / fs + 1e-9
                and (not selection.get("segment_id") or s["segment_id"] == selection["segment_id"])]
    if len(segments) != 1:
        raise ValueError("Selected interval must stay inside one continuous source segment")
    segment = segments[0]
    first = segment["start_sample"] + round((start - segment["recording_start_seconds"]) * fs)
    stop = first + round(length * fs)
    by_index = {c["source_index"]: c for c in stream["channels"]}
    selected = [by_index[i] for i in selection["eeg_indices"]]
    references = {k: by_index[i] for k, i in selection["reference_indices"].items()}
    ordered = selected + list(references.values())
    if any(c.get("unit") != "V" for c in ordered):
        raise ValueError("Every selected EEG/auxiliary channel must have a verified voltage calibration")
    # This public reader uses original indices and calibration. No full-file import
    # or teacher pipeline is called, and no annotation/status affects the samples.
    values = state["reader"].read_window(stream["stream_id"], segment["segment_id"],
                                        [c["channel_id"] for c in ordered], first, stop, "physical")
    import numpy as np
    state['data_sha256'] = hashlib.sha256(np.ascontiguousarray(values, dtype='<f8').tobytes()).hexdigest()
    state.update(data=values[:len(selected)], channels=selected,
                 references={k: values[len(selected) + i] for i, k in enumerate(references)},
                 reference_channels={k: {"channel_id": c["channel_id"], "raw_name": c["raw_name"],
                                         "source_index": c["source_index"]} for k, c in references.items()},
                 fs=fs, first=first,
                 start=segment["recording_start_seconds"] + (first - segment["start_sample"]) / fs)
    state["recording"] = {"channel_count": len(selected), "sampling_rate_hz": fs,
                          "start_seconds": state["start"], "duration_seconds": (stop - first) / fs,
                          "start_sample": first, "stop_sample": stop, "unit": "V",
                          "channel_names": [c["raw_name"] for c in selected],
                          "source_indices": [c["source_index"] for c in selected]}
    return {"selection": selection, "recording": state["recording"],
            "channels": selected, "reference_channels": state["reference_channels"],
            "comparison_groups": config["method_config"].get("comparison_groups"),
            'data_sha256': state['data_sha256'], 'data_hash_encoding': 'ordered EEG then auxiliary, little-endian float64, channel-major SI values',
            "processing_applied": [], "quality_labels_used_for_detection": False}


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    config = context.config
    result = context.result
    row = context.row
    state = context.state
    save = context.save
    payload = read_window(state, config)
    payload['data_tags'] = result['data_tags']
    payload['method_applicability'] = result['method_applicability']
    result["recording"] = state["recording"]
    result['data_sha256'] = state['data_sha256']
    save("M02_selection.json", payload)
    row["summary"] = {**state["recording"], "auxiliary_roles": list(state["references"]),
                      "raw_signal_mutation": False, "quality_labels_used_for_detection": False}

    return row
