"""Offline tests for the week4_adk_preview_v1 Langfuse timing comparison."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.week4.checkers import DEFERRED_DATE_CHECKER_ID
from evals.week4.codify import EXPECTED_SOURCE_SHA256
from evals.week4.langfuse_timing_comparison import (
    BASELINE_ID,
    COMPARISON_NOT,
    DATASET_NAME,
    EXPECTED_DELIVERED,
    EXPECTED_RAW,
    RAW_RUN_KEY,
    RAW_RUN_NAME,
    REPAIR_RUN_KEY,
    REPAIR_RUN_NAME,
    SCORE_NAME,
    already_verified,
    build_comparison_jobs,
    deterministic_score_id,
    deterministic_trace_id,
    item_id,
    label_to_score,
    load_ledger,
    save_ledger,
)


class TimingComparisonOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = build_comparison_jobs()

    def test_prepares_twenty_source_linked_items(self) -> None:
        self.assertEqual(self.prepared["n_jobs"], 20)
        self.assertEqual(self.prepared["dataset_name"], DATASET_NAME)
        self.assertEqual(self.prepared["source_sha256"], EXPECTED_SOURCE_SHA256)
        ids = [job["scenario_id"] for job in self.prepared["jobs"]]
        self.assertEqual(ids, [f"TRACE-S{index:02d}" for index in range(1, 21)])
        self.assertEqual(len({job["item_id"] for job in self.prepared["jobs"]}), 20)
        self.assertEqual(len({job["source_trace_id"] for job in self.prepared["jobs"]}), 20)

    def test_item_input_excludes_labels_and_model_answer(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertEqual(job["item_id"], item_id(job["scenario_id"]))
        self.assertEqual(set(job["input"]), {"scenario_id", "task"})
        self.assertTrue(job["input"]["task"])
        self.assertIsNone(job["expected_output"])
        blob = json.dumps(job["input"])
        self.assertNotIn("reviewed_labels", blob)
        self.assertNotIn(job["runs"][RAW_RUN_KEY]["output"], blob)
        self.assertIn("reviewed_labels", job["metadata"])
        self.assertTrue(job["metadata"]["reviewed_labels_are_not_task_input"])
        self.assertTrue(job["metadata"]["original_model_answer_is_not_gold"])
        self.assertEqual(job["metadata"]["original_run_id"], job["original_run_id"])
        self.assertEqual(job["metadata"]["baseline_id"], BASELINE_ID)
        self.assertIn("traces_sha256", job["metadata"]["source_hashes"])
        self.assertEqual(job["metadata"]["source_trace_id"], job["source_trace_id"])

    def test_recomputed_counts_match_freeze(self) -> None:
        self.assertEqual(self.prepared["raw_summary"]["pass"], EXPECTED_RAW["pass"])
        self.assertEqual(self.prepared["raw_summary"]["fail_ids"], EXPECTED_RAW["fail_ids"])
        self.assertEqual(
            self.prepared["delivered_summary"]["pass"], EXPECTED_DELIVERED["pass"]
        )
        self.assertEqual(self.prepared["delivered_summary"]["fail_ids"], [])
        by_id = {job["scenario_id"]: job for job in self.prepared["jobs"]}
        self.assertEqual(by_id["TRACE-S02"]["runs"][RAW_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S20"]["runs"][RAW_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S01"]["runs"][RAW_RUN_KEY]["score_value"], 1)
        self.assertEqual(by_id["TRACE-S02"]["runs"][REPAIR_RUN_KEY]["score_value"], 1)
        self.assertEqual(by_id["TRACE-S20"]["runs"][REPAIR_RUN_KEY]["score_value"], 1)
        self.assertEqual(label_to_score("pass"), 1)
        self.assertEqual(label_to_score("fail"), 0)
        self.assertEqual(SCORE_NAME, DEFERRED_DATE_CHECKER_ID)

    def test_raw_and_delivered_outputs_stay_separate(self) -> None:
        by_id = {job["scenario_id"]: job for job in self.prepared["jobs"]}
        s02 = by_id["TRACE-S02"]
        raw = s02["runs"][RAW_RUN_KEY]["output"]
        delivered = s02["runs"][REPAIR_RUN_KEY]["output"]
        self.assertTrue(raw)
        self.assertTrue(delivered)
        self.assertNotEqual(raw, delivered)
        self.assertNotEqual(
            s02["runs"][RAW_RUN_KEY]["output_sha256"],
            s02["runs"][REPAIR_RUN_KEY]["output_sha256"],
        )
        self.assertNotEqual(
            s02["runs"][RAW_RUN_KEY]["langfuse_trace_id"],
            s02["source_trace_id"],
        )
        self.assertNotEqual(
            s02["runs"][REPAIR_RUN_KEY]["langfuse_trace_id"],
            s02["source_trace_id"],
        )
        self.assertNotEqual(
            s02["runs"][RAW_RUN_KEY]["langfuse_trace_id"],
            s02["runs"][REPAIR_RUN_KEY]["langfuse_trace_id"],
        )

    def test_comparison_is_application_layer_replay(self) -> None:
        generation = self.prepared["delivered_generation"]
        self.assertEqual(generation["method"], "fresh_application_layer_replay")
        self.assertFalse(generation["model_calls"])
        self.assertFalse(generation["retrieval_calls"])
        self.assertFalse(generation["hosted_judges"])
        self.assertIn("application-layer", generation["label"])
        self.assertIn("improved model reasoning", COMPARISON_NOT)
        self.assertEqual(RAW_RUN_NAME, "Historical raw model answers")
        self.assertEqual(REPAIR_RUN_NAME, "Timing repair: application-layer replay")

    def test_stable_item_and_run_ids(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertEqual(
            job["runs"][RAW_RUN_KEY]["langfuse_trace_id"],
            deterministic_trace_id(RAW_RUN_KEY, job["original_run_id"]),
        )
        first = deterministic_score_id(REPAIR_RUN_KEY, job["original_run_id"])
        self.assertEqual(first, deterministic_score_id(REPAIR_RUN_KEY, job["original_run_id"]))
        self.assertNotEqual(first, deterministic_score_id(RAW_RUN_KEY, job["original_run_id"]))
        self.assertEqual(len(job["runs"][RAW_RUN_KEY]["langfuse_trace_id"]), 32)

    def test_ledger_skips_verified_pairs(self) -> None:
        job = self.prepared["jobs"][0]
        ledger = {
            "runs": {
                RAW_RUN_KEY: {"items": {job["scenario_id"]: {"status": "verified"}}},
                REPAIR_RUN_KEY: {"items": {job["scenario_id"]: {"status": "verified"}}},
            }
        }
        self.assertTrue(already_verified(ledger, RAW_RUN_KEY, job["scenario_id"]))
        self.assertTrue(already_verified(ledger, REPAIR_RUN_KEY, job["scenario_id"]))

    def test_ledger_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = load_ledger(path)
            ledger["items"]["TRACE-S01"] = {"status": "verified"}
            save_ledger(path, ledger)
            loaded = load_ledger(path)
            self.assertEqual(loaded["items"]["TRACE-S01"]["status"], "verified")

    def test_source_does_not_call_live_services(self) -> None:
        source = Path("evals/week4/langfuse_timing_comparison.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("GoogleADKInstrumentor", source)
        self.assertIn("run_experiment", source)
        self.assertIn("DEFERRED_DATE_CHECKER_ID", source)
        self.assertIn("check_deferred_date_qualifications", source)
        self.assertIn("source_trace_id", source)


if __name__ == "__main__":
    unittest.main()
