"""Independent planner contract tests: no EEG data, backend, or downloads.

These tests verify engineering and scientific guardrails, not detector accuracy.
Run with ``python -m unittest discover -s tests -p test_modular_core.py -v``.
"""

from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
core = importlib.import_module("ephys_qc.core")

MANDATORY = {"M01", "M02", "M08", "M09"}
MODULES = {f"M{i:02d}" for i in range(1, 10)}


def record(*, n_eeg=8, auxiliary=False, duration=300.0):
    channels = [
        {"index": i, "name": f"EEG{i}", "sampling_rate_hz": 256.0}
        for i in range(n_eeg)
    ]
    references = {}
    if auxiliary:
        for kind in ("eog", "ecg", "emg"):
            index = len(channels)
            references[kind] = index
            channels.append(
                {"index": index, "name": kind.upper(), "sampling_rate_hz": 256.0}
            )
    return {
        "id": "synthetic-record",
        "dataset_id": "synthetic-no-real-person",
        "profile_id": "adult_multichannel_rest",
        "metadata": {
            "duration_seconds": duration,
            "channels": channels,
            "size_bytes": 256 + int(duration * 256 * len(channels) * 2),
        },
        "default_config": {
            "selection": {
                "eeg_indices": list(range(n_eeg)),
                "reference_indices": references,
                "start_seconds": 0.0,
                "duration_seconds": 60.0,
            },
            "method_config": {"comparison_groups": ["same_reference"] * n_eeg},
        },
    }


def node(plan, module_id):
    return next(n for n in plan["nodes"] if n["id"] == module_id)


class PlannerContractTests(unittest.TestCase):
    def test_catalog_has_nine_unique_described_modules(self):
        catalog = core.catalog()
        self.assertIsInstance(catalog, list)
        self.assertEqual({item["id"] for item in catalog}, MODULES)
        self.assertEqual(len(catalog), 9)
        self.assertTrue(all(item.get("name") for item in catalog))
        json.dumps(catalog, allow_nan=False)

    def test_empty_optional_selection_keeps_mandatory_entry_and_exit(self):
        plan = core.build_plan(record(), selected_modules=[])
        self.assertEqual(set(plan["selected_modules"]), MANDATORY)
        for item in plan["nodes"]:
            if item["id"] not in MANDATORY:
                self.assertEqual(item["status"], "skipped")

    def test_default_plan_is_json_serializable_and_has_explicit_decisions(self):
        plan = core.build_plan(record())
        self.assertEqual(set(plan["selected_modules"]), MODULES)
        self.assertEqual(len(plan["nodes"]), 9)
        self.assertTrue(plan["plan_id"])
        self.assertIsInstance(plan["warnings"], list)
        for item in plan["nodes"]:
            self.assertIn(item["status"], {"ready", "partial", "skipped"})
            self.assertIsInstance(item["depends_on"], list)
            self.assertIsInstance(item["reason"], str)
            if item["status"] != "ready":
                self.assertTrue(item["reason"].strip())
        json.dumps(plan, allow_nan=False)

    def test_m06_adds_m03_and_dependency_precedes_consumer(self):
        plan = core.build_plan(record(auxiliary=True), selected_modules=["M06"])
        ids = [n["id"] for n in plan["nodes"]]
        self.assertEqual(set(plan["selected_modules"]), MANDATORY | {"M03", "M06"})
        self.assertIn("M03", plan["auto_added_modules"])
        self.assertIn("M03", node(plan, "M06")["depends_on"])
        self.assertLess(ids.index("M03"), ids.index("M06"))
        self.assertLess(ids.index("M06"), ids.index("M08"))
        self.assertLess(ids.index("M08"), ids.index("M09"))
        for item in plan["nodes"]:
            if item["id"] not in plan["selected_modules"]:
                continue
            for dependency in item["depends_on"]:
                self.assertIn(dependency, plan["selected_modules"])
                self.assertLess(ids.index(dependency), ids.index(item["id"]))

    def test_unknown_module_rejected(self):
        with self.assertRaises(ValueError):
            core.build_plan(record(), selected_modules=["M99"])

    def test_repeated_modules_do_not_duplicate_execution(self):
        plan = core.build_plan(record(), selected_modules=["M03", "M03", "M01"])
        ids = [n["id"] for n in plan["nodes"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_plan_does_not_mutate_caller_record_or_config(self):
        source = record(auxiliary=True)
        config = deepcopy(source["default_config"])
        original_source, original_config = deepcopy(source), deepcopy(config)
        plan = core.build_plan(source, qc_config=config)
        self.assertEqual(source, original_source)
        self.assertEqual(config, original_config)
        plan["qc_config"]["selection"]["eeg_indices"].append(12345)
        self.assertEqual(source, original_source)
        self.assertEqual(config, original_config)

    def test_plan_id_is_deterministic_under_json_object_key_reordering(self):
        source = record(auxiliary=True)
        reordered = json.loads(json.dumps(source, sort_keys=True))
        self.assertEqual(
            core.build_plan(source)["plan_id"], core.build_plan(reordered)["plan_id"]
        )

    def test_changed_analysis_window_changes_plan_identity(self):
        source = record()
        config = deepcopy(source["default_config"])
        config["selection"]["start_seconds"] = 30.0
        self.assertNotEqual(
            core.build_plan(source)["plan_id"],
            core.build_plan(source, qc_config=config)["plan_id"],
        )

    def test_changed_module_selection_changes_plan_identity(self):
        source = record()
        self.assertNotEqual(
            core.build_plan(source, selected_modules=["M03"])["plan_id"],
            core.build_plan(source, selected_modules=["M04"])["plan_id"],
        )

    def test_missing_annotations_are_skipped_not_claimed_as_normal_state(self):
        plan = core.build_plan(record(), selected_modules=["M07"])
        self.assertEqual(node(plan, "M07")["status"], "skipped")
        self.assertTrue(node(plan, "M07")["reason"])

    def test_absent_auxiliaries_are_not_fully_ready(self):
        plan = core.build_plan(record(), selected_modules=["M06"])
        self.assertIn(node(plan, "M06")["status"], {"partial", "skipped"})
        self.assertTrue(node(plan, "M06")["reason"])

    def test_hmc_three_plus_one_reference_groups_have_partial_m05(self):
        source = record(n_eeg=4, auxiliary=True, duration=14104)
        source["profile_id"] = "sparse_psg_with_auxiliary"
        source["default_config"]["selection"].update(
            start_seconds=100.0, duration_seconds=100.0
        )
        source["default_config"]["method_config"]["comparison_groups"] = [
            "M1", "M1", "M1", "M2"
        ]
        plan = core.build_plan(source, selected_modules=["M05"])
        self.assertEqual(node(plan, "M05")["status"], "partial")
        self.assertEqual(
            plan["qc_config"]["method_config"]["comparison_groups"],
            ["M1", "M1", "M1", "M2"],
        )

    def test_unknown_reference_groups_do_not_enable_relative_bad_channel_claims(self):
        source = record()
        source["default_config"]["method_config"].pop("comparison_groups")
        plan = core.build_plan(source, selected_modules=["M05"])
        self.assertEqual(node(plan, "M05")["status"], "partial")
        self.assertTrue(node(plan, "M05")["reason"])

    def test_range_is_bounded_without_silent_truncation(self):
        source = record(duration=200.0)
        for start, duration in [
            (-1.0, 60.0), (0.0, 0.0), (0.0, -1.0),
            (0.0, 120.01), (190.0, 20.0), (200.0, 1.0),
            (float("nan"), 60.0), (0.0, float("inf")),
        ]:
            with self.subTest(start=start, duration=duration):
                config = deepcopy(source["default_config"])
                config["selection"].update(start_seconds=start, duration_seconds=duration)
                with self.assertRaises(ValueError):
                    core.build_plan(source, qc_config=config)

    def test_exact_record_end_and_120_second_limit_are_valid(self):
        source = record(duration=200.0)
        config = deepcopy(source["default_config"])
        config["selection"].update(start_seconds=80.0, duration_seconds=120.0)
        plan = core.build_plan(source, qc_config=config)
        self.assertEqual(plan["qc_config"]["selection"]["start_seconds"], 80.0)
        self.assertEqual(plan["qc_config"]["selection"]["duration_seconds"], 120.0)

    def test_invalid_eeg_selection_rejected(self):
        source = record()
        for indices in [[], [0, 0], [-1, 0], [0, 8], [0, True]]:
            with self.subTest(indices=indices):
                config = deepcopy(source["default_config"])
                config["selection"]["eeg_indices"] = indices
                config["method_config"]["comparison_groups"] = ["same"] * len(indices)
                with self.assertRaises(ValueError):
                    core.build_plan(source, qc_config=config)

    def test_comparison_groups_must_align_with_selected_eeg(self):
        source = record()
        config = deepcopy(source["default_config"])
        config["method_config"]["comparison_groups"] = ["same"] * 7
        with self.assertRaises(ValueError):
            core.build_plan(source, qc_config=config)

    def test_invalid_auxiliary_index_rejected(self):
        source = record()
        config = deepcopy(source["default_config"])
        config["selection"]["reference_indices"] = {"eog": 99}
        with self.assertRaises(ValueError):
            core.build_plan(source, qc_config=config)

    def test_eeg_cannot_be_its_own_auxiliary_reference(self):
        source = record()
        config = deepcopy(source["default_config"])
        config["selection"]["reference_indices"] = {"eog": 0}
        with self.assertRaises(ValueError):
            core.build_plan(source, qc_config=config)

    def test_mixed_native_sample_clocks_are_rejected_instead_of_silently_aligned(self):
        for change_auxiliary in (False, True):
            with self.subTest(change_auxiliary=change_auxiliary):
                source = record(auxiliary=change_auxiliary)
                index = -1 if change_auxiliary else 1
                source["metadata"]["channels"][index]["sampling_rate_hz"] = 128.0
                with self.assertRaises(ValueError):
                    core.build_plan(source)

    def test_one_auxiliary_channel_cannot_silently_serve_two_physiological_roles(self):
        source = record(auxiliary=True)
        config = deepcopy(source["default_config"])
        config["selection"]["reference_indices"]["ecg"] = config["selection"]["reference_indices"]["eog"]
        with self.assertRaises(ValueError):
            core.build_plan(source, qc_config=config)

    def test_explicitly_empty_auxiliary_map_removes_default_auxiliaries(self):
        source = record(auxiliary=True)
        plan = core.build_plan(
            source, selected_modules=["M06"],
            qc_config={"selection": {"reference_indices": {}}},
        )
        self.assertEqual(plan["qc_config"]["selection"]["reference_indices"], {})
        self.assertEqual(node(plan, "M06")["status"], "partial")

    def test_unsupported_legacy_settings_are_not_silently_accepted(self):
        for key in ("feature_config", "policy_config"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    core.build_plan(record(), qc_config={key: {"legacy_setting": 1}})

    def test_group_dictionary_cannot_match_only_by_length_with_wrong_keys(self):
        source = record()
        config = deepcopy(source["default_config"])
        config["method_config"]["comparison_groups"] = {f"unrelated{i}": "same" for i in range(8)}
        with self.assertRaises(ValueError):
            core.build_plan(source, qc_config=config)

    def test_source_good_bad_labels_do_not_change_predictor_inputs(self):
        source = record()
        baseline = core.build_plan(source)["qc_config"]
        source["quality_labels"] = {"EEG1": "bad", "EEG3": "bad"}
        for channel in source["metadata"]["channels"]:
            channel["source_status"] = "bad" if channel["index"] in {1, 3} else "good"
        labelled = core.build_plan(source)["qc_config"]
        self.assertEqual(labelled, baseline)
        self.assertIn(1, labelled["selection"]["eeg_indices"])
        self.assertIn(3, labelled["selection"]["eeg_indices"])
        self.assertNotIn("source_status", json.dumps(labelled))
        self.assertNotIn("quality_labels", json.dumps(labelled))




class RuntimeFailureContractTests(unittest.TestCase):
    def test_input_failure_blocks_detectors_and_never_becomes_quality_credit(self):
        for create_bad_file in (False, True):
            with self.subTest(create_bad_file=create_bad_file):
                with tempfile.TemporaryDirectory(prefix="runtime-test-", dir=REPO / "tests") as folder:
                    source = record()
                    path = Path(folder) / "unreadable.edf"
                    if create_bad_file:
                        path.write_bytes(b"synthetic bytes, not an EDF recording")
                    source["source_path"] = str(path)
                    source["expected_sha256"] = "0" * 64
                    emitted = []
                    result = core.run_job(
                        {"input": source, "selected_modules": ["M06"]},
                        Path(folder) / "result",
                        lambda *event: emitted.append(event),
                    )
                    by_id = {row["id"]: row for row in result["modules"]}
                    self.assertEqual(result["status"], "failed")
                    self.assertEqual(by_id["M01"]["status"], "failed")
                    for mid in ("M02", "M03", "M06"):
                        self.assertEqual(by_id[mid]["status"], "skipped")
                        self.assertTrue(by_id[mid]["reason"])
                        self.assertNotIn((mid, "running"), [(e[0], e[1]) for e in emitted])
                    self.assertIsNone(result["score"]["value"])
                    self.assertEqual(result["review_status"], "pending")
                    self.assertTrue((Path(folder) / "result" / "artifacts" / "report.html").is_file())
                    json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
