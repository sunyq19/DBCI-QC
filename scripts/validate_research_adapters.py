"""Exercise explicitly selected research adapters on registered public samples.

Engineering evidence only. The ASR calibration selection below is for testing
execution, not a clean-data annotation or clinical validation.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
import urllib.request


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--url',default='http://127.0.0.1:8769')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--input-id',action='append')
    parser.add_argument('--asr-engineering-calibration',action='store_true',
                        help='Explicitly run an exploratory ASR calibration; not a clean-data assertion')
    args=parser.parse_args()
    if args.output.exists():raise SystemExit('Keep old evidence; choose a new output')
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def call(path,body=None):
        req=urllib.request.Request(args.url+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
        with opener.open(req,timeout=45) as response:return json.load(response)
    catalog=call('/api/v1/catalog')
    inputs={r['id']:r for r in catalog['inputs']}
    for modality in ('ecog','seeg','extracellular'):
        inputs.update({r['id']:r for r in call('/api/v1/catalog?modality='+modality)['inputs']})
    cases=[('ds002034-sub01',16,40,['faster_channels','cleanline','zapline_plus','fieldtrip_zvalue']),
           ('mne-ecog-pt1-brainvision',16,20,['fieldtrip_zvalue']),
           ('mne-seeg-misc-fif',16,20,['fieldtrip_zvalue']),
           ('paulk-human-pt03-ap-60s-2s',64,2,['spikeinterface_bad_channels'])]
    if args.asr_engineering_calibration:cases[0][3].append('asr_bursts')
    evidence={'schema_version':'research-adapter-acceptance/1','workbench_version':catalog.get('version'),
              'claim':'engineering execution only; no accuracy, calibrated thresholds or MATLAB equivalence',
              'asr_calibration':'explicit exploratory source-window selection, not clean ground truth', 'cases':[]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for identifier,count,seconds,extras in cases:
        if args.input_id and identifier not in args.input_id:continue
        record=inputs[identifier];config=deepcopy(record['default_config'])
        config['scope']='window';selection=config['selection'];selection['eeg_indices']=list(reversed(selection['eeg_indices'][:count]));selection['duration_seconds']=seconds
        config['method_config']['comparison_groups']=[record['reference_scheme']]*count if record['modality']=='scalp_eeg' else None
        config['method_config']['extensions']=extras
        config['method_config']['extension_parameters']={'asr_bursts':{'calibration_confirmed':True}} if 'asr_bursts' in extras else {}
        body={'input_id':identifier,'qc_config':config,'selected_modules':['M03','M04','M05','M06']}
        plan=call('/api/v1/plan',body)
        gates={r['id']:r for r in plan['method_applicability']}
        assert all(gates[mid]['status'] in {'ready','partial'} for mid in extras),gates
        body['plan_id']=plan['plan_id'];job=call('/api/v1/jobs',body)
        print('RUN',identifier,job['id'],flush=True)
        deadline=time.monotonic()+600
        while job['status'] in {'queued','running'} and time.monotonic()<deadline:
            time.sleep(1);job=call('/api/v1/jobs/'+job['id'])
        assert job['status']=='completed',job
        result=call('/api/v1/jobs/'+job['id']+'/result')
        artifacts={a['name']:a for a in result['artifacts']}
        row={'input_id':identifier,'job_id':job['id'],'report_url':args.url+'/api/v1/jobs/'+job['id']+'/report',
             'status':result['status'],'source_sha256':result['source_sha256'],'plan_id':result['plan_id'],
             'selection':config['selection'],'extensions':[]}
        for entry in result['extensions']:
            detail=call(artifacts[entry['artifact']]['url'])
            row['extensions'].append({'id':entry['id'],'status':entry['status'],'calculated':detail.get('calculated',False),
                    'reason':entry['reason'],'candidate_count':entry.get('candidate_count'),
                    'source':detail.get('source'),'evidence_url':artifacts[entry['artifact']]['url']})
            assert detail.get('input_unchanged') is True and detail.get('automatic_actions')==[],detail
            assert [c['source_index'] for c in detail['channel_mapping']]==selection['eeg_indices']
        evidence['cases'].append(row);args.output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
        print('RESULT',identifier,[(e['id'],e['status'],e['calculated']) for e in row['extensions']],flush=True)
        assert all(e['calculated'] and e['status'] in {'completed','partial'} for e in row['extensions']),row
        assert result['score']['value'] is None
    print('Saved',args.output,flush=True)

if __name__=='__main__':main()
