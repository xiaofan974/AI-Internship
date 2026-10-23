"""Week 4 ADK preview baseline: freeze, select, and collect traces.

Uses only `aeacus_preview_agent` and the direct Python retrieval tool.
Does not open the review register, retry failed scenarios, or invoke
MCP / dual-agent / LangGraph paths.

Collection support: `BaselinePaths.baseline_id` selects the manifest,
run index, and JSONL. Execution behavior is unchanged. The original
`week4_adk_preview_v1` artifacts are not rewritten.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

from aeacus_agent.agent import DEFAULT_MODEL, MODEL
from aeacus_agent.context_preview import PINNED_CONSOLIDATED_SNAPSHOT_ID
from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION, aeacus_preview_agent
from aeacus_agent.trace_store import (
    PROJECT_DIR,
    TraceCapture,
    TraceCaptureConfig,
    application_outcome,
    expose_tool_definitions,
    file_hash_map,
    freeze_agent_instructions,
    persist_trace,
    sha256_file,
    sha256_text,
    update_application_outcome,
    utc_now,
)
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS, run_review

BASELINE_ID = "week4_adk_preview_v1"
CANDIDATE_F1_ID = "week4_adk_preview_f1_v2"
SCENARIO_FILENAME = "scenarios_v1.json"
UNCHANGED_FROM_PARENT_KEYS = (
    "model",
    "tool_definitions",
    "corpus",
    "generation",
    "execution_limits",
)
EXCLUDED_SCENARIO_IDS = frozenset({"capture_smoke"})
EXPECTED_SCENARIO_COUNT = 20
BATCH1_IDS = tuple(f"TRACE-S{index:02d}" for index in range(1, 6))

IMPLEMENTATION_FILES = (
    "aeacus_agent/preview_agent.py",
    "aeacus_agent/context_preview.py",
    "aeacus_agent/trace_store.py",
    "aeacus_agent/agent.py",
    "run_review.py",
    "evals/week4/baseline.py",
    "run_week4_baseline.py",
)
CORPUS_FILES = (
    "records/classification_children_stage9.json",
    "records/consolidated_articles_stage4.json",
    "records/consolidated_annexes_stage5.json",
)

SYSTEMIC_FAILURE_RE = re.compile(
    r"(UNAUTHENTICATED|PERMISSION_DENIED|RESOURCE_EXHAUSTED|quota|"
    r"API key|api key|401|403|429|authentication|insufficient[_ ]quota|"
    r"capture[- ]persist)",
    re.IGNORECASE,
)

ExecuteFn = Callable[..., Awaitable[str]]


class BaselineError(RuntimeError):
    """Baseline freeze, selection, or collection error."""


class DriftError(BaselineError):
    """Frozen configuration no longer matches the working tree."""


class DuplicateAttemptError(BaselineError):
    """A scenario in this baseline was already attempted."""


class SystemicStop(BaselineError):
    """Auth, quota, or capture-persistence failure; the batch must stop."""


@dataclass
class BaselinePaths:
    project_dir: Path = PROJECT_DIR
    baseline_id: str = BASELINE_ID
    scenarios_path: Path | None = None
    manifest_path: Path | None = None
    run_index_path: Path | None = None
    trace_path: Path | None = None

    def __post_init__(self) -> None:
        root = self.project_dir
        identity = self.baseline_id
        if self.scenarios_path is None:
            self.scenarios_path = root / "evals" / "week4" / SCENARIO_FILENAME
        if self.manifest_path is None:
            self.manifest_path = (
                root / "evals" / "week4" / "baselines" / identity / "manifest.json"
            )
        if self.run_index_path is None:
            self.run_index_path = (
                root / "data" / "local" / "evals" / "week4" / identity / "run_index.json"
            )
        if self.trace_path is None:
            self.trace_path = (
                root / "data" / "local" / "traces" / f"{identity}.jsonl"
            )


@dataclass
class Scenario:
    id: str
    input: str


@dataclass
class AttemptRecord:
    scenario_id: str
    run_id: str | None
    status: str
    started_at: str | None = None
    ended_at: str | None = None
    elapsed_ms: float | None = None
    trace_path: str | None = None
    capture_saved: bool | None = None
    capture_error: str | None = None
    stop_reason: str | None = None
    runner_session_id: str | None = None
    error: str | None = None


@dataclass
class BatchResult:
    baseline_id: str
    phase: str
    dry_run: bool
    selected: list[str]
    attempts: list[AttemptRecord] = field(default_factory=list)
    stopped: bool = False
    stop_reason: str | None = None


def load_scenarios(path: Path) -> list[Scenario]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw.get("scenarios")
    if not isinstance(items, list):
        raise BaselineError(f"Scenario file {path} has no scenarios list.")
    scenarios: list[Scenario] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise BaselineError("Scenario extraction is not a mapping; refusing to rewrite.")
        scenario_id = str(item.get("id") or "").strip()
        text = item.get("input")
        if extra := sorted(set(item) - {"id", "input"}):
            raise BaselineError(
                f"Scenario {scenario_id or '<missing>'} has unexpected fields {extra}."
            )
        if not scenario_id:
            raise BaselineError("A scenario is missing an id.")
        if scenario_id in seen:
            raise BaselineError(f"Duplicate scenario ID {scenario_id}.")
        if not isinstance(text, str) or not text.strip():
            raise BaselineError(f"Scenario {scenario_id} has an empty input.")
        seen.add(scenario_id)
        scenarios.append(Scenario(id=scenario_id, input=text))
    if len(scenarios) != EXPECTED_SCENARIO_COUNT:
        raise BaselineError(
            f"Expected {EXPECTED_SCENARIO_COUNT} scenarios, found {len(scenarios)}."
        )
    return scenarios


def parse_scenario_selector(raw: str | Iterable[str] | None) -> list[str]:
    if raw is None:
        raise BaselineError("Scenario selection is required; refusing to default to all 20.")
    if isinstance(raw, str):
        tokens = [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]
    else:
        tokens = [str(part).strip() for part in raw if str(part).strip()]
    selected: list[str] = []
    for token in tokens:
        if ":" in token:
            start, end = (piece.strip() for piece in token.split(":", 1))
            selected.extend(_inclusive_range(start, end))
            continue
        selected.append(token)
    for scenario_id in selected:
        if scenario_id in EXCLUDED_SCENARIO_IDS:
            raise BaselineError(f"{scenario_id} is excluded from this baseline.")
        if not re.fullmatch(r"TRACE-S\d{2}", scenario_id):
            raise BaselineError(f"Unsupported scenario ID {scenario_id!r}.")
    return list(dict.fromkeys(selected))


def _inclusive_range(start: str, end: str) -> list[str]:
    match_start = re.fullmatch(r"TRACE-S(\d{2})", start)
    match_end = re.fullmatch(r"TRACE-S(\d{2})", end)
    if not match_start or not match_end:
        raise BaselineError(f"Invalid scenario range {start}:{end}.")
    begin = int(match_start.group(1))
    finish = int(match_end.group(1))
    if begin > finish:
        raise BaselineError(f"Invalid scenario range {start}:{end}.")
    return [f"TRACE-S{index:02d}" for index in range(begin, finish + 1)]


def select_scenarios(
    scenarios: list[Scenario], selected_ids: Iterable[str]
) -> list[Scenario]:
    by_id = {item.id: item for item in scenarios}
    chosen: list[Scenario] = []
    for scenario_id in selected_ids:
        if scenario_id not in by_id:
            raise BaselineError(f"Unknown scenario ID {scenario_id}.")
        chosen.append(by_id[scenario_id])
    return chosen


def _tool_definition_hash(agent: Any) -> str:
    payload = json.dumps(
        expose_tool_definitions(agent),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return sha256_text(payload)


def snapshot_frozen_configuration(paths: BaselinePaths) -> dict[str, Any]:
    scenarios = load_scenarios(paths.scenarios_path)
    instructions = freeze_agent_instructions(aeacus_preview_agent)
    generate_content_config = getattr(
        aeacus_preview_agent, "generate_content_config", None
    )
    return {
        "baseline_id": paths.baseline_id,
        "architecture": "adk_single_agent_preview",
        "agent_name": aeacus_preview_agent.name,
        "tool_backend": "direct_python",
        "excluded_from_baseline": sorted(EXCLUDED_SCENARIO_IDS),
        "scenarios": {
            "path": (
                str(paths.scenarios_path.relative_to(paths.project_dir))
                if paths.scenarios_path.is_relative_to(paths.project_dir)
                else str(paths.scenarios_path)
            ),
            "sha256": sha256_file(paths.scenarios_path),
            "count": len(scenarios),
            "ids": [item.id for item in scenarios],
        },
        "model": {
            "name": aeacus_preview_agent.model,
            "default_model": DEFAULT_MODEL,
            "env_model": MODEL,
        },
        "generation": {
            "generate_content_config": generate_content_config,
            "generate_content_config_status": (
                "not_set_on_agent"
                if generate_content_config is None
                else "observed"
            ),
            "run_config": {"max_llm_calls": MAX_LLM_CALLS},
            "timeout_seconds": RUN_TIMEOUT_SECONDS,
        },
        "instructions": {
            "sha256": instructions["sha256"],
            "status": instructions["status"],
        },
        "tool_definitions": {
            "sha256": _tool_definition_hash(aeacus_preview_agent),
            "names": [item["name"] for item in expose_tool_definitions(aeacus_preview_agent)],
        },
        "implementation_files": file_hash_map(
            IMPLEMENTATION_FILES, project_dir=paths.project_dir
        ),
        "corpus": {
            "pinned_snapshot_id": PINNED_CONSOLIDATED_SNAPSHOT_ID,
            "artifacts": file_hash_map(CORPUS_FILES, project_dir=paths.project_dir),
        },
        "execution_limits": {
            "max_llm_calls": MAX_LLM_CALLS,
            "timeout_seconds": RUN_TIMEOUT_SECONDS,
        },
        "trace_path": str(paths.trace_path),
        "scenario_attempts": {item.id: None for item in scenarios},
        "frozen_at": utc_now(),
    }


def freeze_baseline(
    paths: BaselinePaths, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    if paths.manifest_path.exists():
        raise BaselineError(
            f"Manifest already exists at {paths.manifest_path}. "
            "Refusing to overwrite frozen configuration."
        )
    manifest = snapshot_frozen_configuration(paths)
    if extra:
        for key in extra:
            if key in manifest and key != "baseline_id":
                raise BaselineError(
                    f"Refusing to overwrite snapshot field {key!r} with extra metadata."
                )
        manifest.update(extra)
    paths.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def candidate_parent_extra(
    paths: BaselinePaths,
    parent_paths: BaselinePaths,
    *,
    instruction_diff_path: Path | None = None,
) -> dict[str, Any]:
    """Document an instruction-only candidate. Does not rewrite the parent."""
    parent = load_manifest(parent_paths)
    current = snapshot_frozen_configuration(paths)
    mismatches = [
        key
        for key in UNCHANGED_FROM_PARENT_KEYS
        if current.get(key) != parent.get(key)
    ]
    if current.get("scenarios", {}).get("sha256") != parent.get("scenarios", {}).get(
        "sha256"
    ):
        mismatches.append("scenarios.sha256")
    if mismatches:
        raise BaselineError(
            "Candidate must keep model, tools, corpus, generation, limits, "
            f"and the frozen scenario-file hash unchanged. Drift: {mismatches}"
        )
    parent_instruction = (parent.get("instructions") or {}).get("sha256")
    candidate_instruction = (current.get("instructions") or {}).get("sha256")
    if not parent_instruction or parent_instruction == candidate_instruction:
        raise BaselineError(
            "Candidate freeze requires an intentional instruction-hash change."
        )
    diff_relative = None
    if instruction_diff_path is not None:
        if instruction_diff_path.is_relative_to(paths.project_dir):
            diff_relative = str(
                instruction_diff_path.relative_to(paths.project_dir)
            )
        else:
            diff_relative = str(instruction_diff_path)
    return {
        "parent_baseline_id": parent["baseline_id"],
        "parent_manifest": (
            str(parent_paths.manifest_path.relative_to(paths.project_dir))
            if parent_paths.manifest_path.is_relative_to(paths.project_dir)
            else str(parent_paths.manifest_path)
        ),
        "change": {
            "kind": "instruction_only",
            "target": "F1",
            "instruction_sha256_parent": parent_instruction,
            "instruction_sha256_candidate": candidate_instruction,
            "instruction_diff_path": diff_relative,
            "note": (
                "Intentional instruction change for F1. Model, tools, corpus, "
                "generation configuration, and limits are unchanged. The parent "
                "manifest is not rewritten; its instruction mismatch is expected."
            ),
        },
        "unchanged_from_parent": {
            "model": True,
            "tool_definitions": True,
            "corpus": True,
            "generation": True,
            "execution_limits": True,
            "scenarios.sha256": True,
        },
    }


def load_manifest(paths: BaselinePaths) -> dict[str, Any]:
    if not paths.manifest_path.is_file():
        raise BaselineError(f"Frozen manifest not found: {paths.manifest_path}")
    return json.loads(paths.manifest_path.read_text(encoding="utf-8"))


def verify_no_drift(paths: BaselinePaths) -> dict[str, Any]:
    frozen = load_manifest(paths)
    current = snapshot_frozen_configuration(paths)
    compared_keys = (
        "baseline_id",
        "architecture",
        "agent_name",
        "tool_backend",
        "scenarios",
        "model",
        "generation",
        "instructions",
        "tool_definitions",
        "implementation_files",
        "corpus",
        "execution_limits",
    )
    mismatches: list[str] = []
    for key in compared_keys:
        if frozen.get(key) != current.get(key):
            mismatches.append(key)
    if mismatches:
        raise DriftError(
            "Frozen baseline no longer matches the working tree: "
            + ", ".join(mismatches)
            + ". Stopping without updating the manifest."
        )
    return frozen


def load_run_index(paths: BaselinePaths) -> dict[str, Any]:
    if not paths.run_index_path.is_file():
        return {
            "baseline_id": paths.baseline_id,
            "attempts": {},
            "updated_at": None,
        }
    return json.loads(paths.run_index_path.read_text(encoding="utf-8"))


def save_run_index(paths: BaselinePaths, index: dict[str, Any]) -> None:
    paths.run_index_path.parent.mkdir(parents=True, exist_ok=True)
    index["updated_at"] = utc_now()
    paths.run_index_path.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def already_attempted(index: dict[str, Any], scenario_id: str) -> bool:
    attempt = (index.get("attempts") or {}).get(scenario_id)
    return attempt is not None


def _write_attempt(paths: BaselinePaths, record: AttemptRecord) -> None:
    index = load_run_index(paths)
    index.setdefault("attempts", {})[record.scenario_id] = {
        "run_id": record.run_id,
        "status": record.status,
        "started_at": record.started_at,
        "ended_at": record.ended_at,
        "elapsed_ms": record.elapsed_ms,
        "trace_path": record.trace_path,
        "capture_saved": record.capture_saved,
        "capture_error": record.capture_error,
        "stop_reason": record.stop_reason,
        "runner_session_id": record.runner_session_id,
        "error": record.error,
    }
    save_run_index(paths, index)


def is_systemic_failure(message: str | None, *, capture_saved: bool | None) -> str | None:
    if capture_saved is False:
        return "capture_persistence_failed"
    text = message or ""
    if SYSTEMIC_FAILURE_RE.search(text):
        return "provider_auth_or_quota"
    return None


def observation_completeness(record: dict[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {
            "complete_original_observations": False,
            "observe_events": 0,
            "reason": "no_trace_record",
        }
    observes = [
        event
        for event in record.get("events") or []
        if event.get("kind") == "observe"
    ]
    if not observes:
        return {
            "complete_original_observations": False,
            "observe_events": 0,
            "reason": "no_observe_events",
        }
    missing: list[str] = []
    for event in observes:
        payload = event.get("payload") or {}
        groups = list(payload.get("matches") or []) + list(
            payload.get("context_records") or []
        )
        if not groups:
            missing.append("empty_observation_payload")
            continue
        for item in groups:
            if not isinstance(item, dict):
                missing.append("non_object_record")
                continue
            if not item.get("text"):
                missing.append("missing_text")
            if not item.get("text_sha256"):
                missing.append("missing_text_sha256")
            if not item.get("record_id"):
                missing.append("missing_record_id")
            if not item.get("source_snapshot_id"):
                missing.append("missing_source_snapshot_id")
    unique_missing = list(dict.fromkeys(missing))
    return {
        "complete_original_observations": not unique_missing,
        "observe_events": len(observes),
        "missing": unique_missing,
        "reason": None if not unique_missing else ",".join(unique_missing),
    }


def classify_result(result: str | None) -> str:
    text = result or ""
    if text.startswith("[FAILED]") and "timed out" in text.lower():
        return "timed_out"
    if text.startswith("[FAILED]"):
        return "failed"
    if text.strip():
        return "ok"
    return "failed"


async def default_execute(
    system_description: str,
    *,
    capture: TraceCapture,
    agent=aeacus_preview_agent,
) -> str:
    return await run_review(
        system_description,
        agent=agent,
        max_llm_calls=MAX_LLM_CALLS,
        timeout_seconds=RUN_TIMEOUT_SECONDS,
        capture=capture,
    )


async def collect_batch(
    *,
    paths: BaselinePaths,
    selected_ids: Iterable[str],
    phase: str,
    dry_run: bool = False,
    execute: ExecuteFn | None = None,
    agent=aeacus_preview_agent,
    provider_call_counter: list[int] | None = None,
) -> BatchResult:
    frozen = verify_no_drift(paths)
    scenarios = select_scenarios(load_scenarios(paths.scenarios_path), selected_ids)
    result = BatchResult(
        baseline_id=frozen["baseline_id"],
        phase=phase,
        dry_run=dry_run,
        selected=[item.id for item in scenarios],
    )
    if dry_run:
        return result

    executor = execute or default_execute
    index = load_run_index(paths)
    for scenario in scenarios:
        if already_attempted(index, scenario.id):
            raise DuplicateAttemptError(
                f"{scenario.id} was already attempted in baseline {paths.baseline_id}."
            )
        runner_session_id = str(uuid.uuid4())
        capture = TraceCapture(
            config=TraceCaptureConfig(
                enabled=True,
                persist=False,
                output_path=paths.trace_path,
                scenario_id=scenario.id,
                entry_point="evals.week4.baseline.collect_batch",
                extra={
                    "id": paths.baseline_id,
                    "phase": phase,
                    "scenario_id": scenario.id,
                    "runner_session_id": runner_session_id,
                },
            )
        )
        attempt = AttemptRecord(
            scenario_id=scenario.id,
            run_id=capture.run_id,
            status="in_progress",
            started_at=utc_now(),
            runner_session_id=runner_session_id,
        )
        _write_attempt(paths, attempt)
        index = load_run_index(paths)
        if provider_call_counter is not None:
            provider_call_counter.append(1)
        try:
            answer = await executor(
                scenario.input,
                capture=capture,
                agent=agent,
            )
        except Exception as exc:
            answer = (
                f"[FAILED] Provider/execution failure ({type(exc).__name__}): {exc}"
            )
            attempt.error = answer
            attempt.status = "interrupted"
        else:
            attempt.status = classify_result(answer)
            attempt.error = None if attempt.status == "ok" else answer

        if capture.record is not None:
            visible = answer if attempt.status == "ok" else None
            update_application_outcome(
                capture,
                application_outcome(
                    execution_status=attempt.status,
                    visible_answer=visible,
                    failure_message=None if attempt.status == "ok" else answer,
                    pending_review=None,
                    pending_review_observed=True,
                ),
            )
            capture.config.persist = True
            persistence = persist_trace(capture)
            attempt.capture_saved = bool(persistence.get("saved"))
            attempt.capture_error = persistence.get("error")
            attempt.trace_path = persistence.get("path")
            attempt.elapsed_ms = capture.elapsed_ms
            attempt.ended_at = capture.ended_at
            attempt.run_id = capture.run_id
        else:
            attempt.capture_saved = False
            attempt.capture_error = "no_trace_record"
            attempt.ended_at = utc_now()

        stop_reason = is_systemic_failure(
            attempt.error, capture_saved=attempt.capture_saved
        )
        attempt.stop_reason = stop_reason
        _write_attempt(paths, attempt)
        result.attempts.append(attempt)
        index = load_run_index(paths)
        if stop_reason:
            result.stopped = True
            result.stop_reason = stop_reason
            raise SystemicStop(
                f"Stopping batch after {scenario.id}: {stop_reason}. "
                "Available evidence was preserved. No further provider calls."
            )
    return result
