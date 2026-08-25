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
        "public-intended editorial material. News Room approval remains a "
        "manual action in kita.balizero.com. WR2 and Flow actions "
        "create internal drafts/assets only. Final publishing to Instagram, X, "
        "Facebook, email, or any client-facing channel is always manual. CRM, "
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
