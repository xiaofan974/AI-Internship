"""Create the Week 4 Langfuse dataset and timing-repair comparison.

Resumes from the local ledger. Does not rewrite frozen artifacts, call a
model, retrieve, or open the review register.
"""

from __future__ import annotations

import json

from aeacus_agent.trace_store import PROJECT_DIR
from evals.week4.langfuse_timing_comparison import run_comparison

REPORT_MD = PROJECT_DIR / "reports" / "week4_langfuse_timing_comparison.md"
REPORT_JSON = PROJECT_DIR / "reports" / "week4_langfuse_timing_comparison.json"


def _write_reports(payload: dict) -> None:
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    counts = payload.get("counts") or {}
    expected = payload.get("expected") or {}
    raw_expected = expected.get("raw") or {}
    delivered_expected = expected.get("delivered") or {}
    links = payload.get("links") or {}
    dataset = payload.get("dataset") or {}
    pilot = payload.get("pilot") or {}
    generation = payload.get("delivered_generation") or {}
    lines = [
        "# Week 4 Langfuse timing-repair comparison",
        "",
        "Source-linked dataset for frozen `week4_adk_preview_v1`, compared as",
        "historical raw model answers versus a fresh application-layer timing",
        "repair. This is not improved model reasoning and not 20 new live",
        "agent executions.",
        "",
        "## Source",
        "",
        f"- Baseline: `{payload.get('baseline_id')}`",
        f"- Dataset: `{payload.get('dataset_name')}` (`{payload.get('dataset_version')}`)",
        f"- Source SHA-256: `{payload.get('source_sha256')}`",
        f"- Source verified: {payload.get('source_sha256_verified')}",
        f"- Provenance ok: {payload.get('provenance_ok')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Historical import ledger: `{payload.get('import_ledger')}`",
        "",
        "## Configuration",
        "",
    ]
    for name, status in (payload.get("config") or {}).items():
        lines.append(f"- `{name}`: {status}")
    if payload.get("missing_credentials"):
        lines.append("- Missing: " + ", ".join(payload["missing_credentials"]))
    lines.extend(
        [
            "",
            "## Dataset",
            "",
            "- One item per TRACE-S01–S20.",
            "- Each item is linked to its verified historical Langfuse source trace.",
            "- Task input is the scenario only. Reviewed F1–F4 labels stay in metadata.",
            "- The original model answer is not stored as a gold-standard expected output.",
            f"- Dataset id: `{dataset.get('id')}`",
            f"- Dataset URL: {links.get('dataset') or dataset.get('url') or 'not created'}",
            "",
            "## Comparison runs",
            "",
            f"- Historical raw: `{(payload.get('run_names') or {}).get('historical_raw')}`",
            f"- Timing repair: `{(payload.get('run_names') or {}).get('timing_repair')}`",
            f"- Delivered outputs: {generation.get('label')}",
            f"- Formatter: `{generation.get('formatter_id')}` v{generation.get('formatter_version')}",
            f"- Model calls: {generation.get('model_calls')}",
            f"- Retrieval calls: {generation.get('retrieval_calls')}",
            f"- Hosted judges: {generation.get('hosted_judges')}",
            f"- Raw run URL: {links.get('historical_raw_run') or 'not created'}",
            f"- Repair run URL: {links.get('timing_repair_run') or 'not created'}",
            f"- Comparison URL: {links.get('comparison') or 'not created'}",
            "",
            "## Scores",
            "",
            f"- Checker: `{payload.get('score_name')}` unchanged.",
            "- Encoding: 1=pass, 0=fail.",
            f"- Expected raw: {raw_expected.get('pass')}/20 pass; fail {raw_expected.get('fail_ids')}.",
            f"- Expected delivered: {delivered_expected.get('pass')}/20 pass; fail {delivered_expected.get('fail_ids')}.",
            f"- Recomputed raw: {(payload.get('raw_summary') or {}).get('pass')}/20; fail {(payload.get('raw_summary') or {}).get('fail_ids')}.",
            f"- Recomputed delivered: {(payload.get('delivered_summary') or {}).get('pass')}/20; fail {(payload.get('delivered_summary') or {}).get('fail_ids')}.",
            "- Delivered-output scores are written only on comparison-run traces, not on the original raw source traces.",
            "",
            "## Verified counts",
            "",
            f"- Prepared pairs: {counts.get('prepared')}",
            f"- Dataset items verified: {counts.get('items_verified')}",
            f"- Historical raw run items verified: {counts.get('raw_verified')}",
            f"- Timing-repair run items verified: {counts.get('delivered_verified')}",
            f"- Paired cases verified: {counts.get('paired_verified')}",
            f"- Failed: {counts.get('failed')}",
            "",
            "## Pilot paired case",
            "",
            f"- Scenario: {pilot.get('scenario_id')}",
            f"- Action: {pilot.get('action')}",
        ]
    )
    raw_pilot = pilot.get("raw") or {}
    delivered_pilot = pilot.get("delivered") or {}
    if raw_pilot or delivered_pilot:
        lines.extend(
            [
                f"- Raw trace: {raw_pilot.get('trace_url') or raw_pilot.get('trace_id')}",
                f"- Raw score: {raw_pilot.get('score_value')}",
                f"- Delivered trace: {delivered_pilot.get('trace_url') or delivered_pilot.get('trace_id')}",
                f"- Delivered score: {delivered_pilot.get('score_value')}",
            ]
        )
        raw_verified = raw_pilot.get("verified") or {}
        delivered_verified = delivered_pilot.get("verified") or {}
        if raw_verified:
            lines.append(
                f"- Raw ingestion delay seconds: {raw_verified.get('ingestion_delay_seconds')}"
            )
        if delivered_verified:
            lines.append(
                f"- Delivered ingestion delay seconds: {delivered_verified.get('ingestion_delay_seconds')}"
            )
    read_back = payload.get("read_back") or {}
    lines.extend(
        [
            "",
            "## Remote read-back",
            "",
            f"- Dataset items: {read_back.get('item_count')}",
            f"- Historical raw run items: {read_back.get('raw_item_count')}",
            f"- Timing-repair run items: {read_back.get('delivered_item_count')}",
        ]
    )
    if read_back.get("error"):
        lines.append(f"- Read-back error: {read_back.get('error')}")
    lines.extend(["", "## Per-trace links", ""])
    for item in payload.get("per_trace") or []:
        lines.append(
            f"- {item.get('scenario_id')}: source {item.get('source_trace_url')}; "
            f"raw {item.get('raw_trace_url')} ({item.get('raw_score')}); "
            f"delivered {item.get('delivered_trace_url')} ({item.get('delivered_score')})"
        )
    if payload.get("error"):
        lines.extend(["", "## Errors", "", str(payload.get("error"))])
        if payload.get("discrepancy"):
            lines.append(str(payload.get("discrepancy")))
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Delivered outputs were regenerated with the deterministic Timing and scope formatter from the original saved observations.",
            "- This comparison is an application-layer repair, not a claim that the model reasoned better.",
            "- No new inference, retrieval, hosted judges, or review-register access.",
            "- Duplicate prevention uses stable dataset item IDs, named experiment runs, and the local ledger.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    prepared = run_comparison(live=False)
    print(f"prepared pairs: {(prepared.get('counts') or {}).get('prepared')}")
    print(f"source sha256 verified: {prepared.get('source_sha256_verified')}")
    print(f"provenance ok: {prepared.get('provenance_ok')}")
    print(f"config: {prepared.get('config')}")
    if prepared.get("error") == "provenance_mismatch":
        print(f"error: {prepared['error']}")
        print(prepared.get("discrepancy"))
        _write_reports(prepared)
        return 1
    if prepared.get("missing_credentials"):
        print("Live comparison skipped. Missing: " + ", ".join(prepared["missing_credentials"]))
        _write_reports(prepared)
        return 2
    result = run_comparison(live=True)
    print(f"items_verified: {(result.get('counts') or {}).get('items_verified')}")
    print(f"raw_verified: {(result.get('counts') or {}).get('raw_verified')}")
    print(f"delivered_verified: {(result.get('counts') or {}).get('delivered_verified')}")
    print(f"paired_verified: {(result.get('counts') or {}).get('paired_verified')}")
    print(f"pilot: {result.get('pilot')}")
    print(f"dataset: {(result.get('links') or {}).get('dataset')}")
    print(f"comparison: {(result.get('links') or {}).get('comparison')}")
    if result.get("error"):
        print(f"error: {result['error']}")
    _write_reports(result)
    print(f"wrote {REPORT_MD}")
    print(f"wrote {REPORT_JSON}")
    counts = result.get("counts") or {}
    if (
        result.get("provenance_ok")
        and counts.get("paired_verified") == 20
        and counts.get("raw_verified") == 20
        and counts.get("delivered_verified") == 20
        and not result.get("error")
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
