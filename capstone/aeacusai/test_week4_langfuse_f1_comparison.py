"""Offline tests for the week4 F1 Langfuse comparison."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.week4.codify import EXPECTED_SOURCE_SHA256
from evals.week4.langfuse_f1_comparison import (
    CANDIDATE_BASELINE_ID,
    CANDIDATE_INSTRUCTION_SHA256,
    CANDIDATE_RUN_KEY,
    CANDIDATE_RUN_NAME,
    EXPECTED_CANDIDATE_FAIL,
    EXPECTED_CANDIDATE_SHA256,
    EXPECTED_PARENT_FAIL,
    EXPECTED_PERSISTENT,
    EXPECTED_RECOVERIES,
    EXPECTED_REGRESSIONS,
    PARENT_BASELINE_ID,
    PARENT_INSTRUCTION_SHA256,
    PARENT_RUN_KEY,
    PARENT_RUN_NAME,
    SCORE_NAME,
    already_verified,
    build_f1_jobs,
    label_to_score,
    load_ledger,
    save_ledger,
)


class F1ComparisonOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = build_f1_jobs()

    def test_prepares_twenty_paired_raw_answers(self) -> None:
        self.assertEqual(self.prepared["n_jobs"], 20)
        self.assertEqual(self.prepared["parent_source_sha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.prepared["candidate_source_sha256"], EXPECTED_CANDIDATE_SHA256)
        self.assertEqual(
            [job["scenario_id"] for job in self.prepared["jobs"]],
            [f"TRACE-S{index:02d}" for index in range(1, 21)],
        )
        self.assertFalse(self.prepared["timing_formatter_applied"])
        self.assertFalse(self.prepared["model_calls"])
        self.assertFalse(self.prepared["retrieval_calls"])

    def test_reviewed_f1_counts_match_accepted_comparison(self) -> None:
        self.assertEqual(self.prepared["parent_summary"]["fail_ids"], EXPECTED_PARENT_FAIL)
        self.assertEqual(
            self.prepared["candidate_summary"]["fail_ids"], EXPECTED_CANDIDATE_FAIL
        )
        self.assertEqual(self.prepared["parent_summary"]["pass"], 15)
        self.assertEqual(self.prepared["candidate_summary"]["pass"], 15)
        self.assertEqual(self.prepared["comparison"]["recoveries"], EXPECTED_RECOVERIES)
        self.assertEqual(self.prepared["comparison"]["regressions"], EXPECTED_REGRESSIONS)
        self.assertEqual(
            self.prepared["comparison"]["persistent_failures"], EXPECTED_PERSISTENT
        )
        self.assertTrue(self.prepared["comparison"]["not_overall_quality_percentage"])
        self.assertFalse(self.prepared["comparison"]["candidate_f2_labels_assigned"])

    def test_score_encoding_and_imported_labels(self) -> None:
        by_id = {job["scenario_id"]: job for job in self.prepared["jobs"]}
        self.assertEqual(SCORE_NAME, "reviewed_f1_pass")
        self.assertEqual(label_to_score("pass"), 1)
        self.assertEqual(label_to_score("fail"), 0)
        self.assertEqual(by_id["TRACE-S04"]["runs"][PARENT_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S08"]["runs"][PARENT_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S08"]["runs"][CANDIDATE_RUN_KEY]["score_value"], 1)
        self.assertEqual(by_id["TRACE-S01"]["runs"][PARENT_RUN_KEY]["score_value"], 1)
        self.assertEqual(by_id["TRACE-S01"]["runs"][CANDIDATE_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S20"]["runs"][PARENT_RUN_KEY]["score_value"], 0)
        self.assertEqual(by_id["TRACE-S20"]["runs"][CANDIDATE_RUN_KEY]["score_value"], 1)

    def test_task_input_excludes_labels_and_uses_saved_raw(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertEqual(set(job["input"]), {"scenario_id", "task"})
        self.assertNotIn("reviewed_labels", json.dumps(job["input"]))
        parent = job["runs"][PARENT_RUN_KEY]["output"]
        candidate = self.prepared["jobs"][0]["runs"][CANDIDATE_RUN_KEY]["output"]
        self.assertTrue(parent)
        self.assertTrue(candidate)
        s01 = {row["scenario_id"]: row for row in self.prepared["jobs"]}["TRACE-S01"]
        self.assertNotEqual(
            s01["runs"][PARENT_RUN_KEY]["output"],
            s01["runs"][CANDIDATE_RUN_KEY]["output"],
        )

    def test_preserves_run_ids_and_instruction_hashes(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertEqual(job["runs"][PARENT_RUN_KEY]["baseline_id"], PARENT_BASELINE_ID)
        self.assertEqual(
            job["runs"][CANDIDATE_RUN_KEY]["baseline_id"], CANDIDATE_BASELINE_ID
        )
        self.assertEqual(
            job["runs"][PARENT_RUN_KEY]["instruction_sha256"], PARENT_INSTRUCTION_SHA256
        )
        self.assertEqual(
            job["runs"][CANDIDATE_RUN_KEY]["instruction_sha256"],
            CANDIDATE_INSTRUCTION_SHA256,
        )
        self.assertTrue(self.prepared["live_instruction_is_restored_parent"])
        self.assertEqual(PARENT_RUN_NAME, "F1: historical parent answers")
        self.assertEqual(CANDIDATE_RUN_NAME, "F1: rejected prompt candidate answers")
        self.assertNotEqual(
            job["runs"][PARENT_RUN_KEY]["original_run_id"],
            job["runs"][CANDIDATE_RUN_KEY]["original_run_id"],
        )

    def test_ledger_skips_verified_pairs(self) -> None:
        job = self.prepared["jobs"][0]
        ledger = {
            "runs": {
                PARENT_RUN_KEY: {"items": {job["scenario_id"]: {"status": "verified"}}},
                CANDIDATE_RUN_KEY: {
                    "items": {job["scenario_id"]: {"status": "verified"}}
                },
            }
        }
        self.assertTrue(already_verified(ledger, PARENT_RUN_KEY, job["scenario_id"]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            save_ledger(path, load_ledger(path))
            self.assertTrue(path.is_file())

    def test_source_does_not_call_live_services_or_formatter(self) -> None:
        source = Path("evals/week4/langfuse_f1_comparison.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("apply_timing_repair", source)
        self.assertIn("run_experiment", source)
        self.assertIn(SCORE_NAME, source)
        self.assertIn("Lily", source)


if __name__ == "__main__":
    unittest.main()
