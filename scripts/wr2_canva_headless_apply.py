"""WR2 headless Canva actuator — launches `claude -p` to apply canva_pending.json
via the /canva-apply skill (duplica-poi-edita). Lease functions here serialize
edits on the master template_design_id across Pro/Mini (shared Fly Postgres)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path

import asyncpg


def _lock_key(template_design_id: str) -> int:
    return int(hashlib.sha256(template_design_id.encode()).hexdigest()[:15], 16)


async def acquire_master_lock(conn: asyncpg.Connection, template_design_id: str) -> bool:
    """pg_try_advisory_lock keyed on template_design_id. False if held by Pro OR Mini
    (session-level advisory locks are cluster-global on the shared Fly Postgres)."""
    return await conn.fetchval("SELECT pg_try_advisory_lock($1)", _lock_key(template_design_id))


async def release_master_lock(conn: asyncpg.Connection, template_design_id: str) -> None:
    await conn.execute("SELECT pg_advisory_unlock($1)", _lock_key(template_design_id))


_QUOTA_BLOCK_PATTERNS = ("usage limit", "out of extra usage", "quota exceeded",
                         "rate limit", "429", "exhausted", "resets in")


def quota_ok_to_run() -> bool:
    """BEST-EFFORT quota signal (A5): `claude auth status` is NOT a reliable MAX
    rolling-window oracle — it reports login state, not remaining quota. This scan
    only catches the case where the CLI surfaces an explicit limit string. Treat a
    True result as "no obvious block", NOT "quota confirmed available". Fail-open on
    probe error. The real protection against a 3am quota outage is the LaunchAgent
    cadence + Telegram alert on repeated headless failures, not this check."""
    try:
        r = subprocess.run(["claude", "auth", "status"], capture_output=True,
                           text=True, timeout=15)
    except Exception:
        return True  # fail-open on probe error: don't block pipeline on a flaky probe
    text = (r.stdout + r.stderr).lower()
    return not any(p in text for p in _QUOTA_BLOCK_PATTERNS)


def canva_tools_loaded_in_stream(stream_jsonl: str) -> bool:
    """A8 fail-closed: scan stream-json for an actual mcp__claude_ai_Canva__* tool_use.
    If the skill never invoked a Canva tool, the run did NOT touch Canva — caller must
    NOT mark the draft rendered."""
    for line in stream_jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        msg = ev.get("message", {})
        content = msg.get("content")
        if isinstance(content, list):
            for blk in content:
                if (isinstance(blk, dict) and blk.get("type") == "tool_use"
                        and str(blk.get("name", "")).startswith("mcp__claude_ai_Canva__")):
                    return True
    return False


HEADLESS_TIMEOUT_SEC = int(os.environ.get("WR2_HEADLESS_TIMEOUT_SEC", "900"))
HEADLESS_MAX_BUDGET_USD = float(os.environ.get("WR2_HEADLESS_MAX_BUDGET_USD", "5"))


def _build_command_text(skill_body: str, pending_path: Path) -> str:
    return (
        "Execute the Canva carousel apply flow below. STEP -2 first (load Canva tools "
        "via ToolSearch). The pending JSON is at the path below. NEVER call "
        "AskUserQuestion; use the hardcoded fallbacks. This is pre-authorized.\n\n"
        f"Pending file path: {pending_path}\n\n---\n\n{skill_body}"
    )


def _verify_skill_hash(skill_path: Path) -> None:
    """A2 re-scope tripwire: compare the installed skill body sha256 against the
    reviewed baseline (infra/claude-skills/canva-apply.sha256). WARN on mismatch,
    do NOT abort — the installed file is operative and may legitimately be ahead of
    a pending mirror sync."""
    baseline = Path(__file__).resolve().parent.parent / "infra/claude-skills/canva-apply.sha256"
    try:
        expected = baseline.read_text(encoding="utf-8").strip()
        actual = hashlib.sha256(skill_path.read_bytes()).hexdigest()
        if actual != expected:
            logging.getLogger("wr2.canva.headless").warning(
                "canva-apply skill body sha256 %s != baseline %s — installed skill "
                "diverged from reviewed mirror", actual[:12], expected[:12])
    except Exception:
        logging.getLogger("wr2.canva.headless").warning(
            "canva-apply skill hash baseline missing/unreadable — tripwire skipped")


async def apply_headless(conn, pending_path: Path, template_design_id: str,
                         output_path: Path):
    """Returns (design_id, edit_url, view_url) on success, None on failure.
    Acquires master lock, runs headless, fail-closed verifies, writes option-c file."""
    if not quota_ok_to_run():
        return None  # caller logs + Telegram defer
    if not await acquire_master_lock(conn, template_design_id):
        return None  # another run (Pro/Mini) holds the master — defer, do not corrupt
    try:
        skill_path = Path.home() / ".claude/skills/canva-apply.md"
        skill_body = skill_path.read_text(encoding="utf-8")
        _verify_skill_hash(skill_path)
        if skill_body.startswith("---"):
            skill_body = skill_body.split("---", 2)[2].lstrip()
        cmd_text = _build_command_text(skill_body, pending_path)
        proc = subprocess.run(
            # A2 re-scope: plain --dangerously-skip-permissions. Flag isolation is
            # unachievable (--strict-mcp-config kills account-hosted Canva;
            # --disallowedTools ignored under skip-permissions). NO regression vs the
            # AppleScript path (same built-ins). Blast-radius = upstream sanitization.
            ["claude", "-p", cmd_text, "--dangerously-skip-permissions",
             "--output-format", "stream-json", "--verbose",
             "--max-budget-usd", str(HEADLESS_MAX_BUDGET_USD)],
            capture_output=True, text=True, timeout=HEADLESS_TIMEOUT_SEC,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode != 0:
            return None  # non-zero exit (auth fail, crash) → do NOT mark rendered
        stream = proc.stdout or ""
        if not canva_tools_loaded_in_stream(stream):
            return None  # A8: Canva never touched — do NOT mark rendered
        pending = json.loads(pending_path.read_text())
        if pending.get("status") != "applied" or not pending.get("design_id"):
            return None
        design_id = pending["design_id"]
        edit_url = pending.get("design_url") or f"https://www.canva.com/design/{design_id}/edit"
        view_url = pending.get("view_url")
        # A3 option-c: actuator writes carousel_canva.json for reconcile + upload-waste
        output_path.write_text(json.dumps({
            "design_id": design_id, "design_url": edit_url, "view_url": view_url,
            "topic": pending.get("topic"), "slides_count": pending.get("slides_count"),
            "status": "applied", "applied_at": pending.get("applied_at"),
        }, indent=2), encoding="utf-8")
        return design_id, edit_url, view_url
    except subprocess.TimeoutExpired:
        return None  # caller logs timeout + Telegram; lock released in finally
    finally:
        await release_master_lock(conn, template_design_id)
