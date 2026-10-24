"""Application-owned durable project memory policy.

This module does not write the review register, call a model, or treat
memory as legal authority. Writes require an explicit user confirmation
supplied by application code. The model cannot set approval or trusted
source flags.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import os
import re
import secrets
from typing import Any, Protocol
from urllib.parse import urlsplit

from aeacus_agent.trace_store import redact_secret_text

ALLOWED_FIELDS = (
    "project_name",
    "declared_actor_role",
    "preferred_response_language",
)
ACTOR_ROLES = ("provider", "deployer", "both", "unknown")
LANGUAGES = ("English", "French")
LANGUAGE_ALIASES = {
    "english": "English",
    "en": "English",
    "french": "French",
    "fr": "French",
    "francais": "French",
    "français": "French",
}
ALLOWED_WRITE_CHANNEL = "application_confirmed_user"
FORBIDDEN_WRITE_CHANNELS = frozenset(
    {
        "model_answer",
        "retrieved_document",
        "tool_observation",
        "tool_dump",
        "review_register",
        "approval",
        "trusted_source",
    }
)
RESERVED_WORKSPACE_NAMES = frozenset(
    {"user1", "user", "demo", "default", "shared", "admin", "workspace"}
)
SOURCE_USER_DECLARED = "user_declared"
STATUS_ACTIVE = "active"
STATUS_SUPERSEDED = "superseded"
DEFAULT_TTL_DAYS = 180
DEFAULT_SCHEMA = "aeacus_memory"
DATABASE_URL_NAME = "AEACUS_MEMORY_DATABASE_URL"
SCHEMA_NAME = "AEACUS_MEMORY_SCHEMA"
TTL_DAYS_NAME = "AEACUS_MEMORY_TTL_DAYS"
PLACEHOLDER_DSNS = frozenset(
    {
        "",
        "your_postgres_url_here",
        "postgresql://user:password@host:5432/dbname",
    }
)
PROJECT_NAME_MAX = 120
WORKSPACE_CODE_MIN = 16
_SECRET_LIKE = re.compile(
    r"(?i)(AIza[0-9A-Za-z\-_]{20,}|pcsk_[0-9A-Za-z\-_]{20,}|sk-[A-Za-z0-9\-_]{16,}"
    r"|postgres(ql)?://|mysql://|mongodb(\+srv)?://|redis://)"
)
_SCHEMA_OK = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_workspace_code() -> str:
    """Random private workspace code. Do not log this value."""
    return secrets.token_urlsafe(24)


def workspace_id_from_code(workspace_code: str) -> str:
    return hashlib.sha256(workspace_code.encode("utf-8")).hexdigest()


def ttl_days_from_env(env: Any | None = None) -> int:
    raw = (env or os.environ).get(TTL_DAYS_NAME, str(DEFAULT_TTL_DAYS))
    try:
        days = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_TTL_DAYS
    return days if days > 0 else DEFAULT_TTL_DAYS


def schema_from_env(env: Any | None = None) -> str:
    raw = str((env or os.environ).get(SCHEMA_NAME, DEFAULT_SCHEMA) or "").strip()
    if _SCHEMA_OK.match(raw):
        return raw
    return DEFAULT_SCHEMA


def configured_database_url(env: Any | None = None) -> str | None:
    raw = str((env or os.environ).get(DATABASE_URL_NAME, "") or "").strip()
    if raw in PLACEHOLDER_DSNS:
        return None
    return raw


_TLS_OK = frozenset({"require", "verify-ca", "verify-full"})
_TLS_FORBIDDEN = frozenset({"disable", "allow", "prefer"})


def prepare_connect_dsn(dsn: str) -> tuple[str | None, str | None]:
    """Require a resolved URL and TLS. Never log the returned DSN."""
    raw = str(dsn or "").strip()
    if not raw or raw in PLACEHOLDER_DSNS:
        return None, "unconfigured"
    if "${" in raw or "{{" in raw or "}}" in raw:
        return None, "unresolved_database_url"
    try:
        parsed = urlsplit(raw)
        _ = parsed.port
    except ValueError:
        return None, "unresolved_database_url"
    if parsed.scheme not in {"postgres", "postgresql"}:
        return None, "unconfigured"
    if not parsed.hostname:
        return None, "unresolved_database_url"
    match = re.search(r"(?i)sslmode=([a-z0-9-]+)", raw)
    if match:
        mode = match.group(1).lower()
        if mode in _TLS_FORBIDDEN or mode not in _TLS_OK:
            return None, "tls_required"
        return raw, None
    separator = "&" if "?" in raw else "?"
    return f"{raw}{separator}sslmode=require", None


def sanitize_failure(
    exc: BaseException,
    *,
    workspace_code: str | None = None,
    dsn: str | None = None,
) -> str:
    """Return a loggable failure label. Never include codes or DSNs."""
    text = redact_secret_text(f"{type(exc).__name__}: {exc}")
    for secret in (workspace_code, dsn):
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)postgres(ql)?://\S+", "[REDACTED]", text)
    text = re.sub(r"(?i)(password|pwd|user|code)=[^\s,&;]+", r"\1=[REDACTED]", text)
    return text.split(":", 1)[0]


def _reject(reason: str, **extra: Any) -> MemoryResult:
    payload = {
        "ok": False,
        "status": "rejected",
        "durable": False,
        "mocked": extra.pop("mocked", False),
        "unavailable": False,
        "reason": reason,
        "value": None,
        "facts": [],
    }
    payload.update(extra)
    return MemoryResult(**payload)


def _unavailable(reason: str, *, mocked: bool = False) -> MemoryResult:
    return MemoryResult(
        ok=False,
        status="memory_unavailable",
        durable=False,
        mocked=mocked,
        unavailable=True,
        reason=reason,
        value=None,
        facts=[],
    )


@dataclass(frozen=True)
class MemoryResult:
    ok: bool
    status: str
    durable: bool
    mocked: bool
    unavailable: bool
    reason: str | None
    value: str | None
    facts: list[dict[str, Any]]
    field: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "durable": self.durable,
            "mocked": self.mocked,
            "unavailable": self.unavailable,
            "reason": self.reason,
            "field": self.field,
            "value": self.value,
            "facts": list(self.facts),
        }


class MemoryStore(Protocol):
    mocked: bool
    durable: bool

    def fetch_active(self, workspace_id: str, field: str) -> MemoryResult: ...
    def fetch_all_active(self, workspace_id: str) -> MemoryResult: ...
    def persist_replace(
        self, workspace_id: str, field: str, value: str, *, now: datetime, expires_at: datetime
    ) -> MemoryResult: ...
    def persist_delete(self, workspace_id: str, field: str) -> MemoryResult: ...


def authorize_write(*, explicit_user_confirmation: bool, channel: str) -> str | None:
    if channel in FORBIDDEN_WRITE_CHANNELS:
        return "writes_from_that_channel_are_forbidden"
    if channel != ALLOWED_WRITE_CHANNEL:
        return "write_channel_is_not_application_confirmed_user"
    if explicit_user_confirmation is not True:
        return "explicit_user_confirmation_required"
    return None


def validate_workspace_code(workspace_code: str) -> str | None:
    code = str(workspace_code or "").strip()
    if not code:
        return "workspace_code_required"
    if code.lower() in RESERVED_WORKSPACE_NAMES:
        return "workspace_code_must_be_private_random"
    if len(code) < WORKSPACE_CODE_MIN:
        return "workspace_code_too_short"
    return None


def validate_field_value(field: str, value: Any) -> tuple[str, str] | str:
    if field not in ALLOWED_FIELDS:
        return "field_not_allowed"
    if value is None or not isinstance(value, str):
        return "value_must_be_text"
    text = value.strip()
    if not text:
        return "value_required"
    if _SECRET_LIKE.search(text):
        return "value_looks_like_a_secret_or_connection_string"
    if field == "declared_actor_role":
        role = text.lower()
        if role not in ACTOR_ROLES:
            return "actor_role_must_be_provider_deployer_both_or_unknown"
        return field, role
    if field == "preferred_response_language":
        language = LANGUAGE_ALIASES.get(text.lower())
        if language not in LANGUAGES:
            return "language_must_be_english_or_french"
        return field, language
    if len(text) > PROJECT_NAME_MAX:
        return "project_name_too_long"
    if "\x00" in text:
        return "project_name_invalid"
    return field, text


class UnavailableMemoryStore:
    """Explicit non-durable result. Not a session or file fallback."""

    mocked = False
    durable = False

    def __init__(self, reason: str = "unconfigured") -> None:
        self.reason = reason

    def fetch_active(self, workspace_id: str, field: str) -> MemoryResult:
        return _unavailable(self.reason)

    def fetch_all_active(self, workspace_id: str) -> MemoryResult:
        return _unavailable(self.reason)

    def persist_replace(
        self, workspace_id: str, field: str, value: str, *, now: datetime, expires_at: datetime
    ) -> MemoryResult:
        return _unavailable(self.reason)

    def persist_delete(self, workspace_id: str, field: str) -> MemoryResult:
        return _unavailable(self.reason)


def open_memory_store(env: Any | None = None, *, connector: Any | None = None) -> MemoryStore:
    """Return the Postgres store or an explicit unavailable store.

    Never substitutes Streamlit session state or local files.
    """
    from aeacus_agent.memory_postgres import PostgresMemoryStore

    dsn = configured_database_url(env)
    if dsn is None:
        return UnavailableMemoryStore("unconfigured")
    prepared, error = prepare_connect_dsn(dsn)
    if error or prepared is None:
        return UnavailableMemoryStore(error or "unconfigured")
    return PostgresMemoryStore(
        dsn=prepared,
        schema=schema_from_env(env),
        connector=connector,
    )


def _bind_workspace(workspace_code: str) -> tuple[str, str] | MemoryResult:
    problem = validate_workspace_code(workspace_code)
    if problem:
        return _reject(problem)
    return workspace_code, workspace_id_from_code(workspace_code.strip())


def get_fact(store: MemoryStore, *, workspace_code: str, field: str) -> MemoryResult:
    bound = _bind_workspace(workspace_code)
    if isinstance(bound, MemoryResult):
        return bound
    _code, workspace_id = bound
    if field not in ALLOWED_FIELDS:
        return _reject("field_not_allowed", field=field)
    result = store.fetch_active(workspace_id, field)
    if result.unavailable:
        return result
    return MemoryResult(
        ok=result.ok,
        status=result.status,
        durable=store.durable,
        mocked=store.mocked,
        unavailable=False,
        reason=result.reason,
        field=field,
        value=result.value,
        facts=result.facts,
    )


def list_facts(store: MemoryStore, *, workspace_code: str) -> MemoryResult:
    bound = _bind_workspace(workspace_code)
    if isinstance(bound, MemoryResult):
        return bound
    _code, workspace_id = bound
    result = store.fetch_all_active(workspace_id)
    if result.unavailable:
        return result
    return MemoryResult(
        ok=result.ok,
        status=result.status,
        durable=store.durable,
        mocked=store.mocked,
        unavailable=False,
        reason=result.reason,
        value=None,
        facts=result.facts,
    )


def replace_fact(
    store: MemoryStore,
    *,
    workspace_code: str,
    field: str,
    value: str,
    explicit_user_confirmation: bool,
    channel: str,
    trusted_source: Any = None,
    approved: Any = None,
    source: Any = None,
) -> MemoryResult:
    if trusted_source is not None or approved is not None or source is not None:
        return _reject("model_or_caller_may_not_set_trust_or_source_flags")
    gate = authorize_write(
        explicit_user_confirmation=explicit_user_confirmation,
        channel=channel,
    )
    if gate:
        return _reject(gate)
    bound = _bind_workspace(workspace_code)
    if isinstance(bound, MemoryResult):
        return bound
    _code, workspace_id = bound
    validated = validate_field_value(field, value)
    if isinstance(validated, str):
        return _reject(validated, field=field)
    field, canonical = validated
    now = utc_now()
    expires_at = now + timedelta(days=ttl_days_from_env())
    result = store.persist_replace(
        workspace_id,
        field,
        canonical,
        now=now,
        expires_at=expires_at,
    )
    if result.unavailable:
        return result
    return MemoryResult(
        ok=result.ok,
        status=result.status,
        durable=store.durable,
        mocked=store.mocked,
        unavailable=False,
        reason=result.reason,
        field=field,
        value=result.value,
        facts=result.facts,
    )


def delete_fact(
    store: MemoryStore,
    *,
    workspace_code: str,
    field: str,
    explicit_user_confirmation: bool,
    channel: str,
    trusted_source: Any = None,
    approved: Any = None,
    source: Any = None,
) -> MemoryResult:
    if trusted_source is not None or approved is not None or source is not None:
        return _reject("model_or_caller_may_not_set_trust_or_source_flags")
    gate = authorize_write(
        explicit_user_confirmation=explicit_user_confirmation,
        channel=channel,
    )
    if gate:
        return _reject(gate)
    bound = _bind_workspace(workspace_code)
    if isinstance(bound, MemoryResult):
        return bound
    _code, workspace_id = bound
    if field not in ALLOWED_FIELDS:
        return _reject("field_not_allowed", field=field)
    result = store.persist_delete(workspace_id, field)
    if result.unavailable:
        return result
    return MemoryResult(
        ok=result.ok,
        status=result.status,
        durable=store.durable,
        mocked=store.mocked,
        unavailable=False,
        reason=result.reason,
        field=field,
        value=None,
        facts=[],
    )
