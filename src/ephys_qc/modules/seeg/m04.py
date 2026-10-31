"""M04 seeg: explicitly gated shared descriptive measurement."""
from ..continuous.m04 import run as measure


def run(context):
    if context.record.get('modality') != 'seeg':
        raise ValueError('This handler requires explicit seeg')
    return measure(context)
