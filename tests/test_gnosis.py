"""Gnosis selection, input preservation, clock mapping and original-call contracts."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ephys_qc.gnosis_catalog import IDS, URL
from ephys_qc.gnosis_runtime import evaluate_extension,run_extension,settings
from ephys_qc.method_registry import methods
from ephys_qc.planning import build_plan
from test_research_methods import record


def facts(**kw):
    return dict(modality='scalp_eeg',verified_voltage=True,n_eeg=8,sampling_rate_hz=256,
                window_seconds=30.,reference_scheme='common_reference',comparison_groups={'all':8},**kw)


class GnosisContracts(unittest.TestCase):
    def test_catalog_selection_and_source_are_explicit(self):
        rows=[m for m in methods() if m['id'] in IDS]
        self.assertEqual(len(rows),8)
        self.assertTrue(all(m['source']['url']==URL and m['optional_extension'] for m in rows))
        for modality in ['ecog','seeg','extracellular']:
            self.assertFalse(IDS & {m['id'] for m in methods(modality)})
        r=record('scalp_eeg');r['default_config']['method_config']['comparison_groups']=['all']*24
        base=build_plan(r,None)
        self.assertTrue(all(not m['selected'] for m in base['method_applicability'] if m['id'] in IDS))
        for mid in IDS:
            plan=build_plan(r,[],{'method_config':{'extensions':[mid]}})
            self.assertEqual([m['id'] for m in plan['method_applicability'] if m['id'] in IDS and m['selected']],[mid])

    def test_gate_rejects_unsupported_data_without_scientific_imports(self):
        with patch.object(Path,'read_text',side_effect=AssertionError('No runtime IO in planning')):
            for mid in IDS:
                self.assertEqual(evaluate_extension(mid,facts())['status'],'ready')
                for fields in [dict(modality='seeg'),dict(verified_voltage=False),dict(sampling_rate_hz=100),
                               dict(reference_scheme='bipolar'),dict(preprocessing_lowpass_hz=40),dict(comparison_groups={}),dict(window_seconds=1)]:
                    self.assertEqual(evaluate_extension(mid,{**facts(),**fields})['status'],'blocked')
                with self.assertRaises(ValueError):evaluate_extension(mid,facts(),{'unknown':1})
                with self.assertRaises(ValueError):evaluate_extension(mid,facts(),{'prepare_copy':'false'})

    def test_original_worker_all_leaves_and_time_origin(self):
        try: settings()
        except (OSError,ValueError):self.skipTest('Separately installed Gnosis runtime required')
        import numpy as np
        x=np.random.default_rng(14).normal(0,5e-6,(8,30*256))
        x[0,10*256:12*256]+=5e-4
        saved=x.copy()
        for mid in sorted(IDS):
            p={'exclude_artifacts':False} if mid in {'gnosis_band_power','gnosis_band_amplitude','gnosis_psd_deviation','gnosis_reference_ranges'} else {}
            result=run_extension(mid,x,256,[f'C{i}' for i in range(8)],100.,p,facts=facts())
            with self.subTest(mid=mid):
                self.assertEqual(result['status'],'completed',result['reason'])
                self.assertTrue(result['calculated']);self.assertTrue(result['input_unchanged'])
                np.testing.assert_array_equal(x,saved)
                self.assertEqual(result['upstream']['packages']['SignalQualityEval'],'3.0.0')
                self.assertFalse(result['preprocessing']['ica'])
                self.assertNotIn('score',result)
                for candidate in result['candidates']:
                    if candidate.get('start_seconds') is not None:
                        self.assertGreaterEqual(candidate['start_seconds'],100)
                        self.assertLessEqual(candidate['stop_seconds'],130)
                if mid=='gnosis_artifact':
                    self.assertGreater(result['metrics']['ratio_by_channel']['C0'],0)
                if mid=='gnosis_band_power':
                    self.assertFalse(any('bands_amp' in n or 'get_Artifact' in n for n in result['upstream_calls']))
                    for ch in result['channel_names']:
                        self.assertAlmostEqual(sum(r['value'] for r in result['metrics']['relative_power'] if r['channel_name']==ch),1.,places=6)


if __name__=='__main__':unittest.main()
