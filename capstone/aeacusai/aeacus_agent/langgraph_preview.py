"""LangGraph mirror of the single-agent classification preview.

LangGraph owns the model/tool loop. This module does not wrap the ADK
Runner, open the review database, or add a critic or MCP path.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Callable, Literal, TypedDict

from google.genai import types
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph

from .agent import MODEL
from .context_preview import preview_classification_search
from .evidence_checks import run_deterministic_checks
from .mcp_payload import records_from_decoded
from .preview_agent import AEACUS_PREVIEW_INSTRUCTION

ALLOWED_TOOL = "preview_classification_search"
MAX_LLM_CALLS = 8
RUN_TIMEOUT_SECONDS = 90
GRAPH_RECURSION_LIMIT = 24
REVIEW_REQUIRED = "review_required"
FAILED = "failed"
RUNNING = "running"

SEARCH_TOOL = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name=ALLOWED_TOOL,
            description=(
                "Search the pinned local Article 6, Annex III, and Article 113 "
                "classification subset. Choose the query yourself. Call this "
                "before making any source-based findings."
            ),
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Lexical search query chosen by the model.",
                    )
                },
                required=["query"],
            ),
        )
    ]
)


class PreviewState(TypedDict, total=False):
    system_description: str
    messages: list[dict[str, Any]]
    pending_calls: list[dict[str, Any]]
    observations: list[dict[str, Any]]
    records: list[dict[str, Any]]
    model_calls: int
    draft: str
    status: str
    error: str | None
    deterministic_checks: dict[str, Any]
    trace: list[dict[str, Any]]
    started_monotonic: float


ModelFn = Callable[[PreviewState], Any]
SearchFn = Callable[[str], dict[str, Any]]


def visible_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    parts = getattr(content, "parts", None) or []
    texts = [
        str(part.text)
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    ]
    return "\n".join(texts).strip()


def _fail(state: PreviewState, message: str) -> dict[str, Any]:
    trace = list(state.get("trace") or [])
    trace.append({"kind": "failed", "message": message})
    print(f"[FAILED] {message}")
    return {
        "status": FAILED,
        "error": message,
        "pending_calls": [],
        "trace": trace,
    }


def _time_exceeded(state: PreviewState) -> bool:
    started = float(state.get("started_monotonic") or 0.0)
    if not started:
        return False
    return (time.monotonic() - started) > RUN_TIMEOUT_SECONDS


def _content_to_dict(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if hasattr(content, "model_dump"):
        dumped = content.model_dump(exclude_none=True)
        if isinstance(dumped, dict) and dumped.get("parts") is not None:
            return dumped
    parts: list[dict[str, Any]] = []
    for part in getattr(content, "parts", None) or []:
        item: dict[str, Any] = {}
        if getattr(part, "text", None):
            item["text"] = part.text
        if getattr(part, "thought", False):
            item["thought"] = True
        fc = getattr(part, "function_call", None)
        if fc:
            item["function_call"] = {
                "id": getattr(fc, "id", None),
                "name": getattr(fc, "name", None),
                "args": dict(getattr(fc, "args", None) or {}),
            }
        fr = getattr(part, "function_response", None)
        if fr:
            item["function_response"] = {
                "id": getattr(fr, "id", None),
                "name": getattr(fr, "name", None),
                "response": getattr(fr, "response", None),
            }
        if item:
            parts.append(item)
    return {"role": getattr(content, "role", "model") or "model", "parts": parts}


def extract_function_calls(response: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    raw_calls = getattr(response, "function_calls", None) or []
    if not raw_calls:
        parts = getattr(response, "parts", None) or []
        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                raw_calls.append(fc)
    for index, fc in enumerate(raw_calls, start=1):
        call_id = getattr(fc, "id", None) or f"call_{index}"
        args = dict(getattr(fc, "args", None) or {})
        calls.append(
            {
                "id": str(call_id),
                "name": getattr(fc, "name", None),
                "args": args,
            }
        )
    return calls


def validate_tool_call(call: dict[str, Any]) -> tuple[bool, str]:
    name = call.get("name")
    if name != ALLOWED_TOOL:
        return False, f"Tool {name!r} is not allowlisted."
    args = call.get("args")
    if not isinstance(args, dict):
        return False, "Tool arguments must be an object."
    extra = set(args) - {"query"}
    if extra:
        return False, f"Unexpected tool arguments: {sorted(extra)}."
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return False, "preview_classification_search requires a non-empty query string."
    return True, query.strip()


def successful_retrieval(observations: list[dict[str, Any]]) -> bool:
    for item in observations or []:
        payload = item.get("payload") or {}
        if payload.get("status") == "ok" and (
            payload.get("matches") or payload.get("context_records")
        ):
            return True
    return False


def gemini_model_fn(state: PreviewState) -> Any:
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured.")
    client = genai.Client(api_key=api_key)
    contents = [
        types.Content.model_validate(item) for item in (state.get("messages") or [])
    ]
    config = types.GenerateContentConfig(
        system_instruction=AEACUS_PREVIEW_INSTRUCTION,
        tools=[SEARCH_TOOL],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    return client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=config,
    )


def compile_preview_graph(
    *,
    model_fn: ModelFn | None = None,
    search_fn: SearchFn | None = None,
):
    """Compile the StateGraph. model_fn/search_fn are injectable for tests."""
    run_model = model_fn or gemini_model_fn
    run_search = search_fn or preview_classification_search

    def model_node(state: PreviewState) -> dict[str, Any]:
        if state.get("status") == FAILED:
            return {}
        if _time_exceeded(state):
            return _fail(
                state,
                f"Run timed out after {RUN_TIMEOUT_SECONDS} seconds "
                "(partial output discarded).",
            )
        calls_used = int(state.get("model_calls") or 0)
        if calls_used >= MAX_LLM_CALLS:
            return _fail(
                state,
                f"Call-limit exhaustion (max_llm_calls={MAX_LLM_CALLS}).",
            )
        messages = list(state.get("messages") or [])
        if not messages:
            messages.append(
                _content_to_dict(
                    types.Content(
                        role="user",
                        parts=[types.Part(text=state.get("system_description") or "")],
                    )
                )
            )
        try:
            response = run_model({**state, "messages": messages})
        except Exception as exc:
            return _fail(
                state,
                f"Provider/execution failure ({type(exc).__name__}): {exc}",
            )
        calls = extract_function_calls(response)
        model_content = None
        candidates = getattr(response, "candidates", None) or []
        if candidates and getattr(candidates[0], "content", None) is not None:
            model_content = candidates[0].content
        elif getattr(response, "content", None) is not None:
            model_content = response.content
        draft = visible_text(model_content) or visible_text(response)
        if model_content is not None:
            messages.append(_content_to_dict(model_content))
        trace = list(state.get("trace") or [])
        if calls:
            for call in calls:
                print(
                    f"[THINK] langgraph_preview selected next action: "
                    f"call tool {call.get('name')}"
                )
                print(
                    f"[ACT] langgraph_preview -> {call.get('name')}("
                    f"{json.dumps(call.get('args') or {}, ensure_ascii=False)})"
                )
                trace.append(
                    {
                        "kind": "act",
                        "tool": call.get("name"),
                        "query": (call.get("args") or {}).get("query"),
                        "call_id": call.get("id"),
                    }
                )
            return {
                "messages": messages,
                "pending_calls": calls,
                "model_calls": calls_used + 1,
                "draft": "",
                "status": RUNNING,
                "trace": trace,
            }
        if not draft:
            return _fail(state, "Model finished without visible text or a tool call.")
        print(f"[FINAL] langgraph_preview: {draft[:200]}...")
        trace.append({"kind": "final", "chars": len(draft)})
        return {
            "messages": messages,
            "pending_calls": [],
            "model_calls": calls_used + 1,
            "draft": draft,
            "status": RUNNING,
            "trace": trace,
        }

    def tool_node(state: PreviewState) -> dict[str, Any]:
        if state.get("status") == FAILED:
            return {}
        if _time_exceeded(state):
            return _fail(
                state,
                f"Run timed out after {RUN_TIMEOUT_SECONDS} seconds "
                "(partial output discarded).",
            )
        pending = list(state.get("pending_calls") or [])
        if not pending:
            return _fail(state, "Tool node reached without a model-selected tool call.")
        messages = list(state.get("messages") or [])
        observations = list(state.get("observations") or [])
        records = list(state.get("records") or [])
        seen_ids = {item.get("record_id") for item in records if item.get("record_id")}
        trace = list(state.get("trace") or [])
        response_parts: list[types.Part] = []
        for call in pending:
            ok, detail = validate_tool_call(call)
            if not ok:
                return _fail(state, detail)
            payload = run_search(detail)
            if not isinstance(payload, dict):
                return _fail(state, "Search tool returned a non-object payload.")
            observation = {
                "call_id": call.get("id"),
                "tool": ALLOWED_TOOL,
                "query": detail,
                "payload": payload,
            }
            observations.append(observation)
            for record in records_from_decoded(payload):
                record_id = record.get("record_id")
                if record_id and record_id not in seen_ids:
                    seen_ids.add(record_id)
                    records.append(record)
            compact = {
                "status": payload.get("status"),
                "match_record_ids": payload.get("match_record_ids") or [],
                "context_record_ids": payload.get("context_record_ids") or [],
            }
            print(
                f"[OBSERVE] langgraph_preview <- {ALLOWED_TOOL}: "
                f"{json.dumps(compact, ensure_ascii=False)}"
            )
            trace.append(
                {
                    "kind": "observe",
                    "call_id": call.get("id"),
                    "tool": ALLOWED_TOOL,
                    "query": detail,
                    **compact,
                }
            )
            response_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        id=call.get("id"),
                        name=ALLOWED_TOOL,
                        response=payload,
                    )
                )
            )
        messages.append(
            _content_to_dict(types.Content(role="user", parts=response_parts))
        )
        return {
            "messages": messages,
            "pending_calls": [],
            "observations": observations,
            "records": records,
            "trace": trace,
        }

    def evidence_check_node(state: PreviewState) -> dict[str, Any]:
        if state.get("status") == FAILED:
            return {}
        if _time_exceeded(state):
            return _fail(
                state,
                f"Run timed out after {RUN_TIMEOUT_SECONDS} seconds "
                "(partial output discarded).",
            )
        draft = (state.get("draft") or "").strip()
        observations = list(state.get("observations") or [])
        records = list(state.get("records") or [])
        if not successful_retrieval(observations):
            return _fail(
                state,
                "Final classification without successful retrieval is not allowed.",
            )
        if not draft:
            return _fail(state, "Model finished after retrieval without a visible draft.")
        checks = run_deterministic_checks(draft, records)
        print("[CHECKS] " + json.dumps({"ok": checks.get("ok")}, ensure_ascii=False))
        if not checks.get("ok"):
            return {
                **_fail(
                    state,
                    "Deterministic citation or quotation checks failed.",
                ),
                "deterministic_checks": checks,
                "draft": draft,
            }
        trace = list(state.get("trace") or [])
        trace.append({"kind": "review_required", "checks_ok": True})
        return {
            "status": REVIEW_REQUIRED,
            "error": None,
            "draft": draft,
            "deterministic_checks": checks,
            "trace": trace,
        }

    def route_after_model(state: PreviewState) -> Literal["tool", "evidence_check", "__end__"]:
        if state.get("status") == FAILED:
            return "__end__"
        if state.get("pending_calls"):
            return "tool"
        return "evidence_check"

    def route_after_tool(state: PreviewState) -> Literal["model", "__end__"]:
        if state.get("status") == FAILED:
            return "__end__"
        return "model"

    graph = StateGraph(PreviewState)
    graph.add_node("model", model_node)
    graph.add_node("tool", tool_node)
    graph.add_node("evidence_check", evidence_check_node)
    graph.add_edge(START, "model")
    graph.add_conditional_edges(
        "model",
        route_after_model,
        {"tool": "tool", "evidence_check": "evidence_check", "__end__": END},
    )
    graph.add_conditional_edges(
        "tool",
        route_after_tool,
        {"model": "model", "__end__": END},
    )
    graph.add_edge("evidence_check", END)
    return graph.compile(name="aeacus_langgraph_preview")


def initial_state(system_description: str) -> PreviewState:
    return {
        "system_description": system_description,
        "messages": [
            types.Content(
                role="user",
                parts=[types.Part(text=system_description)],
            ).model_dump(exclude_none=True)
        ],
        "pending_calls": [],
        "observations": [],
        "records": [],
        "model_calls": 0,
        "draft": "",
        "status": RUNNING,
        "error": None,
        "deterministic_checks": {},
        "trace": [],
        "started_monotonic": time.monotonic(),
    }


def run_langgraph_preview(
    system_description: str,
    *,
    model_fn: ModelFn | None = None,
    search_fn: SearchFn | None = None,
    recursion_limit: int = GRAPH_RECURSION_LIMIT,
) -> PreviewState:
    """Run the compiled graph once. Does not open the review database."""
    graph = compile_preview_graph(model_fn=model_fn, search_fn=search_fn)
    state = initial_state(system_description)
    try:
        result = graph.invoke(state, {"recursion_limit": recursion_limit})
    except GraphRecursionError as exc:
        failed = _fail(
            state,
            f"Graph recursion limit reached ({recursion_limit}): {exc}",
        )
        return {**state, **failed}
    return result


def new_call_id() -> str:
    return f"call_{uuid.uuid4().hex[:8]}"
