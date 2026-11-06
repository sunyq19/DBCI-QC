"""Bounded, selective loading of already-authorized visualization evidence."""
import json
from pathlib import Path

SMALL_LIMIT = 64 * 1024**2
SPECTRAL_LIMIT = 1024**3
LINE_FIELDS = (
    'channel_id', 'channel_index', 'channel_name', 'start_sample',
    'stop_sample', 'status', 'flagged', 'amplitude_uv',
)


def read_evidence(path):
    """The caller must authorize the artifact path before calling this function.

    Spectral evidence can contain large per-frequency test arrays that are not
    needed for these plots. Stream observations one at a time and retain only
    the original values used to count distinct channel-windows.
    """
    path = Path(path)
    size = path.stat().st_size
    spectral = path.name.endswith('M04_spectral.json')
    if size > (SPECTRAL_LIMIT if spectral else SMALL_LIMIT):
        raise ValueError('证据超过本次展示读取范围。')
    if not spectral:
        with path.open(encoding='utf-8') as stream:
            return json.load(stream)
    try:
        import ijson
    except ImportError:
        if size > SMALL_LIMIT:
            raise ValueError('大型频谱图需要安装 visualization 可选依赖。') from None
        with path.open(encoding='utf-8') as stream:
            payload = json.load(stream)
        return {
            'psd': payload.get('psd', {}),
            'line_noise': {'observations': [
                {k: row[k] for k in LINE_FIELDS if k in row}
                for row in payload.get('line_noise', {}).get('observations', [])
            ]},
        }
    try:
        # Each pass parses the complete JSON without building unrelated arrays.
        with path.open('rb') as stream:
            psds = list(ijson.items(stream, 'psd', use_float=True))
        with path.open('rb') as stream:
            observations = [
                {k: row[k] for k in LINE_FIELDS if k in row}
                for row in ijson.items(stream, 'line_noise.observations.item', use_float=True)
            ]
    except (ijson.JSONError, OverflowError) as exc:
        raise ValueError('频谱证据不是有效的 JSON 数值对象。') from exc
    return {'psd': psds[0] if psds else {}, 'line_noise': {'observations': observations}}
