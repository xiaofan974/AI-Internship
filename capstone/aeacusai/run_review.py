"""
Bounded ADK runner with event tracing for AeacusAI.
"""

import asyncio
from contextlib import aclosing
import json
import os
import re
import time
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.runners import RunConfig, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors as genai_errors
from google.genai import types

from aeacus_agent import aeacus_review_agent
from aeacus_agent.trace_store import (
    TraceCapture,
    application_outcome,
    build_trace_record,
    extract_usage_metadata,
    persist_trace,
    provider_id_or_none,
    utc_now,
)

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

APP_NAME = "aeacusai_review"
DEFAULT_USER_ID = "reviewer_1"
MAX_LLM_CALLS = 8
RUN_TIMEOUT_SECONDS = 90
MAX_PAYLOAD_CHARS = 200


def _redact_sensitive(text: str) -> str:
    """Redact any configured API keys or tokens from text."""
    redacted = str(text)
    for env_key in (
        "GOOGLE_API_KEY",
        "OPENAI_API_KEY",
        "PINECONE_API_KEY",
        "SUPABASE_ACCESS_TOKEN",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
    ):
        secret = os.getenv(env_key)
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    redacted = re.sub(r"AIza[0-9A-Za-z\-_]{20,}", "[REDACTED]", redacted)
    redacted = re.sub(r"pcsk_[0-9A-Za-z\-_]{20,}", "[REDACTED]", redacted)
    redacted = re.sub(r"sk-[0-9A-Za-z\-_]{20,}", "[REDACTED]", redacted)
    return redacted


def _format_payload(payload, max_chars: int = MAX_PAYLOAD_CHARS) -> str:
    """Format and truncate a tool argument or response payload safely."""
    try:
        raw = json.dumps(payload, default=str, ensure_ascii=False)
    except Exception:
        raw = str(payload)
    raw = _redact_sensitive(" ".join(raw.split()))
    if len(raw) > max_chars:
        return f"{raw[:max_chars]}... [truncated]"
    return raw


def _redact_value(value):
    """Redact secrets inside nested tool payloads without changing structure."""
    if isinstance(value, str):
        return _redact_sensitive(value)
    if isinstance(value, dict):
        return {key: _redact_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value


def _unwrap_tool_payload(payload) -> dict:
    if not isinstance(payload, dict):
        return {}
    nested = payload.get("result")
    if isinstance(nested, dict) and "status" not in payload:
        return nested
    return payload


def _label_list(body: dict, compact_key: str, records_key: str) -> list[str]:
    compact = body.get(compact_key)
    if isinstance(compact, list) and compact:
        return [str(item) for item in compact if item]
    labels: list[str] = []
    for item in body.get(records_key) or []:
        if isinstance(item, dict) and item.get("label"):
            labels.append(str(item["label"]))
    return labels


def _emit(on_event, event: dict) -> None:
    if on_event is None:
        return
    on_event(_redact_value(event))


def _capture_visible_event(capture: TraceCapture | None, event: dict) -> None:
    if capture is None or not capture.collecting:
        return
    capture.events.append(event)


def _capture_usage(capture: TraceCapture | None, adk_event) -> None:
    if capture is None or not capture.collecting:
        return
    usage = extract_usage_metadata(adk_event)
    if not usage:
        return
    capture.usage_events.append(
        {
            "author": getattr(adk_event, "author", None),
            "usage": usage,
        }
    )


def _finish_capture(
    capture: TraceCapture | None,
    *,
    agent,
    system_description: str,
    max_llm_calls: int,
    timeout_seconds: int,
    result: str | None,
    timed_out: bool = False,
    started_perf: float | None = None,
) -> None:
    if capture is None or not capture.config.enabled or capture.skipped:
        return
    capture.ended_at = utc_now()
    if started_perf is not None:
        capture.elapsed_ms = round((time.perf_counter() - started_perf) * 1000, 3)
    execution_status = "timed_out" if timed_out else (
        "ok"
        if result and not str(result).startswith("[FAILED]")
        else "failed"
    )
    visible = result if execution_status == "ok" else None
    failure = None if execution_status == "ok" else result
    build_trace_record(
        capture,
        agent=agent,
        user_input=system_description,
        max_llm_calls=max_llm_calls,
        timeout_seconds=timeout_seconds,
        result=result,
        timed_out=timed_out,
        application_outcome_value=application_outcome(
            execution_status=execution_status,
            visible_answer=visible,
            failure_message=failure,
            pending_review_observed=False,
        ),
    )
    if capture.config.persist:
        persist_trace(capture)


async def run_review(
    system_description: str,
    agent=aeacus_review_agent,
    max_llm_calls: int = MAX_LLM_CALLS,
    timeout_seconds: int = RUN_TIMEOUT_SECONDS,
    max_payload_chars: int = MAX_PAYLOAD_CHARS,
    tool_log: list | None = None,
    on_event=None,
    capture: TraceCapture | None = None,
) -> str:
    """Run a single bounded review with ADK event tracing.

    Optional `agent` preserves the existing Pinecone default. Optional
    `max_payload_chars`, `tool_log`, and `on_event` do not change default
    tracing or the returned final-answer string.

    TRACE capture is off unless `capture` is provided and enabled for
    `aeacus_preview_agent`. Other agents are not written to the ADK
    preview baseline.
    """
    if capture is not None and capture.config.enabled:
        capture.gate_agent(agent)
        if capture.collecting:
            capture.started_at = utc_now()
    started_perf = time.perf_counter()
    service = InMemorySessionService()
    run_config = RunConfig(max_llm_calls=max_llm_calls)
    content = types.Content(role="user", parts=[types.Part(text=system_description)])
    final_response = None
    final_author = None

    try:
        async with asyncio.timeout(timeout_seconds):
            async with Runner(
                agent=agent,
                app_name=APP_NAME,
                session_service=service,
            ) as runner:
                session = await service.create_session(
                    app_name=APP_NAME,
                    user_id=DEFAULT_USER_ID,
                )
                async with aclosing(
                    runner.run_async(
                        user_id=DEFAULT_USER_ID,
                        session_id=session.id,
                        new_message=content,
                        run_config=run_config,
                    )
                ) as event_stream:
                    async for event in event_stream:
                        author = getattr(event, "author", None) or "unknown"
                        _capture_usage(capture, event)

                        if getattr(event, "error_code", None) or getattr(
                            event, "error_message", None
                        ):
                            raise RuntimeError(
                                f"Event error ({event.error_code}): {event.error_message}"
                            )

                        for fc in event.get_function_calls():
                            tool_name = fc.name or "unknown_tool"
                            args = dict(fc.args) if fc.args else {}
                            provider_call_id = provider_id_or_none(fc)
                            association = None
                            if capture is not None and capture.collecting:
                                association = capture.associator.register_call(
                                    provider_call_id
                                )
                            if tool_log is not None:
                                entry = {
                                    "type": "call",
                                    "author": author,
                                    "tool": tool_name,
                                    "args": args,
                                }
                                if association is not None:
                                    entry["provider_call_id"] = association[
                                        "provider_call_id"
                                    ]
                                    entry["association_key"] = association[
                                        "association_key"
                                    ]
                                tool_log.append(entry)
                            if tool_name == "transfer_to_agent":
                                target = args.get("agent_name", "unknown_agent")
                                action = f"transfer_to_agent -> {target}"
                            else:
                                action = f"call tool {tool_name}"
                            _emit(
                                on_event,
                                {
                                    "kind": "think",
                                    "action": action,
                                },
                            )
                            _emit(
                                on_event,
                                {
                                    "kind": "act",
                                    "tool": tool_name,
                                    "query": args.get("query"),
                                },
                            )
                            _capture_visible_event(
                                capture,
                                {
                                    "kind": "act",
                                    "author": author,
                                    "tool": tool_name,
                                    "query": args.get("query"),
                                    "arguments": args,
                                    "provider_call_id": association[
                                        "provider_call_id"
                                    ]
                                    if association
                                    else provider_call_id,
                                    "association_key": association[
                                        "association_key"
                                    ]
                                    if association
                                    else None,
                                },
                            )
                            print(
                                f"[THINK] {author} selected next action: {action}"
                            )
                            print(
                                f"[ACT] {author} -> {tool_name}("
                                f"{_format_payload(args, max_payload_chars)})"
                            )

                        for fr in event.get_function_responses():
                            tool_name = fr.name or "unknown_tool"
                            payload = fr.response if fr.response is not None else {}
                            provider_response_id = provider_id_or_none(fr)
                            association = None
                            if capture is not None and capture.collecting:
                                association = capture.associator.register_response(
                                    provider_response_id
                                )
                            if tool_log is not None:
                                entry = {
                                    "type": "response",
                                    "author": author,
                                    "tool": tool_name,
                                    "payload": payload,
                                }
                                if association is not None:
                                    entry["provider_call_id"] = association[
                                        "provider_call_id"
                                    ]
                                    entry["association_key"] = association[
                                        "association_key"
                                    ]
                                tool_log.append(entry)
                            transfer_target = getattr(
                                getattr(event, "actions", None),
                                "transfer_to_agent",
                                None,
                            )
                            body = _unwrap_tool_payload(payload)
                            _emit(
                                on_event,
                                {
                                    "kind": "observe",
                                    "tool": tool_name,
                                    "status": body.get("status"),
                                    "match_labels": _label_list(
                                        body, "match_labels", "matches"
                                    ),
                                    "context_labels": _label_list(
                                        body, "context_labels", "context_records"
                                    ),
                                    "payload": body,
                                },
                            )
                            _capture_visible_event(
                                capture,
                                {
                                    "kind": "observe",
                                    "author": author,
                                    "tool": tool_name,
                                    "status": body.get("status"),
                                    "arguments": None,
                                    "provider_call_id": association[
                                        "provider_call_id"
                                    ]
                                    if association
                                    else provider_response_id,
                                    "association_key": association[
                                        "association_key"
                                    ]
                                    if association
                                    else None,
                                    "payload": body,
                                },
                            )
                            if tool_name == "transfer_to_agent" and transfer_target:
                                print(
                                    f"[OBSERVE] {author} <- {tool_name}: "
                                    f"transferred to {transfer_target} | "
                                    f"payload={_format_payload(payload, max_payload_chars)}"
                                )
                            else:
                                print(
                                    f"[OBSERVE] {author} <- {tool_name}: "
                                    f"{_format_payload(payload, max_payload_chars)}"
                                )

                        if (
                            event.is_final_response()
                            and event.content
                            and event.content.parts
                        ):
                            visible_parts = [
                                part.text
                                for part in event.content.parts
                                if getattr(part, "text", None)
                                and not getattr(part, "thought", False)
                            ]
                            if visible_parts:
                                final_response = "\n".join(visible_parts).strip()
                                final_author = author

        if not final_response:
            failure_msg = "[FAILED] Run completed without a valid final response."
            _emit(on_event, {"kind": "failed", "message": failure_msg})
            _capture_visible_event(
                capture, {"kind": "failed", "message": failure_msg}
            )
            print(failure_msg)
            _finish_capture(
                capture,
                agent=agent,
                system_description=system_description,
                max_llm_calls=max_llm_calls,
                timeout_seconds=timeout_seconds,
                result=failure_msg,
                started_perf=started_perf,
            )
            return failure_msg

        _emit(
            on_event,
            {
                "kind": "final",
                "author": final_author,
                "text": final_response,
            },
        )
        _capture_visible_event(
            capture,
            {
                "kind": "final",
                "author": final_author,
                "text": final_response,
            },
        )
        print(f"[FINAL] {final_author}: {_format_payload(final_response)}")
        _finish_capture(
            capture,
            agent=agent,
            system_description=system_description,
            max_llm_calls=max_llm_calls,
            timeout_seconds=timeout_seconds,
            result=final_response,
            started_perf=started_perf,
        )
        return final_response

    except TimeoutError:
        failure_msg = (
            f"[FAILED] Run timed out after {timeout_seconds} seconds "
            "(partial output discarded)."
        )
        _emit(on_event, {"kind": "failed", "message": failure_msg})
        _capture_visible_event(
            capture, {"kind": "failed", "message": failure_msg}
        )
        print(failure_msg)
        _finish_capture(
            capture,
            agent=agent,
            system_description=system_description,
            max_llm_calls=max_llm_calls,
            timeout_seconds=timeout_seconds,
            result=failure_msg,
            timed_out=True,
            started_perf=started_perf,
        )
        return failure_msg
    except LlmCallsLimitExceededError as exc:
        failure_msg = (
            f"[FAILED] Call-limit exhaustion (max_llm_calls={max_llm_calls}): "
            f"{_redact_sensitive(str(exc))}"
        )
        _emit(on_event, {"kind": "failed", "message": failure_msg})
        _capture_visible_event(
            capture, {"kind": "failed", "message": failure_msg}
        )
        print(failure_msg)
        _finish_capture(
            capture,
            agent=agent,
            system_description=system_description,
            max_llm_calls=max_llm_calls,
            timeout_seconds=timeout_seconds,
            result=failure_msg,
            started_perf=started_perf,
        )
        return failure_msg
    except (genai_errors.APIError, Exception) as exc:
        failure_msg = (
            f"[FAILED] Provider/execution failure ({type(exc).__name__}): "
            f"{_redact_sensitive(str(exc))}"
        )
        _emit(on_event, {"kind": "failed", "message": failure_msg})
        _capture_visible_event(
            capture, {"kind": "failed", "message": failure_msg}
        )
        print(failure_msg)
        _finish_capture(
            capture,
            agent=agent,
            system_description=system_description,
            max_llm_calls=max_llm_calls,
            timeout_seconds=timeout_seconds,
            result=failure_msg,
            started_perf=started_perf,
        )
        return failure_msg


async def main() -> None:
    sample_description = (
        "An automated resume-screening AI used by an EU employer to rank job "
        "applicants and filter out candidates before human interview selection."
    )
    print("--- AEACUSAI PRELIMINARY REVIEW ---")
    print(f"Submitted System: {sample_description}\n")
    result = await run_review(sample_description)
    print(f"\nReview Output:\n{result}\n")


if __name__ == "__main__":
    asyncio.run(main())
