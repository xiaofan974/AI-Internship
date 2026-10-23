"""Bounded, read-only local lexical retrieval preview for the 19 Stage 9
classification child records (Article 6 paragraphs 1, 1a, 1b, 1c, 2–8 and
Annex III areas 1–8) from the pinned consolidated EU AI Act snapshot.

Performs deterministic lexical ranking over the 19 Stage 9 candidate children
and expands same-snapshot parent and temporal context from the Stage 4 and
Stage 5 parent files.

Makes no network, embedding, or Pinecone calls, does not modify any records
or review/indexable flags, and does not admit candidate records into the
production retrieval corpus.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent

STAGE9_CHILDREN_PATH = PROJECT_DIR / "records" / "classification_children_stage9.json"
STAGE4_ARTICLES_PATH = PROJECT_DIR / "records" / "consolidated_articles_stage4.json"
STAGE5_ANNEXES_PATH = PROJECT_DIR / "records" / "consolidated_annexes_stage5.json"

PINNED_CONSOLIDATED_SNAPSHOT_ID = (
    "T1-AIA-CONS-20260727@sha256:5e7719f77e8a606b257dc25958ee3222c4383300a5a34270a5b850a2ce8b8715"
)
ARTICLE_6_PARENT_ID = f"{PINNED_CONSOLIDATED_SNAPSHOT_ID}::article/6"
ANNEX_III_PARENT_ID = f"{PINNED_CONSOLIDATED_SNAPSHOT_ID}::annex/III"
ARTICLE_113_TEMPORAL_ID = f"{PINNED_CONSOLIDATED_SNAPSHOT_ID}::article/113"

RETRIEVAL_MODE = "local_lexical_preview"
CORPUS_SCOPE = "Article 6 and Annex III classification subset"
MAX_PREVIEW_MATCHES = 5
EXPECTED_STAGE9_CHILD_COUNT = 19

STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "into",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "that",
        "the",
        "their",
        "this",
        "to",
        "with",
    }
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _tokenize(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    filtered = [t for t in tokens if t not in STOPWORDS]
    return filtered if filtered else tokens


def _stem_key(token: str) -> str:
    """Deterministic light suffix normalization for lexical matching."""
    for suffix in ("ications", "ication", "ments", "ment", "ings", "ing", "ions", "ion", "ies", "es", "s"):
        if len(token) > len(suffix) + 3 and token.endswith(suffix):
            if suffix == "ies":
                return token[:-3] + "y"
            return token[: -len(suffix)]
    return token


def _preview_metadata() -> dict[str, Any]:
    return {
        "retrieval_mode": RETRIEVAL_MODE,
        "corpus_scope": CORPUS_SCOPE,
        "source_snapshot_id": PINNED_CONSOLIDATED_SNAPSHOT_ID,
        "ingestion_permitted": False,
        "candidate_records_admitted_to_production": False,
        "scope_and_review_notice": (
            "Local lexical preview over the 19 pending Stage 9 Article 6 and Annex III "
            "candidate child records only. Content/legal review and wider corpus coverage "
            "remain incomplete. A missing match in this 19-record subset does not establish "
            "that no legal obligation exists."
        ),
    }


def _id_summaries(
    matches: list[dict[str, Any]],
    context_records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "match_record_ids": [item["record_id"] for item in matches],
        "match_labels": [item["label"] for item in matches],
        "context_record_ids": [item["record_id"] for item in context_records],
        "context_labels": [item["label"] for item in context_records],
    }


def _error_response(query: str, category: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "query": query,
        "max_matches": MAX_PREVIEW_MATCHES,
        "match_count": 0,
        **_id_summaries([], []),
        "matches": [],
        "context_records": [],
        **_preview_metadata(),
        "error": {
            "category": category,
            "message": message,
        },
    }


def _validate_record_integrity(
    record: Any,
    *,
    source_label: str,
) -> tuple[bool, str, str]:
    if not isinstance(record, dict):
        return False, "invalid_record", f"Malformed record object in {source_label}."

    required_fields = (
        "record_id",
        "source_snapshot_id",
        "parent_id",
        "unit_kind",
        "legal_function",
        "label",
        "locator",
        "text",
        "text_sha256",
        "source_location",
        "validation_status",
        "review_status",
        "indexable",
    )
    for field in required_fields:
        if field not in record:
            return (
                False,
                "invalid_record",
                f"Record in {source_label} is missing required field '{field}'.",
            )

    record_id = str(record["record_id"])
    snap = str(record["source_snapshot_id"])
    if snap != PINNED_CONSOLIDATED_SNAPSHOT_ID or not record_id.startswith(
        PINNED_CONSOLIDATED_SNAPSHOT_ID + "::"
    ):
        return (
            False,
            "snapshot_mismatch",
            f"Record '{record_id}' in {source_label} has source_snapshot_id '{snap}', "
            f"expected pinned consolidated snapshot '{PINNED_CONSOLIDATED_SNAPSHOT_ID}'.",
        )

    text_val = record["text"]
    expected_hash = record["text_sha256"]
    if not isinstance(text_val, str) or not text_val:
        return (
            False,
            "invalid_record",
            f"Record '{record_id}' in {source_label} has empty or non-string text.",
        )

    actual_hash = _sha256_text(text_val)
    if actual_hash != expected_hash:
        return (
            False,
            "hash_mismatch",
            f"Text SHA-256 mismatch for record '{record_id}' in {source_label}: "
            f"expected {expected_hash}, computed {actual_hash}.",
        )

    return True, "", ""


def _format_record_entry(record: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Return complete, untruncated record fields with provenance."""
    return {
        "record_id": record["record_id"],
        "source_snapshot_id": record["source_snapshot_id"],
        "parent_id": record["parent_id"],
        "unit_kind": record["unit_kind"],
        "legal_function": record["legal_function"],
        "label": record["label"],
        "locator": record["locator"],
        "text": record["text"],
        "text_sha256": record["text_sha256"],
        "source_location": record["source_location"],
        "validation_status": record["validation_status"],
        "review_status": record["review_status"],
        "indexable": record["indexable"],
        **extra,
    }


def _score_child_record(
    query_norm: str,
    query_tokens: list[str],
    record: dict[str, Any],
) -> tuple[float, list[str]]:
    searchable = f"{record['label']} {record['locator'].get('path', '')} {record['text']}".lower()
    doc_tokens = set(re.findall(r"[a-z0-9]+", searchable))
    doc_stems = {_stem_key(t): t for t in doc_tokens}

    matched_terms: list[str] = []
    score = 0.0

    for q_tok in dict.fromkeys(query_tokens):
        if q_tok in doc_tokens:
            matched_terms.append(q_tok)
            occurrences = len(re.findall(rf"\b{re.escape(q_tok)}\b", searchable))
            score += 2.0 + min(occurrences, 4) * 0.25
        elif len(q_tok) >= 4 and _stem_key(q_tok) in doc_stems:
            matched_terms.append(q_tok)
            score += 1.25

    if len(query_tokens) > 1 and query_norm in searchable:
        score += 3.0

    if not matched_terms:
        return 0.0, []

    coverage = len(matched_terms) / max(len(set(query_tokens)), 1)
    total_score = round(score + coverage, 6)
    return total_score, matched_terms


def preview_classification_search(query: str) -> dict[str, Any]:
    """Deterministically search the 19 Stage 9 classification child records
    and expand complete same-snapshot parent and temporal context.
    """
    normalized_query = (query or "").strip() if isinstance(query, str) else ""
    if not normalized_query:
        return _error_response(
            "",
            "invalid_query",
            "Search query cannot be empty.",
        )

    query_tokens = _tokenize(normalized_query)
    if not query_tokens:
        return _error_response(
            normalized_query,
            "invalid_query",
            "Search query must contain at least one alphanumeric search term.",
        )

    # Load and validate local JSON files from application-controlled paths
    try:
        children_raw = json.loads(STAGE9_CHILDREN_PATH.read_text(encoding="utf-8"))
        articles_raw = json.loads(STAGE4_ARTICLES_PATH.read_text(encoding="utf-8"))
        annexes_raw = json.loads(STAGE5_ANNEXES_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return _error_response(
            normalized_query,
            "missing_corpus_file",
            f"Required local corpus file not found: {exc.filename}",
        )
    except Exception as exc:
        return _error_response(
            normalized_query,
            "corpus_load_error",
            f"Failed to load local preview JSON files: {type(exc).__name__}",
        )

    if not isinstance(children_raw, list) or len(children_raw) != EXPECTED_STAGE9_CHILD_COUNT:
        return _error_response(
            normalized_query,
            "invalid_child_inventory",
            f"Expected {EXPECTED_STAGE9_CHILD_COUNT} Stage 9 child records, "
            f"found {len(children_raw) if isinstance(children_raw, list) else 'non-list'}.",
        )

    seen_child_ids: set[str] = set()
    for child in children_raw:
        ok, category, msg = _validate_record_integrity(
            child, source_label="classification_children_stage9.json"
        )
        if not ok:
            return _error_response(normalized_query, category, msg)
        cid = child["record_id"]
        if cid in seen_child_ids:
            return _error_response(
                normalized_query,
                "duplicate_record_id",
                f"Duplicate child record_id '{cid}' in classification_children_stage9.json.",
            )
        seen_child_ids.add(cid)

    if not isinstance(articles_raw, list) or not isinstance(annexes_raw, list):
        return _error_response(
            normalized_query,
            "invalid_parent_inventory",
            "Stage 4 articles or Stage 5 annexes file is not a valid JSON list.",
        )

    parents_by_id: dict[str, dict[str, Any]] = {}
    for parent in articles_raw:
        ok, category, msg = _validate_record_integrity(
            parent, source_label="consolidated_articles_stage4.json"
        )
        if not ok:
            return _error_response(normalized_query, category, msg)
        parents_by_id[parent["record_id"]] = parent

    for parent in annexes_raw:
        ok, category, msg = _validate_record_integrity(
            parent, source_label="consolidated_annexes_stage5.json"
        )
        if not ok:
            return _error_response(normalized_query, category, msg)
        parents_by_id[parent["record_id"]] = parent

    # Verify required parent/context records exist in the loaded Stage 4 / Stage 5 sets
    for required_id, role_desc in (
        (ARTICLE_6_PARENT_ID, "Stage 4 Article 6 parent"),
        (ANNEX_III_PARENT_ID, "Stage 5 Annex III parent"),
        (ARTICLE_113_TEMPORAL_ID, "Stage 4 Article 113 temporal context"),
    ):
        if required_id not in parents_by_id:
            return _error_response(
                normalized_query,
                "missing_parent_or_context",
                f"Required {role_desc} record '{required_id}' is missing.",
            )

    # Also verify every Stage 9 child's parent_id resolves to a valid loaded parent
    for child in children_raw:
        pid = child.get("parent_id")
        if not pid or pid not in parents_by_id:
            return _error_response(
                normalized_query,
                "missing_parent_or_context",
                f"Child record '{child['record_id']}' references missing parent_id '{pid}'.",
            )

    # Deterministic lexical ranking over the 19 Stage 9 children
    q_norm = " ".join(normalized_query.lower().split())
    scored_children: list[tuple[float, int, dict[str, Any], list[str]]] = []
    for idx, child in enumerate(children_raw):
        score, matched_terms = _score_child_record(q_norm, query_tokens, child)
        if score > 0.0:
            scored_children.append((score, idx, child, matched_terms))

    if not scored_children:
        return {
            "status": "no_matches",
            "query": normalized_query,
            "max_matches": MAX_PREVIEW_MATCHES,
            "match_count": 0,
            **_id_summaries([], []),
            "matches": [],
            "context_records": [],
            **_preview_metadata(),
        }

    # Sort by descending lexical score, then by source document order (idx)
    scored_children.sort(key=lambda item: (-item[0], item[1]))
    top_scored = scored_children[:MAX_PREVIEW_MATCHES]

    matches_out: list[dict[str, Any]] = []
    required_context_ids: list[tuple[str, str]] = []

    for score, _, child, matched_terms in top_scored:
        matches_out.append(
            _format_record_entry(
                child,
                lexical_score=score,
                matched_terms=matched_terms,
            )
        )
        if child["unit_kind"] == "paragraph" and child["parent_id"] == ARTICLE_6_PARENT_ID:
            required_context_ids.append(
                (ARTICLE_6_PARENT_ID, "article_6_complete_parent")
            )
        elif child["unit_kind"] == "point" and child["parent_id"] == ANNEX_III_PARENT_ID:
            required_context_ids.append(
                (ANNEX_III_PARENT_ID, "annex_iii_complete_parent")
            )
            required_context_ids.append(
                (ARTICLE_6_PARENT_ID, "article_6_classification_context_for_annex_iii")
            )
        else:
            required_context_ids.append(
                (child["parent_id"], "direct_parent_context")
            )

    # Always include complete Article 113 as temporal context whenever results are returned
    required_context_ids.append(
        (ARTICLE_113_TEMPORAL_ID, "article_113_temporal_applicability_context")
    )

    # Deduplicate context records by record_id while preserving all applicable context roles
    context_roles_by_id: dict[str, list[str]] = {}
    ordered_context_ids: list[str] = []
    for ctx_id, role in required_context_ids:
        if ctx_id not in context_roles_by_id:
            context_roles_by_id[ctx_id] = []
            ordered_context_ids.append(ctx_id)
        if role not in context_roles_by_id[ctx_id]:
            context_roles_by_id[ctx_id].append(role)

    context_out: list[dict[str, Any]] = []
    for ctx_id in ordered_context_ids:
        ctx_rec = parents_by_id[ctx_id]
        context_out.append(
            _format_record_entry(
                ctx_rec,
                context_roles=context_roles_by_id[ctx_id],
            )
        )

    return {
        "status": "ok",
        "query": normalized_query,
        "max_matches": MAX_PREVIEW_MATCHES,
        "match_count": len(matches_out),
        **_id_summaries(matches_out, context_out),
        "matches": matches_out,
        "context_records": context_out,
        **_preview_metadata(),
    }
