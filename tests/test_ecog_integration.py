"""ECoG routing, metadata-only recommendation and modality-preserving docs."""
import copy
from html.parser import HTMLParser
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / 'src'), str(REPO / 'apps/workbench')]
from ephys_qc.recommendations import recommend
from ephys_qc.planning import build_plan
from intake import registration_selection, suggestions
from standards_page import render_standards, safe_url, Markdown, _module_clause_id
from server import insert_report_navigation


def recording():
    return {'id': 'ecog-example', 'modality': 'ecog', 'source_path': '/not-read/sample.fif',
            'expected_sha256': '0' * 64, 'reference_scheme': 'unknown',
            'metadata': {'format': 'FIF', 'duration_seconds': 269.08,
                         'channels': [{'index': i, 'name': f'G{i}', 'unit': 'V', 'sampling_rate_hz': 1000,
                                       'channel_type': 'ecog', 'channel_type_source': 'file_declared'} for i in range(3)]},
            'default_config': {'selection': {'eeg_indices': [0, 1, 2], 'reference_indices': {},
                                             'start_seconds': 60, 'duration_seconds': 120},
                               'method_config': {'ecog': {}, 'comparison_groups': None}}}


class ECoGIntegrationTests(unittest.TestCase):
    def test_report_return_link_supports_explicit_and_omitted_body_tags(self):
        navigation = '<nav><a href="/?modality=ecog&amp;job=123">Return</a></nav>'
        for report in ('<!doctype html><html><style>body{}</style><main>Report</main></html>',
                       '<html><body class="report"><main>Report</main></body></html>'):
            rendered = insert_report_navigation(report, navigation)
            self.assertEqual(rendered.count(navigation), 1)
            self.assertLess(rendered.index(navigation), rendered.index('<main>'))
            self.assertEqual(rendered.replace(navigation, ''), report)

    def test_recommendation_roundtrip_uses_own_methods_without_reading_signal(self):
        record = recording(); before = copy.deepcopy(record)
        result = recommend(record)
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['scope']['supported_modality'], 'ecog')
        self.assertFalse(result['scope']['signal_read'])
        self.assertNotIn('M06', result['selected_modules'])
        self.assertNotIn('M07', result['selected_modules'])
        self.assertEqual(result['qc_config']['method_config']['extensions'], [])
        self.assertEqual(build_plan(record, result['selected_modules'], result['qc_config'])['plan_id'], result['plan_id'])
        self.assertTrue(any(m['id'] == 'ecog_welch_psd' for m in result['recommended_methods']))
        self.assertFalse({'prep_nonspatial', 'hf_burst', 'spectral_model'} & {m['id'] for m in result['method_applicability']})
        self.assertEqual(record, before)

    def test_scalp_parameters_rejected_without_silent_cleanup(self):
        record = recording(); record['default_config']['method_config']['extensions'] = ['mne_amplitude']
        result = recommend(record)
        self.assertEqual(result['status'], 'needs_input')
        self.assertFalse(result['can_apply'])
        self.assertEqual(record['default_config']['method_config']['extensions'], ['mne_amplitude'])

    def test_event_registration_is_separate_from_disease(self):
        record = recording()
        record['default_config']['context_tags'] = {'disease': 'epilepsy'}
        a = recommend(record)
        self.assertNotIn('M07', a['selected_modules'])
        record['annotation'] = {'format': 'clinical_events_tsv', 'path': '/not-read/events.tsv'}
        b = recommend(record)
        self.assertEqual(b['status'], 'ready', b)
        self.assertIn('M07', b['selected_modules'])
        self.assertEqual(a['qc_config']['method_config'], b['qc_config']['method_config'])

    def test_whole_record_recommendation_retains_exact_coverage(self):
        result = recommend(recording(), {'scope': 'recording', 'recording_options': {'window_seconds': 120}})
        self.assertEqual(result['status'], 'ready', result)
        self.assertEqual(result['window_count'], 3)
        self.assertEqual(result['analysis_scope'], 'recording')

    def test_reader_default_eeg_is_not_anatomical_evidence(self):
        record = recording(); meta = record['metadata']
        for c in meta['channels']:
            c.update(channel_type='eeg', channel_type_source='reader_default')
        meta['format'] = 'BrainVision'
        self.assertEqual(len(registration_selection(meta, [0, 1], {}, 'ecog')['eeg_indices']), 2)
        self.assertEqual(recommend(record)['status'], 'ready')
        meta['format'] = 'FIF'
        with self.assertRaises(ValueError):
            registration_selection(meta, [0, 1], {}, 'ecog')
        self.assertEqual(recommend(record)['status'], 'needs_input')

    def test_fif_ecog_suggestion_does_not_select_misc(self):
        meta = recording()['metadata']
        meta['channels'].append({'index': 3, 'name': 'EKG1', 'unit': 'V', 'sampling_rate_hz': 1000,
                                 'channel_type': 'misc', 'channel_type_source': 'file_declared'})
        value, _ = suggestions(meta)
        self.assertEqual(value['eeg_indices'], [0, 1, 2])
        self.assertEqual(value['modality'], 'ecog')
        self.assertEqual(value['modality_evidence']['status'], 'file_declared')

    def test_ecog_documents_keep_modality_language_and_valid_clause_links(self):
        for language in ['zh-CN', 'en']:
            root = REPO / ('docs/en/ecog' if language == 'en' else 'docs/ecog')
            source = (root / 'qc-standards.md').read_text()
            markdown = Markdown(source); markdown.render()
            ids = {heading['id'] for heading in markdown.headings}
            for i in range(1, 10):
                mid = f'M{i:02d}'
                page = render_standards((root / 'modules' / f'{mid}.md').read_text(), mid, lang=language, modality='ecog')
                self.assertIn('/standards/ecog/modules/' + mid, page)
                self.assertIn('/?modality=ecog', page)
                self.assertIn(_module_clause_id(mid, language, 'ecog'), ids)
                self.assertNotIn('href="/standards/modules/', page)
        self.assertEqual(safe_url('/en/standards/ecog/modules/M05'), '/en/standards/ecog/modules/M05')
        self.assertIsNone(safe_url('/standards/ecog/../../private'))


if __name__ == '__main__': unittest.main()
