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
    try:return _read(str(path),path.stat().st_mtime_ns)
    except (OSError,ValueError,TypeError):return {'schema_version':'example-cache/1','examples':[]}


def homepage(store, template):
    data=manifest(store);rows=data['examples']
    esc=lambda value:escape(str(value),quote=True)
    cards=[]
    for r in rows:
        cards.append(f'<a class="demo-report" href="{esc(r["url"])}"><span class="demo-report-copy"><strong>{esc(r["label"])}<small class="example-format">{esc(r["formats"])}</small></strong><span>{esc(r["description"])}</span><small>{r["subjects"]} 个体 · {r["records"]} 份记录 · 报告 {r["reported"]}/{r["records"]}</small></span><span class="demo-report-end">查看报告</span></a>')
    template=template.replace('<p class="small muted">正在读取示例目录…</p>', ''.join(cards) or '<p class="small muted">尚未发布示例报告。</p>')
    template=template.replace('<span id="demo-reports-count" class="tag subtle">—</span>',f'<span id="demo-reports-count" class="tag subtle">{len(rows)}</span>')
    if rows:template=template.replace('href="#demo-reports" hidden','href="#demo-reports"')
    comparisons=[]
    for row in data.get('comparisons',[]):
        comparisons.append(f'<a class="example-comparison-link comparison-zh" href="{esc(row["url"])}"><span>{esc(row["label"])}</span><small>同一数据 · 两套检查方案</small></a><a class="example-comparison-link comparison-en" href="{esc(row.get("url_en",row["url"]))}"><span>{esc(row.get("label_en",row["label"]))}</span><small>Same data · Two workflows</small></a>')
    template=template.replace('<!--example-comparisons-->',''.join(comparisons))
    encoded=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    return template.replace('</head>',f'<script id="example-cache" type="application/json">{encoded}</script></head>',1)


def asset(store, url):
    relative=url.removeprefix('/examples/')
    if not re.fullmatch(r'[a-f0-9]{16}/[A-Za-z0-9_.\-/]+',relative):raise KeyError(url)
    if '..' in Path(relative).parts:raise KeyError(url)
    base=root(store);target=(base/relative).resolve()
    if not target.is_relative_to(base) or not target.is_file() or target.is_symlink():raise KeyError(url)
    return target
