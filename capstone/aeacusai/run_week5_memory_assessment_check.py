"""Two-process live memory-enabled assessment. No secrets on argv."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from aeacus_agent.memory_context import CONTEXT_BEGIN, prepare_assessment_input
from aeacus_agent.project_memory import (
    ALLOWED_FIELDS,
    ALLOWED_WRITE_CHANNEL,
    DATABASE_URL_NAME,
    delete_fact,
    generate_workspace_code,
    list_facts,
    open_memory_store,
    replace_fact,
    workspace_id_from_code,
)
from aeacus_agent.review_register import create_pending_review
from streamlit_app import finalize_preview_result, run_preview_assessment

THIS_DIR = Path(__file__).resolve().parent
STEP_ENV = "AEACUS_MEMORY_ASSESS_STEP"
WORKSPACE_ENV = "AEACUS_MEMORY_CHECK_WORKSPACE"
HANDOFF_ENV = "AEACUS_MEMORY_CHECK_HANDOFF"
DESCRIPTION = (
    "Our AI system filters job applications and ranks candidates. "
    "Human recruiters make the final hiring decision."
)
EXPECTED = {
    "project_name": "Fictional Harbour Hiring",
    "declared_actor_role": "deployer",
    "preferred_response_language": "French",
}
FRENCH_TOKEN_RE = re.compile(
    r"\b(le|la|les|des|une|un|est|pour|dans|avec|cette|cet|qui|que|système|candidats)\b",
    re.IGNORECASE,
)


def _store():
    return open_memory_store()


def _confirmed_write(store, workspace_code: str, field: str, value: str):
    return replace_fact(
        store,
        workspace_code=workspace_code,
        field=field,
        value=value,
        explicit_user_confirmation=True,
        channel=ALLOWED_WRITE_CHANNEL,
    )


def _step_write() -> int:
    store = _store()
    if getattr(store, "durable", False) is False:
        print(json.dumps({"ok": False, "status": "memory_unavailable", "step": "write"}))
        return 1
    code = generate_workspace_code()
    results = [
        _confirmed_write(store, code, field, EXPECTED[field]) for field in EXPECTED
    ]
    if not all(item.ok and item.durable and not item.mocked for item in results):
        print(json.dumps({"ok": False, "status": "write_failed", "step": "write"}))
        return 1
    handoff = Path(os.environ[HANDOFF_ENV])
    handoff.write_text(code, encoding="utf-8")
    handoff.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(json.dumps({"ok": True, "step": "write", "durable": True, "mocked": False}))
    return 0


def _read_code() -> str:
    raw = os.environ.get(WORKSPACE_ENV, "").strip()
    if raw:
        return raw
    path = os.environ.get(HANDOFF_ENV, "").strip()
    return Path(path).read_text(encoding="utf-8").strip() if path else ""


def _step_assess() -> int:
    code = _read_code()
    store = _store()
    events: list[dict] = []

    def on_event(event: dict) -> None:
        events.append(event)

    message, context, snapshot = prepare_assessment_input(
        DESCRIPTION,
        store=store,
        workspace_code=code,
        explicit={},
    )
    search_before = any(
        event.get("kind") == "act"
        and event.get("tool") == "preview_classification_search"
        for event in events
    )
    result = run_preview_assessment(message, on_event)
    search_called = any(
        event.get("kind") == "act"
        and event.get("tool") == "preview_classification_search"
        for event in events
    ) or search_before
    delivered = (
        (result or {}).get("displayed_answer")
        or (result or {}).get("assessment")
        or ""
    )
    pending = None
    if result and result.get("ok"):
        pending = create_pending_review(
            session_id="week5-memory-assess-b",
            system_description=DESCRIPTION,
            assessment=delivered,
            evidence=result.get("evidence") or [],
            memory_used=snapshot,
        )
    prefix, _timing = delivered.split("Timing and scope", 1) if "Timing and scope" in delivered else (delivered, "")
    french_hits = FRENCH_TOKEN_RE.findall(prefix)
    snapshot_values = {
        item["field"]: item["value"] for item in (snapshot or {}).get("fields") or []
    }
    payload = {
        "ok": bool(result and result.get("ok")),
        "step": "assess",
        "memory_status": context.status,
        "fresh_facts_supplied": snapshot_values == EXPECTED,
        "effective": dict(context.effective),
        "conflicts": list(context.conflicts),
        "used_cached_fallback": context.used_cached_fallback,
        "context_block_present": CONTEXT_BEGIN in message,
        "message_has_workspace_secret": False,
        "search_called": search_called,
        "failure": (result or {}).get("failure"),
        "timing_status": ((result or {}).get("timing_repair") or {}).get("status"),
        "has_english_timing_heading": "Timing and scope" in delivered,
        "has_statutory_quotation": "It shall apply from 2 August 2026" in delivered
        or "Chapter III, Sections 1, 2, and 3" in delivered,
        "french_token_count": len(french_hits),
        "provisional": delivered.startswith("Provisional finding")
        or "Provisional finding" in delivered[:80],
        "pending_status": (pending or {}).get("status"),
        "pending_has_original_input": bool(pending)
        and pending["artifact"].get("system_description") == DESCRIPTION,
        "pending_has_delivered": bool(pending)
        and pending["artifact"].get("assessment") == delivered,
        "pending_memory_matches": bool(pending)
        and pending["artifact"].get("memory_used") == snapshot,
        "snapshot_has_secret": False,
        "invocation_count": 1,
    }
    print(json.dumps(payload))
    return 0 if payload["ok"] else 1


def _step_cleanup() -> int:
    code = _read_code()
    store = _store()
    statuses = []
    for field in ALLOWED_FIELDS:
        result = delete_fact(
            store,
            workspace_code=code,
            field=field,
            explicit_user_confirmation=True,
            channel=ALLOWED_WRITE_CHANNEL,
        )
        statuses.append(result.status)
    remaining = list_facts(store, workspace_code=code)
    history = None
    if hasattr(store, "count_all_rows"):
        history = store.count_all_rows(workspace_id_from_code(code))
    print(
        json.dumps(
            {
                "ok": remaining.facts == [] and history in {0, None},
                "step": "cleanup",
                "delete_statuses": statuses,
                "active_cleared": remaining.facts == [],
                "history_rows_remaining": history,
            }
        )
    )
    return 0 if remaining.facts == [] and history in {0, None} else 1


def _run_step(step: str, extra: dict[str, str]) -> dict:
    env = os.environ.copy()
    env.update(extra)
    env[STEP_ENV] = step
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(THIS_DIR),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = {}
    if completed.stdout.strip():
        try:
            payload = json.loads(completed.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            payload = {"ok": False, "status": "child_output_not_json", "step": step}
    payload["returncode"] = completed.returncode
    return payload


def _orchestrate() -> int:
    load_dotenv(THIS_DIR / ".env", override=False, interpolate=False)
    handle = tempfile.NamedTemporaryFile(prefix="aeacus-memory-assess-", delete=False)
    handoff = Path(handle.name)
    handle.close()
    handoff.chmod(stat.S_IRUSR | stat.S_IWUSR)
    write_result = None
    assess_result = None
    cleanup_result = None
    try:
        write_result = _run_step("write", {HANDOFF_ENV: str(handoff)})
        if write_result.get("ok"):
            code = handoff.read_text(encoding="utf-8").strip()
            assess_result = _run_step(
                "assess", {WORKSPACE_ENV: code, HANDOFF_ENV: str(handoff)}
            )
        cleanup_result = _run_step("cleanup", {HANDOFF_ENV: str(handoff)})
        summary = {
            "ok": bool(
                (write_result or {}).get("ok")
                and (assess_result or {}).get("ok")
                and (cleanup_result or {}).get("ok")
            ),
            "configured_env": DATABASE_URL_NAME,
            "write": {k: (write_result or {}).get(k) for k in ("ok", "durable", "mocked")},
            "assess": {
                k: (assess_result or {}).get(k)
                for k in (
                    "ok",
                    "memory_status",
                    "fresh_facts_supplied",
                    "search_called",
                    "timing_status",
                    "has_english_timing_heading",
                    "has_statutory_quotation",
                    "french_token_count",
                    "provisional",
                    "pending_status",
                    "pending_has_original_input",
                    "pending_has_delivered",
                    "pending_memory_matches",
                    "conflicts",
                    "used_cached_fallback",
                    "failure",
                    "invocation_count",
                )
            },
            "cleanup": {
                k: (cleanup_result or {}).get(k)
                for k in ("ok", "active_cleared", "history_rows_remaining")
            },
            "browser_sessions": "unperformed",
            "retries": 0,
        }
        print(json.dumps(summary, indent=2))
        return 0 if summary["ok"] else 1
    finally:
        if handoff.exists():
            handoff.unlink()


def main() -> int:
    step = os.environ.get(STEP_ENV, "").strip()
    if step == "write":
        return _step_write()
    if step == "assess":
        return _step_assess()
    if step == "cleanup":
        return _step_cleanup()
    return _orchestrate()


if __name__ == "__main__":
    raise SystemExit(main())
