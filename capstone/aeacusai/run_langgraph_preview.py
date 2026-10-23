"""One bounded LangGraph mirror of the single-agent classification preview.

Offline mocked checks run first. Then exactly one live recruitment example
is invoked, with no retries. Streamlit, ADK, MCP, and the review register
are not used.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import load_dotenv

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parents[1]
GOOGLE_API_KEY_PLACEHOLDER = "your_google_api_key_here"
REPORT_JSON = THIS_DIR / "reports" / "langgraph_preview_eval.json"
REPORT_MD = THIS_DIR / "reports" / "langgraph_preview_eval.md"
ADK_EXAMPLE = THIS_DIR / "reports" / "dual_preview_eval.json"


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
from aeacus_agent.langgraph_preview import (
    ALLOWED_TOOL,
    GRAPH_RECURSION_LIMIT,
    MAX_LLM_CALLS,
    RUN_TIMEOUT_SECONDS,
    run_langgraph_preview,
)
from aeacus_agent.preview_agent import aeacus_preview_agent
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
        "langchain-core": _pkg("langchain-core"),
        "google-adk": _pkg("google-adk"),
        "google-genai": _pkg("google-genai"),
        "model": MODEL,
    }


def compare_with_adk_example(live: dict) -> dict:
    """Compare scope, provenance, and citation validity. Wording may differ."""
    if not ADK_EXAMPLE.exists():
        return {"available": False, "note": "No saved ADK example report was found."}
    adk = json.loads(ADK_EXAMPLE.read_text(encoding="utf-8"))
    adk_live = adk.get("live_run") or {}
    adk_draft = adk_live.get("classifier_draft") or adk_live.get("final_answer") or ""
    adk_ids = (adk_live.get("handoff") or {}).get("evidence_record_ids") or adk_live.get(
        "observed_record_ids"
    ) or []
    lg_draft = live.get("draft") or ""
    lg_ids = [item.get("record_id") for item in (live.get("records") or [])]
    scope_markers = ("Article 6", "Annex III", "Article 113")
    forbidden = ("fully compliant", "ready for registration", "legal sign-off")
    return {
        "available": True,
        "adk_source": str(ADK_EXAMPLE.name),
        "wording_required_identical": False,
        "scope": {
            "langgraph_mentions_subset": all(marker in lg_draft for marker in scope_markers),
            "adk_mentions_subset": all(marker in adk_draft for marker in scope_markers),
            "langgraph_avoids_full_compliance": not any(
                phrase in lg_draft.lower() for phrase in forbidden
            ),
            "adk_avoids_full_compliance": not any(
                phrase in adk_draft.lower() for phrase in forbidden
            ),
        },
        "evidence_provenance": {
            "langgraph_ids": lg_ids,
            "adk_ids": adk_ids,
            "langgraph_has_hashes": all(
                item.get("text_sha256") for item in (live.get("records") or [])
            ),
            "shared_ids": [item for item in lg_ids if item in adk_ids],
        },
        "citation_validity": {
            "langgraph_checks_ok": (live.get("deterministic_checks") or {}).get("ok"),
            "adk_checks_ok": (adk_live.get("deterministic_checks") or {}).get("ok"),
        },
    }


def compact_live(result: dict) -> dict:
    return {
        "execution": "ok" if result.get("status") == "review_required" else result.get("status"),
        "status": result.get("status"),
        "error": result.get("error"),
        "model_calls": result.get("model_calls"),
        "draft": result.get("draft") or "",
        "deterministic_checks": result.get("deterministic_checks") or {},
        "observations": [
            {
                "call_id": item.get("call_id"),
                "tool": item.get("tool"),
                "query": item.get("query"),
                "status": (item.get("payload") or {}).get("status"),
                "match_record_ids": (item.get("payload") or {}).get("match_record_ids") or [],
                "context_record_ids": (item.get("payload") or {}).get("context_record_ids")
                or [],
            }
            for item in (result.get("observations") or [])
        ],
        "records": [
            {
                "record_id": item.get("record_id"),
                "label": item.get("label"),
                "text_sha256": item.get("text_sha256"),
                "source_snapshot_id": item.get("source_snapshot_id"),
                "role": item.get("role"),
            }
            for item in (result.get("records") or [])
        ],
        "trace": result.get("trace") or [],
        "register_opened": False,
        "register_written": False,
    }


def write_reports(report: dict) -> None:
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    live = report.get("live_run") or {}
    offline = report.get("offline") or {}
    comparison = report.get("comparison") or {}
    lines = [
        "# LangGraph classification-preview mirror",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This is a separate CLI mirror of `aeacus_preview_agent`. Streamlit, ADK",
        "paths, MCP, the corpus, and the human approval register are unchanged.",
        "",
        "## Installed versions",
        "",
        f"- Python: `{report['versions']['python']}` (`{report['versions']['executable']}`)",
        f"- langgraph: `{report['versions']['langgraph']}`",
        f"- langchain-core: `{report['versions']['langchain-core']}`",
        f"- google-adk: `{report['versions']['google-adk']}`",
        f"- google-genai: `{report['versions']['google-genai']}`",
        f"- Model: `{report['versions']['model']}`",
        "",
        "## Offline checks (mocked / no live model)",
        "",
        f"- Unittest: **{'PASS' if offline.get('passed') else 'FAIL'}**",
        f"- Default ADK preview agent unchanged: `{aeacus_preview_agent.name}`",
        f"- Allowlisted tool: `{ALLOWED_TOOL}`",
        f"- Limits: {MAX_LLM_CALLS} model calls, {RUN_TIMEOUT_SECONDS}s, recursion {GRAPH_RECURSION_LIMIT}",
        "",
        "## Live LangGraph run",
        "",
        f"- Execution: **{live.get('execution')}**",
        f"- Status: `{live.get('status')}`",
        f"- Model calls: {live.get('model_calls')}",
        f"- Register opened: {live.get('register_opened')}",
        f"- Register written: {live.get('register_written')}",
        "",
        "### Graph trace",
        "",
        "```",
        json.dumps(live.get("trace") or [], indent=2, ensure_ascii=False),
        "```",
        "",
        "### Observations",
        "",
        "```",
        json.dumps(live.get("observations") or [], indent=2, ensure_ascii=False),
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
        "### Comparison with saved ADK example",
        "",
        "Wording and search results are not required to match.",
        "",
        "```",
        json.dumps(comparison, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Limits",
        "",
        "One LangGraph live run is a framework mirror, not legal certification",
        "or approval. Successful drafts remain `review_required`.",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_live() -> dict:
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
    print("\n--- AEACUSAI LANGGRAPH CLASSIFICATION PREVIEW ---")
    print(f"Submitted System: {SAMPLE_PREVIEW_PROMPT}\n")
    result = run_langgraph_preview(SAMPLE_PREVIEW_PROMPT)
    compact = compact_live(result)
    print(f"\nStatus: {compact.get('status')}")
    print(f"Model calls: {compact.get('model_calls')}")
    if compact.get("error"):
        print(f"Error: {compact.get('error')}")
    print(f"\nPreview Output:\n{compact.get('draft')}\n")
    return compact


def main() -> None:
    versions = installed_versions()
    print(
        f"langgraph {versions['langgraph']}; google-genai {versions['google-genai']}; "
        f"google-adk {versions['google-adk']}; python {versions['python']}"
    )
    print(f"offline configuration: Streamlit/ADK default remains {aeacus_preview_agent.name}")

    print("\nRunning offline LangGraph checks (no live model)...")
    unittest_proc = subprocess.run(
        [sys.executable, "-m", "unittest", "test_langgraph_preview"],
        cwd=str(THIS_DIR),
        capture_output=True,
        text=True,
    )
    print(unittest_proc.stderr or unittest_proc.stdout)
    if unittest_proc.returncode != 0:
        print(unittest_proc.stdout)
        print(unittest_proc.stderr)

    live = run_live()
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "versions": versions,
        "timeouts": {
            "max_llm_calls": MAX_LLM_CALLS,
            "run_timeout_seconds": RUN_TIMEOUT_SECONDS,
            "graph_recursion_limit": GRAPH_RECURSION_LIMIT,
        },
        "offline": {
            "kind": "mocked_or_local_only",
            "passed": unittest_proc.returncode == 0,
            "returncode": unittest_proc.returncode,
            "stderr_tail": (unittest_proc.stderr or "")[-1500:],
        },
        "live_run": live,
        "comparison": compare_with_adk_example(live),
        "limits": (
            "One LangGraph live run is a framework mirror, not legal certification "
            "or approval. Successful drafts remain review_required."
        ),
    }
    write_reports(report)
    print(f"\nWrote {REPORT_JSON}")
    print(f"Wrote {REPORT_MD}")
    print(f"Offline unittest passed: {report['offline']['passed']}")
    print(f"Live execution: {live.get('execution')}")
    print(f"Live status: {live.get('status')}")
    print(f"Deterministic checks ok: {(live.get('deterministic_checks') or {}).get('ok')}")


if __name__ == "__main__":
    main()
