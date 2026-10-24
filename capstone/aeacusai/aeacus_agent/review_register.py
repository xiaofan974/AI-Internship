"""Local human-approval register for AeacusAI preview assessments.

The model has no tool and no parameter that can write here. Only
application/backend code may record an artifact after a human approval
bound to a specific Streamlit session and the exact reviewed content.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any
import uuid

THIS_DIR = Path(__file__).resolve().parent
PROJECT_DIR = THIS_DIR.parent
DEFAULT_DB_PATH = PROJECT_DIR / "data" / "local" / "review_register.sqlite"

PENDING_STATUS = "review_required"
RECORDED_STATUS = "recorded"
REJECTED_STATUS = "rejected"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def snapshot_id_from_record(record: dict[str, Any]) -> str:
    snap = record.get("source_snapshot_id")
    if snap:
        return str(snap)
    record_id = str(record.get("record_id") or "")
    if "::" in record_id:
        return record_id.split("::", 1)[0]
    return ""


def text_sha256_from_record(record: dict[str, Any]) -> str:
    existing = record.get("text_sha256")
    if existing:
        return str(existing)
    return _sha256_text(str(record.get("text") or ""))


def evidence_binding(evidence: list[dict[str, Any]] | None) -> list[dict[str, str]]:
    """Stable evidence identity: record ID, snapshot ID, text hash."""
    bound: list[dict[str, str]] = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        record_id = str(item.get("record_id") or "").strip()
        if not record_id:
            continue
        bound.append(
            {
                "record_id": record_id,
                "source_snapshot_id": snapshot_id_from_record(item),
                "text_sha256": text_sha256_from_record(item),
            }
        )
    return bound


def canonical_artifact_payload(
    *,
    run_id: str,
    system_description: str,
    assessment: str,
    evidence: list[dict[str, Any]] | None,
    memory_used: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "run_id": run_id,
        "system_description": system_description,
        "assessment": assessment,
        "evidence": evidence_binding(evidence),
    }
    if memory_used is not None:
        payload["memory_used"] = memory_used
    return payload


def digest_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return _sha256_text(canonical)


def build_review_artifact(
    *,
    run_id: str,
    system_description: str,
    assessment: str,
    evidence: list[dict[str, Any]] | None,
    memory_used: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = canonical_artifact_payload(
        run_id=run_id,
        system_description=system_description,
        assessment=assessment,
        evidence=evidence,
        memory_used=memory_used,
    )
    artifact = dict(payload)
    artifact["content_digest"] = digest_payload(payload)
    return artifact


def create_pending_review(
    *,
    session_id: str,
    system_description: str,
    assessment: str,
    evidence: list[dict[str, Any]] | None,
    run_id: str | None = None,
    memory_used: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Session-local pending state. Not stored in the register."""
    artifact = build_review_artifact(
        run_id=run_id or str(uuid.uuid4()),
        system_description=system_description,
        assessment=assessment,
        evidence=evidence,
        memory_used=memory_used,
    )
    return {
        "session_id": session_id,
        "status": PENDING_STATUS,
        "artifact": artifact,
        "digest": artifact["content_digest"],
    }


def artifact_matches(
    pending: dict[str, Any] | None,
    *,
    session_id: str,
    system_description: str,
    assessment: str,
    evidence: list[dict[str, Any]] | None,
) -> bool:
    if not pending or pending.get("status") != PENDING_STATUS:
        return False
    if pending.get("session_id") != session_id:
        return False
    artifact = pending.get("artifact") or {}
    run_id = artifact.get("run_id")
    if not run_id:
        return False
    current = build_review_artifact(
        run_id=str(run_id),
        system_description=system_description,
        assessment=assessment,
        evidence=evidence,
        memory_used=artifact.get("memory_used"),
    )
    return current["content_digest"] == pending.get("digest")


def _connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS reviewed_assessments (
            run_id TEXT PRIMARY KEY,
            artifact_json TEXT NOT NULL,
            content_digest TEXT NOT NULL,
            reviewer_label TEXT NOT NULL,
            approved_at TEXT NOT NULL
        )
        """
    )
    return conn


def fetch_entry(db_path: Path | str, run_id: str) -> dict[str, Any] | None:
    conn = _connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT run_id, artifact_json, content_digest, reviewer_label, approved_at
            FROM reviewed_assessments
            WHERE run_id = ?
            """,
            (run_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return {
        "run_id": row[0],
        "artifact": json.loads(row[1]),
        "content_digest": row[2],
        "reviewer_label": row[3],
        "approved_at": row[4],
    }


def entry_count(db_path: Path | str, run_id: str | None = None) -> int:
    conn = _connect(db_path)
    try:
        if run_id is None:
            row = conn.execute(
                "SELECT COUNT(*) FROM reviewed_assessments"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM reviewed_assessments WHERE run_id = ?",
                (run_id,),
            ).fetchone()
    finally:
        conn.close()
    return int(row[0]) if row else 0


def reject_draft(
    pending: dict[str, Any] | None,
    *,
    session_id: str,
) -> dict[str, Any]:
    """Reject without writing a reviewed assessment."""
    if not pending or pending.get("status") != PENDING_STATUS:
        return {"ok": False, "status": "not_pending", "run_id": None}
    if pending.get("session_id") != session_id:
        return {"ok": False, "status": "session_mismatch", "run_id": None}
    run_id = (pending.get("artifact") or {}).get("run_id")
    return {"ok": True, "status": REJECTED_STATUS, "run_id": run_id}


def approve_and_record(
    pending: dict[str, Any] | None,
    *,
    session_id: str,
    reviewer_label: str,
    current_system_description: str,
    current_assessment: str,
    current_evidence: list[dict[str, Any]] | None,
    db_path: Path | str,
) -> dict[str, Any]:
    """Record only after a human approval of this session's exact artifact.

    There is no approved=True argument. Model text cannot authorize a write.
    RECORDED is the caller's responsibility after this function returns ok.
    """
    if not pending or pending.get("status") != PENDING_STATUS:
        return {"ok": False, "status": "not_pending", "run_id": None}
    if pending.get("session_id") != session_id:
        return {"ok": False, "status": "session_mismatch", "run_id": None}

    label = (reviewer_label or "").strip()
    if not label:
        return {"ok": False, "status": "missing_label", "run_id": None}

    artifact = pending.get("artifact") or {}
    run_id = artifact.get("run_id")
    if not run_id:
        return {"ok": False, "status": "invalid_artifact", "run_id": None}

    if not artifact_matches(
        pending,
        session_id=session_id,
        system_description=current_system_description,
        assessment=current_assessment,
        evidence=current_evidence,
    ):
        return {"ok": False, "status": "content_changed", "run_id": run_id}

    approved_at = datetime.now(timezone.utc).isoformat()
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN")
        conn.execute(
            """
            INSERT INTO reviewed_assessments (
                run_id, artifact_json, content_digest, reviewer_label, approved_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                json.dumps(artifact, ensure_ascii=False, sort_keys=True),
                pending["digest"],
                label,
                approved_at,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        return {"ok": False, "status": "duplicate", "run_id": run_id}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    return {
        "ok": True,
        "status": RECORDED_STATUS,
        "run_id": run_id,
        "digest": pending["digest"],
        "reviewer_label": label,
        "approved_at": approved_at,
    }
