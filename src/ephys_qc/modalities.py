"""Declared execution routes, separate from format readers and product navigation."""
import copy
from .ecog_config import validate_ecog_methods

ROUTES = {
    'scalp_eeg': {'label': '头皮 EEG', 'profile': 'scalp-eeg/1', 'key': None, 'slug': '',
                  'scope_note': '头皮EEG科研检查；准确率和总分仍需独立验证。'},
    'ecog': {'label': 'ECoG', 'profile': 'ecog-basic/1', 'key': 'ecog', 'slug': 'ecog',
             'scope_note': '皮层表面触点基础描述；不迁移头皮判坏阈值。'},
    'seeg': {'label': 'sEEG', 'profile': 'seeg-basic/1', 'key': 'seeg', 'slug': 'seeg',
             'scope_note': '深部触点基础描述；不推断电极杆邻接，不将病理放电判坏。'},
    'extracellular': {'label': 'Neuropixels 电压', 'profile': 'neuropixels-voltage/2', 'key': 'neuropixels', 'slug': 'neuropixels',
                      'scope_note': '已核验SpikeGLX AP/LF或明确设备身份的NWB连续电压；保留源处理声明，不包含单元质量或跨流同步。'},
}
DESCRIPTIVE = frozenset({'ecog', 'seeg', 'extracellular'})


def route(modality):
    if modality not in ROUTES:
        raise ValueError('Unsupported QC modality: ' + str(modality))
    return copy.deepcopy(ROUTES[modality])


def default_methods(modality, metadata=None):
    key = route(modality)['key'] if modality in ROUTES else None
    if not key:
        return {'comparison_groups': None}
    config = {}
    if modality == 'extracellular':
        band = (metadata or {}).get('acquisition', {}).get('stream_band')
        config['psd_window_seconds'] = .1 if band == 'ap' else 1.
    return {key: config, 'comparison_groups': None}


def validate_descriptive_methods(methods, modality, metadata=None):
    if modality not in DESCRIPTIVE:
        raise ValueError('Not a descriptive voltage route')
    if modality == 'ecog':
        return validate_ecog_methods(methods)
    key = route(modality)['key']
    if not isinstance(methods, dict) or set(methods) - {key, 'comparison_groups', 'extensions', 'extension_parameters'}:
        raise ValueError(f'{key} accepts only its own measurement configuration; scalp and other modality parameters are incompatible')
    default = default_methods(modality, metadata)[key]
    actual = methods.get(key, default)
    if not isinstance(actual, dict):
        raise ValueError(f'method_config.{key} must be an object')
    proxy = {k: copy.deepcopy(v) for k, v in methods.items() if k != key}
    proxy['ecog'] = {**default, **actual}
    try:
        checked = validate_ecog_methods(proxy)
    except ValueError as error:
        raise ValueError(str(error).replace('ECoG', key).replace('ecog', key)) from error
    checked[key] = checked.pop('ecog')
    return checked


def validate_analysis_channels(metadata, indices, modality):
    """Do not turn a label change into permission to analyze conflicting types."""
    if modality not in ROUTES:
        return
    channels = {c.get('index', c.get('source_index')): c for c in metadata['channels']}
    if modality == 'scalp_eeg':
        incompatible = {'ecog', 'seeg', 'dbs', 'neuropixels', 'stim', 'misc', 'eog', 'ecg', 'emg'}
        if any(channels[i].get('channel_type') in incompatible for i in indices):
            raise ValueError('头皮EEG选道包含文件声明的其他信号类型。')
        return
    if modality == 'extracellular':
        acquisition = metadata.get('acquisition') or {}
        if metadata.get('format') == 'NWB':
            from .source_selection import require_selected_voltage
            require_selected_voltage(metadata)
            if acquisition.get('neuropixels_device_declared') is not True:
                raise ValueError('NWB没有明确的Neuropixels设备身份，不能进入该路线。')
        elif metadata.get('format') != 'SpikeGLX' or acquisition.get('stream_band') not in {'ap', 'lf'}:
            raise ValueError('Neuropixels检查仅接入已核验SpikeGLX AP/LF或NWB连续电压；未接入其他细胞外记录或已分选单元。')
        if any(channels[i].get('channel_type') != 'neuropixels' or channels[i].get('channel_type_source') != 'file_declared' for i in indices):
            raise ValueError('Neuropixels选道仅接受明确声明的神经电压通道；同步字不得进入分析。')
    else:
        def compatible(channel):
            kind = channel.get('channel_type')
            return kind in {None, 'unknown', modality} or (kind == 'eeg' and channel.get('channel_type_source') == 'reader_default' and metadata.get('format') == 'BrainVision')
        if not all(compatible(channels[i]) for i in indices):
            raise ValueError(f'{route(modality)["label"]}选道包含已声明的其他信号类型；不得改名套用。')
