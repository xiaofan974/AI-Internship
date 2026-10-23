"""Real stdio MCP integration checks for the classification search tool.

Spawns a local MCP server subprocess and uses the protocol. These tests
do not call Gemini, OpenAI, or Pinecone.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import unittest
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client

from aeacus_agent.context_preview import preview_classification_search
from aeacus_agent.mcp_preview_agent import (
    ALLOWED_MCP_TOOLS,
    MCP_CALL_TIMEOUT_SECONDS,
    MCP_CONNECTION_TIMEOUT_SECONDS,
    stdio_server_parameters,
)
from aeacus_agent.mcp_server import TOOL_NAME
from aeacus_agent.preview_agent import aeacus_preview_agent

RECRUITMENT_QUERY = "recruitment job applications filter candidates workers"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _child_pids(parent: int) -> set[int]:
    try:
        output = subprocess.check_output(
            ["pgrep", "-P", str(parent)],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return set()
    return {int(line) for line in output.split() if line.strip().isdigit()}


def decode_mcp_tool_result(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        if "status" in structured:
            return structured
        nested = structured.get("result")
        if isinstance(nested, dict) and "status" in nested:
            return nested
        return structured
    texts: list[str] = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        if text:
            texts.append(str(text))
    raw = "\n".join(texts).strip()
    if not raw:
        raise AssertionError("MCP tool result contained no text or structured content.")
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        nested = parsed.get("result")
        if isinstance(nested, dict) and "status" in nested and "status" not in parsed:
            return nested
        return parsed
    raise AssertionError(f"MCP tool result was not an object: {type(parsed)!r}")


def _parity_view(payload: dict[str, Any]) -> dict[str, Any]:
    matches = payload.get("matches") or []
    context = payload.get("context_records") or []
    return {
        "status": payload.get("status"),
        "query": payload.get("query"),
        "match_record_ids": [item.get("record_id") for item in matches],
        "context_record_ids": [item.get("record_id") for item in context],
        "match_texts": [item.get("text") for item in matches],
        "context_texts": [item.get("text") for item in context],
        "match_hashes": [item.get("text_sha256") for item in matches],
        "context_hashes": [item.get("text_sha256") for item in context],
        "match_snapshots": [item.get("source_snapshot_id") for item in matches],
        "context_snapshots": [item.get("source_snapshot_id") for item in context],
        "retrieval_mode": payload.get("retrieval_mode"),
        "corpus_scope": payload.get("corpus_scope"),
        "ingestion_permitted": payload.get("ingestion_permitted"),
        "error": payload.get("error"),
        "scope_and_review_notice": payload.get("scope_and_review_notice"),
    }


async def run_protocol_checks() -> dict[str, Any]:
    """Initialize, list tools, call the search tool, and verify cleanup."""
    report: dict[str, Any] = {
        "launch": {
            "command": stdio_server_parameters().command,
            "args": stdio_server_parameters().args,
            "cwd": stdio_server_parameters().cwd,
        },
        "initialize": {},
        "list_tools": {},
        "recruitment_call": {},
        "empty_query": {},
        "parity": {},
        "cleanup": {},
    }
    parent = os.getpid()
    before = _child_pids(parent)
    spawned: list[int] = []
    leftover: list[int] = []
    try:
        async with stdio_client(stdio_server_parameters()) as (read, write):
            spawned = sorted(_child_pids(parent) - before)
            session = ClientSession(
                read,
                write,
                read_timeout_seconds=timedelta(seconds=MCP_CALL_TIMEOUT_SECONDS),
            )
            async with session:
                init = await asyncio.wait_for(
                    session.initialize(),
                    timeout=MCP_CONNECTION_TIMEOUT_SECONDS,
                )
                report["initialize"] = {
                    "ok": True,
                    "protocolVersion": getattr(init, "protocolVersion", None),
                    "server": (
                        init.serverInfo.model_dump()
                        if getattr(init, "serverInfo", None)
                        else None
                    ),
                    "spawned_pids": spawned,
                }
                listed = await asyncio.wait_for(
                    session.list_tools(),
                    timeout=MCP_CALL_TIMEOUT_SECONDS,
                )
                names = [tool.name for tool in listed.tools]
                report["list_tools"] = {
                    "ok": names == list(ALLOWED_MCP_TOOLS),
                    "names": names,
                    "count": len(names),
                }
                recruitment = await asyncio.wait_for(
                    session.call_tool(
                        TOOL_NAME,
                        {"query": RECRUITMENT_QUERY},
                        read_timeout_seconds=timedelta(
                            seconds=MCP_CALL_TIMEOUT_SECONDS
                        ),
                    ),
                    timeout=MCP_CALL_TIMEOUT_SECONDS,
                )
                mcp_recruitment = decode_mcp_tool_result(recruitment)
                direct_recruitment = preview_classification_search(RECRUITMENT_QUERY)
                recruitment_parity = _parity_view(mcp_recruitment) == _parity_view(
                    direct_recruitment
                )
                report["recruitment_call"] = {
                    "ok": recruitment_parity
                    and mcp_recruitment.get("status") == "ok",
                    "query": RECRUITMENT_QUERY,
                    "isError": bool(getattr(recruitment, "isError", False)),
                    "mcp_status": mcp_recruitment.get("status"),
                    "mcp_match_ids": mcp_recruitment.get("match_record_ids")
                    or [item.get("record_id") for item in mcp_recruitment.get("matches") or []],
                    "mcp_context_ids": mcp_recruitment.get("context_record_ids")
                    or [
                        item.get("record_id")
                        for item in mcp_recruitment.get("context_records") or []
                    ],
                    "direct_match_ids": [
                        item["record_id"] for item in direct_recruitment.get("matches") or []
                    ],
                    "direct_context_ids": [
                        item["record_id"]
                        for item in direct_recruitment.get("context_records") or []
                    ],
                    "parity": recruitment_parity,
                }
                empty = await asyncio.wait_for(
                    session.call_tool(
                        TOOL_NAME,
                        {"query": ""},
                        read_timeout_seconds=timedelta(
                            seconds=MCP_CALL_TIMEOUT_SECONDS
                        ),
                    ),
                    timeout=MCP_CALL_TIMEOUT_SECONDS,
                )
                mcp_empty = decode_mcp_tool_result(empty)
                direct_empty = preview_classification_search("")
                empty_parity = _parity_view(mcp_empty) == _parity_view(direct_empty)
                report["empty_query"] = {
                    "ok": empty_parity and mcp_empty.get("status") == "error",
                    "mcp_status": mcp_empty.get("status"),
                    "mcp_error": mcp_empty.get("error"),
                    "direct_status": direct_empty.get("status"),
                    "direct_error": direct_empty.get("error"),
                    "parity": empty_parity,
                }
                report["parity"] = {
                    "recruitment": recruitment_parity,
                    "empty_query": empty_parity,
                    "ok": recruitment_parity and empty_parity,
                }
        leftover = [pid for pid in spawned if _pid_alive(pid)]
        report["cleanup"] = {
            "ok": not leftover,
            "spawned_pids": spawned,
            "leftover_pids": leftover,
        }
    except Exception as exc:
        leftover = [pid for pid in spawned if _pid_alive(pid)]
        report["cleanup"] = {
            "ok": not leftover,
            "spawned_pids": spawned,
            "leftover_pids": leftover,
            "error": f"{type(exc).__name__}: {exc}",
        }
        report["initialize"]["ok"] = report["initialize"].get("ok", False)
        raise
    return report


class McpPreviewIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_protocol_matches_direct_search_and_cleans_up(
        self,
    ) -> None:
        self.assertEqual(
            [getattr(tool, "__name__", "") for tool in aeacus_preview_agent.tools],
            ["preview_classification_search"],
        )
        report = await run_protocol_checks()
        self.assertTrue(report["initialize"]["ok"], report)
        self.assertEqual(report["list_tools"]["names"], ["preview_classification_search"])
        self.assertTrue(report["list_tools"]["ok"], report["list_tools"])
        self.assertTrue(report["recruitment_call"]["ok"], report["recruitment_call"])
        self.assertTrue(report["empty_query"]["ok"], report["empty_query"])
        self.assertTrue(report["parity"]["ok"], report["parity"])
        self.assertTrue(report["cleanup"]["ok"], report["cleanup"])
        self.assertTrue(report["recruitment_call"]["mcp_match_ids"])
        self.assertEqual(
            report["recruitment_call"]["mcp_match_ids"],
            report["recruitment_call"]["direct_match_ids"],
        )
        self.assertEqual(
            report["recruitment_call"]["mcp_context_ids"],
            report["recruitment_call"]["direct_context_ids"],
        )


if __name__ == "__main__":
    unittest.main()
