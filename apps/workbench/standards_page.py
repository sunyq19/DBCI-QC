"""Read-only, dependency-free presentation of docs/qc-standards.md.

Supported Markdown: ATX headings, paragraphs, ordered/unordered lists (including
indented children), pipe tables, fenced code, inline code, emphasis and links.
Raw HTML is always text. Images, includes, directives and arbitrary file links
are intentionally unsupported. This is a document renderer, not an editor.
"""
from html import escape, unescape
import re
import unicodedata
from urllib.parse import urlsplit, unquote


HEADING = re.compile(r'^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$')
LIST_ITEM = re.compile(r'^( *)([-+*]|[0-9]{1,9}[.)])[ \t]+(.*)$')
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})([^`]*)$')
SEPARATOR = re.compile(r'^:?-{3,}:?$')
from ephys_qc.modalities import ROUTES, DESCRIPTIVE, route

# Fixed document catalog shared by routing and presentation. Never accept paths
# from request parameters or Markdown content.
DOCUMENT_PAGES = {
    'overview': ('workflow-standards.md', '总则', 'General requirements'),
    'fields': ('metadata-fields.md', '字段字典', 'Field dictionary'),
    'applicability': ('method-applicability.md', '方法适用规则', 'Method applicability'),
    'implementation': ('implementation-status.md', '实现与验证范围', 'Implementation and validation'),
}
DOCUMENT_PATHS = {'/standards', '/standards/ecog', '/standards/seeg', '/standards/neuropixels',
                  *('/standards/' + slug for slug in DOCUMENT_PAGES)}
LOCAL_DOCUMENT_PATHS = DOCUMENT_PATHS | {'/en' + path for path in DOCUMENT_PATHS}

MODULE_TITLES = {
    'M01': '数据接入与结构核验', 'M02': '数据画像与检查计划',
    'M03': '信号完整性', 'M04': '频谱与窄带干扰', 'M05': '通道质量候选',
    'M06': '生理伪迹线索', 'M07': '状态与事件核对', 'M08': '分项评价与汇总',
    'M09': '报告与复核',
}
EN_MODULE_TITLES = {
    'M01': 'Data intake and structure checks',
    'M02': 'Data characterization and check plan',
    'M03': 'Signal integrity',
    'M04': 'Spectrum and narrow-band interference',
    'M05': 'Channel quality candidates',
    'M06': 'Physiological artifact indicators',
    'M07': 'State and event checks',
    'M08': 'Evidence summary and aggregation',
    'M09': 'Reporting and review',
}


ECOG_MODULE_TITLES = {**MODULE_TITLES, 'M03': '基础信号完整性', 'M04': '频谱与工频观察', 'M05': '逐触点统计', 'M06': '伪迹方法边界', 'M07': '来源事件核对'}
EN_ECOG_MODULE_TITLES = {**EN_MODULE_TITLES, 'M03': 'Basic signal integrity', 'M04': 'Spectrum and line-frequency observations', 'M05': 'Per-contact statistics', 'M06': 'Artifact method scope', 'M07': 'Source event checks'}


def module_titles(modality, english=False):
    if modality == 'extracellular':
        return ({**EN_ECOG_MODULE_TITLES, 'M04': 'Within-stream spectrum observations', 'M05': 'Per-channel statistics'} if english else
                {**ECOG_MODULE_TITLES, 'M04': '流内频谱观察', 'M05': '逐通道统计'})
    if modality in DESCRIPTIVE:
        return EN_ECOG_MODULE_TITLES if english else ECOG_MODULE_TITLES
    return EN_MODULE_TITLES if english else MODULE_TITLES


def numbered_label(text, prefix='section', formatted=True):
    """Present existing chapter/clause numbers distinctly without inventing any."""
    match = re.match(r'^((?:[0-9]+(?:\.[0-9]+)*)|(?:(?:附录|Appendix)\s+[A-Z]))(\s+)(.+)$', text)
    render = inline if formatted else escape
    if not match:
        return render(text)
    number, separator, title = match.groups()
    return (f'<span class="{prefix}-number">{escape(number)}</span>' + escape(separator)
            + f'<span class="{prefix}-title">{render(title)}</span>')


def safe_url(value):
    """Allow web references, anchors and an exact set of local document routes."""
    value = unescape(value.strip())
    if not value or any(ord(char) <= 32 or ord(char) == 127 for char in value):
        return None
    if '\\' in value:
        return None
    try:
        parsed = urlsplit(value)
        fragment = unquote(parsed.fragment)
        valid_fragment = not fragment or re.fullmatch(r'[\w-]+', fragment)
        if value.startswith('#') and valid_fragment:
            return value
        if value.startswith('/') and not parsed.scheme and not parsed.netloc and not parsed.query and '?' not in value.split('#')[0]:
            if valid_fragment and (parsed.path in LOCAL_DOCUMENT_PATHS or
                                   re.fullmatch(r'/(?:en/)?standards/(?:(?:ecog|seeg|neuropixels)/)?modules/M0[1-9]', parsed.path)):
                return value
            if parsed.path == '/' and re.fullmatch(r'module-M0[1-9]', parsed.fragment):
                return value
        if parsed.scheme.lower() in {'https', 'http'} and parsed.netloc and parsed.hostname:
            return value
    except ValueError:
        pass
    return None


def _link_at(text, start):
    """Read one inline link, including balanced parentheses in its destination."""
    close = text.find('](', start + 1)
    if close < 0 or '\n' in text[start:close] or '[' in text[start + 1:close]:
        return None
    depth, cursor = 1, close + 2
    while cursor < len(text):
        char = text[cursor]
        if char == '\\' and cursor + 1 < len(text):
            cursor += 2
            continue
        if char == '(':
            depth += 1
        elif char == ')':
            depth -= 1
            if depth == 0:
                return text[start + 1:close], text[close + 2:cursor], cursor + 1
        cursor += 1
    return None


def inline(text, depth=0, allow_links=True):
    """Escape source before emitting only renderer-owned tags and attributes."""
    if depth >= 12:
        return escape(text)
    output, cursor = [], 0
    while cursor < len(text):
        char = text[cursor]
        if char == '\\' and cursor + 1 < len(text) and text[cursor + 1] in r'\`*_{}[]()#+-.!|>':
            output.append(escape(text[cursor + 1]))
            cursor += 2
            continue
        if char == '`':
            end = cursor
            while end < len(text) and text[end] == '`':
                end += 1
            marker = text[cursor:end]
            close = text.find(marker, end)
            if close >= 0:
                output.append('<code>' + escape(text[end:close]) + '</code>')
                cursor = close + len(marker)
                continue
        if char == '!' and text[cursor + 1:cursor + 2] == '[':
            image = _link_at(text, cursor + 1)
            if image:
                output.append(escape(text[cursor:image[2]]))
                cursor = image[2]
                continue
        if char == '[' and allow_links:
            link = _link_at(text, cursor)
            if link:
                label, destination, end = link
                url = safe_url(destination)
                if url:
                    attributes = ' rel="noopener noreferrer"' if not url.startswith('#') else ''
                    output.append(f'<a href="{escape(url, quote=True)}"{attributes}>'
                                  + inline(label, depth + 1, False) + '</a>')
                else:
                    output.append(escape(text[cursor:end]))
                cursor = end
                continue
        matched = False
        for marker, tag in (('**', 'strong'), ('__', 'strong'), ('*', 'em'), ('_', 'em')):
            if not text.startswith(marker, cursor):
                continue
            if marker.startswith('_') and cursor and text[cursor - 1].isalnum():
                continue
            close = text.find(marker, cursor + len(marker))
            content = text[cursor + len(marker):close] if close >= 0 else ''
            if content and not content[0].isspace() and not content[-1].isspace():
                output.append(f'<{tag}>' + inline(content, depth + 1, allow_links) + f'</{tag}>')
                cursor = close + len(marker)
                matched = True
                break
        if matched:
            continue
        output.append(escape(char))
        cursor += 1
    return ''.join(output)


def _cells(line):
    """Do not split an escaped pipe or a pipe enclosed in inline code."""
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    cells, current, ticks, cursor = [], [], '', 0
    while cursor < len(line):
        char = line[cursor]
        if char == '\\' and cursor + 1 < len(line):
            current.extend(line[cursor:cursor + 2])
            cursor += 2
            continue
        if char == '`':
            end = cursor
            while end < len(line) and line[end] == '`':
                end += 1
            run = line[cursor:end]
            ticks = '' if ticks == run else run if not ticks else ticks
            current.append(run)
            cursor = end
            continue
        if char == '|' and not ticks:
            cells.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
        cursor += 1
    cells.append(''.join(current).strip())
    return cells


class Markdown:
    def __init__(self, source):
        self.lines = source.expandtabs(4).splitlines()
        self.headings = []
        self.identifiers = {'document', 'print-document', 'return-workbench', 'document-toc', 'module-navigation', 'specification-navigation'}

    def heading(self, level, text):
        # HTMLParser would also consume literal source HTML. Use rendered text
        # only for the slug; the heading itself is always rendered by inline().
        plain = unescape(re.sub(r'<[^>]+>', '', inline(text)))
        base = re.sub(r'[^\w\s-]', '', unicodedata.normalize('NFKC', plain).casefold())
        base = re.sub(r'[\s_]+', '-', base).strip('-') or 'section'
        identifier, suffix = base, 2
        while identifier in self.identifiers:
            identifier, suffix = f'{base}-{suffix}', suffix + 1
        self.identifiers.add(identifier)
        self.headings.append({'level': level, 'id': identifier, 'text': plain})
        label = numbered_label(text) if level > 1 else inline(text)
        return f'<h{level} id="{escape(identifier)}">{label}</h{level}>'

    def table_at(self, index):
        if index + 1 >= len(self.lines) or '|' not in self.lines[index]:
            return None
        headers, separators = _cells(self.lines[index]), _cells(self.lines[index + 1])
        if len(headers) != len(separators) or not all(SEPARATOR.fullmatch(cell) for cell in separators):
            return None
        align = ['center' if cell.startswith(':') and cell.endswith(':') else
                 'right' if cell.endswith(':') else 'left' for cell in separators]
        output = ['<div class="table-scroll" role="region" aria-label="表格，可横向滚动" tabindex="0"><table><thead><tr>']
        output.extend(f'<th scope="col" class="align-{side}">{inline(cell)}</th>' for cell, side in zip(headers, align))
        output.append('</tr></thead><tbody>')
        cursor = index + 2
        while cursor < len(self.lines) and self.lines[cursor].strip() and '|' in self.lines[cursor]:
            cells = _cells(self.lines[cursor])
            cells += [''] * max(0, len(headers) - len(cells))
            output.append('<tr>')
            output.extend(f'<td class="align-{align[i] if i < len(align) else "left"}">{inline(cell)}</td>' for i, cell in enumerate(cells))
            output.append('</tr>')
            cursor += 1
        output.append('</tbody></table></div>')
        return ''.join(output), cursor

    def list_at(self, index):
        first = LIST_ITEM.match(self.lines[index])
        indent, ordered = len(first[1]), first[2][0].isdigit()
        tag = 'ol' if ordered else 'ul'
        start = f' start="{int(first[2][:-1])}"' if ordered and int(first[2][:-1]) != 1 else ''
        output, cursor = [f'<{tag}{start}>'], index
        while cursor < len(self.lines):
            item = LIST_ITEM.match(self.lines[cursor])
            if not item or len(item[1]) != indent or item[2][0].isdigit() != ordered:
                break
            output.append('<li>' + inline(item[3]))
            cursor += 1
            while cursor < len(self.lines):
                line = self.lines[cursor]
                child = LIST_ITEM.match(line)
                if child:
                    if len(child[1]) <= indent:
                        break
                    nested, cursor = self.list_at(cursor)
                    output.append(nested)
                elif not line.strip():
                    if cursor + 1 < len(self.lines) and LIST_ITEM.match(self.lines[cursor + 1]):
                        cursor += 1
                    else:
                        break
                elif len(line) - len(line.lstrip()) > indent:
                    output.append(' ' + inline(line.strip()))
                    cursor += 1
                else:
                    break
            output.append('</li>')
        output.append(f'</{tag}>')
        return ''.join(output), cursor

    def render(self):
        output, cursor = [], 0
        while cursor < len(self.lines):
            line = self.lines[cursor]
            if not line.strip():
                cursor += 1
                continue
            fence = FENCE.match(line)
            if fence:
                marker, language = fence.groups()
                language = language.strip()
                code, cursor = [], cursor + 1
                closing = re.compile(r'^ {0,3}' + re.escape(marker[0]) + '{' + str(len(marker)) + r',}\s*$')
                while cursor < len(self.lines) and not closing.match(self.lines[cursor]):
                    code.append(self.lines[cursor])
                    cursor += 1
                attribute = f' class="language-{language}"' if re.fullmatch(r'[A-Za-z0-9_-]+', language) else ''
                output.append(f'<pre><code{attribute}>' + escape('\n'.join(code)) + '</code></pre>')
                cursor += int(cursor < len(self.lines))
                continue
            heading = HEADING.match(line)
            if heading:
                output.append(self.heading(len(heading[1]), heading[2]))
                cursor += 1
                continue
            table = self.table_at(cursor)
            if table:
                markup, cursor = table
                output.append(markup)
                continue
            if LIST_ITEM.match(line):
                markup, cursor = self.list_at(cursor)
                output.append(markup)
                continue
            if re.fullmatch(r' {0,3}([-*_])(?:\s*\1){2,}\s*', line):
                output.append('<hr>')
                cursor += 1
                continue
            paragraph = [line.strip()]
            cursor += 1
            while cursor < len(self.lines) and self.lines[cursor].strip():
                next_line = self.lines[cursor]
                if HEADING.match(next_line) or FENCE.match(next_line) or LIST_ITEM.match(next_line) or self.table_at(cursor):
                    break
                paragraph.append(next_line.strip())
                cursor += 1
            output.append('<p>' + inline(' '.join(paragraph)) + '</p>')
        return '\n'.join(output)


def heading_tree(headings):
    """Use heading levels as actual parent/child structure, not indentation only."""
    entries = [heading for heading in headings if heading['level'] > 1] or headings
    roots, stack = [], []
    for heading in entries:
        node = {**heading, 'children': []}
        while stack and stack[-1]['level'] >= node['level']:
            stack.pop()
        (stack[-1]['children'] if stack else roots).append(node)
        stack.append(node)
    return roots


def render_toc(nodes):
    items = []
    for node in nodes:
        identifier = escape(node['id'])
        title = numbered_label(node['text'], 'toc', formatted=False)
        link = f'<a href="#{identifier}" data-toc-link="{identifier}">{title}</a>'
        if node['children']:
            items.append(f'<li class="toc-level-{node["level"]}"><details class="toc-branch" data-toc-section="{identifier}">'
                         f'<summary>{link}</summary><ol class="toc-children">'
                         + render_toc(node['children']) + '</ol></details></li>')
        else:
            items.append(f'<li class="toc-leaf toc-level-{node["level"]}">{link}</li>')
    return ''.join(items)


STYLES = """
.document-languages{display:inline-flex;gap:8px;align-items:center;white-space:nowrap}.document-languages a{padding:2px 5px}.document-languages [aria-current="true"]{background:#eaf1fc;border-radius:3px;font-weight:700}
:root{color-scheme:light;--ink:#25354a;--muted:#617084;--blue:#2156b1;--line:#dce4ee}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:6rem}
body{margin:0;background:#f7f9fc;color:var(--ink);font:15.5px/1.9 system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}
a{color:var(--blue);text-underline-offset:.2em;overflow-wrap:anywhere}
a:focus-visible,button:focus-visible,summary:focus-visible,.table-scroll:focus-visible{outline:3px solid #93b7ee;outline-offset:3px}
.skip-link{position:absolute;top:-60px;left:20px;background:white;padding:8px;z-index:3}.skip-link:focus{top:8px}
.document-header{position:sticky;top:0;z-index:2;background:#fff;border-bottom:1px solid var(--line)}
.document-toolbar{max-width:1260px;margin:auto;padding:12px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap;font-size:13px}
.document-kind{margin-right:auto;color:var(--muted);font-size:12px;letter-spacing:.04em}
.document-toolbar a{text-decoration:none}.document-toolbar button{background:transparent;color:var(--blue);border:1px solid var(--line);border-radius:5px;padding:5px 13px;font:inherit;cursor:pointer}
.document-toolbar .workbench-return{display:inline-flex;align-items:center;gap:12px;background:var(--blue);color:white;padding:7px 13px;border-radius:5px;font-weight:600}
.workbench-return kbd{font:11px ui-monospace,monospace;border:1px solid #ffffff66;border-radius:3px;padding:1px 4px}
.document-layout{max-width:1260px;margin:28px auto;padding:0 24px;display:grid;grid-template-columns:240px minmax(0,1fr);gap:30px;align-items:start}
.document-sidebar{position:sticky;top:86px;max-height:calc(100vh - 110px);overflow:auto;padding-right:10px;scrollbar-width:thin;font-size:13px}
.document-sidebar>details{margin-bottom:16px}.document-sidebar>details>summary{font-weight:650;padding:7px 0;color:#314b6f;cursor:pointer;font-size:13px}
.document-sidebar ol{list-style:none;padding:4px 0;margin:0}.document-sidebar li{margin:1px 0;line-height:1.55}
.document-sidebar a{display:block;padding:7px 7px;border-radius:4px;text-decoration:none;color:var(--muted)}
.document-sidebar a:hover{background:#edf3fc;color:var(--blue)}.document-sidebar a[aria-current]{background:#e7effb;color:#19478f;font-weight:650}
.toc-tree>.toc-level-2>details>summary>a,.toc-tree>.toc-level-2>a{color:#304762;font-weight:600}
.toc-branch>summary{display:flex;align-items:baseline;cursor:pointer;list-style:none}.toc-branch>summary::-webkit-details-marker{display:none}
.toc-branch>summary::before{content:'›';color:#8391a5;width:13px;flex:none;text-align:center}.toc-branch[open]>summary::before{transform:rotate(90deg)}
.toc-branch>summary>a{flex:1;min-width:0}.toc-leaf{padding-left:13px}
.document-sidebar .toc-children{margin:1px 0 5px 13px;padding-left:7px;border-left:1px solid #dfe6ef;font-size:12px}
.toc-number{display:inline-block;min-width:1.7em;margin-right:.25em;font-variant-numeric:tabular-nums;color:#7b8ba0;font-weight:500}
.toc-children .toc-number{min-width:2em}.toc-children .toc-children{font-size:12px}
.module-navigation{border-top:1px solid var(--line);padding-top:8px}.module-nav-item code{padding:0;background:none;color:#7b8ba0;margin-right:7px;font-size:12px}
.document-body{min-width:0;background:white;border:1px solid var(--line);border-radius:5px;padding:32px 44px 44px}
.document-body h1{font-size:26px;line-height:1.5;margin:0 0 10px;color:#183b68;letter-spacing:.01em}
.document-body .document-meta{font-size:12px;line-height:1.7;color:var(--muted);margin:0 0 22px;padding-bottom:18px;border-bottom:1px solid #e5eaf2}
.document-body h2{display:flex;align-items:baseline;gap:.45em;font-size:21px;line-height:1.6;margin:44px 0 20px;padding:0 0 9px;border-bottom:1px solid #cfdae9;color:#193f71}
.document-body h2 .section-number{min-width:1.35em;color:var(--blue);font-size:23px;font-weight:600;font-variant-numeric:tabular-nums}
.document-body h3{display:flex;align-items:baseline;gap:.5em;font-size:17px;line-height:1.7;margin:29px 0 12px;color:#263f5c}
.document-body h3 .section-number{min-width:2.1em;color:#42658f;font-size:15px;font-variant-numeric:tabular-nums}
.document-body h4,.document-body h5,.document-body h6{font-size:15px;margin:23px 0 9px;line-height:1.7}
.document-body :is(h4,h5,h6) .section-number{margin-right:.5em;color:#61738b;font-variant-numeric:tabular-nums}
.document-body :is(h2,h3,h4,h5,h6):target{background:#f0f5fd;border-radius:3px}
.document-body p{margin:12px 0;overflow-wrap:anywhere}.document-body ul,.document-body ol{padding-left:25px}.document-body li{margin:6px 0}
.document-body hr{border:0;border-top:1px solid var(--line);margin:28px 0}
.breadcrumbs{display:flex;gap:9px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin-bottom:16px}.breadcrumbs a{text-decoration:none}
.module-actions{display:flex;gap:18px;flex-wrap:wrap;padding:0 0 14px;margin:0 0 20px;border-bottom:1px solid #e5eaf2}.module-actions a{font-size:12px;text-decoration:none}
.module-pagination{display:flex;justify-content:space-between;gap:22px;margin-top:38px;padding-top:20px;border-top:1px solid var(--line);font-size:13px}
.module-pagination>a{max-width:48%;text-decoration:none}.module-pagination>a:last-child{text-align:right}.module-pagination small{display:block;color:var(--muted);font-size:11px}
code{font:0.88em/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;background:#f0f4fa;border-radius:3px;padding:2px 4px;overflow-wrap:anywhere}
pre{padding:16px;background:#f4f7fb;border:1px solid var(--line);border-radius:5px;overflow:auto}pre code{padding:0;background:none;white-space:pre;overflow-wrap:normal}
.table-scroll{overflow-x:auto;margin:20px 0;border:1px solid var(--line);border-radius:4px}table{border-collapse:collapse;width:100%;min-width:560px;font-size:13px;line-height:1.8}
th,td{padding:10px 12px;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:#f0f4fa;color:#2c496d;font-weight:650}tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#fafbfd}
.align-left{text-align:left}.align-center{text-align:center}.align-right{text-align:right}
.document-footer{max-width:1260px;margin:18px auto 30px;padding:0 24px;text-align:right;font-size:12px}.document-footer a{color:var(--muted);text-decoration:none}
@media(max-width:950px){.document-toolbar{padding:10px 16px;gap:12px}.document-kind{font-size:11px}.document-layout{grid-template-columns:205px minmax(0,1fr);padding:0 16px;gap:20px}.document-body{padding:27px 25px}.document-body h1{font-size:24px}.document-sidebar{padding-right:2px}}
@media(max-width:700px){.document-kind{display:none}.document-toolbar{gap:14px}.document-toolbar .workbench-return{margin-right:auto}.document-layout{display:block;margin:18px auto;padding:0 12px}.document-sidebar{position:static;max-height:none;margin:0 2px 18px;padding:0}.document-sidebar>details{padding:0 10px;border:1px solid var(--line);border-radius:5px;margin-bottom:8px;background:white}.document-sidebar .toc-tree{columns:2;column-gap:12px}.toc-tree>li{break-inside:avoid}.document-body{padding:24px 20px}.document-body h1{font-size:22px}.document-body h2{font-size:19px;margin-top:35px}.document-body h2 .section-number{font-size:21px}.document-footer{padding:0 16px}}
@media(max-width:430px){.document-sidebar .toc-tree{columns:1}.document-body{padding:21px 16px}.document-toolbar{gap:10px}.document-toolbar .workbench-return{gap:8px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
@media print{@page{margin:17mm}body{background:white;font-size:10.5pt;line-height:1.65;color:#111}.document-header,.document-sidebar,.skip-link,.document-footer,.module-actions,.module-pagination,.breadcrumbs{display:none}.document-layout{display:block;max-width:none;margin:0;padding:0}.document-body{padding:0;border:0;border-radius:0}.document-body h1{font-size:20pt}.document-body h2{font-size:15pt;break-after:avoid;margin-top:24pt}.document-body h2 .section-number{font-size:16pt}.document-body h3{font-size:12pt;break-after:avoid}.document-body h3 .section-number{font-size:11pt}.document-body .document-meta{font-size:9pt}.table-scroll{overflow:visible;border-radius:0}table{min-width:0;font-size:9pt;table-layout:fixed}th,td{padding:6pt;overflow-wrap:anywhere}tr,pre{break-inside:avoid}pre,pre code{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#111}a[href^="http"]::after{content:" (" attr(href) ")";font-size:.85em}}
"""

NAVIGATION_SCRIPT = r""""use strict";
(() => {
  const back = document.getElementById("return-workbench");
  const entryHref = location.href, entryLength = history.length;
  let fromWorkbench = false;
  try {
    const from = new URL(document.referrer);
    fromWorkbench = from.origin === location.origin && from.pathname === "/" && history.length > 1;
  } catch { /* Direct visits use the reliable root URL. */ }
  function returnToWorkbench() {
    if (fromWorkbench && location.href === entryHref && history.length === entryLength) history.back();
    else {
      const fallback = back.getAttribute?.("href");
      location.assign(["/", "/?lang=en", "/?modality=ecog", "/?modality=ecog&lang=en", "/?modality=seeg", "/?modality=seeg&lang=en", "/?modality=extracellular", "/?modality=extracellular&lang=en"].includes(fallback) ? fallback : "/");
    }
  }
  back.addEventListener("click", event => {
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); returnToWorkbench();
  });
  document.getElementById("print-document").addEventListener("click", () => window.print());

  let composing = false;
  function isEditable(target) {
    const node = target?.nodeType === 3 ? target.parentElement : target;
    return Boolean(node?.isContentEditable || node?.closest?.('input, textarea, select, [role="textbox"], [contenteditable]:not([contenteditable="false"])'));
  }
  document.addEventListener("compositionstart", () => { composing = true; });
  document.addEventListener("compositionend", () => { composing = false; });
  document.addEventListener("keydown", event => {
    if (!event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat ||
        composing || event.isComposing || event.keyCode === 229 || String(event.key).toLowerCase() !== "q" ||
        isEditable(event.target) || isEditable(document.activeElement) || event.composedPath?.().some(isEditable)) return;
    event.preventDefault(); returnToWorkbench();
  });

  const links = Array.from(document.querySelectorAll("[data-toc-link]"));
  const headings = Array.from(document.querySelectorAll(".document-body h2[id], .document-body h3[id], .document-body h4[id], .document-body h5[id], .document-body h6[id]"));
  const automaticallyOpened = new Set();
  let current = null, scheduled = false;
  function markCurrent(id) {
    if (!id || id === current) return;
    current = id;
    const ancestors = new Set();
    for (const link of links) {
      if (link.dataset.tocLink === id) {
        link.setAttribute("aria-current", "location");
        let branch = link.closest("details");
        while (branch) {
          // Keep the chapter overview compact; a heading's own children stay
          // closed until needed or explicitly expanded by the reader.
          if (branch.dataset?.tocSection !== id) ancestors.add(branch);
          branch = branch.parentElement?.closest("details");
        }
      } else link.removeAttribute("aria-current");
    }
    for (const branch of automaticallyOpened) {
      if (!ancestors.has(branch)) { branch.open = false; automaticallyOpened.delete(branch); }
    }
    for (const branch of ancestors) {
      if (!branch.open) { branch.open = true; automaticallyOpened.add(branch); }
    }
  }
  function fromHash() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (headings.some(heading => heading.id === id)) markCurrent(id);
  }
  function syncCurrent() {
    scheduled = false;
    if (!headings.length) return;
    const boundary = (document.querySelector(".document-header")?.getBoundingClientRect().bottom || 90) + 24;
    let active = headings[0];
    for (const heading of headings) {
      if (heading.getBoundingClientRect().top > boundary) break;
      active = heading;
    }
    if (window.scrollY > 0 && window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 2) active = headings[headings.length - 1];
    markCurrent(active.id);
  }
  function scheduleCurrent() {
    if (!scheduled) { scheduled = true; requestAnimationFrame(syncCurrent); }
  }
  links.forEach(link => link.addEventListener("click", () => markCurrent(link.dataset.tocLink)));
  window.addEventListener("scroll", scheduleCurrent, {passive:true});
  window.addEventListener("resize", scheduleCurrent);
  window.addEventListener("hashchange", () => { fromHash(); scheduleCurrent(); });
  fromHash(); scheduleCurrent();
})();
"""
# Keep the earlier script URL compatible with already open document pages.
PRINT_SCRIPT = NAVIGATION_SCRIPT


def _module_clause_id(identifier, lang='zh-CN', modality='scalp_eeg'):
    titles = module_titles(modality, lang == 'en')
    markdown = Markdown('')
    markdown.heading(3, f'5.{int(identifier[1:])} {identifier} {titles[identifier]}')
    return markdown.headings[0]['id']


def _localized_document_links(body, lang, modality='scalp_eeg'):
    """Rewrite only renderer-approved internal documentation links, never prose/code."""
    if lang != 'en':
        return body
    clause_ids = {_module_clause_id(identifier, modality=modality): _module_clause_id(identifier, 'en', modality)
                  for identifier in MODULE_TITLES}

    def localize(match):
        value = unescape(match.group(1))
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query:
            return match.group(0)
        if parsed.path not in DOCUMENT_PATHS and not re.fullmatch(r'/standards/(?:(?:ecog|seeg|neuropixels)/)?modules/M0[1-9]', parsed.path):
            return match.group(0)
        fragment = unquote(parsed.fragment)
        suffix = '#' + clause_ids.get(fragment, fragment) if fragment else ''
        return 'href="' + escape('/en' + parsed.path + suffix, quote=True) + '"'

    return re.sub(r'href="([^"]+)"', localize, body)


def render_standards(source, module_id=None, lang='zh-CN', modality='scalp_eeg'):
    if module_id is not None and module_id not in MODULE_TITLES:
        raise ValueError('Unknown module document')
    if lang not in {'en', 'zh', 'zh-CN'}:
        raise ValueError('Unsupported document language')
    common = modality in DOCUMENT_PAGES
    if modality not in {*ROUTES, *DOCUMENT_PAGES} or (common and module_id is not None):
        raise ValueError('Unsupported document modality')
    english = lang == 'en'
    lang = 'en' if english else 'zh-CN'
    titles = module_titles(modality, english)
    modality_suffix = '/' + modality if common else ('/' + route(modality)['slug'] if route(modality)['slug'] else '')
    base = ('/en/standards' if english else '/standards') + modality_suffix
    workbench_href = ('/?modality=' + modality + ('&lang=en' if english else '')) if modality in DESCRIPTIVE else ('/?lang=en' if english else '/')
    text = lambda chinese, english_text: english_text if english else chinese
    markdown = Markdown(source)
    body = _localized_document_links(markdown.render(), lang, modality)
    if english:
        body = body.replace('aria-label="表格，可横向滚动"', 'aria-label="Table; scroll horizontally"')
    # Style an explicitly labelled source metadata line; keep its exact content.
    body = re.sub(r'(<h1\b[^>]*>.*?</h1>\n)<p>((?:项目技术规范|模块说明|Project technical specification|Module documentation|Module guide|Module description)[^\n]*(?:版本|[Vv]ersion)[^\n]*)</p>',
                  r'\1<p class="document-meta">\2</p>', body, count=1)
    title = next((heading['text'] for heading in markdown.headings if heading['level'] == 1), text('质控技术规范', 'QC technical specification'))
    toc = render_toc(heading_tree(markdown.headings))
    module_links = ''.join(
        f'<li><a class="module-nav-item" href="{base}/modules/{identifier}"'
        + (' aria-current="page"' if identifier == module_id else '')
        + f'><code>{identifier}</code>{escape(name)}</a></li>' for identifier, name in titles.items())
    if common:
        prefix = '/en' if english else ''
        module_links = (f'<li><a href="{prefix}/standards">{text("头皮EEG适用规则", "Scalp EEG requirements")}</a></li>'
                        f'<li><a href="{prefix}/standards/ecog">{text("ECoG适用规则", "ECoG requirements")}</a></li>'
                        f'<li><a href="{prefix}/standards/seeg">{text("sEEG适用规则", "sEEG requirements")}</a></li>'
                        f'<li><a href="{prefix}/standards/neuropixels">{text("Neuropixels连续电压规则", "Neuropixels continuous-voltage requirements")}</a></li>')
    download_path = f'{base}/modules/{module_id}.md' if module_id else base + '.md'
    download_name = f'{module_id}.md' if module_id else (DOCUMENT_PAGES[modality][0] if common else 'qc-standards.md')
    prefix = '/en' if english else ''
    document_links = ''.join(
        f'<li><a href="{prefix}/standards/{slug}"'
        + (' aria-current="page"' if slug == modality else '')
        + f'>{escape(labels[2] if english else labels[1])}</a></li>'
        for slug, labels in DOCUMENT_PAGES.items())
    kind = (text('实现与验证 · 资料性文件', 'Implementation and validation · Informative') if modality == 'implementation' else
            text('模块说明 · 当前实现', 'Module guide · Current implementation') if module_id else
            text('项目技术规范 · 征求意见稿', 'Project technical specification · Consultation draft'))
    breadcrumb = (f'<nav class="breadcrumbs" aria-label="{text("面包屑", "Breadcrumbs")}"><a href="{base}">{text("质控技术规范", "QC technical specification")}</a>'
                  f'<span aria-hidden="true">/</span><span aria-current="page">{module_id}</span></nav>'
                  if module_id else '')
    module_action, pagination = '', ''
    if module_id:
        clause = base + '#' + _module_clause_id(module_id, lang, modality)
        module_action = f'<div class="module-actions"><a href="{workbench_href}#module-{module_id}">{text("在质控台查看本模块", "View this module in QC Workbench")}</a><a href="{escape(clause)}">{text("对应标准条款", "Related specification clause")}</a></div>'
        identifiers = list(MODULE_TITLES)
        index = identifiers.index(module_id)
        previous = identifiers[index - 1] if index else None
        following = identifiers[index + 1] if index + 1 < len(identifiers) else None
        previous_html = (f'<a href="{base}/modules/{previous}" rel="prev"><small>← {text("上一模块", "Previous module")}</small>{previous} {escape(titles[previous])}</a>' if previous else '<span></span>')
        next_html = (f'<a href="{base}/modules/{following}" rel="next"><small>{text("下一模块", "Next module")} →</small>{following} {escape(titles[following])}</a>' if following else '<span></span>')
        pagination = f'<nav class="module-pagination" aria-label="{text("相邻模块", "Adjacent modules")}">{previous_html}{next_html}</nav>'
    suffix = f'/modules/{module_id}' if module_id else ''
    language_links = (f'<span class="document-languages" aria-label="{text("文档语言", "Document language")}">'
                      f'<a href="/standards{modality_suffix}{suffix}" hreflang="zh-CN" lang="zh-CN"' + (' aria-current="true"' if not english else '') + '>中文</a>'
                      f'<a href="/en/standards{modality_suffix}{suffix}" hreflang="en" lang="en"' + (' aria-current="true"' if english else '') + '>EN</a></span>')
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{escape(title)} · {text("质控台", "QC Workbench")}</title>
<style>{STYLES}</style><script src="/standards-navigation.js" defer></script></head><body>
<a class="skip-link" href="#document">{text("跳到正文", "Skip to document")}</a>
<header class="document-header"><nav class="document-toolbar" aria-label="{text("文档操作", "Document actions")}">
<a id="return-workbench" class="workbench-return" href="{workbench_href}" aria-keyshortcuts="Alt+Q" title="{text("返回质控台（Alt+Q）", "Return to QC Workbench (Alt+Q)")}">← {text("返回质控台", "QC Workbench")} <kbd>Alt+Q</kbd></a>
<span class="document-kind">{kind}</span>
{language_links}<a href="{download_path}" download="{download_name}">{text("下载原文", "Download source")}</a><button id="print-document" type="button">{text("打印", "Print")}</button></nav></header>
<main class="document-layout"><aside class="document-sidebar" aria-label="{text("规范导航", "Specification navigation")}">
<details id="specification-navigation" class="module-navigation" open><summary>{text("文档体系", "Document structure")}</summary><nav aria-label="{text("公共规范", "Shared specifications")}"><ol>{document_links}</ol></nav></details>
<details id="document-toc" class="document-toc" open><summary>{text("目录", "Contents")}</summary><nav aria-label="{text("条款目录", "Clause contents")}"><ol class="toc-tree">{toc}</ol></nav></details>
<details id="module-navigation" class="module-navigation"><summary>{text("各模态规范", "Modality requirements") if common else text("模块索引", "Module index")}</summary><nav aria-label="{text("模块详情", "Module details")}"><ol>{module_links}</ol></nav></details></aside>
<article id="document" class="document-body">{breadcrumb}{module_action}{body}{pagination}</article></main>
<footer class="document-footer"><a href="#document">{text("返回顶部", "Back to top")} ↑</a></footer>
</body></html>'''
