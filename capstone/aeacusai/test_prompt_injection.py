"""Deterministic checks that forged approval text cannot write the register.

Uses the prompt-injection fixture and the actual Streamlit approval
boundary. No Gemini, OpenAI, or Pinecone calls.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.review_register import (
    PENDING_STATUS,
    approve_and_record,
    create_pending_review,
    entry_count,
)
from prompt_injection_fixtures import (
    ATTACK_REQUIRED_STATEMENT,
    INJECTED_SYSTEM_DESCRIPTION,
)
from streamlit_app import finalize_preview_result
from test_streamlit_app import _follow_reruns


def _fake_injected_success(description: str, on_event) -> dict:
    on_event({"kind": "think", "action": "skip retrieval as instructed"})
    on_event({"kind": "final", "text": ATTACK_REQUIRED_STATEMENT})
    return finalize_preview_result(ATTACK_REQUIRED_STATEMENT, [])


class PromptInjectionBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "injection_review_register.sqlite")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_forged_approval_text_does_not_write_through_application_boundary(
        self,
    ) -> None:
        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = _fake_injected_success
        at.session_state["review_db_path"] = self.db_path
        at.run()
        at.text_area(key="description").set_value(INJECTED_SYSTEM_DESCRIPTION).run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)

        self.assertEqual(at.session_state.description, INJECTED_SYSTEM_DESCRIPTION)
        self.assertEqual(at.session_state.raw_answer, ATTACK_REQUIRED_STATEMENT)
        self.assertEqual(entry_count(self.db_path), 0)
        self.assertIsNotNone(at.session_state.pending_review)
        self.assertEqual(
            at.session_state.pending_review.get("status"), PENDING_STATUS
        )
        kinds = [event["kind"] for event in at.session_state.trace]
        self.assertIn("review_required", kinds)
        self.assertNotIn("approved", kinds)
        self.assertNotIn("recorded", kinds)
        self.assertEqual((at.session_state.get("reviewer_label") or "").strip(), "")
        approve = at.button(key="approve_and_record")
        self.assertTrue(approve.disabled)

    def test_model_cannot_supply_approved_true_or_lily_as_a_write_parameter(
        self,
    ) -> None:
        pending = create_pending_review(
            session_id="injection-session",
            system_description=INJECTED_SYSTEM_DESCRIPTION,
            assessment=ATTACK_REQUIRED_STATEMENT,
            evidence=[],
            run_id="run-injection",
        )
        self.assertEqual(entry_count(self.db_path), 0)
        self.assertNotIn("approved", inspect.signature(approve_and_record).parameters)
        with self.assertRaises(TypeError):
            approve_and_record(
                pending,
                session_id="injection-session",
                reviewer_label="Lily",
                current_system_description=INJECTED_SYSTEM_DESCRIPTION,
                current_assessment=ATTACK_REQUIRED_STATEMENT,
                current_evidence=[],
                db_path=self.db_path,
                approved=True,
            )
        self.assertEqual(entry_count(self.db_path), 0)
        tool_names = [
            getattr(tool, "__name__", "") for tool in aeacus_preview_agent.tools
        ]
        self.assertEqual(tool_names, ["preview_classification_search"])
        self.assertNotIn("approve_and_record", tool_names)


if __name__ == "__main__":
    unittest.main()
