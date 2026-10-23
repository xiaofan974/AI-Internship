"""Opt-in Langfuse export for the primary ADK classification preview.

Uses the current OpenTelemetry Langfuse Python SDK and
`GoogleADKInstrumentor`. Other architectures are not instrumented.
Local JSONL capture remains the source of record. A Langfuse failure is
reported without changing the assessment or approval outcome.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from dotenv import load_dotenv

from aeacus_agent.trace_store import (
    PROJECT_DIR,
    ALLOWED_AGENT_NAME,
    redact_secret_text,
    redact_value,
    visible_events_only,
)

LANGFUSE_PUBLIC_KEY = "LANGFUSE_PUBLIC_KEY"
LANGFUSE_SECRET_KEY = "LANGFUSE_SECRET_KEY"
LANGFUSE_BASE_URL = "LANGFUSE_BASE_URL"
TRACING_FLAG = "AEACUS_LANGFUSE_TRACING"
PLACEHOLDERS = {
    LANGFUSE_PUBLIC_KEY: {"", "your_langfuse_public_key_here"},
    LANGFUSE_SECRET_KEY: {"", "your_langfuse_secret_key_here"},
    LANGFUSE_BASE_URL: {""},
}
DEFAULT_BASE_URL = "https://cloud.langfuse.com"
ROOT_SPAN_NAME = "aeacus-adk-preview"
EVIDENCE_SPAN_NAME = "application-evidence"
TIMING_SPAN_NAME = "timing-renderer"
THOUGHT_KEYS = {"thought", "thought_text", "hidden_thought"}
EXPECTED_APPLICATION_SPANS = (ROOT_SPAN_NAME, EVIDENCE_SPAN_NAME)

_LOCK = threading.Lock()
_CLIENT = None
_INSTRUMENTOR = None
_ENV_LOADED = False


def load_project_env() -> None:
    """Load this project's .env from its directory. Do not override process env."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    load_dotenv(PROJECT_DIR / ".env", override=False)
    _ENV_LOADED = True


def _raw_env(name: str) -> str:
    load_project_env()
    return os.getenv(name, "").strip().strip('"').strip("'")


def _value_configured(name: str) -> bool:
    return _raw_env(name) not in PLACEHOLDERS.get(name, {""})


def config_status() -> dict[str, str]:
    """Report configuration names only. Never include values."""
    status = {
        LANGFUSE_PUBLIC_KEY: "configured" if _value_configured(LANGFUSE_PUBLIC_KEY) else "missing",
        LANGFUSE_SECRET_KEY: "configured" if _value_configured(LANGFUSE_SECRET_KEY) else "missing",
        LANGFUSE_BASE_URL: "configured" if _value_configured(LANGFUSE_BASE_URL) else "missing",
        TRACING_FLAG: "configured" if _raw_env(TRACING_FLAG) else "missing",
    }
    return status


def missing_credential_names() -> list[str]:
    names = []
    if not _value_configured(LANGFUSE_PUBLIC_KEY):
        names.append(LANGFUSE_PUBLIC_KEY)
    if not _value_configured(LANGFUSE_SECRET_KEY):
        names.append(LANGFUSE_SECRET_KEY)
    return names


def tracing_opted_in() -> bool:
    if os.getenv("AEACUS_UI_DISABLE_LIVE") == "1":
        return False
    return _raw_env(TRACING_FLAG).lower() in {"1", "true", "yes", "on"}


def credentials_configured() -> bool:
    return not missing_credential_names()


def sdk_available() -> bool:
    try:
        import langfuse  # noqa: F401
        from openinference.instrumentation.google_adk import (  # noqa: F401
            GoogleADKInstrumentor,
        )
    except ImportError:
        return False
    return True


def tracing_enabled() -> bool:
    return tracing_opted_in() and credentials_configured() and sdk_available()


def empty_export_status() -> dict[str, Any]:
    return {
        "attempted": False,
        "enabled": False,
        "sdk_available": sdk_available(),
        "opted_in": tracing_opted_in(),
        "credentials_configured": credentials_configured(),
        "config": config_status(),
        "missing": missing_credential_names(),
        "instrumented": False,
        "duplicate_instrumentation": False,
        "flushed": False,
        "retrieved": False,
        "exported": False,
        "authenticated": None,
        "trace_id": None,
        "trace_url": None,
        "observation_names": [],
        "missing_observations": [],
        "error": None,
        "architecture": "adk_single_agent_preview",
        "agent_name": ALLOWED_AGENT_NAME,
    }


def _strip_thoughts(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_thoughts(item)
            for key, item in value.items()
            if str(key).lower() not in THOUGHT_KEYS
        }
    if isinstance(value, list):
        return [_strip_thoughts(item) for item in value]
    return value


def _thought_attribute(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in THOUGHT_KEYS)


def _mask_data(*, data: Any, **kwargs: Any) -> Any:
    return redact_value(_strip_thoughts(data))


def _mask_otel_spans(*, params: Any, **kwargs: Any) -> Any:
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches = {}
    for identifier, span in (getattr(params, "spans", None) or {}).items():
        delete: list[str] = []
        replace: dict[str, Any] = {}
        attributes = getattr(span, "attributes", None) or {}
        for key, value in attributes.items():
            if _thought_attribute(str(key)):
                delete.append(str(key))
                continue
            if isinstance(value, str):
                redacted = redact_secret_text(value)
                if redacted != value:
                    replace[str(key)] = redacted
            elif isinstance(value, (list, tuple)):
                redacted_seq = [
                    redact_secret_text(item) if isinstance(item, str) else item
                    for item in value
                ]
                if redacted_seq != list(value):
                    replace[str(key)] = redacted_seq
        if delete or replace:
            patches[identifier] = OtelSpanPatch(
                set_attributes=replace,
                delete_attributes=tuple(delete),
            )
    if not patches:
        return None
    return MaskOtelSpansResult(span_patches=patches)


def ensure_client():
    """Create the Langfuse client once with redaction hooks."""
    global _CLIENT
    with _LOCK:
        if _CLIENT is not None:
            return _CLIENT
        from langfuse import Langfuse

        load_project_env()
        _CLIENT = Langfuse(
            public_key=_raw_env(LANGFUSE_PUBLIC_KEY) or None,
            secret_key=_raw_env(LANGFUSE_SECRET_KEY) or None,
            base_url=_raw_env(LANGFUSE_BASE_URL) or DEFAULT_BASE_URL,
            tracing_enabled=True,
            mask=_mask_data,
            mask_otel_spans=_mask_otel_spans,
        )
        return _CLIENT


def ensure_instrumented() -> dict[str, bool]:
    """Instrument google.adk once. Safe across Streamlit reruns."""
    global _INSTRUMENTOR
    with _LOCK:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        if _INSTRUMENTOR is None:
            _INSTRUMENTOR = GoogleADKInstrumentor()
        if _INSTRUMENTOR.is_instrumented_by_opentelemetry:
            return {"instrumented": True, "duplicate": True}
        _INSTRUMENTOR.instrument()
        return {
            "instrumented": bool(_INSTRUMENTOR.is_instrumented_by_opentelemetry),
            "duplicate": False,
        }


def auth_check_readonly() -> dict[str, Any]:
    """Read-only credential check. Does not create traces."""
    result = {
        "ok": False,
        "config": config_status(),
        "missing": missing_credential_names(),
        "error": None,
    }
    if result["missing"]:
        result["error"] = "missing_credentials"
        return result
    if not sdk_available():
        result["error"] = "sdk_unavailable"
        return result
    try:
        client = ensure_client()
        result["ok"] = bool(client.auth_check())
        if not result["ok"]:
            result["error"] = "authentication_failed"
    except Exception as exc:
        result["ok"] = False
        result["error"] = f"{type(exc).__name__}: {redact_secret_text(str(exc))}"
    return result


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
                        "tool": event.get("tool"),
                        "association_key": event.get("association_key"),
                    }
                )
    return evidence


def build_export_payload(
    capture: Any,
    *,
    raw_answer: str | None,
    delivered_answer: str | None,
    timing_repair: dict[str, Any] | None,
    error: str | None = None,
) -> dict[str, Any]:
    """Application-layer payload after local redaction and thought filtering."""
    record = getattr(capture, "record", None) or {}
    events = visible_events_only(record.get("events") or getattr(capture, "events", None) or [])
    payload = {
        "input": record.get("user_input"),
        "instructions": record.get("instructions"),
        "configuration": {
            "run_id": getattr(capture, "run_id", None) or record.get("run_id"),
            "scenario_id": record.get("scenario_id"),
            "entry_point": record.get("entry_point"),
            "architecture": record.get("architecture"),
            "agent_name": record.get("agent_name"),
            "model": record.get("model"),
            "tool_backend": record.get("tool_backend"),
            "execution_limits": record.get("execution_limits"),
            "corpus": record.get("corpus"),
            "code": record.get("code"),
        },
        "events": events,
        "retrieved_evidence": _retrieved_evidence(events),
        "raw_answer": raw_answer,
        "delivered_answer": delivered_answer,
        "timing_repair": timing_repair,
        "usage": record.get("usage"),
        "execution_status": record.get("execution_status"),
        "error": error or record.get("error"),
    }
    return redact_value(_strip_thoughts(payload))


def _observation_names(items: Any) -> list[str]:
    names: list[str] = []
    rows = items
    if hasattr(items, "data"):
        rows = items.data
    for item in rows or []:
        name = getattr(item, "name", None)
        if name is None and isinstance(item, dict):
            name = item.get("name")
        if name and name not in names:
            names.append(str(name))
    return names


def retrieve_observations(
    client: Any,
    trace_id: str,
    *,
    timeout_seconds: float = 45.0,
    interval_seconds: float = 3.0,
    required_names: tuple[str, ...] = (),
) -> tuple[list[str], str | None]:
    """Poll Observations API v2 until required names appear, or time out."""
    deadline = time.monotonic() + timeout_seconds
    last_error = None
    best: list[str] = []
    while time.monotonic() <= deadline:
        try:
            page = client.api.observations.get_many(
                trace_id=trace_id,
                limit=100,
                fields="core,basic",
            )
            names = _observation_names(page)
            if names:
                best = names
                if not required_names or all(name in names for name in required_names):
                    return names, None
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {redact_secret_text(str(exc))}"
        time.sleep(interval_seconds)
    if best and required_names and any(name not in best for name in required_names):
        return best, "incomplete_observation_set"
    if best:
        return best, None
    return [], last_error or "trace_not_retrievable"


class PreviewLangfuseSession:
    """One primary-preview run. Failures never raise into the assessment path."""

    def __init__(
        self,
        *,
        run_id: str | None,
        entry_point: str,
        verify_remote: bool = False,
    ) -> None:
        self.run_id = run_id
        self.entry_point = entry_point
        self.verify_remote = verify_remote
        self.status = empty_export_status()
        self.active = False
        self.client = None
        self._root_cm = None
        self._prop_cm = None
        self._root = None
        self.payload: dict[str, Any] | None = None

    def __enter__(self) -> "PreviewLangfuseSession":
        self.status["enabled"] = tracing_enabled()
        if not tracing_opted_in():
            return self
        self.status["attempted"] = True
        if not credentials_configured():
            self.status["error"] = "missing_credentials"
            return self
        if not sdk_available():
            self.status["error"] = "sdk_unavailable"
            return self
        try:
            from langfuse import Langfuse, propagate_attributes

            self.client = ensure_client()
            instrument = ensure_instrumented()
            self.status["instrumented"] = instrument["instrumented"]
            self.status["duplicate_instrumentation"] = instrument["duplicate"]
            trace_id = Langfuse.create_trace_id()
            self.status["trace_id"] = trace_id
            self._root_cm = self.client.start_as_current_observation(
                as_type="agent",
                name=ROOT_SPAN_NAME,
                trace_context={"trace_id": trace_id},
            )
            self._root = self._root_cm.__enter__()
            self._prop_cm = propagate_attributes(
                session_id=self.run_id,
                tags=["aeacusai", "adk-preview", "week4-langfuse-connection"],
                metadata={
                    "architecture": "adk_single_agent_preview",
                    "agent_name": ALLOWED_AGENT_NAME,
                    "entry_point": self.entry_point,
                    "run_id": self.run_id,
                },
                version="aeacus.trace.adk_preview.v1",
                trace_name=ROOT_SPAN_NAME,
            )
            self._prop_cm.__enter__()
            self.active = True
        except Exception as exc:
            self.active = False
            self.status["error"] = (
                f"{type(exc).__name__}: {redact_secret_text(str(exc))}"
            )
            self._safe_close_context(self._prop_cm, None, None, None)
            self._safe_close_context(self._root_cm, None, None, None)
        return self

    def complete(
        self,
        capture: Any,
        *,
        raw_answer: str | None,
        delivered_answer: str | None,
        timing_repair: dict[str, Any] | None,
        error: str | None = None,
    ) -> None:
        self.payload = build_export_payload(
            capture,
            raw_answer=raw_answer,
            delivered_answer=delivered_answer,
            timing_repair=timing_repair,
            error=error,
        )
        if not self.active or self._root is None or self.client is None:
            return
        try:
            self._root.update(
                input=self.payload.get("input"),
                output=(
                    self.payload.get("delivered_answer")
                    or self.payload.get("raw_answer")
                    or self.payload.get("error")
                ),
                metadata={
                    "instructions": self.payload.get("instructions"),
                    "configuration": self.payload.get("configuration"),
                    "usage": self.payload.get("usage"),
                    "execution_status": self.payload.get("execution_status"),
                },
            )
            with self.client.start_as_current_observation(
                as_type="retriever",
                name=EVIDENCE_SPAN_NAME,
            ) as evidence_span:
                evidence_span.update(
                    input={"query_events": [
                        {
                            "tool": item.get("tool"),
                            "query": item.get("query"),
                        }
                        for item in self.payload.get("retrieved_evidence") or []
                    ]},
                    output=self.payload.get("retrieved_evidence"),
                    metadata={"events": self.payload.get("events")},
                )
            if self.payload.get("timing_repair"):
                with self.client.start_as_current_observation(
                    as_type="span",
                    name=TIMING_SPAN_NAME,
                ) as timing_span:
                    repair = self.payload["timing_repair"]
                    timing_span.update(
                        input={"raw_output": repair.get("raw_output")},
                        output={"delivered_output": repair.get("delivered_output")},
                        metadata={
                            key: value
                            for key, value in repair.items()
                            if key not in {"raw_output", "delivered_output"}
                        },
                    )
        except Exception as exc:
            self.status["error"] = (
                f"{type(exc).__name__}: {redact_secret_text(str(exc))}"
            )

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if self.active and self.client is not None:
                self._safe_close_context(self._prop_cm, exc_type, exc, tb)
                self._safe_close_context(self._root_cm, exc_type, exc, tb)
                self.client.flush()
                self.status["flushed"] = True
                if self.verify_remote and self.status.get("trace_id"):
                    expected = list(EXPECTED_APPLICATION_SPANS)
                    if (self.payload or {}).get("timing_repair"):
                        expected.append(TIMING_SPAN_NAME)
                    names, retrieve_error = retrieve_observations(
                        self.client,
                        self.status["trace_id"],
                        required_names=tuple(expected),
                    )
                    self.status["observation_names"] = names
                    self.status["missing_observations"] = [
                        name for name in expected if name not in names
                    ]
                    self.status["retrieved"] = bool(names) and not self.status["missing_observations"]
                    if retrieve_error and not self.status["retrieved"]:
                        self.status["error"] = retrieve_error
                    try:
                        self.status["trace_url"] = self.client.get_trace_url(
                            trace_id=self.status["trace_id"]
                        )
                    except Exception:
                        self.status["trace_url"] = None
                self.status["exported"] = bool(
                    self.status["flushed"]
                    and (self.status["retrieved"] if self.verify_remote else True)
                )
                if self.verify_remote and not self.status["retrieved"]:
                    self.status["exported"] = False
                    if not self.status.get("error"):
                        self.status["error"] = (
                            "Trace was flushed but not retrievable from Langfuse."
                        )
        except Exception as flush_exc:
            self.status["flushed"] = False
            self.status["exported"] = False
            self.status["error"] = (
                f"{type(flush_exc).__name__}: {redact_secret_text(str(flush_exc))}"
            )
        if self.payload is None and exc is not None:
            self.status["error"] = (
                self.status.get("error")
                or f"{type(exc).__name__}: {redact_secret_text(str(exc))}"
            )
        return False

    @staticmethod
    def _safe_close_context(cm: Any, exc_type, exc, tb) -> None:
        if cm is None:
            return
        try:
            cm.__exit__(exc_type, exc, tb)
        except Exception:
            pass


def attach_status(capture: Any, status: dict[str, Any]) -> None:
    if capture is None:
        return
    if getattr(capture, "record", None) is None:
        capture.record = {}
    capture.record["langfuse"] = redact_value(dict(status))


def export_status_for_ui(status: dict[str, Any] | None) -> dict[str, Any]:
    """Public UI fields. No secrets."""
    row = status or empty_export_status()
    return {
        "attempted": bool(row.get("attempted")),
        "exported": bool(row.get("exported")),
        "flushed": bool(row.get("flushed")),
        "retrieved": bool(row.get("retrieved")),
        "trace_id": row.get("trace_id"),
        "trace_url": row.get("trace_url"),
        "error": row.get("error"),
        "missing": list(row.get("missing") or []),
        "config": dict(row.get("config") or {}),
    }
