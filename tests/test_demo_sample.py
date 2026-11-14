"""Network fallback must retain the same public sample and integrity boundary."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import URLError

import pytest


@pytest.fixture
def sample(monkeypatch):
    path = Path(__file__).resolve().parents[1] / 'scripts/demo_sample.py'
    spec = importlib.util.spec_from_file_location('demo_sample_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, 'SHA256', hashlib.sha256(b'verified sample').hexdigest())
    return module


def test_official_mirror_on_network_failure(sample, monkeypatch, tmp_path):
    addresses = []
    def open_url(address, **kwargs):
        addresses.append(address)
        if address == sample.URL:
            raise URLError('network timeout')
        return io.BytesIO(b'verified sample')
    monkeypatch.setattr(sample, 'urlopen', open_url)
    assert sample.download(tmp_path).read_bytes() == b'verified sample'
    assert addresses == [sample.URL, sample.MIRROR_URL]
    source = json.loads((tmp_path / 'SOURCE.json').read_text())
    assert source['source'] == sample.URL
    assert source['downloaded_from'] == sample.MIRROR_URL


def test_wrong_download_is_not_written_or_masked_by_fallback(sample, monkeypatch, tmp_path):
    addresses = []
    def open_url(address, **kwargs):
        addresses.append(address)
        return io.BytesIO(b'wrong sample')
    monkeypatch.setattr(sample, 'urlopen', open_url)
    with pytest.raises(ValueError, match='checksum'):
        sample.download(tmp_path)
    assert addresses == [sample.URL]
    assert not (tmp_path / 'S001R03.edf').exists()


def test_existing_bad_sample_is_preserved(sample, monkeypatch, tmp_path):
    target = tmp_path / 'S001R03.edf'
    target.write_bytes(b'original')
    monkeypatch.setattr(sample, 'urlopen', lambda *a, **kw: pytest.fail('must not download'))
    with pytest.raises(ValueError, match='not overwritten'):
        sample.download(tmp_path)
    assert target.read_bytes() == b'original'
