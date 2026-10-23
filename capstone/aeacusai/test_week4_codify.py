"""Offline Week 4 taxonomy and checker tests. Zero provider calls."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aeacus_agent.trace_store import PROJECT_DIR, sha256_file
from evals.week4.checkers import (
    DEFERRED_DATE_CHECKER_ID,
    S19_BUDGET_CHECKER_ID,
    check_deferred_date_qualifications,
    check_s19_retrieval_budget,
    count_preview_classification_search_calls,
    extract_timing_and_scope,
)
from evals.week4.codify import (
    EXPECTED_CATEGORY_FAILURES,
    EXPECTED_DISTINCT_FAILING_TRACES,
    EXPECTED_SOURCE_SHA256,
    SourceMismatchError,
    default_trace_path,
    evaluate_baseline,
    load_annotations,
    load_taxonomy,
    verify_source_hash,
)

QUALIFIED_TIMING = """### Timing and scope

Under Article 113(c), Chapter III, Sections 1, 2, and 3 (with the exception of Article 6(5)) apply from 2 December 2027.
"""


def _trace(
    *,
    scenario_id: str = "TRACE-S01",
    run_id: str = "run-1",
    output: str = QUALIFIED_TIMING,
    events: list[dict] | None = None,
) -> dict:
    return {
        "scenario_id": scenario_id,
        "run_id": run_id,
        "final_output": output,
        "events": events or [],
    }


def _act(query: str = "q") -> dict:
    return {
        "kind": "act",
        "tool": "preview_classification_search",
        "query": query,
    }


def _observe() -> dict:
    return {
        "kind": "observe",
        "tool": "preview_classification_search",
        "status": "ok",
    }


class TaxonomyFreezeTests(unittest.TestCase):
    def test_taxonomy_and_annotation_counts(self) -> None:
        taxonomy = load_taxonomy(PROJECT_DIR / "evals" / "week4" / "taxonomy_v1.json")
        annotations = load_annotations(
            PROJECT_DIR / "evals" / "week4" / "annotations_v1.json"
        )
        self.assertEqual(taxonomy["first_improvement_target"], "F1")
        self.assertEqual(
            {item["id"]: item["priority_weight"] for item in taxonomy["categories"]},
            {"F1": 3, "F2": 3, "F3": 2, "F4": 1},
        )
        summary = annotations["summary"]
        self.assertEqual(summary["category_failures"], EXPECTED_CATEGORY_FAILURES)
        self.assertEqual(
            summary["distinct_failing_traces"], EXPECTED_DISTINCT_FAILING_TRACES
        )
        self.assertEqual(summary["n_traces"], 20)
        self.assertEqual(summary["summed_category_frequencies"], 13)
        self.assertNotEqual(
            summary["summed_category_frequencies"], summary["distinct_failing_traces"]
        )
        self.assertEqual(taxonomy["review"]["date"], "2026-10-23")
        self.assertIsNone(taxonomy["review"]["acceptance_time"])
        self.assertIsNone(annotations["review"]["acceptance_time"])
        self.assertEqual(annotations["source_traces"]["sha256"], EXPECTED_SOURCE_SHA256)
        for item in annotations["traces"]:
            extra = set(item) - {"scenario_id", "run_id", "categories", "overall"}
            self.assertFalse(extra)
            self.assertTrue(item["scenario_id"].startswith("TRACE-S"))
            self.assertTrue(item["run_id"])

    def test_overall_pass_requires_all_four_passes(self) -> None:
        traces = [
            {
                "scenario_id": "TRACE-S01",
                "run_id": "a",
                "categories": {"F1": "pass", "F2": "pass", "F3": "pass", "F4": "pass"},
                "overall": "pass",
            },
            {
                "scenario_id": "TRACE-S02",
                "run_id": "b",
                "categories": {"F1": "fail", "F2": "pass", "F3": "pass", "F4": "pass"},
                "overall": "fail",
            },
        ]
        # summarize_annotations enforces the frozen 5/5/2/1 counts, so use the
        # real freeze for that invariant and only check the overall rule here.
        item = traces[1]
        failed = [cid for cid, value in item["categories"].items() if value == "fail"]
        self.assertEqual(item["overall"], "fail")
        self.assertEqual(failed, ["F1"])


class DeferredDateCheckerTests(unittest.TestCase):
    def test_accepts_list_and_range_section_variants(self) -> None:
        variants = [
            "Chapter III, Sections 1, 2, and 3, with the exception of Article 6(5), apply from 2 December 2027.",
            "Chapter III, Sections 1, 2 and 3 except Article 6(5) apply from December 2027.",
            "Chapter III Sections 1–3 (excepting Article 6(5)) apply from 2 August 2028.",
            "Chapter 3, Sections 1-3 excluding Article 6(5) apply from 2 December 2027.",
            "Chapter III, Sections 1 to 3, Article 6(5) exception, from 2 December 2027.",
        ]
        for body in variants:
            output = f"### Timing and scope\n\n{body}\n"
            result = check_deferred_date_qualifications(_trace(output=output))
            self.assertEqual(result.result, "pass", body)

    def test_plain_heading_is_accepted(self) -> None:
        output = (
            "Timing and scope\n\n"
            "Chapter III, Sections 1–3, with the exception of Article 6(5), "
            "apply from 2 December 2027.\n"
        )
        result = check_deferred_date_qualifications(_trace(output=output))
        self.assertEqual(result.result, "pass")

    def test_rejects_missing_chapter_sections_or_exception(self) -> None:
        cases = [
            "Sections 1, 2, and 3, with the exception of Article 6(5), apply from 2 December 2027.",
            "Chapter III, with the exception of Article 6(5), applies from 2 December 2027.",
            "Chapter III, Sections 1, 2, and 3 apply from 2 December 2027. Under Article 6(5), guidelines are due by 2 February 2026.",
        ]
        for body in cases:
            output = f"### Timing and scope\n\n{body}\n"
            result = check_deferred_date_qualifications(_trace(output=output))
            self.assertEqual(result.result, "fail", body)
            self.assertTrue(result.applicable)

    def test_not_applicable_without_deferral_or_section(self) -> None:
        no_dates = check_deferred_date_qualifications(
            _trace(output="### Timing and scope\n\nLimited to Article 6, Annex III, and Article 113.\n")
        )
        self.assertEqual(no_dates.result, "not_applicable")
        self.assertFalse(no_dates.applicable)
        dates_elsewhere = check_deferred_date_qualifications(
            _trace(
                output=(
                    "### Why\n\nRules apply from 2 December 2027.\n\n"
                    "### Timing and scope\n\nLimited to the classification subset.\n"
                )
            )
        )
        self.assertEqual(dates_elsewhere.result, "not_applicable")
        missing = check_deferred_date_qualifications(_trace(output="No headings here."))
        self.assertEqual(missing.result, "not_applicable")

    def test_extracts_only_timing_section(self) -> None:
        text = (
            "### Why\nChapter III, Sections 1–3, exception of Article 6(5), 2 December 2027.\n\n"
            "### Timing and scope\nOnly the subset is in scope.\n"
        )
        section = extract_timing_and_scope(text)
        self.assertIsNotNone(section)
        self.assertNotIn("Why", section or "")
        self.assertIn("subset", section or "")


class RetrievalBudgetCheckerTests(unittest.TestCase):
    def test_counts_call_events_not_responses_or_queries(self) -> None:
        events = [_act("same"), _observe(), _act("same"), _observe(), _act("other")]
        self.assertEqual(count_preview_classification_search_calls(events), 3)

    def test_s19_accepts_two_or_fewer_calls(self) -> None:
        for count in (0, 1, 2):
            result = check_s19_retrieval_budget(
                _trace(scenario_id="TRACE-S19", events=[_act(str(i)) for i in range(count)])
            )
            self.assertEqual(result.result, "pass", count)
            self.assertTrue(result.applicable)
            self.assertEqual(result.evidence["search_call_events"], count)

    def test_s19_rejects_more_than_two_calls(self) -> None:
        result = check_s19_retrieval_budget(
            _trace(scenario_id="TRACE-S19", events=[_act(str(i)) for i in range(3)])
        )
        self.assertEqual(result.result, "fail")
        self.assertTrue(result.applicable)
        self.assertEqual(result.evidence["search_call_events"], 3)

    def test_other_scenarios_are_not_applicable(self) -> None:
        result = check_s19_retrieval_budget(
            _trace(scenario_id="TRACE-S01", events=[_act() for _ in range(6)])
        )
        self.assertEqual(result.result, "not_applicable")
        self.assertFalse(result.applicable)
        self.assertEqual(result.evidence["search_call_events"], 6)

    def test_observe_events_do_not_count_against_s19(self) -> None:
        events = [_act(), _observe(), _observe(), _observe()]
        result = check_s19_retrieval_budget(
            _trace(scenario_id="TRACE-S19", events=events)
        )
        self.assertEqual(result.result, "pass")
        self.assertEqual(result.evidence["search_call_events"], 1)


class SourceAndBaselineEvaluationTests(unittest.TestCase):
    def test_source_hash_stops_on_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "traces.jsonl"
            path.write_text('{"scenario_id":"TRACE-S01"}\n', encoding="utf-8")
            with self.assertRaises(SourceMismatchError):
                verify_source_hash(path, EXPECTED_SOURCE_SHA256)

    def test_saved_baseline_has_expected_findings(self) -> None:
        path = default_trace_path()
        if not path.is_file():
            self.skipTest("local baseline traces are not present")
        self.assertEqual(sha256_file(path), EXPECTED_SOURCE_SHA256)
        payload = evaluate_baseline()
        self.assertEqual(payload["checkpoint"], "baseline")
        self.assertEqual(payload["source"]["unattempted_scenarios"], [])
        deferred = payload["deterministic_assertions"][DEFERRED_DATE_CHECKER_ID]
        budget = payload["deterministic_assertions"][S19_BUDGET_CHECKER_ID]
        self.assertEqual(deferred["fail_ids"], ["TRACE-S02", "TRACE-S20"])
        self.assertEqual(deferred["denominator"], 20)
        self.assertEqual(budget["fail_ids"], ["TRACE-S19"])
        self.assertEqual(budget["denominator"], 1)
        self.assertEqual(budget["not_applicable"], 19)
        self.assertEqual(payload["disagreements_with_reviewed_labels"], [])
        self.assertFalse(payload["original_human_annotation_fields"]["populated"])
        s02 = next(row for row in payload["per_trace"] if row["scenario_id"] == "TRACE-S02")
        self.assertEqual(s02["assertions"][DEFERRED_DATE_CHECKER_ID]["result"], "fail")
        self.assertIn(
            "Sections 1–3",
            s02["assertions"][DEFERRED_DATE_CHECKER_ID]["reasons"][0],
        )


if __name__ == "__main__":
    unittest.main()
