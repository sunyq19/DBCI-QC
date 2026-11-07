"""Convert explicit candidate evidence to versioned, missing-safe score outputs.

No detector thresholds are added here. Units and denominators remain method-specific.
"""
import copy
import math
from .score_registry import SPECS, outputs, CONTRACT, enabled


def number(x):
    return type(x) in (int,float) and math.isfinite(x)


def observation(spec, bad=None, total=None, *, status='unavailable', reason='', scope=None, artifact=None):
    valid=number(bad) and number(total) and total>0 and 0<=bad<=total
    return dict(id=spec['id'],method_id=spec['method_id'],module_id=spec['module_id'],name=spec['name'],
        contract_version=CONTRACT,status='computed' if valid else status,value=100*(1-bad/total) if valid else None,
        candidate_amount=bad if valid else None,assessed_amount=total if valid else None,
        numerator=total-bad if valid else 0,denominator=total if valid else 0,unit=spec['unit'],
        reason=reason if reason else '按候选量与有效检查量计算。' if valid else '未得到完整有效的计分证据',scope=copy.deepcopy(scope or {}),
        source_artifacts=[artifact] if artifact else [],formula=spec['formula'])


def _ranges(rows,left,right):
    spans=[]
    for a,b in rows:
        if not number(a) or not number(b) or b<a or a<left-1e-6 or b>right+1e-6:
            raise ValueError('候选区间超出实际检查范围')
        if b>a:spans.append((max(left,a),min(right,b)))
    merged=[]
    for a,b in sorted(spans):
        if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
        else:merged.append((a,b))
    return merged


def extension_outputs(identifier,payload,modality='scalp_eeg',artifact=None):
    specs=outputs(modality,identifier);result=[]
    scope=copy.deepcopy(payload.get('range',{}))
    scope['preprocessing']=copy.deepcopy(payload.get('preprocessing',{}))
    if payload.get('metrics',{}).get('effective_duration_seconds') is not None:
        scope['effective_duration_seconds']=payload['metrics']['effective_duration_seconds']
        scope['used_intervals']=copy.deepcopy(payload['metrics'].get('used_intervals',[]))
    for spec in specs:
        try:
            if payload.get('status') not in {'completed','partial'} or payload.get('calculated') is False:
                raise ValueError(payload.get('reason') or '方法未完成')
            names=payload.get('channel_names',[])
            if not names or len(names)!=len(set(names)) or any(not isinstance(n,str) or not n for n in names):
                raise ValueError('缺少完整且唯一的受检通道身份')
            duration=scope.get('duration_seconds');start=scope.get('start_seconds');stop=scope.get('stop_seconds')
            if not all(number(v) for v in (duration,start,stop)) or duration<=0 or not math.isclose(stop-start,duration,abs_tol=1e-6):
                raise ValueError('缺少明确的检查时段')
            candidates=payload.get('candidates')
            if not isinstance(candidates,list):raise ValueError('未返回候选清单')
            kind=spec['reducer'];reason='候选按当前方法参数判定；不等于已确认伪迹。'
            if kind in {'encoding_samples','assessed_channels'}:
                assessed=payload.get('assessed_channel_names',[])
                if not assessed or len(set(assessed))!=len(assessed) or not set(assessed)<=set(names):
                    raise ValueError('缺少有效判定的通道分母')
                rows=[r for r in payload.get('measurements',[]) if r.get('channel_name') in assessed]
                if len(rows)!=len(assessed) or {r.get('channel_name') for r in rows}!=set(assessed) or any(r.get('status')!='computed' for r in rows):
                    raise ValueError('逐道判定证据不完整')
                if kind=='encoding_samples':
                    if any(not number(r.get('candidate_sample_count')) or not number(r.get('assessed_sample_count')) or not 0<=r['candidate_sample_count']<=r['assessed_sample_count'] for r in rows):
                        raise ValueError('端点平台计数无效')
                    bad=sum(r['candidate_sample_count'] for r in rows);total=sum(r['assessed_sample_count'] for r in rows)
                    reason='文件量程端点平台样本 / 已核验量程的有限样本；不是硬件饱和率。'
                else:
                    if any(not number(r.get('robust_z')) for r in rows):raise ValueError('缺少有效组内偏离值')
                    affected={c.get('channel_name') for c in candidates}
                    if not affected<=set(assessed):raise ValueError('候选超出已评通道')
                    bad,total=len(affected),len(assessed)
                    reason='离群候选 / 有效组内受检通道；不适用的组不计为通过。'
                scope['assessed_channel_names']=assessed
                scope['unassessed_channel_names']=[n for n in names if n not in assessed]
            elif kind in {'channels','pairs'}:
                affected=set()
                for c in candidates:
                    if kind=='pairs':
                        if c.get('localization')!='pair_only':raise ValueError('桥接候选类型不一致')
                        subset=c.get('channel_names',[])
                        if len(subset)!=2 or len(set(subset))!=2:raise ValueError('桥接通道对无效')
                        affected.update(subset)
                    elif c.get('localization')=='channel_only':affected.add(c.get('channel_name'))
                    elif identifier!='mne_amplitude':raise ValueError('非通道候选不能折算为坏通道')
                if not affected<=set(names):raise ValueError('候选通道不属于受检集合')
                if identifier=='mne_lof' and len(payload.get('channel_scores',[]))!=len(names):raise ValueError('LOF 未覆盖全部通道')
                if identifier=='gnosis_line_length' and set(payload.get('metrics',{}).get('line_length_by_channel',{}))!=set(names):raise ValueError('线长测量未覆盖全部通道')
                if identifier=='spikeinterface_bad_channels':
                    labels=payload.get('channel_labels',[])
                    if {r.get('channel_name') for r in labels if r.get('label')=='noise'}!=affected:raise ValueError('标签与候选不一致')
                    if len(labels)!=len(names) or {r.get('channel_name') for r in labels}!=set(names) or any(r.get('label') not in {'good','noise'} for r in labels):raise ValueError('SpikeInterface 存在未评通道')
                bad,total=len(affected),len(names)
                reason='涉及候选的通道数 / 受检通道数；整份按分析块时长加权，不代表实际污染时长。'
                if kind=='pairs':reason='桥接对涉及的通道去重计数；不按通道对数量重复扣分。'
                if identifier in {'mne_amplitude','mne_lof'} and set(payload.get('bad_channels',[]))!=affected:raise ValueError('候选与原方法坏道输出不一致')
                if identifier=='mne_amplitude' and 'bad_channels' not in payload:raise ValueError('缺少原方法坏道输出')
                if identifier=='mne_lof' and ({r.get('channel_name') for r in payload['channel_scores']}!=set(names) or not all(number(r.get('negative_outlier_factor')) for r in payload['channel_scores'])):raise ValueError('LOF 测量无效')
                if identifier=='gnosis_line_length' and not all(number(v) for v in payload['metrics']['line_length_by_channel'].values()):raise ValueError('线长测量非有限')
                if identifier=='gnosis_psd_deviation':
                    rows=[r for r in payload.get('metrics',{}).get('psd_distance',[]) if r.get('band')=='full']
                    effective=scope.get('effective_duration_seconds')
                    if len(rows)!=len(names) or {r.get('channel_name') for r in rows}!=set(names) or not all(number(r.get('value')) for r in rows) or not number(effective) or not 0<effective<=duration+1e-5:raise ValueError('PSD 全频带测量及有效范围不完整')
                    reason+=' 仅评价所保留的频谱输入片段。'
                if identifier=='faster_channels':
                    by=payload.get('by_metric',{})
                    if not by or any(not isinstance(v,list) or not set(v)<=set(names) for v in by.values()) or set().union(*map(set,by.values()))!=affected:raise ValueError('FASTER 分项与候选不一致')
                if identifier=='mne_bridge':
                    rows=payload.get('electrical_distance_uv2',[]);n=payload.get('segmentation',{}).get('n_epochs',0)
                    pairs={tuple(sorted(r.get('channel_names',[]))) for r in rows}
                    if n<1 or len(rows)!=len(names)*(len(names)-1)//2 or len(pairs)!=len(rows) or any(len(r.get('values_by_epoch',[]))!=n or not all(number(v) for v in r['values_by_epoch']) for r in rows):raise ValueError('电气距离证据不完整')
            elif kind=='ratios':
                ratios=payload.get('metrics',{}).get('ratio_by_channel',{})
                if set(ratios)!=set(names) or any(not number(v) or not 0<=v<=1 for v in ratios.values()):raise ValueError('逐道时间占比缺失或无效')
                measured=payload.get('metrics',{}).get('assessed_duration_seconds',duration)
                if not number(measured) or measured<=0 or measured>duration+1e-6:raise ValueError('实际分析时长无效')
                # Ratios in existing Gnosis evidence use original source duration.
                by={n:[] for n in names}
                for c in candidates:
                    name=c.get('channel_name')
                    if name not in by:raise ValueError('候选身份无效')
                    by[name].append((c.get('start_seconds'),c.get('stop_seconds')))
                amounts={n:sum(b-a for a,b in _ranges(v,start,start+measured)) for n,v in by.items()}
                if any(not math.isclose(amounts[n],ratios[n]*duration,abs_tol=1e-5) for n in names):raise ValueError('时间占比与候选区间不一致')
                bad,total=sum(amounts.values()),len(names)*measured
                reason='逐通道合并重叠区间后累加；分母为全部受检通道的实际分析时长。'
            elif kind=='epochs':
                seg=payload.get('segmentation',{});ranges=seg.get('ranges',[]);n=seg.get('n_epochs')
                indices={c.get('epoch_index') for c in candidates}
                if type(n) is not int or n<=0 or len(ranges)!=n or any(type(i) is not int or not 0<=i<n for i in indices):raise ValueError('有效片段及候选索引不完整')
                if len(payload.get('epoch_max_ptp_volts',[]))!=n:raise ValueError('缺少逐段测量')
                bad,total=len(indices),n;reason='超阈值固定片段 / 实际评估片段；未使用尾段不计入分母。'
            elif kind in {'intervals','finite_samples'}:
                if identifier=='mne_amplitude' and not isinstance(payload.get('bad_channels'),list):raise ValueError('缺少幅度检查原始结果')
                spans=_ranges([(c.get('start_seconds'),c.get('stop_seconds')) for c in candidates if c.get('localization')!='channel_only'],start,stop)
                if kind=='finite_samples':
                    z=payload.get('scores_z');n=scope.get('n_samples');fs=scope.get('sampling_rate_hz')
                    if not isinstance(z,list) or len(z)!=n or not number(fs) or fs<=0:raise ValueError('高频分数的有效样本证据缺失')
                    # Count intersected valid samples, not invalid filter edges.
                    valid=[number(v) for v in z];covered=set()
                    for a,b in spans:covered.update(range(max(0,round((a-start)*fs)),min(n,round((b-start)*fs))))
                    bad,total=sum(valid[i] for i in covered),sum(valid)
                    reason='候选与有限分数样本的交集 / 有限分数样本；无效边缘不计为通过。'
                else:
                    if identifier=='fieldtrip_zvalue' and (len(payload.get('zvalue',[]))!=scope.get('n_samples') or not all(number(v) for v in payload.get('zvalue',[]))):raise ValueError('FieldTrip 分数证据不完整')
                    bad,total=sum(b-a for a,b in spans),duration
                    reason='全局候选区间去重时长 / 受检时长；不推断单道位置。'
            else:raise ValueError('该方法尚无可计算的评分适配器')
            score=observation(spec,bad,total,reason=reason,scope=scope,artifact=artifact)
            score['parameters']=copy.deepcopy(payload.get('parameters',{}))
            result.append(score)
        except (ValueError,TypeError,KeyError,OverflowError) as error:
            result.append(observation(spec,reason=str(error),scope=scope,artifact=artifact))
    return result


def core_outputs(per_channel,expected_channels,**kwargs):
    from .scoring import burden_score
    base=burden_score(per_channel,expected_channels,**kwargs)
    return [observation(SPECS[p['id']],p['denominator']-p['numerator'] if p['value'] is not None else None,
                        p['denominator'] if p['value'] is not None else None,
                        reason='按原检测候选量与有效检查量计算；所有选中通道须有有效证据。') for p in base['components']]


def prep_output(payload,expected_channels,scope=None,artifact='M05_bad_channels.json'):
    spec=SPECS['prep_nonspatial'];groups=payload.get('groups',[]);rows=payload.get('channels',[])
    valid=bool(groups) and all(g.get('thresholds_active') for g in groups) and len(rows)==expected_channels
    ids=[r.get('channel_id') for r in rows]
    valid=valid and all(isinstance(i,str) for i in ids) and len(set(ids))==len(ids)
    return observation(spec,sum(bool(r.get('flags')) for r in rows) if valid else None,
        expected_channels if valid else None,scope=scope,artifact=artifact,
        reason='PREP 任一非空间分项命中的通道去重计数。' if valid else '比较组阈值未全部启用或通道证据不完整。')


def aggregate(rows,config,*,coverage_complete=True):
    from .project_scoring import FORMULA, VERSION
    import hashlib,json
    weights=config['weights']
    if set(weights)-set(SPECS) or any(not number(w) or not 0<=w<=100 for w in weights.values()):raise ValueError('无效评分权重')
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('同一计分输出不能重复纳入')
    index={r['id']:r for r in rows};parts=[]
    for key in dict.fromkeys([*index,*weights]):
        spec=SPECS[key];row=copy.deepcopy(index.get(key) or observation(spec,reason='所选计分方法没有有效输出。'))
        if row.get('value') is not None and (row.get('status')!='computed' or not number(row.get('candidate_amount')) or not number(row.get('assessed_amount')) or not 0<=row['candidate_amount']<=row['assessed_amount'] or row['assessed_amount']<=0 or not math.isclose(row['value'],100*(1-row['candidate_amount']/row['assessed_amount']),abs_tol=1e-9)):
            row=observation(spec,reason='计分值与原始分子分母不一致。')
        weight=weights.get(key,0)
        if weight==0 and key not in index:continue
        excluded = config['version']==VERSION and weight>0 and row.get('value') is None
        row.update(weight=0 if excluded else weight, configured_weight=weight, automatically_excluded=excluded)
        row['candidate_fraction']=row['candidate_amount']/row['assessed_amount'] if row['value'] is not None else None
        parts.append(row)
    total_weight=sum(p['weight'] for p in parts)
    for p in parts:p['normalized_weight']=p['weight']/total_weight if total_weight else 0
    active=[p for p in parts if p['weight']>0]
    missing=[p['id'] for p in parts if p['configured_weight']>0 and p['value'] is None]
    excluded=[p['id'] for p in parts if p['automatically_excluded']]
    blocking=[p['id'] for p in active if p['value'] is None]
    value=sum(p['value']*p['weight'] for p in active)/total_weight if active and not blocking and coverage_complete else None
    h=index.get('hf_burst',{})
    return dict(version=config['version'],name='项目自定义评分',value=value,status='project_trial' if active else 'unavailable' if any(weights.values()) else 'disabled',components=parts,
        weights=copy.deepcopy(weights),configuration_id=hashlib.sha256(json.dumps(config,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16],
        effective_weights={p['id']:p['weight'] for p in parts},excluded_components=excluded,
        formula=FORMULA,aggregation='method_fraction_then_weighted_mean',coverage_complete=coverage_complete,
        missing_components=missing,missing_reason='未选择计分项' if not any(weights.values()) else '检查范围未完整覆盖' if not coverage_complete else
            '所有计分项均无有效结果' if not active else ('缺少有效计分证据：'+'、'.join(SPECS[k]['name'] for k in blocking)) if blocking else '',
        calibration='not_expert_calibrated',scope='selected_checks_only',
        hf_valid_channel_seconds=h.get('denominator',0),hf_candidate_channel_seconds=h.get('candidate_amount') or 0)


def pool_windows(windows):
    """Pool actual denominators; channel votes are duration-weighted per block."""
    keys=list(dict.fromkeys(r['id'] for w in windows for r in w.get('method_scores',[])))
    result=[]
    for key in keys:
        spec=SPECS[key];pieces=[next((r for r in w.get('method_scores',[]) if r['id']==key),None) for w in windows]
        valid=bool(windows) and all(r and r['status']=='computed' and r['value'] is not None and number(r.get('candidate_amount')) and number(r.get('assessed_amount')) and 0<=r['candidate_amount']<=r['assessed_amount'] and r['assessed_amount']>0 and number(w.get('duration_seconds')) and w['duration_seconds']>0 and w.get('status','completed') in {'completed','partial'} for w,r in zip(windows,pieces))
        bad=total=0
        if valid:
            for w,r in zip(windows,pieces):
                factor=r.get('scope',{}).get('effective_duration_seconds',w['duration_seconds']) if spec['unit']=='channels' else 1
                bad+=r['candidate_amount']*factor;total+=r['assessed_amount']*factor
        row=observation(spec,bad if valid else None,total if valid else None,
            reason='按全部分析块的实际分子分母汇总。' if valid else '部分分析块无有效计分证据；未用零或满分填补。')
        row['source_artifacts']=[w['id']+'--'+a for w,r in zip(windows,pieces) if r for a in r.get('source_artifacts',[])]
        row['window_count']=len(windows);row['assessed_windows']=sum(bool(r and r['status']=='computed') for r in pieces)
        if spec['unit']=='channels':row.update(unit='channel_block_seconds',reason='各分析块的候选通道比例按时长加权；不代表精确异常时长。' if valid else row['reason'])
        result.append(row)
    return result


def payload_outputs(name,payload,modality,recording):
    """Attach outputs at the algorithm boundary while payloads are in memory."""
    count=recording.get('channel_count',0)
    if modality=='scalp_eeg' and name in {'M03_continuity.json','M04_spectral.json','M06_muscle.json'}:
        from .report_aggregate import channel_evidence
        from .report_view import line_summary
        if name.startswith('M03'):
            key='integrity';evidence=channel_evidence(payload,{},[])
        elif name.startswith('M04'):
            key='line_noise';evidence=channel_evidence({},line_summary(payload.get('line_noise',{})),[])
        else:
            key='hf_burst';evidence=channel_evidence({},{},payload.get('channels',[]) if payload.get('status') in {'ok','partial_channels'} else [])
        out=[r for r in core_outputs(evidence,count) if r['id']==key]
        for r in out:r.update(source_artifacts=[name],scope=copy.deepcopy(recording))
        return out
    if modality=='scalp_eeg' and name=='M05_bad_channels.json':
        return [prep_output(payload,count,recording,name)]
    identifier=name[4:-5] if name.endswith('.json') and name.startswith(('M03_','M04_','M05_','M06_')) else ''
    return extension_outputs(identifier,payload,modality,name)


def finalize(result,rows,*,coverage_complete=True):
    selected=result['selected_modules'];extensions=result['qc_config'].get('method_config',{}).get('extensions',[])
    modality=result.get('input_modality') or result.get('qc_config',{}).get('modality')
    # Runtime stores input_modality as a string; the profile fallback supports SDK fixtures.
    if isinstance(modality,dict):modality=modality.get('value')
    if not isinstance(modality,str):modality='scalp_eeg' if result.get('analysis_profile')=='scalp-eeg/1' else None
    index={r['id']:r for r in rows}
    module_status={m['id']:m.get('status') for m in result.get('modules',[])}
    for key,row in list(index.items()):
        if module_status.get(row['module_id']) in {'failed','skipped','cancelled','interrupted'}:
            index[key]=observation(SPECS[key],reason='所属模块未完成，已保存证据需复核。')
    result['method_scores']=[index.get(s['id']) or observation(s,reason='方法未完成或没有完整计分证据。')
        for s in outputs(modality) if enabled(s,selected,extensions)]
    config=result.get('qc_config',{}).get('scoring')
    if config and config['version'] in {'project-weighted/1.1','project-weighted/1.2'}:
        result['project_score']=aggregate(result['method_scores'],config,coverage_complete=coverage_complete)
    for module in result.get('modules',[]):
        module['score_outputs']=[copy.deepcopy(r) for r in result['method_scores'] if r['module_id']==module['id']]


def report_section(score):
    from html import escape
    from .report_export import score_composition
    point=lambda v:'—' if v is None else f'{v:.2f}'
    total=sum(p.get('weight',0) for p in score['components'] if p.get('weight',0)>0)
    rows=''.join(f'<tr><th>{escape(p["name"])}</th><td>{point(p["value"])}</td><td>{escape(p["reason"])}</td></tr>' for p in score['components'])
    shares=''.join(f'<li>{escape(p["name"])}：{100*p["weight"]/total:.1f}%</li>' for p in score['components'] if p.get('weight',0)>0)
    policy=('受限项本次权重为 0，其余有效项重新归一化。' if score['version']=='project-weighted/1.2' else '缺项不补分、不重新分配比例。')
    composition=f'<details><summary>总分组成</summary><p>{escape(score_composition(score))}</p><ul>{shares}</ul><p>未列入的项目仅展示结果；{policy}</p></details>'
    return f'<section class="project-score" style="max-width:1100px;margin:24px auto;padding:24px;background:white"><h2>项目自定义评分 · {point(score["value"])}</h2><p>{escape(score.get("missing_reason") or score_composition(score))}</p><table><thead><tr><th>检查项目</th><th>分项得分 / 100</th><th>检查说明</th></tr></thead><tbody>{rows}</tbody></table>{composition}<p>{escape(score["version"])} · {escape(score["configuration_id"])}</p></section>'
