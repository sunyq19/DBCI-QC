"""Export correctness: real deduction arithmetic, source mapping and missing evidence."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from ephys_qc.report_export import score_rows, evidence_figure, pdf_bytes
import test_report_view as fixtures


class ReportExportTests(unittest.TestCase):
    setUp = fixtures.ReportViewTests.setUp
    view = fixtures.ReportViewTests.view
    def test_deductions_and_missing_component(self):
        view=self.view();rows=score_rows(view)
        self.assertAlmostEqual(rows[1]['deduction'],100*math.sqrt(.5**2/2))
        view['score']['components'][1]['value']=None
        self.assertIsNone(score_rows(view)[1]['deduction'])
        self.assertIn('未计分',score_rows(view)[1]['reason'])

    @unittest.skipUnless(importlib.util.find_spec('reportlab'), 'optional PDF dependency')
    def test_pdf_preserves_score_and_handles_unavailable_figure(self):
        view=self.view();before=copy.deepcopy(view)
        data=pdf_bytes(view,figure_notes=['来源不可用'],job_id=self.jid)
        self.assertTrue(data.startswith(b'%PDF-'))
        self.assertEqual(view,before)
        self.assertIn(b'/Count 2',data)

    @unittest.skipUnless(importlib.util.find_spec('matplotlib'), 'optional plotting dependency')
    def test_figure_maps_channel_identity_and_refuses_unverified_source(self):
        (self.artifacts/'M02_selection.json').write_text(json.dumps({'channels':[{'channel_id':'a','source_index':17}]}))
        called=[]
        class Workspace:
            root=self.job
            def waveform(inner,**kwargs):
                called.append(kwargs)
                return {'frozen_source_verified':False}
        before={p:p.read_bytes() for p in self.artifacts.iterdir()}
        figure,notes=evidence_figure(self.view(),Workspace())
        self.assertIsNone(figure);self.assertTrue(notes)
        self.assertEqual(called[0]['channel_indices'],[17])
        self.assertLessEqual(called[0]['duration_seconds'],10)
        for p,raw in before.items():self.assertEqual(p.read_bytes(),raw)

if __name__=='__main__':unittest.main()
