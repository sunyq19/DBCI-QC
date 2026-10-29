"""Technical EDF inventory; paths stay in ignored, machine-local configuration."""
from pathlib import Path
import math


def inspect_header(path):
    path = Path(path)
    with path.open('rb') as stream:
        head = stream.read(256)
        if len(head) != 256 or head[:8].strip() not in {b'0', b'\xffBIOSEMI'}:
            raise ValueError('文件不是有效的 EDF/EDF+ 或 BDF。')
        kind = 'BDF' if head[:8] == b'\xffBIOSEMI' else 'EDF'
        width = 3 if kind == 'BDF' else 2
        try:
            n, header_bytes = int(head[252:256]), int(head[184:192])
            records, duration = int(head[236:244]), float(head[244:252])
        except ValueError:
            raise ValueError('EDF 技术字段无效。') from None
        if not 1 <= n <= 4096 or header_bytes != 256 + 256 * n:
            raise ValueError('EDF 通道数或头长度无效。')
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError('EDF 记录时长无效；注释文件不能作为波形输入。')
        if b'EDF+D' in head[192:236] or b'BDF+D' in head[192:236]:
            raise ValueError('当前读取适配器尚不支持不连续 EDF+D。')
        block = stream.read(256 * n)
    if len(block) != 256 * n:
        raise ValueError('EDF 文件头不完整。')

    def field(offset, width):
        return [block[offset * n + i * width:offset * n + (i + 1) * width].decode('latin1').strip() for i in range(n)]

    names, units = field(0, 16), field(96, 8)
    try:
        samples = list(map(int, field(216, 8)))
        pmin, pmax = list(map(float, field(104, 8))), list(map(float, field(112, 8)))
        dmin, dmax = list(map(int, field(120, 8))), list(map(int, field(128, 8)))
    except ValueError:
        raise ValueError('EDF 采样率或缩放字段无效。') from None
    if any(v <= 0 for v in samples):
        raise ValueError('EDF 每记录采样点数无效。')
    payload, record_bytes = path.stat().st_size - header_bytes, width * sum(samples)
    if payload < 0 or payload % record_bytes:
        raise ValueError('EDF 数据长度不是完整记录，可能截断。')
    if records == -1:
        records = payload // record_bytes
    if records <= 0 or payload != records * record_bytes:
        raise ValueError('EDF 数据长度与文件头不一致。')
    channels = []
    for raw_index, name in enumerate(names):
        if name.lower().startswith(('edf annotations', 'bdf annotations')):
            continue
        lo, hi = pmin[raw_index], pmax[raw_index]
        if not math.isfinite(lo) or not math.isfinite(hi) or lo == hi or dmin[raw_index] >= dmax[raw_index]:
            raise ValueError(f'EDF 第 {raw_index} 道缩放范围无效。')
        # Selection indices are EDF source identities, not compact table rows.
        # An annotation signal can precede or separate numerical signals.
        channels.append({'index': raw_index, 'raw_index': raw_index, 'name': name,
                         'unit': units[raw_index], 'sampling_rate_hz': samples[raw_index] / duration})
    return {'format': kind, 'duration_seconds': records * duration, 'channels': channels,
            'raw_signal_count': n, 'size_bytes': path.stat().st_size,
            'annotation_signal_count': n - len(channels), 'complete_records': records}
