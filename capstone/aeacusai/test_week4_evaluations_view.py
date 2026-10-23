"""Offline tests for the Week 4 Evaluations view data layer."""

from __future__ import annotations

import ast
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from aeacus_agent.trace_store import PROJECT_DIR, sha256_file
from evals.week4.checkers import (
    DEFERRED_DATE_CHECKER_ID,
    MAX_S19_SEARCH_CALLS,
    S19_BUDGET_CHECKER_ID,
    S19_SCENARIO_ID,
)
from evals.week4.evaluations_view import (
    DEFAULT_SCENARIO_ID,
    JUDGE_DECISION,
    REPLAY_DESCRIPTION,
    TIMING_TITLE,
    build_view_model,
    confusion_matrix_from_metrics,
    load_historical_bundle,
    load_evaluations_view,
    load_judge_view,
    run_offline_checks,
    scenario_detail,
)
from evals.week4.replay_timing import replay_parent_traces

MODULE_PATH = PROJECT_DIR / "evals" / "week4" / "evaluations_view.py"
FORBIDDEN_IMPORTS = {
    "sqlite3",
    "aeacus_agent.review_register",
    "aeacus_agent.preview_agent",
    "aeacus_agent.retrieval",
    "google",
    "google.genai",
    "openai",
    "pinecone",
    "run_review",
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


class EvaluationsViewIsolationTests(unittest.TestCase):
    def test_module_does_not_import_model_retrieval_or_register(self) -> None:
        imported = _imported_modules(MODULE_PATH)
        self.assertTrue(imported.isdisjoint(FORBIDDEN_IMPORTS), imported & FORBIDDEN_IMPORTS)


class EvaluationsViewBundleTests(unittest.TestCase):
    def test_historical_counts_denominators_and_provenance(self) -> None:
        model = load_evaluations_view()
        self.assertTrue(model["ok"], model.get("errors"))
        self.assertEqual(model["source"], "historical")
        self.assertTrue(model["never_an_overall_quality_or_compliance_percentage"])
        self.assertFalse(model["candidate_f2_reviewed"])

        timing = model["timing"]
        self.assertEqual(timing["title"], TIMING_TITLE)
        self.assertEqual(timing["description"], REPLAY_DESCRIPTION)
        self.assertEqual(timing["raw"]["pass"], 18)
        self.assertEqual(timing["raw"]["fail"], 2)
        self.assertEqual(timing["raw"]["denominator"], 20)
        self.assertEqual(timing["raw"]["percent"], 90.0)
        self.assertEqual(timing["raw"]["fail_ids"], ["TRACE-S02", "TRACE-S20"])
        self.assertEqual(timing["delivered"]["pass"], 20)
        self.assertEqual(timing["delivered"]["fail"], 0)
        self.assertEqual(timing["delivered"]["denominator"], 20)
        self.assertEqual(timing["delivered"]["percent"], 100.0)
        self.assertEqual(timing["change_pp"], 10.0)
        self.assertEqual(timing["checker_id"], DEFERRED_DATE_CHECKER_ID)
        self.assertEqual(timing["unchanged_assertion_id"], S19_BUDGET_CHECKER_ID)
        self.assertEqual(timing["formatter_id"], "aeacus.timing_scope.v1")
        self.assertEqual(timing["formatter_version"], "1")

        f1 = model["f1"]
        self.assertEqual(f1["parent_fail_count"], 5)
        self.assertEqual(f1["candidate_fail_count"], 5)
        self.assertEqual(f1["n_traces"], 20)
        self.assertEqual(f1["recoveries"], ["TRACE-S08", "TRACE-S20"])
        self.assertEqual(f1["regressions"], ["TRACE-S01", "TRACE-S15"])
        self.assertEqual(
            f1["persistent_failures"], ["TRACE-S04", "TRACE-S09", "TRACE-S13"]
        )
        self.assertFalse(f1["candidate_adopted"])
        self.assertTrue(f1["parent_instructions_restored"])
        self.assertFalse(f1["resolves_f1"])
        self.assertFalse(f1["candidate_f2_reviewed"])

        retrieval = model["retrieval"]
        self.assertEqual(retrieval["scenario_id"], S19_SCENARIO_ID)
        self.assertEqual(retrieval["parent_search_call_events"], 6)
        self.assertEqual(retrieval["budget"], MAX_S19_SEARCH_CALLS)
        self.assertEqual(retrieval["denominator"], 1)
        self.assertEqual(retrieval["excluded"], 19)
        self.assertFalse(retrieval["timing_repair_changes_retrieval"])
        incidental = retrieval["f1_candidate_s19"]
        self.assertTrue(incidental["incidental"])
        self.assertEqual(incidental["search_call_events"], 1)
        self.assertEqual(incidental["experiment"], "week4_adk_preview_f1_v2")

        taxonomy = model["taxonomy"]
        counts = {item["id"]: item["fail_count"] for item in taxonomy["categories"]}
        self.assertEqual(counts, {"F1": 5, "F2": 5, "F3": 2, "F4": 1})
        self.assertEqual(model["parent_baseline_id"], "week4_adk_preview_v1")
        self.assertEqual(model["candidate_baseline_id"], "week4_adk_preview_f1_v2")
        self.assertEqual(model["review"]["accepted_by"], "Lily")
        self.assertEqual(
            model["hashes"]["parent_traces"],
            "29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1",
        )

    def test_human_labels_are_separate_from_automated_results(self) -> None:
        detail = scenario_detail(load_historical_bundle(), "TRACE-S02")
        self.assertTrue(detail["ok"])
        self.assertTrue(detail["raw_is_model_text"])
        self.assertTrue(detail["delivered_is_application_rendered"])
        self.assertNotEqual(detail["raw_output"], detail["delivered_output"])
        human = detail["human_labels"]["parent"]["categories"]
        self.assertEqual(human["F3"], "fail")
        self.assertEqual(human["F1"], "pass")
        self.assertFalse(detail["automated_assertions"]["uses_human_labels"])
        raw_a = detail["automated_assertions"]["raw"][DEFERRED_DATE_CHECKER_ID]
        delivered_a = detail["automated_assertions"]["delivered"][DEFERRED_DATE_CHECKER_ID]
        self.assertEqual(raw_a["result"], "fail")
        self.assertEqual(delivered_a["result"], "pass")
        self.assertTrue(detail["failure_reason"]["human_and_automated_are_separate"])
        self.assertEqual(
            [item["category"] for item in detail["failure_reason"]["human_failures"]],
            ["F3"],
        )
        self.assertIn(
            DEFERRED_DATE_CHECKER_ID,
            [
                item["checker_id"]
                for item in detail["failure_reason"]["raw_automated_failures"]
            ],
        )
        evidence = detail["article_113"]
        self.assertTrue(evidence["record_id"].endswith("::article/113"))
        self.assertEqual(
            evidence["expected_text_sha256"],
            "0f628e97ddb44755c40162f14950a4bc8072552fda2a3c38773c5a7f30c8bd4d",
        )

    def test_offline_action_invokes_real_replay_and_checkers(self) -> None:
        with patch(
            "evals.week4.evaluations_view.replay_parent_traces",
            wraps=replay_parent_traces,
        ) as replayed:
            result = run_offline_checks(write=True)
        replayed.assert_called_once()
        self.assertTrue(result["ok"], result.get("errors"))
        self.assertEqual(result["source"], "recomputed")
        self.assertIsNotNone(result["output_path"])
        output = Path(result["output_path"])
        self.assertTrue(output.is_file())
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema"], "aeacus.week4.evaluations_recompute.v1")
        self.assertEqual(payload["result_kind"], "freshly_recomputed")
        self.assertFalse(payload["uses_human_labels"])
        self.assertIn("input_hashes", payload)
        self.assertIn("checker_file_sha256", payload)
        delivered = result["replay"]["deterministic_assertions"]["delivered"][
            DEFERRED_DATE_CHECKER_ID
        ]
        self.assertEqual(delivered["pass"], 20)
        self.assertEqual(delivered["denominator"], 20)
        s19 = result["replay"]["deterministic_assertions"]["delivered"][
            S19_BUDGET_CHECKER_ID
        ]
        self.assertEqual(s19["fail_ids"], ["TRACE-S19"])
        model = build_view_model(result["bundle"], recompute=result)
        self.assertEqual(model["source"], "recomputed")
        parent = Path(PROJECT_DIR / "data/local/traces/week4_adk_preview_v1.jsonl")
        self.assertEqual(
            sha256_file(parent),
            "29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1",
        )

    def test_missing_and_tampered_artifacts_are_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            missing = load_historical_bundle(empty)
            self.assertFalse(missing["ok"])
            self.assertTrue(missing["errors"])
            self.assertTrue(
                any(item.get("detail") == "File is missing." for item in missing["errors"])
            )

            copied = empty / "copy"
            for rel in (
                "evals/week4/taxonomy_v1.json",
                "evals/week4/annotations_v1.json",
                "evals/week4/annotations_f1_v2.json",
                "evals/week4/scenarios_v1.json",
                "evals/week4/checkers.py",
                "evals/week4/results/week4_codify_baseline_v1.json",
                "evals/week4/results/week4_adk_preview_f1_v2_assertions.json",
                "reports/week4_timing_repair_eval.json",
                "data/local/traces/week4_adk_preview_v1.jsonl",
            ):
                dest = copied / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_DIR / rel, dest)
            traces = copied / "data/local/traces/week4_adk_preview_v1.jsonl"
            traces.write_bytes(traces.read_bytes() + b"\n")
            tampered = load_historical_bundle(copied)
            self.assertFalse(tampered["ok"])
            self.assertTrue(
                any("SHA-256" in (item.get("detail") or "") for item in tampered["errors"])
            )
            failed = run_offline_checks(copied, write=False)
            self.assertFalse(failed["ok"])
            self.assertTrue(failed["errors"])


class JudgeViewTests(unittest.TestCase):
    def test_confusion_matrix_orientation_and_denominators(self) -> None:
        matrix = confusion_matrix_from_metrics(
            {"TP": 0, "FN": 5, "TN": 15, "FP": 0}
        )
        self.assertEqual(matrix["row_labels"][0], "Reviewed F1 failure")
        self.assertEqual(matrix["row_labels"][1], "Reviewed F1 pass")
        self.assertEqual(matrix["column_labels"][0], "Judge fail")
        self.assertEqual(matrix["column_labels"][1], "Judge pass")
        self.assertEqual(matrix["cells"][0], [0, 5])
        self.assertEqual(matrix["cells"][1], [0, 15])
        self.assertEqual(matrix["positive_class"], "fail")

        judge = load_judge_view()
        self.assertTrue(judge["ok"], judge.get("errors"))
        self.assertEqual(judge["default_split"], "validation")
        self.assertFalse(judge["mixed_headline"])
        self.assertTrue(judge["tnr_is_not_overall_success"])
        self.assertEqual(judge["decision"], JUDGE_DECISION)
        for version in ("v1", "v2"):
            block = judge["validation"][version]
            self.assertEqual(block["TP"], 0)
            self.assertEqual(block["FN"], 5)
            self.assertEqual(block["TN"], 15)
            self.assertEqual(block["FP"], 0)
            self.assertEqual(block["TPR"]["label"], "0/5 (0%)")
            self.assertEqual(block["TNR"]["label"], "15/15 (100%)")
            self.assertEqual(block["coverage"]["label"], "20/20 (100%)")
            self.assertTrue(block["agrees_with_saved_report"])
            self.assertEqual(len(block["false_negatives"]), 5)
            self.assertTrue(block["false_negatives"][0]["input"])
            self.assertTrue(block["false_negatives"][0]["case_id"])
        self.assertEqual(judge["calibration"]["v1"]["TPR"]["label"], "0/5 (0%)")
        self.assertEqual(judge["calibration"]["v1"]["TNR"]["label"], "15/15 (100%)")
        self.assertEqual(judge["calibration"]["v2"]["TPR"]["label"], "2/5 (40%)")
        self.assertEqual(judge["calibration"]["v2"]["TNR"]["label"], "15/15 (100%)")
        self.assertTrue(judge["calibration"]["v2_examples_reused_calibration_cases"])
        self.assertFalse(
            judge["calibration"]["calibration_improvement_transferred_to_validation"]
        )
        provenance = judge["provenance"]
        self.assertEqual(provenance["n_outputs"], 40)
        self.assertEqual(provenance["n_paired_scenarios"], 20)
        self.assertEqual(provenance["f1_fail"], 10)
        self.assertEqual(provenance["f1_pass"], 30)
        self.assertEqual(provenance["calibration_groups"], 10)
        self.assertEqual(provenance["validation_groups"], 10)
        self.assertEqual(provenance["overlap"], [])
        self.assertTrue(provenance["held_out_from_refinement"])
        self.assertFalse(provenance["unseen_capstone_scenarios"])
        self.assertFalse(judge["invoked_judge"])

    def test_empty_invalid_and_mismatched_judge_artifacts(self) -> None:
        empty = load_judge_view(Path(tempfile.mkdtemp()))
        self.assertFalse(empty["ok"])
        self.assertTrue(empty["errors"])
        self.assertEqual(empty["default_split"], "validation")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            from evals.week4.evaluations_view import JUDGE_PATHS

            for relative in JUDGE_PATHS.values():
                dest = root / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(PROJECT_DIR / relative, dest)
            report = json.loads(
                (root / "reports/week4_f1_judge_validation.json").read_text(
                    encoding="utf-8"
                )
            )
            report["v1"]["score"]["metrics"]["TP"] = 99
            (root / "reports/week4_f1_judge_validation.json").write_text(
                json.dumps(report), encoding="utf-8"
            )
            mismatched = load_judge_view(root)
            self.assertFalse(mismatched["ok"])
            self.assertTrue(
                any(
                    item.get("code") == "judge_report_mismatch"
                    for item in mismatched["errors"]
                )
            )
            self.assertEqual(mismatched["validation"]["v1"]["TP"], 0)

    def test_module_does_not_invoke_judge_or_sqlite(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)


class EvaluationsViewDefaultScenarioTests(unittest.TestCase):
    def test_default_scenario_is_s02(self) -> None:
        model = load_evaluations_view()
        self.assertEqual(model["selected_scenario"], DEFAULT_SCENARIO_ID)
        self.assertEqual(model["scenario"]["scenario_id"], "TRACE-S02")
        self.assertIn("language school", model["scenario"]["input"])


if __name__ == "__main__":
    unittest.main()
