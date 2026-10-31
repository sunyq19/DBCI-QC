"""Cross-route isolation and actual module execution for sEEG/Neuropixels raw."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'apps/workbench')]
from ephys_qc.planning import build_plan, catalog
from ephys_qc.recommendations import recommend
from ephys_qc.modalities import default_methods, route
from ephys_qc.modules import module_specs
from ephys_qc.toolkit import prepare_recording, run_modules
from intake import suggestions, registration_selection
from standards_page import safe_url, render_standards, Markdown, _module_clause_id
from intake import IntakeStore
from test_spikeglx_reader import spikeglx_fixture
from test_upload_packages import package
from test_intake import confirmation


def recording(modality='seeg', band='ap'):
    np = modality == 'extracellular'
    kind = 'neuropixels' if np else modality
    fs = 30000. if np and band == 'ap' else 2500. if np else 1000.
    metadata = {'format': 'SpikeGLX' if np else 'FIF', 'duration_seconds': 10.,
                'channels': [{'index': i, 'name': f'C{i}', 'unit': 'V', 'sampling_rate_hz': fs,
                              'channel_type': kind, 'channel_type_source': 'file_declared'} for i in range(3)]}
    if np: metadata['acquisition'] = {'stream_band': band, 'probe_type': 0}
    return {'id': 'declared-' + modality, 'modality': modality, 'metadata': metadata,
            'source_path': '/not-read/input', 'reference_scheme': 'unknown',
            'default_config': {'selection': {'eeg_indices': [0, 1, 2], 'reference_indices': {},
                                            'start_seconds': 0., 'duration_seconds': 1.},
                               'method_config': default_methods(modality, metadata)}}


class NewRouteContracts(unittest.TestCase):
    def test_recommendation_roundtrip_and_no_scalp_methods(self):
        for modality in ('seeg', 'extracellular'):
            r = recording(modality); before = copy.deepcopy(r)
            result = recommend(r)
            self.assertEqual(result['status'], 'ready', result)
            self.assertEqual(result['scope']['analysis_profile'], route(modality)['profile'])
            self.assertEqual(build_plan(r, result['selected_modules'], result['qc_config'])['plan_id'], result['plan_id'])
            self.assertFalse(result['scope']['signal_read'])
            self.assertNotIn('M06', result['selected_modules'])
            self.assertFalse({'prep_nonspatial', 'hf_burst', 'spectral_model'} & {m['id'] for m in result['method_applicability']})
            self.assertEqual(r, before)
            for module in catalog(modality):
                for method in module['methods']:
                    planned = method['implementation'] == 'planned'
                    self.assertEqual(method['supported_modalities'], [] if planned else [modality])
                    self.assertEqual(method['intended_modalities'], [modality] if planned else [])
            self.assertTrue(all(route(modality)['key'] in spec['entrypoint'] for spec in module_specs(modality) if spec['id'] in {'M03','M04','M05'}))

    def test_ap_lf_have_separate_metadata_driven_defaults(self):
        for band, seconds in [('ap', .1), ('lf', 1.)]:
            result = recommend(recording('extracellular', band))
            self.assertEqual(result['qc_config']['method_config']['neuropixels']['psd_window_seconds'], seconds)
            self.assertIn(band, [t['value'] for t in result['data_tags'] if t['key'] == 'stream_band'])

    def test_cross_modality_parameters_fail_without_silent_conversion(self):
        for modality in ('seeg','extracellular'):
            for wrong in ({'ecog': {}}, {'continuity': {}}, {'extensions': ['mne_amplitude']}, {'comparison_groups': ['all']*3}):
                r=recording(modality);r['default_config']['method_config'].update(wrong)
                self.assertFalse(recommend(r)['can_apply'])
                with self.assertRaises(ValueError): build_plan(r, ['M03'])

    def test_unknown_extracellular_and_sorted_objects_cannot_use_np_recipe(self):
        for fmt, band in [('FIF','ap'),('SpikeGLX','spikes'),('NWB','lf')]:
            r=recording('extracellular');r['metadata']['format']=fmt;r['metadata']['acquisition']['stream_band']=band
            self.assertFalse(recommend(r)['can_apply'])
            with self.assertRaises(ValueError): build_plan(r,['M03'])

    def test_declared_types_prevent_relabeling_or_digital_sync_analysis(self):
        for modality in ('seeg','extracellular'):
            for kind in ('eeg','ecog','stim','misc'):
                r=recording(modality);r['metadata']['channels'][0]['channel_type']=kind
                with self.assertRaises(ValueError): build_plan(r,['M03'])
                with self.assertRaises(ValueError): registration_selection(r['metadata'],[0,1],{},modality)
        r=recording('extracellular');r['modality']='scalp_eeg';r['default_config']['method_config']={}
        with self.assertRaises(ValueError): build_plan(r,['M03'])

    def test_reading_proposals_keep_neural_groups_and_exclude_sync(self):
        for modality in ('seeg','extracellular'):
            meta=recording(modality)['metadata'];meta['channels'].append({'index':3,'name':'EEG1','unit':'count','channel_type':'stim','channel_type_source':'file_declared','sampling_rate_hz':1000})
            proposal,_=suggestions(meta)
            self.assertEqual(proposal['modality'], modality)
            self.assertEqual(proposal['eeg_indices'],[0,1,2])
            meta['channels'][1]['channel_type']='ecog'
            proposal,_=suggestions(meta)
            self.assertEqual(proposal['modality_evidence']['status'],'mixed')
            self.assertEqual(proposal['eeg_indices'],[])

    def test_short_ap_and_whole_record_keep_limits_and_sample_coverage(self):
        r=recording('extracellular');r['metadata']['duration_seconds']=.02
        r['default_config']['selection']['duration_seconds']=.02
        plan=build_plan(r,['M04'])
        self.assertEqual(next(n for n in plan['nodes'] if n['id']=='M04')['status'],'partial')
        r=recording('extracellular');r['metadata']['channels']*=1
        result=recommend(r,{'scope':'recording','recording_options':{'window_seconds':3}})
        self.assertEqual(result['status'],'ready', result)
        self.assertEqual(result['window_count'],4)
        self.assertEqual(result['analysis_scope'],'recording')

    def test_new_module_document_paths_preserve_clause_and_language(self):
        for modality,slug in [('seeg','seeg'),('extracellular','neuropixels')]:
            for lang in ('zh-CN','en'):
                folder=REPO/'docs'/('en' if lang=='en' else '')/slug
                if not (folder/'qc-standards.md').is_file(): self.skipTest('New docs are not ready yet')
                md=Markdown((folder/'qc-standards.md').read_text());md.render();ids={h['id'] for h in md.headings}
                for number in range(1,10):
                    mid=f'M{number:02d}';self.assertIn(_module_clause_id(mid,lang,modality),ids)
                    page=render_standards((folder/'modules'/f'{mid}.md').read_text(),mid,lang=lang,modality=modality)
                    self.assertIn(f'/standards/{slug}/modules/{mid}',page)
                    self.assertIn(f'modality={modality}',page)
                    self.assertIsNotNone(safe_url(f'/standards/{slug}/modules/{mid}'))
                self.assertIsNone(safe_url(f'/standards/{slug}/modules/../../secret'))

    def test_real_module_entrypoints_execute_synthetic_seeg_without_scalp_thresholds(self):
        import mne
        import numpy as np
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path=root/'seeg.fif';fs=1000
            data=np.array([np.sin(np.arange(1200)/fs*2*np.pi*37)*1e-5,np.zeros(1200)])
            raw=mne.io.RawArray(data,mne.create_info(['D1','D2'],fs,['seeg','seeg']),first_samp=2000,verbose='ERROR')
            raw.save(path,fmt='double',verbose='ERROR')
            config={'selection':{'eeg_indices':[0,1],'reference_indices':{},'start_seconds':0,'duration_seconds':1.2},'method_config':{'seeg':{'psd_window_seconds':1}}}
            record=prepare_recording(path,record_id='seeg-contract',modality='seeg',qc_config=config)
            result=run_modules(record,root/'out',['M03','M04','M05'])
            self.assertEqual(result['analysis_profile'],'seeg-basic/1')
            self.assertFalse(any(m['status']=='failed' for m in result['modules']))
            self.assertIsNone(result['score']['value'])
            continuity=json.loads((root/'out/artifacts/M03_continuity.json').read_text())
            self.assertEqual(continuity['modality'],'seeg')
            self.assertEqual(continuity['input_range']['start_sample'],2000)
            self.assertTrue(any(c['candidate_id'].startswith('seeg-continuity:') for c in continuity['candidates']))
            spectral=json.loads((root/'out/artifacts/M04_spectral.json').read_text())
            freq=np.array(spectral['psd']['frequencies_hz']);power=np.array(spectral['psd']['power_v2_hz'][0])
            self.assertEqual(freq[np.argmax(power)],37)
            stats=json.loads((root/'out/artifacts/M05_channel_description.json').read_text())
            self.assertFalse(stats['classification_performed'])
            self.assertIsNone(stats['channels'][0]['quality_label'])
            self.assertIn('sEEG QC',(root/'out/artifacts/report.html').read_text())
            forged=copy.deepcopy(record)
            forged['modality']='ecog'
            forged['default_config']['method_config']={'ecog': {}}
            for channel in forged['metadata']['channels']: channel['channel_type']='ecog'
            rejected=run_modules(forged,root/'forged',['M03'])
            self.assertEqual(next(m for m in rejected['modules'] if m['id']=='M02')['status'],'failed')
            self.assertFalse((root/'forged/artifacts/M03_continuity.json').exists())

    def test_spikeglx_package_confirmation_and_real_short_window_report(self):
        import io
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);path,_=spikeglx_fixture(root)
            body=package([(path.name,path.read_bytes()),(path.with_suffix('.meta').name,path.with_suffix('.meta').read_bytes())])
            store=IntakeStore(root/'store')
            intake=store.receive('probe.zip',len(body),io.BytesIO(body))
            self.assertEqual(intake['status'],'needs_confirmation')
            self.assertEqual(intake['suggestions']['modality'],'extracellular')
            self.assertEqual(intake['suggestions']['eeg_indices'],[0,1])
            self.assertEqual(store.registered(),[])
            with self.assertRaises(ValueError):
                store.confirm(intake['id'],confirmation(modality='extracellular',eeg_indices=[0,2],reference_indices={}))
            record=store.confirm(intake['id'],confirmation(modality='extracellular',reference_indices={}))
            result=run_modules(record,root/'out',['M03','M04','M05'])
            self.assertEqual(result['analysis_profile'],'neuropixels-voltage/2')
            self.assertFalse(any(m['status']=='failed' for m in result['modules']))
            self.assertEqual(next(m for m in result['modules'] if m['id']=='M04')['status'],'partial')
            self.assertEqual(result['recording']['start_sample'],456)
            self.assertEqual(result['recording']['channel_count'],2)
            self.assertIsNone(result['score']['value'])
            self.assertIn('Neuropixels 电压 QC',(root/'out/artifacts/report.html').read_text())
            forged=copy.deepcopy(record)
            forged['metadata']['acquisition']['stream_band']='lf'
            rejected=run_modules(forged,root/'forged',['M03'])
            self.assertEqual(next(m for m in rejected['modules'] if m['id']=='M02')['status'],'failed')
            for name in (path.name,path.with_suffix('.meta').name):
                content=(root/name).read_bytes()
                with self.assertRaises(ValueError): store.receive(name,len(content),io.BytesIO(content))


if __name__ == '__main__': unittest.main()
