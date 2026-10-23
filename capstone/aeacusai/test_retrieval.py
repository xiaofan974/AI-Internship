"""
Offline unit tests for AeacusAI retrieval tool and root ADK agent configuration.

All OpenAI and Pinecone interactions are mocked; no network calls are made.
"""

import inspect
import os
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from pinecone import NotFoundError

from aeacus_agent import (
    DEDICATED_NAMESPACE,
    DEFAULT_EMBEDDING_MODEL,
    FIXED_TOP_K,
    aeacus_review_agent,
    search_legal_sources,
)
from aeacus_agent import retrieval


VALID_ENV = {
    "OPENAI_API_KEY": "sk-test-valid-openai-key",
    "OPENAI_EMBEDDING_MODEL": "text-embedding-3-small",
    "PINECONE_API_KEY": "pcsk_test_valid_pinecone_key",
    "PINECONE_INDEX_NAME": "maven-rag",
    "PINECONE_NAMESPACE": "aeacusai-dev",
}


def _mock_embedding_response() -> SimpleNamespace:
    return SimpleNamespace(
        data=[SimpleNamespace(index=0, embedding=[0.125] * 1536)],
        usage=SimpleNamespace(total_tokens=9),
    )


def _mock_pinecone_match(
    *,
    chunk_id: str = "eu-ai-act-annex-iii:4",
    document_id: str = "eu-ai-act-annex-iii",
    chunk_index: int | None = 4,
    score: float = 0.8923,
    text: str = "AI systems intended to be used for the recruitment or selection of natural persons...",
    extra_metadata: dict | None = None,
) -> SimpleNamespace:
    metadata = {
        "document_id": document_id,
        "text": text,
    }
    if chunk_index is not None:
        metadata["chunk_index"] = chunk_index
    if extra_metadata:
        metadata.update(extra_metadata)
    return SimpleNamespace(id=chunk_id, score=score, metadata=metadata)


class AeacusAgentAttachmentTests(unittest.TestCase):
    def test_root_agent_has_exactly_one_tool_search_legal_sources(self) -> None:
        self.assertEqual(aeacus_review_agent.name, "aeacus_review_agent")
        self.assertEqual(len(aeacus_review_agent.tools), 1)
        self.assertIs(aeacus_review_agent.tools[0], search_legal_sources)
        self.assertEqual(getattr(aeacus_review_agent, "sub_agents", []), [])

    def test_tool_signature_cannot_override_index_or_namespace(self) -> None:
        sig = inspect.signature(search_legal_sources)
        self.assertEqual(list(sig.parameters.keys()), ["query"])

    def test_retrieval_module_has_no_write_or_ingest_helpers(self) -> None:
        for forbidden in ("ingest_document", "upsert", "delete"):
            self.assertFalse(hasattr(retrieval, forbidden))


class SearchLegalSourcesTests(unittest.TestCase):
    def setUp(self) -> None:
        retrieval._pinecone_client = None
        retrieval._index = None
        retrieval._index_name = None
        retrieval._openai_client = None

    @patch.dict(os.environ, VALID_ENV, clear=True)
    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_successful_retrieval_returns_ok_and_preserves_metadata_without_invention(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        mock_openai = mock_get_openai.return_value
        mock_openai.embeddings.create.return_value = _mock_embedding_response()

        mock_index = mock_connect_index.return_value
        mock_index.query.return_value = SimpleNamespace(
            matches=[
                _mock_pinecone_match(
                    extra_metadata={"source": "eu-ai-act-2024-1689"}
                )
            ]
        )

        result = search_legal_sources("recruitment and candidate screening")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["namespace"], "aeacusai-dev")
        self.assertEqual(result["top_k"], 5)
        self.assertEqual(result["match_count"], 1)
        self.assertEqual(len(result["passages"]), 1)

        passage = result["passages"][0]
        self.assertEqual(passage["chunk_id"], "eu-ai-act-annex-iii:4")
        self.assertEqual(passage["document_id"], "eu-ai-act-annex-iii")
        self.assertEqual(passage["chunk_index"], 4)
        self.assertEqual(passage["source"], "eu-ai-act-2024-1689")
        self.assertEqual(passage["metadata"], {"source": "eu-ai-act-2024-1689"})
        # Verify no invented metadata fields when absent
        for absent_field in ("article", "url", "version"):
            self.assertNotIn(absent_field, passage)
            self.assertNotIn(absent_field, passage["metadata"])

        mock_openai.embeddings.create.assert_called_once_with(
            model=DEFAULT_EMBEDDING_MODEL,
            input=["recruitment and candidate screening"],
        )
        mock_index.query.assert_called_once_with(
            vector=[0.125] * 1536,
            top_k=FIXED_TOP_K,
            namespace=DEDICATED_NAMESPACE,
            include_metadata=True,
            include_values=False,
        )
        mock_index.upsert.assert_not_called()
        mock_index.delete.assert_not_called()

    @patch.dict(os.environ, VALID_ENV, clear=True)
    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_no_matches_returns_no_matches_status(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        mock_get_openai.return_value.embeddings.create.return_value = (
            _mock_embedding_response()
        )
        mock_connect_index.return_value.query.return_value = SimpleNamespace(
            matches=[]
        )

        result = search_legal_sources("quantum computing submarine regulations")

        self.assertEqual(
            result,
            {
                "status": "no_matches",
                "query": "quantum computing submarine regulations",
                "namespace": "aeacusai-dev",
                "top_k": 5,
                "match_count": 0,
                "passages": [],
            },
        )

    @patch.dict(os.environ, VALID_ENV, clear=True)
    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_pinecone_not_found_namespace_returns_no_matches(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        mock_get_openai.return_value.embeddings.create.return_value = (
            _mock_embedding_response()
        )
        mock_connect_index.return_value.query.side_effect = NotFoundError()

        result = search_legal_sources("high-risk obligations")
        self.assertEqual(result["status"], "no_matches")
        self.assertEqual(result["match_count"], 0)
        self.assertEqual(result["passages"], [])

    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_empty_query_is_rejected_without_calling_providers(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        for blank in ("", "   ", "\n\t"):
            with self.subTest(query=blank):
                result = search_legal_sources(blank)
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["error"]["category"], "invalid_query")
                self.assertEqual(result["passages"], [])

        mock_get_openai.assert_not_called()
        mock_connect_index.assert_not_called()

    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_missing_credentials_returns_error_observation(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        missing_cases = [
            {**VALID_ENV, "OPENAI_API_KEY": ""},
            {**VALID_ENV, "OPENAI_API_KEY": "your_openai_api_key_here"},
            {**VALID_ENV, "PINECONE_API_KEY": ""},
            {**VALID_ENV, "PINECONE_API_KEY": "your_pinecone_api_key_here"},
        ]
        for env in missing_cases:
            with self.subTest(env=env):
                with patch.dict(os.environ, env, clear=True):
                    result = search_legal_sources("Annex III employment")
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(
                        result["error"]["category"], "configuration_error"
                    )
                    self.assertEqual(result["passages"], [])

        mock_get_openai.assert_not_called()
        mock_connect_index.assert_not_called()

    @patch.dict(os.environ, VALID_ENV, clear=True)
    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_provider_failure_returns_sanitized_error_without_secret_leak(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        mock_get_openai.return_value.embeddings.create.side_effect = TimeoutError(
            "upstream timeout with secret sk-test-valid-openai-key"
        )

        emb_result = search_legal_sources("Article 6 high-risk classification")
        self.assertEqual(emb_result["status"], "error")
        self.assertEqual(emb_result["error"]["category"], "timeout")
        self.assertEqual(emb_result["error"]["stage"], "embedding")
        self.assertNotIn("sk-test-valid-openai-key", str(emb_result))
        self.assertEqual(emb_result["passages"], [])
        mock_connect_index.assert_not_called()

        mock_get_openai.return_value.embeddings.create.side_effect = None
        mock_get_openai.return_value.embeddings.create.return_value = (
            _mock_embedding_response()
        )
        mock_connect_index.return_value.query.side_effect = RuntimeError(
            "pinecone failure pcsk_test_valid_pinecone_key"
        )

        pc_result = search_legal_sources("Article 6 high-risk classification")
        self.assertEqual(pc_result["status"], "error")
        self.assertEqual(pc_result["error"]["stage"], "pinecone_query")
        self.assertNotIn("pcsk_test_valid_pinecone_key", str(pc_result))
        self.assertEqual(pc_result["passages"], [])

    @patch("aeacus_agent.retrieval.connect_to_index")
    @patch("aeacus_agent.retrieval.get_openai_client")
    def test_namespace_isolation_rejects_exampleco_or_non_dedicated_namespace(
        self, mock_get_openai: MagicMock, mock_connect_index: MagicMock
    ) -> None:
        for bad_ns in ("maven-session2", "exampleco", "default", "other-ns"):
            with self.subTest(namespace=bad_ns):
                env = {**VALID_ENV, "PINECONE_NAMESPACE": bad_ns}
                with patch.dict(os.environ, env, clear=True):
                    result = search_legal_sources("biometric categorization")
                    self.assertEqual(result["status"], "error")
                    self.assertEqual(
                        result["error"]["category"], "configuration_error"
                    )
                    self.assertIn("aeacusai-dev", result["error"]["message"])
                    self.assertEqual(result["passages"], [])

        mock_get_openai.assert_not_called()
        mock_connect_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()
