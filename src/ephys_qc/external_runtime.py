"""Bounded Octave subprocesses around separately installed upstream MATLAB code.

Configuration is administrator-owned, never accepted from an upload or job.
No source is fetched at execution time. Local compatibility shims are recorded.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[2]
ENTRYPOINTS = {'asr_bursts': ('clean_rawdata', 'asr_calibrate.m'),
               'cleanline': ('cleanline', 'cleanLineNoise.m'),
               'zapline_plus': ('zapline-plus', 'clean_data_with_zapline_plus.m'),
               'fieldtrip_zvalue': ('fieldtrip', 'ft_artifact_zvalue.m')}


def settings():
    path = Path(os.environ.get('DBCI_QC_METHODS_CONFIG', REPO / '.local/qc-methods.json'))
    config = json.loads(path.read_text())
    if not isinstance(config, dict) or set(config) != {'octave', 'source_root', 'commits', 'signal_sha256'}:
        raise ValueError('Invalid trusted method-runtime configuration')
    return config


def availability(identifier):
    try:
        c = settings()
        root = Path(c['source_root'])
        needed = [root / ENTRYPOINTS[identifier][0] / ENTRYPOINTS[identifier][1],
                  root / 'signal-1.4.8/inst/pwelch.m']
        if identifier == 'cleanline':
            needed.append(root / 'fieldtrip/external/stats/finv.m')
        if not os.access(c['octave'], os.X_OK) or any(not p.is_file() for p in needed):
            return '外部执行器或上游源码未安装；请按运行环境文档配置。'
    except (OSError, ValueError, KeyError, TypeError):
        return '尚未配置受信任的Octave运行环境；该方法不可在当前环境执行。'
    return None


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(c, identifier):
    from importlib.metadata import version
    from .research_runtime import extension_specs
    spec = next(s for s in extension_specs() if s['id'] == identifier)
    names = {ENTRYPOINTS[identifier][0]}
    if identifier == 'cleanline':
        names.add('fieldtrip')
    revisions = {}
    for name in names:
        root = Path(c['source_root']) / name
        rev = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True, timeout=10).stdout.strip()
        dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'], capture_output=True, text=True, check=True, timeout=15).stdout
        if c['commits'].get(name) != rev or dirty.strip():
            raise ValueError('Upstream checkout changed; revalidate the pinned runtime: ' + name)
        revisions[name] = rev
    if _digest(Path(c['source_root']) / 'signal-1.4.8.tar.gz') != c['signal_sha256']:
        raise ValueError('Signal package archive checksum changed')
    import tarfile
    with tarfile.open(Path(c['source_root']) / 'signal-1.4.8.tar.gz') as archive:
        for member in archive:
            if member.isfile() and member.name.startswith('signal-1.4.8/inst/'):
                installed = Path(c['source_root']) / member.name
                if not installed.is_file() or _digest(installed) != hashlib.sha256(archive.extractfile(member).read()).hexdigest():
                    raise ValueError('Extracted signal dependency changed: ' + member.name)
    package, entry = ENTRYPOINTS[identifier]
    return {**spec['source'], 'function': entry[:-2], 'version': revisions[package], 'upstream_commits': revisions,
            'implementation_sha256': _digest(Path(c['source_root']) / package / entry),
            'adapter_sha256': _digest(__file__), 'engine': 'GNU Octave',
            'packages': {k: version(k) for k in ('numpy', 'scipy')},
            'compatibility': 'dbci-octave-compat/1; see docs/optional-methods-runtime.md',
            'signal_archive_sha256': c['signal_sha256']}


def run_external(identifier, data, fs, names, start, params):
    import numpy as np
    from scipy.io import savemat, loadmat
    from scipy.signal import butter, sosfiltfilt, welch
    from scipy.signal.windows import dpss
    from .extra_methods import _data_hash
    c = settings()
    source = _source(c, identifier)
    wrapper = Path(__file__).with_name('octave')
    source['wrapper_files'] = {str(p.relative_to(wrapper)): _digest(p) for p in sorted(wrapper.rglob('*.m'))}
    # Octave's MAT-v5 string reader can truncate UTF-8 paths/labels. Paths
    # travel through the environment; stable ASCII row labels stay internal.
    payload = {'X': np.array(data, copy=True), 'fs': fs,
               'names': np.array([f'row_{i}' for i in range(len(names))], dtype=object),
               'p': params, 'mode': identifier}
    preprocessing = None
    if identifier == 'asr_bursts':
        sos = butter(4, params['highpass_hz'], 'highpass', fs=fs, output='sos')
        payload['X'] = sosfiltfilt(sos, data, axis=1)
        a = round(params['calibration_start_seconds']*fs)
        b = a + round(params['calibration_seconds']*fs)
        rank = int(np.linalg.matrix_rank(payload['X'][:, a:b]))
        if rank < len(names):
            raise ValueError('ASR covariance is rank deficient; do not silently repair or drop channels')
        payload.update(calibration_first=a + 1, calibration_last=b)
        preprocessing = {'kind': 'copy_only_zero_phase_butterworth', 'order': 4,
                         'highpass_hz': params['highpass_hz'], 'sos': sos.tolist(),
                         'evaluation_input_sha256': _data_hash(payload['X']),
                         'calibration': {'source_clock_start_seconds': start+a/fs, 'source_clock_stop_seconds': start+b/fs,
                                         'start_sample_in_window': a, 'stop_sample_in_window_exclusive': b,
                                         'rank': rank, 'sha256': _data_hash(payload['X'][:, a:b]),
                                         'confirmation': 'explicit_caller_selection_not_clean_ground_truth'},
                         'lookahead_seconds': 0., 'edge_warning': 'Filtered window edges and causal startup are not independent evidence.'}
    if identifier == 'cleanline':
        n = round(fs*params['window_seconds'])
        nw = params['window_seconds']  # upstream taper bandwidth 2 Hz => half bandwidth 1 Hz
        k = int(2*nw-1)
        t, eig = dpss(n, nw, k, return_ratios=True)
        payload.update(tapers=t.T, taper_eigenvalues=eig, taper_nw=nw)
        source['dpss_backend'] = 'scipy.signal.windows.dpss, symmetric L2-normalized; exact cached shape only'
    with tempfile.TemporaryDirectory(prefix='dbci-qc-method-') as folder:
        folder = Path(folder)
        savemat(folder/'input.mat', payload)
        if identifier == 'fieldtrip_zvalue':
            # Preserve the upstream alternative parser. Octave addOptional does
            # not accept MATLAB's named option usage in this function.
            original = Path(c['source_root'])/'fieldtrip/utilities/ft_fetch_data.m'
            text = original.read_text()
            if text.count('if true\n') != 1:
                raise ValueError('FieldTrip parser compatibility patch no longer matches pinned source')
            patched = text.replace('if true\n', 'if false\n')
            (folder/'ft_fetch_data.m').write_text(patched)
            source['parser_compatibility_patch'] = {'file': 'utilities/ft_fetch_data.m',
                'original_sha256': _digest(original), 'patched_sha256': _digest(folder/'ft_fetch_data.m'),
                'change': 'if true -> if false; select upstream ft_getopt branch; source checkout unchanged'}
        env = {**os.environ, 'OCTAVE_HOME': str(Path(c['octave']).resolve().parents[1]),
               'DBCI_QC_IO': str(folder), 'DBCI_QC_SOURCE_ROOT': c['source_root'],
               'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
               'GNUTERM': 'dumb'}
        with (folder/'engine.log').open('wb') as log:
            process = subprocess.Popen([c['octave'], '--no-init-file', '--no-site-file', '--no-gui', '--quiet',
                                        str(wrapper/'dbci_external.m')], cwd=folder, env=env,
                                       stdout=log, stderr=subprocess.STDOUT)
            try:
                code = process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise RuntimeError('External method exceeded the 180 second execution limit') from None
        log_text = (folder/'engine.log').read_text(errors='replace')
        if code != 0 or not (folder/'output.mat').is_file():
            raise RuntimeError('Octave execution failed: ' + log_text[-2200:])
        out = loadmat(folder/'output.mat', simplify_cells=True)
    source['engine_version'] = str(out['engine_version'])
    result = {'source': source, 'engine_log_tail': log_text[-8000:], 'notes': [], 'candidates': []}
    if identifier == 'fieldtrip_zvalue':
        intervals = np.asarray(out['intervals']).reshape(-1, 2)
        if len(intervals) and (not np.all(np.isfinite(intervals)) or not np.all(intervals == np.round(intervals))
                               or intervals.min() < 1 or intervals.max() > data.shape[1] or np.any(intervals[:, 1] < intervals[:, 0])):
            raise ValueError('Invalid FieldTrip sample intervals')
        score = np.asarray(out['zvalue']).reshape(-1)
        if score.size != data.shape[1] or not np.isfinite(score).all():
            raise ValueError('FieldTrip returned missing or nonfinite z evidence')
        result.update(sample_intervals_one_based_inclusive=intervals.astype(int).tolist(),
                      zvalue=score.tolist(), feature='absdiff; cumulative=no; no filtering or padding',
                      notes=['最大单道差分z值的区间候选，不提供确认性单道定位；病理放电也可能触发，不等于伪迹。'])
        result['candidates'] = [{'kind': 'fieldtrip_jump_interval_candidate', 'localization': 'interval_only',
                                 'scope': 'selected_channels', 'channel_index': None, 'channel_name': None,
                                 'start_seconds': start+(int(a)-1)/fs, 'stop_seconds': start+int(b)/fs}
                                for a, b in intervals]
        return result
    cleaned = np.asarray(out['cleaned'])
    if cleaned.shape != data.shape or not np.isrealobj(cleaned) or not np.isfinite(cleaned).all():
        raise ValueError('Cleaning output changed shape or contains invalid values')
    reference = payload['X']
    nperseg = min(data.shape[1], max(16, round(fs*2)))
    frequencies, before = welch(reference, fs=fs, nperseg=nperseg, axis=1)
    _, after = welch(cleaned, fs=fs, nperseg=nperseg, axis=1)
    delta = cleaned-reference
    result['evaluation'] = {'input_sha256': _data_hash(reference), 'output_sha256': _data_hash(cleaned),
        'rms_change_volts_by_channel': np.sqrt(np.mean(delta**2, axis=1)).tolist(),
        'relative_rms_change_by_channel': (np.sqrt(np.mean(delta**2, axis=1))/np.sqrt(np.mean(reference**2, axis=1))).tolist(),
        'frequencies_hz': frequencies.tolist(), 'mean_psd_before_v2_hz': before.mean(axis=0).tolist(),
        'mean_psd_after_v2_hz': after.mean(axis=0).tolist(), 'original_signal_overwritten': False,
        'cleaned_signal_exported': False, 'interpretation': 'Processing effect, not a quality score or artifact fraction'}
    if preprocessing:
        result['preprocessing'] = preprocessing
        result['calibration_state'] = {k: np.asarray(out[k]).tolist() for k in ('M', 'T', 'A', 'B')}
        result['notes'].append('ASR差异比较以同一高通副本为基准，不把高通造成的变化计入ASR；校准与评估同片段，不是独立验证。')
    if identifier == 'zapline_plus':
        result['notes'].append('当前片段作为一个固定chunk；自动选择去除成分与调整sigma，未启用自适应分段。')
        result['upstream_analytics'] = _json_value(out.get('analytics', {}))
        result['upstream_configuration'] = _json_value(out.get('configuration', {}))
        quality_notes = []
        for key, limit_key, message in [
                ('proportionBelowLower', 'maxProportionBelowLower', '上游诊断仍提示处理过强；不能把工频下降当作清洗成功。'),
                ('proportionAboveUpper', 'maxProportionAboveUpper', '上游诊断仍提示窄带残留；不能把执行完成当作去噪成功。')]:
            value = np.asarray(out.get('analytics', {}).get(key, []), dtype=float)
            limit = out.get('configuration', {}).get(limit_key, .005)
            if value.size and np.any(value > limit):
                quality_notes.append(message)
        if quality_notes:
            result['processing_warnings'] = quality_notes
            result['notes'].extend(quality_notes)
            result['reason'] = '；'.join(quality_notes)
    if identifier == 'cleanline':
        result['notes'].append('调用官方cleanLineNoise新实现，单个明确工频；末尾不足一个滑窗的样本保留原值。不自动添加谐波。')
        win, step = round(params['window_seconds']*fs), round(params['step_seconds']*fs)
        used = ((data.shape[1]-win)//step)*step+win
        result['evaluation']['tail_samples_not_processed'] = data.shape[1]-used
    result['notes'].append('仅保存前后PSD、变化量与指纹；不导出或覆盖清洗后的波形，不把清洗变化当作异常真值。')
    return result


def _json_value(value):
    """External analytics may contain unmeasurable NaNs; preserve as null."""
    import numpy as np
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items() if not k.startswith('__')}
    if isinstance(value, np.ndarray):
        return _json_value(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    return value
