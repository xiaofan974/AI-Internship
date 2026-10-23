"""Score frozen Week 4 annotations and deterministic checkers offline."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from aeacus_agent.trace_store import PROJECT_DIR, sha256_file, sha256_text, utc_now
from evals.week4.checkers import (
    CHECKER_CONFIG,
    CHECKER_SUITE_ID,
    DEFERRED_DATE_CHECKER_ID,
    S19_BUDGET_CHECKER_ID,
    run_deterministic_assertions,
)

EXPECTED_SOURCE_SHA256 = (
    "29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1"
)
EXPECTED_SCENARIO_COUNT = 20
EXPECTED_CATEGORY_FAILURES = {"F1": 5, "F2": 5, "F3": 2, "F4": 1}
EXPECTED_DISTINCT_FAILING_TRACES = 12
CATEGORY_IDS = ("F1", "F2", "F3", "F4")
RESULT_ID = "week4_codify_baseline_v1"
OVERLAP = {
    DEFERRED_DATE_CHECKER_ID: "F3",
    S19_BUDGET_CHECKER_ID: "F4",
}

TAXONOMY_RELATIVE = "evals/week4/taxonomy_v1.json"
ANNOTATIONS_RELATIVE = "evals/week4/annotations_v1.json"
CHECKERS_RELATIVE = "evals/week4/checkers.py"
CODIFY_RELATIVE = "evals/week4/codify.py"
SCENARIOS_RELATIVE = "evals/week4/scenarios_v1.json"
MANIFEST_RELATIVE = "evals/week4/baselines/week4_adk_preview_v1/manifest.json"
DEFAULT_TRACE_RELATIVE = "data/local/traces/week4_adk_preview_v1.jsonl"
DEFAULT_RESULTS_RELATIVE = "evals/week4/results/week4_codify_baseline_v1.json"
DEFAULT_REPORT_RELATIVE = "reports/week4_codify_baseline.md"


class CodifyError(RuntimeError):
    """Taxonomy, annotation, or source-trace freeze error."""


class SourceMismatchError(CodifyError):
    """Saved baseline bytes do not match the expected SHA-256."""


def default_trace_path(project_dir: Path | None = None) -> Path:
    return (project_dir or PROJECT_DIR) / DEFAULT_TRACE_RELATIVE


def verify_source_hash(
    path: Path, expected: str = EXPECTED_SOURCE_SHA256
) -> str:
    digest = sha256_file(path)
    if digest is None:
        raise SourceMismatchError(f"Baseline trace file is missing: {path}")
    if digest != expected:
        raise SourceMismatchError(
            "Baseline SHA-256 mismatch; refusing to modify or reconstruct "
            f"the traces. expected={expected} observed={digest}"
        )
    return digest


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_traces(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise CodifyError(f"JSONL line {line_no} is not an object.")
        rows.append(row)
    return rows


def load_taxonomy(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if raw.get("schema") != "aeacus.week4.taxonomy.v1":
        raise CodifyError(f"Unexpected taxonomy schema in {path}.")
    ids = [item.get("id") for item in raw.get("categories") or []]
    if ids != list(CATEGORY_IDS):
        raise CodifyError(f"Taxonomy categories must be {CATEGORY_IDS}.")
    if raw.get("first_improvement_target") != "F1":
        raise CodifyError("First improvement target must remain F1.")
    return raw


def _judgment(value: Any) -> str:
    if value not in {"pass", "fail"}:
        raise CodifyError(f"Judgment must be pass or fail, not {value!r}.")
    return value


def summarize_annotations(traces: list[dict[str, Any]]) -> dict[str, Any]:
    category_failures: dict[str, list[str]] = {cid: [] for cid in CATEGORY_IDS}
    failing: list[str] = []
    passing: list[str] = []
    for item in traces:
        scenario_id = item["scenario_id"]
        cats = item["categories"]
        failed = [cid for cid in CATEGORY_IDS if cats[cid] == "fail"]
        expected_overall = "pass" if not failed else "fail"
        if item["overall"] != expected_overall:
            raise CodifyError(
                f"{scenario_id} overall={item['overall']!r} does not match "
                f"category judgments {cats}."
            )
        for cid in failed:
            category_failures[cid].append(scenario_id)
        if failed:
            failing.append(scenario_id)
        else:
            passing.append(scenario_id)
    counts = {cid: len(ids) for cid, ids in category_failures.items()}
    if counts != EXPECTED_CATEGORY_FAILURES:
        raise CodifyError(
            "Category failure counts must be 5/5/2/1, "
            f"found {counts}."
        )
    if len(failing) != EXPECTED_DISTINCT_FAILING_TRACES:
        raise CodifyError(
            "Distinct failing traces must be 12, "
            f"found {len(failing)}."
        )
    return {
        "category_failures": counts,
        "category_fail_ids": category_failures,
        "distinct_failing_traces": len(failing),
        "distinct_failing_ids": failing,
        "overall_pass_ids": passing,
        "overall_fail_ids": failing,
        "overall_pass": len(passing),
        "overall_fail": len(failing),
        "n_traces": len(traces),
        "summed_category_frequencies": sum(counts.values()),
        "summed_category_frequencies_are_not_an_overall_count": True,
    }


def load_annotations(path: Path) -> dict[str, Any]:
    raw = load_json(path)
    if raw.get("schema") != "aeacus.week4.annotations.v1":
        raise CodifyError(f"Unexpected annotations schema in {path}.")
    claimed = (raw.get("source_traces") or {}).get("sha256")
    if claimed != EXPECTED_SOURCE_SHA256:
        raise CodifyError(
            "Annotation freeze is bound to a different source SHA-256."
        )
    items = raw.get("traces")
    if not isinstance(items, list) or len(items) != EXPECTED_SCENARIO_COUNT:
        raise CodifyError(
            f"Annotations must cover exactly {EXPECTED_SCENARIO_COUNT} traces."
        )
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            raise CodifyError("Each annotation must be an object.")
        extra = sorted(
            set(item) - {"scenario_id", "run_id", "categories", "overall"}
        )
        if extra:
            raise CodifyError(
                f"Annotation {item.get('scenario_id')} has extra fields {extra}."
            )
        scenario_id = str(item.get("scenario_id") or "").strip()
        run_id = str(item.get("run_id") or "").strip()
        if not re_full_scenario(scenario_id):
            raise CodifyError(f"Annotation ID must be TRACE-Sxx, not {scenario_id!r}.")
        if scenario_id in seen:
            raise CodifyError(f"Duplicate annotation for {scenario_id}.")
        if not run_id:
            raise CodifyError(f"{scenario_id} is missing a run_id.")
        categories = item.get("categories")
        if not isinstance(categories, dict) or set(categories) != set(CATEGORY_IDS):
            raise CodifyError(f"{scenario_id} must judge all four categories.")
        judged = {cid: _judgment(categories[cid]) for cid in CATEGORY_IDS}
        overall = _judgment(item.get("overall"))
        seen.add(scenario_id)
        normalized.append(
            {
                "scenario_id": scenario_id,
                "run_id": run_id,
                "categories": judged,
                "overall": overall,
            }
        )
    expected_ids = [f"TRACE-S{index:02d}" for index in range(1, 21)]
    if [item["scenario_id"] for item in normalized] != expected_ids:
        raise CodifyError("Annotations must be TRACE-S01 through TRACE-S20 in order.")
    listed = raw.get("category_fail_ids") or {}
    for cid in CATEGORY_IDS:
        actual = [item["scenario_id"] for item in normalized if item["categories"][cid] == "fail"]
        if list(listed.get(cid) or []) != actual:
            raise CodifyError(f"{cid} fail-ID list does not match per-trace judgments.")
    summary = summarize_annotations(normalized)
    raw = dict(raw)
    raw["traces"] = normalized
    raw["summary"] = summary
    return raw


def re_full_scenario(value: str) -> bool:
    return bool(re.fullmatch(r"TRACE-S\d{2}", value))


def empty_human_annotation(value: Any) -> bool:
    return value == {
        "annotator": None,
        "notes": None,
        "labels": [],
        "scores": {},
        "reviewed_at": None,
    }


def join_annotations(
    traces: list[dict[str, Any]], annotations: dict[str, Any]
) -> list[dict[str, Any]]:
    by_run = {row["run_id"]: row for row in traces}
    if len(by_run) != len(traces):
        raise CodifyError("Trace file contains duplicate run IDs.")
    joined: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    populated_original_annotations: list[str] = []
    for item in annotations["traces"]:
        row = by_run.get(item["run_id"])
        if row is None:
            raise CodifyError(
                f"Annotation {item['scenario_id']} run_id "
                f"{item['run_id']} is not in the saved traces."
            )
        if row.get("scenario_id") != item["scenario_id"]:
            raise CodifyError(
                f"Run {item['run_id']} is {row.get('scenario_id')}, "
                f"not {item['scenario_id']}."
            )
        if not empty_human_annotation(row.get("human_annotation")):
            populated_original_annotations.append(item["scenario_id"])
        for field_name in ("final_output", "events", "run_id", "scenario_id"):
            if field_name not in row:
                missing_fields.append(f"{item['scenario_id']}.{field_name}")
        joined.append({"trace": row, "human": item})
    extra = set(by_run) - {item["run_id"] for item in annotations["traces"]}
    if extra:
        raise CodifyError(f"Saved traces have unannotated run IDs: {sorted(extra)}.")
    if populated_original_annotations:
        raise CodifyError(
            "Original traces already contain human_annotation values: "
            + ", ".join(populated_original_annotations)
        )
    if missing_fields:
        raise CodifyError("Missing required trace fields: " + ", ".join(missing_fields))
    return joined


def summarize_assertion_results(
    results: list[dict[str, Any]], checker_id: str
) -> dict[str, Any]:
    applicable = [row for row in results if row["applicable"]]
    counts = Counter(row["result"] for row in results)
    fail_ids = [row["scenario_id"] for row in results if row["result"] == "fail"]
    pass_ids = [row["scenario_id"] for row in results if row["result"] == "pass"]
    na_ids = [row["scenario_id"] for row in results if row["result"] == "not_applicable"]
    return {
        "checker_id": checker_id,
        "applicable": len(applicable),
        "denominator": len(applicable),
        "pass": counts.get("pass", 0),
        "fail": counts.get("fail", 0),
        "not_applicable": counts.get("not_applicable", 0),
        "fail_ids": fail_ids,
        "pass_ids": pass_ids,
        "not_applicable_ids": na_ids,
        "excluded_from_denominator": na_ids,
    }


def find_disagreements(per_trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    disagreements: list[dict[str, Any]] = []
    for row in per_trace:
        human = row["human"]["categories"]
        for checker_id, category_id in OVERLAP.items():
            assertion = row["assertions"][checker_id]
            if assertion["result"] == "not_applicable":
                if human[category_id] == "fail":
                    disagreements.append(
                        {
                            "scenario_id": row["scenario_id"],
                            "run_id": row["run_id"],
                            "human_category": category_id,
                            "human": human[category_id],
                            "checker_id": checker_id,
                            "checker": assertion["result"],
                            "note": (
                                "Reviewed label is fail but the overlapping "
                                "assertion was not applicable."
                            ),
                        }
                    )
                continue
            human_fail = human[category_id] == "fail"
            checker_fail = assertion["result"] == "fail"
            if human_fail != checker_fail:
                disagreements.append(
                    {
                        "scenario_id": row["scenario_id"],
                        "run_id": row["run_id"],
                        "human_category": category_id,
                        "human": human[category_id],
                        "checker_id": checker_id,
                        "checker": assertion["result"],
                        "checker_reasons": assertion["reasons"],
                    }
                )
    return disagreements


def file_hashes(project_dir: Path) -> dict[str, str | None]:
    relatives = {
        "taxonomy_v1": TAXONOMY_RELATIVE,
        "annotations_v1": ANNOTATIONS_RELATIVE,
        "checkers_py": CHECKERS_RELATIVE,
        "codify_py": CODIFY_RELATIVE,
        "scenarios_v1": SCENARIOS_RELATIVE,
        "collection_manifest": MANIFEST_RELATIVE,
    }
    return {
        key: sha256_file(project_dir / relative)
        for key, relative in relatives.items()
    }


def evaluate_baseline(
    *,
    project_dir: Path | None = None,
    trace_path: Path | None = None,
    expected_sha256: str = EXPECTED_SOURCE_SHA256,
) -> dict[str, Any]:
    root = project_dir or PROJECT_DIR
    traces_path = Path(trace_path) if trace_path else default_trace_path(root)
    source_sha = verify_source_hash(traces_path, expected_sha256)
    taxonomy = load_taxonomy(root / TAXONOMY_RELATIVE)
    annotations = load_annotations(root / ANNOTATIONS_RELATIVE)
    traces = load_traces(traces_path)
    if len(traces) != EXPECTED_SCENARIO_COUNT:
        raise CodifyError(
            f"Expected {EXPECTED_SCENARIO_COUNT} saved traces, found {len(traces)}."
        )
    joined = join_annotations(traces, annotations)
    per_trace: list[dict[str, Any]] = []
    assertion_rows: dict[str, list[dict[str, Any]]] = {
        DEFERRED_DATE_CHECKER_ID: [],
        S19_BUDGET_CHECKER_ID: [],
    }
    for item in joined:
        assertions = run_deterministic_assertions(item["trace"])
        serialized = {key: value.to_dict() for key, value in assertions.items()}
        for key, value in serialized.items():
            assertion_rows[key].append(value)
        per_trace.append(
            {
                "scenario_id": item["human"]["scenario_id"],
                "run_id": item["human"]["run_id"],
                "human": item["human"],
                "assertions": serialized,
            }
        )
    assertion_summary = {
        key: summarize_assertion_results(rows, key)
        for key, rows in assertion_rows.items()
    }
    disagreements = find_disagreements(per_trace)
    hashes = file_hashes(root)
    hashes["source_traces"] = source_sha
    hashes["checker_config"] = sha256_text(
        json.dumps(CHECKER_CONFIG, sort_keys=True, ensure_ascii=False)
    )
    return {
        "schema": "aeacus.week4.codify.results.v1",
        "result_id": RESULT_ID,
        "checkpoint": "baseline",
        "claim": (
            "This file records baseline results only. It does not claim a "
            "before/after improvement."
        ),
        "evaluated_at": utc_now(),
        "source": {
            "path": str(traces_path),
            "sha256": source_sha,
            "sha256_verified": True,
            "n_traces": len(traces),
            "unattempted_scenarios": [],
            "missing_fields": [],
        },
        "frozen": {
            "baseline_id": annotations["baseline_id"],
            "taxonomy_id": taxonomy["taxonomy_id"],
            "taxonomy_path": TAXONOMY_RELATIVE,
            "annotations_path": ANNOTATIONS_RELATIVE,
            "collection_manifest_path": MANIFEST_RELATIVE,
            "first_improvement_target": taxonomy["first_improvement_target"],
            "priority_weights": {
                item["id"]: item["priority_weight"]
                for item in taxonomy["categories"]
            },
            "review": taxonomy["review"],
        },
        "hashes": hashes,
        "checker_suite": {
            "id": CHECKER_SUITE_ID,
            "config": CHECKER_CONFIG,
        },
        "human_reviewed_taxonomy": annotations["summary"],
        "deterministic_assertions": assertion_summary,
        "per_trace": per_trace,
        "disagreements_with_reviewed_labels": disagreements,
        "original_human_annotation_fields": {
            "populated": False,
            "value": {
                "annotator": None,
                "notes": None,
                "labels": [],
                "scores": {},
                "reviewed_at": None,
            },
        },
        "limitations": [
            "Deferred-date checking looks for explicit qualification markers in Timing and scope. It does not prove complete semantic correctness.",
            "The S19 rule counts preview_classification_search call events only. It is a scenario-specific regression threshold, not a judgment that context was already complete.",
            "F1 and F2 have no deterministic assertion in this checkpoint.",
            "Reviewed labels are AI-assisted observations accepted by Lily on 2026-10-23. They are not independent expert legal adjudication.",
            "Original JSONL human_annotation fields were left empty.",
            "This checkpoint contains baseline results only.",
        ],
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def render_report(payload: dict[str, Any]) -> str:
    human = payload["human_reviewed_taxonomy"]
    deferred = payload["deterministic_assertions"][DEFERRED_DATE_CHECKER_ID]
    budget = payload["deterministic_assertions"][S19_BUDGET_CHECKER_ID]
    hashes = payload["hashes"]
    review = payload["frozen"]["review"]
    disagreements = payload["disagreements_with_reviewed_labels"]
    if disagreements:
        disagreement_body = "\n".join(
            f"- {item['scenario_id']} ({item['run_id']}): human {item['human_category']}="
            f"{item['human']}; checker {item['checker_id']}={item['checker']}"
            for item in disagreements
        )
    else:
        disagreement_body = (
            "None. On this baseline, deferred-date failures are TRACE-S02 and "
            "TRACE-S20, matching reviewed F3. Both of those Timing and scope "
            "sections mention a December 2027 deferral and an Article 6(5) "
            "exception, but they do not name Chapter III or Sections 1–3. The "
            "S19 retrieval-budget failure is TRACE-S19 with six search call "
            "events, matching reviewed F4. F1 and F2 have no automated "
            "counterpart, so they are not treated as assertion disagreements."
        )
    human_rows = []
    assertion_rows = []
    for row in payload["per_trace"]:
        cats = row["human"]["categories"]
        human_rows.append(
            f"| {row['scenario_id']} | `{row['run_id']}` | {cats['F1']} | "
            f"{cats['F2']} | {cats['F3']} | {cats['F4']} | {row['human']['overall']} |"
        )
        deferred_row = row["assertions"][DEFERRED_DATE_CHECKER_ID]
        budget_row = row["assertions"][S19_BUDGET_CHECKER_ID]
        deferred_reason = deferred_row["reasons"][0] if deferred_row["reasons"] else ""
        budget_reason = budget_row["reasons"][0] if budget_row["reasons"] else ""
        assertion_rows.append(
            f"| {row['scenario_id']} | {deferred_row['result']} | {budget_row['result']} | "
            f"{deferred_reason} | {budget_reason} |"
        )
    return f"""# AeacusAI Week 4 annotation freeze and deterministic baseline

This checkpoint freezes the approved failure taxonomy and scores the unchanged `week4_adk_preview_v1` traces. It does **not** change the agent, rerun scenarios, or claim a before/after improvement. Assertion failures are evaluation findings, not harness errors.

## Source verification

| Item | Value |
| --- | --- |
| Traces | `data/local/traces/week4_adk_preview_v1.jsonl` |
| Expected SHA-256 | `{EXPECTED_SOURCE_SHA256}` |
| Observed SHA-256 | `{payload['source']['sha256']}` |
| Match | yes |
| Lines | {payload['source']['n_traces']} |
| Unattempted scenarios | none |
| Missing required fields | none |

The raw baseline and the frozen collection manifest were not modified. Original `human_annotation` fields remain empty.

## Provenance

- Review date: {review['date']}
- Accepted by: {review['accepted_by']}
- Method: {review['method']}
- Not: {review['not']}
- Acceptance time: not recorded

These are AI-assisted observations and proposed labels reviewed and accepted by Lily in the conversation. They are not independent expert legal adjudication.

## Frozen taxonomy

Separate files:

- `evals/week4/taxonomy_v1.json`
- `evals/week4/annotations_v1.json`

| ID | Title | Priority weight | Failures |
| --- | --- | --- | --- |
| F1 | Classification relies on an unstated premise or extends to an underspecified product. | 3 | {human['category_failures']['F1']} |
| F2 | Explanation broadens or invents a statutory condition or consequence. | 3 | {human['category_failures']['F2']} |
| F3 | Timing summary omits the specific sections whose application is deferred. | 2 | {human['category_failures']['F3']} |
| F4 | Searches continue after relevant child passages and complete context are available. | 1 | {human['category_failures']['F4']} |

Weights are prioritization weights, not answer-quality ratings. The first improvement target remains **F1**, which breaks its priority tie with F2.

Category failure counts: **5 / 5 / 2 / 1**. Distinct failing traces: **{human['distinct_failing_traces']}**. Summed category frequencies ({human['summed_category_frequencies']}) are not an overall failure count.

Overall pass requires all four category passes: **{human['overall_pass']}** pass, **{human['overall_fail']}** fail, out of {human['n_traces']}.

Failing IDs:

- F1: {", ".join(human['category_fail_ids']['F1'])}
- F2: {", ".join(human['category_fail_ids']['F2'])}
- F3: {", ".join(human['category_fail_ids']['F3'])}
- F4: {", ".join(human['category_fail_ids']['F4'])}

## Human-reviewed results by trace

| Scenario | Run ID | F1 | F2 | F3 | F4 | Overall |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(human_rows)}

## Deterministic assertions

Checker suite `{payload['checker_suite']['id']}`. Automated results are read from original `final_output` and `events` only. Human labels are not used to decide an automated result.

### A. Deferred-date qualifications

Inspects **Timing and scope**. When that section summarizes the December 2027 or August 2028 deferral, it requires Chapter III, Sections 1–3, and the Article 6(5) exception. Range and list variants are accepted. This checks explicit qualification markers, not complete semantic correctness.

| Item | Value |
| --- | --- |
| Applicable / denominator | {deferred['applicable']} |
| Pass | {deferred['pass']} |
| Fail | {deferred['fail']} |
| Not applicable | {deferred['not_applicable']} |
| Failures | {", ".join(deferred['fail_ids']) or "none"} |

### B. S19 retrieval budget

Applies only to TRACE-S19. Requires no more than two `preview_classification_search` **call** events. Response events and distinct query strings are not counted. Other scenarios are not applicable and are excluded from the denominator. This is a scenario-specific regression rule, not the agent’s 8-call limit.

| Item | Value |
| --- | --- |
| Applicable / denominator | {budget['applicable']} |
| Pass | {budget['pass']} |
| Fail | {budget['fail']} |
| Not applicable | {budget['not_applicable']} |
| Failures | {", ".join(budget['fail_ids']) or "none"} |

## Per-trace assertion reasons

| Scenario | Deferred-date | S19 budget | Deferred-date reason | S19 budget reason |
| --- | --- | --- | --- | --- |
{chr(10).join(assertion_rows)}

## Disagreements with reviewed labels

Compared only where an assertion overlaps a reviewed category (A with F3, B with F4).

{disagreement_body}

## Configuration and version hashes

| Artifact | SHA-256 |
| --- | --- |
| Source traces | `{hashes['source_traces']}` |
| Taxonomy | `{hashes['taxonomy_v1']}` |
| Annotations | `{hashes['annotations_v1']}` |
| Checker config | `{hashes['checker_config']}` |
| `evals/week4/checkers.py` | `{hashes['checkers_py']}` |
| `evals/week4/codify.py` | `{hashes['codify_py']}` |
| Scenarios | `{hashes['scenarios_v1']}` |
| Collection manifest | `{hashes['collection_manifest']}` |

Evaluated at `{payload['evaluated_at']}`. Result ID `{payload['result_id']}`.

## Limitations

- Deferred-date checking looks for explicit qualification markers in Timing and scope. It does not prove complete semantic correctness.
- The S19 rule counts call events only. It does not itself prove that relevant child passages and complete context were already available.
- F1 and F2 are reviewed labels only in this checkpoint.
- Reviewed labels are not independent expert legal adjudication.
- Original JSONL `human_annotation` fields were not populated.
- This checkpoint contains baseline results only.

Machine-readable results: `evals/week4/results/week4_codify_baseline_v1.json`.
"""


def write_outputs(
    payload: dict[str, Any],
    *,
    project_dir: Path | None = None,
    results_path: Path | None = None,
    report_path: Path | None = None,
) -> tuple[Path, Path]:
    root = project_dir or PROJECT_DIR
    results = Path(results_path) if results_path else root / DEFAULT_RESULTS_RELATIVE
    report = Path(report_path) if report_path else root / DEFAULT_REPORT_RELATIVE
    write_json(results, payload)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(payload), encoding="utf-8")
    return results, report
