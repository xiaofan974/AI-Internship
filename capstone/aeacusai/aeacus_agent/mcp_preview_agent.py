"""Separate ADK preview agent that reaches classification search through MCP.

Does not replace `aeacus_preview_agent`. Process creation happens only when
`create_mcp_toolset()` / `create_mcp_preview_agent()` is called, not at import.
"""

from __future__ import annotations

import sys
from pathlib import Path

from google.adk.agents import Agent
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

from .agent import MODEL
from .preview_agent import AEACUS_PREVIEW_INSTRUCTION

ALLOWED_MCP_TOOLS = ("preview_classification_search",)
MCP_CONNECTION_TIMEOUT_SECONDS = 15.0
MCP_CALL_TIMEOUT_SECONDS = 30.0

PROJECT_DIR = Path(__file__).resolve().parent.parent


def mcp_server_launch_spec() -> dict[str, str | list[str]]:
    """Application-controlled stdio launch: capstone interpreter, module, cwd."""
    return {
        "command": sys.executable,
        "args": ["-m", "aeacus_agent.mcp_server"],
        "cwd": str(PROJECT_DIR),
    }


def stdio_server_parameters() -> StdioServerParameters:
    spec = mcp_server_launch_spec()
    return StdioServerParameters(
        command=str(spec["command"]),
        args=list(spec["args"]),
        cwd=str(spec["cwd"]),
    )


def create_mcp_toolset() -> McpToolset:
    """Spawn the local MCP server on first use. Callers must close the toolset."""
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=stdio_server_parameters(),
            timeout=MCP_CALL_TIMEOUT_SECONDS,
        ),
        tool_filter=list(ALLOWED_MCP_TOOLS),
        errlog=sys.stderr,
    )


def create_mcp_preview_agent(
    *,
    toolset: McpToolset | None = None,
) -> tuple[Agent, McpToolset]:
    """Build the MCP-only preview agent. Does not attach the direct Python tool."""
    owned_toolset = toolset or create_mcp_toolset()
    agent = Agent(
        name="aeacus_mcp_preview_agent",
        model=MODEL,
        description=(
            "Performs a provisional EU AI Act classification assessment against the "
            "local Article 6 and Annex III subset using MCP-backed "
            "preview_classification_search."
        ),
        instruction=AEACUS_PREVIEW_INSTRUCTION,
        tools=[owned_toolset],
    )
    return agent, owned_toolset
