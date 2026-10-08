"""Pinecone configuration and read-only connectivity helpers for Session 2."""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
from pinecone import NotFoundError, Pinecone

THIS_DIR = Path(__file__).resolve().parent
load_dotenv(THIS_DIR / ".env")
load_dotenv(THIS_DIR.parent / ".env")

DEFAULT_INDEX_NAME = "maven-rag"
DEFAULT_NAMESPACE = "maven-session2"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_TOP_K = 5
MAX_TOP_K = 20
MAX_FILTER_VALUE_LENGTH = 200

logger = logging.getLogger(__name__)


class RAGError(RuntimeError):
    """Base error for safe RAG failures."""


class PineconeConfigurationError(RAGError):
    """Raised when required Pinecone configuration is missing."""


class PineconeIndexNotFoundError(RAGError):
    """Raised when the configured Pinecone index does not exist."""


class PineconeConnectionError(RAGError):
    """Raised when Pinecone cannot be reached or queried."""


class EmbeddingError(RAGError):
    """Raised when OpenAI cannot create document embeddings."""


class MetadataFilterError(RAGError):
    """Raised when retrieval filter arguments are invalid."""


@dataclass(frozen=True)
class PineconeConfig:
    api_key: str = field(repr=False)
    index_name: str
    namespace: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int

    @classmethod
    def from_env(cls) -> "PineconeConfig":
        api_key = os.getenv("PINECONE_API_KEY", "").strip()
        if not api_key:
            raise PineconeConfigurationError(
                "PINECONE_API_KEY is missing. Add it to the local .env file "
                "or deployment environment before checking Pinecone."
            )

        index_name = os.getenv("PINECONE_INDEX_NAME", DEFAULT_INDEX_NAME).strip()
        namespace = os.getenv("PINECONE_NAMESPACE", DEFAULT_NAMESPACE).strip()
        embedding_model = os.getenv(
            "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        ).strip()
        try:
            chunk_size = int(os.getenv("RAG_CHUNK_SIZE", str(DEFAULT_CHUNK_SIZE)))
            chunk_overlap = int(
                os.getenv("RAG_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP))
            )
        except ValueError as exc:
            raise PineconeConfigurationError(
                "RAG_CHUNK_SIZE and RAG_CHUNK_OVERLAP must be integers."
            ) from exc

        if not index_name:
            raise PineconeConfigurationError("PINECONE_INDEX_NAME cannot be empty.")
        if not namespace:
            raise PineconeConfigurationError("PINECONE_NAMESPACE cannot be empty.")
        if not embedding_model:
            raise PineconeConfigurationError("OPENAI_EMBEDDING_MODEL cannot be empty.")
        if chunk_size <= 0:
            raise PineconeConfigurationError("RAG_CHUNK_SIZE must be greater than zero.")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise PineconeConfigurationError(
                "RAG_CHUNK_OVERLAP must be non-negative and smaller than RAG_CHUNK_SIZE."
            )

        return cls(
            api_key=api_key,
            index_name=index_name,
            namespace=namespace,
            embedding_model=embedding_model,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )


@dataclass(frozen=True)
class PineconeConnectivity:
    index_name: str
    namespace: str
    dimension: int
    metric: str
    total_vector_count: int
    namespace_vector_count: int


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    document_id: str
    chunk_index: int
    source: str
    score: float
    text: str


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    embedding_tokens: int
    embedding_usage_available: bool


_client: Pinecone | None = None
_index: Any | None = None
_index_name: str | None = None
_openai_client: OpenAI | None = None


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _is_not_found(exc: Exception) -> bool:
    if isinstance(exc, NotFoundError):
        return True
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    return status == 404


def _sanitized_error_category(exc: Exception) -> str:
    """Classify an exception without recording its potentially sensitive message."""

    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    if status in (401, 403):
        return "authentication_or_permission"
    if status == 404:
        return "resource_not_found"
    if status == 429:
        return "rate_limited"
    if isinstance(status, int) and status >= 500:
        return "provider_server_error"

    exception_name = type(exc).__name__.lower()
    if "timeout" in exception_name:
        return "timeout"
    if "connection" in exception_name:
        return "connection"
    if isinstance(exc, (TypeError, ValueError)):
        return "invalid_data"
    return "provider_or_pipeline_error"


def _log_ingestion_failure(
    stage: str, exc: Exception, *, category: str | None = None
) -> None:
    """Log only safe diagnostic fields—never provider messages or payload data."""

    logger.error(
        "rag_ingestion_failed stage=%s exception_type=%s category=%s",
        stage,
        type(exc).__name__,
        category or _sanitized_error_category(exc),
    )


def _log_retrieval_failure(
    stage: str, exc: Exception, *, category: str | None = None
) -> None:
    """Log retrieval failures without queries, document text, or provider messages."""

    logger.error(
        "rag_retrieval_failed stage=%s exception_type=%s category=%s",
        stage,
        type(exc).__name__,
        category or _sanitized_error_category(exc),
    )


def get_pinecone_client(config: PineconeConfig | None = None) -> Pinecone:
    """Create the Pinecone client only when it is first needed."""

    global _client
    config = config or PineconeConfig.from_env()
    if _client is None:
        try:
            _client = Pinecone(api_key=config.api_key)
        except Exception as exc:
            raise PineconeConnectionError(
                "Pinecone client initialization failed."
            ) from exc
    return _client


def get_openai_client() -> OpenAI:
    """Create the OpenAI client only when document embeddings are requested."""

    global _openai_client
    if _openai_client is None:
        try:
            _openai_client = OpenAI()
        except Exception as exc:
            raise EmbeddingError("OpenAI client initialization failed.") from exc
    return _openai_client


def connect_to_index(config: PineconeConfig | None = None) -> Any:
    """Connect to the configured existing index without writing vectors."""

    global _index, _index_name
    config = config or PineconeConfig.from_env()
    if _index is not None and _index_name == config.index_name:
        return _index

    client = get_pinecone_client(config)
    try:
        description = client.describe_index(config.index_name)
    except Exception as exc:
        if _is_not_found(exc):
            raise PineconeIndexNotFoundError(
                f"Pinecone index '{config.index_name}' was not found."
            ) from exc
        raise PineconeConnectionError(
            f"Could not describe Pinecone index '{config.index_name}'."
        ) from exc

    host = _value(description, "host")
    if not host:
        raise PineconeConnectionError(
            f"Pinecone did not return a host for index '{config.index_name}'."
        )

    try:
        _index = client.Index(host=host)
        _index_name = config.index_name
    except Exception as exc:
        raise PineconeConnectionError(
            f"Could not connect to Pinecone index '{config.index_name}'."
        ) from exc
    return _index


def chunk_document(text: str, config: PineconeConfig) -> list[str]:
    """Split a document into overlapping character-based chunks."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap,
        length_function=len,
    )
    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


def stable_chunk_id(document_id: str, chunk_index: int) -> str:
    """Return the deterministic Pinecone ID for one document chunk."""

    return f"{document_id}:{chunk_index}"


def ingest_document(
    *,
    text: str,
    document_id: str,
    source: str | None = None,
    config: PineconeConfig | None = None,
) -> int:
    """Embed and replace all chunks for one document in Pinecone."""

    config = config or PineconeConfig.from_env()
    try:
        chunks = chunk_document(text, config)
    except Exception as exc:
        _log_ingestion_failure("chunking", exc)
        raise RAGError("Document chunking failed.") from exc
    if not chunks:
        exc = ValueError("No indexable chunks were produced.")
        _log_ingestion_failure("chunking", exc, category="empty_result")
        raise RAGError("The document did not produce any indexable chunks.") from exc

    try:
        embedding_response = get_openai_client().embeddings.create(
            model=config.embedding_model,
            input=chunks,
        )
    except Exception as exc:
        _log_ingestion_failure("embedding", exc)
        if isinstance(exc, RAGError):
            raise
        raise EmbeddingError("OpenAI could not create document embeddings.") from exc

    try:
        embedding_data = sorted(embedding_response.data, key=lambda item: item.index)
        if len(embedding_data) != len(chunks):
            raise EmbeddingError(
                "OpenAI returned an unexpected number of document embeddings."
            )

        vectors = [
            {
                "id": stable_chunk_id(document_id, chunk_index),
                "values": embedding_data[chunk_index].embedding,
                "metadata": {
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "source": source or "",
                    "text": chunk,
                },
            }
            for chunk_index, chunk in enumerate(chunks)
        ]
    except Exception as exc:
        _log_ingestion_failure("embedding", exc, category="invalid_embedding_response")
        if isinstance(exc, EmbeddingError):
            raise
        raise EmbeddingError("OpenAI returned invalid embedding data.") from exc

    try:
        index = connect_to_index(config)
    except Exception as exc:
        _log_ingestion_failure("pinecone_index_access", exc)
        raise

    try:
        # Replace the document as a unit so a shorter re-ingestion cannot leave
        # stale chunks from the previous version behind.
        index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=config.namespace,
        )
    except NotFoundError:
        # First ingestion into an empty namespace is a no-op for delete.
        pass
    except Exception as exc:
        _log_ingestion_failure("pinecone_delete", exc)
        raise PineconeConnectionError(
            "Could not remove previous document chunks from Pinecone."
        ) from exc

    try:
        index.upsert(vectors=vectors, namespace=config.namespace)
    except Exception as exc:
        _log_ingestion_failure("pinecone_upsert", exc)
        raise PineconeConnectionError(
            "Could not write document chunks to Pinecone."
        ) from exc

    return len(chunks)


def _embedding_usage(embedding_response: Any) -> tuple[int, bool]:
    usage = getattr(embedding_response, "usage", None)
    if usage is None:
        return 0, False
    tokens = getattr(usage, "total_tokens", None)
    if tokens is None:
        tokens = getattr(usage, "prompt_tokens", 0)
    return int(tokens or 0), True


def _normalized_filter_value(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        raise MetadataFilterError(f"{field_name} cannot be empty.")
    if len(stripped) > MAX_FILTER_VALUE_LENGTH:
        raise MetadataFilterError(f"{field_name} is too long.")
    if any(ord(character) < 32 for character in stripped):
        raise MetadataFilterError(f"{field_name} contains invalid characters.")
    return stripped


def build_metadata_filter(
    *,
    source: str | None = None,
    document_id: str | None = None,
) -> dict[str, Any] | None:
    """Build a Pinecone metadata filter from allowlisted fields only."""

    clauses: list[dict[str, Any]] = []
    source_value = _normalized_filter_value(source, "source")
    document_value = _normalized_filter_value(document_id, "document_id")
    if source_value:
        clauses.append({"source": {"$eq": source_value}})
    if document_value:
        clauses.append({"document_id": {"$eq": document_value}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def retrieve_with_usage(
    *,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    config: PineconeConfig | None = None,
    source: str | None = None,
    document_id: str | None = None,
) -> RetrievalResult:
    """Embed a query, search Pinecone, and return matches plus embedding usage."""

    query = query.strip()
    if not query:
        raise RAGError("Query cannot be empty.")
    if top_k < 1 or top_k > MAX_TOP_K:
        raise RAGError("top_k is out of range.")

    metadata_filter = build_metadata_filter(source=source, document_id=document_id)
    config = config or PineconeConfig.from_env()

    try:
        embedding_response = get_openai_client().embeddings.create(
            model=config.embedding_model,
            input=[query],
        )
        embedding_data = embedding_response.data
        if not embedding_data:
            raise EmbeddingError("OpenAI returned no query embedding.")
        embedding = sorted(embedding_data, key=lambda item: item.index)[0].embedding
        embedding_tokens, embedding_usage_available = _embedding_usage(embedding_response)
    except Exception as exc:
        _log_retrieval_failure("embedding", exc)
        if isinstance(exc, RAGError):
            raise
        raise EmbeddingError("OpenAI could not create a query embedding.") from exc

    try:
        index = connect_to_index(config)
        query_kwargs: dict[str, Any] = {
            "vector": embedding,
            "top_k": top_k,
            "namespace": config.namespace,
            "include_metadata": True,
            "include_values": False,
        }
        if metadata_filter is not None:
            query_kwargs["filter"] = metadata_filter
        response = index.query(**query_kwargs)
    except NotFoundError:
        return RetrievalResult(
            chunks=[],
            embedding_tokens=embedding_tokens,
            embedding_usage_available=embedding_usage_available,
        )
    except Exception as exc:
        _log_retrieval_failure("pinecone_query", exc)
        if isinstance(exc, RAGError):
            raise
        raise PineconeConnectionError("Could not search Pinecone for matching chunks.") from exc

    matches = _value(response, "matches", []) or []
    results: list[RetrievedChunk] = []
    for match in matches:
        metadata = _value(match, "metadata", {}) or {}
        if not isinstance(metadata, Mapping):
            metadata = {}
        try:
            chunk_index = int(metadata.get("chunk_index", 0) or 0)
        except (TypeError, ValueError):
            chunk_index = 0
        try:
            score = float(_value(match, "score", 0.0) or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        results.append(
            RetrievedChunk(
                id=str(_value(match, "id", "") or ""),
                document_id=str(metadata.get("document_id", "") or ""),
                chunk_index=chunk_index,
                source=str(metadata.get("source", "") or ""),
                score=score,
                text=str(metadata.get("text", "") or ""),
            )
        )
    return RetrievalResult(
        chunks=results,
        embedding_tokens=embedding_tokens,
        embedding_usage_available=embedding_usage_available,
    )


def retrieve_chunks(
    *,
    query: str,
    top_k: int = DEFAULT_TOP_K,
    config: PineconeConfig | None = None,
    source: str | None = None,
    document_id: str | None = None,
) -> list[RetrievedChunk]:
    """Embed a query and return the top matching chunks. Never generates an answer."""

    return retrieve_with_usage(
        query=query,
        top_k=top_k,
        config=config,
        source=source,
        document_id=document_id,
    ).chunks


def check_pinecone_connectivity(
    config: PineconeConfig | None = None,
) -> PineconeConnectivity:
    """Read index metadata and statistics; never insert or update vectors."""

    config = config or PineconeConfig.from_env()
    client = get_pinecone_client(config)

    try:
        description = client.describe_index(config.index_name)
    except Exception as exc:
        if _is_not_found(exc):
            raise PineconeIndexNotFoundError(
                f"Pinecone index '{config.index_name}' was not found."
            ) from exc
        raise PineconeConnectionError(
            f"Could not read metadata for Pinecone index '{config.index_name}'."
        ) from exc

    dimension = _value(description, "dimension")
    metric = _value(description, "metric")
    if dimension is None or metric is None:
        raise PineconeConnectionError(
            f"Pinecone returned incomplete metadata for index '{config.index_name}'."
        )

    index = connect_to_index(config)
    try:
        stats = index.describe_index_stats()
    except Exception as exc:
        raise PineconeConnectionError(
            f"Connected to '{config.index_name}', but could not read index statistics."
        ) from exc

    namespaces = _value(stats, "namespaces", {}) or {}
    namespace_stats = (
        namespaces.get(config.namespace, {}) if isinstance(namespaces, Mapping) else {}
    )

    return PineconeConnectivity(
        index_name=config.index_name,
        namespace=config.namespace,
        dimension=int(dimension),
        metric=str(metric).lower(),
        total_vector_count=int(_value(stats, "total_vector_count", 0) or 0),
        namespace_vector_count=int(
            _value(namespace_stats, "vector_count", 0) or 0
        ),
    )
