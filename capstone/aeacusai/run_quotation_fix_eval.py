"""Verify the quotation-check fix without changing the original live report.

Offline tests first, then a saved-artifact replay with no provider calls,
then exactly one new LangGraph live recruitment run.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
ORIGINAL_LIVE = THIS_DIR / "reports" / "langgraph_preview_eval.json"
REPORT_JSON = THIS_DIR / "reports" / "langgraph_quotation_fix_eval.json"
REPORT_MD = THIS_DIR / "reports" / "langgraph_quotation_fix_eval.md"
ADK_PYTHON = THIS_DIR / ".venv" / "bin" / "python"


def _google_api_key_is_configured() -> bool:
    value = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(value) and value != GOOGLE_API_KEY_PLACEHOLDER


def _load_local_google_api_key() -> None:
    load_dotenv(THIS_DIR / ".env")
    if _google_api_key_is_configured():
        return
    bootcamp_env = (
        REPO_ROOT
        / "ai-engineering-bootcamp"
        / "adk-multi-agent-systems"
        / ".env"
    )
    if not bootcamp_env.exists():
        return
    for raw_line in bootcamp_env.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() != "GOOGLE_API_KEY":
            continue
        value = value.strip().strip('"').strip("'")
        if value and value != GOOGLE_API_KEY_PLACEHOLDER:
            os.environ["GOOGLE_API_KEY"] = value
        break


_load_local_google_api_key()

from aeacus_agent.agent import MODEL
from aeacus_agent.evidence_checks import run_deterministic_checks
from aeacus_agent.langgraph_preview import (
    GRAPH_RECURSION_LIMIT,
    MAX_LLM_CALLS,
    RUN_TIMEOUT_SECONDS,
    run_langgraph_preview,
)
from run_classification_preview import SAMPLE_PREVIEW_PROMPT


def _pkg(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "not-installed"


def installed_versions() -> dict:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "langgraph": _pkg("langgraph"),
        "google-adk": _pkg("google-adk"),
        "google-genai": _pkg("google-genai"),
        "model": MODEL,
    }


def replay_saved_artifacts(path: Path) -> dict:
    """Replay corrected checks against the saved draft and observations only."""
    original = json.loads(path.read_text(encoding="utf-8"))
    live = original.get("live_run") or {}
    draft = live.get("draft") or ""
    records = live.get("records") or []
    observations = live.get("observations") or []
    original_checks = live.get("deterministic_checks") or {}
    has_record_text = any(bool(item.get("text")) for item in records)
    has_complete_payload = any(
        isinstance(item.get("payload"), dict)
        and (item.get("payload") or {}).get("matches")
        for item in observations
    )
    inventory = {
        "draft": bool(draft),
        "record_ids": all(item.get("record_id") for item in records) if records else False,
        "record_hashes": all(item.get("text_sha256") for item in records) if records else False,
        "record_texts": has_record_text,
        "complete_observation_payloads": has_complete_payload,
    }
    sufficient = bool(draft and records and has_record_text)
    replay = {
        "citation_ids": None,
        "provisions": None,
        "quotations": {
            "skipped": True,
            "reason": (
                "Saved records include IDs and hashes but not complete source "
                "text, and observations omit full tool payloads. Quotation "
                "replay would require reconstructing evidence."
            ),
        },
    }
    if draft and records:
        partial = run_deterministic_checks(draft, records)
        replay["citation_ids"] = partial.get("citation_ids")
        replay["provisions"] = partial.get("provisions")
        if sufficient:
            replay["quotations"] = partial.get("quotations")
    return {
        "source": str(path.name),
        "original_failure": {
            "status": live.get("status"),
            "error": live.get("error"),
            "deterministic_checks": original_checks,
        },
        "artifact_inventory": inventory,
        "artifacts_sufficient_for_quotation_replay": sufficient,
        "limitation": None
        if sufficient
        else (
            "The original live report preserved the draft, record IDs, hashes, "
            "and compact observation metadata, but not complete source text or "
            "full tool payloads. Corrected quotation checks were not replayed "
            "against reconstructed corpus text."
        ),
        "replay": replay,
        "provider_calls": 0,
        "retrieval_calls": 0,
    }


def compact_complete_live(result: dict) -> dict:
    """Keep complete observation payloads and record text for later replay."""
    return {
        "execution": "ok" if result.get("status") == "review_required" else result.get("status"),
        "status": result.get("status"),
        "error": result.get("error"),
        "model_calls": result.get("model_calls"),
        "draft": result.get("draft") or "",
        "deterministic_checks": result.get("deterministic_checks") or {},
        "observations": result.get("observations") or [],
        "records": result.get("records") or [],
        "trace": result.get("trace") or [],
        "register_opened": False,
        "register_written": False,
    }


def run_command(command: list[str], cwd: Path) -> dict:
    proc = subprocess.run(command, cwd=str(cwd), capture_output=True, text=True)
    return {
        "command": command,
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stderr_tail": (proc.stderr or proc.stdout or "")[-1500:],
    }


def write_reports(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    offline = report.get("offline") or {}
    replay = report.get("saved_artifact_replay") or {}
    live = report.get("new_live_run") or {}
    lines = [
        "# LangGraph quotation-check fix verification",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "The original failed live report (`langgraph_preview_eval.json`) is unchanged.",
        "This file records offline tests, saved-artifact replay, and one new live run.",
        "",
        "## Offline tests",
        "",
        f"- LangGraph tests (`.venv-langgraph`): **{'PASS' if (offline.get('langgraph') or {}).get('passed') else 'FAIL'}**",
        f"- Evidence-check tests (ADK `.venv`): **{'PASS' if (offline.get('evidence_checks') or {}).get('passed') else 'FAIL'}**",
        f"- Dual-preview tests (ADK `.venv`): **{'PASS' if (offline.get('dual_preview') or {}).get('passed') else 'FAIL'}**",
        f"- Streamlit tests (ADK `.venv`): **{'PASS' if (offline.get('streamlit') or {}).get('passed') else 'FAIL'}**",
        "",
        "## Saved-artifact replay",
        "",
        f"- Source: `{replay.get('source')}`",
        f"- Original status: `{((replay.get('original_failure') or {}).get('status'))}`",
        f"- Artifacts sufficient for quotation replay: {replay.get('artifacts_sufficient_for_quotation_replay')}",
        f"- Provider calls: {replay.get('provider_calls')}",
        f"- Retrieval calls: {replay.get('retrieval_calls')}",
        "",
        replay.get("limitation") or "Saved artifacts included complete source text.",
        "",
        "### Original failure",
        "",
        "```",
        json.dumps((replay.get("original_failure") or {}).get("deterministic_checks") or {}, indent=2),
        "```",
        "",
        "### Replay (no reconstructed evidence)",
        "",
        "```",
        json.dumps(replay.get("replay") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## New live LangGraph run",
        "",
        f"- Execution: **{live.get('execution')}**",
        f"- Status: `{live.get('status')}`",
        f"- Model calls: {live.get('model_calls')}",
        f"- Register opened: {live.get('register_opened')}",
        f"- Register written: {live.get('register_written')}",
        "",
        "### Trace",
        "",
        "```",
        json.dumps(live.get("trace") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "### Draft",
        "",
        "```",
        str(live.get("draft") or ""),
        "```",
        "",
        "### Deterministic checks",
        "",
        "```",
        json.dumps(live.get("deterministic_checks") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Limits",
        "",
        "This verification is not legal certification or approval. "
        "A successful draft remains `review_required`.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_new_live() -> dict:
    if not _google_api_key_is_configured():
        return {
            "execution": "skipped",
            "status": "skipped",
            "error": "Live run skipped: GOOGLE_API_KEY is not configured.",
            "model_calls": 0,
            "draft": "",
            "deterministic_checks": {},
            "observations": [],
            "records": [],
            "trace": [],
            "register_opened": False,
            "register_written": False,
        }
    opened: list[str] = []
    original_connect = sqlite3.connect

    def guarded_connect(database, *args, **kwargs):
        opened.append(str(database))
        return original_connect(database, *args, **kwargs)

    sqlite3.connect = guarded_connect  # type: ignore[assignment]
    try:
        print("\n--- AEACUSAI LANGGRAPH QUOTATION-FIX LIVE VERIFICATION ---")
        print(f"Submitted System: {SAMPLE_PREVIEW_PROMPT}\n")
        result = run_langgraph_preview(SAMPLE_PREVIEW_PROMPT)
        compact = compact_complete_live(result)
        compact["register_opened"] = bool(opened)
        compact["register_written"] = False
        print(f"\nStatus: {compact.get('status')}")
        print(f"Model calls: {compact.get('model_calls')}")
        if compact.get("error"):
            print(f"Error: {compact.get('error')}")
        print(f"\nPreview Output:\n{compact.get('draft')}\n")
        return compact
    finally:
        sqlite3.connect = original_connect


def main() -> None:
    versions = installed_versions()
    print(
        f"langgraph {versions['langgraph']}; google-genai {versions['google-genai']}; "
        f"python {versions['python']}"
    )

    print("\nRunning focused LangGraph tests in .venv-langgraph...")
    langgraph_tests = run_command(
        [sys.executable, "-m", "unittest", "test_langgraph_preview", "test_evidence_checks"],
        THIS_DIR,
    )
    print(langgraph_tests["stderr_tail"])

    adk_python = str(ADK_PYTHON if ADK_PYTHON.exists() else sys.executable)
    print("\nRunning affected ADK-environment tests...")
    evidence_tests = run_command(
        [adk_python, "-m", "unittest", "test_evidence_checks"],
        THIS_DIR,
    )
    dual_tests = run_command(
        [adk_python, "-m", "unittest", "test_dual_preview"],
        THIS_DIR,
    )
    streamlit_tests = run_command(
        [adk_python, "-m", "unittest", "test_streamlit_app"],
        THIS_DIR,
    )
    print(
        "ADK: "
        f"evidence={evidence_tests['passed']} "
        f"dual={dual_tests['passed']} "
        f"streamlit={streamlit_tests['passed']}"
    )

    print("\nReplaying saved original live artifacts (no provider or retrieval)...")
    replay = replay_saved_artifacts(ORIGINAL_LIVE)
    print(
        f"sufficient={replay['artifacts_sufficient_for_quotation_replay']} "
        f"original={replay['original_failure']['status']}"
    )

    offline_ok = all(
        item["passed"]
        for item in (langgraph_tests, evidence_tests, dual_tests, streamlit_tests)
    )
    live = {
        "execution": "skipped",
        "status": "skipped",
        "error": "New live run skipped because offline checks failed.",
        "model_calls": 0,
        "draft": "",
        "deterministic_checks": {},
        "observations": [],
        "records": [],
        "trace": [],
        "register_opened": False,
        "register_written": False,
    }
    if offline_ok:
        live = run_new_live()
    else:
        print("Offline checks failed; not starting a live model run.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": versions,
        "timeouts": {
            "max_llm_calls": MAX_LLM_CALLS,
            "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
            "graph_recursion_limit": GRAPH_RECURSION_LIMIT,
        },
        "original_report_unchanged": str(ORIGINAL_LIVE),
        "offline": {
            "kind": "mocked_or_local_only",
            "passed": offline_ok,
            "langgraph": langgraph_tests,
            "evidence_checks": evidence_tests,
            "dual_preview": dual_tests,
            "streamlit": streamlit_tests,
        },
        "saved_artifact_replay": replay,
        "new_live_run": live,
        "limits": (
            "Verification distinguishes offline tests, saved-artifact replay, "
            "and one new live run. This is not legal certification."
        ),
    }
    write_reports(report)
    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Offline passed: {offline_ok}")
    print(f"Replay sufficient: {replay.get('artifacts_sufficient_for_quotation_replay')}")
    print(f"New live status: {live.get('status')}")
    print(f"New live checks ok: {(live.get('deterministic_checks') or {}).get('ok')}")


if __name__ == "__main__":
    main()
