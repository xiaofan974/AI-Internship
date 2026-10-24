"""Explicit aeacus_memory schema apply. Not imported by the store."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from aeacus_agent.project_memory import (
    DATABASE_URL_NAME,
    configured_database_url,
    open_memory_store,
    prepare_connect_dsn,
    sanitize_failure,
    schema_from_env,
)

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
MIGRATION_PATH = PROJECT_DIR / "sql" / "memory" / "0001_init.sql"
SCHEMA = "aeacus_memory"


def load_migration_sql(path: Path | None = None) -> str:
    target = path or MIGRATION_PATH
    return target.read_text(encoding="utf-8")


def migration_is_scoped_to_aeacus_memory(sql: str) -> bool:
    if SCHEMA not in sql:
        return False
    without_comments = []
    for raw in sql.splitlines():
        line = raw.split("--", 1)[0].strip()
        if line:
            without_comments.append(line)
    statements = [
        " ".join(item.split())
        for item in " ".join(without_comments).split(";")
        if item.strip()
    ]
    if not statements:
        return False
    for statement in statements:
        upper = statement.upper()
        if SCHEMA not in statement:
            return False
        if "INFORMATION_SCHEMA" in upper or "PG_CATALOG" in upper:
            return False
        for other in re.findall(
            r"\b([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_][A-Za-z0-9_]*",
            statement,
        ):
            if other != SCHEMA:
                return False
    return True


def apply_memory_schema(
    env: Any | None = None,
    *,
    connector: Any | None = None,
    sql_path: Path | None = None,
) -> dict[str, Any]:
    """Apply 0001_init.sql. Call this explicitly. Never from import."""
    sql = load_migration_sql(sql_path)
    if not migration_is_scoped_to_aeacus_memory(sql):
        return {
            "ok": False,
            "status": "rejected",
            "reason": "migration_not_limited_to_aeacus_memory",
            "applied": False,
        }
    store = open_memory_store(env, connector=connector)
    if getattr(store, "durable", False) is False:
        return {
            "ok": False,
            "status": "memory_unavailable",
            "reason": getattr(store, "reason", "unconfigured"),
            "applied": False,
        }
    dsn = configured_database_url(env)
    prepared, error = prepare_connect_dsn(dsn or "")
    if error or prepared is None:
        return {
            "ok": False,
            "status": "memory_unavailable",
            "reason": error or "unconfigured",
            "applied": False,
        }
    connect = connector
    if connect is None:
        try:
            import psycopg
        except ImportError:
            return {
                "ok": False,
                "status": "memory_unavailable",
                "reason": "psycopg_unavailable",
                "applied": False,
            }
        connect = psycopg.connect
    connection = None
    try:
        connection = connect(prepared)
        cursor = connection.cursor()
        cursor.execute(sql)
        if hasattr(connection, "commit"):
            connection.commit()
        schema = schema_from_env(env)
        cursor.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname = %s",
            (schema,),
        )
        present = cursor.fetchone() is not None
        return {
            "ok": True,
            "status": "applied",
            "reason": None,
            "applied": True,
            "schema_present": present,
            "path": str(sql_path or MIGRATION_PATH),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "memory_unavailable",
            "reason": sanitize_failure(exc, dsn=dsn),
            "applied": False,
        }
    finally:
        if connection is not None and hasattr(connection, "close"):
            connection.close()


# Guard: importing this module must not apply the migration.
assert DATABASE_URL_NAME
