"""Read-time proposals are not confirmation, anatomy guesses or QC execution."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'),str(REPO/'apps/workbench')]
from intake import IntakeStore, suggestions


def channel(index, kind, *, source='file_declared', name=None, unit='V', fs=100.):
    result = {'index': index, 'name': name or f'sensor-{index}', 'unit': unit,
              'channel_type': kind, 'sampling_rate_hz': fs}
    if source is not None: result['channel_type_source'] = source
    return result


def metadata(*channels, format_='FIF'):
    return {'format':format_,'channels':list(channels),'duration_seconds':2.}


class ModalityProposalTests(unittest.TestCase):
    def test_single_file_declared_neural_group_is_only_a_proposal(self):
        for kind, modality in [('eeg','scalp_eeg'),('ecog','ecog'),('seeg','seeg')]:
            with self.subTest(kind=kind):
                meta=metadata(channel(7,kind),channel(2,kind),channel(9,'stim',unit='unknown'))
                original=copy.deepcopy(meta)
                proposal,_=suggestions(meta)
                self.assertEqual(proposal['modality'],modality)
                evidence=proposal['modality_evidence']
                self.assertEqual(evidence['status'],'file_declared')
                self.assertEqual(evidence['channel_groups'],[{'modality':modality,'indices':[2,7]}])
                self.assertEqual(proposal['eeg_indices'],[7,2])
                self.assertNotIn('confirmed',proposal)
                self.assertEqual(proposal['reference_scheme'],'unknown')
                self.assertEqual(meta,original)
                json.dumps(proposal,allow_nan=False)

    def test_brainvision_default_eeg_and_eeglab_inferred_types_are_not_anatomical_evidence(self):
        for format_, source in [('BrainVision','reader_default'),('EEGLAB','reader_inferred')]:
            with self.subTest(format=format_):
                proposal,_=suggestions(metadata(channel(2,'eeg',source=source,name='Cz'),format_=format_))
                self.assertEqual(proposal['modality'],'unknown')
                self.assertEqual(proposal['modality_evidence']['status'],'unknown')
                self.assertEqual(proposal['modality_evidence']['channel_groups'],[])
                self.assertEqual(proposal['eeg_indices'],[2])

    def test_unproven_types_and_adversarial_filename_disease_do_not_identify_modality(self):
        meta=metadata(channel(2,'ecog',source=None,name='EEG Cz'),format_='FIF')
        a,_=suggestions(meta)
        meta.update(filename='definitely_scalp_eeg.edf',diagnosis='epilepsy',modality='scalp_eeg',
                    annotations={'description':'invasive ECoG'},data=[1,2,3])
        b,_=suggestions(meta)
        self.assertEqual(a,b);self.assertEqual(a['modality'],'unknown')

    def test_default_or_inferred_eeg_allows_aux_name_candidates_but_not_anatomy(self):
        for format_,source in [('BrainVision','reader_default'),('EEGLAB','reader_inferred')]:
            with self.subTest(format=format_):
                meta=metadata(channel(0,'eeg',source=source,name='Cz'),
                    channel(1,'eeg',source=source,name='ECG'),
                    channel(2,'eeg',source=source,name='EOG'),format_=format_)
                proposal,_=suggestions(meta)
                self.assertEqual(proposal['eeg_indices'],[0])
                self.assertEqual(proposal['reference_indices'],{'ecg':1,'eog':2})
                self.assertEqual(proposal['modality'],'unknown')
                self.assertEqual(proposal['modality_evidence']['channel_groups'],[])
                meta['channels'].append(channel(3,'ecg',name='EEG'))
                proposal,_=suggestions(meta)
                self.assertEqual(proposal['reference_indices'],{'ecg':3,'eog':2})

    def test_file_declared_eeg_retains_anatomical_role_despite_aux_name(self):
        proposal,_=suggestions(metadata(channel(1,'eeg',name='ECG'),
            channel(2,'eeg',name='EOG'),channel(3,'eog',name='Cz')))
        self.assertEqual(proposal['eeg_indices'],[1,2])
        self.assertEqual(proposal['reference_indices'],{'eog':3})
        self.assertEqual(proposal['modality'],'scalp_eeg')

    def test_mixed_file_declared_eeg_ecog_seeg_requires_single_group_choice(self):
        proposal,_=suggestions(metadata(channel(7,'ecog'),channel(2,'eeg'),channel(11,'seeg'),channel(12,'eog')))
        self.assertEqual(proposal['modality'],'unknown')
        self.assertEqual(proposal['modality_evidence']['status'],'mixed')
        self.assertEqual(proposal['modality_evidence']['channel_groups'],[
            {'modality':'scalp_eeg','indices':[2]}, {'modality':'ecog','indices':[7]}, {'modality':'seeg','indices':[11]}])
        self.assertEqual(proposal['eeg_indices'],[])
        self.assertEqual(proposal['reference_indices'],{'eog':12})

    def test_mixed_meg_eeg_not_proposed_as_pure_scalp(self):
        proposal,_=suggestions(metadata(channel(0,'eeg'),channel(1,'mag',unit='T'),channel(2,'grad',unit='T/m')))
        self.assertEqual(proposal['modality_evidence']['status'],'mixed')
        self.assertEqual(proposal['modality_evidence']['channel_groups'],[
            {'modality':'scalp_eeg','indices':[0]}, {'modality':'other','indices':[1,2]}])
        self.assertEqual(proposal['eeg_indices'],[])
        self.assertEqual(proposal['modality'],'unknown')

    def test_partial_declaration_keeps_trusted_group_but_does_not_label_whole_record(self):
        proposal,_=suggestions(metadata(channel(3,'ecog'),channel(4,'eeg',source='reader_default')))
        self.assertEqual(proposal['modality'],'unknown')
        self.assertEqual(proposal['modality_evidence']['status'],'unknown')
        self.assertEqual(proposal['modality_evidence']['channel_groups'],[
            {'modality':'ecog','indices':[3]}, {'modality':'unknown','indices':[4]}])
        self.assertEqual(proposal['eeg_indices'],[3])

    def test_explicit_misc_and_auxiliary_types_win_over_names(self):
        meta=metadata(channel(2,'ecog',name='ECG'),channel(3,'misc',name='EKG1'),
            channel(4,'misc',name='ECG'),channel(5,'misc',name='Cz'),channel(6,'ecg',name='EOG'),
            channel(7,'eog',name='ECG'),channel(8,'eog',name='EEG Cz'),channel(9,'stim',name='Cz'))
        proposal,_=suggestions(meta)
        self.assertEqual(proposal['modality'],'ecog')
        self.assertEqual(proposal['eeg_indices'],[2])
        self.assertEqual(proposal['reference_indices'],{'ecg':6,'eog':7})
        self.assertEqual(proposal['modality_evidence']['channel_groups'],[{'modality':'ecog','indices':[2]}])

    def test_unknown_legacy_edf_keeps_role_proposals_without_modality_inference(self):
        proposal,_=suggestions(metadata(channel(0,None,source=None,name='Cz'),channel(2,None,source=None,name='EOG'),format_='EDF'))
        self.assertEqual(proposal['eeg_indices'],[0]);self.assertEqual(proposal['reference_indices'],{'eog':2})
        self.assertEqual(proposal['modality'],'unknown')
        self.assertEqual(proposal['modality_evidence']['channel_groups'],[])

    def test_aux_only_or_unsupported_neural_type_remains_unknown(self):
        for channels in [(channel(0,'eog'),channel(1,'misc',name='Cz')),(channel(0,'dbs'),)]:
            proposal,_=suggestions(metadata(*channels))
            self.assertEqual(proposal['modality'],'unknown')
            self.assertEqual(proposal['eeg_indices'],[])

    @unittest.skipUnless(importlib.util.find_spec('mne'), 'Scientific reader environment required')
    def test_actual_fif_read_proposes_but_never_registers_and_preserves_snapshot(self):
        import mne
        import numpy as np
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            path=root/'scalp_named_but_ecog_raw.fif'
            raw=mne.io.RawArray(np.zeros((4,200)),mne.create_info(['G1','G2','EKG1','EOG'],100.,['ecog','ecog','misc','eog']),verbose='ERROR')
            raw.save(path,fmt='double',overwrite=True,verbose='ERROR');raw.close()
            data=path.read_bytes();store=IntakeStore(root/'runtime')
            intake=store.receive(path.name,len(data),io.BytesIO(data))
            self.assertEqual(intake['suggestions']['modality'],'ecog')
            self.assertEqual(intake['suggestions']['eeg_indices'],[0,1])
            self.assertEqual(intake['suggestions']['reference_indices'],{'eog':3})
            self.assertEqual(intake['status'],'needs_confirmation')
            self.assertEqual(store.registered(),[])
            with self.assertRaises(ValueError): store.confirm(intake['id'],{'confirmed':False})
            self.assertEqual(store.registered(),[])
            body={'confirmed':True,'modality':'ecog','eeg_indices':[0,1],'reference_indices':{'eog':3},'reference_scheme':'unknown'}
            registered=store.confirm(intake['id'],body)
            snapshot=(store.root/intake['id']/'record.json').read_bytes()
            with patch('intake.suggestions',side_effect=AssertionError('Do not recompute saved proposals')):
                reopened=IntakeStore(root/'runtime')
                self.assertEqual(reopened.registered(),[registered])
                self.assertEqual(reopened.get(intake['id'])['suggestions']['modality'],'ecog')
            self.assertEqual((store.root/intake['id']/'record.json').read_bytes(),snapshot)
            self.assertEqual(path.read_bytes(),data)

if __name__=='__main__':unittest.main()
