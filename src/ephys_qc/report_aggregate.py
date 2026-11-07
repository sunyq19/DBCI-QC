"""Aggregate EEG evidence across native windows without averaging window scores."""
import copy
import json
import math
from pathlib import Path


def channel_evidence(continuity, line, muscle):
    rows = {}
    def row(item):
        cid = item.get('channel_id')
        if cid is None:
            return None
        return rows.setdefault(cid, {'channel_id': cid, 'name': item.get('channel_name', item.get('name', str(cid))), 'components': {}})
    for item in continuity.get('measurements', []):
        r = row(item)
        if r is not None:
            a, b = item.get('finite_outside_constant_sample_count'), item.get('finite_sample_count')
            n = item.get('nonfinite_sample_count')
            if all(isinstance(x, (int, float)) and math.isfinite(x) for x in (a,b,n)) and 0 <= a <= b and n >= 0:
                r['components']['integrity'] = {'numerator': a, 'denominator': b+n}
    for item in line.get('channels', []) if line.get('score_eligible', True) else []:
        r = row(item)
        if r is not None:
            r['components']['line_noise'] = {'numerator': item['total']-item['hits'], 'denominator': item['total']}
            r['line_example'] = item.get('example')
    for item in muscle:
        r = row(item)
        a, b = item.get('candidate_seconds'), item.get('valid_seconds')
        if r is not None and item.get('status') == 'ok' and all(isinstance(x,(int,float)) and math.isfinite(x) for x in (a,b)) and 0 <= a <= b:
            r['components']['hf_burst'] = {'numerator': b-a, 'denominator': b}
    return list(rows.values())


NAMES = {'integrity':'信号完整性', 'line_noise':'工频干扰', 'hf_burst':'高频突发'}


def local_summary(evidence, expected_windows=1):
    """Expose the lowest assessed component per channel; not a new overall grade."""
    rows=[]
    for entry in evidence:
        components=[]
        for key,name in NAMES.items():
            part=entry['components'].get(key,{})
            den=part.get('denominator',0)
            value=100*part['numerator']/den if den>0 and part.get('windows',1)==expected_windows else None
            components.append({'id':key,'name':name,'value':value})
        measured=[c for c in components if c['value'] is not None]
        worst=min(measured,key=lambda c:c['value']) if measured else None
        rows.append({'channel_id':entry['channel_id'],'name':entry['name'],'components':components,
                     'lowest_component':worst,
                     'value':min(c['value'] for c in measured) if len(measured)==3 else None})
    rows.sort(key=lambda c:(c['lowest_component']['value'] if c['lowest_component'] else 101,c['name']))
    return {'channels':rows, 'lowest':next((r for r in rows if r['lowest_component']),None),
            'explanation':'通道分项为未命中占比；总体分项按通道异常占比的均方根计算。'}


def build_recording_view(result, artifacts, label=''):
    from .report_view import build_report_view, VIEW_VERSION
    if result.get('analysis_profile')!='scalp-eeg/1' or result.get('scope')!='recording':
        return None
    if not isinstance(result.get('coverage'),dict) or not isinstance(result.get('windows'),list):
        return None
    root=Path(artifacts).resolve(); declared={a['name'] for a in result.get('artifacts',[])}
    windows=result.get('windows',[]); views=[]; errors=[]; timeline=[]; last_stop=None
    for w in windows:
        view=None
        try:
            name=w['result_artifact']; p=(root/name).resolve()
            if w['status'] not in {'completed','partial'} or name not in declared or not p.is_relative_to(root):
                raise ValueError('Window unavailable')
            if last_stop is not None and w['start_sample']<last_stop:
                raise ValueError('Overlapping aggregation windows')
            last_stop=w['stop_sample']
            child=json.loads(p.read_text())
            rec=child.get('recording',{})
            if rec.get('start_sample')!=w['start_sample'] or rec.get('stop_sample')!=w['stop_sample']:
                raise ValueError('Window sample identity mismatch')
            if rec.get('source_indices')!=result['recording'].get('source_indices'):
                raise ValueError('Channel identity mismatch')
            prefix=w['id']+'--'
            child['artifacts']=[a for a in child.get('artifacts',[]) if prefix+a['name'] in declared]
            view=build_report_view(child,root,label,artifact_prefix=prefix)
            if view is None: raise ValueError('No EEG view')
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append(w.get('id','unknown'))
        views.append(view)
        timeline.append({'id':w['id'],'start_seconds':w['start_seconds'],'duration_seconds':w['duration_seconds'],
                         'status':w['status'],'value':view['score']['value'] if view else None,
                         'components':view['score']['components'] if view else [],
                         'report_artifact':w.get('report_artifact') if w.get('report_artifact') in declared else None})
    present=[v for v in views if v]
    # An empty evidence shell still produces an honest partial report.
    shell=build_report_view({**result,'scope':'window','artifacts':[]},root,label)
    base=copy.deepcopy(present[0] if present else shell)
    base.update(schema_version=VIEW_VERSION,scope='recording',label=label or result.get('label',''),
                recording=result['recording'],input_duration_seconds=result['coverage']['total_seconds'],
                artifacts=sorted(declared),modules=result['modules'],warnings=result.get('warnings',[]),
                plan_id=result.get('plan_id'),source_sha256=result.get('source_sha256'),
                window_scores=timeline,coverage=result['coverage'],window_count=len(windows),
                score_scope='recording',parameters={'aggregation':'ratio_of_summed_evidence',
                    'window_seconds':result.get('qc_config',{}).get('recording_options',{}).get('window_seconds',120),
                    'window_boundary_policy':'independent_native_windows',
                    'method_config':result.get('qc_config',{}).get('method_config',{})})
    parts=[]
    for i,key in enumerate(NAMES):
        source=[v['score']['components'][i] for v in present]
        good=sum(c['numerator'] for c in source if c['value'] is not None)
        total=sum(c['denominator'] for c in source if c['value'] is not None)
        assessed=sum(w['duration_seconds'] for w,v in zip(windows,views) if v and v['score']['components'][i]['value'] is not None)
        value=100*good/total if total and len(source)==len(windows) and all(c['value'] is not None for c in source) else None
        parts.append({**base['score']['components'][i],'value':value,'numerator':good,'denominator':total,
                      'assessed_window_seconds':assessed,'window_count':sum(c['value'] is not None for c in source),
                      'assessed_channels':result['recording']['channel_count'] if value is not None else 0})
    cov=result['coverage']
    complete=bool(windows) and not errors and cov['completed_samples']==cov['total_samples'] and not cov['gap_samples'] and result.get('source_integrity')=='verified_after_run' and result.get('status') not in {'failed','cancelled'}
    scored_windows=[w for w in timeline if w['value'] is not None]
    base['lowest_window']=min(scored_windows,key=lambda w:w['value']) if scored_windows else None
    # Combine per-channel sufficient statistics; retain every window's identity.
    channels={}; line_channels={}; hf=[]; hf_count=0; hf_ids=set(); line_ids=set(); fingerprints={}
    for v,w in zip(views,windows):
        if not v: continue
        fingerprints.update(v['source_fingerprints'])
        for r in v.get('channel_evidence',[]):
            dest=channels.setdefault(r['channel_id'],{'channel_id':r['channel_id'],'name':r['name'],'components':{}})
            for key,part in r['components'].items():
                if part.get('denominator',0)<=0: continue
                d=dest['components'].setdefault(key,{'numerator':0,'denominator':0,'windows':0})
                for field in ('numerator','denominator'):d[field]+=part[field]
                d['windows']+=1
            if r.get('line_example'):
                old=dest.get('line_example')
                if old is None or old.get('amplitude_uv',0)<r['line_example'].get('amplitude_uv',0):dest['line_example']=r['line_example']
        hf_count+=v.get('hf_candidate_count') or 0
        hf_ids.update(c['channel_id'] for c in v.get('channel_evidence',[]) if c['components'].get('hf_burst',{}).get('denominator',0)>c['components'].get('hf_burst',{}).get('numerator',0))
        for c in v['hf_candidates']:
            if len(hf)<100: hf.append({**c,'window_id':w['id'],'evidence_artifact':w['id']+'--M06_muscle.json'})
    for cid,r in channels.items():
        part=r['components'].get('line_noise',{});total=part.get('denominator',0);hits=total-part.get('numerator',0)
        if hits:
            line_ids.add(cid);line_channels[cid]={'channel_id':cid,'name':r['name'],'hits':hits,'total':total,'percent':100*hits/total,'example':r.get('line_example')}
    ranked=sorted(line_channels.values(),key=lambda r:(-r['hits'],r['name']))
    base.update(channel_evidence=list(channels.values()),local_quality=local_summary(list(channels.values()),len(windows)),
                line_channels=ranked[:100],hf_candidates=hf,hf_candidate_count=hf_count if present else None,
                hf_affected_channels=len(hf_ids),source_fingerprints=fingerprints)
    from .scoring import burden_score, score_revision
    base['score']=burden_score(list(channels.values()),result['recording']['channel_count'],
                              expected_windows=len(windows),coverage_complete=complete)
    for part,pooled in zip(base['score']['components'],parts):
        part.update(assessed_window_seconds=pooled['assessed_window_seconds'],window_count=pooled['window_count'])
    scoring_config = result.get('qc_config',{}).get('scoring')
    if scoring_config and scoring_config['version']=='project-weighted/1.1':
        from .method_scores import aggregate, core_outputs
        score_rows = core_outputs(list(channels.values()), result['recording']['channel_count'], expected_windows=len(windows), coverage_complete=complete)
        score_rows += [r for r in result.get('method_scores',[]) if r['id'] not in NAMES]
        base['score'] = aggregate(score_rows, scoring_config, coverage_complete=complete)
        for part in base['score']['components']:
            previous = next((p for p in parts if p['id']==part['id']), {})
            part.setdefault('window_count',previous.get('window_count',0))
            part.setdefault('assessed_window_seconds',previous.get('assessed_window_seconds', sum(w['duration_seconds'] for w in windows) if part['value'] is not None else 0))
    elif scoring_config:
        from .project_scoring import weighted_score
        base['score'] = weighted_score(list(channels.values()),result['recording']['channel_count'],
            result['qc_config']['scoring'],expected_windows=len(windows),coverage_complete=complete)
        for part,pooled in zip(base['score']['components'],parts):
            part.update(assessed_window_seconds=pooled['assessed_window_seconds'],window_count=pooled['window_count'])
    parts=base['score']['components']
    base['score_revision']=score_revision(result,base['score'])
    base['scoring_complete']=base['score']['value'] is not None
    base['parameters']['aggregation']=base['score']['aggregation']
    base['line']={key:sum(v['line'][key] for v in present) for key in ('total','hits','observed_frequency_rows','flagged_frequency_rows')}
    base['line'].update(assessed_channels=sum('line_noise' in r['components'] for r in channels.values()),affected_channels=len(line_ids),
                        percent=100*base['line']['hits']/base['line']['total'] if base['line']['total'] else None)
    base['finite']={key:sum(v['finite'].get(key) or 0 for v in present) if present else None for key in ('total','finite','nonfinite','constant','finite_outside_constant')}
    base['finite'].update(measured_channels=sum('integrity' in r['components'] for r in channels.values()))
    base['checks']=[{'name':p['name'],'value':f'{p["window_count"]}/{len(windows)} 个窗口可计分，{p["assessed_window_seconds"]:g} 秒',
                     'state':'已汇总' if p['value'] is not None else '部分未评','artifact':'window-results.json','note':'逐窗原始证据可追溯。'} for p in parts]
    base['checks'].append({'name':'补充检查','value':'通道一致性、辅助锁时、事件及扩展结果见逐窗报告','state':'逐窗保留','artifact':'window-results.json','note':''})
    base['failures']=[m['id'] for m in result['modules'] if m['status']=='failed']
    base['evidence_errors']=[f'{len(errors)} 个窗口证据未能核对'] if errors else []
    base['notes']=['逐通道累加各窗分子分母，再计算异常占比的均方根；总分取最低分项。不平均窗口分数。',
                   '各窗口独立检测，阈值与边缘剔除逐窗计算；边界可能影响候选。',
                   '通道与辅助导联的额外检查保留在逐窗报告中，未并入三项基础评分。']
    base['notes'].extend(dict.fromkeys(note for v in present if v.get('processing_scope') for note in v['notes'] if '滤波' in note or '输入信号' in note or '频带未完整' in note))
    if base['score']['version'].startswith('project-weighted/'):
        base['notes'][0]=base['score']['formula']
        base['notes'][2]='扩展方法按配置权重纳入；无权重的结果单独展示。'
        base['local_quality']['explanation']='通道分项与总体分项均按各自范围的候选量与有效检查量计算。'
    if not base['scoring_complete'] and base['score'].get('status')!='disabled':base['notes'].append('部分范围或基础分项未完成，不给整份总分；已有证据仍展示。')
    line=base['line'];base['headline']='检出待复核线索' if line['hits'] or hf_count or base['finite']['nonfinite'] or base['finite']['constant'] else '基础检查未检出候选'
    if not base['scoring_complete'] and base['score'].get('status')!='disabled':base['headline']='已完成部分检查'
    base['summary']=f'工频候选涉及 {len(line_ids)} 个通道；高频突发有 {hf_count} 条候选区间。'
    base['priority']='工频优先复核：'+'；'.join(f'{c["name"]} 命中 {c["hits"]}/{c["total"]} 窗' for c in ranked[:2])+'。' if ranked else ''
    return base
