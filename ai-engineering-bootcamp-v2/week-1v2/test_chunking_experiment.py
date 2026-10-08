"""Mocked tests for the chunking A/B experiment. No provider calls."""

import io
import unittest
from unittest.mock import MagicMock, patch

import rag
from rag import RetrievedChunk

import chunking_experiment as exp


def _chunk(chunk_id: str, text: str) -> RetrievedChunk:
    document_id = chunk_id.rsplit(":", 1)[0]
    return RetrievedChunk(
        id=chunk_id,
        document_id=document_id,
        chunk_index=int(chunk_id.rsplit(":", 1)[1]),
        source="exampleco-synthetic-policies",
        score=0.5,
        text=text,
    )


class ChunkingExperimentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.documents = exp.load_corpus()
        self.cases = exp.factual_cases()

    def test_uses_two_isolated_namespaces(self) -> None:
        self.assertEqual(exp.PRODUCTION_NAMESPACE, "maven-session2")
        self.assertEqual(exp.CANDIDATE_NAMESPACE, "maven-session2-chunk600-test")
        self.assertEqual(exp.BASELINE_NAMESPACE, "maven-session2-chunk800-test")
        self.assertNotEqual(exp.BASELINE_NAMESPACE, exp.PRODUCTION_NAMESPACE)
        self.assertNotEqual(exp.CANDIDATE_NAMESPACE, exp.PRODUCTION_NAMESPACE)
        self.assertNotEqual(exp.BASELINE_NAMESPACE, exp.CANDIDATE_NAMESPACE)

    def test_corpus_is_five_exampleco_docs_only(self) -> None:
        ids = [item["document_id"] for item in self.documents]
        self.assertEqual(
            ids,
            [
                "exampleco-remote-work",
                "exampleco-annual-leave",
                "exampleco-expenses",
                "exampleco-it-equipment",
                "exampleco-information-security",
            ],
        )
        self.assertTrue(exp.FORBIDDEN_DOCUMENT_IDS.isdisjoint(ids))

    def test_questions_match_existing_factual_set(self) -> None:
        self.assertEqual(len(self.cases), 5)
        self.assertEqual(self.cases[-1]["id"], "q5_unused_access")
        self.assertIn("60 days", self.cases[-1]["evidence_phrases"])

    def test_local_security_chunk_lengths(self) -> None:
        baseline = exp.local_chunk_preview(self.documents, exp.BASELINE)
        candidate = exp.local_chunk_preview(self.documents, exp.CANDIDATE)
        security_800 = next(
            item
            for item in baseline["documents"]
            if item["document_id"] == "exampleco-information-security"
        )
        security_600 = next(
            item
            for item in candidate["documents"]
            if item["document_id"] == "exampleco-information-security"
        )
        self.assertEqual(security_800["lengths"], [526, 709, 224])
        self.assertEqual(security_600["lengths"], [526, 573, 360])
        self.assertEqual(baseline["chunk_count"], 13)
        self.assertEqual(candidate["chunk_count"], 15)

    def test_only_chunk_size_and_namespace_differ(self) -> None:
        left = exp.dummy_config(exp.BASELINE)
        right = exp.dummy_config(exp.CANDIDATE)
        self.assertEqual(left.embedding_model, right.embedding_model)
        self.assertEqual(left.index_name, right.index_name)
        self.assertEqual(left.chunk_overlap, right.chunk_overlap)
        self.assertEqual(left.chunk_size, 800)
        self.assertEqual(right.chunk_size, 600)

    def test_production_namespace_is_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            exp.ensure_experimental_namespace("maven-session2")

    def test_metrics_from_supporting_chunk_text(self) -> None:
        cases = self.cases
        retrieved = {
            "q1_remote_days": [
                _chunk(
                    "exampleco-remote-work:0",
                    "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                )
            ],
            "q2_annual_leave": [
                _chunk(
                    "exampleco-annual-leave:0",
                    "Full-time employees receive 22 days plus public holidays.",
                )
            ],
            "q3_expense_approval": [
                _chunk(
                    "exampleco-expenses:0",
                    "Line managers may approve a single submission up to 250.",
                )
            ],
            "q4_laptop_approval": [
                _chunk("exampleco-expenses:0", "Line managers may approve 250."),
                _chunk(
                    "exampleco-it-equipment:0",
                    "Items from 400.01 require the Head of IT.",
                ),
            ],
            "q5_unused_access": [
                _chunk("exampleco-information-security:0", "MFA is required."),
                _chunk("exampleco-information-security:1", "Devices stay managed."),
                _chunk("other:0", "x"),
                _chunk("other:1", "y"),
                _chunk("other:2", "z"),
                _chunk("other:3", "w"),
                _chunk(
                    "exampleco-information-security:2",
                    "Access unused for 60 days is revoked.",
                ),
            ],
        }
        for case in cases:
            retrieved.setdefault(case["id"], [])
        scores = exp.score_condition(cases, retrieved)
        self.assertAlmostEqual(scores["recall_at_5"], 0.8)
        self.assertAlmostEqual(scores["hit_at_1"], 0.6)
        self.assertAlmostEqual(scores["mrr"], 0.7)
        self.assertEqual(scores["q5_supporting_rank"], 7)

    def test_cost_plan_has_no_generation(self) -> None:
        cost = exp.estimate_cost(self.documents, len(self.cases))
        self.assertEqual(cost["ingest_embedding_calls"], 10)
        self.assertEqual(cost["query_embedding_calls"], 10)
        self.assertEqual(cost["openai_embedding_calls"], 20)
        self.assertEqual(cost["generation_calls"], 0)
        self.assertLess(cost["estimated_usd"], 0.001)

    def test_dry_run_does_not_call_providers(self) -> None:
        with patch.object(rag, "ingest_document") as ingest:
            with patch.object(rag, "retrieve_chunks") as retrieve:
                with patch("sys.argv", ["chunking_experiment.py"]):
                    with patch("sys.stdout", new=io.StringIO()) as stdout:
                        code = exp.main()
        self.assertEqual(code, 0)
        ingest.assert_not_called()
        retrieve.assert_not_called()
        output = stdout.getvalue()
        self.assertIn("maven-session2-chunk800-test", output)
        self.assertIn("maven-session2-chunk600-test", output)
        self.assertIn("no API calls", output)

    def test_mocked_live_run_writes_only_experiment_namespaces(self) -> None:
        ingest_namespaces: list[str] = []

        def fake_ingest(*, text, document_id, source, config):
            ingest_namespaces.append(config.namespace)
            self.assertNotEqual(config.namespace, exp.PRODUCTION_NAMESPACE)
            self.assertNotIn(document_id, exp.FORBIDDEN_DOCUMENT_IDS)
            return 1

        def fake_retrieve(*, query, top_k, config):
            self.assertEqual(top_k, 10)
            self.assertEqual(config.embedding_model, "text-embedding-3-small")
            if "revoked" in query:
                return [
                    _chunk("exampleco-information-security:2", "Access unused for 60 days is revoked.")
                ]
            if "remote" in query:
                return [
                    _chunk(
                        "exampleco-remote-work:0",
                        "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                    )
                ]
            if "annual leave" in query:
                return [
                    _chunk(
                        "exampleco-annual-leave:0",
                        "22 days plus public holidays.",
                    )
                ]
            if "line manager" in query:
                return [
                    _chunk(
                        "exampleco-expenses:0",
                        "Line managers may approve a single submission up to 250.",
                    )
                ]
            return [
                _chunk(
                    "exampleco-it-equipment:0",
                    "Items from 400.01 require the Head of IT.",
                )
            ]

        with patch.object(exp, "live_config", side_effect=lambda cond: exp.dummy_config(cond)):
            with patch.object(rag, "ingest_document", side_effect=fake_ingest) as ingest:
                with patch.object(rag, "retrieve_chunks", side_effect=fake_retrieve) as retrieve:
                    scores = exp.run_live(self.documents, self.cases)

        self.assertEqual(ingest.call_count, 10)
        self.assertEqual(retrieve.call_count, 10)
        self.assertEqual(ingest_namespaces.count(exp.BASELINE_NAMESPACE), 5)
        self.assertEqual(ingest_namespaces.count(exp.CANDIDATE_NAMESPACE), 5)
        self.assertNotIn(exp.PRODUCTION_NAMESPACE, ingest_namespaces)
        self.assertEqual(scores[exp.BASELINE.name]["recall_at_5"], 1.0)
        self.assertEqual(scores[exp.CANDIDATE.name]["q5_supporting_rank"], 1)


if __name__ == "__main__":
    unittest.main()
