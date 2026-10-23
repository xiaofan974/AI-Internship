"""Application-owned Timing and scope renderer for the primary ADK preview.

Replaces the model-authored Timing and scope section with text grounded in
this invocation’s complete Article 113 observation. Does not call models,
change retrieval, or invent statutory dates when evidence is missing.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from aeacus_agent.context_preview import (
    ARTICLE_113_TEMPORAL_ID,
    PINNED_CONSOLIDATED_SNAPSHOT_ID,
)

FORMATTER_ID = "aeacus.timing_scope.v1"
FORMATTER_VERSION = "1"
EXPECTED_SNAPSHOT_ID = PINNED_CONSOLIDATED_SNAPSHOT_ID
EXPECTED_ARTICLE_113_RECORD_ID = ARTICLE_113_TEMPORAL_ID
EXPECTED_ARTICLE_113_TEXT_SHA256 = (
    "0f628e97ddb44755c40162f14950a4bc8072552fda2a3c38773c5a7f30c8bd4d"
)
ARTICLE_113_LABEL = "Article 113 — Entry into force and application"

TIMING_HEADING_RE = re.compile(
    r"(?im)^(?:#{1,6}\s*)?(?:\*\*)?Timing and scope(?:\*\*)?\s*$"
)
NEXT_HEADING_RE = re.compile(r"(?im)^#{1,6}\s+\S+")
GENERAL_APPLY_RE = re.compile(r"It shall apply from 2 August 2026\.")
POINT_C_RE = re.compile(
    r"Chapter III,\s*Sections 1,\s*2,\s*and 3,\s*with the exception of "
    r"Article 6\(5\),\s*shall apply from:\s*"
    r"\(i\)\s*2 December 2027 as regards AI systems classified as high-risk "
    r"pursuant to Article 6\(2\) and Annex III;\s*and\s*"
    r"\(ii\)\s*2 August 2028 as regards AI systems classified as high-risk "
    r"pursuant to Article 6\(1\) and Annex I;"
)

SUBSET_SCOPE = (
    "This is a provisional reading against the pinned classification subset "
    "only: Article 6, Annex III, and Article 113, from the consolidated "
    "edition dated 27 July 2026. It does not cover the whole EU AI Act."
)


@dataclass
class TimingRepairResult:
    status: str
    raw_output: str
    delivered_output: str
    formatter_id: str = FORMATTER_ID
    formatter_version: str = FORMATTER_VERSION
    reason: str | None = None
    source_record_id: str | None = None
    source_text_sha256: str | None = None
    source_snapshot_id: str | None = None
    prefix: str = ""
    excerpts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "formatter_id": self.formatter_id,
            "formatter_version": self.formatter_version,
            "status": self.status,
            "reason": self.reason,
            "source_record_id": self.source_record_id,
            "source_text_sha256": self.source_text_sha256,
            "source_snapshot_id": self.source_snapshot_id,
            "raw_output": self.raw_output,
            "delivered_output": self.delivered_output,
        }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def records_from_events(events: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for event in events or []:
        if not isinstance(event, dict) or event.get("kind") != "observe":
            continue
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        records.extend(
            item
            for item in list(payload.get("matches") or [])
            + list(payload.get("context_records") or [])
            if isinstance(item, dict)
        )
    return records


def records_from_evidence(evidence: Any) -> list[dict[str, Any]]:
    return [item for item in evidence or [] if isinstance(item, dict)]


def split_prefix(text: str) -> tuple[str, str | None]:
    """Return text before Timing and scope, or an ambiguity reason."""
    if not text:
        return "", None
    matches = list(TIMING_HEADING_RE.finditer(text))
    if len(matches) > 1:
        return text[: matches[0].start()].rstrip(), "ambiguous_timing_heading"
    if not matches:
        return text.rstrip(), None
    rest = text[matches[0].end() :]
    if NEXT_HEADING_RE.search(rest):
        return text[: matches[0].start()].rstrip(), "ambiguous_section_boundaries"
    return text[: matches[0].start()].rstrip(), None


def prefix_outside_timing(text: str) -> str:
    prefix, _ = split_prefix(text)
    return prefix


def _unique_search(pattern: re.Pattern[str], text: str, name: str) -> str:
    found = list(pattern.finditer(text))
    if not found:
        raise ValueError(f"missing_{name}")
    if len(found) > 1:
        raise ValueError(f"ambiguous_{name}")
    return found[0].group(0)


def _select_article_113(
    records: list[dict[str, Any]],
    *,
    expected_hash: str,
) -> dict[str, Any]:
    candidates = [
        item
        for item in records
        if item.get("record_id") == EXPECTED_ARTICLE_113_RECORD_ID
        or str(item.get("label") or "").startswith("Article 113")
    ]
    if not candidates:
        raise ValueError("missing_article_113_observation")
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        text = item.get("text") or ""
        record_id = str(item.get("record_id") or "")
        snapshot = str(item.get("source_snapshot_id") or "")
        key = (record_id, snapshot, text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    if len(normalized) > 1:
        texts = {item.get("text") for item in normalized}
        hashes = {item.get("text_sha256") for item in normalized}
        if len(texts) > 1 or len(hashes) > 1:
            raise ValueError("inconsistent_article_113_observations")
    item = normalized[0]
    text = str(item.get("text") or "")
    if not text.strip():
        raise ValueError("missing_article_113_text")
    computed = sha256_text(text)
    claimed = item.get("text_sha256")
    if claimed and claimed != computed:
        raise ValueError("observation_hash_mismatch")
    if item.get("source_snapshot_id") != EXPECTED_SNAPSHOT_ID:
        raise ValueError("wrong_edition_snapshot")
    if item.get("record_id") and item.get("record_id") != EXPECTED_ARTICLE_113_RECORD_ID:
        raise ValueError("wrong_edition_record_id")
    if computed != expected_hash:
        raise ValueError("source_text_hash_mismatch")
    return {
        "record_id": item.get("record_id") or EXPECTED_ARTICLE_113_RECORD_ID,
        "source_snapshot_id": item.get("source_snapshot_id"),
        "text": text,
        "text_sha256": computed,
        "label": item.get("label") or ARTICLE_113_LABEL,
    }


def _excerpts_from_source(text: str) -> list[str]:
    general = _unique_search(GENERAL_APPLY_RE, text, "general_application_sentence")
    point_c = _unique_search(POINT_C_RE, text, "chapter_iii_point_c")
    required = (
        "Chapter III",
        "Sections 1, 2, and 3",
        "Article 6(5)",
        "2 December 2027",
        "2 August 2028",
        "Article 6(2)",
        "Article 6(1)",
    )
    missing = [marker for marker in required if marker not in point_c]
    if missing:
        raise ValueError("incomplete_point_c_excerpt:" + ",".join(missing))
    return [general, point_c]


def _timing_section(body: str) -> str:
    return "### Timing and scope\n\n" + body.strip() + "\n"


def _ok_body(excerpts: list[str]) -> str:
    quoted = "\n\n".join(f"> {excerpt}" for excerpt in excerpts)
    return (
        f"{SUBSET_SCOPE}\n\n"
        f"From {ARTICLE_113_LABEL}:\n\n"
        f"{quoted}\n"
    )


def _fail_body(reason: str) -> str:
    return (
        f"{SUBSET_SCOPE}\n\n"
        "Timing and scope could not be rendered from this run’s Article 113 "
        f"observation: {reason}. No statutory application dates are stated.\n"
    )


def _compose(prefix: str, body: str) -> str:
    section = _timing_section(body)
    if prefix:
        return prefix + "\n\n" + section
    return section


def apply_timing_repair(
    raw_output: str,
    records: list[dict[str, Any]] | None,
    *,
    expected_hash: str = EXPECTED_ARTICLE_113_TEXT_SHA256,
) -> TimingRepairResult:
    raw = raw_output or ""
    prefix, boundary_error = split_prefix(raw)
    if boundary_error:
        delivered = _compose(prefix, _fail_body(boundary_error))
        return TimingRepairResult(
            status="failed",
            reason=boundary_error,
            raw_output=raw,
            delivered_output=delivered,
            prefix=prefix,
        )
    try:
        source = _select_article_113(records or [], expected_hash=expected_hash)
        excerpts = _excerpts_from_source(source["text"])
    except ValueError as exc:
        reason = str(exc)
        delivered = _compose(prefix, _fail_body(reason))
        return TimingRepairResult(
            status="failed",
            reason=reason,
            raw_output=raw,
            delivered_output=delivered,
            prefix=prefix,
        )
    delivered = _compose(prefix, _ok_body(excerpts))
    return TimingRepairResult(
        status="ok",
        reason=None,
        raw_output=raw,
        delivered_output=delivered,
        prefix=prefix,
        excerpts=excerpts,
        source_record_id=source["record_id"],
        source_text_sha256=source["text_sha256"],
        source_snapshot_id=source["source_snapshot_id"],
    )
