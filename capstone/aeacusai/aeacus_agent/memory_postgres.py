"""External Postgres adapter for project memory.

Uses parameterized queries only. Does not log the DSN or workspace code.
This adapter is not a local-file or session fallback.
"""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from aeacus_agent.project_memory import (
    DEFAULT_SCHEMA,
    SCHEMA_NAME,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    MemoryResult,
    prepare_connect_dsn,
    sanitize_failure,
    schema_from_env,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PostgresMemoryStore:
    mocked = False
    durable = True

    def __init__(
        self,
        *,
        dsn: str,
        schema: str = DEFAULT_SCHEMA,
        connector: Any | None = None,
    ) -> None:
        self._dsn = dsn
        self._schema = schema_from_env({SCHEMA_NAME: schema})
        self._connector = connector
        self._connection: Any | None = None

    def __repr__(self) -> str:
        return "PostgresMemoryStore(configured=True)"

    def _connect(self) -> Any:
        if self._connection is not None:
            return self._connection
        connect = self._connector
        if connect is None:
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("psycopg_unavailable") from exc
            connect = psycopg.connect
        prepared, error = prepare_connect_dsn(self._dsn)
        if error or prepared is None:
            raise RuntimeError(error or "unconfigured")
        try:
            self._connection = connect(prepared)
        except Exception as exc:
            raise RuntimeError(sanitize_failure(exc, dsn=self._dsn)) from None
        return self._connection

    def _unavailable(self, exc: BaseException) -> MemoryResult:
        return MemoryResult(
            ok=False,
            status="memory_unavailable",
            durable=False,
            mocked=False,
            unavailable=True,
            reason="unavailable",
            value=None,
            facts=[],
            field=None,
        )

    def _execute(
        self,
        sql: str,
        params: tuple[Any, ...] = (),
        *,
        fetchone: bool = False,
        fetchall: bool = False,
    ) -> Any:
        connection = self._connect()
        cursor = connection.cursor()
        cursor.execute(sql, params)
        rows = None
        if fetchone:
            rows = cursor.fetchone()
        elif fetchall:
            rows = cursor.fetchall()
        if hasattr(connection, "commit"):
            connection.commit()
        return rows

    def _table(self) -> str:
        return f"{self._schema}.facts"

    def fetch_active(self, workspace_id: str, field: str) -> MemoryResult:
        now = _utcnow()
        sql = (
            f"SELECT value, created_at, expires_at FROM {self._table()} "
            "WHERE workspace_id = %s AND field = %s AND status = %s "
            "AND expires_at > %s"
        )
        try:
            row = self._execute(
                sql,
                (workspace_id, field, STATUS_ACTIVE, now),
                fetchone=True,
            )
        except Exception as exc:
            return self._unavailable(exc)
        if not row:
            return MemoryResult(
                ok=True,
                status="empty",
                durable=True,
                mocked=False,
                unavailable=False,
                reason=None,
                field=field,
                value=None,
                facts=[],
            )
        value = row[0]
        return MemoryResult(
            ok=True,
            status="found",
            durable=True,
            mocked=False,
            unavailable=False,
            reason=None,
            field=field,
            value=value,
            facts=[_row_fact(field, row, now=now)],
        )

    def fetch_all_active(self, workspace_id: str) -> MemoryResult:
        now = _utcnow()
        sql = (
            f"SELECT field, value, created_at, expires_at FROM {self._table()} "
            "WHERE workspace_id = %s AND status = %s AND expires_at > %s "
            "ORDER BY field"
        )
        try:
            rows = self._execute(
                sql,
                (workspace_id, STATUS_ACTIVE, now),
                fetchall=True,
            )
        except Exception as exc:
            return self._unavailable(exc)
        facts = [
            {
                "field": row[0],
                "value": row[1],
                "source": SOURCE_USER_DECLARED,
                "created_at": _iso(row[2]),
                "expires_at": _iso(row[3]),
            }
            for row in rows or []
        ]
        return MemoryResult(
            ok=True,
            status="listed" if facts else "empty",
            durable=True,
            mocked=False,
            unavailable=False,
            reason=None,
            value=None,
            facts=facts,
        )

    def persist_replace(
        self,
        workspace_id: str,
        field: str,
        value: str,
        *,
        now: datetime,
        expires_at: datetime,
    ) -> MemoryResult:
        current_sql = (
            f"SELECT id, value FROM {self._table()} "
            "WHERE workspace_id = %s AND field = %s AND status = %s"
        )
        try:
            current = self._execute(
                current_sql,
                (workspace_id, field, STATUS_ACTIVE),
                fetchone=True,
            )
            if current and current[1] == value:
                return MemoryResult(
                    ok=True,
                    status="unchanged",
                    durable=True,
                    mocked=False,
                    unavailable=False,
                    reason=None,
                    field=field,
                    value=value,
                    facts=[],
                )
            if current:
                self._execute(
                    f"UPDATE {self._table()} SET status = %s, superseded_at = %s "
                    "WHERE workspace_id = %s AND field = %s AND status = %s",
                    (STATUS_SUPERSEDED, now, workspace_id, field, STATUS_ACTIVE),
                )
            self._execute(
                f"INSERT INTO {self._table()} "
                "(id, workspace_id, field, value, status, source, created_at, expires_at, superseded_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    str(uuid.uuid4()),
                    workspace_id,
                    field,
                    value,
                    STATUS_ACTIVE,
                    SOURCE_USER_DECLARED,
                    now,
                    expires_at,
                    None,
                ),
            )
        except Exception as exc:
            return self._unavailable(exc)
        return MemoryResult(
            ok=True,
            status="replaced",
            durable=True,
            mocked=False,
            unavailable=False,
            reason=None,
            field=field,
            value=value,
            facts=[],
        )

    def count_all_rows(self, workspace_id: str) -> int | None:
        sql = f"SELECT COUNT(*) FROM {self._table()} WHERE workspace_id = %s"
        try:
            row = self._execute(sql, (workspace_id,), fetchone=True)
        except Exception:
            return None
        if not row:
            return 0
        return int(row[0])

    def persist_delete(self, workspace_id: str, field: str) -> MemoryResult:
        sql = f"DELETE FROM {self._table()} WHERE workspace_id = %s AND field = %s"
        try:
            self._execute(sql, (workspace_id, field))
        except Exception as exc:
            return self._unavailable(exc)
        return MemoryResult(
            ok=True,
            status="deleted",
            durable=True,
            mocked=False,
            unavailable=False,
            reason=None,
            field=field,
            value=None,
            facts=[],
        )


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _row_fact(field: str, row: Any, *, now: datetime) -> dict[str, Any]:
    return {
        "field": field,
        "value": row[0],
        "source": SOURCE_USER_DECLARED,
        "created_at": _iso(row[1]),
        "expires_at": _iso(row[2]),
    }
