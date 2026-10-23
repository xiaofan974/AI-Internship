"""Offline Langfuse preview-export tests. No provider, retrieval, or SQLite."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from aeacus_agent.langfuse_preview import (
    EVIDENCE_SPAN_NAME,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
    ROOT_SPAN_NAME,
    TIMING_SPAN_NAME,
    PreviewLangfuseSession,
    attach_status,
    build_export_payload,
    config_status,
    empty_export_status,
    export_status_for_ui,
    tracing_enabled,
    tracing_opted_in,
)
from aeacus_agent.trace_store import TraceCapture, TraceCaptureConfig, build_trace_record


FAKE_GOOGLE = "AIzaSyDummyLangfusePreviewSecretValue999"
FAKE_LANGFUSE = "sk-lf-dummy-langfuse-preview-secret"


class _FakeAgent:
    name = "aeacus_preview_agent"
    model = "gemini-3.8-flash"
    instruction = "Frozen preview instruction."
    tools = []


def _capture() -> TraceCapture:
    capture = TraceCapture(
        config=TraceCaptureConfig(
            enabled=True,
            persist=False,
            scenario_id="langfuse_connection_smoke",
            entry_point="test_langfuse_preview",
        ),
        run_id="run-langfuse-test",
    )
    capture.events = [
        {
            "kind": "think",
            "thought": "hidden internal reasoning",
            "thought_text": "do not export",
        },
        {
            "kind": "act",
            "tool": "preview_classification_search",
            "query": "recruitment Annex III",
        },
        {
            "kind": "observe",
            "tool": "preview_classification_search",
            "payload": {
                "status": "ok",
                "query": "recruitment Annex III",
                "matches": [
                    {
                        "label": "Annex III, point 4",
                        "record_id": "record-4",
                        "text": "filter job applications",
                        "text_sha256": "hash-4",
                        "source_snapshot_id": "snap-1",
                    }
                ],
                "context_records": [
                    {
                        "label": "Article 6",
                        "record_id": "record-6",
                        "text": "complete parent text",
                        "text_sha256": "hash-6",
                        "source_snapshot_id": "snap-1",
                    }
                ],
            },
        },
        {"kind": "final", "text": "Provisional finding with secret " + FAKE_GOOGLE},
    ]
    build_trace_record(
        capture,
        agent=_FakeAgent(),
        user_input="Recruitment ranking system.",
        max_llm_calls=8,
        timeout_seconds=90,
        result="Provisional finding with secret " + FAKE_GOOGLE,
    )
    return capture


class LangfusePreviewOfflineTests(unittest.TestCase):
    def test_config_status_names_only(self) -> None:
        status = config_status()
        self.assertEqual(
            set(status),
            {
                "LANGFUSE_PUBLIC_KEY",
                "LANGFUSE_SECRET_KEY",
                "LANGFUSE_BASE_URL",
                "AEACUS_LANGFUSE_TRACING",
            },
        )
        for value in status.values():
            self.assertIn(value, {"configured", "missing"})
        blob = str(status)
        self.assertNotIn("pk-lf-", blob)
        self.assertNotIn("sk-lf-", blob)

    def test_tracing_is_opt_in(self) -> None:
        env = {
            "AEACUS_LANGFUSE_TRACING": "0",
            LANGFUSE_PUBLIC_KEY: "pk-lf-test",
            LANGFUSE_SECRET_KEY: FAKE_LANGFUSE,
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            from aeacus_agent import langfuse_preview as module

            module._ENV_LOADED = True
            self.assertFalse(tracing_opted_in())
            self.assertFalse(tracing_enabled())

    def test_placeholders_are_missing(self) -> None:
        env = {
            LANGFUSE_PUBLIC_KEY: "your_langfuse_public_key_here",
            LANGFUSE_SECRET_KEY: "your_langfuse_secret_key_here",
            "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
            "AEACUS_LANGFUSE_TRACING": "1",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            from aeacus_agent import langfuse_preview as module

            module._ENV_LOADED = True
            status = config_status()
            self.assertEqual(status[LANGFUSE_PUBLIC_KEY], "missing")
            self.assertEqual(status[LANGFUSE_SECRET_KEY], "missing")
            self.assertEqual(status["LANGFUSE_BASE_URL"], "configured")

    def test_payload_redacts_secrets_and_drops_thoughts(self) -> None:
        with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": FAKE_GOOGLE}, clear=False):
            capture = _capture()
            payload = build_export_payload(
                capture,
                raw_answer=capture.record["final_output"],
                delivered_answer="Delivered answer",
                timing_repair={
                    "formatter_id": "aeacus.timing_scope.v1",
                    "status": "ok",
                    "raw_output": capture.record["final_output"],
                    "delivered_output": "Delivered answer",
                    "source_text_sha256": "timing-hash",
                },
            )
        encoded = str(payload)
        self.assertNotIn(FAKE_GOOGLE, encoded)
        self.assertNotIn("hidden internal reasoning", encoded)
        self.assertTrue(all(event.get("kind") != "think" for event in payload["events"]))
        self.assertEqual(payload["delivered_answer"], "Delivered answer")
        self.assertEqual(len(payload["retrieved_evidence"]), 2)
        self.assertEqual(payload["retrieved_evidence"][0]["text_sha256"], "hash-4")
        self.assertIn("complete parent text", payload["retrieved_evidence"][1]["text"])
        self.assertEqual(payload["configuration"]["execution_limits"]["max_llm_calls"], 8)
        self.assertEqual(payload["instructions"]["sha256"], capture.record["instructions"]["sha256"])

    def test_disabled_session_does_not_change_assessment(self) -> None:
        capture = _capture()
        raw = "raw-assessment"
        with mock.patch.dict(os.environ, {"AEACUS_LANGFUSE_TRACING": "0"}, clear=False):
            from aeacus_agent import langfuse_preview as module

            module._ENV_LOADED = True
            with PreviewLangfuseSession(
                run_id=capture.run_id,
                entry_point="test",
                verify_remote=False,
            ) as session:
                session.complete(
                    capture,
                    raw_answer=raw,
                    delivered_answer="delivered",
                    timing_repair={"status": "ok"},
                )
        self.assertFalse(session.status["attempted"])
        self.assertFalse(session.status["exported"])
        self.assertEqual(raw, "raw-assessment")

    def test_export_failure_is_visible_and_non_fatal(self) -> None:
        capture = _capture()
        status = empty_export_status()
        status["attempted"] = True
        status["error"] = "flush failed"
        status["exported"] = False
        attach_status(capture, status)
        ui = export_status_for_ui(capture.record["langfuse"])
        self.assertTrue(ui["attempted"])
        self.assertFalse(ui["exported"])
        self.assertEqual(ui["error"], "flush failed")
        self.assertEqual(capture.record["execution_status"], "ok")

    def test_instrumentation_is_idempotent(self) -> None:
        class _Instrumentor:
            is_instrumented_by_opentelemetry = False
            calls = 0

            def instrument(self) -> None:
                self.calls += 1
                self.is_instrumented_by_opentelemetry = True

        fake = _Instrumentor()
        fake_mod = mock.Mock()
        fake_mod.GoogleADKInstrumentor = mock.Mock(return_value=fake)
        from aeacus_agent import langfuse_preview as module

        with mock.patch.dict(
            "sys.modules",
            {
                "openinference": mock.Mock(),
                "openinference.instrumentation": mock.Mock(),
                "openinference.instrumentation.google_adk": fake_mod,
            },
        ):
            with mock.patch.object(module, "_INSTRUMENTOR", None):
                first = module.ensure_instrumented()
                second = module.ensure_instrumented()
        self.assertEqual(fake.calls, 1)
        self.assertTrue(first["instrumented"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])

    def test_source_does_not_touch_other_architectures_or_live_services(self) -> None:
        source = Path("aeacus_agent/langfuse_preview.py").read_text(encoding="utf-8")
        self.assertNotIn("LiveJudgeTransport", source)
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("search_legal_sources", source)
        self.assertNotIn("aeacus_review_agent", source)
        self.assertNotIn("langgraph", source.lower())
        self.assertNotIn("mcp_preview", source)
        self.assertNotIn("dual_preview", source)
        self.assertNotIn("generate_content", source)
        self.assertIn("GoogleADKInstrumentor", source)
        self.assertIn("get_many", source)
        self.assertNotIn("api.trace.list", source)
        self.assertNotIn("langfuse.trace(", source)

    def test_expected_span_names_are_stable(self) -> None:
        self.assertEqual(ROOT_SPAN_NAME, "aeacus-adk-preview")
        self.assertEqual(EVIDENCE_SPAN_NAME, "application-evidence")
        self.assertEqual(TIMING_SPAN_NAME, "timing-renderer")


if __name__ == "__main__":
    unittest.main()
