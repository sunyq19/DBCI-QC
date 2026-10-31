"""Published document links must resolve to an allowlisted page and exact anchor."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'apps/workbench'))
from standards_page import DOCUMENT_PAGES, MODULE_TITLES, render_standards
from ephys_qc.modalities import ROUTES


class PageLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.ids = [], set()
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])
        if 'id' in attrs:
            self.ids.add(attrs['id'])


class DocumentLinkTests(unittest.TestCase):
    def test_all_published_internal_pages_and_anchors_resolve(self):
        pages = {}
        for lang, folder, prefix in [('zh-CN', ROOT/'docs', ''), ('en', ROOT/'docs/en', '/en')]:
            for slug, (filename, _, _) in DOCUMENT_PAGES.items():
                pages[prefix+'/standards/'+slug] = PageLinks(render_standards((folder/filename).read_text(), lang=lang, modality=slug))
            for modality, route in ROUTES.items():
                base = prefix+'/standards'+('/'+route['slug'] if route['slug'] else '')
                docdir = folder/route['slug'] if route['slug'] else folder
                pages[base] = PageLinks(render_standards((docdir/'qc-standards.md').read_text(), lang=lang, modality=modality))
                for module in MODULE_TITLES:
                    pages[base+'/modules/'+module] = PageLinks(render_standards((docdir/'modules'/f'{module}.md').read_text(), module, lang, modality))
        for origin, page in pages.items():
            for href in page.links:
                parsed = urlsplit(href)
                if parsed.scheme or parsed.netloc or parsed.path == '/':
                    continue
                target = parsed.path or origin
                if target.endswith('.md'):
                    target = target[:-3]
                self.assertIn(target, pages, (origin, href))
                if parsed.fragment:
                    self.assertIn(unquote(parsed.fragment), pages[target].ids, (origin, href))


if __name__ == '__main__':
    unittest.main()
