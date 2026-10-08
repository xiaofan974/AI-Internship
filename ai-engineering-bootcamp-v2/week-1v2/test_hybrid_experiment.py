"""Mocked tests for hybrid BM25 + dense + RRF retrieval. No provider calls."""

import io
import unittest
from unittest.mock import patch

import rag
from rag import RetrievedChunk

import hybrid_experiment as hyb
from chunking_experiment import BASELINE_NAMESPACE, PRODUCTION_NAMESPACE, score_condition


def _chunk(chunk_id: str, text: str, score: float = 0.0) -> RetrievedChunk:
    document_id, index = chunk_id.rsplit(":", 1)
    return RetrievedChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=int(index),
        source="exampleco-synthetic-policies",
        score=score,
        text=text,
    )


class HybridExperimentTests(unittest.TestCase):
    def test_tokenize_is_lowercase_and_keeps_decimals(self) -> None:
        tokens = hyb.tokenize("Head of IT approves £400.01 items.")
        self.assertEqual(tokens, ["head", "of", "it", "approves", "400.01", "items"])

    def test_rrf_is_deterministic_on_known_lists(self) -> None:
        fused = hyb.reciprocal_rank_fusion(
            [["x", "y"], ["y"]],
            k=60,
        )
        self.assertEqual([item[0] for item in fused], ["y", "x"])
        y_score = 1 / 61 + 1 / 62
        x_score = 1 / 61
        self.assertAlmostEqual(fused[0][1], y_score)
        self.assertAlmostEqual(fused[1][1], x_score)

    def test_rrf_duplicate_ids_in_one_list_count_once(self) -> None:
        fused = hyb.reciprocal_rank_fusion([["a", "a", "b"]], k=60)
        self.assertEqual([item[0] for item in fused], ["a", "b"])
        self.assertAlmostEqual(fused[0][1], 1 / 61)

    def test_rrf_rejects_nonpositive_k(self) -> None:
        with self.assertRaises(ValueError):
            hyb.reciprocal_rank_fusion([["a"]], k=0)

    def test_local_chunks_match_800_100_stable_ids(self) -> None:
        chunks = hyb.build_local_chunks()
        ids = [chunk.id for chunk in chunks]
        self.assertEqual(len(chunks), 13)
        self.assertTrue(all(chunk.id == rag.stable_chunk_id(chunk.document_id, chunk.chunk_index) for chunk in chunks))
        self.assertIn("exampleco-information-security:2", ids)
        security = next(chunk for chunk in chunks if chunk.id == "exampleco-information-security:2")
        self.assertEqual(len(security.text), 224)
        self.assertIn("60 days", security.text.lower())

    def test_supporting_evidence_requires_chunk_text_not_document_id(self) -> None:
        cases = hyb.factual_cases()
        q5 = next(case for case in cases if case["id"] == "q5_unused_access")
        retrieved = {
            "q5_unused_access": [
                _chunk("exampleco-information-security:0", "MFA is required on email."),
                _chunk(
                    "exampleco-information-security:2",
                    "Access unused for 60 days is revoked.",
                ),
            ]
        }
        for case in cases:
            retrieved.setdefault(case["id"], retrieved["q5_unused_access"])
        scores = score_condition([q5], {"q5_unused_access": retrieved["q5_unused_access"]})
        self.assertEqual(scores["q5_supporting_rank"], 2)

    def test_bm25_ranks_sixty_day_chunk_without_api(self) -> None:
        chunks = hyb.build_local_chunks()
        index = hyb.BM25Index.from_chunks(chunks)
        question = next(
            case["question"]
            for case in hyb.factual_cases()
            if case["id"] == "q5_unused_access"
        )
        ranked = index.search(question, top_k=10)
        self.assertTrue(ranked)
        self.assertTrue(any("60 days" in chunk.text.lower() for chunk in ranked[:5]))
        first_hit = next(
            rank
            for rank, chunk in enumerate(ranked, start=1)
            if "60 days" in chunk.text.lower()
        )
        self.assertLessEqual(first_hit, 5)

    def test_hybrid_rrf_can_promote_a_keyword_hit(self) -> None:
        dense = [
            _chunk("exampleco-information-security:0", "MFA is required."),
            _chunk("exampleco-remote-work:0", "Tuesday and Thursday only."),
        ]
        sparse = [
            _chunk(
                "exampleco-information-security:2",
                "Access unused for 60 days is revoked.",
            ),
            _chunk("exampleco-information-security:0", "MFA is required."),
        ]
        fused = hyb.fuse_rankings(dense, sparse, k=60)
        self.assertEqual(fused[0].id, "exampleco-information-security:0")
        self.assertIn("exampleco-information-security:2", [chunk.id for chunk in fused])

    def test_evaluate_compares_three_retrievers(self) -> None:
        cases = [
            case
            for case in hyb.factual_cases()
            if case["id"] in {"q1_remote_days", "q5_unused_access"}
        ]
        chunks = hyb.build_local_chunks()
        index = hyb.BM25Index.from_chunks(chunks)
        dense_by_case = {
            "q1_remote_days": [
                _chunk(
                    "exampleco-remote-work:0",
                    "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                )
            ],
            "q5_unused_access": [
                _chunk("exampleco-information-security:0", "MFA is required."),
            ],
        }
        scores = hyb.evaluate_retrievers(cases, dense_by_case=dense_by_case, bm25_index=index)
        self.assertEqual(set(scores), {"dense", "bm25", "hybrid"})
        self.assertEqual(scores["dense"]["q5_supporting_rank"], None)
        self.assertIsNotNone(scores["bm25"]["q5_supporting_rank"])
        self.assertLessEqual(scores["bm25"]["q5_supporting_rank"], 5)

    def test_dry_run_does_not_call_providers(self) -> None:
        with patch.object(rag, "retrieve_chunks") as retrieve:
            with patch.object(rag, "ingest_document") as ingest:
                with patch("sys.argv", ["hybrid_experiment.py"]):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = hyb.main()
        self.assertEqual(code, 0)
        retrieve.assert_not_called()
        ingest.assert_not_called()
        output = stdout.getvalue()
        self.assertIn(BASELINE_NAMESPACE, output)
        self.assertIn("no API calls", output)
        self.assertIn("OpenAI query embeddings: 5", output)

    def test_dense_retrieve_uses_isolated_namespace(self) -> None:
        captured = {}

        def fake_retrieve(*, query, top_k, config):
            captured["namespace"] = config.namespace
            captured["model"] = config.embedding_model
            self.assertEqual(top_k, 10)
            return [_chunk("exampleco-remote-work:0", "Tuesday and Thursday only.")]

        cases = [hyb.factual_cases()[0]]
        with patch.object(hyb, "live_config", return_value=hyb.dummy_config(hyb.BASELINE)):
            with patch.object(rag, "retrieve_chunks", side_effect=fake_retrieve):
                hyb.dense_retrieve(cases)
        self.assertEqual(captured["namespace"], BASELINE_NAMESPACE)
        self.assertNotEqual(captured["namespace"], PRODUCTION_NAMESPACE)
        self.assertEqual(captured["model"], "text-embedding-3-small")


if __name__ == "__main__":
    unittest.main()
