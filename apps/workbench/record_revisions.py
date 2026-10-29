"""Append-only input revisions; old requests and labels retain their own bytes."""
import copy
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import uuid

from intake import (_save, _load, _hash, MODALITIES, REFERENCE_SCHEMES,
                    registration_selection)
from ephys_qc.readers import inspect_recording, open_reader
from ephys_qc.tagging import validate_context, data_facts


class RevisionConflict(ValueError):
    pass


class RecordRevisions:
    def __init__(self, runtime_root):
        self.root = Path(runtime_root) / 'record-revisions'
        self.root.mkdir(exist_ok=True)

    def registered(self):
        return [_load(path) for path in sorted(self.root.glob('*/record.json'))]

    def revise(self, original, body, latest_revision):
        allowed = {'modality', 'reference_scheme', 'eeg_indices', 'reference_indices',
                   'context_tags', 'label', 'source_note', 'confirmed', 'base_revision',
                   'preprocessing', 'annotation_mapping'}
        if not isinstance(body, dict) or set(body) - allowed or body.get('confirmed') is not True:
            raise ValueError('请明确确认本次信息修订，不接受其他字段。')
        version = original.get('record_revision', 1)
        if type(body.get('base_revision')) is not int or body['base_revision'] != version or version != latest_revision:
            raise RevisionConflict('记录已有新版本，请载入最新信息后再更正。')
        source = Path(original['source_path'])
        if _hash(source) != original['expected_sha256']:
            raise ValueError('来源指纹发生变化，不能修订旧记录。')
        for member in original.get('expected_source_files', []):
            if _hash(Path(member['path'])) != member['sha256']:
                raise ValueError('来源配套文件发生变化，不能修订旧记录。')
        record = copy.deepcopy(original)
        record['metadata'] = inspect_recording(source)
        modality = body.get('modality', record.get('modality', 'scalp_eeg'))
        reference = body.get('reference_scheme', record.get('reference_scheme', 'unknown'))
        if modality not in MODALITIES - {'unknown'} or reference not in REFERENCE_SCHEMES:
            raise ValueError('请确认模态和参考构型。')
        config = record.setdefault('default_config', {})
        selection = config.get('selection', {})
        eeg = body.get('eeg_indices', selection.get('eeg_indices'))
        refs = body.get('reference_indices', selection.get('reference_indices', {}))
        config['selection'] = registration_selection(record['metadata'], eeg, refs, modality)
        config['context_tags'] = validate_context(record, body.get('context_tags', config.get('context_tags')))
        old_context = original.get('default_config', {}).get('context_tags', {})
        record['context_evidence'] = {key: evidence for key, evidence in record.get('context_evidence', {}).items()
                                      if config['context_tags'].get(key) == old_context.get(key)}
        # Changing role/reference invalidates previous comparison groups.
        if eeg != selection.get('eeg_indices') or reference != original.get('reference_scheme', 'unknown'):
            config.setdefault('method_config', {})['comparison_groups'] = (
                ['user_confirmed_reference'] * len(eeg) if reference in {'common_reference', 'linked_ears'} else None)
        label = body.get('label', record['label'])
        note = body.get('source_note', record.get('provenance', {}).get('note', ''))
        if not isinstance(label, str) or not label.strip() or len(label) > 160 or not isinstance(note, str) or len(note) > 2000:
            raise ValueError('记录名称最多160字，来源说明最多2000字。')
        record.update(label=label.strip(), modality=modality, reference_scheme=reference,
                      modality_source='用户在记录修订中明确声明。',
                      reference_evidence='用户在记录修订中明确声明；未自动重参考。')
        record.setdefault('provenance', {})['note'] = note
        if 'preprocessing' in body:
            prep = body['preprocessing']
            if not isinstance(prep, dict) or set(prep) - {'verified', 'highpass_hz', 'lowpass_hz', 'note'} or type(prep.get('verified')) is not bool:
                raise ValueError('处理史需明确 verified，并提供可选高通、低通频率与说明。')
            if not isinstance(prep.get('note', ''), str) or len(prep.get('note', '')) > 2000:
                raise ValueError('处理史说明最多2000字。')
            if prep['verified'] and not prep.get('note', '').strip():
                raise ValueError('确认处理史时，请注明资料依据。')
            record['preprocessing'] = {**prep, 'source': 'user_declaration_not_independent_measurement'}
        data_facts(record, config)  # Frequency bounds and context types.
        identifier = 'revision-' + uuid.uuid4().hex
        record.update(id=identifier, record_family=original.get('record_family', original['id']),
                      record_revision=version + 1, parent_input_id=original['id'],
                      revised_at=datetime.now(timezone.utc).isoformat())
        record.pop('availability', None)
        directory = self.root / identifier
        directory.mkdir(mode=0o700)
        try:
            if 'annotation_mapping' in body:
                self._map_annotations(record, body['annotation_mapping'], directory)
            _save(directory / 'change.json', copy.deepcopy(body))
            # record.json is the commit marker; incomplete revisions are not listed.
            _save(directory / 'record.json', record)
        except Exception:
            import shutil
            shutil.rmtree(directory)
            raise
        return record

    def _map_annotations(self, record, mapping, directory):
        if mapping is None:
            record.pop('annotation', None)
            record.pop('annotation_mapping', None)
            return
        if not isinstance(mapping, dict) or set(mapping) - {'kind', 'labels', 'note', 'confirmed'} or mapping.get('confirmed') is not True:
            raise ValueError('标注映射须明确确认类型、原始标签与解释。')
        kind, labels = mapping.get('kind'), mapping.get('labels')
        if kind not in {'task', 'sleep_stage', 'clinical_event'} or not isinstance(labels, dict) or not 0 < len(labels) <= 512:
            raise ValueError('标注类型或映射标签无效。')
        if any(not isinstance(k, str) or not isinstance(v, str) or not v.strip() or len(k) > 500 or len(v) > 500 for k, v in labels.items()):
            raise ValueError('每个原始标签须对应明确解释。')
        if not isinstance(mapping.get('note', ''), str) or len(mapping.get('note', '')) > 2000:
            raise ValueError('标注说明最多2000字。')
        reader = open_reader(record['source_path'], record['id'])
        try:
            events = reader.describe().get('events', [])
        finally:
            reader.close()
        present = {e['text'] for e in events}
        if set(labels) - present:
            raise ValueError('映射含文件中不存在的原始标签。')
        technical = {'boundary', 'bad boundary', 'edge boundary', 'bad_acq_skip'}
        if any(label.casefold() in technical for label in labels):
            raise ValueError('采集断点不能转换成任务、分期或临床事件。')
        selected = [copy.deepcopy(e) for e in events if e['text'] in labels]
        for event in selected:
            # EDF+ TAL may omit duration. Preserve that fact and map it only
            # to a point; never infer a stage or clinical-event span.
            event['source_duration_present'] = event.get('duration_seconds') is not None
            if not event['source_duration_present']:
                event['duration_seconds'] = 0.
            if any(isinstance(event.get(key), bool) or not isinstance(event.get(key), (int, float)) or
                   not math.isfinite(event[key]) for key in ('onset_seconds', 'duration_seconds')):
                raise ValueError('标注含无效时间值。')
        if any(e['onset_seconds'] < 0 or e['duration_seconds'] < 0 or
               e['onset_seconds'] + e['duration_seconds'] > record['metadata']['duration_seconds'] + 1e-6 for e in selected):
            raise ValueError('映射标注超出记录时钟，请核实来源。')
        if kind == 'sleep_stage' and any(e['duration_seconds'] <= 0 for e in selected):
            raise ValueError('睡眠分期须有明确的正时长，不能由点事件推定。')
        path = directory / 'annotations.tsv'
        fields = (['onset', 'duration', 'event_name', 'source_description', 'source_duration_present'] if kind == 'task' else
                  ['onset_s', 'duration_s', 'stage', 'source_description', 'source_duration_present'] if kind == 'sleep_stage' else
                  ['onset_s', 'duration_s', 'label', 'label_type', 'source_description', 'source_duration_present'])
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.writer(handle, delimiter='\t')
            writer.writerow(fields)
            for event in sorted(selected, key=lambda e: e['onset_seconds']):
                row = [event['onset_seconds'], event['duration_seconds'], labels[event['text']]]
                if kind == 'clinical_event':
                    row.append('user_declared_clinical_event')
                writer.writerow(row + [event['text'], str(event['source_duration_present']).lower()])
        record['annotation'] = {'path': str(path), 'expected_sha256': _hash(path),
                                'format': {'task': 'bids_events_tsv', 'sleep_stage': 'sleep_stages_tsv', 'clinical_event': 'clinical_events_tsv'}[kind],
                                'label_scope': 'user_confirmed_context_not_quality_truth',
                                'duration_interpretation': 'Missing source duration is retained as a point event, never an inferred span.',
                                'source_path': record['source_path'], 'source_expected_sha256': record['expected_sha256']}
        record['annotation_mapping'] = copy.deepcopy(mapping)
        record.setdefault('data_usage', {})['annotations'] = '用户确认的原始文件标注映射；不作为伪迹真值。'
