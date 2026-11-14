#!/usr/bin/env python3
"""Build a portable example release offline. Never starts Store/workers.

Usage: python scripts/publish_example_cache.py --config .local/workbench.json
Only declared demo datasets and comparison runs are exported. Signals and private runtime
records are not included; runtime JSON/parameters are excluded from public HTML.
"""
import argparse,copy,hashlib,json,pathlib,re,shutil,sys,tempfile,threading
from datetime import datetime,timezone
from html import escape,unescape
from urllib.parse import urljoin,urlsplit,unquote,parse_qs
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


def comparison_page(spec, views, source, language):
    """Two explicit saved runs: compare workflow scope, never rank unlike scores."""
    en=language=='en'
    t=lambda zh,english:english if en else zh
    esc=lambda value:escape(str(value),quote=True)
    label=spec.get('label_en',spec['label']) if en else spec['label']
    rec=views[0]['recording'];start=rec.get('start_seconds',0);duration=rec.get('duration_seconds',0)
    window=next((w for w in views[0].get('window_scores',[]) if str(w.get('id',''))+'--'==spec['window']),None)
    graph_scope=(f'{window["start_seconds"]:g}–{window["start_seconds"]+window["duration_seconds"]:g} s' if window else t('所选窗口','selected window'))
    cards=[]
    for variant,view in zip(spec['variants'],views):
        jid=variant['job_id'];score=view['score'];value=score.get('value')
        parts=[p for p in score['components'] if p.get('weight',0)>0]
        total=sum(p.get('weight',0) for p in parts)
        names={'integrity':'Integrity','line_noise':'Line interference','hf_burst':'High-frequency bursts','gnosis_line_length':'Line length','gnosis_artifact':'Artifact intervals','gnosis_low_band':'Low-band abnormalities','gnosis_high_band':'High-band abnormalities','gnosis_psd_deviation':'PSD differences'}
        basis=' · '.join(f'{names.get(p["id"],p["name"]) if en else p["name"]} {p.get("weight",0)/total*100:.1f}%' for p in parts) if total else t('未启用综合评分','No overall score configured')
        title=variant.get('label_en',variant['label']) if en else variant['label']
        description=variant.get('description_en',variant['description']) if en else variant['description']
        result=t('整份总分未汇总','Overall score not aggregated') if value is None else f'{value:.2f} / 100'
        score_class='score-unavailable' if value is None else ''
        result_note=variant.get('result_note_en',variant.get('result_note','')) if en else variant.get('result_note','')
        coverage_note=f'<p class="route-coverage">{esc(result_note)}</p>' if value is None and result_note else ''
        cards.append(f'''<section class="route-card"><h2>{esc(title)}</h2><p>{esc(description)}</p>
<p class="route-score"><span>{t('本方案评分','Score for this configuration')}</span><strong class="{score_class}">{esc(result)}</strong></p>
{coverage_note}<p class="score-basis">{esc(basis)}</p><div class="route-actions"><a class="primary" href="/api/v1/jobs/{jid}/report">{t('查看报告','Report')}</a><a href="/api/v1/jobs/{jid}/report.pdf" download>PDF</a><a href="/api/v1/jobs/{jid}/visualizations">{t('查看图表','Charts')}</a></div></section>''')
    differences=[
        (t('输入处理','Signal preparation'),t('直接检查输入信号。','Checks the input signal.'),t('保留共同基础检查；扩展方法另用 ≤256 Hz、1–70 Hz、平均参考的分析副本。','Keeps common base checks; extensions use a separate copy at ≤256 Hz, 1–70 Hz and common-average reference.')),
        (t('主要检查','Main checks'),t('完整性、工频、高频突发；另列 PREP 坏道候选等结果。','Integrity, line interference and high-frequency bursts; PREP channel candidates remain separately reported.'),t('增加线长、伪差区间、低频/高频异常、PSD 通道差异与频带特征。','Adds line length, artifact intervals, low/high-band abnormalities, PSD channel differences and band features.')),
        (t('计分组成','Scored components'),t('信号完整性、工频干扰、高频突发，三项等比例。','Integrity, line interference and high-frequency bursts, equally weighted.'),t('线长、伪差区间、低频异常、高频异常、PSD 差异，五项等比例。基础分项另列。','Line length, artifact intervals, low-band, high-band and PSD differences, equally weighted. Base results remain separate.')),
        (t('重点图表','Key charts'),t('原始 PSD、工频命中比例、通道指标、候选波形及时间轴。','Input PSD, line-detection ratios, channel metrics, candidate waveforms and a timeline.'),t('分析副本 PSD、异常时间占比、频带功率/幅值、PSD 差异、参考区间。','Prepared-copy PSD, abnormal-time fractions, band power/amplitude, PSD differences and reference ranges.')),
        (t('如何理解差异','Interpretation'),t('定位输入信号中的问题。','Locate findings in the input signal.'),t('默认避开候选伪差后统计频谱；无合适片段时该项未评。曲线更平滑不等于数据更好。','Spectra normally use the artifact complement; without suitable segments, that item is unassessed. Smoother curves do not establish better data.')),
    ]
    rows=''.join('<tr>'+''.join(f'<{tag}>{esc(value)}</{tag}>' for tag,value in zip(['th','td','td'],row))+'</tr>' for row in differences)
    source_url=source.get('url','');source_link=(f'<a href="{esc(source_url)}">{esc(source.get("name","Open data"))}</a>' if source_url.startswith('https://') else esc(source.get('name','')))
    return f'''<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(label)} · DBCI-QC</title><link rel="stylesheet" href="/ui-tokens.css"><style>
*{{box-sizing:border-box}}body{{margin:0;background:var(--workspace,#f3f5f8);color:var(--ink,#243449);font:14px/1.65 var(--font-ui,system-ui)}}a{{color:var(--primary,#2459bc);text-decoration:none}}a:hover{{text-decoration:underline}}nav{{background:white;border-bottom:1px solid var(--line);padding:16px max(24px,calc((100vw - 1120px)/2));display:flex;gap:24px;justify-content:space-between}}main{{max-width:1168px;padding:32px 24px;margin:auto}}h1{{font-size:24px;margin:0 0 8px;font-weight:600}}h2{{font-size:16px;margin:0 0 12px;font-weight:600}}p{{margin:8px 0}}.lead,.facts,.score-basis{{color:var(--muted)}}.facts{{display:flex;gap:12px 24px;flex-wrap:wrap;font-size:13px}}.routes{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:24px 0}}.route-card,.comparison{{background:white;border:1px solid var(--line);border-radius:6px;padding:24px}}.route-score{{display:flex;align-items:baseline;justify-content:space-between;margin-top:24px;padding-top:16px;border-top:1px solid var(--line);gap:12px}}.route-score span{{font-size:12px;color:var(--muted)}}.route-score strong{{font-size:25px;font-weight:600;font-variant-numeric:tabular-nums}}.route-score .score-unavailable{{font-size:17px;text-align:right;line-height:1.5}}.score-basis{{font-size:12px;min-height:60px}}.route-coverage{{font-size:13px;padding:10px 12px;background:#f8f6ef;border-left:2px solid #b68944}}.route-actions{{display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin-top:20px}}.route-actions .primary{{background:var(--primary);color:white;border-radius:4px;padding:7px 12px;text-decoration:none}}.note{{border-left:3px solid var(--primary);padding:10px 14px;background:var(--primary-light);font-size:13px}}.table-scroll{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;min-width:650px;font-size:13px}}th,td{{text-align:left;padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top}}thead th{{background:var(--wash);font-weight:500}}tbody th{{width:120px;font-weight:500}}td{{width:43%}}footer{{margin:24px 0;color:var(--muted);font-size:12px}}@media(max-width:720px){{.routes{{grid-template-columns:1fr}}main{{padding:24px 16px}}.route-card,.comparison{{padding:18px}}nav{{padding:14px 16px}}}}@media print{{body{{background:white}}nav,.route-actions{{display:none}}main{{padding:0}}.route-card{{break-inside:avoid}}}}
</style></head><body><nav><a href="/">{t('← 返回质控台','← Workbench')}</a><a href="/standards/eeg-scoring">{t('评分说明','Scoring rules')}</a></nav><main>
<h1>{esc(label)}</h1><p class="lead">{esc(spec.get('description_en',spec['description']) if en else spec['description'])}</p>
<div class="facts"><span>{esc(views[0]['label'])}</span><span>{rec.get('channel_count')} {t('通道','channels')} · {rec.get('sampling_rate_hz'):g} Hz</span><span>{t('两份报告均检查','Both reports cover')} {start:g}–{start+duration:g} s</span></div>
<p class="note">{t('两种配置的计分项目不同，总分不用于判断哪套方法更好。请比较发现的问题、定位与证据。','The scored components differ. Overall scores cannot rank these methods; compare their findings, locations and evidence.')}</p>
<div class="routes">{''.join(cards)}</div><section class="comparison"><h2>{t('两套方案看什么','What each workflow examines')}</h2><div class="table-scroll"><table><thead><tr><th>{t('比较内容','Aspect')}</th><th>{t('当前推荐方案','Recommended workflow')}</th><th>{t('灵犀云扩展方案','Gnosis extensions')}</th></tr></thead><tbody>{rows}</tbody></table></div></section>
<footer><p>{t('图表快照选取同一原记录窗口','Chart snapshots use the same recording window')} {esc(graph_scope)}。{t('通道指标最多显示64道，PSD曲线显示前12道；整份报告按实际证据汇总。','Channel plots show up to 64 channels; PSD curves show the first 12. Full reports aggregate the saved evidence.')}</p><p>{t('此样例为注意任务。灵犀云结果用于方法对照演示，不作为静息态标准验证；头皮地形图和雷达图尚未接入。','This is an attention task. Gnosis results demonstrate the methods, not validation of a resting-state standard. Topography and radar plots are not yet integrated.')}</p><p>{t('数据来源','Data source')}：{source_link} · {esc(source.get('version',''))} · {esc(source.get('license',''))}</p><p><a href="https://github.com/sunyq19/DBCI-QC">DBCI-QC</a> · <a href="https://github.com/Jlei61/BrainElecQC">BrainElecQC</a> · <a href="https://github.com/Gnosis-Neurodynamics/GnosisNeuroDynamicSE">GnosisNeuroDynamicSE</a></p></footer></main></body></html>'''


def publish(config,destination):
    from data_library import featured_reports
    from dataset_overview import build_overview,render_overview
    from saved_reports import served_report, frozen_view
    from project_score_cache import load
    from ephys_qc.report_export import pdf_bytes, evidence_figure
    from ephys_qc.report_presentation import focused_figure
    from ephys_qc.visualizations.render import render_gallery
    from presentation_cache import load_evidence
    store=snapshot(config);examples=featured_reports(store)
    if not examples:raise ValueError('No explicitly configured examples')
    overviews={r['package_id']:build_overview(store,r['package_id']) for r in examples}
    jobids={r['signal']['job_id'] for o in overviews.values() for r in o['records'] if r.get('signal',{}).get('report_url')}
    comparisons=copy.deepcopy(store.settings.get('demo_comparisons',[]))
    comparison_jobs={}
    for comparison in comparisons:
        if not re.fullmatch(r'[a-z0-9-]+',comparison.get('id','')) or len(comparison.get('variants',[]))!=2:
            raise ValueError('A comparison requires an explicit ID and two saved runs')
        if len({v['job_id'] for v in comparison['variants']})!=2:
            raise ValueError('A comparison requires two distinct saved runs')
        if not re.fullmatch(r'w[0-9]{6}--',comparison.get('window','')):
            raise ValueError('A comparison requires an explicit recording window')
        for variant in comparison['variants']:
            jid=variant['job_id']
            if not re.fullmatch(r'[a-f0-9]{32}',jid) or store.job(jid)['status']!='completed':
                raise ValueError('Comparison run is not complete: '+jid)
            if store.job(jid)['input_id']!=comparison['input_id']:
                raise ValueError('Comparison must use the same declared input')
            comparison_jobs[jid]={**variant,'comparison_id':comparison['id'],'window':comparison['window'],'limit':comparison.get('limit',64)}
            jobids.add(jid)
    if any(r['reported']!=r['records'] for r in examples):raise ValueError('Publish only after every example has a saved report')
    # Freeze finding indexes alongside their reports. The server may attach
    # an explicitly configured, fingerprint-verified source for exploration.
    interactive_jobs={jid for jid in jobids if store.job(jid).get('plan',{}).get('input_modality',{}).get('value') in {'scalp_eeg','ecog','seeg','extracellular'}}
    destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='examples-',dir=destination.parent) as temp:
        out=pathlib.Path(temp);done=set();replacement='/examples/RELEASE/';views={};figures={}
        def put(name,data):
            p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data if isinstance(data,bytes) else data.encode())
        from example_review import snapshot as review_snapshot
        review_receipts={}
        for jid in sorted(interactive_jobs):
            review=review_snapshot(store.workspace(jid))
            encoded=json.dumps(review,ensure_ascii=False,allow_nan=False,separators=(',',':'))
            if len(encoded.encode()) > 32 * 1024**2:
                raise ValueError('Example review snapshot exceeds the serving limit: '+jid)
            if re.search(r'/(?:home|media|tmp|mnt)/',encoded):
                raise ValueError('Machine paths must not be published in example review metadata')
            put(f'review/{jid}.json',encoded)
            review_receipts[jid]={'finding_count':len(review['findings']['findings']),
                'default_method_ids':review['findings']['default_method_ids'],
                'source_sha256':review['source']['source_sha256']}
        def report_view(jid):
            if jid not in views:
                saved=load(store,jid)
                views[jid]=saved.get('report_view') if saved else frozen_view(store,jid)
            return views[jid]
        def figure(jid):
            if jid not in figures:
                view=report_view(jid)
                try:figures[jid]=evidence_figure(view,store.workspace(jid)) if view else (None,[])
                except (OSError,KeyError,ValueError,RuntimeError,ImportError):figures[jid]=(None,['波形未随快照发布；原始测量结果保留。'])
            return figures[jid]
        def gallery(jid,language,embedded=False):
            view=report_view(jid)
            name=f'visualizations/{jid}{".embedded" if embedded else ""}.{language}.html'
            if name not in done:
                done.add(name)
                if view:
                    result={k:view.get(k) for k in ('scope','recording')}
                    result.update(windows=view.get('window_scores',[]),artifacts=[{'name':n} for n in view['artifacts']])
                else:
                    result=store.result(jid,compact=True)
                options=comparison_jobs.get(jid,{})
                selected=copy.deepcopy(options.get('visualizations'))
                if selected is not None:
                    names=[a['name'] for a in result.get('artifacts',[])]
                    for stem,keys in [('M04_spectral.json',('psd','interference')),('M06_muscle.json',('timeline',))]:
                        if any(n.endswith(stem) for n in names):
                            selected.extend(k for k in keys if k not in selected)
                html=render_gallery(result,lambda n:load_evidence(store,jid,n),
                    selected=selected,window=options.get('window',''),limit=options.get('limit',32),
                    embedded=embedded,back_url=f'/api/v1/jobs/{jid}/report',asset_url=lambda n:f'/api/v1/jobs/{jid}/artifacts/{n}')
                html=re.sub(r'<form\b.*?</form>','',html,flags=re.S|re.I)
                html=html.replace('读取已有结果，切换图表不会重新质控或改变分数。','已保存的图表快照，不重新计算或更改分数。')
                put(name,clean(html,f'/api/v1/jobs/{jid}/visualizations',language))
            return replacement+name
        def _resource(value,origin,language):
            value=unescape(value)
            if value.startswith(('#','https://','http://','data:')):return value
            parsed=urlsplit(urljoin('https://local'+origin,value))
            path=unquote(parsed.path)
            requested_language=parse_qs(parsed.query).get('lang',[language])[0]
            if requested_language in {'zh-CN','en'}:language=requested_language
            m=re.fullmatch(r'/api/v1/packages/([\w-]+)/overview/report',path)
            if m and m[1] in overviews:return replacement+f'datasets/{m[1]}.{language}.html'
            m=re.fullmatch(r'/api/v1/jobs/([a-f0-9]{32})/(report|report\.pdf|report-evidence\.png|report-focus-\d+\.png|visualizations|artifacts/([\w.\-]+))',path)
            if m and m[1] in jobids:
                jid,action,filename=m.groups()
                if action=='report':return replacement+f'records/{jid}.{language}.html'
                if action=='visualizations':return gallery(jid,language,parse_qs(parsed.query).get('embedded')==['1'])
                if action.startswith('report-focus-'):
                    index=int(action[13:-4]);key=(jid,index)
                    if key not in figures:
                        try:figures[key]=focused_figure(report_view(jid),store.workspace(jid),index)
                        except (OSError,KeyError,ValueError,RuntimeError,ImportError):figures[key]=(None,[])
                    image,_=figures[key]
                    if image is None:return '#snapshot-info'
                    name=f'records/{jid}.focus-{index}.png';put(name,image)
                    return replacement+name
                if action=='report-evidence.png':
                    image,_=figure(jid)
                    if image is None:return '#snapshot-info'
                    name=f'records/{jid}.evidence.png';put(name,image)
                    return replacement+name
                if action=='report.pdf':
                    view=report_view(jid)
                    if not view:return '#snapshot-info'
                    name=f'records/{jid}.pdf'
                    if name not in done:
                        done.add(name)
                        image,notes=figure(jid)
                        put(name,pdf_bytes(view,image,notes,job_id=jid))
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
            if path in {'/ui-tokens.css','/workbench-ui.css','/dataset-report.css','/dataset-report.js','/visualizations.js','/report-interactions.js','/waveform-explorer.js','/waveform-explorer.css','/standards-nav.js'}:
                src=REPO/'apps/workbench/web'/path[1:]
                if src.is_file():put('assets'+path,src.read_bytes());return replacement+'assets'+path
            if path.startswith('/standards'):return path
            if path=='/':return '/'
            return '#snapshot-info'
        def resource(value,origin,language):
            result=_resource(value,origin,language)
            fragment=urlsplit(unescape(value)).fragment
            # Preserve figure anchors and expanded-module targets after freezing.
            if fragment and not result.startswith('#') and not value.startswith(('http:','https:')):
                result+='#'+fragment
            return result
        def clean(html,origin,language):
            # A release-specific read-only endpoint uses the same frozen index
            # as this report. Never couple a snapshot to a changing runtime job.
            def review_base(match):
                jid=match[1]
                return f' data-waveform-base="/api/v1/examples/RELEASE/records/{jid}"' if jid in interactive_jobs else ''
            html=re.sub(r'\sdata-waveform-base="/api/v1/jobs/([a-f0-9]{32})"',review_base,html)
            html=re.sub(r'<pre\b[^>]*>.*?</pre>','',html,flags=re.S|re.I)
            # A public example has no user's live run workspace to restore.
            html=re.sub(r'<a\b[^>]*>\s*(?:本次检查|Open this run)\s*</a>','',html)
            html=re.sub(r'''\b(data-chart-src|src|href)=(['"])([^'"]+)\2''',lambda m:m[1]+'='+m[2]+escape(resource(m[3],origin,language),quote=True)+m[2],html)
            html=re.sub(r'<img\b[^>]*\bsrc=[\"\']#snapshot-info[\"\'][^>]*>','',html,flags=re.I)
            html=re.sub(r'<a\b[^>]*\bhref=[\"\']#snapshot-info[\"\'][^>]*>(.*?)</a>',lambda m:'<span class="snapshot-unavailable" title="'+('Not included in this example' if language=='en' else '此示例未附带该文件')+'">'+m[1]+'</span>',html,flags=re.S|re.I)
            html=re.sub(r'/(?:home|media|tmp)/[^\s<>"\'&]+','[本地来源路径]',html)
            note=('Reports, figures and saved finding locations are included. Interactive waveforms require the corresponding example source configured on the server.' if language=='en' else '示例保存报告、图像及检查位置。交互波形按需读取服务端配置的对应示例文件。')
            return html.replace('</body>',f'<details id="snapshot-info" style="max-width:1100px;margin:16px auto;padding:0 16px;color:#607087;font-size:12px"><summary>'+('About this example' if language=='en' else '示例文件说明')+f'</summary><p>{note}</p></details></body>')
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
                # Each modality uses the same read-only frozen finding index.
                html=clean(served_report(store,jid,language,interactive=jid in interactive_jobs),f'/api/v1/jobs/{jid}/report',language)
                if jid in comparison_jobs:
                    url=replacement+f'comparisons/{comparison_jobs[jid]["comparison_id"]}.{language}.html'
                    label='← EEG workflow comparison' if language=='en' else '← 返回 EEG 方案对照'
                    link=f'<a href="{escape(url,quote=True)}">{label}</a>'
                    html=re.sub(r'(<nav class="saved-report-nav"[^>]*>)',lambda m:m[1]+link,html,count=1)
                put(f'records/{jid}.{language}.html',html)
            for comparison in comparisons:
                source=store.inputs[comparison['input_id']].get('provenance',{})
                actual=[report_view(v['job_id']) for v in comparison['variants']]
                if any(not v for v in actual):raise ValueError('A comparison needs two saved report views')
                identity=lambda v:(v.get('source_sha256'),v['recording'].get('source_indices'),v['recording'].get('start_seconds'),v['recording'].get('duration_seconds'))
                if identity(actual[0])!=identity(actual[1]):raise ValueError('Comparison data or checked range differs')
                for v in actual:
                    if not any(str(w.get('id',''))+'--'==comparison['window'] for w in v.get('window_scores',[])):
                        raise ValueError('Selected comparison window is not in the saved report')
                for v in comparison['variants']:
                    gallery(v['job_id'],language)
                    resource(f'/api/v1/jobs/{v["job_id"]}/report.pdf','/',language)
                page=comparison_page(comparison,actual,source,language)
                put(f'comparisons/{comparison["id"]}.{language}.html',clean(page,'/',language))
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
        comparison_rows=[{k:v for k,v in c.items() if k in {'id','label','label_en','description','description_en'}} for c in comparisons]
        for row in comparison_rows:row.update(url=f'/examples/{release}/comparisons/{row["id"]}.zh-CN.html',url_en=f'/examples/{release}/comparisons/{row["id"]}.en.html',cached=True)
        # Keep the exact run and scoring provenance with the release. Checking
        # this receipt prevents a current UI from silently shipping old scores.
        report_scores={}
        for jid in sorted(jobids):
            job=store.job(jid)
            path=store.root/'jobs'/jid/'artifacts/method-scores.json'
            score=json.loads(path.read_text()).get('project_score') if path.is_file() else None
            if not score:
                score=(report_view(jid) or {}).get('score') or {}
            declared=job.get('plan',{}).get('input_modality',{})
            report_scores[jid]={'modality':declared.get('value') if isinstance(declared,dict) else declared,
                'created_at':job['created_at'],'preset':score.get('preset'),'version':score.get('version'),
                'value':score.get('value'),'components':[{k:c.get(k) for k in
                    ('id','value','status','configured_weight','weight','normalized_weight','automatically_excluded')}
                    for c in score.get('components',[])]}
        manifest={'schema_version':'example-cache/1','release':release,'published_at':datetime.now(timezone.utc).isoformat(),'examples':rows,'comparisons':comparison_rows,'report_scores':report_scores,'review_snapshots':review_receipts,'files':files,'raw_data_included':False}
        target=destination/release
        if not target.exists():shutil.copytree(out,target)
        pending=destination/'manifest.tmp';pending.write_text(json.dumps(manifest,ensure_ascii=False,indent=2));pending.replace(destination/'manifest.json')
        print(json.dumps({'release':release,'datasets':len(rows),'comparisons':len(comparison_rows),'reports':len(jobids),'files':len(files),'bytes':sum((target/f).stat().st_size for f in files)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,default=REPO/'apps/workbench/example-cache');args=p.parse_args();publish(args.config,args.output)
