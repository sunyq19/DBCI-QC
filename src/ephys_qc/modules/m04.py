"""M04: Spectral measurements and explicit unassessed conditions."""
from .context import backend_args as _args, source_origin as _origin

from .context import ModuleContext


def run(context: ModuleContext) -> dict:
    """Execute this module; return its result row and save its named evidence."""
    row = context.row
    state = context.state
    methods = context.config["method_config"]
    save = context.save
    from brainelecqc.eeg.spectral import compute_spectral_qc
    from ..method_selection import selected
    if 'core_methods' in methods and not selected(context.config, 'spectral_model'):
        payload = _selected_spectrum(context)
    else:
        payload = compute_spectral_qc(*_args(state), **_origin(state), config=methods.get("spectral"))
    from ..processing_history import scope, restrict_line_evidence
    restrict_line_evidence(payload, scope(context.record, context.config, state['fs']))
    from ..method_selection import selected
    if not selected(context.config, 'thomson_line'):
        payload['line_noise'] = {'status': 'not_selected', 'observations': [], 'reason': '本次未选择工频检查。'}
    if not selected(context.config, 'spectral_model'):
        payload['parameterization'] = {'status': 'not_selected', 'full': [], 'windows': []}
        payload.pop('alpha_power', None)
    if not selected(context.config, 'welch_psd'):
        # The upstream spectral routines share PSD internally. Do not expose
        # the unselected standalone measurement as a selected report result.
        payload['psd'] = {'status': 'not_selected', 'frequencies_hz': [], 'power_v2_hz': [], 'channel_ids': []}
    payload['selected_methods'] = [m for m in ('welch_psd','thomson_line','spectral_model') if selected(context.config, m)]
    save("M04_spectral.json", payload)
    line = payload["line_noise"]
    row["summary"] = {"line_status": line["status"], "line_observation_count": len(line["observations"]),
                      "line_flagged_observations": sum(r["flagged"] for r in line["observations"]),
                      "full_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["full"]}),
                      "window_spectral_fit_statuses": sorted({r["status"] for r in payload["parameterization"]["windows"]}),
                      "drift_assessment": "not_implemented"}
    if line["status"] not in {"computed", "not_selected"} or any(r["status"] != "computed" for scope in ("full", "windows") for r in payload["parameterization"][scope]):
        row.update(status="partial", reason="部分工频/频谱指标未能评估，详见方法结果")

    return row


def _selected_spectrum(context):
    """Use the original spectral primitives without running unselected FOOOF."""
    from brainelecqc.eeg import spectral as upstream
    from ..method_selection import selected
    from dataclasses import asdict
    import numpy as np
    state=context.state
    data,fs,ids,names,cfg=upstream._validate(*_args(state), state['first'], state['start'], context.config['method_config'].get('spectral'))
    origin=upstream._location(0,data.shape[1],fs,state['first'],state['start'])
    payload={'schema_version':upstream.SPECTRAL_VERSION, 'config':asdict(cfg),
             'input':{**origin,'sfreq':fs,'n_samples':data.shape[1],'channel_ids':ids,'channel_names':names,'unit':'V'},
             'parameterization':{'status':'not_selected','full':[],'windows':[]},
             'psd':{'status':'not_selected','frequencies_hz':[],'power_v2_hz':[],'channel_ids':[]},
             'line_noise':{'status':'not_selected','observations':[]}}
    if selected(context.config,'welch_psd'):
        f,p,estimator=upstream._welch(data,fs,cfg)
        payload['psd']={'frequencies_hz':f.tolist(),'power_v2_hz':p.tolist(),'channel_ids':ids,**origin,'estimator':estimator}
    if selected(context.config,'thomson_line'):
        line=upstream._line_analysis(data,fs,ids,names,cfg,state['first'],state['start'])
        line['strongest_window_psd']=None
        measured=[r for r in line['observations'] if r['status']=='computed']
        if measured:
            r=max(measured,key=lambda r:np.inf if r['f_is_infinite'] else r['f_statistic'])
            left,right,ci=r['start_offset'],r['stop_offset'],r['channel_index']
            f,p,estimator=upstream._welch(data[ci:ci+1,left:right],fs,cfg)
            line['strongest_window_psd']={**upstream._channel(ci,ids,names),**upstream._location(left,right,fs,state['first'],state['start']),
                'nominal_hz':r['nominal_hz'],'selection_rule':'maximum F across computed observations',
                'frequencies_hz':f.tolist(),'power_v2_hz':p[0].tolist(),'estimator':estimator}
        payload['line_noise']=line
    return payload
