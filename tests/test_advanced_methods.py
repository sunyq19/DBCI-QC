"""Eligibility, evidence and scoring boundaries for upstream method adapters."""
import copy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from ephys_qc.advanced_methods import evaluate_extension,valid_positions
from ephys_qc.method_registry import methods
from ephys_qc.method_scores import extension_outputs


def facts():
    import numpy as np
    from mne.channels import make_standard_montage
    pos=list(make_standard_montage('standard_1020').get_positions()['ch_pos'].values())[:24]
    return dict(modality='scalp_eeg',verified_voltage=True,n_eeg=24,sampling_rate_hz=500,window_seconds=60,
        reference_scheme='common_reference',electrode_positions_m=[p.tolist() for p in pos],electrode_coordinate_frame='head')


@pytest.mark.parametrize('method',['pyprep_ransac','autoreject_epochs','ica_iclabel'])
def test_no_label_guesses_and_wrong_modality(method):
    with patch('ephys_qc.advanced_methods.find_spec',return_value=object()):
        f=facts();assert evaluate_extension(method,f)['status']=='ready'
        for override in [dict(electrode_positions_m=[]),dict(electrode_coordinate_frame='unknown'),dict(modality='seeg'),dict(reference_scheme='bipolar'),dict(verified_voltage=False),dict(window_seconds=1)]:
            assert evaluate_extension(method,{**f,**override})['status']=='blocked'


def test_iclabel_known_filtered_band_blocks():
    with patch('ephys_qc.advanced_methods.find_spec',return_value=object()):
        assert evaluate_extension('ica_iclabel',{**facts(),'preprocessing_lowpass_hz':40})['status']=='blocked'


def test_drift_never_ap_or_missing_shanks():
    f=dict(modality='extracellular',verified_voltage=True,n_eeg=16,sampling_rate_hz=2500,window_seconds=20,
        probe_positions_um=[[0,i*20] for i in range(16)],probe_shanks=[0]*16,stream_band='LF')
    with patch('ephys_qc.advanced_methods.find_spec',return_value=object()):
        assert evaluate_extension('dredge_lfp',f)['status']=='ready'
        for change in [dict(stream_band='AP'),dict(probe_shanks=[]),dict(window_seconds=2)]:
            assert evaluate_extension('dredge_lfp',{**f,**change})['status']=='blocked'


def test_local_labels_count_once_and_failed_evidence_is_not_score():
    p=dict(status='completed',range=dict(start_seconds=10,stop_seconds=15,duration_seconds=5),channel_names=['a','b'],
        segmentation={'n_epochs':2,'tail_samples_not_used':100},labels=[[0,2],[1,0]],
        candidates=[{'epoch_index':0,'channel_name':'b'},{'epoch_index':1,'channel_name':'a'}])
    result=extension_outputs('autoreject_epochs',p)[0]
    assert result['value']==50 and result['assessed_amount']==4 and result['candidate_amount']==2
    p['status']='failed';assert extension_outputs('autoreject_epochs',p)[0]['value'] is None
    p['status']='completed';p['labels'][0][0]=float('nan');assert extension_outputs('autoreject_epochs',p)[0]['value'] is None


def test_catalog_and_default_score_roles():
    from ephys_qc.score_registry import outputs
    for mod in ['scalp_eeg','ecog','seeg','extracellular']:
        rows=methods(mod);assert len(rows)==len({r['id'] for r in rows})
        assert next(r for r in rows if r['id']=='nwb_inspector')['can_output_score'] is False
    eeg={r['id']:r for r in methods('scalp_eeg')}
    assert eeg['pyprep_ransac']['can_output_score'] and eeg['autoreject_epochs']['can_output_score']
    assert not eeg['ica_iclabel']['can_output_score']
    assert not next(r for r in methods('extracellular') if r['id']=='dredge_lfp')['can_output_score']
    assert all(s['default_weight']==0 for k in ['pyprep_ransac','autoreject_epochs'] for s in outputs(method_id=k))


def test_ransac_does_not_turn_excluded_flat_channels_into_passes():
    payload = dict(status='partial', channel_names=['a'],
        range=dict(start_seconds=0, stop_seconds=30, duration_seconds=30),
        candidates=[], measurements=[dict(channel_name='a', bad_window_fraction=0, correlations=[.9])],
        unassessed_channel_names=['flat'])
    score = extension_outputs('pyprep_ransac', payload)[0]
    assert score['value'] is None and '未参与空间预测' in score['reason']
    payload['unassessed_channel_names'] = []
    payload['status'] = 'completed'
    assert extension_outputs('pyprep_ransac', payload)[0]['value'] == 100


def test_saved_measurements_are_rendered_without_rerunning(tmp_path):
    from ephys_qc.advanced_report import append_to
    folder = tmp_path / 'artifacts'; folder.mkdir()
    (folder/'M05_dredge_lfp.json').write_text(json.dumps(dict(status='completed',
        range=dict(start_seconds=0, stop_seconds=20),
        motion=[dict(shank=0, range_um=12.5, reference_seconds=.004)])))
    report = append_to('<main></main>', tmp_path)
    assert 'DREDge LF 漂移' in report and '12.50' in report
    assert append_to(report, tmp_path) == report
    nested=append_to('<main><details id="checks"><summary>报告详情</summary><div id="method-evidence-slot"></div></details></main>',tmp_path)
    assert 'class="report-detail-group"' in nested and '<h3>方法测量</h3>' in nested
    assert nested.index('DREDge LF') < nested.rindex('</details>')
    visible=append_to('<main><details id="locations"></details></main>',tmp_path)
    assert visible.index('12.50') < visible.index('id="locations"')


def test_bids_grouping_keeps_repeated_locations_and_severities_distinct():
    from ephys_qc.dataset_qc.bids_findings import grouped_checks
    issues=[{'severity':severity,'code':code,'location':'/same.tsv','subCode':str(i)}
            for severity,code,n in [('error','TYPE',2),('warning','TYPE',4),('warning','FIELD',201)] for i in range(n)]
    before=json.dumps(issues)
    grouped=grouped_checks({'status':'completed','issues':{'issues':issues}})
    assert len(grouped)==3
    assert len({g['id'] for g in grouped})==3
    assert sum(g['observed']['occurrences'] for g in grouped)==207
    assert sum(len(g['observed']['details']) for g in grouped)==207
    assert json.dumps(issues)==before


def test_coordinates_survive_reader(tmp_path):
    import numpy as np,mne
    from ephys_qc.readers import inspect_recording
    raw=mne.io.RawArray(np.zeros((2,200)),mne.create_info(['Fz','Cz'],100,'eeg'),verbose=False)
    raw.set_montage(mne.channels.make_standard_montage('standard_1020'))
    p=tmp_path/'test_raw.fif';raw.save(p,overwrite=True,verbose=False)
    c=inspect_recording(p)['channels']
    assert valid_positions([row['electrode_position_m'] for row in c],2)
    assert all(row['electrode_coordinate_frame']=='head' and row['electrode_coordinate_source']=='file_embedded_mne' for row in c)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'apps/workbench'))
    from server import Store
    old = dict(reader_id='mne_fif', channels=[])
    record = dict(source_path=str(p), metadata=old, reference_scheme='common_reference')
    Store._availability(record)
    assert record['metadata']['coordinate_metadata_version'] == 1
    assert old == dict(reader_id='mne_fif', channels=[])  # Frozen snapshots are not mutated.
    with patch('server.inspect_recording', side_effect=AssertionError('repeated inspection')):
        Store._availability(record)
    assert record['reference_scheme'] == 'common_reference'


def test_bids_plain_folder_is_not_checked(tmp_path):
    from ephys_qc.format_validation import inspect_bids
    assert inspect_bids(tmp_path)['status']=='not_applicable'


def test_bids_invalid_description_does_not_pass_or_crash(tmp_path):
    from ephys_qc.format_validation import inspect_bids
    (tmp_path/'dataset_description.json').write_text('[]')
    result=inspect_bids(tmp_path)
    assert result['status']=='unassessed' and not result['calculated']
