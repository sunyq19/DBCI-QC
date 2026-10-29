"""MNE adapters, preserving channel identity, SI units and native sample clocks.

Official APIs (checked against installed MNE 1.13.2):
https://mne.tools/stable/generated/mne.io.read_raw_brainvision.html
https://mne.tools/stable/generated/mne.io.read_raw_eeglab.html
https://mne.tools/stable/generated/mne.io.read_raw_fif.html
Private metadata parsers are used only for preflight reference checks. They are
covered by fixture tests and their backend version is recorded in every result.
"""
from pathlib import Path
from numbers import Integral
import configparser
import copy
import math
import re
import warnings
from .common import (SourceGuard, companion, source_manifest, public_manifest,
                     annotation_summary)


def _configuration(path):
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError('BrainVision 文本头超过当前读取限制。')
    data = path.read_bytes()
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252')
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    offset = text.find('[Common Infos]')
    if offset < 0:
        raise ValueError('BrainVision 缺少 Common Infos。')
    # The BrainVision Comment section is free text, not INI key/value data.
    header_text = re.split(r'(?m)^\[Comment\]\s*$', text[offset:], maxsplit=1)[0]
    parser.read_string(header_text)
    return parser


def _brainvision_files(path):
    header = _configuration(path)
    data = companion(path, header['Common Infos']['DataFile'])
    marker = companion(path, header['Common Infos']['MarkerFile'], '.vmrk')
    marker_header = _configuration(marker)
    marker_data = companion(marker, marker_header['Common Infos']['DataFile'])
    if marker_data != data:
        raise ValueError('BrainVision 头与标记文件指向不同数据文件。')
    n = int(header['Common Infos']['NumberOfChannels'])
    if not 1 <= n <= 4096:
        raise ValueError('BrainVision 通道数超出当前限制。')
    names, units = [], []
    for i in range(1, n + 1):
        fields = header['Channel Infos'][f'Ch{i}'].split(',')
        if len(fields) < 3:
            raise ValueError('BrainVision 通道分辨率字段缺失。')
        names.append(fields[0].replace(r'\1', ','))
        units.append(fields[3].strip() if len(fields) > 3 else '')
    if len(set(names)) != len(names):
        raise ValueError('当前 MNE BrainVision 后端不能可靠处理重复通道名；保持源文件，拒绝合并或静默改名。')
    return [(path, 'main'), (marker, 'markers'), (data, 'signal')], names, units


def _no_hdf_external_links(path):
    with path.open('rb') as source:
        prefix = source.read(1024)
    if b'\x89HDF\r\n\x1a\n' not in prefix:
        return
    import h5py
    with h5py.File(path, 'r') as handle:
        seen = set()
        def walk(group):
            if group.id in seen:
                return
            seen.add(group.id)
            for key in group:
                link = group.get(key, getlink=True)
                if isinstance(link, h5py.ExternalLink):
                    raise ValueError('EEGLAB HDF5 外部文件链接不被允许。')
                obj = group[key]
                if isinstance(obj, h5py.Group):
                    walk(obj)
                elif isinstance(obj, h5py.Dataset) and (obj.external or obj.is_virtual):
                    raise ValueError('EEGLAB HDF5 外部或虚拟数据集不被允许。')
        walk(handle)


def _eeglab_files(path):
    _no_hdf_external_links(path)
    from mne.io.eeglab.eeglab import _check_load_mat
    eeg = _check_load_mat(path, None, preload=False)
    if eeg.trials != 1:
        raise ValueError('EEGLAB 当前只接入连续记录，不能把多个 epochs 拼成连续信号。')
    if not 1 <= eeg.nbchan <= 4096 or eeg.pnts < 1:
        raise ValueError('EEGLAB 通道或样本数量无效。')
    files = [(path, 'main')]
    if isinstance(eeg.data, str):
        # MNE's lazy numeric-MAT loader represents embedded data by this exact
        # main-file path. An external reference must otherwise be a safe basename.
        if eeg.data != str(path):
            data = companion(path, eeg.data, '.fdt')
            if data.stat().st_size != 4 * eeg.nbchan * eeg.pnts:
                raise ValueError('EEGLAB FDT 长度与声明的通道/样本不一致。')
            files.append((data, 'signal'))
    locs = eeg.get('chanlocs')
    if isinstance(locs, dict):
        labels = locs.get('labels', [])
        names = [labels] if isinstance(labels, str) else list(labels)
    elif isinstance(locs, (list, tuple)):
        names = [entry.get('labels', '') for entry in locs]
    else:
        names = []
    return files, names, eeg.get('xmin')


def _fif_preflight(path):
    from mne._fiff.open import fiff_open
    from mne._fiff.constants import FIFF
    from mne._fiff.tag import read_tag
    handle, _, directory = fiff_open(path, preload=False, verbose='ERROR')
    with handle:
        if any(tag.kind in {FIFF.FIFF_REF_FILE_NAME, FIFF.FIFF_REF_FILE_NUM} for tag in directory):
            raise ValueError('当前接入仅接受单文件 FIF；split FIF 引用不会自动打开。')
        channels = [read_tag(handle, tag.pos).data for tag in directory if tag.kind == FIFF.FIFF_CH_INFO]
    return [ch['ch_name'] for ch in channels]


class MNEReader(SourceGuard):
    def __init__(self, path, record_id, kind):
        import mne
        from mne._fiff.constants import FIFF
        self.path, self.kind, self.record_id = Path(path).resolve(), kind, str(record_id)
        original_names, original_units, xmin = [], [], None
        if kind == 'BrainVision':
            files, original_names, original_units = _brainvision_files(self.path)
        elif kind == 'EEGLAB':
            files, original_names, xmin = _eeglab_files(self.path)
        elif kind == 'FIF':
            original_names = _fif_preflight(self.path)
            files = [(self.path, 'main')]
        else:
            raise ValueError('Unregistered MNE reader')
        self.capture(source_manifest(files))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            if kind == 'BrainVision':
                self.raw = mne.io.read_raw_brainvision(self.path, preload=False, verbose='ERROR')
            elif kind == 'EEGLAB':
                self.raw = mne.io.read_raw_eeglab(self.path, preload=False, verbose='ERROR')
            else:
                self.raw = mne.io.read_raw_fif(self.path, preload=False, on_split_missing='raise', verbose='ERROR')
        self.assert_unchanged()
        def public_warning(message):
            for item in self.source_files:
                message = message.replace(item['path'], item['name'])
            return message
        self.warnings = list(dict.fromkeys(public_warning(str(w.message)) for w in caught))
        n, fs = len(self.raw.ch_names), float(self.raw.info['sfreq'])
        self.n_times = int(self.raw.n_times)
        if not 1 <= n <= 4096 or not math.isfinite(fs) or fs <= 0 or self.n_times < 1:
            self.close()
            raise ValueError('记录的通道数、采样率或长度无效。')
        if len(original_names) != n:
            original_names = list(self.raw.ch_names)
        elif kind == 'FIF':
            # FIF supports extended long names. Preserve those decoded names;
            # recover raw duplicated short labels if MNE had uniquified them.
            from collections import Counter
            counts = Counter(original_names)
            original_names = [old if counts[old] > 1 else parsed
                              for old, parsed in zip(original_names, self.raw.ch_names)]
        self.channels = []
        for i, (name, typ, info) in enumerate(zip(original_names, self.raw.get_channel_types(), self.raw.info['chs'])):
            voltage = info['unit'] == FIFF.FIFF_UNIT_V
            unit = 'V' if voltage else {FIFF.FIFF_UNIT_T: 'T', FIFF.FIFF_UNIT_T_M: 'T/m', FIFF.FIFF_UNIT_NONE: 'unknown'}.get(info['unit'], 'unknown')
            original = original_units[i] if original_units else ('uV' if kind == 'EEGLAB' and voltage else unit)
            # BrainVision explicitly defines omitted units as microvolts, as
            # implemented by MNE. Keep that default distinguishable from a
            # written source unit; this is not an inferred subject attribute.
            if kind == 'BrainVision' and original not in {'', 'V', 'mV', 'uV', 'µV', 'μV', 'nV'}:
                voltage, unit = False, {'uS': 'S', 'µS': 'S'}.get(original, original or 'unknown')
            self.channels.append({'channel_id': f'{self.record_id}:ch:{i}', 'source_index': i,
                                  'raw_name': name, 'reader_name': self.raw.ch_names[i],
                                  'channel_type': typ, 'quantity': 'voltage' if voltage else 'other',
                                  'unit': unit, 'physical_unit': original,
                                  'unit_source': 'BrainVision_format_default_microvolts' if kind == 'BrainVision' and not original else 'file_format_calibration',
                                  'unit_status': 'known_voltage' if voltage else 'not_voltage',
                                  'scale_to_si': 1.0 if voltage else None,
                                  'digital_to_physical_scale': None, 'physical_min': None, 'physical_max': None,
                                  'calibration_source': f'MNE {kind} SI decoding; ADC endpoints unavailable'})
        self.fs, self.origin = fs, int(self.raw.first_samp)
        stream_id = f'{self.record_id}:rate:{fs:g}'
        events = []
        for i, (onset, duration, description) in enumerate(zip(self.raw.annotations.onset, self.raw.annotations.duration, self.raw.annotations.description)):
            onset = float(onset - self.raw.first_time)
            duration = float(duration)
            if not math.isfinite(onset) or not math.isfinite(duration) or duration < 0:
                raise ValueError('记录含无效注释时钟。')
            events.append({'event_id': f'{self.record_id}:ann:{i}', 'onset_seconds': onset,
                           'duration_seconds': duration, 'text': str(description),
                           'interpretation_status': 'source_description_only'})
        gaps = []
        for event in events:
            if event['text'].casefold() in {'boundary', 'bad boundary', 'edge boundary', 'bad_acq_skip'}:
                a = max(0, min(self.n_times, round(event['onset_seconds'] * fs)))
                # EEGLAB boundary duration can describe removed acquisition
                # samples, which are not present in the stored array. Split at
                # that point; only FIF's stored BAD_ACQ_SKIP spans omit samples.
                b = (max(a, min(self.n_times, round((event['onset_seconds'] + event['duration_seconds']) * fs)))
                     if event['text'].casefold() == 'bad_acq_skip' else a)
                gaps.append((a, b))
        ranges, cursor = [], 0
        for a, b in sorted(gaps):
            if a > cursor:
                ranges.append((cursor, a))
            cursor = max(cursor, b)
        if cursor < self.n_times:
            ranges.append((cursor, self.n_times))
        self.segments = [{'segment_id': f'{stream_id}:segment:{i}', 'start_sample': self.origin + a,
                          'stop_sample': self.origin + b, 'recording_start_seconds': a / fs}
                         for i, (a, b) in enumerate(ranges)]
        if gaps:
            self.warnings.append('来源包含明确断点或采集缺口；分析窗口不可跨越连续段。')
        self.description = {'reader_id': 'mne_' + kind.lower(), 'reader_version': 'mne-adapter/1',
                            'backend_version': mne.__version__, 'source_id': self.record_id, 'format': kind,
                            'source_files': self.source_files, 'header_channel_count': n, 'events': events,
                            'annotations': annotation_summary(events, [p for p, _ in files]),
                            'clock': {'origin': 'first_sample_in_file', 'first_sample': self.origin,
                                      'first_time_seconds': float(self.raw.first_time), 'source_xmin_seconds': float(xmin) if xmin is not None else None,
                                      'cross_source_alignment': 'unverified'},
                            'streams': [{'stream_id': stream_id, 'sampling_frequency_hz': fs,
                                         'sample_index_origin': self.origin, 'sample_count': self.n_times,
                                         'segments': self.segments, 'channels': self.channels,
                                         'reference': 'as_stored', 'processing_applied': []}],
                            'warnings': self.warnings, 'processing_applied': [], 'scientific_validity': 'pending'}

    def describe(self):
        self.assert_unchanged()
        return copy.deepcopy(self.description)

    def metadata(self):
        self.assert_unchanged()
        types = sorted({ch['channel_type'] for ch in self.channels})
        result = {'format': self.kind, 'duration_seconds': self.n_times / self.fs,
                'channels': [{'index': ch['source_index'], 'raw_index': ch['source_index'], 'name': ch['raw_name'],
                              'unit': ch['unit'], 'source_unit': ch['physical_unit'],
                              'unit_source': ch['unit_source'],
                              'channel_type': ch['channel_type'], 'sampling_rate_hz': self.fs} for ch in self.channels],
                'raw_signal_count': len(self.channels), 'annotation_signal_count': 0,
                'size_bytes': sum(f['size_bytes'] for f in self.source_files),
                'reader_id': self.description['reader_id'], 'reader_version': self.description['reader_version'],
                'backend_version': self.description['backend_version'],
                'source_files': public_manifest(self.source_files), 'annotations': copy.deepcopy(self.description['annotations']),
                'modality_evidence': {'value': 'unknown', 'source': 'declared_channel_types',
                                      'channel_types': types, 'requires_confirmation': True},
                'clock': copy.deepcopy(self.description['clock']),
                'continuous_segments': copy.deepcopy(self.segments), 'warnings': self.warnings.copy()}
        if self.kind == 'FIF':
            filters = {key + '_hz': float(self.raw.info[key]) for key in ('highpass', 'lowpass')
                       if self.raw.info.get(key) is not None and math.isfinite(self.raw.info[key])}
            result['declared_filters'] = {**filters, 'source': 'FIF_file_header',
                                          'verified_declaration': True,
                                          'complete_processing_history': False}
        return result

    def read_window(self, stream_id, segment_id, channel_ids, start_sample, stop_sample, representation='physical'):
        import numpy as np
        self.assert_unchanged()
        stream = self.description['streams'][0]
        segment = next((s for s in self.segments if s['segment_id'] == segment_id), None)
        if representation != 'physical':
            raise ValueError('MNE 适配器仅提供原始标定的 SI 数值，不伪造数字 ADC 样本。')
        if (stream_id != stream['stream_id'] or segment is None or
                any(isinstance(v, bool) or not isinstance(v, Integral) for v in (start_sample, stop_sample)) or
                start_sample < segment['start_sample'] or stop_sample > segment['stop_sample'] or start_sample >= stop_sample):
            raise ValueError('读取窗口须位于一个已声明的原生连续段内。')
        lookup = {ch['channel_id']: ch['source_index'] for ch in self.channels}
        if (not isinstance(channel_ids, (list, tuple)) or not channel_ids or
                any(not isinstance(c, str) or c not in lookup for c in channel_ids) or len(set(channel_ids)) != len(channel_ids)):
            raise ValueError('读取通道必须是不同的有效源通道 ID。')
        if len(channel_ids) * (stop_sample - start_sample) * 8 > 256 * 1024 * 1024:
            raise ValueError('读取窗口超过 256 MiB 限制。')
        values = self.raw.get_data(picks=[lookup[c] for c in channel_ids],
                                   start=int(start_sample - self.origin), stop=int(stop_sample - self.origin),
                                   reject_by_annotation=None, verbose='ERROR')
        self.assert_unchanged()
        return np.array(values, dtype=np.float64, copy=True)

    def close(self):
        if hasattr(self, 'raw'):
            self.raw.close()
