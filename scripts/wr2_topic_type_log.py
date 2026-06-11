#!/usr/bin/env python3
"""Shared anti-sameness ledger writer (P-1 S1, constitution Art 10.6).

Single home for the `topic_type_log` INSERT so every render lane (HTML
chokepoint, legacy Canva apply until R2 retires it) feeds the same Postgres
ledger (migration 216). Extracted verbatim from wr2_canva_desktop_apply.py
after the 2026-06-09 HTML cutover orphaned the write there (the variety
machine read side in wr2_draft_generator starves without it).

Callers wrap this in their own best-effort/savepoint pattern — a logging
failure must NEVER abort a render promote.
"""
from __future__ import annotations

from uuid import UUID

import asyncpg


async def log_topic_type(
    conn: asyncpg.Connection,
    draft_id: UUID,
    topic: str | None = None,
    slides_json: object | None = None,
    register: str | None = None,
) -> None:
    """Derive (domain, dominant_mode, layout_family, archetype) and INSERT one
    row into topic_type_log, idempotent on draft_id.

    If topic/slides_json/register were not threaded in by the caller, fall back
    to a single SELECT on war_room_drafts (best-effort logging tolerates the
    extra query). Pure-derivation lives in wr2_topic_type.
    """
    import wr2_topic_type as tt  # local import: keep module import side-effect-free

    if topic is None or slides_json is None or register is None:
        rec = await conn.fetchrow(
            "SELECT topic, register, slides_json FROM war_room_drafts WHERE id = $1",
            draft_id,
        )
        if rec is not None:
            topic = topic if topic is not None else rec["topic"]
            register = register if register is not None else rec["register"]
            slides_json = slides_json if slides_json is not None else rec["slides_json"]

    domain = tt.derive_domain(topic)
    dominant_mode = tt.derive_dominant_mode(slides_json)
    layout_family = tt.derive_layout_family(slides_json)
    archetype = tt.extract_archetype(slides_json)

    await conn.execute(
        """
        INSERT INTO topic_type_log
            (draft_id, domain, register, dominant_mode, layout_family, archetype, topic)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (draft_id) DO NOTHING
        """,
        draft_id,
        domain,
        register,
        dominant_mode,
        layout_family,
        archetype,
        topic,
    )
