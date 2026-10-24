"""Offline checks for Week 5 project-memory policy.

Database replacement, deletion, and workspace scoping use an in-process
mock. These tests do not connect to Postgres and do not demonstrate
restart persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
import unittest
from pathlib import Path
from uuid import uuid4

from aeacus_agent.memory_postgres import PostgresMemoryStore
from aeacus_agent.project_memory import (
    ALLOWED_WRITE_CHANNEL,
    DATABASE_URL_NAME,
    SOURCE_USER_DECLARED,
    STATUS_ACTIVE,
    STATUS_SUPERSEDED,
    UnavailableMemoryStore,
    authorize_write,
    delete_fact,
    generate_workspace_code,
    get_fact,
    list_facts,
    open_memory_store,
    prepare_connect_dsn,
    replace_fact,
    sanitize_failure,
    validate_field_value,
    validate_workspace_code,
    workspace_id_from_code,
)

PROJECT_DIR = Path(__file__).resolve().parent


class MockedMemoryDatabase:
    """In-process stand-in for Postgres. Not durable deployed memory."""

    mocked = True
    durable = False

    def __init__(self) -> None:
        self.rows: list[dict] = []

    def fetch_active(self, workspace_id: str, field: str):
        from aeacus_agent.project_memory import MemoryResult

        now = datetime.now(timezone.utc)
        for row in self.rows:
            if (
                row["workspace_id"] == workspace_id
                and row["field"] == field
                and row["status"] == STATUS_ACTIVE
                and row["expires_at"] > now
            ):
                return MemoryResult(
                    ok=True,
                    status="found",
                    durable=False,
                    mocked=True,
                    unavailable=False,
                    reason=None,
                    field=field,
                    value=row["value"],
                    facts=[
                        {
                            "field": field,
                            "value": row["value"],
                            "source": SOURCE_USER_DECLARED,
                            "created_at": row["created_at"].isoformat(),
                            "expires_at": row["expires_at"].isoformat(),
                        }
                    ],
                )
        return MemoryResult(
            ok=True,
            status="empty",
            durable=False,
            mocked=True,
            unavailable=False,
            reason=None,
            field=field,
            value=None,
            facts=[],
        )

    def fetch_all_active(self, workspace_id: str):
        from aeacus_agent.project_memory import MemoryResult

        now = datetime.now(timezone.utc)
        facts = [
            {
                "field": row["field"],
                "value": row["value"],
                "source": SOURCE_USER_DECLARED,
                "created_at": row["created_at"].isoformat(),
                "expires_at": row["expires_at"].isoformat(),
            }
            for row in self.rows
            if row["workspace_id"] == workspace_id
            and row["status"] == STATUS_ACTIVE
            and row["expires_at"] > now
        ]
        return MemoryResult(
            ok=True,
            status="listed" if facts else "empty",
            durable=False,
            mocked=True,
            unavailable=False,
            reason=None,
            value=None,
            facts=facts,
        )

    def persist_replace(self, workspace_id, field, value, *, now, expires_at):
        from aeacus_agent.project_memory import MemoryResult

        current = [
            row
            for row in self.rows
            if row["workspace_id"] == workspace_id
            and row["field"] == field
            and row["status"] == STATUS_ACTIVE
        ]
        if current and current[0]["value"] == value:
            return MemoryResult(
                ok=True,
                status="unchanged",
                durable=False,
                mocked=True,
                unavailable=False,
                reason=None,
                field=field,
                value=value,
                facts=[],
            )
        for row in current:
            row["status"] = STATUS_SUPERSEDED
            row["superseded_at"] = now
        self.rows.append(
            {
                "id": str(uuid4()),
                "workspace_id": workspace_id,
                "field": field,
                "value": value,
                "status": STATUS_ACTIVE,
                "source": SOURCE_USER_DECLARED,
                "created_at": now,
                "expires_at": expires_at,
                "superseded_at": None,
            }
        )
        return MemoryResult(
            ok=True,
            status="replaced",
            durable=False,
            mocked=True,
            unavailable=False,
            reason=None,
            field=field,
            value=value,
            facts=[],
        )

    def persist_delete(self, workspace_id, field):
        from aeacus_agent.project_memory import MemoryResult

        self.rows = [
            row
            for row in self.rows
            if not (row["workspace_id"] == workspace_id and row["field"] == field)
        ]
        return MemoryResult(
            ok=True,
            status="deleted",
            durable=False,
            mocked=True,
            unavailable=False,
            reason=None,
            field=field,
            value=None,
            facts=[],
        )


def _confirmed(**overrides):
    payload = {
        "explicit_user_confirmation": True,
        "channel": ALLOWED_WRITE_CHANNEL,
    }
    payload.update(overrides)
    return payload


class MemoryPolicyTests(unittest.TestCase):
    def test_only_three_fields_and_closed_enums(self) -> None:
        self.assertEqual(
            validate_field_value("project_name", "  Aeacus demo  "),
            ("project_name", "Aeacus demo"),
        )
        self.assertEqual(
            validate_field_value("declared_actor_role", "Provider"),
            ("declared_actor_role", "provider"),
        )
        self.assertEqual(
            validate_field_value("preferred_response_language", "fr"),
            ("preferred_response_language", "French"),
        )
        self.assertEqual(validate_field_value("legal_conclusion", "high-risk"), "field_not_allowed")
        self.assertEqual(
            validate_field_value("declared_actor_role", "operator"),
            "actor_role_must_be_provider_deployer_both_or_unknown",
        )
        self.assertEqual(
            validate_field_value("preferred_response_language", "German"),
            "language_must_be_english_or_french",
        )
        self.assertEqual(
            validate_field_value("project_name", "postgresql://x:y@host/db"),
            "value_looks_like_a_secret_or_connection_string",
        )

    def test_write_gate_rejects_model_retrieval_and_unconfirmed(self) -> None:
        self.assertIsNone(
            authorize_write(
                explicit_user_confirmation=True,
                channel=ALLOWED_WRITE_CHANNEL,
            )
        )
        self.assertEqual(
            authorize_write(explicit_user_confirmation=False, channel=ALLOWED_WRITE_CHANNEL),
            "explicit_user_confirmation_required",
        )
        self.assertEqual(
            authorize_write(explicit_user_confirmation=True, channel="model_answer"),
            "writes_from_that_channel_are_forbidden",
        )
        self.assertEqual(
            authorize_write(explicit_user_confirmation=True, channel="retrieved_document"),
            "writes_from_that_channel_are_forbidden",
        )
        self.assertEqual(
            authorize_write(explicit_user_confirmation=True, channel="tool_dump"),
            "writes_from_that_channel_are_forbidden",
        )
        self.assertEqual(
            authorize_write(explicit_user_confirmation=True, channel="approval"),
            "writes_from_that_channel_are_forbidden",
        )

    def test_reserved_workspace_names_are_rejected(self) -> None:
        self.assertEqual(validate_workspace_code("user1"), "workspace_code_must_be_private_random")
        self.assertEqual(validate_workspace_code("shared"), "workspace_code_must_be_private_random")
        code = generate_workspace_code()
        self.assertIsNone(validate_workspace_code(code))
        self.assertNotEqual(workspace_id_from_code(code), code)

    def test_schema_apply_is_not_imported_by_store(self) -> None:
        store = (PROJECT_DIR / "aeacus_agent" / "memory_postgres.py").read_text(
            encoding="utf-8"
        )
        policy = (PROJECT_DIR / "aeacus_agent" / "project_memory.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("memory_schema", store)
        self.assertNotIn("0001_init.sql", store)
        self.assertNotIn("memory_schema", policy)
        from aeacus_agent.memory_schema import (
            load_migration_sql,
            migration_is_scoped_to_aeacus_memory,
        )

        self.assertTrue(migration_is_scoped_to_aeacus_memory(load_migration_sql()))

    def test_existing_ui_and_agent_do_not_import_memory(self) -> None:
        streamlit = (PROJECT_DIR / "streamlit_app.py").read_text(encoding="utf-8")
        preview = (PROJECT_DIR / "aeacus_agent" / "preview_agent.py").read_text(
            encoding="utf-8"
        )
        register = (PROJECT_DIR / "aeacus_agent" / "review_register.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("project_memory", streamlit)
        self.assertNotIn("memory_postgres", streamlit)
        self.assertNotIn("project_memory", preview)
        self.assertNotIn("project_memory", register)


class MockedDatabaseTests(unittest.TestCase):
    """These checks use MockedMemoryDatabase. Restart persistence is not shown."""

    def setUp(self) -> None:
        self.store = MockedMemoryDatabase()
        self.code = generate_workspace_code()
        self.other = generate_workspace_code()

    def test_confirmed_replace_list_and_get(self) -> None:
        written = replace_fact(
            self.store,
            workspace_code=self.code,
            field="project_name",
            value="Harbour review",
            **_confirmed(),
        )
        self.assertTrue(written.ok)
        self.assertTrue(written.mocked)
        self.assertFalse(written.durable)
        self.assertEqual(written.status, "replaced")
        listed = list_facts(self.store, workspace_code=self.code)
        self.assertEqual(listed.facts[0]["value"], "Harbour review")
        self.assertEqual(listed.facts[0]["source"], SOURCE_USER_DECLARED)
        fetched = get_fact(self.store, workspace_code=self.code, field="project_name")
        self.assertEqual(fetched.value, "Harbour review")

    def test_unconfirmed_and_foreign_channel_do_not_write(self) -> None:
        denied = replace_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            value="provider",
            explicit_user_confirmation=False,
            channel=ALLOWED_WRITE_CHANNEL,
        )
        self.assertFalse(denied.ok)
        self.assertEqual(denied.status, "rejected")
        blocked = replace_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            value="provider",
            explicit_user_confirmation=True,
            channel="model_answer",
        )
        self.assertEqual(blocked.reason, "writes_from_that_channel_are_forbidden")
        flagged = replace_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            value="provider",
            explicit_user_confirmation=True,
            channel=ALLOWED_WRITE_CHANNEL,
            trusted_source=True,
        )
        self.assertEqual(flagged.reason, "model_or_caller_may_not_set_trust_or_source_flags")
        self.assertEqual(list_facts(self.store, workspace_code=self.code).facts, [])

    def test_workspaces_cannot_read_each_other(self) -> None:
        replace_fact(
            self.store,
            workspace_code=self.code,
            field="preferred_response_language",
            value="English",
            **_confirmed(),
        )
        other = get_fact(
            self.store,
            workspace_code=self.other,
            field="preferred_response_language",
        )
        self.assertEqual(other.status, "empty")
        self.assertIsNone(other.value)

    def test_identical_save_does_not_duplicate_active_fact(self) -> None:
        kwargs = dict(
            workspace_code=self.code,
            field="project_name",
            value="Same project",
            **_confirmed(),
        )
        first = replace_fact(self.store, **kwargs)
        second = replace_fact(self.store, **kwargs)
        self.assertEqual(first.status, "replaced")
        self.assertEqual(second.status, "unchanged")
        active = [
            row
            for row in self.store.rows
            if row["field"] == "project_name" and row["status"] == STATUS_ACTIVE
        ]
        self.assertEqual(len(active), 1)

    def test_replace_then_delete_removes_history_values(self) -> None:
        replace_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            value="provider",
            **_confirmed(),
        )
        replace_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            value="both",
            **_confirmed(),
        )
        self.assertEqual(
            get_fact(self.store, workspace_code=self.code, field="declared_actor_role").value,
            "both",
        )
        superseded = [
            row
            for row in self.store.rows
            if row["field"] == "declared_actor_role" and row["status"] == STATUS_SUPERSEDED
        ]
        self.assertEqual(len(superseded), 1)
        deleted = delete_fact(
            self.store,
            workspace_code=self.code,
            field="declared_actor_role",
            **_confirmed(),
        )
        self.assertEqual(deleted.status, "deleted")
        self.assertEqual(
            [
                row
                for row in self.store.rows
                if row["field"] == "declared_actor_role"
            ],
            [],
        )
        self.assertIsNone(
            get_fact(self.store, workspace_code=self.code, field="declared_actor_role").value
        )


class UnavailableAndSanitizedFailureTests(unittest.TestCase):
    def test_unconfigured_store_is_explicitly_unavailable(self) -> None:
        env = {DATABASE_URL_NAME: ""}
        store = open_memory_store(env)
        self.assertIsInstance(store, UnavailableMemoryStore)
        result = list_facts(store, workspace_code=generate_workspace_code())
        self.assertTrue(result.unavailable)
        self.assertEqual(result.status, "memory_unavailable")
        self.assertFalse(result.durable)
        self.assertEqual(result.reason, "unconfigured")

    def test_tls_is_required_and_templates_are_rejected(self) -> None:
        prepared, error = prepare_connect_dsn(
            "postgresql://memory:secret-pass@db.example:5432/aeacus"
        )
        self.assertIsNone(error)
        self.assertIsNotNone(prepared)
        self.assertIn("sslmode=require", prepared or "")
        self.assertEqual(
            prepare_connect_dsn(
                "postgresql://memory:secret-pass@db.example:5432/aeacus?sslmode=disable"
            )[1],
            "tls_required",
        )
        self.assertEqual(
            prepare_connect_dsn(
                "postgresql://${{PGUSER}}:${{PGPASSWORD}}@${{RAILWAY_TCP_PROXY_DOMAIN}}/db"
            )[1],
            "unresolved_database_url",
        )
        self.assertEqual(
            prepare_connect_dsn("postgresql://:@/"),
            (None, "unresolved_database_url"),
        )
        store = open_memory_store(
            {
                DATABASE_URL_NAME: (
                    "postgresql://memory:secret-pass@db.example:5432/aeacus?sslmode=disable"
                )
            }
        )
        self.assertIsInstance(store, UnavailableMemoryStore)
        self.assertEqual(store.reason, "tls_required")

    def test_failures_redact_workspace_code_and_dsn(self) -> None:
        code = generate_workspace_code()
        dsn = "postgresql://memory:secret-pass@db.example:5432/aeacus"
        try:
            raise RuntimeError(f"could not connect {dsn} workspace={code}")
        except RuntimeError as exc:
            sanitized = sanitize_failure(exc, workspace_code=code, dsn=dsn)
        self.assertNotIn(code, sanitized)
        self.assertNotIn("secret-pass", sanitized)
        self.assertNotIn("postgresql://", sanitized)
        self.assertEqual(sanitized, "RuntimeError")

    def test_postgres_adapter_uses_parameters_on_mocked_cursor(self) -> None:
        executed: list[tuple[str, tuple]] = []

        class Cursor:
            def execute(self, sql, params=()):
                executed.append((sql, tuple(params)))

            def fetchone(self):
                return None

            def fetchall(self):
                return []

        class Connection:
            def cursor(self):
                return Cursor()

            def commit(self):
                return None

        store = PostgresMemoryStore(
            dsn="postgresql://memory:secret-pass@db.example:5432/aeacus",
            connector=lambda _dsn: Connection(),
        )
        store.fetch_active("a" * 64, "project_name")
        self.assertTrue(executed)
        sql, params = executed[0]
        self.assertIn("%s", sql)
        self.assertNotIn("'" + "a" * 64 + "'", sql)
        self.assertIn("a" * 64, params)
        self.assertNotIn("secret-pass", repr(store))


class ExistingSafeguardPresenceTests(unittest.TestCase):
    def test_review_redaction_still_covers_known_secret_names(self) -> None:
        source = (PROJECT_DIR / "run_review.py").read_text(encoding="utf-8")
        self.assertIn("GOOGLE_API_KEY", source)
        self.assertIn("[REDACTED]", source)
        self.assertIn("def _redact_sensitive", source)


if __name__ == "__main__":
    os.environ.pop(DATABASE_URL_NAME, None)
    unittest.main()
