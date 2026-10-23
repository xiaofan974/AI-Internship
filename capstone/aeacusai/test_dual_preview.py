"""Offline checks for the two-agent SequentialAgent preview.

These tests mock events and drafts. They do not call Gemini, OpenAI, or
Pinecone, and they do not prove live model behavior.
"""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path

from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.dual_preview import (
    CLASSIFIER_NAME,
    CRITIC_NAME,
    EVIDENCE_STATE_KEY,
    PIPELINE_NAME,
    EvidenceBook,
    apply_deterministic_checks,
    collect_handoff_from_events,
    create_dual_preview_pipeline,
    parse_critic_verdict,
)
from aeacus_agent.evidence_checks import run_deterministic_checks
from aeacus_agent.mcp_payload import decode_mcp_observation
from aeacus_agent.mcp_preview_agent import ALLOWED_MCP_TOOLS
from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.review_register import DEFAULT_DB_PATH
from google.adk.tools.mcp_tool import McpToolset

RECRUITMENT_QUERY = "recruitment job applications filter candidates workers"
FABRICATED_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    "::article/5"
)


class _FakeFn:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class _FakeEvent:
    def __init__(self, *, author, invocation_id, calls=None, responses=None):
        self.author = author
        self.invocation_id = invocation_id
        self._calls = calls or []
        self._responses = responses or []

    def get_function_calls(self):
        return self._calls

    def get_function_responses(self):
        return self._responses


def _wrapped_mcp_payload(direct: dict) -> dict:
    return {"content": [{"type": "text", "text": json.dumps(direct, ensure_ascii=False)}]}


def _child_pids(parent: int) -> set[int]:
    try:
        output = subprocess.check_output(
            ["pgrep", "-P", str(parent)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return set()
    return {int(line) for line in output.split() if line.strip().isdigit()}


class DualPreviewOfflineTests(unittest.TestCase):
    def test_default_streamlit_agent_is_unchanged(self) -> None:
        self.assertEqual(aeacus_preview_agent.name, "aeacus_preview_agent")
        self.assertEqual(
            [getattr(tool, "__name__", "") for tool in aeacus_preview_agent.tools],
            ["preview_classification_search"],
        )

    def test_sequential_orchestration_and_tool_permissions(self) -> None:
        pipeline, toolset, book = create_dual_preview_pipeline()
        try:
            self.assertEqual(pipeline.name, PIPELINE_NAME)
            self.assertEqual(
                [agent.name for agent in pipeline.sub_agents],
                [CLASSIFIER_NAME, CRITIC_NAME],
            )
            classifier, critic = pipeline.sub_agents
            self.assertEqual(len(classifier.tools), 1)
            self.assertIsInstance(classifier.tools[0], McpToolset)
            self.assertEqual(
                list(classifier.tools[0].tool_filter),
                list(ALLOWED_MCP_TOOLS),
            )
            self.assertEqual(list(critic.tools), [])
            self.assertTrue(classifier.disallow_transfer_to_peers)
            self.assertTrue(critic.disallow_transfer_to_peers)
            self.assertEqual(getattr(critic, "include_contents", None), "none")
            self.assertIs(classifier.tools[0], toolset)
            self.assertNotIn(
                "approve_and_record",
                [getattr(tool, "__name__", type(tool).__name__) for tool in classifier.tools],
            )
            self.assertIs(book.bundle, None)
        finally:
            # close is async; use the session manager sync path via asyncio
            import asyncio

            asyncio.run(toolset.close())

    def test_mcp_json_wrapped_as_text_is_decoded_and_associated(self) -> None:
        direct = preview_classification_search(RECRUITMENT_QUERY)
        self.assertEqual(direct["status"], "ok")
        wrapped = _wrapped_mcp_payload(direct)
        self.assertEqual(decode_mcp_observation(wrapped)["match_record_ids"], direct["match_record_ids"])
        result_wrapped = {"result": json.dumps(direct, ensure_ascii=False)}
        self.assertEqual(
            decode_mcp_observation(result_wrapped)["match_record_ids"],
            direct["match_record_ids"],
        )
        events = [
            _FakeEvent(
                author=CLASSIFIER_NAME,
                invocation_id="inv-1",
                calls=[
                    _FakeFn(
                        id="call-1",
                        name="preview_classification_search",
                        args={"query": RECRUITMENT_QUERY},
                    )
                ],
            ),
            _FakeEvent(
                author=CLASSIFIER_NAME,
                invocation_id="inv-1",
                responses=[
                    _FakeFn(
                        id="call-1",
                        name="preview_classification_search",
                        response=wrapped,
                    )
                ],
            ),
        ]
        bundle = collect_handoff_from_events(
            events=events,
            invocation_id="inv-1",
            author=CLASSIFIER_NAME,
            system_description="A recruitment filter.",
            draft="Provisional finding\n\nAnnex III, point 4 applies.",
        )
        self.assertTrue(bundle["handoff_ok"], bundle)
        self.assertEqual(bundle["observations"][0]["query"], RECRUITMENT_QUERY)
        self.assertEqual(
            [item["record_id"] for item in bundle["records"] if item["role"] == "match"],
            direct["match_record_ids"],
        )
        self.assertEqual(bundle["records"][0]["text"], direct["matches"][0]["text"])
        self.assertEqual(
            bundle["records"][0]["text_sha256"],
            direct["matches"][0]["text_sha256"],
        )

    def test_undecodable_or_unassociated_evidence_fails_handoff(self) -> None:
        events = [
            _FakeEvent(
                author=CLASSIFIER_NAME,
                invocation_id="inv-2",
                responses=[
                    _FakeFn(
                        id="orphan",
                        name="preview_classification_search",
                        response={"content": [{"type": "text", "text": "not-json"}]},
                    )
                ],
            )
        ]
        bundle = collect_handoff_from_events(
            events=events,
            invocation_id="inv-2",
            author=CLASSIFIER_NAME,
            system_description="A recruitment filter.",
            draft="draft",
        )
        self.assertFalse(bundle["handoff_ok"])
        self.assertIn("could not", bundle["handoff_error"].lower())

        class _State(dict):
            pass

        class _Ctx:
            def __init__(self, bundle):
                self.state = _State({EVIDENCE_STATE_KEY: bundle})

        skipped = EvidenceBook().before_critic(_Ctx(bundle))
        self.assertIsNotNone(skipped)
        skipped_text = "".join(
            part.text for part in skipped.parts if getattr(part, "text", None)
        )
        skipped_verdict = parse_critic_verdict(skipped_text)
        self.assertEqual(skipped_verdict["verdict"], "insufficient_evidence")

    def test_fabricated_citation_and_altered_quote_fail_deterministic_checks(
        self,
    ) -> None:
        direct = preview_classification_search(RECRUITMENT_QUERY)
        genuine = direct["matches"][0]["text"]
        records = [
            {
                "record_id": direct["matches"][0]["record_id"],
                "label": direct["matches"][0]["label"],
                "text": genuine,
                "text_sha256": direct["matches"][0]["text_sha256"],
            }
        ]
        supported = run_deterministic_checks(
            f'Provisional finding\n\n"{genuine[:80]}"\n\nSee Annex III, point 4.',
            records,
        )
        self.assertTrue(supported["ok"], supported)

        fabricated = run_deterministic_checks(
            f"See `{FABRICATED_ID}` and Article 5.",
            records,
        )
        self.assertFalse(fabricated["citation_ids"]["ok"])
        self.assertIn(FABRICATED_ID, fabricated["citation_ids"]["unknown"])

        altered = genuine.replace("natural persons", "legal persons", 1)
        self.assertNotEqual(altered, genuine)
        quote_fail = run_deterministic_checks(
            f'The statute says "{altered}"',
            records,
        )
        self.assertFalse(quote_fail["quotations"]["ok"])
        self.assertTrue(quote_fail["quotations"]["unsupported"])

    def test_deterministic_checks_stay_separate_from_model_verdict(self) -> None:
        parsed = parse_critic_verdict(
            '{"verdict": "supported", "findings": [], "scope_note": "x"}'
        )
        self.assertEqual(parsed["verdict"], "supported")
        checks = apply_deterministic_checks(
            {
                "classifier_draft": f"Unknown `{FABRICATED_ID}`",
                "records": [],
            }
        )
        self.assertFalse(checks["ok"])
        self.assertNotEqual(checks["ok"], parsed["verdict"] == "supported")

    def test_toolset_cleanup_does_not_leave_child_processes(self) -> None:
        import asyncio

        parent = os.getpid()
        before = _child_pids(parent)
        pipeline, toolset, _book = create_dual_preview_pipeline()
        self.assertEqual(pipeline.name, PIPELINE_NAME)
        asyncio.run(toolset.close())
        leftover = _child_pids(parent) - before
        self.assertEqual(leftover, set())

    def test_real_review_database_path_is_not_required(self) -> None:
        self.assertEqual(
            Path(DEFAULT_DB_PATH).name, "review_register.sqlite"
        )


if __name__ == "__main__":
    unittest.main()
