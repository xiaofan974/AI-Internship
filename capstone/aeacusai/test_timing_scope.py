"""Offline tests for the application-owned Timing and scope renderer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aeacus_agent.context_preview import (
    ARTICLE_113_TEMPORAL_ID,
    PINNED_CONSOLIDATED_SNAPSHOT_ID,
    STAGE4_ARTICLES_PATH,
)
from aeacus_agent.review_register import artifact_matches, create_pending_review
from aeacus_agent.timing_scope import (
    EXPECTED_ARTICLE_113_TEXT_SHA256,
    apply_timing_repair,
    prefix_outside_timing,
    records_from_events,
    sha256_text,
)
from aeacus_agent.trace_store import PROJECT_DIR
from streamlit_app import evidence_from_observe_payload, finalize_preview_result

PARENT_TRACE = PROJECT_DIR / "data" / "local" / "traces" / "week4_adk_preview_v1.jsonl"
PARENT_SHA = "29871169b2db5aebeac179cdd254a4700e36f252b2873ea9e05e334400204db1"


def _article_113() -> dict:
    records = json.loads(STAGE4_ARTICLES_PATH.read_text(encoding="utf-8"))
    return next(item for item in records if item["record_id"] == ARTICLE_113_TEMPORAL_ID)


def _record(**overrides) -> dict:
    source = _article_113()
    item = {
        "record_id": source["record_id"],
        "source_snapshot_id": source["source_snapshot_id"],
        "label": source["label"],
        "text": source["text"],
        "text_sha256": source["text_sha256"],
    }
    item.update(overrides)
    return item


RAW = """### Provisional finding

Likely high-risk under Annex III, point 3.

### Why

The described scoring is an evaluation of learning outcomes.

### What could change this

A purely preparatory use might change the reading.

### Missing facts

- Whether the school is an educational institution.

### Timing and scope

The high-risk rules apply from 2 December 2027.
"""


class TimingRepairUnitTests(unittest.TestCase):
    def test_valid_rendering_quotes_source_and_replaces_model_timing(self) -> None:
        repair = apply_timing_repair(RAW, [_record()])
        self.assertEqual(repair.status, "ok")
        self.assertEqual(repair.raw_output, RAW)
        self.assertEqual(repair.source_record_id, ARTICLE_113_TEMPORAL_ID)
        self.assertEqual(repair.source_text_sha256, EXPECTED_ARTICLE_113_TEXT_SHA256)
        self.assertEqual(repair.source_snapshot_id, PINNED_CONSOLIDATED_SNAPSHOT_ID)
        self.assertIn("Chapter III, Sections 1, 2, and 3", repair.delivered_output)
        self.assertIn("with the exception of Article 6(5)", repair.delivered_output)
        self.assertIn("2 December 2027", repair.delivered_output)
        self.assertIn("2 August 2028", repair.delivered_output)
        self.assertIn("Article 6(2) and Annex III", repair.delivered_output)
        self.assertIn("Article 6(1) and Annex I", repair.delivered_output)
        self.assertNotIn(
            "The high-risk rules apply from 2 December 2027.",
            repair.delivered_output,
        )
        self.assertEqual(
            prefix_outside_timing(repair.delivered_output),
            prefix_outside_timing(RAW),
        )

    def test_missing_article_113_fails_without_statutory_fallback(self) -> None:
        repair = apply_timing_repair(RAW, [])
        self.assertEqual(repair.status, "failed")
        self.assertEqual(repair.reason, "missing_article_113_observation")
        self.assertIn("No statutory application dates are stated.", repair.delivered_output)
        self.assertNotIn("2 December 2027", repair.delivered_output)
        self.assertEqual(repair.raw_output, RAW)
        self.assertNotIn(
            "The high-risk rules apply from 2 December 2027.",
            repair.delivered_output,
        )

    def test_tampered_hash_fails(self) -> None:
        repair = apply_timing_repair(
            RAW,
            [_record(text_sha256="0" * 64)],
        )
        self.assertEqual(repair.status, "failed")
        self.assertEqual(repair.reason, "observation_hash_mismatch")
        self.assertNotIn("2 August 2028", repair.delivered_output)

    def test_wrong_edition_fails(self) -> None:
        repair = apply_timing_repair(
            RAW,
            [
                _record(
                    source_snapshot_id="T1-AIA-OJ-2024@sha256:" + "ab" * 32,
                    record_id="T1-AIA-OJ-2024@sha256:" + "ab" * 32 + "::article/113",
                )
            ],
        )
        self.assertEqual(repair.status, "failed")
        self.assertIn(repair.reason, {"wrong_edition_snapshot", "wrong_edition_record_id"})

    def test_source_hash_mismatch_fails(self) -> None:
        other = "A different Article 113 edition with no deferred dates."
        repair = apply_timing_repair(
            RAW,
            [
                _record(
                    text=other,
                    text_sha256=sha256_text(other),
                )
            ],
        )
        self.assertEqual(repair.status, "failed")
        self.assertEqual(repair.reason, "source_text_hash_mismatch")

    def test_ambiguous_heading_drops_model_timing(self) -> None:
        raw = RAW + "\n### Timing and scope\nAnother timing paragraph.\n"
        repair = apply_timing_repair(raw, [_record()])
        self.assertEqual(repair.status, "failed")
        self.assertEqual(repair.reason, "ambiguous_timing_heading")
        self.assertNotIn("Another timing paragraph.", repair.delivered_output)
        self.assertNotIn("The high-risk rules apply from 2 December 2027.", repair.delivered_output)

    def test_heading_after_timing_is_ambiguous(self) -> None:
        raw = RAW + "\n### Extra\nLeftover.\n"
        repair = apply_timing_repair(raw, [_record()])
        self.assertEqual(repair.status, "failed")
        self.assertEqual(repair.reason, "ambiguous_section_boundaries")
        self.assertNotIn("Leftover.", repair.delivered_output)

    def test_raw_answer_is_preserved_on_finalize(self) -> None:
        evidence = evidence_from_observe_payload(
            {"matches": [], "context_records": [_record()]}
        )
        result = finalize_preview_result(RAW, evidence)
        self.assertEqual(result["raw_answer"], RAW)
        self.assertNotEqual(result["displayed_answer"], RAW)
        self.assertEqual(result["timing_repair"]["status"], "ok")
        self.assertIn("Chapter III, Sections 1, 2, and 3", result["displayed_answer"])

    def test_pending_review_binds_to_delivered_not_raw(self) -> None:
        evidence = evidence_from_observe_payload(
            {"matches": [], "context_records": [_record()]}
        )
        result = finalize_preview_result(RAW, evidence)
        pending = create_pending_review(
            session_id="session-timing",
            system_description="A scoring tool.",
            assessment=result["displayed_answer"],
            evidence=evidence,
            run_id="run-timing",
        )
        self.assertTrue(
            artifact_matches(
                pending,
                session_id="session-timing",
                system_description="A scoring tool.",
                assessment=result["displayed_answer"],
                evidence=evidence,
            )
        )
        self.assertFalse(
            artifact_matches(
                pending,
                session_id="session-timing",
                system_description="A scoring tool.",
                assessment=result["raw_answer"],
                evidence=evidence,
            )
        )


class BaselineReplayTests(unittest.TestCase):
    def test_replay_keeps_non_timing_text_and_uses_saved_observations(self) -> None:
        if not PARENT_TRACE.is_file():
            self.skipTest("local baseline traces are not present")
        import hashlib

        self.assertEqual(
            hashlib.sha256(PARENT_TRACE.read_bytes()).hexdigest(), PARENT_SHA
        )
        rows = [
            json.loads(line)
            for line in PARENT_TRACE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(rows), 20)
        for row in rows:
            raw = row["final_output"]
            repair = apply_timing_repair(raw, records_from_events(row.get("events")))
            self.assertEqual(repair.raw_output, raw)
            self.assertEqual(
                prefix_outside_timing(repair.delivered_output),
                prefix_outside_timing(raw),
            )
            self.assertNotIn("think", json.dumps(repair.to_dict()))


if __name__ == "__main__":
    unittest.main()
