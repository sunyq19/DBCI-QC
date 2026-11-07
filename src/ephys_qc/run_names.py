"""Human-readable run titles; never part of analysis configuration or identity."""
from datetime import datetime
import re
import unicodedata

MAX_NAME_LENGTH = 120


def resolve_run_name(value, label, scope='recording'):
    if value is not None and not isinstance(value, str):
        raise ValueError('质检名称须为文字。')
    value = value or ''
    if any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in value):
        raise ValueError('质检名称不能包含换行或隐藏控制字符。')
    value = value.strip()
    if len(value) > MAX_NAME_LENGTH:
        raise ValueError('质检名称最多 120 个字符。')
    if value:
        return value
    stem = re.sub(r'(?i)\.(edf|bdf|vhdr|set|fif|nwb|bin|meta|zip)$', '', str(label or '数据'))
    stem = ''.join(c for c in stem if unicodedata.category(c) not in {'Cc', 'Cf', 'Cs'})[:72]
    kind = {'recording': '整份检查', 'window': '片段检查', 'dataset': '资料检查'}.get(scope, '质检')
    return f'{stem} · {kind} · {datetime.now().astimezone():%m-%d %H:%M}'
