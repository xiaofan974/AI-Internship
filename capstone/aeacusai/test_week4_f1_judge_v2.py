"""Offline checks for F1 judge v2. No live model, retrieval, or SQLite."""

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
    JudgeContractError,
    JudgeError,
    approved_payload,
    calibration_case_rows,
    confusion_counts,
    load_manifest,
    load_rubric,
    load_split,
    metric_block,
    parse_and_validate,
    rate_or_undefined,
    select_calibration_jobs,
    validation_evaluation_ids,
)
from evals.week4.f1_judge_v2 import (
    EXPECTED_HASHES,
    JUDGE_ID,
    V1_GENERATION,
    assert_provenance_is_calibration_only,
    build_model_request,
    compare_versions,
    load_inference_config,
    load_prompt,
    load_provenance,
    run_calibration,
    verify_frozen_inputs,
)

JUDGE_SOURCE = PROJECT_DIR / "evals" / "week4" / "f1_judge_v2.py"
RUNNER_SOURCE = PROJECT_DIR / "run_week4_f1_judge_v2_calibration.py"
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
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def generate(self, request):
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        return {
            "raw_text": '{"verdict":"pass","reason":"No unstated product extension.","excerpt":""}',
            "usage": {"total_token_count": 12},
            "elapsed_ms": 1.0,
            "started_at": "2026-10-23T00:00:00+00:00",
            "ended_at": "2026-10-23T00:00:01+00:00",
            "model_version": "fake",
        }


class ProvenanceTests(unittest.TestCase):
    def test_prompt_provenance_is_calibration_only(self) -> None:
        hashes = verify_frozen_inputs()
        self.assertEqual(hashes, EXPECTED_HASHES)
        prompt = load_prompt()
        self.assertIn("especially Why", prompt)
        self.assertIn("Example A", prompt)
        self.assertIn("Example B", prompt)
        self.assertNotIn("TRACE-S", prompt)
        self.assertNotIn("week4_adk_preview", prompt)
        config = load_inference_config()
        self.assertEqual(config["judge_id"], JUDGE_ID)
        self.assertEqual(config["generation"], V1_GENERATION)
        self.assertEqual(config["model"], "gemini-3.8-flash")
        provenance = load_provenance()
        manifest = load_manifest()
        assert_provenance_is_calibration_only(provenance, manifest)
        informed = {
            row["evaluation_id"]
            for row in provenance["informed_by_calibration_cases"]
        }
        self.assertTrue(informed.isdisjoint(validation_evaluation_ids(manifest)))
        self.assertIn("c953f67527f058d9", informed)
        self.assertIn("c46d129cacb772e2", informed)
        self.assertEqual(provenance["used_validation"], False)
        self.assertEqual(provenance["validation_cases_inspected"], [])


class CalibrationSelectionTests(unittest.TestCase):
    def test_only_calibration_jobs_are_selected(self) -> None:
        from evals.week4.f1_judge_v1 import load_jsonl_by_id

        manifest = load_manifest()
        split = load_split()
        rubric = load_rubric()
        calibration_ids = {
            row["evaluation_id"] for row in calibration_case_rows(manifest)
        }
        payloads = load_jsonl_by_id(
            PROJECT_DIR / "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
            calibration_ids,
        )
        jobs = select_calibration_jobs(
            manifest, payloads, rubric=rubric, split=split
        )
        self.assertEqual(len(jobs), 20)
        leaked = dict(payloads)
        leaked[next(iter(validation_evaluation_ids(manifest)))] = next(
            iter(payloads.values())
        )
        with self.assertRaises(JudgeError):
            select_calibration_jobs(manifest, leaked, rubric=rubric, split=split)


class LeakageTests(unittest.TestCase):
    def test_labels_and_identities_cannot_enter_request(self) -> None:
        payload = {
            "evaluation_id": "cafebabecafebabe",
            "case_id": "week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S04:run",
            "baseline_id": "week4_adk_preview_f1_v2",
            "scenario_id": "TRACE-S04",
            "run_id": "run-id-should-not-appear",
            "group": "calibration",
            "f1": "fail",
            "expected_result": "candidate recovery",
            "system_description": "Lobby cameras compare faces to a watchlist.",
            "retrieved_evidence": [],
            "answer": "Why asserts 1-to-many identification as established.",
        }
        request = build_model_request(payload)
        blob = request["user_text"] + request["system_instruction"]
        for field in FORBIDDEN_REQUEST_FIELDS:
            self.assertNotIn(field, request)
        for token in (
            "cafebabecafebabe",
            "week4_adk_preview_f1_v2",
            "TRACE-S04",
            "run-id-should-not-appear",
            "candidate recovery",
        ):
            self.assertNotIn(token, blob)
        self.assertEqual(
            set(approved_payload(payload)),
            {"system_description", "retrieved_evidence", "answer"},
        )


class OutputAndMetricsTests(unittest.TestCase):
    def test_exact_excerpt_and_confusion_matrix(self) -> None:
        answer = "Why: it functions as a 1-to-many biometric identification system."
        parsed = parse_and_validate(
            '{"verdict":"fail","reason":"Asserts an unknown identification mode.","excerpt":"functions as a 1-to-many biometric identification system"}',
            answer,
        )
        self.assertEqual(parsed["verdict"], "fail")
        with self.assertRaises(JudgeContractError):
            parse_and_validate(
                '{"verdict":"fail","reason":"Invented.","excerpt":"presents a badge first"}',
                answer,
            )
        counts = confusion_counts(
            [("fail", "fail"), ("fail", "pass"), ("pass", "pass"), ("pass", "fail")]
        )
        self.assertEqual(counts, {"TP": 1, "FN": 1, "TN": 1, "FP": 1})
        metrics = metric_block(counts)
        self.assertEqual(metrics["positive_class"], "fail")
        self.assertIsNone(rate_or_undefined(0, 0))

    def test_compare_versions_tracks_corrections_and_regressions(self) -> None:
        labels = {
            "fn-fixed": {"f1": "fail", "scenario_id": "TRACE-S04"},
            "fn-kept": {"f1": "fail", "scenario_id": "TRACE-S09"},
            "new-fp": {"f1": "pass", "scenario_id": "TRACE-S02"},
            "stable-tn": {"f1": "pass", "scenario_id": "TRACE-S05"},
        }

        def pred(evaluation_id: str, verdict: str) -> dict:
            return {
                "evaluation_id": evaluation_id,
                "status": "valid",
                "parsed": {"verdict": verdict, "reason": "x", "excerpt": ""},
            }

        comparison = compare_versions(
            v1_predictions=[
                pred("fn-fixed", "pass"),
                pred("fn-kept", "pass"),
                pred("new-fp", "pass"),
                pred("stable-tn", "pass"),
            ],
            v2_predictions=[
                pred("fn-fixed", "fail"),
                pred("fn-kept", "pass"),
                pred("new-fp", "fail"),
                pred("stable-tn", "pass"),
            ],
            labels=labels,
            v1_score={
                "metrics": {
                    "TP": 0,
                    "FN": 2,
                    "TN": 2,
                    "FP": 0,
                    "TPR": 0.0,
                    "TNR": 1.0,
                    "positives_in_metrics": 2,
                    "negatives_in_metrics": 2,
                },
                "valid_n": 4,
                "invalid_n": 0,
                "missing_n": 0,
                "prediction_coverage": 1.0,
                "valid_response_only": False,
            },
            v2_score={
                "metrics": {
                    "TP": 1,
                    "FN": 1,
                    "TN": 1,
                    "FP": 1,
                    "TPR": 0.5,
                    "TNR": 0.5,
                    "positives_in_metrics": 2,
                    "negatives_in_metrics": 2,
                },
                "valid_n": 4,
                "invalid_n": 0,
                "missing_n": 0,
                "prediction_coverage": 1.0,
                "valid_response_only": False,
            },
        )
        self.assertEqual(
            [row["evaluation_id"] for row in comparison["false_negatives_corrected"]],
            ["fn-fixed"],
        )
        self.assertEqual(
            [row["evaluation_id"] for row in comparison["false_negatives_retained"]],
            ["fn-kept"],
        )
        self.assertEqual(
            [row["evaluation_id"] for row in comparison["new_false_positives"]],
            ["new-fp"],
        )
        self.assertFalse(comparison["held_out"])


class IsolationTests(unittest.TestCase):
    def test_no_capstone_retrieval_or_sqlite_imports(self) -> None:
        names = _imports(JUDGE_SOURCE) | _imports(RUNNER_SOURCE)
        self.assertEqual(names & BLOCKED_IMPORTS, set())
        source = JUDGE_SOURCE.read_text(encoding="utf-8") + RUNNER_SOURCE.read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("preview_classification_search", source)
        self.assertNotIn("search_legal_sources", source)

    def test_run_calibration_refuses_labels_and_validation(self) -> None:
        with self.assertRaises(JudgeError):
            run_calibration(lambda: FakeTransport(), load_labels=True)

        tmp = Path(tempfile.mkdtemp())
        try:
            for relative in (
                "evals/week4/judge/f1_v2/prompt_v2.txt",
                "evals/week4/judge/f1_v2/inference_config.json",
                "evals/week4/judge/f1_v2/refinement_provenance.json",
                "evals/week4/golden/f1_v1/manifest.json",
                "evals/week4/golden/f1_v1/split.json",
                "evals/week4/golden/f1_v1/f1_rubric.json",
                "evals/week4/golden/f1_v1/judge_contract.json",
                "data/local/evals/week4/golden/f1_v1/cases.jsonl",
                "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
                "data/local/evals/week4/judge/f1_v1/calibration_v1/predictions.json",
            ):
                dest = tmp / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_DIR / relative, dest)
            transport = FakeTransport()
            report = run_calibration(lambda: transport, root=tmp)
            self.assertEqual(len(transport.calls), 20)
            self.assertFalse(report["held_out"])
            self.assertTrue(report["examples_reused_calibration_cases"])
            self.assertFalse(report["validation_inference"])
            predictions = json.loads(
                (
                    tmp
                    / "data/local/evals/week4/judge/f1_v2/calibration_v2/predictions.json"
                ).read_text(encoding="utf-8")
            )
            self.assertFalse(predictions["labels_included"])
            self.assertNotIn('"f1":', json.dumps(predictions))
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
