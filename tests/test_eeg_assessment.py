"""Rule/evidence traceability regressions, not detector-accuracy validation.

Small artifact fixtures use the existing scientific functions' exported field
names. Conflicting module summaries deliberately exercise the evidence boundary.
"""
import copy
import hashlib
from html.parser import HTMLParser
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ephys_qc import eeg_assessment as assessment


class Elements(HTMLParser):
    def __init__(self, markup):
        super().__init__(convert_charrefs=True)
        self.elements = []
        self.text = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def module(identifier, status='completed', summary=None, reason='Executed'):
    return {'id': identifier, 'status': status, 'reason': reason,
            'summary': copy.deepcopy(summary or {})}


def result(*modules, **changes):
    row = {'analysis_profile': 'scalp-eeg/1', 'scope': 'window',
           'plan_id': 'frozen-input-and-configuration', 'review_status': 'pending',
           'modules': list(modules), 'extensions': [],
           'qc_config': {'method_config': {}}}
    row.update(changes)
    return row


def check(index, identifier):
    return next(item for item in index['checks'] if item['id'] == identifier)


class EEGCatalogTests(unittest.TestCase):
    def test_twelve_unique_bilingual_checks_cover_nine_existing_modules(self):
        catalog = assessment.load_catalog()
        checks = catalog['checks']
        self.assertEqual(len(checks), 12)
        self.assertEqual({c['id'] for c in checks}, {f'EEG-{i:03d}' for i in range(1, 13)})
        self.assertEqual({c['module_id'] for c in checks}, {f'M{i:02d}' for i in range(1, 10)})
        self.assertEqual(catalog['status'], 'project_draft_not_published_standard')
        for row in checks:
            with self.subTest(check=row['id']):
                self.assertTrue(row['source_ids'])
                self.assertEqual(len(row['source_ids']), len(set(row['source_ids'])))
                for field in ('title', 'applicability', 'measurement', 'decision_basis', 'report_content', 'validation'):
                    self.assertEqual(set(row[field]), {'zh', 'en'})
                    self.assertTrue(all(row[field].values()))
                self.assertTrue(row['artifacts'])
                self.assertTrue(row['evidence_fields'])
                self.assertTrue(all(Path(name).name == name for name in row['artifacts']))

    def test_every_cited_source_has_a_stable_heading_in_both_evidence_documents(self):
        references = {source for row in assessment.load_catalog()['checks'] for source in row['source_ids']}
        for relative in ('docs/eeg-evidence.md', 'docs/en/eeg-evidence.md'):
            headings = set(re.findall(r'^## (SRC-[A-Z0-9-]+)\s*$', (ROOT / relative).read_text(), re.M))
            with self.subTest(document=relative):
                self.assertFalse(references - headings, f'Unresolved references: {sorted(references-headings)}')

    def test_both_generated_check_documents_match_the_packaged_catalog(self):
        path = ROOT / 'scripts/build_eeg_specification.py'
        spec = importlib.util.spec_from_file_location('build_eeg_specification_for_test', path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        catalog = assessment.load_catalog()
        for lang, relative in [('zh', 'docs/eeg-checks.md'), ('en', 'docs/en/eeg-checks.md')]:
            with self.subTest(language=lang):
                expected = generator.render(catalog, lang)
                self.assertEqual((ROOT / relative).read_text(), expected)
                for row in catalog['checks']:
                    self.assertIn('## ' + row['id'] + '\n', expected)
                    self.assertIn(row['title'][lang], expected)
                    for source in row['source_ids']:
                        self.assertIn(source, expected)


class EEGAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.artifacts / name
        # Deliberately retain non-canonical whitespace to verify file hashing.
        path.write_text(json.dumps(value, ensure_ascii=False, indent=3) + '\n', encoding='utf-8')
        return path

    def attach(self, row):
        return assessment.attach_eeg_assessment(row, self.artifacts)

    def test_effective_parameters_and_hash_come_from_artifact_not_plan(self):
        payload = {'parameters': {'min_constant_seconds': 0.23, 'near_zero_volts': 2e-7,
                                  'min_constant_samples': 59},
                   'input_range': {'start_sample': 1024, 'stop_sample': 2048},
                   'measurements': [{'channel_id': 'source:ch:4', 'nonfinite_sample_count': 2}],
                   'candidates': []}
        path = self.write('M03_continuity.json', payload)
        row = result(module('M03', summary={'candidate_count': 0}))
        row['qc_config']['method_config']['continuity'] = {'min_constant_seconds': 0.9}
        frozen = self.attach(row)
        item = check(frozen, 'EEG-003')
        self.assertEqual(item['parameters']['M03_continuity.json#parameters'], payload['parameters'])
        self.assertEqual(item['evidence'][0]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(item['evidence_status'], 'recorded')
        self.assertIsNone(frozen['conformance'])
        self.assertFalse(frozen['score_calibrated'])
        self.assertFalse(frozen['expert_accuracy_validated'])
        self.assertEqual(frozen['population_confirmation'], 'not_captured_by_runtime')

    def test_omitted_evidence_does_not_turn_module_summary_into_measurements(self):
        row = result(module('M03', summary={'candidate_count': 0, 'automatic_exclusions': 0}))
        item = check(self.attach(row), 'EEG-003')
        self.assertEqual(item['evidence_status'], 'not_recorded')
        self.assertEqual(item['evidence'], [])
        self.assertEqual(item['parameters'], {})
        self.assertEqual(item['measurement_summary'], {})

    def test_never_run_check_preserves_unknown_not_numeric_zero(self):
        item = check(self.attach(result()), 'EEG-007')
        self.assertEqual(item['module_status'], 'not_run')
        self.assertEqual(item['measurement_summary'], {})
        self.assertEqual(item['evidence_status'], 'not_recorded')

    def test_failed_module_remains_failed_even_if_a_partial_artifact_exists(self):
        self.write('M04_spectral.json', {'config': {'welch_seconds': 4.0}})
        row = result(module('M04', 'failed', {'line_status': 'computed'}, 'nonfinite input'))
        frozen = self.attach(row)
        for identifier in ('EEG-004', 'EEG-005', 'EEG-006'):
            with self.subTest(check=identifier):
                item = check(frozen, identifier)
                self.assertEqual(item['module_status'], 'failed')
                self.assertEqual(item['module_reason'], 'nonfinite input')
                self.assertEqual(item['measurement_summary'], {})
        parsed = Elements(assessment.render_eeg_assessment(row))
        self.assertIn('失败', ''.join(parsed.text))

    def test_psd_uses_real_estimator_path_and_preserves_uncovered_tail(self):
        estimator = {'density_unit': 'V^2/Hz', 'nperseg': 1024, 'noverlap': 512,
                     'nfft': 1024, 'frequency_resolution_hz': .25,
                     'periodogram_count': 3, 'covered_samples': 2048, 'tail_samples': 13}
        self.write('M04_spectral.json', {'psd': {'frequencies_hz': [0., .25],
                    'power_v2_hz': [[0., 1e-10]], 'channel_ids': ['source:ch:2'],
                    'estimator': estimator}, 'config': {'welch_seconds': 4.0}})
        item = check(self.attach(result(module('M04'))), 'EEG-004')
        summary = item['measurement_summary']
        # Either nested or flattened presentation is acceptable; field names
        # and values must remain the backend's real estimator contract.
        observed = summary.get('estimator', summary)
        for key in ('frequency_resolution_hz', 'nperseg', 'noverlap', 'periodogram_count', 'covered_samples', 'tail_samples'):
            with self.subTest(metric=key):
                self.assertEqual(observed[key], estimator[key])

    def test_line_counts_are_not_summed_into_independent_artifact_duration(self):
        channels = [
            {'channel_id': 'source:ch:2', 'nominal_hz': 50., 'assessed_window_count': 7,
             'flagged_window_count': 3, 'flagged_union_seconds': 6.,
             'flagged_union_fraction_of_input': .6},
            {'channel_id': 'source:ch:2', 'nominal_hz': 60., 'assessed_window_count': 7,
             'flagged_window_count': 4, 'flagged_union_seconds': 7.,
             'flagged_union_fraction_of_input': .7}]
        path = self.write('M04_spectral.json', {'line_noise': {'status': 'computed', 'channel_summary': channels}})
        before = path.read_bytes()
        item = check(self.attach(result(module('M04'))), 'EEG-005')
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(path.read_text())['line_noise']['channel_summary'], channels)
        self.assertIn('line_noise.channel_summary', item['evidence'][0]['fields'])
        self.assertEqual(item['evidence'][0]['sha256'], hashlib.sha256(before).hexdigest())
        self.assertNotIn('candidate_seconds', item['measurement_summary'])
        self.assertNotIn('contamination_fraction', item['measurement_summary'])

    def test_spectral_subitems_cannot_borrow_parent_module_fit_success(self):
        self.write('M04_spectral.json', {'psd': {'estimator': {'periodogram_count': 1}},
                                       'line_noise': {'status': 'insufficient_duration'}})
        row = result(module('M04', summary={'full_spectral_fit_statuses': ['computed'],
                                           'window_spectral_fit_statuses': ['computed']}))
        frozen = self.attach(row)
        self.assertEqual(check(frozen, 'EEG-005')['measurement_summary']['status'], 'insufficient_duration')
        self.assertEqual(check(frozen, 'EEG-006')['measurement_summary'], {})

    def test_auxiliary_summary_is_taken_from_real_by_kind_evidence(self):
        self.write('M06_auxiliary_events.json', {
            'config': {'epoch_tmin_seconds': -.5, 'epoch_tmax_seconds': .5},
            'by_kind': {'ecg': {'status': 'missing_reference', 'detected_event_count': 0},
                        'eog': {'status': 'no_events', 'detected_event_count': 0}}})
        row = result(module('M06', summary={'events': {'ecg': {'status': 'computed', 'event_count': 999}},
                                           'muscle_status': 'ok', 'high_frequency_candidate_count': 0}))
        frozen = self.attach(row)
        auxiliary = check(frozen, 'EEG-008')['measurement_summary']
        by_kind = auxiliary.get('by_kind', auxiliary.get('events', auxiliary))
        self.assertEqual(by_kind['ecg']['status'], 'missing_reference')
        self.assertIsNone(by_kind['ecg']['detected_event_count'])
        self.assertEqual(by_kind['eog']['status'], 'no_events')
        self.assertEqual(by_kind['eog']['detected_event_count'], 0)
        self.assertNotIn('999', json.dumps(auxiliary))
        self.assertEqual(check(frozen, 'EEG-009')['measurement_summary'], {})

    def test_unassessed_muscle_empty_candidates_are_not_zero_artifact_findings(self):
        for status, channels, expected in [
                ('insufficient_sampling_rate', [], None),
                ('partial_channels', [{'status': 'nonfinite_input'}], None),
                ('ok', [{'status': 'ok', 'valid_seconds': 0}], None),
                ('ok', [{'status': 'ok', 'valid_seconds': 8}], 0)]:
            with self.subTest(status=status, channels=channels):
                self.write('M06_muscle.json', {'status': status, 'channels': channels, 'candidates': []})
                summary = check(self.attach(result(module('M06'))), 'EEG-009')['measurement_summary']
                self.assertEqual(summary['candidate_interval_count'], expected)

    def test_detected_and_averaged_auxiliary_event_counts_are_distinct(self):
        self.write('M06_auxiliary_events.json', {
            'by_kind': {'ecg': {'status': 'computed', 'detected_event_count': 12,
                               'complete_epoch_count': 10, 'boundary_excluded_count': 2,
                               'averaged_event_count': 6}}})
        item = check(self.attach(result(module('M06'))), 'EEG-008')
        summary = item['measurement_summary']
        ecg = summary.get('by_kind', summary.get('events', summary))['ecg']
        self.assertEqual(ecg['detected_event_count'], 12)
        self.assertEqual(ecg['complete_epoch_count'], 10)
        self.assertEqual(ecg['boundary_excluded_count'], 2)
        self.assertEqual(ecg['averaged_event_count'], 6)
        self.assertNotIn('used_event_count', ecg)

    def test_non_eeg_results_are_untouched_and_do_not_create_artifacts(self):
        for profile in ('ecog-basic/1', 'seeg-basic/1', 'neuropixels-basic/1', None):
            with self.subTest(profile=profile):
                row = result(analysis_profile=profile)
                before = copy.deepcopy(row)
                with patch.object(assessment, 'catalog_bytes', side_effect=AssertionError('non-EEG must not load EEG rules')):
                    self.assertIsNone(self.attach(row))
                self.assertEqual(row, before)
                self.assertEqual(list(self.artifacts.iterdir()), [])

    def test_catalog_and_evidence_fingerprints_remain_frozen_after_files_change(self):
        payload_path = self.write('M03_continuity.json', {'parameters': {'min_constant_seconds': .1},
                                                        'measurements': [], 'candidates': []})
        original_evidence = payload_path.read_bytes()
        original_rules = assessment.catalog_bytes()
        catalog_path = self.root / 'active-rules.json'
        catalog_path.write_bytes(original_rules)
        row = result(module('M03'), extensions=[{'id': 'mne_amplitude', 'parameters': {'flat_volts': 0.}}])
        with patch.object(assessment, 'CATALOG_PATH', catalog_path):
            index = self.attach(row)
            saved = (self.artifacts / 'eeg-assessment.json').read_bytes()
            modified = json.loads(original_rules)
            modified['version'] = 'future-revision'
            modified['checks'][0]['title']['zh'] = '未来修改后的词条'
            catalog_path.write_text(json.dumps(modified))
            payload_path.write_text('{"different": true}')
            row['extensions'][0]['parameters']['flat_volts'] = 9.
            self.assertEqual((self.artifacts / 'eeg-rules.json').read_bytes(), original_rules)
            self.assertEqual((self.artifacts / 'eeg-assessment.json').read_bytes(), saved)
            self.assertEqual(index['catalog_sha256'], hashlib.sha256(original_rules).hexdigest())
            self.assertEqual(check(index, 'EEG-003')['evidence'][0]['sha256'], hashlib.sha256(original_evidence).hexdigest())
            self.assertEqual(index['optional_methods'][0]['parameters']['flat_volts'], 0.)
            with patch.object(assessment, 'catalog_bytes', side_effect=AssertionError('render the saved snapshot only')):
                markup = assessment.render_eeg_assessment(row)
            self.assertNotIn('未来修改后的词条', markup)
            self.assertNotIn('future-revision', markup)

    def test_recording_index_links_children_and_does_not_aggregate_candidates(self):
        windows = [
            {'id': 'window-0001', 'result_artifact': 'window-0001--result.json',
             'report_artifact': 'window-0001--report.html', 'status': 'partial',
             'start_seconds': 0., 'duration_seconds': 10.},
            {'id': 'window-0002', 'result_artifact': 'window-0002--result.json',
             'report_artifact': 'window-0002--report.html', 'status': 'completed',
             'start_seconds': 10., 'duration_seconds': 10.}]
        self.write('window-results.json', windows)
        coverage = {'completed_seconds': 20., 'fully_assessed_seconds': 0., 'total_seconds': 20.,
                    'failed_seconds': 0., 'unexecuted_seconds': 0., 'gap_seconds': 0.,
                    'execution_percent': 100., 'available_execution_percent': 100.,
                    'fully_assessed_percent': 0., 'quality_score': False}
        self.write('coverage.json', coverage)
        first = self.write('window-0001--M03_continuity.json', {'candidates': [{'kind': 'flat'}]})
        second = self.write('window-0002--M03_continuity.json', {'candidates': []})
        original = first.read_bytes(), second.read_bytes()
        row = result(module('M04', 'partial', {'window_status_counts': {'completed': 1, 'partial': 1},
                                             'window_count': 2}), scope='recording', windows=copy.deepcopy(windows),
                     coverage=coverage, warnings=[], coverage_plan={'gaps': []}, candidate_index=[])
        row['modules'][0]['name'] = '频谱与干扰'
        index = self.attach(row)
        self.assertEqual(index['child_results'], [w['result_artifact'] for w in windows])
        maps = index['child_artifact_maps']
        self.assertEqual(maps[0]['artifacts']['M03_continuity.json'], 'window-0001--M03_continuity.json')
        self.assertEqual(maps[1]['artifacts']['M03_continuity.json'], 'window-0002--M03_continuity.json')
        self.assertEqual((first.read_bytes(), second.read_bytes()), original)
        self.assertEqual(row['windows'], windows)
        self.assertTrue(all(c['observation_scope'] == 'window_execution_summary' for c in index['checks']))
        for item in index['checks']:
            self.assertEqual(item['parameters'], {})
            self.assertNotIn('candidate_seconds', item['measurement_summary'])
            self.assertNotIn('flagged_union_seconds', item['measurement_summary'])
            self.assertNotIn('contamination_fraction', item['measurement_summary'])
        # Existing whole-record renderer owns the child-report navigation;
        # the new rule index must preserve it, not introduce a second table.
        from ephys_qc.whole_record import render_recording_report
        report_path = self.root / 'recording-report.html'
        render_recording_report(row, report_path)
        parsed = Elements(report_path.read_text())
        links = {attrs.get('href') for tag, attrs in parsed.elements if tag == 'a'}
        self.assertTrue({w['report_artifact'] for w in windows}.issubset(links))
        self.assertIn('未合并跨窗候选', assessment.render_eeg_assessment(row))

    def test_html_escapes_text_and_links_only_to_rule_pages_and_local_evidence(self):
        self.write('M03_continuity.json', {'parameters': {}})
        row = result(module('M03'))
        index = self.attach(row)
        index['checks'][0]['title']['zh'] = '<img src=x onerror="bad()">'
        index['specification_version'] = '<script>bad()</script>'
        parsed = Elements(assessment.render_eeg_assessment(row))
        self.assertFalse({'script', 'img', 'iframe', 'svg'} & {tag for tag, _ in parsed.elements})
        self.assertFalse(any(key.startswith('on') for _, attrs in parsed.elements for key in attrs))
        self.assertIn('<img src=x onerror="bad()">', ''.join(parsed.text))
        links = {attrs.get('href') for tag, attrs in parsed.elements if tag == 'a'}
        expected = {'eeg-assessment.json', 'eeg-rules.json', 'M03_continuity.json',
                    '/standards/eeg-evidence', '/standards/eeg-report'}
        expected.update('/standards/eeg-checks#eeg-%03d' % i for i in range(1, 13))
        self.assertEqual(links, expected)

    def test_report_without_saved_assessment_has_no_synthetic_checklist(self):
        self.assertEqual(assessment.render_eeg_assessment(result()), '')

    def test_artifact_symlink_cannot_read_evidence_outside_job_directory(self):
        outside = self.root / 'unrelated.json'
        outside.write_text('{"private": "do not ingest"}')
        (self.artifacts / 'M03_continuity.json').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'artifact directory'):
            self.attach(result(module('M03')))
        self.assertFalse((self.artifacts / 'eeg-assessment.json').exists())


if __name__ == '__main__':
    unittest.main()
