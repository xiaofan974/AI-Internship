"""One bounded two-agent ADK demo: MCP classifier plus evidence critic.

Offline checks run first. Then exactly one live recruitment example is
invoked, with no retries. The Streamlit app, single-agent paths, and
human-approval register are not used.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from contextlib import aclosing
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
REPORT_JSON = THIS_DIR / "reports" / "dual_preview_eval.json"
REPORT_MD = THIS_DIR / "reports" / "dual_preview_eval.md"


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

from aeacus_agent.agent import MODEL
from aeacus_agent.dual_preview import (
    CLASSIFIER_NAME,
    CRITIC_NAME,
    PIPELINE_NAME,
    apply_deterministic_checks,
    create_dual_preview_pipeline,
    parse_critic_verdict,
)
from aeacus_agent.mcp_preview_agent import ALLOWED_MCP_TOOLS
from aeacus_agent.preview_agent import aeacus_preview_agent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.runners import RunConfig, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import errors as genai_errors
from google.genai import types
from run_classification_preview import SAMPLE_PREVIEW_PROMPT
from run_review import (
    APP_NAME,
    DEFAULT_USER_ID,
    MAX_LLM_CALLS,
    RUN_TIMEOUT_SECONDS,
    _format_payload,
    _redact_sensitive,
)
from test_mcp_preview import _child_pids, _pid_alive


def installed_versions() -> dict:
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "google-adk": version("google-adk"),
        "mcp": version("mcp"),
        "google-genai": version("google-genai"),
        "model": MODEL,
    }


def compact_bundle(bundle: dict | None) -> dict:
    bundle = bundle or {}
    records = bundle.get("records") or []
    return {
        "handoff_ok": bundle.get("handoff_ok"),
        "handoff_error": bundle.get("handoff_error"),
        "system_description": bundle.get("system_description"),
        "classifier_draft": bundle.get("classifier_draft"),
        "evidence_record_ids": [item.get("record_id") for item in records],
        "evidence_labels": [item.get("label") for item in records if item.get("label")],
        "evidence_hashes": [
            {
                "record_id": item.get("record_id"),
                "text_sha256": item.get("text_sha256"),
            }
            for item in records
        ],
        "tool_calls": [
            {
                "id": item.get("id"),
                "tool": item.get("tool"),
                "query": item.get("query"),
            }
            for item in (bundle.get("tool_calls") or [])
        ],
        "observation_statuses": [
            {
                "call_id": item.get("call_id"),
                "tool": item.get("tool"),
                "query": item.get("query"),
                "status": item.get("status"),
            }
            for item in (bundle.get("observations") or [])
        ],
    }


def write_reports(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    live = report.get("live_run") or {}
    verdict = live.get("critic_verdict") or {}
    checks = live.get("deterministic_checks") or {}
    handoff = live.get("handoff") or {}
    offline = report.get("offline") or {}
    lines = [
        "# Two-agent SequentialAgent preview checkpoint",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This is a separate CLI demo. The Streamlit app, direct Python preview",
        "tool, single-agent MCP path, and human approval register are unchanged.",
        "The critic verdict is automated evidence critique, not legal certification.",
        "",
        "## Installed versions",
        "",
        f"- Python: `{report['versions']['python']}` (`{report['versions']['executable']}`)",
        f"- google-adk: `{report['versions']['google-adk']}`",
        f"- mcp: `{report['versions']['mcp']}`",
        f"- google-genai: `{report['versions']['google-genai']}`",
        f"- Model: `{report['versions']['model']}`",
        "",
        "## Offline checks (mocked / no live model)",
        "",
        f"- Unittest: **{'PASS' if offline.get('passed') else 'FAIL'}**",
        f"- Orchestration: SequentialAgent `{PIPELINE_NAME}` with `{CLASSIFIER_NAME}` then `{CRITIC_NAME}`",
        f"- Classifier tools: `{list(ALLOWED_MCP_TOOLS)}` through MCP",
        "- Critic tools: none",
        "- Fabricated citations and altered statutory quotations fail deterministic checks",
        "",
        "## Live two-agent run",
        "",
        f"- Execution: **{live.get('execution')}**",
        f"- Invocations used: {live.get('invocations_used')}",
        f"- Register opened: {live.get('register_opened')}",
        f"- Handoff ok: {handoff.get('handoff_ok')}",
        f"- Handoff error: {handoff.get('handoff_error')}",
        "",
        "### Two-agent trace",
        "",
    ]
    calls = live.get("tool_log") or []
    if calls:
        for index, call in enumerate(calls, start=1):
            lines.append(
                f"{index}. `{call.get('author')}` -> `{call.get('tool')}` "
                f"query={call.get('query')!r}"
            )
    else:
        lines.append("No MCP tool calls were recorded.")
    lines.extend(
        [
            "",
            f"- Observation statuses: `{json.dumps(handoff.get('observation_statuses') or [])}`",
            "",
            "### Classifier draft",
        "",
        "```",
        str(live.get("classifier_draft") or ""),
        "```",
        "",
        "### Critic verdict (model)",
        "",
        f"- Verdict: `{verdict.get('verdict')}`",
        f"- Parse ok: {verdict.get('parse_ok')}",
        "",
        "```",
        json.dumps(verdict.get("findings") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        f"Scope note: {verdict.get('scope_note') or ''}",
        "",
        "### Deterministic checks (application-owned, separate from the model)",
        "",
        "```",
        json.dumps(checks, indent=2, ensure_ascii=False),
        "```",
        "",
        "### Evidence IDs captured from this run's MCP observations",
        "",
        "```",
        json.dumps(handoff.get("evidence_record_ids") or [], indent=2),
        "```",
        "",
        "### Cleanup",
        "",
        "```",
        json.dumps(live.get("cleanup") or {}, indent=2),
        "```",
        "",
        "## Limits",
        "",
        "One SequentialAgent live run is not independent legal certification,",
        "approval, or readiness for registration. `supported` means only that the",
        "draft was supported within the supplied evidence and limited subset.",
        "",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _visible_event_text(event) -> str:
    content = getattr(event, "content", None)
    parts = getattr(content, "parts", None) or []
    texts = [
        str(part.text)
        for part in parts
        if getattr(part, "text", None) and not getattr(part, "thought", False)
    ]
    return "\n".join(texts).strip()


async def _run_pipeline(pipeline, book, system_description: str, tool_log: list) -> dict:
    """Run the SequentialAgent once with the shared 8-call / 90-second budget."""
    service = InMemorySessionService()
    run_config = RunConfig(max_llm_calls=MAX_LLM_CALLS)
    content = types.Content(role="user", parts=[types.Part(text=system_description)])
    finals: dict[str, str] = {}
    try:
        async with asyncio.timeout(RUN_TIMEOUT_SECONDS):
            async with Runner(
                agent=pipeline,
                app_name=APP_NAME,
                session_service=service,
            ) as runner:
                session = await service.create_session(
                    app_name=APP_NAME,
                    user_id=DEFAULT_USER_ID,
                )
                async with aclosing(
                    runner.run_async(
                        user_id=DEFAULT_USER_ID,
                        session_id=session.id,
                        new_message=content,
                        run_config=run_config,
                    )
                ) as event_stream:
                    async for event in event_stream:
                        author = getattr(event, "author", None) or "unknown"
                        if getattr(event, "error_code", None) or getattr(
                            event, "error_message", None
                        ):
                            raise RuntimeError(
                                f"Event error ({event.error_code}): {event.error_message}"
                            )
                        for fc in event.get_function_calls() or []:
                            tool_name = fc.name or "unknown_tool"
                            args = dict(fc.args) if fc.args else {}
                            tool_log.append(
                                {
                                    "type": "call",
                                    "author": author,
                                    "tool": tool_name,
                                    "args": args,
                                    "id": getattr(fc, "id", None),
                                }
                            )
                            print(
                                f"[THINK] {author} selected next action: "
                                f"call tool {tool_name}"
                            )
                            print(
                                f"[ACT] {author} -> {tool_name}("
                                f"{_format_payload(args)})"
                            )
                        for fr in event.get_function_responses() or []:
                            tool_name = fr.name or "unknown_tool"
                            payload = fr.response if fr.response is not None else {}
                            tool_log.append(
                                {
                                    "type": "response",
                                    "author": author,
                                    "tool": tool_name,
                                    "payload": payload,
                                    "id": getattr(fr, "id", None),
                                }
                            )
                            print(
                                f"[OBSERVE] {author} <- {tool_name}: "
                                f"{_format_payload(payload)}"
                            )
                        visible = _visible_event_text(event)
                        if event.is_final_response() and visible:
                            finals[author] = visible
                            print(f"[FINAL] {author}: {_format_payload(visible)}")
        if CLASSIFIER_NAME not in finals and CRITIC_NAME not in finals:
            failure = "[FAILED] Run completed without a valid final response."
            print(failure)
            return {"execution": "failed", "error": failure, "finals": finals}
        return {"execution": "ok", "error": None, "finals": finals}
    except TimeoutError:
        failure = (
            f"[FAILED] Run timed out after {RUN_TIMEOUT_SECONDS} seconds "
            "(partial output discarded)."
        )
        print(failure)
        return {"execution": "failed", "error": failure, "finals": finals}
    except LlmCallsLimitExceededError as exc:
        failure = (
            f"[FAILED] Call-limit exhaustion (max_llm_calls={MAX_LLM_CALLS}): "
            f"{_redact_sensitive(str(exc))}"
        )
        print(failure)
        return {"execution": "failed", "error": failure, "finals": finals}
    except (genai_errors.APIError, Exception) as exc:
        failure = (
            f"[FAILED] Provider/execution failure ({type(exc).__name__}): "
            f"{_redact_sensitive(str(exc))}"
        )
        print(failure)
        return {"execution": "failed", "error": failure, "finals": finals}


async def run_live_dual_preview() -> dict:
    if not _google_api_key_is_configured():
        return {
            "execution": "skipped",
            "invocations_used": 0,
            "classifier_draft": "",
            "critic_verdict": {},
            "deterministic_checks": {},
            "handoff": {},
            "register_opened": False,
            "cleanup": {"ok": True, "note": "No MCP agent process was started."},
        }

    parent = os.getpid()
    before = _child_pids(parent)
    pipeline, toolset, book = create_dual_preview_pipeline()
    tool_log: list = []
    cleanup_error = None
    result = {"execution": "failed", "error": None, "finals": {}}

    try:
        print("\n--- AEACUSAI TWO-AGENT CLASSIFICATION PREVIEW ---")
        print(f"Pipeline: {pipeline.name}")
        print(f"Agents: {[agent.name for agent in pipeline.sub_agents]}")
        print(f"Submitted System: {SAMPLE_PREVIEW_PROMPT}\n")
        result = await _run_pipeline(
            pipeline, book, SAMPLE_PREVIEW_PROMPT, tool_log
        )
    except Exception as exc:
        result = {
            "execution": "failed",
            "error": (
                f"[FAILED] Provider/execution failure ({type(exc).__name__}): {exc}"
            ),
            "finals": {},
        }
        print(result["error"])
    finally:
        try:
            await toolset.close()
        except Exception as exc:
            cleanup_error = f"{type(exc).__name__}: {exc}"
            print(f"toolset.close() warning: {cleanup_error}", file=sys.stderr)

    leftover = sorted(
        pid for pid in (_child_pids(parent) - before) if _pid_alive(pid)
    )
    bundle = book.bundle or {}
    finals = result.get("finals") or {}
    draft = bundle.get("classifier_draft") or finals.get(CLASSIFIER_NAME) or ""
    critic_text = finals.get(CRITIC_NAME) or result.get("error") or ""
    verdict = parse_critic_verdict(critic_text)
    execution = result.get("execution") or "failed"
    checks = apply_deterministic_checks(bundle)
    print("\n[CRITIC VERDICT]")
    print(json.dumps(verdict, indent=2, ensure_ascii=False, default=str))
    print("\n[DETERMINISTIC CHECKS]")
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    print("\n[ORIGINAL DRAFT PRESERVED]")
    print(draft)
    return {
        "execution": execution,
        "invocations_used": 1,
        "pipeline": pipeline.name,
        "agents": [agent.name for agent in pipeline.sub_agents],
        "classifier_draft": draft,
        "critic_raw": critic_text,
        "critic_verdict": verdict,
        "deterministic_checks": checks,
        "handoff": compact_bundle(bundle),
        "tool_log": [
            {
                "type": event.get("type"),
                "author": event.get("author"),
                "tool": event.get("tool"),
                "query": (event.get("args") or {}).get("query"),
            }
            for event in tool_log
            if event.get("type") == "call"
        ],
        "register_opened": False,
        "cleanup": {
            "ok": not leftover and cleanup_error is None,
            "leftover_child_pids": leftover,
            "close_error": cleanup_error,
        },
    }


async def main() -> None:
    versions = installed_versions()
    print(
        f"google-adk {versions['google-adk']}; mcp {versions['mcp']}; "
        f"python {versions['python']}"
    )
    print(
        f"offline configuration: Streamlit default remains {aeacus_preview_agent.name}; "
        f"two-agent pipeline is {PIPELINE_NAME}"
    )

    print("\nRunning offline two-agent checks (no live model)...")
    unittest_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "test_dual_preview"],
        cwd=str(THIS_DIR),
        capture_output=True,
        text=True,
    )
    print(unittest_proc.stderr or unittest_proc.stdout)
    if unittest_proc.returncode != 0:
        print(unittest_proc.stdout)
        print(unittest_proc.stderr)

    live = await run_live_dual_preview()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": versions,
        "timeouts": {
            "max_llm_calls": MAX_LLM_CALLS,
            "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
        },
        "offline": {
            "kind": "mocked_or_local_only",
            "passed": unittest_proc.returncode == 0,
            "returncode": unittest_proc.returncode,
            "stderr_tail": (unittest_proc.stderr or "")[-1500:],
        },
        "live_run": live,
        "limits": (
            "One SequentialAgent live run is automated evidence critique, "
            "not legal certification, approval, or readiness for registration."
        ),
    }
    write_reports(report)
    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Offline unittest passed: {report['offline']['passed']}")
    print(f"Live execution: {live.get('execution')}")
    print(f"Handoff ok: {(live.get('handoff') or {}).get('handoff_ok')}")
    print(f"Critic verdict: {(live.get('critic_verdict') or {}).get('verdict')}")
    print(f"Deterministic checks ok: {(live.get('deterministic_checks') or {}).get('ok')}")
    print(f"Cleanup ok: {(live.get('cleanup') or {}).get('ok')}")


if __name__ == "__main__":
    asyncio.run(main())
