"""Presentation of the implemented scoring contracts, by modality (not a scoring engine)."""
from .method_registry import methods
from . import project_scoring, ieeg_scoring, neuropixels_scoring
from .score_registry import SPECS
from .ieeg_baseline import configure as ieeg_recipe
from .neuropixels_standard import AP_METHOD
IEEG_DEFAULTS=ieeg_recipe({'method_config':{}},{'modality':'ecog','metadata':{'format':'EDF'}})['method_config']['extensions']

def percent(weights, key):
    total=sum(weights.values())
    return f"{100*weights.get(key,0)/total:.1f}".removesuffix(".0")+"%" if total else "0%"

EEG_WEIGHTS=project_scoring.normalize(None,"scalp_eeg",["M03","M04","M06"])["weights"]
IEEG_WEIGHTS=ieeg_scoring.default_config("ecog")["weights"]
NP_WEIGHTS=neuropixels_scoring.default_config()["weights"]
EI=percent(IEEG_WEIGHTS,ieeg_scoring.NUMERIC)
ES=percent(IEEG_WEIGHTS,ieeg_scoring.STABILITY)
NI=percent(NP_WEIGHTS,neuropixels_scoring.NUMERIC)
NS=percent(NP_WEIGHTS,neuropixels_scoring.STATE)

MODES = {'scalp_eeg':'eeg','ecog':'ecog','seeg':'seeg','extracellular':'np'}
LIMITED = '缺少有效证据的分项本次权重为0，其余有效权重按比例归一化；保留未评原因。有效得分为0仍参与计分。全部无效、权重全0或整份范围未覆盖时不给综合分。'

def entry(scope, role='measurement', outputs=None, weight='不分配总分权重', rule='保留测量、状态或流程输出，不独立扣分。', version='method-score/1', limited=LIMITED):
    return dict(scope=scope,role=role,canOutputScore=role in ('default','optional'),outputs=outputs or [],weight=weight,rule=rule,limited=limited,version=version)

def method_entry(m, scope):
    scores=m.get('scoring',{}).get('outputs',[])
    if m['implementation']=='planned':
        return entry(scope,'unavailable',rule='当前没有执行及评分输出；不能以计划功能参与计分。',version='尚未接入')
    if not scores:
        return entry(scope,rule=m.get('scoring',{}).get('reason','只提供检查结果或执行支持。'))
    key=m['id']; names=[s['name']+' · '+s['id'] for s in scores]
    if scope=='eeg':
        default=any(EEG_WEIGHTS.get(s['id'],0)>0 for s in scores)
        return entry(scope,'default' if default else 'optional',names,
            ' / '.join(s['name']+' '+percent(EEG_WEIGHTS,s['id']) for s in scores)+'；可调整' if default else '默认0%；启用方法并设为正权重后参与',
            '100 ×（1 − 本方法候选量 / 有效受检量）。分母按方法分别为采样点、通道、时长或窗口。跨方法候选可能重叠；可选方法不应不加区分地全部叠加。',
            version=project_scoring.VERSION)
    if scope in ('ecog','seeg'):
        weights=ieeg_scoring.default_config(scope)['weights']
        EI=percent(weights,ieeg_scoring.NUMERIC);ES=percent(weights,ieeg_scoring.STABILITY)
        if key in ('ecog_continuity','seeg_continuity'):
            return entry(scope,'default',names,f'数值有效性{EI}；可调整','仅NaN/Inf占比：100 ×（1 − 无效数值 / 受检采样点）。恒值问题另归入稳定性。',version=ieeg_scoring.VERSION)
        default=key in IEEG_DEFAULTS and weights.get(ieeg_scoring.STABILITY,0)>0
        return entry(scope,'default' if default else 'optional',names,
            f'并入信号稳定性{ES}；原始项不再单独加权',
            ('文件量程端点平台仅在EDF/BDF有有效标定时默认启用。' if key=='ieeg_range_plateau' else '')+
            '稳定性取有效相关方法的整份分数最低值，只计一次；不声称逐样本异常并集。选择可选证据会改变稳定性的依据。',version=ieeg_scoring.VERSION,
            limited='无效原始证据排除；有其他有效依据时继续计算稳定性。全部依据无效时稳定性权重为0。'+LIMITED)
    if key=='neuropixels_continuity':
        return entry(scope,'default',names,f'数值有效性{NI}；整窗恒值并入通道状态{NS}',rule='NaN/Inf按采样点计分。整窗恒值按来源通道身份进入通道状态；短暂量化重复只测量。恒值不另分总分权重。',version=neuropixels_scoring.VERSION)
    if key==AP_METHOD:
        return entry(scope,'default',names,f'AP条件满足时并入通道状态{NS}；原始项权重0',rule='AP已确认且分组、时长及频带满足条件时默认使用原版MAD/std离群；不用于LF/LFP。与整窗恒值按同一来源通道、同一分析窗取并集，不重复计数。',version=neuropixels_scoring.VERSION,limited='任一分析窗受限时，该方法不进入整份并集；已检出候选仍保留。恒值完整有效时可独立支撑通道状态。'+LIMITED)
    return entry(scope,'default',names,f'通道状态{NS}；可调整',rule='汇总整窗恒值与适用的AP离群，逐窗按来源通道取并集，再按通道窗时长加权。LF仅使用恒值；AP与LF不混排。合并项和原始项不能重复加权。',version=neuropixels_scoring.VERSION)

def attach_scoring(catalog, roots, node, base):
    contracts={}
    for mode,scope in MODES.items():
        for method in methods(mode):
            contracts.setdefault('f_'+method['id'],[]).append(method_entry(method,scope))
    def visit(n):
        n['scoring']=contracts.get(n['id']) or [entry(s,'unavailable' if n['status']=='planned' else 'measurement',rule='尚未接入执行，不能计分。' if n['status']=='planned' else '本项提供测量、资料检查、流程支持或图表；不作为独立信号质量分项。') for s in n['scope']]
        for contract in n['scoring']:
            mode=next((m for m,s in MODES.items() if s==contract['scope']),None)
            specs=[s for s in SPECS.values() if s['id'] in [o.split(' · ')[-1] for o in contract['outputs']]]
            if specs: contract['rule'] += '\n接口公式：'+'；'.join(dict.fromkeys(s['formula'] for s in specs))
        for child in n.get('children',[]): visit(child)
    for group in catalog.values():
        for n in group: visit(n)
    for n in roots: visit(n)
    # Aggregation contracts are shown next to the per-method badges, in the existing M08 layer.
    rules=[
        ('score_eeg','EEG · 默认三项',['eeg'],' / '.join(SPECS[k]['name']+' '+percent(EEG_WEIGHTS,k) for k in EEG_WEIGHTS),
         '按默认方案的有效权重加权平均；权重可以调整。PREP、MNE、FASTER、FieldTrip及灵犀云中已具备分数接口的方法可以另选，不默认全部加入。',
         '可选方法可能重复标记同一问题。本版未做所有EEG方法之间的统一去重；同类方法优先作为替代方案比较。工频已声明被滤除时未评，不能补100分。','docs/eeg-scoring.md'),
        ('score_ieeg','ECoG / sEEG · 默认两项',['ecog','seeg'],f'数值有效性{EI} + 信号稳定性{ES}',
         '稳定性使用MNE平线，文件有标定时加入端点平台；分组触点离群、FieldTrip跳变可选。先汇总每个方法的整份分数，再取最低有效分作为稳定性。',
         '同类证据仅计一次；原始项不再独立加权。取最低分是保守合并规则，不是异常并集，可能低估多个独立问题的合计负担。','docs/ieeg-scoring.md'),
        ('score_np','Neuropixels · 默认两项',['np'],f'数值有效性{NI} + 通道状态{NS}',
         '数值有效性检查NaN/Inf。通道状态按整窗恒值和条件适用的AP离群取并集；按通道窗时长汇总。LF/LFP只使用恒值依据。',
         '同一来源通道在同一窗口只计一次。任一窗受限的原始方法不进入整份并集，候选仍保留。原始恒值/AP与合并项不能重复分权重。','docs/neuropixels-scoring.md'),
        ('score_weight','权重与受限项',list(MODES.values()),'综合分 = Σ（有效分项分数 × 权重）/ Σ有效权重',
         project_scoring.FORMULA+'权重可配置，0表示主动不计入。分项缺少有效证据时本次有效权重自动置0，其余有效项重新归一化。模块部分受限不代表所有输出都无效，按每个计分输出判断。',
         LIMITED+'只有在检查范围、方法、处理史、有效项目及权重相同时，分数才适合比较。100分表示本次有效检查未检出候选。','docs/eeg-scoring.md')]
    for key,title,scope,summary,desc,notes,path in rules:
        n=node(key,title,scope,kind='report',status='trial',entry='support',summary=summary,description=desc,inputs='各方法保存的有效计分证据与本次权重',outputs='分项、综合分、有效权重、未评原因及版本',conditions='整份执行范围及来源核验有效；仅对本次已完成检查解释分数。',methods='项目计分汇总；不重新执行检测算法。',notes=notes+' 现为项目试行方案，尚未通过专家审核。',evidence=base+'apps/flow-editor/content/scoring-rules/'+path.rsplit('/',1)[-1])
        visit(n)
        for s in n['scoring']:
            s.update(weight=summary,rule=desc,limited=notes,version=project_scoring.VERSION+' / '+ieeg_scoring.VERSION+' / '+neuropixels_scoring.VERSION)
        catalog.setdefault('M08',[]).append(n)
