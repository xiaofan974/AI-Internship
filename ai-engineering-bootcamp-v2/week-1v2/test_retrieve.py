"""No-network tests for GET /debug/retrieve and the retrieval pipeline."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import rag
from main import app
from test_ingest import embedding_response, test_config


def pinecone_match(
    *,
    vector_id: str = "handbook:0",
    document_id: str = "handbook",
    chunk_index: int = 0,
    source: str = "employee-handbook",
    score: float = 0.91,
    text: str = "Remote work: up to 3 days per week.",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=vector_id,
        score=score,
        metadata={
            "document_id": document_id,
            "chunk_index": chunk_index,
            "source": source,
            "text": text,
        },
    )


class RetrieveEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_successful_retrieval(self, mock_retrieve: MagicMock) -> None:
        mock_retrieve.return_value = [
            rag.RetrievedChunk(
                id="handbook:0",
                document_id="handbook",
                chunk_index=0,
                source="employee-handbook",
                score=0.91,
                text="Remote work: up to 3 days per week.",
            )
        ]

        response = self.client.get(
            "/debug/retrieve",
            params={"q": "remote work policy", "top_k": 3},
            headers={"X-Ingest-Key": "configured-secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "query": "remote work policy",
                "match_count": 1,
                "matches": [
                    {
                        "id": "handbook:0",
                        "document_id": "handbook",
                        "chunk_index": 0,
                        "source": "employee-handbook",
                        "score": 0.91,
                        "text": "Remote work: up to 3 days per week.",
                    }
                ],
            },
        )
        mock_retrieve.assert_called_once_with(query="remote work policy", top_k=3)

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks", return_value=[])
    def test_empty_matches(self, mock_retrieve: MagicMock) -> None:
        response = self.client.get(
            "/debug/retrieve",
            params={"q": "unrelated question"},
            headers={"X-Ingest-Key": "configured-secret"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"query": "unrelated question", "match_count": 0, "matches": []},
        )
        mock_retrieve.assert_called_once_with(query="unrelated question", top_k=5)

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_empty_query_returns_400(self, mock_retrieve: MagicMock) -> None:
        response = self.client.get(
            "/debug/retrieve",
            params={"q": "   "},
            headers={"X-Ingest-Key": "configured-secret"},
        )

        self.assertEqual(response.status_code, 400)
        mock_retrieve.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_missing_query_returns_422(self, mock_retrieve: MagicMock) -> None:
        response = self.client.get(
            "/debug/retrieve",
            headers={"X-Ingest-Key": "configured-secret"},
        )

        self.assertEqual(response.status_code, 422)
        mock_retrieve.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_invalid_top_k_returns_400(self, mock_retrieve: MagicMock) -> None:
        for top_k in (0, 21):
            with self.subTest(top_k=top_k):
                response = self.client.get(
                    "/debug/retrieve",
                    params={"q": "remote work", "top_k": top_k},
                    headers={"X-Ingest-Key": "configured-secret"},
                )
                self.assertEqual(response.status_code, 400)
        mock_retrieve.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_missing_ingest_key_returns_401(self, mock_retrieve: MagicMock) -> None:
        response = self.client.get("/debug/retrieve", params={"q": "remote work"})

        self.assertEqual(response.status_code, 401)
        mock_retrieve.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": ""})
    @patch("main.retrieve_chunks")
    def test_unconfigured_debug_endpoint_returns_503(
        self, mock_retrieve: MagicMock
    ) -> None:
        response = self.client.get("/debug/retrieve", params={"q": "remote work"})

        self.assertEqual(response.status_code, 503)
        mock_retrieve.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks", side_effect=rag.EmbeddingError("embedding failed"))
    def test_provider_failure_returns_generic_502(
        self, mock_retrieve: MagicMock
    ) -> None:
        response = self.client.get(
            "/debug/retrieve",
            params={"q": "remote work"},
            headers={"X-Ingest-Key": "configured-secret"},
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Document retrieval failed."})
        mock_retrieve.assert_called_once()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_source_filter_is_passed(self, mock_retrieve: MagicMock) -> None:
        mock_retrieve.return_value = []
        response = self.client.get(
            "/debug/retrieve",
            params={
                "q": "remote work",
                "source": "exampleco-synthetic-policies",
            },
            headers={"X-Ingest-Key": "configured-secret"},
        )
        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once_with(
            query="remote work",
            top_k=5,
            source="exampleco-synthetic-policies",
        )

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_document_id_filter_is_passed(self, mock_retrieve: MagicMock) -> None:
        mock_retrieve.return_value = []
        response = self.client.get(
            "/debug/retrieve",
            params={"q": "remote work", "document_id": "exampleco-remote-work"},
            headers={"X-Ingest-Key": "configured-secret"},
        )
        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once_with(
            query="remote work",
            top_k=5,
            document_id="exampleco-remote-work",
        )

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_combined_filters_are_passed(self, mock_retrieve: MagicMock) -> None:
        mock_retrieve.return_value = []
        response = self.client.get(
            "/debug/retrieve",
            params={
                "q": "remote work",
                "source": "exampleco-synthetic-policies",
                "document_id": "exampleco-remote-work",
            },
            headers={"X-Ingest-Key": "configured-secret"},
        )
        self.assertEqual(response.status_code, 200)
        mock_retrieve.assert_called_once_with(
            query="remote work",
            top_k=5,
            source="exampleco-synthetic-policies",
            document_id="exampleco-remote-work",
        )

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.retrieve_chunks")
    def test_empty_filter_values_return_400(self, mock_retrieve: MagicMock) -> None:
        for params in (
            {"q": "remote work", "source": "   "},
            {"q": "remote work", "document_id": "   "},
        ):
            with self.subTest(params=params):
                response = self.client.get(
                    "/debug/retrieve",
                    params=params,
                    headers={"X-Ingest-Key": "configured-secret"},
                )
                self.assertEqual(response.status_code, 400)
        mock_retrieve.assert_not_called()


class MetadataFilterHelperTests(unittest.TestCase):
    def test_no_fields_returns_none(self) -> None:
        self.assertIsNone(rag.build_metadata_filter())

    def test_source_filter(self) -> None:
        self.assertEqual(
            rag.build_metadata_filter(source="exampleco-synthetic-policies"),
            {"source": {"$eq": "exampleco-synthetic-policies"}},
        )

    def test_document_id_filter(self) -> None:
        self.assertEqual(
            rag.build_metadata_filter(document_id="exampleco-remote-work"),
            {"document_id": {"$eq": "exampleco-remote-work"}},
        )

    def test_combined_filter_uses_and(self) -> None:
        self.assertEqual(
            rag.build_metadata_filter(
                source="exampleco-synthetic-policies",
                document_id="exampleco-remote-work",
            ),
            {
                "$and": [
                    {"source": {"$eq": "exampleco-synthetic-policies"}},
                    {"document_id": {"$eq": "exampleco-remote-work"}},
                ]
            },
        )

    def test_invalid_filter_values_raise(self) -> None:
        with self.assertRaises(rag.MetadataFilterError):
            rag.build_metadata_filter(source="   ")
        with self.assertRaises(rag.MetadataFilterError):
            rag.build_metadata_filter(document_id="x" * 201)


class RetrievalPipelineTests(unittest.TestCase):
    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_successful_retrieval_uses_query_embedding(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.return_value = SimpleNamespace(matches=[pinecone_match()])

        matches = rag.retrieve_chunks(
            query="remote work policy",
            top_k=5,
            config=test_config(),
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].id, "handbook:0")
        self.assertEqual(matches[0].document_id, "handbook")
        self.assertEqual(matches[0].chunk_index, 0)
        self.assertEqual(matches[0].source, "employee-handbook")
        self.assertEqual(matches[0].score, 0.91)
        openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["remote work policy"],
        )
        index.query.assert_called_once_with(
            vector=[0.0] * 1536,
            top_k=5,
            namespace="maven-session2",
            include_metadata=True,
            include_values=False,
        )
        index.upsert.assert_not_called()
        index.delete.assert_not_called()

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_source_filter_is_sent_to_pinecone(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.return_value = SimpleNamespace(matches=[])

        matches = rag.retrieve_chunks(
            query="remote work policy",
            top_k=5,
            config=test_config(),
            source="exampleco-synthetic-policies",
        )

        self.assertEqual(matches, [])
        index.query.assert_called_once_with(
            vector=[0.0] * 1536,
            top_k=5,
            namespace="maven-session2",
            include_metadata=True,
            include_values=False,
            filter={"source": {"$eq": "exampleco-synthetic-policies"}},
        )

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_document_id_filter_is_sent_to_pinecone(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.return_value = SimpleNamespace(matches=[])

        rag.retrieve_chunks(
            query="remote work policy",
            config=test_config(),
            document_id="exampleco-remote-work",
        )

        kwargs = index.query.call_args.kwargs
        self.assertEqual(
            kwargs["filter"],
            {"document_id": {"$eq": "exampleco-remote-work"}},
        )

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_combined_filters_are_sent_to_pinecone(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.return_value = SimpleNamespace(matches=[])

        rag.retrieve_chunks(
            query="remote work policy",
            config=test_config(),
            source="exampleco-synthetic-policies",
            document_id="exampleco-remote-work",
        )

        kwargs = index.query.call_args.kwargs
        self.assertEqual(
            kwargs["filter"],
            {
                "$and": [
                    {"source": {"$eq": "exampleco-synthetic-policies"}},
                    {"document_id": {"$eq": "exampleco-remote-work"}},
                ]
            },
        )

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_empty_matches_are_returned(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.return_value = SimpleNamespace(matches=[])

        matches = rag.retrieve_chunks(
            query="unrelated question",
            config=test_config(),
        )

        self.assertEqual(matches, [])

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_missing_namespace_returns_empty_matches(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        from pinecone import NotFoundError

        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.side_effect = NotFoundError()

        matches = rag.retrieve_chunks(
            query="remote work policy",
            config=test_config(),
        )

        self.assertEqual(matches, [])

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_embedding_failure_raises_embedding_error(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = TimeoutError()

        with self.assertRaises(rag.EmbeddingError):
            rag.retrieve_chunks(query="remote work policy", config=test_config())

        mock_connect.assert_not_called()

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_pinecone_query_failure_raises_connection_error(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.query.side_effect = RuntimeError("unexpected pinecone failure")

        with self.assertRaises(rag.PineconeConnectionError):
            rag.retrieve_chunks(query="remote work policy", config=test_config())


if __name__ == "__main__":
    unittest.main()
