"""AeacusAI ADK package."""

from .agent import DEFAULT_MODEL, MODEL, aeacus_review_agent, root_agent
from .retrieval import (
    DEDICATED_NAMESPACE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_INDEX_NAME,
    FIXED_TOP_K,
    RetrievalConfig,
    search_legal_sources,
)

__all__ = [
    "DEDICATED_NAMESPACE",
    "DEFAULT_EMBEDDING_MODEL",
    "DEFAULT_INDEX_NAME",
    "DEFAULT_MODEL",
    "FIXED_TOP_K",
    "MODEL",
    "RetrievalConfig",
    "aeacus_review_agent",
    "root_agent",
    "search_legal_sources",
]
