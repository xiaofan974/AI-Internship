"""Offline checks for F1 judge validation. No live model or SQLite."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from evals.week4.f1_judge_v1 import (
    FORBIDDEN_REQUEST_FIELDS,
    PROJECT_DIR,
    JudgeError,
    approved_payload,
    load_jsonl_by_id,
    load_manifest,
    load_rubric,
    load_split,
)
from evals.week4.f1_judge_validation import (
    EXPECTED_HASHES,
    HASH_PATHS,
    PROTOCOL_ID,
    confirm_validation_split,
    derive_request_schedule,
    load_protocol,
    paired_validation_comparison,
    recommend_use,
    run_validation,
    select_validation_jobs,
    validation_case_rows,
    verify_frozen_artifacts,
    verify_protocol,
)
from evals.week4.f1_judge_v1 import build_model_request as build_v1_request
from evals.week4.f1_judge_v2 import build_model_request as build_v2_request

SOURCE = PROJECT_DIR / "evals" / "week4" / "f1_judge_validation.py"
RUNNER = PROJECT_DIR / "run_week4_f1_judge_validation.py"
BLOCKED_IMPORTS = {
    "sqlite3",
    "aeacus_agent.preview_agent",
    "aeacus_agent.retrieval",
    "aeacus_agent.review_register",
    "aeacus_agent.agent",
    "run_review",
    "run_classification_preview",
    "google.adk",
}


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class FakeTransport:
    def generate(self, request):
        return {
            "raw_text": '{"verdict":"pass","reason":"No unstated premise.","excerpt":""}',
            "usage": {"total_token_count": 9},
            "elapsed_ms": 1.0,
            "started_at": "2026-10-23T00:00:00+00:00",
            "ended_at": "2026-10-23T00:00:01+00:00",
            "model_version": "fake",
        }


class FreezeTests(unittest.TestCase):
    def test_frozen_hashes_and_validation_composition(self) -> None:
        observed = verify_frozen_artifacts()
        self.assertEqual(observed, EXPECTED_HASHES)
        manifest = load_manifest()
        split = load_split()
        info = confirm_validation_split(manifest, split)
        self.assertEqual(info["n_outputs"], 20)
        self.assertEqual(info["n_scenario_groups"], 10)
        self.assertEqual(info["fail"], 5)
        self.assertEqual(info["pass"], 15)
        self.assertEqual(info["overlap"], [])
        protocol = load_protocol()
        verify_protocol(protocol, info["evaluation_ids"])
        self.assertEqual(protocol["protocol_id"], PROTOCOL_ID)
        self.assertEqual(len(protocol["requests"]), 40)
        firsts = [
            row["version"]
            for row in protocol["requests"]
            if row["seq"] % 2 == 1
        ]
        self.assertEqual(firsts, ["v1", "v2"] * 10)
        self.assertNotIn('"f1"', json.dumps(protocol["requests"]))


class SelectionAndLeakageTests(unittest.TestCase):
    def test_only_validation_jobs_and_no_label_leakage(self) -> None:
        manifest = load_manifest()
        split = load_split()
        rubric = load_rubric()
        validation_ids = {
            row["evaluation_id"] for row in validation_case_rows(manifest)
        }
        payloads = load_jsonl_by_id(
            PROJECT_DIR / "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
            validation_ids,
        )
        jobs = select_validation_jobs(
            manifest, payloads, rubric=rubric, split=split
        )
        self.assertEqual(len(jobs), 20)
        leaked = dict(payloads)
        cal_id = next(
            row["evaluation_id"]
            for row in manifest["cases"]
            if row["group"] == "calibration"
        )
        leaked[cal_id] = next(iter(payloads.values()))
        with self.assertRaises(JudgeError):
            select_validation_jobs(manifest, leaked, rubric=rubric, split=split)

        payload = {
            "evaluation_id": "0123456789abcdef",
            "baseline_id": "week4_adk_preview_v1",
            "scenario_id": "TRACE-S13",
            "f1": "fail",
            "expected_result": "v2 better than v1",
            "system_description": "A fictional kiosk.",
            "retrieved_evidence": [],
            "answer": "Provisional classification depends on missing facts.",
        }
        for builder in (build_v1_request, build_v2_request):
            request = builder(payload)
            blob = request["user_text"] + request["system_instruction"]
            for field in FORBIDDEN_REQUEST_FIELDS:
                self.assertNotIn(field, request)
            for token in (
                "0123456789abcdef",
                "week4_adk_preview_v1",
                "TRACE-S13",
                "v2 better than v1",
            ):
                self.assertNotIn(token, blob)
            self.assertEqual(
                set(approved_payload(payload)),
                {"system_description", "retrieved_evidence", "answer"},
            )


class ComparisonTests(unittest.TestCase):
    def test_paired_comparison_and_no_gate_recommendation(self) -> None:
        labels = {
            "a": {
                "f1": "fail",
                "scenario_id": "TRACE-S13",
                "case_id": "case-a",
            },
            "b": {
                "f1": "fail",
                "scenario_id": "TRACE-S20",
                "case_id": "case-b",
            },
            "c": {
                "f1": "pass",
                "scenario_id": "TRACE-S12",
                "case_id": "case-c",
            },
        }

        def pred(evaluation_id: str, verdict: str) -> dict:
            return {
                "evaluation_id": evaluation_id,
                "status": "valid",
                "parsed": {"verdict": verdict, "reason": "x", "excerpt": ""},
            }

        empty_score = {
            "metrics": {
                "TP": 0,
                "FN": 0,
                "TN": 0,
                "FP": 0,
                "TPR": 0.0,
                "TNR": 1.0,
                "positives_in_metrics": 2,
                "negatives_in_metrics": 1,
            },
            "valid_n": 3,
            "invalid_n": 0,
            "missing_n": 0,
            "prediction_coverage": 1.0,
            "valid_response_only": False,
        }
        comparison = paired_validation_comparison(
            v1_score=empty_score,
            v2_score=empty_score,
            labels=labels,
            v1_predictions=[
                pred("a", "pass"),
                pred("b", "fail"),
                pred("c", "pass"),
            ],
            v2_predictions=[
                pred("a", "fail"),
                pred("b", "pass"),
                pred("c", "fail"),
            ],
        )
        self.assertEqual(
            [row["evaluation_id"] for row in comparison["failures_newly_detected"]],
            ["a"],
        )
        self.assertEqual(
            [row["evaluation_id"] for row in comparison["failures_newly_missed"]],
            ["b"],
        )
        self.assertEqual(
            [
                row["evaluation_id"]
                for row in comparison["passes_newly_flagged_incorrectly"]
            ],
            ["c"],
        )
        self.assertEqual(len(comparison["changed_verdicts"]), 3)
        self.assertFalse(comparison["mixed_with_calibration"])
        recommendation = recommend_use(comparison)
        self.assertFalse(recommendation["approval_or_release_gate"])
        self.assertFalse(recommendation["automatic_qualification"])

    def test_schedule_alternates_first_version(self) -> None:
        schedule = derive_request_schedule(["aa", "bb", "cc"])
        self.assertEqual(
            [(row["evaluation_id"], row["version"]) for row in schedule],
            [
                ("aa", "v1"),
                ("aa", "v2"),
                ("bb", "v2"),
                ("bb", "v1"),
                ("cc", "v1"),
                ("cc", "v2"),
            ],
        )


class IsolationTests(unittest.TestCase):
    def test_no_capstone_or_sqlite_imports(self) -> None:
        names = _imports(SOURCE) | _imports(RUNNER)
        self.assertEqual(names & BLOCKED_IMPORTS, set())
        text = SOURCE.read_text(encoding="utf-8") + RUNNER.read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", text)
        self.assertNotIn("search_legal_sources", text)

    def test_run_validation_refuses_labels_and_stays_on_validation(self) -> None:
        with self.assertRaises(JudgeError):
            run_validation(lambda: FakeTransport(), load_labels=True)
        tmp = Path(tempfile.mkdtemp())
        try:
            for relative in HASH_PATHS.values():
                dest = tmp / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_DIR / relative, dest)
            transport = FakeTransport()
            report = run_validation(lambda: transport, root=tmp)
            self.assertEqual(report["split"], "validation")
            self.assertFalse(report["mixed_with_calibration"])
            self.assertFalse(report["not_an_application_or_approval_gate"] is False)
            self.assertEqual(report["run"]["n_attempted"], 40)
            self.assertEqual(report["v1"]["score"]["expected_n"], 20)
            self.assertEqual(report["v2"]["score"]["expected_n"], 20)
            predictions = json.loads(
                (tmp / "data/local/evals/week4/judge/validation_v1/predictions.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(predictions["labels_included"])
            self.assertNotIn('"f1":', json.dumps(predictions))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
