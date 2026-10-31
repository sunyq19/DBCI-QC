"""NWB 2 / HDF5 continuous ElectricalSeries, one explicit native clock at a time.

Units spike tables and SpikeEventSeries are not continuous voltage. No spatial
modality inference, resampling, filtering, or reconstruction is performed.
See https://pynwb.readthedocs.io/en/stable/pynwb.ecephys.html and
https://pynwb.readthedocs.io/en/stable/tutorials/domain/ecephys.html .
"""
from pathlib import Path
from numbers import Integral
import copy
import math
import posixpath
import re

from .common import SourceGuard, source_manifest, public_manifest, annotation_summary


MAX_WINDOW_BYTES = 256 * 1024 * 1024
READ_CHUNK_BYTES = 4 * 1024 * 1024
TIMESTAMP_CHUNK = 262144


def _text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else str(value)


def _finite(value, name, positive=False):
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f'NWB {name} 必须为有限数值。') from error
    if not math.isfinite(result) or (positive and result <= 0):
        raise ValueError(f'NWB {name} 必须为有限' + ('正数。' if positive else '数值。'))
    return result


def _safe_hdf_inventory(handle):
    """Inspect links before dereferencing, including soft links through parents.

    Internal soft links are common in NWB; resolve every path component ourselves
    so a soft link cannot hide an external-link parent. HDF object addresses avoid
    hard-link cycles. No external HDF5 file or raw-data file is opened.
    """
    import h5py
    object_paths, seen = {}, set()

    def resolve(path, depth=0):
        if depth > 64:
            raise ValueError('NWB 内部链接循环或深度过大。')
        parts = [part for part in posixpath.normpath('/' + path.lstrip('/')).split('/') if part]
        group = handle['/']
        for index, part in enumerate(parts):
            if not isinstance(group, h5py.Group):
                raise ValueError('NWB 内部链接路径无效。')
            link = group.get(part, getlink=True)
            if isinstance(link, h5py.ExternalLink):
                raise ValueError('NWB 外部链接不受支持；请提供自包含 HDF5 文件。')
            if isinstance(link, h5py.SoftLink):
                target = link.path if link.path.startswith('/') else posixpath.join(group.name, link.path)
                return resolve(posixpath.join(target, *parts[index + 1:]), depth + 1)
            if link is None:
                raise ValueError('NWB 内部链接目标缺失。')
            group = group[part]
        return group

    def visit(obj):
        address = h5py.h5o.get_info(obj.id).addr
        if address in seen:
            return
        seen.add(address)
        if isinstance(obj, h5py.Dataset):
            if obj.is_virtual or obj.external:
                raise ValueError('NWB 虚拟数据集或外部原始数据存储不受支持。')
            return
        object_id = obj.attrs.get('object_id')
        if object_id is not None:
            object_paths[_text(object_id)] = obj.name
        for name in sorted(obj.keys()):
            visit(resolve(posixpath.join(obj.name, name)))

    visit(handle['/'])
    return object_paths


def _unit_scale(unit):
    key = _text(unit).strip().lower().replace('μ', 'u').replace('µ', 'u')
    scales = {'v': 1., 'volt': 1., 'volts': 1.,
              'mv': 1e-3, 'millivolt': 1e-3, 'millivolts': 1e-3,
              'uv': 1e-6, 'microvolt': 1e-6, 'microvolts': 1e-6,
              'nv': 1e-9, 'nanovolt': 1e-9, 'nanovolts': 1e-9}
    if key not in scales:
        raise ValueError('NWB ElectricalSeries 缺少明确的电压单位；不能猜测单位。')
    return scales[key]


def _clock(group, count):
    """Validate every explicit timestamp in bounded blocks, not a sampled prefix."""
    import numpy as np
    time_dataset = group.get('timestamps') if 'timestamps' in group else group.get('starting_time')
    if time_dataset is not None and _text(time_dataset.attrs.get('unit', '')).lower() not in {'seconds', 'second', 's'}:
        raise ValueError('NWB 时钟单位不是明确的秒；不能将其他时间单位直接当成秒。')
    if 'timestamps' not in group:
        if 'starting_time' not in group or 'rate' not in group['starting_time'].attrs:
            raise ValueError('NWB 连续流缺少规则采样时钟。')
        source_start = _finite(group['starting_time'][()], 'starting_time')
        rate = _finite(group['starting_time'].attrs['rate'], 'rate', True)
        timing = {'source': 'starting_time_and_rate', 'verified_timestamp_count': 0}
    else:
        times = group['timestamps']
        if times.ndim != 1 or times.shape[0] != count or times.dtype.kind not in 'iuf' or count < 2:
            raise ValueError('NWB timestamps 须与样本数一致且至少有两个数值。')
        source_start = _finite(times[0], 'timestamps[0]')
        source_end = _finite(times[-1], 'timestamps[-1]')
        step = _finite((source_end - source_start) / (count - 1), 'timestamp interval', True)
        tolerance = max(step * 1e-6, 1e-12, 8 * np.finfo(float).eps * max(abs(source_start), abs(source_end)))
        if tolerance > step * .01:
            raise ValueError('NWB timestamps 数值精度不足，无法核验规则采样。')
        maximum_error, previous = 0., None
        for start in range(0, count, TIMESTAMP_CHUNK):
            block = np.asarray(times[start:min(start + TIMESTAMP_CHUNK, count)], dtype=float)
            if (not np.all(np.isfinite(block)) or np.any(np.diff(block) <= 0)
                    or (previous is not None and block[0] <= previous)):
                raise ValueError('NWB timestamps 存在缺失、回跳或重复，不能视为连续规则采样。')
            expected = source_start + np.arange(start, start + len(block), dtype=float) * step
            error = float(np.max(np.abs(block - expected)))
            maximum_error = max(maximum_error, error)
            if error > tolerance:
                raise ValueError('NWB timestamps 不等距或存在间断；当前不重采样。')
            previous = float(block[-1])
        rate = 1 / step
        timing = {'source': 'fully_verified_regular_timestamps', 'verified_timestamp_count': count,
                  'maximum_timing_error_seconds': maximum_error, 'tolerance_seconds': tolerance}
    if not math.isfinite(count / rate) or count / rate <= 0:
        raise ValueError('NWB 样本数与采样时钟无法组成有效时长。')
    return rate, {'origin': 'selected_series_start', 'first_sample': 0, 'first_time_seconds': source_start,
        'source_starting_time_seconds': source_start, 'sampling_frequency_hz': rate,
        'sample_origin_semantics': 'series_local_not_acquisition_sample_number',
        'cross_source_alignment': 'not_verified', **timing}


def _device_info(device):
    """Only model metadata or an explicit model statement, never device/stream names."""
    if device is None:
        return {'probe_model': None, 'probe_type': None, 'neuropixels_device_declared': False,
                'model_evidence': []}
    model = getattr(device, 'model', None)
    fields = []
    for obj, attrs, prefix in [(model, ('name', 'model_number'), 'device.model'),
                                (device, ('model_name', 'model_number'), 'device')]:
        if obj is not None:
            for attr in attrs:
                value = getattr(obj, attr, None)
                if value:
                    fields.append({'field': prefix + '.' + attr, 'value': _text(value)})
    description = getattr(device, 'description', None)
    if description and re.search(r'\bNeuropixels\b', _text(description), re.I):
        fields.append({'field': 'device.description', 'value': _text(description)})
    manufacturer = getattr(model, 'manufacturer', None) or getattr(device, 'manufacturer', None) or ''
    part_mapping = {**{f'NP{i}': 0 for i in [1000, 1001, *range(1010, 1018)]}, 'NP2000': 21, 'NP2010': 24}
    declared = any(re.search(r'\bNeuropixels\b', f['value'], re.I) for f in fields)
    part = next((f['value'].upper() for f in fields if f['value'].upper() in part_mapping), None)
    declared = declared or (part is not None and 'imec' in _text(manufacturer).lower())
    return {'probe_model': fields[0]['value'] if fields else None,
            'probe_type': part_mapping.get(part) if declared else None,
            'neuropixels_device_declared': bool(declared), 'model_evidence': fields}


class NWBReader(SourceGuard):
    def __init__(self, path, record_id, *, stream_id=None):
        import h5py
        import pynwb
        from pynwb.ecephys import ElectricalSeries, SpikeEventSeries
        self.path, self.record_id = Path(path).resolve(), str(record_id)
        self.io, self.handle = None, None
        self.capture(source_manifest([(self.path, 'main')]))
        try:
            self.handle = h5py.File(self.path, 'r')
            version = _text(self.handle.attrs.get('nwb_version', ''))
            if not version.startswith('2.'):
                raise ValueError('当前 NWB 读取器仅支持 NWB 2 / HDF5。')
            paths = _safe_hdf_inventory(self.handle)
            # Same already-inspected handle: PyNWB cannot reopen an unchecked file.
            self.io = pynwb.NWBHDF5IO(file=self.handle, mode='r', load_namespaces=True)
            nwb = self.io.read()
            units = nwb.units
            self.nwb_info = {'version': version, 'storage': 'HDF5', 'units_present': units is not None,
                'units_count': len(units) if units is not None else 0,
                'units_interpretation': 'spike_table_not_continuous_voltage',
                'interval_tables': sorted(nwb.intervals.keys()),
                'schema_validation': 'structural_reader_checks_not_full_nwb_validation'}
            self.backend_version = 'pynwb/' + pynwb.__version__
            self._streams, self.available_streams = {}, []
            objects = [obj for obj in nwb.objects.values() if isinstance(obj, ElectricalSeries)
                       and not isinstance(obj, SpikeEventSeries)]
            self.nwb_info['electrical_series_count'] = len(objects)
            for obj in sorted(objects, key=lambda item: paths.get(str(item.object_id), '')):
                source_path = paths.get(str(obj.object_id))
                if source_path is None:
                    raise ValueError('NWB ElectricalSeries 缺少可追溯的 HDF5 对象路径。')
                parent_kind = type(obj.parent).__name__
                summary = {'stream_id': source_path, 'name': obj.name, 'container_type': parent_kind,
                           'object_type': type(obj).__name__, 'channel_count': None, 'sample_count': None,
                           'sampling_rate_hz': None, 'duration_seconds': None}
                try:
                    stream = self._prepare_stream(obj, self.handle[source_path], source_path, parent_kind)
                    self._streams[source_path] = stream
                    summary.update(status='available', reason=None, readable=True, unsupported_reason=None,
                        channel_count=len(stream['channels']), sample_count=stream['sample_count'],
                        sampling_rate_hz=stream['sampling_frequency_hz'],
                        duration_seconds=stream['sample_count'] / stream['sampling_frequency_hz'],
                        acquisition=stream['acquisition'], capabilities=stream['capabilities'])
                except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
                    summary.update(status='unsupported', reason=str(error), readable=False, unsupported_reason=str(error),
                                   acquisition={}, capabilities={'continuous_voltage': False})
                self.available_streams.append(summary)
            if stream_id is not None and (not isinstance(stream_id, str) or stream_id not in self._streams):
                summary = next((s for s in self.available_streams if s['stream_id'] == stream_id), None)
                raise ValueError('NWB 所选流不可读：' + (summary['reason'] if summary else '未知的流路径。'))
            self.selected_stream_id = stream_id if stream_id is not None else (
                next(iter(self._streams)) if len(self._streams) == 1 else None)
            self.selected = self._streams.get(self.selected_stream_id)
            self.assert_unchanged()
        except Exception:
            self.close()
            raise

    def _prepare_stream(self, obj, group, source_path, parent_kind):
        import numpy as np
        data = group['data']
        if data.ndim not in (1, 2) or data.dtype.kind not in 'iuf' or data.shape[0] < 1:
            raise ValueError('NWB 连续电压须为非空 time × channel 或一维数值数组。')
        count, n_channels = int(data.shape[0]), (int(data.shape[1]) if data.ndim == 2 else 1)
        if not 1 <= n_channels <= 4096:
            raise ValueError('NWB 流通道数必须在 1–4096 之间。')
        source_unit = _text(data.attrs.get('unit', ''))
        unit_scale = _unit_scale(source_unit)
        conversion = _finite(data.attrs.get('conversion', 1.), 'conversion', True)
        offset = _finite(data.attrs.get('offset', 0.), 'offset')
        if 'channel_conversion' in group:
            cc_dataset = group['channel_conversion']
            if cc_dataset.shape != (n_channels,) or cc_dataset.dtype.kind not in 'iuf':
                raise ValueError('NWB channel_conversion 必须与通道一一对应。')
            channel_conversion = np.asarray(cc_dataset[:], dtype=float)
        else:
            channel_conversion = np.ones(n_channels)
        if not np.all(np.isfinite(channel_conversion)) or np.any(channel_conversion <= 0):
            raise ValueError('NWB channel_conversion 必须为有限正数。')
        with np.errstate(over='ignore', under='ignore'):
            scales = conversion * channel_conversion * unit_scale
            offset_si = offset * unit_scale
        if not np.all(np.isfinite(scales)) or np.any(scales <= 0) or not math.isfinite(offset_si):
            raise ValueError('NWB 电压校准超出数值范围。')
        rate, clock = _clock(group, count)
        region = obj.electrodes
        if region is None or region.table is None:
            raise ValueError('NWB ElectricalSeries 缺少 electrodes 映射。')
        table = region.table
        if region.data.shape != (n_channels,) or region.data.dtype.kind not in 'iu':
            raise ValueError('NWB electrodes 行索引必须与每个通道一一对应。')
        rows = np.asarray(region.data[:])
        if np.any(rows < 0) or np.any(rows >= len(table)):
            raise ValueError('NWB electrodes 行索引越界；不能把表 ID 当成行号。')
        labels_column = next((name for name in ('label', 'channel_name', 'electrode_name') if name in table.colnames), None)
        channels, devices = [], []
        for index, row_value in enumerate(rows):
            row = int(row_value)
            electrode_id = table.id[row]
            if isinstance(electrode_id, np.integer):
                electrode_id = int(electrode_id)
            if not isinstance(electrode_id, (str, int)) or isinstance(electrode_id, bool):
                raise ValueError('NWB electrode ID 不是可追溯的整数或字符串。')
            name = _text(table[labels_column][row]) if labels_column else f'electrode_{electrode_id}'
            electrode_group = table['group'][row] if 'group' in table.colnames else None
            device_info = _device_info(getattr(electrode_group, 'device', None))
            devices.append(device_info)
            channels.append({'channel_id': f'{self.record_id}:ch:{index}', 'source_index': index,
                'raw_name': name, 'reader_name': name, 'electrode_row_index': row, 'electrode_id': electrode_id,
                'electrode_group': getattr(electrode_group, 'name', None),
                'channel_type': 'neuropixels' if device_info['neuropixels_device_declared'] else 'unknown',
                'channel_type_source': 'file_declared' if device_info['neuropixels_device_declared'] else 'unknown',
                'quantity': 'voltage', 'unit': 'V', 'physical_unit': 'V', 'source_unit': source_unit,
                'unit_source': 'NWB_data_attributes', 'unit_status': 'known_voltage', 'scale_to_si': 1.,
                'digital_to_physical_scale': float(scales[index]), 'physical_offset': offset_si,
                'physical_min': None, 'physical_max': None, 'conversion': conversion,
                'channel_conversion': float(channel_conversion[index]), 'unit_scale_to_si': unit_scale,
                'calibration_source': '(stored * conversion * channel_conversion + offset) * unit_to_si'})
        source_container = source_path.split('/')[1]
        processed = source_container == 'processing' or parent_kind in {'LFP', 'FilteredEphys'}
        warnings = []
        if source_unit != 'volts':
            warnings.append('NWB ElectricalSeries 使用非规范单位拼写/量级；依据原始 data.unit 显式换算为 V。')
        if len({c['raw_name'] for c in channels}) != n_channels:
            warnings.append('源通道名称重复；保留原名，使用独立通道索引，不合并。')
        if len(set(int(row) for row in rows)) != n_channels:
            warnings.append('多个信号列引用同一电极表行；保留各列，不假设它们独立。')
        if processed:
            warnings.append('此 ElectricalSeries 位于处理结果容器；不是已核验的原始采集信号。')
        probe_models = sorted({d['probe_model'] for d in devices if d['probe_model']})
        declared_np = all(d['neuropixels_device_declared'] for d in devices)
        probe_types = {d['probe_type'] for d in devices}
        acquisition = {'system': 'NWB', 'stream_band': 'lf' if parent_kind == 'LFP' else 'unknown',
            'probe_model': probe_models[0] if len(probe_models) == 1 else None, 'probe_models': probe_models,
            'probe_type': next(iter(probe_types)) if len(probe_types) == 1 else None,
            'neuropixels_device_declared': declared_np, 'source_container': source_container,
            'processing_status': 'processed' if processed else 'acquisition_declared_history_unverified',
            'raw_source': False if processed else 'unknown',
            'description': _text(obj.description) if obj.description is not None else None,
            'comments': _text(obj.comments) if obj.comments is not None else None,
            'filtering_declaration': _text(obj.filtering) if obj.filtering is not None else None,
            'device_model_evidence': list({(e['field'], e['value']): e for d in devices for e in d['model_evidence']}.values())}
        capabilities = {'continuous_voltage': True, 'regular_sampling': True,
            'voltage_calibration_verified': True, 'electrode_mapping_verified': True,
            'source_series_kind': 'ElectricalSeries', 'source_container': source_container,
            'raw_source': False if processed else 'unknown', 'processed': True if processed else None}
        segment = {'segment_id': source_path + ':segment:0', 'start_sample': 0,
                   'stop_sample': count, 'recording_start_seconds': 0.}
        return {'stream_id': source_path, 'sampling_frequency_hz': rate, 'sample_index_origin': 0,
                'sample_count': count, 'segments': [segment], 'channels': channels, 'clock': clock,
                'reference': 'as_stored', 'processing_applied': [], 'acquisition': acquisition,
                'capabilities': capabilities, 'warnings': warnings, '_dataset': data}

    def describe(self):
        self.assert_unchanged()
        return {'reader_id': 'pynwb_electrical_series', 'reader_version': 'nwb-adapter/1',
            'backend_version': self.backend_version, 'source_id': self.record_id, 'format': 'NWB',
            'source_files': copy.deepcopy(self.source_files),
            'header_channel_count': len(self.selected['channels']) if self.selected else 0,
            'events': [], 'annotations': self._annotations(),
            'clock': copy.deepcopy(self.selected['clock']) if self.selected else {},
            'streams': [copy.deepcopy({k: v for k, v in self.selected.items() if not k.startswith('_')})] if self.selected else [],
            'selected_stream_id': self.selected_stream_id, 'available_streams': copy.deepcopy(self.available_streams),
            'nwb': copy.deepcopy(self.nwb_info), 'warnings': self._warnings(),
            'processing_applied': [], 'scientific_validity': 'pending'}

    def _warnings(self):
        warnings = list(self.selected['warnings']) if self.selected else []
        warnings.append('当前未提取 NWB 事件或将其时钟映射到所选信号；不表示文件中不存在标注。')
        if self.selected is None:
            warnings.append('存在多个可用电压流，请明确选择。' if len(self._streams) > 1 else '没有当前支持的连续电压流。')
        if self.nwb_info['units_present']:
            warnings.append('Units 是 spike / unit 表，本次仅记录数量，不作为连续波形质控。')
        if self.nwb_info['interval_tables']:
            warnings.append('保留 interval 表清单；当前未将事件时钟映射到所选电压流。')
        return warnings

    def _annotations(self):
        return {**annotation_summary([], [self.path]), 'available': None, 'count': None,
                'extraction_status': 'not_extracted', 'time_reference': 'not_mapped_to_selected_series'}

    def metadata(self):
        self.assert_unchanged()
        selected = self.selected
        channels = selected['channels'] if selected else []
        np_declared = bool(selected and selected['acquisition']['neuropixels_device_declared'])
        return {'format': 'NWB',
            'duration_seconds': selected['sample_count'] / selected['sampling_frequency_hz'] if selected else 0.,
            'channels': [{'index': c['source_index'], 'raw_index': c['source_index'], 'name': c['raw_name'],
                'unit': 'V', 'source_unit': c['source_unit'], 'unit_source': c['unit_source'],
                'channel_type': c['channel_type'], 'channel_type_source': c['channel_type_source'],
                'sampling_rate_hz': selected['sampling_frequency_hz'], 'electrode_id': c['electrode_id'],
                'electrode_row_index': c['electrode_row_index']} for c in channels],
            'raw_signal_count': len(channels), 'annotation_signal_count': 0,
            'size_bytes': sum(f['size_bytes'] for f in self.source_files), 'reader_id': 'pynwb_electrical_series',
            'reader_version': 'nwb-adapter/1', 'backend_version': self.backend_version,
            'source_files': public_manifest(self.source_files), 'annotations': self._annotations(),
            'modality_evidence': {'value': 'extracellular' if np_declared else 'unknown',
                'source': 'file_declared' if np_declared else 'unknown',
                'channel_types': sorted({c['channel_type'] for c in channels}), 'requires_confirmation': True},
            'acquisition': copy.deepcopy(selected['acquisition']) if selected else {},
            'capabilities': copy.deepcopy(selected['capabilities']) if selected else {},
            'clock': copy.deepcopy(selected['clock']) if selected else {},
            'continuous_segments': copy.deepcopy(selected['segments']) if selected else [],
            'selected_stream_id': self.selected_stream_id,
            'stream_selection_required': len(self._streams) > 1 and self.selected_stream_id is None,
            'available_streams': copy.deepcopy(self.available_streams), 'nwb': copy.deepcopy(self.nwb_info),
            'warnings': self._warnings()}

    def read_window(self, stream_id, segment_id, channel_ids, start_sample, stop_sample, representation='physical'):
        import numpy as np
        self.assert_unchanged()
        stream = self.selected
        if (stream is None or stream_id != self.selected_stream_id or segment_id != stream['segments'][0]['segment_id']
                or representation != 'physical'
                or any(isinstance(v, bool) or not isinstance(v, Integral) for v in (start_sample, stop_sample))
                or start_sample < 0 or stop_sample > stream['sample_count'] or start_sample >= stop_sample):
            raise ValueError('NWB 读取窗口须位于明确选定的规则电压流内，输出仅为物理电压。')
        lookup = {c['channel_id']: c for c in stream['channels']}
        if (not isinstance(channel_ids, (list, tuple)) or not channel_ids
                or any(not isinstance(c, str) or c not in lookup for c in channel_ids)
                or len(set(channel_ids)) != len(channel_ids)):
            raise ValueError('NWB 读取通道须为不同的有效源通道 ID。')
        length = stop_sample - start_sample
        if len(channel_ids) * length * 8 > MAX_WINDOW_BYTES:
            raise ValueError('读取窗口超过 256 MiB 限制。')
        channels = [lookup[key] for key in channel_ids]
        order = sorted(range(len(channels)), key=lambda i: channels[i]['source_index'])
        indices = [channels[i]['source_index'] for i in order]
        data = stream['_dataset']
        block_length = max(1, READ_CHUNK_BYTES // (len(channels) * max(data.dtype.itemsize, 8)))
        output = np.empty((len(channels), length), dtype=np.float64)
        for start in range(start_sample, stop_sample, block_length):
            stop = min(start + block_length, stop_sample)
            block = data[start:stop, indices] if data.ndim == 2 else data[start:stop][:, None]
            for j, channel_index in enumerate(order):
                channel = channels[channel_index]
                target = output[channel_index, start - start_sample:stop - start_sample]
                with np.errstate(over='ignore', invalid='ignore'):
                    target[:] = block[:, j]
                    target *= channel['digital_to_physical_scale']
                    target += channel['physical_offset']
                if np.any(np.isfinite(block[:, j]) & ~np.isfinite(target)):
                    raise ValueError('NWB 电压校准发生数值溢出。')
        self.assert_unchanged()
        return output

    def close(self):
        if self.io is not None:
            self.io.close()
            self.io = None
        if self.handle is not None:
            self.handle.close()
            self.handle = None
