"""Decode MCP/ADK tool observations without making another retrieval call."""

from __future__ import annotations

import json
from typing import Any


def _as_dict(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        dumped = payload.model_dump()
        return dumped if isinstance(dumped, dict) else None
    return None


def _parse_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def decode_mcp_observation(payload: Any) -> dict[str, Any] | None:
    """Return the original preview-search dict from an ADK/MCP wrapper.

    ADK may wrap the MCP JSON as ``{"content": [{"type": "text", "text": "..."}]}``
    or as ``{"result": "<json>"}``. Returns None when the original search
    payload cannot be recovered.
    """
    if isinstance(payload, str):
        payload = _parse_json_object(payload)
    data = _as_dict(payload)
    if data is None:
        return None
    if _is_preview_payload(data):
        return data
    nested = data.get("result")
    if isinstance(nested, dict) and _is_preview_payload(nested):
        return nested
    if isinstance(nested, str):
        parsed_result = _parse_json_object(nested)
        if parsed_result and _is_preview_payload(parsed_result):
            return parsed_result
        if parsed_result:
            data = parsed_result
    texts: list[str] = []
    content = data.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                texts.append(str(item["text"]))
            elif hasattr(item, "text") and item.text:
                texts.append(str(item.text))
    raw = "\n".join(texts).strip()
    parsed = _parse_json_object(raw)
    if parsed is None:
        return None
    if _is_preview_payload(parsed):
        return parsed
    inner = parsed.get("result")
    if isinstance(inner, dict) and _is_preview_payload(inner):
        return inner
    if isinstance(inner, str):
        inner_parsed = _parse_json_object(inner)
        if inner_parsed and _is_preview_payload(inner_parsed):
            return inner_parsed
    return None


def _is_preview_payload(payload: dict[str, Any]) -> bool:
    status = payload.get("status")
    if status not in {"ok", "error", "no_matches"}:
        return False
    return any(
        key in payload
        for key in ("matches", "context_records", "match_record_ids", "error")
    )


def records_from_decoded(decoded: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten match and context records, keeping complete text and hashes."""
    records: list[dict[str, Any]] = []
    seen_set: set[str] = set()
    for role, key in (("match", "matches"), ("context", "context_records")):
        for item in decoded.get(key) or []:
            if not isinstance(item, dict):
                continue
            record_id = str(item.get("record_id") or "").strip()
            if not record_id or record_id in seen_set:
                continue
            seen_set.add(record_id)
            records.append(
                {
                    "role": role,
                    "record_id": record_id,
                    "label": item.get("label") or "",
                    "text": item.get("text") or "",
                    "text_sha256": item.get("text_sha256") or "",
                    "source_snapshot_id": item.get("source_snapshot_id") or "",
                }
            )
    return records
