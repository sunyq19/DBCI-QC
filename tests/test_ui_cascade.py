"""Real DOM-selector cascade regression checks, not browser geometry/visual QA.

Install tests/requirements-ui.txt; run PYTHONPATH=tests python -m unittest test_ui_cascade.
"""
import unittest

from ui_cascade import Cascade, WEB


SHEETS = [WEB/name for name in ['styles.css', 'datasets.css', 'ui-tokens.css', 'workbench-ui.css']]
INDEX = (WEB/'index.html').read_text()
WIDTHS = (320, 480, 768, 1001, 1440)
RAILS = ('demo-reports', 'data-library', 'run-history-panel', 'toolkit-section')


class UICascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {width: Cascade(INDEX, SHEETS, width) for width in WIDTHS}

    def test_peer_disclosures_have_matching_insets_and_typography(self):
        for width, page in self.pages.items():
            with self.subTest(width=width):
                values = []
                for identifier in RAILS:
                    node = page.ids[identifier]
                    summary = page.child(node, 'summary')
                    values.append((page.value(node, 'padding-left'), page.value(node, 'padding-right'),
                        page.value(summary, 'padding-left'), page.value(summary, 'padding-right'),
                        page.value(summary, 'font-size'), page.value(summary, 'font-weight'),
                        page.value(summary, 'line-height'), page.value(summary, 'min-height')))
                self.assertEqual(len(set(values)), 1, dict(zip(RAILS, values)))
                self.assertEqual(values[0][4], '14px')
                self.assertEqual(values[0][5], '500')
                self.assertEqual(values[0][6], '1.5')

    def test_each_disclosure_uses_same_content_insets(self):
        for width, page in self.pages.items():
            values = []
            for identifier in RAILS:
                node = page.ids[identifier]
                content = next(c for c in node.iter_children() if 'disclosure-content' in c.classes)
                values.append(tuple(page.value(content, 'padding-'+side) for side in ['top', 'right', 'bottom', 'left']))
            self.assertEqual(len(set(values)), 1, (width, dict(zip(RAILS, values))))

    def test_left_rail_examples_do_not_inherit_viewport_two_column_layout(self):
        for width, page in self.pages.items():
            node = page.ids['demo-report-list']
            value = page.value(node, 'grid-template-columns').replace(' ', '')
            self.assertIn(value, ('none', '1fr', 'minmax(0,1fr)'),
                          f'{width}px: {value}; {page.source(node, "grid-template-columns")}')

    def test_hidden_elements_stay_hidden_despite_component_display_rules(self):
        for width, page in self.pages.items():
            for node in page.nodes:
                if 'hidden' in node.etree_element.attrib:
                    self.assertEqual(page.value(node, 'display'), 'none',
                        f'{width}px {node.id or node.local_name}: {page.source(node, "display")}')

    def test_open_table_disclosures_have_only_one_toggle_symbol(self):
        for state in ('', 'open'):
            html = f'<html><body class="qc-app"><table class="dataset-table"><tr><td><details {state}><summary id="toggle">Evidence</summary><p>Body</p></details></td></tr></table></body></html>'
            page = Cascade(html, SHEETS)
            node = page.ids['toggle']
            before = page.value(node, 'content', 'before')
            after = page.value(node, 'content', 'after').strip('"\'')
            self.assertIn(before, ('none', 'normal', '""', "''"), page.source(node, 'content', 'before'))
            self.assertEqual(after, '−' if state else '+')
            self.assertEqual(page.value(node, 'position', 'after'), 'static')

    def test_module_detail_io_stacks_on_narrow_screens(self):
        html = '<html><body class="qc-app"><dialog id="module-dialog" open><div id="module-dialog-content"><div class="method-io" id="io"><div>Input</div><div>Output</div></div></div></dialog></body></html>'
        for width in (320, 480, 620):
            page = Cascade(html, SHEETS, width)
            self.assertEqual(page.value(page.ids['io'], 'grid-template-columns').replace(' ', ''), 'minmax(0,1fr)')

    def test_toolbox_focus_indicator_stays_inside_clipped_card(self):
        html = '<html><body class="qc-app"><details class="toolkit-module"><summary id="focus">Module</summary></details></body></html>'
        page = Cascade(html, SHEETS, focus_visible=('focus',))
        node = page.ids['focus']
        self.assertEqual(page.value(node, 'outline-offset'), '-3px', page.source(node, 'outline-offset'))


if __name__ == '__main__':
    unittest.main()
