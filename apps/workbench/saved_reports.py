"""Serve frozen HTML without rebuilding spectra, scores or candidate indices."""
from html import escape
from pathlib import Path
import re
from urllib.parse import quote


def frozen_view(store, identifier):
    """Read the saved presentation data without recomputing QC or scores.

    Large candidate arrays stay on disk. The original report and evidence are
    untouched; the current template can also present older completed runs.
    """
    import copy
    import ijson
    path = store.root / 'jobs' / identifier / 'result.json'
    try:
        if path.is_symlink(): return None
        stat = path.stat(); signature = (stat.st_size, stat.st_mtime_ns)
        with store.lock:
            if not hasattr(store, 'presentation_views'): store.presentation_views = {}
            cached = store.presentation_views.get(identifier)
            if cached and cached[0] == signature: return copy.deepcopy(cached[1])
        from presentation_cache import cached, stamps
        import json
        def read_view():
            with path.open('rb') as handle:
                value = next(ijson.items(handle, 'report_view', use_float=True), None)
            return json.dumps(value, allow_nan=False).encode()
        view = json.loads(cached(path.parent, 'frozen-view', stamps([path]), read_view))
        if not isinstance(view, dict) or not view.get('score'): return None
        version = view['score'].get('version', '')
        if version not in {'eeg-basic-screen/0.1', 'eeg-basic-screen/0.2'} and not version.startswith('project-weighted/'):
            return None  # Preserve an unknown historical report in its original format.
        with store.lock:
            if len(store.presentation_views) >= 16: store.presentation_views.pop(next(iter(store.presentation_views)))
            store.presentation_views[identifier] = (signature, view)
        return copy.deepcopy(view)
    except (OSError, ValueError, ijson.JSONError):
        return None


def report_file(store, identifier):
    if store.job(identifier)['status'] != 'completed':
        raise ValueError('任务尚未完成，没有可用的最终报告。')
    root = store.root / 'jobs' / identifier / 'artifacts'
    target = root / 'report.html'
    if root.is_symlink() or target.is_symlink() or not target.is_file():
        raise KeyError('report.html')
    return target


def served_report(store, identifier, language='zh-CN'):
    from server import insert_report_navigation
    report = report_file(store, identifier).read_text(encoding='utf-8')
    from project_score_cache import load
    published = load(store, identifier)
    view = published.get('report_view') if published else frozen_view(store, identifier)
    if view:
        from ephys_qc.report_view import render_report_view
        report = render_report_view(view, evidence_url=f'/api/v1/jobs/{identifier}/report-evidence.png', pdf_url=f'/api/v1/jobs/{identifier}/report.pdf', visualization_url=f'/api/v1/jobs/{identifier}/visualizations', focus_url=lambda i:f'/api/v1/jobs/{identifier}/report-focus-{i}.png', waveform_url=f'/api/v1/jobs/{identifier}')
        note = '本页是保留原始检测证据的评分修订版。' if published else '使用当前版式展示运行时保存的结果，检测与分数未改动。'
        archive = f'<details class="report-archive"><summary>版本与存档</summary><p><a href="/api/v1/jobs/{identifier}/artifacts/report.html">运行时原始报告</a> · {note}</p></details>'
        report = report.replace('<div id="report-archive-slot"></div>', archive) if 'id="report-archive-slot"' in report else report.replace('</main>',archive+'</main>')
    declared = store.job(identifier).get('plan', {}).get('input_modality', {})
    modality = declared.get('value') if isinstance(declared, dict) else declared
    if modality in {'ecog', 'seeg', 'extracellular'}:
        from descriptive_report import render
        report = render(store, identifier, language) or report
        from ephys_qc.report_presentation import inline_charts
        chart_link=f'<p><a href="/api/v1/jobs/{identifier}/visualizations">'
        report=re.sub(re.escape(chart_link)+r'.*?</a></p>',
                      lambda _:inline_charts(f'/api/v1/jobs/{identifier}/visualizations',english=language=='en'),report)
        report=report.replace('</head>','<script src="/report-interactions.js" defer></script></head>',1)
    # Every relative resource is still checked against the artifact manifest by
    # its endpoint. This rewrite grants no access to new files or host paths.
    def resource(match):
        attr, mark, name = match.groups()
        if name.startswith(('/', '#', 'http:', 'https:', 'data:')) or Path(name).name != name:
            return match.group(0)
        return f'{attr}={mark}/api/v1/jobs/{identifier}/artifacts/{quote(name)}{mark}'
    report = re.sub(r'''\b(src|href)=(['"])([^'"]+)\2''', resource, report)
    report = report.replace('</head>', '<link rel="stylesheet" href="/ui-tokens.css"><link rel="stylesheet" href="/workbench-ui.css"></head>', 1)
    report = report.replace('<body>', '<body class="qc-signal-report">', 1)
    job = store.job(identifier)
    package = (job.get('dataset_context') or {}).get('package_id')
    en = language == 'en'
    links = [(f'/?job={identifier}', 'Open this run' if en else '本次检查')]
    if package and re.fullmatch('[a-zA-Z0-9_-]+', package):
        links.insert(0, (f'/api/v1/packages/{package}/overview/report?lang={language}',
                         '← Dataset report' if en else '← 返回数据集报告'))
    else: links.insert(0, ('/', '← Workbench' if en else '← 返回质控台'))
    print_button = ''
    if 'id="print-report"' not in report:
        print_button = '<button id="print-report">' + ('Print / PDF' if en else '打印 / PDF') + '</button>'
        report = report.replace('</head>', '<script src="/dataset-report.js" defer></script></head>', 1)
    navigation = '<nav class="saved-report-nav" aria-label="QC navigation">' + ''.join(
        f'<a href="{escape(url, quote=True)}">{text}</a>' for url, text in links) + print_button + '</nav>'
    return insert_report_navigation(report, navigation)


def artifact_names(store, identifier):
    """Small persistent manifest; never call score-building Store.result here."""
    import json
    import ijson
    from server import save_json
    if store.job(identifier)['status'] != 'completed': raise KeyError(identifier)
    path = store.root / 'jobs' / identifier / 'result.json'
    signature = [path.stat().st_mtime_ns, path.stat().st_size]
    cache = path.with_name('artifact-manifest-cache.json')
    try:
        if cache.stat().st_size < 1024 * 1024:
            saved = json.loads(cache.read_text())
            if saved['signature'] == signature: return set(saved['names'])
    except (OSError, ValueError, KeyError, TypeError): pass
    with path.open('rb') as handle:
        names = [item['name'] for item in ijson.items(handle, 'artifacts.item')]
    try: save_json(cache, {'signature': signature, 'names': names})
    except OSError: pass  # Read-only result archives remain usable.
    return set(names)
