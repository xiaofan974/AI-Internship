"""One live Langfuse connection smoke for the primary ADK preview.

Uses the recruitment sample. Existing 8-call / 90-second limits. No retries.
Writes a separate local JSONL path. Does not open the review register or
touch frozen Week 4 datasets.
"""

from __future__ import annotations

import asyncio
import json
import os

from aeacus_agent.langfuse_preview import (
    PreviewLangfuseSession,
    attach_status,
    auth_check_readonly,
    config_status,
    load_project_env,
    missing_credential_names,
)
from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.timing_scope import apply_timing_repair, records_from_events
from aeacus_agent.trace_store import (
    PROJECT_DIR,
    TraceCapture,
    TraceCaptureConfig,
    application_outcome,
    persist_trace,
    update_application_outcome,
)
from run_classification_preview import (
    SAMPLE_PREVIEW_PROMPT,
    _google_api_key_is_configured,
    offline_configuration_check,
)
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS, run_review

SCENARIO_ID = "langfuse_connection_smoke"
TRACE_PATH = PROJECT_DIR / "data" / "local" / "traces" / "week4_langfuse_connection_smoke.jsonl"
REPORT_PATH = PROJECT_DIR / "data" / "local" / "traces" / "week4_langfuse_connection_smoke_status.json"


def _print_status(label: str, status: dict) -> None:
    print(label)
    for key, value in status.items():
        print(f"  {key}: {value}")


async def main() -> int:
    load_project_env()
    os.environ["AEACUS_LANGFUSE_TRACING"] = "1"
    offline_configuration_check()
    _print_status("Langfuse configuration:", config_status())
    missing = missing_credential_names()
    if missing:
        print("Live Langfuse smoke skipped. Missing: " + ", ".join(missing))
        return 2
    if not _google_api_key_is_configured():
        print("Live Langfuse smoke skipped. Missing: GOOGLE_API_KEY")
        return 2

    auth = auth_check_readonly()
    print(f"Langfuse auth_check: {'ok' if auth.get('ok') else 'failed'}")
    if auth.get("error"):
        print(f"Langfuse auth_check error: {auth['error']}")
    if not auth.get("ok"):
        print("Live Langfuse smoke skipped after failed read-only authentication.")
        return 3

    capture = TraceCapture(
        config=TraceCaptureConfig(
            enabled=True,
            persist=False,
            output_path=TRACE_PATH,
            scenario_id=SCENARIO_ID,
            entry_point="run_langfuse_preview_smoke.main",
            extra={
                "id": "langfuse_connection_smoke",
                "note": "Separate Langfuse connection smoke. Not part of either frozen 20-run dataset.",
            },
        )
    )
    session = PreviewLangfuseSession(
        run_id=capture.run_id,
        entry_point="run_langfuse_preview_smoke.main",
        verify_remote=True,
    )
    with session:
        result = await run_review(
            SAMPLE_PREVIEW_PROMPT,
            agent=aeacus_preview_agent,
            max_llm_calls=MAX_LLM_CALLS,
            timeout_seconds=RUN_TIMEOUT_SECONDS,
            capture=capture,
        )
        timed_out = "timed out" in str(result).lower()
        execution_status = (
            "timed_out"
            if timed_out
            else (
                "ok"
                if result and not str(result).startswith("[FAILED]")
                else "failed"
            )
        )
        visible = result if execution_status == "ok" else None
        timing = None
        if execution_status == "ok":
            repair = apply_timing_repair(result, records_from_events(capture.events))
            visible = repair.delivered_output
            timing = repair.to_dict()
            if capture.record is not None:
                capture.record["timing_repair"] = timing
                capture.record["final_output"] = visible
        update_application_outcome(
            capture,
            application_outcome(
                execution_status=execution_status,
                visible_answer=visible,
                failure_message=None if execution_status == "ok" else result,
                pending_review=None,
                pending_review_observed=False,
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
    capture.config.persist = True
    persist_trace(capture)

    export = {
        "run_id": capture.run_id,
        "execution_status": capture.record.get("execution_status") if capture.record else None,
        "local_trace_path": str(TRACE_PATH),
        "langfuse": {
            key: session.status.get(key)
            for key in (
                "attempted",
                "exported",
                "flushed",
                "retrieved",
                "trace_id",
                "trace_url",
                "observation_names",
                "missing_observations",
                "error",
                "config",
                "missing",
            )
        },
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(export, indent=2) + "\n", encoding="utf-8")
    print(f"local run_id: {capture.run_id}")
    print(f"execution_status: {export['execution_status']}")
    print(f"langfuse exported: {session.status.get('exported')}")
    print(f"langfuse flushed: {session.status.get('flushed')}")
    print(f"langfuse retrieved: {session.status.get('retrieved')}")
    print(f"langfuse trace_id: {session.status.get('trace_id')}")
    print(f"langfuse trace_url: {session.status.get('trace_url')}")
    print(f"langfuse observation_names: {session.status.get('observation_names')}")
    print(f"langfuse missing_observations: {session.status.get('missing_observations')}")
    if session.status.get("error"):
        print(f"langfuse error: {session.status['error']}")
    print("Review register: not opened")
    return 0 if session.status.get("exported") and export["execution_status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
