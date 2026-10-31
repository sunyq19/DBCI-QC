#!/usr/bin/env python3
"""Prepare public NWB examples, explicit range-derived ECoG, and synthetic boundaries.

Requires h5py, numpy, requests and PyNWB. Writes data/evidence outside the repo;
does not register inputs, alter source files, run QC or infer anatomical modality.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys

import h5py
import numpy as np
import requests

REPO = Path(__file__).resolve().parents[2]
API = 'https://api.dandiarchive.org/api/'
SOURCES = [
    dict(id='sumac-lfp', dandiset='000165', version='0.211118.1526',
         asset='fd219159-b8ee-4bb3-933b-581245af0317', size=23312384,
         sha256='58d883df3f383bacd3db293f59a8ac61f322d148a516ec5e34799ce78657efa3',
         role='legacy_unit_continuous_lfp'),
    dict(id='jacobsen-clock-reset', dandiset='000230', version='0.220506.1516',
         asset='2f99c2e6-873d-4658-b74f-c81ba98c63b7', size=24275752,
         sha256='42b0289fa260ad37e2caec3e57f1fe5740910b136d1be9a1ca6959c9f8d242d2',
         role='negative_nonmonotonic_timestamps'),
    dict(id='tc6-high-gamma', dandiset='001193', version='0.240921.1006',
         asset='0d19ff6a-94cd-464c-a5af-1ef9a7d79510', size=29077240,
         sha256='7490caa0c5662facf17ae4b1113a44e5eb077b3762f71e5d9c0e645257f0c42a',
         role='processed_high_gamma_not_raw_voltage_reference'),
    dict(id='allen-probeD-lfp', dandiset='000021', version='0.251116.2246',
         asset='11646673-ac9a-42a0-b768-470af79ff4bc', size=71781159,
         sha256='ca8bc74bf3c0d9ee34d8338a10fbb1075aea1519206d6731eb39cde96938731d',
         role='public_zero_signal_lfp_boundary'),
]
ECOG = dict(id='ec9-b15', dandiset='000019', version='0.220126.2148',
            asset='4e4287f2-b557-4f30-a2d6-932f18c3e915', size=558155445)
TUTORIAL = 'https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html'


def plain(x):
    if isinstance(x, bytes): return x.decode('utf-8')
    if isinstance(x, (np.generic,)): return plain(x.item())
    if isinstance(x, np.ndarray): return [plain(v) for v in x.tolist()]
    if isinstance(x, (list, tuple)): return [plain(v) for v in x]
    if isinstance(x, dict): return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, float) and not np.isfinite(x): return None
    if isinstance(x, h5py.Reference): return '<HDF5 reference>'
    return x


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plain(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def copy_verified(source, target):
    """Leave existing identical upload copies untouched, including their mtime."""
    if target.exists():
        if sha256(target) != sha256(source):
            raise ValueError(f'Existing upload copy differs: {target.name}')
    else:
        shutil.copyfile(source, target)


def dandi_etag(path):
    """64 MiB multipart algorithm for these files (< 640 GiB)."""
    parts = []
    with path.open('rb') as f:
        for b in iter(lambda: f.read(64 * 1024 * 1024), b''):
            parts.append(hashlib.md5(b).digest())
    return hashlib.md5(b''.join(parts)).hexdigest() + '-' + str(len(parts))


def metadata(source, root):
    base = API + f"dandisets/{source['dandiset']}/versions/{source['version']}/"
    values = []
    for suffix, label in [('', 'dandiset'), (f"assets/{source['asset']}/", 'asset')]:
        p = root / 'provenance' / f"{source['id']}-{label}.json"
        if p.exists(): value = json.loads(p.read_text())
        else:
            response = requests.get(base + suffix, timeout=60)
            response.raise_for_status(); value = response.json(); save(p, value)
        values.append(value)
    dandiset, asset = values
    assert asset['contentSize'] == source['size']
    return dandiset, asset


def fetch(source, root):
    dandiset, asset = metadata(source, root)
    path = root / 'originals' / Path(asset['path']).name
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        tmp = path.with_suffix('.part')
        with requests.get(API + f"assets/{source['asset']}/download/", stream=True, timeout=60) as r:
            r.raise_for_status()
            with tmp.open('wb') as f:
                count = 0
                for block in r.iter_content(1024 * 1024):
                    count += len(block)
                    if count > source['size']: raise ValueError('Source exceeds pinned size')
                    f.write(block)
        assert tmp.stat().st_size == source['size'] and sha256(tmp) == source['sha256']
        tmp.rename(path)
    assert path.stat().st_size == source['size'] and sha256(path) == source['sha256']
    assert asset['digest']['dandi:sha2-256'] == source['sha256']
    assert dandi_etag(path) == asset['digest']['dandi:dandi-etag']
    return path, dict(source, source_path=asset['path'], license=dandiset.get('license'),
                      doi=dandiset.get('doi'), path=str(path), original_file_complete=True,
                      source_published_utc=asset.get('datePublished'), source_metadata_modified_utc=asset.get('dateModified'),
                      source_blob_modified_utc=asset.get('blobDateModified'),
                      local_file_mtime_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                      published_sha256_verified=True, published_dandi_etag_verified=True)


class Remote(io.RawIOBase):
    """Bounded, cached HTTP range reader; records only public content metadata."""
    def __init__(self, url, size, cache):
        self.url, self.size, self.cache = url, size, cache
        cache.mkdir(parents=True, exist_ok=True)
        self.pos = 0; self.ranges = {}; self.received = 0; self.session = requests.Session()

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos
    def seek(self, offset, whence=0):
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        if self.pos < 0: raise ValueError('Negative seek')
        return self.pos

    def read(self, n=-1):
        if n < 0: n = self.size - self.pos
        end = min(self.pos + n, self.size); parts = []
        while self.pos < end:
            i = self.pos // 262144; start = i * 262144; stop = min(start + 262144, self.size) - 1
            path = self.cache / f'{start}-{stop}.bin'
            if not path.exists():
                r = self.session.get(self.url, headers={'Range': f'bytes={start}-{stop}'}, timeout=60)
                if r.status_code != 206 or r.headers.get('Content-Range') != f'bytes {start}-{stop}/{self.size}':
                    raise ValueError('Server did not honor the exact HTTP range')
                if len(r.content) != stop - start + 1: raise ValueError('Short HTTP range')
                path.write_bytes(r.content); self.received += len(r.content)
            block = path.read_bytes()
            if len(block) != stop - start + 1: raise ValueError('Corrupt cached range')
            self.ranges[i] = dict(start_byte=start, stop_byte_inclusive=stop,
                                 sha256=hashlib.sha256(block).hexdigest())
            if sum(v['stop_byte_inclusive'] - v['start_byte'] + 1 for v in self.ranges.values()) > 150 * 1024**2:
                raise ValueError('HTTP range budget exceeded')
            take = min(end - self.pos, stop - self.pos + 1)
            parts.append(block[self.pos-start:self.pos-start+take]); self.pos += take
        return b''.join(parts)

    def readinto(self, b):
        data = self.read(len(b)); b[:len(data)] = data; return len(data)


def ecog_excerpt(root, upload):
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries
    from hdmf.backends.hdf5.h5_utils import H5DataIO
    dandiset, asset = metadata(ECOG, root)
    remote = Remote(next(u for u in asset['contentUrl'] if 's3.amazonaws.com' in u),
                    ECOG['size'], root / 'range-cache' / ECOG['asset'])
    series_path = '/acquisition/ElectricalSeries'; first, stop = 30518, 61036
    target = root / 'derived' / 'DANDI_000019_EC9_B15_samples30518-61036.nwb'
    target.parent.mkdir(exist_ok=True)
    with h5py.File(remote, 'r') as f:
        g = f[series_path]; raw = g['data'][first:stop, :]
        fs = float(g['starting_time'].attrs['rate']); origin = float(g['starting_time'][()])
        start_time = origin + first / fs
        assert raw.shape == (30518, 256) and raw.dtype == np.float32
        assert fs == 3051.7578 and g['data'].attrs['conversion'] == 0.001
        rows = g['electrodes'][:]; table = f[g['electrodes'].attrs['table']]
        table_meta = {k: plain(v[:]) for k, v in table.items()
                      if isinstance(v, h5py.Dataset) and v.dtype.kind != 'O'}
        for key in ['location', 'filtering', 'group_name']:
            if key in table: table_meta[key] = plain(table[key][:])
        ids = table['id'][:]; session_date = datetime.fromisoformat(plain(f['session_start_time'][()]))
        session_desc = plain(f['session_description'][()])
        sample_hash = hashlib.sha256(raw.tobytes(order='C')).hexdigest()
        source = dict(ECOG, source_path=asset['path'], series_path=series_path,
                      doi=dandiset.get('doi'), license=dandiset.get('license'),
                      source_published_utc=asset.get('datePublished'), source_metadata_modified_utc=asset.get('dateModified'),
                      source_blob_modified_utc=asset.get('blobDateModified'), source_session_start_time=session_date.isoformat(),
                      original_size_bytes=asset['contentSize'], original_published_digest=asset['digest'],
                      original_full_digest_verified=False, source_sample_start=first, source_sample_stop_exclusive=stop,
                      original_sample_count=g['data'].shape[0], channel_count=256,
                      source_starting_time_seconds=origin, excerpt_starting_time_seconds=start_time,
                      sampling_frequency_hz=fs, duration_seconds=(stop-first)/fs,
                      source_unit=plain(g['data'].attrs['unit']), source_conversion=0.001, source_offset=0.0,
                      source_data_dtype=str(raw.dtype), selected_stored_values_sha256=sample_hash,
                      source_electrode_table_rows=rows.tolist(), source_electrode_ids=ids[rows].tolist(),
                      source_electrode_table=table_meta,
                      operations=['Select source samples [30518,61036), all source channels',
                                  'Write a declared derived NWB; preserve stored float32 values and conversion',
                                  'Canonicalize source unit spelling volt to volts without numerical change',
                                  'Represent empty source electrode locations as unknown; retain original values in provenance'],
                      not_applied=['filtering', 'resampling', 'rereferencing', 'artifact removal'],
                      omitted_source_content=['stimuli', 'trials', 'other non-voltage objects'],
                      processing_history_complete=False, reference_scheme='unknown')
        if not target.exists():
            nwb = NWBFile(session_description=f'Derived 10 s excerpt of public {session_desc}; full provenance in notes.',
                          identifier='DBCI-QC-DANDI-000019-EC9-B15-samples30518-61036',
                          session_start_time=session_date, file_create_date=datetime(2026, 10, 30, tzinfo=timezone.utc),
                          notes=json.dumps(plain(source), ensure_ascii=False),
                          related_publications=[dandiset.get('doi', '')])
            device = nwb.create_device(name='source_256Grid')
            group = nwb.create_electrode_group(name='source_256Grid', description='Source ECoG 256Grid; no new anatomy inferred',
                                               location='source electrode locations retained per row', device=device)
            nwb.add_electrode_column(name='source_row_index', description='Row of original source electrodes table')
            nwb.add_electrode_column(name='source_electrode_id', description='Identifier in original source electrodes table')
            for row in rows:
                nwb.add_electrode(id=int(ids[row]), group=group,
                                  location=(plain(table['location'][row]) or 'unknown') if 'location' in table else 'unknown',
                                  source_row_index=int(row), source_electrode_id=int(ids[row]))
            nwb.add_acquisition(ElectricalSeries(name='ElectricalSeries',
                description='Real ECoG source excerpt; no filtering, resampling or rereferencing performed by DBCI-QC',
                data=H5DataIO(raw, compression='gzip'), electrodes=nwb.create_electrode_table_region(list(range(256)), 'All source channels in unchanged order'),
                starting_time=start_time, rate=fs, conversion=0.001, offset=0.0))
            with NWBHDF5IO(str(target), 'w') as writer: writer.write(nwb)
    with h5py.File(target, 'r') as f:
        out = f[series_path]
        assert np.array_equal(raw, out['data'][:])
        assert float(out['starting_time'][()]) == start_time
        assert float(out['data'].attrs['conversion']) == source['source_conversion']
        assert np.array_equal(f['general/extracellular_ephys/electrodes/source_electrode_id'][:], ids[rows])
    source.update(path=str(target), sha256=sha256(target), size_bytes=target.stat().st_size,
                  local_file_mtime_utc=datetime.fromtimestamp(target.stat().st_mtime, timezone.utc).isoformat(),
                  range_bytes_used=sum(x['stop_byte_inclusive']-x['start_byte']+1 for x in remote.ranges.values()),
                  byte_ranges_inclusive=list(remote.ranges.values()), all_excerpt_values_bitwise_equal=True)
    save(root / 'evidence/ecog-excerpt.json', source)
    copy = upload / target.name; copy_verified(target, copy)
    return dict(source, upload_path=str(copy), role='real_ecog_derived_positive')


def synthetic(root, upload):
    """Original deterministic fixtures using official NWB tutorial structure."""
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries, LFP
    from pynwb.misc import AnnotationSeries
    paths = []
    for kind in ['multistream', 'units_only']:
        target = root / 'synthetic' / f'DBCI_synthetic_{kind}.nwb'; target.parent.mkdir(exist_ok=True)
        if not target.exists():
            f = NWBFile(session_description='SYNTHETIC engineering fixture; not a biological recording',
                        identifier='DBCI-synthetic-nwb-' + kind,
                        session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
                        file_create_date=datetime(2026, 10, 30, tzinfo=timezone.utc),
                        notes='Original deterministic test values; structure follows '+TUTORIAL)
            if kind == 'multistream':
                d = f.create_device(name='synthetic_test_device')
                g = f.create_electrode_group(name='synthetic', description='Synthetic; no real anatomy', location='unknown', device=d)
                f.add_electrode_column('label', 'Synthetic electrode label')
                for i in range(4): f.add_electrode(id=100+i*10, group=g, location='unknown', label=f'Test{i}')
                t = np.arange(20000)/1000.0
                raw = np.rint(np.column_stack([80*np.sin(2*np.pi*10*t), 40*np.sin(2*np.pi*21*t), 20*np.cos(2*np.pi*7*t)])).astype('int16')
                f.add_acquisition(ElectricalSeries(name='raw_regular', description='Synthetic raw voltage', data=raw,
                    electrodes=f.create_electrode_table_region([2, 0, 3], 'Nonidentity mapping tests row order, not table IDs'),
                    rate=1000.0, starting_time=5.0, conversion=1e-6, channel_conversion=[1., 2., .5], offset=2e-6))
                t_lfp = np.arange(2500)/250.0
                lfp = np.column_stack([10*np.sin(2*np.pi*8*t_lfp), 5*np.cos(2*np.pi*12*t_lfp)])
                s = ElectricalSeries(name='lfp_timestamps', description='Synthetic LFP; separate clock and channels',
                    data=lfp, electrodes=f.create_electrode_table_region([1, 3], 'Independent LFP mapping'),
                    timestamps=12.0+t_lfp, conversion=1e-6, filtering='Synthetic fixture, no applied real filter')
                f.create_processing_module('ecephys', 'Synthetic processing structure').add(LFP(electrical_series=s))
                f.add_acquisition(AnnotationSeries(name='events', data=['synthetic event'], timestamps=[13.0]))
            f.add_unit(id=7, spike_times=[6.0, 6.5, 7.0])
            f.add_unit(id=42, spike_times=[6.1, 9.0])
            with NWBHDF5IO(str(target), 'w') as writer: writer.write(f)
        copy = upload / target.name; copy_verified(target, copy)
        paths.append(dict(id='synthetic-'+kind, path=str(target), upload_path=str(copy),
                          sha256=sha256(target), size_bytes=target.stat().st_size, synthetic=True,
                          source=TUTORIAL, role='multistream_clock_and_mapping' if kind=='multistream' else 'negative_no_continuous_voltage'))
    return paths


def audit_h5(path):
    """Independent source inventory: direct HDF5 data, never PyNWB getter data."""
    result = dict(path=str(path), sha256=sha256(path), method='direct_h5py_no_pynwb_data_access', series=[])
    with h5py.File(path, 'r') as f:
        result['nwb_version'] = plain(f.attrs.get('nwb_version'))
        result['units_count'] = len(f['units/id']) if 'units/id' in f else 0
        def inspect(name, obj):
            if not isinstance(obj, h5py.Group) or plain(obj.attrs.get('neurodata_type')) != 'ElectricalSeries': return
            d = obj['data']; e = dict(path='/'+name, shape=list(d.shape), dtype=str(d.dtype),
                data_attributes=plain(dict(d.attrs)), electrode_rows=obj['electrodes'][:].tolist())
            table = f[obj['electrodes'].attrs['table']]; e['electrode_ids'] = table['id'][:][obj['electrodes'][:]].tolist()
            if 'starting_time' in obj:
                e.update(starting_time=float(obj['starting_time'][()]), rate=float(obj['starting_time'].attrs['rate']))
            if 'timestamps' in obj:
                ts = obj['timestamps'][:]; dt = np.diff(ts); median = float(np.median(dt))
                e['clock'] = dict(first=float(ts[0]), last=float(ts[-1]), count=len(ts),
                    min_interval=float(dt.min()), max_interval=float(dt.max()), median_interval=median,
                    nonpositive_intervals=int(np.sum(dt<=0)), nonpositive_after_sample=np.flatnonzero(dt<=0).tolist(),
                    max_interval_deviation=float(np.max(np.abs(dt-median))))
            # Large compressed all-zero source is deliberately checked in distant windows,
            # rather than represented as a full-array numerical audit.
            windows = [(0, min(1000, len(d))), (max(0, len(d)//2-500), min(len(d), len(d)//2+500)),
                       (max(0, len(d)-1000), len(d))]
            e['stored_value_windows'] = []
            for lo, hi in windows:
                x = d[lo:hi]
                e['stored_value_windows'].append(dict(start=lo, stop_exclusive=hi,
                    sha256=hashlib.sha256(x.tobytes(order='C')).hexdigest(),
                    finite_count=int(np.isfinite(x).sum()), nonzero_count=int(np.count_nonzero(x)),
                    minimum=float(np.nanmin(x)), maximum=float(np.nanmax(x))))
            result['series'].append(e)
        f.visititems(inspect)
    return result


def audit_reader(entries):
    """Compare adapter output with independent h5py calibration and table rows."""
    sys.path.insert(0, str(REPO / 'src'))
    from ephys_qc.readers import open_reader
    checks = []
    for entry in entries:
        if entry['id'] not in {'ec9-b15', 'sumac-lfp', 'synthetic-multistream'}: continue
        path = Path(entry['path'])
        probe = open_reader(path, 'nwb-independent-audit')
        try:
            available = probe.describe()['available_streams']
        finally: probe.close()
        for available_stream in available:
            stream_id = available_stream['stream_id']
            reader = open_reader(path, 'nwb-independent-audit', stream_id=stream_id)
            try:
                stream = reader.describe()['streams'][0]
                channels = stream['channels']; segment = stream['segments'][0]
                compared = 0; max_error = 0.
                with h5py.File(path, 'r') as f:
                    obj = f[stream_id]; d = obj['data']; attrs = d.attrs
                    units = {'volts': 1., 'volt': 1., 'microvolts': 1e-6}
                    unit_scale = units[plain(attrs['unit'])]
                    conversion = float(attrs.get('conversion', 1.)); offset = float(attrs.get('offset', 0.))
                    channel_scale = obj['channel_conversion'][:] if 'channel_conversion' in obj else np.ones(d.shape[1])
                    table = f[obj['electrodes'].attrs['table']]; rows = obj['electrodes'][:]
                    ids = table['id'][:][rows]
                    assert [c['electrode_row_index'] for c in channels] == rows.tolist()
                    assert [c['electrode_id'] for c in channels] == ids.tolist()
                    for lo in range(0, len(d), 10000):
                        hi = min(lo+10000, len(d)); stored = d[lo:hi].astype(np.float64)
                        reference = (stored * conversion * channel_scale[None, :] + offset) * unit_scale
                        actual = reader.read_window(stream_id, segment['segment_id'],
                            [c['channel_id'] for c in channels], lo, hi, 'physical').T
                        assert np.array_equal(actual, reference), 'Independent physical calibration differs'
                        max_error = max(max_error, float(np.max(np.abs(reference-actual))))
                        compared += int(reference.size)
                    # Reversed selection checks requested channel order independently.
                    reversed_actual = reader.read_window(stream_id, segment['segment_id'],
                        [c['channel_id'] for c in reversed(channels)], 0, 10, 'physical')
                    reference = (d[:10].astype(np.float64)*conversion*channel_scale[None, :]+offset)*unit_scale
                    assert np.array_equal(reversed_actual, reference[:, ::-1].T)
                reader.assert_unchanged(hashes=True)
                checks.append(dict(id=entry['id'], stream_id=stream_id, compared_values=compared,
                    all_values_exactly_equal=True, max_absolute_error_volts=max_error,
                    electrode_mapping_verified=True, reversed_channel_order_verified=True,
                    reference='Direct h5py stored arrays and raw HDF5 unit/conversion/offset attributes; no PyNWB data getter'))
            finally: reader.close()
    return dict(status='passed', checks=checks, scientific_accuracy_validated=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Source and evidence directory outside the repository')
    parser.add_argument('--upload-dir', type=Path, required=True, help='Upload example directory outside the repository')
    parser.add_argument('--audit-reader', action='store_true', help='Compare current installed adapter to independent HDF5 arrays')
    args = parser.parse_args(); root = args.output.resolve(); upload = args.upload_dir.resolve()
    if root.is_relative_to(REPO) or upload.is_relative_to(REPO): parser.error('Store source data outside the repository')
    root.mkdir(parents=True, exist_ok=True); upload.mkdir(parents=True, exist_ok=True)
    entries = []
    for source in SOURCES:
        path, entry = fetch(source, root)
        dest = upload / ('边界样例' if source['id'] != 'sumac-lfp' else '') / path.name
        dest.parent.mkdir(exist_ok=True); copy_verified(path, dest); entry['upload_path'] = str(dest)
        entries.append(entry)
    entries.append(ecog_excerpt(root, upload)); entries.extend(synthetic(root, upload))
    evidence = [audit_h5(Path(e['path'])) for e in entries]
    save(root / 'evidence/h5py-source-audit.json', evidence)
    manifest = dict(schema_version='nwb-examples/1.0', prepared_date='2026-10-30',
        source_observation_count=5, synthetic_observation_count=0,
        synthetic_fixture_count=2, entries=entries,
        limitations=['Repository metadata and stored units are evidence, not independent amplifier calibration.',
                     'The human ECoG file is a declared excerpt, not a full original-file download.',
                     'Some source files are rejected or scientifically restricted boundaries, not usable raw-voltage positives.',
                     'Synthetic samples test contracts only; they add no independent physiological/clinical evidence.',
                     'No dataset supplies artifact or bad-channel accuracy ground truth.'])
    save(root / 'manifest.json', manifest)
    if args.audit_reader:
        save(root / 'evidence/independent-adapter-readback.json', audit_reader(entries))
    (upload/'README.txt').write_text(
        'NWB 上传测试样例\n\n'
        '1. DANDI_000019_EC9_B15_samples30518-61036.nwb：人类 ECoG 原生 NWB 的明确约10秒截取副本，256道；不是原文件全量。\n'
        '2. sub-Sumac...nwb：真实小鼠32道LFP原文件，legacy microvolts单位，另含Units。\n'
        '3. DBCI_synthetic_multistream.nwb：纯合成，两个不同电极映射/时钟的连续流，另含Units。\n'
        '4. DBCI_synthetic_units_only.nwb：纯合成，只有Units，没有可质控的连续电压，应明确拒绝。\n'
        '5. 边界样例目录：真实来源时间戳回跳、处理后高伽马、抽查全零LFP；不可当成正常原始电压标准。\n\n'
        '来源、版权、摘要、原始样本与独立核对见 ../../公开数据/NWB/manifest.json 和 evidence/。\n'
        'DANDI数据集为CC-BY-4.0；请保留来源DOI和作者信息，Allen数据还须遵循其来源使用条款。\n', encoding='utf-8')
    print(json.dumps(dict(status='prepared', manifest=str(root/'manifest.json'), upload=str(upload),
                          entries=len(entries), synthetic_fixtures=2), ensure_ascii=False))


if __name__ == '__main__': main()
