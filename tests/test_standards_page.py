"""Read-only standards routes and finite Markdown safety; no live QC jobs."""
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'apps' / 'workbench'))
import server as workbench_server
from standards_page import (Markdown, inline, render_standards, safe_url,
                            heading_tree, MODULE_TITLES, NAVIGATION_SCRIPT, PRINT_SCRIPT,
                            DOCUMENT_PAGES)


class Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


class MarkdownSafetyTests(unittest.TestCase):
    def test_raw_html_and_code_are_text_not_executable_markup(self):
        source = '''# 标准
<script>alert(1)</script><img src=x onerror=alert(2)>

**<svg onload=alert(3)>** and `<iframe src="file:///secret">`

```html
<script>alert(4)</script>
```
'''
        markup = Markdown(source).render()
        parsed = Elements(markup)
        self.assertFalse({'script', 'img', 'svg', 'iframe'} & {tag for tag, _ in parsed.elements})
        self.assertFalse(any(name.startswith('on') for _, attrs in parsed.elements for name in attrs))
        self.assertIn('<script>alert(1)</script>', ''.join(parsed.text))
        self.assertIn('<script>alert(4)</script>', ''.join(parsed.text))
        self.assertIn('<strong>&lt;svg', markup)

    def test_url_allowlist_rejects_executable_local_relative_and_obfuscated_links(self):
        unsafe = ['javascript:alert(1)', 'JavaScript:alert(1)', 'javascript&#58;alert(1)',
                  'java&#x09;script:alert(1)', 'data:text/html,hello', 'file:///etc/passwd',
                  'vbscript:hello', '//example.com/path', '/api/v1/jobs', '../private.md',
                  'https:\\example.com', 'https://', 'https://example.com/\nscript',
                  '%6aavascript:alert(1)']
        for url in unsafe:
            with self.subTest(url=url):
                self.assertIsNone(safe_url(url))
                self.assertNotIn('<a ', inline(f'[text]({url})'))
        self.assertEqual(safe_url('https://example.test/reference?a=1&amp;b=2'),
                         'https://example.test/reference?a=1&b=2')
        self.assertEqual(safe_url('#原始数据'), '#原始数据')

    def test_safe_links_keep_balanced_parentheses_and_escape_attributes(self):
        markup = inline('[**来源**](https://example.test/paper_(2024)?a=1&b=2) '
                        '[quoted](https://example.test/"onmouseover="bad)')
        links = [attrs for tag, attrs in Elements(markup).elements if tag == 'a']
        self.assertEqual(links[0]['href'], 'https://example.test/paper_(2024)?a=1&b=2')
        self.assertIn('<strong>来源</strong>', markup)
        self.assertTrue(all(set(attrs) <= {'href', 'rel'} for attrs in links))
        self.assertIn('noopener', links[0]['rel'])

    def test_source_images_never_load_remote_or_local_resources(self):
        parsed = Elements(inline('![secret](file:///secret) ![pixel](https://example.test/pixel.png)'))
        self.assertFalse(any(tag in {'img', 'a'} for tag, _ in parsed.elements))

    def test_unicode_heading_ids_are_unique_stable_and_match_contents(self):
        source = '# 文档\n## 原始数据\n## 原始数据\n## 原始数据-2\n## document\n## specification-navigation\n'
        page = render_standards(source)
        parsed = Elements(page)
        ids = [attrs['id'] for _, attrs in parsed.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in parsed.elements:
            if attrs.get('href', '').startswith('#'):
                self.assertIn(attrs['href'][1:], ids)
        self.assertIn('原始数据-2', ids)
        self.assertEqual(page, render_standards(source))

    def test_table_preserves_escaped_pipes_inline_code_alignment_and_extra_content(self):
        source = '''| 条目 | 值 | 状态 |
| :--- | ---: | :---: |
| A\\|B | `x|y` | **待复核** |
| extra | 2 | 保留 | 不丢弃 |
'''
        markup = Markdown(source).render()
        parsed = Elements(markup)
        self.assertEqual(sum(tag == 'table' for tag, _ in parsed.elements), 1)
        self.assertEqual(sum(tag == 'th' for tag, _ in parsed.elements), 3)
        self.assertEqual(sum(tag == 'td' for tag, _ in parsed.elements), 7)
        self.assertIn('A|B', ''.join(parsed.text))
        self.assertIn('<code>x|y</code>', markup)
        self.assertIn('不丢弃', markup)
        self.assertIn('class="align-right"', markup)
        self.assertIn('tabindex="0"', markup)

    def test_lists_paragraphs_and_fenced_code_have_distinct_structure(self):
        source = '''First paragraph
continued line.

- parent
  - nested
- next

3. third
4. fourth

```python
print("<data>")
```
'''
        markup = Markdown(source).render()
        self.assertIn('<p>First paragraph continued line.</p>', markup)
        self.assertIn('<li>parent<ul><li>nested</li></ul></li>', markup)
        self.assertIn('<ol start="3">', markup)
        self.assertIn('class="language-python"', markup)
        self.assertIn('&lt;data&gt;', markup)

    def test_download_print_return_navigation_and_responsive_document_are_present(self):
        markup = render_standards('# 标准\n## 范围\n正文')
        parsed = Elements(markup)
        self.assertIn(('a', {'href': '/standards.md', 'download': 'qc-standards.md'}), parsed.elements)
        back = next(attrs for tag, attrs in parsed.elements if attrs.get('id') == 'return-workbench')
        self.assertEqual(back['href'], '/')
        self.assertEqual(back['aria-keyshortcuts'], 'Alt+Q')
        self.assertTrue(any(tag == 'button' and attrs.get('id') == 'print-document' for tag, attrs in parsed.elements))
        self.assertEqual([attrs['src'] for tag, attrs in parsed.elements if tag == 'script'], ['/standards-navigation.js'])
        self.assertFalse(any(name.startswith('on') for _, attrs in parsed.elements for name in attrs))
        self.assertIn('@media print', markup)
        self.assertIn('overflow-x:auto', markup)
        self.assertIn('window.print()', PRINT_SCRIPT)
        self.assertIn('history.back()', PRINT_SCRIPT)

    def test_local_document_links_use_exact_allowlist_and_safe_fragments(self):
        permitted = ['/standards', '/standards#51-m01-数据接入与结构核验',
                     '/standards/modules/M01', '/standards/modules/M09#输入',
                     '/#module-M01', '/#module-M09', '#5-模块要求']
        for url in permitted:
            with self.subTest(url=url):
                self.assertEqual(safe_url(url), url)
                self.assertIn('<a ', inline(f'[说明]({url})'))
        forbidden = ['/', '/#module-M00', '/#module-M10', '/#anything',
                     '/standards?download=1', '/standards?', '/standards/modules/M01.md',
                     '/standards/modules/M10', '/standards/modules/m01',
                     '/standards/modules/M01/../../secret', '/standards/%2e%2e/secret',
                     '/standards/modules/%4d01', '//evil.test/standards',
                     '/standards#x%0aonclick', '/standards#%2fprivate', '/standards#x?y']
        for url in forbidden:
            with self.subTest(url=url):
                self.assertIsNone(safe_url(url))

    def test_h2_h3_h4_are_nested_tree_with_expandable_chapter_branches(self):
        markdown = Markdown('# 规范\n## 1 范围\n### 1.1 对象\n#### 1.1.1 输入\n'
                            '### 1.2 限制\n## 2 通用要求\n#### 2.1 跳级条款\n')
        markdown.render()
        tree = heading_tree(markdown.headings)
        self.assertEqual([node['text'] for node in tree], ['1 范围', '2 通用要求'])
        self.assertEqual([node['text'] for node in tree[0]['children']], ['1.1 对象', '1.2 限制'])
        self.assertEqual(tree[0]['children'][0]['children'][0]['text'], '1.1.1 输入')
        self.assertEqual(tree[1]['children'][0]['text'], '2.1 跳级条款')
        page = render_standards('\n'.join(markdown.lines))
        branches = [attrs for tag, attrs in Elements(page).elements
                    if tag == 'details' and attrs.get('class') == 'toc-branch']
        self.assertEqual(len(branches), 3)
        self.assertTrue(all('open' not in attrs for attrs in branches))
        self.assertIn('<ol class="toc-children">', page)

    def test_numbered_heading_hierarchy_preserves_text_and_source_anchors(self):
        source = '# 规范\n## 5 模块要求\n### 5.1 M01 数据接入与结构核验\n#### 5.1.1 输入条件\n## 附录 A 来源\n'
        markdown = Markdown(source)
        rendered = markdown.render()
        self.assertIn('<span class="section-number">5</span> <span class="section-title">模块要求</span>', rendered)
        self.assertIn('<span class="section-number">5.1</span> <span class="section-title">M01 数据接入与结构核验</span>', rendered)
        self.assertIn('<span class="section-number">附录 A</span>', rendered)
        self.assertEqual(''.join(Elements(rendered).text).splitlines(),
                         ['规范', '5 模块要求', '5.1 M01 数据接入与结构核验', '5.1.1 输入条件', '附录 A 来源'])
        self.assertIn('51-m01-数据接入与结构核验', [h['id'] for h in markdown.headings])
        page = render_standards(source)
        self.assertIn('class="toc-number">5.1</span>', page)
        self.assertIn('class="toc-level-2"', page)
        self.assertIn('class="toc-level-3"', page)

    def test_metadata_is_compact_without_removing_or_rewriting_source_text(self):
        metadata = '项目技术规范 · 征求意见稿 · 版本 0.2 · 2026年10月29日'
        page = render_standards(f'# 标题\n\n{metadata}\n\n正文中的版本表述保持普通段落。\n')
        self.assertIn(f'<p class="document-meta">{metadata}</p>', page)
        self.assertIn('<p>正文中的版本表述保持普通段落。</p>', page)
        self.assertNotIn('class="breadcrumbs"', page)
        self.assertNotIn('正文与下载使用同一份', page)
        for source in ['# 标题\n\n普通说明含版本两个字。', '# 标题\n\n项目技术规范的普通正文。']:
            elements = Elements(render_standards(source)).elements
            self.assertFalse(any(attrs.get('class') == 'document-meta' for _, attrs in elements))
        module_meta = '模块说明 · 适用实现：工作台 0.4 · 文档版本：0.2'
        module = render_standards(f'# M01\n\n{module_meta}', 'M01')
        self.assertIn(f'<p class="document-meta">{module_meta}</p>', module)

    def test_chapter_overview_is_open_but_single_module_index_is_closed_on_all_pages(self):
        source = '# 标准\n## 1 范围\n## 2 条款\n### 2.1 细则\n'
        for module in [None, 'M01', 'M09']:
            with self.subTest(module=module):
                parsed = Elements(render_standards(source, module))
                directories = [attrs for tag, attrs in parsed.elements if tag == 'details' and attrs.get('id') == 'document-toc']
                indexes = [attrs for tag, attrs in parsed.elements if tag == 'details' and attrs.get('id') == 'module-navigation']
                self.assertEqual(len(directories), 1)
                self.assertIn('open', directories[0])
                self.assertEqual(len(indexes), 1)
                self.assertNotIn('open', indexes[0])
                self.assertEqual(sum(attrs.get('class') == 'module-nav-item' for _, attrs in parsed.elements), 9)

    def test_each_module_has_distinct_status_breadcrumb_download_and_exact_clause_return(self):
        for identifier, title in MODULE_TITLES.items():
            with self.subTest(identifier=identifier):
                page = render_standards(f'# {identifier} {title}\n## 输入\n描述', identifier)
                elements = Elements(page).elements
                links = [attrs for tag, attrs in elements if tag == 'a']
                self.assertIn({'href': f'/standards/modules/{identifier}.md', 'download': f'{identifier}.md'}, links)
                self.assertTrue(any(attrs.get('href') == f'/#module-{identifier}' for attrs in links))
                clause = f'/standards#5{int(identifier[1:])}-{identifier.lower()}-{title}'
                self.assertTrue(any(attrs.get('href') == clause for attrs in links))
                selected = [attrs for attrs in links if attrs.get('aria-current') == 'page']
                self.assertEqual([attrs['href'] for attrs in selected], [f'/standards/modules/{identifier}'])
                module_links = [attrs for attrs in links if attrs.get('class') == 'module-nav-item']
                self.assertEqual(len(module_links), 9)
                self.assertIn('模块说明 · 当前实现', page)
                self.assertNotIn('项目技术规范 · 征求意见稿', page)
        self.assertIn('项目技术规范 · 征求意见稿', render_standards('# 主规范'))

    def test_module_previous_next_boundaries_and_unknown_id_rejected(self):
        for identifier, expected in [('M01', {'next': '/standards/modules/M02'}),
                                     ('M05', {'prev': '/standards/modules/M04', 'next': '/standards/modules/M06'}),
                                     ('M09', {'prev': '/standards/modules/M08'})]:
            page = Elements(render_standards('# 模块', identifier))
            actual = {attrs['rel']: attrs['href'] for tag, attrs in page.elements
                      if tag == 'a' and attrs.get('rel') in {'prev', 'next'}}
            self.assertEqual(actual, expected)
        for identifier in ['M00', 'M10', '../secret', '<script>', 'm01']:
            with self.assertRaises(ValueError):
                render_standards('# text', identifier)


class StandardsRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        (cls.root / 'docs').mkdir()
        cls.modules = cls.root / 'docs' / 'modules'
        cls.modules.mkdir()
        (cls.root / 'docs/en/modules').mkdir(parents=True)
        cls.source = cls.root / 'docs' / 'qc-standards.md'
        cls.patch = patch.object(workbench_server, 'REPO', cls.root)
        cls.patch.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), workbench_server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'
        cls.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)
        cls.patch.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.data = '# 质控标准\r\n\r\n## 适用范围\r\n\r\n**原始数据**保留。\r\n'.encode('utf-8')
        self.source.write_bytes(self.data)
        for slug, (filename, zh, en) in DOCUMENT_PAGES.items():
            for language, title in [('', zh), ('en', en)]:
                path = self.root / 'docs' / language / filename
                if path.is_symlink():
                    path.unlink()
                path.write_text(f'# {title}\n\n## 1 Scope\n[Fields](/standards/fields)', encoding='utf-8')
        (self.root / 'docs/en/qc-standards.md').write_text('# EEG QC specification\n\n## 1 Scope\nPreserve source data.', encoding='utf-8')
        for identifier in MODULE_TITLES:
            path = self.modules / f'{identifier}.md'
            if path.is_symlink():
                path.unlink()
            path.write_text(f'# {identifier} 模块\n\n## 输入\n\n### 输入字段\n保留原始数据。', encoding='utf-8')
            (self.root / 'docs/en/modules' / f'{identifier}.md').write_text(f'# {identifier} Module\n\n## 1 Scope\nPreserve source data.', encoding='utf-8')

    def test_english_pages_and_downloads_use_only_corresponding_english_sources(self):
        for suffix, filename in [('', 'qc-standards.md')] + [(f'/modules/{i}', f'modules/{i}.md') for i in MODULE_TITLES]:
            path = '/en/standards' + suffix
            status, headers, content = self.request(path)
            self.assertEqual(status, 200)
            self.assertIn('<html lang="en">', content.decode())
            self.assertIn('QC Workbench', content.decode())
            self.assertEqual(self.request(path + '.md')[2], (self.root / 'docs/en' / filename).read_bytes())
            self.assertEqual(self.request(path, method='POST')[0], 404)
        for path in ['/en/standards/modules/M10', '/en/standards/../server.py', '/en/standards/modules/../../private.txt', '/en/en/standards', '/en/api/v1/jobs']:
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request('/en/standards', headers={'Origin': 'https://other.example'})[0], 403)

    def test_common_documents_are_read_only_localized_and_download_exact_source(self):
        for slug, (filename, zh, en) in DOCUMENT_PAGES.items():
            for prefix, language, title in [('', '', zh), ('/en', 'en', en)]:
                path = prefix + '/standards/' + slug
                status, headers, page = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(title, page.decode())
                self.assertIn(f'href="{prefix}/standards/fields"', page.decode())
                self.assertIn('id="return-workbench"', page.decode())
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertEqual(self.request(path+'.md')[2], (self.root/'docs'/language/filename).read_bytes())
                self.assertEqual(self.request(path+'.md')[1]['Content-Disposition'], f'attachment; filename="{filename}"')
                self.assertEqual(self.request(path, 'POST')[0], 404)
                self.assertEqual(self.request(path, headers={'Origin': 'https://other.example'})[0], 403)

    def test_common_catalog_cannot_expose_arbitrary_paths_or_symlinks(self):
        for path in ['/standards/fields/modules/M01', '/standards/fields.md/extra',
                     '/standards/implementation/../../server.py', '/standards/metadata-fields',
                     '/standards/TODO.md', '/en/standards/unknown']:
            self.assertEqual(self.request(path)[0], 404)
            self.assertIsNone(safe_url(path))
        source = self.root/'docs/metadata-fields.md'
        source.unlink()
        self.assertEqual(self.request('/standards/fields')[0], 404)
        secret = self.root/'secret.md'
        secret.write_text('PRIVATE')
        source.symlink_to(secret)
        self.assertEqual(self.request('/standards/fields')[0], 404)
        self.assertEqual(self.request('/standards/fields.md')[0], 404)

    def test_common_source_updates_are_immediate(self):
        source = self.root/'docs/method-applicability.md'
        source.write_text('# Revised applicability')
        self.assertIn('Revised applicability', self.request('/standards/applicability')[2].decode())
        self.assertEqual(self.request('/standards/applicability.md')[2], source.read_bytes())

    def request(self, path, method='GET', headers=None):
        request = urllib.request.Request(self.url + path, method=method, headers=headers or {})
        try:
            response = self.opener.open(request, timeout=3)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, response.headers, response.read()

    def test_page_and_download_share_exact_source_and_remain_uncached(self):
        status, headers, page = self.request('/standards')
        self.assertEqual(status, 200)
        self.assertIn('text/html', headers['Content-Type'])
        self.assertIn('<h2 id="适用范围">适用范围</h2>', page.decode('utf-8'))
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        status, headers, markdown = self.request('/standards.md')
        self.assertEqual(status, 200)
        self.assertEqual(markdown, self.data)
        self.assertIn('text/markdown', headers['Content-Type'])
        self.assertEqual(headers['Content-Disposition'], 'attachment; filename="qc-standards.md"')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_source_edit_is_visible_without_build_or_server_restart(self):
        self.request('/standards')
        revised = '# 更新后的标准\n\n## 新条目\n新内容。'.encode('utf-8')
        self.source.write_bytes(revised)
        self.assertIn('更新后的标准', self.request('/standards')[2].decode('utf-8'))
        self.assertEqual(self.request('/standards.md')[2], revised)

    def test_print_script_and_navigation_are_local_assets(self):
        status, headers, script = self.request('/standards-print.js')
        self.assertEqual(status, 200)
        self.assertIn('javascript', headers['Content-Type'])
        self.assertEqual(script, PRINT_SCRIPT.encode('utf-8'))
        self.assertEqual(self.request('/standards-navigation.js')[2], NAVIGATION_SCRIPT.encode('utf-8'))
        self.assertRegex(self.request('/')[2].decode('utf-8'), r'<a\b[^>]*href="/standards/overview"[^>]*>质控标准</a>')

    def test_routes_are_read_only_and_do_not_expose_other_repository_files(self):
        for path in ['/standards', '/standards.md', '/standards/modules/M01', '/standards/modules/M09.md']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path, 'POST')[0], 404)
        for path in ['/docs/qc-standards.md', '/standards/../server.py', '/standards.md/../../.local/workbench.json',
                     '/standards/modules/M00', '/standards/modules/M10', '/standards/modules/m01',
                     '/standards/modules/M01/../../server.py', '/standards/modules/../qc-standards.md',
                     '/standards/modules/%2e%2e/server.py', '/standards/modules/M01.txt',
                     '/standards/modules/M01.md/extra']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.source.read_bytes(), self.data)

    def test_document_routes_retain_local_request_boundary(self):
        for path in ['/standards', '/standards.md', '/standards-print.js', '/standards-navigation.js',
                     '/standards/modules/M01', '/standards/modules/M01.md']:
            with self.subTest(path=path):
                self.assertEqual(self.request(path, headers={'Origin': 'https://other.example'})[0], 403)
                self.assertEqual(self.request(path, headers={'Host': 'other.example'})[0], 403)

    def test_missing_source_is_a_not_found_response(self):
        self.source.unlink()
        self.assertEqual(self.request('/standards')[0], 404)
        self.assertEqual(self.request('/standards.md')[0], 404)

    def test_all_nine_module_pages_and_downloads_are_same_source_read_only(self):
        for identifier in MODULE_TITLES:
            with self.subTest(identifier=identifier):
                path = f'/standards/modules/{identifier}'
                status, headers, page = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(f'<h1 id="{identifier.lower()}-模块">', page.decode('utf-8'))
                self.assertEqual(headers['Cache-Control'], 'no-store')
                status, headers, source = self.request(path + '.md')
                self.assertEqual(status, 200)
                self.assertEqual(source, (self.modules / f'{identifier}.md').read_bytes())
                self.assertEqual(headers['Content-Disposition'], f'attachment; filename="{identifier}.md"')
        # This isolated server intentionally has no Store; document reads never touch jobs.
        self.assertFalse(hasattr(self.server, 'store'))

    def test_module_update_and_missing_source_need_no_build(self):
        self.request('/standards/modules/M03')
        path = self.modules / 'M03.md'
        revised = '# M03 更新\n\n## 新规则\n新内容。'.encode('utf-8')
        path.write_bytes(revised)
        self.assertIn('M03 更新', self.request('/standards/modules/M03')[2].decode('utf-8'))
        self.assertEqual(self.request('/standards/modules/M03.md')[2], revised)
        path.unlink()
        self.assertEqual(self.request('/standards/modules/M03')[0], 404)
        self.assertEqual(self.request('/standards/modules/M03.md')[0], 404)

    def test_symlink_outside_document_root_is_not_served(self):
        private = self.root / 'private.txt'
        private.write_text('private secret', encoding='utf-8')
        path = self.modules / 'M01.md'
        path.unlink()
        path.symlink_to(private)
        self.assertEqual(self.request('/standards/modules/M01')[0], 404)
        self.assertEqual(self.request('/standards/modules/M01.md')[0], 404)


if __name__ == '__main__':
    unittest.main()
