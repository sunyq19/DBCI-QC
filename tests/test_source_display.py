from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'apps/workbench'))
from source_display import markup, short_name


def test_short_links_keep_full_provenance_in_details():
    row = {'name':'A long public dataset title','url':'https://openneuro.org/datasets/ds004100/versions/1.1.3','version':'1.1.3','license':'CC0'}
    assert short_name(row) == 'OpenNeuro · ds004100'
    html = markup(row)
    assert 'OpenNeuro · ds004100<span' in html
    assert '<details class="public-source-details">' in html
    assert '1.1.3 · CC0' in html and row['url'] in html and row['name'] in html
    assert ' open' not in html


def test_invalid_links_rejected_and_untrusted_names_escaped():
    assert markup({'name':'bad','url':'javascript:alert(1)','license':'CC0'}) == ''
    text = markup({'name':'<script>','url':'https://example.org','license':'<b>'})
    assert '<script>' not in text and '&lt;script&gt;' in text and '<b>' not in text
