"""Contract checks plus deterministic public-library screening experiments."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ephys_qc.extra_methods import evaluate_extension, extension_specs, run_extension


def facts(count=24, seconds=40, fs=160, scheme="common_reference"):
    return {"sampling_rate_hz": fs, "n_eeg": count, "window_seconds": seconds, "verified_voltage": True,
            "reference_scheme": scheme, "comparison_groups": {"same_reference": count}}


class EligibilityTests(unittest.TestCase):
    def test_catalog_has_three_optional_methods(self):
        specs = extension_specs()
        self.assertEqual([r["id"] for r in specs], ["mne_bridge", "mne_lof", "autoreject_global"])
        self.assertEqual([r["module_id"] for r in specs], ["M05", "M05", "M03"])
        self.assertTrue(all(r["category"] == "optional" and r["source"]["license"] == "BSD-3-Clause" for r in specs))
        specs[0]["defaults"]["lm_cutoff_uv2"] = 999
        self.assertEqual(extension_specs()[0]["defaults"]["lm_cutoff_uv2"], 16)

    def test_catalog_imports_no_scientific_dependencies(self):
        source = str(Path(__file__).resolve().parents[1] / "src")
        code = f"import sys;sys.path.insert(0,{source!r});from ephys_qc.extra_methods import extension_specs;extension_specs();assert not (set(sys.modules)&{{'numpy','scipy','mne','sklearn','autoreject'}})"
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_missing_unit_and_facts_block(self):
        for row in extension_specs():
            self.assertEqual(evaluate_extension(row["id"], None)["status"], "blocked")
            self.assertEqual(evaluate_extension(row["id"], {**facts(), "verified_voltage": False})["status"], "blocked")

    def test_reference_gates_prevent_bipolar_and_unknown_similarity(self):
        for method in ("mne_bridge", "mne_lof"):
            for scheme in ("bipolar", "mixed", "unknown"):
                self.assertEqual(evaluate_extension(method, facts(scheme=scheme))["status"], "blocked")
            self.assertEqual(evaluate_extension(method, facts(scheme="linked_ears"))["status"], "ready")

    def test_comparison_group_must_cover_exact_input_once(self):
        for method in ("mne_bridge", "mne_lof"):
            for group in ({}, {"a": 12, "b": 12}, {"a": 23}, {"a": True}, {"a": "24"}, ["a"] * 23):
                self.assertEqual(evaluate_extension(method, {**facts(), "comparison_groups": group})["status"], "blocked")
            self.assertEqual(evaluate_extension(method, {**facts(), "comparison_groups": ["a"] * 24})["status"], "ready")

    def test_low_channels_and_lof_neighbor_count_are_not_silently_clamped(self):
        self.assertEqual(evaluate_extension("mne_bridge", facts(count=4))["status"], "blocked")
        self.assertEqual(evaluate_extension("mne_lof", facts(count=20))["status"], "blocked")
        self.assertEqual(evaluate_extension("mne_lof", facts(count=21))["status"], "ready")
        self.assertEqual(evaluate_extension("mne_lof", facts(count=8), {"n_neighbors": 7})["status"], "ready")

    def test_duration_and_nyquist_gates(self):
        self.assertEqual(evaluate_extension("mne_bridge", facts(fs=60))["status"], "blocked")
        self.assertEqual(evaluate_extension("mne_bridge", facts(seconds=9))["status"], "blocked")
        self.assertEqual(evaluate_extension("mne_bridge", facts(seconds=12), {"epoch_duration_seconds": 3})["status"], "blocked")
        for method in ("mne_bridge", "mne_lof", "autoreject_global"):
            self.assertEqual(evaluate_extension(method, facts(seconds=121))["status"], "blocked")

    def test_global_threshold_requires_enough_fixed_segments(self):
        self.assertEqual(evaluate_extension("autoreject_global", facts(seconds=39.99))["status"], "blocked")
        self.assertEqual(evaluate_extension("autoreject_global", facts(seconds=40))["status"], "partial")
        self.assertEqual(evaluate_extension("autoreject_global", facts(seconds=60), {"cv": 10})["status"], "blocked")
        self.assertEqual(evaluate_extension("autoreject_global", facts(seconds=50, fs=100), {"epoch_duration_seconds": 2.001})["status"], "blocked")

    def test_global_threshold_can_explore_two_bipolar_channels(self):
        self.assertEqual(evaluate_extension("autoreject_global", facts(count=2, fs=100, seconds=100, scheme="bipolar"))["status"], "partial")

    def test_parameters_are_strict_json_with_no_unreviewed_decimation(self):
        cases = [("mne_bridge", {"lm_cutoff_uv2": float("nan")}), ("mne_bridge", {"epoch_threshold": 1}),
                 ("mne_bridge", {"l_freq_hz": -1}), ("mne_lof", {"threshold": float("inf")}),
                 ("mne_lof", {"n_neighbors": True}), ("mne_lof", {"metric": "cosine"}),
                 ("autoreject_global", {"decim": 2}), ("autoreject_global", {"cv": 1}),
                 ("autoreject_global", {"random_state": -1}), ("autoreject_global", {"reject": True})]
        for method, params in cases:
            with self.assertRaises(ValueError, msg=str(params)):
                evaluate_extension(method, facts(), params)

    def test_disease_does_not_change_eligibility_or_parameters(self):
        for method in ("mne_bridge", "mne_lof", "autoreject_global"):
            self.assertEqual(evaluate_extension(method, facts()), evaluate_extension(method, {**facts(), "context": {"disease": "epilepsy", "task": "sleep"}}))


SCIENTIFIC = all(importlib.util.find_spec(package) is not None for package in ("numpy", "mne", "sklearn", "autoreject"))


@unittest.skipUnless(SCIENTIFIC, "Dedicated scientific environment required")
class ScientificAdapterTests(unittest.TestCase):
    def setUp(self):
        import numpy as np
        self.np = np
        self.rng = np.random.default_rng(41)
        self.data = self.rng.normal(0, 20e-6, (24, 160 * 40))
        self.names = [f"E{i}" for i in range(24)]

    def run_method(self, method, data=None, start=73, metadata=None):
        data = self.data if data is None else data
        before = data.copy()
        result = run_extension(method, data, 160, self.names, start, {}, facts=metadata or facts())
        self.np.testing.assert_array_equal(before, data)
        self.assertTrue(result["input_unchanged"])
        self.assertEqual(result["automatic_actions"], [])
        self.assertEqual(result["review_status"], "pending")
        self.assertEqual(len(result["data_sha256"]), 64)
        json.dumps(result, allow_nan=False)
        if result["status"] in {"completed", "partial", "failed"}:
            self.assertEqual(len(result["source"]["implementation_sha256"]), 64)
            self.assertEqual(len(result["source"]["adapter_sha256"]), 64)
        return result

    def test_no_facts_is_blocked_even_with_valid_array(self):
        result = run_extension("mne_bridge", self.data, 160, self.names, 73, {}, facts=None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(len(result["data_sha256"]), 64)

    def test_input_shape_names_finiteness_and_fact_mismatch(self):
        with self.assertRaises(ValueError):
            run_extension("mne_lof", self.data, 160, ["duplicate"] * 24, 0, {}, facts=facts())
        invalid = self.data.copy()
        invalid[0, 0] = self.np.nan
        with self.assertRaises(ValueError):
            run_extension("mne_lof", invalid, 160, self.names, 0, {}, facts=facts())
        for overrides in ({"n_eeg": 25}, {"sampling_rate_hz": 256}, {"window_seconds": 60}):
            result = self.run_method("mne_lof", metadata={**facts(), **overrides, "comparison_groups": {"a": overrides.get("n_eeg", 24)}})
            self.assertEqual(result["status"], "blocked")

    def test_bridge_detects_known_near_duplicate_pair_without_fake_onset(self):
        data = self.data.copy()
        data[1] = data[0] + self.rng.normal(0, .1e-6, data.shape[1])
        result = self.run_method("mne_bridge", data)
        self.assertEqual(result["status"], "completed", result["reason"])
        self.assertEqual([r["channel_indices"] for r in result["candidates"]], [[0, 1]])
        self.assertIsNone(result["candidates"][0]["start_seconds"])
        self.assertEqual(result["candidates"][0]["analysis_range"], [73, 113])
        self.assertEqual(result["segmentation"]["ranges"][0], {"index": 0, "start_seconds": 73, "stop_seconds": 75})
        self.assertEqual(len(result["electrical_distance_uv2"]), 24 * 23 // 2)

    def test_bridge_degenerate_distance_distribution_is_not_clean_result(self):
        data = self.np.tile(self.data[0], (24, 1))
        result = self.run_method("mne_bridge", data)
        self.assertEqual(result["status"], "failed")
        self.assertIn("不能解释", result["reason"])

    def test_lof_detects_injected_high_amplitude_channel(self):
        data = self.data.copy()
        data[-1] *= 50
        result = self.run_method("mne_lof", data)
        self.assertEqual(result["status"], "completed", result["reason"])
        self.assertEqual(result["bad_channels"], ["E23"])
        self.assertGreaterEqual(result["channel_scores"][-1]["absolute_lof"], 1.5)
        self.assertIsNone(result["candidates"][0]["start_seconds"])

    def test_global_threshold_contains_injected_segment_without_rejecting(self):
        data = self.data.copy()
        data[:, 1600:1920] *= 50
        result = self.run_method("autoreject_global", data)
        self.assertEqual(result["status"], "partial", result["reason"])
        self.assertGreater(result["estimated_thresholds_volts"]["eeg"], 0)
        candidates = {c["epoch_index"]: c for c in result["candidates"]}
        self.assertIn(5, candidates)
        self.assertEqual(candidates[5]["start_seconds"], 83)
        self.assertEqual(candidates[5]["stop_seconds"], 85)
        self.assertEqual(result["segmentation"]["n_epochs"], 20)
        self.assertEqual(result["assessment_scope"], "same_window_in_sample_descriptive_threshold")

    def test_global_threshold_reports_tail_and_original_clock_once(self):
        data = self.np.concatenate([self.data, self.data[:, :160]], axis=1)
        result = self.run_method("autoreject_global", data, start=100, metadata=facts(seconds=41))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["segmentation"]["tail_samples_not_used"], 160)
        self.assertEqual(result["segmentation"]["tail_range_not_used"], [140, 141])
        self.assertEqual(result["segmentation"]["ranges"][-1]["stop_seconds"], 140)
        for candidate in result["candidates"]:
            self.assertGreaterEqual(candidate["start_seconds"], 100)
            self.assertLessEqual(candidate["stop_seconds"], 140)

    def test_global_threshold_disease_label_does_not_change_output(self):
        base = self.run_method("autoreject_global")
        disease = self.run_method("autoreject_global", metadata={**facts(), "context": {"disease": "epilepsy"}})
        self.assertEqual(base["estimated_thresholds_volts"], disease["estimated_thresholds_volts"])
        self.assertEqual(base["candidates"], disease["candidates"])

    def test_entirely_constant_input_cannot_be_reported_clean(self):
        data = self.np.zeros_like(self.data)
        for method in ("mne_bridge", "mne_lof", "autoreject_global"):
            self.assertEqual(self.run_method(method, data)["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
