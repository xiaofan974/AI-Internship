"""Create the Week 4 Langfuse F1 prompt comparison.

Resumes from the local ledger. Does not rewrite frozen artifacts, call a
model, retrieve, apply the timing formatter, or open the review register.
"""

from __future__ import annotations

import json

from aeacus_agent.trace_store import PROJECT_DIR
from evals.week4.langfuse_f1_comparison import run_comparison

REPORT_MD = PROJECT_DIR / "reports" / "week4_langfuse_f1_comparison.md"
REPORT_JSON = PROJECT_DIR / "reports" / "week4_langfuse_f1_comparison.json"


def _write_reports(payload: dict) -> None:
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    counts = payload.get("counts") or {}
    expected = payload.get("expected") or {}
    links = payload.get("links") or {}
    dataset = payload.get("dataset") or {}
    pilot = payload.get("pilot") or {}
    comparison = payload.get("comparison") or {}
    review = ((payload.get("review") or {}).get("candidate") or {})
    lines = [
        "# Week 4 Langfuse F1 prompt comparison",
        "",
        "Frozen F1 prompt experiment on the existing `week4_adk_preview_v1`",
        "dataset. Historical parent raw answers versus the rejected prompt",
        "candidate raw answers. This is not a timing repair, not 20 new live",
        "executions, and not an overall quality percentage.",
        "",
        "## Source",
        "",
        f"- Dataset: `{payload.get('dataset_name')}`",
        f"- Parent baseline: `{payload.get('parent_baseline_id')}`",
        f"- Candidate baseline: `{payload.get('candidate_baseline_id')}`",
        f"- Parent SHA-256: `{payload.get('parent_source_sha256')}`",
        f"- Candidate SHA-256: `{payload.get('candidate_source_sha256')}`",
        f"- Parent instruction: `{payload.get('parent_instruction_sha256')}`",
        f"- Candidate instruction: `{payload.get('candidate_instruction_sha256')}`",
        f"- Live instruction restored to parent: {payload.get('live_instruction_is_restored_parent')}",
        f"- Provenance ok: {payload.get('provenance_ok')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        "",
        "## Configuration",
        "",
    ]
    for name, status in (payload.get("config") or {}).items():
        lines.append(f"- `{name}`: {status}")
    lines.extend(
        [
            "",
            "## Comparison runs",
            "",
            f"- Parent: `{(payload.get('run_names') or {}).get('f1_parent')}`",
            f"- Candidate: `{(payload.get('run_names') or {}).get('f1_candidate')}`",
            f"- Dataset URL: {links.get('dataset') or dataset.get('url') or 'not created'}",
            f"- Parent run URL: {links.get('parent_run') or 'not created'}",
            f"- Candidate run URL: {links.get('candidate_run') or 'not created'}",
            f"- Comparison URL: {links.get('comparison') or 'not created'}",
            "- Timing formatter applied: False",
            f"- Model calls: {payload.get('model_calls')}",
            f"- Retrieval calls: {payload.get('retrieval_calls')}",
            f"- Hosted judges: {payload.get('hosted_judges')}",
            "",
            "## Reviewed F1 scores",
            "",
            f"- Score name: `{payload.get('score_name')}`. Encoding: 1=pass, 0=fail.",
            f"- Imported AI-assisted judgments accepted by {review.get('accepted_by')}.",
            f"- Not: {review.get('not')}.",
            f"- Parent fail IDs: {expected.get('parent_fail_ids')}.",
            f"- Candidate fail IDs: {expected.get('candidate_fail_ids')}.",
            f"- Recoveries: {comparison.get('recoveries')}.",
            f"- Regressions: {comparison.get('regressions')}.",
            f"- Persistent failures: {comparison.get('persistent_failures')}.",
            "- Both versions: 15/20 F1 pass, 5/20 F1 fail. These are not an overall quality percentage.",
            "- Candidate F2 labels were not assigned and were not scored.",
            "",
            "## Verified counts",
            "",
            f"- Prepared pairs: {counts.get('prepared')}",
            f"- Parent run items verified: {counts.get('parent_verified')}",
            f"- Candidate run items verified: {counts.get('candidate_verified')}",
            f"- Paired cases verified: {counts.get('paired_verified')}",
            f"- Failed: {counts.get('failed')}",
            "",
            "## Pilot paired case",
            "",
            f"- Scenario: {pilot.get('scenario_id')}",
            f"- Action: {pilot.get('action')}",
        ]
    )
    parent_pilot = pilot.get("parent") or {}
    candidate_pilot = pilot.get("candidate") or {}
    if parent_pilot or candidate_pilot:
        lines.extend(
            [
                f"- Parent trace: {parent_pilot.get('trace_url') or parent_pilot.get('trace_id')}",
                f"- Parent score: {parent_pilot.get('score_value')}",
                f"- Candidate trace: {candidate_pilot.get('trace_url') or candidate_pilot.get('trace_id')}",
                f"- Candidate score: {candidate_pilot.get('score_value')}",
            ]
        )
        parent_verified = parent_pilot.get("verified") or {}
        candidate_verified = candidate_pilot.get("verified") or {}
        if parent_verified:
            lines.append(
                f"- Parent ingestion delay seconds: {parent_verified.get('ingestion_delay_seconds')}"
            )
        if candidate_verified:
            lines.append(
                f"- Candidate ingestion delay seconds: {candidate_verified.get('ingestion_delay_seconds')}"
            )
    read_back = payload.get("read_back") or {}
    lines.extend(
        [
            "",
            "## Remote read-back",
            "",
            f"- Dataset items: {read_back.get('item_count')}",
            f"- Parent run items: {read_back.get('parent_item_count')}",
            f"- Candidate run items: {read_back.get('candidate_item_count')}",
        ]
    )
    if read_back.get("error"):
        lines.append(f"- Read-back error: {read_back.get('error')}")
    lines.extend(["", "## Per-trace links", ""])
    for item in payload.get("per_trace") or []:
        lines.append(
            f"- {item.get('scenario_id')}: parent {item.get('parent_trace_url')} "
            f"({item.get('parent_score')}); candidate {item.get('candidate_trace_url')} "
            f"({item.get('candidate_score')})"
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
            "- Outputs are the original saved raw answers. The timing formatter was not applied.",
            "- Scores are imported reviewed F1 judgments, not newly generated labels.",
            "- This is not independent expert legal adjudication.",
            "- Candidate F2 was not labelled or scored. No overall quality percentage is reported.",
            "- Existing timing comparison runs and historical source traces were not rewritten.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    prepared = run_comparison(live=False)
    print(f"prepared pairs: {(prepared.get('counts') or {}).get('prepared')}")
    print(f"provenance ok: {prepared.get('provenance_ok')}")
    if prepared.get("error") == "provenance_mismatch":
        print(prepared.get("discrepancy"))
        _write_reports(prepared)
        return 1
    if prepared.get("missing_credentials"):
        print("Live comparison skipped. Missing: " + ", ".join(prepared["missing_credentials"]))
        _write_reports(prepared)
        return 2
    result = run_comparison(live=True)
    print(f"parent_verified: {(result.get('counts') or {}).get('parent_verified')}")
    print(f"candidate_verified: {(result.get('counts') or {}).get('candidate_verified')}")
    print(f"paired_verified: {(result.get('counts') or {}).get('paired_verified')}")
    print(f"pilot: {result.get('pilot')}")
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
        and not result.get("error")
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
