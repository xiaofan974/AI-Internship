"""Bounded ADK runner for the local classification preview demo.

Reuses `run_review()` and its event-tracing safeguards (`MAX_LLM_CALLS = 8`,
`RUN_TIMEOUT_SECONDS = 90`, hidden-thought filtering, full stream consumption
inside `aclosing(...)`, and explicit failure reporting) while passing
`agent=aeacus_preview_agent`.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import os
import re
from pathlib import Path
from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
CITED_ID_RE = re.compile(
    r"T1-AIA-[A-Z0-9-]+@sha256:[a-f0-9]{64}::[A-Za-z0-9/._-]+"
)
OBSERVE_PAYLOAD_CHARS = 4000


def _google_api_key_is_configured() -> bool:
    value = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(value) and value != GOOGLE_API_KEY_PLACEHOLDER


def _load_local_google_api_key() -> None:
    """Load GOOGLE_API_KEY only. Do not load OpenAI or Pinecone credentials."""
    load_dotenv(THIS_DIR / ".env")
    if _google_api_key_is_configured():
        return
    bootcamp_env = (
        REPO_ROOT
        / "ai-engineering-bootcamp"
        / "adk-multi-agent-systems"
        / ".env"
    )
    if not bootcamp_env.exists():
        return
    for raw_line in bootcamp_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "GOOGLE_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        if value and value != GOOGLE_API_KEY_PLACEHOLDER:
            os.environ["GOOGLE_API_KEY"] = value
        break


_load_local_google_api_key()

from aeacus_agent.agent import MODEL, aeacus_review_agent
from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.retrieval import search_legal_sources
from aeacus_agent.timing_scope import apply_timing_repair, records_from_events
from aeacus_agent.trace_store import (
    TraceCapture,
    TraceCaptureConfig,
    application_outcome,
    capture_enabled_from_env,
    persist_trace,
    update_application_outcome,
)
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS, run_review

SAMPLE_PREVIEW_PROMPT = (
    "A company uses an AI system to analyse and filter job applications and rank "
    "candidates for recruiters. Recruiters make the final hiring decision. Give a "
    "provisional classification assessment against the pinned corpus, identify "
    "relevant exceptions, and state which additional facts are needed."
)


def offline_configuration_check() -> None:
    """Confirm the preview agent is a single local-tool agent and that the
    Pinecone review agent is unchanged. Importing this module must not make
    provider calls.
    """
    assert aeacus_preview_agent.name == "aeacus_preview_agent"
    assert aeacus_preview_agent.model == MODEL
    assert len(aeacus_preview_agent.tools) == 1
    assert aeacus_preview_agent.tools[0] is preview_classification_search
    assert getattr(aeacus_preview_agent, "sub_agents", []) == []
    assert list(inspect.signature(preview_classification_search).parameters) == [
        "query"
    ]
    assert len(aeacus_review_agent.tools) == 1
    assert aeacus_review_agent.tools[0] is search_legal_sources
    assert getattr(aeacus_review_agent, "sub_agents", []) == []
    print("offline configuration check: passed")
    print("preview agent tools: ['preview_classification_search']")
    print("preview agent sub-agents: []")
    print("pinecone agent tools unchanged: ['search_legal_sources']")


def _unwrap_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        return {}
    result = payload.get("result")
    if isinstance(result, dict):
        return result
    return payload


def _observation_ids(tool_log: list) -> list[str]:
    seen: list[str] = []
    for event in tool_log:
        if event.get("type") != "response":
            continue
        body = _unwrap_payload(event.get("payload"))
        for key in ("match_record_ids", "context_record_ids"):
            for record_id in body.get(key) or []:
                if record_id not in seen:
                    seen.append(record_id)
        for group in ("matches", "context_records"):
            for item in body.get(group) or []:
                if not isinstance(item, dict):
                    continue
                record_id = item.get("record_id")
                if record_id and record_id not in seen:
                    seen.append(record_id)
    return seen


def _print_tool_summary(tool_log: list, final_answer: str) -> None:
    calls = [event for event in tool_log if event.get("type") == "call"]
    responses = [event for event in tool_log if event.get("type") == "response"]
    print("\n--- TOOL CALL SUMMARY ---")
    if not calls:
        print("No tool calls were made.")
        return
    for index, event in enumerate(calls, start=1):
        args = event.get("args") or {}
        print(f"call {index}: {event.get('tool')} query={args.get('query')!r}")
    for index, event in enumerate(responses, start=1):
        body = _unwrap_payload(event.get("payload"))
        print(
            f"response {index}: status={body.get('status')!r} "
            f"match_ids={body.get('match_record_ids') or []} "
            f"context_ids={body.get('context_record_ids') or []}"
        )
        if body.get("status") == "error":
            error = body.get("error") or {}
            print(
                f"response {index} error: "
                f"category={error.get('category')!r} "
                f"message={error.get('message')!r}"
            )

    observed_ids = _observation_ids(tool_log)
    cited_ids = list(dict.fromkeys(CITED_ID_RE.findall(final_answer or "")))
    missing = [record_id for record_id in cited_ids if record_id not in observed_ids]
    print(f"cited record IDs: {cited_ids}")
    print(f"cited IDs missing from tool observations: {missing}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the AeacusAI classification preview agent."
    )
    parser.add_argument(
        "--scenario-id",
        default=None,
        help="Optional TRACE scenario ID (for example capture_smoke).",
    )
    return parser.parse_args(argv)


def _print_trace_persistence(capture: TraceCapture | None) -> None:
    if capture is None:
        print("TRACE capture: disabled")
        return
    persistence = capture.persistence or {}
    if persistence.get("skipped"):
        print(f"TRACE capture skipped: {persistence['skipped']}")
        return
    if persistence.get("saved"):
        print(
            "TRACE capture saved: "
            f"path={persistence.get('path')} run_id={capture.run_id} "
            f"scenario_id={capture.config.scenario_id!r}"
        )
        return
    print(
        "TRACE capture FAILED: complete saved trace was not written. "
        f"error={persistence.get('error')!r} path={persistence.get('path')!r}"
    )


async def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    offline_configuration_check()
    if not _google_api_key_is_configured():
        print("Live run skipped: GOOGLE_API_KEY is not configured.")
        return

    print("\n--- AEACUSAI CLASSIFICATION PREVIEW ---")
    print(f"Submitted System: {SAMPLE_PREVIEW_PROMPT}\n")
    tool_log: list = []
    capture = None
    if capture_enabled_from_env(default=True):
        capture = TraceCapture(
            config=TraceCaptureConfig(
                enabled=True,
                persist=False,
                scenario_id=args.scenario_id,
                entry_point="run_classification_preview.main",
            )
        )
    from aeacus_agent.langfuse_preview import PreviewLangfuseSession, attach_status

    session = PreviewLangfuseSession(
        run_id=None if capture is None else capture.run_id,
        entry_point="run_classification_preview.main",
        verify_remote=False,
    )
    with session:
        result = await run_review(
            SAMPLE_PREVIEW_PROMPT,
            agent=aeacus_preview_agent,
            max_llm_calls=MAX_LLM_CALLS,
            timeout_seconds=RUN_TIMEOUT_SECONDS,
            max_payload_chars=OBSERVE_PAYLOAD_CHARS,
            tool_log=tool_log,
            capture=capture,
        )
        timed_out = "timed out" in str(result).lower()
        execution_status = (
            "timed_out"
            if timed_out
            else ("ok" if result and not str(result).startswith("[FAILED]") else "failed")
        )
        visible = result if execution_status == "ok" else None
        timing = None
        if capture is not None and capture.record is not None:
            if execution_status == "ok":
                repair = apply_timing_repair(
                    result, records_from_events(capture.events)
                )
                visible = repair.delivered_output
                timing = repair.to_dict()
                capture.record["timing_repair"] = timing
                capture.record["final_output"] = visible
            update_application_outcome(
                capture,
                application_outcome(
                    execution_status=execution_status,
                    visible_answer=visible,
                    failure_message=None if execution_status == "ok" else result,
                    pending_review=None,
                    pending_review_observed=True,
                ),
            )
        session.complete(
            capture,
            raw_answer=result,
            delivered_answer=visible,
            timing_repair=timing,
            error=None if execution_status == "ok" else result,
        )
    attach_status(capture, session.status)
    if capture is not None and capture.record is not None:
        capture.config.persist = True
        persist_trace(capture)
    print(f"\nRaw model output:\n{result}\n")
    if capture is not None and capture.record and capture.record.get("timing_repair"):
        print(
            "\nDelivered output:\n"
            f"{capture.record['timing_repair']['delivered_output']}\n"
        )
    _print_tool_summary(tool_log, result)
    _print_trace_persistence(capture)
    if session.status.get("attempted") and not session.status.get("exported"):
        print(
            "Langfuse export FAILED. Assessment outcome unchanged. "
            f"error={session.status.get('error')!r}"
        )
    elif session.status.get("flushed"):
        print(
            "Langfuse flush completed. Remote retrieval is verified only "
            "by the dedicated connection smoke."
        )


if __name__ == "__main__":
    asyncio.run(main())
