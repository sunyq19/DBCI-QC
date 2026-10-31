"""Source-reviewed adapters require explicit selection and preserve default policy."""
import copy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ephys_qc.method_registry import methods
from ephys_qc.method_descriptions import method_documentation
from ephys_qc.modalities import default_methods
from ephys_qc.planning import build_plan
from ephys_qc.recommendations import recommend
from ephys_qc.research_methods import research_methods

EXPECTED = {
    'scalp_eeg': {'faster_channels', 'asr_bursts', 'cleanline', 'zapline_plus', 'fieldtrip_zvalue'},
    'ecog': {'fieldtrip_zvalue'}, 'seeg': {'fieldtrip_zvalue'},
    'extracellular': {'spikeinterface_bad_channels'},
}


def record(modality):
    probe = modality == 'extracellular'
    metadata = {'format': 'SpikeGLX' if probe else 'FIF', 'duration_seconds': 60.,
                'size_bytes': 1000, 'channels': [
                    {'index': i, 'name': f'C{i}', 'unit': 'V',
                     'sampling_rate_hz': 30000 if probe else 512,
                     'channel_type': 'neuropixels' if probe else 'eeg' if modality == 'scalp_eeg' else modality,
                     'channel_type_source': 'file_declared'} for i in range(24)]}
    if probe:
        metadata['acquisition'] = {'stream_band': 'ap', 'probe_type': 0}
    return {'id': 'research-gate-fixture', 'modality': modality, 'metadata': metadata,
            'source_path': '/not-opened/source', 'expected_sha256': 'a' * 64,
            'reference_scheme': 'common_reference', 'default_config': {
                'selection': {'eeg_indices': list(range(24)), 'reference_indices': {},
                              'start_seconds': 0., 'duration_seconds': 30.},
                'method_config': default_methods(modality, metadata)}}


class ResearchCatalogueTests(unittest.TestCase):
    def test_routes_expose_candidates_without_claiming_supported_execution(self):
        for modality, expected in EXPECTED.items():
            rows = methods(modality)
            candidates = [r for r in rows if r.get('reviewed_on')]
            self.assertEqual({r['id'] for r in candidates}, expected)
            self.assertEqual(len({r['id'] for r in rows}), len(rows))
            for row in candidates:
                self.assertEqual(row['implementation'], 'available')
                self.assertTrue(row['optional_extension'])
                self.assertEqual(row['supported_modalities'], [modality])
                self.assertEqual(row['intended_modalities'], [])
                self.assertTrue(row['scope_note'])
                self.assertNotIn('尚无', row['documentation']['upstream_call'])

    def test_selecting_all_modules_does_not_select_research_methods(self):
        for modality, expected in EXPECTED.items():
            plan = build_plan(record(modality), [f'M{i:02d}' for i in range(1, 10)])
            candidates = {r['id']: r for r in plan['method_applicability'] if r['id'] in expected}
            self.assertEqual(set(candidates), expected)
            for item in candidates.values():
                self.assertEqual(item['status'], 'not_selected')
                self.assertFalse(item['selected'])

    def test_only_matching_modalities_allow_explicit_extensions(self):
        all_ids = set.union(*EXPECTED.values())
        for modality, allowed in EXPECTED.items():
            for identifier in all_ids:
                r = record(modality)
                r['default_config']['method_config']['extensions'] = [identifier]
                if identifier in allowed:
                    plan = build_plan(r, [])
                    row = next(m for m in plan['method_applicability'] if m['id'] == identifier)
                    self.assertTrue(row['selected'])
                    self.assertIn(row['status'], {'ready', 'partial', 'blocked'})
                else:
                    with self.assertRaises(ValueError):
                        build_plan(r, [])

    def test_research_catalogue_does_not_change_recommended_config_or_selected_modules(self):
        for modality in EXPECTED:
            r = record(modality)
            original = copy.deepcopy(r)
            with patch('ephys_qc.research_runtime.extension_specs', return_value=[]):
                baseline = recommend(r)
            actual = recommend(r)
            self.assertTrue(actual['can_apply'], actual)
            for key in ('selected_modules', 'qc_config', 'quality_score'):
                self.assertEqual(actual[key], baseline[key], (modality, key))
            self.assertEqual(r, original)
            self.assertIsNone(actual['quality_score'])
            self.assertFalse(EXPECTED[modality] & {m['id'] for m in actual['recommended_methods']})
            self.assertFalse(EXPECTED[modality] & set(actual['qc_config']['method_config']['extensions']))

    def test_new_descriptions_and_translations_remain_complete_and_independent(self):
        js = (ROOT / 'apps/workbench/web/i18n.js').read_text()
        pairs = json.loads(js.split('const researchPairs = ', 1)[1].split(';\n  // END reviewed research methods', 1)[0])
        translations = dict(pairs)
        for modality in EXPECTED:
            for row in research_methods(modality):
                doc = method_documentation(row['id'])
                self.assertEqual(doc, row['documentation'])
                for key, value in doc.items():
                    if key != 'references' and re.search('[\u3400-\u9fff]', value):
                        self.assertIn(value, translations, (row['id'], key))
                        self.assertFalse(re.search('[\u3400-\u9fff]', translations[value]))
                row['documentation']['references'].clear()
                self.assertTrue(method_documentation(row['id'])['references'])

    def test_cleaning_and_sorted_unit_boundaries_are_explicit(self):
        asr = next(r for r in research_methods('scalp_eeg') if r['id'] == 'asr_bursts')
        self.assertIn('UC', asr['source']['license'])
        for identifier in ('asr_bursts', 'cleanline', 'zapline_plus'):
            doc = method_documentation(identifier)
            self.assertIn('工程回归', doc['validation_status'])
        np = research_methods('extracellular')[0]
        self.assertIn('不是分选单元质量', np['documentation']['interpretation'])
        self.assertIn('shank', np['documentation']['when_to_use'])
        self.assertFalse(any('bombcell' in r['id'] or 'unit_quality' in r['id']
                             for r in methods('extracellular')))


if __name__ == '__main__':
    unittest.main()
