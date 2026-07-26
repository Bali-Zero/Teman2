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
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from .designer_loop import Critique

logger = logging.getLogger("wr2.claude_vision")


def _run_process_group(
    cmd: list[str],
    *,
    timeout: float,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a CLI in its own session and reap its full process tree on timeout."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        else:
            time.sleep(0.1)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)


class VisionTransient(Exception):
    """A vision call failed for a TRANSIENT infra reason (quota window, endpoint
    timeout) — NOT a real outage and NOT a defect of the slide. The draft is
    recoverable next tick, so the apply-worker must release it WITHOUT burning a
    circuit-breaker attempt. Deliberately NOT a subclass of RuntimeError so the
    worker's generic `except RuntimeError` (a real transient render failure,
    which DOES burn an attempt) cannot swallow it."""


class VisionRateLimited(VisionTransient):
    """Transient: HTTP 429 / session limit."""


class VisionTimeout(VisionTransient):
    """Transient: the vision CLI call exceeded its wall-clock budget. A timeout
    is almost always endpoint latency/overload (verified 2026-06-12: intermittent
    120s timeouts during an Anthropic congestion window, the SAME run sometimes
    completing), not a property of the slide — so it must not burn an attempt and
    fail a healthy draft. The draft retries next tick when latency recovers."""


# A 429 surfaces either as a JSON envelope with api_error_status==429 / is_error
# + a session-limit message, or (older CLI paths) as rc!=0 with the limit text
# on stdout/stderr. Bound the numeric status so KBLI codes such as 42911 do not
# rotate accounts accidentally.
_RATE_LIMIT_RE = re.compile(
    r"session limit|rate.?limit|usage limit|weekly limit|quota|exhausted|"
    r"too many requests|hit your limit|(?<![\d/])429(?![\d/])",
    re.IGNORECASE,
)
_AUTH_FAILURE_RE = re.compile(
    r"authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token|"
    r"unauthori[sz]ed|(?<![\d/])401(?![\d/])",
    re.IGNORECASE,
)
_OAUTH_SCRUB_KEYS = frozenset({
    "GOOGLE_APPLICATION_CREDENTIALS",
    "CLOUD_ML_REGION",
    "GOOGLE_API_KEY",
})
_OAUTH_SCRUB_PREFIXES = (
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_USE_",
    "ANTHROPIC_",
    "AWS_",
    "VERTEX_AI_",
    "OPENAI_",
    "OPENROUTER_",
    "GEMINI_",
    "DEEPSEEK_",
    "TOGETHER_",
    "FIREWORKS_",
    "MISTRAL_",
    "COHERE_",
    "GROQ_",
    "XAI_",
    "PERPLEXITY_",
)
_STDOUT_RATE_DIAGNOSTIC = re.compile(
    r"\s*(?:(?:error|fatal)(?:\s*[:\-]\s*|\s+))?"
    r"(?:session limit|rate.?limit(?:ed| exceeded)?|usage limit(?: reached| exceeded)?|"
    r"weekly limit(?: reached| exceeded)?|quota (?:exceeded|exhausted)|exhausted|"
    r"too many requests|hit your limit|429(?:\s+too many requests)?)"
    r"(?:[\s:.,;\-].{0,240})?\s*",
    re.IGNORECASE | re.DOTALL,
)
_STDOUT_AUTH_DIAGNOSTIC = re.compile(
    r"\s*(?:(?:error|fatal)(?:\s*[:\-]\s*|\s+))?"
    r"(?:authentication (?:failed|required|expired)|auth required|login required|"
    r"please (?:log in|login)|not logged in|not authenticated|"
    r"invalid[_ ](?:grant|token)|token[_ ]revoked|refresh_token(?:_reused)?|"
    r"unauthori[sz]ed|401(?: unauthori[sz]ed)?)"
    r"(?:[\s:.,;\-].{0,240})?\s*",
    re.IGNORECASE | re.DOTALL,
)


def _oauth_cli_env(source: dict[str, str], token: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in source.items()
        if key not in _OAUTH_SCRUB_KEYS
        and not key.startswith(_OAUTH_SCRUB_PREFIXES)
    }
    if token:
        env["CLAUDE_CODE_OAUTH_TOKEN"] = token
    else:
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
    return env


def _vision_retry_reason(
    envelope: dict[str, Any] | None,
    stdout: str,
    stderr: str,
) -> str | None:
    """Classify retryable diagnostics while preserving valid vision output."""
    if _RATE_LIMIT_RE.search(stderr or ""):
        return "rate_limit"
    if _AUTH_FAILURE_RE.search(stderr or ""):
        return "auth"
    if isinstance(envelope, dict):
        if envelope.get("api_error_status") == 429:
            return "rate_limit"
        envelope_type = str(
            envelope.get("type") or envelope.get("status") or ""
        ).lower()
        if envelope.get("is_error") or envelope_type in {
            "error",
            "failed",
            "failure",
        } or (
            envelope_type == "result"
            and envelope.get("subtype") not in (None, "success")
        ):
            serialized = json.dumps(envelope, ensure_ascii=False)
            if _RATE_LIMIT_RE.search(serialized):
                return "rate_limit"
            if _AUTH_FAILURE_RE.search(serialized):
                return "auth"
    if _STDOUT_RATE_DIAGNOSTIC.fullmatch(stdout or ""):
        return "rate_limit"
    if _STDOUT_AUTH_DIAGNOSTIC.fullmatch(stdout or ""):
        return "auth"
    return None


def _detect_rate_limit(
    envelope: dict[str, Any] | None,
    combined_text: str,
    returncode: int,
) -> bool:
    """Compatibility wrapper retained for the focused regression suite."""
    del returncode
    return (
        _vision_retry_reason(envelope, combined_text, "")
        == "rate_limit"
    )

# The lever vocabulary the critic may return — kept in sync with
# designer_loop._apply_levers so the loop can act on them.
_ALLOWED_LEVERS = {
    "scrim_opacity",   # darken behind text (delta)
    "text_stroke",     # stronger outline
    "shrink_font",     # target: heading|body|subhead
    "grow_font",       # target: subhead|body — toward a thumbnail-legible min
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

Judge it like a designer who cares about clarity and restraint (think NYT/FT/Bloomberg editorial, NOT generic marketing).

VIEWING CONTEXT (critical — judge legibility at the RIGHT scale): an Instagram
carousel is READ at full size (~1080px) once the viewer opens it. Only the
HEADLINE/hook needs to survive the small grid thumbnail (~110px) to earn the
tap. The kicker/eyebrow, sub-headline and body are SECONDARY context read after
the open — judge them at full resolution, NOT at thumbnail scale. Do NOT fail a
slide because a kicker/subhead/body would be small at 110px: only fail if it is
unreadable at full open size, or if the dominant HEADLINE itself is illegible.

1. READABLE: at full open size, is every word easy to read (crisp contrast over
   any photo)? Separately: does the HEADLINE still read at thumbnail scale?
   (Secondary text is NOT required to read at thumbnail.)
2. HIERARCHY: does the title dominate, with sub-headline and body clearly subordinate? Do key numbers stand out?
3. BALANCED: does it breathe, or is text crammed/floating awkwardly? Is the photo (if any) used well — does it dominate the cover? A 3-line title with a slightly shorter last line is acceptable if it reads cleanly; only flag wrap as a problem when it produces a true one-word orphan or a jarring shape. IMPORTANT — generous margin is NOT dead-air when it is FRAMED: a text-only editorial slide (no hero photo) that places a short yellow rule above the heading AND a thin full-width hairline rule just above the footer logo is using deliberate NYT/FT editorial restraint. The empty band between the body and that bottom hairline is intentional margin, not a layout bug — judge such a slide balanced=true as long as the content block reads cleanly and is bracketed top (yellow rule) and bottom (hairline above logo). Only set balanced=false for UNFRAMED voids (text floating in empty space with nothing bracketing the lower edge), genuinely crammed text, or a block pushed hard to one edge. Do NOT propose 'rerender' merely because a framed editorial slide has breathing room below the text.

CALIBRATION RUBRIC (make the three judgments concrete, not "by feel" — count markers, do not vibe-check):

hierarchy_ok = false only if 2+ of these fire (a single one is a nudge, not a fail):
  - the headline does NOT clearly dominate — sub-headline or body competes for the eye at the same weight
  - a key number/date that should anchor the slide is buried in body text at body weight instead of standing out
  - three or more text elements share one visual weight so the eye has no entry point
  - the eyebrow/kicker is larger or heavier than the sub-headline below it (inverted ladder)
If only 1 fires, hierarchy_ok = true (it reads with a clear-enough top-down order).

balanced = false only if 2+ of these fire (the framed-margin exception above always wins first):
  - text is genuinely crammed — lines touch or nearly touch, no gutter between blocks
  - a block is shoved hard against one edge with a large UNFRAMED void opposite (nothing bracketing that void)
  - the photo (on a hero slide) is decorative filler that adds no meaning, or is cropped so the subject is lost
  - competing focal points fight for attention with no clear primary
A framed editorial slide with breathing room below the text is balanced=true (see the IMPORTANT note above).

readable is a HARD signal, not a rubric: set readable=false whenever ANY headline/body word is genuinely hard to read at full open size (low contrast, too small, occluded) — one real illegibility is enough. Do NOT soften readable with the 2+ rule; it is the one dimension where a single defect fails.

Anchor these to the brand's reference: NYT/FT/Bloomberg editorial restraint (one dominant headline, quiet secondary text, generous FRAMED margin), NOT dense marketing where everything shouts. When unsure between a nudge and a fail, prefer passing — a slightly-imperfect but legible, on-brand slide is publish-quality; reserve false verdicts for defects a reader would actually notice.

Brand rules you must respect (do NOT propose violating these): anthracite/white/yellow/red palette only, Montserrat font, logo present, no emoji, regulatory citations verbatim.

If it is publish-quality, set passes=true. Otherwise list concrete issues and propose levers from this exact set:
- scrim_opacity (delta: +0.1..+0.3) — darken behind text when contrast is weak over a photo
- text_stroke — add/strengthen outline on text over a photo
- shrink_font (target: heading|body) — when text overflows or is too dense
- grow_font (target: subhead|body) — increase the font size of a text element when it is too small to read AT FULL OPEN SIZE (not merely small at thumbnail scale; does NOT change palette/logo/layout)
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


def _vision_token_chain(env: dict[str, str]) -> list[tuple[str, str]]:
    """Return OAuth seats in a stable order without duplicating credentials.

    The universal fleet order is numbered seats 1→2→3→4→5, then the legacy
    bare token for backward compatibility, followed by the CLI keychain login.
    """
    chain: list[tuple[str, str]] = []
    for index in (1, 2, 3, 4, 5):
        token = env.get(f"CLAUDE_CODE_OAUTH_TOKEN_{index}", "").strip()
        if token and not any(existing == token for _, existing in chain):
            chain.append((f"token_{index}", token))
    bare = env.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
    if bare and not any(existing == bare for _, existing in chain):
        chain.append(("token_legacy", bare))
    chain.append(("keychain", ""))
    return chain


def _run_claude_json(prompt: str, schema: dict[str, Any], *, timeout_s: int | None = None) -> dict[str, Any] | None:
    """Call the claude CLI with a JSON schema, return the parsed object or None.

    Strips ANTHROPIC_API_KEY from the env (defense-in-depth: force OAuth path,
    never the paid endpoint — CLAUDE.md hard rule).

    Raises VisionTimeout (transient) when the call exceeds the wall-clock budget
    (default 180s, override WR2_VISION_TIMEOUT_S) and VisionRateLimited on a 429.
    """
    if timeout_s is None:
        timeout_s = int(os.environ.get("WR2_VISION_TIMEOUT_S", "180"))
    base_env = dict(os.environ)
    # Pin the vision model (default sonnet: vision-capable + solid editorial
    # judgment, lighter/cheaper than opus so it neither burns the MAX-plan quota
    # window nor trips the 120s timeout). Configurable without a code change.
    model = os.environ.get("WR2_VISION_MODEL", "claude-sonnet-5")
    cmd = [
        _CLAUDE_BIN, "--print",
        "--model", model,
        "--output-format", "json",
        "--json-schema", json.dumps(schema),
        prompt,
    ]
    saw_rate_limit = False
    saw_timeout = False
    deadline = time.monotonic() + timeout_s

    chain = _vision_token_chain(base_env)
    for position, (label, token) in enumerate(chain):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        attempt_timeout = max(0.1, remaining / (len(chain) - position))

        try:
            proc = _run_process_group(
                cmd,
                env=_oauth_cli_env(base_env, token),
                timeout=attempt_timeout,
            )
        except subprocess.TimeoutExpired:
            logger.warning(
                "claude vision %s timed out — trying next account",
                label,
            )
            saw_timeout = True
            continue

        # Parse the stdout envelope up front so a 429 can be told apart from a
        # real failure even when the CLI exits rc!=0.
        out = proc.stdout.strip()
        envelope: dict[str, Any] | None = None
        if out:
            try:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    envelope = parsed
            except json.JSONDecodeError:
                envelope = None
        retry_reason = _vision_retry_reason(envelope, proc.stdout, proc.stderr)
        if retry_reason == "rate_limit":
            saw_rate_limit = True
            logger.warning(
                "claude vision %s rate-limited — trying next account", label
            )
            continue
        if retry_reason == "auth":
            logger.warning(
                "claude vision %s authentication failed — trying next account",
                label,
            )
            continue
        if proc.returncode != 0:
            logger.warning(
                "claude vision call failed rc=%s",
                proc.returncode,
            )
            return None
        if not out:
            logger.warning(
                "claude vision %s returned empty output — trying next account",
                label,
            )
            continue
        if envelope is None:
            logger.warning("claude vision: stdout not JSON: %s", out[:200])
            return None

        # CLI json envelope: schema output lives in `structured_output`.
        structured = envelope.get("structured_output")
        if isinstance(structured, dict):
            return structured
        result = envelope.get("result")
        if isinstance(result, dict):
            return result
        if isinstance(result, str):
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                logger.warning(
                    "claude vision: no structured_output and result not JSON: %s",
                    result[:200],
                )
                return None
        logger.warning("claude vision: no structured_output / result in envelope")
        return None

    if saw_rate_limit:
        raise VisionRateLimited("claude vision rate-limited across all OAuth accounts")
    if saw_timeout:
        raise VisionTimeout(f"vision call exceeded its {timeout_s}s global budget")
    return None


def claude_design_critic(png_path: Path, slide: dict[str, Any], context: dict[str, Any]) -> Critique:
    """Claude-vision design critic (Tier 3). Returns a Critique with levers."""
    obj = _run_claude_json(_CRITIC_PROMPT.format(png_path=png_path), _CRITIC_SCHEMA)
    if obj is None:
        # vision unavailable. Default: soft-pass (don't block — historical behavior).
        # WR2_VISION_REQUIRED=1 (v4 condition E / GO#3 c1): FAIL-CLOSED — a carousel
        # must NOT be marked rendered when the vision critic could not actually run.
        if os.environ.get("WR2_VISION_REQUIRED") == "1":
            return Critique(
                tier="vision",
                passed=False,
                issues=["vision REQUIRED but unavailable — fail-closed (WR2_VISION_REQUIRED=1)"],
                levers=[],
            )
        return Critique(tier="vision", passed=True, issues=["vision unavailable — skipped"], levers=[])
    levers = [
        lever
        for lever in obj.get("levers", [])
        if lever.get("lever") in _ALLOWED_LEVERS
    ]
    issues = list(obj.get("issues", []))
    # Read the structured boolean verdict the critic JSON already emits. These are
    # the authoritative, non-reformulable signal the designer-loop uses to decide
    # accept-as-composition-debt (see designer_loop._classify_residual_issues).
    readable = bool(obj.get("readable", True))
    hierarchy_ok = bool(obj.get("hierarchy_ok", True))
    balanced = bool(obj.get("balanced", True))
    # Keep the synthetic prose markers too — they remain useful as human-readable
    # explanations and as a fallback for any path that still reads issues only.
    if not readable:
        issues.append("vision: text not easily readable")
    if not hierarchy_ok:
        issues.append("vision: weak hierarchy")
    if not balanced:
        issues.append("vision: unbalanced/crammed")
    return Critique(
        tier="vision",
        passed=bool(obj.get("passes", False)),
        issues=issues,
        levers=levers,
        score=float(obj.get("score", 0.0)),
        readable=readable,
        hierarchy_ok=hierarchy_ok,
        balanced=balanced,
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
