"""Mocked tests for the RAG golden-set evaluator. No provider calls."""

import io
import os
import unittest
from unittest.mock import patch

import eval_rag


def _ask(
    answer: str,
    citations: list[str],
    retrieved: list[str],
) -> dict:
    return {
        "answer": {
            "answer": answer,
            "confidence": 0.9,
            "sources_needed": False,
            "citations": citations,
        },
        "retrieved_chunk_ids": retrieved,
        "model": "gpt-4o-mini",
        "tokens_used": 100,
        "cost_usd": 0.0001,
        "latency_ms": 1000,
    }


def _retrieve(matches: list[tuple[str, str]]) -> dict:
    return {
        "query": "q",
        "match_count": len(matches),
        "matches": [{"id": chunk_id, "text": text} for chunk_id, text in matches],
    }


class GoldenSetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = eval_rag.load_spec()
        self.cases = {case["id"]: case for case in self.spec["cases"]}

    def test_case_inventory(self) -> None:
        types = [case["type"] for case in self.spec["cases"]]
        self.assertEqual(types.count("factual"), 5)
        self.assertEqual(types.count("refusal"), 2)
        self.assertEqual(self.spec["previous_retrieval_baseline"]["recall_at_5"], 0.8)

    def test_grounded_remote_work_passes(self) -> None:
        case = self.cases["q1_remote_days"]
        ask = _ask(
            "Eligible staff may work remotely on Tuesday and Thursday only.",
            ["exampleco-remote-work:0"],
            ["exampleco-remote-work:0", "exampleco-remote-work:1"],
        )
        retrieve = _retrieve(
            [
                (
                    "exampleco-remote-work:0",
                    "Eligible staff may work remotely on Tuesday and Thursday only. "
                    "Monday, Wednesday, and Friday are mandatory office days.",
                )
            ]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertTrue(score.retrieval_hit)
        self.assertTrue(score.correctness)
        self.assertTrue(score.faithfulness)
        self.assertTrue(score.citation_validity)
        self.assertIsNone(score.refusal)

    def test_unused_access_retrieval_miss(self) -> None:
        case = self.cases["q5_unused_access"]
        ask = _ask(
            "I don't have enough information to answer that.",
            [],
            ["exampleco-remote-work:0"],
        )
        retrieve = _retrieve(
            [("exampleco-remote-work:0", "Remote days cannot be moved to another week.")]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertFalse(score.retrieval_hit)
        self.assertFalse(score.correctness)
        self.assertFalse(score.citation_validity)

    def test_forbidden_expense_citation_fails_laptop_case(self) -> None:
        case = self.cases["q4_laptop_approval"]
        ask = _ask(
            "The Head of IT approves catalogue items from 400.01.",
            ["exampleco-expenses:0"],
            ["exampleco-expenses:0", "exampleco-it-equipment:0"],
        )
        retrieve = _retrieve(
            [
                (
                    "exampleco-it-equipment:0",
                    "Items from 400.01 to 1200 require the Head of IT.",
                )
            ]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertTrue(score.retrieval_hit)
        self.assertTrue(score.correctness)
        self.assertFalse(score.citation_validity)

    def test_successful_refusal(self) -> None:
        case = self.cases["r2_sabbatical"]
        ask = _ask(eval_rag.REFUSAL_ANSWER, [], ["exampleco-annual-leave:0"])
        retrieve = _retrieve(
            [("exampleco-annual-leave:0", "Full-time employees receive 22 days of leave.")]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertIsNone(score.retrieval_hit)
        self.assertTrue(score.correctness)
        self.assertTrue(score.faithfulness)
        self.assertTrue(score.citation_validity)
        self.assertTrue(score.refusal)

    def test_invented_sabbatical_fails_refusal(self) -> None:
        case = self.cases["r2_sabbatical"]
        ask = _ask(
            "Yes, ExampleCo offers a paid sabbatical after five years.",
            ["exampleco-annual-leave:0"],
            ["exampleco-annual-leave:0"],
        )
        retrieve = _retrieve(
            [("exampleco-annual-leave:0", "Buying extra leave is not offered.")]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertFalse(score.correctness)
        self.assertFalse(score.faithfulness)
        self.assertFalse(score.citation_validity)
        self.assertFalse(score.refusal)

    def test_unfaithful_number_is_flagged(self) -> None:
        case = self.cases["q3_expense_approval"]
        ask = _ask(
            "Line managers may approve 250, or 999 in special cases.",
            ["exampleco-expenses:0"],
            ["exampleco-expenses:0"],
        )
        retrieve = _retrieve(
            [
                (
                    "exampleco-expenses:0",
                    "Line managers may approve a single submission up to 250.",
                )
            ]
        )
        score = eval_rag.evaluate_case(case, ask, retrieve)
        self.assertTrue(score.retrieval_hit)
        self.assertTrue(score.correctness)
        self.assertFalse(score.faithfulness)

    def test_markdown_labels_previous_baseline(self) -> None:
        case = self.cases["q1_remote_days"]
        ask = _ask(
            "Tuesday and Thursday only.",
            ["exampleco-remote-work:0"],
            ["exampleco-remote-work:0"],
        )
        retrieve = _retrieve(
            [
                (
                    "exampleco-remote-work:0",
                    "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                )
            ]
        )
        markdown = eval_rag.render_markdown(
            self.spec, [eval_rag.evaluate_case(case, ask, retrieve)]
        )
        self.assertIn("Previous retrieval baseline", markdown)
        self.assertIn("**not** recomputed", markdown)
        self.assertIn("| Recall@5 | 80% |", markdown)
        self.assertIn("| Hit@1 | 60% |", markdown)
        self.assertIn("| MRR | 0.70 |", markdown)
        self.assertIn("Retrieval hit (factual)", markdown)

    def test_dry_run_makes_no_http_calls(self) -> None:
        with patch.object(eval_rag, "call_json") as mocked:
            with patch("sys.argv", ["eval_rag.py"]):
                with patch("sys.stdout", new=io.StringIO()) as stdout:
                    code = eval_rag.main()
        self.assertEqual(code, 0)
        mocked.assert_not_called()
        self.assertIn("no API calls", stdout.getvalue())

    @patch.dict(os.environ, {"INGEST_API_KEY": ""}, clear=False)
    def test_live_without_key_does_not_call_api(self) -> None:
        with patch.object(eval_rag, "call_json") as mocked:
            with patch("sys.argv", ["eval_rag.py", "--live"]):
                with patch("sys.stdout", new=io.StringIO()):
                    code = eval_rag.main()
        self.assertEqual(code, 2)
        mocked.assert_not_called()

    def test_mocked_live_runner_uses_existing_routes(self) -> None:
        spec = {
            "top_k": 5,
            "cases": [self.cases["q1_remote_days"]],
        }
        ask = _ask(
            "Tuesday and Thursday only.",
            ["exampleco-remote-work:0"],
            ["exampleco-remote-work:0"],
        )
        retrieve = _retrieve(
            [
                (
                    "exampleco-remote-work:0",
                    "Tuesday and Thursday only. Monday, Wednesday, and Friday are office days.",
                )
            ]
        )

        def fake_call(method, url, payload=None, headers=None, params=None, timeout=120.0):
            if url.endswith("/ask"):
                self.assertEqual(method, "POST")
                self.assertEqual(payload["model"], "gpt-4o-mini")
                self.assertFalse(payload["force_bad"])
                return 200, ask
            self.assertEqual(method, "GET")
            self.assertTrue(url.endswith("/debug/retrieve"))
            self.assertEqual(params["top_k"], 5)
            self.assertIn("X-Ingest-Key", headers)
            return 200, retrieve

        with patch.object(eval_rag, "call_json", side_effect=fake_call):
            scores = eval_rag.run_live(spec, "https://example.test", "test-key")
        self.assertEqual(len(scores), 1)
        self.assertTrue(scores[0].correctness)


if __name__ == "__main__":
    unittest.main()
