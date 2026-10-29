"""Explicitly selected MNE screening adapters; no automatic signal repair.

Catalog and eligibility checks use only the standard library. Scientific
dependencies are imported only when an eligible extension actually runs.
"""
import copy
import hashlib
import inspect
import math
from pathlib import Path
import warnings


_SPECS = [
    {"id": "mne_amplitude", "name": "MNE 相邻采样变化 / 平线", "module_id": "M03", "category": "optional",
     "description": "按相邻采样点差分定位平线/变化候选，分别保留时间标注与通道建议；默认未启用peak阈值。",
     "inputs": ["已标定为V的EEG", "原生采样率", "明确阈值及最短持续时间"],
     "outputs": ["跨通道合并时间候选", "通道级候选（可能没有具体时段）"],
     "requirements": ["电压单位核实并标定为V", "保留原生采样的EEG", "明确平线/变化阈值及最短持续时间"],
     "source": {"name": "MNE-Python annotate_amplitude", "url": "https://mne.tools/stable/generated/mne.preprocessing.annotate_amplitude.html", "license": "BSD-3-Clause"},
     "implementation": "available", "status": "available",
     "defaults": {"peak_volts": None, "flat_volts": 0.0, "min_duration_seconds": 0.1, "bad_percent": 5.0},
     "limitations": ["检查相邻样本差分，不是固定窗峰峰值或通用大振幅/漂移检测。",
                     "flat=0、最短0.1秒为项目研究参数；软件默认值也不代表公认好坏界线。",
                     "默认peak=None，未启用突变阈值；启用时必须明确以V填写。",
                     "MNE可能只返回通道建议而无时间标注；时间标注不提供单道定位。",
                     "阈值依赖采样率、量化精度和处理史；结果不自动排除通道或样本。"]},
    {"id": "mne_muscle", "name": "MNE 跨通道高频线索", "module_id": "M06", "category": "optional",
     "description": "用MNE默认110–140 Hz频带和跨选中EEG通道包络分数，产生探索性时间候选。",
     "inputs": ["已标定为V的EEG", "足够原生采样率", "采集/预处理滤波史"],
     "outputs": ["跨通道时间候选", "逐采样聚合z分数及有效性检查"],
     "requirements": ["电压单位核实并标定为V", "原生采样率高于280 Hz", "本版至少10秒分析窗口", "采集和滤波史需支持110–140 Hz"],
     "source": {"name": "MNE-Python annotate_muscle_zscore", "url": "https://mne.tools/stable/generated/mne.preprocessing.annotate_muscle_zscore.html", "license": "BSD-3-Clause"},
     "implementation": "available", "status": "available",
     "defaults": {"threshold_z": 4.0, "filter_freq_hz": [110.0, 140.0], "min_length_good_seconds": 0.1},
     "limitations": ["首版固定110–140 Hz；160/256 Hz输入不适用，不降低频带伪装同一方法。",
                     "这是选中EEG通道的聚合时间分数，不提供单通道定位；选道会影响结果。",
                     "120 Hz工频谐波等也可能贡献高频能量；无同步EMG确认，不能诊断肌电。",
                     "未知滤波史时仅作探索性输出；不执行自动剔除、ICA或修复。",
                     "阈值4与间隔合并0.1秒是MNE默认值，不是国际共识阈值。"]},
]


def extension_specs():
    from .extra_methods import extension_specs as additional_specs
    return copy.deepcopy(_SPECS) + additional_specs()


def _spec(extension_id):
    for spec in _SPECS:
        if spec["id"] == extension_id:
            return copy.deepcopy(spec)
    raise ValueError(f"Unknown extension: {extension_id}")


def _number(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite JSON number")
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")
    return float(value)


def _parameters(extension_id, params):
    defaults = _spec(extension_id)["defaults"]
    if params is not None and (not isinstance(params, dict) or set(params) - set(defaults)):
        raise ValueError("Extension parameters must be an object with only declared parameter names")
    values = {**defaults, **copy.deepcopy(params or {})}
    if extension_id == "mne_amplitude":
        for name in ("peak_volts", "flat_volts"):
            if values[name] is not None:
                values[name] = _number(values[name], name, zero=name == "flat_volts")
        if values["peak_volts"] is None and values["flat_volts"] is None:
            raise ValueError("At least one explicit peak_volts or flat_volts threshold is required")
        if values["peak_volts"] is not None and values["flat_volts"] is not None and values["peak_volts"] <= values["flat_volts"]:
            raise ValueError("peak_volts must exceed flat_volts when both are enabled")
        values["min_duration_seconds"] = _number(values["min_duration_seconds"], "min_duration_seconds")
        values["bad_percent"] = _number(values["bad_percent"], "bad_percent")
        if values["bad_percent"] > 100:
            raise ValueError("bad_percent must be greater than zero and at most 100")
    else:
        values["threshold_z"] = _number(values["threshold_z"], "threshold_z")
        values["min_length_good_seconds"] = _number(values["min_length_good_seconds"], "min_length_good_seconds", zero=True)
        band = values["filter_freq_hz"]
        if not isinstance(band, list) or len(band) != 2:
            raise ValueError("filter_freq_hz must be a two-element JSON array")
        band = [_number(v, "filter_freq_hz") for v in band]
        if band != [110.0, 140.0]:
            raise ValueError("This adapter fixes the MNE 110–140 Hz band; alternative bands need a separately reviewed method")
        values["filter_freq_hz"] = band
    return values


def evaluate_extension(extension_id, facts, params=None):
    if extension_id not in {spec['id'] for spec in _SPECS}:
        from .extra_methods import evaluate_extension as evaluate_extra
        return evaluate_extra(extension_id, facts, params)
    parameters = _parameters(extension_id, params)
    verdict = {"status": "blocked", "reason": "", "parameters": parameters}
    if not isinstance(facts, dict) or facts.get("verified_voltage") is not True:
        return {**verdict, "reason": "电压单位尚未核实为V"}
    try:
        fs = _number(facts.get("sampling_rate_hz"), "sampling_rate_hz")
        duration = _number(facts.get("window_seconds"), "window_seconds")
        count = facts.get("n_eeg")
        if type(count) is not int or count < 1:
            raise ValueError("n_eeg must be a positive integer")
        if round(duration * fs) < 2:
            raise ValueError("At least two native samples are required")
    except ValueError as error:
        return {**verdict, "reason": str(error)}
    if duration > 120:
        return {**verdict, "reason": "首版可选方法单次窗口最多120秒"}
    if extension_id == "mne_amplitude":
        minimum = parameters["min_duration_seconds"]
        if minimum > duration or round(minimum * fs) < 1:
            return {**verdict, "reason": "最短持续时间须落在当前窗口内且至少对应一个差分采样间隔"}
        return {**verdict, "status": "ready", "reason": "可运行相邻差分检查；阈值仅是研究参数，默认peak未启用" if parameters["peak_volts"] is None else "可按明确给定的V阈值运行；不是公认质量分界"}
    low, high = parameters["filter_freq_hz"]
    if fs / 2 <= high:
        return {**verdict, "reason": f"奈奎斯特频率{fs/2:g} Hz不足以支持固定110–140 Hz频带"}
    if duration < 10:
        return {**verdict, "reason": "项目首版要求至少10秒以估计包络分布；这是项目门槛"}
    if parameters["min_length_good_seconds"] >= duration:
        return {**verdict, "reason": "间隔合并长度必须短于分析窗口"}
    hp, lp = facts.get("preprocessing_highpass_hz"), facts.get("preprocessing_lowpass_hz")
    try:
        if hp is not None:
            hp = _number(hp, "preprocessing_highpass_hz", zero=True)
        if lp is not None:
            lp = _number(lp, "preprocessing_lowpass_hz")
    except ValueError as error:
        return {**verdict, "reason": "滤波史数值无效：" + str(error)}
    if (hp is not None and hp >= low) or (lp is not None and lp <= high):
        return {**verdict, "reason": "已知上游滤波限制了110–140 Hz目标频带，不能据此评估该方法"}
    if hp is None or lp is None:
        return {**verdict, "status": "partial", "reason": "采集/预处理滤波史未完整确认；可探索性运行，但不是已确认肌电，需排查120 Hz谐波等干扰"}
    return {**verdict, "status": "ready", "reason": "已声明频带可用；输出仍为跨通道高频线索，无EMG确认，不提供单道定位"}


def _data_hash(data):
    import numpy as np
    canonical = np.asarray(data, dtype="<f8", order="C")
    return hashlib.sha256(memoryview(canonical).cast("B")).hexdigest()


def _source(extension_id, mne):
    source = _spec(extension_id)["source"]
    name = "annotate_amplitude" if extension_id == "mne_amplitude" else "annotate_muscle_zscore"
    function = getattr(mne.preprocessing, name)
    location = inspect.getsourcefile(inspect.unwrap(function))
    if not location or not Path(location).is_file():
        # MNE's generated verbose wrapper can report <decorator-gen-N>.
        module = inspect.getmodule(function)
        location = getattr(module, "__file__", None)
    source.update(version=mne.__version__, function="mne.preprocessing." + name,
                  implementation_sha256=hashlib.sha256(Path(location).read_bytes()).hexdigest() if location and Path(location).is_file() else None)
    return source


def run_extension(extension_id, data_volts, sfreq, channel_names, start_seconds, parameters, *, facts=None):
    if extension_id not in {spec['id'] for spec in _SPECS}:
        from .extra_methods import run_extension as run_extra
        return run_extra(extension_id, data_volts, sfreq, channel_names, start_seconds, parameters, facts=facts)
    import numpy as np
    config = _parameters(extension_id, parameters)
    fs, start = _number(sfreq, "sfreq"), _number(start_seconds, "start_seconds", zero=True)
    original = np.asarray(data_volts)
    if original.ndim != 2 or min(original.shape) < 1 or original.dtype.kind not in "fiu" or not np.all(np.isfinite(original)):
        raise ValueError("data_volts must be a finite real channel-by-sample array")
    names = list(channel_names) if not isinstance(channel_names, (str, bytes)) else []
    if len(names) != len(original) or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("channel_names must be distinct nonempty names matching the selected EEG rows")
    data = np.asarray(original, dtype=float, order="C")
    duration = data.shape[1] / fs
    if not math.isfinite(start + duration):
        raise ValueError("Original recording stop time must be finite")
    digest = _data_hash(data)
    preflight = evaluate_extension(extension_id, {"sampling_rate_hz": fs, "n_eeg": len(data),
                    "window_seconds": duration, "verified_voltage": True}, config)
    result = {"schema_version": "ephys-extension-result/1.0", "extension_id": extension_id,
              "status": preflight["status"], "reason": preflight["reason"], "parameters": config,
              "source": _spec(extension_id)["source"], "data_sha256": digest,
              "range": {"start_seconds": start, "stop_seconds": start + duration,
                        "duration_seconds": duration, "sampling_rate_hz": fs, "n_samples": data.shape[1]},
              "channel_names": names, "unit": "V", "candidates": [], "notes": [],
              "automatic_actions": [], "input_unchanged": True, "review_status": "pending"}
    if preflight["status"] == "blocked":
        return result
    if extension_id == "mne_muscle" and np.any(np.ptp(data, axis=1) == 0):
        return {**result, "status": "blocked", "reason": "存在全段恒值通道，聚合z分数不可可靠估计；未自动移除该通道",
                "constant_channel_names": [names[i] for i in np.flatnonzero(np.ptp(data, axis=1) == 0)]}
    import mne
    result["source"] = _source(extension_id, mne)
    # An owned copy and first_samp=0 prevent source mutation and double offsets.
    raw = mne.io.RawArray(data.copy(), mne.create_info(names, fs, "eeg"), first_samp=0, copy="both", verbose="ERROR")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if extension_id == "mne_amplitude":
            annotation, bads = mne.preprocessing.annotate_amplitude(
                raw, peak=config["peak_volts"], flat=config["flat_volts"],
                bad_percent=config["bad_percent"], min_duration=config["min_duration_seconds"],
                picks="eeg", verbose="ERROR")
            bad_set = set(bads)
            result["bad_channels"] = [n for n in names if n in bad_set]
            result["status"] = "completed"
            result["reason"] = "相邻差分候选计算完成；未自动应用标注或移除通道"
            result["notes"] += ["相邻样本差分，不是固定窗峰峰值；通道候选的精确异常区间未由MNE返回。",
                                "初始默认flat=0和最短0.1秒为项目研究参数；5%是软件默认分流阈值，不代表通道临床不可用；实际值见parameters。",
                                "默认peak=None时仅检查平线；0个时间标注不代表没有通道候选。" if config["peak_volts"] is None else "peak已按给定V阈值启用；不得把候选直接当作最终坏道。"]
        else:
            annotation, scores = mne.preprocessing.annotate_muscle_zscore(
                raw, threshold=config["threshold_z"], ch_type="eeg",
                min_length_good=config["min_length_good_seconds"], filter_freq=tuple(config["filter_freq_hz"]),
                n_jobs=1, verbose="ERROR")
            finite = np.isfinite(scores)
            result["scores_z"] = [float(v) if math.isfinite(float(v)) else None for v in scores]
            result["score_summary"] = {"n_samples": len(scores), "finite_count": int(finite.sum()),
                "nonfinite_count": int((~finite).sum()), "min": float(scores[finite].min()) if finite.any() else None,
                "max": float(scores[finite].max()) if finite.any() else None,
                "constant_score": bool(np.ptp(scores[finite]) == 0) if finite.any() else None}
            usable = len(scores) == data.shape[1] and finite.any() and np.ptp(scores[finite]) > 0
            result["status"] = "partial" if usable else "failed"
            result["reason"] = "探索性跨通道高频线索；采集滤波史须结合计划复核，无同步EMG确认" if usable else "聚合分数非有限或全常数，不能把空候选解释为无伪迹"
            result["notes"] += ["110–140 Hz聚合分数与当前选道有关；MNE不返回单道定位。",
                                "120 Hz工频谐波等也可能触发；无同步EMG确认，不能将BAD_muscle名称当作诊断。",
                                "仅在MNE拥有的副本上滤波和Hilbert变换，没有覆盖原始电压。",
                                "threshold=4和min_length_good=.1是软件默认值，非国际共识；滤波史需结合执行计划。"]
            if not usable:
                annotation = mne.Annotations([], [], [])
    for onset, length, description in zip(annotation.onset, annotation.duration, annotation.description):
        left, right = max(0.0, float(onset)), min(duration, float(onset + length))
        if right <= left:
            continue
        result["candidates"].append({"kind": str(description), "localization": "interval_only",
            "scope": "across_selected_eeg_channels", "start_seconds": start + left, "stop_seconds": start + right,
            "duration_seconds": right - left, "channel_index": None, "channel_name": None,
            "action": "review", "review_status": "pending"})
    result["candidate_interval_count"] = len(result["candidates"])
    if extension_id == "mne_amplitude":
        for name in result["bad_channels"]:
            result["candidates"].append({"kind": "amplitude_channel_candidate", "localization": "channel_only",
                "scope": "channel", "channel_index": names.index(name), "channel_name": name,
                "start_seconds": None, "stop_seconds": None, "duration_seconds": None,
                "analysis_range": [start, start + duration], "action": "review", "review_status": "pending",
                "reason": "MNE按异常占比返回通道建议，未返回该通道精确候选时间"})
    result["candidate_channel_count"] = len(result.get("bad_channels", []))
    result["notes"] += sorted({str(w.message) for w in caught})
    result["input_unchanged"] = _data_hash(original) == digest
    if not result["input_unchanged"]:
        raise RuntimeError("Extension unexpectedly mutated the caller's input")
    return result
