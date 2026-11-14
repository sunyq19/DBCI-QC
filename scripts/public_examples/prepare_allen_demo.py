"""Make traceable 60-second LFP excerpts from two public Allen mice.

Only time is cropped. Stored samples, units, timestamps and electrode positions
are retained, with public byte-range receipts. Full remote-file SHA is not
claimed when only ranges were retrieved.
"""
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import h5py
import numpy as np
import requests
from pynwb import NWBFile,NWBHDF5IO
from pynwb.ecephys import ElectricalSeries,LFP
from pynwb.file import Subject
from hdmf.backends.hdf5.h5_utils import H5DataIO
from prepare_nwb_examples import Remote,plain,sha256,save
from prepare_eight_datasets import DEFAULT_ROOT

SOURCES=[('7d6bd755-e75b-48c8-bc37-2e11333c5f29','699733573','810755797'),
         ('b703e4a9-1cfa-49be-8bc3-92e2ec432969','707296975','760213137')]

def prepare(asset,subject,probe,base=DEFAULT_ROOT):
    root=base/'08_Neuropixels_小鼠LFP';root.mkdir(parents=True,exist_ok=True)
    target=root/f'sub-{subject}_probe-{probe}_lfp_excerpt60s.nwb'
    receipt=root/(target.stem+'.source.json')
    if target.exists() and receipt.exists():
        assert sha256(target)==json.loads(receipt.read_text())['excerpt_sha256'];return
    mp=root/(asset+'.metadata.json')
    if mp.exists():m=json.loads(mp.read_text())
    else:
        r=requests.get(f'https://api.dandiarchive.org/api/dandisets/000021/versions/0.251116.2246/assets/{asset}/',timeout=60);r.raise_for_status();m=r.json();save(mp,m)
    remote=Remote(next(u for u in m['contentUrl'] if 's3.amazonaws.com' in u),m['contentSize'],root/'.range-cache'/asset)
    path=f'acquisition/probe_{probe}_lfp/probe_{probe}_lfp_data'
    with h5py.File(remote,'r') as f:
        g=f[path];stop=75000
        print('reading',subject,g['data'].shape,flush=True)
        raw=g['data'][:stop,:];ts=g['timestamps'][:stop]
        assert np.isfinite(raw).all() and np.std(raw)>0
        assert np.all(np.diff(ts)>0) and np.allclose(np.diff(ts),np.median(np.diff(ts)),rtol=1e-5,atol=1e-9)
        rows=g['electrodes'][:];table=f[g['electrodes'].attrs['table']];ids=table['id'][:]
        desc=plain(f['session_description'][()]);date=datetime.fromisoformat(plain(f['session_start_time'][()]))
        source=dict(name='Allen Visual Coding Neuropixels',url='https://dandiarchive.org/dandiset/000021/0.251116.2246',version='0.251116.2246',license='CC-BY-4.0',asset_id=asset,source_path=m['path'],source_series=path,source_size_bytes=m['contentSize'],published_digest=m['digest'],full_source_digest_verified=False,subject=subject,source_samples=g['data'].shape[0],selected_samples=[0,stop],time_start_seconds=float(ts[0]),time_stop_seconds=float(ts[-1]+np.median(np.diff(ts))),sampling_rate_hz=float(1/np.median(np.diff(ts))),channel_count=len(rows),source_processing='Allen LFP: temporal/spatial subsampling, 0.1 Hz high-pass and out-of-brain reference; see AllenSDK documentation.',processing_documentation='https://allensdk.readthedocs.io/en/latest/visual_coding_neuropixels.html',local_processing='Time crop only; stored samples and timestamps unchanged. Original source electrode rows and positions retained.',quality_truth='not_available',samples_sha256=__import__('hashlib').sha256(raw.tobytes()).hexdigest())
        n=NWBFile(session_description='60-second public LFP excerpt. '+desc,identifier=target.stem,session_start_time=date,file_create_date=datetime(2026,11,13,tzinfo=timezone.utc),notes=json.dumps(source))
        n.subject=Subject(subject_id=subject,species='Mus musculus')
        device=n.create_device(name='Neuropixels_1.0',description='Neuropixels 1.0 probe; Allen Visual Coding source',manufacturer='imec')
        group=n.create_electrode_group(name='probe_'+probe,description='Single source Neuropixels probe; positions retained',location='See source electrode locations',device=device)
        for key in ['source_row_index','probe_horizontal_position','probe_vertical_position']:
            n.add_electrode_column(key,'Retained source '+key)
        for row in rows:
            n.add_electrode(id=int(ids[row]),group=group,location=plain(table['location'][row]) or 'unknown',source_row_index=int(row),probe_horizontal_position=float(table['probe_horizontal_position'][row]),probe_vertical_position=float(table['probe_vertical_position'][row]))
        n.add_acquisition(LFP(electrical_series=ElectricalSeries(name='lfp',data=H5DataIO(raw,compression='gzip'),timestamps=ts,electrodes=n.create_electrode_table_region(list(range(len(rows))),'Source channel order retained'),conversion=float(g['data'].attrs.get('conversion',1)),offset=float(g['data'].attrs.get('offset',0)),filtering=source['source_processing'],description='Continuous preprocessed LFP, not AP or spike-sorted units.')))
        with NWBHDF5IO(str(target),'w') as io:io.write(n)
    with h5py.File(target,'r') as f:
        assert np.array_equal(raw,f['acquisition/LFP/lfp/data'][:]);assert np.array_equal(ts,f['acquisition/LFP/lfp/timestamps'][:])
    source.update(excerpt_sha256=sha256(target),size_bytes=target.stat().st_size,byte_ranges=list(remote.ranges.values()),all_excerpt_values_bitwise_equal=True)
    save(receipt,source);print('verified',target.name,raw.shape,source['time_start_seconds'],source['time_stop_seconds'],flush=True)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    args=parser.parse_args()
    for row in SOURCES:prepare(*row,base=args.root)
