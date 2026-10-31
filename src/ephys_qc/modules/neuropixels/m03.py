"""M03 neuropixels: explicitly gated shared descriptive measurement."""
from ..continuous.m03 import run as measure


def run(context):
    if context.record.get('modality') != 'extracellular':
        raise ValueError('This handler requires explicit extracellular')
    return measure(context)
