"""Hierarchy is reusable without the workbench and cannot widen modality gates."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.toolkit import catalog, workflow
from ephys_qc.modalities import ROUTES
from ephys_qc.modules import get_handler


class WorkflowTests(unittest.TestCase):
    def test_same_hierarchy_covers_each_catalog_once(self):
        reference = workflow()['groups']
        for modality in ROUTES:
            with self.subTest(modality=modality):
                spec = workflow(modality)
                rows = catalog(modality)
                self.assertEqual(spec['groups'], reference)
                self.assertEqual([mid for group in spec['groups'] for mid in group['module_ids']],
                                 [row['id'] for row in rows])
                selectable = {row['id'] for row in rows if row.get('selectable', True)}
                self.assertTrue(set(spec['default_selected_modules']) <= selectable)

    def test_hierarchy_cannot_be_mutated_by_a_client_or_unknown_route(self):
        expected = copy.deepcopy(workflow())
        spec = workflow(); spec['groups'][0]['module_ids'].clear()
        spec['method_groups'][0]['label'] = 'changed'
        self.assertEqual(workflow(), expected)
        with self.assertRaises(ValueError): workflow('unknown')

    def test_shared_measurements_keep_modality_specific_entry_gates(self):
        from types import SimpleNamespace
        for modality in ('ecog', 'seeg', 'extracellular'):
            for mid in ('M03', 'M04', 'M05'):
                for other in ROUTES:
                    if other == modality: continue
                    # Gate must fail before touching even a missing signal state.
                    with self.subTest(modality=modality, module=mid, other=other):
                        with self.assertRaises(ValueError):
                            get_handler(mid, modality)(SimpleNamespace(record={'modality': other}))


if __name__ == '__main__': unittest.main()
