"""Focused citation and quotation-check regressions.

These tests use local corpus text only. They do not call Gemini, OpenAI,
or Pinecone, and they do not prove live model behavior.
"""

from __future__ import annotations

import unittest

from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.evidence_checks import (
    extract_explicit_quotes,
    run_deterministic_checks,
    unwrap_presentation_delimiters,
)

RECRUITMENT_QUERY = "recruitment job applications filter candidates workers"
FABRICATED_ID = (
    "T1-AIA-CONS-20260727@sha256:"
    "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    "::article/5"
)
STATUTORY_SPAN = (
    "AI systems intended to be used for the recruitment or selection of "
    "natural persons, in particular to place targeted job advertisements, "
    "to analyse and filter job applications, and to evaluate candidates;"
)
PROFILING_SPAN = (
    "Notwithstanding the first subparagraph, an AI system referred to in "
    "Annex III shall always be considered to be high-risk where the AI "
    "system performs profiling of natural persons."
)


def _recruitment_record() -> dict:
    payload = preview_classification_search(RECRUITMENT_QUERY)
    match = payload["matches"][0]
    return {
        "record_id": match["record_id"],
        "label": match["label"],
        "text": match["text"],
        "text_sha256": match["text_sha256"],
    }


class EvidenceCheckRegressionTests(unittest.TestCase):
    def test_unwrap_removes_only_clearly_paired_wrappers(self) -> None:
        self.assertEqual(
            unwrap_presentation_delimiters(f'"{STATUTORY_SPAN}"'),
            STATUTORY_SPAN,
        )
        self.assertEqual(
            unwrap_presentation_delimiters(f"“{STATUTORY_SPAN}”"),
            STATUTORY_SPAN,
        )
        mixed = f'"{STATUTORY_SPAN}”'
        self.assertEqual(unwrap_presentation_delimiters(mixed), mixed)
        with_internal = f'The phrase "{STATUTORY_SPAN[:32]}" remains inside.'
        self.assertEqual(unwrap_presentation_delimiters(with_internal), with_internal)

    def test_exact_blockquote_with_straight_or_curly_wrappers_passes(self) -> None:
        record = _recruitment_record()
        self.assertIn(STATUTORY_SPAN, record["text"])
        for draft in (
            f"Provisional finding\n\n> \"{STATUTORY_SPAN}\"\n\nSee Annex III, point 4.",
            f"Provisional finding\n\n> “{STATUTORY_SPAN}”\n\nSee Annex III, point 4.",
            f"Provisional finding\n\n> {STATUTORY_SPAN}\n\nSee Annex III, point 4.",
        ):
            quotes = extract_explicit_quotes(draft)
            self.assertIn(STATUTORY_SPAN, quotes)
            self.assertNotIn(f'"{STATUTORY_SPAN}"', quotes)
            checks = run_deterministic_checks(draft, [record])
            self.assertTrue(checks["quotations"]["ok"], checks)
            self.assertTrue(checks["ok"], checks)

    def test_altered_word_in_quotation_fails(self) -> None:
        record = _recruitment_record()
        altered = STATUTORY_SPAN.replace("natural persons", "legal persons", 1)
        self.assertNotEqual(altered, STATUTORY_SPAN)
        checks = run_deterministic_checks(
            f'Provisional finding\n\n> "{altered}"\n\nSee Annex III, point 4.',
            [record],
        )
        self.assertFalse(checks["quotations"]["ok"])
        self.assertTrue(any("legal persons" in item for item in checks["quotations"]["unsupported"]))

    def test_omitted_qualification_in_quotation_fails(self) -> None:
        record = _recruitment_record()
        omitted = STATUTORY_SPAN.replace(
            "in particular to place targeted job advertisements, ",
            "",
        )
        self.assertNotEqual(omitted, STATUTORY_SPAN)
        self.assertNotIn(omitted, record["text"])
        checks = run_deterministic_checks(
            f'The statute says "{omitted}"',
            [record],
        )
        self.assertFalse(checks["quotations"]["ok"])
        self.assertIn(omitted, checks["quotations"]["unsupported"])

    def test_fabricated_citation_still_fails(self) -> None:
        record = _recruitment_record()
        checks = run_deterministic_checks(
            f"See `{FABRICATED_ID}` and Annex III, point 4.",
            [record],
        )
        self.assertFalse(checks["citation_ids"]["ok"])
        self.assertIn(FABRICATED_ID, checks["citation_ids"]["unknown"])
        self.assertFalse(checks["ok"])

    def test_quotation_absent_from_cited_record_fails(self) -> None:
        record = _recruitment_record()
        self.assertNotIn(PROFILING_SPAN, record["text"])
        checks = run_deterministic_checks(
            f'Annex III, point 4 says "{PROFILING_SPAN}"',
            [record],
        )
        self.assertFalse(checks["quotations"]["ok"])
        self.assertIn(PROFILING_SPAN, checks["quotations"]["unsupported"])


if __name__ == "__main__":
    unittest.main()
