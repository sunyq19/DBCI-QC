#!/usr/bin/env python3
"""Build a portable example release offline. Never starts Store/workers.

Usage: python scripts/publish_example_cache.py --config .local/workbench.json
Only explicitly declared demo datasets are exported. Signals and private runtime
records are not included; runtime JSON/parameters are excluded from public HTML.
"""
import argparse,copy,hashlib,json,pathlib,re,shutil,sys,tempfile,threading
from datetime import datetime,timezone
from html import escape,unescape
from urllib.parse import urljoin,urlsplit,unquote
REPO=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0]=[str(REPO/'src'),str(REPO/'apps/workbench')]


def snapshot(config):
    from server import Store
    from package_jobs import PackageJobs
    from intake import IntakeStore
    from ephys_qc.admission import configured_policy
    settings=json.loads(config.read_text());store=Store.__new__(Store)
    store.settings=settings;store.root=pathlib.Path(settings['data_dir']);store.lock=threading.RLock();store.dataset_summaries={}
    store.jobs={j['id']:j for j in (json.loads(f.read_text()) for f in (store.root/'jobs').glob('*/job.json'))}
    store.inputs={r['id']:r for r in settings.get('inputs',[])}
    for pattern in ['intakes/*/record.json','record-revisions/*/*.json']:
        for f in store.root.glob(pattern):
            r=json.loads(f.read_text())
            if 'id' in r and 'source_path' in r:store.inputs[r['id']]=r
    store.intakes=IntakeStore.__new__(IntakeStore);store.intakes.root=store.root/'intakes'
    p=PackageJobs.__new__(PackageJobs);p.root=store.root/'package_jobs';p.packages={q['id']:q for q in settings.get('packages',[])}
    p.lock=threading.RLock();p.jobs={j['id']:j for j in (json.loads(f.read_text()) for f in p.root.glob('*/job.json'))}
    p.admission_policy=configured_policy(settings);p.examples={r['package_id']:r for r in settings.get('demo_examples',[])};p.validation_ids=set(settings.get('validation_library_ids',[]));store.packages=p
    return store


def publish(config,destination):
    from data_library import featured_reports
    from dataset_overview import build_overview,render_overview
    from saved_reports import served_report
    from project_score_cache import load
    from ephys_qc.report_export import pdf_bytes, evidence_figure
    store=snapshot(config);examples=featured_reports(store)
    if not examples:raise ValueError('No explicitly configured examples')
    overviews={r['package_id']:build_overview(store,r['package_id']) for r in examples}
    jobids={r['signal']['job_id'] for o in overviews.values() for r in o['records'] if r.get('signal',{}).get('report_url')}
    if any(r['reported']!=r['records'] for r in examples):raise ValueError('Publish only after every example has a saved report')
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='examples-',dir=destination.parent) as temp:
        out=pathlib.Path(temp);done=set();replacement='/examples/RELEASE/'
        def put(name,data):
            p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode())
        def resource(value,origin,language):
            value=unescape(value)
            if value.startswith(('#','https://','http://','data:')):return value
            path=unquote(urlsplit(urljoin('https://local'+origin,value)).path)
            m=re.fullmatch(r'/api/v1/packages/([\w-]+)/overview/report',path)
            if m and m[1] in overviews:return replacement+f'datasets/{m[1]}.{language}.html'
            m=re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/(report|report.pdf|artifacts/([\w.\-]+))',path)
            if m and m[1] in jobids:
                jid,action,filename=m.groups()
                if action=='report':return replacement+f'records/{jid}.{language}.html'
                if action=='report.pdf':
                    view=load(store,jid)
                    if not view:return '#snapshot-info'
                    name=f'records/{jid}.pdf'
                    if name not in done:
                        done.add(name)
                        try:figure,notes=evidence_figure(view['report_view'],store.workspace(jid))
                        except (OSError,KeyError,ValueError,RuntimeError,ImportError):figure,notes=None,['波形未随快照发布；原始测量结果保留。']
                        put(name,pdf_bytes(view['report_view'],figure,notes,job_id=jid))
                    return replacement+name
                # Freeze presentation artifacts only; raw evidence remains in original runtime.
                src=store.root/'jobs'/jid/'artifacts'/filename
                if src.suffix not in {'.png','.svg','.html'} or not src.is_file():return '#snapshot-info'
                if src.stat().st_size>8*1024*1024:raise ValueError('Oversized presentation artifact: '+filename)
                name=f'artifacts/{jid}/{filename}'
                if name not in done:
                    done.add(name)
                    put(name,clean(src.read_text(),path,language) if src.suffix=='.html' else src.read_bytes())
                return replacement+name
            if path in {'/ui-tokens.css','/workbench-ui.css','/dataset-report.css','/dataset-report.js','/standards-nav.js'}:
                src=REPO/'apps/workbench/web'/path[1:]
                if src.is_file():put('assets'+path,src.read_bytes());return replacement+'assets'+path
            if path.startswith('/standards'):return path
            if path=='/':return '/'
            return '#snapshot-info'
        def clean(html,origin,language):
            html=re.sub(r'<pre\b[^>]*>.*?</pre>','',html,flags=re.S|re.I)
            html=re.sub(r'''\b(src|href)=(['"])([^'"]+)\2''',lambda m:m[1]+'='+m[2]+escape(resource(m[3],origin,language),quote=True)+m[2],html)
            html=re.sub(r'/(?:home|media|tmp)/[^\s<>"\'&]+','[本地来源路径]',html)
            note=('Saved public-data example. Reports and images are cached; original files and runtime evidence are not part of this snapshot.' if language=='en' else '公开数据示例快照。报告与图像已缓存；本页不包含原始数据和运行证据文件。')
            return html.replace('</body>',f'<p id="snapshot-info" style="max-width:1100px;margin:24px auto;padding:16px;color:#607087;font-size:12px">{note}</p></body>')
        for language in ['zh-CN','en']:
            for pid,o in overviews.items():
                # rendering is a pure saved-evidence view, no algorithm execution
                html=render_overview(o,language=language)
                source=o.get('source',{});sources=source.get('sources',[source])
                links=[]
                for source in sources:
                    url=source.get('dataset_url') or source.get('url')
                    if not url or not url.startswith('https://'):continue
                    title=source.get('name') or source.get('dataset') or source.get('dataset_id') or url
                    version=source.get('snapshot') or source.get('version') or source.get('version_doi') or ''
                    links.append(f'<li><a href="{escape(url,quote=True)}">{escape(title)}</a> · {escape(version)} · {escape(source.get("license",""))}</li>')
                html=html.replace('</main>', '<details class="disclosure"><summary>'+('Sources and licenses' if language=='en' else '来源与许可')+'</summary><ul>'+''.join(links)+'</ul></details></main>')
                put(f'datasets/{pid}.{language}.html',clean(html,f'/api/v1/packages/{pid}/overview/report',language))
            for jid in sorted(jobids):
                put(f'records/{jid}.{language}.html',clean(served_report(store,jid,language),f'/api/v1/jobs/{jid}/report',language))
        digest=hashlib.sha256()
        for f in sorted(out.rglob('*')):
            if f.is_file():digest.update(str(f.relative_to(out)).encode());digest.update(f.read_bytes())
        release=digest.hexdigest()[:16]
        for f in out.rglob('*.html'):f.write_text(f.read_text().replace('/examples/RELEASE/','/examples/'+release+'/'))
        rows=copy.deepcopy(examples)
        for row in rows:
            modes={r['modality'] for r in overviews[row['package_id']]['records']}
            row['modality']=next(iter(modes)) if len(modes)==1 else 'mixed'
            row['source']=overviews[row['package_id']].get('source',{})
            row.update(url=f'/examples/{release}/datasets/{row["package_id"]}.zh-CN.html',url_en=f'/examples/{release}/datasets/{row["package_id"]}.en.html',available=True,cached=True)
        files={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.rglob('*')) if f.is_file()}
        manifest={'schema_version':'example-cache/1','release':release,'published_at':datetime.now(timezone.utc).isoformat(),'examples':rows,'files':files,'raw_data_included':False}
        target=destination/release
        if not target.exists():shutil.copytree(out,target)
        pending=destination/'manifest.tmp';pending.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));pending.replace(destination/'manifest.json')
        print(json.dumps({'release':release,'datasets':len(rows),'reports':len(jobids),'files':len(files),'bytes':sum((target/f).stat().st_size for f in files)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,default=REPO/'apps/workbench/example-cache');args=p.parse_args();publish(args.config,args.output)
