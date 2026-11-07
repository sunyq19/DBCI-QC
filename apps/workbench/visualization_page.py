"""HTTP adapter for the optional presentation layer; reads only declared artifacts."""
import re
from urllib.parse import parse_qs, urlsplit, quote
from ephys_qc.visualizations.render import render_gallery


def dispatch_visualizations(handler,path):
    match=re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/visualizations',path)
    if not match:return False
    identifier=match.group(1)
    query=parse_qs(urlsplit(handler.path).query,keep_blank_values=True)
    if set(query)-{'show','configured','window','limit','band','lang','embedded'} or any(len(v)!=1 for k,v in query.items() if k!='show'):
        raise ValueError('图表选择参数无效。')
    if query.get('lang',['zh-CN'])[0] not in {'zh-CN','en'}:
        raise ValueError('不支持此语言。')
    if query.get('embedded',['0'])[0] not in {'0','1'}:
        raise ValueError('图表显示方式无效。')
    if handler.store.job(identifier)['status']!='completed':
        raise ValueError('任务尚未完成，没有可用的最终报告。')
    from presentation_cache import gallery
    handler.send_bytes(gallery(handler.store,identifier,query),'text/html; charset=utf-8')
    return True


def build_gallery(store,identifier,query):
    # The gallery only needs the saved presentation manifest, not the potentially
    # very large candidate index in Store.result's generic summary builder.
    from project_score_cache import load as published_result
    from saved_reports import frozen_view
    saved=published_result(store,identifier)
    view=saved.get('report_view') if saved else frozen_view(store,identifier)
    if view:
        result={k:view.get(k) for k in ('scope','recording')}
        result.update(windows=view.get('window_scores',[]),
                      artifacts=[{'name':n} for n in view.get('artifacts',[])])
    else:
        result=store.result(identifier,compact=True)
    def load(name):
        from presentation_cache import load_evidence
        return load_evidence(store,identifier,name)
    base=f'/api/v1/jobs/{identifier}'
    return render_gallery(result,load,selected=query.get('show',[]) if query.get('configured')==['1'] else None,
                        window=query.get('window',[''])[0],limit=int(query.get('limit',['32'])[0]),band=query.get('band',['alpha'])[0],
                        back_url=base+'/report',action=base+'/visualizations',asset_url=lambda n:base+'/artifacts/'+quote(n),
                        embedded=query.get('embedded')==['1'])
