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
        from public_catalog import deleted_examples
        deleted = deleted_examples(store)
        if not deleted: return data
        blocked, jobs = _withdrawn(str(path), path.stat().st_mtime_ns, tuple(sorted(deleted)))
        return {**data,
                'examples': [r for r in data['examples'] if r['id'] not in deleted],
                'comparisons': [r for r in data.get('comparisons', []) if r['url'].split('/'+data['release']+'/', 1)[-1] not in blocked],
                'files': {k: v for k, v in data.get('files', {}).items() if k not in blocked},
                **{key: {k: v for k, v in data.get(key, {}).items() if k not in jobs}
                   for key in ('report_scores', 'review_snapshots')}}
    except (OSError,ValueError,TypeError):return {'schema_version':'example-cache/1','examples':[]}


@lru_cache(maxsize=16)
def _withdrawn(path, stamp, deleted):
    """Remove associated reports and downloads too, including links from old bookmarks."""
    data = _read(path, stamp)
    base = Path(path).parent / data['release']
    prefix = '/examples/' + data['release'] + '/'
    job_pattern = re.compile(r'/(?:records|review|visualizations|artifacts)/([a-f0-9]{32})')
    owners = {}
    pages = {}
    for row in data['examples']:
        names = {row[k].removeprefix(prefix) for k in ('url', 'url_en') if row.get(k)}
        pages[row['id']] = names
        owners[row['id']] = set().union(*(set(job_pattern.findall((base / name).read_text(encoding='utf-8'))) for name in names))
    removed = set().union(*(owners.get(i, set()) for i in deleted))
    retained = set().union(*(v for k, v in owners.items() if k not in deleted))
    jobs = removed - retained
    blocked = set().union(*(pages.get(i, set()) for i in deleted))
    blocked.update(name for name in data.get('files', {}) if any(job in name for job in jobs))
    # Comparison pages can expose additional routes for the withdrawn data.
    for name in data.get('files', {}):
        if name.startswith('comparisons/') and name.endswith('.html'):
            ids = set(job_pattern.findall((base / name).read_text(encoding='utf-8')))
            if ids & jobs:
                blocked.add(name)
                jobs.update(ids - retained)
    blocked.update(name for name in data.get('files', {}) if any(job in name for job in jobs))
    return frozenset(blocked), frozenset(jobs)


def homepage(store, template):
    data=manifest(store);rows=data['examples']
    esc=lambda value:escape(str(value),quote=True)
    cards=[]
    for r in rows:
        from source_display import markup
        cards.append(f'<div class="public-example"><a class="demo-report" href="{esc(r["url"])}"><span class="demo-report-copy"><strong>{esc(r["label"])}<small class="example-format">{esc(r["formats"])}</small></strong><span>{esc(r["description"])}</span><small>{r["subjects"]} 个体 · {r["records"]} 份记录 · 报告 {r["reported"]}/{r["records"]}</small></span><span class="demo-report-end">查看报告</span></a>{markup(r.get("source"))}</div>')
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
    from public_catalog import deleted_examples
    if enabled(store.settings) or deleted_examples(store):
        data = manifest(store)
        release, name = relative.split('/', 1)
        if release != data.get('release') or name not in data.get('files', {}): raise KeyError(url)
    base=root(store);target=(base/relative).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.is_symlink():raise KeyError(url)
    return target
