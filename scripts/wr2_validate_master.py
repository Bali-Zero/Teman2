#!/usr/bin/env python3
"""WR2 master template structural validator.

Pre-flight check for any change to TEMPLATE_DESIGN_ID in
apps/backend-rag/backend/services/canva_renderer/pending_builder.py.

Why this exists: PR #565 (2026-05-09) promoted a master template
(`DAHJLYRn_3E`) without verifying its structural shape. The design
only had richtext slots on pages 2 and 3; Phase A of the canva-apply
skill detected 19/22 ops would drop and aborted. This validator runs
the same shape check the skill does — but BEFORE any code change ships.

What "structurally compatible" means for the WR2 pipeline:
- The Canva design exists and is reachable via MCP.
- It has at least 11 usable pages (renderer clamps to MAX_SLIDES_TEMPLATE).
- It has at least 18 richtext elements (heading + body × 9 pages min)
  with width >= 30. The width filter excludes bullet-glyph decorations.
- Pages 1 (cover), 7, 9, 10, 11 may legitimately have only 1 richtext
  per the original DAHE6lx1lf8 layout (image-heavy slides).

Usage:
    # Validate the current TEMPLATE_DESIGN_ID:
    python scripts/wr2_validate_master.py

    # Validate a candidate replacement before changing the constant:
    python scripts/wr2_validate_master.py --design-id DAHXNew123

    # JSON output for CI consumption:
    python scripts/wr2_validate_master.py --json

Exits 0 on pass, non-zero on fail. The check is empirical (calls
Canva MCP via the same OAuth flow the apply skill uses), so it
needs to run on a machine with Claude Desktop + Canva integration
authenticated. CI integration (Phase 2) requires service-account
OAuth which is not yet wired.

Limitations:
- We cannot reach Canva from headless CI without Canva-side OAuth.
  This script is a HUMAN gate: contributors run it locally before
  bumping TEMPLATE_DESIGN_ID and paste the JSON output into the PR.
- The unit test in test_pending_builder.py only validates the
  shape of the constant (regex match). The empirical check is here.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("wr2.validate_master")

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "apps" / "backend-rag"))

# Import the constant we are validating. The import side-effects are zero
# (pending_builder is a pure module), so this is safe to call from any
# context.
try:
    from backend.services.canva_renderer.pending_builder import (
        MAX_SLIDES_TEMPLATE,
        TEMPLATE_DESIGN_ID,
    )
except ImportError as exc:
    print(f"ERROR: cannot import pending_builder: {exc}", file=sys.stderr)
    sys.exit(2)

# Empirical thresholds for "structurally compatible".
# These come from the live shape of the original DAHE6lx1lf8 master
# (verified 2026-04-22) re-confirmed via DAHJEkWpkzY (2026-05-10).
MIN_USABLE_PAGES = MAX_SLIDES_TEMPLATE  # 11
MIN_RICHTEXTS = 18  # heading + body × 9 pages
MIN_RICHTEXT_WIDTH = 30  # filter out bullet glyphs / decorative rules

# Canva design ID format (validated by the unit test, repeated here
# for the manual --design-id flag).
DESIGN_ID_RE = re.compile(r"^DAH[A-Za-z0-9_-]{8}$")


def _canva_mcp_get_pages(design_id: str) -> list[dict] | None:
    """Call Canva MCP via Claude CLI to fetch the design page count.

    Falls back to a stub when the MCP is unreachable — caller decides
    how to interpret that. Returns None on any failure.
    """
    # We shell out to the `claude` CLI with a minimal prompt that asks
    # it to invoke the get-design tool and dump JSON. This avoids
    # re-implementing OAuth here; the skill already handles auth.
    prompt = (
        f"Use the Canva MCP get-design tool with design_id {design_id}. "
        "Return ONLY the JSON response, no commentary. "
        "If the design is not found, return {\"error\": \"not_found\"}."
    )
    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning("claude CLI unavailable: %s", exc)
        return None

    if result.returncode != 0:
        logger.warning("claude CLI exit %d: %s", result.returncode, result.stderr)
        return None

    # Try to parse the first JSON object from stdout. Claude CLI may
    # emit prose around it.
    stdout = result.stdout
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1:
        logger.warning("no JSON in claude output: %s", stdout[:200])
        return None
    try:
        return json.loads(stdout[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("invalid JSON in claude output")
        return None


def validate_constant_shape(design_id: str) -> tuple[bool, str]:
    """Validate the design ID matches the Canva format. Cheap, no I/O."""
    if not DESIGN_ID_RE.match(design_id):
        return False, (
            f"TEMPLATE_DESIGN_ID={design_id!r} does not match {DESIGN_ID_RE.pattern}. "
            "Expected an 11-char Canva design ID starting with 'DAH'."
        )
    return True, "constant shape OK"


def validate_live_structure(design_id: str) -> tuple[bool, dict]:
    """Empirical check via Canva MCP. Returns (ok, diagnostics)."""
    diag: dict = {"design_id": design_id}
    pages = _canva_mcp_get_pages(design_id)
    if pages is None:
        diag["status"] = "MCP_UNREACHABLE"
        diag["message"] = (
            "Could not reach Canva MCP. Run this script on a machine "
            "with Claude Desktop + Canva integration authenticated, OR "
            "manually verify the design has >= 18 richtexts (width>=30) "
            "across >= 11 pages, then paste the get-design-content "
            "output in the PR description."
        )
        return False, diag
    if pages.get("error") == "not_found":
        diag["status"] = "DESIGN_NOT_FOUND"
        diag["message"] = (
            f"Canva returned 'design not found' for {design_id}. "
            "The design may have been trashed or the ID is wrong."
        )
        return False, diag

    # Schema: `pages.pages` is a list of {page_id, page_number, ...}.
    page_list = pages.get("pages") or []
    diag["page_count"] = len(page_list)
    if len(page_list) < MIN_USABLE_PAGES:
        diag["status"] = "INSUFFICIENT_PAGES"
        diag["message"] = (
            f"Design has {len(page_list)} pages; the renderer requires "
            f"at least {MIN_USABLE_PAGES} (clamps `MAX_SLIDES_TEMPLATE`)."
        )
        return False, diag

    # Schema: `pages.richtexts` is a flat list across all pages.
    richtexts = pages.get("richtexts") or []
    eligible = [
        rt
        for rt in richtexts
        if (rt.get("containerElement", {}).get("dimension", {}).get("width", 0))
        >= MIN_RICHTEXT_WIDTH
    ]
    diag["richtext_total"] = len(richtexts)
    diag["richtext_eligible"] = len(eligible)
    if len(eligible) < MIN_RICHTEXTS:
        diag["status"] = "INSUFFICIENT_RICHTEXTS"
        diag["message"] = (
            f"Design has {len(eligible)} richtexts with width>={MIN_RICHTEXT_WIDTH}; "
            f"renderer requires at least {MIN_RICHTEXTS} (heading+body × 9 pages)."
        )
        return False, diag

    # Per-page distribution (informational): pages 1, 7, 9, 10, 11 may
    # legitimately have only 1 richtext each (cover + image-heavy slides).
    by_page: dict[int, int] = {}
    for rt in eligible:
        p = rt.get("page_index") or rt.get("containerElement", {}).get("page_index")
        if p is not None:
            by_page[p] = by_page.get(p, 0) + 1
    diag["richtexts_by_page"] = dict(sorted(by_page.items()))

    diag["status"] = "OK"
    diag["message"] = (
        f"Design {design_id} has {len(page_list)} pages and "
        f"{len(eligible)} eligible richtexts. Structurally compatible."
    )
    return True, diag


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--design-id",
        default=None,
        help=(
            "Override TEMPLATE_DESIGN_ID for this run. Use this to "
            "validate a candidate before changing the source constant."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (for CI / PR description paste).",
    )
    parser.add_argument(
        "--skip-live",
        action="store_true",
        help=(
            "Skip the live MCP check (only validate constant shape). "
            "Useful when running in a CI sandbox without Canva access."
        ),
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    design_id = args.design_id or TEMPLATE_DESIGN_ID
    out: dict = {"design_id": design_id, "checks": []}

    ok, msg = validate_constant_shape(design_id)
    out["checks"].append({"name": "constant_shape", "ok": ok, "message": msg})
    if not ok:
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"FAIL: {msg}")
        return 1

    if args.skip_live:
        out["checks"].append(
            {"name": "live_structure", "ok": True, "message": "skipped"}
        )
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"PASS: {design_id} (constant shape only, live skipped)")
        return 0

    live_ok, diag = validate_live_structure(design_id)
    out["checks"].append({"name": "live_structure", "ok": live_ok, **diag})
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"{'PASS' if live_ok else 'FAIL'}: {diag.get('message')}")
        if "richtexts_by_page" in diag:
            print("  per-page richtexts:", diag["richtexts_by_page"])
    return 0 if live_ok else 1


if __name__ == "__main__":
    sys.exit(main())
