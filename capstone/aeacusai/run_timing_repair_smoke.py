"""One live TRACE-S02 integration smoke for the timing renderer.

Does not write to the frozen 20-run datasets or the review register.
"""

from __future__ import annotations

import asyncio

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
from evals.week4.baseline import load_scenarios
from run_classification_preview import _google_api_key_is_configured, offline_configuration_check
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS, run_review

SCENARIO_ID = "timing_repair_smoke"
TRACE_PATH = PROJECT_DIR / "data" / "local" / "traces" / "timing_repair_smoke.jsonl"


async def main() -> int:
    offline_configuration_check()
    if not _google_api_key_is_configured():
        print("Live smoke stopped: GOOGLE_API_KEY is not configured.")
        return 2
    scenarios = {item.id: item.input for item in load_scenarios(
        PROJECT_DIR / "evals" / "week4" / "scenarios_v1.json"
    )}
    prompt = scenarios["TRACE-S02"]
    capture = TraceCapture(
        config=TraceCaptureConfig(
            enabled=True,
            persist=False,
            output_path=TRACE_PATH,
            scenario_id=SCENARIO_ID,
            entry_point="run_timing_repair_smoke.main",
            extra={
                "id": "timing_repair_smoke",
                "source_scenario_id": "TRACE-S02",
                "note": "Separate integration smoke. Not part of either frozen 20-run dataset.",
            },
        )
    )
    result = await run_review(
        prompt,
        agent=aeacus_preview_agent,
        max_llm_calls=MAX_LLM_CALLS,
        timeout_seconds=RUN_TIMEOUT_SECONDS,
        capture=capture,
    )
    if capture.record is None:
        print("Live smoke failed: no trace record.")
        return 5
    timed_out = "timed out" in str(result).lower()
    execution_status = (
        "timed_out"
        if timed_out
        else ("ok" if result and not str(result).startswith("[FAILED]") else "failed")
    )
    visible = None
    if execution_status == "ok":
        repair = apply_timing_repair(result, records_from_events(capture.events))
        visible = repair.delivered_output
        capture.record["timing_repair"] = repair.to_dict()
        capture.record["final_output"] = visible
        print(f"timing_repair.status: {repair.status}")
        print(f"timing_repair.reason: {repair.reason}")
        print(f"source_record_id: {repair.source_record_id}")
        print(f"source_text_sha256: {repair.source_text_sha256}")
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
    capture.config.persist = True
    persistence = persist_trace(capture)
    print(f"scenario_id: {SCENARIO_ID}")
    print(f"source_scenario_id: TRACE-S02")
    print(f"run_id: {capture.run_id}")
    print(f"status: {execution_status}")
    print(f"capture_saved: {persistence.get('saved')}")
    print(f"path: {persistence.get('path')}")
    print("excluded_from_frozen_datasets: true")
    print("review_register: not opened")
    if capture.record.get("timing_repair"):
        print("\n--- RAW ---\n")
        print(capture.record["timing_repair"]["raw_output"])
        print("\n--- DELIVERED ---\n")
        print(capture.record["timing_repair"]["delivered_output"])
    return 0 if persistence.get("saved") else 5


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
