"""Versioned upload notice; consent lives with the temporary intake, not a user account."""
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

DOCUMENT = Path(__file__).with_name('web') / 'privacy.html'
VERSION = 'privacy-demo/2026-11-17-' + sha256(DOCUMENT.read_bytes()).hexdigest()[:12]


def describe():
    return {'version': VERSION, 'url': '/privacy', 'required': True}


def receipt(headers):
    if (headers.get('X-QC-Privacy-Consent') != 'agree'
            or headers.get('X-QC-Privacy-Version') != VERSION):
        raise PermissionError('请阅读并勾选当前隐私协议后上传；协议更新时请刷新页面重新确认。')
    return {'version': VERSION, 'accepted_at': datetime.now(timezone.utc).isoformat()}
