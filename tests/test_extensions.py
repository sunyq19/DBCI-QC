"""Extension contracts and small MNE probes; never read participant data."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ephys_qc.extensions import extension_specs, evaluate_extension, run_extension


def facts(**overrides):
    return {"sampling_rate_hz": 512.0, "n_eeg": 4, "window_seconds": 60.0,
            "verified_voltage": True, "preprocessing_highpass_hz": .01,
            "preprocessing_lowpass_hz": 250.0, **overrides}


class ExtensionPlanningTests(unittest.TestCase):
    def test_specs_are_independent_optional_objects(self):
        first = extension_specs()
        self.assertEqual({s["id"] for s in first}, {"mne_amplitude", "mne_muscle", "mne_bridge", "mne_lof", "autoreject_global"})
        self.assertEqual(len(first), len({s['id'] for s in first}))
        self.assertTrue(all(s["category"] == "optional" and s["source"]["license"] == "BSD-3-Clause" for s in first))
        first[0]["defaults"]["flat_volts"] = 77
        self.assertEqual(extension_specs()[0]["defaults"]["flat_volts"], 0)
        json.dumps(extension_specs(), allow_nan=False)

    def test_amplitude_defaults_do_not_enable_peak(self):
        p = evaluate_extension("mne_amplitude", facts())
        self.assertEqual(p["status"], "ready")
        self.assertIsNone(p["parameters"]["peak_volts"])
        self.assertEqual(p["parameters"]["flat_volts"], 0)

    def test_lower_sampling_rates_cannot_run_default_muscle_band(self):
        for rate in (160, 256, 280):
            with self.subTest(rate=rate):
                self.assertEqual(evaluate_extension("mne_muscle", facts(sampling_rate_hz=rate))["status"], "blocked")
        self.assertEqual(evaluate_extension("mne_muscle", facts())["status"], "ready")

    def test_unknown_passband_is_partial_not_confirmed(self):
        self.assertEqual(evaluate_extension("mne_muscle", facts(preprocessing_lowpass_hz=None))["status"], "partial")
        self.assertEqual(evaluate_extension("mne_muscle", facts(preprocessing_highpass_hz=None, preprocessing_lowpass_hz=None))["status"], "partial")

    def test_known_filtering_must_preserve_target_band(self):
        for values in ({"preprocessing_lowpass_hz": 100}, {"preprocessing_lowpass_hz": 140},
                       {"preprocessing_highpass_hz": 110}, {"preprocessing_lowpass_hz": float("nan")}):
            with self.subTest(values=values):
                self.assertEqual(evaluate_extension("mne_muscle", facts(**values))["status"], "blocked")

    def test_unverified_units_and_invalid_facts_are_blocked(self):
        for values in ({"verified_voltage": False}, {"verified_voltage": "V"}, {"n_eeg": True},
                       {"sampling_rate_hz": float("nan")}, {"window_seconds": 0}, {"window_seconds": 121}):
            with self.subTest(values=values):
                self.assertEqual(evaluate_extension("mne_amplitude", facts(**values))["status"], "blocked")

    def test_short_muscle_windows_are_blocked(self):
        self.assertEqual(evaluate_extension("mne_muscle", facts(window_seconds=9.99))["status"], "blocked")

    def test_parameter_json_is_strict(self):
        trials = [("mne_amplitude", {"flat_volts": -1}), ("mne_amplitude", {"peak_volts": 0}),
                  ("mne_amplitude", {"flat_volts": None, "peak_volts": None}),
                  ("mne_amplitude", {"min_duration_seconds": float("nan")}),
                  ("mne_amplitude", {"bad_percent": 0}), ("mne_amplitude", {"bad_percent": 101}),
                  ("mne_amplitude", {"flat_volts": 1, "peak_volts": .1}),
                  ("mne_muscle", {"threshold_z": True}), ("mne_muscle", {"threshold_z": float("inf")}),
                  ("mne_muscle", {"filter_freq_hz": [30, 100]}),
                  ("mne_muscle", {"min_length_good_seconds": -1}), ("mne_muscle", {"unknown": 1})]
        for extension, params in trials:
            with self.subTest(extension=extension, params=params), self.assertRaises(ValueError):
                evaluate_extension(extension, facts(), params)

    def test_inputs_are_not_mutated_by_preflight(self):
        original = facts()
        params = {"filter_freq_hz": [110, 140]}
        before = copy.deepcopy((original, params))
        evaluate_extension("mne_muscle", original, params)
        self.assertEqual((original, params), before)

    def test_unknown_extension_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_extension("pretend_ica", facts())


_SCIENCE_AVAILABLE = importlib.util.find_spec("numpy") is not None and importlib.util.find_spec("mne") is not None


@unittest.skipUnless(_SCIENCE_AVAILABLE, "Run numerical adapter probes in the existing scientific environment")
class ExtensionExecutionTests(unittest.TestCase):
    def test_constant_channel_is_retained_even_without_time_annotation(self):
        import numpy as np
        data = np.zeros((1, 2560), dtype=float)
        result = run_extension("mne_amplitude", data, 256, ["flat"], 100, None)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["candidate_interval_count"], 0)
        self.assertEqual(result["candidate_channel_count"], 1)
        self.assertEqual(result["bad_channels"], ["flat"])
        self.assertEqual(len(result["source"]["implementation_sha256"]), 64)
        self.assertEqual(result["candidates"][0]["localization"], "channel_only")
        self.assertIsNone(result["candidates"][0]["start_seconds"])
        np.testing.assert_array_equal(data, 0)
        json.dumps(result, allow_nan=False)

    def test_short_flat_interval_preserves_global_offset_without_channel_claim(self):
        import numpy as np
        data = (np.random.default_rng(9).normal(size=(2, 2560)) * 1e-6)
        data[0, 512:565] = 0
        before = data.copy()
        result = run_extension("mne_amplitude", data, 256, ["a", "b"], 100, None)
        intervals = [c for c in result["candidates"] if c["localization"] == "interval_only"]
        self.assertTrue(intervals)
        self.assertTrue(any(101.99 <= c["start_seconds"] <= 102.01 for c in intervals))
        self.assertTrue(all(c["channel_index"] is None for c in intervals))
        np.testing.assert_array_equal(data, before)

    def test_muscle_returns_only_global_intervals_and_owns_input_copy(self):
        import mne
        import numpy as np
        data = np.random.default_rng(7).normal(size=(2, 5120)) * 1e-6
        before = data.copy()
        def fake(raw, **kwargs):
            self.assertEqual(raw.first_samp, 0)
            self.assertEqual(kwargs["ch_type"], "eeg")
            raw._data[:] = 0  # A hostile backend still must not mutate the caller.
            return mne.Annotations([2.0], [.5], ["BAD_muscle"]), np.linspace(-1, 6, 5120)
        with patch("mne.preprocessing.annotate_muscle_zscore", new=fake):
            result = run_extension("mne_muscle", data, 512, ["a", "b"], 60, None)
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["candidates"][0]["start_seconds"], 62)
        self.assertEqual(result["candidates"][0]["stop_seconds"], 62.5)
        self.assertIsNone(result["candidates"][0]["channel_index"])
        self.assertEqual(result["candidate_channel_count"], 0)
        self.assertTrue(result["input_unchanged"])
        np.testing.assert_array_equal(data, before)

    def test_undefined_muscle_scores_do_not_become_a_clean_result(self):
        import mne
        import numpy as np
        data = np.random.default_rng(8).normal(size=(1, 5120)) * 1e-6
        def fake(raw, **kwargs):
            return mne.Annotations([], [], []), np.full(5120, np.nan)
        with patch("mne.preprocessing.annotate_muscle_zscore", new=fake):
            result = run_extension("mne_muscle", data, 512, ["a"], 0, None)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["score_summary"]["finite_count"], 0)
        self.assertTrue(all(v is None for v in result["scores_z"]))
        json.dumps(result, allow_nan=False)

    def test_constant_muscle_input_is_blocked_without_silent_channel_drop(self):
        import numpy as np
        result = run_extension("mne_muscle", np.zeros((2, 5120)), 512, ["a", "b"], 0, None)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["constant_channel_names"], ["a", "b"])
        self.assertEqual(result["automatic_actions"], [])

    def test_nonfinite_input_is_not_imputed(self):
        import numpy as np
        with self.assertRaises(ValueError):
            run_extension("mne_amplitude", np.array([[0, np.nan]]), 256, ["a"], 0, None)


if __name__ == "__main__":
    unittest.main()
