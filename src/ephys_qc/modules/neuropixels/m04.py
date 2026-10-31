"""M04 neuropixels: explicitly gated shared descriptive measurement."""
from ..continuous.m04 import run as measure


def run(context):
    if context.record.get('modality') != 'extracellular':
        raise ValueError('This handler requires explicit extracellular')
    return measure(context)
