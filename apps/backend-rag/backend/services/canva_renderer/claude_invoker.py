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

DEFAULT_TIMEOUT_SEC = 600  # 10 min — full APPLICA_WAR_ROOM runbook can take 5-8 min
DEFAULT_CLAUDE_BIN = "claude"  # resolved from PATH
APPLICA_RUNBOOK_PATH = Path(
    "/Users/nuzantara/Desktop/nuzantara/apps/war-room/APPLICA_WAR_ROOM.md",
)

# Regex pool, tried in order: JSON field, markdown link, bare URL
_CANVA_URL_RE = re.compile(r"https?://(?:www\.)?canva\.com/d/([A-Za-z0-9_\-]+)")
_CANVA_JSON_RE = re.compile(
    r'"(?:edit_url|edit_design_url|url)"\s*:\s*"(https?://[^"]+canva\.com/d/[^"]+)"',
)
_DESIGN_ID_JSON_RE = re.compile(
    r'"design_id"\s*:\s*"(D[A-Za-z0-9_\-]+)"',
)
_VIEW_URL_JSON_RE = re.compile(
    r'"view_url"\s*:\s*"(https?://[^"]+canva\.com/d/[^"]+)"',
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


def _build_prompt(canva_pending_path: Path) -> str:
    """Compose the prompt: runbook body + path to pending JSON + output contract.

    Keeping the runbook in a file (not inline) means editorial changes in
    APPLICA_WAR_ROOM.md propagate automatically.
    """
    if not APPLICA_RUNBOOK_PATH.is_file():
        raise CanvaInvokeError(
            f"runbook not found at {APPLICA_RUNBOOK_PATH}. "
            "Is the war-room app on Pro? WR1 removal plan must preserve "
            "this file until WR2 has its own runbook.",
        )
    runbook = APPLICA_RUNBOOK_PATH.read_text(encoding="utf-8")
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

    logger.info(
        "Invoking claude -p for Canva apply — pending=%s timeout=%ds",
        canva_pending_path,
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
