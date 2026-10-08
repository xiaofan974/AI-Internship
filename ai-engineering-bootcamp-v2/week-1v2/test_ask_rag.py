"""No-network tests for retrieval-augmented POST /ask."""

import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import rag
from main import (
    REFUSAL_ANSWER,
    Answer,
    AskRequest,
    AskResponse,
    GROUNDING_PROMPT_TEMPLATE,
    DEFAULT_MODEL,
    app,
    build_grounding_prompt,
    validate_grounded_answer,
)


def sample_chunk() -> rag.RetrievedChunk:
    return rag.RetrievedChunk(
        id="northwind-handbook:0",
        document_id="northwind-handbook",
        chunk_index=0,
        source="northwind-sample",
        score=0.55,
        text="Northwind employees may work remotely up to three days per week.",
    )


def retrieval_result(
    chunks: list[rag.RetrievedChunk] | None = None,
    embedding_tokens: int = 12,
) -> rag.RetrievalResult:
    return rag.RetrievalResult(
        chunks=chunks if chunks is not None else [sample_chunk()],
        embedding_tokens=embedding_tokens,
        embedding_usage_available=True,
    )


def grounded_answer(**overrides) -> Answer:
    payload = {
        "answer": "Employees may work remotely up to three days per week.",
        "confidence": 0.9,
        "sources_needed": False,
        "citations": ["northwind-handbook:0"],
    }
    payload.update(overrides)
    return Answer(**payload)


class AskContractTests(unittest.TestCase):
    def test_minimal_request_and_response_fields_are_preserved(self) -> None:
        minimal = AskRequest.model_validate({"question": "What is RAG?"})
        self.assertEqual(minimal.model, DEFAULT_MODEL)
        self.assertFalse(minimal.force_bad)
        self.assertEqual(
            set(AskResponse.model_fields),
            {
                "answer",
                "tokens_used",
                "model",
                "latency_ms",
                "cost_usd",
                "attempts",
                "retrieved_chunk_ids",
            },
        )
        self.assertEqual(
            set(Answer.model_fields),
            {"answer", "confidence", "sources_needed", "citations"},
        )


class GroundingHelperTests(unittest.TestCase):
    def test_prompt_contains_required_grounding_rules(self) -> None:
        prompt = build_grounding_prompt("How many remote days?", [sample_chunk()])
        self.assertIn("Answer ONLY using the retrieved context.", prompt)
        self.assertIn("untrusted reference material", prompt)
        self.assertIn(REFUSAL_ANSWER, prompt)
        self.assertIn("[northwind-handbook:0]", prompt)
        self.assertIn("How many remote days?", prompt)
        self.assertEqual(
            GROUNDING_PROMPT_TEMPLATE.format(
                context="[northwind-handbook:0]\n"
                "Northwind employees may work remotely up to three days per week.",
                question="How many remote days?",
            ),
            prompt,
        )

    def test_duplicate_citations_are_removed(self) -> None:
        answer = validate_grounded_answer(
            grounded_answer(
                citations=["northwind-handbook:0", "northwind-handbook:0"]
            ),
            ["northwind-handbook:0"],
        )
        self.assertEqual(answer.citations, ["northwind-handbook:0"])

    def test_fabricated_citation_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_grounded_answer(
                grounded_answer(citations=["made-up:9"]),
                ["northwind-handbook:0"],
            )

    def test_refusal_cannot_include_citations(self) -> None:
        with self.assertRaises(ValueError):
            validate_grounded_answer(
                grounded_answer(
                    answer=REFUSAL_ANSWER,
                    sources_needed=True,
                    citations=["northwind-handbook:0"],
                ),
                ["northwind-handbook:0"],
            )


class AskRagEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("main.call_structured_model")
    @patch("main.retrieve_with_usage", return_value=retrieval_result())
    def test_successful_grounded_answer(
        self, mock_retrieve: MagicMock, mock_generate: MagicMock
    ) -> None:
        mock_generate.return_value = (grounded_answer(), 100, 80, 20)

        response = self.client.post(
            "/ask", json={"question": "How many days can employees work from home?"}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(
            payload["answer"]["answer"],
            "Employees may work remotely up to three days per week.",
        )
        self.assertEqual(payload["answer"]["citations"], ["northwind-handbook:0"])
        self.assertEqual(payload["retrieved_chunk_ids"], ["northwind-handbook:0"])
        self.assertEqual(payload["tokens_used"], 112)
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertIn("latency_ms", payload)
        self.assertIn("cost_usd", payload)
        self.assertIn("attempts", payload)
        mock_retrieve.assert_called_once_with(
            query="How many days can employees work from home?", top_k=5
        )
        mock_generate.assert_called_once()
        self.assertIn("[northwind-handbook:0]", mock_generate.call_args.args[0])

    @patch("main.call_structured_model")
    @patch("main.retrieve_with_usage", return_value=retrieval_result())
    def test_refusal_when_context_is_insufficient(
        self, mock_retrieve: MagicMock, mock_generate: MagicMock
    ) -> None:
        mock_generate.return_value = (
            grounded_answer(
                answer=REFUSAL_ANSWER,
                confidence=0.2,
                sources_needed=True,
                citations=[],
            ),
            90,
            70,
            20,
        )

        response = self.client.post(
            "/ask", json={"question": "Can employees bring dogs to the office?"}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"]["answer"], REFUSAL_ANSWER)
        self.assertEqual(payload["answer"]["citations"], [])
        self.assertEqual(payload["retrieved_chunk_ids"], ["northwind-handbook:0"])
        mock_retrieve.assert_called_once()

    @patch("main.call_structured_model")
    @patch("main.call_malformed_json_once")
    @patch(
        "main.retrieve_with_usage",
        return_value=retrieval_result(chunks=[]),
    )
    def test_empty_retrieval_refuses_without_generation(
        self,
        mock_retrieve: MagicMock,
        mock_malformed: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        response = self.client.post("/ask", json={"question": "What is the dress code?"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"]["answer"], REFUSAL_ANSWER)
        self.assertEqual(payload["answer"]["citations"], [])
        self.assertEqual(payload["retrieved_chunk_ids"], [])
        self.assertEqual(payload["tokens_used"], 12)
        self.assertEqual(payload["attempts"][0]["step"], "retrieval")
        mock_generate.assert_not_called()
        mock_malformed.assert_not_called()
        mock_retrieve.assert_called_once()

    @patch("main.call_structured_model")
    @patch("main.retrieve_with_usage", return_value=retrieval_result())
    def test_fabricated_citation_retries_then_succeeds(
        self, mock_retrieve: MagicMock, mock_generate: MagicMock
    ) -> None:
        mock_generate.side_effect = [
            (grounded_answer(citations=["made-up:9"]), 50, 40, 10),
            (grounded_answer(), 60, 45, 15),
        ]

        response = self.client.post(
            "/ask", json={"question": "How many remote days are allowed?"}
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"]["citations"], ["northwind-handbook:0"])
        self.assertEqual(len(payload["attempts"]), 2)
        self.assertFalse(payload["attempts"][0]["ok"])
        self.assertTrue(payload["attempts"][1]["ok"])
        self.assertEqual(mock_retrieve.call_count, 1)
        self.assertEqual(mock_generate.call_count, 2)

    @patch("main.call_structured_model")
    @patch("main.retrieve_with_usage", return_value=retrieval_result())
    def test_duplicate_citations_are_deduplicated(
        self, mock_retrieve: MagicMock, mock_generate: MagicMock
    ) -> None:
        mock_generate.return_value = (
            grounded_answer(
                citations=["northwind-handbook:0", "northwind-handbook:0"]
            ),
            80,
            60,
            20,
        )

        response = self.client.post(
            "/ask", json={"question": "How many remote days are allowed?"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"]["citations"], ["northwind-handbook:0"]
        )

    @patch("main.call_structured_model")
    @patch(
        "main.retrieve_with_usage",
        side_effect=rag.PineconeConnectionError("search failed"),
    )
    def test_retrieval_provider_failure_returns_generic_502(
        self, mock_retrieve: MagicMock, mock_generate: MagicMock
    ) -> None:
        response = self.client.post("/ask", json={"question": "How many remote days?"})

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Document retrieval failed."})
        mock_generate.assert_not_called()

    @patch("main.call_structured_model")
    @patch("main.call_malformed_json_once")
    @patch("main.retrieve_with_usage", return_value=retrieval_result())
    def test_force_bad_retrieves_once_then_retries_generation(
        self,
        mock_retrieve: MagicMock,
        mock_malformed: MagicMock,
        mock_generate: MagicMock,
    ) -> None:
        mock_malformed.return_value = (
            '{"answer":"bad","confidence":"very high","sources_needed":false}',
            40,
            30,
            10,
        )
        mock_generate.return_value = (grounded_answer(), 70, 50, 20)

        response = self.client.post(
            "/ask",
            json={
                "question": "How many remote days are allowed?",
                "model": "gpt-4o-mini",
                "force_bad": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["answer"]["citations"], ["northwind-handbook:0"])
        self.assertEqual(mock_retrieve.call_count, 1)
        mock_malformed.assert_called_once()
        mock_generate.assert_called_once()
        self.assertEqual(payload["attempts"][0]["step"], "forced_bad_json")
        self.assertFalse(payload["attempts"][0]["ok"])
        self.assertEqual(payload["attempts"][1]["step"], "structured_output")


if __name__ == "__main__":
    unittest.main()
