"""Explicit ECoG measurement recipe; no scalp thresholds or signal access."""
import math

PROFILE = 'ecog-basic/1'


def validate_ecog_methods(methods):
    if not isinstance(methods, dict):
        raise ValueError('method_config must be an object')
    if set(methods) - {'ecog', 'comparison_groups', 'extensions', 'extension_parameters'}:
        raise ValueError('ECoG does not accept scalp EEG method parameters or thresholds')
    for key, empty in [('comparison_groups', None)]:
        if key in methods and methods[key] != empty:
            raise ValueError('ECoG basic execution does not support ' + key)
    config = methods.get('ecog', {})
    if not isinstance(config, dict) or set(config) - {'psd_window_seconds', 'line_frequencies_hz'}:
        raise ValueError('method_config.ecog accepts psd_window_seconds and line_frequencies_hz only')
    seconds = config.get('psd_window_seconds', 4.)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 < seconds <= 120:
        raise ValueError('ecog.psd_window_seconds must be finite and in (0, 120]')
    frequencies = config.get('line_frequencies_hz', [50., 60.])
    if (not isinstance(frequencies, list) or not 1 <= len(frequencies) <= 8 or
            any(isinstance(f, bool) or not isinstance(f, (int, float)) or not math.isfinite(f) or f <= 0 for f in frequencies)
            or len(set(frequencies)) != len(frequencies)):
        raise ValueError('ecog.line_frequencies_hz requires 1–8 distinct positive finite frequencies')
    return {'ecog': {'psd_window_seconds': float(seconds), 'line_frequencies_hz': sorted(float(f) for f in frequencies)},
            'comparison_groups': None, 'extensions': methods.get('extensions', []),
            'extension_parameters': methods.get('extension_parameters', {})}
