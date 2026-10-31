#!/usr/bin/env python3
"""Compare every sample with independently obtained official readSGLX helpers.

The reference file is not vendored, installed or fetched by this script. Pass a
reviewed local copy of Python/DemoReadSGLXData/readSGLX.py from
https://github.com/jenniferColonell/SpikeGLX_Datafile_Tools
commit c1b7075dfbb36b054d7334d18bf2b1b0496b2e72.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ephys_qc.readers import open_reader


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def validate(root,reference):
    if sha(reference) != '2ef2b406a136170b979a2f7343b951c42717f61d7bb4d173554a6f0ff5bd80f3':
        raise ValueError('Reference script differs from the reviewed pinned official version.')
    import matplotlib
    matplotlib.use('Agg')
    import numpy as np
    spec=importlib.util.spec_from_file_location('official_readSGLX',reference)
    official=importlib.util.module_from_spec(spec);spec.loader.exec_module(official)
    records=json.loads((root/'registration-additions.json').read_text())['inputs']
    results=[]
    for record in records:
        path=Path(record['source_path']); reader=open_reader(path,record['id'])
        try:
            desc=reader.describe();stream=desc['streams'][0];segment=stream['segments'][0]
            before={x['path']:sha(x['path']) for x in desc['source_files']}
            meta=official.readMeta(path);reference_data=official.makeMemMapRaw(path,meta)
            neural=[i for i,c in enumerate(stream['channels']) if c['quantity']=='voltage']
            sync=[i for i,c in enumerate(stream['channels']) if c['quantity']=='digital_word']
            neural_ids=[stream['channels'][i]['channel_id'] for i in neural]
            origin=stream['sample_index_origin']; n=stream['sample_count'];fs=stream['sampling_frequency_hz']
            count=0;digital_count=0;sync_count=0
            for a in range(0,n,3000):
                b=min(n,a+3000)
                expected=official.GainCorrectIM(reference_data[neural,a:b],neural,meta)
                actual=reader.read_window(stream['stream_id'],segment['segment_id'],neural_ids,origin+a,origin+b)
                np.testing.assert_array_equal(actual,expected);count+=actual.size
                all_ids=[c['channel_id'] for c in stream['channels']]
                digital=reader.read_window(stream['stream_id'],segment['segment_id'],all_ids,origin+a,origin+b,'digital')
                np.testing.assert_array_equal(digital,reference_data[:,a:b]);digital_count+=digital.size
                for s in sync:
                    bits=reader.read_window(stream['stream_id'],segment['segment_id'],[all_ids[s]],origin+a,origin+b)[0]
                    np.testing.assert_array_equal(bits,reference_data[s,a:b].view('<u2'));sync_count+=bits.size
            assert fs==official.SampRate(meta)
            assert origin==int(meta['firstSample']) and segment['recording_start_seconds']==0
            assert before=={p:sha(p) for p in before}
            assert reader.metadata()['acquisition']['declared_sha1_status']=='verified'
            reference_data._mmap.close()
            results.append({'id':record['id'],'path':str(path),'samples_per_channel':n,'neural_channels':len(neural),
                'physical_values_compared':count,'digital_values_compared':digital_count,'sync_words_compared':sync_count,
                'max_absolute_error_volts':0.,'all_physical_samples_bit_exact_float64':True,
                'all_digital_samples_exact':True,'sync_excluded_from_voltage':True,'first_sample':origin,
                'sampling_rate_hz':fs,'source_files_unchanged':True,'source_sha256':before})
        finally:reader.close()
    negatives=json.loads((root/'sample-manifest.json').read_text())['negative_fixtures']
    for fixture in negatives:
        try:open_reader(fixture['path'],'negative').close()
        except ValueError as error:assert 'fileSHA1' in str(error)
        else:raise AssertionError('Inconsistent source was accepted')
    report={'status':'passed','reference_url':'https://github.com/jenniferColonell/SpikeGLX_Datafile_Tools/blob/c1b7075dfbb36b054d7334d18bf2b1b0496b2e72/Python/DemoReadSGLXData/readSGLX.py',
            'reference_sha256':sha(reference),'records':results,'negative_fixtures_rejected':len(negatives),
            'limits':['Metadata-based numerical equivalence, not an independent validation of device calibration.',
                      'Human AP is a declared 2-second byte-range derivative. Full remote binary checksum was not verified.',
                      'NP2 has synthetic tests only. No clinical quality or unit-quality accuracy is established.']}
    target=root/'independent-readback.json';target.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'output':str(target),'records':len(results),
                      'physical_values_compared':sum(x['physical_values_compared'] for x in results)},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--reference',type=Path,required=True)
    args=p.parse_args();validate(args.directory.resolve(),args.reference.resolve())
