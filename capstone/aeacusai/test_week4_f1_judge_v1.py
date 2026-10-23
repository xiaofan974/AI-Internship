"""Offline checks for F1 judge v1. No live model, retrieval, or SQLite."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evals.week4.f1_judge_v1 import (
    EXPECTED_HASHES,
    FORBIDDEN_REQUEST_FIELDS,
    JUDGE_ID,
    PROJECT_DIR,
    JudgeContractError,
    JudgeError,
    JudgeStopError,
    approved_payload,
    assert_request_has_no_leakage,
    build_model_request,
    calibration_case_rows,
    confusion_counts,
    is_stop_error,
    load_inference_config,
    load_jsonl_by_id,
    load_manifest,
    load_prompt,
    load_rubric,
    load_split,
    metric_block,
    parse_and_validate,
    persist_prediction_line,
    predict_one,
    rate_or_undefined,
    run_calibration,
    score_predictions,
    select_calibration_jobs,
    validation_evaluation_ids,
    verify_frozen_inputs,
)

JUDGE_SOURCE = PROJECT_DIR / "evals" / "week4" / "f1_judge_v1.py"
RUNNER_SOURCE = PROJECT_DIR / "run_week4_f1_judge_v1_calibration.py"
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
    def __init__(self, responses: dict[str, str] | None = None, error: Exception | None = None):
        self.responses = responses or {}
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


class FrozenInputsTests(unittest.TestCase):
    def test_required_inputs_complete_and_hashes_match(self) -> None:
        observed = verify_frozen_inputs()
        self.assertEqual(observed, EXPECTED_HASHES)
        config = load_inference_config()
        self.assertEqual(config["judge_id"], JUDGE_ID)
        self.assertTrue(config["separate_from_capstone_generation"])
        self.assertEqual(config["generation"]["temperature"], 0.0)
        self.assertEqual(config["generation"]["tools"], [])
        self.assertFalse(config["generation"]["include_thoughts"])
        prompt = load_prompt()
        self.assertIn("Assess F1 only", prompt)
        self.assertNotIn("TRACE-S", prompt)
        self.assertNotIn("week4_adk_preview", prompt)

    def test_calibration_only_jobs(self) -> None:
        manifest = load_manifest()
        split = load_split()
        rubric = load_rubric()
        calibration_ids = {
            row["evaluation_id"] for row in calibration_case_rows(manifest)
        }
        self.assertEqual(len(calibration_ids), 20)
        payloads = load_jsonl_by_id(
            PROJECT_DIR / "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
            calibration_ids,
        )
        jobs = select_calibration_jobs(
            manifest, payloads, rubric=rubric, split=split
        )
        self.assertEqual(len(jobs), 20)
        self.assertTrue(
            set(payloads).isdisjoint(validation_evaluation_ids(manifest))
        )
        leaked = dict(payloads)
        validation_id = next(iter(validation_evaluation_ids(manifest)))
        leaked[validation_id] = next(iter(payloads.values()))
        with self.assertRaises(JudgeError):
            select_calibration_jobs(
                manifest, leaked, rubric=rubric, split=split
            )


class LeakageTests(unittest.TestCase):
    def test_labels_and_comparison_metadata_cannot_enter_request(self) -> None:
        payload = {
            "evaluation_id": "deadbeefdeadbeef",
            "case_id": "week4_f1_golden_v1:week4_adk_preview_v1:TRACE-S01:run",
            "baseline_id": "week4_adk_preview_v1",
            "scenario_id": "TRACE-S01",
            "run_id": "run-id-should-not-appear",
            "group": "calibration",
            "f1": "fail",
            "gold": "fail",
            "expected": "fail",
            "expected_result": "candidate recovery",
            "system_description": "A fictional inventory tool used in a warehouse.",
            "retrieved_evidence": [
                {
                    "label": "Article 6",
                    "record_id": "rec-1",
                    "text_sha256": "abc",
                    "text": "Classification rules.",
                }
            ],
            "answer": "Provisional classification: limited risk if the stated facts hold.",
            "f1_rubric": {
                "rubric_id": "week4_f1_rubric_v1",
                "category_id": "F1",
                "title": "Classification relies on an unstated premise or extends to an underspecified product.",
                "positive_means": "F1 failure detected",
            },
        }
        request = build_model_request(payload)
        user_text = request["user_text"]
        for field in FORBIDDEN_REQUEST_FIELDS:
            self.assertNotIn(field, request)
        for token in (
            "deadbeefdeadbeef",
            "week4_adk_preview_v1",
            "TRACE-S01",
            "run-id-should-not-appear",
            "candidate recovery",
            "week4_f1_golden_v1",
        ):
            self.assertNotIn(token, user_text)
            self.assertNotIn(token, request["system_instruction"])
        self.assertIn("A fictional inventory tool used in a warehouse.", user_text)
        assert_request_has_no_leakage(request, payload)
        stripped = approved_payload(payload)
        self.assertEqual(set(stripped), {"system_description", "retrieved_evidence", "answer"})


class OutputValidationTests(unittest.TestCase):
    def test_invalid_verdict_and_invented_excerpt(self) -> None:
        answer = "The stated system is high-risk if it scores creditworthiness."
        parsed = parse_and_validate(
            '{"verdict":"fail","reason":"Extends beyond the stated system.","excerpt":"scores creditworthiness"}',
            answer,
        )
        self.assertEqual(parsed["verdict"], "fail")
        with self.assertRaises(JudgeContractError):
            parse_and_validate(
                '{"verdict":"maybe","reason":"Unsure.","excerpt":""}',
                answer,
            )
        with self.assertRaises(JudgeContractError):
            parse_and_validate(
                '{"verdict":"fail","reason":"Invented.","excerpt":"biometric categorisation"}',
                answer,
            )
        with self.assertRaises(JudgeContractError):
            parse_and_validate(
                '{"verdict":"pass","reason":"Fine.","excerpt":"high-risk"}',
                answer,
            )
        with self.assertRaises(JudgeContractError):
            parse_and_validate("not json", answer)
        with self.assertRaises(JudgeContractError):
            parse_and_validate(
                '{"verdict":"fail","reason":"line1\\nline2","excerpt":"high-risk"}',
                answer,
            )


class MetricsTests(unittest.TestCase):
    def test_confusion_matrix_uses_failure_as_positive(self) -> None:
        counts = confusion_counts(
            [
                ("fail", "fail"),
                ("fail", "pass"),
                ("pass", "pass"),
                ("pass", "fail"),
            ]
        )
        self.assertEqual(counts, {"TP": 1, "FN": 1, "TN": 1, "FP": 1})
        metrics = metric_block(counts)
        self.assertEqual(metrics["TPR"], 0.5)
        self.assertEqual(metrics["TNR"], 0.5)
        self.assertEqual(metrics["positives_in_metrics"], 2)
        self.assertEqual(metrics["negatives_in_metrics"], 2)
        self.assertEqual(metrics["positive_class"], "fail")

    def test_zero_denominators_remain_undefined(self) -> None:
        self.assertIsNone(rate_or_undefined(0, 0))
        all_pass = metric_block(confusion_counts([("pass", "pass")]))
        self.assertIsNone(all_pass["TPR"])
        self.assertEqual(all_pass["TNR"], 1.0)
        all_fail = metric_block(confusion_counts([("fail", "fail")]))
        self.assertEqual(all_fail["TPR"], 1.0)
        self.assertIsNone(all_fail["TNR"])

    def test_invalid_predictions_are_excluded_from_rates(self) -> None:
        score = score_predictions(
            [
                {
                    "evaluation_id": "a",
                    "status": "valid",
                    "parsed": {
                        "verdict": "fail",
                        "reason": "Unstated product.",
                        "excerpt": "the platform",
                    },
                },
                {
                    "evaluation_id": "b",
                    "status": "invalid",
                    "parsed": None,
                    "validation_error": "invented excerpt",
                },
            ],
            {
                "a": {"f1": "fail", "scenario_id": "TRACE-S04"},
                "b": {"f1": "pass", "scenario_id": "TRACE-S02"},
            },
            {
                "a": {"system_description": "A", "answer": "Uses the platform as high-risk."},
                "b": {"system_description": "B", "answer": "Limited risk."},
            },
        )
        self.assertEqual(score["metrics"]["TP"], 1)
        self.assertEqual(score["valid_n"], 1)
        self.assertEqual(score["invalid_n"], 1)
        self.assertTrue(score["valid_response_only"])
        self.assertIsNone(score["metrics"]["TNR"])


class PartialBatchTests(unittest.TestCase):
    def test_provider_errors_and_partial_batches_are_preserved(self) -> None:
        self.assertTrue(is_stop_error(RuntimeError("401 UNAUTHENTICATED")))
        self.assertTrue(is_stop_error(RuntimeError("RESOURCE_EXHAUSTED quota")))
        self.assertFalse(is_stop_error(RuntimeError("malformed JSON from model")))
        job = {
            "evaluation_id": "abc123abc123abcd",
            "payload": {
                "system_description": "A scanner.",
                "retrieved_evidence": [],
                "answer": "Limited risk if used only as described.",
            },
        }
        with self.assertRaises(JudgeStopError):
            predict_one(
                FakeTransport(error=RuntimeError("UNAUTHENTICATED API key")),
                job,
            )
        recorded = predict_one(
            FakeTransport(error=RuntimeError("malformed upstream payload")),
            job,
        )
        self.assertEqual(recorded["status"], "provider_error")
        self.assertIsNone(recorded["parsed"])
        self.assertIn("malformed upstream payload", recorded["provider_error"])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partial.jsonl"
            persist_prediction_line(path, recorded)
            persist_prediction_line(
                path,
                {"evaluation_id": "second", "status": "stopped", "parsed": None},
            )
            lines = path.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(json.loads(lines[0])["status"], "provider_error")


class IsolationTests(unittest.TestCase):
    def test_no_capstone_retrieval_or_sqlite_imports(self) -> None:
        names = _imports(JUDGE_SOURCE) | _imports(RUNNER_SOURCE)
        blocked = names & BLOCKED_IMPORTS
        self.assertEqual(blocked, set())
        source = JUDGE_SOURCE.read_text(encoding="utf-8") + RUNNER_SOURCE.read_text(
            encoding="utf-8"
        )
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("preview_classification_search", source)
        self.assertNotIn("search_legal_sources", source)


class CalibrationRunnerIsolationTests(unittest.TestCase):
    def test_run_calibration_refuses_preloaded_labels_and_does_not_call_validation(self) -> None:
        with self.assertRaises(JudgeError):
            run_calibration(lambda: FakeTransport(), load_labels=True)

        tmp = Path(tempfile.mkdtemp())
        try:
            for relative in (
                "evals/week4/judge/f1_v1/prompt_v1.txt",
                "evals/week4/judge/f1_v1/inference_config.json",
                "evals/week4/golden/f1_v1/manifest.json",
                "evals/week4/golden/f1_v1/split.json",
                "evals/week4/golden/f1_v1/f1_rubric.json",
                "evals/week4/golden/f1_v1/judge_contract.json",
                "data/local/evals/week4/golden/f1_v1/cases.jsonl",
                "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
            ):
                dest = tmp / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_DIR / relative, dest)
            transport = FakeTransport()
            with patch.object(
                FakeTransport,
                "generate",
                wraps=transport.generate,
            ) as wrapped:
                report = run_calibration(lambda: transport, root=tmp)
            self.assertEqual(wrapped.call_count, 20)
            self.assertEqual(report["score"]["expected_n"], 20)
            self.assertFalse(report["validation_inference"])
            self.assertTrue(report["not_an_application_or_approval_gate"])
            predictions = json.loads(
                (tmp / "data/local/evals/week4/judge/f1_v1/calibration_v1/predictions.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(predictions["labels_included"])
            serialized = json.dumps(predictions)
            self.assertNotIn('"f1":', serialized)
            self.assertNotIn("week4_adk_preview_v1", serialized)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
