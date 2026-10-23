"""Offline tests for the week4_adk_preview_v1 Langfuse historical importer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.week4.codify import EXPECTED_SOURCE_SHA256
from evals.week4.langfuse_baseline_import import (
    AUTOMATED_S19_SCORE,
    AUTOMATED_TIMING_SCORE,
    BASELINE_ID,
    HISTORICAL_TAG,
    REVIEWED_SCORE_NAMES,
    already_imported,
    already_verified,
    association_key,
    build_import_jobs,
    deterministic_score_id,
    deterministic_trace_id,
    label_to_score,
    load_ledger,
    pending_jobs,
    save_ledger,
)


class BaselineImportOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = build_import_jobs()

    def test_prepares_twenty_original_jobs(self) -> None:
        self.assertEqual(self.prepared["n_jobs"], 20)
        self.assertEqual(self.prepared["source_sha256"], EXPECTED_SOURCE_SHA256)
        self.assertEqual(self.prepared["expected"]["timing_pass"], 18)
        self.assertEqual(self.prepared["expected"]["timing_fail"], 2)
        self.assertEqual(self.prepared["expected"]["s19_fail"], 1)
        self.assertEqual(self.prepared["expected"]["s19_excluded"], 19)
        self.assertFalse(self.prepared["invented"]["per_event_timestamps"])
        self.assertFalse(self.prepared["invented"]["model_generations"])
        self.assertFalse(self.prepared["invented"]["tool_durations"])

    def test_reviewed_and_automated_score_names_use_pass_fail_bits(self) -> None:
        by_id = {job["scenario_id"]: job for job in self.prepared["jobs"]}
        s01 = by_id["TRACE-S01"]
        names = {row["name"]: row["value"] for row in s01["scores"]}
        self.assertEqual(set(REVIEWED_SCORE_NAMES.values()) | {AUTOMATED_TIMING_SCORE}, set(names))
        self.assertNotIn(AUTOMATED_S19_SCORE, names)
        self.assertEqual(names["reviewed_f1"], 1)
        self.assertEqual(names[AUTOMATED_TIMING_SCORE], 1)
        s02 = {row["name"]: row["value"] for row in by_id["TRACE-S02"]["scores"]}
        self.assertEqual(s02[AUTOMATED_TIMING_SCORE], 0)
        s19 = {row["name"]: row["value"] for row in by_id["TRACE-S19"]["scores"]}
        self.assertEqual(s19[AUTOMATED_S19_SCORE], 0)
        self.assertTrue(by_id["TRACE-S01"]["s19_excluded"])
        self.assertFalse(by_id["TRACE-S19"]["s19_excluded"])
        self.assertEqual(label_to_score("pass"), 1)
        self.assertEqual(label_to_score("fail"), 0)

    def test_payloads_keep_input_evidence_and_answers(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertTrue(job["input"])
        self.assertTrue(job["answer"])
        self.assertTrue(job["evidence"])
        self.assertTrue(any(item.get("text_sha256") for item in job["evidence"]))
        self.assertTrue(any(item.get("text") for item in job["evidence"]))
        self.assertIn("original_run_id", job["provenance"])
        self.assertIn("original_started_at", job["provenance"])
        self.assertNotIn("duration_ms", json.dumps(job["events"]))
        self.assertNotIn("token_usage_invented", json.dumps(job))

    def test_stable_associations(self) -> None:
        job = self.prepared["jobs"][0]
        self.assertEqual(job["association_key"], association_key(job["run_id"]))
        self.assertEqual(job["langfuse_trace_id"], deterministic_trace_id(job["run_id"]))
        self.assertEqual(len(job["langfuse_trace_id"]), 32)
        first = deterministic_score_id(job["run_id"], "reviewed_f1")
        second = deterministic_score_id(job["run_id"], "reviewed_f1")
        self.assertEqual(first, second)
        self.assertNotEqual(first, deterministic_score_id(job["run_id"], "reviewed_f2"))

    def test_ledger_skips_verified_records(self) -> None:
        job = self.prepared["jobs"][0]
        ledger = {"records": {job["run_id"]: {"status": "verified"}}}
        self.assertTrue(already_verified(ledger, job["run_id"]))
        self.assertTrue(already_imported(ledger, job["run_id"]))
        self.assertEqual(pending_jobs(self.prepared["jobs"], ledger, need="upload"), self.prepared["jobs"][1:])
        self.assertEqual(pending_jobs(self.prepared["jobs"], ledger, need="verify"), [])

    def test_ledger_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            ledger = load_ledger(path)
            ledger["records"]["run-1"] = {"status": "verified"}
            save_ledger(path, ledger)
            loaded = load_ledger(path)
            self.assertEqual(loaded["records"]["run-1"]["status"], "verified")

    def test_review_attribution(self) -> None:
        review = self.prepared["review"]
        self.assertEqual(review.get("accepted_by"), "Lily")
        self.assertIn("AI-assisted", review.get("method") or "")
        job = next(item for item in self.prepared["jobs"] if item["scenario_id"] == "TRACE-S04")
        f1 = next(row for row in job["scores"] if row["name"] == "reviewed_f1")
        self.assertEqual(f1["value"], 0)
        self.assertIn("Lily", f1["comment"])
        self.assertEqual(f1["family"], "reviewed")

    def test_source_does_not_call_live_services(self) -> None:
        source = Path("evals/week4/langfuse_baseline_import.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("GoogleADKInstrumentor", source)
        self.assertIn(HISTORICAL_TAG, source)
        self.assertIn(BASELINE_ID, source)


if __name__ == "__main__":
    unittest.main()
