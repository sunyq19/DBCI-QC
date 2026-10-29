"""English document navigation and exact internal links; no analysis or browser."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps' / 'workbench'))
from standards_page import (render_standards, Markdown, safe_url, MODULE_TITLES,
                            EN_MODULE_TITLES, _module_clause_id)


class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class DocumentLanguageTests(unittest.TestCase):
    def test_english_shell_download_and_language_links_use_same_document(self):
        page = render_standards('# EEG QC specification\n\n## 1 Scope\nScope text.', lang='en')
        elements = Elements(page).elements
        self.assertIn(('html', {'lang': 'en'}), elements)
        self.assertIn('QC Workbench', page)
        self.assertIn('Project technical specification · Consultation draft', page)
        self.assertIn('>Download source</a>', page)
        self.assertIn('>Contents</summary>', page)
        self.assertIn('>Module index</summary>', page)
        links = [attrs for tag, attrs in elements if tag == 'a']
        self.assertIn({'href': '/en/standards.md', 'download': 'qc-standards.md'}, links)
        self.assertTrue(any(a.get('href') == '/?lang=en' and a.get('id') == 'return-workbench' for a in links))
        self.assertTrue(any(a.get('href') == '/standards' and a.get('hreflang') == 'zh-CN' for a in links))
        self.assertTrue(any(a.get('href') == '/en/standards' and a.get('aria-current') == 'true' for a in links))
        self.assertNotIn('返回质控台', page)
        self.assertNotIn('EEG 质控工作台', page)

    def test_every_module_has_localized_index_clause_source_and_back_link(self):
        for identifier, title in EN_MODULE_TITLES.items():
            with self.subTest(module=identifier):
                page = render_standards(f'# {identifier} {title}\n\n## 1 Scope\nText.', identifier, lang='en')
                links = [attrs for tag, attrs in Elements(page).elements if tag == 'a']
                self.assertIn({'href': f'/en/standards/modules/{identifier}.md', 'download': f'{identifier}.md'}, links)
                self.assertTrue(any(a.get('href') == f'/?lang=en#module-{identifier}' for a in links))
                self.assertTrue(any(a.get('href') == '/en/standards#' + _module_clause_id(identifier, 'en') for a in links))
                selected = [a['href'] for a in links if a.get('aria-current') == 'page']
                self.assertEqual(selected, [f'/en/standards/modules/{identifier}'])
                self.assertEqual(sum(a.get('class') == 'module-nav-item' for a in links), 9)
                self.assertIn('Module guide · Current implementation', page)
                self.assertNotIn('Consultation draft', page)

    def test_english_clause_links_match_actual_generated_heading_ids(self):
        source = '# Specification\n\n## 5 Module requirements\n' + '\n'.join(
            f'### 5.{int(identifier[1:])} {identifier} {title}' for identifier, title in EN_MODULE_TITLES.items())
        markdown = Markdown(source)
        markdown.render()
        ids = {heading['id'] for heading in markdown.headings}
        for identifier in MODULE_TITLES:
            self.assertIn(_module_clause_id(identifier, 'en'), ids)

    def test_source_links_localize_but_source_text_code_and_external_urls_do_not(self):
        source = ('# Module\n\n[Clause](/standards#57-m07-状态与事件核对) · '
                  '[M02](/standards/modules/M02) · [English](/en/standards/modules/M03)\n\n'
                  '[External](https://example.test/standards)\n\n'
                  'Source text: /standards/modules/M02\n\n'
                  '`href="/standards/modules/M02"`\n')
        page = render_standards(source, 'M07', lang='en')
        self.assertIn('href="/en/standards#57-m07-state-and-event-checks"', page)
        self.assertIn('href="/en/standards/modules/M02"', page)
        self.assertIn('href="https://example.test/standards"', page)
        self.assertIn('Source text: /standards/modules/M02', page)
        self.assertIn('<code>href=&quot;/standards/modules/M02&quot;</code>', page)

    def test_english_allowlist_remains_exact_and_rejects_unknown_paths_queries(self):
        for url in ['/en/standards', '/en/standards#51-m01-data-intake-and-structure-checks', '/en/standards/modules/M09']:
            self.assertEqual(safe_url(url), url)
        for url in ['/en/standards/../private', '/en/standards/modules/M10', '/en/api/v1/jobs',
                    '/en/standards?run=true', '/en/standards/modules/M01.md', '//en/standards']:
            self.assertIsNone(safe_url(url), url)
        for lang in ['fr', 'en<script>', '../../en']:
            with self.assertRaises(ValueError):
                render_standards('# Test', lang=lang)

    def test_english_metadata_and_table_accessibility_are_localized(self):
        source = ('# Module\n\nModule guide · Workbench 0.5 · Document version: 0.2\n\n'
                  '| Field | Meaning |\n| --- | --- |\n| V | Volts |\n\n## Appendix A Sources\n')
        page = render_standards(source, 'M01', lang='en')
        self.assertIn('<p class="document-meta">Module guide · Workbench 0.5 · Document version: 0.2</p>', page)
        self.assertIn('aria-label="Table; scroll horizontally"', page)
        self.assertIn('<span class="section-number">Appendix A</span>', page)
        self.assertNotIn('表格，可横向滚动', page)

    def test_published_english_source_module_clause_links_match_main_document(self):
        main = REPO / 'docs' / 'en' / 'qc-standards.md'
        if not main.is_file():
            self.skipTest('English source documents are being authored separately')
        markdown = Markdown(main.read_text(encoding='utf-8'))
        markdown.render()
        ids = {heading['id'] for heading in markdown.headings}
        for identifier in EN_MODULE_TITLES:
            self.assertIn(_module_clause_id(identifier, 'en'), ids)
            module = REPO / 'docs' / 'en' / 'modules' / f'{identifier}.md'
            if not module.is_file():
                continue  # Individual modules are authored independently.
            page = render_standards(module.read_text(encoding='utf-8'), identifier, lang='en')
            for _, attributes in Elements(page).elements:
                href = attributes.get('href', '')
                if href.startswith('/en/standards#'):
                    self.assertIn(href.split('#', 1)[1], ids, f'{identifier}: {href}')


if __name__ == '__main__':
    unittest.main()
