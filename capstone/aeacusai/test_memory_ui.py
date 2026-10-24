"""Focused Streamlit checks for the Project memory workspace.

These tests inject an in-process store. They do not prove a second
browser process or restart persistence.
"""

from __future__ import annotations

import os
import unittest

from streamlit.testing.v1 import AppTest

from aeacus_agent.project_memory import UnavailableMemoryStore
from test_project_memory import MockedMemoryDatabase
from test_streamlit_app import _visible_text

os.environ["AEACUS_UI_DISABLE_LIVE"] = "1"


def _forbidden_preview(description: str, on_event) -> dict:
    raise AssertionError("memory UI must not run an assessment")


def _open_memory_app(store) -> AppTest:
    at = AppTest.from_file("streamlit_app.py", default_timeout=8)
    at.session_state["preview_runner"] = _forbidden_preview
    at.session_state["memory_store"] = store
    at.run()
    at.radio(key="ui_view").set_value("Project memory").run()
    return at


def _connect(at: AppTest, code: str) -> AppTest:
    at.text_input(key="memory_workspace_entry").set_value(code).run()
    at.button(key="use_memory_workspace").click().run()
    return at


class ProjectMemoryUiTests(unittest.TestCase):
    def test_opening_app_stays_on_assessment_and_does_not_write_memory(self) -> None:
        store = MockedMemoryDatabase()
        at = AppTest.from_file("streamlit_app.py", default_timeout=8)
        at.session_state["preview_runner"] = _forbidden_preview
        at.session_state["memory_store"] = store
        at.run()
        self.assertEqual(at.session_state.ui_view, "Assessment")
        self.assertEqual(store.rows, [])
        self.assertFalse(at.session_state.get("memory_workspace_code"))
        self.assertFalse(any(btn.key == "save_project_memory" for btn in at.button))
        page = _visible_text(at)
        self.assertIn("System description", page)
        self.assertNotIn("Save project memory", page)

    def test_confirmation_is_required_before_write(self) -> None:
        store = MockedMemoryDatabase()
        at = _open_memory_app(store)
        at.button(key="create_memory_workspace").click().run()
        at.text_input(key="memory_project_name").set_value("Harbour draft").run()
        at.selectbox(key="memory_actor_role").set_value("deployer").run()
        at.selectbox(key="memory_language").set_value("French").run()
        at.button(key="save_project_memory").click().run()
        self.assertEqual(store.rows, [])
        statuses = [item["status"] for item in at.session_state.memory_last_results]
        self.assertTrue(statuses)
        self.assertTrue(
            all(status == "rejected" for status in statuses), statuses
        )
        self.assertTrue(
            all(
                item["reason"] == "explicit_user_confirmation_required"
                for item in at.session_state.memory_last_results
            )
        )

    def test_confirmed_save_recall_and_fresh_read_ignore_form_cache(self) -> None:
        store = MockedMemoryDatabase()
        at = _open_memory_app(store)
        at.button(key="create_memory_workspace").click().run()
        at.text_input(key="memory_project_name").set_value("Session form only").run()
        at.button(key="recall_saved_memory").click().run()
        self.assertEqual(at.session_state.memory_recalled_facts, [])
        self.assertEqual(at.session_state.memory_project_name, "Session form only")

        at.selectbox(key="memory_actor_role").set_value("provider").run()
        at.selectbox(key="memory_language").set_value("English").run()
        at.checkbox(key="memory_confirm_save").check().run()
        at.text_input(key="memory_project_name").set_value("Fictional Canal Review").run()
        at.button(key="save_project_memory").click().run()
        statuses = [item["status"] for item in at.session_state.memory_last_results]
        self.assertEqual(set(statuses), {"replaced"})
        self.assertEqual(at.session_state.memory_recalled_facts, [])

        at.text_input(key="memory_project_name").set_value("Stale form value").run()
        at.button(key="recall_saved_memory").click().run()
        recalled = {
            item["field"]: item["value"]
            for item in at.session_state.memory_recalled_facts
        }
        self.assertEqual(recalled["project_name"], "Fictional Canal Review")
        self.assertNotEqual(recalled["project_name"], at.session_state.memory_project_name)
        self.assertEqual(recalled["declared_actor_role"], "provider")
        self.assertEqual(recalled["preferred_response_language"], "English")
        self.assertTrue(
            all(item.get("source") == "user_declared" for item in at.session_state.memory_recalled_facts)
        )
        page = _visible_text(at)
        self.assertIn("user_declared", page)
        self.assertIn("Fictional Canal Review", page)

        at.checkbox(key="memory_confirm_delete").check().run()
        at.selectbox(key="memory_delete_field").set_value("project_name").run()
        at.button(key="delete_memory_field").click().run()
        self.assertEqual(at.session_state.memory_last_results[0]["status"], "deleted")
        self.assertEqual(at.session_state.memory_recalled_facts, [])
        at.button(key="recall_saved_memory").click().run()
        recalled = {
            item["field"]: item["value"]
            for item in at.session_state.memory_recalled_facts
        }
        self.assertNotIn("project_name", recalled)

    def test_workspaces_are_isolated_and_disconnect_clears_cache(self) -> None:
        store = MockedMemoryDatabase()
        first = _open_memory_app(store)
        first.button(key="create_memory_workspace").click().run()
        code_a = first.session_state.memory_workspace_code
        first.text_input(key="memory_project_name").set_value("Workspace A only").run()
        first.selectbox(key="memory_actor_role").set_value("both").run()
        first.selectbox(key="memory_language").set_value("French").run()
        first.checkbox(key="memory_confirm_save").check().run()
        first.button(key="save_project_memory").click().run()

        second = _open_memory_app(store)
        second.button(key="create_memory_workspace").click().run()
        self.assertNotEqual(
            second.session_state.memory_workspace_code, code_a
        )
        second.button(key="recall_saved_memory").click().run()
        self.assertEqual(second.session_state.memory_recalled_facts, [])

        _connect(second, code_a)
        second.button(key="recall_saved_memory").click().run()
        recalled = {
            item["field"]: item["value"]
            for item in second.session_state.memory_recalled_facts
        }
        self.assertEqual(recalled["project_name"], "Workspace A only")

        second.button(key="disconnect_memory_workspace").click().run()
        self.assertFalse(second.session_state.memory_workspace_code)
        self.assertEqual(second.session_state.memory_recalled_facts, [])
        self.assertEqual(second.session_state.memory_last_results, [])

    def test_unavailable_store_is_shown_and_does_not_use_session_fallback(self) -> None:
        store = UnavailableMemoryStore("unconfigured")
        at = _open_memory_app(store)
        page = _visible_text(at)
        self.assertIn("unavailable", page.lower())
        at.button(key="create_memory_workspace").click().run()
        at.text_input(key="memory_project_name").set_value("Should not persist").run()
        at.checkbox(key="memory_confirm_save").check().run()
        at.button(key="save_project_memory").click().run()
        self.assertEqual(
            at.session_state.memory_last_results[0]["status"], "memory_unavailable"
        )
        self.assertTrue(at.session_state.memory_last_results[0]["unavailable"])
        at.button(key="recall_saved_memory").click().run()
        self.assertEqual(at.session_state.memory_recalled_facts, [])
        self.assertNotEqual(
            at.session_state.memory_project_name, at.session_state.memory_recalled_facts
        )
        page = _visible_text(at)
        self.assertIn("memory is unavailable", page.lower())

    def test_memory_workspace_is_distinct_from_approval_and_week4(self) -> None:
        at = _open_memory_app(MockedMemoryDatabase())
        page = _visible_text(at)
        self.assertIn("not statutory evidence", page.lower())
        self.assertIn("not human approval", page.lower())
        self.assertFalse(any(btn.key == "run_assessment" for btn in at.button))
        self.assertFalse(any(btn.key == "approve_review" for btn in at.button))
        self.assertIn("Project memory", [item.value for item in at.radio])


if __name__ == "__main__":
    unittest.main()
