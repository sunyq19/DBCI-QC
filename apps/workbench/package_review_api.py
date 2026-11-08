"""Thin local HTTP adapter for D04; all checks remain in reusable core code."""
import re
from urllib.parse import parse_qs, urlsplit
from package_reviews import ReviewConflict


def dispatch(handler, path):
    if path == '/dataset-review-report.js' and handler.command == 'GET':
        from ephys_qc.dataset_qc.review_report_web import SCRIPT
        handler.send_bytes(SCRIPT.encode(), 'application/javascript; charset=utf-8')
        return True
    match = re.fullmatch(r'/api/v1/package-jobs/([a-f0-9]{32})/review(?:/(report|pdf))?', path)
    if not match:
        return False
    identifier, output = match.groups()
    reviews = handler.store.package_reviews
    if handler.command == 'POST' and not output:
        try:
            handler.json(reviews.save(identifier, handler.body()), 201)
        except ReviewConflict as error:
            handler.json({'error': str(error)}, 409)
        return True
    if handler.command == 'GET':
        query = parse_qs(urlsplit(handler.path).query)
        if set(query) - {'lang', 'download'} or any(len(v) != 1 for v in query.values()):
            raise ValueError('报告参数无效。')
        language = query.get('lang', ['zh-CN'])[0]
        if language not in {'zh-CN', 'en'}:
            raise ValueError('语言无效。')
        case = reviews.get(identifier)
        if output == 'report':
            from ephys_qc.dataset_qc.review_report import render_review_report
            headers = {'Content-Disposition': f'attachment; filename="dataset-review-{identifier[:8]}.html"'} if query.get('download') == ['1'] else None
            handler.send_bytes(render_review_report(case, language, standalone=bool(headers)).encode(), 'text/html; charset=utf-8', headers=headers)
        elif output == 'pdf':
            from ephys_qc.dataset_qc.review_report import review_pdf
            handler.send_bytes(review_pdf(case, language), 'application/pdf', headers={
                'Content-Disposition': f'attachment; filename="dataset-review-{identifier[:8]}.pdf"'})
        else:
            handler.json(case)
        return True
    return False
