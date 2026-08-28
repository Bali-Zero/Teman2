"""Cloud-safe MCP server for the Bali Zero ChatGPT Business marketing team.

This server is a fresh, fail-closed FastMCP instance.  It never registers the
full Nuzantara surface.  The only reachable capabilities are the explicit
marketing tools in ``tools.workspace_marketing``.
"""

from __future__ import annotations

from fastmcp import FastMCP

from nuzantara_mcp.tools.workspace_marketing import register
from nuzantara_mcp.workspace_backend import call

mcp = FastMCP(
    name="Nuzantara Marketing Workspace",
    mask_error_details=True,
    instructions=(
        "Private Bali Zero marketing bridge for ChatGPT Business. Respond in "
        "Italian to Zero and in Bahasa Indonesia to Damar/team. Use only "
        "public-intended editorial material. News Room publication is allowed "
        "only after Damar explicitly requests it, the article is complete, and "
        "a pre-generated cover is attached. Static images use native ImageGen; "
        "Flow is video-only. Final publishing to Instagram, X, Facebook, email, "
        "or any other client-facing channel is always manual. CRM, "
        "client records, documents, raw OSINT, admin operations, arbitrary file "
        "paths, and secrets are not exposed by this server. Never enter client "
        "names, identifiers, credentials, or private case details."
    ),
)

register(mcp, call)


def main() -> None:
    """Run the workspace marketing server over stdio."""

    mcp.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()
