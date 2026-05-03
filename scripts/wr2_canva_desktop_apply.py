#!/usr/bin/env python3
"""WR2 Canva Apply via Claude Desktop GUI automation.

Why this exists: `claude -p` subprocess doesn't load the Canva MCP server
reliably (project-scoped OAuth doesn't survive the spawn cleanly). Canva
Connect REST API doesn't support element-level text replacement on custom
Instagram designs. The only reliable path is the interactive Claude
Desktop session — so we automate it with AppleScript.

Flow:
    1. Query DB for drafts with status='drafts' and canva_edit_url IS NULL
    2. For each draft:
        a. Build canva_pending.json and write it to the path the
           /canva-apply skill expects:
           apps/war-room/output/canva/canva_pending.json
        b. Focus Claude Desktop, open a new chat (Cmd+N), paste
           `/canva-apply`, press Enter.
        c. Poll apps/war-room/output/canva/carousel_canva.json until the
           skill writes the new design URL (timeout 10 min).
        d. Persist canva_design_id / canva_edit_url to the draft; set
           status='rendered'.
        e. Telegram notify with the Canva URL.

Kill switch: system_settings.wr2_canva_desktop_apply_enabled must be 'true'.

Requires:
    - macOS with osascript
    - Claude Desktop at /Applications/Claude.app
    - Terminal or the runner shell must have Automation permission for
      "Claude" + "System Events" (System Settings → Privacy & Security →
      Automation).
    - ~/.claude/skills/canva-apply.md defines the /canva-apply skill
      (edit master in-place → duplicate → move to folder → RESET master →
      write carousel_canva.json).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from uuid import UUID

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

import asyncpg  # noqa: E402

from backend.services.canva_renderer import build_canva_pending  # noqa: E402

logger = logging.getLogger("wr2.canva_desktop_apply")

MAX_DRAFTS_PER_RUN = 1  # GUI automation is fragile — never race
CLAUDE_APP_NAME = "Claude"

# Where the /canva-apply skill looks for the pending file.
# Must match the path in ~/.claude/skills/canva-apply.md.
CANVA_PENDING_PATH = (
    _REPO_ROOT / "apps" / "war-room" / "output" / "canva" / "canva_pending.json"
)
CANVA_OUTPUT_PATH = (
    _REPO_ROOT / "apps" / "war-room" / "output" / "canva" / "carousel_canva.json"
)

POLL_INTERVAL_SEC = 10
POLL_TIMEOUT_SEC = 600  # 10 minutes


def _configure_logging() -> None:
    log_dir = Path.home() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "wr2_canva_desktop_apply.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


def _send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


# ─────────────────────────────────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────────────────────────────────


async def _kill_switch_enabled(conn: asyncpg.Connection) -> bool:
    v = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'wr2_canva_desktop_apply_enabled'",
    )
    return v == "true"


async def _fetch_ready_drafts(conn: asyncpg.Connection, limit: int) -> list[asyncpg.Record]:
    # WR2 pipeline: topic → briefed → (draft_generator) → drafts →
    # (image_generator) → drafts_imaged → (canva_apply) → published.
    # Accept both 'drafts_imaged' (normal) and 'drafts' (legacy/fallback when
    # image_generator is disabled) so the pipeline keeps flowing even if
    # the image step is skipped.
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


async def _persist_result(
    conn: asyncpg.Connection,
    draft_id: UUID,
    design_id: str,
    edit_url: str,
    view_url: str | None,
) -> None:
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
        design_id,
        edit_url,
        view_url,
    )


# ─────────────────────────────────────────────────────────────────────────
# Claude Desktop GUI automation
# ─────────────────────────────────────────────────────────────────────────


def _run_applescript(script: str, timeout: int = 30) -> tuple[int, str, str]:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _claude_is_running() -> bool:
    rc = subprocess.run(
        ["pgrep", "-f", "Claude.app/Contents/MacOS/Claude"],
        capture_output=True,
    ).returncode
    return rc == 0


def _launch_claude() -> None:
    if _claude_is_running():
        return
    logger.info("Claude Desktop not running — launching...")
    subprocess.run(["open", "-a", CLAUDE_APP_NAME], check=True)
    time.sleep(5)


def _focus_claude_and_send_command(command: str) -> None:
    """Bring Claude Desktop to front, open a new chat, paste command, press Enter.

    Hardened (2026-04-25): pbcopy is confirmed before paste (prevents the
    clipboard containing stale content like "/canva-apply"), frontmost is
    forced + verified before every keystroke (prevents paste into wrong app
    like iTerm2 or browser), and Cmd+V uses a longer delay before Enter so
    Claude Desktop can register the full prompt before submission.
    """
    rc, _, err = _run_applescript(
        f'''
        tell application "{CLAUDE_APP_NAME}" to activate
        delay 1
        tell application "System Events"
            tell process "{CLAUDE_APP_NAME}" to set frontmost to true
        end tell
        '''
    )
    if rc != 0:
        raise RuntimeError(f"activate failed: {err}")
    time.sleep(1.5)

    def _verify_frontmost() -> None:
        rc_v, out, err_v = _run_applescript(
            'tell application "System Events" to return name of first application process whose frontmost is true'
        )
        if rc_v != 0:
            raise RuntimeError(f"frontmost check failed: {err_v}")
        if out != CLAUDE_APP_NAME:
            raise RuntimeError(
                f"frontmost is {out!r}, expected {CLAUDE_APP_NAME!r} — "
                "refusing to keystroke (would paste into wrong app). "
                "Close whatever is stealing focus and re-trigger."
            )

    _verify_frontmost()

    # Open a fresh chat — force frontmost inside the tell
    rc, _, err = _run_applescript(
        f'''
        tell application "System Events"
            tell process "{CLAUDE_APP_NAME}"
                set frontmost to true
                keystroke "n" using command down
            end tell
        end tell
        '''
    )
    if rc != 0:
        raise RuntimeError(f"Cmd+N failed: {err}")
    time.sleep(1.5)
    _verify_frontmost()

    # Stage command on clipboard and VERIFY the expected bytes landed.
    # pbcopy has been observed to race under load, leaving stale content
    # (e.g. a prior "/canva-apply" string) on the clipboard and causing
    # the paste to submit an empty-ish prompt to Claude Desktop.
    subprocess.run(["pbcopy"], input=command.encode(), check=True)
    expected_len = len(command)
    # Give pasteboard a moment to settle, then read back via pbpaste
    time.sleep(0.5)
    pb_check = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
    actual_len = len(pb_check.stdout)
    if actual_len < expected_len - 10:  # tolerate small trailing-newline drift
        # One retry
        subprocess.run(["pbcopy"], input=command.encode(), check=True)
        time.sleep(1.0)
        pb_check = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
        actual_len = len(pb_check.stdout)
        if actual_len < expected_len - 10:
            raise RuntimeError(
                f"pbcopy failed to stage full command: expected {expected_len} bytes, "
                f"clipboard has {actual_len}. Aborting to avoid sending truncated prompt."
            )

    rc, _, err = _run_applescript(
        f'''
        tell application "System Events"
            tell process "{CLAUDE_APP_NAME}"
                set frontmost to true
                keystroke "v" using command down
                delay 0.8
                key code 36
            end tell
        end tell
        '''
    )
    if rc != 0:
        raise RuntimeError(f"paste+enter failed: {err}")


# ─────────────────────────────────────────────────────────────────────────
# Poll for carousel_canva.json
# ─────────────────────────────────────────────────────────────────────────


def _wait_for_canva_output(
    since_ts: float,
    timeout_sec: int = POLL_TIMEOUT_SEC,
) -> tuple[str, str, str | None] | None:
    """Return (design_id, edit_url, view_url) when the skill writes carousel_canva.json.

    Checks mtime to ensure we only read NEW output (produced after since_ts).
    Returns None on timeout.
    """
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if CANVA_OUTPUT_PATH.is_file():
            mtime = CANVA_OUTPUT_PATH.stat().st_mtime
            if mtime >= since_ts:
                try:
                    data = json.loads(CANVA_OUTPUT_PATH.read_text())
                    design_id = data.get("design_id")
                    if design_id:
                        edit_url = data.get("design_url") or (
                            f"https://www.canva.com/design/{design_id}/edit"
                        )
                        view_url = data.get("view_url")
                        return design_id, edit_url, view_url
                except (json.JSONDecodeError, OSError) as e:
                    logger.debug("output read failed: %s", e)
        time.sleep(POLL_INTERVAL_SEC)
    return None


# ─────────────────────────────────────────────────────────────────────────
# Per-draft flow
# ─────────────────────────────────────────────────────────────────────────


async def _apply_one(conn: asyncpg.Connection, row: asyncpg.Record) -> bool:
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

    pending["status"] = "pending"  # /canva-apply skill requires this
    CANVA_PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANVA_PENDING_PATH.write_text(json.dumps(pending, indent=2), encoding="utf-8")
    logger.info("Wrote pending → %s", CANVA_PENDING_PATH)

    # Clear stale output
    if CANVA_OUTPUT_PATH.is_file():
        CANVA_OUTPUT_PATH.unlink()

    _send_telegram(
        "WR2 Canva apply starting\n"
        f"Topic: {topic[:100]}\n"
        f"Draft: {draft_id}\n"
        "Driving Claude Desktop..."
    )

    # Claude Desktop does NOT understand Claude Code slash-commands like
    # "/canva-apply". Instead of sending the command, we inline the full
    # skill body from ~/.claude/skills/canva-apply.md as a natural-language
    # prompt. This guarantees Claude Desktop executes the intended 4-phase
    # flow (edit master → duplicate → reset master → persist) using the
    # template's original element_id mapping.
    skill_path = Path.home() / ".claude" / "skills" / "canva-apply.md"
    if not skill_path.is_file():
        logger.error("Skill file missing: %s", skill_path)
        return False
    skill_body = skill_path.read_text(encoding="utf-8")
    # Strip the frontmatter (Claude Desktop doesn't care about YAML meta)
    if skill_body.startswith("---"):
        parts = skill_body.split("---", 2)
        if len(parts) >= 3:
            skill_body = parts[2].lstrip()

    command_text = (
        "Please execute the Canva carousel apply flow described below. "
        "The pending JSON already exists at the path below. Follow the steps "
        "exactly — no TodoWrite, no confirmation prompts between MCP tool calls, "
        "this is a pre-authorized maintenance operation.\n\n"
        f"Pending file path: {CANVA_PENDING_PATH}\n\n"
        "---\n\n"
        + skill_body
    )

    started_at = time.time()
    # PR-D2 (2026-04-30): GUI automation fails transiently when another app
    # steals focus during the milliseconds between activate + verify_frontmost.
    # Retry envelope: up to 5 attempts with 30s gap. Telegram alert only
    # after the full envelope fails — no per-attempt noise.
    last_error: Exception | None = None
    for attempt in range(1, 6):
        try:
            _launch_claude()
            _focus_claude_and_send_command(command_text)
            if attempt > 1:
                logger.info("GUI automation succeeded on attempt %d/5", attempt)
            last_error = None
            break
        except Exception as e:  # noqa: BLE001
            last_error = e
            logger.warning(
                "GUI automation attempt %d/5 failed: %s", attempt, e,
            )
            if attempt < 5:
                time.sleep(30)
    if last_error is not None:
        logger.error("GUI automation exhausted 5 retries: %s", last_error)
        _send_telegram(
            f"WR2 Canva apply GUI failed after 5 retries: {last_error}"
        )
        return False

    logger.info("Command sent — polling for output...")
    result = _wait_for_canva_output(since_ts=started_at)
    if not result:
        _send_telegram(
            f"WR2 Canva apply TIMEOUT after {POLL_TIMEOUT_SEC}s\n"
            f"Draft: {draft_id}\n"
            "Check Claude Desktop manually"
        )
        return False

    design_id, edit_url, view_url = result
    await _persist_result(conn, draft_id, design_id, edit_url, view_url)
    duration = time.time() - started_at
    logger.info(
        "Draft %s rendered — design=%s edit=%s duration=%.0fs",
        draft_id,
        design_id,
        edit_url,
        duration,
    )
    _send_telegram(
        "WR2 Canva carousel ready\n"
        f"Topic: {topic[:100]}\n"
        f"Design: {design_id}\n"
        f"Open: {edit_url}\n"
        f"Duration: {duration:.0f}s"
    )
    return True


async def run(dry_run: bool = False) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2

    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        if not await _kill_switch_enabled(conn):
            logger.info("wr2_canva_desktop_apply_enabled != true — exiting")
            return 0

        drafts = await _fetch_ready_drafts(conn, MAX_DRAFTS_PER_RUN)
        if not drafts:
            logger.info("no drafts ready")
            return 0

        if dry_run:
            logger.info("[DRY-RUN] would process %d drafts:", len(drafts))
            for d in drafts:
                logger.info("  %s — %s", d["id"], d["topic"][:80])
            return 0

        successes = 0
        for row in drafts:
            try:
                if await _apply_one(conn, row):
                    successes += 1
            except Exception as e:
                logger.exception("Draft %s crashed: %s", row["id"], e)

        return 0 if successes == len(drafts) else 1
    finally:
        await conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    _configure_logging()
    try:
        return asyncio.run(run(dry_run=args.dry_run))
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        _send_telegram(f"WR2 canva_desktop_apply crashed: {str(e)[:300]}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
