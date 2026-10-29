"""Metadata-only recommendation tests; no EDF reads or algorithm execution."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ephys_qc.recommendations import recommend, POLICY_VERSION
from ephys_qc.planning import build_plan


def recording(count=24, fs=512, duration=60, reference="linked_ears"):
    return {"id": "synthetic-registration", "source_path": "/not-opened/example.edf", "modality": "scalp_eeg",
            "expected_sha256": "a" * 64, "metadata": {"format": "EDF", "duration_seconds": 200,
                "channels": [{"index": i, "name": f"E{i}", "unit": "uV", "sampling_rate_hz": fs} for i in range(count)], "size_bytes": 1024},
            "reference_scheme": reference, "default_config": {"selection": {"eeg_indices": list(range(count)), "reference_indices": {},
                "start_seconds": 10, "duration_seconds": duration}, "method_config": {"comparison_groups": ["same_reference"] * count}},
            "preprocessing": {"verified": False}, "verified_electrode_coordinates": False}


def method_ids(rows):
    return {row["id"] for row in rows}


def reverse_objects(value):
    if isinstance(value, dict):
        return {key: reverse_objects(value[key]) for key in reversed(value)}
    if isinstance(value, list):
        return [reverse_objects(item) for item in value]
    return value


class RecommendationTests(unittest.TestCase):
    def assert_round_trip(self, record, result):
        self.assertEqual(result["status"], "ready", result["summary"])
        self.assertTrue(result["can_apply"])
        plan = build_plan(record, result["selected_modules"], result["qc_config"])
        for key in ("plan_id", "selected_modules", "qc_config", "data_tags", "method_applicability"):
            self.assertEqual(result[key], plan[key], key)
        self.assertEqual(result["plan_warnings"], plan["warnings"])
        self.assertIsNone(result["quality_score"])
        json.dumps(result, allow_nan=False)
        return plan

    def test_default_is_conservative_and_directly_plannable(self):
        r = recording()
        result = recommend(r)
        self.assert_round_trip(r, result)
        self.assertEqual(result["qc_config"]["method_config"]["extensions"], ["mne_amplitude"])
        params = result["qc_config"]["method_config"]["extension_parameters"]["mne_amplitude"]
        self.assertIsNone(params["peak_volts"])
        self.assertEqual(params["flat_volts"], 0)
        self.assertEqual(method_ids(result["optional_methods"]), {"mne_bridge", "mne_lof", "mne_muscle", "autoreject_global"})
        self.assertFalse(result["scope"]["signal_read"])
        self.assertFalse(result["scope"]["job_created"])

    def test_policy_is_stable_and_input_objects_not_mutated(self):
        r, config = recording(), {"selection": {"start_seconds": 20}}
        before_r, before_config = copy.deepcopy(r), copy.deepcopy(config)
        a, b = recommend(r, config), recommend(r, config)
        self.assertEqual(a, b)
        self.assertEqual(a["policy_version"], POLICY_VERSION)
        self.assertEqual(len(a["recommendation_id"]), 64)
        self.assertEqual(r, before_r)
        self.assertEqual(config, before_config)

    def test_object_key_order_does_not_change_fingerprint(self):
        r = recording()
        config = {"selection": {"duration_seconds": 40, "start_seconds": 25}, "context_tags": {"task": "sleep", "age_group": "child"}}
        self.assertEqual(recommend(r, config)["recommendation_id"], recommend(reverse_objects(r), reverse_objects(config))["recommendation_id"])
        self.assertEqual(recommend(r)["recommendation_id"], recommend(r, {})["recommendation_id"])

    def test_config_or_source_change_requires_new_recommendation(self):
        r = recording()
        base = recommend(r)
        changed = recommend(r, {"selection": {"start_seconds": 11}})
        self.assertNotEqual(base["recommendation_id"], changed["recommendation_id"])
        self.assertNotEqual(base["plan_id"], changed["plan_id"])
        source = copy.deepcopy(r)
        source["expected_sha256"] = "b" * 64
        self.assertNotEqual(base["recommendation_id"], recommend(source)["recommendation_id"])

    def test_existing_explicit_thresholds_and_selection_are_preserved(self):
        r = recording()
        config = {"selection": {"start_seconds": 20, "duration_seconds": 80}, "method_config": {
            "extensions": ["mne_lof", "autoreject_global"], "bad_channels": {"min_group_channels": 8},
            "extension_parameters": {"mne_amplitude": {"flat_volts": 1e-9, "peak_volts": 1e-3}, "mne_lof": {"threshold": 2.1}}}}
        result = recommend(r, config)
        self.assert_round_trip(r, result)
        self.assertEqual(result["qc_config"]["selection"]["start_seconds"], 20)
        self.assertEqual(result["qc_config"]["method_config"]["bad_channels"]["min_group_channels"], 8)
        parameters = result["qc_config"]["method_config"]["extension_parameters"]
        self.assertEqual(parameters["mne_amplitude"]["flat_volts"], 1e-9)
        self.assertEqual(parameters["mne_amplitude"]["peak_volts"], 1e-3)
        self.assertEqual(parameters["mne_lof"]["threshold"], 2.1)
        self.assertEqual(result["current_extensions"], ["autoreject_global", "mne_lof"])
        self.assertTrue(result["extension_selection_changed"])
        self.assertNotIn("autoreject_global", result["qc_config"]["method_config"]["extensions"])

    def test_background_changes_review_focus_but_never_thresholds_or_choices(self):
        r = recording()
        base = recommend(r)
        altered = recommend(r, {"context_tags": {"disease": "epilepsy", "task": "sleep", "age_group": "child"}})
        self.assertEqual(base["selected_modules"], altered["selected_modules"])
        self.assertEqual(base["qc_config"]["method_config"], altered["qc_config"]["method_config"])
        for key in ("recommended_methods", "optional_methods", "blocked_methods"):
            self.assertEqual(method_ids(base[key]), method_ids(altered[key]))
        self.assertNotEqual(base["review_focus"], altered["review_focus"])
        self.assertNotEqual(base["recommendation_id"], altered["recommendation_id"])
        self.assertNotIn("M07", altered["selected_modules"])

    def test_motor_imagery_has_distinct_context_without_changing_detection(self):
        r = recording()
        motor = recommend(r, {"context_tags": {"task": "motor"}})
        imagery = recommend(r, {"context_tags": {"task": "motor_imagery"}})
        self.assert_round_trip(r, imagery)
        self.assertEqual(motor["selected_modules"], imagery["selected_modules"])
        self.assertEqual(motor["qc_config"]["method_config"], imagery["qc_config"]["method_config"])
        self.assertIn("不证明发生了实际动作", "".join(imagery["review_focus"]))
        self.assertNotIn("任务动作可改变", "".join(imagery["review_focus"]))
        task = next(t for t in imagery["data_tags"] if t["key"] == "task")
        self.assertEqual(task["display"], "运动想象")

    def test_unknown_bipolar_mixed_reference_never_enables_similarity_extensions(self):
        for reference in ("unknown", "bipolar", "mixed"):
            r = recording(reference=reference)
            result = recommend(r)
            self.assert_round_trip(r, result)
            self.assertIn("M05", result["selected_modules"])
            self.assertTrue({"mne_bridge", "mne_lof"} <= method_ids(result["blocked_methods"]))
            self.assertFalse({"mne_bridge", "mne_lof"} & method_ids(result["optional_methods"]))
            self.assertEqual(result["qc_config"]["method_config"]["comparison_groups"], ["same_reference"] * 24)

    def test_missing_comparison_group_is_not_invented(self):
        r = recording()
        r["default_config"]["method_config"]["comparison_groups"] = None
        result = recommend(r)
        self.assert_round_trip(r, result)
        self.assertIsNone(result["qc_config"]["method_config"]["comparison_groups"])
        gate = next(m for m in result["method_applicability"] if m["id"] == "prep_nonspatial")
        self.assertEqual(gate["status"], "partial")
        self.assertIn("M05", result["selected_modules"])

    def test_low_sampling_no_auxiliary_omits_unassessable_m06(self):
        r = recording(fs=40)
        result = recommend(r)
        self.assert_round_trip(r, result)
        self.assertNotIn("M06", result["selected_modules"])
        self.assertTrue({"ecg_locked", "eog_locked", "hf_burst", "mne_muscle"} <= method_ids(result["blocked_methods"]))

    def test_same_clock_eog_supports_m06_in_low_rate_sleep(self):
        r = recording(count=3, fs=100, reference="bipolar")
        r["default_config"]["selection"].update(eeg_indices=[0, 1], reference_indices={"eog": 2})
        r["default_config"]["method_config"]["comparison_groups"] = None
        r["default_config"]["context_tags"] = {"task": "sleep"}
        result = recommend(r)
        self.assert_round_trip(r, result)
        self.assertIn("M06", result["selected_modules"])
        self.assertIn("eog_locked", method_ids(result["recommended_methods"]))
        self.assertNotIn("hf_burst", method_ids(result["recommended_methods"]))
        self.assertTrue({"mne_bridge", "mne_lof", "mne_muscle"} <= method_ids(result["blocked_methods"]))

    def test_m06_honors_existing_custom_duration_gate(self):
        result = recommend(recording(duration=20), {"method_config": {"muscle": {"min_duration_seconds": 30}}})
        self.assertNotIn("M06", result["selected_modules"])
        self.assertIn("hf_burst", method_ids(result["blocked_methods"]))

    def test_annotations_only_enable_matching_timeline_without_reading_files(self):
        for fmt, expected in (("sleep_stages_tsv", "sleep_timeline"), ("bids_events_tsv", "task_timeline"), ("clinical_events_tsv", "clinical_timeline")):
            r = recording()
            r["annotation"] = {"format": fmt, "path": "/never-read/labels.tsv", "label_scope": "not_quality"}
            with patch("builtins.open", side_effect=AssertionError("No file reads allowed")), patch.object(Path, "read_text", side_effect=AssertionError("No file reads allowed")):
                result = recommend(r)
            self.assert_round_trip(r, result)
            self.assertIn("M07", result["selected_modules"])
            self.assertIn(expected, method_ids(result["recommended_methods"]))

    def test_annotation_path_missing_or_format_unknown_does_not_enable_m07(self):
        for annotation in ({"format": "clinical_events_tsv"}, {"format": "unsupported_labels", "path": "/a/b"}):
            r = recording(); r["annotation"] = annotation
            result = recommend(r)
            self.assert_round_trip(r, result)
            self.assertNotIn("M07", result["selected_modules"])
            self.assertIn("annotation", {m["key"] for m in result["missing_fields"]})

    def test_coordinates_never_enable_unimplemented_ica_or_ransac(self):
        for present in (False, True):
            r = recording(); r["verified_electrode_coordinates"] = present
            result = recommend(r)
            expected = {"pyprep_ransac", "autoreject_epochs", "ica_iclabel"}
            self.assertTrue(expected <= method_ids(result["blocked_methods"]))
            self.assertFalse(expected & method_ids(result["recommended_methods"]))

    def test_autoreject_is_optional_even_with_verified_epochs(self):
        r = recording(); r["verified_epochs"] = True
        result = recommend(r, {"method_config": {"extensions": ["autoreject_global"]}})
        self.assertIn("autoreject_global", method_ids(result["optional_methods"]))
        self.assertNotIn("autoreject_global", method_ids(result["recommended_methods"]))

    def test_short_window_keeps_existing_method_gates(self):
        r = recording(duration=.05, fs=160)
        result = recommend(r)
        self.assert_round_trip(r, result)
        self.assertEqual(result["qc_config"]["method_config"]["extensions"], [])
        self.assertTrue({"mne_amplitude", "autoreject_global", "mne_bridge", "mne_lof"} <= method_ids(result["blocked_methods"]))

    def test_missing_modality_is_not_guessed_from_profile_or_names(self):
        r = recording(); del r["modality"]; r["profile_id"] = "adult_multichannel_rest"
        result = recommend(r)
        self.assertEqual(result["status"], "needs_input")
        self.assertFalse(result["can_apply"])
        self.assertIsNone(result["plan_id"])
        self.assertTrue(any(m["key"] == "modality" and m["blocking"] for m in result["missing_fields"]))

    def test_other_formats_and_modalities_are_explicitly_unsupported(self):
        for modality in ("seeg", "ecog", "neuropixels"):
            r = recording(); r["modality"] = modality
            result = recommend(r)
            self.assertEqual(result["status"], "unsupported")
            self.assertFalse(result["can_apply"])
            self.assertEqual(result["selected_modules"], [])
        for fmt in ("CSV", "NWB", "unknown-format"):
            r = recording(); r["metadata"]["format"] = fmt
            self.assertEqual(recommend(r)["status"], "unsupported")

    def test_registered_reader_formats_share_the_same_qc_contract(self):
        for fmt in ('EDF', 'EDF+', 'BDF', 'FIF', 'BrainVision', 'EEGLAB'):
            r = recording(); r['metadata']['format'] = fmt
            result = recommend(r)
            self.assertEqual(result['status'], 'ready', fmt)
            self.assertTrue(result['can_apply'])

    def test_missing_core_metadata_is_structured_needs_input(self):
        cases = []
        for key in ("id", "source_path", "metadata"):
            r = recording(); del r[key]; cases.append(r)
        for key in ("format", "channels", "duration_seconds"):
            r = recording(); del r["metadata"][key]; cases.append(r)
        r = recording(); del r["default_config"]["selection"]["eeg_indices"]; cases.append(r)
        r = recording(); r["metadata"]["channels"][0]["index"] = 1; cases.append(r)
        for r in cases:
            result = recommend(r)
            self.assertEqual(result["status"], "needs_input", str(r))
            self.assertFalse(result["can_apply"])
            self.assertTrue(any(m["blocking"] for m in result["missing_fields"]))

    def test_units_must_be_voltage_and_clock_mismatch_is_not_resampled(self):
        r = recording(); r["metadata"]["channels"][0]["unit"] = "counts"
        result = recommend(r)
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("metadata.channels.unit", {m["key"] for m in result["missing_fields"]})
        r = recording(); r["metadata"]["channels"][0]["sampling_rate_hz"] = 1
        self.assertEqual(recommend(r)["status"], "needs_input")

    def test_invalid_config_is_not_silently_repaired(self):
        for config in ({"selection": {"duration_seconds": 121}}, {"selection": {"eeg_indices": [0, 0]}},
                       {"method_config": {"extensions": ["ica_iclabel"]}},
                       {"method_config": {"extension_parameters": {"mne_lof": {"n_neighbors": -1}}}}):
            result = recommend(recording(), config)
            self.assertEqual(result["status"], "needs_input")
            self.assertFalse(result["can_apply"])
            self.assertEqual(result["recommended_methods"], [])

    def test_nonfinite_or_non_json_values_raise_clear_validation_error(self):
        with self.assertRaises(ValueError):
            recommend(recording(), {"selection": {"duration_seconds": float("nan")}})
        with self.assertRaises(ValueError):
            recommend(recording(), {"selection": {"eeg_indices": {0, 1}}})

    def test_no_heavy_import_or_signal_reads_for_suggestion(self):
        code = (f"import sys;sys.path.insert(0,{str(REPO / 'src')!r});"
                "from ephys_qc.recommendations import recommend;recommend({'modality':'scalp_eeg'});"
                "assert not (set(sys.modules)&{'numpy','scipy','mne','sklearn','autoreject','brainelecqc'})")
        subprocess.run([sys.executable, "-c", code], check=True)


class RegisteredMetadataTests(unittest.TestCase):
    @unittest.skipUnless((REPO / ".local/workbench.json").is_file(), "Local registration is intentionally not distributed")
    def test_eight_registered_inputs_round_trip_without_opening_signal_files(self):
        wanted = {"eegmmidb-s001r01", "hmc-sn062", "ds002034-sub01", "ds002034-sub02", "eegmmidb-s001r02", "eegmmidb-s001r03", "sleep-edfx-sc4001", "chbmit-chb01-03"}
        registered = json.loads((REPO / ".local/workbench.json").read_text())["inputs"]
        selected = [r for r in registered if r["id"] in wanted]
        self.assertEqual({r["id"] for r in selected}, wanted)
        for record in selected:
            before = copy.deepcopy(record)
            with patch("builtins.open", side_effect=AssertionError("No signal or annotation reads")), patch.object(Path, "read_text", side_effect=AssertionError("No signal or annotation reads")):
                result = recommend(record)
            self.assertEqual(result["status"], "ready", record["id"] + result["summary"])
            self.assertEqual(record, before)
            plan = build_plan(record, result["selected_modules"], result["qc_config"])
            for key in ("plan_id", "qc_config", "selected_modules", "data_tags", "method_applicability"):
                self.assertEqual(result[key], plan[key], record["id"] + key)
            self.assertEqual(result["qc_config"]["method_config"]["extensions"], ["mne_amplitude"])
            self.assertEqual("M07" in result["selected_modules"], record["id"] not in {"eegmmidb-s001r01", "eegmmidb-s001r02"})
            options = method_ids(result["optional_methods"])
            self.assertIn("autoreject_global", options)
            if record["id"].startswith("ds002034"):
                self.assertTrue({"mne_bridge", "mne_lof", "mne_muscle"} <= options)
            else:
                self.assertTrue({"mne_bridge", "mne_lof"} <= method_ids(result["blocked_methods"]))


if __name__ == "__main__":
    unittest.main()
