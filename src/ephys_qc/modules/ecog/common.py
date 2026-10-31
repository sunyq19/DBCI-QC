"""Compatibility helpers; descriptive computations live in continuous/common.py."""
from types import SimpleNamespace
from ..continuous.common import finite_float, identity, interval, run_bounds
from ..continuous.common import inputs as _inputs, provenance as _provenance


def inputs(context):
    if context.record.get('modality') != 'ecog':
        raise ValueError('ECoG handlers require explicit modality=ecog')
    return _inputs(context)


def provenance(state, data):
    return _provenance(SimpleNamespace(record={'modality': 'ecog'}, state=state), data)
