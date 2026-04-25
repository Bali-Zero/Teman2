#!/usr/bin/env python3
"""WR2 Canva Renderer worker — Pro-only, headless.

Picks war_room_drafts ready for rendering, runs `claude -p` with
APPLICA_WAR_ROOM.md against each draft's canva_pending.json, writes the
resulting Canva edit URL back into the draft.

Runs on Pro (not Fly.io) because MCP Canva needs Claude Code CLI with
browser-bound OAuth. Schedule via launchd:
    infra/launchagents/com.balizero.wr2.canva-renderer.plist

Flow per draft:
    1. Read slides_json + topic + tone from war_room_drafts (status=drafts,
       canva_edit_url IS NULL)
    2. build_canva_pending(topic, tone, slides) → pending dict
    3. Write pending to /tmp/wr2_canva_pending_<draft_id>.json
    4. invoke_claude_apply(pending_path) → CanvaApplyResult
    5. UPDATE war_room_drafts SET canva_*, status='rendered'
    6. (optional) Telegram notify with link — the Review Gate worker picks
       it up via the next status transition

Kill switch:
    system_settings.wr2_canva_renderer_enabled must be 'true'.

Env:
    DATABASE_URL  — Fly Postgres via tunnel (localhost:15432)
    TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID — optional notifications
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID

# Ensure backend-rag importable when run from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer import build_canva_pending  # noqa: E402
from backend.services.canva_renderer.claude_invoker import (  # noqa: E402
    CanvaApplyResult,
    CanvaInvokeError,
    invoke_claude_apply,
)

logger = logging.getLogger("wr2.canva_apply")

MAX_DRAFTS_PER_RUN = 3  # avoid stampede; launchd runs every 5 min
PENDING_TMP_DIR = Path(tempfile.gettempdir())


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_canva_apply.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


async def _kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_canva_renderer_enabled'",
    )
    return value == "true"


async def _fetch_ready_drafts(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    return await conn.fetch(
        """
        SELECT id, topic, register AS tone_register, slides_json
          FROM war_room_drafts
         WHERE status = 'drafts'
           AND canva_edit_url IS NULL
         ORDER BY created_at ASC
         LIMIT $1
        """,
        limit,
    )


async def _persist_canva_result(
    conn: asyncpg.Connection,
    draft_id: UUID,
    result: CanvaApplyResult,
) -> None:
    """Store edit URL + advance status to 'rendered'."""
    await conn.execute(
        """
        UPDATE war_room_drafts
           SET canva_design_id  = $2,
               canva_edit_url   = $3,
               canva_view_url   = $4,
               canva_applied_at = NOW(),
               status           = 'rendered',
               updated_at       = NOW()
         WHERE id = $1
        """,
        draft_id,
        result.design_id,
        result.edit_url,
        result.view_url,
    )


def _send_telegram(text: str) -> None:
    """Optional best-effort notification. Failures swallowed."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


async def _apply_one_draft(conn: asyncpg.Connection, row: asyncpg.Record) -> bool:
    """Process a single draft. Returns True on success."""
    draft_id: UUID = row["id"]
    topic: str = row["topic"]
    tone: str = row["tone_register"] or "pedagogico"
    slides_json = row["slides_json"]

    if isinstance(slides_json, str):
        slides_json = json.loads(slides_json)
    slides = slides_json.get("slides") if isinstance(slides_json, dict) else slides_json

    if not slides:
        logger.warning("Draft %s has no slides — skipping", draft_id)
        return False

    try:
        pending = build_canva_pending(topic=topic, tone=tone, slides=slides)
    except ValueError as exc:
        logger.error("Draft %s pending build failed: %s", draft_id, exc)
        return False

    pending_path = PENDING_TMP_DIR / f"wr2_canva_pending_{draft_id}.json"
    pending_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    logger.info("Wrote pending JSON for draft %s → %s", draft_id, pending_path)

    try:
        result = invoke_claude_apply(pending_path)
    except CanvaInvokeError as exc:
        logger.error("Draft %s Canva apply failed: %s", draft_id, exc)
        _send_telegram(
            f"🚨 *WR2 Canva apply failed*\ndraft: `{draft_id}`\ntopic: {topic[:80]}\n"
            f"error: `{str(exc)[:400]}`",
        )
        return False

    await _persist_canva_result(conn, draft_id, result)
    logger.info(
        "Draft %s applied — design=%s edit_url=%s duration=%.1fs",
        draft_id,
        result.design_id,
        result.edit_url,
        result.duration_sec,
    )
    _send_telegram(
        f"🎨 *WR2 Canva rendered*\ntopic: {topic[:80]}\n"
        f"[Open in Canva]({result.edit_url})\n"
        f"duration: {result.duration_sec:.1f}s",
    )
    # Clean up pending file on success (keep on failure for debug)
    try:
        pending_path.unlink()
    except OSError:
        pass
    return True


async def run() -> int:
    _configure_logging()

    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        if not await _kill_switch_enabled(conn):
            logger.info("wr2_canva_renderer_enabled != true — exiting quietly")
            return 0

        drafts = await _fetch_ready_drafts(conn, MAX_DRAFTS_PER_RUN)
        if not drafts:
            logger.info("no drafts ready for Canva rendering")
            return 0

        logger.info("processing %d draft(s)", len(drafts))
        successes = 0
        started = time.monotonic()
        for row in drafts:
            ok = await _apply_one_draft(conn, row)
            if ok:
                successes += 1

        elapsed = time.monotonic() - started
        logger.info(
            "run complete — %d/%d ok in %.1fs",
            successes,
            len(drafts),
            elapsed,
        )
        return 0 if successes == len(drafts) else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
