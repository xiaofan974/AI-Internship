"""Mocked tests for cross-encoder reranking. No provider or model downloads."""

import io
import unittest
from unittest.mock import MagicMock, patch

import rag
from rag import RetrievedChunk

import rerank_experiment as exp
from chunking_experiment import (
    BASELINE,
    BASELINE_NAMESPACE,
    PRODUCTION_NAMESPACE,
    dummy_config,
)


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


class FakeReranker:
    def __init__(self, scores: list[float]) -> None:
        self.scores = scores
        self.pairs: list[list[tuple[str, str]]] = []

    def predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        self.pairs.append(list(pairs))
        return self.scores[: len(pairs)]


class RerankExperimentTests(unittest.TestCase):
    def test_rerank_uses_query_and_chunk_text_only(self) -> None:
        chunks = [
            _chunk("exampleco-information-security:0", "MFA is required."),
            _chunk(
                "exampleco-information-security:2",
                "Access unused for 60 days is revoked.",
            ),
        ]
        reranker = FakeReranker([0.1, 0.9])
        ranked, latency = exp.rerank_chunks("When is unused access revoked?", chunks, reranker)
        self.assertGreaterEqual(latency, 0.0)
        self.assertEqual(ranked[0].id, "exampleco-information-security:2")
        self.assertEqual(ranked[0].document_id, "exampleco-information-security")
        self.assertEqual(ranked[0].chunk_index, 2)
        self.assertEqual(ranked[0].source, "exampleco-synthetic-policies")
        pair_texts = [text for _query, text in reranker.pairs[0]]
        self.assertEqual(
            pair_texts,
            ["MFA is required.", "Access unused for 60 days is revoked."],
        )
        self.assertNotIn("60 days", reranker.pairs[0][0][0])
        queries = {query for query, _text in reranker.pairs[0]}
        self.assertEqual(queries, {"When is unused access revoked?"})

    def test_rerank_keeps_top_k_and_is_deterministic_on_ties(self) -> None:
        chunks = [
            _chunk("b:0", "second"),
            _chunk("a:0", "first"),
            _chunk("c:0", "third"),
        ]
        ranked, _ = exp.rerank_chunks("q", chunks, FakeReranker([0.5, 0.5, 0.1]), top_k=2)
        self.assertEqual([chunk.id for chunk in ranked], ["a:0", "b:0"])

    def test_candidate_miss_is_not_blamed_on_reranker(self) -> None:
        cases = [
            case
            for case in exp.factual_cases()
            if case["id"] in {"q1_remote_days", "q5_unused_access"}
        ]
        candidates = {
            "q1_remote_days": [
                _chunk(
                    "exampleco-remote-work:0",
                    "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                )
            ]
            + [_chunk(f"filler:{i}", "unrelated") for i in range(9)],
            "q5_unused_access": [
                _chunk("exampleco-information-security:0", "MFA is required.")
            ]
            + [_chunk(f"other:{i}", "no access policy") for i in range(9)],
        }
        reranker = FakeReranker([0.2] * 10)

        def predict(pairs):
            return [0.2] * len(pairs)

        reranker.predict = predict  # type: ignore[method-assign]
        results = exp.evaluate_rerank(
            cases, candidates_by_case=candidates, reranker=reranker
        )
        self.assertFalse(results["candidate_misses"]["q1_remote_days"])
        self.assertTrue(results["candidate_misses"]["q5_unused_access"])
        self.assertIsNone(results["rerank"]["q5_supporting_rank"])
        self.assertIsNone(results["q5_candidate_rank"])

    def test_reranker_can_promote_q5_into_top_five(self) -> None:
        q5 = next(case for case in exp.factual_cases() if case["id"] == "q5_unused_access")
        candidates = [
            _chunk(f"noise:{i}", f"generic policy text {i}") for i in range(6)
        ] + [
            _chunk(
                "exampleco-information-security:2",
                "Access unused for 60 days is revoked.",
            )
        ]
        scores = [0.05] * 6 + [0.99]
        reranker = FakeReranker(scores)
        results = exp.evaluate_rerank(
            [q5],
            candidates_by_case={"q5_unused_access": candidates},
            reranker=reranker,
        )
        self.assertEqual(results["dense"]["q5_supporting_rank"], None)
        self.assertEqual(results["q5_candidate_rank"], 7)
        self.assertEqual(results["rerank"]["q5_supporting_rank"], 1)
        self.assertEqual(results["rerank"]["q5_chunk_id_rank"], 1)
        self.assertEqual(results["rerank"]["recall_at_5"], 1.0)

    def test_dry_run_does_not_retrieve_or_load_model(self) -> None:
        with patch.object(rag, "retrieve_chunks") as retrieve:
            with patch.object(exp, "load_reranker") as loader:
                with patch("sys.argv", ["rerank_experiment.py"]):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = exp.main()
        self.assertEqual(code, 0)
        retrieve.assert_not_called()
        loader.assert_not_called()
        output = stdout.getvalue()
        self.assertIn(BASELINE_NAMESPACE, output)
        self.assertIn("no API or model-download", output)
        self.assertIn("OpenAI query embeddings: 5", output)

    def test_dense_candidates_use_isolated_namespace(self) -> None:
        captured: dict[str, str] = {}

        def fake_retrieve(*, query, top_k, config):
            captured["namespace"] = config.namespace
            self.assertEqual(top_k, 10)
            return [_chunk("exampleco-remote-work:0", "Tuesday and Thursday only.")]

        with patch.object(exp, "live_config", return_value=dummy_config(BASELINE)):
            with patch.object(rag, "retrieve_chunks", side_effect=fake_retrieve):
                exp.dense_candidates([exp.factual_cases()[0]])
        self.assertEqual(captured["namespace"], BASELINE_NAMESPACE)
        self.assertNotEqual(captured["namespace"], PRODUCTION_NAMESPACE)

    def test_load_reranker_explains_missing_optional_dependency(self) -> None:
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with self.assertRaises(RuntimeError) as raised:
                exp.load_reranker()
        self.assertIn("sentence-transformers", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
