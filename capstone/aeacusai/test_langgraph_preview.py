"""Offline checks for the LangGraph classification-preview mirror.

These tests mock the model. They do not call Gemini, OpenAI, or Pinecone,
and they do not prove live model behavior.
"""

from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path

from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.evidence_checks import run_deterministic_checks
from aeacus_agent.langgraph_preview import (
    ALLOWED_TOOL,
    GRAPH_RECURSION_LIMIT,
    MAX_LLM_CALLS,
    compile_preview_graph,
    extract_function_calls,
    run_langgraph_preview,
    successful_retrieval,
    validate_tool_call,
)
from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION, aeacus_preview_agent
from aeacus_agent.review_register import DEFAULT_DB_PATH
from langgraph.graph import END, START
from langgraph.graph.state import CompiledStateGraph

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


class _FakePart:
    def __init__(self, text=None, function_call=None, thought=False):
        self.text = text
        self.function_call = function_call
        self.thought = thought


class _FakeContent:
    def __init__(self, parts, role="model"):
        self.parts = parts
        self.role = role


class _FakeResponse:
    def __init__(self, *, text="", calls=None, thought=None):
        parts = []
        if thought:
            parts.append(_FakePart(text=thought, thought=True))
        if calls:
            for call in calls:
                parts.append(_FakePart(function_call=call))
        if text:
            parts.append(_FakePart(text=text))
        self.content = _FakeContent(parts)
        self.candidates = [_FakeFn(content=self.content)]
        self.parts = parts
        self.function_calls = calls or []
        self.text = text


class _ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def __call__(self, state):
        self.calls += 1
        if not self.responses:
            raise RuntimeError("scripted model has no remaining responses")
        return self.responses.pop(0)


class LangGraphPreviewOfflineTests(unittest.TestCase):
    def test_adk_preview_agent_is_unchanged(self) -> None:
        self.assertEqual(aeacus_preview_agent.name, "aeacus_preview_agent")
        self.assertEqual(
            [getattr(tool, "__name__", "") for tool in aeacus_preview_agent.tools],
            ["preview_classification_search"],
        )
        self.assertIn("preview_classification_search", AEACUS_PREVIEW_INSTRUCTION)

    def test_compiled_graph_routing_and_nodes(self) -> None:
        graph = compile_preview_graph(
            model_fn=lambda state: _FakeResponse(text="unused"),
        )
        self.assertIsInstance(graph, CompiledStateGraph)
        self.assertEqual(graph.name, "aeacus_langgraph_preview")
        self.assertGreaterEqual(GRAPH_RECURSION_LIMIT, (MAX_LLM_CALLS * 2) + 2)
        self.assertIn(START, graph.nodes)
        for name in ("model", "tool", "evidence_check"):
            self.assertIn(name, graph.nodes)
        channels = getattr(graph, "get_graph", None)
        if callable(channels):
            drawable = graph.get_graph()
            edge_pairs = {
                (getattr(edge, "source", None), getattr(edge, "target", None))
                for edge in (getattr(drawable, "edges", None) or [])
            }
            self.assertIn(("model", "tool"), edge_pairs)
            self.assertIn(("model", "evidence_check"), edge_pairs)
            self.assertIn(("tool", "model"), edge_pairs)
            self.assertTrue(
                ("evidence_check", END) in edge_pairs
                or ("evidence_check", "__end__") in edge_pairs
            )

    def test_model_selected_query_is_dispatched_to_real_search(self) -> None:
        seen: list[str] = []

        def search(query: str) -> dict:
            seen.append(query)
            return preview_classification_search(query)

        chosen = "employment recruitment filter candidates Annex III"
        model = _ScriptedModel(
            [
                _FakeResponse(
                    calls=[
                        _FakeFn(
                            id="call_route",
                            name=ALLOWED_TOOL,
                            args={"query": chosen},
                        )
                    ]
                ),
                _FakeResponse(
                    text=(
                        "Provisional finding\n\nWhy\nAnnex III, point 4 applies.\n\n"
                        "What could change this\nArticle 6(3) may apply.\n\n"
                        "Missing facts\nWorkflow unknown.\n\n"
                        "Timing and scope\nLimited to Article 6, Annex III, and Article 113."
                    )
                ),
            ]
        )
        result = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=model,
            search_fn=search,
        )
        self.assertEqual(seen, [chosen])
        self.assertEqual(result["status"], "review_required")
        self.assertTrue(successful_retrieval(result["observations"]))
        self.assertEqual(result["observations"][0]["call_id"], "call_route")
        self.assertEqual(result["observations"][0]["query"], chosen)
        self.assertTrue(result["records"])
        self.assertTrue(result["records"][0]["text_sha256"])
        self.assertTrue(result["deterministic_checks"]["ok"])
        self.assertEqual(model.calls, 2)

    def test_unknown_tool_and_empty_query_are_rejected(self) -> None:
        ok, message = validate_tool_call(
            {"name": "search_legal_sources", "args": {"query": "x"}}
        )
        self.assertFalse(ok)
        self.assertIn("allowlisted", message)
        ok, message = validate_tool_call(
            {"name": ALLOWED_TOOL, "args": {"query": "   "}}
        )
        self.assertFalse(ok)
        result = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=lambda state: _FakeResponse(
                calls=[_FakeFn(id="c1", name="not_a_tool", args={"query": "x"})]
            ),
            search_fn=lambda query: self.fail(f"search should not run: {query}"),
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("allowlisted", result["error"] or "")

    def test_call_limit_is_enforced_before_recursion_limit(self) -> None:
        def always_tool(state):
            n = int(state.get("model_calls") or 0) + 1
            return _FakeResponse(
                calls=[
                    _FakeFn(
                        id=f"call_{n}",
                        name=ALLOWED_TOOL,
                        args={"query": f"recruitment pass {n}"},
                    )
                ]
            )

        result = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=always_tool,
            search_fn=preview_classification_search,
        )
        self.assertEqual(result["status"], "failed")
        self.assertIn("Call-limit exhaustion", result["error"] or "")
        self.assertEqual(result["model_calls"], MAX_LLM_CALLS)
        self.assertLessEqual(result["model_calls"], GRAPH_RECURSION_LIMIT)

    def test_provider_error_and_missing_retrieval_fail(self) -> None:
        provider = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=lambda state: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        self.assertEqual(provider["status"], "failed")
        self.assertIn("Provider/execution failure", provider["error"] or "")

        missing = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=lambda state: _FakeResponse(
                text="Provisional finding\n\nThis is high-risk under Article 6."
            ),
            search_fn=lambda query: self.fail("search must not be hardcoded"),
        )
        self.assertEqual(missing["status"], "failed")
        self.assertIn("without successful retrieval", missing["error"] or "")

    def test_fabricated_citation_fails_deterministic_checks(self) -> None:
        payload = preview_classification_search(RECRUITMENT_QUERY)
        draft = (
            "Provisional finding\n\n"
            f"See `{FABRICATED_ID}` and Annex III, point 4.\n\n"
            "What could change this\nUnknown.\n\n"
            "Missing facts\nNone stated.\n\n"
            "Timing and scope\nArticle 6 subset only."
        )
        checks = run_deterministic_checks(draft, [])
        self.assertFalse(checks["citation_ids"]["ok"])

        model = _ScriptedModel(
            [
                _FakeResponse(
                    calls=[
                        _FakeFn(
                            id="call_cite",
                            name=ALLOWED_TOOL,
                            args={"query": RECRUITMENT_QUERY},
                        )
                    ]
                ),
                _FakeResponse(text=draft),
            ]
        )
        result = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=model,
            search_fn=preview_classification_search,
        )
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["deterministic_checks"]["ok"])
        self.assertIn(FABRICATED_ID, result["deterministic_checks"]["citation_ids"]["unknown"])
        self.assertEqual(payload["status"], "ok")
        genuine = payload["matches"][0]["text"]
        quoted = genuine[:80]
        blockquote_draft = f'Provisional finding\n\n> "{quoted}"\n\nSee Annex III, point 4.'
        wrapped_ok = run_deterministic_checks(
            blockquote_draft,
            [
                {
                    "record_id": payload["matches"][0]["record_id"],
                    "label": payload["matches"][0]["label"],
                    "text": genuine,
                }
            ],
        )
        self.assertTrue(wrapped_ok["quotations"]["ok"], wrapped_ok)

    def test_hidden_thoughts_are_not_used_as_the_draft(self) -> None:
        calls = extract_function_calls(
            _FakeResponse(thought="hidden plan", text="Provisional finding")
        )
        self.assertEqual(calls, [])
        model = _ScriptedModel(
            [
                _FakeResponse(
                    thought="do not print this",
                    calls=[
                        _FakeFn(
                            id="call_thought",
                            name=ALLOWED_TOOL,
                            args={"query": RECRUITMENT_QUERY},
                        )
                    ],
                ),
                _FakeResponse(
                    thought="hidden critic notes",
                    text=(
                        "Provisional finding\n\nWhy\nAnnex III, point 4.\n\n"
                        "What could change this\nArticle 6(3).\n\n"
                        "Missing facts\nProfiling unknown.\n\n"
                        "Timing and scope\nArticle 6, Annex III, and Article 113 only."
                    ),
                ),
            ]
        )
        result = run_langgraph_preview(
            "A recruiter ranking system.",
            model_fn=model,
            search_fn=preview_classification_search,
        )
        self.assertEqual(result["status"], "review_required")
        self.assertNotIn("hidden critic notes", result["draft"])
        self.assertTrue(result["draft"].startswith("Provisional finding"))

    def test_review_database_is_not_opened(self) -> None:
        opened: list[str] = []
        original_connect = sqlite3.connect

        def guarded_connect(database, *args, **kwargs):
            opened.append(str(database))
            return original_connect(database, *args, **kwargs)

        sqlite3.connect = guarded_connect  # type: ignore[assignment]
        try:
            model = _ScriptedModel(
                [
                    _FakeResponse(
                        calls=[
                            _FakeFn(
                                id="call_db",
                                name=ALLOWED_TOOL,
                                args={"query": RECRUITMENT_QUERY},
                            )
                        ]
                    ),
                    _FakeResponse(
                        text=(
                            "Provisional finding\n\nWhy\nAnnex III, point 4.\n\n"
                            "What could change this\nArticle 6(3).\n\n"
                            "Missing facts\nUnknown.\n\n"
                            "Timing and scope\nArticle 6, Annex III, Article 113."
                        )
                    ),
                ]
            )
            result = run_langgraph_preview(
                "A recruiter ranking system.",
                model_fn=model,
                search_fn=preview_classification_search,
            )
            self.assertEqual(result["status"], "review_required")
            self.assertEqual(opened, [])
            self.assertEqual(Path(DEFAULT_DB_PATH).name, "review_register.sqlite")
        finally:
            sqlite3.connect = original_connect


if __name__ == "__main__":
    unittest.main()
