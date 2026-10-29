"""Preserve the existing EDF/BDF source-index, physical-unit and native-rate reader."""
import copy
import importlib.metadata
import math
from pathlib import Path
from .edf_header import inspect_header
from .common import SourceGuard, source_manifest, public_manifest, annotation_summary


class NativeReader(SourceGuard):
    def __init__(self, path, record_id):
        from brainelecqc.readers.edf import EdfBdfReader
        self.path = Path(path).resolve()
        self.header = inspect_header(self.path)
        self.capture(source_manifest([(self.path, 'main')]))
        self.reader = EdfBdfReader(self.path, str(record_id))
        try:
            self.description = self.reader.describe()
            self._validate_clock()
        except Exception:
            self.close()
            raise
        self.description.update(reader_id='native_edf_bdf', source_files=self.source_files,
                                format=self.header['format'],
                                adapter_version='native-reader/1',
                                backend_version=importlib.metadata.version('brainelecqc'))
        self.description['annotations'] = annotation_summary(self.description['events'], [self.path])

    def _validate_clock(self):
        """The lightweight inventory models only a zero-based continuous clock.

        A +C header is not evidence that TAL timestamps are contiguous. Reject
        layouts whose real segments cannot be represented by that inventory,
        rather than exposing compressed storage time as acquisition time.
        """
        message = ('当前不支持此 EDF/BDF TAL 时钟布局：需要从记录时间0开始、覆盖文件头时长的单一连续段；'
                   '这不表示文件必然损坏。')
        duration = self.header['duration_seconds']
        streams = self.description.get('streams', [])
        if not streams:
            raise ValueError(message)
        for stream in streams:
            segments = stream.get('segments', [])
            if len(segments) != 1:
                raise ValueError(message)
            segment = segments[0]
            fs = stream['sampling_frequency_hz']
            onset = segment['recording_start_seconds']
            first, stop = segment['start_sample'], segment['stop_sample']
            if (not math.isfinite(fs) or fs <= 0 or not math.isfinite(onset)
                    or not math.isclose(onset, 0.0, rel_tol=0, abs_tol=1e-9)
                    or first != 0 or stop != stream['sample_count']
                    or stop <= first
                    or not math.isclose((stop - first) / fs, duration, rel_tol=0, abs_tol=1e-9)):
                raise ValueError(message)
            # Keep the sub-nanosecond source value as provenance while making
            # the accepted zero origin exact for half-open window comparisons.
            # The backend read uses source sample bounds, never this display time.
            if onset != 0.0:
                segment['source_recording_start_seconds'] = onset
                segment['recording_start_seconds'] = 0.0
                segment['clock_zero_tolerance_seconds'] = 1e-9

    def describe(self):
        self.assert_unchanged()
        return copy.deepcopy(self.description)

    def metadata(self):
        self.assert_unchanged()
        return {**copy.deepcopy(self.header), 'reader_id': 'native_edf_bdf',
                'reader_version': self.description['reader_version'],
                'source_files': public_manifest(self.source_files),
                'modality_evidence': {'value': 'unknown', 'source': 'format_is_not_modality',
                                      'requires_confirmation': True},
                'annotations': copy.deepcopy(self.description['annotations']),
                'warnings': copy.deepcopy(self.description['warnings'])}

    def read_window(self, *args, **kwargs):
        self.assert_unchanged()
        result = self.reader.read_window(*args, **kwargs)
        self.assert_unchanged()
        return result

    def close(self):
        close = getattr(getattr(self, 'reader', None), 'close', None)
        if callable(close):
            close()
