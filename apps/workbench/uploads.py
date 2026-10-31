"""Bounded local recording packages; no archive names become host paths."""
from pathlib import Path, PurePosixPath
import hashlib
import stat
import zipfile

MAX_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 64
ENTRY_SUFFIXES = {'.edf', '.bdf', '.vhdr', '.set', '.fif', '.meta', '.nwb'}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def prepare_source(upload, filename, directory):
    """Return the one recording entry, preserving safe paired-file references."""
    upload, directory = Path(upload), Path(directory)
    if zipfile.is_zipfile(upload):
        payload = directory / 'payload'
        payload.mkdir(mode=0o700)
        with zipfile.ZipFile(upload) as archive:
            members = archive.infolist()
            if not members or len(members) > MAX_MEMBERS:
                raise ValueError('ZIP须包含1至64个条目，一次只提交一份记录。')
            planned, seen, total = [], set(), 0
            for info in members:
                name = info.filename
                path = PurePosixPath(name)
                if (not name or '\\' in name or ':' in name or path.is_absolute()
                        or '..' in path.parts or any(ord(c) < 32 for c in name)):
                    raise ValueError('ZIP中包含不安全的文件路径。')
                if info.flag_bits & 1:
                    raise ValueError('不支持加密ZIP。')
                kind = stat.S_IFMT(info.external_attr >> 16)
                if kind not in {0, stat.S_IFREG, stat.S_IFDIR}:
                    raise ValueError('ZIP只接受普通文件和目录，不接受链接。')
                identity = str(path).casefold()
                if identity in seen:
                    raise ValueError('ZIP包含重复或大小写冲突的文件名。')
                seen.add(identity)
                if info.is_dir():
                    continue
                if info.file_size < 0:
                    raise ValueError('ZIP文件大小无效。')
                total += info.file_size
                if total > MAX_BYTES:
                    raise ValueError('ZIP解压后的总大小不得超过512 MiB。')
                planned.append((info, payload.joinpath(*path.parts)))
            for info, target in planned:
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                with archive.open(info) as source, target.open('xb') as output:
                    remaining = info.file_size
                    while remaining:
                        block = source.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError('ZIP中的文件不完整。')
                        output.write(block)
                        remaining -= len(block)
                    if source.read(1):
                        raise ValueError('ZIP中的实际大小与声明不一致。')
            entries = [target for _, target in planned if target.suffix.lower() in ENTRY_SUFFIXES
                       and not any(part.startswith('.') or part == '__MACOSX' for part in target.relative_to(payload).parts)]
            if len(entries) != 1:
                raise ValueError('ZIP须包含唯一的EDF、BDF、VHDR、SET、FIF、NWB或SpikeGLX META主文件及其配套文件。')
        upload.replace(directory / 'original.zip')
        entry = entries[0]
        if entry.suffix.lower() == '.meta':
            entry = entry.with_suffix('.bin')
            if not entry.is_file() or not entry.name.lower().endswith(('.ap.bin', '.lf.bin')):
                raise ValueError('SpikeGLX配套缺失：META须对应同名AP或LF BIN。')
        return entry
    with upload.open('rb') as handle:
        signature = handle.read(8)
    suffix = Path(filename).suffix.lower()
    if signature.strip() == b'0':
        suffix = '.edf'
    elif signature == b'\xffBIOSEMI':
        suffix = '.bdf'
    if suffix not in ENTRY_SUFFIXES:
        raise ValueError('请选择已支持格式；SpikeGLX的单流BIN和META必须一起打包ZIP。')
    if suffix == '.meta':
        raise ValueError('SpikeGLX须将同名.ap.bin/.ap.meta或.lf.bin/.lf.meta一起打包ZIP，不能单独提交META。')
    target = directory / ('source' + suffix)
    upload.replace(target)
    return target


def source_manifest(source, metadata):
    """Freeze every file the selected reader declares as part of the recording."""
    source = Path(source).resolve()
    names = [item['name'] for item in metadata.get('source_files', [])] or [source.name]
    files = []
    for name in names:
        path = (source.parent / name).resolve()
        if not path.is_relative_to(source.parent) or not path.is_file():
            raise ValueError('读取模块声明了包外或缺失的配套文件。')
        files.append({'path': str(path), 'sha256': sha256(path)})
    if str(source) not in {item['path'] for item in files}:
        raise ValueError('读取模块未声明主文件。')
    return files
