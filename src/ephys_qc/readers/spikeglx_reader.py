"""Restricted, native-clock SpikeGLX reader for NP1 (0), NP2 (21/24).

One AP or LF binary and its same-name metadata are one recording. No joining,
filtering, inferred calibration, probe-localization or spike sorting is done.
Specification: https://billkarsh.github.io/SpikeGLX/More_help/Metadata_20.html
IMRO formats: https://billkarsh.github.io/SpikeGLX/help/imroTables/
Reference: https://github.com/jenniferColonell/SpikeGLX_Datafile_Tools
"""
from pathlib import Path
from numbers import Integral
import copy
import hashlib
import math
import re

from .common import SourceGuard, companion, source_manifest, public_manifest, annotation_summary


def _int(value, name, minimum=0, maximum=2**63 - 1):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+', value):
        raise ValueError(f'SpikeGLX {name} 必须是非负整数。')
    result = int(value)
    if not minimum <= result <= maximum:
        raise ValueError(f'SpikeGLX {name} 超出支持范围。')
    return result


def _positive(value, name):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'SpikeGLX {name} 必须是正数。') from error
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f'SpikeGLX {name} 必须是有限正数。')
    return result


def _metadata(path):
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('SpikeGLX 文本头超过 4 MiB。')
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition('=')
        key = key.removeprefix('~')
        if not sep or not key or key in result:
            raise ValueError('SpikeGLX 元数据存在无效或重复键。')
        result[key] = value
    return result


def _counts(value, name):
    parts = value.split(',')
    if len(parts) != 3:
        raise ValueError(f'SpikeGLX {name} 需要 AP、LF、SY 三个计数。')
    return tuple(_int(p, name, maximum=4096) for p in parts)


def _subset(value, count, total):
    if value == 'all':
        indices = list(range(count))
    else:
        indices = []
        for part in value.split(','):
            bounds = part.split(':')
            if len(bounds) not in (1, 2):
                raise ValueError('SpikeGLX 保存通道子集无效。')
            start = _int(bounds[0], 'snsSaveChanSubset', maximum=total - 1)
            stop = _int(bounds[-1], 'snsSaveChanSubset', maximum=total - 1)
            if start > stop:
                raise ValueError('SpikeGLX 保存通道范围倒置。')
            indices.extend(range(start, stop + 1))
    if len(indices) != count or len(set(indices)) != count or indices != sorted(indices):
        raise ValueError('SpikeGLX 保存通道子集须唯一、有序且与 nSavedChans 一致。')
    if not indices or max(indices) >= total:
        raise ValueError('SpikeGLX 保存通道超出采集通道范围。')
    return indices


def _table(value, name):
    parts = re.findall(r'\(([^()]*)\)', value)
    if not parts or ''.join('(' + p + ')' for p in parts) != value:
        raise ValueError(f'SpikeGLX {name} 表结构无效。')
    return parts


class SpikeGLXReader(SourceGuard):
    def __init__(self, path, record_id):
        self.path, self.record_id = Path(path).resolve(), str(record_id)
        match = re.fullmatch(r'.+\.(ap|lf)\.bin', self.path.name, re.IGNORECASE)
        if not match:
            raise ValueError('SpikeGLX 仅支持单流 .ap.bin 或 .lf.bin 与同名 .meta；不接入任意二进制文件。')
        band = match.group(1).lower()
        meta_path = companion(self.path, self.path.with_suffix('.meta').name, '.meta')
        self.capture(source_manifest([(self.path, 'main'), (meta_path, 'metadata')]))
        meta = _metadata(meta_path)
        source_sha1 = meta.get('fileSHA1', '')
        if source_sha1:
            if not re.fullmatch(r'[0-9a-fA-F]{40}', source_sha1):
                raise ValueError('SpikeGLX fileSHA1 不是有效的 SHA1 校验值。')
            checksum = hashlib.sha1()
            with self.path.open('rb') as binary:
                for block in iter(lambda: binary.read(1024 * 1024), b''):
                    checksum.update(block)
            if checksum.hexdigest() != source_sha1.lower():
                raise ValueError('SpikeGLX fileSHA1 与二进制内容不一致；请核对来源，不能静默修正。')
        if meta.get('typeThis') != 'imec':
            raise ValueError('当前 SpikeGLX 仅接入 imec Neuropixels 流。')
        probe = _int(meta.get('imDatPrb_type'), 'imDatPrb_type')
        if probe not in {0, 21, 24}:
            raise ValueError('当前仅支持 Neuropixels 型号 0、21、24；不会猜测未知型号的校准。')
        acquired = _counts(meta.get('acqApLfSy', ''), 'acqApLfSy')
        saved = _counts(meta.get('snsApLfSy', ''), 'snsApLfSy')
        n = _int(meta.get('nSavedChans'), 'nSavedChans', 1, 4096)
        if sum(saved) != n or acquired[0] < 1 or sum(acquired) > 4096:
            raise ValueError('SpikeGLX 保存或采集通道计数不一致。')
        if (band == 'ap' and (saved[0] < 1 or saved[1])) or (band == 'lf' and (saved[1] < 1 or saved[0])):
            raise ValueError('SpikeGLX 文件名 AP/LF 与保存通道类型不一致。')
        if probe in {21, 24} and (band != 'ap' or acquired[1]):
            raise ValueError('NP2 型号 21/24 不提供原生 LF 流。')
        indices = _subset(meta.get('snsSaveChanSubset', ''), n, sum(acquired))
        kinds = ['ap' if i < acquired[0] else 'lf' if i < sum(acquired[:2]) else 'sync' for i in indices]
        if tuple(kinds.count(k) for k in ('ap', 'lf', 'sync')) != saved:
            raise ValueError('SpikeGLX 子集与 AP/LF/SY 计数不一致。')
        fs = _positive(meta.get('imSampRate'), 'imSampRate')
        vmax = _positive(meta.get('imAiRangeMax'), 'imAiRangeMax')
        expected_max = 512 if probe == 0 else 8192
        max_int = _int(meta.get('imMaxInt', str(expected_max)), 'imMaxInt', 1, 32768)
        if max_int != expected_max:
            raise ValueError('SpikeGLX ADC 范围与当前支持的探针型号不一致。')
        origin = _int(meta.get('firstSample'), 'firstSample')
        size = self.path.stat().st_size
        if size == 0 or size % (2 * n) or _int(meta.get('fileSizeBytes'), 'fileSizeBytes') != size:
            raise ValueError('SpikeGLX 数据字节数与元数据/完整采样帧不一致。')
        n_times = size // (2 * n)
        declared_duration = _positive(meta.get('fileTimeSecs'), 'fileTimeSecs')
        if abs(declared_duration - n_times / fs) > max(1 / fs, 1e-9):
            raise ValueError('SpikeGLX 声明时长与采样帧数不一致。')
        imro = _table(meta.get('imroTbl', ''), 'imroTbl')
        header = imro[0].split(',')
        if len(header) != 2 or _int(header[1], 'imroTbl.count') != acquired[0]:
            raise ValueError('SpikeGLX imroTbl 型号或通道数不一致。')
        if header[0].startswith('NP'):
            # Since 2026-01-15 the table can use a part number. Accept only the
            # documented mapping for supported types and consistent metadata.
            supported_parts = {0: {'NP1000', 'NP1001'} | {f'NP{i}' for i in range(1010, 1018)},
                               21: {'NP2000'}, 24: {'NP2010'}}
            if header[0] not in supported_parts[probe] or meta.get('imDatPrb_pn') != header[0]:
                raise ValueError('SpikeGLX imroTbl 部件号与支持型号/元数据不一致。')
        elif _int(header[0], 'imroTbl.type') != probe:
            raise ValueError('SpikeGLX imroTbl 型号不一致。')
        entries = {}
        for row in imro[1:]:
            fields = row.split()
            expected_fields = {0: 6, 21: 4, 24: 5}[probe]
            if len(fields) != expected_fields:
                raise ValueError('SpikeGLX imroTbl 条目格式不支持。')
            channel = _int(fields[0], 'imroTbl.channel', maximum=acquired[0] - 1)
            if channel in entries:
                raise ValueError('SpikeGLX imroTbl 存在重复通道。')
            entries[channel] = fields
        if len(entries) != acquired[0]:
            raise ValueError('SpikeGLX imroTbl 未完整描述采集通道。')
        names = None
        if 'snsChanMap' in meta:
            mapped = _table(meta['snsChanMap'], 'snsChanMap')[1:]
            if len(mapped) != n:
                raise ValueError('SpikeGLX snsChanMap 条目数不一致。')
            names = []
            for entry, index in zip(mapped, indices):
                name, sep, mapping = entry.partition(';')
                fields = mapping.split(':')
                if not sep or not name or len(fields) != 2 or _int(fields[0], 'snsChanMap.index') != index:
                    raise ValueError('SpikeGLX snsChanMap 与保存通道子集不一致。')
                names.append(name)
        if names and len(set(names)) != n:
            raise ValueError('SpikeGLX 通道名重复；不静默改名。')
        self.channels = []
        for saved_index, (index, kind) in enumerate(zip(indices, kinds)):
            is_neural = kind != 'sync'
            gain = None
            if is_neural:
                channel = index if kind == 'ap' else index - acquired[0]
                if channel not in entries:
                    raise ValueError('SpikeGLX LF 通道缺少对应 imroTbl 校准。')
                gain = (_positive(entries[channel][3 if kind == 'ap' else 4], 'imroTbl.gain')
                        if probe == 0 else 80.)
                if probe in {21, 24} and 'imChan0apGain' in meta and _positive(meta['imChan0apGain'], 'imChan0apGain') != gain:
                    raise ValueError('NP2 固定增益与声明值冲突。')
            scale = vmax / max_int / gain if is_neural else None
            name = names[saved_index] if names else f'{kind.upper()}{index}'
            self.channels.append({'channel_id': f'{record_id}:ch:{saved_index}', 'source_index': saved_index,
                'acquired_index': index, 'raw_name': name, 'reader_name': name,
                'channel_type': 'neuropixels' if is_neural else 'stim', 'channel_type_source': 'file_declared',
                'stream_band': band if is_neural else 'sync', 'quantity': 'voltage' if is_neural else 'digital_word',
                'unit': 'V' if is_neural else 'bits', 'physical_unit': 'V' if is_neural else 'bits',
                'unit_source': 'SpikeGLX_metadata_calibration' if is_neural else 'SpikeGLX_sync_word',
                'unit_status': 'known_voltage' if is_neural else 'not_voltage',
                'scale_to_si': 1. if is_neural else None, 'gain': gain,
                'digital_min': -max_int if is_neural else -32768, 'digital_max': max_int - 1 if is_neural else 32767,
                'digital_to_physical_scale': scale, 'physical_min': -max_int * scale if is_neural else None,
                'physical_max': (max_int - 1) * scale if is_neural else None,
                'calibration_source': 'imAiRangeMax / imMaxInt / per-channel gain' if is_neural else 'raw sync bits'})
        geometry = None
        if 'snsShankMap' in meta:
            rows = _table(meta['snsShankMap'], 'snsShankMap')[1:]
            neural = [c for c in self.channels if c['quantity'] == 'voltage']
            if len(rows) != len(neural):
                raise ValueError('SpikeGLX snsShankMap 与神经通道数不一致。')
            for row, channel in zip(rows, neural):
                fields = row.split(':')
                if len(fields) != 4:
                    raise ValueError('SpikeGLX snsShankMap 条目无效。')
                channel['probe_grid'] = dict(zip(('shank', 'column', 'row', 'used'), [_int(v, 'snsShankMap') for v in fields]))
            geometry = 'source_grid_indices_not_anatomical_coordinates'
        self.assert_unchanged()
        self.fs, self.origin, self.n_times = fs, origin, n_times
        self.acquisition = {'system': 'SpikeGLX', 'stream_band': band, 'probe_type': probe,
            'probe_model': {0: 'Neuropixels 1.0', 21: 'Neuropixels 2.0 single-shank', 24: 'Neuropixels 2.0 four-shank'}[probe],
            'probe_part_number': meta.get('imDatPrb_pn'), 'sampling_rate_hz': fs,
            'saved_neural_channel_count': saved[0] + saved[1], 'saved_sync_channel_count': saved[2],
            'adc_max_integer': max_int, 'adc_max_integer_source': 'file_declared' if 'imMaxInt' in meta else 'supported_probe_specification',
            'adc_voltage_range_max': vmax, 'channel_gains': sorted({c['gain'] for c in self.channels if c['gain'] is not None}),
            'declared_sha1_status': 'verified' if source_sha1 else 'not_declared',
            'geometry': geometry, 'cross_stream_alignment': 'unverified', 'processing_applied': []}
        stream_id = f'{record_id}:spikeglx:{band}'
        self.segments = [{'segment_id': f'{stream_id}:segment:0', 'start_sample': origin,
                          'stop_sample': origin + n_times, 'recording_start_seconds': 0.}]
        warnings = ['原始 AP/LF 流；未进行 spike sorting、单元质量评估或跨流时钟对齐。',
                    '文件声明的样本时钟不证明采集期间没有丢帧；同步字保留但不解释为临床事件。']
        self.description = {'reader_id': 'native_spikeglx', 'reader_version': 'spikeglx-adapter/1',
            'backend_version': 'native-int16-memmap/1', 'source_id': str(record_id), 'format': 'SpikeGLX',
            'source_files': self.source_files, 'header_channel_count': n, 'events': [],
            'annotations': annotation_summary([], []), 'acquisition': self.acquisition,
            'clock': {'origin': 'first_sample_in_file', 'first_sample': origin, 'first_time_seconds': origin / fs,
                      'time_reference': 'recording_start_seconds', 'cross_source_alignment': 'unverified'},
            'streams': [{'stream_id': stream_id, 'sampling_frequency_hz': fs, 'sample_index_origin': origin,
                         'sample_count': n_times, 'segments': self.segments, 'channels': self.channels,
                         'reference': 'as_stored', 'processing_applied': []}],
            'warnings': warnings, 'processing_applied': [], 'scientific_validity': 'pending'}
        import numpy as np
        self.raw = np.memmap(self.path, dtype='<i2', mode='r', shape=(n_times, n))
        self.assert_unchanged()

    def describe(self):
        self.assert_unchanged()
        return copy.deepcopy(self.description)

    def metadata(self):
        self.assert_unchanged()
        return {'format': 'SpikeGLX', 'duration_seconds': self.n_times / self.fs,
            'channels': [{'index': c['source_index'], 'raw_index': c['source_index'], 'name': c['raw_name'],
                          'unit': c['unit'], 'source_unit': c['physical_unit'], 'unit_source': c['unit_source'],
                          'channel_type': c['channel_type'], 'channel_type_source': c['channel_type_source'],
                          'sampling_rate_hz': self.fs, 'acquired_index': c['acquired_index'],
                          'stream_band': c['stream_band'], 'gain': c['gain'],
                          **({'probe_grid': copy.deepcopy(c['probe_grid'])} if 'probe_grid' in c else {})} for c in self.channels],
            'raw_signal_count': len(self.channels), 'annotation_signal_count': 0,
            'size_bytes': sum(f['size_bytes'] for f in self.source_files), 'reader_id': 'native_spikeglx',
            'reader_version': 'spikeglx-adapter/1', 'backend_version': 'native-int16-memmap/1',
            'source_files': public_manifest(self.source_files), 'annotations': copy.deepcopy(self.description['annotations']),
            'modality_evidence': {'value': 'extracellular', 'source': 'file_declared',
                                  'channel_types': sorted({c['channel_type'] for c in self.channels}), 'requires_confirmation': True},
            'acquisition': copy.deepcopy(self.acquisition), 'clock': copy.deepcopy(self.description['clock']),
            'continuous_segments': copy.deepcopy(self.segments), 'warnings': self.description['warnings'].copy()}

    def read_window(self, stream_id, segment_id, channel_ids, start_sample, stop_sample, representation='physical'):
        import numpy as np
        self.assert_unchanged()
        stream, segment = self.description['streams'][0], self.segments[0]
        if (representation not in {'physical', 'digital'} or stream_id != stream['stream_id'] or segment_id != segment['segment_id']
                or any(isinstance(v, bool) or not isinstance(v, Integral) for v in (start_sample, stop_sample))
                or start_sample < self.origin or stop_sample > self.origin + self.n_times or start_sample >= stop_sample):
            raise ValueError('SpikeGLX 读取窗口须位于一个原生连续段内。')
        lookup = {c['channel_id']: c for c in self.channels}
        if (not isinstance(channel_ids, (tuple, list)) or not channel_ids
                or any(not isinstance(c, str) or c not in lookup for c in channel_ids)
                or len(set(channel_ids)) != len(channel_ids)):
            raise ValueError('读取通道必须是不同的有效源通道 ID。')
        if len(channel_ids) * (stop_sample - start_sample) * 8 > 256 * 1024 * 1024:
            raise ValueError('读取窗口超过 256 MiB 限制。')
        channels = [lookup[c] for c in channel_ids]
        data = np.array(self.raw[start_sample - self.origin:stop_sample - self.origin,
                                  [c['source_index'] for c in channels]].T, copy=True)
        if representation == 'physical':
            values = data.astype(np.float64)
            for i, channel in enumerate(channels):
                if channel['quantity'] == 'voltage':
                    values[i] *= channel['digital_to_physical_scale']
                else:
                    values[i] = data[i].view('<u2')  # unit bits; never volts
            data = values
        self.assert_unchanged()
        return data

    def close(self):
        if hasattr(self, 'raw'):
            self.raw._mmap.close()
