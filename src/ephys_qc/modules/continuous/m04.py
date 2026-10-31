"""M04 continuous voltage: Welch density and configured narrowband observations, no classification."""
from importlib.metadata import version
from .common import method_prefix, finite_float, identity, inputs, provenance


def run(context):
    import numpy as np
    from scipy.signal import welch
    data, fs, config = inputs(context)
    state = context.state
    requested = round(config['psd_window_seconds'] * fs)
    length = min(data.shape[1], requested)
    payload = {**provenance(context, data), 'method': method_prefix(context) + '_welch_and_narrowband_description',
        'software': {'scipy': version('scipy'), 'numpy': version('numpy')}, 'config': config,
        'parameters': {'window': 'hann', 'noverlap': max(0, length // 2), 'nperseg': length,
                       'nfft': length, 'detrend': 'constant', 'scaling': 'density', 'average': 'mean',
                       'shortened_to_available_samples': data.shape[1] < requested,
                       'narrowband_half_width_rule': 'max(1 Hz, frequency_resolution_hz)',
                       'classification_threshold': None},
        'psd': {'frequencies_hz': [], 'power_v2_hz': [], 'channels': []},
        'line_noise': {'status': 'unassessed', 'observations': [], 'assessment': 'descriptive_only'},
        'candidates': [], 'notes': ['Configured frequencies are not automatically expanded to harmonics.',
            'Band energy or peaks do not establish noise origin; pathological and physiological activity are not classified as bad.',
            'No scalp FOOOF/alpha, Thomson significance, PREP or muscle threshold is used.']}
    incomplete = length < 2 or data.shape[1] < requested
    frequency = np.fft.rfftfreq(length, 1 / fs) if length >= 2 else np.array([])
    payload['psd']['frequencies_hz'] = frequency.tolist()
    resolution = fs / length if length >= 2 else None
    payload['parameters']['frequency_resolution_hz'] = resolution
    for index, values in enumerate(data):
        ident = identity(state, index)
        status = 'insufficient_samples' if length < 2 else 'nonfinite_input' if not np.isfinite(values).all() else 'computed'
        power = None
        if status == 'computed':
            _, power = welch(values, fs=fs, window='hann', nperseg=length, noverlap=length // 2,
                             nfft=length, detrend='constant', return_onesided=True,
                             scaling='density', average='mean')
            if np.ptp(values) == 0: power[:] = 0.
            if not np.isfinite(power).all(): status, power = 'nonfinite_spectrum', None
        if status != 'computed': incomplete = True
        payload['psd']['channels'].append({**ident, 'status': status})
        payload['psd']['power_v2_hz'].append(None if power is None else power.tolist())
        for nominal in config['line_frequencies_hz']:
            half = max(1., resolution) if resolution else None
            item = {**ident, 'nominal_hz': nominal, 'half_width_hz': half, 'status': status,
                    'band_power_v2': None, 'peak_frequency_hz': None, 'peak_density_v2_hz': None,
                    'artifact_classification': 'not_performed'}
            if status == 'computed':
                if nominal - half < frequency[0] or nominal + half > frequency[-1]:
                    item['status'] = 'outside_measurable_band'; incomplete = True
                else:
                    lo, hi = nominal - half, nominal + half
                    inside = (frequency > lo) & (frequency < hi)
                    x = np.r_[lo, frequency[inside], hi]
                    y = np.interp(x, frequency, power)
                    integrate = getattr(np, 'trapezoid', None) or np.trapz
                    item['band_power_v2'] = finite_float(integrate(y, x))
                    peak = int(np.argmax(y))
                    item.update(peak_frequency_hz=float(x[peak]), peak_density_v2_hz=finite_float(y[peak]))
            payload['line_noise']['observations'].append(item)
    observations = payload['line_noise']['observations']
    payload['line_noise']['status'] = 'computed' if all(r['status'] == 'computed' for r in observations) else 'partial'
    context.save('M04_spectral.json', payload)
    context.row['summary'] = {'analysis_profile': payload['analysis_profile'], 'psd_channel_count': len(data),
        'psd_computed_channel_count': sum(c['status'] == 'computed' for c in payload['psd']['channels']),
        'line_status': payload['line_noise']['status'], 'line_observation_count': len(observations),
        'line_computed_observation_count': sum(r['status'] == 'computed' for r in observations),
        'quality_classification': False, 'scalp_thresholds_used': False, 'spectral_model': 'not_performed'}
    if incomplete:
        context.row.update(status='partial', reason='短窗、非有限输入或频率范围限制已保留；仅提供可测PSD与窄带描述。')
    return context.row
