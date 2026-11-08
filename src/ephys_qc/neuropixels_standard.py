"""Metadata-only Neuropixels voltage recipe; independent from sorted-unit QC."""
from copy import deepcopy

VERSION = 'neuropixels-qc/0.1'
RECIPE = 'neuropixels-basic-recipe/0.1'
AP_METHOD = 'spikeinterface_bad_channels'


def configure(config, record, plan, submitted=None):
    """Recommend existing AP screening only where a real execution window fits.

    An explicit extension list is a user choice, including an empty list. Never
    infer shanks or apply AP parameters to LF or an unknown NWB signal band.
    """
    from .tagging import data_facts
    from .research_runtime import evaluate_extension
    result = deepcopy(config)
    if 'extensions' in (submitted or {}).get('method_config', {}):
        return result
    facts = data_facts(record, result)
    params = result['method_config'].get('extension_parameters', {}).get(AP_METHOD)
    durations = [w['duration_seconds'] for w in plan.get('windows', [])] or [facts['window_seconds']]
    if any(evaluate_extension(AP_METHOD, {**facts, 'window_seconds': seconds}, params)['status'] in {'ready', 'partial'}
           for seconds in sorted(set(durations))):
        result['method_config']['extensions'] = sorted(set(result['method_config'].get('extensions', [])) | {AP_METHOD})
    return result
