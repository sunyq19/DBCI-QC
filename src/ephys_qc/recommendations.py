"""Deterministic, metadata-only suggestions validated by the existing planner.

This module never opens signal/annotation files, imports scientific packages,
starts jobs, infers missing channel roles, or uses clinical context as a threshold.
"""
import copy
import hashlib
import json

from .planning import build_plan
from .method_registry import methods
from .tagging import data_facts
from .extensions import extension_specs

SCHEMA_VERSION = "ephys-recommendation/1.0"
POLICY_VERSION = "scalp-eeg-metadata-rules/1.1.0"
_ANNOTATIONS = {"sleep_stages_tsv": "sleep_timeline", "bids_events_tsv": "task_timeline", "clinical_events_tsv": "clinical_timeline"}
_BASE_MODULES = ["M03", "M04", "M05"]


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Recommendation inputs must contain finite JSON values") from error


def _missing(key, label, reason, blocking=False, blocks_methods=None):
    return {"key": key, "label": label, "reason": reason, "blocking": blocking,
            "blocks_methods": list(blocks_methods or [])}


def _finish(result, record, submitted):
    # Include the user's current selection/parameters even when the proposed
    # extension selection differs. Object-key order is intentionally irrelevant.
    identity = {"policy_version": POLICY_VERSION, "schema_version": SCHEMA_VERSION,
                "record": record, "submitted_qc_config": submitted or {},
                "status": result["status"], "plan_id": result.get("plan_id"),
                "selected_modules": result["selected_modules"], "qc_config": result["qc_config"]}
    result["recommendation_id"] = hashlib.sha256(_canonical(identity).encode()).hexdigest()
    _canonical(result)
    return result


def _empty(record, status, reason, missing=None):
    return {"schema_version": SCHEMA_VERSION, "policy_version": POLICY_VERSION,
            "recommendation_id": None, "status": status, "can_apply": False,
            "summary": reason, "reason": reason, "selected_modules": [], "qc_config": None,
            "recommended_methods": [], "optional_methods": [], "blocked_methods": [],
            "missing_fields": list(missing or []), "cautions": [
                "仅根据登记元数据提供确定性规则建议；不声称AI最优或行业统一处方。",
                "尚未读取信号、核验文件现存性、运行方法或生成质量分。"],
            "data_tags": [], "method_applicability": [], "review_focus": [], "plan_id": None,
            "plan_warnings": [], "current_extensions": [], "extension_selection_changed": False,
            "scope": {"supported_modality": "scalp_eeg", "supported_metadata_formats": ["EDF", "EDF+", "BDF", "BrainVision", "EEGLAB", "FIF"],
                      "declared_modality": record.get("modality"),
                      "declared_format": record.get("metadata", {}).get("format") if isinstance(record.get("metadata"), dict) else None,
                      "basis": "registered_metadata_only", "signal_read": False, "job_created": False},
            "quality_score": None}


def _config_error_key(message):
    for fragment, key, label in [
        ("电压单位", "metadata.channels.unit", "电压单位与标定"),
        ("非头皮EEG类型", "metadata.channels.type", "分析信号类型"),
        ("metadata.channels", "metadata.channels", "通道技术清单"),
        ("metadata.duration_seconds", "metadata.duration_seconds", "记录时长"),
        ("eeg_indices", "selection.eeg_indices", "EEG源通道选择"),
        ("Auxiliary", "selection.reference_indices", "辅助导联选择"),
        ("reference_indices", "selection.reference_indices", "辅助导联选择"),
        ("sampling", "metadata.channels.sampling_rate_hz", "原生采样时钟"),
        ("range", "selection.duration_seconds", "分析时间范围"),
        ("120 seconds", "selection.duration_seconds", "分析时长"),
        ("comparison_groups", "method_config.comparison_groups", "参考比较组"),
    ]:
        if fragment in message:
            return key, label
    return "qc_config", "检查配置或登记字段"


def _review_focus(context):
    focus = []
    if context.get("task") == "sleep" or context.get("disease") == "sleep_disorder":
        focus.append("睡眠阶段会改变幅度和频谱；慢波、纺锤及阶段转变不能仅因偏离阈值就判为伪迹。")
    if context.get("disease") == "epilepsy":
        focus.append("发作及癫痫样活动可能高幅或呈异常节律；与临床事件并排复核，不把病理活动当质量真值。")
    elif context.get("disease") not in {None, "unknown", "healthy_control", "sleep_disorder"}:
        focus.append("已登记疾病背景仅提示复核生理/病理活动与伪迹的区别，不据此改阈值或质量分。")
    if context.get("task") == "motor":
        focus.append("任务动作可改变EEG和肌电，但任务事件本身不是伪迹标签；需结合原始波形复核。")
    elif context.get("task") == "motor_imagery":
        focus.append("运动想象事件标记想象任务，不证明发生了实际动作或肌电污染；需结合原始波形复核。")
    elif context.get("task") in {"attention", "erp"}:
        focus.append("事件锁时和任务状态会改变波形；事件存在不等于已经形成独立可比的试次。")
    if context.get("age_group") in {"neonate", "child", "older_adult"}:
        focus.append("已登记年龄组可能影响正常幅度与谱形；本推荐不建立或套用年龄专属阈值。")
    if not focus:
        focus.append("结合原始波形、采集记录及已核实的状态背景复核候选；未登记背景保持未知。")
    return focus


def recommend(record, qc_config=None):
    """Return a proposal whose selected_modules/qc_config reproduce plan_id.

    Valid JSON with missing/unsupported metadata returns needs_input/unsupported;
    non-JSON values and nonfinite numbers raise ValueError, as in build_plan.
    A ready proposal is not an executed check or a quality verdict.
    """
    if not isinstance(record, dict) or (qc_config is not None and not isinstance(qc_config, dict)):
        raise ValueError("record and optional qc_config must be JSON objects")
    _canonical(record)
    _canonical(qc_config)
    record = copy.deepcopy(record)
    submitted = copy.deepcopy(qc_config)
    scope_missing = []
    modality = record.get("modality")
    metadata = record.get("metadata")
    file_format = metadata.get("format") if isinstance(metadata, dict) else None
    if modality in (None, "", "unknown"):
        scope_missing.append(_missing("modality", "信号模态", "需明确登记为头皮EEG；不从文件名、通道名或疾病背景推断。", True))
    elif modality != "scalp_eeg":
        return _finish(_empty(record, "unsupported", "当前推荐仅接入头皮EEG；此模态没有已验证的推荐路线。"), record, submitted)
    if file_format in (None, "", "unknown"):
        scope_missing.append(_missing("metadata.format", "原始文件格式", "需由读取模块核实文件格式，不根据扩展名推断。", True))
    elif file_format not in {"EDF", "EDF+", "BDF", "BrainVision", "EEGLAB", "FIF"}:
        return _finish(_empty(record, "unsupported", "此格式没有可用读取模块；尚不能推荐信号检查。"), record, submitted)
    if scope_missing:
        return _finish(_empty(record, "needs_input", "先补充并核实模态/文件格式，再给出可应用建议。", scope_missing), record, submitted)

    prerequisites = []
    if not isinstance(record.get("id"), str) or not record["id"].strip():
        prerequisites.append(_missing("id", "记录身份", "需要稳定登记ID以保留源通道身份和计划指纹。", True))
    if not isinstance(record.get("source_path"), str) or not record["source_path"].strip():
        prerequisites.append(_missing("source_path", "原始文件登记", "需要登记原始文件路径；推荐引擎不会访问或猜测该路径。", True))
    channels = metadata.get("channels")
    if not isinstance(channels, list) or not channels:
        prerequisites.append(_missing("metadata.channels", "通道技术清单", "需要已核验的源索引、单位和采样率，不能自动猜选道。", True))
    elif any(not isinstance(c, dict) or type(c.get("index")) is not int for c in channels) or len({c.get("index") for c in channels}) != len(channels):
        prerequisites.append(_missing("metadata.channels", "源通道身份", "通道清单须包含唯一整数index；重名允许，源索引不能重复或缺失。", True))
    if prerequisites:
        return _finish(_empty(record, "needs_input", "关键接入信息不足，暂不生成可应用计划。", prerequisites), record, submitted)

    try:
        # Keep user-supplied thresholds, selection and current choices intact for
        # validation before proposing any new extension selection.
        current = build_plan(record, selected_modules=[], qc_config=submitted)
        config = copy.deepcopy(current["qc_config"])
        facts = data_facts(record, config)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        key, label = _config_error_key(str(error))
        missing = [_missing(key, label, "现有计划器未接受此配置：" + str(error), True)]
        return _finish(_empty(record, "needs_input", "配置须先通过现有计划器核验；未自动修补或绕过门槛。", missing), record, submitted)
    if not facts["verified_voltage"]:
        missing = [_missing("metadata.channels.unit", "电压单位与标定", "所选EEG/辅助通道单位未全部核实为可标定电压；实际读取会拒绝，不能默认按V解释。", True)]
        result = _empty(record, "needs_input", "先核实所选信号的电压单位，再推荐信号检查。", missing)
        result.update(data_tags=current["data_tags"], method_applicability=current["method_applicability"])
        return _finish(result, record, submitted)

    specs = methods()
    by_id = {m["id"]: m for m in specs}
    extra_ids = [m["id"] for m in extension_specs()]
    probe_config = copy.deepcopy(config)
    probe_config["method_config"]["extensions"] = extra_ids
    try:
        candidate_plan = build_plan(record, ["M03", "M04", "M05", "M06", "M07"], probe_config)
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        return _finish(_empty(record, "needs_input", "候选方法参数未通过现有计划器；未生成建议。",
                             [_missing("method_config", "方法参数", str(error), True)]), record, submitted)
    gates = {m["id"]: m for m in candidate_plan["method_applicability"]}
    selected = list(_BASE_MODULES)
    if any(gates[name]["status"] in {"ready", "partial"} for name in ("ecg_locked", "eog_locked", "hf_burst")):
        selected.append("M06")
    annotation = record.get("annotation") or {}
    annotation_id = _ANNOTATIONS.get(annotation.get("format"))
    annotation_complete = annotation_id and isinstance(annotation.get("path"), str) and bool(annotation["path"].strip())
    if annotation_complete:
        selected.append("M07")
    recommended_extras = ["mne_amplitude"] if gates["mne_amplitude"]["status"] in {"ready", "partial"} else []
    config["method_config"]["extensions"] = recommended_extras
    # Only introduce parameters for the newly suggested default. Existing
    # explicit parameters of unselected methods remain available for user review.
    for name in recommended_extras:
        config["method_config"]["extension_parameters"][name] = copy.deepcopy(gates[name]["parameters"])
    final = build_plan(record, selected, config)
    final_gates = {m["id"]: m for m in final["method_applicability"]}

    result = _empty(record, "ready", "已根据登记技术条件形成建议，执行时核验计划并由用户明确启动。")
    result.update(can_apply=True, selected_modules=final["selected_modules"], qc_config=final["qc_config"],
                  plan_id=final["plan_id"], data_tags=final["data_tags"], method_applicability=final["method_applicability"],
                  plan_warnings=final["warnings"], review_focus=_review_focus(facts["context"]),
                  current_extensions=current["qc_config"]["method_config"]["extensions"],
                  extension_selection_changed=current["qc_config"]["method_config"]["extensions"] != recommended_extras)

    def entry(identifier, reason, gate, *, disposition):
        spec = by_id[identifier]
        return {"id": identifier, "module_id": spec["module_id"], "name": spec["name"], "reason": reason,
                "applicability": gate["status"], "implementation": spec["implementation"],
                "parameters": copy.deepcopy(gate.get("parameters")), "disposition": disposition,
                "optional_extension": spec["optional_extension"]}

    reasons = {
        "edf_reader": "保留结构、来源指纹和原始时钟核验；格式可读不等于质量合格。",
        "voltage_calibration": "所选信号已登记电压单位，执行时仍须核对逐道标定。",
        "qc_plan": "冻结用户明确的选道、原生采样时钟和时间窗，不猜通道角色。",
        "continuity": "先检查缺失、恒值和端点平台，为后续方法保留完整性证据。",
        "welch_psd": "提供当前片段的基础频谱描述；谱形差异不直接判质量。",
        "thomson_line": "仅在本片段可测频带内检查工频及谐波，不补造奈奎斯特频率外结果。",
        "spectral_model": "保留背景谱与谱峰描述，并如实标记短窗或频带不足的未评项。",
        "prep_nonspatial": "保留M05非空间描述与实现已允许的比较组；不补参考、不扩大比较组。",
        "ecg_locked": "已明确配置同钟ECG，可检查锁时支持；不能仅凭EEG确认心电污染。",
        "eog_locked": "已明确配置同钟EOG，可检查锁时支持；通道名未用于猜辅助角色。",
        "hf_burst": "有效频带和时长允许现有高频检查；无EMG时仅保留探索线索。",
        "sleep_timeline": "已有明确睡眠分期表，核对原记录时间和覆盖；分期不是质量标签。",
        "task_timeline": "已有支持格式的任务事件表，核对原记录时间；任务事件不是伪迹真值。",
        "clinical_timeline": "已有临床事件表，仅并排呈现来源事件；发作不作为伪迹或扣分依据。",
        "aggregate": "汇总已评和未评原因；总质量分尚未校准，继续保持null。",
        "report": "保留可追溯证据并交人工复核，不自动删道、删段或清洗。",
        "mne_amplitude": "增加只读相邻采样差分检查；未给参数时默认仅查平线（flat=0、peak=None），不是峰峰值阈值。",
    }
    for spec in specs:
        identifier = spec["id"]
        gate, active = gates[identifier], final_gates[identifier]
        if spec["implementation"] != "available":
            reason = gate["reason"]
            if not facts["has_coordinates"] and identifier in {"pyprep_ransac", "autoreject_epochs", "ica_iclabel"}:
                reason += " 电极坐标未核实，不从通道名称补位置。"
            result["blocked_methods"].append(entry(identifier, reason, gate, disposition="not_implemented"))
        elif identifier in _ANNOTATIONS.values() and not annotation_complete and gate["status"] != "blocked":
            result["blocked_methods"].append(entry(identifier, "标注登记缺少支持的格式或明确路径；不猜标注来源。",
                                                  {**gate, "status": "blocked"}, disposition="missing_registration"))
        elif gate["status"] == "blocked":
            result["blocked_methods"].append(entry(identifier, gate["reason"], gate, disposition="blocked_by_existing_gate"))
        elif active["selected"] and active["status"] in {"ready", "partial"}:
            result["recommended_methods"].append(entry(identifier, reasons.get(identifier, gate["reason"]) + " " + active["reason"], active, disposition="recommended"))
        elif spec["optional_extension"]:
            option_reason = {
                "mne_bridge": "参考、比较组和通道数满足现有门槛；桥接候选仍需硬件/波形复核，默认不增加该筛查。",
                "mne_lof": "同参考比较和邻居数门槛满足；离群不等于坏道，默认不增加额外通道候选。",
                "mne_muscle": "仅可显式选择探索性高频时间线索；滤波史未知时尤其不能确认肌电，也需排查120Hz谐波。",
                "autoreject_global": "始终只列可选探索：连续固定段不是任务试次，同窗口拟合阈值不能当独立泛化验证或坏段真值。",
            }.get(identifier, "可显式选择此项；当前策略未将其设为默认。")
            result["optional_methods"].append(entry(identifier, option_reason + " " + gate["reason"], gate, disposition="optional_exploratory"))

    missing = result["missing_fields"]
    if not record.get("expected_sha256"):
        missing.append(_missing("expected_sha256", "来源预期指纹", "未登记预期SHA-256；执行时可计算指纹，但目前不能与已登记原本比对。"))
    if facts["reference_scheme"] == "unknown":
        missing.append(_missing("reference_scheme", "参考构型", "参考未知，不从同一记录或通道名称推断共同参考。", blocks_methods=["mne_bridge", "mne_lof"]))
    if not facts["comparison_groups"]:
        missing.append(_missing("method_config.comparison_groups", "参考比较组", "没有明确比较组；M05保留描述量，不为组阈值自动凑组。", blocks_methods=["prep_nonspatial", "mne_bridge", "mne_lof"]))
    if not facts["preprocessing_verified"] or facts["preprocessing_highpass_hz"] is None or facts["preprocessing_lowpass_hz"] is None:
        missing.append(_missing("preprocessing", "采集/滤波史", "处理史未完整核实；采样率足够不等于目标高频实际保留。", blocks_methods=["mne_muscle"]))
    if not facts["has_coordinates"]:
        missing.append(_missing("verified_electrode_coordinates", "电极位置", "坐标未核实；空间方法和ICA尚未接入，不会因名称像标准电极而推荐。", blocks_methods=["pyprep_ransac", "autoreject_epochs", "ica_iclabel"]))
    for role, label, blocked in [("ecg", "ECG辅助导联", ["ecg_locked"]), ("eog", "EOG辅助导联", ["eog_locked"]), ("emg", "EMG辅助导联", ["hf_burst"] )]:
        if not facts["has_" + role]:
            missing.append(_missing("selection.reference_indices." + role, label, "当前未确认并配置该角色，不推断原文件是否含有可用导联；缺失不计作质量差。", blocks_methods=blocked))
    if not annotation_complete:
        missing.append(_missing("annotation", "状态/事件标注", "未登记完整且支持的状态或事件表；不从任务/疾病背景推断事件或分期。", blocks_methods=list(_ANNOTATIONS.values())))
    result["cautions"] += [
        "推荐只是可解释规则；是否启用探索方法仍由用户选择。应用建议会重新生成扩展选择集合，现有明确参数与选道保留。",
        "疾病、年龄和任务仅用于复核提示，不改变推荐阈值、选道或质量分；unknown保持未知。",
        "RANSAC、local AutoReject和ICA/ICLabel仍未接入；已有坐标也不代表可执行。",
        "每次窗口至多120秒；整记录模式分块执行，最终覆盖需查看实际结果，推荐本身不是已完成验证。",
    ]
    if facts["reference_scheme"] in {"bipolar", "mixed"}:
        result["cautions"].append("双极/混合参考不作为普通同参考帽上通道集合比较；桥接和LOF沿用现有阻断门槛。")
    result["cautions"] = list(dict.fromkeys(result["cautions"] + final["warnings"]))
    scope_description = (f"整记录{final['window_count']}个连续段内窗口" if final.get('scope') == 'recording'
                         else f"{facts['window_seconds']:g}秒片段")
    result.update(analysis_scope=final.get('scope', 'window'), window_count=final.get('window_count', 1),
                  coverage_plan=final.get('coverage_plan'))
    result["summary"] = (f"按已登记{facts['n_eeg']}道EEG、{facts['sampling_rate_hz']:g}Hz、{scope_description}，"
                         f"建议{len(final['selected_modules'])}个模块和{len(recommended_extras)}个默认可选增强；"
                         f"另有{len(result['optional_methods'])}项可显式探索。计算完成不表示质量合格。")
    return _finish(result, record, submitted)
