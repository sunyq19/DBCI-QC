"""M06: Auxiliary events and muscle evidence with continuity guards."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    if "core_methods" in methods:
        return _run_selected(context)
    from brainelecqc.eeg.events import compute_event_qc
    from brainelecqc.eeg.muscle import compute_muscle_qc
    aux = {"references": state["references"], "reference_channels": state["reference_channels"]}
    events = compute_event_qc(*_args(state), **_origin(state), **aux, config=methods.get("events"))
    save("M06_auxiliary_events.json", events)
    from ..processing_history import scope
    assessment = scope(context.record, context.config, state['fs'])
    if assessment['hf_limited_by_history']:
        payload = {'status': 'not_assessed_preprocessing', 'channels': [], 'windows': [], 'candidates': [],
                   'reference': {'status': 'not_assessed'}, 'processing_scope': assessment,
                   'reason': '已声明滤波范围未保留当前高频检查频带；不计为满分。'}
    else:
        payload = compute_muscle_qc(*_args(state), **_origin(state), **aux, config=methods.get("muscle"),
                                    excluded_intervals=state["continuity_candidates"])
        payload['processing_scope'] = assessment
    save("M06_muscle.json", payload)
    row["summary"] = {"events": {k: {"status": b["status"], "event_count": b["detected_event_count"]} for k, b in events["by_kind"].items()},
                      "muscle_status": payload["status"], "emg_reference_status": payload["reference"]["status"],
                      "high_frequency_candidate_count": len(payload["candidates"]),
                      "emg_supported_count": sum(c["kind"] == "emg_supported_burst" for c in payload["candidates"]),
                      "continuity_guard_applied": True}
    if any(b["status"] not in {"computed", "no_events"} for b in events["by_kind"].values()) or payload["reference"]["status"] != "ok" or payload["status"] != "ok":
        row.update(status="partial", reason="部分生理伪迹缺少可用辅助证据；一般高频突发不等于已确认肌电")
    del events

    return row


def _run_selected(context):
    """Run selected event/HF methods; guards are dependencies, not scored checks."""
    from ..method_selection import selected
    from brainelecqc.eeg.events import compute_event_qc
    from brainelecqc.eeg.muscle import compute_muscle_qc
    from ..processing_history import scope
    state, config, row = context.state, context.config, context.row
    methods = config['method_config']
    aux = {"references": state["references"], "reference_channels": state["reference_channels"]}
    chosen_kinds = [kind for kind in ('ecg','eog') if selected(config, kind + '_locked')]
    limited = False
    if chosen_kinds:
        event_aux = {key: {kind: value for kind,value in values.items() if kind in chosen_kinds}
                     for key,values in aux.items()}
        events = compute_event_qc(*_args(state), **_origin(state), **event_aux, config=methods.get('events'))
        events['by_kind'] = {key:value for key,value in events['by_kind'].items() if key in chosen_kinds}
        context.save('M06_auxiliary_events.json', events)
        row['summary']['events'] = {k: {'status': b['status'], 'event_count': b['detected_event_count']} for k,b in events['by_kind'].items()}
        limited |= any(b['status'] not in {'computed','no_events'} for b in events['by_kind'].values())
    if selected(config, 'hf_burst'):
        assessment = scope(context.record, config, state['fs'])
        if assessment['hf_limited_by_history']:
            payload = {'status':'not_assessed_preprocessing','channels':[],'windows':[],'candidates':[],
                       'reference':{'status':'not_assessed'},'processing_scope':assessment}
        else:
            if 'continuity_candidates' not in state:
                from brainelecqc.eeg.continuity import compute_continuity_qc
                guard = compute_continuity_qc(*_args(state), **_origin(state), channels=state['channels'], config=methods.get('continuity'))
                state['continuity_candidates'] = guard['candidates']
                row['summary']['internal_dependencies'] = ['continuity_guard']
            payload = compute_muscle_qc(*_args(state), **_origin(state), **aux, config=methods.get('muscle'),
                                        excluded_intervals=state['continuity_candidates'])
            payload['processing_scope'] = assessment
        context.save('M06_muscle.json', payload)
        row['summary'].update(muscle_status=payload['status'], high_frequency_candidate_count=len(payload['candidates']),
                              emg_reference_status=payload['reference']['status'],
                              continuity_guard_applied=not assessment['hf_limited_by_history'])
        # EMG supports attribution; its absence does not invalidate EEG-only
        # high-frequency detection. The source payload retains that limitation.
        limited |= payload['status'] != 'ok'
    if limited:
        row.update(status='partial', reason='已选方法存在未评条件；详见相应检查结果。')
    return row
