"""Registered native-clock readers. Importing this module loads no scientific library.

Format support does not confirm scalp EEG modality or clinical interpretation.
"""
from pathlib import Path
import copy

SUPPORTED_FORMATS = frozenset({'EDF', 'EDF+', 'BDF', 'BrainVision', 'EEGLAB', 'FIF', 'SpikeGLX', 'NWB'})

_SPECS = [
    {'id': 'native_edf_bdf', 'name': 'EDF/BDF 原生采样流', 'formats': ['EDF', 'BDF'],
     'extensions': ['.edf', '.bdf'], 'multifile': False,
     'limitations': ['不支持 EDF+D/BDF+D；不同采样流不能隐式重采样。']},
    {'id': 'mne_brainvision', 'name': 'BrainVision', 'formats': ['BrainVision'],
     'extensions': ['.vhdr'], 'multifile': True,
     'limitations': ['主文件、MarkerFile 和 DataFile 须位于同一目录。', '当前后端对重复通道名明确拒绝，不合并或静默改名。']},
    {'id': 'mne_eeglab', 'name': 'EEGLAB', 'formats': ['EEGLAB'],
     'extensions': ['.set'], 'multifile': True,
     'limitations': ['只接入连续记录；外置 FDT 须在同一目录；不执行历史脚本或 ICA。']},
    {'id': 'mne_fif', 'name': 'FIF', 'formats': ['FIF'],
     'extensions': ['.fif'], 'multifile': False,
     'limitations': ['只接入单文件原始记录；split FIF 暂不接入；保留非 EEG 通道类型。']},
    {'id': 'native_spikeglx', 'name': 'SpikeGLX · Neuropixels 原始流', 'formats': ['SpikeGLX'],
     'extensions': ['.ap.bin', '.lf.bin'], 'multifile': True,
     'limitations': ['单个 AP 或 LF .bin 须配同名 .meta；当前接入 NP1 型号0及 NP2 型号21/24。',
                    '不接入任意二进制、压缩 cbin、跨流自动同步或 spike sorting。']},
    {'id': 'pynwb_electrical_series', 'name': 'NWB · 连续电压流', 'formats': ['NWB'],
     'extensions': ['.nwb'], 'multifile': False,
     'limitations': ['支持自包含 NWB 2 / HDF5 的连续 ElectricalSeries；多个可用流须明确选择。',
                    '核验原生时钟、电压单位及电极映射；不接入不等距时钟、外部链接或 spike/unit 质控。']},
]


def list_readers():
    return [{**copy.deepcopy(s), 'status': 'available'} for s in _SPECS]


def detect_format(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('输入必须是本地普通文件，不能是符号链接。')
    # SpikeGLX has no binary magic. Its registered suffix + strict companion
    # metadata take precedence over coincidental ASCII-looking ADC samples.
    if path.name.lower().endswith(('.ap.bin', '.lf.bin')):
        return 'SpikeGLX'
    with path.open('rb') as source:
        magic = source.read(8)
    if path.suffix.lower() == '.nwb':
        if magic != b'\x89HDF\r\n\x1a\n':
            raise ValueError('NWB 输入须为 HDF5 文件；当前不接入 Zarr 或其他容器。')
        return 'NWB'
    if magic.strip() == b'0':
        return 'EDF'
    if magic == b'\xffBIOSEMI':
        return 'BDF'
    kinds = {'.vhdr': 'BrainVision', '.set': 'EEGLAB', '.fif': 'FIF'}
    if path.suffix.lower() not in kinds:
        raise ValueError('未注册的记录格式。支持 EDF、BDF、BrainVision、EEGLAB、单文件 FIF、SpikeGLX AP/LF + meta 和 NWB 2 / HDF5。')
    return kinds[path.suffix.lower()]


def open_reader(path, record_id='inspection', *, stream_id=None):
    try:
        kind = detect_format(path)
        if kind == 'NWB':
            from .nwb_reader import NWBReader
            return NWBReader(path, record_id, stream_id=stream_id)
        if stream_id is not None:
            raise ValueError('仅 NWB 容器支持在打开文件时指定流；其他格式使用原生读取窗口选择。')
        if kind in {'EDF', 'BDF'}:
            from .native import NativeReader
            return NativeReader(path, record_id)
        if kind == 'SpikeGLX':
            from .spikeglx_reader import SpikeGLXReader
            return SpikeGLXReader(path, record_id)
        from .mne_reader import MNEReader
        return MNEReader(path, record_id, kind)
    except MemoryError:
        raise
    except Exception as error:
        # Reader/parser failures are input errors, including malformed INI keys
        # and MAT/FIF structures. Do not turn a parser KeyError into HTTP 404 or
        # expose machine-local paths through library exception text.
        source = Path(path)
        message = str(error).replace(str(source.resolve()), source.name)
        if str(source.resolve().parent) != '/':
            message = message.replace(str(source.resolve().parent), '[package]')
        raise ValueError(message or 'Unable to decode recording structure') from error


def inspect_recording(path, *, stream_id=None):
    """Return JSON technical metadata; no signal analysis and no modality guesses.

    Non-EDF formats require the configured scientific Python environment. Internal
    reader descriptions carry full file paths; public metadata uses basenames.
    """
    reader = open_reader(path, 'inspection', stream_id=stream_id)
    try:
        return reader.metadata()
    finally:
        reader.close()
