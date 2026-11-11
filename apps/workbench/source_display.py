"""Compact public provenance; complete citation stays one disclosure away."""
from html import escape
import re
from urllib.parse import urlsplit
from temporary_uploads import source


def short_name(row):
    url = urlsplit(row['url'])
    if url.hostname == 'openneuro.org':
        match = re.search(r'/datasets/(ds\d+)', url.path)
        if match: return 'OpenNeuro · ' + match[1]
    if url.hostname in {'physionet.org', 'www.physionet.org'}:
        match = re.search(r'/content/([^/]+)', url.path)
        if match: return 'PhysioNet · ' + match[1]
    if url.hostname == 'zenodo.org':
        match = re.search(r'/records?/(\d+)', url.path)
        if match: return 'Zenodo · ' + match[1]
    if 'mne-testing-data' in url.path: return 'MNE testing data'
    return row['name']


def markup(value):
    value = source(value)
    if not value: return ''
    rows = value.get('sources', [value])
    links, info = [], []
    for row in rows:
        links.append(f'<a class="public-source-link" href="{escape(row["url"], quote=True)}" target="_blank" rel="noopener noreferrer" title="{escape(row["name"], quote=True)}" data-i18n-skip>{escape(short_name(row))}<span aria-hidden="true">↗</span></a>')
        version = row['version']
        version = '' if re.fullmatch('[a-fA-F0-9]{32,64}', version) else re.sub(r'^doi:.*\.v(?=[0-9])', '', version)
        info.append(f'<div><strong data-i18n-skip>{escape(row["name"])}</strong><span data-i18n-skip>{escape(" · ".join(x for x in [version, row["license"]] if x))}</span></div>')
    return '<div class="public-source"><span class="public-source-label">来源</span>' + ''.join(links) + '<details class="public-source-details"><summary aria-label="来源详情" title="来源详情">ⓘ</summary><div class="public-source-panel">' + ''.join(info) + '</div></details></div>'
