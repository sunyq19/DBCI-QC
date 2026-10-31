"""Local file intake: inspect bytes, then require explicit channel-role confirmation.

No waveform leaves the host, no arbitrary server path is accepted, and name-based
role suggestions never register a record or start an analysis by themselves.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import copy
import hashlib
import json
import re
import shutil
import zipfile
import uuid

from ephys_qc.readers import inspect_recording, list_readers
from ephys_qc.modalities import ROUTES, DESCRIPTIVE, default_methods, validate_analysis_channels
from ephys_qc.source_selection import reader_kwargs, require_selected_voltage
from uploads import prepare_source, source_manifest
from ephys_qc.tagging import validate_context

MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MODALITIES = {'unknown', 'scalp_eeg', 'ecog', 'seeg', 'extracellular', 'other'}
REFERENCE_SCHEMES = {'unknown', 'common_reference', 'linked_ears', 'bipolar', 'mixed'}


def _save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def _load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _voltage(channel):
    return str(channel.get('unit', '')).lower().strip().replace('μ', 'u').replace('µ', 'u') in {'v', 'mv', 'uv', 'nv'}


def registration_selection(metadata, eeg, refs, modality):
    """Validate roles independently of whether an analysis window exists."""
    require_selected_voltage(metadata)
    channels = {c['index']: c for c in metadata['channels']}
    if not isinstance(eeg, list) or not eeg or any(type(i) is not int or i not in channels for i in eeg) or len(set(eeg)) != len(eeg):
        raise ValueError('请选择至少一道不同的信号通道。')
    if not isinstance(refs, dict) or set(refs) - {'eog', 'ecg', 'emg'} or any(type(i) is not int or i not in channels for i in refs.values()):
        raise ValueError('辅助通道索引或角色无效。')
    if len(set(refs.values())) != len(refs) or set(eeg) & set(refs.values()):
        raise ValueError('同一通道不能兼任两个角色。')
    selected = [channels[i] for i in eeg + list(refs.values())]
    if not all(_voltage(c) for c in selected):
        raise ValueError('所选通道须有明确电压单位。')
    incompatible = {'seeg', 'ecog', 'neuropixels', 'dbs', 'mag', 'grad', 'ref_meg', 'stim', 'fnirs_cw_amplitude', 'hbo', 'hbr'}
    if modality == 'scalp_eeg' and any(channels[i].get('channel_type') in incompatible for i in eeg):
        raise ValueError('所选通道包含已声明的非头皮EEG类型。')
    if modality in DESCRIPTIVE:
        validate_analysis_channels(metadata, eeg, modality)
    rates = {c['sampling_rate_hz'] for c in selected}
    if len(rates) != 1:
        raise ValueError('EEG and auxiliary channels must share one native sample clock; no automatic resampling')
    fs = next(iter(rates))
    max_samples = min(round(120 * fs), (256 * 1024 * 1024) // (len(selected) * 8))
    segments = metadata.get('continuous_segments')
    start, duration = 0., min(max_samples / fs, metadata['duration_seconds'])
    if segments is not None:
        usable = [s for s in segments if s['stop_sample'] > s['start_sample']]
        if usable:
            first = min(usable, key=lambda s: s['recording_start_seconds'])
            start = first['recording_start_seconds']
            duration = min(max_samples, first['stop_sample'] - first['start_sample']) / fs
        else:
            # Registration succeeds even if all samples are declared missing.
            # The planner still refuses analysis of such a recording.
            duration = 0.
    result = {'eeg_indices': eeg, 'reference_indices': refs,
              'start_seconds': start, 'duration_seconds': duration}
    if metadata.get('format') == 'NWB':
        result['stream_id'] = metadata['selected_stream_id']
    return result


def _modality_proposal(metadata, analysis_indices):
    """Propose anatomy only from file-declared signal types, never from labels.

    The current reader records native FIF types as ``file_declared``. In
    contrast, BrainVision's default ``eeg`` and EEGLAB's inferred types are not
    anatomical evidence. Auxiliary, miscellaneous and trigger channels do not
    vote on modality. Other explicitly declared neural modalities (e.g. MEG)
    prevent a mixed recording from being proposed as pure scalp EEG or ECoG.
    ``channel_groups`` contains original source indices, not analysis offsets.
    """
    brain_types = {'eeg': 'scalp_eeg', 'ecog': 'ecog', 'seeg': 'seeg', 'neuropixels': 'extracellular'}
    other_neural = {'mag', 'grad', 'ref_meg', 'dbs', 'fnirs_cw_amplitude',
                    'fnirs_fd_ac_amplitude', 'fnirs_fd_phase', 'fnirs_od', 'hbo', 'hbr'}
    groups, unresolved = {}, []
    for channel in metadata['channels']:
        declared = channel.get('channel_type', channel.get('type', channel.get('kind')))
        if channel.get('channel_type_source') == 'file_declared' and (declared in brain_types or declared in other_neural):
            modality = brain_types.get(declared, 'other')
            groups.setdefault(modality, []).append(channel['index'])
        elif channel['index'] in analysis_indices:
            unresolved.append(channel['index'])
    grouped = [{'modality': key, 'indices': sorted(groups[key])}
               for key in ('scalp_eeg', 'ecog', 'seeg', 'extracellular', 'other') if key in groups]
    source = 'metadata.channels.channel_type; channel_type_source=file_declared'
    proposed = 'unknown'
    if len(groups) > 1:
        status, reason = 'mixed', '文件明确声明了多种神经信号类型；请按采集资料选择同一模态的通道，不合并套用质控。'
    elif groups and unresolved:
        status, reason = 'unknown', '只有部分建议分析通道具有文件明确声明的模态；其余通道须核实，不能将部分声明扩展为整份记录。'
    elif len(groups) == 1 and next(iter(groups)) in brain_types.values():
        proposed = next(iter(groups))
        status, reason = 'file_declared', '模态建议来自文件明确声明的通道类型，仍须确认采集资料与分析通道；不等于已经登记或可执行。'
    elif groups:
        status, reason = 'unknown', '文件声明的神经信号类型不属于当前可提议的头皮EEG、ECoG或sEEG；请根据采集资料确认。'
    else:
        status, reason = 'unknown', '未获得文件明确声明的神经信号模态；通道名称、读取器默认或推测类型不能证明电极采集位置。'
        source = 'no_reliable_file_declared_neural_channel_type'
    if groups and unresolved:
        grouped.append({'modality': 'unknown', 'indices': sorted(unresolved)})
    return proposed, {'status': status, 'source': source, 'reason': reason, 'channel_groups': grouped}


def suggestions(metadata):
    """Return unconfirmed channel-role and modality proposals from read metadata.

    API: ``modality`` is a proposal and ``modality_evidence`` explains its
    ``status`` (file_declared/unknown/mixed), ``source``, ``reason`` and source
    index ``channel_groups``. Neither field confirms, registers or executes QC.
    Mixed declared neural groups leave analysis selection empty, requiring an
    explicit single-group choice. A reliable group plus uncertain analysis
    candidates keeps only the reliable group, but the modality stays unknown.
    File-declared channel types take precedence over name heuristics: a declared
    MISC channel named EKG1 stays unassigned, and EOG/ECG/EMG keep their roles.
    Default/inferred brain types may still use names for auxiliary-role
    candidates; e.g. BrainVision default EEG named ECG is proposed as ECG.
    These name-based role suggestions never provide anatomical evidence.
    This function is pure and does not rewrite existing intake/record snapshots.
    """
    eeg, auxiliaries = [], {}
    # Reserve known auxiliary roles before considering any label candidates,
    # independent of whether the actual auxiliary appears earlier in the file.
    for reliable in (True, False):
        for channel in metadata['channels']:
            declared = channel.get('channel_type', channel.get('type', channel.get('kind')))
            if (_voltage(channel) and declared in {'eog', 'ecg', 'emg'} and
                    (channel.get('channel_type_source') == 'file_declared') == reliable):
                auxiliaries.setdefault(declared, channel['index'])
    warnings = ['通道角色优先保留已声明类型，未声明时仅按名称提出角色建议；模态及参考仍须确认，不据名称推断疾病。',
                '文件标注仅提取原始事件描述，不据此推断疾病、睡眠阶段或质量标签。']
    for channel in metadata['channels']:
        if not _voltage(channel):
            continue
        name = channel['name'].upper().strip()
        declared = channel.get('channel_type', channel.get('type', channel.get('kind')))
        reliable_type = channel.get('channel_type_source') == 'file_declared'
        if declared in {'eog', 'ecg', 'emg'}:
            auxiliaries.setdefault(declared, channel['index'])
            continue
        if reliable_type and declared in {'eeg', 'ecog', 'seeg', 'neuropixels'}:
            eeg.append(channel['index'])
            continue
        if reliable_type and declared not in {None, '', 'unknown'}:
            # Preserve explicit MISC, stimulus and other signal types even if
            # their labels happen to resemble EEG/ECG/EOG/EMG channel names.
            continue
        match = re.search(r'\b(EOG|ECG|EKG|EMG)\b', name)
        if match:
            role = {'EKG': 'ecg'}.get(match[1], match[1].lower())
            if role not in auxiliaries:
                auxiliaries[role] = channel['index']
            continue
        # Iz is already a complete midline electrode name (unlike F/C/...,
        # which need a number or z). Keep EDF dot padding and montage suffixes.
        if ((metadata.get('format') == 'NWB' and declared in {None, 'unknown'}) or
                declared in {'eeg', 'ecog', 'seeg', 'neuropixels'} or name.startswith('EEG') or re.fullmatch(r'[A-H][1-9][0-9]?', name) or re.match(r'^(?:IZ(?:[ .-]|$)|(?:FP|AF|FC|FT|CP|TP|PO|F|C|T|P|O)(?:\d{1,2}|Z)(?:[ .-]|$))', name)):
            eeg.append(channel['index'])
    modality, evidence = _modality_proposal(metadata, eeg)
    trusted_groups = [g for g in evidence['channel_groups'] if g['modality'] != 'unknown']
    if evidence['status'] == 'mixed':
        eeg = []
        warnings.append('文件含多种已声明神经模态，尚未建议分析通道；请明确选择一个通道组。')
    elif evidence['status'] == 'unknown' and len(trusted_groups) == 1:
        trusted = set(trusted_groups[0]['indices'])
        eeg = [index for index in eeg if index in trusted]
    rates = Counter(c['sampling_rate_hz'] for c in metadata['channels'] if c['index'] in eeg)
    if len(rates) > 1:
        warnings.append('建议EEG含多个原生采样率；确认时必须选择同一采样率的EEG和辅助导联，本版不自动重采样。')
    elif rates:
        fs = next(iter(rates))
        by_index = {c['index']: c for c in metadata['channels']}
        for role, index in list(auxiliaries.items()):
            if by_index[index]['sampling_rate_hz'] != fs:
                del auxiliaries[role]
                warnings.append(f'{role.upper()}名称候选与EEG采样率不同，未自动选入辅助导联。')
    if metadata.get('format') == 'NWB' and not metadata.get('selected_stream_id'):
        warnings.append('请先选择一个可读取的连续电压信号；Units表仅作内容识别，不进入波形质控。')
    elif not eeg:
        warnings.append('无法从名称提出EEG角色建议；请根据实验资料选择至少一道EEG。')
    return {'eeg_indices': eeg, 'reference_indices': auxiliaries,
            'reference_scheme': 'unknown', 'modality': modality, 'modality_evidence': evidence,
            'context_tags': {'disease': 'unknown', 'age_group': 'unknown', 'task': 'unknown'}}, warnings


class IntakeStore:
    def __init__(self, runtime_root):
        self.root = Path(runtime_root).resolve() / 'intakes'
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def _directory(self, identifier):
        if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier):
            raise KeyError(identifier)
        return self.root / identifier

    def get(self, identifier):
        path = self._directory(identifier) / 'intake.json'
        if not path.is_file():
            raise KeyError(identifier)
        return _load(path)

    def receive(self, filename, length, stream):
        if type(length) is not int or not 0 < length <= MAX_UPLOAD_BYTES:
            raise ValueError('单个文件须大于0字节且不超过512 MiB；文件只保存到本机。')
        if not isinstance(filename, str) or not filename or len(filename) > 240 or any(ord(c) < 32 for c in filename):
            raise ValueError('文件名无效。')
        # The original display name never forms a filesystem path.
        filename = filename.replace('\\', '/').rsplit('/', 1)[-1]
        if not filename:
            raise ValueError('文件名无效。')
        identifier = uuid.uuid4().hex
        directory = self._directory(identifier)
        directory.mkdir(mode=0o700)
        pending = directory / 'upload.partial'
        digest = hashlib.sha256()
        try:
            remaining = length
            with pending.open('xb') as output:
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise ValueError('文件上传未完成，请重新选择文件；未登记部分内容。')
                    output.write(block)
                    digest.update(block)
                    remaining -= len(block)
            source = prepare_source(pending, filename, directory)
            metadata = inspect_recording(source)
            files = source_manifest(source, metadata)
            proposal, warnings = suggestions(metadata)
            value = {'id': identifier, 'status': 'needs_confirmation', 'filename': filename,
                     'sha256': digest.hexdigest(), 'metadata': metadata,
                     'entry_file': str(source.relative_to(directory)),
                     'source_sha256': _hash(source),
                     'source_files': [{'name': str(Path(item['path']).relative_to(directory)), 'sha256': item['sha256']} for item in files],
                     'suggestions': proposal, 'warnings': warnings, 'selection_revision': 0,
                     'received_at': datetime.now(timezone.utc).isoformat(),
                     'capabilities': {'supported_modality': 'scalp_eeg', 'supported_modalities': list(ROUTES), 'inspection_modalities': sorted(MODALITIES),
                                      'readers': list_readers(), 'max_window_seconds': 120,
                                      'max_upload_bytes': MAX_UPLOAD_BYTES}}
            _save(directory / 'intake.json', value)
            return value
        except Exception as error:
            # This UUID directory was created by this request; no existing data is removed.
            shutil.rmtree(directory)
            if isinstance(error, (zipfile.BadZipFile, NotImplementedError, EOFError, FileExistsError, IsADirectoryError, NotADirectoryError)):
                raise ValueError('文件或ZIP不完整，或使用了不支持的编码。') from error
            raise

    def select_stream(self, identifier, body):
        if not isinstance(body, dict) or set(body) != {'stream_id'} or not isinstance(body['stream_id'], str):
            raise ValueError('请选择文件中列出的NWB信号。')
        intake = self.get(identifier)
        if intake['status'] != 'needs_confirmation':
            raise ValueError('已登记记录的NWB信号不可覆盖；请重新提交文件以检查其他信号。')
        metadata = intake['metadata']
        streams = {item['stream_id']: item for item in metadata.get('available_streams', [])}
        selected = streams.get(body['stream_id'])
        if metadata.get('format') != 'NWB' or not selected or selected.get('status') != 'available':
            raise ValueError('所选NWB信号不可读取，或不属于这份文件。')
        directory = self._directory(identifier)
        source = (directory / intake['entry_file']).resolve()
        if not source.is_relative_to(directory.resolve()) or _hash(source) != intake['source_sha256']:
            raise ValueError('本地接收副本的指纹发生变化，请重新提交原文件。')
        metadata = inspect_recording(source, stream_id=body['stream_id'])
        require_selected_voltage(metadata)
        proposal, warnings = suggestions(metadata)
        intake.update(metadata=metadata, suggestions=proposal, warnings=warnings,
                      selection_revision=intake.get('selection_revision', 0) + 1)
        _save(directory / 'intake.json', intake)
        return intake

    def confirm(self, identifier, body):
        allowed = {'modality', 'reference_scheme', 'eeg_indices', 'reference_indices',
                   'context_tags', 'label', 'source_note', 'confirmed', 'selected_stream_id'}
        if not isinstance(body, dict) or set(body) - allowed or body.get('confirmed') is not True:
            raise ValueError('请明确确认模态、通道角色和参考信息；不接受其他登记字段。')
        directory = self._directory(identifier)
        intake = self.get(identifier)
        if intake['status'] == 'registered':
            # Retrying an identical confirmation is safe; changed metadata needs a new intake.
            existing = _load(directory / 'confirmation.json')
            if existing != body:
                raise ValueError('这份文件已登记；不能通过重复确认覆盖历史来源。')
            return _load(directory / 'record.json')
        if intake['metadata'].get('format') == 'NWB':
            require_selected_voltage(intake['metadata'])
            if body.get('selected_stream_id') != intake['metadata']['selected_stream_id']:
                raise ValueError('NWB信号选择已变化，请重新核对当前信号后确认。')
        elif 'selected_stream_id' in body:
            raise ValueError('只有NWB记录接受信号对象选择。')
        modality = body.get('modality')
        if not isinstance(modality, str) or modality not in MODALITIES or modality == 'unknown':
            raise ValueError('请根据采集资料确认信号模态；不能仅由文件格式推断。')
        reference = body.get('reference_scheme')
        if not isinstance(reference, str) or reference not in REFERENCE_SCHEMES:
            raise ValueError('请选择参考构型；不清楚时选择未知。')
        eeg = body.get('eeg_indices')
        refs = body.get('reference_indices', {})
        source = (directory / intake.get('entry_file', 'source.edf')).resolve()
        if not source.is_relative_to(directory.resolve()):
            raise ValueError('主文件路径不在当前接收目录中。')
        if _hash(source) != intake.get('source_sha256', intake['sha256']):
            raise ValueError('本地接收副本的指纹发生变化，请重新提交原文件。')
        for item in intake.get('source_files', []):
            member = (directory / item['name']).resolve()
            if not member.is_relative_to(directory.resolve()) or not member.is_file() or _hash(member) != item['sha256']:
                raise ValueError('本地配套文件的指纹发生变化，请重新提交原记录。')
        metadata = inspect_recording(source, **reader_kwargs(intake['metadata']))
        files = source_manifest(source, metadata)
        by_index = {c['index']: c for c in metadata['channels']}
        if not isinstance(eeg, list) or not eeg or any(type(i) is not int or i not in by_index for i in eeg) or len(set(eeg)) != len(eeg):
            raise ValueError('请明确选择至少一道不同的EEG通道。')
        if not isinstance(refs, dict) or set(refs) - {'ecg', 'eog', 'emg'} or any(type(i) is not int or i not in by_index for i in refs.values()):
            raise ValueError('辅助导联只接受已存在的ECG/EOG/EMG通道索引。')
        if len(set(refs.values())) != len(refs) or set(eeg) & set(refs.values()):
            raise ValueError('同一通道不能同时充当EEG与辅助导联，也不能兼任两个辅助角色。')
        if not all(_voltage(by_index[i]) for i in eeg + list(refs.values())):
            raise ValueError('选中信号的物理单位必须能明确换算成电压；请排除标记、呼吸、温度等非电压信号。')
        label = body.get('label') or intake['filename']
        note = body.get('source_note') or '来源说明尚未补充。'
        if not isinstance(label, str) or not label.strip() or len(label) > 160 or not isinstance(note, str) or len(note) > 2000:
            raise ValueError('记录名称最多160字，来源说明最多2000字。')
        record = {'id': 'local-' + identifier, 'label': label.strip(), 'source_path': str(source),
                  'record_family': 'local-' + identifier, 'record_revision': 1,
                  'expected_sha256': _hash(source), 'expected_source_files': files, 'dataset_id': 'local-submitted',
                  'profile_id': 'user_confirmed_' + modality, 'modality': modality,
                  'modality_source': '用户在本机提交后明确确认；文件头本身不证明电极所在位置。',
                  'description': '本机提交；技术头已读取，通道角色和参考由用户确认。',
                  'metadata': metadata, 'reference_scheme': reference,
                  'reference_evidence': '用户明确声明，未从文件名或波形推断；未自动重参考。',
                  'verified_electrode_coordinates': False, 'verified_epochs': False,
                  'preprocessing': {'verified': False},
                  'provenance': {'name': '本机提交：' + intake['filename'], 'url': '',
                                 'license': '用户数据；未声明再分发许可', 'note': note,
                                 'received_at': intake['received_at']},
                  'data_usage': {'typical_use': note, 'annotations': '文件内标注仅作技术信息提取；尚未登记为经过语义核实的任务、分期或质量标签。',
                                 'annotation_limits': '用户背景声明不是临床诊断或伪迹真值。'},
                  'default_config': {'selection': registration_selection(metadata, eeg, refs, modality),
                                     'context_tags': validate_context({}, body.get('context_tags')),
                                     'method_config': (default_methods(modality, metadata) if modality in DESCRIPTIVE else
                                                       {'comparison_groups': ['user_confirmed_reference'] * len(eeg)
                                                       if reference in {'common_reference', 'linked_ears'} else None})},
                  'intake_confirmation': {'confirmed': True, 'technical_header_automatic': True,
                                          'roles_reference_modality': 'user_confirmed',
                                          'automatic_cleaning': False}}
        filters = metadata.get('declared_filters') or {}
        if filters.get('verified_declaration') is True:
            record['preprocessing'] = {'verified': True, 'source': 'file_header_declaration',
                'highpass_hz': filters.get('highpass_hz'), 'lowpass_hz': filters.get('lowpass_hz'),
                'note': '保留文件声明；未独立测量实际滤波传递函数。'}
        _save(directory / 'record.json', record)
        _save(directory / 'confirmation.json', copy.deepcopy(body))
        intake.update(status='registered', input_id=record['id'])
        _save(directory / 'intake.json', intake)
        return record

    def registered(self):
        records = []
        for path in sorted(self.root.glob('*/intake.json')):
            intake = _load(path)
            if intake.get('status') == 'registered':
                record = _load(path.parent / 'record.json')
                # Technical facts were frozen at registration. Availability is
                # checked by Store without making one missing input fatal.
                records.append(record)
        return records

    def pending(self):
        return sorted([_load(p) for p in self.root.glob('*/intake.json')
                       if _load(p).get('status') == 'needs_confirmation'],
                      key=lambda item: item['received_at'], reverse=True)
