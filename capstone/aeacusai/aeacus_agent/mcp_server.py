"""Local stdio MCP server for the classification preview search tool.

Exposes exactly one read-only tool that delegates to
`preview_classification_search`. Protocol frames go to stdout; diagnostics
go to stderr. The server starts only from `main()`.
"""

from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from aeacus_agent.context_preview import (
    preview_classification_search as search_classification_preview,
)

TOOL_NAME = "preview_classification_search"
SERVER_NAME = "aeacus-classification-preview"


def build_server() -> FastMCP:
    """Register the single search tool. Does not open stdio or spawn processes."""
    server = FastMCP(
        SERVER_NAME,
        instructions=(
            "Read-only local lexical search over the pinned Article 6, Annex III, "
            "and Article 113 classification subset. No write, approval, database, "
            "or filesystem tools are available."
        ),
        log_level="INFO",
    )

    @server.tool(
        name=TOOL_NAME,
        description=(
            "Search the pinned local Article 6 and Annex III classification subset. "
            "Choose a query yourself. Returns complete match and context records "
            "with hashes and snapshot identifiers. Read-only; does not write or approve."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
        ),
        structured_output=False,
    )
    def preview_classification_search(query: str) -> dict:
        return search_classification_preview(query)

    return server


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="aeacus-mcp-server %(levelname)s: %(message)s",
    )
    print(
        "Starting AeacusAI classification preview MCP server on stdio.",
        file=sys.stderr,
        flush=True,
    )
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
