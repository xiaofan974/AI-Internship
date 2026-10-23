"""
Read-only EU AI Act legal retrieval module for AeacusAI.

Adapted from the Week 2 retrieval pipeline (`rag.py`) with strict
application-controlled configuration:
- Dedicated namespace: `aeacusai-dev` (never falls back to ExampleCo's `maven-session2`)
- Fixed `top_k = 5`
- Read-only (no ingestion, deletion, or upsert operations)
- Returns structured observations (`ok`, `no_matches`, `error`) without
  fabricating passages or metadata.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
from typing import Any, Mapping

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import NotFoundError, Pinecone

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
load_dotenv(PROJECT_DIR / ".env", override=False)

DEFAULT_INDEX_NAME = "maven-rag"
DEDICATED_NAMESPACE = "aeacusai-dev"
FORBIDDEN_NAMESPACES = frozenset({"maven-session2", "exampleco"})
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
FIXED_TOP_K = 5

logger = logging.getLogger(__name__)


class RetrievalError(RuntimeError):
    """Base error for safe retrieval failures."""


class RetrievalConfigurationError(RetrievalError):
    """Raised when required retrieval configuration is missing or invalid."""


class PineconeIndexNotFoundError(RetrievalError):
    """Raised when the configured Pinecone index does not exist."""


class PineconeConnectionError(RetrievalError):
    """Raised when Pinecone cannot be reached or queried."""


class EmbeddingError(RetrievalError):
    """Raised when OpenAI cannot create a query embedding."""


@dataclass(frozen=True)
class RetrievalConfig:
    openai_api_key: str = field(repr=False)
    pinecone_api_key: str = field(repr=False)
    index_name: str
    namespace: str
    embedding_model: str
    top_k: int = FIXED_TOP_K

    @classmethod
    def from_env(cls) -> "RetrievalConfig":
        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if (
            not openai_api_key
            or openai_api_key == "your_openai_api_key_here"
        ):
            raise RetrievalConfigurationError(
                "OPENAI_API_KEY is missing or set to placeholder."
            )

        pinecone_api_key = os.getenv("PINECONE_API_KEY", "").strip()
        if (
            not pinecone_api_key
            or pinecone_api_key == "your_pinecone_api_key_here"
        ):
            raise RetrievalConfigurationError(
                "PINECONE_API_KEY is missing or set to placeholder."
            )

        index_name = os.getenv("PINECONE_INDEX_NAME", DEFAULT_INDEX_NAME).strip()
        if not index_name or index_name == "your_pinecone_index_name_here":
            raise RetrievalConfigurationError(
                "PINECONE_INDEX_NAME cannot be empty or placeholder."
            )

        raw_namespace = os.getenv("PINECONE_NAMESPACE", DEDICATED_NAMESPACE).strip()
        if not raw_namespace:
            raise RetrievalConfigurationError("PINECONE_NAMESPACE cannot be empty.")
        if raw_namespace in FORBIDDEN_NAMESPACES or raw_namespace != DEDICATED_NAMESPACE:
            raise RetrievalConfigurationError(
                f"PINECONE_NAMESPACE must be the dedicated namespace '{DEDICATED_NAMESPACE}'."
            )

        embedding_model = os.getenv(
            "OPENAI_EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL
        ).strip()
        if not embedding_model:
            raise RetrievalConfigurationError(
                "OPENAI_EMBEDDING_MODEL cannot be empty."
            )

        return cls(
            openai_api_key=openai_api_key,
            pinecone_api_key=pinecone_api_key,
            index_name=index_name,
            namespace=DEDICATED_NAMESPACE,
            embedding_model=embedding_model,
            top_k=FIXED_TOP_K,
        )


_pinecone_client: Pinecone | None = None
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
    """Classify an exception without exposing raw provider messages or secrets."""
    if isinstance(exc, RetrievalConfigurationError):
        return "configuration_error"
    if isinstance(exc, PineconeIndexNotFoundError):
        return "index_not_found"

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


def _log_retrieval_failure(
    stage: str, exc: Exception, *, category: str | None = None
) -> None:
    """Log retrieval failures without queries, document text, or provider messages."""
    logger.error(
        "aeacusai_retrieval_failed stage=%s exception_type=%s category=%s",
        stage,
        type(exc).__name__,
        category or _sanitized_error_category(exc),
    )


def get_pinecone_client(config: RetrievalConfig | None = None) -> Pinecone:
    """Create the Pinecone client lazily."""
    global _pinecone_client
    config = config or RetrievalConfig.from_env()
    if _pinecone_client is None:
        try:
            _pinecone_client = Pinecone(api_key=config.pinecone_api_key)
        except Exception as exc:
            raise PineconeConnectionError(
                "Pinecone client initialization failed."
            ) from exc
    return _pinecone_client


def get_openai_client(config: RetrievalConfig | None = None) -> OpenAI:
    """Create the OpenAI client lazily."""
    global _openai_client
    config = config or RetrievalConfig.from_env()
    if _openai_client is None:
        try:
            _openai_client = OpenAI(api_key=config.openai_api_key)
        except Exception as exc:
            raise EmbeddingError("OpenAI client initialization failed.") from exc
    return _openai_client


def connect_to_index(config: RetrievalConfig | None = None) -> Any:
    """Connect to the configured existing Pinecone index in read-only mode."""
    global _index, _index_name
    config = config or RetrievalConfig.from_env()
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


def _extract_source_metadata(raw_metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Return only metadata fields actually present in the stored chunk."""
    reserved = {"text", "document_id", "chunk_index"}
    extracted: dict[str, Any] = {}
    for key, val in raw_metadata.items():
        if key in reserved or val is None:
            continue
        if isinstance(val, str):
            stripped = val.strip()
            if stripped:
                extracted[key] = stripped
        else:
            extracted[key] = val
    return extracted


def search_legal_sources(query: str) -> dict[str, Any]:
    """Search the curated EU AI Act legal corpus for passages matching a query.

    Embeds `query` and searches the application-configured Pinecone index in
    the dedicated `aeacusai-dev` namespace with a fixed `top_k=5`. Returns
    structured observations (`ok`, `no_matches`, or `error`) containing
    passage text, chunk IDs, document IDs, and available source metadata.
    Never generates an answer or fabricates missing citations.

    Args:
        query: Non-empty search query describing the EU AI Act concepts,
            obligations, risk categories, or definitions to look up.
    """
    normalized_query = (query or "").strip() if isinstance(query, str) else ""
    if not normalized_query:
        return {
            "status": "error",
            "query": "",
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
            "error": {
                "category": "invalid_query",
                "message": "Search query cannot be empty.",
            },
        }

    try:
        config = RetrievalConfig.from_env()
    except RetrievalConfigurationError as exc:
        _log_retrieval_failure("configuration", exc, category="configuration_error")
        return {
            "status": "error",
            "query": normalized_query,
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
            "error": {
                "category": "configuration_error",
                "message": str(exc),
            },
        }

    try:
        embedding_response = get_openai_client(config).embeddings.create(
            model=config.embedding_model,
            input=[normalized_query],
        )
        embedding_data = getattr(embedding_response, "data", None) or []
        if not embedding_data:
            raise EmbeddingError("OpenAI returned no query embedding.")
        embedding = sorted(embedding_data, key=lambda item: item.index)[0].embedding
    except Exception as exc:
        category = _sanitized_error_category(exc)
        _log_retrieval_failure("embedding", exc, category=category)
        return {
            "status": "error",
            "query": normalized_query,
            "namespace": config.namespace,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
            "error": {
                "category": category,
                "stage": "embedding",
                "message": "Query embedding failed due to an upstream provider error.",
            },
        }

    try:
        index = connect_to_index(config)
        response = index.query(
            vector=embedding,
            top_k=FIXED_TOP_K,
            namespace=DEDICATED_NAMESPACE,
            include_metadata=True,
            include_values=False,
        )
    except NotFoundError:
        return {
            "status": "no_matches",
            "query": normalized_query,
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
        }
    except PineconeIndexNotFoundError as exc:
        _log_retrieval_failure("pinecone_index", exc, category="index_not_found")
        return {
            "status": "error",
            "query": normalized_query,
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
            "error": {
                "category": "index_not_found",
                "stage": "pinecone_query",
                "message": str(exc),
            },
        }
    except Exception as exc:
        category = _sanitized_error_category(exc)
        _log_retrieval_failure("pinecone_query", exc, category=category)
        return {
            "status": "error",
            "query": normalized_query,
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
            "error": {
                "category": category,
                "stage": "pinecone_query",
                "message": "Vector search failed due to a Pinecone connection or query error.",
            },
        }

    matches = _value(response, "matches", []) or []
    passages: list[dict[str, Any]] = []
    for match in matches:
        raw_metadata = _value(match, "metadata", {}) or {}
        if not isinstance(raw_metadata, Mapping):
            raw_metadata = {}

        chunk_id = str(_value(match, "id", "") or "")
        document_id = str(raw_metadata.get("document_id", "") or "")
        text = str(raw_metadata.get("text", "") or "")

        chunk_index_raw = raw_metadata.get("chunk_index")
        try:
            chunk_index = int(chunk_index_raw) if chunk_index_raw is not None else None
        except (TypeError, ValueError):
            chunk_index = None

        try:
            score = round(float(_value(match, "score", 0.0) or 0.0), 6)
        except (TypeError, ValueError):
            score = 0.0

        source_metadata = _extract_source_metadata(raw_metadata)

        passage_entry: dict[str, Any] = {
            "chunk_id": chunk_id,
            "document_id": document_id,
            "text": text,
            "score": score,
            "metadata": source_metadata,
        }
        if chunk_index is not None:
            passage_entry["chunk_index"] = chunk_index
        if "source" in source_metadata:
            passage_entry["source"] = source_metadata["source"]

        passages.append(passage_entry)

    if not passages:
        return {
            "status": "no_matches",
            "query": normalized_query,
            "namespace": DEDICATED_NAMESPACE,
            "top_k": FIXED_TOP_K,
            "match_count": 0,
            "passages": [],
        }

    return {
        "status": "ok",
        "query": normalized_query,
        "namespace": DEDICATED_NAMESPACE,
        "top_k": FIXED_TOP_K,
        "match_count": len(passages),
        "passages": passages,
    }
