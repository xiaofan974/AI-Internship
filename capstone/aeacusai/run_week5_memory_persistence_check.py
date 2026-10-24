"""Two-process durable memory check. Do not pass secrets on argv."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from aeacus_agent.memory_postgres import PostgresMemoryStore
from aeacus_agent.project_memory import (
    ALLOWED_FIELDS,
    ALLOWED_WRITE_CHANNEL,
    DATABASE_URL_NAME,
    delete_fact,
    generate_workspace_code,
    get_fact,
    list_facts,
    open_memory_store,
    replace_fact,
    workspace_id_from_code,
)

THIS_DIR = Path(__file__).resolve().parent
STEP_ENV = "AEACUS_MEMORY_CHECK_STEP"
WORKSPACE_ENV = "AEACUS_MEMORY_CHECK_WORKSPACE"
HANDOFF_ENV = "AEACUS_MEMORY_CHECK_HANDOFF"
EXPECTED = {
    "project_name": "Fictional Harbour Pilot",
    "declared_actor_role": "deployer",
    "preferred_response_language": "French",
}
SUPERSEDED_NAME = "Fictional Dockside Review"


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
    handoff = Path(os.environ[HANDOFF_ENV])
    first = _confirmed_write(store, code, "project_name", SUPERSEDED_NAME)
    second = _confirmed_write(store, code, "project_name", EXPECTED["project_name"])
    role = _confirmed_write(store, code, "declared_actor_role", EXPECTED["declared_actor_role"])
    language = _confirmed_write(
        store, code, "preferred_response_language", EXPECTED["preferred_response_language"]
    )
    if not all(item.ok and item.durable and not item.mocked for item in (first, second, role, language)):
        failed = next(
            item for item in (first, second, role, language) if not (item.ok and item.durable)
        )
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "write_failed",
                    "step": "write",
                    "reason": failed.reason or failed.status,
                }
            )
        )
        return 1
    handoff.write_text(code, encoding="utf-8")
    handoff.chmod(stat.S_IRUSR | stat.S_IWUSR)
    print(
        json.dumps(
            {
                "ok": True,
                "step": "write",
                "durable": True,
                "mocked": False,
                "statuses": [first.status, second.status, role.status, language.status],
                "handoff": "written",
            }
        )
    )
    return 0


def _read_handoff_code() -> str:
    raw = os.environ.get(WORKSPACE_ENV, "").strip()
    if raw:
        return raw
    path = os.environ.get(HANDOFF_ENV, "").strip()
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8").strip()


def _step_read() -> int:
    code = _read_handoff_code()
    store = _store()
    if getattr(store, "durable", False) is False:
        print(json.dumps({"ok": False, "status": "memory_unavailable", "step": "read"}))
        return 1
    listed = list_facts(store, workspace_code=code)
    retrieved = {item["field"]: item["value"] for item in listed.facts}
    other = list_facts(store, workspace_code=generate_workspace_code())
    print(
        json.dumps(
            {
                "ok": listed.ok and listed.durable and not listed.mocked,
                "step": "read",
                "durable": listed.durable,
                "mocked": listed.mocked,
                "retrieved": retrieved,
                "other_workspace_empty": other.status == "empty" and other.facts == [],
                "other_workspace_durable": other.durable,
            }
        )
    )
    return 0 if listed.ok else 1


def _step_cleanup() -> int:
    code = _read_handoff_code()
    store = _store()
    if getattr(store, "durable", False) is False:
        print(json.dumps({"ok": False, "status": "memory_unavailable", "step": "cleanup"}))
        return 1
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
        if not result.ok:
            print(json.dumps({"ok": False, "status": result.status, "step": "cleanup"}))
            return 1
    remaining_gets = [
        get_fact(store, workspace_code=code, field=field).value for field in ALLOWED_FIELDS
    ]
    remaining_rows = None
    if isinstance(store, PostgresMemoryStore):
        remaining_rows = store.count_all_rows(workspace_id_from_code(code))
    print(
        json.dumps(
            {
                "ok": remaining_gets == [None, None, None] and remaining_rows == 0,
                "step": "cleanup",
                "delete_statuses": statuses,
                "active_values_cleared": remaining_gets == [None, None, None],
                "history_rows_remaining": remaining_rows,
            }
        )
    )
    return 0 if remaining_gets == [None, None, None] and remaining_rows == 0 else 1


def _run_step(step: str, env: dict[str, str]) -> dict:
    child_env = os.environ.copy()
    child_env.update(env)
    child_env[STEP_ENV] = step
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve())],
        cwd=str(THIS_DIR),
        env=child_env,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = {}
    stdout = completed.stdout.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "status": "child_output_not_json", "step": step}
    if completed.returncode != 0 and "ok" not in payload:
        payload = {"ok": False, "status": "child_failed", "step": step}
    payload["returncode"] = completed.returncode
    return payload


def _orchestrate() -> int:
    load_dotenv(THIS_DIR / ".env", override=False, interpolate=False)
    store = _store()
    if getattr(store, "durable", False) is False:
        print(
            json.dumps(
                {
                    "ok": False,
                    "status": "memory_unavailable",
                    "reason": getattr(store, "reason", "unconfigured"),
                    "fresh_process_recall": False,
                }
            )
        )
        return 1
    handle = tempfile.NamedTemporaryFile(prefix="aeacus-memory-handoff-", delete=False)
    handoff = Path(handle.name)
    handle.close()
    handoff.chmod(stat.S_IRUSR | stat.S_IWUSR)
    try:
        write_result = _run_step( "write", {HANDOFF_ENV: str(handoff)})
        if not write_result.get("ok"):
            print(json.dumps({"ok": False, "write": write_result, "read": None, "cleanup": None}))
            return 1
        code = handoff.read_text(encoding="utf-8").strip()
        read_env = {WORKSPACE_ENV: code}
        read_result = _run_step("read", read_env)
        retrieved = read_result.get("retrieved") or {}
        recall_ok = retrieved == EXPECTED
        isolation_ok = bool(read_result.get("other_workspace_empty"))
        cleanup_result = _run_step("cleanup", read_env)
        summary = {
            "ok": bool(
                write_result.get("ok")
                and read_result.get("ok")
                and recall_ok
                and isolation_ok
                and cleanup_result.get("ok")
            ),
            "write": {k: write_result.get(k) for k in ("ok", "durable", "mocked", "statuses")},
            "read": {
                "ok": read_result.get("ok"),
                "durable": read_result.get("durable"),
                "mocked": read_result.get("mocked"),
                "retrieved": retrieved,
                "matches_expected": recall_ok,
                "other_workspace_empty": isolation_ok,
            },
            "cleanup": {
                "ok": cleanup_result.get("ok"),
                "active_values_cleared": cleanup_result.get("active_values_cleared"),
                "history_rows_remaining": cleanup_result.get("history_rows_remaining"),
            },
            "fresh_process_recall": recall_ok,
            "configured_env": DATABASE_URL_NAME,
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
    if step == "read":
        return _step_read()
    if step == "cleanup":
        return _step_cleanup()
    return _orchestrate()


if __name__ == "__main__":
    raise SystemExit(main())
