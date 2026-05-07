"""Headless invocation of `claude -p` to apply canva_pending.json via MCP.

This module runs ON PRO (not on Fly.io) because the Claude Code CLI needs
to be installed and MCP Canva must be OAuth-authenticated in the user's
browser session. Verified working 2026-04-22 with claude 2.1.116.

Flow:
    canva_pending.json path + APPLICA_WAR_ROOM.md prompt
      → subprocess.run(["claude", "-p", prompt_text], stdin=DEVNULL, timeout=N)
      → parse stdout for design_id + edit_url + view_url
      → return CanvaApplyResult
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SEC = 2400  # 40 min — bumped from 1500 after empirical
# evidence on 7 May 2026: skill v3.2 (height-based remap + width<30 filter
# in BOTH Phase A.5 and Phase C) added ~12-15 min to wall clock. Run
# 0e8e1cf5 (skill v3.1, 2026-05-07 05:16 WITA) finished in 1474s. Run
# e21c86c0 (skill v3.2, 2026-05-07 08:53 WITA) timed out at 1500s. Each
# Canva MCP round-trip is ~3-8s; the new height/width inspection pass on
# 12 pages × ~10 elements each is ~120 inspections. 2400s budgets for
# pathological cases (Canva MCP rate-limit pauses, transient API stalls).
DEFAULT_CLAUDE_BIN = "claude"  # resolved from PATH
# 2026-05-07: APPLICA_WAR_ROOM.md was at apps/war-room/ but that directory was
# removed in PR #171 (WR1 decommission). The authoritative runbook is now the
# userspace skill ~/.claude/skills/canva-apply.md (the ADAPTIVE skill that
# wr2_canva_desktop_apply.py also injects inline). Reading it here reuses the
# single source of truth — any edit to the skill propagates to both code paths.
APPLICA_RUNBOOK_PATH = Path.home() / ".claude" / "skills" / "canva-apply.md"

# Regex pool, tried in order: JSON field, markdown link, bare URL.
# Path tolerates both `/d/<slug>` (legacy) and `/design/<slug>` (current,
# emitted by the canva-apply skill via Canva MCP).
_CANVA_URL_RE = re.compile(
    r"https?://(?:www\.)?canva\.com/(?:d|design)/([A-Za-z0-9_\-]+)",
)
_CANVA_JSON_RE = re.compile(
    r'"(?:edit_url|edit_design_url|url)"\s*:\s*"(https?://[^"]+canva\.com/(?:d|design)/[^"]+)"',
)
_DESIGN_ID_JSON_RE = re.compile(
    r'"design_id"\s*:\s*"(D[A-Za-z0-9_\-]+)"',
)
_VIEW_URL_JSON_RE = re.compile(
    r'"view_url"\s*:\s*"(https?://[^"]+canva\.com/(?:d|design)/[^"]+)"',
)


class CanvaInvokeError(RuntimeError):
    """Raised when claude -p invocation or URL extraction fails."""


@dataclass(frozen=True)
class CanvaApplyResult:
    """Parsed output of a successful apply."""

    design_id: str | None
    edit_url: str
    view_url: str | None
    stdout_tail: str  # last 500 chars for audit
    duration_sec: float


def extract_canva_urls(stdout: str) -> CanvaApplyResult:
    """Parse stdout from claude -p into a CanvaApplyResult.

    Tries in order: JSON fields → markdown link → bare canva.com/d/ URL.
    Raises CanvaInvokeError if nothing usable is found.
    """
    if not stdout.strip():
        raise CanvaInvokeError("empty output from claude -p")

    # 1. JSON extraction
    json_url = _CANVA_JSON_RE.search(stdout)
    design_id_match = _DESIGN_ID_JSON_RE.search(stdout)
    view_url_match = _VIEW_URL_JSON_RE.search(stdout)

    if json_url:
        return CanvaApplyResult(
            design_id=design_id_match.group(1) if design_id_match else None,
            edit_url=json_url.group(1),
            view_url=view_url_match.group(1) if view_url_match else None,
            stdout_tail=stdout[-500:],
            duration_sec=0.0,  # filled by caller
        )

    # 2. Any canva.com/d/ URL (markdown link or bare)
    bare = _CANVA_URL_RE.search(stdout)
    if bare:
        return CanvaApplyResult(
            design_id=None,
            edit_url=bare.group(0),
            view_url=None,
            stdout_tail=stdout[-500:],
            duration_sec=0.0,
        )

    raise CanvaInvokeError(
        f"no Canva URL found in claude -p output (tail: ...{stdout[-200:]!r})",
    )


def _strip_frontmatter(skill_text: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from a skill markdown body.

    Skills under ~/.claude/skills/ start with a frontmatter block carrying
    `name:` and `description:` keys consumed by the slash-command registry.
    The body below the closing `---` is the operational runbook itself —
    the only part the subprocess needs.
    """
    if not skill_text.startswith("---\n"):
        return skill_text
    end = skill_text.find("\n---\n", 4)
    if end == -1:
        return skill_text
    return skill_text[end + 5 :].lstrip("\n")


def _build_prompt(canva_pending_path: Path) -> str:
    """Compose the prompt: skill body + path to pending JSON + output contract.

    Reads the userspace skill at ~/.claude/skills/canva-apply.md (single
    source of truth shared with wr2_canva_desktop_apply.py). Editorial
    changes to the skill propagate to this subprocess path automatically.
    """
    if not APPLICA_RUNBOOK_PATH.is_file():
        raise CanvaInvokeError(
            f"canva-apply skill not found at {APPLICA_RUNBOOK_PATH}. "
            "Install the skill at ~/.claude/skills/canva-apply.md "
            "(authoritative runbook for the WR2 canva-apply flow).",
        )
    runbook = _strip_frontmatter(APPLICA_RUNBOOK_PATH.read_text(encoding="utf-8"))
    contract = (
        "\n\n---\n"
        "OUTPUT CONTRACT (mandatory, last line of your response):\n"
        "Emit a single JSON object on its own line, no markdown fences, "
        "with keys: design_id (the new Canva design id, starts with 'D'), "
        "edit_url (canva.com/d/<slug> editor URL), "
        "view_url (canva.com/d/<slug> read-only URL if available else same as edit_url).\n"
        "Example: "
        '{"design_id":"DAEabc12345","edit_url":"https://www.canva.com/d/abc","view_url":"https://www.canva.com/d/xyz"}'
    )
    # Point claude at the pending file it must read
    header = (
        f"Apply the canva_pending.json at path: {canva_pending_path}\n"
        "Follow the runbook below exactly. Do not ask for confirmation.\n\n"
    )
    return header + runbook + contract


def invoke_claude_apply(
    canva_pending_path: Path,
    *,
    claude_bin: str = DEFAULT_CLAUDE_BIN,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> CanvaApplyResult:
    """Run `claude -p` to apply a canva_pending.json and return the design URLs.

    Blocks until claude exits or timeout. Captures stdout; stderr is
    preserved in the error message. stdin is closed (DEVNULL) to avoid
    the "no stdin data received in 3s" warning.
    """
    import time

    if not canva_pending_path.is_file():
        raise CanvaInvokeError(f"canva_pending.json not found: {canva_pending_path}")

    # Sanity: validate it parses as JSON before spending a CLI invocation
    try:
        json.loads(canva_pending_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CanvaInvokeError(f"canva_pending.json is not valid JSON: {exc}") from exc

    prompt = _build_prompt(canva_pending_path)

    # 2026-05-07: Claude CLI MCP scope is per-directory. The MCP Canva
    # connector (mcp.canva.com/mcp, OAuth token in ~/.mcp-auth/) is only
    # registered for the main repo at ~/Desktop/nuzantara. The deploy
    # worktree at ~/Desktop/nuzantara-deploy (used as WR2_REPO_ROOT in
    # production cron via wr2-script-wrapper.sh) does NOT have the Canva
    # MCP server. Live failure 04:13 WITA on draft 0e8e1cf5 returned:
    #   "ERROR: Canva MCP not available in nuzantara-deploy workspace"
    # Fix: pin cwd to the main repo regardless of where the worker runs.
    # The skill reads canva_pending.json by absolute path, so cwd here is
    # purely the MCP scope discriminator — the pending file location is
    # unaffected by this pin (and is also CANVA_PENDING_PATH-hardcoded
    # to the main repo from wr2_canva_desktop_apply.py history).
    claude_cwd = Path.home() / "Desktop" / "nuzantara"

    logger.info(
        "Invoking claude -p for Canva apply — pending=%s cwd=%s timeout=%ds",
        canva_pending_path,
        claude_cwd,
        timeout_sec,
    )
    start = time.monotonic()
    try:
        completed = subprocess.run(
            [claude_bin, "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            cwd=str(claude_cwd),
        )
    except subprocess.TimeoutExpired as exc:
        raise CanvaInvokeError(
            f"claude -p timed out after {timeout_sec}s — "
            f"check MCP Canva reachability and runbook size",
        ) from exc
    except FileNotFoundError as exc:
        raise CanvaInvokeError(
            f"claude binary not found at {claude_bin!r} — "
            "ensure Claude Code CLI is installed on this machine (Pro)",
        ) from exc

    duration = time.monotonic() - start

    if completed.returncode != 0:
        raise CanvaInvokeError(
            f"claude -p exited {completed.returncode} after {duration:.1f}s. "
            f"stderr: {completed.stderr[-1000:] if completed.stderr else '(empty)'}",
        )

    result = extract_canva_urls(completed.stdout)
    # Re-pack with actual duration (dataclass is frozen — rebuild)
    return CanvaApplyResult(
        design_id=result.design_id,
        edit_url=result.edit_url,
        view_url=result.view_url,
        stdout_tail=result.stdout_tail,
        duration_sec=duration,
    )
