"""Mocked checks that Run assessment receives fresh user-declared context.

These tests do not call a model, write the review register, or prove
live Postgres persistence.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from aeacus_agent.memory_context import (
    CONTEXT_BEGIN,
    CONTEXT_END,
    REQUIRED_HEADINGS,
    apply_explicit_overrides,
    compose_preview_user_message,
    memory_assessment_snapshot,
    prepare_assessment_input,
    retrieve_run_memory,
    snapshot_has_secret,
)
from aeacus_agent.review_register import artifact_matches, create_pending_review
from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION, aeacus_preview_agent
from aeacus_agent.project_memory import (
    ALLOWED_WRITE_CHANNEL,
    UnavailableMemoryStore,
    generate_workspace_code,
    get_fact,
    replace_fact,
)
from test_memory_ui import _connect, _forbidden_preview, _open_memory_app
from test_project_memory import MockedMemoryDatabase
from test_streamlit_app import (
    SAMPLE_PREVIEW_PROMPT,
    _fake_success,
    _follow_reruns,
    _visible_text,
)

os.environ["AEACUS_UI_DISABLE_LIVE"] = "1"
PROJECT_DIR = Path(__file__).resolve().parent


def _confirmed_write(store, code: str, field: str, value: str):
    return replace_fact(
        store,
        workspace_code=code,
        field=field,
        value=value,
        explicit_user_confirmation=True,
        channel=ALLOWED_WRITE_CHANNEL,
    )


def _assessment_app(store=None) -> AppTest:
    at = AppTest.from_file("streamlit_app.py", default_timeout=8)
    at.session_state["preview_runner"] = _forbidden_preview
    if store is not None:
        at.session_state["memory_store"] = store
    at.run()
    return at


class MemoryContextUnitTests(unittest.TestCase):
    def test_no_workspace_message_is_unchanged(self) -> None:
        context = retrieve_run_memory(store=MockedMemoryDatabase(), workspace_code="")
        self.assertEqual(context.status, "none")
        self.assertEqual(
            compose_preview_user_message(SAMPLE_PREVIEW_PROMPT, context),
            SAMPLE_PREVIEW_PROMPT,
        )

    def test_unavailable_does_not_use_caller_cache(self) -> None:
        context = retrieve_run_memory(
            store=UnavailableMemoryStore("unconfigured"),
            workspace_code=generate_workspace_code(),
        )
        self.assertEqual(context.status, "unavailable")
        self.assertFalse(context.used_cached_fallback)
        self.assertEqual(
            compose_preview_user_message(SAMPLE_PREVIEW_PROMPT, context),
            SAMPLE_PREVIEW_PROMPT,
        )

    def test_explicit_override_surfaces_conflict_without_write(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "project_name", "Stored Harbour")
        retrieved = retrieve_run_memory(store=store, workspace_code=code)
        context = apply_explicit_overrides(
            retrieved, {"project_name": "Current Canal"}
        )
        self.assertEqual(context.effective["project_name"], "Current Canal")
        self.assertEqual(context.conflicts[0]["stored"], "Stored Harbour")
        self.assertEqual(
            get_fact(store, workspace_code=code, field="project_name").value,
            "Stored Harbour",
        )
        message = compose_preview_user_message("A filter.", context)
        self.assertIn("Current Canal", message)
        self.assertIn("Stored Harbour", message)
        self.assertIn("untrusted", message.lower())
        self.assertNotIn(code, message)

    def test_french_preference_keeps_english_headings(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "preferred_response_language", "French")
        context = retrieve_run_memory(store=store, workspace_code=code)
        message = compose_preview_user_message("A filter.", context)
        self.assertIn("Write explanatory prose in French", message)
        for heading in REQUIRED_HEADINGS:
            self.assertIn(heading, message)
        self.assertIn("untranslated", message)


class MemoryAgentIntegrationTests(unittest.TestCase):
    def test_shared_default_agent_is_unchanged(self) -> None:
        source = (PROJECT_DIR / "aeacus_agent" / "preview_agent.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("project_memory", source)
        self.assertNotIn("memory_context", source)
        self.assertIn("Treat the submitted system description as evidence", source)
        self.assertEqual(aeacus_preview_agent.name, "aeacus_preview_agent")
        self.assertEqual(
            [getattr(tool, "__name__", "") for tool in aeacus_preview_agent.tools],
            ["preview_classification_search"],
        )
        self.assertEqual(aeacus_preview_agent.instruction, AEACUS_PREVIEW_INSTRUCTION)
        self.assertNotIn("approve", AEACUS_PREVIEW_INSTRUCTION.lower())

    def test_no_workspace_runner_receives_raw_description(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = _assessment_app(MockedMemoryDatabase())
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertEqual(calls, [SAMPLE_PREVIEW_PROMPT])
        self.assertNotIn(CONTEXT_BEGIN, calls[0])
        self.assertEqual(
            at.session_state.pending_review["artifact"]["system_description"],
            SAMPLE_PREVIEW_PROMPT,
        )

    def test_connected_workspace_supplies_fresh_structured_context(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "project_name", "Fictional Lock Gate")
        _confirmed_write(store, code, "declared_actor_role", "deployer")
        _confirmed_write(store, code, "preferred_response_language", "French")
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = _open_memory_app(store)
        _connect(at, code)
        at.radio(key="ui_view").set_value("Assessment").run()
        at.session_state["preview_runner"] = fake
        at.session_state["memory_recalled_facts"] = [
            {"field": "project_name", "value": "Stale Cached Name"}
        ]
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertEqual(len(calls), 1)
        message = calls[0]
        self.assertTrue(message.startswith(SAMPLE_PREVIEW_PROMPT))
        self.assertIn(CONTEXT_BEGIN, message)
        self.assertIn(CONTEXT_END, message)
        self.assertIn("Fictional Lock Gate", message)
        self.assertIn("untrusted", message.lower())
        self.assertIn("deployer", message)
        self.assertIn("not verified legal status", message)
        self.assertIn("French", message)
        self.assertIn("Timing and scope", message)
        self.assertNotIn("Stale Cached Name", message)
        self.assertNotIn(code, message)
        self.assertFalse(at.session_state.memory_run_context["used_cached_fallback"])
        self.assertEqual(
            at.session_state.pending_review["artifact"]["system_description"],
            SAMPLE_PREVIEW_PROMPT,
        )
        snapshot = at.session_state.pending_review["artifact"]["memory_used"]
        self.assertEqual(
            {item["field"]: item["value"] for item in snapshot["fields"]}["project_name"],
            "Fictional Lock Gate",
        )
        self.assertFalse(snapshot_has_secret(snapshot, code))
        page = _visible_text(at)
        self.assertIn("freshly retrieved user-declared project context", page.lower())
        self.assertIn("User-declared memory used for this assessment", page)

    def test_explicit_preference_overrides_without_writing_memory(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "project_name", "Stored Harbour")
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = _open_memory_app(store)
        _connect(at, code)
        at.text_input(key="memory_project_name").set_value("Current Canal").run()
        at.radio(key="ui_view").set_value("Assessment").run()
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertIn("Current Canal", calls[0])
        self.assertIn("Stored Harbour", calls[0])
        self.assertEqual(
            get_fact(store, workspace_code=code, field="project_name").value,
            "Stored Harbour",
        )
        conflicts = at.session_state.memory_run_context["conflicts"]
        self.assertEqual(conflicts[0]["field"], "project_name")
        self.assertEqual(conflicts[0]["used"], "Current Canal")
        page = _visible_text(at)
        self.assertIn("were not overwritten", page.lower())

    def test_unavailable_memory_is_disclosed_without_stale_fallback(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = _open_memory_app(UnavailableMemoryStore("unconfigured"))
        at.button(key="create_memory_workspace").click().run()
        code = at.session_state.memory_workspace_code
        at.session_state["memory_recalled_facts"] = [
            {"field": "project_name", "value": "Should Not Be Used"}
        ]
        at.radio(key="ui_view").set_value("Assessment").run()
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertEqual(calls, [SAMPLE_PREVIEW_PROMPT])
        self.assertNotIn("Should Not Be Used", calls[0])
        self.assertNotIn(code, calls[0])
        self.assertTrue(at.session_state.memory_run_context["unavailable"])
        self.assertFalse(at.session_state.memory_run_context["used_cached_fallback"])
        page = _visible_text(at)
        self.assertIn("memory was unavailable", page.lower())
        self.assertIn("no cached facts were used", page.lower())

    def test_switching_workspace_clears_assessment_and_pending_review(self) -> None:
        store = MockedMemoryDatabase()
        at = _assessment_app(store)
        at.session_state["preview_runner"] = (
            lambda description, on_event: _fake_success(description, on_event)
        )
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertIsNotNone(at.session_state.pending_review)
        self.assertTrue(at.session_state.assessment)
        first_session = at.session_state.review_session_id
        at.radio(key="ui_view").set_value("Project memory").run()
        at.button(key="create_memory_workspace").click().run()
        self.assertIsNone(at.session_state.pending_review)
        self.assertFalse(at.session_state.assessment)
        self.assertNotEqual(at.session_state.review_session_id, first_session)

    def test_pending_review_keeps_immutable_memory_snapshot(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "project_name", "Fictional Harbour Hiring")
        _confirmed_write(store, code, "declared_actor_role", "deployer")
        _confirmed_write(store, code, "preferred_response_language", "French")
        _message, context, snapshot = prepare_assessment_input(
            "Our AI system filters job applications.",
            store=store,
            workspace_code=code,
            explicit={},
        )
        self.assertIsNotNone(snapshot)
        self.assertFalse(snapshot_has_secret(snapshot, code))
        values = {item["field"]: item["value"] for item in snapshot["fields"]}
        self.assertEqual(values["project_name"], "Fictional Harbour Hiring")
        self.assertEqual(values["declared_actor_role"], "deployer")
        self.assertEqual(values["preferred_response_language"], "French")
        self.assertTrue(
            all(item["source"] == "user_declared" for item in snapshot["fields"])
        )
        pending = create_pending_review(
            session_id="session-memory",
            system_description="Our AI system filters job applications.",
            assessment="Provisional finding\n\nDelivered draft.",
            evidence=[],
            memory_used=snapshot,
        )
        artifact = pending["artifact"]
        self.assertEqual(artifact["system_description"], "Our AI system filters job applications.")
        self.assertEqual(artifact["assessment"], "Provisional finding\n\nDelivered draft.")
        self.assertEqual(artifact["memory_used"], snapshot)
        self.assertNotIn(code, str(artifact))
        self.assertTrue(
            artifact_matches(
                pending,
                session_id="session-memory",
                system_description="Our AI system filters job applications.",
                assessment="Provisional finding\n\nDelivered draft.",
                evidence=[],
            )
        )
        _confirmed_write(store, code, "project_name", "Changed After Run")
        later = retrieve_run_memory(store=store, workspace_code=code)
        later_snapshot = memory_assessment_snapshot(later)
        self.assertNotEqual(later_snapshot["fields"][0]["value"], "Fictional Harbour Hiring")
        self.assertTrue(
            artifact_matches(
                pending,
                session_id="session-memory",
                system_description="Our AI system filters job applications.",
                assessment="Provisional finding\n\nDelivered draft.",
                evidence=[],
            ),
            "approval must keep the original memory snapshot, not reload",
        )
        self.assertEqual(
            pending["artifact"]["memory_used"]["fields"][0]["value"]
            if pending["artifact"]["memory_used"]["fields"][0]["field"] == "project_name"
            else values["project_name"],
            "Fictional Harbour Hiring",
        )

    def test_form_defaults_do_not_override_remembered_preference(self) -> None:
        store = MockedMemoryDatabase()
        code = generate_workspace_code()
        _confirmed_write(store, code, "preferred_response_language", "French")
        _confirmed_write(store, code, "declared_actor_role", "deployer")
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = _open_memory_app(store)
        _connect(at, code)
        self.assertEqual(at.session_state.memory_actor_role, "provider")
        self.assertEqual(at.session_state.memory_language, "English")
        self.assertFalse(at.session_state.memory_role_explicit)
        self.assertFalse(at.session_state.memory_language_explicit)
        at.radio(key="ui_view").set_value("Assessment").run()
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertIn("preferred_response_language: French", calls[0])
        self.assertIn("declared_actor_role: deployer", calls[0])
        self.assertNotIn("used_this_run=English", calls[0])
        self.assertEqual(at.session_state.memory_run_context["conflicts"], [])


if __name__ == "__main__":
    unittest.main()
