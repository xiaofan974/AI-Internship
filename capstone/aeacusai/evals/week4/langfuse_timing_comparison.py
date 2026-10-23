"""Source-linked Langfuse dataset and timing-repair comparison.

Uses frozen week4_adk_preview_v1 traces, the verified historical import
ledger, and a fresh application-layer formatter replay. Does not call
models, retrieve, open the review register, or rewrite frozen artifacts.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from aeacus_agent.langfuse_preview import (
    auth_check_readonly,
    config_status,
    ensure_client,
    missing_credential_names,
    sdk_available,
)
from aeacus_agent.timing_scope import (
    FORMATTER_ID,
    FORMATTER_VERSION,
    apply_timing_repair,
    prefix_outside_timing,
    records_from_events,
)
from aeacus_agent.trace_store import PROJECT_DIR, redact_value, sha256_file, sha256_text, utc_now
from evals.week4.checkers import DEFERRED_DATE_CHECKER_ID, check_deferred_date_qualifications
from evals.week4.codify import (
    ANNOTATIONS_RELATIVE,
    CHECKERS_RELATIVE,
    DEFAULT_TRACE_RELATIVE,
    EXPECTED_SOURCE_SHA256,
    SCENARIOS_RELATIVE,
    load_json,
    load_traces,
    verify_source_hash,
)
from evals.week4.langfuse_baseline_import import (
    BASELINE_ID,
    LEDGER_RELATIVE as IMPORT_LEDGER_RELATIVE,
    default_ledger_path as default_import_ledger_path,
    load_ledger as load_import_ledger,
)
from evals.week4.replay_timing import replay_parent_traces

SCHEMA = "aeacus.week4.langfuse_timing_comparison.v1"
LEDGER_SCHEMA = "aeacus.week4.langfuse_timing_comparison.ledger.v1"
DATASET_NAME = "week4_adk_preview_v1"
DATASET_VERSION = "v1"
RAW_RUN_KEY = "historical_raw"
REPAIR_RUN_KEY = "timing_repair"
RAW_RUN_NAME = "Historical raw model answers"
REPAIR_RUN_NAME = "Timing repair: application-layer replay"
RAW_SPAN_NAME = "historical-raw-answer"
REPAIR_SPAN_NAME = "timing-repair-replay"
SCORE_NAME = DEFERRED_DATE_CHECKER_ID
TIMING_REPORT_RELATIVE = "reports/week4_timing_repair_eval.json"
LEDGER_RELATIVE = (
    "data/local/evals/week4/langfuse/week4_adk_preview_v1_timing_comparison_ledger.json"
)
SCORE_NAMESPACE = uuid.UUID("2c7a1d90-4e6f-4b11-9a58-0d3f6c8e1b24")
EXPECTED_RAW = {
    "pass": 18,
    "fail": 2,
    "fail_ids": ["TRACE-S02", "TRACE-S20"],
}
EXPECTED_DELIVERED = {
    "pass": 20,
    "fail": 0,
    "fail_ids": [],
}
COMPARISON_NOT = [
    "improved model reasoning",
    "20 new live agent executions",
    "a hosted judge",
    "a gold-standard model answer",
]
REPAIR_LABEL = (
    "Fresh application-layer replay of the original saved observations. "
    "No model or retrieval calls."
)
RAW_LABEL = "Historical raw model answers from frozen week4_adk_preview_v1 traces."


class ProvenanceError(RuntimeError):
    """Recomputed checker results or source links do not match the freeze."""


def label_to_score(label: str) -> int:
    if label == "pass":
        return 1
    if label == "fail":
        return 0
    raise ValueError(f"Unsupported label {label!r}; expected pass or fail.")


def item_id(scenario_id: str) -> str:
    return f"{BASELINE_ID}:item:{scenario_id}"


def run_association_key(run_key: str, original_run_id: str) -> str:
    return f"{BASELINE_ID}:dataset_run:{run_key}:{original_run_id}"


def deterministic_trace_id(run_key: str, original_run_id: str) -> str:
    seed = run_association_key(run_key, original_run_id)
    return hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex()


def deterministic_score_id(run_key: str, original_run_id: str) -> str:
    return str(
        uuid.uuid5(
            SCORE_NAMESPACE,
            f"{run_association_key(run_key, original_run_id)}:{SCORE_NAME}",
        )
    )


def default_ledger_path(project_dir: Path | None = None) -> Path:
    return (project_dir or PROJECT_DIR) / LEDGER_RELATIVE


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema": LEDGER_SCHEMA,
            "baseline_id": BASELINE_ID,
            "dataset_name": DATASET_NAME,
            "source_sha256": EXPECTED_SOURCE_SHA256,
            "dataset": {},
            "items": {},
            "runs": {
                RAW_RUN_KEY: {"name": RAW_RUN_NAME, "id": None, "items": {}},
                REPAIR_RUN_KEY: {"name": REPAIR_RUN_NAME, "id": None, "items": {}},
            },
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("dataset", {})
    payload.setdefault("items", {})
    payload.setdefault(
        "runs",
        {
            RAW_RUN_KEY: {"name": RAW_RUN_NAME, "id": None, "items": {}},
            REPAIR_RUN_KEY: {"name": REPAIR_RUN_NAME, "id": None, "items": {}},
        },
    )
    for key, name in ((RAW_RUN_KEY, RAW_RUN_NAME), (REPAIR_RUN_KEY, REPAIR_RUN_NAME)):
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


def already_uploaded(ledger: dict[str, Any], run_key: str, scenario_id: str) -> bool:
    return _run_item_record(ledger, run_key, scenario_id).get("status") in {
        "uploaded",
        "verified",
    }


def already_verified(ledger: dict[str, Any], run_key: str, scenario_id: str) -> bool:
    return _run_item_record(ledger, run_key, scenario_id).get("status") == "verified"


def already_item_verified(ledger: dict[str, Any], scenario_id: str) -> bool:
    return ((ledger.get("items") or {}).get(scenario_id) or {}).get("status") == "verified"


def _assertion_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    pass_ids = [row["scenario_id"] for row in rows if row["result"] == "pass"]
    fail_ids = [row["scenario_id"] for row in rows if row["result"] == "fail"]
    return {
        "checker_id": DEFERRED_DATE_CHECKER_ID,
        "pass": len(pass_ids),
        "fail": len(fail_ids),
        "fail_ids": fail_ids,
        "pass_ids": pass_ids,
    }


def _matches_expected(summary: dict[str, Any], expected: dict[str, Any]) -> bool:
    return (
        summary.get("pass") == expected["pass"]
        and summary.get("fail") == expected["fail"]
        and list(summary.get("fail_ids") or []) == expected["fail_ids"]
    )


def _report_timing_summary(report: dict[str, Any], layer: str) -> dict[str, Any]:
    replay = (
        report.get("replay")
        or (report.get("offline_verification") or {}).get("replay")
        or {}
    )
    block = (
        (replay.get("deterministic_assertions") or {}).get(layer)
        or (report.get("deterministic_assertions") or {}).get(layer)
        or {}
    )
    timing = block.get(DEFERRED_DATE_CHECKER_ID) or {}
    return {
        "pass": timing.get("pass"),
        "fail": timing.get("fail"),
        "fail_ids": list(timing.get("fail_ids") or []),
        "pass_ids": list(timing.get("pass_ids") or []),
    }


def _verified_import_records(project_dir: Path) -> dict[str, dict[str, Any]]:
    ledger = load_import_ledger(default_import_ledger_path(project_dir))
    records = ledger.get("records") or {}
    by_scenario: dict[str, dict[str, Any]] = {}
    missing = []
    unverified = []
    for run_id, row in records.items():
        scenario_id = str(row.get("scenario_id") or "")
        if not scenario_id:
            continue
        if row.get("status") != "verified" or not row.get("langfuse_trace_id"):
            unverified.append(scenario_id or run_id)
            continue
        by_scenario[scenario_id] = row
    expected_ids = [f"TRACE-S{index:02d}" for index in range(1, 21)]
    missing = [scenario_id for scenario_id in expected_ids if scenario_id not in by_scenario]
    if missing or unverified:
        raise ProvenanceError(
            "Historical import ledger does not contain 20 verified source traces: "
            f"missing={missing} unverified={unverified}"
        )
    return by_scenario


def build_comparison_jobs(project_dir: Path | None = None) -> dict[str, Any]:
    """Prepare one dataset item and two comparison outputs per frozen trace."""
    root = project_dir or PROJECT_DIR
    traces_path = root / DEFAULT_TRACE_RELATIVE
    source_sha = verify_source_hash(traces_path)
    traces = load_traces(traces_path)
    annotations = load_json(root / ANNOTATIONS_RELATIVE)
    scenarios = load_json(root / SCENARIOS_RELATIVE)
    timing_report = load_json(root / TIMING_REPORT_RELATIVE)
    import_records = _verified_import_records(root)
    replay = replay_parent_traces(traces_path, expected_sha256=source_sha)
    raw_block = ((replay.get("deterministic_assertions") or {}).get("raw") or {}).get(
        DEFERRED_DATE_CHECKER_ID
    ) or {}
    delivered_block = (
        (replay.get("deterministic_assertions") or {}).get("delivered") or {}
    ).get(DEFERRED_DATE_CHECKER_ID) or {}
    annotation_by_run = {
        str(row["run_id"]): row for row in annotations.get("traces") or []
    }
    scenario_input = {
        str(row["id"]): row.get("input") for row in scenarios.get("scenarios") or []
    }
    repair_by_scenario = {
        str(item["scenario_id"]): item for item in replay.get("per_trace") or []
    }
    report_raw = _report_timing_summary(timing_report, "raw")
    report_delivered = _report_timing_summary(timing_report, "delivered")
    jobs = []
    raw_results = []
    delivered_results = []
    for trace in traces:
        scenario_id = str(trace["scenario_id"])
        run_id = str(trace["run_id"])
        annotation = annotation_by_run[run_id]
        import_row = import_records[scenario_id]
        if import_row.get("run_id") != run_id:
            raise ProvenanceError(
                f"{scenario_id} import run_id {import_row.get('run_id')} "
                f"does not match frozen run_id {run_id}."
            )
        raw_output = str(trace.get("final_output") or "")
        repair_row = repair_by_scenario[scenario_id]
        repair = repair_row.get("repair") or {}
        if repair.get("raw_output") != raw_output:
            raise ProvenanceError(
                f"{scenario_id} replay raw_output does not match frozen final_output."
            )
        delivered_output = str(repair.get("delivered_output") or "")
        live_repair = apply_timing_repair(
            raw_output, records_from_events(trace.get("events"))
        )
        if live_repair.delivered_output != delivered_output:
            raise ProvenanceError(
                f"{scenario_id} formatter replay does not match replay_parent_traces."
            )
        if prefix_outside_timing(delivered_output) != prefix_outside_timing(raw_output):
            raise ProvenanceError(f"{scenario_id} formatter changed text outside Timing and scope.")
        raw_check = check_deferred_date_qualifications(
            {"scenario_id": scenario_id, "run_id": run_id, "final_output": raw_output}
        )
        delivered_check = check_deferred_date_qualifications(
            {
                "scenario_id": scenario_id,
                "run_id": run_id,
                "final_output": delivered_output,
            }
        )
        raw_results.append(raw_check.to_dict())
        delivered_results.append(delivered_check.to_dict())
        reviewed_labels = dict(annotation.get("categories") or {})
        source_trace_id = str(import_row["langfuse_trace_id"])
        jobs.append(
            redact_value(
                {
                    "baseline_id": BASELINE_ID,
                    "scenario_id": scenario_id,
                    "original_run_id": run_id,
                    "item_id": item_id(scenario_id),
                    "source_trace_id": source_trace_id,
                    "source_trace_url": import_row.get("trace_url"),
                    "input": {
                        "scenario_id": scenario_id,
                        "task": scenario_input.get(scenario_id) or trace.get("user_input"),
                    },
                    "expected_output": None,
                    "metadata": {
                        "scenario_id": scenario_id,
                        "original_run_id": run_id,
                        "baseline_id": BASELINE_ID,
                        "dataset_version": DATASET_VERSION,
                        "source_trace_id": source_trace_id,
                        "source_hashes": {
                            "traces_sha256": source_sha,
                            "scenarios_sha256": sha256_file(root / SCENARIOS_RELATIVE),
                            "annotations_sha256": sha256_file(root / ANNOTATIONS_RELATIVE),
                            "checkers_sha256": sha256_file(root / CHECKERS_RELATIVE),
                            "import_association_key": import_row.get("association_key"),
                        },
                        "reviewed_labels": reviewed_labels,
                        "reviewed_labels_are_not_task_input": True,
                        "original_model_answer_is_not_gold": True,
                    },
                    "runs": {
                        RAW_RUN_KEY: {
                            "key": RAW_RUN_KEY,
                            "name": RAW_RUN_NAME,
                            "span_name": RAW_SPAN_NAME,
                            "label": RAW_LABEL,
                            "output": raw_output,
                            "output_sha256": sha256_text(raw_output),
                            "score_value": label_to_score(raw_check.result),
                            "score_label": raw_check.result,
                            "score_id": deterministic_score_id(RAW_RUN_KEY, run_id),
                            "langfuse_trace_id": deterministic_trace_id(RAW_RUN_KEY, run_id),
                            "checker": raw_check.to_dict(),
                        },
                        REPAIR_RUN_KEY: {
                            "key": REPAIR_RUN_KEY,
                            "name": REPAIR_RUN_NAME,
                            "span_name": REPAIR_SPAN_NAME,
                            "label": REPAIR_LABEL,
                            "output": delivered_output,
                            "output_sha256": sha256_text(delivered_output),
                            "score_value": label_to_score(delivered_check.result),
                            "score_label": delivered_check.result,
                            "score_id": deterministic_score_id(REPAIR_RUN_KEY, run_id),
                            "langfuse_trace_id": deterministic_trace_id(
                                REPAIR_RUN_KEY, run_id
                            ),
                            "checker": delivered_check.to_dict(),
                            "formatter_id": FORMATTER_ID,
                            "formatter_version": FORMATTER_VERSION,
                            "repair_status": repair.get("status"),
                            "source_record_id": repair.get("source_record_id"),
                            "source_text_sha256": repair.get("source_text_sha256"),
                        },
                    },
                }
            )
        )
    raw_summary = _assertion_summary(raw_results)
    delivered_summary = _assertion_summary(delivered_results)
    discrepancies = []
    if not _matches_expected(raw_summary, EXPECTED_RAW):
        discrepancies.append({"layer": "recomputed_raw", "observed": raw_summary})
    if not _matches_expected(delivered_summary, EXPECTED_DELIVERED):
        discrepancies.append(
            {"layer": "recomputed_delivered", "observed": delivered_summary}
        )
    if not _matches_expected(report_raw, EXPECTED_RAW):
        discrepancies.append({"layer": "timing_report_raw", "observed": report_raw})
    if not _matches_expected(report_delivered, EXPECTED_DELIVERED):
        discrepancies.append(
            {"layer": "timing_report_delivered", "observed": report_delivered}
        )
    if not _matches_expected(
        {
            "pass": raw_block.get("pass"),
            "fail": raw_block.get("fail"),
            "fail_ids": list(raw_block.get("fail_ids") or []),
        },
        EXPECTED_RAW,
    ):
        discrepancies.append({"layer": "replay_raw", "observed": raw_block})
    if not _matches_expected(
        {
            "pass": delivered_block.get("pass"),
            "fail": delivered_block.get("fail"),
            "fail_ids": list(delivered_block.get("fail_ids") or []),
        },
        EXPECTED_DELIVERED,
    ):
        discrepancies.append({"layer": "replay_delivered", "observed": delivered_block})
    if discrepancies:
        raise ProvenanceError(
            "Recomputed timing results differ from the expected 18/20 raw and "
            f"20/20 delivered freeze: {json.dumps(discrepancies, default=str)}"
        )
    return {
        "schema": SCHEMA,
        "baseline_id": BASELINE_ID,
        "dataset_name": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "source_sha256": source_sha,
        "n_jobs": len(jobs),
        "jobs": jobs,
        "raw_summary": raw_summary,
        "delivered_summary": delivered_summary,
        "expected": {
            "raw": EXPECTED_RAW,
            "delivered": EXPECTED_DELIVERED,
        },
        "delivered_generation": {
            "method": "fresh_application_layer_replay",
            "formatter_id": FORMATTER_ID,
            "formatter_version": FORMATTER_VERSION,
            "label": REPAIR_LABEL,
            "model_calls": False,
            "retrieval_calls": False,
            "hosted_judges": False,
        },
        "comparison_not": COMPARISON_NOT,
        "review": annotations.get("review") or {},
        "import_ledger": IMPORT_LEDGER_RELATIVE,
    }


def _dataset_description() -> str:
    return (
        "Versioned source-linked dataset for frozen week4_adk_preview_v1. "
        "Each item is one TRACE-S01–S20 case linked to its verified historical "
        "Langfuse source trace. Reviewed labels live in item metadata only. "
        "The original model answer is not a gold-standard expected output."
    )


def _run_description(run_key: str) -> str:
    if run_key == RAW_RUN_KEY:
        return (
            "Historical raw model answers from frozen week4_adk_preview_v1 traces. "
            "Not new live agent executions. Scores use unchanged "
            f"{DEFERRED_DATE_CHECKER_ID} (1=pass, 0=fail)."
        )
    return (
        "Application-layer timing repair: fresh deterministic formatter replay "
        "of the original saved observations. No model or retrieval calls. "
        "Not improved model reasoning and not 20 new live agent executions. "
        f"Scores use unchanged {DEFERRED_DATE_CHECKER_ID} (1=pass, 0=fail)."
    )


def dataset_url(base_url: str, project_id: str, dataset_id: str) -> str:
    return f"{base_url.rstrip('/')}/project/{project_id}/datasets/{dataset_id}"


def dataset_compare_url(
    base_url: str, project_id: str, dataset_id: str, run_ids: list[str]
) -> str:
    query = "&".join(f"runs={item}" for item in run_ids if item)
    return f"{dataset_url(base_url, project_id, dataset_id)}/compare?{query}"


def dataset_run_url(
    base_url: str, project_id: str, dataset_id: str, run_id: str
) -> str:
    return f"{dataset_url(base_url, project_id, dataset_id)}/runs/{run_id}"


def _client_base_url(client: Any) -> str:
    return str(getattr(client, "_base_url", None) or "https://cloud.langfuse.com")


def _client_project_id(client: Any, fallback: str | None = None) -> str | None:
    return getattr(client, "_project_id", None) or fallback


def _find_dataset(client: Any, name: str) -> Any | None:
    page = 1
    while True:
        result = client.api.datasets.list(page=page, limit=50)
        for row in result.data or []:
            if getattr(row, "name", None) == name:
                return row
        meta = getattr(result, "meta", None)
        total_pages = getattr(meta, "total_pages", 1) if meta is not None else 1
        if page >= total_pages:
            return None
        page += 1


def ensure_dataset(client: Any, prepared: dict[str, Any]) -> dict[str, Any]:
    existing = _find_dataset(client, DATASET_NAME)
    created = False
    if existing is None:
        existing = client.create_dataset(
            name=DATASET_NAME,
            description=_dataset_description(),
            metadata={
                "version": DATASET_VERSION,
                "baseline_id": BASELINE_ID,
                "source_sha256": prepared["source_sha256"],
                "original_model_answer_is_not_gold": True,
                "reviewed_labels_location": "item.metadata.reviewed_labels",
                "comparison_not": COMPARISON_NOT,
            },
        )
        created = True
    project_id = getattr(existing, "project_id", None) or _client_project_id(client)
    url = None
    if project_id:
        url = dataset_url(_client_base_url(client), str(project_id), existing.id)
    return {
        "id": existing.id,
        "name": existing.name,
        "project_id": project_id,
        "url": url,
        "created": created,
    }


def upsert_dataset_item(client: Any, job: dict[str, Any]) -> Any:
    return client.create_dataset_item(
        dataset_name=DATASET_NAME,
        id=job["item_id"],
        input=job["input"],
        expected_output=job["expected_output"],
        metadata=job["metadata"],
        source_trace_id=job["source_trace_id"],
    )


def _experiment_task(jobs_by_item_id: dict[str, dict[str, Any]], run_key: str):
    def task(*, item, **kwargs):
        job = jobs_by_item_id[getattr(item, "id")]
        return job["runs"][run_key]["output"]

    return task


def _experiment_evaluator(run_key: str):
    from langfuse import Evaluation

    def evaluator(*, input, output, expected_output=None, metadata=None, **kwargs):
        del expected_output
        text = output if isinstance(output, str) else _output_text(output)
        scenario_id = (input or {}).get("scenario_id") if isinstance(input, dict) else None
        checked = check_deferred_date_qualifications(
            {"scenario_id": scenario_id, "final_output": text}
        )
        return Evaluation(
            name=SCORE_NAME,
            value=float(label_to_score(checked.result)),
            comment=(
                f"Unchanged {DEFERRED_DATE_CHECKER_ID} on the "
                f"{'delivered formatter replay' if run_key == REPAIR_RUN_KEY else 'historical raw answer'}. "
                "Encoding 1=pass, 0=fail. Not a hosted judge and not a score on the "
                "original raw source trace."
            ),
            metadata={
                "checker_id": DEFERRED_DATE_CHECKER_ID,
                "layer": "delivered" if run_key == REPAIR_RUN_KEY else "raw",
                "original_result": checked.result,
                "scored_trace_is_not_source_trace": "true",
            },
            data_type="NUMERIC",
        )

    return evaluator


def _dataset_items_by_id(client: Any) -> dict[str, Any]:
    dataset = client.get_dataset(DATASET_NAME, fetch_items_page_size=50)
    return {item.id: item for item in dataset.items}


def find_experiment_item(
    client: Any,
    *,
    dataset_id: str,
    experiment_name: str,
    dataset_item_id: str,
    from_start_time: Any,
) -> Any | None:
    page = client.api.experiments.list_items(
        from_start_time=from_start_time,
        dataset_id=dataset_id,
        experiment_name=experiment_name,
        fields="core",
        limit=100,
    )
    for row in page.data or []:
        if getattr(row, "experiment_item_id", None) == dataset_item_id:
            return row
        metadata = getattr(row, "experiment_item_metadata", None) or {}
        if isinstance(metadata, dict) and metadata.get("dataset_item_id") == dataset_item_id:
            return row
    return None


def run_supported_experiment(
    client: Any,
    jobs: list[dict[str, Any]],
    run_key: str,
) -> dict[str, Any]:
    """Create one Langfuse experiment run item per job via run_experiment.

    The local task returns saved raw or formatter-replayed text. The local
    evaluator reuses deferred_date_qualifications_v1. No model or retrieval.
    """
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
        evaluators=[_experiment_evaluator(run_key)],
        max_concurrency=1,
        metadata={
            "baseline_id": BASELINE_ID,
            "comparison_kind": (
                "application-layer repair"
                if run_key == REPAIR_RUN_KEY
                else "historical raw model answers"
            ),
            "model_calls": "false",
            "retrieval_calls": "false",
            "hosted_judges": "false",
        },
    )
    mapped: dict[str, Any] = {}
    for item_result in result.item_results:
        item = item_result.item
        dataset_item_id = getattr(item, "id", None)
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


def _observation_rows(page: Any) -> list[Any]:
    return list(getattr(page, "data", None) or [])


def _observation_names(page: Any) -> list[str]:
    names: list[str] = []
    for item in _observation_rows(page):
        name = getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("name")
        if name and name not in names:
            names.append(str(name))
    return names


def _score_map(page: Any) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    if page is None:
        return mapped
    for item in getattr(page, "data", None) or []:
        name = getattr(item, "name", None)
        value = getattr(item, "value", None)
        if name is None and isinstance(item, dict):
            name = item.get("name")
            value = item.get("value")
        if name is not None:
            mapped[str(name)] = value
    return mapped


def _root_payload(page: Any, span_name: str) -> dict[str, Any]:
    for item in _observation_rows(page):
        name = getattr(item, "name", None)
        if name == span_name:
            return {
                "input": getattr(item, "input", None),
                "output": getattr(item, "output", None),
                "metadata": getattr(item, "metadata", None),
            }
    return {}


def read_scores(client: Any, trace_id: str) -> tuple[dict[str, Any], str | None]:
    score_error = None
    scores = None
    try:
        scores = client.api.scores_v3.get_many_v3(trace_id=trace_id, limit=50)
    except Exception as exc:
        score_error = type(exc).__name__
        try:
            scores = client.api.scores.get_many(trace_id=trace_id, limit=50)
            score_error = None
        except Exception as exc2:
            score_error = f"{score_error}+{type(exc2).__name__}"
    return _score_map(scores), score_error


def read_remote(client: Any, trace_id: str, span_name: str) -> dict[str, Any]:
    observations = client.api.observations.get_many(
        trace_id=trace_id, limit=100, fields="core,basic,io"
    )
    scores, score_error = read_scores(client, trace_id)
    return {
        "observation_names": _observation_names(observations),
        "observation_count": len(_observation_rows(observations)),
        "root": _root_payload(observations, span_name),
        "scores": scores,
        "score_error": score_error,
    }


def _output_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("output", "delivered_output", "raw_output", "text"):
            if isinstance(value.get(key), str):
                return value[key]
        return json.dumps(value, sort_keys=True)
    return str(value)


def verify_dataset_item(
    client: Any,
    job: dict[str, Any],
    *,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 3.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    started = time.monotonic()
    last: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        remote = None
        error = None
        try:
            remote = client.api.dataset_items.get(id=job["item_id"])
        except Exception as exc:
            error = type(exc).__name__
        last = {
            "id": getattr(remote, "id", None),
            "source_trace_id": getattr(remote, "source_trace_id", None),
            "expected_output": getattr(remote, "expected_output", None),
            "input": getattr(remote, "input", None),
            "metadata": getattr(remote, "metadata", None),
            "error": error,
        }
        input_ok = isinstance(last["input"], dict) and bool(last["input"].get("task"))
        labels_not_in_input = True
        if isinstance(last["input"], dict):
            blob = json.dumps(last["input"])
            labels_not_in_input = "reviewed_labels" not in blob and "F1" not in blob
        source_ok = last["source_trace_id"] == job["source_trace_id"]
        expected_empty = last["expected_output"] in (None, "", {}, [])
        if input_ok and source_ok and expected_empty and labels_not_in_input:
            return {
                "ok": True,
                "ingestion_delay_seconds": round(time.monotonic() - started, 1),
                "source_trace_id": last["source_trace_id"],
                "expected_output": last["expected_output"],
                "labels_in_input": False,
            }
        time.sleep(interval_seconds)
    return {
        "ok": False,
        "ingestion_delay_seconds": round(time.monotonic() - started, 1),
        "source_trace_id": last.get("source_trace_id"),
        "expected_output": last.get("expected_output"),
        "error": last.get("error") or "dataset_item_incomplete",
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
        source_scores, source_score_error = read_scores(client, job["source_trace_id"])
        last["source_scores"] = source_scores
        last["source_score_error"] = source_score_error
        remote_score = last["scores"].get(SCORE_NAME)
        score_ok = remote_score is not None and int(float(remote_score)) == int(
            spec["score_value"]
        )
        output = _output_text((last.get("root") or {}).get("output"))
        output_ok = bool(output) and sha256_text(output) == spec["output_sha256"]
        source_has_comparison_score = SCORE_NAME in source_scores
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
        if (
            has_experiment_obs
            and score_ok
            and output_ok
            and link_ok
            and not source_has_comparison_score
        ):
            return {
                "ok": True,
                "ingestion_delay_seconds": round(time.monotonic() - started, 1),
                "observation_names": last["observation_names"],
                "score_value": last["scores"].get(SCORE_NAME),
                "output_sha256": spec["output_sha256"],
                "source_has_comparison_score": False,
                "linked_trace_id": getattr(linked, "trace_id", None),
                "experiment_id": getattr(linked, "experiment_id", None),
                "score_query_error": last.get("score_error"),
            }
        last["score_ok"] = score_ok
        last["output_ok"] = output_ok
        last["link_ok"] = link_ok
        last["source_has_comparison_score"] = source_has_comparison_score
        time.sleep(interval_seconds)
    return {
        "ok": False,
        "ingestion_delay_seconds": round(time.monotonic() - started, 1),
        "observation_names": last.get("observation_names") or [],
        "score_value": (last.get("scores") or {}).get(SCORE_NAME),
        "source_scores": last.get("source_scores") or {},
        "source_has_comparison_score": last.get("source_has_comparison_score"),
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
        "original_run_id": job["original_run_id"],
        "langfuse_trace_id": spec["langfuse_trace_id"],
        "score_id": spec["score_id"],
        "score_value": spec["score_value"],
        "output_sha256": spec["output_sha256"],
        "status": "pending",
        "trace_url": None,
        "dataset_run_id": None,
        "dataset_run_item_id": None,
        "uploaded_at": None,
        "verified_at": None,
        "error": None,
        "verified": None,
    }


def upsert_items(
    jobs: list[dict[str, Any]],
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> list[dict[str, Any]]:
    outcomes = []
    for job in jobs:
        scenario_id = job["scenario_id"]
        record = (ledger.get("items") or {}).get(scenario_id) or {
            "scenario_id": scenario_id,
            "item_id": job["item_id"],
            "source_trace_id": job["source_trace_id"],
            "status": "pending",
        }
        ledger.setdefault("items", {})[scenario_id] = record
        if already_item_verified(ledger, scenario_id):
            outcomes.append({"scenario_id": scenario_id, "action": "skipped_verified"})
            continue
        try:
            upsert_dataset_item(client, job)
            record.update(
                {
                    "item_id": job["item_id"],
                    "source_trace_id": job["source_trace_id"],
                    "source_trace_url": job.get("source_trace_url"),
                    "status": "created",
                    "created_at": utc_now(),
                }
            )
            save_ledger(ledger_path, ledger)
            checked = verify_dataset_item(client, job)
            record["verified"] = checked
            if checked.get("ok"):
                record["status"] = "verified"
                record["verified_at"] = utc_now()
                record["error"] = None
            else:
                record["error"] = checked.get("error")
            save_ledger(ledger_path, ledger)
            outcomes.append(
                {
                    "scenario_id": scenario_id,
                    "action": "verified" if checked.get("ok") else "item_incomplete",
                    "item_id": job["item_id"],
                    "source_trace_id": job["source_trace_id"],
                    "verified": checked,
                }
            )
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = type(exc).__name__
            save_ledger(ledger_path, ledger)
            outcomes.append(
                {
                    "scenario_id": scenario_id,
                    "action": "failed",
                    "error": type(exc).__name__,
                }
            )
    return outcomes


def import_run_items(
    jobs: list[dict[str, Any]],
    run_key: str,
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
    verify: bool = True,
) -> list[dict[str, Any]]:
    from datetime import datetime, timedelta, timezone

    outcomes = []
    run_state = ledger.setdefault("runs", {}).setdefault(
        run_key, {"name": None, "id": None, "items": {}}
    )
    dataset_id = (ledger.get("dataset") or {}).get("id")
    started_from = datetime.now(timezone.utc) - timedelta(hours=6)
    pending = []
    for job in jobs:
        scenario_id = job["scenario_id"]
        record = run_state.setdefault("items", {}).get(scenario_id) or _empty_run_record(
            job, run_key
        )
        run_state["items"][scenario_id] = record
        if already_verified(ledger, run_key, scenario_id):
            outcomes.append(
                {
                    "scenario_id": scenario_id,
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
        scenario_id = job["scenario_id"]
        record = run_state["items"][scenario_id]
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
                record["trace_url"] = client.get_trace_url(
                    trace_id=item_upload["trace_id"]
                )
            except Exception:
                record["trace_url"] = None
        save_ledger(ledger_path, ledger)
        if not verify:
            outcomes.append(
                {
                    "scenario_id": scenario_id,
                    "run_key": run_key,
                    "action": "uploaded",
                    "trace_id": item_upload.get("trace_id"),
                    "trace_url": record.get("trace_url"),
                }
            )
            continue
        if not item_upload.get("trace_id"):
            record["status"] = "failed"
            record["error"] = "experiment_item_missing"
            save_ledger(ledger_path, ledger)
            outcomes.append(
                {
                    "scenario_id": scenario_id,
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
            if checked.get("experiment_id"):
                run_state["id"] = record.get("dataset_run_id") or run_state.get("id")
        else:
            record["status"] = "uploaded"
            record["error"] = checked.get("error")
        save_ledger(ledger_path, ledger)
        outcomes.append(
            {
                "scenario_id": scenario_id,
                "run_key": run_key,
                "action": "verified" if checked.get("ok") else "verify_incomplete",
                "trace_id": item_upload.get("trace_id"),
                "trace_url": record.get("trace_url"),
                "score_value": job["runs"][run_key]["score_value"],
                "verified": checked,
            }
        )
    return outcomes


def _pair_verified(ledger: dict[str, Any], scenario_id: str) -> bool:
    return already_verified(ledger, RAW_RUN_KEY, scenario_id) and already_verified(
        ledger, REPAIR_RUN_KEY, scenario_id
    )


def import_paired_case(
    job: dict[str, Any],
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
) -> dict[str, Any]:
    raw = import_run_items(
        [job],
        RAW_RUN_KEY,
        client=client,
        ledger=ledger,
        ledger_path=ledger_path,
        verify=True,
    )[0]
    if raw.get("action") not in {"verified", "skipped_verified"}:
        return {
            "scenario_id": job["scenario_id"],
            "action": "pilot_raw_incomplete",
            "raw": raw,
            "delivered": None,
        }
    delivered = import_run_items(
        [job],
        REPAIR_RUN_KEY,
        client=client,
        ledger=ledger,
        ledger_path=ledger_path,
        verify=True,
    )[0]
    action = (
        "verified"
        if raw.get("action") in {"verified", "skipped_verified"}
        and delivered.get("action") in {"verified", "skipped_verified"}
        else "pilot_incomplete"
    )
    return {
        "scenario_id": job["scenario_id"],
        "action": action,
        "raw": raw,
        "delivered": delivered,
    }


def read_back_dataset(client: Any) -> dict[str, Any]:
    dataset = client.get_dataset(DATASET_NAME, fetch_items_page_size=50)
    items = []
    for item in dataset.items:
        items.append(
            {
                "id": item.id,
                "source_trace_id": item.source_trace_id,
                "expected_output": item.expected_output,
                "has_task_input": isinstance(item.input, dict)
                and bool(item.input.get("task")),
                "reviewed_labels_in_metadata": isinstance(item.metadata, dict)
                and "reviewed_labels" in item.metadata,
            }
        )
    from datetime import datetime, timezone, timedelta

    runs = {}
    start = datetime.now(timezone.utc) - timedelta(days=2)
    for key, name in ((RAW_RUN_KEY, RAW_RUN_NAME), (REPAIR_RUN_KEY, REPAIR_RUN_NAME)):
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
            "description": getattr(experiment, "description", None),
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
        prepared = build_comparison_jobs(root)
    except ProvenanceError as exc:
        return {
            "schema": SCHEMA,
            "baseline_id": BASELINE_ID,
            "source_sha256_verified": False,
            "provenance_ok": False,
            "error": "provenance_mismatch",
            "discrepancy": str(exc),
            "live": live,
            "counts": {},
        }
    ledger_path = default_ledger_path(root)
    ledger = load_ledger(ledger_path)
    ledger["source_sha256"] = prepared["source_sha256"]
    report = {
        "schema": SCHEMA,
        "baseline_id": BASELINE_ID,
        "dataset_name": DATASET_NAME,
        "dataset_version": DATASET_VERSION,
        "source_sha256": prepared["source_sha256"],
        "source_sha256_verified": True,
        "provenance_ok": True,
        "config": config_status(),
        "missing_credentials": missing_credential_names(),
        "sdk_available": sdk_available(),
        "ledger_path": str(ledger_path),
        "import_ledger": prepared["import_ledger"],
        "expected": prepared["expected"],
        "raw_summary": prepared["raw_summary"],
        "delivered_summary": prepared["delivered_summary"],
        "delivered_generation": prepared["delivered_generation"],
        "comparison_not": prepared["comparison_not"],
        "review": prepared["review"],
        "score_name": SCORE_NAME,
        "score_encoding": {"pass": 1, "fail": 0},
        "run_names": {
            RAW_RUN_KEY: RAW_RUN_NAME,
            REPAIR_RUN_KEY: REPAIR_RUN_NAME,
        },
        "pilot": None,
        "remaining": [],
        "dataset": None,
        "read_back": None,
        "links": {},
        "counts": {
            "prepared": prepared["n_jobs"],
            "items_verified": 0,
            "raw_verified": 0,
            "delivered_verified": 0,
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
    dataset = ensure_dataset(client, prepared)
    ledger["dataset"] = dataset
    save_ledger(ledger_path, ledger)
    report["dataset"] = dataset
    item_outcomes = upsert_items(
        prepared["jobs"],
        client=client,
        ledger=ledger,
        ledger_path=ledger_path,
    )
    report["item_outcomes"] = [
        {
            "scenario_id": row.get("scenario_id"),
            "action": row.get("action"),
            "source_trace_id": row.get("source_trace_id"),
        }
        for row in item_outcomes
    ]
    if any(row.get("action") not in {"verified", "skipped_verified"} for row in item_outcomes):
        report["error"] = "dataset_items_not_verified"
        _summarize(report, ledger, prepared["jobs"], client)
        save_ledger(ledger_path, ledger)
        return report
    jobs = prepared["jobs"]
    unverified_pairs = [job for job in jobs if not _pair_verified(ledger, job["scenario_id"])]
    if unverified_pairs:
        pilot_job = unverified_pairs[0]
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
        remaining = []
        for job in rest:
            remaining.append(
                import_paired_case(
                    job,
                    client=client,
                    ledger=ledger,
                    ledger_path=ledger_path,
                )
            )
        report["remaining"] = remaining
        if any(row.get("action") != "verified" for row in remaining):
            report["error"] = "remaining_not_verified"
    if report.get("pilot") is None and jobs:
        first = jobs[0]
        raw = _run_item_record(ledger, RAW_RUN_KEY, first["scenario_id"])
        delivered = _run_item_record(ledger, REPAIR_RUN_KEY, first["scenario_id"])
        if raw.get("status") == "verified" and delivered.get("status") == "verified":
            report["pilot"] = {
                "scenario_id": first["scenario_id"],
                "action": "verified",
                "raw": {
                    "scenario_id": first["scenario_id"],
                    "run_key": RAW_RUN_KEY,
                    "action": "skipped_verified",
                    "trace_id": raw.get("langfuse_trace_id"),
                    "trace_url": raw.get("trace_url"),
                    "score_value": raw.get("score_value"),
                    "verified": raw.get("verified"),
                },
                "delivered": {
                    "scenario_id": first["scenario_id"],
                    "run_key": REPAIR_RUN_KEY,
                    "action": "skipped_verified",
                    "trace_id": delivered.get("langfuse_trace_id"),
                    "trace_url": delivered.get("trace_url"),
                    "score_value": delivered.get("score_value"),
                    "verified": delivered.get("verified"),
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
    items_verified = 0
    raw_verified = 0
    delivered_verified = 0
    failed = 0
    per_trace = []
    for job in jobs:
        item = (ledger.get("items") or {}).get(job["scenario_id"]) or {}
        raw = _run_item_record(ledger, RAW_RUN_KEY, job["scenario_id"])
        delivered = _run_item_record(ledger, REPAIR_RUN_KEY, job["scenario_id"])
        if item.get("status") == "verified":
            items_verified += 1
        if raw.get("status") == "verified":
            raw_verified += 1
        if delivered.get("status") == "verified":
            delivered_verified += 1
        if "failed" in {item.get("status"), raw.get("status"), delivered.get("status")}:
            failed += 1
        per_trace.append(
            {
                "scenario_id": job["scenario_id"],
                "original_run_id": job["original_run_id"],
                "item_id": job["item_id"],
                "source_trace_id": job["source_trace_id"],
                "source_trace_url": job.get("source_trace_url"),
                "raw_score": job["runs"][RAW_RUN_KEY]["score_value"],
                "delivered_score": job["runs"][REPAIR_RUN_KEY]["score_value"],
                "raw_output_sha256": job["runs"][RAW_RUN_KEY]["output_sha256"],
                "delivered_output_sha256": job["runs"][REPAIR_RUN_KEY]["output_sha256"],
                "raw_trace_id": raw.get("langfuse_trace_id"),
                "delivered_trace_id": delivered.get("langfuse_trace_id"),
                "raw_trace_url": raw.get("trace_url"),
                "delivered_trace_url": delivered.get("trace_url"),
                "item_status": item.get("status"),
                "raw_status": raw.get("status"),
                "delivered_status": delivered.get("status"),
            }
        )
    report["counts"]["items_verified"] = items_verified
    report["counts"]["raw_verified"] = raw_verified
    report["counts"]["delivered_verified"] = delivered_verified
    report["counts"]["paired_verified"] = sum(
        1
        for job in jobs
        if _pair_verified(ledger, job["scenario_id"])
    )
    report["counts"]["failed"] = failed
    report["per_trace"] = per_trace
    dataset = ledger.get("dataset") or report.get("dataset") or {}
    project_id = dataset.get("project_id")
    dataset_id = dataset.get("id")
    raw_run_id = ((ledger.get("runs") or {}).get(RAW_RUN_KEY) or {}).get("id")
    repair_run_id = ((ledger.get("runs") or {}).get(REPAIR_RUN_KEY) or {}).get("id")
    if client is not None:
        try:
            read_back = read_back_dataset(client)
            report["read_back"] = {
                "item_count": read_back.get("item_count"),
                "dataset_id": read_back.get("dataset_id"),
                "raw_item_count": (read_back.get("runs") or {})
                .get(RAW_RUN_KEY, {})
                .get("item_count"),
                "delivered_item_count": (read_back.get("runs") or {})
                .get(REPAIR_RUN_KEY, {})
                .get("item_count"),
                "raw_run_id": (read_back.get("runs") or {}).get(RAW_RUN_KEY, {}).get("id"),
                "delivered_run_id": (read_back.get("runs") or {})
                .get(REPAIR_RUN_KEY, {})
                .get("id"),
                "source_links": [
                    {
                        "id": item.get("id"),
                        "source_trace_id": item.get("source_trace_id"),
                    }
                    for item in read_back.get("items") or []
                ],
            }
            project_id = project_id or read_back.get("project_id")
            dataset_id = dataset_id or read_back.get("dataset_id")
            raw_run_id = raw_run_id or (read_back.get("runs") or {}).get(RAW_RUN_KEY, {}).get(
                "id"
            )
            repair_run_id = repair_run_id or (read_back.get("runs") or {}).get(
                REPAIR_RUN_KEY, {}
            ).get("id")
            if dataset.get("id") != dataset_id or not dataset.get("project_id"):
                dataset = {
                    **dataset,
                    "id": dataset_id,
                    "project_id": project_id,
                    "name": DATASET_NAME,
                }
                report["dataset"] = dataset
        except Exception as exc:
            report["read_back"] = {"error": type(exc).__name__}
    base_url = _client_base_url(client) if client is not None else "https://cloud.langfuse.com"
    links = {
        "dataset": dataset.get("url"),
        "historical_raw_run": None,
        "timing_repair_run": None,
        "comparison": None,
    }
    if project_id and dataset_id:
        links["dataset"] = dataset_url(base_url, str(project_id), str(dataset_id))
        if raw_run_id:
            links["historical_raw_run"] = dataset_run_url(
                base_url, str(project_id), str(dataset_id), str(raw_run_id)
            )
        if repair_run_id:
            links["timing_repair_run"] = dataset_run_url(
                base_url, str(project_id), str(dataset_id), str(repair_run_id)
            )
        if raw_run_id and repair_run_id:
            links["comparison"] = dataset_compare_url(
                base_url,
                str(project_id),
                str(dataset_id),
                [str(raw_run_id), str(repair_run_id)],
            )
    report["links"] = links
    report["dataset_run_ids"] = {
        RAW_RUN_KEY: raw_run_id,
        REPAIR_RUN_KEY: repair_run_id,
    }
