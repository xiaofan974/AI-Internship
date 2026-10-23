"""Offline tests for the Week 4 Langfuse F1 judge import."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evals.week4.build_golden_dataset import (
    CANDIDATE_BASELINE_ID,
    PARENT_BASELINE_ID,
)
from evals.week4.langfuse_judge_import import (
    CAL_V1_KEY,
    CAL_V1_NAME,
    CAL_V2_KEY,
    CAL_V2_NAME,
    CALIBRATION_DATASET_NAME,
    DECISION,
    EXPECTED_MATRICES,
    JUDGE_SCORE_NAME,
    REVIEWED_SCORE_NAME,
    VAL_V1_KEY,
    VAL_V1_NAME,
    VAL_V2_KEY,
    VAL_V2_NAME,
    VALIDATION_DATASET_NAME,
    already_verified,
    build_import_jobs,
    label_to_score,
    load_ledger,
    save_ledger,
)


class JudgeImportOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.prepared = build_import_jobs()

    def test_split_contains_paired_outputs_not_independent_scenarios(self) -> None:
        calibration = self.prepared["jobs"]["calibration"]
        validation = self.prepared["jobs"]["validation"]
        self.assertEqual(len(calibration), 20)
        self.assertEqual(len(validation), 20)
        self.assertEqual(self.prepared["n_outputs"], 40)
        self.assertEqual(self.prepared["n_scenarios"], 20)
        self.assertTrue(self.prepared["not_40_independent_scenarios"])
        for jobs in (calibration, validation):
            scenario_ids = {job["scenario_id"] for job in jobs}
            self.assertEqual(len(scenario_ids), 10)
            versions = {}
            for job in jobs:
                versions.setdefault(job["scenario_id"], set()).add(job["baseline_id"])
            for baselines in versions.values():
                self.assertEqual(
                    baselines, {PARENT_BASELINE_ID, CANDIDATE_BASELINE_ID}
                )
            self.assertEqual(
                sum(1 for job in jobs if job["reviewed_label"] == "fail"), 5
            )
            self.assertEqual(
                sum(1 for job in jobs if job["reviewed_label"] == "pass"), 15
            )
        self.assertFalse(
            {job["scenario_id"] for job in calibration}
            & {job["scenario_id"] for job in validation}
        )
        case_ids = [job["case_id"] for job in calibration + validation]
        self.assertEqual(len(set(case_ids)), 40)
        self.assertEqual(set(case_ids), {job["item_id"] for job in calibration + validation})

    def test_recomputed_matrices_match_freeze_and_are_not_combined(self) -> None:
        for key, expected in EXPECTED_MATRICES.items():
            block = self.prepared["matrices"][key]
            self.assertEqual(
                {name: block[name] for name in ("TP", "FN", "TN", "FP")},
                expected,
            )
            self.assertTrue(block["matches_expected"])
            self.assertEqual(block["valid_n"], 20)
            self.assertEqual(block["invalid_n"], 0)
            self.assertEqual(block["missing_n"], 0)
            self.assertEqual(block["positive_class"], "fail")
            self.assertEqual(
                block["TPR_fraction"],
                f"{expected['TP']}/{expected['TP'] + expected['FN']}",
            )
            self.assertEqual(
                block["TNR_fraction"],
                f"{expected['TN']}/{expected['TN'] + expected['FP']}",
            )
        self.assertEqual(self.prepared["matrices"][CAL_V1_KEY]["TPR"], 0.0)
        self.assertEqual(self.prepared["matrices"][CAL_V2_KEY]["TPR"], 0.4)
        self.assertEqual(self.prepared["matrices"][VAL_V1_KEY]["TPR"], 0.0)
        self.assertEqual(self.prepared["matrices"][VAL_V2_KEY]["TPR"], 0.0)
        self.assertFalse(self.prepared["splits_combined"])
        self.assertFalse(self.prepared["agreement_headlined"])
        self.assertIn("did not transfer to validation", DECISION)

    def test_task_inputs_exclude_reviewed_labels(self) -> None:
        job = self.prepared["jobs"]["calibration"][0]
        blob = json.dumps(job["input"])
        self.assertNotIn("reviewed_labels", blob)
        self.assertNotIn("accepted by Lily", blob)
        self.assertNotIn(PARENT_BASELINE_ID, blob)
        self.assertNotIn(CANDIDATE_BASELINE_ID, blob)
        self.assertIn("reviewed_labels", job["metadata"])
        self.assertEqual(job["metadata"]["reviewed_labels"]["accepted_by"], "Lily")
        self.assertTrue(job["metadata"]["reviewed_labels_are_not_task_input"])
        self.assertIsNone(job["expected_output"])
        self.assertTrue(job["input"]["system_description"])
        self.assertTrue(job["input"]["answer"])

    def test_parent_source_links_and_candidate_absence(self) -> None:
        calibration = self.prepared["jobs"]["calibration"]
        validation = self.prepared["jobs"]["validation"]
        parents = [
            job
            for job in calibration + validation
            if job["baseline_id"] == PARENT_BASELINE_ID
        ]
        candidates = [
            job
            for job in calibration + validation
            if job["baseline_id"] == CANDIDATE_BASELINE_ID
        ]
        self.assertEqual(len(parents), 20)
        self.assertEqual(len(candidates), 20)
        self.assertTrue(all(job["source_trace_id"] for job in parents))
        self.assertTrue(all(job["source_association_available"] for job in parents))
        self.assertTrue(all(job["source_trace_id"] is None for job in candidates))
        self.assertTrue(
            all(not job["source_association_available"] for job in candidates)
        )
        self.assertEqual(len({job["source_trace_id"] for job in parents}), 20)

    def test_saved_predictions_and_score_encoding(self) -> None:
        self.assertEqual(JUDGE_SCORE_NAME, "judge_f1_pass")
        self.assertEqual(REVIEWED_SCORE_NAME, "reviewed_f1_pass")
        self.assertEqual(label_to_score("pass"), 1)
        self.assertEqual(label_to_score("fail"), 0)
        by_eval = {
            job["evaluation_id"]: job
            for job in self.prepared["jobs"]["calibration"]
        }
        s01_candidate = by_eval["bd7ec9dcdb3fcb7c"]
        self.assertEqual(s01_candidate["reviewed_label"], "fail")
        self.assertEqual(s01_candidate["runs"][CAL_V1_KEY]["judge_label"], "pass")
        self.assertEqual(s01_candidate["runs"][CAL_V1_KEY]["judge_score_value"], 1)
        self.assertEqual(s01_candidate["runs"][CAL_V1_KEY]["reviewed_score_value"], 0)
        s04_candidate = by_eval["c953f67527f058d9"]
        self.assertEqual(s04_candidate["runs"][CAL_V1_KEY]["judge_label"], "pass")
        self.assertEqual(s04_candidate["runs"][CAL_V2_KEY]["judge_label"], "fail")
        for job in self.prepared["jobs"]["calibration"] + self.prepared["jobs"]["validation"]:
            for run in job["runs"].values():
                self.assertEqual(set(run["output"]), {"verdict", "reason", "excerpt"})
                self.assertNotIn("usage", run["output"])
                self.assertNotIn("elapsed_ms", run["output"])
                self.assertTrue(run["historical_import"])

    def test_run_and_dataset_names(self) -> None:
        self.assertEqual(CALIBRATION_DATASET_NAME, "week4_f1_calibration_v1")
        self.assertEqual(VALIDATION_DATASET_NAME, "week4_f1_validation_v1")
        self.assertEqual(CAL_V1_NAME, "Calibration: frozen judge v1")
        self.assertEqual(CAL_V2_NAME, "Calibration: frozen judge v2")
        self.assertEqual(VAL_V1_NAME, "Validation: frozen judge v1")
        self.assertEqual(VAL_V2_NAME, "Validation: frozen judge v2")
        self.assertFalse(self.prepared["model_calls"])
        self.assertFalse(self.prepared["retrieval_calls"])
        self.assertFalse(self.prepared["hosted_evaluators"])
        self.assertFalse(self.prepared["judges_rerun"])
        self.assertFalse(self.prepared["judges_refined"])

    def test_ledger_skips_verified_items(self) -> None:
        job = self.prepared["jobs"]["calibration"][0]
        ledger = {
            "runs": {
                CAL_V1_KEY: {"items": {job["case_id"]: {"status": "verified"}}},
            }
        }
        self.assertTrue(already_verified(ledger, CAL_V1_KEY, job["case_id"]))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ledger.json"
            save_ledger(path, load_ledger(path))
            self.assertTrue(path.is_file())

    def test_source_does_not_call_live_services_or_judges(self) -> None:
        source = Path("evals/week4/langfuse_judge_import.py").read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("apply_timing_repair", source)
        self.assertIn("run_experiment", source)
        self.assertIn(JUDGE_SCORE_NAME, source)
        self.assertIn(REVIEWED_SCORE_NAME, source)
        self.assertIn("Lily", source)
        self.assertIn("Neither frozen judge qualifies as an F1 detector", source)
        self.assertIn("did not transfer to validation", source)


if __name__ == "__main__":
    unittest.main()
