"""State/event table tests use only known artificial labels and stdlib."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


class AnnotationContractTests(unittest.TestCase):
    """Known artificial tables test annotation semantics, not EEG accuracy."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="annotation-test-", dir=REPO / "tests")
        self.addCleanup(self.temp.cleanup)
        self.check = importlib.import_module("ephys_qc.annotations").check_annotations

    def table(self, text, kind="sleep_stages_tsv"):
        path = Path(self.temp.name) / "annotation.tsv"
        path.write_text(text, encoding="utf-8")
        return {"format": kind, "path": str(path), "label_scope": "state_not_quality"}

    def test_clinical_event_retains_original_time_without_quality_label(self):
        annotation = self.table('onset_s\tduration_s\tlabel\tlabel_type\n2996\t40\tseizure\tclinical\n', kind='clinical_events_tsv')
        annotation['label_scope'] = 'clinical_events_not_quality'
        result = self.check(annotation, 2990., 100., 256., 3600.)
        self.assertEqual(result['selected_count'], 1)
        self.assertEqual(result['events'][0]['start_sample'], 2996 * 256)
        self.assertEqual(result['clinical_event_seconds'], 40.)
        self.assertEqual(result['stage_seconds'], {})
        self.assertIsNone(result['covered_seconds'])
        self.assertFalse(result['quality_ground_truth'])
        self.assertFalse(result['used_for_signal_detection'])
        self.assertFalse(result['unlabelled_means_normal'])

    def test_clinical_event_overlap_uses_union_and_does_not_invent_normal_intervals(self):
        annotation = self.table('onset_s\tduration_s\tlabel\tlabel_type\n98\t10\ta\tclinical\n105\t10\tb\tclinical\n', kind='clinical_events_tsv')
        result = self.check(annotation, 100., 20., 100., 200.)
        self.assertEqual(result['clinical_event_seconds'], 15.)
        self.assertEqual(result['uncovered_intervals'], [])
        self.assertEqual(result['events'][0]['onset_seconds'], 98.)
        self.assertEqual(result['events'][0]['selected_start_seconds'], 100.)
        self.assertEqual(result['status'], 'completed')

    def test_absence_of_clinical_events_is_not_a_normality_claim(self):
        annotation = self.table('onset_s\tduration_s\tlabel\tlabel_type\n2996\t40\tseizure\tclinical\n', kind='clinical_events_tsv')
        result = self.check(annotation, 0., 100., 256., 3600.)
        self.assertEqual(result['selected_count'], 0)
        self.assertEqual(result['clinical_event_seconds'], 0.)
        self.assertFalse(result['unlabelled_means_normal'])

    def test_changed_registered_annotation_is_rejected(self):
        annotation = self.table('onset_s\tduration_s\tstage\n0\t30\tW\n')
        annotation['expected_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            self.check(annotation, 0., 30., 100., 30.)

    def test_hmc_style_crop_retains_recording_clock_and_two_states(self):
        annotation = self.table(
            "onset_s\tduration_s\tstage\n"
            "90\t30\tN1\n120\t30\tN1\n150\t30\tN2\n180\t30\tN2\n"
        )
        result = self.check(annotation, 100.0, 100.0, 256.0, 14104.0)
        self.assertEqual(result["stage_seconds"], {"N1": 50.0, "N2": 50.0})
        self.assertEqual(result["covered_seconds"], 100.0)
        self.assertEqual(result["uncovered_intervals"], [])
        self.assertEqual(result["events"][0]["onset_seconds"], 90.0)
        self.assertEqual(result["events"][0]["selected_start_seconds"], 100.0)
        self.assertEqual(result["events"][0]["start_sample"], 25600)
        self.assertEqual(result["events"][-1]["stop_sample"], 51200)
        self.assertFalse(result["quality_ground_truth"])
        self.assertFalse(result["used_for_signal_detection"])

    def test_unannotated_tail_is_unknown_not_forward_filled_wake(self):
        annotation = self.table("onset_s\tduration_s\tstage\n14070\t30\tW\n")
        result = self.check(annotation, 14070.0, 34.0, 256.0, 14104.0)
        self.assertEqual(result["stage_seconds"], {"W": 30.0})
        self.assertEqual(result["covered_seconds"], 30.0)
        self.assertEqual(result["uncovered_intervals"], [
            {"start_seconds": 14100.0, "stop_seconds": 14104.0, "label": "unknown"}
        ])
        self.assertEqual(result["status"], "partial")

    def test_point_events_obey_half_open_window_and_keep_global_samples(self):
        annotation = self.table(
            "onset\tduration\tevent_name\tevent_value\n"
            "99.5\t0\tbefore\t1\n100\t0\tat_start\t2\n"
            "150\t0\tmiddle\t3\n200\t0\tat_stop\t4\n",
            kind="bids_events_tsv",
        )
        result = self.check(annotation, 100.0, 100.0, 256.0, 300.0)
        self.assertEqual([e["label"] for e in result["events"]], ["at_start", "middle"])
        self.assertEqual([e["start_sample"] for e in result["events"]], [25600, 38400])
        self.assertIsNone(result["covered_seconds"])
        self.assertEqual(result["stage_seconds"], {})
        self.assertFalse(result["quality_ground_truth"])

    def test_ds_style_64_second_event_is_four_seconds_into_selected_window(self):
        annotation = self.table(
            "onset\tduration\tevent_name\tevent_value\n64\t0\tstimulus\t1\n",
            kind="bids_events_tsv",
        )
        result = self.check(annotation, 60.0, 60.0, 512.0, 733.0)
        self.assertEqual(result["selected_count"], 1)
        event = result["events"][0]
        self.assertEqual(event["onset_seconds"], 64.0)
        self.assertEqual(event["start_sample"], 32768)
        self.assertEqual(event["start_sample"] - result["input_range"]["start_sample"], 2048)
        self.assertFalse(result["quality_ground_truth"])
        self.assertFalse(result["used_for_signal_detection"])

    def test_overlap_is_flagged_and_union_coverage_is_not_double_counted(self):
        annotation = self.table("onset_s\tduration_s\tstage\n0\t30\tN1\n20\t30\tN2\n")
        result = self.check(annotation, 0.0, 50.0, 256.0, 100.0)
        self.assertEqual(result["covered_seconds"], 50.0)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["issues"])

    def test_nonfinite_and_negative_annotation_times_are_not_mapped(self):
        annotation = self.table(
            "onset_s\tduration_s\tstage\n"
            "nan\t30\tN1\n-1\t30\tN2\n0\tinf\tN3\n0\t-2\tR\n"
        )
        result = self.check(annotation, 0.0, 60.0, 256.0, 100.0)
        self.assertEqual(result["valid_rows"], 0)
        self.assertEqual(result["events"], [])
        self.assertEqual(result["covered_seconds"], 0.0)
        self.assertEqual(len(result["issues"]), 4)
        json.dumps(result, allow_nan=False)

    def test_bad_explicit_end_is_not_silently_ignored(self):
        for end in ("29", "nan", "inf"):
            with self.subTest(end=end):
                annotation = self.table(
                    f"onset_s\tduration_s\tend_s\tstage\n0\t30\t{end}\tN1\n"
                )
                result = self.check(annotation, 0.0, 60.0, 256.0, 100.0)
                self.assertEqual(result["valid_rows"], 0)
                self.assertTrue(result["issues"])

    def test_annotation_source_hash_and_bytes_remain_unchanged(self):
        annotation = self.table("onset_s\tduration_s\tstage\n0\t30\tN1\n")
        before = Path(annotation["path"]).read_bytes()
        result = self.check(annotation, 0.0, 30.0, 256.0, 100.0)
        self.assertEqual(Path(annotation["path"]).read_bytes(), before)
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(len(result["sources"][0]["sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
