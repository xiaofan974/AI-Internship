"""Historical Langfuse import for frozen week4_adk_preview_v1 traces.

Resumable ledger prevents duplicate uploads. Does not call models, retrieve,
open the review register, or rewrite frozen artifacts.
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
from aeacus_agent.trace_store import (
    PROJECT_DIR,
    redact_value,
    utc_now,
    visible_events_only,
)
from evals.week4.checkers import DEFERRED_DATE_CHECKER_ID, S19_BUDGET_CHECKER_ID
from evals.week4.codify import (
    ANNOTATIONS_RELATIVE,
    DEFAULT_RESULTS_RELATIVE,
    DEFAULT_TRACE_RELATIVE,
    EXPECTED_SOURCE_SHA256,
    load_json,
    load_traces,
    verify_source_hash,
)

SCHEMA = "aeacus.week4.langfuse_baseline_import.v1"
LEDGER_SCHEMA = "aeacus.week4.langfuse_baseline_import.ledger.v1"
BASELINE_ID = "week4_adk_preview_v1"
HISTORICAL_TAG = "historical_import"
ASSOCIATION_PREFIX = "week4_adk_preview_v1"
ROOT_SPAN_NAME = "historical-import"
EVENTS_SPAN_NAME = "recorded-events"
EVIDENCE_SPAN_NAME = "recorded-evidence"
REVIEWED_SCORE_NAMES = {
    "F1": "reviewed_f1",
    "F2": "reviewed_f2",
    "F3": "reviewed_f3",
    "F4": "reviewed_f4",
}
AUTOMATED_TIMING_SCORE = "automated_deferred_date_qualifications_v1"
AUTOMATED_S19_SCORE = "automated_s19_retrieval_budget_v1"
REVIEW_COMMENT = (
    "Imported AI-assisted judgment accepted by Lily. "
    "Not independent expert legal adjudication."
)
AUTOMATED_COMMENT = (
    "Imported original deterministic checker result from week4_codify_baseline_v1."
)
LEDGER_RELATIVE = (
    "data/local/evals/week4/langfuse/week4_adk_preview_v1_import_ledger.json"
)
SCORE_NAMESPACE = uuid.UUID("6d28bfa7-d6d4-4c8c-b1e8-7adf877137ed")


def association_key(run_id: str) -> str:
    return f"{ASSOCIATION_PREFIX}:{run_id}"


def deterministic_trace_id(run_id: str) -> str:
    seed = association_key(run_id)
    return hashlib.sha256(seed.encode("utf-8")).digest()[:16].hex()


def deterministic_score_id(run_id: str, score_name: str) -> str:
    return str(uuid.uuid5(SCORE_NAMESPACE, f"{association_key(run_id)}:{score_name}"))


def label_to_score(label: str) -> int:
    if label == "pass":
        return 1
    if label == "fail":
        return 0
    raise ValueError(f"Unsupported label {label!r}; expected pass or fail.")


def default_ledger_path(project_dir: Path | None = None) -> Path:
    return (project_dir or PROJECT_DIR) / LEDGER_RELATIVE


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {
            "schema": LEDGER_SCHEMA,
            "baseline_id": BASELINE_ID,
            "source_sha256": EXPECTED_SOURCE_SHA256,
            "records": {},
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("records", {})
    return payload


def save_ledger(path: Path, ledger: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")


def _retrieved_evidence(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for event in events:
        if event.get("kind") != "observe":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        for group in ("matches", "context_records"):
            for item in payload.get(group) or []:
                if not isinstance(item, dict):
                    continue
                evidence.append(
                    {
                        "group": group,
                        "label": item.get("label"),
                        "record_id": item.get("record_id"),
                        "source_snapshot_id": item.get("source_snapshot_id"),
                        "text_sha256": item.get("text_sha256"),
                        "text": item.get("text"),
                        "query": payload.get("query"),
                    }
                )
    return evidence


def _build_scores(
    annotation: dict[str, Any],
    assertions: dict[str, Any],
    run_id: str,
) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []
    categories = (annotation.get("categories") or {})
    for category, name in REVIEWED_SCORE_NAMES.items():
        scores.append(
            {
                "name": name,
                "value": label_to_score(str(categories[category])),
                "score_id": deterministic_score_id(run_id, name),
                "family": "reviewed",
                "comment": REVIEW_COMMENT,
                "metadata": {
                    "category": category,
                    "original_label": categories[category],
                    "accepted_by": "Lily",
                    "method": REVIEW_COMMENT,
                },
            }
        )
    timing = assertions.get(DEFERRED_DATE_CHECKER_ID) or {}
    scores.append(
        {
            "name": AUTOMATED_TIMING_SCORE,
            "value": label_to_score(str(timing.get("result"))),
            "score_id": deterministic_score_id(run_id, AUTOMATED_TIMING_SCORE),
            "family": "automated",
            "comment": AUTOMATED_COMMENT,
            "metadata": {
                "checker_id": DEFERRED_DATE_CHECKER_ID,
                "applicable": True,
                "original_result": timing.get("result"),
                "reasons": timing.get("reasons") or [],
            },
        }
    )
    s19 = assertions.get(S19_BUDGET_CHECKER_ID) or {}
    if s19.get("applicable") and s19.get("result") in {"pass", "fail"}:
        scores.append(
            {
                "name": AUTOMATED_S19_SCORE,
                "value": label_to_score(str(s19.get("result"))),
                "score_id": deterministic_score_id(run_id, AUTOMATED_S19_SCORE),
                "family": "automated",
                "comment": AUTOMATED_COMMENT,
                "metadata": {
                    "checker_id": S19_BUDGET_CHECKER_ID,
                    "applicable": True,
                    "excluded": False,
                    "original_result": s19.get("result"),
                    "reasons": s19.get("reasons") or [],
                    "evidence": s19.get("evidence") or {},
                },
            }
        )
    return scores


def build_import_jobs(project_dir: Path | None = None) -> dict[str, Any]:
    """Prepare 20 historical jobs from frozen traces and original scores."""
    root = project_dir or PROJECT_DIR
    traces_path = root / DEFAULT_TRACE_RELATIVE
    source_sha = verify_source_hash(traces_path)
    traces = load_traces(traces_path)
    annotations = load_json(root / ANNOTATIONS_RELATIVE)
    results = load_json(root / DEFAULT_RESULTS_RELATIVE)
    annotation_by_run = {
        str(row["run_id"]): row for row in annotations.get("traces") or []
    }
    assertion_by_run = {
        str(row["run_id"]): row for row in results.get("per_trace") or []
    }
    jobs = []
    for trace in traces:
        run_id = str(trace["run_id"])
        scenario_id = str(trace["scenario_id"])
        annotation = annotation_by_run[run_id]
        assertion_row = assertion_by_run[run_id]
        events = visible_events_only(trace.get("events") or [])
        jobs.append(
            redact_value(
                {
                    "baseline_id": BASELINE_ID,
                    "scenario_id": scenario_id,
                    "run_id": run_id,
                    "association_key": association_key(run_id),
                    "langfuse_trace_id": deterministic_trace_id(run_id),
                    "provenance": {
                        "original_run_id": run_id,
                        "original_started_at": trace.get("started_at"),
                        "original_ended_at": trace.get("ended_at"),
                        "original_recorded_at": trace.get("recorded_at"),
                        "original_elapsed_ms": trace.get("elapsed_ms"),
                        "source_sha256": source_sha,
                        "schema_version": trace.get("schema_version"),
                    },
                    "input": trace.get("user_input"),
                    "answer": trace.get("final_output"),
                    "instructions": trace.get("instructions"),
                    "events": events,
                    "evidence": _retrieved_evidence(events),
                    "usage": trace.get("usage"),
                    "configuration": {
                        "model": trace.get("model"),
                        "architecture": trace.get("architecture"),
                        "tool_backend": trace.get("tool_backend"),
                        "execution_limits": trace.get("execution_limits"),
                        "corpus": trace.get("corpus"),
                    },
                    "scores": _build_scores(
                        annotation, assertion_row.get("assertions") or {}, run_id
                    ),
                    "s19_excluded": scenario_id != "TRACE-S19",
                }
            )
        )
    timing = (results.get("deterministic_assertions") or {}).get(
        DEFERRED_DATE_CHECKER_ID
    ) or {}
    s19 = (results.get("deterministic_assertions") or {}).get(
        S19_BUDGET_CHECKER_ID
    ) or {}
    return {
        "schema": SCHEMA,
        "baseline_id": BASELINE_ID,
        "source_sha256": source_sha,
        "n_jobs": len(jobs),
        "jobs": jobs,
        "expected": {
            "n_traces": 20,
            "timing_pass": timing.get("pass"),
            "timing_fail": timing.get("fail"),
            "s19_fail": s19.get("fail"),
            "s19_excluded": s19.get("not_applicable"),
        },
        "review": annotations.get("review") or {},
        "invented": {
            "per_event_timestamps": False,
            "model_generations": False,
            "tool_durations": False,
        },
    }


def _ledger_record(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "scenario_id": job["scenario_id"],
        "run_id": job["run_id"],
        "association_key": job["association_key"],
        "langfuse_trace_id": job["langfuse_trace_id"],
        "status": "pending",
        "score_ids": {row["name"]: row["score_id"] for row in job["scores"]},
        "trace_url": None,
        "uploaded_at": None,
        "verified_at": None,
        "error": None,
        "verified": None,
    }


def already_imported(ledger: dict[str, Any], run_id: str) -> bool:
    row = (ledger.get("records") or {}).get(run_id) or {}
    return row.get("status") in {"uploaded", "verified"}


def already_verified(ledger: dict[str, Any], run_id: str) -> bool:
    row = (ledger.get("records") or {}).get(run_id) or {}
    return row.get("status") == "verified"


def pending_jobs(
    jobs: list[dict[str, Any]],
    ledger: dict[str, Any],
    *,
    need: str,
) -> list[dict[str, Any]]:
    selected = []
    for job in jobs:
        run_id = job["run_id"]
        if need == "upload" and already_imported(ledger, run_id):
            continue
        if need == "verify" and already_verified(ledger, run_id):
            continue
        if need == "verify" and not already_imported(ledger, run_id):
            continue
        selected.append(job)
    return selected


def upload_job(client: Any, job: dict[str, Any]) -> dict[str, Any]:
    """Create application-layer observations and scores. No ADK generations."""
    from langfuse import propagate_attributes

    trace_id = job["langfuse_trace_id"]
    with client.start_as_current_observation(
        as_type="span",
        name=ROOT_SPAN_NAME,
        trace_context={"trace_id": trace_id},
        input=job.get("input"),
        output=job.get("answer"),
        metadata={
            "provenance": job.get("provenance"),
            "configuration": job.get("configuration"),
            "instructions": job.get("instructions"),
            "usage": job.get("usage"),
            "s19_excluded": job.get("s19_excluded"),
        },
    ) as root:
        with propagate_attributes(
            session_id=BASELINE_ID,
            tags=[HISTORICAL_TAG, BASELINE_ID, job["scenario_id"]],
            metadata={
                "association_key": job["association_key"],
                "original_run_id": job["run_id"],
                "import_kind": HISTORICAL_TAG,
            },
            trace_name=f"{ROOT_SPAN_NAME} {job['scenario_id']}",
        ):
            with client.start_as_current_observation(
                as_type="span",
                name=EVENTS_SPAN_NAME,
            ) as events_span:
                events_span.update(output=job.get("events"))
            with client.start_as_current_observation(
                as_type="retriever",
                name=EVIDENCE_SPAN_NAME,
            ) as evidence_span:
                evidence_span.update(output=job.get("evidence"))
            for score in job["scores"]:
                client.create_score(
                    name=score["name"],
                    value=float(score["value"]),
                    trace_id=trace_id,
                    score_id=score["score_id"],
                    data_type="NUMERIC",
                    comment=score["comment"],
                    metadata=score.get("metadata"),
                )
            root.update(output=job.get("answer"))
    return {"trace_id": trace_id}


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


def _score_rows(page: Any) -> list[Any]:
    return list(getattr(page, "data", None) or [])


def _score_map(page: Any) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for item in _score_rows(page):
        name = getattr(item, "name", None)
        value = getattr(item, "value", None)
        if name is None and isinstance(item, dict):
            name = item.get("name")
            value = item.get("value")
        if name is not None:
            mapped[str(name)] = value
    return mapped


def _root_payload(page: Any) -> dict[str, Any]:
    for item in _observation_rows(page):
        name = getattr(item, "name", None)
        if name == ROOT_SPAN_NAME:
            return {
                "input": getattr(item, "input", None),
                "output": getattr(item, "output", None),
                "metadata": getattr(item, "metadata", None),
            }
    return {}


def read_remote(client: Any, trace_id: str) -> dict[str, Any]:
    observations = client.api.observations.get_many(
        trace_id=trace_id, limit=100, fields="core,basic,io"
    )
    scores = None
    score_error = None
    try:
        scores = client.api.scores_v3.get_many_v3(trace_id=trace_id, limit=50)
    except Exception as exc:
        score_error = f"{type(exc).__name__}"
        try:
            scores = client.api.scores.get_many(trace_id=trace_id, limit=50)
            score_error = None
        except Exception as exc2:
            score_error = f"{score_error}+{type(exc2).__name__}"
    return {
        "observation_names": _observation_names(observations),
        "observation_count": len(_observation_rows(observations)),
        "root": _root_payload(observations),
        "scores": _score_map(scores) if scores is not None else {},
        "score_error": score_error,
    }


def verify_job(
    client: Any,
    job: dict[str, Any],
    *,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 3.0,
) -> dict[str, Any]:
    required_obs = [ROOT_SPAN_NAME, EVENTS_SPAN_NAME, EVIDENCE_SPAN_NAME]
    required_scores = {row["name"]: row["value"] for row in job["scores"]}
    deadline = time.monotonic() + timeout_seconds
    started = time.monotonic()
    last: dict[str, Any] = {}
    while time.monotonic() <= deadline:
        last = read_remote(client, job["langfuse_trace_id"])
        missing_obs = [name for name in required_obs if name not in last["observation_names"]]
        missing_scores = [
            name for name in required_scores if name not in last["scores"]
        ]
        mismatched = [
            name
            for name, value in required_scores.items()
            if name in last["scores"]
            and int(float(last["scores"][name])) != int(value)
        ]
        missing_fields = []
        root = last.get("root") or {}
        if root.get("input") in (None, "", {}):
            missing_fields.append("root.input")
        if root.get("output") in (None, "", {}):
            missing_fields.append("root.output")
        if not missing_obs and not missing_scores and not mismatched and not missing_fields:
            return {
                "ok": True,
                "ingestion_delay_seconds": round(time.monotonic() - started, 1),
                "observation_names": last["observation_names"],
                "observation_count": last["observation_count"],
                "score_names": sorted(last["scores"]),
                "score_values": last["scores"],
                "missing_observations": [],
                "missing_scores": [],
                "mismatched_scores": [],
                "missing_fields": [],
                "score_query_error": last.get("score_error"),
            }
        last["missing_observations"] = missing_obs
        last["missing_scores"] = missing_scores
        last["mismatched_scores"] = mismatched
        last["missing_fields"] = missing_fields
        time.sleep(interval_seconds)
    return {
        "ok": False,
        "ingestion_delay_seconds": round(time.monotonic() - started, 1),
        "observation_names": last.get("observation_names") or [],
        "observation_count": last.get("observation_count") or 0,
        "score_names": sorted((last.get("scores") or {})),
        "score_values": last.get("scores") or {},
        "missing_observations": last.get("missing_observations") or required_obs,
        "missing_scores": last.get("missing_scores") or list(required_scores),
        "mismatched_scores": last.get("mismatched_scores") or [],
        "missing_fields": last.get("missing_fields") or [],
        "score_query_error": last.get("score_error"),
        "error": "remote_payload_incomplete",
    }


def import_jobs(
    jobs: list[dict[str, Any]],
    *,
    client: Any,
    ledger: dict[str, Any],
    ledger_path: Path,
    verify: bool = True,
) -> list[dict[str, Any]]:
    outcomes = []
    for job in jobs:
        run_id = job["run_id"]
        record = (ledger.get("records") or {}).get(run_id) or _ledger_record(job)
        ledger.setdefault("records", {})[run_id] = record
        if already_verified(ledger, run_id):
            outcomes.append({"run_id": run_id, "action": "skipped_verified"})
            continue
        try:
            if not already_imported(ledger, run_id):
                upload_job(client, job)
                client.flush()
                record["status"] = "uploaded"
                record["uploaded_at"] = utc_now()
                try:
                    record["trace_url"] = client.get_trace_url(
                        trace_id=job["langfuse_trace_id"]
                    )
                except Exception:
                    record["trace_url"] = None
                save_ledger(ledger_path, ledger)
            if verify:
                checked = verify_job(client, job)
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
                        "run_id": run_id,
                        "scenario_id": job["scenario_id"],
                        "action": "verified" if checked.get("ok") else "verify_incomplete",
                        "trace_id": job["langfuse_trace_id"],
                        "trace_url": record.get("trace_url"),
                        "verified": checked,
                    }
                )
            else:
                outcomes.append(
                    {
                        "run_id": run_id,
                        "scenario_id": job["scenario_id"],
                        "action": "uploaded",
                        "trace_id": job["langfuse_trace_id"],
                        "trace_url": record.get("trace_url"),
                    }
                )
        except Exception as exc:
            record["status"] = "failed"
            record["error"] = type(exc).__name__
            save_ledger(ledger_path, ledger)
            outcomes.append(
                {
                    "run_id": run_id,
                    "scenario_id": job["scenario_id"],
                    "action": "failed",
                    "error": type(exc).__name__,
                }
            )
    return outcomes


def run_import(
    project_dir: Path | None = None,
    *,
    live: bool = False,
) -> dict[str, Any]:
    root = project_dir or PROJECT_DIR
    prepared = build_import_jobs(root)
    ledger_path = default_ledger_path(root)
    ledger = load_ledger(ledger_path)
    ledger["source_sha256"] = prepared["source_sha256"]
    report = {
        "schema": SCHEMA,
        "baseline_id": BASELINE_ID,
        "source_sha256": prepared["source_sha256"],
        "source_sha256_verified": True,
        "config": config_status(),
        "missing_credentials": missing_credential_names(),
        "sdk_available": sdk_available(),
        "ledger_path": str(ledger_path),
        "importer_existed": ledger_path.is_file()
        and bool((load_ledger(ledger_path).get("records") or {})),
        "expected": prepared["expected"],
        "review": prepared["review"],
        "invented": prepared["invented"],
        "pilot": None,
        "remaining": [],
        "counts": {
            "prepared": prepared["n_jobs"],
            "verified": 0,
            "uploaded_unverified": 0,
            "failed": 0,
            "skipped_verified": 0,
        },
        "links": [],
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
    jobs = prepared["jobs"]
    verified_before = [job for job in jobs if already_verified(ledger, job["run_id"])]
    report["counts"]["skipped_verified"] = len(verified_before)
    unverified = [job for job in jobs if not already_verified(ledger, job["run_id"])]
    if unverified:
        pilot = unverified[0]
        if already_imported(ledger, pilot["run_id"]):
            report["pilot"] = import_jobs(
                [pilot],
                client=client,
                ledger=ledger,
                ledger_path=ledger_path,
                verify=True,
            )[0]
        else:
            report["pilot"] = import_jobs(
                [pilot],
                client=client,
                ledger=ledger,
                ledger_path=ledger_path,
                verify=True,
            )[0]
        if report["pilot"].get("action") not in {"verified", "skipped_verified"}:
            report["error"] = "pilot_not_verified"
            _summarize(report, ledger, jobs)
            save_ledger(ledger_path, ledger)
            return report
        rest = [
            job
            for job in jobs
            if job["run_id"] != pilot["run_id"]
            and not already_verified(ledger, job["run_id"])
        ]
        report["remaining"] = import_jobs(
            rest,
            client=client,
            ledger=ledger,
            ledger_path=ledger_path,
            verify=True,
        )
    _summarize(report, ledger, jobs)
    save_ledger(ledger_path, ledger)
    return report


def _summarize(
    report: dict[str, Any], ledger: dict[str, Any], jobs: list[dict[str, Any]]
) -> None:
    verified = []
    uploaded = []
    failed = []
    links = []
    for job in jobs:
        row = (ledger.get("records") or {}).get(job["run_id"]) or {}
        status = row.get("status")
        if status == "verified":
            verified.append(job["run_id"])
        elif status == "uploaded":
            uploaded.append(job["run_id"])
        elif status == "failed":
            failed.append(job["run_id"])
        if row.get("trace_url"):
            links.append(
                {
                    "scenario_id": job["scenario_id"],
                    "run_id": job["run_id"],
                    "trace_id": job["langfuse_trace_id"],
                    "trace_url": row.get("trace_url"),
                    "status": status,
                }
            )
    report["counts"]["verified"] = len(verified)
    report["counts"]["uploaded_unverified"] = len(uploaded)
    report["counts"]["failed"] = len(failed)
    report["links"] = links
