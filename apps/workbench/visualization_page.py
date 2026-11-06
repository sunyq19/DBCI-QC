"""HTTP adapter for the optional presentation layer; reads only declared artifacts."""
import re
from urllib.parse import parse_qs, urlsplit, quote
from ephys_qc.visualizations.render import render_gallery
from ephys_qc.visualizations.evidence import read_evidence


def dispatch_visualizations(handler,path):
    match=re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/visualizations',path)
    if not match:return False
    identifier=match.group(1)
    query=parse_qs(urlsplit(handler.path).query,keep_blank_values=True)
    if set(query)-{'show','configured','window','limit','band'} or any(len(v)!=1 for k,v in query.items() if k!='show'):
        raise ValueError('图表选择参数无效。')
    result=handler.store.result(identifier,compact=True)
    def load(name):
        target=handler.store.artifact(identifier,name)
        return read_evidence(target)
    base=f'/api/v1/jobs/{identifier}'
    page=render_gallery(result,load,selected=query.get('show',[]) if query.get('configured')==['1'] else None,
                        window=query.get('window',[''])[0],limit=int(query.get('limit',['32'])[0]),band=query.get('band',['alpha'])[0],
                        back_url=base+'/report',action=base+'/visualizations',asset_url=lambda n:base+'/artifacts/'+quote(n))
    handler.send_bytes(page.encode(),'text/html; charset=utf-8')
    return True
