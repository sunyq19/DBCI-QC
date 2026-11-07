"""Versioned basic iEEG proposal; explicit recipe, never a clinical cutoff."""
from copy import deepcopy

VERSION = 'ieeg-basic-recipe/0.2'
FLAT_PARAMETERS = {'peak_volts': None, 'flat_volts': 0.,
                   'min_duration_seconds': .05, 'bad_percent': 5.}


def configure(config, record=None):
    """Keep explicit custom methods and parameters; add the original MNE flat check.

    50 ms follows MNE-BIDS inspect_dataset's review default. The 5% setting
    routes MNE output to channels rather than intervals, not a clinical cutoff.
    """
    result = deepcopy(config)
    methods = result['method_config']
    methods['extensions'] = sorted(set(methods.get('extensions', [])) | {'mne_amplitude'})
    methods.setdefault('extension_parameters', {}).setdefault('mne_amplitude', deepcopy(FLAT_PARAMETERS))
    if record and record.get('metadata',{}).get('format') in {'EDF','BDF'}:
        methods['extensions'] = sorted(set(methods['extensions']) | {'ieeg_range_plateau'})
    return result


def encoding_ranges(channels):
    """Only reader-supplied file calibration, never extrema measured from data."""
    import math
    rows=[]
    for c in channels:
        try:
            a,b,d0,d1,s=(float(c[k]) for k in ('physical_min','physical_max','digital_min','digital_max','scale_to_si'))
            if not all(math.isfinite(v) for v in (a,b,d0,d1,s)) or a==b or d1<=d0 or s<=0:raise ValueError()
            lo,hi=sorted((a*s,b*s))
            rows.append(dict(minimum_volts=lo,maximum_volts=hi,step_volts=(hi-lo)/(d1-d0),source='file_encoding_range_not_hardware_ADC'))
        except (KeyError,ValueError,TypeError):rows.append(None)
    return rows
