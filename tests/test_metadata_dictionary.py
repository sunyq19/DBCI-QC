"""Design contract drift and real-source mapping regressions; no runtime API claim."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.util.spec_from_file_location('build_metadata_dictionary', ROOT/'scripts/build_metadata_dictionary.py')
generator = importlib.util.module_from_spec(loader)
loader.loader.exec_module(generator)


class MetadataDictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((ROOT/'specs/metadata-fields.v1.json').read_text())
        cls.examples = json.loads((ROOT/'examples/metadata/real-source-mappings.json').read_text())
        cls.fields = {f['id']: f for g in cls.spec['groups'] for f in g['fields']}
        cls.cases = {c['id']: c for c in cls.examples['cases']}

    def test_generated_languages_have_no_catalog_drift(self):
        for lang, filename in [('zh-CN', 'docs/metadata-fields.md'), ('en', 'docs/en/metadata-fields.md')]:
            self.assertEqual((ROOT/filename).read_text(), generator.render(self.spec, lang))
        self.assertEqual(len(self.fields), sum(len(g['fields']) for g in self.spec['groups']))
        for field in self.fields.values():
            self.assertIn(field['value_type'], self.spec['value_types'])
            self.assertEqual(set(field['definition']), {'zh-CN', 'en'})
        self.assertEqual(self.spec['status'], 'design_contract_not_runtime_api')

    def test_examples_have_source_fingerprints_and_known_fields(self):
        self.assertEqual(self.examples['dictionary_version'], self.spec['dictionary_version'])
        references = {s['path'] for s in self.examples['sources']}
        for source in self.examples['sources']:
            self.assertRegex(source['sha256'], r'^[0-9a-f]{64}$')
            self.assertGreater(source['size_bytes'], 0)
            self.assertFalse(Path(source['path']).is_absolute())
        for case in self.cases.values():
            for key, field in case['fields'].items():
                self.assertIn(key, self.fields)
                self.assertIn(field['status'], self.spec['field_statuses'])
                self.assertIn(field['confirmation'], self.spec['confirmation_states'])
                if field['status'] != 'known':
                    self.assertIsNone(field['value'])
                self.assertTrue(field['source'])
                for source in field['source']:
                    self.assertIn(source['reference'], references)
                    self.assertIn(source['kind'], self.spec['source_kinds'])
                    self.assertTrue(source['locator'])

    def test_age_missingness_units_and_time_basis_are_preserved(self):
        human = self.cases['human-eeg']['fields']
        self.assertEqual(human['subject.age']['status'], 'unknown')
        self.assertEqual(human['subject.background']['status'], 'unknown')
        monkey = self.cases['monkey-ecog']['fields']['subject.age']['value']
        self.assertEqual((monkey['lower'], monkey['upper'], monkey['unit'], monkey['at']), (9, 9, 'year', 'experiment_start'))
        mouse = self.cases['mouse-lfp']['fields']['subject.age']['value']
        self.assertEqual((mouse['lower'], mouse['upper'], mouse['unit'], mouse['source_text']), (6.4, 6.4, 'month', 'P6.4M'))
        self.assertEqual(mouse['at'], 'source_unspecified')
        for case in self.cases.values():
            self.assertNotIn('subject.life_stage', case['fields'])

    def test_duration_conflict_is_not_silently_resolved(self):
        value = self.cases['monkey-ecog']['fields']['recording.duration_seconds']
        self.assertEqual(value['status'], 'conflict')
        self.assertIsNone(value['value'])
        self.assertEqual({v['value'] for v in value['alternatives']}, {195.047, 196})
        observed = self.cases['monkey-ecog']['observations']
        self.assertEqual(observed['file_numeric_channel_count'], 50)
        self.assertEqual(observed['file_annotation_signal_count'], 1)
        self.assertEqual(observed['sidecar_total_channel_count'], 49)

    def test_generic_lfp_does_not_become_neuropixels(self):
        mouse = self.cases['mouse-lfp']['fields']
        self.assertEqual(mouse['acquisition.hardware']['value']['manufacturer'], 'Neuronexus')
        self.assertEqual(mouse['recording.sample_count']['value'], 274737)
        self.assertEqual(mouse['recording.sampling_rate_hz']['value'], 1000)
        self.assertIn('NOT Neuropixels', self.cases['mouse-lfp']['scope'])


if __name__ == '__main__':
    unittest.main()
