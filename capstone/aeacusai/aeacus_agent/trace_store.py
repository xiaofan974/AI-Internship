"""JSONL TRACE capture for the primary ADK classification preview.

Opt-in capture for `aeacus_preview_agent` with the direct Python
`preview_classification_search` tool. Other agents are not written to
this baseline. This module does not call models, open the review
register, or change retrieval behavior.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - non-Unix
    fcntl = None  # type: ignore[assignment]

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
SCHEMA_VERSION = "aeacus.trace.adk_preview.v1"
ARCHITECTURE = "adk_single_agent_preview"
ALLOWED_AGENT_NAME = "aeacus_preview_agent"
TOOL_BACKEND = "direct_python"
ALLOWED_TOOL_NAME = "preview_classification_search"
DEFAULT_TRACE_FILENAME = "adk_preview.jsonl"
NOT_OBSERVED = "not_observed"

RELEVANT_SOURCE_FILES = (
    "aeacus_agent/trace_store.py",
    "aeacus_agent/preview_agent.py",
    "aeacus_agent/context_preview.py",
    "aeacus_agent/langfuse_preview.py",
    "run_review.py",
    "streamlit_app.py",
    "run_classification_preview.py",
)
CORPUS_ARTIFACTS = (
    "records/classification_children_stage9.json",
    "records/consolidated_articles_stage4.json",
    "records/consolidated_annexes_stage5.json",
)

_ENV_SECRET_KEYS = (
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "PINECONE_API_KEY",
    "SUPABASE_ACCESS_TOKEN",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
)
_SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"pcsk_[0-9A-Za-z\-_]{20,}"),
    re.compile(r"sk-[0-9A-Za-z\-_]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-+=/]{8,}"),
    re.compile(r"(?i)(authorization\s*[:=]\s*)(\S+)"),
)

_PROCESS_LOCK = threading.Lock()


def default_trace_path() -> Path:
    configured = os.getenv("AEACUS_TRACE_PATH", "").strip()
    if configured:
        return Path(configured).expanduser()
    return PROJECT_DIR / "data" / "local" / "traces" / DEFAULT_TRACE_FILENAME


def capture_enabled_from_env(*, default: bool = True) -> bool:
    raw = os.getenv("AEACUS_TRACE_CAPTURE")
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return str(uuid.uuid4())


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact_secret_text(text: str) -> str:
    """Replace known secret values. Does not truncate surrounding text."""
    redacted = str(text)
    for env_key in _ENV_SECRET_KEYS:
        secret = os.getenv(env_key)
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = _SECRET_PATTERNS[0].sub("[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[1].sub("[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[2].sub("[REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[3].sub("Bearer [REDACTED]", redacted)
    redacted = _SECRET_PATTERNS[4].sub(r"\1[REDACTED]", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [redact_value(item) for item in value]
    return value


def empty_human_annotation() -> dict[str, Any]:
    return {
        "annotator": None,
        "notes": None,
        "labels": [],
        "scores": {},
        "reviewed_at": None,
    }


def provider_id_or_none(value: Any) -> str | None:
    """Return a provider tool-call ID only when the object actually has one."""
    if value is None:
        return None
    raw = getattr(value, "id", value) if not isinstance(value, (str, bytes)) else value
    if raw is None:
        return None
    text = str(raw).strip()
    return text or None


class CallAssociator:
    """Pair tool calls with responses without inventing provider IDs."""

    def __init__(self) -> None:
        self._seq = 0
        self._pending: list[dict[str, Any]] = []

    def register_call(self, provider_call_id: str | None) -> dict[str, Any]:
        self._seq += 1
        item = {
            "association_key": f"trace_call_{self._seq}",
            "provider_call_id": provider_id_or_none(provider_call_id),
        }
        self._pending.append(item)
        return dict(item)

    def register_response(self, provider_response_id: str | None) -> dict[str, Any]:
        response_id = provider_id_or_none(provider_response_id)
        if response_id:
            for index, item in enumerate(self._pending):
                if item.get("provider_call_id") == response_id:
                    return dict(self._pending.pop(index))
        if self._pending:
            return dict(self._pending.pop(0))
        self._seq += 1
        return {
            "association_key": f"trace_call_{self._seq}",
            "provider_call_id": response_id,
        }


def git_identity(project_dir: Path | None = None) -> dict[str, Any]:
    root = project_dir or PROJECT_DIR
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).strip()
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            timeout=5,
            stderr=subprocess.DEVNULL,
        )
        return {
            "commit": commit or None,
            "dirty": bool(porcelain.strip()),
            "status": "observed",
        }
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return {
            "commit": None,
            "dirty": None,
            "status": NOT_OBSERVED,
        }


def file_hash_map(relative_paths: tuple[str, ...], *, project_dir: Path | None = None) -> dict[str, Any]:
    root = project_dir or PROJECT_DIR
    items: dict[str, Any] = {}
    for relative in relative_paths:
        path = root / relative
        digest = sha256_file(path)
        items[relative] = {
            "sha256": digest,
            "status": "observed" if digest else "missing",
        }
    return items


def freeze_agent_instructions(agent: Any) -> dict[str, Any]:
    instruction = getattr(agent, "instruction", None)
    if callable(instruction):
        return {
            "text": None,
            "sha256": None,
            "status": "callable_instruction_not_invoked",
        }
    text = "" if instruction is None else str(instruction)
    return {
        "text": text,
        "sha256": sha256_text(text),
        "status": "observed",
    }


def expose_tool_definitions(agent: Any) -> list[dict[str, Any]]:
    definitions: list[dict[str, Any]] = []
    for tool in getattr(agent, "tools", None) or []:
        func = tool
        if not callable(func):
            func = getattr(tool, "func", None) or getattr(tool, "function", None) or tool
        name = getattr(func, "__name__", None) or getattr(tool, "name", None) or "unknown_tool"
        doc = inspect.getdoc(func) if callable(func) else None
        try:
            signature = str(inspect.signature(func)) if callable(func) else None
        except (TypeError, ValueError):
            signature = None
        definitions.append(
            {
                "name": name,
                "backend": TOOL_BACKEND if name == ALLOWED_TOOL_NAME else NOT_OBSERVED,
                "signature": signature,
                "doc": doc,
            }
        )
    return definitions


def extract_usage_metadata(event: Any) -> dict[str, Any] | None:
    raw = getattr(event, "usage_metadata", None)
    if raw is None:
        raw = getattr(event, "usage", None)
    if raw is None:
        return None
    mapping = (
        "prompt_token_count",
        "candidates_token_count",
        "total_token_count",
        "cached_content_token_count",
        "thoughts_token_count",
    )
    fields: dict[str, Any] = {}
    for key in mapping:
        value = raw.get(key) if isinstance(raw, dict) else getattr(raw, key, None)
        if value is not None:
            fields[key] = value
    return fields or None


def usage_summary(usage_events: list[dict[str, Any]]) -> dict[str, Any]:
    observed = [item for item in usage_events if item.get("usage")]
    if not observed:
        return {
            "status": "unknown",
            "prompt_token_count": None,
            "candidates_token_count": None,
            "total_token_count": None,
            "aggregation": None,
            "note": "No usage metadata was present on ADK events. Counts were not invented.",
        }
    last = dict(observed[-1]["usage"])
    return {
        "status": "last_observed",
        "prompt_token_count": last.get("prompt_token_count"),
        "candidates_token_count": last.get("candidates_token_count"),
        "total_token_count": last.get("total_token_count"),
        "aggregation": "last_observed_not_summed",
        "event_count_with_usage": len(observed),
        "note": "Per-event usage may be cumulative. Values were not summed.",
        "last_observed": last,
    }


def corpus_identity() -> dict[str, Any]:
    from aeacus_agent.context_preview import (
        PINNED_CONSOLIDATED_SNAPSHOT_ID,
        STAGE4_ARTICLES_PATH,
        STAGE5_ANNEXES_PATH,
        STAGE9_CHILDREN_PATH,
    )

    return {
        "pinned_snapshot_id": PINNED_CONSOLIDATED_SNAPSHOT_ID,
        "artifacts": {
            "records/classification_children_stage9.json": {
                "path": str(STAGE9_CHILDREN_PATH),
                "sha256": sha256_file(STAGE9_CHILDREN_PATH),
            },
            "records/consolidated_articles_stage4.json": {
                "path": str(STAGE4_ARTICLES_PATH),
                "sha256": sha256_file(STAGE4_ARTICLES_PATH),
            },
            "records/consolidated_annexes_stage5.json": {
                "path": str(STAGE5_ANNEXES_PATH),
                "sha256": sha256_file(STAGE5_ANNEXES_PATH),
            },
        },
    }


def application_outcome(
    *,
    execution_status: str,
    visible_answer: str | None,
    failure_message: str | None,
    pending_review: dict[str, Any] | None = None,
    pending_review_observed: bool = False,
) -> dict[str, Any]:
    if not pending_review_observed:
        pending = {
            "status": NOT_OBSERVED,
            "run_id": None,
            "digest": None,
            "storage": NOT_OBSERVED,
        }
    elif pending_review:
        artifact = pending_review.get("artifact") or {}
        pending = {
            "status": pending_review.get("status") or "review_required",
            "run_id": artifact.get("run_id"),
            "digest": pending_review.get("digest") or artifact.get("content_digest"),
            "storage": "session_local_not_register",
        }
    else:
        pending = {
            "status": "not_created",
            "run_id": None,
            "digest": None,
            "storage": "none",
        }
    if execution_status == "ok" and visible_answer:
        visible_status = "complete"
    elif execution_status in {"failed", "timed_out"}:
        visible_status = "none_partial_discarded"
    else:
        visible_status = "none"
    return {
        "execution_status": execution_status,
        "visible_answer_status": visible_status,
        "failure_message": failure_message,
        "pending_review": pending,
        "register_opened": NOT_OBSERVED,
        "register_written": NOT_OBSERVED,
        "register_note": (
            "Capture does not query the review database. A review_required "
            "status is not proof of a SQLite write."
        ),
    }


def classify_execution_status(result: str | None, *, timed_out: bool = False) -> str:
    if timed_out:
        return "timed_out"
    text = result or ""
    if text.startswith("[FAILED]"):
        if "timed out" in text.lower():
            return "timed_out"
        return "failed"
    if text.strip():
        return "ok"
    return "failed"


@dataclass
class TraceCaptureConfig:
    enabled: bool = False
    allowed_agent_name: str = ALLOWED_AGENT_NAME
    architecture: str = ARCHITECTURE
    tool_backend: str = TOOL_BACKEND
    output_path: Path | None = None
    scenario_id: str | None = None
    entry_point: str = "unknown"
    persist: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    def resolved_path(self) -> Path:
        return Path(self.output_path) if self.output_path else default_trace_path()


@dataclass
class TraceCapture:
    config: TraceCaptureConfig
    run_id: str = field(default_factory=new_run_id)
    associator: CallAssociator = field(default_factory=CallAssociator)
    events: list[dict[str, Any]] = field(default_factory=list)
    usage_events: list[dict[str, Any]] = field(default_factory=list)
    started_at: str | None = None
    ended_at: str | None = None
    started_perf: float | None = None
    elapsed_ms: float | None = None
    record: dict[str, Any] | None = None
    skipped: str | None = None
    persistence: dict[str, Any] = field(
        default_factory=lambda: {
            "saved": False,
            "path": None,
            "error": None,
            "skipped": None,
        }
    )

    @property
    def collecting(self) -> bool:
        return bool(self.config.enabled) and self.skipped is None

    def skip(self, reason: str) -> None:
        self.skipped = reason
        self.persistence["skipped"] = reason
        self.persistence["saved"] = False

    def gate_agent(self, agent: Any) -> bool:
        name = getattr(agent, "name", None)
        if name != self.config.allowed_agent_name:
            self.skip(f"agent_not_in_baseline:{name}")
            return False
        return True


def visible_events_only(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep ordered visible events. Drop hidden thought content."""
    visible: list[dict[str, Any]] = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        if event.get("kind") == "think":
            continue
        if event.get("thought"):
            continue
        cleaned = {
            key: value
            for key, value in event.items()
            if key not in {"thought", "thought_text", "hidden_thought"}
        }
        visible.append(cleaned)
    return visible


def build_trace_record(
    capture: TraceCapture,
    *,
    agent: Any,
    user_input: str,
    max_llm_calls: int,
    timeout_seconds: int,
    result: str | None,
    timed_out: bool = False,
    application_outcome_value: dict[str, Any] | None = None,
) -> dict[str, Any]:
    execution_status = classify_execution_status(result, timed_out=timed_out)
    visible = None if execution_status != "ok" else result
    failure = None if execution_status == "ok" else (result or "[FAILED] Run failed.")
    instructions = freeze_agent_instructions(agent)
    git = git_identity()
    record = {
        "schema_version": SCHEMA_VERSION,
        "run_id": capture.run_id,
        "scenario_id": capture.config.scenario_id,
        "entry_point": capture.config.entry_point,
        "recorded_at": utc_now(),
        "started_at": capture.started_at,
        "ended_at": capture.ended_at or utc_now(),
        "elapsed_ms": capture.elapsed_ms,
        "architecture": capture.config.architecture,
        "agent_name": getattr(agent, "name", None),
        "model": getattr(agent, "model", None),
        "tool_backend": capture.config.tool_backend,
        "execution_limits": {
            "max_llm_calls": max_llm_calls,
            "timeout_seconds": timeout_seconds,
        },
        "instructions": instructions,
        "user_input": user_input,
        "tool_definitions": expose_tool_definitions(agent),
        "code": {
            "git": git,
            "source_files": file_hash_map(RELEVANT_SOURCE_FILES),
        },
        "corpus": corpus_identity(),
        "events": visible_events_only(capture.events),
        "final_output": visible,
        "execution_status": execution_status,
        "error": failure,
        "usage": usage_summary(capture.usage_events),
        "usage_events": list(capture.usage_events),
        "application_outcome": application_outcome_value
        or application_outcome(
            execution_status=execution_status,
            visible_answer=visible,
            failure_message=failure,
            pending_review_observed=False,
        ),
        "human_annotation": empty_human_annotation(),
        "capture": {
            "complete": False,
            "persistence": dict(capture.persistence),
        },
    }
    if capture.config.extra:
        record["baseline"] = dict(capture.config.extra)
    capture.record = redact_value(record)
    return capture.record


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    data = line.encode("utf-8")
    with _PROCESS_LOCK:
        with path.open("ab") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def update_application_outcome(
    capture: TraceCapture, outcome: dict[str, Any]
) -> None:
    if capture.record is None:
        return
    capture.record["application_outcome"] = redact_value(outcome)


def persist_trace(capture: TraceCapture) -> dict[str, Any]:
    """Write one JSONL line. Never reports saved=True on failure."""
    if capture.skipped:
        capture.persistence = {
            "saved": False,
            "path": None,
            "error": None,
            "skipped": capture.skipped,
        }
        if capture.record is not None:
            capture.record.setdefault("capture", {})
            capture.record["capture"]["complete"] = False
            capture.record["capture"]["persistence"] = dict(capture.persistence)
        return capture.persistence
    if not capture.config.enabled or not capture.config.persist:
        capture.persistence = {
            "saved": False,
            "path": None,
            "error": None,
            "skipped": "persist_disabled" if capture.config.enabled else "capture_disabled",
        }
        return capture.persistence
    if capture.record is None:
        capture.persistence = {
            "saved": False,
            "path": None,
            "error": "no_trace_record",
            "skipped": None,
        }
        return capture.persistence
    path = capture.config.resolved_path()
    pending_persistence = {
        "saved": True,
        "path": str(path),
        "error": None,
        "skipped": None,
    }
    to_write = dict(capture.record)
    to_write["capture"] = {
        "complete": True,
        "persistence": dict(pending_persistence),
    }
    try:
        append_jsonl(path, to_write)
    except Exception as exc:
        capture.persistence = {
            "saved": False,
            "path": str(path),
            "error": f"{type(exc).__name__}: {redact_secret_text(str(exc))}",
            "skipped": None,
        }
        capture.record.setdefault("capture", {})
        capture.record["capture"]["complete"] = False
        capture.record["capture"]["persistence"] = dict(capture.persistence)
        return capture.persistence

    capture.record = to_write
    capture.persistence = dict(pending_persistence)
    return capture.persistence


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            records.append(json.loads(text))
    return records
