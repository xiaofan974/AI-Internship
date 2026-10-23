"""One bounded live classification preview through the MCP-only ADK agent.

Protocol integration is checked first with a real stdio subprocess and zero
model calls. Then exactly one recruitment assessment is run. The real review
database is not opened.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
REPORT_JSON = THIS_DIR / "reports" / "mcp_preview_eval.json"
REPORT_MD = THIS_DIR / "reports" / "mcp_preview_eval.md"


def _google_api_key_is_configured() -> bool:
    value = os.getenv("GOOGLE_API_KEY", "").strip()
    return bool(value) and value != GOOGLE_API_KEY_PLACEHOLDER


def _load_local_google_api_key() -> None:
    """Load GOOGLE_API_KEY only. Do not load OpenAI or Pinecone credentials."""
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

from aeacus_agent.agent import MODEL, aeacus_review_agent
from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.mcp_preview_agent import (
    ALLOWED_MCP_TOOLS,
    MCP_CALL_TIMEOUT_SECONDS,
    MCP_CONNECTION_TIMEOUT_SECONDS,
    create_mcp_preview_agent,
    mcp_server_launch_spec,
)
from aeacus_agent.preview_agent import aeacus_preview_agent
from aeacus_agent.retrieval import search_legal_sources
from run_classification_preview import (
    CITED_ID_RE,
    SAMPLE_PREVIEW_PROMPT,
    _print_tool_summary,
)
from run_review import MAX_LLM_CALLS, RUN_TIMEOUT_SECONDS, run_review
from test_mcp_preview import _child_pids, _pid_alive, run_protocol_checks


def installed_versions() -> dict:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "google-adk": version("google-adk"),
        "mcp": version("mcp"),
        "google-genai": version("google-genai"),
        "model": MODEL,
    }


def offline_configuration_check() -> dict:
    """Confirm the Streamlit default agent is unchanged and MCP is separate."""
    assert aeacus_preview_agent.name == "aeacus_preview_agent"
    assert aeacus_preview_agent.model == MODEL
    assert len(aeacus_preview_agent.tools) == 1
    assert aeacus_preview_agent.tools[0] is preview_classification_search
    assert getattr(aeacus_preview_agent, "sub_agents", []) == []
    assert list(inspect.signature(preview_classification_search).parameters) == [
        "query"
    ]
    assert len(aeacus_review_agent.tools) == 1
    assert aeacus_review_agent.tools[0] is search_legal_sources
    print("offline configuration check: default Streamlit preview agent unchanged")
    return {
        "default_preview_agent": aeacus_preview_agent.name,
        "default_preview_tools": [
            getattr(tool, "__name__", type(tool).__name__)
            for tool in aeacus_preview_agent.tools
        ],
        "mcp_allowlist": list(ALLOWED_MCP_TOOLS),
        "pinecone_agent_tools": [
            getattr(tool, "__name__", type(tool).__name__)
            for tool in aeacus_review_agent.tools
        ],
    }


def unwrap_preview_payload(payload: object) -> dict:
    """Unwrap ADK/MCP observation payloads, including JSON text content."""
    if not isinstance(payload, dict):
        return {}
    if payload.get("status") in {"ok", "error", "no_matches"}:
        return payload
    nested = payload.get("result")
    if isinstance(nested, dict) and nested.get("status"):
        return nested
    texts: list[str] = []
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                texts.append(str(item["text"]))
    raw = "\n".join(texts).strip()
    if raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            return parsed
    return payload


def observation_ids(tool_log: list) -> list[str]:
    seen: list[str] = []
    for event in tool_log:
        if event.get("type") != "response":
            continue
        body = unwrap_preview_payload(event.get("payload"))
        for key in ("match_record_ids", "context_record_ids"):
            for record_id in body.get(key) or []:
                if record_id not in seen:
                    seen.append(record_id)
        for group in ("matches", "context_records"):
            for item in body.get(group) or []:
                if not isinstance(item, dict):
                    continue
                record_id = item.get("record_id")
                if record_id and record_id not in seen:
                    seen.append(record_id)
    return seen


def compact_tool_log(tool_log: list) -> list[dict]:
    compact: list[dict] = []
    for event in tool_log:
        item = {"type": event.get("type"), "tool": event.get("tool")}
        if event.get("type") == "call":
            item["args"] = event.get("args")
        else:
            body = unwrap_preview_payload(event.get("payload"))
            item["status"] = body.get("status")
            item["match_labels"] = body.get("match_labels")
            item["match_record_ids"] = body.get("match_record_ids")
            item["context_labels"] = body.get("context_labels")
            item["context_record_ids"] = body.get("context_record_ids")
            if body.get("status") == "error":
                item["error"] = body.get("error")
        compact.append(item)
    return compact


def write_reports(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    live = report.get("live_run") or {}
    protocol = report.get("protocol") or {}
    launch = report.get("launch") or {}
    lines = [
        "# MCP-backed classification preview checkpoint",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "The Streamlit demo and `aeacus_preview_agent` remain on the direct Python tool.",
        "This checkpoint uses a separate MCP-only agent.",
        "",
        "## Installed versions",
        "",
        f"- Python: `{report['versions']['python']}` (`{report['versions']['executable']}`)",
        f"- google-adk: `{report['versions']['google-adk']}`",
        f"- mcp: `{report['versions']['mcp']}`",
        f"- google-genai: `{report['versions']['google-genai']}`",
        f"- Model: `{report['versions']['model']}`",
        "",
        "## Server launch method",
        "",
        f"- Command: `{launch.get('command')}`",
        f"- Args: `{launch.get('args')}`",
        f"- Working directory: `{launch.get('cwd')}`",
        f"- Connection timeout: {MCP_CONNECTION_TIMEOUT_SECONDS}s",
        f"- Call/read timeout: {MCP_CALL_TIMEOUT_SECONDS}s",
        "",
        "## Protocol checks (no model calls)",
        "",
        f"- Initialize: **{'PASS' if (protocol.get('initialize') or {}).get('ok') else 'FAIL'}**",
        f"- List tools: `{(protocol.get('list_tools') or {}).get('names')}`",
        f"- Recruitment parity: **{'PASS' if (protocol.get('parity') or {}).get('recruitment') else 'FAIL'}**",
        f"- Empty-query parity: **{'PASS' if (protocol.get('parity') or {}).get('empty_query') else 'FAIL'}**",
        f"- Subprocess cleanup: **{'PASS' if (protocol.get('cleanup') or {}).get('ok') else 'FAIL'}**",
        "",
        "```",
        json.dumps(
            {
                "initialize": protocol.get("initialize"),
                "list_tools": protocol.get("list_tools"),
                "recruitment_call": {
                    key: value
                    for key, value in (protocol.get("recruitment_call") or {}).items()
                    if key != "payload"
                },
                "empty_query": protocol.get("empty_query"),
                "cleanup": protocol.get("cleanup"),
            },
            indent=2,
            ensure_ascii=False,
        ),
        "```",
        "",
        "## Live MCP-only assessment",
        "",
        f"- Execution: **{live.get('execution')}**",
        f"- Live invocations used: {live.get('invocations_used')}",
        f"- Register opened: {live.get('register_opened')}",
        "",
        "### Tool calls",
        "",
    ]
    calls = live.get("tool_calls") or []
    if calls:
        for index, call in enumerate(calls, start=1):
            lines.append(
                f"{index}. `{call.get('tool')}` query={call.get('query')!r}"
            )
    else:
        lines.append("No tool calls were recorded.")
    lines.extend(
        [
            "",
            "### Observed evidence IDs",
            "",
            live.get("observed_ids_note") or "",
            "",
            "```",
            json.dumps(live.get("observed_record_ids") or [], indent=2),
            "```",
            "",
            "### Final answer",
            "",
            "```",
            str(live.get("final_answer") or ""),
            "```",
            "",
            "### Cleanup",
            "",
            json.dumps(live.get("cleanup") or {}, indent=2),
            "",
            "## Limits",
            "",
            "One MCP-backed live run is not a general MCP security or reliability proof.",
            "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_live_assessment() -> dict:
    if not _google_api_key_is_configured():
        return {
            "execution": "skipped",
            "invocations_used": 0,
            "final_answer": "Live run skipped: GOOGLE_API_KEY is not configured.",
            "tool_calls": [],
            "tool_log": [],
            "observed_record_ids": [],
            "cited_record_ids": [],
            "cited_ids_missing_from_observations": [],
            "register_opened": False,
            "cleanup": {"ok": True, "note": "No MCP agent process was started."},
        }

    parent = os.getpid()
    before = _child_pids(parent)
    agent, toolset = create_mcp_preview_agent()
    tool_log: list = []
    answer = None
    try:
        print("\n--- AEACUSAI MCP CLASSIFICATION PREVIEW ---")
        print(f"Submitted System: {SAMPLE_PREVIEW_PROMPT}\n")
        answer = await run_review(
            SAMPLE_PREVIEW_PROMPT,
            agent=agent,
            max_llm_calls=MAX_LLM_CALLS,
            timeout_seconds=RUN_TIMEOUT_SECONDS,
            tool_log=tool_log,
        )
        print(f"\nPreview Output:\n{answer}\n")
        _print_tool_summary(tool_log, answer)
        execution = (
            "failed" if str(answer).startswith("[FAILED]") else "ok"
        )
    except Exception as exc:
        execution = "failed"
        answer = f"[FAILED] Provider/execution failure ({type(exc).__name__}): {exc}"
        print(answer)
    finally:
        try:
            await toolset.close()
        except Exception as exc:
            print(f"toolset.close() warning: {type(exc).__name__}: {exc}", file=sys.stderr)

    leftover = sorted(
        pid for pid in (_child_pids(parent) - before) if _pid_alive(pid)
    )
    observed = observation_ids(tool_log)
    cited = list(dict.fromkeys(CITED_ID_RE.findall(str(answer or ""))))
    calls = [
        {
            "tool": event.get("tool"),
            "query": (event.get("args") or {}).get("query"),
        }
        for event in tool_log
        if event.get("type") == "call"
    ]
    return {
        "execution": execution,
        "invocations_used": 1,
        "agent": agent.name,
        "final_answer": answer,
        "tool_calls": calls,
        "tool_log": compact_tool_log(tool_log),
        "observed_record_ids": observed,
        "cited_record_ids": cited,
        "cited_ids_missing_from_observations": [
            record_id for record_id in cited if record_id not in observed
        ],
        "register_opened": False,
        "cleanup": {
            "ok": not leftover,
            "leftover_child_pids": leftover,
        },
    }


async def main() -> None:
    versions = installed_versions()
    print(
        f"google-adk {versions['google-adk']}; mcp {versions['mcp']}; "
        f"python {versions['python']}"
    )
    config = offline_configuration_check()
    launch = mcp_server_launch_spec()
    print(f"MCP server launch: {launch['command']} {launch['args']} cwd={launch['cwd']}")

    print("\nRunning real stdio MCP protocol checks (no model calls)...")
    protocol = await run_protocol_checks()
    print(
        "protocol: "
        f"init={protocol['initialize'].get('ok')} "
        f"tools={protocol['list_tools'].get('names')} "
        f"parity={protocol['parity'].get('ok')} "
        f"cleanup={protocol['cleanup'].get('ok')}"
    )

    unittest_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "test_mcp_preview"],
        cwd=str(THIS_DIR),
        capture_output=True,
        text=True,
    )
    print(unittest_proc.stderr or unittest_proc.stdout)

    live = await run_live_assessment()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": versions,
        "launch": launch,
        "timeouts": {
            "connection_seconds": MCP_CONNECTION_TIMEOUT_SECONDS,
            "call_seconds": MCP_CALL_TIMEOUT_SECONDS,
            "max_llm_calls": MAX_LLM_CALLS,
            "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
        },
        "offline_configuration": config,
        "protocol": protocol,
        "unittest": {
            "returncode": unittest_proc.returncode,
            "passed": unittest_proc.returncode == 0,
            "stderr_tail": (unittest_proc.stderr or "")[-1500:],
        },
        "live_run": live,
        "limits": (
            "One MCP-backed live run is not a general MCP security or reliability proof."
        ),
    }
    write_reports(report)
    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Protocol cleanup ok: {protocol.get('cleanup', {}).get('ok')}")
    print(f"Live execution: {live.get('execution')}")
    print(f"Live leftover PIDs: {live.get('cleanup', {}).get('leftover_child_pids')}")


if __name__ == "__main__":
    asyncio.run(main())
