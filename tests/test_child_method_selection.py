"""Child choices control scheduling, evidence and scoring, not just UI badges."""
from copy import deepcopy
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.planning import build_plan
from ephys_qc.method_registry import methods
from ephys_qc.method_selection import validate, score_selected
from test_modular_core import record, MANDATORY, node


def config(core=(), extensions=()):
    return {'method_config': {'core_methods': list(core), 'extensions': list(extensions)}}


def test_parent_is_derived_and_last_child_off_removes_parent():
    one = build_plan(record(), ['M03','M04','M05','M06','M07'], config(['welch_psd']))
    assert set(one['selected_modules']) == MANDATORY | {'M04'}
    chosen = {m['id'] for m in one['method_applicability'] if m['selected']}
    assert 'welch_psd' in chosen and 'thomson_line' not in chosen and 'spectral_model' not in chosen
    empty = build_plan(record(), ['M03','M04','M05','M06','M07'], config())
    assert set(empty['selected_modules']) == MANDATORY
    assert one['plan_id'] != empty['plan_id']


def test_extension_only_never_selects_parent_core_methods():
    plan = build_plan(record(), [], config(extensions=['mne_amplitude']))
    assert set(plan['selected_modules']) == MANDATORY | {'M03'}
    rows = {m['id']: m for m in plan['method_applicability']}
    assert rows['mne_amplitude']['selected']
    assert not rows['continuity']['selected']
    assert rows['continuity']['status'] == 'not_selected'


def test_hf_dependency_is_internal_without_selecting_m03_report():
    plan = build_plan(record(), [], config(['hf_burst']))
    assert 'M06' in plan['selected_modules'] and 'M03' not in plan['selected_modules']
    assert node(plan, 'M06')['depends_on'] == ['M02']
    # Legacy plans keep their old dependency and fingerprint semantics.
    legacy = build_plan(record(), ['M06'])
    assert 'M03' in legacy['selected_modules']


@pytest.mark.parametrize('core', [None, 'continuity', [123], ['mne_amplitude'], ['report'], ['seeg_continuity']])
def test_core_allowlist_rejects_invalid_or_wrong_route_choices(core):
    with pytest.raises(ValueError):
        build_plan(record(), [], {'method_config': {'core_methods': core}})


def test_explicit_children_survive_recording_plan_and_score_aliases():
    supplied = config(['welch_psd'])
    supplied['scope'] = 'recording'
    plan = build_plan(record(), [], supplied)
    assert plan['qc_config']['method_config']['core_methods'] == ['welch_psd']
    assert 'M04' in plan['selected_modules'] and 'M03' not in plan['selected_modules']
    from ephys_qc.score_registry import SPECS
    assert not score_selected(SPECS['line_noise'], supplied, 'scalp_eeg')
    assert not score_selected(SPECS['neuropixels_numeric_integrity'], config(), 'extracellular')


@pytest.mark.parametrize('modality,prefix', [('ecog','ecog'),('seeg','seeg'),('extracellular','neuropixels')])
def test_other_route_catalogs_support_independent_core_choices(modality, prefix):
    supplied=config([prefix+'_welch_psd'])
    assert validate(supplied, methods(modality)) == {'M04'}
    from ephys_qc.modalities import validate_descriptive_methods
    assert validate_descriptive_methods(supplied['method_config'],modality)['core_methods'] == [prefix+'_welch_psd']


def test_selected_spectral_primitives_match_original_without_fooof():
    np=pytest.importorskip('numpy')
    upstream=pytest.importorskip('brainelecqc.eeg.spectral')
    from types import SimpleNamespace
    from ephys_qc.modules.m04 import _selected_spectrum
    fs=256.; t=np.arange(int(12*fs))/fs
    data=np.array([1e-5*np.sin(2*np.pi*10*t)+2e-6*np.sin(2*np.pi*50*t)])
    state={'data':data,'fs':fs,'first':256,'start':1.,'channels':[{'channel_id':'x:0','raw_name':'Cz'}]}
    ctx=SimpleNamespace(state=state,config=config(['welch_psd','thomson_line']))
    reference=upstream.compute_spectral_qc(data,fs,['x:0'],['Cz'],start_sample=256,start_seconds=1.)
    with patch.object(upstream,'_fooof_class',side_effect=AssertionError('unselected model executed')):
        actual=_selected_spectrum(ctx)
    np.testing.assert_array_equal(actual['psd']['power_v2_hz'],reference['psd']['power_v2_hz'])
    assert actual['line_noise'] == reference['line_noise']
    assert actual['parameterization']['status'] == 'not_selected'


def test_unselected_core_score_does_not_leak_from_parent_extension():
    from ephys_qc.method_scores import finalize
    result={'selected_modules':['M01','M02','M03','M08','M09'],
            'qc_config':config(extensions=['mne_amplitude']),
            'input_modality':{'value':'scalp_eeg'},'modules':[{'id':'M03','status':'completed'}]}
    finalize(result, [])
    assert {row['id'] for row in result['method_scores']} == {'mne_amplitude_channels','mne_amplitude_time'}


def test_continuous_psd_only_does_not_inherit_unselected_line_band_limit():
    np = pytest.importorskip('numpy')
    from types import SimpleNamespace
    from ephys_qc.modules.continuous.m04 import run
    fs = 64.  # 50/60 Hz cannot be measured, but were not requested.
    t = np.arange(int(12 * fs)) / fs
    saved = {}
    ctx = SimpleNamespace(record={'modality': 'seeg', 'metadata': {}},
        config=config(['seeg_welch_psd']), row={'status': 'completed'},
        state={'data': np.array([1e-5 * np.sin(2 * np.pi * 10 * t)]),
               'fs': fs, 'first': 0, 'start': 0.,
               'channels': [{'channel_id': 'x:0', 'raw_name': 'A1', 'source_index': 0}]},
        save=lambda name, payload: saved.update({name: payload}))
    run(ctx)
    assert ctx.row['status'] == 'completed'
    assert saved['M04_spectral.json']['line_noise']['status'] == 'not_selected'
    assert saved['M04_spectral.json']['psd']['channels'][0]['status'] == 'computed'
