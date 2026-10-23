"""Offline checks for preview answer format, grounding instructions,
and citation presentation.

These tests do not call Gemini, OpenAI, or Pinecone and do not prove live
model behavior.
"""

from __future__ import annotations

import unittest

from aeacus_agent.preview_agent import AEACUS_PREVIEW_INSTRUCTION
from streamlit_app import (
    evidence_from_observe_payload,
    finalize_preview_result,
    present_citations,
)

PINNED = (
    "T1-AIA-CONS-20260727@sha256:"
    "5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715"
)
AREA4_ID = f"{PINNED}::annex/III/point/4"
ART6_ID = f"{PINNED}::article/6"
ART113_ID = f"{PINNED}::article/113"
UNKNOWN_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    "::article/5"
)

EVIDENCE = [
    {"label": "Annex III, point 4", "record_id": AREA4_ID, "text": "child"},
    {
        "label": "Article 6 — Classification rules for high-risk AI systems",
        "record_id": ART6_ID,
        "text": "parent",
    },
    {
        "label": "Article 113 — Entry into force and application",
        "record_id": ART113_ID,
        "text": "timing",
    },
]


class PreviewInstructionTests(unittest.TestCase):
    def test_instructions_require_plain_headings_and_word_target(self) -> None:
        text = AEACUS_PREVIEW_INSTRUCTION
        self.assertIn("Provisional finding", text)
        for heading in (
            "Why",
            "What could change this",
            "Missing facts",
            "Timing and scope",
        ):
            self.assertIn(heading, text)
        self.assertTrue("300–450" in text or "300-450" in text)
        self.assertNotIn("epistemic assessment", text.lower())
        self.assertNotIn("epistemic structure", text.lower())
        self.assertNotIn("Stage 9", text)
        self.assertNotIn("stage 9", text.lower())

    def test_instructions_address_grounding_defects(self) -> None:
        text = AEACUS_PREVIEW_INSTRUCTION.lower()
        self.assertIn("stated facts", text)
        self.assertIn("conditional inferences", text)
        self.assertIn("material influence", text)
        self.assertIn("unknown", text)
        self.assertIn("reviewing every application", text)
        self.assertIn("necessary or sufficient", text)
        self.assertIn("profiling", text)
        self.assertIn("unresolved", text)
        self.assertIn("do not invent a definition", text)
        self.assertIn("article 113(c)", text)
        self.assertIn("article 6(5)", text)
        self.assertIn("direct quote", text)
        self.assertIn("retrieved source wording", text)
        self.assertNotRegex(
            AEACUS_PREVIEW_INSTRUCTION,
            r"this recruitment system is high-risk",
            msg="Instructions must not hardcode the recruitment finding.",
        )


class CitationPresentationTests(unittest.TestCase):
    def test_known_ids_map_to_short_labels_without_deleting_unknown_ids(self) -> None:
        raw = (
            "Provisional finding\n\n"
            f"The facts match Annex III, point 4 (`{AREA4_ID}`). "
            f"Parent context is {ART6_ID}. "
            f"An unverified cite is {UNKNOWN_ID}.\n\n"
            "## Missing facts\n"
            "- Whether recruiters see every filtered application.\n"
        )
        result = present_citations(raw, EVIDENCE)
        displayed = result["displayed_answer"]

        self.assertEqual(result["raw_answer"], raw)
        self.assertIn("Annex III, point 4", displayed)
        self.assertNotIn(AREA4_ID, displayed)
        self.assertIn(
            "Article 6 — Classification rules for high-risk AI systems",
            displayed,
        )
        self.assertNotIn(ART6_ID, displayed)
        self.assertIn(UNKNOWN_ID, displayed)
        self.assertEqual(result["unknown_references"], [UNKNOWN_ID])
        self.assertEqual(
            [item["record_id"] for item in result["citation_map"]],
            [AREA4_ID, ART6_ID, ART113_ID],
        )
        self.assertEqual(result["citation_map"][0]["label"], "Annex III, point 4")

    def test_parent_id_replacement_does_not_consume_a_longer_child_id(self) -> None:
        child_id = f"{PINNED}::annex/III/point/4"
        parent_id = f"{PINNED}::annex/III"
        evidence = [
            {"label": "Annex III, point 4", "record_id": child_id},
            {"label": "Annex III", "record_id": parent_id},
        ]
        raw = f"Child {child_id} and parent {parent_id}."
        displayed = present_citations(raw, evidence)["displayed_answer"]
        self.assertEqual(displayed, "Child Annex III, point 4 and parent Annex III.")

    def test_finalize_keeps_raw_answer_and_extracts_missing_facts(self) -> None:
        raw = (
            "Provisional finding\n\n"
            f"See Annex III, point 4 (`{AREA4_ID}`).\n\n"
            "## Why\nRelevant because it describes recruitment filtering.\n\n"
            "## Missing facts\n"
            "- Whether recruiters see every filtered application.\n"
        )
        payload = {
            "matches": [
                {
                    "label": "Annex III, point 4",
                    "record_id": AREA4_ID,
                    "text": "retrieved child text",
                    "source_location": {
                        "url": "https://publications.europa.eu/example-annex-iii-point-4"
                    },
                }
            ],
            "context_records": [],
        }
        evidence = evidence_from_observe_payload(payload)
        result = finalize_preview_result(raw, evidence)
        self.assertTrue(result["ok"])
        self.assertEqual(result["raw_answer"], raw)
        self.assertIn("Annex III, point 4", result["assessment"])
        self.assertNotIn(AREA4_ID, result["assessment"])
        self.assertTrue(
            any(
                "recruiters see every filtered application" in item
                for item in result["missing_facts"]
            )
        )


if __name__ == "__main__":
    unittest.main()
