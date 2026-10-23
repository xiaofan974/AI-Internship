"""Offline unit and integration tests for AeacusAI Stage 10 local lexical
retrieval preview (`aeacus_agent.context_preview.preview_classification_search`).

Runs against the actual Stage 4, Stage 5, and Stage 9 JSON files on disk,
and uses temporary test fixtures to verify explicit failure handling on
missing parents, tampered text hashes, and edition/snapshot mismatches.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from aeacus_agent import context_preview
from aeacus_agent.context_preview import (
    ANNEX_III_PARENT_ID,
    ARTICLE_113_TEMPORAL_ID,
    ARTICLE_6_PARENT_ID,
    CORPUS_SCOPE,
    PINNED_CONSOLIDATED_SNAPSHOT_ID,
    RETRIEVAL_MODE,
    STAGE4_ARTICLES_PATH,
    STAGE5_ANNEXES_PATH,
    STAGE9_CHILDREN_PATH,
    preview_classification_search,
)


class ContextPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stage9_children = json.loads(
            STAGE9_CHILDREN_PATH.read_text(encoding="utf-8")
        )
        cls.stage4_articles = json.loads(
            STAGE4_ARTICLES_PATH.read_text(encoding="utf-8")
        )
        cls.stage5_annexes = json.loads(
            STAGE5_ANNEXES_PATH.read_text(encoding="utf-8")
        )
        cls.by_id = {
            r["record_id"]: r
            for r in (*cls.stage9_children, *cls.stage4_articles, *cls.stage5_annexes)
        }

    def test_recruitment_query_retrieves_annex_iii_area_4_with_parents_and_article_113(
        self,
    ) -> None:
        result = preview_classification_search(
            "recruitment job applications filter candidates workers"
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["retrieval_mode"], RETRIEVAL_MODE)
        self.assertEqual(result["corpus_scope"], CORPUS_SCOPE)
        self.assertIs(result["ingestion_permitted"], False)
        self.assertGreaterEqual(result["match_count"], 1)
        self.assertLessEqual(result["match_count"], 5)

        area4_id = f"{PINNED_CONSOLIDATED_SNAPSHOT_ID}::annex/III/point/4"
        match_ids = [m["record_id"] for m in result["matches"]]
        self.assertEqual(match_ids[0], area4_id)

        top_match = result["matches"][0]
        expected_area4 = self.by_id[area4_id]
        # Verify complete, untruncated child text and provenance fields
        self.assertEqual(top_match["text"], expected_area4["text"])
        self.assertEqual(top_match["text_sha256"], expected_area4["text_sha256"])
        self.assertEqual(top_match["label"], "Annex III, point 4")
        self.assertEqual(
            top_match["source_location"], expected_area4["source_location"]
        )
        self.assertEqual(
            top_match["source_snapshot_id"], PINNED_CONSOLIDATED_SNAPSHOT_ID
        )

        context_ids = [c["record_id"] for c in result["context_records"]]
        self.assertEqual(len(context_ids), len(set(context_ids)))
        self.assertIn(ANNEX_III_PARENT_ID, context_ids)
        self.assertIn(ARTICLE_6_PARENT_ID, context_ids)
        self.assertIn(ARTICLE_113_TEMPORAL_ID, context_ids)

        # Verify context records contain complete, untruncated text
        for ctx in result["context_records"]:
            orig = self.by_id[ctx["record_id"]]
            self.assertEqual(ctx["text"], orig["text"])
            self.assertEqual(ctx["text_sha256"], orig["text_sha256"])

    def test_article_6_query_includes_complete_article_6_and_article_113_context(
        self,
    ) -> None:
        # Query terms specific to Article 6(3) without hitting Annex III area 6 ('profiling')
        result = preview_classification_search(
            "derogation narrow procedural preparatory"
        )

        self.assertEqual(result["status"], "ok")
        art6_p3_id = f"{PINNED_CONSOLIDATED_SNAPSHOT_ID}::article/6/paragraph/3"
        match_ids = [m["record_id"] for m in result["matches"]]
        self.assertEqual(match_ids, [art6_p3_id])
        self.assertEqual(
            result["matches"][0]["text"], self.by_id[art6_p3_id]["text"]
        )

        context_ids = [c["record_id"] for c in result["context_records"]]
        self.assertEqual(context_ids, [ARTICLE_6_PARENT_ID, ARTICLE_113_TEMPORAL_ID])

    def test_context_records_are_deduplicated_across_multiple_hits(self) -> None:
        result = preview_classification_search(
            "high-risk AI systems safety component Annex I Annex III biometric recruitment"
        )

        self.assertEqual(result["status"], "ok")
        self.assertGreater(result["match_count"], 1)
        self.assertLessEqual(result["match_count"], 5)

        context_ids = [c["record_id"] for c in result["context_records"]]
        self.assertEqual(len(context_ids), len(set(context_ids)))
        self.assertEqual(
            set(context_ids),
            {ANNEX_III_PARENT_ID, ARTICLE_6_PARENT_ID, ARTICLE_113_TEMPORAL_ID},
        )

    def test_empty_and_unrelated_queries_behave_correctly(self) -> None:
        for empty_q in ("", "   ", "\n\t"):
            with self.subTest(query=empty_q):
                res = preview_classification_search(empty_q)
                self.assertEqual(res["status"], "error")
                self.assertEqual(res["error"]["category"], "invalid_query")
                self.assertEqual(res["matches"], [])
                self.assertEqual(res["context_records"], [])

        unrelated = preview_classification_search(
            "interplanetary spacecraft propulsion warp drive"
        )
        self.assertEqual(unrelated["status"], "no_matches")
        self.assertEqual(unrelated["match_count"], 0)
        self.assertEqual(unrelated["matches"], [])
        self.assertEqual(unrelated["context_records"], [])
        self.assertEqual(res["retrieval_mode"], RETRIEVAL_MODE)
        self.assertIs(res["ingestion_permitted"], False)

    def test_preview_agent_configuration_is_offline_with_single_preview_tool(
        self,
    ) -> None:
        from aeacus_agent.agent import MODEL, aeacus_review_agent
        from aeacus_agent.preview_agent import aeacus_preview_agent
        from aeacus_agent.retrieval import search_legal_sources

        self.assertEqual(aeacus_preview_agent.name, "aeacus_preview_agent")
        self.assertEqual(aeacus_preview_agent.model, MODEL)
        self.assertEqual(len(aeacus_preview_agent.tools), 1)
        self.assertIs(
            aeacus_preview_agent.tools[0], preview_classification_search
        )
        self.assertEqual(getattr(aeacus_preview_agent, "sub_agents", []), [])

        # Confirm existing Pinecone agent defaults remain untouched
        self.assertEqual(len(aeacus_review_agent.tools), 1)
        self.assertIs(aeacus_review_agent.tools[0], search_legal_sources)

    def test_missing_parent_returns_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_articles_path = Path(tmpdir) / "articles_missing_art6.json"
            articles_without_art6 = [
                r
                for r in self.stage4_articles
                if r["record_id"] != ARTICLE_6_PARENT_ID
            ]
            tmp_articles_path.write_text(
                json.dumps(articles_without_art6), encoding="utf-8"
            )

            with patch.object(
                context_preview, "STAGE4_ARTICLES_PATH", tmp_articles_path
            ):
                res = preview_classification_search("recruitment candidates")
                self.assertEqual(res["status"], "error")
                self.assertEqual(
                    res["error"]["category"], "missing_parent_or_context"
                )
                self.assertIn(ARTICLE_6_PARENT_ID, res["error"]["message"])
                self.assertEqual(res["matches"], [])
                self.assertEqual(res["context_records"], [])

    def test_tampered_text_hash_returns_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_children_path = Path(tmpdir) / "children_tampered.json"
            tampered_children = copy.deepcopy(self.stage9_children)
            tampered_children[0]["text"] += " [tampered]"
            tmp_children_path.write_text(
                json.dumps(tampered_children), encoding="utf-8"
            )

            with patch.object(
                context_preview, "STAGE9_CHILDREN_PATH", tmp_children_path
            ):
                res = preview_classification_search("recruitment candidates")
                self.assertEqual(res["status"], "error")
                self.assertEqual(res["error"]["category"], "hash_mismatch")
                self.assertEqual(res["matches"], [])
                self.assertEqual(res["context_records"], [])

    def test_wrong_snapshot_returns_explicit_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_children_path = Path(tmpdir) / "children_wrong_snap.json"
            wrong_snap_children = copy.deepcopy(self.stage9_children)
            wrong_snap = "T1-AIA-OJ-2024@sha256:8f0b656302f9864cc87e040c371f209a9d65ae1a6cecc25ca5eb737e872d721a"
            wrong_snap_children[0]["source_snapshot_id"] = wrong_snap
            tmp_children_path.write_text(
                json.dumps(wrong_snap_children), encoding="utf-8"
            )

            with patch.object(
                context_preview, "STAGE9_CHILDREN_PATH", tmp_children_path
            ):
                res = preview_classification_search("recruitment candidates")
                self.assertEqual(res["status"], "error")
                self.assertEqual(res["error"]["category"], "snapshot_mismatch")
                self.assertEqual(res["matches"], [])
                self.assertEqual(res["context_records"], [])


if __name__ == "__main__":
    unittest.main()
