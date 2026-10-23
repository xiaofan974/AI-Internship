"""Offline TRACE capture tests. No Gemini, OpenAI, or Pinecone calls."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION
from aeacus_agent.trace_store import (
    ALLOWED_AGENT_NAME,
    SCHEMA_VERSION,
    CallAssociator,
    TraceCapture,
    TraceCaptureConfig,
    application_outcome,
    build_trace_record,
    persist_trace,
    provider_id_or_none,
    read_jsonl,
    redact_secret_text,
    usage_summary,
)
from streamlit_app import SAMPLE_PREVIEW_PROMPT, finalize_preview_result


STATUTE = (
    "AI systems intended to be used for the recruitment or selection of natural "
    "persons, in particular to place targeted job advertisements, to analyse and "
    "filter job applications, and to evaluate candidates;"
)
FAKE_KEY = "AIzaSyDummyTraceCaptureSecretValue999"


class _FakeAgent:
    name = ALLOWED_AGENT_NAME
    model = "gemini-3.8-flash"
    instruction = AEACUS_PREVIEW_INSTRUCTION
    tools = [preview_classification_search]


class _OtherAgent:
    name = "aeacus_review_agent"
    model = "gemini-3.8-flash"
    instruction = "other"
    tools = []


def _observe_payload() -> dict:
    return {
        "status": "ok",
        "query": "recruitment",
        "matches": [
            {
                "label": "Annex III, point 4",
                "record_id": "T1-AIA-CONS-20260727@sha256:abc::annex/III/point/4",
                "source_snapshot_id": "T1-AIA-CONS-20260727@sha256:abc",
                "text": STATUTE,
                "text_sha256": "statute-hash",
            }
        ],
        "context_records": [
            {
                "label": "Article 6",
                "record_id": "T1-AIA-CONS-20260727@sha256:abc::article/6",
                "source_snapshot_id": "T1-AIA-CONS-20260727@sha256:abc",
                "text": "Complete Article 6 parent text.",
                "text_sha256": "article-hash",
            }
        ],
    }


def _capture(path: Path, **kwargs) -> TraceCapture:
    config = TraceCaptureConfig(
        enabled=True,
        persist=True,
        output_path=path,
        scenario_id=kwargs.get("scenario_id"),
        entry_point=kwargs.get("entry_point", "test_trace_store"),
    )
    capture = TraceCapture(config=config, run_id=kwargs.get("run_id", "run-test"))
    capture.started_at = "2026-10-22T00:00:00+00:00"
    capture.ended_at = "2026-10-22T00:00:01+00:00"
    capture.elapsed_ms = 1000.0
    return capture


def _success_events(association_key: str, provider_call_id: str | None) -> list[dict]:
    return [
        {
            "kind": "think",
            "action": "call tool preview_classification_search",
            "thought": "hidden model scratchpad must not persist",
        },
        {
            "kind": "act",
            "author": "aeacus_preview_agent",
            "tool": "preview_classification_search",
            "query": "recruitment",
            "arguments": {"query": "recruitment"},
            "provider_call_id": provider_call_id,
            "association_key": association_key,
        },
        {
            "kind": "observe",
            "author": "aeacus_preview_agent",
            "tool": "preview_classification_search",
            "status": "ok",
            "provider_call_id": provider_call_id,
            "association_key": association_key,
            "payload": _observe_payload(),
        },
        {
            "kind": "final",
            "author": "aeacus_preview_agent",
            "text": "### Provisional finding\nThe system is provisionally classified.",
        },
    ]


class CallAssociationTests(unittest.TestCase):
    def test_provider_id_absent_stays_null(self) -> None:
        self.assertIsNone(provider_id_or_none(None))
        self.assertIsNone(provider_id_or_none(""))
        self.assertIsNone(provider_id_or_none(type("X", (), {"id": None})()))

    def test_call_and_response_share_trace_local_key(self) -> None:
        associator = CallAssociator()
        call = associator.register_call(None)
        response = associator.register_response(None)
        self.assertIsNone(call["provider_call_id"])
        self.assertEqual(call["association_key"], "trace_call_1")
        self.assertEqual(response["association_key"], call["association_key"])

    def test_provider_ids_pair_without_invention(self) -> None:
        associator = CallAssociator()
        first = associator.register_call("call_aaa")
        second = associator.register_call("call_bbb")
        matched = associator.register_response("call_bbb")
        self.assertEqual(first["provider_call_id"], "call_aaa")
        self.assertEqual(matched["association_key"], second["association_key"])
        self.assertEqual(matched["provider_call_id"], "call_bbb")


class TraceStoreTests(unittest.TestCase):
    def test_full_tool_response_text_survives_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adk_preview.jsonl"
            capture = _capture(path, run_id="run-full-text")
            capture.events = _success_events("trace_call_1", None)
            build_trace_record(
                capture,
                agent=_FakeAgent(),
                user_input=SAMPLE_PREVIEW_PROMPT,
                max_llm_calls=8,
                timeout_seconds=90,
                result="### Provisional finding\nThe system is provisionally classified.",
            )
            persist_trace(capture)
            saved = read_jsonl(path)[0]
            observe = next(item for item in saved["events"] if item["kind"] == "observe")
            self.assertEqual(observe["payload"]["matches"][0]["text"], STATUTE)
            self.assertEqual(
                observe["payload"]["context_records"][0]["text"],
                "Complete Article 6 parent text.",
            )
            self.assertIn(STATUTE, json.dumps(saved, ensure_ascii=False))

    def test_hidden_thoughts_and_secrets_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adk_preview.jsonl"
            capture = _capture(path)
            events = _success_events("trace_call_1", None)
            events[2]["payload"]["matches"][0]["text"] = (
                STATUTE + " credential=" + FAKE_KEY
            )
            events.append(
                {
                    "kind": "final",
                    "text": "ok",
                    "thought": "should be stripped",
                }
            )
            capture.events = events
            with mock.patch.dict(os.environ, {"GOOGLE_API_KEY": FAKE_KEY}):
                build_trace_record(
                    capture,
                    agent=_FakeAgent(),
                    user_input=f"system uses key {FAKE_KEY}",
                    max_llm_calls=8,
                    timeout_seconds=90,
                    result="### Provisional finding\nVisible only.",
                )
                persist_trace(capture)
            saved = read_jsonl(path)[0]
            dumped = json.dumps(saved)
            self.assertNotIn(FAKE_KEY, dumped)
            self.assertNotIn("hidden model scratchpad", dumped)
            kinds = [item["kind"] for item in saved["events"]]
            self.assertNotIn("think", kinds)
            observe = next(item for item in saved["events"] if item["kind"] == "observe")
            self.assertIn(STATUTE, observe["payload"]["matches"][0]["text"])
            self.assertIn("[REDACTED]", observe["payload"]["matches"][0]["text"])
            self.assertEqual(saved["instructions"]["text"], AEACUS_PREVIEW_INSTRUCTION)
            self.assertNotIn("thought", saved["events"][-1])

    def test_success_failure_and_timeout_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adk_preview.jsonl"
            cases = [
                (
                    "run-ok",
                    "### Provisional finding\nVisible.",
                    False,
                    "ok",
                    "### Provisional finding\nVisible.",
                    None,
                ),
                (
                    "run-fail",
                    "[FAILED] Provider/execution failure (RuntimeError): boom",
                    False,
                    "failed",
                    None,
                    "[FAILED] Provider/execution failure (RuntimeError): boom",
                ),
                (
                    "run-timeout",
                    "[FAILED] Run timed out after 90 seconds (partial output discarded).",
                    True,
                    "timed_out",
                    None,
                    "[FAILED] Run timed out after 90 seconds (partial output discarded).",
                ),
            ]
            for run_id, result, timed_out, status, output, error in cases:
                capture = _capture(path, run_id=run_id)
                capture.events = [
                    {"kind": "act", "association_key": "trace_call_1", "provider_call_id": None},
                    {"kind": "observe", "association_key": "trace_call_1", "payload": _observe_payload()},
                    {"kind": "failed", "message": error} if status != "ok" else {"kind": "final", "text": output},
                ]
                build_trace_record(
                    capture,
                    agent=_FakeAgent(),
                    user_input=SAMPLE_PREVIEW_PROMPT,
                    max_llm_calls=8,
                    timeout_seconds=90,
                    result=result,
                    timed_out=timed_out,
                )
                persist_trace(capture)
            records = {item["run_id"]: item for item in read_jsonl(path)}
            self.assertEqual(records["run-ok"]["execution_status"], "ok")
            self.assertEqual(records["run-ok"]["final_output"], "### Provisional finding\nVisible.")
            self.assertIsNone(records["run-fail"]["final_output"])
            self.assertEqual(records["run-fail"]["execution_status"], "failed")
            self.assertIsNone(records["run-timeout"]["final_output"])
            self.assertEqual(records["run-timeout"]["execution_status"], "timed_out")
            self.assertIn("partial output discarded", records["run-timeout"]["error"])

    def test_missing_usage_remains_unknown(self) -> None:
        summary = usage_summary([])
        self.assertEqual(summary["status"], "unknown")
        self.assertIsNone(summary["prompt_token_count"])
        self.assertIsNone(summary["total_token_count"])
        last_then_first = usage_summary(
            [
                {"usage": {"prompt_token_count": 10, "total_token_count": 12}},
                {"usage": {"prompt_token_count": 22, "total_token_count": 30}},
            ]
        )
        self.assertEqual(last_then_first["aggregation"], "last_observed_not_summed")
        self.assertEqual(last_then_first["total_token_count"], 30)
        self.assertNotEqual(last_then_first["total_token_count"], 42)

    def test_consecutive_and_concurrent_writes_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adk_preview.jsonl"
            errors: list[str] = []

            def _write(index: int) -> None:
                try:
                    capture = _capture(path, run_id=f"run-{index}")
                    capture.events = _success_events("trace_call_1", None)
                    build_trace_record(
                        capture,
                        agent=_FakeAgent(),
                        user_input=f"input {index}",
                        max_llm_calls=8,
                        timeout_seconds=90,
                        result=f"### Provisional finding\nAnswer {index}",
                    )
                    persist_trace(capture)
                    if not capture.persistence["saved"]:
                        errors.append(str(capture.persistence))
                except Exception as exc:  # pragma: no cover - test failure path
                    errors.append(str(exc))

            _write(0)
            _write(1)
            threads = [threading.Thread(target=_write, args=(index,)) for index in range(2, 8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            records = read_jsonl(path)
            self.assertEqual(len(records), 8)
            ids = {item["run_id"] for item in records}
            self.assertEqual(ids, {f"run-{index}" for index in range(8)})
            for item in records:
                json.loads(json.dumps(item))
                self.assertEqual(item["schema_version"], SCHEMA_VERSION)

    def test_wrong_agent_is_not_written_to_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "adk_preview.jsonl"
            capture = _capture(path)
            self.assertFalse(capture.gate_agent(_OtherAgent()))
            persist_trace(capture)
            self.assertFalse(path.exists())
            self.assertFalse(capture.persistence["saved"])
            self.assertIn("agent_not_in_baseline", capture.persistence["skipped"] or "")

    def test_persist_failure_is_explicit_and_not_marked_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocker = Path(tmp) / "not-a-directory"
            blocker.write_text("nope", encoding="utf-8")
            path = blocker / "adk_preview.jsonl"
            capture = _capture(path)
            capture.events = _success_events("trace_call_1", None)
            build_trace_record(
                capture,
                agent=_FakeAgent(),
                user_input=SAMPLE_PREVIEW_PROMPT,
                max_llm_calls=8,
                timeout_seconds=90,
                result="### Provisional finding\nVisible.",
            )
            persistence = persist_trace(capture)
            self.assertFalse(persistence["saved"])
            self.assertIsNotNone(persistence["error"])
            self.assertFalse(capture.record["capture"]["complete"])

    def test_application_outcome_does_not_claim_register_write(self) -> None:
        outcome = application_outcome(
            execution_status="ok",
            visible_answer="draft",
            failure_message=None,
            pending_review={
                "status": "review_required",
                "digest": "abc",
                "artifact": {"run_id": "pending-1"},
            },
            pending_review_observed=True,
        )
        self.assertEqual(outcome["register_opened"], "not_observed")
        self.assertEqual(outcome["register_written"], "not_observed")
        self.assertEqual(outcome["pending_review"]["storage"], "session_local_not_register")

    def test_redact_does_not_truncate_statutory_text(self) -> None:
        text = STATUTE + " " + FAKE_KEY + " " + STATUTE
        redacted = redact_secret_text(text)
        self.assertIn(STATUTE, redacted)
        self.assertNotIn(FAKE_KEY, redacted)
        self.assertLess(len(redacted), len(text) + 20)

    def test_finalize_preview_result_unchanged(self) -> None:
        evidence = [
            {
                "label": "Annex III, point 4",
                "record_id": "T1-AIA-CONS-20260727@sha256:abc::annex/III/point/4",
                "text": STATUTE,
            }
        ]
        result = finalize_preview_result(
            "### Provisional finding\nThe facts match Annex III, point 4.",
            evidence,
        )
        self.assertTrue(result["ok"])
        self.assertIn("Annex III, point 4", result["displayed_answer"])


if __name__ == "__main__":
    unittest.main()
