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

DEFAULT_TIMEOUT_SEC = 1500  # 25 min — full runbook can take 10-15 min on 11-slide
# template with cover upload + bulk editorial + bold pass + duplicate + move + QA.
# Budget breakdown observed 2026-04-24:
#   STEP 1 (start transaction):       ~5s
#   STEP 2 (cover upload-asset):    ~15s
#   STEP 3 (batch slides 1-6):       ~90s (MCP perform-editing-ops is slow)
#   STEP 3' (batch slides 7-11):     ~90s
#   STEP 4 (bold/formatting pass):  ~60s
#   STEP 5 (commit transaction):     ~10s
#   STEP 6 (duplicate template):     ~30s
#   STEP 7 (move to folder):         ~15s
#   STEP 8 (QA thumbnails):          ~60s
#   Planner/reasoning overhead:    ~120s
#   TOTAL:                          ~495s (~8 min)
# Plus 2-3x safety margin for cold-cache iterations + MCP server latency.
DEFAULT_CLAUDE_BIN = "claude"  # resolved from PATH
# Runbook ships next to this module (portable across Pro/Air/CI). Historical
# note: WR1 kept it at apps/war-room/APPLICA_WAR_ROOM.md — that tree was
# decommissioned 2026-04-22 when WR2 took over the headless Canva apply.
APPLICA_RUNBOOK_PATH = Path(__file__).parent / "runbooks" / "APPLICA_WAR_ROOM.md"

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
    """Compose a minimalist, deterministic prompt for `claude -p`.

    Historical note: from 2026-03 to 2026-04-24 this function concatenated the
    full APPLICA_WAR_ROOM.md runbook (~180 lines of editorial guidance, QA
    steps, TodoWrite tracking, bold pass, remapping heuristics). Empirically
    Claude got lost in the runbook narrative — it would spend 10-25 minutes
    interpreting steps, open Todos, second-guess element IDs, and often
    bail out with a fake fallback JSON before completing. Verified
    reproducibly on draft 6ace6b26 (two consecutive runs, 118s and 1500s
    timeout).

    Replacement: this prompt reads the pending file itself and emits an
    imperative 5-step script inline. Every MCP tool call is named explicitly
    with its `mcp__claude_ai_Canva__*` prefix. Operations are passed as a
    literal JSON payload Claude only has to forward. No QA step, no bold
    pass — the editor workflow is manual-by-design (design doc §3).

    Test evidence (2026-04-24): the shorter prompt completed the same draft
    in ~90 seconds and produced new design_id=DAHHvBPPbuI.

    The runbook file is kept on disk for reference but is no longer loaded
    by the headless worker.
    """
    if not canva_pending_path.is_file():
        raise CanvaInvokeError(f"canva_pending.json not found: {canva_pending_path}")

    pending = json.loads(canva_pending_path.read_text(encoding="utf-8"))
    template_id = pending["template_design_id"]
    folder_id = pending.get("folder_id")
    operations = pending.get("operations", [])

    # Split ops into replace_text vs upload-asset-from-url (which needs a
    # different tool: upload-asset-from-url must happen first to get the
    # asset_id that is then referenced by a replace-image inside perform-
    # editing-operations — but Canva MCP accepts the URL directly via
    # perform-editing-operations when the op type is 'replace_image' with
    # media_url. We keep the builder's shape and let Claude translate).
    #
    # We ship ALL operations in a single perform-editing-operations call.
    # The builder already ensures ops are template-ready; Claude just
    # forwards the JSON verbatim.
    ops_json = json.dumps(operations, ensure_ascii=False)

    return f"""You have access to MCP Canva tools. Execute the following EXACT sequence without deviation, commentary, or TodoWrite calls.

STEP 1. Call mcp__claude_ai_Canva__start-editing-transaction:
  design_id = "{template_id}"
  user_intent = "apply carousel text and image replacements"
→ Save the transaction_id from the response.

STEP 2. For EACH op in the operations array below where type == "upload-asset-from-url",
call mcp__claude_ai_Canva__upload-asset-from-url with url, name={canva_pending_path.stem!r},
user_intent="cover asset for carousel" ONCE per unique url. Save the asset_id returned.
(If the same url appears multiple times only upload it once.)

STEP 3. Call mcp__claude_ai_Canva__perform-editing-operations:
  transaction_id = <from step 1>
  user_intent = "apply carousel replacements"
  pages = [1,2,3,4,5,6,7,8,9,10,11]
  operations = the JSON array below, with every {{"type":"upload-asset-from-url",...}}
               rewritten to {{"type":"replace_image","element_id":<same>,"asset_id":<from step 2>,"page_index":<same>}}.
               Leave every {{"type":"replace_text",...}} unchanged.

OPERATIONS JSON (forward as-is except for the upload→replace_image rewrite):
{ops_json}

STEP 4. Call mcp__claude_ai_Canva__commit-editing-transaction with the transaction_id.

STEP 5. Call mcp__claude_ai_Canva__resize-design to duplicate the template to a new design:
  design_id = "{template_id}"
  (keep same dimensions — this duplicates.)
→ Save the NEW design_id from the response.

STEP 6 (optional, skip if it fails). Call mcp__claude_ai_Canva__move-item-to-folder:
  item_id = <new design_id>
  folder_id = "{folder_id}"

STEP 7. OUTPUT CONTRACT — emit EXACTLY this JSON on a single line as the last
line of your response, no markdown fences, no surrounding prose:

{{"design_id":"<NEW_DESIGN_ID>","edit_url":"https://www.canva.com/design/<NEW_DESIGN_ID>/edit","view_url":"https://www.canva.com/design/<NEW_DESIGN_ID>/view"}}

If step 5 fails and you cannot obtain a new design_id, output the original template id as design_id and its /edit URL — do NOT skip the JSON line.
"""


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
    # CRITICAL: Claude Code loads MCP servers from the project-level
    # `~/.claude.json > projects[<cwd>] > mcpServers` map, keyed by the
    # current working directory at spawn time. If we don't pin cwd to the
    # Nuzantara repo root, `claude -p` runs in /Users/nuzantara (home),
    # where the Canva MCP server is NOT configured, and Claude silently
    # falls back to "no tools available" — producing a graceful-sounding
    # but useless meta-commentary response. Verified 2026-04-24.
    repo_root = Path(__file__).resolve().parents[5]  # …/apps/backend-rag/backend/services/canva_renderer/claude_invoker.py → repo root (nuzantara/)
    try:
        completed = subprocess.run(
            [claude_bin, "-p", prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            cwd=str(repo_root),
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
