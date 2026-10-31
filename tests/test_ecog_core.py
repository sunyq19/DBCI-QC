"""ECoG routing, source identity and numerical contracts, not clinical accuracy."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.core import build_plan, catalog
from ephys_qc.method_registry import methods
from ephys_qc.modules import ModuleContext, get_handler, module_specs, run_module

SCI = importlib.util.find_spec('numpy') and importlib.util.find_spec('mne')


def record():
    return {'id': 'ecog-fixture', 'modality': 'ecog', 'metadata': {
        'format': 'FIF', 'duration_seconds': 300., 'size_bytes': 1000,
        'channels': [{'index': i, 'name': 'G' + str(i), 'unit': 'V',
                      'sampling_rate_hz': 256., 'channel_type': 'ecog',
                      'channel_type_source': 'file_declared'} for i in [2, 7]]},
        'default_config': {'selection': {'eeg_indices': [7, 2], 'reference_indices': {},
            'start_seconds': 10., 'duration_seconds': 60.}, 'method_config': {'ecog': {
                'psd_window_seconds': 4., 'line_frequencies_hz': [50, 60]}}}}


class EcogPlanTests(unittest.TestCase):
    def test_catalog_and_registry_use_independent_ecog_handlers(self):
        rows = catalog('ecog')
        self.assertEqual(len(rows), 9)
        self.assertTrue(next(r for r in rows if r['id'] == 'M06')['selectable'])
        ids = {r['id'] for r in methods('ecog')}
        self.assertTrue({'ecog_continuity', 'ecog_welch_psd', 'ecog_channel_description'} <= ids)
        self.assertFalse(ids & {'continuity', 'prep_nonspatial', 'spectral_model', 'hf_burst', 'mne_lof'})
        for spec in module_specs('ecog'):
            handler = get_handler(spec['id'], 'ecog')
            self.assertEqual(handler.__module__ + ':run', spec['entrypoint'])
        for method in methods('ecog'):
            self.assertEqual(method['supported_modalities'], [] if method['implementation'] == 'planned' else ['ecog'])
            self.assertEqual(method['intended_modalities'], ['ecog'] if method['implementation'] == 'planned' else [])
            self.assertIsInstance(method['documentation']['when_to_use'], str)
        self.assertTrue(any(m['id'] == 'prep_nonspatial' for m in methods()))

    def test_short_single_contact_has_no_scalp_group_gate_m06_is_skipped(self):
        r = record(); r['default_config']['selection'].update(eeg_indices=[7], duration_seconds=1.)
        p = build_plan(r, ['M03', 'M04', 'M05', 'M06'])
        nodes = {n['id']: n for n in p['nodes']}
        self.assertEqual(nodes['M05']['status'], 'ready')
        self.assertEqual(nodes['M04']['status'], 'partial')
        self.assertEqual(nodes['M06']['status'], 'skipped')
        self.assertEqual(p['analysis_profile'], 'ecog-basic/1')
        self.assertEqual(nodes['M06']['depends_on'], ['M02'])
        p6 = build_plan(r, ['M06']); self.assertNotIn('M03', p6['selected_modules'])

    def test_scalp_parameters_and_extensions_are_rejected_without_mutation(self):
        for patch_ in [{'continuity': {}}, {'spectral': {'line_frequency_hz': 50}},
                       {'muscle': {}}, {'bad_channels': {}}, {'events': {}},
                       {'comparison_groups': ['a','a']}, {'extensions': ['mne_amplitude']},
                       {'extension_parameters': {'mne_muscle': {}}},
                       {'ecog': {'alpha_band': [8,12]}}]:
            with self.subTest(parameters=patch_):
                r = record(); original = copy.deepcopy(r)
                with self.assertRaises(ValueError): build_plan(r, qc_config={'method_config': patch_})
                self.assertEqual(r, original)

    def test_config_finite_strict_and_identity_stable(self):
        r = record(); p = build_plan(r)
        self.assertEqual(p['plan_id'], build_plan(json.loads(json.dumps(r, sort_keys=True)))['plan_id'])
        for value in [0, -1, True, float('nan'), float('inf'), 121]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_plan(r, qc_config={'method_config': {'ecog': {'psd_window_seconds': value}}})
        self.assertNotEqual(p['plan_id'], build_plan(r, qc_config={'method_config': {'ecog': {'psd_window_seconds': 2}}})['plan_id'])
        for value in [[], [50,50], [True], [-50], [float('nan')]]:
            with self.assertRaises(ValueError): build_plan(r, qc_config={'method_config': {'ecog': {'line_frequencies_hz': value}}})

    def test_channel_types_require_modality_confirmation_not_names(self):
        for kind in ['eeg','seeg','mag','stim']:
            r = record(); r['metadata']['channels'][0]['channel_type'] = kind
            with self.subTest(kind=kind), self.assertRaises(ValueError): build_plan(r)
        r = record(); r['metadata']['format'] = 'BrainVision'
        for c in r['metadata']['channels']: c.update(channel_type='eeg', channel_type_source='reader_default')
        self.assertEqual(build_plan(r)['input_modality']['value'], 'ecog')
        r['metadata']['channels'][0]['channel_type_source'] = 'file_declared'
        with self.assertRaises(ValueError): build_plan(r)
        r = record(); r['modality'] = 'seeg'
        with self.assertRaises(ValueError): build_plan(r)

    def test_whole_plan_covers_all_samples_without_scalp_parameters(self):
        p = build_plan(record(), ['M03','M04','M05'], {'scope': 'recording', 'recording_options': {'window_seconds': 120}})
        self.assertEqual(p['analysis_profile'], 'ecog-basic/1')
        self.assertEqual(len(p['windows']), 3)
        self.assertEqual(p['coverage_plan']['available_seconds'], 300.)
        self.assertEqual(p['qc_config']['method_config']['extensions'], [])

    def test_catalog_import_is_lightweight(self):
        code = '''import importlib.abc,sys
sys.path.insert(0,sys.argv[1])
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'numpy','scipy','mne','brainelecqc','matplotlib','apps'}: raise AssertionError(fullname)
sys.meta_path.insert(0,Block())
from ephys_qc.core import catalog
from ephys_qc.modules import module_specs,get_handler
assert len(catalog('ecog'))==9
for spec in module_specs('ecog'): get_handler(spec['id'],'ecog')
'''
        subprocess.run([sys.executable, '-c', code, str(REPO/'src')], check=True, capture_output=True)


@unittest.skipUnless(SCI, 'Scientific dependencies required')
class EcogNumericalTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.saved = {}

    def tearDown(self): self.temp.cleanup()

    def context(self, data, *, fs=256., first=2560, start=10., params=None, record_extra=None):
        row = {'id': 'test', 'status': 'completed', 'reason': 'ready', 'summary': {}, 'artifacts': []}
        state = {'data': self.np.asarray(data, dtype=float), 'fs': fs, 'first': first, 'start': start,
                 'channels': [{'source_index': i*5+2, 'channel_id': f'test:ch:{i*5+2}', 'raw_name': 'G'+str(i)} for i in range(len(data))]}
        def save(name,payload,attached): self.saved[name] = payload; attached['artifacts'].append(name)
        return ModuleContext(record={'modality':'ecog', **(record_extra or {})}, plan={},
            config={'method_config':{'ecog': params or {}}},state=state,result={},row=row,
            source=self.root/'source',root=self.root,artifacts=self.root,write_artifact=save)

    def test_continuity_exact_runs_retain_source_clock_and_nonfinite_identity(self):
        x = [[1,2,2,2,3,float('nan'),float('inf'),4,4]]
        c = self.context(x, fs=10., first=1000, start=12.)
        original = c.state['data'].copy(); run_module('M03', c)
        out = self.saved['M03_continuity.json']; candidates = out['candidates']
        self.assertEqual([(v['kind'],v['start_sample'],v['stop_sample']) for v in candidates],
                         [('nonfinite_samples',1005,1007),('exact_constant_samples',1001,1004),('exact_constant_samples',1007,1009)])
        self.assertEqual(candidates[1]['start_seconds'],12.1)
        self.assertTrue(all(v['source_index']==2 and v['quality_label'] is None for v in candidates))
        self.np.testing.assert_array_equal(c.state['data'],original)
        json.dumps(out, allow_nan=False)

    def test_dense_quantized_runs_are_counted_but_evidence_is_bounded(self):
        data=self.np.tile([0.,0.,1.,1.],6000)[None,:]
        c=self.context(data); run_module('M03',c)
        out=self.saved['M03_continuity.json']
        self.assertEqual(out['candidate_total_count'],12000)
        self.assertEqual(len(out['candidates']),10000)
        self.assertTrue(out['candidate_details_truncated'])
        self.assertEqual(out['channels'][0]['exact_constant_run_count'],12000)
        self.assertEqual(out['candidate_evidence']['omitted_interval_count'],2000)
        self.assertEqual(c.row['status'],'partial')
        self.assertTrue(c.result['warnings'])

    def test_psd_matches_scipy_and_sine_energy_no_classification(self):
        from scipy.signal import welch
        np=self.np; fs=256.; t=np.arange(2048)/fs; data=(2e-5*np.sin(2*np.pi*50*t))[None,:]
        c=self.context(data); original=data.copy(); run_module('M04',c)
        out=self.saved['M04_spectral.json']; f,p=welch(data[0],fs=fs,window='hann',nperseg=1024,noverlap=512,nfft=1024,detrend='constant',scaling='density',average='mean')
        np.testing.assert_allclose(out['psd']['frequencies_hz'],f,rtol=0,atol=0)
        np.testing.assert_allclose(out['psd']['power_v2_hz'][0],p,rtol=1e-14,atol=0)
        self.assertAlmostEqual(float(np.trapezoid(p,f)),2e-10,delta=1e-18)
        obs=out['line_noise']['observations'][0]
        self.assertAlmostEqual(obs['band_power_v2'],2e-10,delta=1e-18)
        self.assertEqual(obs['peak_frequency_hz'],50.)
        self.assertEqual(out['candidates'],[]); self.assertNotIn('flagged',obs)
        np.testing.assert_array_equal(c.state['data'],original)

    def test_odd_psd_grid_does_not_extrapolate_to_nyquist(self):
        c=self.context([list(range(255))],fs=256.,params={'psd_window_seconds':255/256,'line_frequencies_hz':[126.75]})
        run_module('M04',c); out=self.saved['M04_spectral.json']
        self.assertEqual(out['line_noise']['observations'][0]['status'],'outside_measurable_band')
        self.assertIsNone(out['line_noise']['observations'][0]['band_power_v2'])
        self.assertEqual(c.row['status'],'partial')

    def test_nonfinite_and_single_sample_psd_are_explicit_unassessed(self):
        for values in [[1.], [0.,float('nan'),1.]]:
            c=self.context([values]); run_module('M04',c)
            out=self.saved['M04_spectral.json']; self.assertIsNone(out['psd']['power_v2_hz'][0])
            self.assertEqual(c.row['status'],'partial'); json.dumps(out,allow_nan=False)

    def test_contact_statistics_do_not_use_source_bad_or_disease(self):
        values=[[1e-6,2e-6,float('nan'),3e-6],[float('nan')]*4]
        c=self.context(values, record_extra={'diagnosis':'epilepsy','source_bads':['G0']}); original=c.state['data'].copy()
        run_module('M05',c); out=self.saved['M05_channel_description.json']; rows=out['channels']
        self.assertEqual(rows[0]['finite_sample_count'],3)
        self.assertAlmostEqual(rows[0]['mean_volts'],2e-6)
        self.assertIsNone(rows[1]['rms_volts']); self.assertEqual(c.row['status'],'partial')
        self.assertEqual(out['candidates'],[]); self.assertFalse(out['classification_performed'])
        np=self.np; np.testing.assert_array_equal(c.state['data'],original)
        c2=self.context(values); run_module('M05',c2)
        self.assertEqual(out,self.saved['M05_channel_description.json'])
        json.dumps(out,allow_nan=False)

    def test_toolkit_window_and_whole_use_ecog_handlers_and_preserve_source(self):
        from test_readers import brainvision_fixture
        from ephys_qc.toolkit import prepare_recording,run_modules
        from ephys_qc.annotations import file_sha256
        path,_=brainvision_fixture(self.root)
        cfg={'selection':{'eeg_indices':[1,0],'reference_indices':{},'start_seconds':1.,'duration_seconds':2.},
             'method_config':{'ecog':{'psd_window_seconds':1.,'line_frequencies_hz':[10]}}}
        rec=prepare_recording(path,record_id='ecog-test',modality='ecog',qc_config=cfg)
        hashes={p.name:file_sha256(p) for p in self.root.iterdir() if p.is_file()}
        # Any accidental reuse of scalp measurement modules must fail this test.
        with patch('ephys_qc.modules.m03.run',side_effect=AssertionError('scalp continuity called')),patch('ephys_qc.modules.m04.run',side_effect=AssertionError('scalp spectral called')),patch('ephys_qc.modules.m05.run',side_effect=AssertionError('scalp bad channels called')):
            result=run_modules(rec,self.root/'window',['M03','M04','M05','M06'])
            whole=run_modules(rec,self.root/'whole',['M03','M04','M05'],qc_config={'scope':'recording','recording_options':{'window_seconds':1.5}})
        self.assertEqual(result['analysis_profile'],'ecog-basic/1')
        self.assertFalse(any(m['status']=='failed' for m in result['modules']))
        self.assertEqual(next(m for m in result['modules'] if m['id']=='M06')['status'],'skipped')
        self.assertEqual(result['recording']['source_indices'],[1,0])
        self.assertIsNone(result['score']['value'])
        self.assertEqual(whole['coverage']['completed_samples'],400)
        self.assertEqual(len(whole['windows']),3)
        self.assertEqual(whole['analysis_profile'],'ecog-basic/1')
        page=(self.root/'window/artifacts/report.html').read_text()
        self.assertIn('ECoG QC',page); self.assertIn('独立描述统计',page)
        for name,digest in hashes.items(): self.assertEqual(file_sha256(self.root/name),digest)
        environment=json.loads((self.root/'window/artifacts/environment.json').read_text())
        self.assertEqual(environment['adapter'],'ecog_descriptive_measurements')
        actual=environment['actual_executed_sources']
        self.assertIn('ephys_qc.ecog_config',actual)
        self.assertIn('ephys_qc.modules.m01',actual)
        self.assertIn('ephys_qc.modules.ecog.m04',actual)
        self.assertNotIn('ephys_qc.modules.m04',actual)
        for entry in actual.values(): self.assertEqual(file_sha256(entry['file']),entry['sha256'])
        self.assertTrue(all('modules/ecog/' in s['file'] for s in environment['method_sources'].values()))

if __name__=='__main__': unittest.main()
