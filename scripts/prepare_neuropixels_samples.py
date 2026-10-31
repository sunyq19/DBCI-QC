#!/usr/bin/env python3
"""Prepare versioned public local-only SpikeGLX examples and provenance.

Run with the scientific Python: python scripts/prepare_neuropixels_samples.py
    --destination ../work/neuromodal_extension_20261030/neuropixels
Never registers records in a live server or uploads/pushes source recordings.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys
from urllib.request import Request, urlopen
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from ephys_qc.readers import open_reader

GIN_COMMIT = '4304c8cdc0d345e8ca70ff7720c1087f911d1d5b'
GIN = f'https://gin.g-node.org/NeuralEnsemble/ephy_testing_data/raw/{GIN_COMMIT}/'
NOISE = 'spikeglx/Noise4Sam_g0/Noise4Sam_g0_imec0/Noise4Sam_g0_t0.imec0'
ACSF = 'spikeglx/multi_trigger_multi_gate/SpikeGLX/5-19-2022-CI1/5-19-2022-CI1_g0/5-19-2022-CI1_g0_t0.imec0.ap'
ZENODO = 'https://zenodo.org/records/5899237/files/'
FILES = [
    ('raw/Noise4Sam_g0_t0.imec0.lf.meta', GIN+NOISE+'.lf.meta', 'db7301341a9c1adb6712589984ea981206f50b764492d33684dc8fc364d7e0e1'),
    ('raw/Noise4Sam_g0_t0.imec0.lf.bin', GIN+NOISE+'.lf.bin', '9222e7ce44caa7ec2c3dd514459158f6e351ae0ad1d9c415e197b49adde550a5'),
    ('raw/Noise4Sam_g0_t0.imec0.ap.meta', GIN+NOISE+'.ap.meta', '6b710d4bd537a8e6f418ef5e47aa15e0cf2d9dfce40b949b22a0327af32ef075'),
    ('raw/Noise4Sam_g0_t0.imec0.ap.bin', GIN+NOISE+'.ap.bin', '330a02910ca7c73bbdb9f1157694a0f83fb098a2b94f26ff22002b71b24db519'),
    ('acsf-ap-raw/5-19-2022-CI1_g0_t0.imec0.ap.meta', GIN+ACSF+'.meta', '548cd95a32ebd2a31c2d7d32f04940c413fcfb7fae2ee5eca494acfb5eefcbf9'),
    ('acsf-ap-raw/5-19-2022-CI1_g0_t0.imec0.ap.bin', GIN+ACSF+'.bin', 'b45fc6acdb240ce74e09103033219047565bddebff2f44017010e7a17097ccc9'),
    ('human-ap-source/Pt03.imec0.ap.meta', ZENODO+'Pt03.imec0.ap.meta?download=1', '73ecf75bbc26e59290ceb03729817a638d64bc766abc7bf465998ad9d67bb95a'),
]


def digest(path, algorithm='sha256'):
    h=hashlib.new(algorithm)
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024), b''):h.update(block)
    return h.hexdigest()


def json_save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def fetch(path, url, expected):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        temporary=path.with_name(path.name+'.download')
        with urlopen(url, timeout=60) as source, temporary.open('wb') as out:shutil.copyfileobj(source,out)
        if digest(temporary)!=expected:raise ValueError(f'Download SHA256 mismatch: {path.name}')
        temporary.rename(path)
    if digest(path)!=expected:raise ValueError(f'Existing source SHA256 mismatch: {path.name}')


def prepare(root):
    root.mkdir(parents=True, exist_ok=True)
    for name,url,expected in FILES:fetch(root/name,url,expected)
    # Only the complete source LF passes its source-declared SHA1. The ACSF
    # fixture and shortened Noise AP remain unchanged negative fixtures.
    for relative in ['raw/Noise4Sam_g0_t0.imec0.lf.bin']:
        p=root/relative; m=dict(line.split('=',1) for line in p.with_suffix('.meta').read_text().splitlines())
        assert digest(p,'sha1').upper()==m['fileSHA1'].upper()
    ranged=root/'human-ap-source/Pt03.recording60-62s.range.bin'
    expected='859039ccf67275f8773bd9d9419f776558c348cb6f6b8eb20c860b40a0075c97'
    start,stop,total=1386000000,1432200000,13543042590
    url=ZENODO+'Pt03.imec0.ap.bin?download=1&slice=60-62'
    range_evidence=root/'human-ap-source/range-download.json'
    if not ranged.exists():
        request=Request(url,headers={'Range':f'bytes={start}-{stop-1}'})
        with urlopen(request,timeout=60) as response:
            if response.status!=206 or response.headers.get('Content-Range')!=f'bytes {start}-{stop-1}/{total}':
                raise ValueError('Remote server did not return the exact requested byte range.')
            data=response.read(stop-start+1)
            if len(data)!=stop-start or hashlib.sha256(data).hexdigest()!=expected:raise ValueError('Partial-source range hash/size mismatch.')
            ranged.write_bytes(data)
            json_save(range_evidence,{'url':url,'request_range':f'bytes={start}-{stop-1}',
                'response_status':response.status,'response_headers':{
                    k:v for k,v in response.headers.items() if k.lower() in {'content-range','content-length','etag','content-type'}},
                'sha256':expected,'size_bytes':len(data),'full_original_file_downloaded':False,
                'original_full_md5_verified':False})
    if digest(ranged)!=expected:raise ValueError('Existing partial source SHA256 mismatch.')
    evidence=json.loads(range_evidence.read_text())
    headers={k.lower():v for k,v in evidence['response_headers'].items()}
    assert evidence['response_status']==206 and headers['content-range']==f'bytes {start}-{stop-1}/{total}'
    original_meta=root/'human-ap-source/Pt03.imec0.ap.meta'
    assert digest(original_meta,'md5')=='b30865dbb1f087d7569ecc597dd6b8c3'
    # This is an explicitly derived segment. The original .meta is never edited.
    derived=root/'human-ap-derived';derived.mkdir(exist_ok=True)
    binary=derived/'Pt03_recording60-62s.imec0.ap.bin'
    if not binary.exists():shutil.copyfile(ranged,binary)
    assert digest(binary)==expected
    old=dict(line.split('=',1) for line in original_meta.read_text().splitlines())
    changed={'fileName':binary.name,'fileSizeBytes':str(stop-start),'fileTimeSecs':'2',
             'firstSample':str(int(old['firstSample'])+1800000),'fileSHA1':digest(binary,'sha1').upper()}
    values={**old,**changed,'dbciDerivedSource':'Zenodo5899237 Pt03 original recording interval [60,62) seconds',
            'dbciDerivedOperation':'byte_exact_contiguous_sample_range_no_filter_no_resample_no_rereference'}
    binary.with_suffix('.meta').write_text('\n'.join(f'{k}={v}' for k,v in values.items())+'\n')
    derivation={'source_url':url,'source_total_bytes':total,'source_whole_file_md5':'edccc662126063fca131bc982da1cbad',
        'source_whole_file_downloaded':False,'source_whole_file_md5_verified':False,
        'source_meta_sha256':digest(original_meta),'source_meta_md5_verified':True,
        'source_file_sample_start':1800000,'source_file_sample_stop_exclusive':1860000,
        'source_recording_seconds':[60,62],'byte_range_half_open':[start,stop],
        'sample_frame_bytes':770,'all_385_saved_channels_retained':True,'derived_sha256':expected,
        'metadata_changes':{k:{'source':old.get(k),'derived':v} for k,v in changed.items()},
        'metadata_added':{k:v for k,v in values.items() if k.startswith('dbciDerived')},
        'raw_signal_values_changed':False,'processing_applied':[]}
    json_save(root/'human-ap-derivation.json',derivation)
    samples=[
        {'id':'neo-neuropixels-noise4sam-lf','path':root/'raw/Noise4Sam_g0_t0.imec0.lf.bin',
         'label':'Neuropixels · NP1 LF · Noise4Sam 5.27 s', 'observation':'neo-noise4sam-imec0',
         'dataset':'neo-ephy-testing-data','license':'CC-BY-SA-4.0','source_url':GIN+NOISE+'.lf.bin',
         'description':'公开设备读取测试记录；来源未提供足够实验背景，不推断动物、人类、疾病或正常质量。',
         'biological_recording_verified':False,'derived':False,'disease':'unknown'},
        {'id':'paulk-human-pt03-ap-60s-2s','path':binary,
         'label':'Neuropixels · 人脑 Pt03 AP · 原始60–62 s','observation':'paulk-dryad-d2547d840-pt03',
         'dataset':'paulk-human-neuropixels-2022','license':'CC0-1.0', 'source_url':'https://zenodo.org/records/5899237',
         'description':'Paulk等公开人脑Neuropixels 1.0-ST记录；Pt03左前颞叶癫痫手术，原始60–62秒的逐字节片段。只验证接口与读数，无质控金标准。',
         'biological_recording_verified':True,'derived':True,'disease':'epilepsy'},
    ]
    inputs=[]; uploads=root/'upload-samples';uploads.mkdir(exist_ok=True)
    for sample in samples:
        p=sample['path'];reader=open_reader(p,sample['id'])
        try:meta,description=reader.metadata(),reader.describe()
        finally:reader.close()
        indices=[c['index'] for c in meta['channels'] if c['channel_type']=='neuropixels']
        band=meta['acquisition']['stream_band']
        record={'id':sample['id'],'label':sample['label'],'dataset_id':sample['dataset'],
            'source_observation_id':sample['observation'],'profile_id':'neuropixels_raw',
            'source_path':str(p.resolve()),'expected_sha256':digest(p),'expected_source_files':description['source_files'],
            'metadata':meta,'modality':'extracellular','modality_source':'SpikeGLX explicit imec Neuropixels probe metadata',
            'reference_scheme':'unknown','reference_evidence':'imro reference IDs retained in source; no anatomical reference interpretation.',
            'preprocessing':{'verified':False,'note':'Native AP/LF acquisition stream; complete source processing history not independently verified. No local filtering, sorting or rereferencing.'},
            'verified_electrode_coordinates':False,'verified_epochs':False,
            'default_config':{'selection':{'eeg_indices':indices,'reference_indices':{},'start_seconds':0.,
                                           'duration_seconds':meta['duration_seconds']},
                              'method_config':{'comparison_groups':None},
                              'context_tags':{'disease':sample['disease'],'age_group':'unknown','task':'other'}},
            'provenance':{'name':sample['dataset'],'version':GIN_COMMIT if sample['dataset']=='neo-ephy-testing-data' else 'Zenodo5899237 v1',
                          'license':sample['license'],'url':sample['source_url'],'derived':sample['derived']},
            'data_usage':{'typical_use':sample['description'],'annotations':'No interpreted events; sync words retained as non-voltage.',
                          'annotation_limits':'No channel or artifact quality ground truth; no spike sorting/unit labels.'},
            'scientific_limits':{'quality_ground_truth':False,'biological_recording_verified':sample['biological_recording_verified'],
                                 'raw_signal_values_modified':False,'interval_derived':sample['derived'],'cross_stream_alignment':'unverified'}}
        if sample['derived']:record['provenance']['derivation']=derivation
        inputs.append(record)
        zpath=uploads/(sample['id']+'.zip')
        with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for member in (p,p.with_suffix('.meta')):archive.write(member,member.name)
    json_save(root/'registration-additions.json',{'inputs':inputs,'profiles':[{
        'id':'neuropixels_raw','name':'Neuropixels原始流基础检查',
        'description':'单个AP/LF流的完整性、频谱和逐通道统计；不含分选后单元质量。',
        'modality':'extracellular','modules':['M03','M04','M05']}]})
    negatives=[]
    for name,reason in [('raw/Noise4Sam_g0_t0.imec0.ap.bin','Neo source README says AP was shortened to three packets; original size/time/checksum metadata is inconsistent.'),
                        ('acsf-ap-raw/5-19-2022-CI1_g0_t0.imec0.ap.bin','ACSF hardware test fixture has matching length/time but the declared original SHA1 does not match.')]:
        negative=root/name
        try:open_reader(negative,'negative').close()
        except ValueError as error:negative_message=str(error)
        else:raise AssertionError('Known inconsistent AP fixture was not rejected')
        m=dict(line.split('=',1) for line in negative.with_suffix('.meta').read_text().splitlines())
        negatives.append({'path':str(negative.resolve()),'actual_bytes':negative.stat().st_size,'declared_bytes':int(m['fileSizeBytes']),
                          'declared_sha1':m['fileSHA1'],'actual_sha1':digest(negative,'sha1'),
                          'reason':reason,'rejected':True,'message':negative_message,'registered':False})
    json_save(root/'sample-manifest.json',{'source_version':GIN_COMMIT,'sources':[{'path':name,'url':url,'sha256':expected} for name,url,expected in FILES],
        'examples':[{'input_id':r['id'],'source_path':r['source_path'],'observation_id':r['source_observation_id'],
                     'sha256':r['expected_sha256'],'duration_seconds':r['metadata']['duration_seconds'],
                     'acquisition':r['metadata']['acquisition'],'license':r['provenance']['license'],
                     'limitations':r['data_usage']['typical_use']} for r in inputs],
        'negative_fixtures':negatives,
        'np2_validation':'Synthetic decoding contracts only; no real NP2 dataset tested.',
        'not_redistributed_in_repository':True})
    print(json.dumps({'registration':str(root/'registration-additions.json'),'uploads':str(uploads),'inputs':len(inputs)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True)
    prepare(parser.parse_args().destination.resolve())
