"""Pure-standard-library planning; no signal or quality-label access."""
import copy
import hashlib
import json
import math
from collections import Counter
from .tagging import validate_context, data_facts, describe_data
from .method_registry import methods as method_catalog, evaluate_methods
from .readers import SUPPORTED_FORMATS
from .modalities import ROUTES, DESCRIPTIVE, route, validate_descriptive_methods, validate_analysis_channels


_SPECS = [
    ("M01", "数据接入与结构核验", "接入", [], True,
     "按注册读取器核对主文件与伴随文件指纹、格式结构、采样流与连续段。", ["已登记原始文件或配套文件组"], ["来源指纹", "技术头核对"],
     ["支持连续EDF/BDF、BrainVision、EEGLAB与单文件FIF；只有已确认头皮EEG可执行本质控，结构可读不等于科学有效。"]),
    ("M02", "数据画像与检查计划", "计划", ["M01"], True,
     "冻结选道、原生采样时间窗、辅助导联和参考比较组。", ["技术元信息", "显式配置"], ["冻结配置", "原始时钟选区"],
     ["单窗最多120秒；整记录按原生连续段分块；不自动重参考或跨采样流对齐。"]),
    ("M03", "信号完整性", "检查", ["M02"], False,
     "检查非有限样本、恒值与端点平台；可选MNE平线和autoreject全局阈值。", ["原始电压", "逐道标定"], ["连续性候选", "样本区间", "可选固定段幅度阈值"],
     ["尚未实现一般重复数据块和断续检测；平台是待复核候选。"]),
    ("M04", "频谱与干扰", "检查", ["M02"], False,
     "独立计算Welch PSD、Thomson工频及FOOOF频谱特征。", ["原始电压", "采样率与分析范围"], ["PSD", "工频候选", "频谱拟合"],
     ["未实现专门漂移判定；分析范围会改变工频多重比较族。"]),
    ("M05", "坏通道候选", "检查", ["M02"], False,
     "计算PREP非空间分项；可选MNE桥接和LOF，按各自参考及通道条件运行。", ["原始电压", "明确比较组", "扩展所需参考构型"], ["通道候选", "分项指标", "可选电极对候选"],
     ["空间预测和插值尚未接入；桥接、LOF须单独选择；来源坏道标签不参与检测。", "基础方法每组至少4道是当前实现门槛；扩展另有门槛，都不是国际共识。"]),
    ("M06", "生理伪迹线索", "检查", ["M02", "M03"], False,
     "独立计算ECG/EOG锁时线索和高频突发；使用M03区间作为肌电保护区。", ["EEG", "可选ECG/EOG/EMG", "M03连续性候选"], ["辅助事件", "高频突发", "EMG支持状态"],
     ["缺辅助导联时不能确认相应生理伪迹；不执行ICA或自动清理。"]),
    ("M07", "状态和事件检查", "检查", ["M02"], False,
     "读取任务、睡眠分期或临床事件表，核对范围并保留记录原始时间。", ["明确类型的标注文件"], ["选区事件", "阶段覆盖或临床事件时长", "标注指纹"],
     ["任务、分期和发作标注都不是质量真值；外部同步准确性未验证。", "任务事件TSV使用明确的event_name字段；支持登记的来源转换表，非通用BIDS解析器。"]),
    ("M08", "分项评价与可比性", "汇总", [], True,
     "汇总已选模块的执行状态、观察量和未评原因。", ["模块结果或未评状态"], ["分项摘要", "未校准总分说明"],
     ["总分未校准，固定为null；执行完成率不作为质量评分。"]),
    ("M09", "报告与人工复核", "报告", ["M08"], True,
     "生成本地HTML、波形PNG和结构化证据，等待人工复核。", ["分项结果", "原始选区"], ["HTML报告", "波形PNG", "结果JSON"],
     ["检测报告保持不变；人工意见在工作台独立留版本，不自动删除原数据。"]),
]


def catalog(modality='scalp_eeg'):
    children = method_catalog(modality)
    rows = [{"id": i, "name": name, "stage": stage, "description": description,
             "inputs": inputs.copy(), "outputs": outputs.copy(), "dependencies": dependencies.copy(),
             "required": required, "limitations": limitations.copy(),
             "evidence": "独立调度适配；方法级与数据级验证范围需分别核对，执行成功不代表质量合格。",
             "methods": [copy.deepcopy(method) for method in children if method['module_id'] == i]}
            for i, name, stage, dependencies, required, description, inputs, outputs, limitations in _SPECS]
    if modality in DESCRIPTIVE:
        from .descriptive_catalog import module_overrides
        for row in rows:
            row.update(selectable=True, implementation='available')
            row.update(module_overrides(row['id'], modality))
    return rows


def _finite_json(value, path="config"):
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _finite_json(item, f"{path}[{i}]")
        return
    if isinstance(value, dict) and all(isinstance(k, str) for k in value):
        for key, item in value.items():
            _finite_json(item, f"{path}.{key}")
        return
    raise ValueError(f"{path} must contain JSON values")


def _merge(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        result[key] = _merge(result[key], value) if key not in {"reference_indices", "comparison_groups"} and isinstance(value, dict) and isinstance(result.get(key), dict) else copy.deepcopy(value)
    return result


def _number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite numeric")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{name} must be {'positive' if positive else 'nonnegative'}")
    return float(value)


def build_plan(input_record, selected_modules=None, qc_config=None):
    if not isinstance(input_record, dict):
        raise ValueError("input_record requires a stable id")
    if qc_config is not None and not isinstance(qc_config, dict):
        raise ValueError("qc_config must be an object")
    default = input_record.get('default_config', {})
    scope = (qc_config or {}).get('scope', default.get('scope', 'window') if isinstance(default, dict) else 'window')
    if scope == 'recording':
        from .whole_record import build_recording_plan
        return build_recording_plan(input_record, selected_modules, qc_config)
    if scope != 'window':
        raise ValueError("scope must be window or recording")
    return _build_window_plan(input_record, selected_modules, qc_config)


def _build_window_plan(input_record, selected_modules=None, qc_config=None):
    if not isinstance(input_record, dict) or not input_record.get("id"):
        raise ValueError("input_record requires a stable id")
    # Legacy registered jobs predate the explicit modality field. New intake
    # requires confirmation; an explicitly different modality cannot bypass it.
    modality = input_record.get('modality', 'scalp_eeg')
    if modality not in ROUTES:
        raise ValueError('请确认已接入的分析路线：头皮EEG、ECoG、sEEG或Neuropixels原始AP/LF。')
    if input_record.get('metadata', {}).get('format', 'EDF') not in SUPPORTED_FORMATS:
        raise ValueError('当前执行器只支持已注册并核验的读取格式。')
    if input_record.get('metadata', {}).get('format', 'EDF') not in {'EDF', 'EDF+'} and input_record.get('modality') not in ROUTES:
        raise ValueError('新增格式必须先明确确认支持的模态，不能仅按文件类型推定。')
    if qc_config is not None and not isinstance(qc_config, dict):
        raise ValueError("qc_config must be an object")
    default = input_record.get("default_config", {})
    if not isinstance(default, dict):
        raise ValueError("default_config must be an object")
    config = _merge(default, qc_config or {})
    _finite_json(config)
    if set(config) - {"selection", "method_config", "feature_config", "policy_config", "context_tags", "scope", "recording_options"}:
        raise ValueError("Unknown QC configuration fields")
    if config.get('scope', 'window') != 'window':
        raise ValueError('Window planner requires scope=window')
    if 'recording_options' in config:
        from .whole_record import validate_recording_options
        config['recording_options'] = validate_recording_options(config['recording_options'])
    config['context_tags'] = validate_context(input_record, config.get('context_tags'))
    if config.get("feature_config") or config.get("policy_config"):
        raise ValueError("Nonempty feature_config/policy_config belongs to the old whole-pipeline API and is not supported by independent modules")
    selection = config.setdefault("selection", {})
    if not isinstance(selection, dict) or set(selection) - {"eeg_indices", "reference_indices", "start_seconds", "duration_seconds", "stream_id", "segment_id"}:
        raise ValueError("Invalid selection fields")
    meta = input_record.get("metadata", {})
    from .source_selection import validate_frozen_stream
    validate_frozen_stream(meta, selection)
    channels = meta.get("channels", [])
    if not isinstance(channels, list) or not channels:
        raise ValueError("metadata.channels is required for a reviewed selection")
    by_index = {c.get("index", c.get("source_index")): c for c in channels if isinstance(c, dict)}
    indices = selection.get("eeg_indices")
    if not isinstance(indices, list) or not indices or any(type(i) is not int or i not in by_index for i in indices) or len(set(indices)) != len(indices):
        raise ValueError("eeg_indices must contain distinct registered source indices")
    incompatible = {'seeg', 'ecog', 'neuropixels', 'dbs', 'mag', 'grad', 'ref_meg', 'stim', 'fnirs_cw_amplitude', 'hbo', 'hbr'}
    if modality == 'scalp_eeg':
        if any(by_index[i].get('channel_type', 'unknown') in incompatible for i in indices):
            raise ValueError('选中通道包含已声明的非头皮EEG类型，不能套用头皮EEG质控。')
    else:
        validate_analysis_channels(meta, indices, modality)
    refs = selection.setdefault("reference_indices", {})
    if not isinstance(refs, dict) or set(refs) - {"ecg", "eog", "emg"}:
        raise ValueError("reference_indices accepts ecg/eog/emg only")
    if any(type(i) is not int or i not in by_index or i in indices for i in refs.values()):
        raise ValueError("Auxiliary source indices must exist and must not overlap EEG")
    if len(set(refs.values())) != len(refs):
        raise ValueError("A single auxiliary channel cannot silently serve multiple roles")
    voltage_units = {'V', 'mV', 'uV', 'µV', 'μV', 'nV'}
    if any(by_index[i].get('unit') not in voltage_units | ({None} if modality == 'scalp_eeg' else set()) for i in indices + list(refs.values())):
        raise ValueError('所选 EEG 和辅助通道必须具有已核验的电压单位。')
    duration = _number(meta.get("duration_seconds"), "metadata.duration_seconds", True)
    start = _number(selection.get("start_seconds", 0), "start_seconds")
    length = _number(selection.get("duration_seconds", min(120.0, duration - start)), "duration_seconds", True)
    if length > 120:
        raise ValueError("The initial workbench supports windows of at most 120 seconds")
    if start + length > duration + 1e-9:
        raise ValueError("Selected range exceeds the recording duration")
    selection.update(start_seconds=start, duration_seconds=length)
    rates = {_number(by_index[i].get("sampling_rate_hz"), "sampling_rate_hz", True) for i in indices + list(refs.values())}
    if len(rates) != 1:
        raise ValueError("EEG and auxiliary channels must share one native sample clock; no automatic resampling")
    fs = next(iter(rates))
    segments = meta.get('continuous_segments')
    if segments is not None:
        if not any(s['recording_start_seconds'] <= start and start + length <=
                   s['recording_start_seconds'] + (s['stop_sample'] - s['start_sample']) / fs + 1e-9 for s in segments):
            raise ValueError('分析选区必须位于同一个原生连续段，不能跨越文件声明的断点或采集缺口。')
    if round(length * fs) < 1 or (len(indices) + len(refs)) * round(length * fs) * 8 > 256 * 1024 * 1024:
        raise ValueError("Selected window is empty or exceeds the 256 MiB input budget")
    methods = config.setdefault("method_config", {})
    if modality in DESCRIPTIVE:
        methods = config['method_config'] = validate_descriptive_methods(methods, modality, meta)
        labels, minimum = [], 4
    else:
        if not isinstance(methods, dict) or set(methods) - {"comparison_groups", "continuity", "spectral", "bad_channels", "events", "muscle", "extensions", "extension_parameters"}:
            raise ValueError("Invalid method_config fields")
        for key, value in methods.items():
            if key not in {"comparison_groups", "extensions"} and not isinstance(value, dict):
                raise ValueError(f"method_config.{key} must be an object")
        minimum = methods.get("bad_channels", {}).get("min_group_channels", 4)
        if type(minimum) is not int or minimum < 4:
            raise ValueError("bad_channels.min_group_channels must be an integer >= 4")
        groups = methods.get("comparison_groups")
        if groups is not None:
            if isinstance(groups, dict) and set(groups) != {f"{input_record['id']}:ch:{i}" for i in indices}:
                raise ValueError("comparison_groups mapping keys must match stable reader channel IDs: <input-id>:ch:<source-index>")
            labels = list(groups.values()) if isinstance(groups, dict) else groups
            if not isinstance(labels, list) or len(labels) != len(indices) or any(not isinstance(g, str) or not g.strip() for g in labels):
                raise ValueError("comparison_groups must declare one nonempty group for each selected EEG channel")
        else:
            labels = []
    from .extensions import extension_specs, evaluate_extension
    extra_specs = {item['id']: item for item in extension_specs()
                   if modality in item.get('research_modalities', ['scalp_eeg'])}
    extras = methods.setdefault('extensions', [])
    if not isinstance(extras, list) or any(not isinstance(item, str) or item not in extra_specs for item in extras):
        raise ValueError('extensions只能选择已接入的可选方法。')
    methods['extensions'] = sorted(set(extras))
    supplied_params = methods.setdefault('extension_parameters', {})
    if not isinstance(supplied_params, dict):
        raise ValueError('extension_parameters must be an object')
    if set(supplied_params) - set(extra_specs):
        raise ValueError('存在未接入方法的参数。')
    facts = data_facts(input_record, config)
    for extension in sorted(set(extras) | set(supplied_params)):
        gate = evaluate_extension(extension, facts, supplied_params.get(extension))
        supplied_params[extension] = gate['parameters']
    modules = catalog(modality)
    known = {m["id"]: m for m in modules}
    if selected_modules is None:
        requested = set(known)
    else:
        if not isinstance(selected_modules, list) or any(not isinstance(m, str) or m not in known for m in selected_modules):
            raise ValueError("selected_modules must contain known module IDs")
        requested = set(selected_modules)
    selected = requested | {m["id"] for m in modules if m["required"]}
    selected |= {extra_specs[extension]['module_id'] for extension in extras}
    while True:
        extended = selected | {d for m in selected for d in known[m]["dependencies"]}
        if extended == selected:
            break
        selected = extended
    nodes, warnings = [], []
    for module in modules:
        mid = module["id"]
        dependencies = module["dependencies"].copy()
        if mid == "M08":
            dependencies = [m["id"] for m in modules if m["id"] in selected and m["id"] not in {"M08", "M09"}]
        status, reason = "ready", "符合当前运行入口条件；结果仍待人工复核"
        if mid not in selected:
            status, reason = "skipped", "用户未选择此模块"
        elif modality in DESCRIPTIVE and mid == 'M06' and 'fieldtrip_zvalue' not in extras:
            status = 'skipped'
            reason = ('未选择可选区间检测；生理伪迹分类未运行。' if modality in {'ecog', 'seeg'} else
                      route(modality)['label'] + '伪迹方法尚未接入；不迁移头皮ECG/EOG/肌电阈值。')
        elif modality in DESCRIPTIVE and mid == 'M04' and length < methods[route(modality)['key']]['psd_window_seconds']:
            status, reason = 'partial', '选区短于所设PSD窗长；实际窗长与不可测范围将明确记录。'
        elif modality == "scalp_eeg" and mid == "M05" and (not labels or min(Counter(labels).values()) < minimum):
            status, reason = "partial", "参考组未声明或部分组不足4道；保留描述量，相关组的队列阈值不启用"
        elif modality == "scalp_eeg" and mid == "M05" and fs <= 100:
            status, reason = "partial", "采样率不高于100 Hz，高频分项不可评"
        elif modality == "scalp_eeg" and mid == "M06" and (set(refs) != {"ecg", "eog", "emg"} or length < 10 or min(100, .45 * fs) - 30 < 20):
            status, reason = "partial", "部分辅助导联、时长或有效频带不足；可计算的线索保留，缺失项不计为合格"
        elif modality == "scalp_eeg" and mid == "M04" and length < 10:
            status, reason = "partial", "短于10秒，部分谱拟合不可评"
        elif mid == "M07" and not input_record.get("annotation"):
            status, reason = "skipped", "没有登记事件或状态标注；不推断任务或睡眠状态"
        elif mid == "M07" and input_record["annotation"].get("format") not in {"sleep_stages_tsv", "bids_events_tsv", "clinical_events_tsv"}:
            status, reason = "skipped", "标注格式未接入，不能作为事件或质量真值"
        if mid in selected and status != "ready":
            warnings.append(f"{mid}: {reason}")
        nodes.append({"id": mid, "name": module["name"], "status": status, "reason": reason, "depends_on": dependencies})
    if modality in DESCRIPTIVE:
        warnings.append(route(modality)['label'] + '基础路线只提供完整性、频谱和触点描述；不以头皮阈值、高频或病理活动判坏。')
    applicability = evaluate_methods(input_record, config, selected)
    data_tags = describe_data(input_record, config)
    for method in applicability:
        if method['id'] in extras and method['status'] in {'blocked', 'partial'}:
            warnings.append(f"{method['name']}: {method['reason']}")
    provenance = copy.deepcopy(input_record.get('provenance', {}))
    data_usage = copy.deepcopy(input_record.get('data_usage', {}))
    input_metadata = copy.deepcopy(meta)
    # Public plans keep package-relative file identities, never internal paths.
    if isinstance(input_metadata.get('source_files'), list):
        input_metadata['source_files'] = [{k: v for k, v in item.items() if k != 'path'}
                                          for item in input_metadata['source_files']]
    input_modality = {'value': input_record.get('modality', 'unknown'), 'source': input_record.get('modality_source')}
    lineage = {key: copy.deepcopy(input_record[key]) for key in ('record_family', 'record_revision', 'parent_input_id') if key in input_record}
    fingerprint = {"version": "ephys-plan/1.3", "input_id": input_record["id"], 'input_lineage': lineage,
                   'modality': input_record.get('modality'), 'modality_source': input_record.get('modality_source'),
                   "source_path": input_record.get("source_path"), "expected_sha256": input_record.get("expected_sha256"),
                   'expected_source_files': sorted(input_record.get('expected_source_files', []), key=lambda f: f['path']),
                   'input_metadata': input_metadata, 'input_modality': input_modality,
                   "profile_id": input_record.get("profile_id"), "duration_seconds": duration,
                   "channels": [{"index": i, "name": by_index[i].get("name"), "sampling_rate_hz": by_index[i].get("sampling_rate_hz"), 'unit': by_index[i].get('unit')} for i in indices + [refs[k] for k in sorted(refs)]],
                   "annotation": input_record.get("annotation"), "preprocessing": input_record.get('preprocessing'),
                   'data_facts': facts, 'data_tags': data_tags, 'method_applicability': applicability,
                   'input_provenance': provenance, 'input_data_usage': data_usage,
                   "selected_modules": sorted(selected), "qc_config": config}
    _finite_json(fingerprint, "plan_identity")
    identity = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {"schema_version": "ephys-plan/1.3", "plan_id": identity,
            'analysis_profile': route(modality)['profile'], 'scope': 'window', 'input_lineage': lineage,
            "selected_modules": sorted(selected), "auto_added_modules": sorted(selected - requested),
            "qc_config": config, "nodes": nodes,
            "edges": [{"from": d, "to": n["id"]} for n in nodes if n["id"] in selected for d in n["depends_on"] if d in selected],
            "warnings": warnings, 'data_tags': data_tags, 'method_applicability': applicability,
            'input_provenance': provenance, 'input_data_usage': data_usage,
            'input_metadata': input_metadata, 'input_modality': input_modality}
