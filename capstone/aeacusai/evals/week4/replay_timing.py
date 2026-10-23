"""Replay saved baseline traces through the timing formatter. No model calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aeacus_agent.timing_scope import (
    FORMATTER_ID,
    FORMATTER_VERSION,
    apply_timing_repair,
    prefix_outside_timing,
    records_from_events,
)
from aeacus_agent.trace_store import PROJECT_DIR, sha256_file
from evals.week4.checkers import DEFERRED_DATE_CHECKER_ID, S19_BUDGET_CHECKER_ID
from evals.week4.codify import EXPECTED_SOURCE_SHA256, load_traces
from evals.week4.evaluate_assertions import (
    compare_assertion_summaries,
    evaluate_assertions_only,
)

PARENT_TRACE = PROJECT_DIR / "data" / "local" / "traces" / "week4_adk_preview_v1.jsonl"
BASELINE_RESULTS = (
    PROJECT_DIR / "evals" / "week4" / "results" / "week4_codify_baseline_v1.json"
)
LABEL = "Application-layer replay of 20 saved live traces."


def replay_parent_traces(
    trace_path: Path | None = None,
    *,
    expected_sha256: str = EXPECTED_SOURCE_SHA256,
) -> dict[str, Any]:
    path = Path(trace_path) if trace_path else PARENT_TRACE
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise RuntimeError(
            "Refusing replay: parent trace hash mismatch. "
            f"expected={expected_sha256} observed={digest}"
        )
    traces = load_traces(path)
    replayed: list[dict[str, Any]] = []
    delivered_traces: list[dict[str, Any]] = []
    raw_traces: list[dict[str, Any]] = []
    prefix_mismatches: list[str] = []
    for row in traces:
        raw = row.get("final_output") or ""
        repair = apply_timing_repair(raw, records_from_events(row.get("events")))
        if prefix_outside_timing(repair.delivered_output) != prefix_outside_timing(raw):
            prefix_mismatches.append(row.get("scenario_id"))
        replayed.append(
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "repair": repair.to_dict(),
                "prefix_unchanged": row.get("scenario_id") not in prefix_mismatches,
            }
        )
        delivered_traces.append(
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "final_output": repair.delivered_output,
                "events": row.get("events") or [],
                "human_annotation": row.get("human_annotation"),
            }
        )
        raw_traces.append(
            {
                "scenario_id": row.get("scenario_id"),
                "run_id": row.get("run_id"),
                "final_output": raw,
                "events": row.get("events") or [],
                "human_annotation": row.get("human_annotation"),
            }
        )
    delivered_eval = evaluate_assertions_only(delivered_traces)
    raw_eval = evaluate_assertions_only(raw_traces)
    baseline = json.loads(BASELINE_RESULTS.read_text(encoding="utf-8"))
    return {
        "label": LABEL,
        "not": [
            "20 new live runs",
            "a model-quality improvement",
        ],
        "formatter_id": FORMATTER_ID,
        "formatter_version": FORMATTER_VERSION,
        "source": {
            "path": str(path),
            "sha256": digest,
            "n_traces": len(traces),
        },
        "prefix_unchanged_ids": [
            item["scenario_id"]
            for item in replayed
            if item["prefix_unchanged"]
        ],
        "prefix_mismatches": prefix_mismatches,
        "repair_status_counts": {
            "ok": sum(1 for item in replayed if item["repair"]["status"] == "ok"),
            "failed": sum(1 for item in replayed if item["repair"]["status"] == "failed"),
        },
        "per_trace": replayed,
        "deterministic_assertions": {
            "raw": raw_eval["deterministic_assertions"],
            "delivered": delivered_eval["deterministic_assertions"],
        },
        "comparison_to_saved_baseline_assertions": compare_assertion_summaries(
            baseline["deterministic_assertions"],
            delivered_eval["deterministic_assertions"],
        ),
        "raw_versus_saved_baseline": compare_assertion_summaries(
            baseline["deterministic_assertions"],
            raw_eval["deterministic_assertions"],
        ),
        "checker_file_sha256": hashlib.sha256(
            (PROJECT_DIR / "evals" / "week4" / "checkers.py").read_bytes()
        ).hexdigest(),
    }
