"""Mocked Streamlit UI checks for the classification preview.

These tests never call Gemini, OpenAI, or Pinecone.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from streamlit_app import SAMPLE_PREVIEW_PROMPT, finalize_preview_result

os.environ["AEACUS_UI_DISABLE_LIVE"] = "1"


def _visible_text(at: AppTest) -> str:
    chunks: list[str] = []
    for attr in (
        "title",
        "header",
        "subheader",
        "markdown",
        "text",
        "caption",
        "error",
        "info",
        "warning",
        "success",
        "metric",
    ):
        for item in getattr(at, attr, []):
            value = getattr(item, "value", None)
            if value:
                chunks.append(str(value))
    for exp in at.expander:
        label = getattr(exp, "label", "")
        if label:
            chunks.append(str(label))
    return "\n".join(chunks)

KNOWN_AREA4_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715"
    "::annex/III/point/4"
)
KNOWN_ART6_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715"
    "::article/6"
)
UNKNOWN_ART5_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    "::article/5"
)

SUCCESS_ANSWER = f"""Provisional finding

The described system is used to analyse and filter job applications and rank candidates.

## Why

The submitted facts match Annex III, point 4 (`{KNOWN_AREA4_ID}`).

## What could change this

Whether filtering excludes applications from recruiter review is unknown, so material influence is not established.

## Missing facts

- Whether recruiters see every filtered application.

## Timing and scope

This reading uses Article 6 (`{KNOWN_ART6_ID}`) and is limited to the pinned classification subset.
"""

UNKNOWN_CITATION_ANSWER = SUCCESS_ANSWER.replace(
    f"The submitted facts match Annex III, point 4 (`{KNOWN_AREA4_ID}`).",
    (
        f"The submitted facts match Annex III, point 4 (`{KNOWN_AREA4_ID}`). "
        f"An extra citation not returned in this run is {UNKNOWN_ART5_ID}."
    ),
)

SUCCESS_PAYLOAD = {
    "status": "ok",
    "retrieval_mode": "local_lexical_preview",
    "corpus_scope": "Article 6 and Annex III classification subset",
    "scope_and_review_notice": (
        "Local lexical preview over the pinned Article 6 and Annex III subset only."
    ),
    "match_labels": ["Annex III, point 4"],
    "context_labels": ["Article 6 — Classification rules for high-risk AI systems"],
    "matches": [
        {
            "label": "Annex III, point 4",
            "record_id": KNOWN_AREA4_ID,
            "text": "AI systems intended to be used for the recruitment or selection of natural persons.",
            "source_location": {
                "url": "https://publications.europa.eu/example-annex-iii-point-4"
            },
        }
    ],
    "context_records": [
        {
            "label": "Article 6 — Classification rules for high-risk AI systems",
            "record_id": KNOWN_ART6_ID,
            "text": "Complete Article 6 parent text for classification rules.",
            "source_location": {
                "url": "https://publications.europa.eu/example-article-6"
            },
        }
    ],
}


def _follow_reruns(at: AppTest, *, max_extra: int = 4) -> AppTest:
    for _ in range(max_extra):
        if not at.session_state.get("running") and not at.session_state.get(
            "pending_run"
        ):
            break
        at.run(timeout=5)
    return at


def _fake_success(description: str, on_event) -> dict:
    on_event(
        {"kind": "think", "action": "call tool preview_classification_search"}
    )
    on_event(
        {
            "kind": "act",
            "tool": "preview_classification_search",
            "query": "recruitment filter job applications",
        }
    )
    on_event(
        {
            "kind": "observe",
            "tool": "preview_classification_search",
            "status": "ok",
            "match_labels": SUCCESS_PAYLOAD["match_labels"],
            "context_labels": SUCCESS_PAYLOAD["context_labels"],
            "payload": SUCCESS_PAYLOAD,
        }
    )
    on_event({"kind": "final", "text": SUCCESS_ANSWER})
    from streamlit_app import evidence_from_observe_payload

    return finalize_preview_result(
        SUCCESS_ANSWER, evidence_from_observe_payload(SUCCESS_PAYLOAD)
    )


def _fake_failure(description: str, on_event) -> dict:
    on_event(
        {"kind": "think", "action": "call tool preview_classification_search"}
    )
    on_event(
        {
            "kind": "failed",
            "message": "[FAILED] Provider/execution failure (RuntimeError): mocked failure",
        }
    )
    return {
        "ok": False,
        "failure": "[FAILED] Provider/execution failure (RuntimeError): mocked failure",
        "assessment": None,
        "missing_facts": [],
        "evidence": [],
        "raw_answer": None,
        "citation_map": [],
        "unknown_references": [],
    }


class StreamlitPreviewUiTests(unittest.TestCase):
    def test_initial_page_makes_zero_provider_calls(self) -> None:
        calls: list[str] = []

        def forbidden(description: str, on_event) -> dict:
            calls.append(description)
            raise AssertionError("runner must not run on the initial page")

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = forbidden
        at.run()

        self.assertEqual(calls, [])
        self.assertEqual(at.session_state.invocation_count, 0)
        self.assertFalse(at.session_state.running)
        self.assertIn("AeacusAI", at.title[0].value)
        page_text = _visible_text(at)
        self.assertIn("Classification preview", page_text)
        self.assertTrue(any("27 July 2026" in md.value for md in at.markdown))
        self.assertFalse(at.session_state.assessment)
        self.assertEqual(at.session_state.trace, [])

    def test_running_state_disables_controls_without_model_call(self) -> None:
        calls: list[str] = []

        def forbidden(description: str, on_event) -> dict:
            calls.append(description)
            raise AssertionError("runner must not run while an in-progress flag is shown")

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = forbidden
        at.session_state["running"] = True
        at.session_state["pending_run"] = False
        at.session_state["description"] = SAMPLE_PREVIEW_PROMPT
        at.run()

        self.assertEqual(calls, [])
        self.assertEqual(at.session_state.invocation_count, 0)
        self.assertTrue(at.button(key="run_assessment").disabled)
        self.assertTrue(at.button(key="load_example").disabled)
        self.assertTrue(at.button(key="clear_results").disabled)
        self.assertTrue(
            any("Running assessment" in info.value for info in at.info)
        )

    def test_mocked_success_displays_trace_and_answer(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)

        self.assertEqual(calls, [SAMPLE_PREVIEW_PROMPT])
        self.assertEqual(at.session_state.invocation_count, 1)
        self.assertFalse(at.session_state.running)
        self.assertIsNone(at.session_state.failure)
        self.assertIn("Annex III, point 4", at.session_state.assessment)
        self.assertTrue(
            any("recruiters see every filtered application" in item for item in at.session_state.missing_facts)
        )
        kinds = [event["kind"] for event in at.session_state.trace]
        self.assertEqual(kinds, ["think", "act", "observe", "final", "review_required"])
        page_text = _visible_text(at)
        self.assertIn("THINK:", page_text)
        self.assertIn("ACT:", page_text)
        self.assertIn("OBSERVE:", page_text)
        self.assertIn("FINAL:", page_text)
        expander_labels = [exp.label for exp in at.expander]
        self.assertTrue(any("Search match: Annex III, point 4" in label for label in expander_labels))
        self.assertTrue(any("Expanded context:" in label for label in expander_labels))
        self.assertEqual(
            at.session_state.evidence[0]["text"],
            "AI systems intended to be used for the recruitment or selection of natural persons.",
        )
        self.assertEqual(
            at.session_state.evidence[0]["url"],
            "https://publications.europa.eu/example-annex-iii-point-4",
        )
        self.assertNotIn("Epistemic Assessment", at.session_state.assessment)
        self.assertNotIn("Epistemic Assessment", page_text)
        self.assertNotIn(KNOWN_AREA4_ID, at.session_state.assessment)
        self.assertEqual(at.session_state.raw_answer, SUCCESS_ANSWER)
        self.assertIn(KNOWN_AREA4_ID, at.session_state.raw_answer)
        self.assertIn(
            "This reading uses Article 6",
            at.session_state.raw_answer,
        )
        self.assertNotIn(
            "This reading uses Article 6",
            at.session_state.assessment,
        )
        self.assertEqual(
            at.session_state.pending_review["artifact"]["assessment"],
            at.session_state.displayed_answer,
        )
        self.assertNotEqual(
            at.session_state.pending_review["artifact"]["assessment"],
            at.session_state.raw_answer,
        )
        self.assertEqual(
            [item["record_id"] for item in at.session_state.citation_map],
            [KNOWN_AREA4_ID, KNOWN_ART6_ID],
        )
        expander_labels = [exp.label for exp in at.expander]
        self.assertTrue(
            any("Observed source map" in label for label in expander_labels)
        )
        self.assertTrue(
            any("Raw answer and full identifiers" in label for label in expander_labels)
        )

    def test_mocked_failure_resets_interface_and_hides_earlier_answer(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            if len(calls) == 1:
                return _fake_success(description, on_event)
            return _fake_failure(description, on_event)

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertIsNotNone(at.session_state.assessment)

        at.button(key="run_assessment").click().run()
        _follow_reruns(at)

        self.assertEqual(len(calls), 2)
        self.assertFalse(at.session_state.running)
        self.assertIsNone(at.session_state.assessment)
        self.assertEqual(at.session_state.missing_facts, [])
        self.assertIn("mocked failure", at.session_state.failure)
        self.assertTrue(any("mocked failure" in err.value for err in at.error))
        page_text = "\n".join(item.value for item in at.markdown)
        self.assertNotIn(
            "The submitted facts match Annex III, point 4",
            page_text,
        )

    def test_ordinary_reruns_do_not_repeat_a_completed_invocation(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertEqual(len(calls), 1)

        at.run()
        at.run()
        self.assertEqual(len(calls), 1)
        self.assertEqual(at.session_state.invocation_count, 1)
        self.assertIsNotNone(at.session_state.assessment)

    def test_unknown_citation_is_flagged_and_not_deleted(self) -> None:
        def fake(description: str, on_event) -> dict:
            on_event(
                {"kind": "think", "action": "call tool preview_classification_search"}
            )
            on_event(
                {
                    "kind": "observe",
                    "tool": "preview_classification_search",
                    "status": "ok",
                    "match_labels": SUCCESS_PAYLOAD["match_labels"],
                    "context_labels": SUCCESS_PAYLOAD["context_labels"],
                    "payload": SUCCESS_PAYLOAD,
                }
            )
            on_event({"kind": "final", "text": UNKNOWN_CITATION_ANSWER})
            from streamlit_app import evidence_from_observe_payload

            return finalize_preview_result(
                UNKNOWN_CITATION_ANSWER,
                evidence_from_observe_payload(SUCCESS_PAYLOAD),
            )

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = fake
        at.run()
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)

        self.assertEqual(at.session_state.unknown_references, [UNKNOWN_ART5_ID])
        self.assertIn(UNKNOWN_ART5_ID, at.session_state.assessment)
        self.assertIn(UNKNOWN_ART5_ID, at.session_state.raw_answer)
        self.assertNotIn(KNOWN_AREA4_ID, at.session_state.assessment)
        self.assertTrue(
            any("Unknown source references" in warn.value for warn in at.warning)
        )

    def test_evaluations_view_is_offline_and_shows_separate_findings(self) -> None:
        calls: list[str] = []

        def forbidden(description: str, on_event) -> dict:
            calls.append(description)
            raise AssertionError("evaluations view must not run an assessment")

        at = AppTest.from_file("streamlit_app.py", default_timeout=20)
        at.session_state["preview_runner"] = forbidden
        at.run()
        at.radio(key="ui_view").set_value("Week 4 evaluations").run(timeout=20)

        self.assertEqual(calls, [])
        self.assertEqual(at.session_state.invocation_count, 0)
        self.assertFalse(at.session_state.assessment)
        page = _visible_text(at)
        self.assertIn("Timing qualification checks", page)
        self.assertIn("18/20 passed (90%)", page)
        self.assertIn("20/20 passed (100%)", page)
        self.assertIn("+10 percentage points", page)
        self.assertIn("Application-layer replay of 20 saved live traces.", page)
        self.assertIn("No new model or retrieval calls.", page)
        self.assertIn("F1 prompt experiment — unsuccessful", page)
        self.assertIn("5/20 → 5/20", page)
        self.assertIn("The candidate was not adopted", page)
        self.assertIn("timing renderer did not resolve F1", page)
        self.assertIn("Retrieval regression check", page)
        self.assertIn("6", page)
        self.assertIn("budget of **2**", page)
        self.assertIn("denominator is 1, with 19 excluded", page)
        self.assertIn("incidental", page.lower())
        self.assertIn("not an overall quality or compliance percentage", page.lower())
        self.assertIn("Candidate F2 remains unreviewed", page)
        self.assertIn("F1 judges — validation (default)", page)
        self.assertIn("Both judges missed every reviewed validation failure.", page)
        self.assertIn("Keep both versions outside detection, approval, and release gates.", page)
        self.assertIn("TP=0 · FN=5 · TN=15 · FP=0", page)
        self.assertIn("TPR=0/5 (0%)", page)
        self.assertIn("TNR=15/15 (100%)", page)
        self.assertIn("100% TNR is not overall success", page)
        self.assertIn("Calibration (separate from validation)", page)
        self.assertNotIn("75%", page)
        self.assertIn("TRACE-S02", page)
        self.assertTrue(any("Full raw model text" in exp.label for exp in at.expander))
        self.assertTrue(
            any("Full application-rendered text" in exp.label for exp in at.expander)
        )
        self.assertTrue(any("Article 113 evidence" in exp.label for exp in at.expander))
        self.assertFalse(any(btn.key == "run_assessment" for btn in at.button))
        from evals.week4.evaluations_view import load_evaluations_view
        from streamlit_app import timing_comparison_bars

        timing = load_evaluations_view()["timing"]
        bars = timing_comparison_bars(timing)
        self.assertFalse(bars["stacked"])
        self.assertEqual(len(bars["rows"]), 2)
        self.assertEqual(bars["axis_max"], timing["raw"]["denominator"])
        self.assertEqual(bars["axis_max"], timing["delivered"]["denominator"])
        self.assertEqual(bars["rows"][0]["passed"], timing["raw"]["pass"])
        self.assertEqual(bars["rows"][1]["passed"], timing["delivered"]["pass"])
        self.assertLess(max(row["passed"] for row in bars["rows"]), bars["rows"][0]["passed"] + bars["rows"][1]["passed"])
        self.assertEqual(
            bars["rows"][0]["label"],
            f"Raw answers: {timing['raw']['pass']}/{timing['raw']['denominator']} "
            f"({int(timing['raw']['percent'])}%)",
        )
        self.assertEqual(
            bars["rows"][1]["label"],
            f"Delivered after repair: {timing['delivered']['pass']}/"
            f"{timing['delivered']['denominator']} "
            f"({int(timing['delivered']['percent'])}%)",
        )
        source = Path("streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("timing_comparison_bars", source)
        self.assertIn("altair_chart", source)
        self.assertNotIn('"Raw answers": [raw.get("pass") or 0]', source)

    def test_offline_checks_button_invokes_real_runner(self) -> None:
        calls: list[str] = []

        def runner() -> dict:
            calls.append("offline")
            from evals.week4.evaluations_view import run_offline_checks

            return run_offline_checks(write=False)

        at = AppTest.from_file("streamlit_app.py", default_timeout=8)
        at.session_state["preview_runner"] = (
            lambda description, on_event: (_ for _ in ()).throw(
                AssertionError("no assessment")
            )
        )
        at.session_state["offline_check_runner"] = runner
        at.run()
        at.radio(key="ui_view").set_value("Week 4 evaluations").run()
        at.button(key="run_offline_checks").click().run()

        self.assertEqual(calls, ["offline"])
        page = _visible_text(at)
        self.assertIn("freshly recomputed", page.lower())
        self.assertIn("historical reports were not overwritten", page.lower())

    def test_evaluations_errors_are_visible_and_not_success_cards(self) -> None:
        def broken_loader(**kwargs):
            return {
                "ok": False,
                "source": "historical",
                "errors": [
                    {
                        "code": "artifact_error",
                        "label": "parent_traces",
                        "path": "missing.jsonl",
                        "detail": "SHA-256 mismatch: expected abc, observed def.",
                    }
                ],
                "timing": {},
                "f1": {},
                "retrieval": {},
            }

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["evaluations_loader"] = broken_loader
        at.session_state["preview_runner"] = (
            lambda description, on_event: (_ for _ in ()).throw(
                AssertionError("no assessment")
            )
        )
        at.run()
        at.radio(key="ui_view").set_value("Week 4 evaluations").run()
        page = _visible_text(at)
        self.assertIn("SHA-256 mismatch", page)
        self.assertNotIn("18/20 passed (90%)", page)
        self.assertNotIn("20/20 passed (100%)", page)
        self.assertTrue(any("not success results" in err.value.lower() for err in at.error))

    def test_assessment_workspace_is_unchanged_when_evaluations_exist(self) -> None:
        calls: list[str] = []

        def fake(description: str, on_event) -> dict:
            calls.append(description)
            return _fake_success(description, on_event)

        at = AppTest.from_file("streamlit_app.py", default_timeout=5)
        at.session_state["preview_runner"] = fake
        at.run()
        self.assertEqual(at.session_state.ui_view, "Assessment")
        at.button(key="load_example").click().run()
        at.button(key="run_assessment").click().run()
        _follow_reruns(at)
        self.assertEqual(calls, [SAMPLE_PREVIEW_PROMPT])
        self.assertIsNotNone(at.session_state.pending_review)
        self.assertEqual(
            at.session_state.pending_review["artifact"]["assessment"],
            at.session_state.displayed_answer,
        )


if __name__ == "__main__":
    unittest.main()

