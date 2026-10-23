"""Offline Week 4 evaluation bundle for the Streamlit Evaluations view.

Reads frozen taxonomy, annotations, assertion results, timing-repair
reports, and saved F1 judge predictions. Recomputes only the existing
deterministic checkers, the timing formatter, and judge metrics from
those saved files. Does not call models, retrieve, or open the review
register.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from aeacus_agent.timing_scope import (
    EXPECTED_ARTICLE_113_RECORD_ID,
    EXPECTED_ARTICLE_113_TEXT_SHA256,
    FORMATTER_ID,
    FORMATTER_VERSION,
    apply_timing_repair,
    records_from_events,
)
from aeacus_agent.trace_store import PROJECT_DIR, sha256_file, sha256_text, utc_now
from evals.week4.checkers import (
    CHECKER_SUITE_ID,
    DEFERRED_DATE_CHECKER_ID,
    MAX_S19_SEARCH_CALLS,
    S19_BUDGET_CHECKER_ID,
    S19_SCENARIO_ID,
    count_preview_classification_search_calls,
    run_deterministic_assertions,
)
from evals.week4.codify import EXPECTED_SOURCE_SHA256, load_traces, verify_source_hash
from evals.week4.evaluate_assertions import evaluate_assertions_only
from evals.week4.f1_judge_v1 import (
    association_map,
    load_jsonl_by_id,
    score_predictions,
)
from evals.week4.replay_timing import LABEL as REPLAY_LABEL
from evals.week4.replay_timing import replay_parent_traces

REPLAY_DESCRIPTION = (
    "Application-layer replay of 20 saved live traces.\n"
    "No new model or retrieval calls."
)
DEFAULT_SCENARIO_ID = "TRACE-S02"
PARENT_BASELINE_ID = "week4_adk_preview_v1"
CANDIDATE_BASELINE_ID = "week4_adk_preview_f1_v2"
TIMING_TITLE = "Timing qualification checks"

RELATIVE_PATHS = {
    "taxonomy": "evals/week4/taxonomy_v1.json",
    "annotations": "evals/week4/annotations_v1.json",
    "annotations_f1": "evals/week4/annotations_f1_v2.json",
    "scenarios": "evals/week4/scenarios_v1.json",
    "parent_traces": "data/local/traces/week4_adk_preview_v1.jsonl",
    "candidate_traces": "data/local/traces/week4_adk_preview_f1_v2.jsonl",
    "baseline_results": "evals/week4/results/week4_codify_baseline_v1.json",
    "f1_assertions": "evals/week4/results/week4_adk_preview_f1_v2_assertions.json",
    "timing_report": "reports/week4_timing_repair_eval.json",
    "checkers": "evals/week4/checkers.py",
}

RECOMPUTE_DIR = Path("evals/week4/results/offline_recompute")
JUDGE_DECISION = (
    "Both judges missed every reviewed validation failure. "
    "Keep both versions outside detection, approval, and release gates."
)
JUDGE_PATHS = {
    "golden_manifest": "evals/week4/golden/f1_v1/manifest.json",
    "golden_split": "evals/week4/golden/f1_v1/split.json",
    "payloads": "data/local/evals/week4/golden/f1_v1/judge_payloads.jsonl",
    "v1_calibration_predictions": (
        "data/local/evals/week4/judge/f1_v1/calibration_v1/predictions.json"
    ),
    "v2_calibration_predictions": (
        "data/local/evals/week4/judge/f1_v2/calibration_v2/predictions.json"
    ),
    "validation_v1_predictions": (
        "data/local/evals/week4/judge/validation_v1/v1_predictions.json"
    ),
    "validation_v2_predictions": (
        "data/local/evals/week4/judge/validation_v1/v2_predictions.json"
    ),
    "v1_calibration_report": "reports/week4_f1_judge_v1_calibration.json",
    "v2_calibration_report": "reports/week4_f1_judge_v2_calibration.json",
    "validation_report": "reports/week4_f1_judge_validation.json",
    "v2_provenance": "evals/week4/judge/f1_v2/refinement_provenance.json",
}


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_error(label: str, path: Path, detail: str) -> dict[str, str]:
    return {
        "code": "artifact_error",
        "label": label,
        "path": str(path),
        "detail": detail,
    }


def _rate(passed: int | None, denominator: int | None) -> float | None:
    if passed is None or not denominator:
        return None
    return round(100.0 * passed / denominator, 1)


def _change_pp(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(after - before, 1)


def _assert_schema(payload: Any, expected: str, label: str) -> str | None:
    if not isinstance(payload, dict):
        return f"{label} is not a JSON object."
    schema = payload.get("schema")
    if schema != expected:
        return f"{label} schema is {schema!r}, expected {expected!r}."
    return None


def _hash_or_none(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _verify_file(
    *,
    label: str,
    path: Path,
    expected_sha256: str | None = None,
    errors: list[dict[str, str]],
) -> str | None:
    if not path.is_file():
        errors.append(_file_error(label, path, "File is missing."))
        return None
    digest = sha256_file(path)
    if expected_sha256 and digest != expected_sha256:
        errors.append(
            _file_error(
                label,
                path,
                f"SHA-256 mismatch: expected {expected_sha256}, observed {digest}.",
            )
        )
        return digest
    return digest


def load_historical_bundle(project_dir: Path | None = None) -> dict[str, Any]:
    """Load frozen Week 4 artifacts. Errors stay visible; nothing is invented."""
    root = Path(project_dir) if project_dir else PROJECT_DIR
    errors: list[dict[str, str]] = []
    paths = {key: root / rel for key, rel in RELATIVE_PATHS.items()}
    hashes: dict[str, str | None] = {}

    for key, path in paths.items():
        hashes[key] = _hash_or_none(path)
        if not path.is_file():
            errors.append(_file_error(key, path, "File is missing."))

    required_ok = all(paths[key].is_file() for key in (
        "taxonomy",
        "annotations",
        "annotations_f1",
        "scenarios",
        "parent_traces",
        "baseline_results",
        "f1_assertions",
        "timing_report",
        "checkers",
    ))
    if not required_ok:
        return {
            "ok": False,
            "source": "historical",
            "errors": errors,
            "project_dir": str(root),
            "paths": {key: str(path) for key, path in paths.items()},
            "hashes": hashes,
        }

    try:
        verify_source_hash(paths["parent_traces"], EXPECTED_SOURCE_SHA256)
    except Exception as exc:
        errors.append(
            _file_error("parent_traces", paths["parent_traces"], str(exc))
        )

    taxonomy = _read_json(paths["taxonomy"])
    annotations = _read_json(paths["annotations"])
    annotations_f1 = _read_json(paths["annotations_f1"])
    scenarios = _read_json(paths["scenarios"])
    baseline_results = _read_json(paths["baseline_results"])
    f1_assertions = _read_json(paths["f1_assertions"])
    timing_report = _read_json(paths["timing_report"])

    for message in (
        _assert_schema(taxonomy, "aeacus.week4.taxonomy.v1", "taxonomy"),
        _assert_schema(annotations, "aeacus.week4.annotations.v1", "annotations"),
        _assert_schema(
            annotations_f1,
            "aeacus.week4.annotations.f1_candidate.v1",
            "F1 annotations",
        ),
        _assert_schema(scenarios, "aeacus.week4.scenarios.v1", "scenarios"),
        _assert_schema(
            baseline_results, "aeacus.week4.codify.results.v1", "baseline results"
        ),
        _assert_schema(
            f1_assertions, "aeacus.week4.codify.results.v1", "F1 assertion results"
        ),
        _assert_schema(
            timing_report, "aeacus.week4.timing_repair_eval.v1", "timing-repair report"
        ),
    ):
        if message:
            errors.append(
                {
                    "code": "schema_error",
                    "label": "schema",
                    "path": "",
                    "detail": message,
                }
            )

    expected_from_results = (baseline_results.get("hashes") or {}) if isinstance(
        baseline_results, dict
    ) else {}
    for key, hash_key in (
        ("taxonomy", "taxonomy_v1"),
        ("annotations", "annotations_v1"),
        ("checkers", "checkers_py"),
        ("scenarios", "scenarios_v1"),
        ("parent_traces", "source_traces"),
    ):
        expected = expected_from_results.get(hash_key)
        if expected and hashes.get(key) and hashes[key] != expected:
            errors.append(
                _file_error(
                    key,
                    paths[key],
                    f"Does not match {hash_key} recorded in baseline results "
                    f"({expected}).",
                )
            )

    ann_source = (annotations.get("source_traces") or {}) if isinstance(
        annotations, dict
    ) else {}
    if ann_source.get("sha256") and hashes["parent_traces"] != ann_source.get("sha256"):
        errors.append(
            _file_error(
                "parent_traces",
                paths["parent_traces"],
                "Does not match annotations_v1 source_traces.sha256.",
            )
        )
    f1_parent = (annotations_f1.get("parent_source_traces") or {}) if isinstance(
        annotations_f1, dict
    ) else {}
    if f1_parent.get("sha256") and hashes["parent_traces"] != f1_parent.get("sha256"):
        errors.append(
            _file_error(
                "parent_traces",
                paths["parent_traces"],
                "Does not match annotations_f1_v2 parent_source_traces.sha256.",
            )
        )
    if paths["candidate_traces"].is_file():
        f1_source = (annotations_f1.get("source_traces") or {}) if isinstance(
            annotations_f1, dict
        ) else {}
        if f1_source.get("sha256") and hashes["candidate_traces"] != f1_source.get(
            "sha256"
        ):
            errors.append(
                _file_error(
                    "candidate_traces",
                    paths["candidate_traces"],
                    "Does not match annotations_f1_v2 source_traces.sha256.",
                )
            )

    traces: list[dict[str, Any]] = []
    if paths["parent_traces"].is_file() and not any(
        item.get("label") == "parent_traces" for item in errors
    ):
        traces = load_traces(paths["parent_traces"])

    return {
        "ok": not errors,
        "source": "historical",
        "errors": errors,
        "project_dir": str(root),
        "paths": {key: str(path) for key, path in paths.items()},
        "hashes": hashes,
        "taxonomy": taxonomy,
        "annotations": annotations,
        "annotations_f1": annotations_f1,
        "scenarios": scenarios,
        "baseline_results": baseline_results,
        "f1_assertions": f1_assertions,
        "timing_report": timing_report,
        "parent_traces": traces,
    }


def _assertion_block(summary: dict[str, Any] | None) -> dict[str, Any]:
    summary = summary or {}
    denominator = summary.get("denominator")
    passed = summary.get("pass")
    failed = summary.get("fail")
    return {
        "checker_id": summary.get("checker_id"),
        "denominator": denominator,
        "pass": passed,
        "fail": failed,
        "not_applicable": summary.get("not_applicable"),
        "excluded_from_denominator": list(summary.get("excluded_from_denominator") or []),
        "fail_ids": list(summary.get("fail_ids") or []),
        "pass_ids": list(summary.get("pass_ids") or []),
        "percent": _rate(passed, denominator),
    }


def _parent_trace_map(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row.get("scenario_id"): row
        for row in bundle.get("parent_traces") or []
        if isinstance(row, dict) and row.get("scenario_id")
    }


def _s19_call_count(trace: dict[str, Any] | None) -> int | None:
    if not trace:
        return None
    return count_preview_classification_search_calls(trace.get("events"))


def _f1_candidate_s19_calls(f1_assertions: dict[str, Any]) -> dict[str, Any]:
    for row in f1_assertions.get("per_trace") or []:
        if row.get("scenario_id") != S19_SCENARIO_ID:
            continue
        assertion = (row.get("assertions") or {}).get(S19_BUDGET_CHECKER_ID) or {}
        evidence = assertion.get("evidence") or {}
        return {
            "scenario_id": S19_SCENARIO_ID,
            "result": assertion.get("result"),
            "search_call_events": evidence.get("search_call_events"),
            "incidental": True,
            "experiment": CANDIDATE_BASELINE_ID,
            "note": (
                "Incidental result from the separate, unsuccessful F1 prompt "
                "experiment. It is not a timing-repair outcome."
            ),
        }
    return {
        "scenario_id": S19_SCENARIO_ID,
        "result": None,
        "search_call_events": None,
        "incidental": True,
        "experiment": CANDIDATE_BASELINE_ID,
        "note": "F1 candidate S19 assertion row was not found.",
    }


def _timing_from_historical(bundle: dict[str, Any]) -> dict[str, Any]:
    baseline = bundle.get("baseline_results") or {}
    timing_report = bundle.get("timing_report") or {}
    raw = _assertion_block(
        (baseline.get("deterministic_assertions") or {}).get(DEFERRED_DATE_CHECKER_ID)
    )
    unchanged = timing_report.get("unchanged_check") or {}
    delivered = _assertion_block(
        (unchanged.get("delivered_after") or {}).get(DEFERRED_DATE_CHECKER_ID)
    )
    retrieval = _assertion_block(
        (unchanged.get("delivered_after") or {}).get(S19_BUDGET_CHECKER_ID)
        or (baseline.get("deterministic_assertions") or {}).get(S19_BUDGET_CHECKER_ID)
    )
    return {
        "title": TIMING_TITLE,
        "description": REPLAY_DESCRIPTION,
        "label": timing_report.get("label_replay") or REPLAY_LABEL,
        "checker_id": DEFERRED_DATE_CHECKER_ID,
        "checker_suite": CHECKER_SUITE_ID,
        "formatter_id": (
            (timing_report.get("repair") or {}).get("formatter_id") or FORMATTER_ID
        ),
        "formatter_version": (
            (timing_report.get("repair") or {}).get("formatter_version")
            or FORMATTER_VERSION
        ),
        "unchanged_assertion_id": S19_BUDGET_CHECKER_ID,
        "raw": raw,
        "delivered": delivered,
        "change_pp": _change_pp(raw.get("percent"), delivered.get("percent")),
        "retrieval_after_repair": retrieval,
    }


def _timing_from_replay(replay: dict[str, Any]) -> dict[str, Any]:
    assertions = replay.get("deterministic_assertions") or {}
    raw = _assertion_block((assertions.get("raw") or {}).get(DEFERRED_DATE_CHECKER_ID))
    delivered = _assertion_block(
        (assertions.get("delivered") or {}).get(DEFERRED_DATE_CHECKER_ID)
    )
    retrieval = _assertion_block(
        (assertions.get("delivered") or {}).get(S19_BUDGET_CHECKER_ID)
    )
    return {
        "title": TIMING_TITLE,
        "description": REPLAY_DESCRIPTION,
        "label": replay.get("label") or REPLAY_LABEL,
        "checker_id": DEFERRED_DATE_CHECKER_ID,
        "checker_suite": CHECKER_SUITE_ID,
        "formatter_id": replay.get("formatter_id") or FORMATTER_ID,
        "formatter_version": replay.get("formatter_version") or FORMATTER_VERSION,
        "unchanged_assertion_id": S19_BUDGET_CHECKER_ID,
        "raw": raw,
        "delivered": delivered,
        "change_pp": _change_pp(raw.get("percent"), delivered.get("percent")),
        "retrieval_after_repair": retrieval,
        "repair_status_counts": replay.get("repair_status_counts"),
        "prefix_mismatches": replay.get("prefix_mismatches") or [],
    }


def _f1_finding(bundle: dict[str, Any]) -> dict[str, Any]:
    annotations_f1 = bundle.get("annotations_f1") or {}
    comparison = annotations_f1.get("comparison_to_parent_f1") or {}
    review = annotations_f1.get("review") or {}
    n_traces = comparison.get("n_traces") or len(annotations_f1.get("traces") or [])
    parent_fail = comparison.get("parent_f1_failure_count")
    candidate_fail = comparison.get("candidate_f1_failure_count")
    return {
        "title": "F1 prompt experiment — unsuccessful",
        "parent_baseline_id": annotations_f1.get("parent_baseline_id")
        or PARENT_BASELINE_ID,
        "candidate_baseline_id": annotations_f1.get("baseline_id")
        or CANDIDATE_BASELINE_ID,
        "category_scope": list(annotations_f1.get("category_scope") or ["F1"]),
        "n_traces": n_traces,
        "parent_fail_count": parent_fail,
        "candidate_fail_count": candidate_fail,
        "parent_fail_ids": list(comparison.get("parent_fail_ids") or []),
        "candidate_fail_ids": list(comparison.get("candidate_fail_ids") or []),
        "recoveries": list(comparison.get("recoveries") or []),
        "regressions": list(comparison.get("regressions") or []),
        "persistent_failures": list(comparison.get("persistent_failures") or []),
        "candidate_adopted": False,
        "parent_instructions_restored": True,
        "candidate_f2_reviewed": False,
        "resolves_f1": False,
        "review": review,
        "note": comparison.get("note")
        or (
            "Two F1 recoveries, two regressions, three persistent failures. "
            "5/20 F1 failures in both versions."
        ),
    }


def _retrieval_finding(bundle: dict[str, Any]) -> dict[str, Any]:
    traces = _parent_trace_map(bundle)
    parent_s19 = traces.get(S19_SCENARIO_ID)
    baseline = bundle.get("baseline_results") or {}
    raw_s19 = _assertion_block(
        (baseline.get("deterministic_assertions") or {}).get(S19_BUDGET_CHECKER_ID)
    )
    timing_report = bundle.get("timing_report") or {}
    after = _assertion_block(
        ((timing_report.get("unchanged_check") or {}).get("delivered_after") or {}).get(
            S19_BUDGET_CHECKER_ID
        )
    )
    return {
        "title": "Retrieval regression check",
        "checker_id": S19_BUDGET_CHECKER_ID,
        "scenario_id": S19_SCENARIO_ID,
        "budget": MAX_S19_SEARCH_CALLS,
        "parent_search_call_events": _s19_call_count(parent_s19),
        "denominator": raw_s19.get("denominator"),
        "excluded": raw_s19.get("not_applicable")
        if raw_s19.get("not_applicable") is not None
        else len(raw_s19.get("excluded_from_denominator") or []),
        "parent": raw_s19,
        "after_timing_repair": after,
        "timing_repair_changes_retrieval": False,
        "f1_candidate_s19": _f1_candidate_s19_calls(bundle.get("f1_assertions") or {}),
    }


def _taxonomy_finding(bundle: dict[str, Any]) -> dict[str, Any]:
    taxonomy = bundle.get("taxonomy") or {}
    annotations = bundle.get("annotations") or {}
    fail_ids = annotations.get("category_fail_ids") or {}
    categories = []
    for item in taxonomy.get("categories") or []:
        category_id = item.get("id")
        ids = list(fail_ids.get(category_id) or [])
        categories.append(
            {
                "id": category_id,
                "title": item.get("title"),
                "priority_weight": item.get("priority_weight"),
                "fail_count": len(ids),
                "fail_ids": ids,
            }
        )
    return {
        "taxonomy_id": taxonomy.get("taxonomy_id"),
        "first_improvement_target": taxonomy.get("first_improvement_target"),
        "priority_note": taxonomy.get("priority_note"),
        "counting_rule": taxonomy.get("counting_rule"),
        "review": taxonomy.get("review") or annotations.get("review") or {},
        "categories": categories,
        "n_traces": len(annotations.get("traces") or []),
    }


def _prediction_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("predictions"), list):
        return [row for row in payload["predictions"] if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _count_rate(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator == 0:
        return {
            "numerator": numerator,
            "denominator": 0,
            "percent": None,
            "label": "undefined",
        }
    percent = 100.0 * numerator / denominator
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": percent,
        "label": f"{numerator}/{denominator} ({percent:.0f}%)",
    }


def confusion_matrix_from_metrics(metrics: Mapping[str, int]) -> dict[str, Any]:
    """Rows are reviewed labels; columns are judge outputs. Failure is positive."""
    return {
        "row_labels": ["Reviewed F1 failure", "Reviewed F1 pass"],
        "column_labels": ["Judge fail", "Judge pass"],
        "cells": [
            [metrics.get("TP", 0), metrics.get("FN", 0)],
            [metrics.get("FP", 0), metrics.get("TN", 0)],
        ],
        "positive_class": "fail",
        "orientation": "rows=reviewed, columns=judge",
    }


def _metrics_from_saved_report(saved: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(saved, dict):
        return None
    if "TP" in saved:
        return saved
    nested = saved.get("metrics")
    if isinstance(nested, dict) and "TP" in nested:
        return nested
    return None


def _metrics_agree(derived: Mapping[str, Any], saved: Mapping[str, Any] | None) -> bool:
    if not saved:
        return False
    for key in ("TP", "FN", "TN", "FP"):
        if derived.get(key) != saved.get(key):
            return False
    return True


def _false_negative_rows(
    score: Mapping[str, Any],
    labels: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in score.get("false_negatives") or []:
        evaluation_id = str(item.get("evaluation_id") or "")
        label_row = labels.get(evaluation_id) or {}
        excerpt = item.get("excerpt") or ""
        if not excerpt:
            answer = str(item.get("answer") or "")
            excerpt = answer[:280] + ("…" if len(answer) > 280 else "")
        rows.append(
            {
                "evaluation_id": evaluation_id,
                "scenario_id": item.get("scenario_id") or label_row.get("scenario_id"),
                "case_id": label_row.get("case_id"),
                "baseline_id": label_row.get("baseline_id"),
                "run_id": label_row.get("run_id"),
                "input": item.get("input") or "",
                "answer_excerpt": excerpt,
                "reviewed_label": item.get("reviewed_label"),
                "judge_verdict": item.get("judge_verdict"),
                "judge_reason": item.get("reason"),
            }
        )
    return rows


def _version_block(
    *,
    version: str,
    score: Mapping[str, Any],
    labels: Mapping[str, Mapping[str, Any]],
    saved_metrics: Mapping[str, Any] | None,
    report_path: str,
) -> dict[str, Any]:
    metrics = score["metrics"]
    expected = score.get("expected_n") or 0
    valid = score.get("valid_n") or 0
    invalid = score.get("invalid_n") or 0
    missing = score.get("missing_n") or 0
    agrees = _metrics_agree(metrics, saved_metrics)
    return {
        "version": version,
        "TP": metrics["TP"],
        "FN": metrics["FN"],
        "TN": metrics["TN"],
        "FP": metrics["FP"],
        "TPR": _count_rate(metrics["TP"], metrics["positives_in_metrics"]),
        "TNR": _count_rate(metrics["TN"], metrics["negatives_in_metrics"]),
        "coverage": _count_rate(valid, expected),
        "valid_n": valid,
        "invalid_n": invalid,
        "missing_n": missing,
        "attempted_n": valid + invalid,
        "expected_n": expected,
        "valid_response_only": bool(score.get("valid_response_only")),
        "confusion_matrix": confusion_matrix_from_metrics(metrics),
        "false_negatives": _false_negative_rows(score, labels),
        "false_positives": [
            {
                "evaluation_id": item.get("evaluation_id"),
                "scenario_id": item.get("scenario_id"),
                "reviewed_label": item.get("reviewed_label"),
                "judge_verdict": item.get("judge_verdict"),
                "judge_reason": item.get("reason"),
                "answer_excerpt": item.get("excerpt") or "",
            }
            for item in score.get("false_positives") or []
        ],
        "agrees_with_saved_report": agrees,
        "saved_report_path": report_path,
        "not_overall_success": True,
    }


def _group_labels(
    manifest: Mapping[str, Any], group: str
) -> dict[str, dict[str, Any]]:
    rows = [
        dict(row)
        for row in manifest.get("cases") or []
        if row.get("group") == group
    ]
    return association_map(rows)


def load_judge_view(
    project_dir: Path | None = None,
    *,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Derive judge metrics from saved predictions and reviewed labels."""
    root = Path(project_dir) if project_dir else PROJECT_DIR
    errors = errors if errors is not None else []
    paths = {key: root / rel for key, rel in JUDGE_PATHS.items()}
    missing = [key for key, path in paths.items() if not path.is_file()]
    if missing:
        for key in missing:
            errors.append(_file_error(key, paths[key], "File is missing."))
        return {
            "ok": False,
            "errors": errors,
            "default_split": "validation",
            "decision": JUDGE_DECISION,
            "mixed_headline": False,
        }

    manifest = _read_json(paths["golden_manifest"])
    split = _read_json(paths["golden_split"])
    v1_cal_pred = _prediction_rows(_read_json(paths["v1_calibration_predictions"]))
    v2_cal_pred = _prediction_rows(_read_json(paths["v2_calibration_predictions"]))
    v1_val_pred = _prediction_rows(_read_json(paths["validation_v1_predictions"]))
    v2_val_pred = _prediction_rows(_read_json(paths["validation_v2_predictions"]))
    v1_cal_report = _read_json(paths["v1_calibration_report"])
    v2_cal_report = _read_json(paths["v2_calibration_report"])
    validation_report = _read_json(paths["validation_report"])
    provenance_file = _read_json(paths["v2_provenance"])

    cal_ids = {
        str(row["evaluation_id"])
        for row in manifest.get("cases") or []
        if row.get("group") == "calibration"
    }
    val_ids = {
        str(row["evaluation_id"])
        for row in manifest.get("cases") or []
        if row.get("group") == "validation"
    }
    try:
        payloads = load_jsonl_by_id(paths["payloads"], cal_ids | val_ids)
    except Exception as exc:
        errors.append(_file_error("payloads", paths["payloads"], str(exc)))
        return {
            "ok": False,
            "errors": errors,
            "default_split": "validation",
            "decision": JUDGE_DECISION,
            "mixed_headline": False,
        }

    cal_labels = _group_labels(manifest, "calibration")
    val_labels = _group_labels(manifest, "validation")
    v1_cal = score_predictions(v1_cal_pred, cal_labels, payloads)
    v2_cal = score_predictions(v2_cal_pred, cal_labels, payloads)
    v1_val = score_predictions(v1_val_pred, val_labels, payloads)
    v2_val = score_predictions(v2_val_pred, val_labels, payloads)

    v1_cal_block = _version_block(
        version="v1",
        score=v1_cal,
        labels=cal_labels,
        saved_metrics=_metrics_from_saved_report(v1_cal_report.get("score")),
        report_path=str(paths["v1_calibration_report"]),
    )
    v2_cal_block = _version_block(
        version="v2",
        score=v2_cal,
        labels=cal_labels,
        saved_metrics=_metrics_from_saved_report(v2_cal_report.get("score")),
        report_path=str(paths["v2_calibration_report"]),
    )
    v1_val_block = _version_block(
        version="v1",
        score=v1_val,
        labels=val_labels,
        saved_metrics=_metrics_from_saved_report(
            (validation_report.get("v1") or {}).get("score")
        ),
        report_path=str(paths["validation_report"]),
    )
    v2_val_block = _version_block(
        version="v2",
        score=v2_val,
        labels=val_labels,
        saved_metrics=_metrics_from_saved_report(
            (validation_report.get("v2") or {}).get("score")
        ),
        report_path=str(paths["validation_report"]),
    )
    for block in (v1_cal_block, v2_cal_block, v1_val_block, v2_val_block):
        if not block["agrees_with_saved_report"]:
            errors.append(
                {
                    "code": "judge_report_mismatch",
                    "label": f"judge_{block['version']}",
                    "path": block["saved_report_path"],
                    "detail": "Derived judge metrics do not match the saved report.",
                }
            )

    cal_v1_tpr = v1_cal_block["TPR"]["percent"]
    cal_v2_tpr = v2_cal_block["TPR"]["percent"]
    val_v1_tpr = v1_val_block["TPR"]["percent"]
    val_v2_tpr = v2_val_block["TPR"]["percent"]
    cal_improved = (
        cal_v2_tpr is not None
        and cal_v1_tpr is not None
        and cal_v2_tpr > cal_v1_tpr
    )
    val_improved = (
        val_v2_tpr is not None
        and val_v1_tpr is not None
        and val_v2_tpr > val_v1_tpr
    )
    examples_reused = bool(
        v2_cal_report.get("examples_reused_calibration_cases")
        or provenance_file.get("example_source_split") == "calibration"
    )
    validation_fails = sum(
        1
        for row in manifest.get("cases") or []
        if row.get("group") == "validation" and row.get("f1") == "fail"
    )
    both_missed = (
        v1_val_block["TP"] == 0
        and v2_val_block["TP"] == 0
        and v1_val_block["FN"] == validation_fails
        and v2_val_block["FN"] == validation_fails
        and validation_fails > 0
    )
    decision = (
        JUDGE_DECISION
        if both_missed
        else (
            "Validation did not miss every reviewed failure. "
            "Keep both versions outside detection, approval, and release gates."
        )
    )
    cal_ids_set = set(split.get("calibration_scenario_ids") or [])
    val_ids_set = set(split.get("validation_scenario_ids") or [])
    return {
        "ok": not errors,
        "errors": errors,
        "default_split": "validation",
        "decision": decision,
        "both_missed_every_validation_failure": both_missed,
        "outside_detection_approval_and_release_gates": True,
        "mixed_headline": False,
        "tnr_is_not_overall_success": True,
        "agreement_is_not_a_success_headline": True,
        "validation": {"v1": v1_val_block, "v2": v2_val_block},
        "calibration": {
            "v1": v1_cal_block,
            "v2": v2_cal_block,
            "v2_examples_reused_calibration_cases": examples_reused,
            "calibration_improvement_transferred_to_validation": (
                cal_improved and val_improved
            ),
        },
        "provenance": {
            "n_outputs": manifest.get("n_cases"),
            "n_paired_scenarios": (manifest.get("provenance") or {}).get(
                "n_paired_scenarios"
            )
            or manifest.get("n_scenarios"),
            "kind": (manifest.get("provenance") or {}).get("kind"),
            "f1_fail": (manifest.get("labels") or {}).get("f1_fail"),
            "f1_pass": (manifest.get("labels") or {}).get("f1_pass"),
            "calibration_groups": len(cal_ids_set),
            "calibration_outputs": split.get("calibration_n_outputs"),
            "validation_groups": len(val_ids_set),
            "validation_outputs": split.get("validation_n_outputs"),
            "overlap": sorted(cal_ids_set & val_ids_set),
            "labels": (manifest.get("provenance") or {}).get("labels"),
            "same_model_family": True,
            "held_out_from_refinement": True,
            "unseen_capstone_scenarios": False,
            "payloads_gitignored": True,
            "payloads_path": str(paths["payloads"]),
        },
        "invoked_judge": False,
    }


def _human_labels_for(
    bundle: dict[str, Any], scenario_id: str
) -> dict[str, Any]:
    parent = {}
    for row in (bundle.get("annotations") or {}).get("traces") or []:
        if row.get("scenario_id") == scenario_id:
            parent = {
                "run_id": row.get("run_id"),
                "categories": dict(row.get("categories") or {}),
                "overall": row.get("overall"),
            }
            break
    candidate = {}
    for row in (bundle.get("annotations_f1") or {}).get("traces") or []:
        if row.get("scenario_id") == scenario_id:
            candidate = {
                "run_id": row.get("run_id"),
                "categories": dict(row.get("categories") or {}),
            }
            break
    return {"parent": parent, "f1_candidate": candidate}


def _article_113_evidence(trace: dict[str, Any] | None) -> dict[str, Any] | None:
    if not trace:
        return None
    records = records_from_events(trace.get("events"))
    for item in records:
        if item.get("record_id") == EXPECTED_ARTICLE_113_RECORD_ID or str(
            item.get("label") or ""
        ).startswith("Article 113"):
            text = str(item.get("text") or "")
            return {
                "label": item.get("label"),
                "record_id": item.get("record_id"),
                "source_snapshot_id": item.get("source_snapshot_id"),
                "text_sha256": item.get("text_sha256") or sha256_text(text),
                "expected_text_sha256": EXPECTED_ARTICLE_113_TEXT_SHA256,
                "text": text,
            }
    return None


def _failure_reason(
    *,
    scenario_id: str,
    human: dict[str, Any],
    raw_assertions: dict[str, Any],
    delivered_assertions: dict[str, Any],
    taxonomy: dict[str, Any],
    repair: dict[str, Any],
) -> dict[str, Any]:
    titles = {
        item.get("id"): item.get("title")
        for item in (taxonomy.get("categories") or [])
    }
    human_fails = [
        {
            "category": key,
            "title": titles.get(key),
            "source": "human_reviewed_parent",
        }
        for key, value in (human.get("parent") or {}).get("categories", {}).items()
        if value == "fail"
    ]
    automated = []
    for checker_id, row in (raw_assertions or {}).items():
        if row.get("result") == "fail":
            automated.append(
                {
                    "checker_id": checker_id,
                    "layer": "raw_model_output",
                    "reasons": list(row.get("reasons") or []),
                }
            )
    delivered_fails = []
    for checker_id, row in (delivered_assertions or {}).items():
        if row.get("result") == "fail":
            delivered_fails.append(
                {
                    "checker_id": checker_id,
                    "layer": "delivered_output",
                    "reasons": list(row.get("reasons") or []),
                }
            )
    return {
        "scenario_id": scenario_id,
        "human_failures": human_fails,
        "raw_automated_failures": automated,
        "delivered_automated_failures": delivered_fails,
        "timing_repair_status": repair.get("status"),
        "timing_repair_reason": repair.get("reason"),
        "human_and_automated_are_separate": True,
    }


def scenario_detail(
    bundle: dict[str, Any],
    scenario_id: str | None = None,
    *,
    replay_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chosen = scenario_id or DEFAULT_SCENARIO_ID
    traces = _parent_trace_map(bundle)
    trace = traces.get(chosen)
    scenarios = {
        item.get("id"): item.get("input")
        for item in (bundle.get("scenarios") or {}).get("scenarios") or []
        if isinstance(item, dict)
    }
    if trace is None:
        return {
            "ok": False,
            "scenario_id": chosen,
            "error": f"Saved parent trace for {chosen} is not available.",
        }
    raw = trace.get("final_output") or ""
    if replay_row and replay_row.get("repair"):
        repair = replay_row["repair"]
    else:
        repair = apply_timing_repair(raw, records_from_events(trace.get("events"))).to_dict()
    raw_trace = {
        "scenario_id": chosen,
        "run_id": trace.get("run_id"),
        "final_output": raw,
        "events": trace.get("events") or [],
    }
    delivered_trace = {
        **raw_trace,
        "final_output": repair.get("delivered_output") or "",
    }
    raw_assertions = {
        key: value.to_dict()
        for key, value in run_deterministic_assertions(raw_trace).items()
    }
    delivered_assertions = {
        key: value.to_dict()
        for key, value in run_deterministic_assertions(delivered_trace).items()
    }
    human = _human_labels_for(bundle, chosen)
    return {
        "ok": True,
        "scenario_id": chosen,
        "parent_run_id": trace.get("run_id"),
        "input": scenarios.get(chosen) or trace.get("user_input") or "",
        "raw_output": raw,
        "delivered_output": repair.get("delivered_output") or "",
        "raw_is_model_text": True,
        "delivered_is_application_rendered": True,
        "repair": {
            "status": repair.get("status"),
            "reason": repair.get("reason"),
            "formatter_id": repair.get("formatter_id") or FORMATTER_ID,
            "formatter_version": repair.get("formatter_version") or FORMATTER_VERSION,
            "source_record_id": repair.get("source_record_id"),
            "source_text_sha256": repair.get("source_text_sha256"),
            "source_snapshot_id": repair.get("source_snapshot_id"),
        },
        "article_113": _article_113_evidence(trace),
        "human_labels": human,
        "automated_assertions": {
            "uses_human_labels": False,
            "raw": raw_assertions,
            "delivered": delivered_assertions,
        },
        "failure_reason": _failure_reason(
            scenario_id=chosen,
            human=human,
            raw_assertions=raw_assertions,
            delivered_assertions=delivered_assertions,
            taxonomy=bundle.get("taxonomy") or {},
            repair=repair,
        ),
    }


def build_view_model(
    bundle: dict[str, Any],
    *,
    recompute: dict[str, Any] | None = None,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    errors = list(bundle.get("errors") or [])
    if recompute and recompute.get("errors"):
        errors.extend(recompute["errors"])
    source = "recomputed" if recompute and recompute.get("ok") else "historical"
    timing = (
        _timing_from_replay(recompute["replay"])
        if source == "recomputed"
        else _timing_from_historical(bundle)
    )
    scenario_ids = [
        item.get("id")
        for item in (bundle.get("scenarios") or {}).get("scenarios") or []
        if isinstance(item, dict) and item.get("id")
    ]
    replay_row = None
    if source == "recomputed":
        replay_row = next(
            (
                item
                for item in (recompute.get("replay") or {}).get("per_trace") or []
                if item.get("scenario_id") == (scenario_id or DEFAULT_SCENARIO_ID)
            ),
            None,
        )
    model = {
        "ok": bundle.get("ok") and not (
            recompute and recompute.get("ok") is False
        ),
        "source": source,
        "errors": errors,
        "never_an_overall_quality_or_compliance_percentage": True,
        "candidate_f2_reviewed": False,
        "parent_baseline_id": PARENT_BASELINE_ID,
        "candidate_baseline_id": CANDIDATE_BASELINE_ID,
        "hashes": bundle.get("hashes") or {},
        "paths": bundle.get("paths") or {},
        "timing": timing,
        "f1": _f1_finding(bundle),
        "retrieval": _retrieval_finding(bundle),
        "taxonomy": _taxonomy_finding(bundle),
        "judge": (recompute or {}).get("judge")
        or load_judge_view(Path(bundle.get("project_dir") or PROJECT_DIR)),
        "scenario_ids": scenario_ids,
        "selected_scenario": scenario_id or DEFAULT_SCENARIO_ID,
        "scenario": scenario_detail(
            bundle, scenario_id or DEFAULT_SCENARIO_ID, replay_row=replay_row
        )
        if bundle.get("ok")
        else None,
        "recompute_output_path": (recompute or {}).get("output_path"),
        "recompute_computed_at": (recompute or {}).get("computed_at"),
        "review": (bundle.get("taxonomy") or {}).get("review")
        or (bundle.get("annotations") or {}).get("review")
        or {},
    }
    if errors:
        model["ok"] = False
    return model


def _compact_replay(replay: dict[str, Any]) -> dict[str, Any]:
    compact_traces = []
    for item in replay.get("per_trace") or []:
        repair = item.get("repair") or {}
        compact_traces.append(
            {
                "scenario_id": item.get("scenario_id"),
                "run_id": item.get("run_id"),
                "prefix_unchanged": item.get("prefix_unchanged"),
                "repair": {
                    "status": repair.get("status"),
                    "reason": repair.get("reason"),
                    "formatter_id": repair.get("formatter_id"),
                    "formatter_version": repair.get("formatter_version"),
                    "source_record_id": repair.get("source_record_id"),
                    "source_text_sha256": repair.get("source_text_sha256"),
                    "source_snapshot_id": repair.get("source_snapshot_id"),
                },
            }
        )
    return {
        "label": replay.get("label"),
        "not": replay.get("not"),
        "formatter_id": replay.get("formatter_id"),
        "formatter_version": replay.get("formatter_version"),
        "source": replay.get("source"),
        "repair_status_counts": replay.get("repair_status_counts"),
        "prefix_mismatches": replay.get("prefix_mismatches"),
        "deterministic_assertions": replay.get("deterministic_assertions"),
        "comparison_to_saved_baseline_assertions": replay.get(
            "comparison_to_saved_baseline_assertions"
        ),
        "raw_versus_saved_baseline": replay.get("raw_versus_saved_baseline"),
        "checker_file_sha256": replay.get("checker_file_sha256"),
        "per_trace": compact_traces,
    }


def run_offline_checks(
    project_dir: Path | None = None,
    *,
    write: bool = True,
) -> dict[str, Any]:
    """Rerun frozen assertions and the timing formatter on saved traces."""
    root = Path(project_dir) if project_dir else PROJECT_DIR
    bundle = load_historical_bundle(root)
    if not bundle.get("ok"):
        return {
            "ok": False,
            "source": "recomputed",
            "errors": bundle.get("errors") or [
                {
                    "code": "evaluation_error",
                    "label": "bundle",
                    "path": str(root),
                    "detail": "Historical bundle is not usable.",
                }
            ],
            "computed_at": utc_now(),
        }
    parent_path = Path(bundle["paths"]["parent_traces"])
    try:
        replay = replay_parent_traces(parent_path)
    except Exception as exc:
        return {
            "ok": False,
            "source": "recomputed",
            "errors": [
                {
                    "code": "evaluation_error",
                    "label": "replay",
                    "path": str(parent_path),
                    "detail": str(exc),
                }
            ],
            "computed_at": utc_now(),
        }
    raw_eval = evaluate_assertions_only(bundle["parent_traces"])
    payload = {
        "schema": "aeacus.week4.evaluations_recompute.v1",
        "result_kind": "freshly_recomputed",
        "not": [
            "new agent runs",
            "model or retrieval calls",
            "judge inference",
            "an overall quality or compliance percentage",
        ],
        "label": REPLAY_LABEL,
        "computed_at": utc_now(),
        "input_hashes": bundle.get("hashes") or {},
        "checker_suite": CHECKER_SUITE_ID,
        "checker_file_sha256": replay.get("checker_file_sha256"),
        "formatter_id": replay.get("formatter_id") or FORMATTER_ID,
        "formatter_version": replay.get("formatter_version") or FORMATTER_VERSION,
        "uses_human_labels": False,
        "human_labels_unchanged": True,
        "replay": _compact_replay(replay),
        "raw_assertions_from_saved_traces": raw_eval["deterministic_assertions"],
        "judge_metrics_from_saved_predictions": True,
        "invoked_judge": False,
    }
    output_path = None
    if write:
        out_dir = root / RECOMPUTE_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = payload["computed_at"].replace(":", "").replace("+00:00", "Z")
        output_path = out_dir / f"week4_evaluations_recompute_{stamp}.json"
        output_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        payload["output_path"] = str(output_path)
    return {
        "ok": True,
        "source": "recomputed",
        "errors": [],
        "computed_at": payload["computed_at"],
        "output_path": str(output_path) if output_path else None,
        "payload": payload,
        "replay": replay,
        "bundle": bundle,
        "judge": load_judge_view(root),
        "invoked_judge": False,
    }


def load_evaluations_view(
    project_dir: Path | None = None,
    *,
    scenario_id: str | None = None,
    recompute: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bundle = load_historical_bundle(project_dir)
    return build_view_model(bundle, recompute=recompute, scenario_id=scenario_id)
