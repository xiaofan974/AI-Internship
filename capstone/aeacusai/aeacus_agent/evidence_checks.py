"""Deterministic citation and quotation checks against supplied evidence.

These results are application-owned and must stay separate from the model
critic verdict. They never approve or record a draft.
"""

from __future__ import annotations

import re
from typing import Any

RECORD_ID_RE = re.compile(
    r"T1-AIA-[A-Z0-9-]+@sha256:[a-f0-9]+::[A-Za-z0-9/_-]+"
)
PROVISION_RE = re.compile(
    r"Annex III,\s*point\s*\d+[a-z]?|Article\s+\d+(?:\s*\([0-9a-z]+\))?",
    re.IGNORECASE,
)
QUOTED_RE = re.compile(r"[“\"]([^”\"]{24,})[”\"]")
_PAIRED_WRAPPERS = (
    ('"', '"'),
    ("“", "”"),
)


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def unwrap_presentation_delimiters(text: str) -> str:
    """Remove one clearly paired wrapping quote pair, if present.

    Markdown blockquote markers are stripped by the collector before this
    runs. Internal quotation marks, punctuation, and wording are kept.
    Mixed or unmatched wrappers are not removed.
    """
    cleaned = (text or "").strip()
    if len(cleaned) < 2:
        return cleaned
    for left, right in _PAIRED_WRAPPERS:
        if (
            cleaned.startswith(left)
            and cleaned.endswith(right)
            and len(cleaned) > len(left) + len(right)
        ):
            return cleaned[len(left) : -len(right)].strip()
    return cleaned


def _collect_blockquote_spans(text: str) -> list[str]:
    spans: list[str] = []
    current: list[str] = []
    for line in (text or "").splitlines():
        stripped = line.lstrip()
        if stripped.startswith(">"):
            current.append(stripped[1:].strip())
            continue
        if current:
            spans.append(" ".join(current).strip())
            current = []
    if current:
        spans.append(" ".join(current).strip())
    return [item for item in spans if item]


def extract_record_ids(text: str) -> list[str]:
    return list(dict.fromkeys(RECORD_ID_RE.findall(text or "")))


def extract_provisions(text: str) -> list[str]:
    found = [item.strip() for item in PROVISION_RE.findall(text or "")]
    return list(dict.fromkeys(found))


def extract_explicit_quotes(text: str) -> list[str]:
    quotes = [item.strip() for item in QUOTED_RE.findall(text or "")]
    for item in _collect_blockquote_spans(text):
        cleaned = unwrap_presentation_delimiters(item)
        if len(cleaned) >= 24 and cleaned not in quotes:
            quotes.append(cleaned)
    return [item for item in quotes if item]


def _provision_observed(citation: str, labels: list[str], record_ids: list[str]) -> bool:
    compact = _normalize_ws(citation).lower()
    haystack = " ".join(labels + record_ids).lower()
    if compact in haystack:
        return True
    article = re.match(r"article\s+(\d+)", compact)
    if article and (
        f"article {article.group(1)}" in haystack
        or f"article/{article.group(1)}" in haystack
    ):
        return True
    annex = re.search(r"annex iii,\s*point\s*(\d+[a-z]?)", compact)
    if annex and (
        f"point {annex.group(1)}" in haystack
        or f"point/{annex.group(1)}" in haystack
    ):
        return True
    return False


def _quote_supported(quote: str, record_texts: list[str]) -> bool:
    needle = _normalize_ws(quote)
    if len(needle) < 24:
        return True
    for text in record_texts:
        if needle in _normalize_ws(text):
            return True
    return False


def run_deterministic_checks(
    draft: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check cited IDs and explicit statutory quotations against supplied records."""
    observed_ids = [
        str(item.get("record_id") or "")
        for item in records
        if item.get("record_id")
    ]
    observed_labels = [
        str(item.get("label") or "")
        for item in records
        if item.get("label")
    ]
    record_texts = [str(item.get("text") or "") for item in records]
    cited_ids = extract_record_ids(draft)
    unknown_ids = [item for item in cited_ids if item not in observed_ids]
    provisions = extract_provisions(draft)
    unsupported_provisions = [
        item
        for item in provisions
        if not _provision_observed(item, observed_labels, observed_ids)
    ]
    quotes = extract_explicit_quotes(draft)
    altered_quotes = [
        quote for quote in quotes if not _quote_supported(quote, record_texts)
    ]
    citation_ids_ok = not unknown_ids
    quotations_ok = not altered_quotes
    return {
        "citation_ids": {
            "ok": citation_ids_ok,
            "cited": cited_ids,
            "unknown": unknown_ids,
        },
        "provisions": {
            "cited": provisions,
            "unsupported": unsupported_provisions,
            "ok": not unsupported_provisions,
        },
        "quotations": {
            "ok": quotations_ok,
            "checked": quotes,
            "unsupported": altered_quotes,
        },
        "ok": citation_ids_ok and quotations_ok,
    }
