"""Run the frozen Week 4 deterministic assertions without assigning labels.

Does not modify checkers, thresholds, traces, or human annotations.
"""

from __future__ import annotations

from typing import Any

from evals.week4.checkers import (
    CHECKER_CONFIG,
    CHECKER_SUITE_ID,
    DEFERRED_DATE_CHECKER_ID,
    S19_BUDGET_CHECKER_ID,
    run_deterministic_assertions,
)
from evals.week4.codify import summarize_assertion_results


def evaluate_assertions_only(traces: list[dict[str, Any]]) -> dict[str, Any]:
    assertion_rows: dict[str, list[dict[str, Any]]] = {
        DEFERRED_DATE_CHECKER_ID: [],
        S19_BUDGET_CHECKER_ID: [],
    }
    per_trace: list[dict[str, Any]] = []
    empty_human = []
    for row in traces:
        serialized = {
            key: value.to_dict()
            for key, value in run_deterministic_assertions(row).items()
        }
        for key, value in serialized.items():
            assertion_rows[key].append(value)
        annotation = row.get("human_annotation")
        if annotation != {
            "annotator": None,
            "notes": None,
            "labels": [],
            "scores": {},
            "reviewed_at": None,
        }:
            empty_human.append(row.get("scenario_id"))
        per_trace.append(
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "assertions": serialized,
                "human_annotation": annotation,
            }
        )
    return {
        "checker_suite": CHECKER_SUITE_ID,
        "uses_human_labels": False,
        "config": CHECKER_CONFIG,
        "deterministic_assertions": {
            key: summarize_assertion_results(rows, key)
            for key, rows in assertion_rows.items()
        },
        "per_trace": per_trace,
        "original_human_annotation_fields_empty": not empty_human,
        "populated_human_annotation_ids": empty_human,
    }


def compare_assertion_summaries(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for checker_id in (DEFERRED_DATE_CHECKER_ID, S19_BUDGET_CHECKER_ID):
        before = baseline[checker_id]
        after = candidate[checker_id]
        before_fail = set(before.get("fail_ids") or [])
        after_fail = set(after.get("fail_ids") or [])
        before_pass = set(before.get("pass_ids") or [])
        after_pass = set(after.get("pass_ids") or [])
        comparison[checker_id] = {
            "baseline_denominator": before.get("denominator"),
            "candidate_denominator": after.get("denominator"),
            "baseline_fail_ids": sorted(before_fail),
            "candidate_fail_ids": sorted(after_fail),
            "still_failing": sorted(before_fail & after_fail),
            "newly_failing": sorted(after_fail - before_fail),
            "newly_passing": sorted(before_fail & after_pass),
            "regressed_from_pass": sorted(before_pass & after_fail),
        }
    return comparison
