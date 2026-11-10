"""Example exploration is frozen, source-verified, and independent of live jobs."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO/'src'), str(REPO/'apps/workbench')]
from example_review import snapshot, response, ExampleWorkspace
from review_workspace import ReviewWorkspace
import test_review_workspace as fixtures


class ExampleReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.WaveformContracts(); self.fixture.setUp()
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.release, self.jid = 'a'*16, 'b'*32
        self.root.joinpath('request.json').write_text(json.dumps(fixtures.request_fixture()))
        workspace = ReviewWorkspace(self.root, reader_factory=self.fixture.factory)
        self.locations = {'findings': [{'method': 'test', 'localization': 'channel'}],
                          'default_method_ids': ['test'], 'selection_policy': 'all_saved_candidates'}
        with patch('finding_locations.locations', return_value=self.locations):
            self.saved = snapshot(workspace)
        dest = self.root/self.release/'review'; dest.mkdir(parents=True)
        (dest/(self.jid+'.json')).write_text(json.dumps(self.saved))
        self.store = SimpleNamespace(settings={'example_cache_dir':str(self.root)})

    def test_snapshot_omits_private_paths_and_scores(self):
        text = json.dumps(self.saved)
        self.assertNotIn('source_path', text)
        self.assertNotIn('/not-opened', text)
        self.assertNotIn('score', text)
        self.assertEqual(self.saved['findings'], self.locations)

    def test_offline_findings_and_context_need_no_jobs_or_raw_sources(self):
        self.assertEqual(response(self.store,self.release,self.jid,'finding-locations'),self.locations)
        ctx = response(self.store,self.release,self.jid,'waveform-context')
        self.assertFalse(ctx['waveform_available'])
        self.assertEqual(ctx['limits']['max_channels'],15)
        with self.assertRaisesRegex(ValueError,'未配置'):
            response(self.store,self.release,self.jid,'waveform-window')

    def configure(self):
        path=self.root/'source.fif';path.write_text('fixture')
        self.store.settings['example_review_sources']={self.saved['source']['source_sha256']:str(path)}

    def test_relocated_source_retains_native_values_and_ids(self):
        self.configure()
        self.assertTrue(response(self.store,self.release,self.jid,'waveform-context')['waveform_available'])
        with patch('ephys_qc.readers.open_reader',self.fixture.factory):
            wave=response(self.store,self.release,self.jid,'waveform-window',
                          {'start_seconds':.1,'duration_seconds':.2,'channel_indices':[7,2]})
        self.assertTrue(wave['frozen_source_verified'])
        self.assertFalse(wave['analysis_modified'])
        self.assertEqual([r['source_index'] for r in wave['channels']],[7,2])
        self.assertNotIn('source_path',json.dumps(wave))

    def test_wrong_source_is_refused_before_any_samples_are_returned(self):
        self.configure(); self.fixture.description['source_files'][0]['sha256']='c'*64
        with patch('ephys_qc.readers.open_reader',self.fixture.factory),self.assertRaisesRegex(ValueError,'frozen'):
            response(self.store,self.release,self.jid,'waveform-window',
                     {'start_seconds':.1,'duration_seconds':.2,'channel_indices':[7]})
        self.assertEqual(self.fixture.calls,[])

    def test_unknown_release_job_and_traversal_are_refused(self):
        for release,jid in [('c'*16,self.jid),(self.release,'d'*32),('..',self.jid)]:
            with self.subTest(release=release,jid=jid), self.assertRaises(KeyError):
                response(self.store,release,jid,'finding-locations')


if __name__=='__main__':unittest.main()
