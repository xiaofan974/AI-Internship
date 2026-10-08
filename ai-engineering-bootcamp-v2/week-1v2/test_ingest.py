"""No-network tests for POST /ingest and the ingestion pipeline."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pinecone import NotFoundError

import rag
from main import app


def test_config(*, chunk_size: int = 800, chunk_overlap: int = 100) -> rag.PineconeConfig:
    return rag.PineconeConfig(
        api_key="test-key",
        index_name="maven-rag",
        namespace="maven-session2",
        embedding_model="text-embedding-3-small",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


def embedding_response(inputs: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=[float(index)] * 1536)
            for index, _ in enumerate(inputs)
        ]
    )


class IngestEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch.dict(os.environ, {"INGEST_API_KEY": ""})
    @patch("main.ingest_document", return_value=1)
    def test_successful_ingestion(self, mock_ingest: MagicMock) -> None:
        response = self.client.post(
            "/ingest",
            json={
                "text": "Remote work: up to 3 days per week.",
                "document_id": "handbook",
                "source": "employee-handbook",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "document_id": "handbook",
                "chunks_indexed": 1,
                "status": "success",
            },
        )
        mock_ingest.assert_called_once_with(
            text="Remote work: up to 3 days per week.",
            document_id="handbook",
            source="employee-handbook",
        )

    @patch.dict(os.environ, {"INGEST_API_KEY": ""})
    @patch("main.ingest_document")
    def test_empty_text_returns_400(self, mock_ingest: MagicMock) -> None:
        response = self.client.post(
            "/ingest",
            json={"text": "   ", "document_id": "handbook"},
        )

        self.assertEqual(response.status_code, 400)
        mock_ingest.assert_not_called()

    def test_missing_document_id_returns_422(self) -> None:
        response = self.client.post("/ingest", json={"text": "Some text"})
        self.assertEqual(response.status_code, 422)

    @patch.dict(os.environ, {"INGEST_API_KEY": ""})
    @patch("main.ingest_document")
    def test_empty_document_id_returns_400(self, mock_ingest: MagicMock) -> None:
        response = self.client.post(
            "/ingest",
            json={"text": "Some text", "document_id": "   "},
        )

        self.assertEqual(response.status_code, 400)
        mock_ingest.assert_not_called()

    @patch.dict(os.environ, {"INGEST_API_KEY": "configured-secret"})
    @patch("main.ingest_document")
    def test_configured_ingest_key_is_required(self, mock_ingest: MagicMock) -> None:
        response = self.client.post(
            "/ingest",
            json={"text": "Some text", "document_id": "handbook"},
        )

        self.assertEqual(response.status_code, 401)
        mock_ingest.assert_not_called()


class IngestionPipelineTests(unittest.TestCase):
    def test_stable_chunk_ids(self) -> None:
        self.assertEqual(rag.stable_chunk_id("handbook", 0), "handbook:0")
        self.assertEqual(rag.stable_chunk_id("handbook", 4), "handbook:4")

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_openai_and_pinecone_calls_are_mocked(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value

        chunks_indexed = rag.ingest_document(
            text="Remote work: up to 3 days per week with manager approval.",
            document_id="handbook",
            source="employee-handbook",
            config=test_config(),
        )

        self.assertEqual(chunks_indexed, 1)
        openai_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-small",
            input=["Remote work: up to 3 days per week with manager approval."],
        )
        index.delete.assert_called_once_with(
            filter={"document_id": {"$eq": "handbook"}},
            namespace="maven-session2",
        )
        vectors = index.upsert.call_args.kwargs["vectors"]
        self.assertEqual(vectors[0]["id"], "handbook:0")
        self.assertEqual(
            vectors[0]["metadata"],
            {
                "document_id": "handbook",
                "chunk_index": 0,
                "source": "employee-handbook",
                "text": "Remote work: up to 3 days per week with manager approval.",
            },
        )

    @patch("rag.chunk_document")
    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_shorter_reingestion_removes_obsolete_chunks(
        self,
        mock_openai_client: MagicMock,
        mock_connect: MagicMock,
        mock_chunk_document: MagicMock,
    ) -> None:
        mock_chunk_document.side_effect = [
            ["old chunk 0", "old chunk 1", "old chunk 2"],
            ["new chunk 0"],
        ]
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        config = test_config()

        rag.ingest_document(
            text="old version",
            document_id="handbook",
            config=config,
        )
        rag.ingest_document(
            text="shorter version",
            document_id="handbook",
            config=config,
        )

        self.assertEqual(index.delete.call_count, 2)
        self.assertEqual(
            index.method_calls,
            [
                unittest.mock.call.delete(
                    filter={"document_id": {"$eq": "handbook"}},
                    namespace="maven-session2",
                ),
                unittest.mock.call.upsert(
                    vectors=unittest.mock.ANY,
                    namespace="maven-session2",
                ),
                unittest.mock.call.delete(
                    filter={"document_id": {"$eq": "handbook"}},
                    namespace="maven-session2",
                ),
                unittest.mock.call.upsert(
                    vectors=unittest.mock.ANY,
                    namespace="maven-session2",
                ),
            ],
        )
        second_vectors = index.upsert.call_args_list[1].kwargs["vectors"]
        self.assertEqual([vector["id"] for vector in second_vectors], ["handbook:0"])

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_first_ingestion_continues_when_delete_raises_not_found(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.delete.side_effect = NotFoundError()

        chunks_indexed = rag.ingest_document(
            text="Remote work: up to 3 days per week with manager approval.",
            document_id="handbook",
            source="employee-handbook",
            config=test_config(),
        )

        self.assertEqual(chunks_indexed, 1)
        index.delete.assert_called_once_with(
            filter={"document_id": {"$eq": "handbook"}},
            namespace="maven-session2",
        )
        index.upsert.assert_called_once()
        self.assertEqual(
            index.upsert.call_args.kwargs["vectors"][0]["id"], "handbook:0"
        )

    @patch("rag.connect_to_index")
    @patch("rag.get_openai_client")
    def test_delete_errors_other_than_not_found_still_fail(
        self, mock_openai_client: MagicMock, mock_connect: MagicMock
    ) -> None:
        openai_client = mock_openai_client.return_value
        openai_client.embeddings.create.side_effect = (
            lambda *, model, input: embedding_response(input)
        )
        index = mock_connect.return_value
        index.delete.side_effect = RuntimeError("unexpected pinecone failure")

        with self.assertRaises(rag.PineconeConnectionError):
            rag.ingest_document(
                text="Remote work: up to 3 days per week with manager approval.",
                document_id="handbook",
                config=test_config(),
            )

        index.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
