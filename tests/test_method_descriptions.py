"""Documentation contracts protect provenance and method capability boundaries."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys
import unittest
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ephys_qc.method_descriptions import enrich_method, method_documentation
from ephys_qc.method_registry import methods


EXPECTED_IDS = {
    "edf_reader", "voltage_calibration", "qc_plan", "continuity", "welch_psd",
    "thomson_line", "spectral_model", "prep_nonspatial", "ecg_locked", "eog_locked",
    "hf_burst", "sleep_timeline", "task_timeline", "clinical_timeline", "aggregate",
    "report", "mne_amplitude", "mne_muscle", "mne_bridge", "mne_lof",
    "autoreject_global", "pyprep_ransac", "autoreject_epochs", "ica_iclabel",
    "faster_channels", "asr_bursts", "cleanline", "zapline_plus", "fieldtrip_zvalue",
}
TEXT_FIELDS = {
    "purpose", "how_it_works", "interpretation", "when_to_use", "when_not_to_use",
    "validation_status", "upstream_call", "implementation_origin", "version_note",
}


class MethodDocumentationTests(unittest.TestCase):
    def test_every_catalogue_method_has_complete_independent_documentation(self):
        rows = methods()
        self.assertEqual({row["id"] for row in rows}, EXPECTED_IDS)
        self.assertEqual(len(rows), len(EXPECTED_IDS))
        for row in rows:
            with self.subTest(method=row["id"]):
                doc = method_documentation(row["id"])
                self.assertEqual(set(doc), TEXT_FIELDS | {"references"})
                self.assertTrue(all(isinstance(doc[key], str) and doc[key].strip() for key in TEXT_FIELDS))
                self.assertTrue(doc["references"])

    def test_reference_types_distinguish_web_evidence_from_local_wrapper(self):
        for identifier in EXPECTED_IDS:
            for ref in method_documentation(identifier)["references"]:
                with self.subTest(method=identifier, title=ref["title"]):
                    self.assertEqual(set(ref), {"title", "url", "kind"})
                    self.assertTrue(ref["title"].strip())
                    self.assertIn(ref["kind"], {"算法论文", "上游代码", "官方文档", "本项目封装"})
                    if ref["kind"] == "本项目封装":
                        self.assertTrue(ref["url"].startswith("src/ephys_qc/"))
                        self.assertTrue((ROOT / ref["url"]).is_file())
                    else:
                        self.assertEqual(urlparse(ref["url"]).scheme, "https")
                        self.assertTrue(urlparse(ref["url"]).netloc)

    def test_enrichment_does_not_mutate_or_promote_a_method(self):
        for row in methods():
            before = deepcopy(row)
            enriched = enrich_method(row)
            expected = deepcopy(before)
            expected["documentation"] = method_documentation(row["id"])
            self.assertEqual(enriched, expected)
            self.assertEqual(row, before)
            self.assertEqual(enriched["implementation"], before["implementation"])
            enriched["source"]["name"] = "changed by consumer"
            enriched["requirements"].append("changed by consumer")
            self.assertEqual(row, before)

    def test_documentation_and_reference_objects_are_not_shared(self):
        doc = method_documentation("prep_nonspatial")
        original = deepcopy(doc)
        doc["references"][0]["title"] = "changed"
        doc["purpose"] = "changed"
        self.assertEqual(method_documentation("prep_nonspatial"), original)
        self.assertNotEqual(method_documentation("pyprep_ransac")["references"][1]["title"], "changed")

    def test_unknown_methods_fail_closed_instead_of_claiming_support(self):
        with self.assertRaises(KeyError):
            method_documentation("unreviewed_new_algorithm")
        with self.assertRaises(KeyError):
            enrich_method({"id": "unreviewed_new_algorithm", "implementation": "planned"})

    def test_import_and_lookup_require_no_scientific_runtime(self):
        code = (
            f"import sys;sys.path.insert(0,{str(ROOT / 'src')!r});"
            "from ephys_qc.method_descriptions import method_documentation;"
            "method_documentation('spectral_model');"
            "assert not (set(sys.modules) & {'numpy','scipy','mne','fooof','pyprep','autoreject'})"
        )
        subprocess.run([sys.executable, "-c", code], check=True)

    def test_prep_provenance_is_not_misattributed_to_pyprep(self):
        doc = method_documentation("prep_nonspatial")
        self.assertIn("主流程不调用pyprep.NoisyChannels", doc["upstream_call"])
        self.assertIn("compare_with_pyprep", doc["implementation_origin"])
        self.assertIn("不一致", doc["validation_status"])
        planned = method_documentation("pyprep_ransac")
        self.assertIn("尚无平台执行调用", planned["upstream_call"])

    def test_planned_methods_remain_unvalidated_not_executable(self):
        for identifier in ("pyprep_ransac", "autoreject_epochs", "ica_iclabel"):
            doc = method_documentation(identifier)
            self.assertIn("尚未接入", doc["validation_status"])
            self.assertIn("尚无平台执行调用", doc["upstream_call"])

    def test_distinct_methods_preserve_scientific_interpretation_limits(self):
        self.assertIn("没有直接调用annotate_muscle_zscore", method_documentation("hf_burst")["implementation_origin"])
        self.assertIn("不是固定时间窗峰峰值法", method_documentation("mne_amplitude")["interpretation"])
        self.assertIn("不是最终桥接阈值", method_documentation("mne_bridge")["interpretation"])
        self.assertIn("同一选区", method_documentation("autoreject_global")["interpretation"])
        self.assertIn("不是质量真值", method_documentation("sleep_timeline")["interpretation"])
        self.assertIn("不是伪迹真值", method_documentation("clinical_timeline")["interpretation"])
        self.assertIn("完成率不是信号质量", method_documentation("aggregate")["interpretation"])


if __name__ == "__main__":
    unittest.main()
