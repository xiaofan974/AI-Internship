"""Import frozen week4_adk_preview_v1 traces into Langfuse.

Resumes from the local ledger. Does not rewrite frozen artifacts, call a
model, retrieve, or open the review register.
"""

from __future__ import annotations

import json

from aeacus_agent.trace_store import PROJECT_DIR
from evals.week4.langfuse_baseline_import import run_import

REPORT_MD = PROJECT_DIR / "reports" / "week4_langfuse_baseline_import.md"
REPORT_JSON = PROJECT_DIR / "reports" / "week4_langfuse_baseline_import.json"


def _write_reports(payload: dict) -> None:
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    counts = payload.get("counts") or {}
    expected = payload.get("expected") or {}
    review = payload.get("review") or {}
    links = payload.get("links") or []
    pilot = payload.get("pilot") or {}
    lines = [
        "# Week 4 Langfuse baseline import",
        "",
        "Historical import of frozen `week4_adk_preview_v1` only. No new model",
        "calls, retrieval, hosted evaluators, or review-register access.",
        "",
        "## Source",
        "",
        f"- Baseline: `{payload.get('baseline_id')}`",
        f"- Source SHA-256: `{payload.get('source_sha256')}`",
        f"- Source verified: {payload.get('source_sha256_verified')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Importer/ledger already present: {payload.get('importer_existed')}",
        "",
        "## Configuration",
        "",
    ]
    for name, status in (payload.get("config") or {}).items():
        lines.append(f"- `{name}`: {status}")
    if payload.get("missing_credentials"):
        lines.append(
            "- Missing: " + ", ".join(payload["missing_credentials"])
        )
    lines.extend(
        [
            "",
            "## Expected original scores",
            "",
            f"- Reviewed F1–F4 labels: imported AI-assisted judgments accepted by {review.get('accepted_by')}.",
            f"- Timing check: {expected.get('timing_pass')}/20 pass, {expected.get('timing_fail')} fail.",
            f"- S19 retrieval budget: {expected.get('s19_fail')} fail; {expected.get('s19_excluded')} excluded.",
            "- Score encoding: 1=pass, 0=fail. Reviewed and automated names are separate.",
            "",
            "## Verified counts",
            "",
            f"- Prepared: {counts.get('prepared')}",
            f"- Verified: {counts.get('verified')}",
            f"- Uploaded but not fully verified: {counts.get('uploaded_unverified')}",
            f"- Failed: {counts.get('failed')}",
            f"- Skipped already verified: {counts.get('skipped_verified')}",
            "",
            "## Pilot",
            "",
            f"- Scenario: {pilot.get('scenario_id')}",
            f"- Action: {pilot.get('action')}",
            f"- Trace: {pilot.get('trace_url') or pilot.get('trace_id')}",
        ]
    )
    verified = (pilot.get("verified") or {})
    if verified:
        lines.extend(
            [
                f"- Ingestion delay seconds: {verified.get('ingestion_delay_seconds')}",
                f"- Missing fields: {verified.get('missing_fields') or []}",
                f"- Missing observations: {verified.get('missing_observations') or []}",
                f"- Missing scores: {verified.get('missing_scores') or []}",
            ]
        )
    lines.extend(["", "## Langfuse links", ""])
    if not links:
        lines.append("No verified Langfuse links.")
    for item in links:
        lines.append(
            f"- {item.get('scenario_id')} ({item.get('status')}): {item.get('trace_url')}"
        )
    if payload.get("error"):
        lines.extend(["", "## Errors", "", str(payload.get("error"))])
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- Observation timestamps are import-time. Original run IDs and timestamps are provenance metadata only.",
            "- No per-event timestamps, model generations, or tool durations were invented.",
            "- Duplicate prevention uses deterministic trace/score IDs plus the local ledger.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    prepared = run_import(live=False)
    print(f"prepared jobs: {prepared['counts']['prepared']}")
    print(f"source sha256 verified: {prepared['source_sha256_verified']}")
    print(f"ledger existed: {prepared['importer_existed']}")
    print(f"config: {prepared['config']}")
    if prepared.get("missing_credentials"):
        print("Live import skipped. Missing: " + ", ".join(prepared["missing_credentials"]))
        _write_reports(prepared)
        return 2
    result = run_import(live=True)
    print(f"verified: {result['counts']['verified']}")
    print(f"uploaded_unverified: {result['counts']['uploaded_unverified']}")
    print(f"failed: {result['counts']['failed']}")
    print(f"pilot: {result.get('pilot')}")
    if result.get("error"):
        print(f"error: {result['error']}")
    _write_reports(result)
    print(f"wrote {REPORT_MD}")
    print(f"wrote {REPORT_JSON}")
    if result["counts"]["verified"] == 20 and not result.get("error"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
