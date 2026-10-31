"""M05 ECoG: explicitly gated shared descriptive measurement."""
from ..continuous.m05 import run as measure


def run(context):
    if context.record.get('modality') != 'ecog':
        raise ValueError('This handler requires explicit ecog')
    return measure(context)
