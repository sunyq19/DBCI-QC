"""Presentation contracts: no recomputation, source separation, units and missing data."""
import copy
import json
from pathlib import Path
import sys
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ephys_qc.visualizations import visualization_specs
from ephys_qc.visualizations.render import render_gallery, bars, spectrum
from ephys_qc.visualizations.evidence import read_evidence

class VisualizationTests(unittest.TestCase):
    def test_individual_selection_never_reads_unselected_evidence(self):
        data={'status':'completed','calculated':True,'metrics':{'relative_power':[{'channel_name':'C3','band':'alpha','value':.4},{'channel_name':'C4','band':'alpha','value':None}]}}
        old=copy.deepcopy(data);reads=[]
        def load(name):reads.append(name);return data
        result={'artifacts':[{'name':'M04_gnosis_band_power.json'},{'name':'M05_bad_channels.json'}]}
        html=render_gallery(result,load,selected=['band_power'])
        self.assertEqual(reads,['M04_gnosis_band_power.json']);self.assertEqual(data,old)
        self.assertIn('40',html);self.assertIn('未评',html);self.assertIn('0 → 100 %',html)
        self.assertIn('Gnosis-Neurodynamics',html)
        self.assertNotIn('id="viz_psd"',html)
    def test_empty_and_failed_results_are_not_zero(self):
        result={'artifacts':[{'name':'M04_gnosis_band_power.json'}]}
        html=render_gallery(result,lambda _:dict(status='failed',calculated=False,metrics={'relative_power':[dict(channel_name='X',band='alpha',value=.8)]}),selected=['band_power'])
        self.assertIn('对应指标未生成',html);self.assertNotIn('>80<',html)
        self.assertNotIn('id="viz_',render_gallery(result,lambda _: {},selected=[]))
    def test_scope_selection_does_not_merge_window_evidence(self):
        files=['w001--M02_selection.json','w002--M02_selection.json','w001--M04_gnosis_band_power.json','w002--M04_gnosis_band_power.json']
        reads=[]
        def load(n):reads.append(n);return {}
        render_gallery({'artifacts':[dict(name=n) for n in files]},load,selected=['band_power'],window='w002--')
        self.assertEqual(reads,['w002--M04_gnosis_band_power.json'])
        with self.assertRaises(ValueError):render_gallery({'artifacts':[]},load,window='../')
    def test_units_and_unsafe_labels(self):
        a=spectrum([1,2],[[1e-12,1e-11]],['C3'],1e12)
        b=spectrum([1,2],[[1,10]],['C3'],1)
        self.assertEqual(a,b)
        html=bars([('<script>alert(1)</script>',None,False),('X',2,True)],'%')
        self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html);self.assertIn('未评',html)
    def test_catalog_keeps_visualizations_out_of_algorithm_registry(self):
        from ephys_qc.method_registry import methods
        v=visualization_specs();self.assertEqual(len(v),12)
        self.assertEqual(sum(s['status']=='available' for s in v),10)
        self.assertFalse({s['id'] for s in v}&{m['id'] for m in methods()})
        with self.assertRaises(ValueError):render_gallery({},lambda _: {},selected=['radar'])

    def test_spectral_reader_preserves_window_counts_without_scan_arrays(self):
        from ephys_qc.report_view import line_summary
        rows=[dict(channel_id='C3',channel_name='C3',start_sample=0,stop_sample=100,
                   status='computed',flagged=flag,amplitude_uv=2,
                   scan_frequencies_hz=list(range(100))) for flag in [False,True]]
        original={'psd':{'power_v2_hz':[[1e-12]],'frequencies_hz':[1]},
                  'line_noise':{'observations':rows},'parameterization':{'unused':[1,2,3]}}
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'M04_spectral.json';path.write_text(json.dumps(original))
            loaded=read_evidence(path)
        self.assertEqual(loaded['psd'],original['psd'])
        a=line_summary(original['line_noise']);b=line_summary(loaded['line_noise'])
        for key in ['total','hits','percent','observed_frequency_rows']:
            self.assertEqual(a[key],b[key])
        self.assertEqual(b['channels'][0]['percent'],100)
        self.assertNotIn('parameterization',loaded)
        self.assertNotIn('scan_frequencies_hz',loaded['line_noise']['observations'][0])

if __name__=='__main__':unittest.main()
