"""Provenance and applicability contracts, not clinical detector accuracy."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from test_modular_core import record, core
from ephys_qc.tagging import describe_data, context_defaults
from ephys_qc.runtime import _extension_status, _extension_channel_mapping


def input_record(fs=512):
    item = record()
    for channel in item['metadata']['channels']:
        channel.update(sampling_rate_hz=fs, unit='uV')
    return item


def extension_config():
    return {'method_config': {'extensions': ['mne_amplitude', 'mne_muscle']}}


def outcomes(plan):
    return {row['id']: row for row in plan['method_applicability']}


class TagAndMethodContractTests(unittest.TestCase):
    def test_repeated_channel_names_keep_separate_source_identity(self):
        channels = [{'raw_name': 'T8-P8', 'source_index': 4, 'channel_id': 'case:ch:4'},
                    {'raw_name': 'T8-P8', 'source_index': 9, 'channel_id': 'case:ch:9'},
                    {'raw_name': 'Fz', 'source_index': 10, 'channel_id': 'case:ch:10'}]
        mapping = _extension_channel_mapping(channels)
        self.assertEqual(len({r['adapter_name'] for r in mapping}), 3)
        self.assertEqual([r['source_index'] for r in mapping], [4, 9, 10])
        self.assertEqual(mapping[0]['raw_name'], mapping[1]['raw_name'])
        self.assertNotEqual(mapping[0]['channel_id'], mapping[1]['channel_id'])

    def test_source_and_clinical_annotation_are_frozen_without_entering_thresholds(self):
        item = input_record()
        item['provenance'] = {'name': 'public study', 'url': 'https://example.org/study'}
        item['data_usage'] = {'annotations': 'clinical events, not artifacts'}
        first = core.build_plan(item)
        item['provenance']['name'] = 'corrected study'
        item['annotation'] = {'format': 'clinical_events_tsv', 'path': '/unused/example.tsv'}
        second = core.build_plan(item)
        self.assertNotEqual(first['plan_id'], second['plan_id'])
        self.assertEqual(first['input_provenance']['name'], 'public study')
        self.assertEqual(outcomes(second)['clinical_timeline']['status'], 'ready')
        self.assertEqual(first['qc_config']['method_config'], second['qc_config']['method_config'])

    def test_adult_profile_is_not_participant_age_evidence(self):
        tags = {row['key']: row for row in describe_data(input_record())}
        self.assertEqual(tags['age_group']['status'], 'unknown')
        self.assertEqual(tags['coordinates']['status'], 'unknown')
        self.assertEqual(tags['preprocessing']['status'], 'unknown')
        self.assertEqual(context_defaults(input_record())['task'], 'rest')

    def test_clinical_context_changes_provenance_but_not_technical_gates(self):
        first = core.build_plan(input_record(), qc_config=extension_config())
        config = extension_config()
        config['context_tags'] = {'disease': 'epilepsy', 'age_group': 'child', 'task': 'sleep'}
        other = core.build_plan(input_record(), qc_config=config)
        self.assertNotEqual(first['plan_id'], other['plan_id'])
        self.assertEqual(first['method_applicability'], other['method_applicability'])
        self.assertEqual(first['qc_config']['method_config'], other['qc_config']['method_config'])
        self.assertEqual(outcomes(other)['sleep_timeline']['status'], 'blocked')

    def test_extension_selection_adds_real_parent_dependencies(self):
        plan = core.build_plan(input_record(), selected_modules=[], qc_config=extension_config())
        self.assertEqual(set(plan['selected_modules']), {'M01','M02','M03','M06','M08','M09'})
        self.assertEqual(outcomes(plan)['mne_amplitude']['status'], 'ready')
        self.assertEqual(outcomes(plan)['mne_muscle']['status'], 'partial')
        self.assertIsNone(plan['qc_config']['method_config']['extension_parameters']['mne_amplitude']['peak_volts'])

    def test_missing_auxiliaries_do_not_become_available_from_tags(self):
        config = {'context_tags': {'disease': 'sleep_disorder', 'task': 'sleep'}}
        plan = core.build_plan(input_record(), qc_config=config)
        for id_ in ('ecg_locked', 'eog_locked', 'sleep_timeline', 'task_timeline'):
            self.assertEqual(outcomes(plan)[id_]['status'], 'blocked')

    def test_unknown_and_unverified_passbands_are_not_ready(self):
        item = input_record()
        item['preprocessing'] = {'highpass_hz': .1, 'lowpass_hz': 200, 'verified': False}
        plan = core.build_plan(item, qc_config=extension_config())
        self.assertEqual(outcomes(plan)['mne_muscle']['status'], 'partial')
        item['preprocessing']['verified'] = True
        self.assertEqual(outcomes(core.build_plan(item, qc_config=extension_config()))['mne_muscle']['status'], 'ready')
        item['preprocessing']['lowpass_hz'] = 100
        self.assertEqual(outcomes(core.build_plan(item, qc_config=extension_config()))['mne_muscle']['status'], 'blocked')

    def test_sample_rate_blocks_muscle_without_silent_band_change(self):
        for fs in (160, 256):
            plan = core.build_plan(input_record(fs), qc_config=extension_config())
            result = outcomes(plan)['mne_muscle']
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(result['parameters']['filter_freq_hz'], [110., 140.])

    def test_verified_markers_cannot_be_truthy_strings(self):
        for key in ('preprocessing', 'verified_electrode_coordinates', 'verified_epochs'):
            item = input_record()
            item[key] = {'verified': 'false'} if key == 'preprocessing' else 'false'
            with self.subTest(key=key), self.assertRaises(ValueError):
                core.build_plan(item)

    def test_changed_unit_or_geometry_changes_frozen_plan(self):
        item = input_record()
        initial = core.build_plan(item, qc_config=extension_config())['plan_id']
        for mutation in ('mV', 'geometry'):
            changed = deepcopy(item)
            if mutation == 'geometry':
                changed['verified_electrode_coordinates'] = True
            else:
                changed['metadata']['channels'][0]['unit'] = mutation
            self.assertNotEqual(initial, core.build_plan(changed, qc_config=extension_config())['plan_id'])
        changed = deepcopy(item)
        changed['metadata']['channels'][0]['unit'] = 'unknown'
        with self.assertRaisesRegex(ValueError, '电压单位'):
            core.build_plan(changed, qc_config=extension_config())

    def test_base_high_frequency_gate_checks_bandwidth_and_duration(self):
        item = record(auxiliary=True)
        for channel in item['metadata']['channels']:
            channel.update(sampling_rate_hz=64, unit='uV')
        self.assertEqual(outcomes(core.build_plan(item))['hf_burst']['status'], 'blocked')
        for channel in item['metadata']['channels']:
            channel['sampling_rate_hz'] = 256
        self.assertEqual(outcomes(core.build_plan(item))['hf_burst']['status'], 'ready')
        item['default_config']['selection']['duration_seconds'] = 5
        self.assertEqual(outcomes(core.build_plan(item))['hf_burst']['status'], 'blocked')

    def test_bad_channel_submethod_uses_configured_group_minimum(self):
        plan = core.build_plan(input_record(), qc_config={'method_config': {'bad_channels': {'min_group_channels': 9}}})
        self.assertEqual(outcomes(plan)['prep_nonspatial']['status'], 'partial')
        self.assertIn('9', outcomes(plan)['prep_nonspatial']['reason'])

    def test_unsupported_or_forged_tags_and_planned_methods_are_rejected(self):
        cases = [{'context_tags': {'has_eog': True}}, {'context_tags': {'disease': 'invented'}},
                 {'method_config': {'extensions': ['pyprep_ransac']}},
                 {'method_config': {'comparison_groups': [{}] * 8}},
                 {'method_config': {'extension_parameters': {'mne_muscle': {'threshold_z': float('nan')}}}}]
        for config in cases:
            with self.subTest(config=config), self.assertRaises(ValueError):
                core.build_plan(input_record(), qc_config=config)

    def test_tags_are_frozen_and_serialize_without_mutating_input(self):
        item = input_record()
        before = deepcopy(item)
        plan = core.build_plan(item, qc_config=extension_config())
        plan['data_tags'][0]['display'] = 'changed'
        self.assertEqual(item, before)
        json.dumps(plan, allow_nan=False)

    def test_partial_gate_does_not_hide_failed_or_blocked_execution(self):
        self.assertEqual(_extension_status('failed', 'partial'), 'failed')
        self.assertEqual(_extension_status('blocked', 'partial'), 'skipped')
        self.assertEqual(_extension_status('completed', 'partial'), 'partial')

    def test_failed_input_records_each_selected_extension_as_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            item = input_record()
            item['source_path'] = str(Path(temp) / 'missing.edf')
            result = core.run_job({'input': item, 'selected_modules': [], 'qc_config': extension_config()},
                                  Path(temp) / 'job', lambda *args: None)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(len(result['extensions']), 2)
            for extra in result['extensions']:
                self.assertEqual(extra['status'], 'skipped')
                saved = json.loads((Path(temp) / 'job' / 'artifacts' / extra['artifact']).read_text())
                self.assertFalse(saved['calculated'])
            self.assertIsNone(result['score']['value'])


if __name__ == '__main__':
    unittest.main()
