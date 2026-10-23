"""Langfuse F1 prompt comparison on the existing week4_adk_preview_v1 dataset.

Uses saved raw outputs from week4_adk_preview_v1 and week4_adk_preview_f1_v2.
Does not call models, retrieve, apply the timing formatter, open the review
register, or rewrite frozen artifacts.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from aeacus_agent.langfuse_preview import (
    auth_check_readonly,
    config_status,
    ensure_client,
    missing_credential_names,
    sdk_available,
)
from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION
from aeacus_agent.trace_store import PROJECT_DIR, redact_value, sha256_file, sha256_text, utc_now
from evals.week4.codify import (
    ANNOTATIONS_RELATIVE,
    DEFAULT_TRACE_RELATIVE,
    EXPECTED_SOURCE_SHA256,
    SCENARIOS_RELATIVE,
    load_json,
    load_traces,
    verify_source_hash,
)
from evals.week4.langfuse_timing_comparison import (
    DATASET_NAME,
    _client_base_url,
    _dataset_items_by_id,
    _find_dataset,
    _output_text,
    _root_payload,
    dataset_compare_url,
    dataset_run_url,
    dataset_url,
    find_experiment_item,
    item_id,
    label_to_score,
    read_remote,
    read_scores,
)

SCHEMA = "aeacus.week4.langfuse_f1_comparison.v1"
LEDGER_SCHEMA = "aeacus.week4.langfuse_f1_comparison.ledger.v1"
PARENT_BASELINE_ID = "week4_adk_preview_v1"
CANDIDATE_BASELINE_ID = "week4_adk_preview_f1_v2"
PARENT_RUN_KEY = "f1_parent"
CANDIDATE_RUN_KEY = "f1_candidate"
PARENT_RUN_NAME = "F1: historical parent answers"
CANDIDATE_RUN_NAME = "F1: rejected prompt candidate answers"
SCORE_NAME = "reviewed_f1_pass"
CANDIDATE_TRACE_RELATIVE = "data/local/traces/week4_adk_preview_f1_v2.jsonl"
CANDIDATE_ANNOTATIONS_RELATIVE = "evals/week4/annotations_f1_v2.json"
PARENT_MANIFEST_RELATIVE = "evals/week4/baselines/week4_adk_preview_v1/manifest.json"
CANDIDATE_MANIFEST_RELATIVE = "evals/week4/baselines/week4_adk_preview_f1_v2/manifest.json"
LEDGER_RELATIVE = (
    "data/local/evals/week4/langfuse/week4_adk_preview_v1_f1_comparison_ledger.json"
)
EXPECTED_CANDIDATE_SHA256 = (
    "3b1fa10c5a05a8db61403ddda04d3e6d5ecf0ae06f684daf3cf30392e253f848"
)
PARENT_INSTRUCTION_SHA256 = (
    "6d28bfa7d6d42c8ce1c21211b1e87adf877137ed878b1082c0ec6f36716a7de7"
)
CANDIDATE_INSTRUCTION_SHA256 = (
    "20f72d6ea00bb6a052266a9abc79066d93119f321a56a3cea446f556cda9517e"
)
EXPECTED_PARENT_FAIL = ["TRACE-S04", "TRACE-S08", "TRACE-S09", "TRACE-S13", "TRACE-S20"]
EXPECTED_CANDIDATE_FAIL = ["TRACE-S01", "TRACE-S04", "TRACE-S09", "TRACE-S13", "TRACE-S15"]
EXPECTED_RECOVERIES = ["TRACE-S08", "TRACE-S20"]
EXPECTED_REGRESSIONS = ["TRACE-S01", "TRACE-S15"]
EXPECTED_PERSISTENT = ["TRACE-S04", "TRACE-S09", "TRACE-S13"]
REVIEW_COMMENT = (
    "Imported AI-assisted F1 judgment accepted by Lily. "
    "Not independent expert legal adjudication."
)


class ProvenanceError(RuntimeError):
    """Frozen F1 artifacts or labels do not match the expected comparison."""


def default_ledger_path(project_dir: Path | None = None) -> Path:
    return (project_dir or PROJECT_DIR) / LEDGER_RELATIVE


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema": LEDGER_SCHEMA,
            "dataset_name": DATASET_NAME,
            "dataset": {},
            "runs": {
                PARENT_RUN_KEY: {"name": PARENT_RUN_NAME, "id": None, "items": {}},
                CANDIDATE_RUN_KEY: {"name": CANDIDATE_RUN_NAME, "id": None, "items": {}},
            },
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("dataset", {})
    payload.setdefault(
        "runs",
        {
            PARENT_RUN_KEY: {"name": PARENT_RUN_NAME, "id": None, "items": {}},
            CANDIDATE_RUN_KEY: {"name": CANDIDATE_RUN_NAME, "id": None, "items": {}},
        },
    )
    for key, name in (
        (PARENT_RUN_KEY, PARENT_RUN_NAME),
        (CANDIDATE_RUN_KEY, CANDIDATE_RUN_NAME),
    ):
        payload["runs"].setdefault(key, {"name": name, "id": None, "items": {}})
        payload["runs"][key].setdefault("items", {})
    return payload


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def _run_item_record(ledger: dict[str, Any], run_key: str, scenario_id: str) -> dict[str, Any]:
    return ((ledger.get("runs") or {}).get(run_key) or {}).get("items", {}).get(
        scenario_id
    ) or {}


def already_verified(ledger: dict[str, Any], run_key: str, scenario_id: str) -> bool:
    return _run_item_record(ledger, run_key, scenario_id).get("status") == "verified"


def _pair_verified(ledger: dict[str, Any], scenario_id: str) -> bool:
    return already_verified(ledger, PARENT_RUN_KEY, scenario_id) and already_verified(
        ledger, CANDIDATE_RUN_KEY, scenario_id
    )


def _fail_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [row["scenario_id"] for row in rows if row["label"] == "fail"]


def _pass_ids(rows: list[dict[str, Any]]) -> list[str]:
    return [row["scenario_id"] for row in rows if row["label"] == "pass"]


def _instruction_sha(trace: dict[str, Any]) -> str:
    instructions = trace.get("instructions") or {}
    return str(instructions.get("sha256") or "")


def _by_scenario(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(row["scenario_id"]): row for row in rows}


def _f1_rows(
    traces: list[dict[str, Any]], annotations: dict[str, Any]
) -> list[dict[str, Any]]:
    annotation_by_run = {
        str(row["run_id"]): row for row in annotations.get("traces") or []
    }
    rows = []
    for trace in traces:
        scenario_id = str(trace["scenario_id"])
        run_id = str(trace["run_id"])
        annotation = annotation_by_run.get(run_id)
        if annotation is None:
            raise ProvenanceError(
                f"{scenario_id} run_id {run_id} is missing from reviewed F1 annotations."
            )
        if str(annotation.get("scenario_id")) != scenario_id:
            raise ProvenanceError(
                f"{scenario_id} annotation scenario does not match run {run_id}."
            )
        categories = annotation.get("categories") or {}
        if "F2" in categories and annotations.get("schema") == "aeacus.week4.annotations.f1_candidate.v1":
            raise ProvenanceError("Candidate F2 labels must not be assigned.")
        label = categories.get("F1")
        if label not in {"pass", "fail"}:
            raise ProvenanceError(f"{scenario_id} is missing a reviewed F1 pass/fail label.")
        rows.append(
            {
                "scenario_id": scenario_id,
                "run_id": run_id,
                "label": label,
                "output": str(trace.get("final_output") or ""),
                "instruction_sha256": _instruction_sha(trace),
                "user_input": trace.get("user_input"),
            }
        )
    return rows


def build_f1_jobs(project_dir: Path | None = None) -> dict[str, Any]:
    """Prepare 20 paired F1 jobs from frozen parent and candidate raw answers."""
    root = project_dir or PROJECT_DIR
    parent_path = root / DEFAULT_TRACE_RELATIVE
    candidate_path = root / CANDIDATE_TRACE_RELATIVE
    parent_sha = verify_source_hash(parent_path, EXPECTED_SOURCE_SHA256)
    candidate_sha = sha256_file(candidate_path)
    if candidate_sha != EXPECTED_CANDIDATE_SHA256:
        raise ProvenanceError(
            "Candidate trace hash mismatch. "
            f"expected={EXPECTED_CANDIDATE_SHA256} observed={candidate_sha}"
        )
    parent_traces = load_traces(parent_path)
    candidate_traces = load_traces(candidate_path)
    scenarios = load_json(root / SCENARIOS_RELATIVE)
    parent_manifest = load_json(root / PARENT_MANIFEST_RELATIVE)
    candidate_manifest = load_json(root / CANDIDATE_MANIFEST_RELATIVE)
    parent_annotations = load_json(root / ANNOTATIONS_RELATIVE)
    candidate_annotations = load_json(root / CANDIDATE_ANNOTATIONS_RELATIVE)
    live_instruction = sha256_text(AEACUS_PREVIEW_INSTRUCTION)
    if live_instruction != PARENT_INSTRUCTION_SHA256:
        raise ProvenanceError(
            "Application instruction is not the restored parent. "
            f"expected={PARENT_INSTRUCTION_SHA256} observed={live_instruction}"
        )
    if parent_manifest.get("baseline_id") != PARENT_BASELINE_ID:
        raise ProvenanceError("Parent manifest baseline_id mismatch.")
    if candidate_manifest.get("baseline_id") != CANDIDATE_BASELINE_ID:
        raise ProvenanceError("Candidate manifest baseline_id mismatch.")
    if candidate_manifest.get("parent_baseline_id") != PARENT_BASELINE_ID:
        raise ProvenanceError("Candidate manifest parent_baseline_id mismatch.")
    if (parent_manifest.get("instructions") or {}).get("sha256") != PARENT_INSTRUCTION_SHA256:
        raise ProvenanceError("Parent manifest instruction hash mismatch.")
    if (candidate_manifest.get("instructions") or {}).get("sha256") != CANDIDATE_INSTRUCTION_SHA256:
        raise ProvenanceError("Candidate manifest instruction hash mismatch.")
    if (parent_manifest.get("scenarios") or {}).get("sha256") != sha256_file(
        root / SCENARIOS_RELATIVE
    ):
        raise ProvenanceError("Parent manifest scenario hash mismatch.")
    if (candidate_manifest.get("scenarios") or {}).get("sha256") != (
        parent_manifest.get("scenarios") or {}
    ).get("sha256"):
        raise ProvenanceError("Candidate scenario hash does not match the parent freeze.")
    scenario_input = {
        str(row["id"]): row.get("input") for row in scenarios.get("scenarios") or []
    }
    if set(scenario_input) != {f"TRACE-S{index:02d}" for index in range(1, 21)}:
        raise ProvenanceError("Frozen scenarios are not TRACE-S01–S20.")
    parent_rows = _f1_rows(parent_traces, parent_annotations)
    candidate_rows = _f1_rows(candidate_traces, candidate_annotations)
    parent_by_id = _by_scenario(parent_rows)
    candidate_by_id = _by_scenario(candidate_rows)
    if set(parent_by_id) != set(candidate_by_id) or set(parent_by_id) != set(scenario_input):
        raise ProvenanceError("Parent, candidate, and scenario IDs do not match.")
    parent_fail = _fail_ids(parent_rows)
    candidate_fail = _fail_ids(candidate_rows)
    recoveries = sorted(set(parent_fail) - set(candidate_fail))
    regressions = sorted(set(candidate_fail) - set(parent_fail))
    persistent = sorted(set(parent_fail) & set(candidate_fail))
    discrepancies = []
    expected = {
        "parent_fail_ids": EXPECTED_PARENT_FAIL,
        "candidate_fail_ids": EXPECTED_CANDIDATE_FAIL,
        "recoveries": EXPECTED_RECOVERIES,
        "regressions": EXPECTED_REGRESSIONS,
        "persistent_failures": EXPECTED_PERSISTENT,
        "parent_pass": 15,
        "candidate_pass": 15,
    }
    observed = {
        "parent_fail_ids": parent_fail,
        "candidate_fail_ids": candidate_fail,
        "recoveries": recoveries,
        "regressions": regressions,
        "persistent_failures": persistent,
        "parent_pass": len(_pass_ids(parent_rows)),
        "candidate_pass": len(_pass_ids(candidate_rows)),
    }
    if observed != expected:
        discrepancies.append({"expected": expected, "observed": observed})
    jobs = []
    for scenario_id in [f"TRACE-S{index:02d}" for index in range(1, 21)]:
        parent = parent_by_id[scenario_id]
        candidate = candidate_by_id[scenario_id]
        expected_input = scenario_input[scenario_id]
        if parent["user_input"] != expected_input or candidate["user_input"] != expected_input:
            discrepancies.append({"scenario_id": scenario_id, "error": "scenario_input_mismatch"})
            continue
        if parent["instruction_sha256"] != PARENT_INSTRUCTION_SHA256:
            discrepancies.append(
                {"scenario_id": scenario_id, "error": "parent_instruction_mismatch"}
            )
            continue
        if candidate["instruction_sha256"] != CANDIDATE_INSTRUCTION_SHA256:
            discrepancies.append(
                {"scenario_id": scenario_id, "error": "candidate_instruction_mismatch"}
            )
            continue
        if not parent["output"] or not candidate["output"]:
            discrepancies.append({"scenario_id": scenario_id, "error": "missing_raw_output"})
            continue
        jobs.append(
            redact_value(
                {
                    "scenario_id": scenario_id,
                    "item_id": item_id(scenario_id),
                    "input": {"scenario_id": scenario_id, "task": expected_input},
                    "runs": {
                        PARENT_RUN_KEY: {
                            "key": PARENT_RUN_KEY,
                            "name": PARENT_RUN_NAME,
                            "baseline_id": PARENT_BASELINE_ID,
                            "original_run_id": parent["run_id"],
                            "instruction_sha256": parent["instruction_sha256"],
                            "source_sha256": parent_sha,
                            "output": parent["output"],
                            "output_sha256": sha256_text(parent["output"]),
                            "score_label": parent["label"],
                            "score_value": label_to_score(parent["label"]),
                        },
                        CANDIDATE_RUN_KEY: {
                            "key": CANDIDATE_RUN_KEY,
                            "name": CANDIDATE_RUN_NAME,
                            "baseline_id": CANDIDATE_BASELINE_ID,
                            "original_run_id": candidate["run_id"],
                            "instruction_sha256": candidate["instruction_sha256"],
                            "source_sha256": candidate_sha,
                            "output": candidate["output"],
                            "output_sha256": sha256_text(candidate["output"]),
                            "score_label": candidate["label"],
                            "score_value": label_to_score(candidate["label"]),
                        },
                    },
                }
            )
        )
    if discrepancies:
        raise ProvenanceError(
            "Frozen F1 comparison does not match the accepted review: "
            f"{json.dumps(discrepancies, default=str)}"
        )
    return {
        "schema": SCHEMA,
        "dataset_name": DATASET_NAME,
        "parent_baseline_id": PARENT_BASELINE_ID,
        "candidate_baseline_id": CANDIDATE_BASELINE_ID,
        "parent_source_sha256": parent_sha,
        "candidate_source_sha256": candidate_sha,
        "parent_instruction_sha256": PARENT_INSTRUCTION_SHA256,
        "candidate_instruction_sha256": CANDIDATE_INSTRUCTION_SHA256,
        "live_instruction_sha256": live_instruction,
        "live_instruction_is_restored_parent": True,
        "n_jobs": len(jobs),
        "jobs": jobs,
        "parent_summary": {
            "pass": observed["parent_pass"],
            "fail": len(parent_fail),
            "fail_ids": parent_fail,
        },
        "candidate_summary": {
            "pass": observed["candidate_pass"],
            "fail": len(candidate_fail),
            "fail_ids": candidate_fail,
        },
        "comparison": {
            "recoveries": recoveries,
            "regressions": regressions,
            "persistent_failures": persistent,
            "not_overall_quality_percentage": True,
            "candidate_f2_labels_assigned": False,
        },
        "expected": expected,
        "review": {
            "parent": parent_annotations.get("review") or {},
            "candidate": candidate_annotations.get("review") or {},
        },
        "timing_formatter_applied": False,
        "model_calls": False,
        "retrieval_calls": False,
        "hosted_judges": False,
    }


def _run_description(run_key: str) -> str:
    if run_key == PARENT_RUN_KEY:
        return (
            "Saved raw answers from frozen week4_adk_preview_v1. "
            "Reviewed F1 labels only. Not new live executions and not a timing repair."
        )
    return (
        "Saved raw answers from the rejected week4_adk_preview_f1_v2 prompt candidate. "
        "Reviewed F1 labels only. Not new live executions and not a timing repair."
    )


def require_existing_dataset(client: Any) -> dict[str, Any]:
    existing = _find_dataset(client, DATASET_NAME)
    if existing is None:
        raise RuntimeError("Dataset week4_adk_preview_v1 must already exist.")
    project_id = getattr(existing, "project_id", None)
    url = None
    if project_id:
        url = dataset_url(_client_base_url(client), str(project_id), existing.id)
    return {
        "id": existing.id,
        "name": existing.name,
        "project_id": project_id,
        "url": url,
        "created": False,
    }


def _experiment_task(jobs_by_item_id: dict[str, dict[str, Any]], run_key: str):
    def task(*, item, **kwargs):
        job = jobs_by_item_id[getattr(item, "id")]
        return job["runs"][run_key]["output"]

    return task


def _experiment_evaluator(jobs_by_item_id: dict[str, dict[str, Any]], run_key: str):
    from langfuse import Evaluation

    def evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
        del expected_output, metadata
        scenario_id = (input or {}).get("scenario_id") if isinstance(input, dict) else None
        job = next(
            item
            for item in jobs_by_item_id.values()
            if item["scenario_id"] == scenario_id
        )
        spec = job["runs"][run_key]
        text = output if isinstance(output, str) else _output_text(output)
        if sha256_text(text) != spec["output_sha256"]:
            raise ProvenanceError(
                f"{scenario_id} {run_key} output drifted from the saved raw answer."
            )
        return Evaluation(
            name=SCORE_NAME,
            value=float(spec["score_value"]),
            comment=REVIEW_COMMENT,
            metadata={
                "accepted_by": "Lily",
                "method": (
                    "AI-assisted observations and proposed labels reviewed "
                    "and accepted by Lily."
                ),
                "not": "independent expert legal adjudication",
                "original_label": spec["score_label"],
                "original_run_id": spec["original_run_id"],
                "baseline_id": spec["baseline_id"],
                "instruction_sha256": spec["instruction_sha256"],
                "imported_reviewed_label": "true",
                "generated_new_label": "false",
            },
            data_type="NUMERIC",
        )

    return evaluator


def run_supported_experiment(
    client: Any,
    jobs: list[dict[str, Any]],
    run_key: str,
) -> dict[str, Any]:
    items_by_id = _dataset_items_by_id(client)
    jobs_by_item_id = {job["item_id"]: job for job in jobs}
    data = []
    for job in jobs:
        item = items_by_id.get(job["item_id"])
        if item is None:
            raise RuntimeError(f"Dataset item {job['item_id']} is not on Langfuse.")
        data.append(item)
    spec = jobs[0]["runs"][run_key]
    result = client.run_experiment(
        name=spec["name"],
        run_name=spec["name"],
        description=_run_description(run_key),
        data=data,
        task=_experiment_task(jobs_by_item_id, run_key),
        evaluators=[_experiment_evaluator(jobs_by_item_id, run_key)],
        max_concurrency=1,
        metadata={
            "baseline_id": spec["baseline_id"],
            "original_run_id": spec["original_run_id"],
            "instruction_sha256": spec["instruction_sha256"],
            "source_sha256": spec["source_sha256"],
            "scenario_id": jobs[0]["scenario_id"],
            "comparison_kind": run_key,
            "timing_formatter_applied": "false",
            "model_calls": "false",
            "retrieval_calls": "false",
            "hosted_judges": "false",
            "score_name": SCORE_NAME,
        },
    )
    mapped: dict[str, Any] = {}
    for item_result in result.item_results:
        dataset_item_id = getattr(item_result.item, "id", None)
        evaluations = {
            getattr(row, "name", None): getattr(row, "value", None)
            for row in item_result.evaluations or []
        }
        mapped[dataset_item_id] = {
            "trace_id": item_result.trace_id,
            "dataset_run_id": item_result.dataset_run_id or result.dataset_run_id,
            "output": item_result.output,
            "output_sha256": sha256_text(_output_text(item_result.output)),
            "score_value": evaluations.get(SCORE_NAME),
        }
    return {
        "run_name": result.run_name,
        "dataset_run_id": result.dataset_run_id,
        "dataset_run_url": result.dataset_run_url,
        "experiment_id": result.experiment_id,
        "items": mapped,
    }


def verify_run_item(
    client: Any,
    job: dict[str, Any],
    run_key: str,
    *,
    trace_id: str,
    dataset_id: str,
    from_start_time: Any,
    timeout_seconds: float = 90.0,
    interval_seconds: float = 3.0,
) -> dict[str, Any]:
    spec = job["runs"][run_key]
    deadline = time.monotonic() + timeout_seconds
    started = time.monotonic()
    last: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        last = read_remote(client, trace_id, "experiment-item-run")
        if "experiment-item-task" in last["observation_names"]:
            last["root"] = _root_payload(
                client.api.observations.get_many(
                    trace_id=trace_id, limit=100, fields="core,basic,io"
                ),
                "experiment-item-task",
            ) or last.get("root")
        remote_score = last["scores"].get(SCORE_NAME)
        score_ok = remote_score is not None and int(float(remote_score)) == int(
            spec["score_value"]
        )
        output = _output_text((last.get("root") or {}).get("output"))
        output_ok = bool(output) and sha256_text(output) == spec["output_sha256"]
        linked = None
        try:
            linked = find_experiment_item(
                client,
                dataset_id=dataset_id,
                experiment_name=spec["name"],
                dataset_item_id=job["item_id"],
                from_start_time=from_start_time,
            )
        except Exception as exc:
            last["link_error"] = type(exc).__name__
        link_ok = linked is not None and getattr(linked, "trace_id", None) == trace_id
        has_experiment_obs = any(
            name in last["observation_names"]
            for name in ("experiment-item-run", "experiment-item-task")
        )
        if has_experiment_obs and score_ok and output_ok and link_ok:
            return {
                "ok": True,
                "ingestion_delay_seconds": round(time.monotonic() - started, 1),
                "observation_names": last["observation_names"],
                "score_value": last["scores"].get(SCORE_NAME),
                "output_sha256": spec["output_sha256"],
                "linked_trace_id": getattr(linked, "trace_id", None),
                "experiment_id": getattr(linked, "experiment_id", None),
                "score_query_error": last.get("score_error"),
            }
        last["score_ok"] = score_ok
        last["output_ok"] = output_ok
        last["link_ok"] = link_ok
        time.sleep(interval_seconds)
    return {
        "ok": False,
        "ingestion_delay_seconds": round(time.monotonic() - started, 1),
        "observation_names": last.get("observation_names") or [],
        "score_value": (last.get("scores") or {}).get(SCORE_NAME),
        "score_ok": last.get("score_ok"),
        "output_ok": last.get("output_ok"),
        "link_ok": last.get("link_ok"),
        "link_error": last.get("link_error"),
        "score_query_error": last.get("score_error"),
        "error": "remote_payload_incomplete",
    }


def _empty_run_record(job: dict[str, Any], run_key: str) -> dict[str, Any]:
    spec = job["runs"][run_key]
    return {
        "scenario_id": job["scenario_id"],
        "original_run_id": spec["original_run_id"],
        "baseline_id": spec["baseline_id"],
        "instruction_sha256": spec["instruction_sha256"],
        "score_value": spec["score_value"],
        "output_sha256": spec["output_sha256"],
        "status": "pending",
        "trace_url": None,
        "langfuse_trace_id": None,
        "dataset_run_id": None,
        "uploaded_at": None,
        "verified_at": None,
        "error": None,
        "verified": None,
    }


def import_run_items(
    jobs: list[dict[str, Any]],
    run_key: str,
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> list[dict[str, Any]]:
    outcomes = []
    run_state = ledger.setdefault("runs", {}).setdefault(
        run_key, {"name": None, "id": None, "items": {}}
    )
    dataset_id = (ledger.get("dataset") or {}).get("id")
    started_from = datetime.now(timezone.utc) - timedelta(hours=6)
    pending = []
    for job in jobs:
        record = run_state.setdefault("items", {}).get(job["scenario_id"]) or _empty_run_record(
            job, run_key
        )
        run_state["items"][job["scenario_id"]] = record
        if already_verified(ledger, run_key, job["scenario_id"]):
            outcomes.append(
                {
                    "scenario_id": job["scenario_id"],
                    "run_key": run_key,
                    "action": "skipped_verified",
                }
            )
            continue
        pending.append(job)
    if not pending:
        return outcomes
    try:
        uploaded = run_supported_experiment(client, pending, run_key)
    except Exception as exc:
        for job in pending:
            record = run_state["items"][job["scenario_id"]]
            record["status"] = "failed"
            record["error"] = type(exc).__name__
            outcomes.append(
                {
                    "scenario_id": job["scenario_id"],
                    "run_key": run_key,
                    "action": "failed",
                    "error": type(exc).__name__,
                }
            )
        save_ledger(ledger_path, ledger)
        return outcomes
    if uploaded.get("dataset_run_id"):
        run_state["id"] = uploaded["dataset_run_id"]
        run_state["url"] = uploaded.get("dataset_run_url")
        run_state["name"] = uploaded.get("run_name")
    for job in pending:
        record = run_state["items"][job["scenario_id"]]
        item_upload = (uploaded.get("items") or {}).get(job["item_id"]) or {}
        record.update(
            {
                "status": "uploaded",
                "uploaded_at": utc_now(),
                "dataset_run_id": item_upload.get("dataset_run_id")
                or uploaded.get("dataset_run_id"),
                "langfuse_trace_id": item_upload.get("trace_id"),
                "experiment_output_sha256": item_upload.get("output_sha256"),
            }
        )
        if item_upload.get("trace_id"):
            try:
                record["trace_url"] = client.get_trace_url(trace_id=item_upload["trace_id"])
            except Exception:
                record["trace_url"] = None
        save_ledger(ledger_path, ledger)
        if not item_upload.get("trace_id"):
            record["status"] = "failed"
            record["error"] = "experiment_item_missing"
            save_ledger(ledger_path, ledger)
            outcomes.append(
                {
                    "scenario_id": job["scenario_id"],
                    "run_key": run_key,
                    "action": "failed",
                    "error": "experiment_item_missing",
                }
            )
            continue
        checked = verify_run_item(
            client,
            job,
            run_key,
            trace_id=item_upload["trace_id"],
            dataset_id=dataset_id,
            from_start_time=started_from,
        )
        record["verified"] = checked
        if checked.get("ok"):
            record["status"] = "verified"
            record["verified_at"] = utc_now()
            record["error"] = None
        else:
            record["status"] = "uploaded"
            record["error"] = checked.get("error")
        save_ledger(ledger_path, ledger)
        outcomes.append(
            {
                "scenario_id": job["scenario_id"],
                "run_key": run_key,
                "action": "verified" if checked.get("ok") else "verify_incomplete",
                "trace_id": item_upload.get("trace_id"),
                "trace_url": record.get("trace_url"),
                "score_value": job["runs"][run_key]["score_value"],
                "verified": checked,
            }
        )
    return outcomes


def import_paired_case(
    job: dict[str, Any],
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> dict[str, Any]:
    parent = import_run_items(
        [job],
        PARENT_RUN_KEY,
        client=client,
        ledger=ledger,
        ledger_path=ledger_path,
    )[0]
    if parent.get("action") not in {"verified", "skipped_verified"}:
        return {
            "scenario_id": job["scenario_id"],
            "action": "pilot_parent_incomplete",
            "parent": parent,
            "candidate": None,
        }
    candidate = import_run_items(
        [job],
        CANDIDATE_RUN_KEY,
        client=client,
        ledger=ledger,
        ledger_path=ledger_path,
    )[0]
    action = (
        "verified"
        if parent.get("action") in {"verified", "skipped_verified"}
        and candidate.get("action") in {"verified", "skipped_verified"}
        else "pilot_incomplete"
    )
    return {
        "scenario_id": job["scenario_id"],
        "action": action,
        "parent": parent,
        "candidate": candidate,
    }


def read_back_dataset(client: Any) -> dict[str, Any]:
    dataset = client.get_dataset(DATASET_NAME, fetch_items_page_size=50)
    items = [
        {
            "id": item.id,
            "source_trace_id": item.source_trace_id,
            "has_task_input": isinstance(item.input, dict) and bool(item.input.get("task")),
            "labels_in_input": "reviewed_labels" in json.dumps(item.input or {}),
        }
        for item in dataset.items
    ]
    start = datetime.now(timezone.utc) - timedelta(days=2)
    runs = {}
    for key, name in (
        (PARENT_RUN_KEY, PARENT_RUN_NAME),
        (CANDIDATE_RUN_KEY, CANDIDATE_RUN_NAME),
    ):
        try:
            listed = client.api.experiments.list(
                from_start_time=start,
                dataset_id=dataset.id,
                name=name,
                fields="core",
                limit=50,
            )
            experiment_items = client.api.experiments.list_items(
                from_start_time=start,
                dataset_id=dataset.id,
                experiment_name=name,
                fields="core",
                limit=100,
            )
        except Exception as exc:
            runs[key] = {"error": type(exc).__name__, "items": []}
            continue
        experiment = (listed.data or [None])[0]
        runs[key] = {
            "id": getattr(experiment, "id", None),
            "name": getattr(experiment, "name", None) or name,
            "item_count": len(experiment_items.data or []),
            "items": [
                {
                    "dataset_item_id": getattr(row, "experiment_item_id", None),
                    "trace_id": getattr(row, "trace_id", None),
                    "dataset_run_id": getattr(row, "experiment_id", None),
                }
                for row in experiment_items.data or []
            ],
        }
    return {
        "dataset_id": dataset.id,
        "dataset_name": dataset.name,
        "project_id": dataset.project_id,
        "item_count": len(items),
        "items": items,
        "runs": runs,
    }


def run_comparison(
    project_dir: Path | None = None,
    *,
    live: bool = False,
) -> dict[str, Any]:
    root = project_dir or PROJECT_DIR
    try:
        prepared = build_f1_jobs(root)
    except ProvenanceError as exc:
        return {
            "schema": SCHEMA,
            "provenance_ok": False,
            "error": "provenance_mismatch",
            "discrepancy": str(exc),
            "live": live,
            "counts": {},
        }
    ledger_path = default_ledger_path(root)
    ledger = load_ledger(ledger_path)
    report = {
        "schema": SCHEMA,
        "dataset_name": DATASET_NAME,
        "parent_baseline_id": prepared["parent_baseline_id"],
        "candidate_baseline_id": prepared["candidate_baseline_id"],
        "parent_source_sha256": prepared["parent_source_sha256"],
        "candidate_source_sha256": prepared["candidate_source_sha256"],
        "parent_instruction_sha256": prepared["parent_instruction_sha256"],
        "candidate_instruction_sha256": prepared["candidate_instruction_sha256"],
        "live_instruction_sha256": prepared["live_instruction_sha256"],
        "live_instruction_is_restored_parent": prepared["live_instruction_is_restored_parent"],
        "source_sha256_verified": True,
        "provenance_ok": True,
        "config": config_status(),
        "missing_credentials": missing_credential_names(),
        "sdk_available": sdk_available(),
        "ledger_path": str(ledger_path),
        "expected": prepared["expected"],
        "parent_summary": prepared["parent_summary"],
        "candidate_summary": prepared["candidate_summary"],
        "comparison": prepared["comparison"],
        "review": prepared["review"],
        "score_name": SCORE_NAME,
        "score_encoding": {"pass": 1, "fail": 0},
        "run_names": {
            PARENT_RUN_KEY: PARENT_RUN_NAME,
            CANDIDATE_RUN_KEY: CANDIDATE_RUN_NAME,
        },
        "timing_formatter_applied": False,
        "model_calls": False,
        "retrieval_calls": False,
        "hosted_judges": False,
        "candidate_f2_labels_assigned": False,
        "overall_quality_percentage_reported": False,
        "pilot": None,
        "remaining": [],
        "dataset": None,
        "read_back": None,
        "links": {},
        "counts": {
            "prepared": prepared["n_jobs"],
            "parent_verified": 0,
            "candidate_verified": 0,
            "paired_verified": 0,
            "failed": 0,
        },
        "live": live,
    }
    if not live:
        save_ledger(ledger_path, ledger)
        return report
    if report["missing_credentials"] or not report["sdk_available"]:
        report["error"] = "offline_only_missing_langfuse"
        return report
    auth = auth_check_readonly()
    report["auth_check"] = {"ok": auth.get("ok"), "error": auth.get("error")}
    if not auth.get("ok"):
        report["error"] = "auth_check_failed"
        return report
    client = ensure_client()
    dataset = require_existing_dataset(client)
    ledger["dataset"] = dataset
    save_ledger(ledger_path, ledger)
    report["dataset"] = dataset
    jobs = prepared["jobs"]
    unverified = [job for job in jobs if not _pair_verified(ledger, job["scenario_id"])]
    if unverified:
        pilot_job = unverified[0]
        report["pilot"] = import_paired_case(
            pilot_job,
            client=client,
            ledger=ledger,
            ledger_path=ledger_path,
        )
        if report["pilot"].get("action") != "verified":
            report["error"] = "pilot_not_verified"
            _summarize(report, ledger, jobs, client)
            save_ledger(ledger_path, ledger)
            return report
        rest = [
            job
            for job in jobs
            if job["scenario_id"] != pilot_job["scenario_id"]
            and not _pair_verified(ledger, job["scenario_id"])
        ]
        remaining = [
            import_paired_case(
                job, client=client, ledger=ledger, ledger_path=ledger_path
            )
            for job in rest
        ]
        report["remaining"] = remaining
        if any(row.get("action") != "verified" for row in remaining):
            report["error"] = "remaining_not_verified"
    if report.get("pilot") is None and jobs:
        first = jobs[0]
        parent = _run_item_record(ledger, PARENT_RUN_KEY, first["scenario_id"])
        candidate = _run_item_record(ledger, CANDIDATE_RUN_KEY, first["scenario_id"])
        if parent.get("status") == "verified" and candidate.get("status") == "verified":
            report["pilot"] = {
                "scenario_id": first["scenario_id"],
                "action": "verified",
                "parent": {
                    "scenario_id": first["scenario_id"],
                    "action": "skipped_verified",
                    "trace_id": parent.get("langfuse_trace_id"),
                    "trace_url": parent.get("trace_url"),
                    "score_value": parent.get("score_value"),
                    "verified": parent.get("verified"),
                },
                "candidate": {
                    "scenario_id": first["scenario_id"],
                    "action": "skipped_verified",
                    "trace_id": candidate.get("langfuse_trace_id"),
                    "trace_url": candidate.get("trace_url"),
                    "score_value": candidate.get("score_value"),
                    "verified": candidate.get("verified"),
                },
            }
    _summarize(report, ledger, jobs, client)
    save_ledger(ledger_path, ledger)
    return report


def _summarize(
    report: dict[str, Any],
    ledger: dict[str, Any],
    jobs: list[dict[str, Any]],
    client: Any | None = None,
) -> None:
    parent_verified = 0
    candidate_verified = 0
    failed = 0
    per_trace = []
    for job in jobs:
        parent = _run_item_record(ledger, PARENT_RUN_KEY, job["scenario_id"])
        candidate = _run_item_record(ledger, CANDIDATE_RUN_KEY, job["scenario_id"])
        if parent.get("status") == "verified":
            parent_verified += 1
        if candidate.get("status") == "verified":
            candidate_verified += 1
        if "failed" in {parent.get("status"), candidate.get("status")}:
            failed += 1
        per_trace.append(
            {
                "scenario_id": job["scenario_id"],
                "parent_run_id": job["runs"][PARENT_RUN_KEY]["original_run_id"],
                "candidate_run_id": job["runs"][CANDIDATE_RUN_KEY]["original_run_id"],
                "parent_instruction_sha256": job["runs"][PARENT_RUN_KEY][
                    "instruction_sha256"
                ],
                "candidate_instruction_sha256": job["runs"][CANDIDATE_RUN_KEY][
                    "instruction_sha256"
                ],
                "parent_score": job["runs"][PARENT_RUN_KEY]["score_value"],
                "candidate_score": job["runs"][CANDIDATE_RUN_KEY]["score_value"],
                "parent_trace_id": parent.get("langfuse_trace_id"),
                "candidate_trace_id": candidate.get("langfuse_trace_id"),
                "parent_trace_url": parent.get("trace_url"),
                "candidate_trace_url": candidate.get("trace_url"),
                "parent_status": parent.get("status"),
                "candidate_status": candidate.get("status"),
            }
        )
    report["counts"]["parent_verified"] = parent_verified
    report["counts"]["candidate_verified"] = candidate_verified
    report["counts"]["paired_verified"] = sum(
        1 for job in jobs if _pair_verified(ledger, job["scenario_id"])
    )
    report["counts"]["failed"] = failed
    report["per_trace"] = per_trace
    dataset = ledger.get("dataset") or report.get("dataset") or {}
    project_id = dataset.get("project_id")
    dataset_id = dataset.get("id")
    parent_run_id = ((ledger.get("runs") or {}).get(PARENT_RUN_KEY) or {}).get("id")
    candidate_run_id = ((ledger.get("runs") or {}).get(CANDIDATE_RUN_KEY) or {}).get("id")
    if client is not None:
        try:
            read_back = read_back_dataset(client)
            report["read_back"] = {
                "item_count": read_back.get("item_count"),
                "dataset_id": read_back.get("dataset_id"),
                "parent_item_count": (read_back.get("runs") or {})
                .get(PARENT_RUN_KEY, {})
                .get("item_count"),
                "candidate_item_count": (read_back.get("runs") or {})
                .get(CANDIDATE_RUN_KEY, {})
                .get("item_count"),
                "parent_run_id": (read_back.get("runs") or {})
                .get(PARENT_RUN_KEY, {})
                .get("id"),
                "candidate_run_id": (read_back.get("runs") or {})
                .get(CANDIDATE_RUN_KEY, {})
                .get("id"),
            }
            project_id = project_id or read_back.get("project_id")
            dataset_id = dataset_id or read_back.get("dataset_id")
            parent_run_id = parent_run_id or (read_back.get("runs") or {}).get(
                PARENT_RUN_KEY, {}
            ).get("id")
            candidate_run_id = candidate_run_id or (read_back.get("runs") or {}).get(
                CANDIDATE_RUN_KEY, {}
            ).get("id")
        except Exception as exc:
            report["read_back"] = {"error": type(exc).__name__}
    base_url = _client_base_url(client) if client is not None else "https://cloud.langfuse.com"
    links = {
        "dataset": dataset.get("url"),
        "parent_run": None,
        "candidate_run": None,
        "comparison": None,
    }
    if project_id and dataset_id:
        links["dataset"] = dataset_url(base_url, str(project_id), str(dataset_id))
        if parent_run_id:
            links["parent_run"] = dataset_run_url(
                base_url, str(project_id), str(dataset_id), str(parent_run_id)
            )
        if candidate_run_id:
            links["candidate_run"] = dataset_run_url(
                base_url, str(project_id), str(dataset_id), str(candidate_run_id)
            )
        if parent_run_id and candidate_run_id:
            links["comparison"] = dataset_compare_url(
                base_url,
                str(project_id),
                str(dataset_id),
                [str(parent_run_id), str(candidate_run_id)],
            )
    report["links"] = links
    report["dataset_run_ids"] = {
        PARENT_RUN_KEY: parent_run_id,
        CANDIDATE_RUN_KEY: candidate_run_id,
    }
