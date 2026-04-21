"""Canva Renderer — WR2 stage that converts Council+Visual output into an
editable Canva design via MCP Canva headless (claude -p).

Replaces WR2's Playwright → PNG layout stage with Canva WYSIWYG editor
so Zero can edit any slide in Canva UI after Council approval.

Flow:
    WR2 war_room_drafts.slides_json
      → pending_builder → canva_pending.json
      → claude_invoker → subprocess `claude -p` reads APPLICA_WAR_ROOM.md
      → MCP Canva applies 26+ operations to template DAHE6lx1lf8
      → url_extractor pulls edit_design_url from stdout
      → war_room_drafts.canva_url (new column, migration 129)
      → Review Gate shows Canva link in Telegram instead of PNG

Reference: APPLICA_WAR_ROOM.md (apps/war-room/APPLICA_WAR_ROOM.md) — the
editorial runbook that claude -p executes headlessly. Template element IDs
map in `pending_builder.TEMPLATE_SLOTS`, recovered via start-editing-transaction
on 2026-03-26 and 2026-04-22.
"""

from backend.services.canva_renderer.pending_builder import (
    TEMPLATE_DESIGN_ID,
    TEMPLATE_SLOTS,
    build_canva_pending,
    slides_to_operations,
)

__all__ = [
    "TEMPLATE_DESIGN_ID",
    "TEMPLATE_SLOTS",
    "build_canva_pending",
    "slides_to_operations",
]
