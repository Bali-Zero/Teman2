"""Claude-vision adapters for the designer loop (the "human eye").

Per operator decision (2026-06-07): use Claude vision for the holistic design
judgment. Called ONLY after the cheap deterministic gates pass (so spend stays
low). Two adapters:

  - claude_design_critic: judges the rendered slide like an editorial designer
    (legibility-over-photo, hierarchy, balance, wrapping, "does it breathe")
    and returns actionable levers the loop can pull.
  - claude_brand_verifier: a SEPARATE gate that checks a proposed change did NOT
    drift the brand (palette, single font, no banned patterns, headline intact).
    This is the autonomy guardrail — the critic proposes, the verifier vetoes.

Both shell out to the `claude` CLI with CLAUDE_CODE_OAUTH_TOKEN (MAX-plan quota,
Law-5 compliant — NEVER the paid SDK/api_key). The CLI reads the PNG by path
(verified 2026-06-07: it genuinely sees the image). Structured output via
--json-schema so parsing is robust.

These operate on brand ASSETS (rendered slides), not client PII → cloud Claude
is permitted (CLAUDE.md cost rule: PII boundary, not a flat cloud ban).

Env flags:
  WR2_VISION_REQUIRED — when truthy (1/true/yes/on), the design critic fails
    CLOSED on a CLI outage (returns passed=False) instead of soft-passing. Set
    this in the LIVE/wired pipeline so a Claude outage can never make the loop
    accept an unjudged slide. Unset (default) keeps fail-open for offline
    cheap-tier testing. The brand verifier ALWAYS fails closed regardless.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from .designer_loop import Critique

logger = logging.getLogger("wr2.claude_vision")

# The lever vocabulary the critic may return — kept in sync with
# designer_loop._apply_levers so the loop can act on them.
_ALLOWED_LEVERS = {
    "scrim_opacity",   # darken behind text (delta)
    "text_stroke",     # stronger outline
    "shrink_font",     # target: heading|body
    "text_anchor",     # to_band: 0..2
    "rebalance_wrap",  # rewrap title for balanced line lengths
    "rerender",        # structural (controller handles)
}

_CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "passes": {"type": "boolean", "description": "true if the slide is publish-quality as-is"},
        "readable": {"type": "boolean", "description": "is ALL text easily readable (incl. at thumbnail size)?"},
        "hierarchy_ok": {"type": "boolean", "description": "clear visual hierarchy (title dominates, sub/body subordinate)?"},
        "balanced": {"type": "boolean", "description": "composition balanced, not crammed, breathes?"},
        "issues": {"type": "array", "items": {"type": "string"}, "description": "concrete problems, designer voice"},
        "levers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lever": {"type": "string", "enum": sorted(_ALLOWED_LEVERS)},
                    "target": {"type": "string"},
                    "delta": {"type": "number"},
                    "to_band": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["lever", "reason"],
            },
        },
        "score": {"type": "number", "description": "overall visual quality 0..1"},
    },
    "required": ["passes", "readable", "hierarchy_ok", "balanced", "issues", "levers", "score"],
}

_CRITIC_PROMPT = """You are a senior editorial designer reviewing ONE Instagram carousel slide for Bali Zero (a regulatory/legal-info brand). Look at the image at: {png_path}

Judge it like a designer who cares about clarity and restraint (think NYT/FT/Bloomberg editorial, NOT generic marketing):
1. READABLE: is every word easy to read — including when shrunk to a phone thumbnail? Text over a photo must stay crisp.
2. HIERARCHY: does the title dominate, with sub-headline and body clearly subordinate? Do key numbers stand out?
3. BALANCED: does it breathe, or is text crammed/floating awkwardly? Is the photo (if any) used well — does it dominate the cover?

Brand rules you must respect (do NOT propose violating these): anthracite/white/yellow/red palette only, Montserrat font, logo present, no emoji, regulatory citations verbatim.

If it is publish-quality, set passes=true. Otherwise list concrete issues and propose levers from this exact set:
- scrim_opacity (delta: +0.1..+0.3) — darken behind text when contrast is weak over a photo
- text_stroke — add/strengthen outline on text over a photo
- text_anchor (to_band: 0=top,1=middle,2=bottom) — move the text block to a calmer part of the photo
- shrink_font (target: heading|body) — when text overflows or is too dense
- rebalance_wrap — rewrap the title so line lengths are balanced (avoid one long line + one tiny orphan)
- rerender — structural problem a small tweak can't fix

Be specific and honest. score = your overall 0..1 quality."""

_VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "brand_ok": {"type": "boolean", "description": "true if brand is intact after the change"},
        "violations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["brand_ok", "violations"],
}

_VERIFIER_PROMPT = """You are a brand compliance checker for Bali Zero. Look at the image at: {png_path}

Verify ONLY these brand invariants (do not judge aesthetics):
- Colors are only anthracite/black background, white text, yellow (#F4C430) accents, red (#C8102E) for logo/critical. NO other colors in text/UI zones (a photo may have natural colors).
- Single font family throughout (Montserrat-like geometric sans). No serif/script/display fonts.
- The Bali Zero logo is present.
- No emoji in title/body.
- The headline text is intact and not garbled/cut off.

Set brand_ok=true only if ALL hold. List any violations."""

_CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")


def _vision_required() -> bool:
    """Whether the design critic must fail CLOSED when the CLI is unavailable.

    Default (unset / "0" / "false") → fail OPEN (today's behavior): a CLI
    outage soft-passes so the cheap-tier offline tests don't block. When
    `WR2_VISION_REQUIRED` is truthy (live/wired mode), a CLI down/timeout/
    non-JSON makes the critic return passed=False ("vision_required") so the
    loop never accepts a slide just because Claude was down (panel fix C).
    """
    return os.environ.get("WR2_VISION_REQUIRED", "").strip().lower() in ("1", "true", "yes", "on")


def _run_claude_json(prompt: str, schema: dict[str, Any], *, timeout_s: int = 120) -> dict[str, Any] | None:
    """Call the claude CLI with a JSON schema, return the parsed object or None.

    Strips ANTHROPIC_API_KEY from the env (defense-in-depth: force OAuth path,
    never the paid endpoint — CLAUDE.md hard rule).
    """
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    cmd = [
        _CLAUDE_BIN, "--print",
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        prompt,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        logger.warning("claude vision call timed out after %ss", timeout_s)
        return None
    except OSError as exc:
        # CLI binary missing / not executable / launch failure — this IS "CLI
        # down". Return None so the caller's fail-open/closed policy applies
        # (fix C: never crash the loop; in vision_required mode this becomes a
        # fail-closed Critique upstream).
        logger.warning("claude vision call could not launch (%s): %s", _CLAUDE_BIN, exc)
        return None
    if proc.returncode != 0:
        logger.warning("claude vision call failed rc=%s err=%s", proc.returncode, proc.stderr[:300])
        return None
    out = proc.stdout.strip()
    if not out:
        return None
    try:
        envelope = json.loads(out)
    except json.JSONDecodeError:
        logger.warning("claude vision: stdout not JSON: %s", out[:200])
        return None
    # CLI json envelope (verified 2026-06-07): when --json-schema is used the
    # schema-conformant object lives in `structured_output` (a dict); `result`
    # is the human-prose narration. Prefer structured_output.
    so = envelope.get("structured_output")
    if isinstance(so, dict):
        return so
    # Fallback: some versions/paths may put JSON (as a string) in `result`.
    result = envelope.get("result")
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            logger.warning("claude vision: no structured_output and result not JSON: %s", result[:200])
            return None
    logger.warning("claude vision: no structured_output / result in envelope")
    return None


def claude_design_critic(png_path: Path, slide: dict[str, Any], context: dict[str, Any]) -> Critique:
    """Claude-vision design critic (Tier 3). Returns a Critique with levers."""
    obj = _run_claude_json(_CRITIC_PROMPT.format(png_path=png_path), _CRITIC_SCHEMA)
    if obj is None:
        if _vision_required():
            # live/wired mode: a CLI outage must NOT soft-pass — fail CLOSED so
            # the loop never accepts a slide just because Claude was down.
            return Critique(
                tier="vision",
                passed=False,
                issues=["vision unavailable — failing closed (vision_required)"],
                levers=[],
            )
        # offline/cheap-tier mode: don't block the pipeline; soft-pass with a note
        return Critique(tier="vision", passed=True, issues=["vision unavailable — skipped"], levers=[])
    levers = [lev for lev in obj.get("levers", []) if lev.get("lever") in _ALLOWED_LEVERS]
    issues = list(obj.get("issues", []))
    if not obj.get("readable", True):
        issues.append("vision: text not easily readable")
    if not obj.get("hierarchy_ok", True):
        issues.append("vision: weak hierarchy")
    if not obj.get("balanced", True):
        issues.append("vision: unbalanced/crammed")
    return Critique(
        tier="vision",
        passed=bool(obj.get("passes", False)),
        issues=issues,
        levers=levers,
        score=float(obj.get("score", 0.0)),
    )


def claude_brand_verifier(png_path: Path, slide: dict[str, Any], context: dict[str, Any]) -> Critique:
    """Claude-vision brand verifier (autonomy guardrail). passed=brand intact."""
    obj = _run_claude_json(_VERIFIER_PROMPT.format(png_path=png_path), _VERIFIER_SCHEMA)
    if obj is None:
        # if the verifier can't run, FAIL CLOSED — don't let an unverified change
        # through (the critic's autonomy must be gated).
        return Critique(tier="brand", passed=False, issues=["brand verifier unavailable — failing closed"])
    return Critique(
        tier="brand",
        passed=bool(obj.get("brand_ok", False)),
        issues=list(obj.get("violations", [])),
    )
