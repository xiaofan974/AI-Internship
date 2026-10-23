"""Import the frozen F1 golden split and saved judge predictions into Langfuse.

Resumes from the local ledger. Does not rewrite frozen artifacts, rerun or
refine either judge, retrieve, or open the review register.
"""

from __future__ import annotations

import json

from aeacus_agent.trace_store import PROJECT_DIR
from evals.week4.langfuse_judge_import import run_import

REPORT_MD = PROJECT_DIR / "reports" / "week4_langfuse_judge_import.md"
REPORT_JSON = PROJECT_DIR / "reports" / "week4_langfuse_judge_import.json"


def _matrix_lines(title: str, block: dict) -> list[str]:
    return [
        f"### {title}",
        "",
        "Positive class is F1 failure.",
        "",
        f"- TP = reviewed fail / judge fail: {block.get('TP')}",
        f"- FN = reviewed fail / judge pass: {block.get('FN')}",
        f"- TN = reviewed pass / judge pass: {block.get('TN')}",
        f"- FP = reviewed pass / judge fail: {block.get('FP')}",
        f"- TPR = TP/(TP+FN): {block.get('TPR')} = {block.get('TPR_fraction')}",
        f"- TNR = TN/(TN+FP): {block.get('TNR')} = {block.get('TNR_fraction')}",
        f"- Valid predictions: {block.get('valid_n')}",
        f"- Invalid predictions: {block.get('invalid_n')}",
        f"- Missing predictions: {block.get('missing_n')}",
        f"- Matches frozen expected matrix: {block.get('matches_expected')}",
        "",
    ]


def _write_reports(payload: dict) -> None:
    REPORT_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    counts = payload.get("counts") or {}
    links = payload.get("links") or {}
    datasets = payload.get("datasets") or {}
    pilot = payload.get("pilot") or {}
    matrices = payload.get("matrices") or {}
    read_back = payload.get("read_back") or {}
    lines = [
        "# Week 4 Langfuse F1 judge import",
        "",
        "Historical import of the frozen F1 golden dataset, split, and saved",
        "judge predictions. This is not a new judge run, not a prompt",
        "refinement, and not an application, approval, or release gate.",
        "",
        "## Source",
        "",
        f"- Golden dataset: `{payload.get('golden_dataset_id')}`",
        f"- Split: `{payload.get('split_id')}`",
        f"- Label version: `{payload.get('label_version')}`",
        f"- Calibration dataset: `{payload.get('calibration_dataset_name')}`",
        f"- Validation dataset: `{payload.get('validation_dataset_name')}`",
        f"- Provenance ok: {payload.get('provenance_ok')}",
        f"- Ledger: `{payload.get('ledger_path')}`",
        f"- Outputs: {payload.get('n_outputs')} from {payload.get('n_scenarios')} paired scenarios",
        "- Not 40 independent scenarios.",
        "",
        "## Configuration",
        "",
    ]
    for name, status in (payload.get("config") or {}).items():
        lines.append(f"- `{name}`: {status}")
    lines.extend(
        [
            "",
            "## Datasets",
            "",
            f"- Calibration URL: {links.get('calibration_dataset') or (datasets.get('calibration') or {}).get('url') or 'not created'}",
            f"- Validation URL: {links.get('validation_dataset') or (datasets.get('validation') or {}).get('url') or 'not created'}",
            "- Each dataset contains 20 outputs from 10 paired scenarios: 5 reviewed F1 failures and 15 reviewed passes.",
            "- Both versions of each scenario remain in the same split.",
            "- Reviewed labels are AI-assisted judgments accepted by Lily and are stored in item metadata, not in judge task inputs.",
            "",
            "## Historical judge runs",
            "",
            f"- `{(payload.get('run_names') or {}).get('calibration_v1')}`",
            f"- `{(payload.get('run_names') or {}).get('calibration_v2')}`",
            f"- `{(payload.get('run_names') or {}).get('validation_v1')}`",
            f"- `{(payload.get('run_names') or {}).get('validation_v2')}`",
            f"- Calibration v1 run: {links.get('calibration_v1_run') or 'not created'}",
            f"- Calibration v2 run: {links.get('calibration_v2_run') or 'not created'}",
            f"- Validation v1 run: {links.get('validation_v1_run') or 'not created'}",
            f"- Validation v2 run: {links.get('validation_v2_run') or 'not created'}",
            f"- Calibration comparison: {links.get('calibration_comparison') or 'not created'}",
            f"- Validation comparison: {links.get('validation_comparison') or 'not created'}",
            f"- Model calls: {payload.get('model_calls')}",
            f"- Retrieval calls: {payload.get('retrieval_calls')}",
            f"- Hosted evaluators: {payload.get('hosted_evaluators')}",
            f"- Judges rerun: {payload.get('judges_rerun')}",
            f"- Judges refined: {payload.get('judges_refined')}",
            "",
            "## Scores",
            "",
            f"- `{((payload.get('score_names') or {}).get('judge'))}`: 1=judge pass, 0=judge fail.",
            f"- `{((payload.get('score_names') or {}).get('reviewed'))}`: 1=reviewed pass, 0=reviewed fail. Kept separately identifiable.",
            "- Tasks return saved verdicts, reasons, and excerpts only.",
            "- Generation spans, token usage, and original inference durations were not invented.",
            "",
            "## Recomputed confusion matrices",
            "",
            "Splits are not combined. Agreement is not headlined.",
            "",
        ]
    )
    lines.extend(_matrix_lines("Calibration: frozen judge v1", matrices.get("calibration_v1") or {}))
    lines.extend(_matrix_lines("Calibration: frozen judge v2", matrices.get("calibration_v2") or {}))
    lines.extend(_matrix_lines("Validation: frozen judge v1", matrices.get("validation_v1") or {}))
    lines.extend(_matrix_lines("Validation: frozen judge v2", matrices.get("validation_v2") or {}))
    lines.extend(
        [
            "## Decision",
            "",
            str(payload.get("decision")),
            "",
            "## Verified counts",
            "",
            f"- Prepared outputs: {counts.get('prepared_outputs')}",
            f"- Prepared scenarios: {counts.get('prepared_scenarios')}",
            f"- Calibration items verified: {counts.get('calibration_items_verified')}",
            f"- Validation items verified: {counts.get('validation_items_verified')}",
            f"- Calibration v1 verified: {counts.get('calibration_v1_verified')}",
            f"- Calibration v2 verified: {counts.get('calibration_v2_verified')}",
            f"- Validation v1 verified: {counts.get('validation_v1_verified')}",
            f"- Validation v2 verified: {counts.get('validation_v2_verified')}",
            f"- Failed: {counts.get('failed')}",
            "",
            "## Pilot",
            "",
            f"- Case: {pilot.get('case_id')}",
            f"- Scenario: {pilot.get('scenario_id')}",
            f"- Baseline: {pilot.get('baseline_id')}",
            f"- Action: {pilot.get('action')}",
        ]
    )
    v1_pilot = pilot.get("calibration_v1") or {}
    v2_pilot = pilot.get("calibration_v2") or {}
    if v1_pilot or v2_pilot:
        lines.extend(
            [
                f"- Calibration v1 trace: {v1_pilot.get('trace_url') or v1_pilot.get('trace_id') or v1_pilot.get('langfuse_trace_id')}",
                f"- Calibration v1 judge score: {v1_pilot.get('judge_score_value')}",
                f"- Calibration v2 trace: {v2_pilot.get('trace_url') or v2_pilot.get('trace_id') or v2_pilot.get('langfuse_trace_id')}",
                f"- Calibration v2 judge score: {v2_pilot.get('judge_score_value')}",
            ]
        )
        v1_verified = v1_pilot.get("verified") or {}
        v2_verified = v2_pilot.get("verified") or {}
        if v1_verified:
            lines.append(
                f"- Calibration v1 ingestion delay seconds: {v1_verified.get('ingestion_delay_seconds')}"
            )
        if v2_verified:
            lines.append(
                f"- Calibration v2 ingestion delay seconds: {v2_verified.get('ingestion_delay_seconds')}"
            )
    lines.extend(
        [
            "",
            "## Remote read-back",
            "",
            f"- Calibration items: {(read_back.get('calibration') or {}).get('item_count')}",
            f"- Validation items: {(read_back.get('validation') or {}).get('item_count')}",
            f"- Calibration v1 run items: {(read_back.get('calibration') or {}).get('v1_item_count')}",
            f"- Calibration v2 run items: {(read_back.get('calibration') or {}).get('v2_item_count')}",
            f"- Validation v1 run items: {(read_back.get('validation') or {}).get('v1_item_count')}",
            f"- Validation v2 run items: {(read_back.get('validation') or {}).get('v2_item_count')}",
            f"- Calibration source associations: {(read_back.get('calibration') or {}).get('source_associations')}",
            f"- Validation source associations: {(read_back.get('validation') or {}).get('source_associations')}",
        ]
    )
    if read_back.get("error"):
        lines.append(f"- Read-back error: {read_back.get('error')}")
    lines.extend(["", "## Per-case links", ""])
    for item in payload.get("per_case") or []:
        runs = item.get("runs") or {}
        run_bits = []
        for key, row in runs.items():
            run_bits.append(
                f"{key} {row.get('trace_url')} "
                f"(judge={row.get('judge_score')}, {row.get('judge_label')})"
            )
        lines.append(
            f"- {item.get('case_id')}: reviewed {item.get('reviewed_label')} "
            f"({item.get('reviewed_score')}); source {item.get('source_trace_id')}; "
            + "; ".join(run_bits)
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
            "- Outputs are saved historical judge predictions, not new inference.",
            "- Reviewed labels are AI-assisted judgments accepted by Lily, not independent expert legal adjudication.",
            "- Candidate traces were not historically imported, so only parent Langfuse source associations are available.",
            "- Neither judge is an F1 detector, approval gate, or release gate.",
            "- Existing baseline, timing, and F1 prompt comparisons were not rewritten.",
            "- Frozen local golden, split, prompt, and prediction artifacts were not rewritten.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    prepared = run_import(live=False)
    print(f"prepared outputs: {(prepared.get('counts') or {}).get('prepared_outputs')}")
    print(f"provenance ok: {prepared.get('provenance_ok')}")
    if prepared.get("error") == "provenance_mismatch":
        print(prepared.get("discrepancy"))
        _write_reports(prepared)
        return 1
    if prepared.get("missing_credentials"):
        print("Live import skipped. Missing: " + ", ".join(prepared["missing_credentials"]))
        _write_reports(prepared)
        return 2
    result = run_import(live=True)
    counts = result.get("counts") or {}
    print(f"calibration items: {counts.get('calibration_items_verified')}")
    print(f"validation items: {counts.get('validation_items_verified')}")
    print(f"calibration v1: {counts.get('calibration_v1_verified')}")
    print(f"calibration v2: {counts.get('calibration_v2_verified')}")
    print(f"validation v1: {counts.get('validation_v1_verified')}")
    print(f"validation v2: {counts.get('validation_v2_verified')}")
    print(f"pilot: {result.get('pilot')}")
    print(f"calibration comparison: {(result.get('links') or {}).get('calibration_comparison')}")
    print(f"validation comparison: {(result.get('links') or {}).get('validation_comparison')}")
    if result.get("error"):
        print(f"error: {result['error']}")
    _write_reports(result)
    print(f"wrote {REPORT_MD}")
    print(f"wrote {REPORT_JSON}")
    if (
        result.get("provenance_ok")
        and counts.get("calibration_items_verified") == 20
        and counts.get("validation_items_verified") == 20
        and counts.get("calibration_v1_verified") == 20
        and counts.get("calibration_v2_verified") == 20
        and counts.get("validation_v1_verified") == 20
        and counts.get("validation_v2_verified") == 20
        and not result.get("error")
    ):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
