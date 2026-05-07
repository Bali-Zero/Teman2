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
from datetime import datetime, timezone
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

# B0 instrumentation (2026-05-08): detect-sentinel + retry-once + telemetry.
# After 4 independent design reviews, the "MCP cache warming" hypothesis was
# rejected as architecturally unfounded. The 50% empirical canva-apply fail
# rate is unexplained; instrument with append-only JSONL telemetry to collect
# 7 days of real data before deciding on a long-term fix (B1/B2/other).
TELEMETRY_PATH = Path.home() / "logs" / "wr2_canva_apply_telemetry.jsonl"

# When `claude -p` returns these strings in stdout, the canva apply failed
# because the MCP Canva connector was not visible to the subprocess. Cheap
# retry after 60s sleep is worth attempting before giving up.
MCP_NOT_AVAILABLE_SENTINELS = (
    "MCP Canva not available",
    "Canva cloud connector requires claude.ai",
    "claude.ai Canva server is not in mcp-needs-auth-cache",
    "Canva MCP server is not available",
    "mcp__claude_ai_Canva__.* are not loaded in this session",
)


def _is_mcp_cold_failure(exc: CanvaInvokeError) -> bool:
    """Return True if the failure looks like MCP Canva missing from the subprocess."""
    msg = str(exc)
    return any(s in msg for s in MCP_NOT_AVAILABLE_SENTINELS)


def _is_timeout_failure(exc: CanvaInvokeError) -> bool:
    return "timed out" in str(exc).lower()


def _classify_failure(exc: CanvaInvokeError) -> str:
    if _is_mcp_cold_failure(exc):
        return "cold_sentinel"
    if _is_timeout_failure(exc):
        return "timeout"
    return "other"


def _log_run_telemetry(
    draft_id: UUID,
    attempt: int,
    outcome: str,
    duration_s: float,
    exc_text: str,
) -> None:
    """Append one JSONL line per run attempt to ~/logs/wr2_canva_apply_telemetry.jsonl.

    Append-only. No DB schema. Never raises (telemetry must not break the run).
    """
    try:
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "draft_id": str(draft_id),
            "attempt": attempt,  # 1 = first try, 2 = retry-after-cold
            "outcome": outcome,  # 'success' | 'cold_sentinel' | 'timeout' | 'other'
            "duration_s": round(duration_s, 1),
            "exc_head": (exc_text or "")[:240],
        }
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.warning("telemetry write failed (non-fatal): %s", e)

# 2026-05-07: the canva-apply skill (~/.claude/skills/canva-apply.md) has the
# pending JSON path HARDCODED to apps/war-room/output/canva/canva_pending.json.
# Even though invoke_claude_apply passes the actual path in the prompt header,
# the skill body's "Read the file `<absolute path>`" instruction wins. Live
# failure 04:34 WITA on draft 37263a1f returned design=D_ALREADY_APPLIED
# because the skill read the leftover prod pending (status=applied from a
# previous synthetic test) instead of the per-draft /tmp file we wrote.
#
# Fix: write the per-draft pending into the prod path the skill expects.
# MAX_DRAFTS_PER_RUN=3 still serial (sequential loop), so no race risk.
# Sprint B can refactor the skill to honour the prompt-passed path; until
# then this is the single-write convention shared with wr2_canva_desktop_apply.py
# (which also targets the prod path, per CANVA_PENDING_PATH discovery 2026-05-06).
PENDING_PROD_DIR = Path.home() / "Desktop" / "nuzantara" / "apps" / "war-room" / "output" / "canva"
PENDING_PROD_FILE = PENDING_PROD_DIR / "canva_pending.json"


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
    # 2026-05-07: aligned with wr2_canva_desktop_apply (PR #341 fix).
    # DB column is `register` (text), aliased to `tone` for downstream code.
    # Status filter widened to include 'drafts_imaged' since fact-checker
    # and fact-extractor stages are disabled (.disabled/) and canva-apply
    # consumes drafts directly after image-generator.
    return await conn.fetch(
        """
        SELECT id, topic, register AS tone, slides_json
          FROM war_room_drafts
         WHERE status IN ('drafts_imaged', 'drafts')
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
    tone: str = row["tone"] or "pedagogico"
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

    # Write to the prod path that the canva-apply skill hardcodes; see header.
    PENDING_PROD_DIR.mkdir(parents=True, exist_ok=True)
    pending_path = PENDING_PROD_FILE
    pending_path.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    logger.info("Wrote pending JSON for draft %s → %s", draft_id, pending_path)

    # B0 (2026-05-08): detect-sentinel + retry-once + per-attempt telemetry.
    # On the happy path (50% baseline), this adds zero overhead beyond a
    # JSONL log line. On cold-sentinel detection, sleep 60s and retry once
    # before giving up — far cheaper than the 25-min wasted timeout.
    t0 = time.time()
    result = None
    try:
        result = invoke_claude_apply(pending_path)
        _log_run_telemetry(draft_id, 1, "success", time.time() - t0, "")
    except CanvaInvokeError as exc:
        d1 = time.time() - t0
        outcome1 = _classify_failure(exc)
        _log_run_telemetry(draft_id, 1, outcome1, d1, str(exc))
        if outcome1 == "cold_sentinel":
            logger.warning(
                "Draft %s: MCP cold sentinel on attempt 1 (%.1fs) — sleep 60s, retry once",
                draft_id, d1,
            )
            time.sleep(60)
            t1 = time.time()
            try:
                result = invoke_claude_apply(pending_path)
                _log_run_telemetry(draft_id, 2, "success", time.time() - t1, "")
            except CanvaInvokeError as exc2:
                d2 = time.time() - t1
                outcome2 = _classify_failure(exc2)
                _log_run_telemetry(draft_id, 2, outcome2, d2, str(exc2))
                logger.error(
                    "Draft %s: retry after cold also failed (%s, %.1fs): %s",
                    draft_id, outcome2, d2, exc2,
                )
                _send_telegram(
                    f"🚨 *WR2 Canva apply failed*\ndraft: `{draft_id}`\n"
                    f"topic: {topic[:80]}\noutcome: `cold→{outcome2}`\n"
                    f"error: `{str(exc2)[:400]}`",
                )
                return False
        else:
            logger.error("Draft %s Canva apply failed (%s): %s", draft_id, outcome1, exc)
            _send_telegram(
                f"🚨 *WR2 Canva apply failed*\ndraft: `{draft_id}`\n"
                f"topic: {topic[:80]}\noutcome: `{outcome1}`\n"
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
