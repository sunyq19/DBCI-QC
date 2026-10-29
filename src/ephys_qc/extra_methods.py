"""Optional, read-only adapters around published MNE and autoreject methods.

Catalog and eligibility checks are standard-library only. These methods return
screening evidence or a fitted threshold; they never repair or remove signals.
"""
import copy
import hashlib
import inspect
import math
from pathlib import Path
import warnings


_SPECS = [
    {"id": "mne_bridge", "name": "MNE 电极桥接候选", "module_id": "M05", "category": "optional",
     "description": "用成对电压差的方差和MNE分布拟合识别桥接候选；不等于已确认短接。",
     "inputs": ["已标定为V的同参考EEG", "参考构型和比较组", "连续原生采样片段"],
     "outputs": ["通道对候选", "固定时间段的电气距离（μV²）"],
     "requirements": ["共同或连接耳参考且仅一个完整比较组", "本版至少8道及10秒", "采样率支持0.5–30 Hz方法滤波"],
     "source": {"name": "MNE-Python compute_bridged_electrodes", "url": "https://mne.tools/stable/generated/mne.preprocessing.compute_bridged_electrodes.html", "license": "BSD-3-Clause"},
     "implementation": "available", "status": "available",
     "defaults": {"lm_cutoff_uv2": 16.0, "epoch_threshold": 0.5, "l_freq_hz": 0.5, "h_freq_hz": 30.0, "epoch_duration_seconds": 2.0},
     "limitations": ["默认参数来自MNE实现，不是公认质量界线；至少8道/10秒是本项目的保守门槛。",
                     "lm_cutoff是分布拟合范围上限，不是最终桥接阈值；MNE未返回拟合的局部极小值。",
                     "双极、混合或未知参考阻断；当前适配不自动拆组或重参考。",
                     "方法不需要坐标，但相近生理信号也会低电气距离；候选仍需原始波形和硬件记录复核。",
                     "完全重复或退化距离分布可能导致KDE失败；失败不得解释为无桥接。",
                     "仅MNE副本上滤波；不插值、不删道，候选不提供已确认的起止时刻。"]},
    {"id": "mne_lof", "name": "MNE LOF 通道离群候选", "module_id": "M05", "category": "optional",
     "description": "按选中EEG波形之间的局部离群因子提供通道候选；不自动判定信号无效。",
     "inputs": ["已标定为V的同参考EEG", "足够比较通道", "原生采样连续片段"],
     "outputs": ["通道候选", "各道原始负LOF及其绝对值"],
     "requirements": ["共同或连接耳参考且仅一个完整比较组", "本版至少8道、10秒且通道数大于邻居数", "scikit-learn运行依赖"],
     "source": {"name": "MNE-Python find_bad_channels_lof", "url": "https://mne.tools/stable/generated/mne.preprocessing.find_bad_channels_lof.html", "license": "BSD-3-Clause"},
     "implementation": "available", "status": "available",
     "defaults": {"n_neighbors": 20, "metric": "euclidean", "threshold": 1.5},
     "limitations": ["邻居20和阈值1.5是软件默认值，不是国际共识；少于21道时默认配置阻断。",
                     "比较整个当前片段的波形向量；参考、幅值、选道、片段长度和病理活动均影响离群结果。",
                     "双极、混合或未知参考阻断；不把双极链中的不同导联当普通帽上通道比较。",
                     "没有额外滤波、重参考、归一化或空间插值；不需要电极坐标。",
                     "算法返回通道级候选，不提供单道异常时间；疾病标签不参与计算。"]},
    {"id": "autoreject_global", "name": "autoreject 全局阈值估计", "module_id": "M03", "category": "optional",
     "description": "把连续片段分成固定长度段，用全局交叉验证估计EEG峰峰值阈值；不执行剔除。",
     "inputs": ["已标定为V的EEG", "至少20个完整固定长度段", "固定交叉验证配置"],
     "outputs": ["本片段估计的全局峰峰值阈值（V）", "同片段超阈值固定段候选", "原记录时钟上的分段范围与未使用尾段"],
     "requirements": ["本版至少20个完整固定段且不少于4×cv", "autoreject运行依赖", "明确固定段不是任务试次"],
     "source": {"name": "autoreject get_rejection_threshold", "url": "https://autoreject.github.io/stable/generated/autoreject.get_rejection_threshold.html", "license": "BSD-3-Clause"},
     "implementation": "available", "status": "available",
     "defaults": {"epoch_duration_seconds": 2.0, "cv": 5, "random_state": 0, "decim": 1},
     "limitations": ["固定连续分段不是已验证独立任务试次；相邻时间段相关，CV结果不能当独立泛化验证。",
                     "分段2秒、随机种子0、至少20段是项目研究配置；cv=5是库默认值，均非通用质量阈值。",
                     "允许双极导联作探索性阈值估计；睡眠慢波、癫痫样活动等可能影响阈值，不能据此称伪迹。",
                     "不执行drop_bad、reject、transform或局部AutoReject；不使用源坏道、事件或疾病标签。",
                     "不足一个完整段的尾部不参与阈值估计并明确报告；不自动降采样或过滤数据。"]},
]


def extension_specs():
    return copy.deepcopy(_SPECS)


def _spec(identifier):
    for spec in _SPECS:
        if spec["id"] == identifier:
            return copy.deepcopy(spec)
    raise ValueError(f"Unknown extension: {identifier}")


def _number(value, name, *, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite JSON number")
    if value < 0 or (value == 0 and not zero):
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")
    return float(value)


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _parameters(identifier, params):
    defaults = _spec(identifier)["defaults"]
    if params is not None and (not isinstance(params, dict) or set(params) - set(defaults)):
        raise ValueError("Parameters must be an object containing only declared parameter names")
    values = {**defaults, **copy.deepcopy(params or {})}
    if identifier == "mne_bridge":
        for key in values:
            values[key] = _number(values[key], key)
        if values["epoch_threshold"] >= 1:
            raise ValueError("epoch_threshold must be strictly between 0 and 1")
        if not 0.1 <= values["l_freq_hz"] < values["h_freq_hz"] <= 45:
            raise ValueError("Bridge method requires 0.1 <= l_freq_hz < h_freq_hz <= 45")
        if not 1 <= values["epoch_duration_seconds"] <= 10:
            raise ValueError("epoch_duration_seconds must be between 1 and 10")
    elif identifier == "mne_lof":
        values["n_neighbors"] = _integer(values["n_neighbors"], "n_neighbors", 2, 255)
        values["threshold"] = _number(values["threshold"], "threshold")
        if values["threshold"] <= 1:
            raise ValueError("threshold must exceed 1 for this LOF screening adapter")
        if values["metric"] != "euclidean":
            raise ValueError("This adapter exposes only the reviewed euclidean metric")
    else:
        values["epoch_duration_seconds"] = _number(values["epoch_duration_seconds"], "epoch_duration_seconds")
        if not 1 <= values["epoch_duration_seconds"] <= 10:
            raise ValueError("epoch_duration_seconds must be between 1 and 10")
        values["cv"] = _integer(values["cv"], "cv", 2, 10)
        values["random_state"] = _integer(values["random_state"], "random_state", 0, 2**32 - 1)
        values["decim"] = _integer(values["decim"], "decim", 1, 1)
    return values


def _one_comparison_group(groups, count):
    if isinstance(groups, list):
        return len(groups) == count and all(isinstance(g, str) and g for g in groups) and len(set(groups)) == 1
    if isinstance(groups, dict) and len(groups) == 1:
        name, size = next(iter(groups.items()))
        return isinstance(name, str) and bool(name) and type(size) is int and size == count
    return False


def evaluate_extension(identifier, facts, params=None):
    parameters = _parameters(identifier, params)
    result = {"status": "blocked", "reason": "", "parameters": parameters}
    if not isinstance(facts, dict) or facts.get("verified_voltage") is not True:
        return {**result, "reason": "必须提供明确的电压标定与数据事实；未确认单位为V"}
    try:
        fs = _number(facts.get("sampling_rate_hz"), "sampling_rate_hz")
        seconds = _number(facts.get("window_seconds"), "window_seconds")
        count = _integer(facts.get("n_eeg"), "n_eeg", 1, 256)
        if seconds > 120 or round(seconds * fs) < 2:
            raise ValueError("本版窗口须至少2采样点、至多120秒")
    except ValueError as error:
        return {**result, "reason": str(error)}
    if identifier in {"mne_bridge", "mne_lof"}:
        if facts.get("reference_scheme") not in {"common_reference", "linked_ears"}:
            return {**result, "reason": "本版仅支持已核实的共同/连接耳参考；双极、混合或未知参考不可按帽上通道相似性筛查"}
        if not _one_comparison_group(facts.get("comparison_groups"), count):
            return {**result, "reason": "需要一个覆盖全部所选EEG的明确比较组；不自动跨组比较或重参考"}
        if count < 8 or seconds < 10:
            return {**result, "reason": "本版保守门槛为至少8道、10秒；这是项目门槛而非国际标准"}
    if identifier == "mne_bridge":
        if fs / 2 <= parameters["h_freq_hz"]:
            return {**result, "reason": "奈奎斯特频率不足以支持声明的桥接检测滤波频带"}
        if seconds < 5 * parameters["epoch_duration_seconds"]:
            return {**result, "reason": "桥接分布估计至少需要5个完整固定段（项目门槛）"}
        return {**result, "status": "ready", "reason": "可计算电气距离与桥接候选；软件阈值不等于硬件短接证据"}
    if identifier == "mne_lof":
        if count <= parameters["n_neighbors"]:
            return {**result, "reason": "EEG通道数必须大于n_neighbors；不允许软件静默缩减邻居数"}
        return {**result, "status": "ready", "reason": "可运行同参考EEG的LOF离群筛查；输出仅为通道候选"}
    n_samples = round(seconds * fs)
    epoch_samples = round(parameters["epoch_duration_seconds"] * fs)
    if epoch_samples < 2 or abs(epoch_samples / fs - parameters["epoch_duration_seconds"]) > 1e-8:
        return {**result, "reason": "固定段长度必须精确对应整数个原生采样点且至少2点"}
    minimum = max(20, 4 * parameters["cv"])
    if n_samples // epoch_samples < minimum:
        return {**result, "reason": f"本版至少需要{minimum}个完整固定段以估计阈值；短片段不强行拟合"}
    return {**result, "status": "partial", "reason": "仅探索性连续分段全局阈值；固定段非任务试次，病理/睡眠活动不据此判伪迹"}


def _data_hash(data):
    import numpy as np
    canonical = np.asarray(data, dtype="<f8", order="C")
    return hashlib.sha256(memoryview(canonical).cast("B")).hexdigest()


def _source(identifier, function):
    from importlib.metadata import version
    source = _spec(identifier)["source"]
    unwrapped = inspect.unwrap(function)
    location = inspect.getsourcefile(unwrapped)
    if not location or not Path(location).is_file():
        location = getattr(inspect.getmodule(function), "__file__", None)
    source.update(function=function.__module__ + "." + function.__name__,
                  version=version("autoreject" if identifier == "autoreject_global" else "mne"),
                  implementation_sha256=hashlib.sha256(Path(location).read_bytes()).hexdigest() if location and Path(location).is_file() else None,
                  adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  packages={name: version(name) for name in ("mne", "numpy", "scipy", "scikit-learn")})
    return source


def _base_result(identifier, data, fs, names, start, parameters, verdict):
    return {"schema_version": "ephys-extension-result/1.0", "extension_id": identifier,
            "status": verdict["status"], "reason": verdict["reason"], "parameters": parameters,
            "source": _spec(identifier)["source"], "data_sha256": _data_hash(data),
            "range": {"start_seconds": start, "stop_seconds": start + data.shape[1] / fs,
                      "duration_seconds": data.shape[1] / fs, "sampling_rate_hz": fs, "n_samples": data.shape[1]},
            "channel_names": names, "unit": "V", "candidates": [], "notes": [], "automatic_actions": [],
            "input_unchanged": True, "review_status": "pending", "candidate_interval_count": 0,
            "candidate_channel_count": 0, "candidate_pair_count": 0}


def _epochs(data, fs, seconds, start):
    """Own-copy, nonoverlapping fixed segments with explicit original-clock ranges."""
    import numpy as np
    width = round(seconds * fs)
    count = data.shape[1] // width
    used = count * width
    values = np.array(data[:, :used].reshape(len(data), count, width).transpose(1, 0, 2), copy=True)
    info = {"kind": "fixed_continuous_segments_not_task_trials", "epoch_duration_seconds": width / fs,
            "epoch_samples": width, "n_epochs": count, "ranges": [
                {"index": i, "start_seconds": start + i * width / fs, "stop_seconds": start + (i + 1) * width / fs}
                for i in range(count)],
            "tail_samples_not_used": data.shape[1] - used,
            "tail_range_not_used": [start + used / fs, start + data.shape[1] / fs] if used < data.shape[1] else None}
    return values, info


def run_extension(identifier, data_volts, sfreq, channel_names, start_seconds, parameters, *, facts=None):
    """Run an explicitly selected method; facts are mandatory and revalidated.

    data_volts rows must be the selected EEG channels, with unique adapter names.
    The caller retains a separate source-index mapping when raw labels repeat.
    """
    import numpy as np
    parameters = _parameters(identifier, parameters)
    fs = _number(sfreq, "sfreq")
    start = _number(start_seconds, "start_seconds", zero=True)
    original = np.asarray(data_volts)
    if original.ndim != 2 or min(original.shape) < 1 or original.dtype.kind not in "fiu" or not np.all(np.isfinite(original)):
        raise ValueError("data_volts must be a finite real channel-by-sample array")
    names = list(channel_names) if not isinstance(channel_names, (str, bytes)) else []
    if len(names) != len(original) or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError("channel_names must be distinct nonempty names matching selected EEG rows")
    data = np.asarray(original, dtype=float, order="C")
    if not math.isfinite(start + data.shape[1] / fs):
        raise ValueError("Original recording stop time must be finite")
    verdict = evaluate_extension(identifier, facts, parameters)
    result = _base_result(identifier, data, fs, names, start, parameters, verdict)
    if verdict["status"] == "blocked":
        return result
    # Never silently override metadata that contradicts the actual input.
    if (facts.get("n_eeg") != len(data) or
        not math.isclose(facts["sampling_rate_hz"], fs, rel_tol=0, abs_tol=1e-8) or
        not math.isclose(facts["window_seconds"], data.shape[1] / fs, rel_tol=0, abs_tol=0.5 / fs)):
        return {**result, "status": "blocked", "reason": "声明的通道数/采样率/窗口与实际数组不一致"}
    if np.ptp(data) == 0:
        return {**result, "status": "blocked", "reason": "整个输入为恒值，不能将退化分布下的空候选或零阈值解释为正常"}
    caught = []
    try:
        import mne
        if identifier == "autoreject_global":
            from autoreject import get_rejection_threshold
            function = get_rejection_threshold
        else:
            function = getattr(mne.preprocessing, "compute_bridged_electrodes" if identifier == "mne_bridge" else "find_bad_channels_lof")
        result["source"] = _source(identifier, function)
        # Copies only; no source bads/annotations are imported and first_samp=0.
        raw = mne.io.RawArray(data.copy(), mne.create_info(names, fs, "eeg"), first_samp=0, copy="both", verbose="ERROR")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            if identifier == "mne_bridge":
                pairs, distances = function(raw, lm_cutoff=parameters["lm_cutoff_uv2"],
                    epoch_threshold=parameters["epoch_threshold"], l_freq=parameters["l_freq_hz"],
                    h_freq=parameters["h_freq_hz"], epoch_duration=parameters["epoch_duration_seconds"], verbose="ERROR")
                n_epochs = len(distances)
                # Lower triangle/diagonal are structural NaNs in MNE, not errors.
                upper = np.triu_indices(len(names), 1)
                if n_epochs < 5 or not np.all(np.isfinite(distances[:, upper[0], upper[1]])):
                    raise RuntimeError("Electrical-distance upper triangle contains nonfinite values or insufficient epochs")
                result["electrical_distance_uv2"] = [
                    {"channel_indices": [i, j], "channel_names": [names[i], names[j]],
                     "values_by_epoch": [float(v) for v in distances[:, i, j]]}
                    for i, j in zip(upper[0].tolist(), upper[1].tolist())]
                actual_epochs = mne.make_fixed_length_epochs(raw, duration=parameters["epoch_duration_seconds"], preload=False, verbose="ERROR")
                if len(actual_epochs.events) != n_epochs:
                    raise RuntimeError("Bridge epoch timing could not be matched to MNE output")
                epoch_samples = len(actual_epochs.times)
                starts = actual_epochs.events[:, 0].tolist()
                used_stop = starts[-1] + epoch_samples
                result["segmentation"] = {"kind": "fixed_continuous_segments_not_task_trials", "n_epochs": n_epochs,
                    "epoch_samples": epoch_samples, "epoch_duration_seconds": epoch_samples / fs,
                    "ranges": [{"index": i, "start_seconds": start + s / fs, "stop_seconds": start + (s + epoch_samples) / fs} for i, s in enumerate(starts)],
                    "tail_samples_not_used": data.shape[1] - used_stop,
                    "tail_range_not_used": [start + used_stop / fs, result["range"]["stop_seconds"]] if used_stop < data.shape[1] else None}
                for i, j in pairs:
                    i, j = int(i), int(j)
                    result["candidates"].append({"kind": "electrode_bridge_candidate", "localization": "pair_only", "scope": "channel_pair",
                        "channel_indices": [i, j], "channel_names": [names[i], names[j]], "channel_index": None, "channel_name": None,
                        "start_seconds": None, "stop_seconds": None, "duration_seconds": None,
                        "analysis_range": [start, result["range"]["stop_seconds"]], "action": "review", "review_status": "pending"})
                result["candidate_pair_count"] = len(pairs)
                result["candidate_channel_count"] = len({int(i) for pair in pairs for i in pair})
                result["status"] = "completed"
                result["reason"] = "电气距离与桥接候选计算完成；须复核波形和硬件，不执行插值"
                result["notes"] += ["只存上三角有效电气距离，单位μV²；MNE下三角及对角的结构性NaN未序列化。",
                    "lm_cutoff是KDE拟合范围上限；算法未返回实际局部极小值，未伪造最终阈值。",
                    "MNE只给全分析片段上的通道对候选；逐段距离是证据，不是已确认桥接发生时刻。",
                    "MNE在自有副本上进行声明的带通滤波；未知上游滤波史限制与其他记录的直接比较。"]
            elif identifier == "mne_lof":
                bads, scores = function(raw, n_neighbors=parameters["n_neighbors"], picks="eeg", metric=parameters["metric"],
                                       threshold=parameters["threshold"], return_scores=True, verbose="ERROR")
                if len(scores) != len(names) or not np.all(np.isfinite(scores)):
                    raise RuntimeError("LOF returned invalid channel scores")
                result["channel_scores"] = [{"channel_index": i, "channel_name": name,
                    "negative_outlier_factor": float(scores[i]), "absolute_lof": float(abs(scores[i]))} for i, name in enumerate(names)]
                result["bad_channels"] = list(bads)
                for name in bads:
                    result["candidates"].append({"kind": "lof_channel_candidate", "localization": "channel_only", "scope": "channel",
                        "channel_index": names.index(name), "channel_name": name, "start_seconds": None, "stop_seconds": None,
                        "duration_seconds": None, "analysis_range": [start, result["range"]["stop_seconds"]], "action": "review", "review_status": "pending"})
                result["candidate_channel_count"] = len(bads)
                result["status"] = "completed"
                result["reason"] = "同参考EEG的LOF通道候选计算完成；无时间定位，不自动删道"
                result["notes"] += ["保留负LOF原值；MNE用其绝对值>=threshold生成候选。",
                    "欧氏距离直接使用当前选中波形，不额外滤波、归一化、重参考；选道和片段变化会影响结果。"]
            else:
                values, segmentation = _epochs(data, fs, parameters["epoch_duration_seconds"], start)
                epoch_values_before = _data_hash(values)
                events = np.column_stack((np.arange(len(values)) * values.shape[-1], np.zeros(len(values), dtype=int), np.ones(len(values), dtype=int)))
                epochs = mne.EpochsArray(values.copy(), raw.info.copy(), events=events, event_id={"fixed_segment": 1},
                                         tmin=0, baseline=None, reject=None, flat=None, proj=False, verbose="ERROR")
                thresholds = function(epochs, decim=parameters["decim"], random_state=parameters["random_state"],
                                      ch_types=["eeg"], cv=parameters["cv"], verbose=False)
                threshold = float(thresholds["eeg"])
                if not math.isfinite(threshold) or threshold <= 0:
                    raise RuntimeError("autoreject did not return a finite positive EEG threshold")
                if len(epochs) != len(values) or _data_hash(epochs.get_data(copy=False)) != epoch_values_before:
                    raise RuntimeError("Threshold estimation unexpectedly changed the fixed epochs")
                result["estimated_thresholds_volts"] = {"eeg": threshold}
                result["segmentation"] = segmentation
                maxima = np.ptp(values, axis=2).max(axis=1)
                result["epoch_max_ptp_volts"] = [float(v) for v in maxima]
                result["assessment_scope"] = "same_window_in_sample_descriptive_threshold"
                result["threshold_comparison"] = ">"
                for i in np.flatnonzero(maxima > threshold).tolist():
                    interval = segmentation["ranges"][i]
                    result["candidates"].append({"kind": "global_threshold_segment_candidate", "localization": "epoch_only",
                        "scope": "fixed_segment_across_selected_eeg_channels", "epoch_index": i,
                        "start_seconds": interval["start_seconds"], "stop_seconds": interval["stop_seconds"],
                        "duration_seconds": interval["stop_seconds"] - interval["start_seconds"],
                        "channel_index": None, "channel_name": None, "max_ptp_volts": float(maxima[i]),
                        "threshold_volts": threshold, "action": "review", "review_status": "pending"})
                result["candidate_interval_count"] = len(result["candidates"])
                result["status"] = "partial"
                result["reason"] = "已估计本片段全局峰峰值阈值；连续分段不是任务试次，仅供探索和复核"
                result["notes"] += ["仅调用get_rejection_threshold估计阈值，再只读比较各段最大EEG峰峰值；未删除、标坏或修复任何信号。",
                    "候选是同一拟合片段内的描述性超阈值段，不是独立验证指标、最终坏段或伪迹真值。",
                    "固定连续段相邻且可能相关；库内部CV优化不是独立受试者/任务泛化验证。",
                    "睡眠慢波、癫痫样等生理或病理活动可影响阈值；疾病及事件标签不进入算法。",
                    "零个超阈值段不表示数据通过质量审查；未评估阈值的跨片段泛化。"]
    except (ImportError, ModuleNotFoundError) as error:
        result.update(status="blocked", reason="运行环境缺少该公开方法的依赖：" + str(error), error_type=type(error).__name__)
    except Exception as error:
        result.update(status="failed", reason="公开方法执行失败，不能解释为空候选或正常：" + str(error), error_type=type(error).__name__)
        result["candidates"] = []
        result.update(candidate_interval_count=0, candidate_channel_count=0, candidate_pair_count=0)
    result["notes"] += sorted({str(w.message) for w in caught})
    result["notes"].append("未执行自动删除、插值、重参考或清洗；所有候选等待人工复核。")
    result["input_unchanged"] = _data_hash(original) == result["data_sha256"]
    if not result["input_unchanged"]:
        raise RuntimeError("Extension unexpectedly mutated the caller's input")
    return result
