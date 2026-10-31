"""Explicit, read-only adapters for the source-reviewed research extensions.

Catalog/planning stays dependency-light. Upstream code is installed separately;
the runtime never downloads code, repairs the input, or changes a quality score.
"""
from copy import deepcopy
import hashlib
import inspect
import math
from pathlib import Path
import warnings

DEFAULTS = {
    'faster_channels': {'threshold_z': 3., 'epoch_seconds': 2., 'max_iter': 1},
    'spikeinterface_bad_channels': {'method': 'mad', 'threshold': 5., 'highpass_hz': 300.,
                                    'chunk_seconds': .3, 'num_chunks': 20, 'seed': 0},
    'fieldtrip_zvalue': {'threshold_z': 4.},
    'asr_bursts': {'cutoff': 20., 'calibration_start_seconds': 0., 'calibration_seconds': 30.,
                   'calibration_confirmed': False, 'highpass_hz': 1., 'window_seconds': 1.},
    'cleanline': {'line_frequency_hz': 50., 'window_seconds': 4., 'step_seconds': 1., 'alpha': .01},
    'zapline_plus': {'line_frequency_hz': 50.},
}
IDS = frozenset(DEFAULTS)


def extension_specs():
    from .research_methods import _ROWS
    result = []
    for row in _ROWS:
        if row['id'] not in IDS:
            continue
        item = deepcopy(row)
        item.update(implementation='available', status='available', optional_extension=True,
                    defaults=deepcopy(DEFAULTS[item['id']]),
                    supported_modalities=list(item['research_modalities']))
        result.append(item)
    return result


def _parameters(identifier, params):
    from .extra_methods import _number, _integer
    if identifier not in IDS:
        raise ValueError('Unknown research extension: ' + identifier)
    if params is not None and (not isinstance(params, dict) or set(params) - set(DEFAULTS[identifier])):
        raise ValueError('Only declared extension parameters are accepted')
    p = {**DEFAULTS[identifier], **deepcopy(params or {})}
    for key in p:
        if key == 'method':
            if p[key] not in {'std', 'mad'}:
                raise ValueError('This adapter supports std/mad only; IBL coherence+psd needs a separately verified geometry adapter')
        elif key == 'calibration_confirmed':
            if type(p[key]) is not bool:
                raise ValueError('calibration_confirmed must be an explicit boolean')
        elif key in {'seed', 'max_iter', 'num_chunks'}:
            p[key] = _integer(p[key], key, 0 if key == 'seed' else 1,
                              2**31 - 1 if key == 'seed' else 10 if key == 'max_iter' else 100)
        else:
            p[key] = _number(p[key], key, zero=key == 'calibration_start_seconds')
    if identifier == 'faster_channels' and not 1 <= p['epoch_seconds'] <= 10:
        raise ValueError('epoch_seconds must be in [1, 10]')
    if identifier == 'spikeinterface_bad_channels' and not .05 <= p['chunk_seconds'] <= 1:
        raise ValueError('chunk_seconds must be in [0.05, 1]')
    if identifier == 'cleanline' and not (0 < p['alpha'] < 1 and 2 <= p['window_seconds'] <= 10
                                         and 0 < p['step_seconds'] < p['window_seconds']):
        raise ValueError('CleanLine requires alpha in (0,1), 2–10s windows and a shorter positive step')
    if identifier == 'asr_bursts' and not (5 <= p['cutoff'] <= 100 and .5 <= p['highpass_hz'] <= 2
                                         and .5 <= p['window_seconds'] <= 2):
        raise ValueError('ASR requires cutoff 5–100, highpass 0.5–2 Hz and statistics window 0.5–2 s')
    return p


def evaluate_extension(identifier, facts, params=None):
    from .extra_methods import _number, _integer, _one_comparison_group
    p = _parameters(identifier, params)
    result = {'status': 'blocked', 'reason': '', 'parameters': p}
    def blocked(reason):
        return {**result, 'reason': reason}
    if not isinstance(facts, dict) or facts.get('verified_voltage') is not True:
        return blocked('必须核实物理单位为V。')
    spec = next(s for s in extension_specs() if s['id'] == identifier)
    if facts.get('modality') not in spec['research_modalities']:
        return blocked('所选模态不在此适配器的执行范围内。')
    try:
        fs = _number(facts.get('sampling_rate_hz'), 'sampling_rate_hz')
        seconds = _number(facts.get('window_seconds'), 'window_seconds')
        count = _integer(facts.get('n_eeg'), 'n_eeg', 1, 384)
    except ValueError as error:
        return blocked(str(error))
    if seconds > 120 or seconds < 1 or count * round(seconds * fs) * 8 > 256 * 1024**2:
        return blocked('研究扩展限1–120秒、256MiB输入；长记录须分窗。')
    if identifier in {'faster_channels', 'asr_bursts', 'zapline_plus'}:
        if count < 8 or count > 128 or seconds < 10:
            return blocked('本适配器要求8–128道及至少10秒。')
        if facts.get('reference_scheme') not in {'common_reference', 'linked_ears'} or not _one_comparison_group(facts.get('comparison_groups'), count):
            return blocked('需核实共同/连接耳参考，并声明覆盖所选通道的同一比较组。')
    if identifier == 'faster_channels':
        if fs < 100 or seconds // p['epoch_seconds'] < 5:
            return blocked('FASTER本版要求采样率至少100Hz及5个完整固定段。')
        if not math.isclose(round(p['epoch_seconds'] * fs), p['epoch_seconds'] * fs, abs_tol=1e-8):
            return blocked('固定段必须对应整数采样点。')
    elif identifier == 'spikeinterface_bad_channels':
        if facts.get('stream_band') != 'ap':
            return blocked('本版只接AP流；不把AP高通和阈值用于LF或未知频带。')
        if count < 8 or fs <= 2 * p['highpass_hz'] or seconds < 2 * p['chunk_seconds']:
            return blocked('需至少8道、两个抽样窗，且采样率支持高通频率。')
        # Per-shank grouping is mandatory even for median-based std/mad.
        groups = facts.get('probe_shanks')
        if not isinstance(groups, list) or len(groups) != count or any(type(g) is not int or g < 0 for g in groups):
            return blocked('缺少所选通道的原始shank映射；不跨探针杆比较。')
        if any(groups.count(g) < 8 for g in set(groups)):
            return blocked('各shank至少需8个选中通道。')
    elif identifier == 'asr_bursts':
        if not p['calibration_confirmed']:
            return blocked('请先复核校准段，再明确设置calibration_confirmed=true；不自动假定前30秒干净。')
        if p['calibration_seconds'] < 30 or p['calibration_start_seconds'] + p['calibration_seconds'] > seconds:
            return blocked('校准段须至少30秒，且完整位于当前窗口内。')
        if any(not math.isclose(round(p[k]*fs), p[k]*fs, abs_tol=1e-8) for k in ('calibration_start_seconds', 'calibration_seconds')):
            return blocked('校准段起点和长度须对应整数原生采样点。')
        if p['window_seconds'] * fs < 1.5 * count:
            return blocked('ASR统计窗采样点数须至少为通道数的1.5倍。')
        if fs not in {100, 128, 200, 256, 300, 500, 512}:
            return blocked('当前Octave路径只使用上游预置谱加权滤波器；此采样率没有预置系数，不自动重采样。')
        if facts.get('scope') == 'recording':
            return blocked('ASR校准段按当前片段定位；尚不支持整记录自动分窗重校准。')
    elif identifier in {'cleanline', 'zapline_plus'}:
        freq = p['line_frequency_hz']
        lowpass = facts.get('preprocessing_lowpass_hz')
        if freq <= 3 or freq + 3 >= fs / 2 or (lowpass is not None and freq + 3 >= lowpass):
            return blocked('目标工频及邻带超出可测频带或已知低通范围。')
        if identifier == 'cleanline':
            if seconds < 2 * p['window_seconds']:
                return blocked('CleanLine至少需要两个分析窗。')
            if any(not math.isclose(round(p[k]*fs), p[k]*fs, abs_tol=1e-8) for k in ('window_seconds', 'step_seconds')):
                return blocked('窗长和步长须精确对应整数采样点。')
        elif seconds < 32 or fs != round(fs):
            return blocked('Zapline-plus本版至少32秒，采样率须为整数。')
    elif identifier == 'fieldtrip_zvalue' and seconds < 10:
        return blocked('FieldTrip差分z值本版至少需要10秒以估计分布。')
    return {**result, 'status': 'partial', 'reason': '可运行研究性评估；阈值未校准为质量标准，结果须人工复核。'}


def _source(identifier, function, package):
    from importlib.metadata import version
    spec = next(s for s in extension_specs() if s['id'] == identifier)
    location = inspect.getsourcefile(inspect.unwrap(function))
    return {**spec['source'], 'function': function.__module__ + '.' + function.__name__,
            'version': version(package), 'implementation_sha256': hashlib.sha256(Path(location).read_bytes()).hexdigest(),
            'adapter_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'packages': {k: version(k) for k in ('numpy', 'scipy', package, *(['mne'] if package == 'mne-faster' else []))}}


def run_extension(identifier, data_volts, sfreq, channel_names, start_seconds, parameters, *, facts=None):
    import numpy as np
    from .extra_methods import _number, _data_hash
    p = _parameters(identifier, parameters)
    fs = _number(sfreq, 'sfreq')
    start = _number(start_seconds, 'start_seconds', zero=True)
    original = np.asarray(data_volts)
    if original.ndim != 2 or min(original.shape) < 1 or original.dtype.kind not in 'fiu' or not np.all(np.isfinite(original)):
        raise ValueError('Expected finite, real channel-by-sample voltage')
    names = list(channel_names) if not isinstance(channel_names, (str, bytes)) else []
    if len(names) != len(original) or any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
        raise ValueError('Distinct nonempty channel names must match input rows')
    data = np.asarray(original, dtype=float)
    if not np.isfinite(data).all() or not math.isfinite(start + data.shape[1] / fs):
        raise ValueError('Float64 voltage and source stop time must be finite')
    verdict = evaluate_extension(identifier, facts, p)
    result = {'schema_version': 'ephys-extension-result/1.0', 'extension_id': identifier,
              'status': verdict['status'], 'reason': verdict['reason'], 'parameters': p,
              'source': next(s for s in extension_specs() if s['id'] == identifier)['source'],
              'data_sha256': _data_hash(data), 'channel_names': names, 'unit': 'V',
              'range': {'start_seconds': start, 'stop_seconds': start + data.shape[1] / fs,
                        'duration_seconds': data.shape[1]/fs, 'sampling_rate_hz': fs, 'n_samples': data.shape[1]},
              'candidates': [], 'notes': [], 'automatic_actions': [], 'input_unchanged': True,
              'review_status': 'pending', 'calculated': False, 'candidate_channel_count': 0, 'candidate_interval_count': 0}
    if verdict['status'] == 'blocked':
        return result
    if identifier in {'asr_bursts', 'cleanline', 'zapline_plus', 'fieldtrip_zvalue'}:
        from .external_runtime import availability
        problem = availability(identifier)
        if problem:
            return {**result, 'status': 'blocked', 'reason': problem}
    else:
        import importlib.util
        package = 'mne_faster' if identifier == 'faster_channels' else 'spikeinterface'
        if importlib.util.find_spec(package) is None:
            return {**result, 'status': 'blocked', 'reason': '执行环境缺少依赖：' + package}
    if (facts['n_eeg'] != len(data) or not math.isclose(facts['sampling_rate_hz'], fs, abs_tol=1e-8)
            or not math.isclose(facts['window_seconds'], data.shape[1]/fs, rel_tol=0, abs_tol=.5/fs)):
        return {**result, 'status': 'blocked', 'reason': '数据事实与实际数组不一致。'}
    if np.any(np.std(data, axis=1) == 0) and identifier != 'spikeinterface_bad_channels':
        return {**result, 'status': 'blocked', 'reason': '所选通道含恒值，分布或协方差退化；请先复核基础连续性结果。'}
    def channel(i, kind, **extra):
        return {'kind': kind, 'localization': 'channel_only', 'scope': 'channel',
                'channel_index': int(i), 'channel_name': names[i], 'start_seconds': None, 'stop_seconds': None,
                'analysis_range': [start, result['range']['stop_seconds']], **extra}
    caught = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if identifier == 'faster_channels':
                import mne
                from mne_faster import find_bad_channels
                from .extra_methods import _epochs
                segmented, segmentation = _epochs(data, fs, p['epoch_seconds'], start)
                epochs = mne.EpochsArray(segmented, mne.create_info(names, fs, 'eeg'), verbose='ERROR')
                measurable_line = fs > 120 and (facts.get('preprocessing_lowpass_hz') is None or facts['preprocessing_lowpass_hz'] > 60)
                metrics = ['variance', 'correlation', 'hurst', 'kurtosis'] + (['line_noise'] if measurable_line else [])
                result['source'] = _source(identifier, find_bad_channels, 'mne-faster')
                out = find_bad_channels(epochs, thres=p['threshold_z'], max_iter=p['max_iter'],
                                       use_metrics=metrics, eeg_ref_corr=False, return_by_metric=True)
                if set(out) != set(metrics) or any(n not in names for v in out.values() for n in v):
                    raise ValueError('Unexpected FASTER channel mapping')
                if any('invalid' in str(w.message).lower() or 'divide by zero' in str(w.message).lower() for w in caught):
                    raise ValueError('Degenerate FASTER statistic; no empty-success interpretation')
                result.update(by_metric=out, segmentation=segmentation,
                              excluded_metrics=[] if measurable_line else ['line_noise: requires both 50 and 60 Hz within measurable bandwidth'])
                result['candidates'] = [channel(i, 'faster_channel_candidate', metrics=[k for k, v in out.items() if n in v])
                                        for i, n in enumerate(names) if any(n in v for v in out.values())]
            elif identifier == 'spikeinterface_bad_channels':
                from spikeinterface import NumpyRecording
                from spikeinterface.preprocessing import detect_bad_channels
                result['source'] = _source(identifier, detect_bad_channels, 'spikeinterface')
                labels = ['unassessed'] * len(names)
                shanks = facts['probe_shanks']
                for shank in sorted(set(shanks)):
                    indices = [i for i, s in enumerate(shanks) if s == shank]
                    values = data[indices].T.copy() * 1e6
                    if np.median(np.std(values, axis=0)) == 0:
                        raise ValueError('Median channel dispersion is zero in a shank')
                    recording = NumpyRecording(values, fs, channel_ids=np.array(indices))
                    recording.set_channel_gains(1.)
                    recording.set_channel_offsets(0.)
                    bads, detected = detect_bad_channels(recording, method=p['method'], std_mad_threshold=p['threshold'],
                        highpass_filter_cutoff=p['highpass_hz'], chunk_duration_s=p['chunk_seconds'],
                        num_random_chunks=p['num_chunks'], seed=p['seed'])
                    if len(detected) != len(indices) or not set(detected) <= {'good', 'noise'}:
                        raise ValueError('Unexpected SpikeInterface labels')
                    for i, value in zip(indices, detected):
                        labels[i] = str(value)
                result['channel_labels'] = [{'channel_index': i, 'channel_name': n, 'shank': shanks[i], 'label': labels[i]}
                                            for i, n in enumerate(names)]
                result['candidates'] = [channel(i, 'spikeinterface_noise_candidate', label=v) for i, v in enumerate(labels) if v == 'noise']
                result['notes'].append('std/mad只识别高离散度noise候选；good仅表示未超此阈值，不代表排除dead/out或单元合格。每个shank独立高通与抽样。')
            else:
                from .external_runtime import run_external
                result.update(run_external(identifier, data, fs, names, start, p))
        result['calculated'] = True
        result['status'] = 'completed'
        result['candidate_channel_count'] = len({c['channel_index'] for c in result['candidates'] if c.get('channel_index') is not None})
        result['candidate_interval_count'] = sum(c.get('start_seconds') is not None for c in result['candidates'])
    except Exception as error:
        result.update(status='failed', reason=f'{type(error).__name__}: {error}', calculated=False, candidates=[])
    result['warnings'] = list(dict.fromkeys(str(w.message) for w in caught))
    if _data_hash(original) != result['data_sha256']:
        raise RuntimeError('Extension modified its source input')
    return result
