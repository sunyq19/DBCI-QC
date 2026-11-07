"""Versioned basic iEEG proposal; explicit recipe, never a clinical cutoff."""
from copy import deepcopy

VERSION = 'ieeg-basic-recipe/0.1'
FLAT_PARAMETERS = {'peak_volts': None, 'flat_volts': 0.,
                   'min_duration_seconds': .05, 'bad_percent': 5.}


def configure(config):
    """Keep explicit custom methods and parameters; add the original MNE flat check.

    50 ms follows MNE-BIDS inspect_dataset's review default. The 5% setting
    routes MNE output to channels rather than intervals, not a clinical cutoff.
    """
    result = deepcopy(config)
    methods = result['method_config']
    methods['extensions'] = sorted(set(methods.get('extensions', [])) | {'mne_amplitude'})
    methods.setdefault('extension_parameters', {}).setdefault('mne_amplitude', deepcopy(FLAT_PARAMETERS))
    return result
