"""Functional grouping does not change activation gates or claim new modalities."""
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from ephys_qc.method_registry import methods, tool_domains


class MethodDomainTests(unittest.TestCase):
    def test_domains_cover_nine_modules_once_in_stable_functional_order(self):
        domains = tool_domains()
        self.assertEqual([d['id'] for d in domains], ['data_intake', 'signal_integrity',
            'spectrum_interference', 'channel_quality', 'artifacts', 'events_sync', 'reporting'])
        modules = [mid for domain in domains for mid in domain['module_ids']]
        self.assertEqual(sorted(modules), [f'M{i:02d}' for i in range(1, 10)])
        self.assertEqual(next(d['label'] for d in domains if d['id'] == 'events_sync'), '事件与时间')
        self.assertNotIn('spike_unit', [d['id'] for d in domains])
        domains[0]['module_ids'].clear()
        self.assertEqual(tool_domains()[0]['module_ids'], ['M01', 'M02'])

    def test_every_method_including_extensions_has_its_module_domain(self):
        expected = {mid: (d['id'], d['label']) for d in tool_domains() for mid in d['module_ids']}
        rows = methods()
        self.assertTrue(any(row['optional_extension'] for row in rows))
        self.assertTrue(any(row['implementation'] == 'planned' for row in rows))
        for row in rows:
            with self.subTest(id=row['id']):
                self.assertEqual((row['domain'], row['domain_label']), expected[row['module_id']])
        # The grouping is stable across independent catalog snapshots.
        self.assertEqual({r['id']: r['domain'] for r in rows}, {r['id']: r['domain'] for r in methods()})

    def test_category_is_preserved_as_activation_not_cross_modality_support(self):
        activation = {'basic': ('with_module', '随模块运行'),
                      'conditional': ('conditional', '满足条件'),
                      'optional': ('manual_extension', '手动扩展')}
        for row in methods():
            with self.subTest(id=row['id']):
                self.assertEqual((row['activation'], row['activation_label']), activation[row['category']])
                self.assertIn('头皮 EEG', row['scope_note'])
                self.assertIn('其他', row['scope_note'])
                if row['implementation'] == 'planned':
                    self.assertEqual(row['supported_modalities'], [])
                    self.assertEqual(row['intended_modalities'], ['scalp_eeg'])
                    self.assertIn('尚未接入', row['scope_note'])
                else:
                    self.assertEqual(row['supported_modalities'], ['scalp_eeg'])
                    self.assertEqual(row['intended_modalities'], [])
        first = methods(); first[0]['supported_modalities'].append('seeg')
        self.assertEqual(methods()[0]['supported_modalities'], ['scalp_eeg'])


if __name__ == '__main__': unittest.main()
