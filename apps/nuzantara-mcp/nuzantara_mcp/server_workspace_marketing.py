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
        "public-intended editorial material. News Room flow: when Damar asks "
        "what is available, call newsroom_list_pending and show the titles. "
        "When Damar names an article to publish, that order is the decision: "
        "find its item_id by title, generate a cover with native ImageGen and "
        "attach it with newsroom_attach_cover if none is attached, then call "
        "newsroom_publish with confirmation CONFIRM. Do not ask Damar for SEO "
        "fields, do not edit the article, and do not run the fact gate unless "
        "he asks for a fact check: newsroom_update_article and "
        "newsroom_fact_gate are optional tools, never preconditions. "
        "Confirmed Flow image and video generation remain available "
        "for governed Flow/WR3 assets; neither authorizes social publication. "
        "Final publishing to Instagram, X, Facebook, email, or any other "
        "client-facing channel is always manual. CRM, client records, documents, "
        "raw OSINT, admin operations, arbitrary file "
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
