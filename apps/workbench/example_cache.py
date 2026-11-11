"""Published, source-independent examples. Requests never generate reports."""
from functools import lru_cache
from html import escape
from pathlib import Path
import json
import re

DEFAULT_ROOT = Path(__file__).with_name('example-cache')


def root(store):
    return Path(store.settings.get('example_cache_dir') or DEFAULT_ROOT).resolve()


@lru_cache(maxsize=4)
def _read(path, stamp):
    manifest=json.loads(Path(path).read_text(encoding='utf-8'))
    if manifest.get('schema_version')!='example-cache/1':raise ValueError('Invalid example cache')
    return manifest


def manifest(store):
    path=root(store)/'manifest.json'
    try:
        data = _read(str(path),path.stat().st_mtime_ns)
        from temporary_uploads import enabled, source
        if enabled(store.settings) and not all(source(row.get('source')) for row in data['examples']):
            raise ValueError('Published examples need verified source metadata')
        return data
    except (OSError,ValueError,TypeError):return {'schema_version':'example-cache/1','examples':[]}


def homepage(store, template):
    data=manifest(store);rows=data['examples']
    esc=lambda value:escape(str(value),quote=True)
    cards=[]
    for r in rows:
        from temporary_uploads import source
        origin = source(r.get('source'))
        sources = origin.get('sources', [origin]) if origin else []
        for s in sources:
            s['version'] = '' if re.fullmatch('[a-fA-F0-9]{32,64}', s['version']) else re.sub(r'^doi:.*\.v(?=[0-9])', '', s['version'])
        links = ' · '.join(f'<a href="{esc(s["url"])}" target="_blank" rel="noopener noreferrer">{esc(s["name"])}{(" · " + esc(s["version"])) if s["version"] else ""}</a> <span>{esc(s["license"])}</span>' for s in sources)
        cards.append(f'<div class="public-example"><a class="demo-report" href="{esc(r["url"])}"><span class="demo-report-copy"><strong>{esc(r["label"])}<small class="example-format">{esc(r["formats"])}</small></strong><span>{esc(r["description"])}</span><small>{r["subjects"]} 个体 · {r["records"]} 份记录 · 报告 {r["reported"]}/{r["records"]}</small></span><span class="demo-report-end">查看报告</span></a><div class="public-source">来源：{links}</div></div>')
    template=template.replace('<p class="small muted">正在读取示例目录…</p>', ''.join(cards) or '<p class="small muted">尚未发布示例报告。</p>')
    template=template.replace('<span id="demo-reports-count" class="tag subtle">—</span>',f'<span id="demo-reports-count" class="tag subtle">{len(rows)}</span>')
    # Completed personal runs belong to the data library, not a second example
    # entry. Existing published comparison URLs remain archived and readable.
    visible_data={k:v for k,v in data.items() if k!='comparisons'}
    encoded=json.dumps(visible_data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return template.replace('</head>',f'<script id="example-cache" type="application/json">{encoded}</script></head>',1)


def asset(store, url):
    relative=url.removeprefix('/examples/')
    if not re.fullmatch(r'[a-f0-9]{16}/[A-Za-z0-9_.\-/]+',relative):raise KeyError(url)
    if '..' in Path(relative).parts:raise KeyError(url)
    from temporary_uploads import enabled
    if enabled(store.settings):
        data = manifest(store)
        release, name = relative.split('/', 1)
        if release != data.get('release') or name not in data.get('files', {}): raise KeyError(url)
    base=root(store);target=(base/relative).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.is_symlink():raise KeyError(url)
    return target
