"""Static CSS cascade checks using standards-aware parsers and selector matching.

This does not measure boxes, text wrapping, browser layout, or visual appearance.
It handles the properties and screen-width queries used by workbench contracts.
"""
from functools import lru_cache
from pathlib import Path
import re

import cssselect2
import html5lib
import tinycss2


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'apps/workbench/web'
INHERITED = {'font-size', 'font-weight', 'font-family', 'line-height', 'color'}
INITIAL = {'display': 'inline', 'padding-top': '0', 'padding-right': '0',
           'padding-bottom': '0', 'padding-left': '0', 'font-size': '16px',
           'font-weight': '400', 'line-height': 'normal', 'content': 'normal',
           'grid-template-columns': 'none'}


def serialize(tokens):
    return tinycss2.serialize(tokens).strip()


def components(tokens):
    """Top-level shorthand terms; function arguments remain a single token."""
    return [tinycss2.serialize([t]).strip() for t in tokens
            if t.type not in {'whitespace', 'comment'}]


def declarations(tokens):
    for item in tinycss2.parse_declaration_list(tokens, skip_whitespace=True, skip_comments=True):
        if item.type != 'declaration':
            continue
        name = item.lower_name
        value = serialize(item.value)
        yield name, value, item.important
        parts = components(item.value)
        if name in {'padding', 'margin'} and 1 <= len(parts) <= 4:
            top = parts[0]
            right = parts[1] if len(parts) > 1 else top
            bottom = parts[2] if len(parts) > 2 else top
            left = parts[3] if len(parts) > 3 else right
            for side, term in zip(['top', 'right', 'bottom', 'left'], [top, right, bottom, left]):
                yield name+'-'+side, term, item.important
        elif name in {'padding-inline', 'margin-inline', 'padding-block', 'margin-block'} and 1 <= len(parts) <= 2:
            # Both workbench locales use horizontal left-to-right writing.
            base, axis = name.split('-')
            sides = ['left', 'right'] if axis == 'inline' else ['top', 'bottom']
            for side, term in zip(sides, [parts[0], parts[-1]]):
                yield base+'-'+side, term, item.important
        elif name == 'font':
            # Recognize font sizes without breaking var() or quoted font families.
            significant = [t for t in item.value if t.type not in {'whitespace', 'comment'}]
            size_index = next((i for i, token in enumerate(significant)
                               if token.type in {'dimension', 'percentage'}
                               or token.type == 'function' and token.lower_name == 'var'), None)
            if size_index is not None:
                for prop, term in [('font-weight', '400'), ('line-height', 'normal')]:
                    yield prop, term, item.important
                for token in significant[:size_index]:
                    if token.type == 'number' or token.type == 'ident' and token.value in {'bold', 'normal', 'bolder', 'lighter'}:
                        yield 'font-weight', serialize([token]), item.important
                yield 'font-size', serialize([significant[size_index]]), item.important
                next_index = size_index+1
                if next_index < len(significant) and significant[next_index].type == 'literal' and significant[next_index].value == '/':
                    yield 'line-height', serialize([significant[next_index+1]]), item.important
                    next_index += 2
                if next_index < len(significant):
                    yield 'font-family', serialize(significant[next_index:]), item.important


def media_matches(text, width):
    """Evaluate the workbench's screen / width queries, not print or preferences."""
    for branch in text.split(','):
        branch = branch.strip()
        if re.search(r'print|prefers-|forced-colors', branch):
            continue
        if any((kind == 'min' and width < float(n)) or (kind == 'max' and width > float(n))
               for kind, n in re.findall(r'\((min|max)-width\s*:\s*([\d.]+)px\)', branch)):
            continue
        if re.search(r'\((?!min-width|max-width)[\w-]+\s*:', branch):
            raise AssertionError('Unimplemented media condition: '+branch)
        return True
    return False


class Cascade:
    def __init__(self, html, files, width=1440, focus_visible=()):
        tree = html5lib.parse(html, treebuilder='etree', namespaceHTMLElements=False)
        self.root = cssselect2.ElementWrapper.from_html_root(tree)
        self.nodes = list(self.root.iter_subtree())
        self.ids = {n.id: n for n in self.nodes if n.id}
        # cssselect2 is static: represent this state by an attribute with equal
        # specificity. This validates focus CSS, not actual keyboard behavior.
        for identifier in focus_visible:
            self.ids[identifier].etree_element.set('data-test-focus-visible', '')
        self.matcher = cssselect2.Matcher()
        self.width = width
        self.ignored_pseudo_selectors = []
        self.order = 0
        for filename in files:
            self._collect(tinycss2.parse_stylesheet(Path(filename).read_text(),
                          skip_whitespace=True, skip_comments=True), Path(filename).name)

    def _collect(self, rules, filename):
        for rule in rules:
            if rule.type == 'at-rule':
                if rule.lower_at_keyword == 'media' and media_matches(serialize(rule.prelude), self.width):
                    self._collect(tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True), filename)
                elif rule.lower_at_keyword == 'supports':
                    # Workbench uses modern native details/:has(); matcher supports them.
                    self._collect(tinycss2.parse_rule_list(rule.content, skip_whitespace=True, skip_comments=True), filename)
                continue
            if rule.type != 'qualified-rule':
                continue
            selector = serialize(rule.prelude)
            self.order += 1
            values = list(declarations(rule.content))
            try:
                compiled = cssselect2.compile_selector_list(selector.replace(':focus-visible', '[data-test-focus-visible]'))
            except cssselect2.SelectorError:
                if re.search(r'::(?:-webkit-[\w-]+|backdrop|file-selector-button)', selector):
                    self.ignored_pseudo_selectors.append(selector)
                    continue
                raise
            for entry in compiled:
                self.matcher.add_selector(entry, (values, self.order, f'{filename}:{rule.source_line}: {selector}'))

    @lru_cache(maxsize=None)
    def winning(self, node, pseudo=None):
        winners = {}
        for specificity, _, matched_pseudo, (values, order, source) in self.matcher.match(node):
            if matched_pseudo != pseudo:
                continue
            for index, (name, value, important) in enumerate(values):
                priority = (important, specificity, order, index)
                if name not in winners or priority >= winners[name][0]:
                    winners[name] = (priority, value, source)
        return winners

    def _raw(self, node, prop, pseudo=None):
        entry = self.winning(node, pseudo).get(prop)
        if entry and entry[1] not in {'inherit', 'unset'}:
            return entry[1]
        if prop.startswith('--') or prop in INHERITED or entry and entry[1] == 'inherit':
            if pseudo is not None:
                return self._raw(node, prop)
            if node.parent is not None:
                return self._raw(node.parent, prop)
        return INITIAL.get(prop, '')

    def value(self, node, prop, pseudo=None):
        value = self._raw(node, prop, pseudo)
        for _ in range(20):
            changed = re.sub(r'var\((--[\w-]+)(?:,\s*([^()]*))?\)',
                             lambda m: self._raw(node, m[1], pseudo) or m[2] or '', value)
            if changed == value:
                return value
            value = changed
        raise AssertionError('Cyclic custom property while computing '+prop)

    def source(self, node, prop, pseudo=None):
        return self.winning(node, pseudo).get(prop, (None, None, 'inherited / initial'))[2]

    def child(self, node, tag):
        return next(c for c in node.iter_children() if c.local_name == tag)
