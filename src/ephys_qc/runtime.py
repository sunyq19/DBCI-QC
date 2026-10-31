"""Independent method scheduling over immutable, native-clock source windows."""
import gc
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import time

from .annotations import file_sha256
from .planning import build_plan
from .tagging import data_facts
from collections import Counter
from .modules import ModuleContext, run_module, module_specs
# Compatibility names for existing readers, report tools and tests.
from .modules.m02 import read_window as _read_window
from .modules.m09 import waveform as _waveform, render_report as _report


def _extension_status(observed, applicability):
    """An eligibility caveat never downgrades a failed computation to partial."""
    if observed == 'blocked':
        return 'skipped'
    if observed not in {'completed', 'partial'}:
        return 'failed'
    return 'partial' if applicability == 'partial' or observed == 'partial' else 'completed'


def _extension_channel_mapping(channels):
    """Unique adapter names keep repeated labels as distinct source channels."""
    counts = Counter(channel['raw_name'] for channel in channels)
    names = [channel['raw_name'] if counts[channel['raw_name']] == 1 else
             f"{channel['raw_name']} [source {channel['source_index']}]" for channel in channels]
    if len(set(names)) != len(names):
        names = [channel['channel_id'] for channel in channels]
    if len(set(names)) != len(names):
        raise ValueError('Reader channel IDs are not unique')
    return [{'analysis_index': i, 'adapter_name': name, 'channel_id': channel['channel_id'],
             'raw_name': channel['raw_name'], 'source_index': channel['source_index']}
            for i, (channel, name) in enumerate(zip(channels, names))]


def _safe(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_safe(v) for v in value]
    if hasattr(value, "tolist"):
        return _safe(value.tolist())
    if hasattr(value, "item"):
        return _safe(value.item())
    raise TypeError(f"Unsupported result value: {type(value).__name__}")


def _write_json(path, value):
    path.write_text(json.dumps(_safe(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def execute(request, job_dir, emit):
    supplied = request.get('plan') or {} if isinstance(request, dict) else {}
    config = request.get('qc_config', supplied.get('qc_config')) if isinstance(request, dict) else None
    scope = (config or {}).get('scope', request.get('input', {}).get('default_config', {}).get('scope', 'window')) if isinstance(request, dict) else 'window'
    if scope == 'recording':
        from .whole_record import execute_recording
        return execute_recording(request, job_dir, emit)
    return _execute_window(request, job_dir, emit)


def _execute_window(request, job_dir, emit, *, source_context=None, cancel_requested=None):
    if not isinstance(request, dict) or not callable(emit):
        raise ValueError("run_job requires a request and an emit callback")
    record = request["input"]
    supplied = request.get("plan")
    selected = request.get("selected_modules")
    if selected is None and supplied:
        selected = supplied["selected_modules"]
    config = request.get("qc_config", supplied.get("qc_config") if supplied else None)
    plan = build_plan(record, selected, config)
    if supplied and supplied.get("plan_id") != plan["plan_id"]:
        raise ValueError("Submitted plan differs from input, selected modules or configuration")
    # Preserve the caller-visible auto-added list after verifying the stable identity.
    if supplied:
        plan = {**plan, "auto_added_modules": supplied.get("auto_added_modules", [])}
    root = Path(job_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    if (root / "result.json").exists():
        raise FileExistsError("A completed result already exists; use a new job directory")
    artifacts = root / "artifacts"
    artifacts.mkdir(exist_ok=True)
    source = Path(record["source_path"])
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Job outputs must be separate from the original input file")
    result = {"schema_version": "ephys-result/1.3", "plan_id": plan["plan_id"], 'scope': 'window',
              'analysis_profile': plan['analysis_profile'],
              "recording": {"channel_count": 0, "sampling_rate_hz": None,
                            "start_seconds": plan["qc_config"]["selection"]["start_seconds"],
                            "duration_seconds": plan["qc_config"]["selection"]["duration_seconds"]},
              "score": {"value": None, "label": "未校准", "reason": "总分与跨场景权重未校准；执行完成率不表示信号质量。"},
              "modules": [], "review_status": "pending", "source_sha256": None,
              "artifacts": [], "warnings": list(plan["warnings"]), "report_path": "artifacts/report.html",
              "selected_modules": plan["selected_modules"], "qc_config": plan["qc_config"],
              'data_tags': plan['data_tags'], 'method_applicability': plan['method_applicability'], 'extensions': [],
              'input_provenance': plan['input_provenance'], 'input_data_usage': plan['input_data_usage'],
              'input_metadata': plan['input_metadata'], 'input_modality': plan['input_modality'],
              'input_lineage': plan.get('input_lineage', {})}
    state, statuses = {}, {}
    config = plan["qc_config"]
    methods = config["method_config"]
    _write_json(artifacts / "plan.json", plan)
    versions = {}
    for name in ("brainelecqc", "numpy", "scipy", "mne", "fooof", "matplotlib", "pynwb", "hdmf", "h5py"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    method_sources = {}
    from .modalities import DESCRIPTIVE, route
    modality = record.get('modality', 'scalp_eeg')
    ecog = modality == 'ecog'
    descriptive = modality in DESCRIPTIVE
    source_modules = ({name: 'ephys_qc.modules.ecog.' + name for name in ('common', 'm03', 'm04', 'm05')}
                      if ecog else {name: 'brainelecqc.eeg.' + name for name in ('continuity', 'spectral', 'bad_channels', 'events', 'muscle')})
    if modality in {'seeg', 'extracellular'}:
        source_modules = {name: 'ephys_qc.modules.continuous.' + name for name in ('common', 'm03', 'm04', 'm05')}
    for name, module_name in source_modules.items():
        try:
            spec = importlib.util.find_spec(module_name)
            method_sources[name] = {"file": str(spec.origin), "sha256": file_sha256(spec.origin)} if spec and spec.origin else None
        except (ImportError, ValueError, OSError):
            method_sources[name] = None
    from .version import __version__
    environment = {"packages": versions, "implementation": "ephys_qc/" + __version__,
                'analysis_profile': plan['analysis_profile'],
                "adapter": route(modality)["key"] + "_descriptive_measurements" if descriptive else "independent_public_function_calls", "method_sources": method_sources,
                'actual_executed_sources': {}}
    entrypoints = {item['id']: item['entrypoint'].split(':')[0] for item in module_specs(record.get('modality', 'scalp_eeg'))}
    _write_json(artifacts / "environment.json", environment)

    def track_sources(mid):
        names = [entrypoints[mid]]
        if mid in {'M01', 'M02'} and record.get('metadata', {}).get('format') == 'NWB':
            names += ['ephys_qc.readers.nwb_reader', 'ephys_qc.source_selection']
        if ecog and mid in {'M03', 'M04', 'M05'}:
            names += ['ephys_qc.modules.ecog.common', 'ephys_qc.ecog_config']
        if modality in {'seeg', 'extracellular'} and mid in {'M03', 'M04', 'M05'}:
            names += ['ephys_qc.modules.continuous.' + mid.lower(), 'ephys_qc.modules.continuous.common', 'ephys_qc.modalities', 'ephys_qc.ecog_config']
        for name in names:
            spec = importlib.util.find_spec(name)
            if spec and spec.origin:
                entry = environment['actual_executed_sources'].setdefault(name, {
                    'file': str(spec.origin), 'sha256': file_sha256(spec.origin), 'module_ids': []})
                if mid not in entry['module_ids']:
                    entry['module_ids'].append(mid)

    def save(name, payload, row):
        _write_json(artifacts / name, payload)
        row["artifacts"].append(name)

    def record_unrun_extras(mid, row):
        from .extensions import extension_specs
        done = {entry['id'] for entry in result['extensions']}
        for spec in extension_specs():
            id_ = spec['id']
            if spec['module_id'] != mid or id_ not in methods.get('extensions', []) or id_ in done:
                continue
            entry = {'id': id_, 'name': spec['name'], 'module_id': mid, 'status': 'skipped',
                     'reason': '未运行：所属模块或上游未完成。' + row['reason'],
                     'parameters': methods['extension_parameters'][id_],
                     'artifact': mid + '_' + id_ + '.json'}
            save(entry['artifact'], {**entry, 'calculated': False, 'candidates': []}, row)
            result['extensions'].append(entry)
            row['summary'].setdefault('extensions', []).append(entry)

    def run_extras(mid, row):
        from .extensions import extension_specs, evaluate_extension, run_extension
        specs = {s['id']: s for s in extension_specs()}
        facts = data_facts(record, config)
        facts.update(sampling_rate_hz=state['fs'], n_eeg=len(state['channels']),
                     window_seconds=state['recording']['duration_seconds'], verified_voltage=True)
        channel_mapping = _extension_channel_mapping(state['channels'])
        for id_ in methods.get('extensions', []):
            spec = specs[id_]
            if spec['module_id'] != mid:
                continue
            gate = evaluate_extension(id_, facts, methods.get('extension_parameters', {}).get(id_))
            filename = mid + '_' + id_ + '.json'
            entry = {'id': id_, 'name': spec['name'], 'module_id': mid, 'status': 'skipped',
                     'reason': gate['reason'], 'parameters': gate['parameters'], 'artifact': filename}
            try:
                if gate['status'] == 'blocked':
                    detail = {**entry, 'candidates': [], 'calculated': False, 'applicability': gate}
                    if row['status'] == 'completed':
                        row.update(status='partial', reason='已选增强方法有条件不足的未评项；基础检查结果保留。')
                else:
                    emit(mid, 'running', '正在执行可选增强：' + spec['name'])
                    detail = run_extension(id_, state['data'], state['fs'], [c['adapter_name'] for c in channel_mapping],
                                           state['start'], gate['parameters'], facts=facts)
                    observed = detail.get('status', 'failed')
                    # A planning caveat cannot hide an actual calculation failure.
                    entry['status'] = _extension_status(observed, gate['status'])
                    entry['candidate_count'] = len(detail.get('candidates', []))
                    for count_key in ('candidate_interval_count', 'candidate_channel_count', 'candidate_pair_count', 'candidate_epoch_count'):
                        if count_key in detail:
                            entry[count_key] = detail[count_key]
                    entry['reason'] = detail.get('reason', gate['reason'])
                    if gate['status'] == 'partial' and entry['reason'] != gate['reason']:
                        entry['reason'] += '；' + gate['reason']
                    detail['applicability'] = gate
                    detail['context_tags'] = config['context_tags']
                    detail['channel_mapping'] = channel_mapping
                    detail['sample_clock'] = {
                        'seconds_reference': 'selected_input_recording_time',
                        'window_start_seconds': state['start'],
                        'source_start_sample': state['recording']['start_sample'],
                        'source_stop_sample_exclusive': state['recording']['stop_sample'],
                        'sampling_rate_hz': state['fs']}
                    for candidate in detail.get('candidates', []):
                        if candidate.get('start_seconds') is not None and candidate.get('stop_seconds') is not None:
                            candidate['source_start_sample'] = state['recording']['start_sample'] + round((candidate['start_seconds'] - state['start']) * state['fs'])
                            candidate['source_stop_sample_exclusive'] = state['recording']['start_sample'] + round((candidate['stop_seconds'] - state['start']) * state['fs'])
                    if detail.get('calculated') and detail.get('evaluation'):
                        import statistics
                        evaluation = detail['evaluation']
                        entry['evaluation_summary'] = {
                            'median_relative_rms_change': statistics.median(evaluation['relative_rms_change_by_channel']),
                            'interpretation': '处理变化量，不是质量分或伪迹比例',
                            'original_signal_overwritten': False}
                        # A readable comparison accompanies the raw JSON evidence.
                        from .modules.m09 import extension_spectrum
                        image_name = mid + '_' + id_ + '_spectrum.png'
                        try:
                            extension_spectrum(evaluation, artifacts / image_name, spec['name'])
                            row['artifacts'].append(image_name)
                            entry['spectrum_image'] = image_name
                        except Exception as plot_error:
                            detail.setdefault('notes', []).append('PSD图生成失败，数值仍保留：' + str(plot_error))
                    if entry['status'] != 'completed' and row['status'] == 'completed':
                        row.update(status='partial', reason='增强方法存在适用限制或未评项，详见子项。')
            except Exception as error:
                entry.update(status='failed', reason=f'{type(error).__name__}: {error}')
                detail = {**entry, 'calculated': False}
                if row['status'] == 'completed':
                    row.update(status='partial', reason='可选增强执行失败；已完成的基础检查结果保留。')
                result['warnings'].append(spec['name'] + ': ' + entry['reason'])
            save(filename, detail, row)
            result['extensions'].append(entry)
            row['summary'].setdefault('extensions', []).append(entry)

    for node in plan["nodes"]:
        if cancel_requested and cancel_requested():
            from .whole_record import RecordingCancelled
            raise RecordingCancelled('Recording job cancellation requested')
        mid = node["id"]
        row = {"id": mid, "name": node["name"], "status": "skipped", "reason": node["reason"],
               "summary": {}, "duration_seconds": 0.0, "artifacts": []}
        result["modules"].append(row)
        if node["status"] == "skipped":
            record_unrun_extras(mid, row)
            statuses[mid] = "skipped"
            emit(mid, "skipped", row["reason"])
            continue
        blockers = [d for d in node["depends_on"] if statuses.get(d) in {"failed", "skipped"}]
        if blockers and mid not in {"M08", "M09"}:
            row["reason"] = "所需计算未完成：" + ", ".join(blockers)
            record_unrun_extras(mid, row)
            statuses[mid] = "skipped"
            emit(mid, "skipped", row["reason"])
            continue
        emit(mid, "running", "正在执行独立节点")
        started = time.perf_counter()
        row["status"] = "partial" if node["status"] == "partial" else "completed"
        try:
            track_sources(mid)
            run_module(mid, ModuleContext(
                record=record, plan=plan, config=config, state=state, result=result, row=row,
                source=source, root=root, artifacts=artifacts, write_artifact=save,
                source_context=source_context))
            if mid in {'M03', 'M04', 'M05', 'M06'}:
                run_extras(mid, row)
            row["duration_seconds"] = time.perf_counter() - started
        except Exception as error:
            row.update(status="failed", reason=f"{type(error).__name__}: {error}", duration_seconds=time.perf_counter() - started)
            row["summary"] = {"error_type": type(error).__name__, "message": str(error)}
            result["warnings"].append(f"{mid}: {row['reason']}")
            save(mid + "_error.json", row["summary"], row)
            record_unrun_extras(mid, row)
        statuses[mid] = row["status"]
        emit(mid, row["status"], row["reason"])
        # Module-local payloads are released when each handler returns.
        gc.collect()
    if state.get('reader') and not source_context:
        state['reader'].close()
    for entry in environment['actual_executed_sources'].values():
        entry['module_statuses'] = {mid: statuses[mid] for mid in entry['module_ids']}
    _write_json(artifacts / "environment.json", environment)
    result["status"] = "failed" if any(statuses.get(k) == "failed" for k in ("M01", "M02", "M08")) else "partial" if any(v in {"partial", "failed"} for v in statuses.values()) else "completed"
    result["warnings"] = list(dict.fromkeys(result["warnings"]))
    result = _safe(result)
    result["artifacts"] = [{"name": p.name, "bytes": p.stat().st_size,
                            "kind": "image" if p.suffix == ".png" else "json" if p.suffix == ".json" else "report"}
                           for p in sorted(artifacts.iterdir()) if p.is_file() and p.name != "report.html"]
    _report(result, record.get("label", record["id"]), artifacts / "report.html")
    result["artifacts"].append({"name": "report.html", "bytes": (artifacts / "report.html").stat().st_size, "kind": "report"})
    _write_json(root / "result.json", result)
    return result
