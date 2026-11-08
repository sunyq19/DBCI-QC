"""Download one public EEG recording with source and integrity verification."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

URL = 'https://physionet.org/files/eegmmidb/1.0.0/S001/S001R03.edf'
SHA256 = '3427c8d01bff1380bc9ab9f27a35ece2af5dfadf3e291bbc05eb66e4dadbfe2e'


def download(directory):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / 'S001R03.edf'
    if target.exists():
        data = target.read_bytes()
    else:
        with urlopen(URL, timeout=90) as response:
            data = response.read(5 * 1024**2)
        if hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError('Public sample checksum mismatch; no file written')
        with target.open('xb') as stream:
            stream.write(data)
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError('Existing sample differs; it was not overwritten')
    source = {'dataset': 'EEG Motor Movement/Imagery Dataset 1.0.0',
              'source': URL, 'sha256': SHA256,
              'license': 'Open Data Commons Attribution License v1.0',
              'citation': 'Schalk G, McFarland DJ, Hinterberger T, Birbaumer N, Wolpaw JR. BCI2000. IEEE TBME 51(6):1034–1043 (2004).',
              'dataset_url': 'https://physionet.org/content/eegmmidb/1.0.0/',
              'description': '公开头皮 EEG，64 道，160 Hz，125 秒；左右握拳任务。',
              'usage': '上传 EDF，确认头皮 EEG，保留 64 个信号通道；参考构型不清楚时留未知。采用推荐方案、整份检查。无人工伪迹真值，不能据此验证检测准确率。'}
    (directory / 'SOURCE.json').write_text(json.dumps(source, ensure_ascii=False, indent=2) + '\n')
    print(target)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    download(parser.parse_args().output)
