"""Designer loop: render → critique (cheap→expensive) → adjust levers → re-render.

The autonomous "human eye" loop. Per the operator decision (2026-06-07):
  - Autonomy: auto-fix within brand-verifier guardrails, max 3 iterations, then
    show the result.
  - Vision: Claude vision for the holistic judgment, but ONLY after the cheap
    deterministic gates run first (a clean slide spends ~$0).
  - Stop: pairwise "better than best-so-far?" + Legge 5 (loop stops at the PNG;
    a human publishes).

Cascade (cheap → expensive), short-circuits as soon as a tier says FAIL with an
actionable lever:
  Tier 0  geometry_lint           free      near-empty / overflow
  Tier 1  saliency + contrast     free      text on busy region / low contrast
  Tier 2  (VLM readability)       cheap-ish title legible at thumbnail scale
  Tier 3  Claude-vision critic    paid      balance / hierarchy / aesthetics
          + brand verifier        paid      palette/font/brief not drifted

This module owns Tier 0-1 + the controller + the lever→CSS mapping. Tier 2-3
(the vision calls) are pluggable callables so the loop is testable offline and
so the vision backend can be swapped. The default vision adapter shells out to
the `claude` CLI (OAuth, Law-5 compliant) — wired in claude_vision.py.

Reuse: the controller shape (render→QA→patch→re-render, max-3, escalation) mirrors
the production apps/backend-rag/backend/services/layout/layout_renderer.py loop,
adapted here to WR2 carousel slides + the cheap-signal cascade.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from .critic_signals import (
    WCAG_AAA_NORMAL,
    calmest_band,
    geometry_lint,
    text_region_contrast,
)
from .ocr_check import OcrVerdict, headline_legible, is_text_legibility_claim

logger = logging.getLogger("wr2.designer_loop")

# Where the text block sits on a slide, in fractional coords (matches the
# templates: bottom third). Tier-1 contrast/saliency sample here.
DEFAULT_TEXT_BOX = (0.05, 0.55, 0.95, 0.92)

# Contrast floor: brand targets AAA (7.0). Below this, a remedy lever fires.
CONTRAST_FLOOR = WCAG_AAA_NORMAL

# Pure-legibility levers: they only IMPROVE text legibility in place (darken the
# scrim, outline the text, down-step a font) and by construction cannot drift the
# brand (no palette / font-family / logo / composition change). When the ONLY
# levers a step proposes/applies are in this set, a brand_verifier rejection for
# a NON-legibility reason must NOT kill them — they're always safe to commit.
_LEGIBILITY_LEVERS = {"scrim_opacity", "text_stroke", "shrink_font", "grow_font"}

# Brand-inert levers: the legibility set PLUS rebalance_wrap. rebalance_wrap only
# re-wraps the headline TEXT (inserts a <br> at a balanced word boundary) — it
# never touches palette / font-family / logo / composition either, so it is just
# as brand-inert as the legibility levers. The deadlock override below keys off
# THIS set: if the only levers applied are brand-inert, a brand_verifier
# rejection for a non-inert reason (hierarchy/logo/palette) must NOT break the
# loop — the inert change is always safe to commit + keep iterating.
_BRAND_INERT_LEVERS = _LEGIBILITY_LEVERS | {"rebalance_wrap"}

# Composition-only levers: structural signals the loop CANNOT auto-apply (it has
# no rerender/hero-swap actuator). A vision reject whose only proposed lever is
# one of these is an EDITORIAL/composition debt, not a legibility/brand defect.
_COMPOSITION_LEVERS = {"rerender", "regen"}

# Substrings that mark a vision issue as a COMPOSITION/EDITORIAL critique (a
# weak/generic hero photo, awkward whitespace, "editorially weak", etc.) — the
# kind of thing only a rerender or a human hero-swap fixes, NOT a CSS lever.
#
# The vertical-balance / dead-zone family was MISSING: the Claude vision critic
# routinely describes a layout-balance debt as "dead zone at top", "wasted
# vertical real estate", "content sits in the upper portion leaving the lower
# third empty", "anchored to the floor", "unbalanced/crammed" — none of which
# matched the original markers. A single such unmatched claim flipped
# all_composition→False (see _classify_residual_issues), so the loop could
# neither accept (not all-composition) nor fix (no CSS lever) → it stalled to
# max_iters and emitted "did not converge", failing EVERY fresh draft for ~10
# days (last real `rendered` 2026-06-17). This is the W82 UNDER-match class:
# the taxonomy decided on a vocabulary that did not cover how the critic really
# names the defect. Phrases below are balance-specific and were innocence-tested
# NOT to swallow a real legibility/clip/brand HARD defect (has_hard always wins).
_COMPOSITION_CLAIM_MARKERS = (
    "photo", "hero", "image", "editorial", "generic", "stock", "weak",
    "spacing", "whitespace", "white space", "breathe", "composition",
    "crop", "scene", "imagery", "boring", "bland", "uninspired",
    # vertical-balance / dead-zone family (W82 under-match fix)
    "dead zone", "dead-zone", "dead space", "empty anthracite",
    "lower third", "upper third", "top third", "bottom third",
    "upper portion", "lower portion", "anchored to the floor",
    "real estate", "unbalanced", "imbalanced", "crammed", "cramped",
    "lopsided", "top-heavy", "bottom-heavy", "off-center", "off-centre",
    "leaving the lower", "leaving the upper",
    # gap / void / negative-space phrasings of the same vertical-balance debt
    "bottom gap", "top gap", "large gap", "substantial gap",
    "large void", "void before", "void above", "void below",
    "negative space", "large empty", "empty band", "empty strip",
)

# HARD-defect markers, matched on WORD BOUNDARY (not bare substring) — the
# W68/W72/W73 guard-over-match class. A claim is HARD only when it names an
# ACTUAL, CATEGORICAL, blocking defect (illegibility / clipping / real palette
# drift). NOTE: "wrap"/"stub"/"orphan" are NOT here (graded by _orphan_is_hard —
# a balanced multi-line wrap with a short tail is editorial rhythm); "color"
# alone is NOT here (an accent-color SUGGESTION is editorial — real palette drift
# needs a specific phrase, see _BRAND_DRIFT_MARKERS); legibility markers here are
# gated by "is this CONDITIONAL?" (see _CONDITIONAL_MARKERS) so a "may be
# illegible" hypothetical does not count.
_LEGIBILITY_HARD_MARKERS = (
    "illegible", "unreadable", "not readable", "cannot read", "can't read",
    "hard to read", "too small to read", "garbled", "smudged",
)
# Actual clipping/overflow of text out of its box (a real render defect).
_CLIP_HARD_MARKERS = (
    "clipped", "cut off", "cut-off", "overflows", "overflowing", "overflow",
    "outside the frame", "off the edge", "off-screen", "truncated", "overlaps",
    "overlapping",
)
# Real brand/palette drift — specific phrases, NOT a bare "color" (an
# "accent color" suggestion must stay editorial).
_BRAND_DRIFT_MARKERS = (
    "off-brand", "off brand", "wrong color", "wrong colour", "not in palette",
    "off-palette", "clashing", "non-brand color", "unbranded color",
    "wrong font", "serif font", "script font", "emoji",
)

# CONDITIONAL / hypothetical language — the defect is NOT actual, it is a risk or
# a "might". A claim that is ONLY conditional is editorial, never a HARD reject.
_CONDITIONAL_MARKERS = (
    "may", "might", "could", "would", "risk of", "at risk", "borderline",
    "approaching", "verges on", "bordering", "tends to", "in danger of",
    "potentially", "possibly", "if anything", "slightly",
)
# Editorial SUGGESTIONS / refinements (improvements, not defects) → never HARD.
_SUGGESTION_MARKERS = (
    "consider", "pop the", "popping", "would benefit", "could add", "could use",
    "accent color", "accent colour", "brand accent", "nice to", "nice-to-have",
    "suggest", "recommend", "elevate", "punch up", "punchier", "tighten up",
    "refine", "polish",
)
# A claim that explicitly affirms correctness ("the eyebrow is the CORRECT brand
# treatment but …") is the critic conceding the element is fine → not a HARD
# defect about that element.
_AFFIRMS_CORRECT_MARKERS = (
    "is correct", "are correct", "is the correct", "correct brand",
    "correct treatment", "is fine", "looks fine", "is good", "works well",
    "is solid", "reads well", "is legible",
)

# An issue that talks about an orphan / stub / wrap-rhythm / a line "sitting
# alone" / "N-line" complaint. After the pixel-wrap (which guarantees no line
# overflows), any of these on an ALREADY-re-wrapped slide is an editorial-rhythm
# critique, not a render defect — graded by _orphan_is_hard (negative-gating).
_ORPHAN_MARKERS = (
    "orphan", "stub", "alone on line", "alone on the line", "sits alone",
    "stranded", "dangling word", "widow", "wrap", "rewrap", "re-wrap",
    "line stub", "3-line", "4-line", "two-line", "three-line", "extra line",
    "short tail", "short last line", "ragged",
)

# A 1-WORD orphan is genuine illegibility (a lone word on its own line) → HARD.
_ONE_WORD_ORPHAN_MARKERS = (
    "single word", "single-word", "1 word", "one word", "one-word",
    "a lone word", "lone word", "just one word", "only one word", "1-word",
)


def _is_composition_only_lever(lever_names: set[str]) -> bool:
    """True iff every proposed lever is a composition-only signal (rerender/regen)."""
    return bool(lever_names) and lever_names <= _COMPOSITION_LEVERS


# Superscar #3 cure (4th over-match): identify a typographic orphan POSITIVELY,
# don't blacklist metaphors. A real orphan is a unit of running TEXT that wrapped
# or landed badly on a line. "decorative orphan", "logo sits alone", "image
# stranded", "divider stranded" reuse the same words for SPATIAL isolation of a
# layout element — they carry no text-unit, so they are composition, not orphans.

# A unit of running text that can wrap badly.
_ORPHAN_TEXT_UNITS = (
    "word", "line", "title", "headline", "heading", "sentence",
    "tail", "caption", "body copy",
)
# How that text unit failed to land — the "bad-landing" predicate.
_ORPHAN_BAD_LANDING = (
    "orphan", "stub", "widow", "stranded", "sits alone",
    "alone on line", "alone on the line", "dangling", "ragged",
    "short tail", "short last line", "wraps", "wrapped", "wrap",
    "rewrap", "re-wrap", "extra line", "line stub", "3-line", "4-line",
    "two-line", "three-line", "on its own line", "on the line",
)


def _is_typographic_orphan(low: str) -> bool:
    """Positive identification of a TEXT orphan (superscar #3 cure).

    True iff an explicit one-word marker is present, OR a text-unit token
    co-occurs with a bad-landing predicate. A bare bad-landing word with no
    text-unit ("decorative orphan", "logo sits alone", "divider stranded") is a
    composition metaphor, not a typographic orphan — keys on INTENT, not phrase.
    """
    if _contains_any_word(low, _ONE_WORD_ORPHAN_MARKERS):
        return True
    return (
        _contains_any_word(low, _ORPHAN_TEXT_UNITS)
        and _contains_any_word(low, _ORPHAN_BAD_LANDING)
    )


def _orphan_is_hard(low: str, *, rebalance_applied: bool) -> tuple[bool, bool]:
    """Grade an orphan / stub / wrap-rhythm claim. Returns (is_orphan_claim, is_hard).

    Negative-gating (the W73 lesson) keyed on whether the slide already re-wrapped:
      - a ONE-WORD orphan (a lone word on its own line) is genuine illegibility
        → HARD, always (even after a re-wrap; that IS a real defect).
      - if the slide ALREADY re-wrapped (_rebalance_wrap committed), the pixel
        wrap guarantees no line overflows, so any remaining orphan/stub/wrap/
        N-line/short-tail complaint is editorial RHYTHM → SOFT (default-pass).
      - if NO re-wrap was attempted, an orphan claim is a real unfixed defect
        → HARD (fail-safe toward the strict gate).
    """
    if not _is_typographic_orphan(low):
        return False, False  # not a TEXT orphan (or a composition metaphor)
    # a genuine 1-word orphan is a real defect regardless of re-wrap state.
    if _contains_any_word(low, _ONE_WORD_ORPHAN_MARKERS):
        return True, True
    # already re-wrapped → the remaining complaint is rhythm/editorial → SOFT.
    if rebalance_applied:
        return True, False
    # no re-wrap attempted yet → treat as a real, fixable defect → HARD.
    return True, True


def _contains_any_word(value: str, terms: tuple[str, ...]) -> bool:
    """Whole-word containment (mirrors openclaw_whatsapp_bridge._contains_any_word,
    the W73 word-boundary helper). A short marker like "wrap"/"color"/"legib"
    only matches on a word boundary, so it does NOT fire inside "rewrap"/
    "discolor"/"legible". Multi-word terms match as a contiguous phrase."""
    for term in terms:
        pattern = r"\b" + r"\s+".join(re.escape(part) for part in term.split())
        if re.search(pattern, value):
            return True
    return False


def _is_conditional_or_suggestion(low: str) -> bool:
    """True if the claim is hypothetical (may/might/could/risk-of/borderline) OR
    an editorial suggestion (consider/pop/accent-color/would-benefit) OR the
    critic affirms the element is actually correct. Such a claim is NEVER a HARD
    defect — it is a refinement/risk, not an actual blocking flaw."""
    return (
        _contains_any_word(low, _CONDITIONAL_MARKERS)
        or _contains_any_word(low, _SUGGESTION_MARKERS)
        or _contains_any_word(low, _AFFIRMS_CORRECT_MARKERS)
    )


def _claim_is_hard(low: str) -> bool:
    """True iff a claim names an ACTUAL, CATEGORICAL, blocking defect.

    Negative-gating (the W73 lesson "clobber only on a detectable WRONG signal,
    default passthrough"): a conditional/suggestion/affirms-correct claim returns
    False up front; only an unconditional illegibility / clipping / real
    palette-drift marker (word-boundary matched) returns True. Orphan/wrap claims
    are graded elsewhere (_orphan_is_hard).
    """
    if not low.strip():
        return False
    # Conditional or editorial-suggestion → not an actual defect.
    if _is_conditional_or_suggestion(low):
        return False
    return (
        _contains_any_word(low, _LEGIBILITY_HARD_MARKERS)
        or _contains_any_word(low, _CLIP_HARD_MARKERS)
        or _contains_any_word(low, _BRAND_DRIFT_MARKERS)
    )


# Synthetic categorical summaries appended by the Claude design critic
# (claude_vision.py: "vision: text not easily readable" / "vision: weak
# hierarchy" / "vision: unbalanced/crammed"). They are derived from the critic's
# OWN boolean flags, not atomic defects — the gradeable defects are in the
# model's free-text issues. Treated as NEUTRAL by the classifier (neither
# composition-accept nor hard-block) so a single summary marker does not veto an
# otherwise-SOFT residual (under-match, W68/W72/W73 class). NOTE: the exact
# prefix is "vision: " WITH a colon — the fail-closed "vision REQUIRED but
# unavailable…" string has no colon and is NOT skipped (it is a real block).
_VISION_SUMMARY_PREFIX = "vision: "


def _is_vision_summary_marker(low: str) -> bool:
    """True if a (already-lowercased) issue is a synthetic 'vision: …' summary.

    These are the critic's categorical meta-labels, not atomic defects. Robust
    to leading whitespace; matches only the colon-prefixed form so the
    fail-closed 'vision REQUIRED but unavailable…' (no colon) is NOT matched.
    """
    return low.lstrip().startswith(_VISION_SUMMARY_PREFIX)


def _classify_residual_issues(
    issues: list[str], *, rebalance_applied: bool = False
) -> tuple[bool, bool]:
    """Classify a list of vision issue strings.

    Returns (has_hard, all_composition):
      has_hard         — at least one issue is a legibility/brand HARD defect.
      all_composition  — every issue is a composition/editorial critique (and
                         there is at least one issue).
    A HARD marker always wins (an issue that is both is treated as hard).

    `rebalance_applied` (True when the slide already committed _rebalance_wrap)
    relaxes the orphan grading: a ≥2-word short tail on an already-balanced wrap
    is editorial rhythm (SOFT), while a 1-word orphan stays HARD (see
    _orphan_is_hard). When False (no re-wrap attempted) every orphan claim is
    treated as HARD.
    """
    has_hard = False
    all_composition = bool(issues)
    for raw in issues:
        low = (raw or "").lower()
        # Synthetic 'vision: …' summary markers are the critic's own meta-labels,
        # not atomic defects → NEUTRAL: skip without touching has_hard or
        # all_composition. The real severity comes from the atomic claims; if an
        # atomic legibility/brand defect coexists it still sets has_hard below.
        if _is_vision_summary_marker(low):
            continue
        is_orphan, orphan_hard = _orphan_is_hard(low, rebalance_applied=rebalance_applied)
        # ACTUAL hard defect (word-boundary, conditional/suggestion excluded) OR a
        # genuine 1-word orphan.
        hard = _claim_is_hard(low) or (is_orphan and orphan_hard)
        comp = any(m in low for m in _COMPOSITION_CLAIM_MARKERS)
        # editorial signals that count as composition (acceptable debt): a soft
        # orphan-rhythm tail, or a purely conditional/suggestion/affirms-correct
        # claim (W68/W72/W73: a refinement is not a defect).
        soft_orphan = is_orphan and not orphan_hard
        editorial = comp or soft_orphan or _is_conditional_or_suggestion(low)
        if hard:
            has_hard = True
            all_composition = False
        elif editorial:
            continue  # composition/editorial → keep all_composition
        else:
            # an issue we can't classify as composition is NOT safe to accept
            all_composition = False
    return has_hard, all_composition


@dataclass
class Critique:
    """One critique pass result: a verdict + the levers to pull next."""

    tier: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    levers: list[dict[str, Any]] = field(default_factory=list)  # ordered, actionable
    score: float | None = None  # optional 0..1 quality (for pairwise stop)
    # Structured boolean flags emitted directly by the Claude vision critic JSON
    # (claude_vision.py: readable / hierarchy_ok / balanced). These are the
    # MACHINE-READABLE verdict and are NOT reformulable by the LLM — using them to
    # decide "accept as composition debt?" replaces the brittle substring match on
    # the critic's free-text prose (W82 under-match: chasing prose phrasings is
    # whack-a-mole). None means "flag not provided" (older critics / cheap tiers)
    # → the classifier falls back to the prose heuristic.
    readable: bool | None = None
    hierarchy_ok: bool | None = None
    balanced: bool | None = None


class VisionCritic(Protocol):
    """A pluggable vision judgment. Implementations call a VLM (Claude/qwen)."""

    def __call__(self, png_path: Path, slide: dict[str, Any], context: dict[str, Any]) -> Critique: ...


class OcrCritic(Protocol):
    """A pluggable OCR round-trip check (default: ocr_check.headline_legible).

    Returns an OcrVerdict for whether `expected` reads back from the PNG. Kept
    pluggable so the loop is unit-testable offline (a stub can simulate
    legible/illegible without EasyOCR installed).
    """

    def __call__(self, png_path: Path, expected: str) -> OcrVerdict: ...


def _default_ocr_critic(png_path: Path, expected: str) -> OcrVerdict:
    return headline_legible(png_path, expected)


# ---------------------------------------------------------------------------
# Tier 0-1: cheap deterministic critics (no model call)
# ---------------------------------------------------------------------------

def critic_geometry(png_path: Path, slide: dict[str, Any]) -> Critique:
    """Tier 0 — gross structural failures from the PNG (free)."""
    gl = geometry_lint(png_path)
    issues: list[str] = list(gl.flags)
    levers: list[dict[str, Any]] = []
    if gl.near_empty:
        # near-empty usually means the hero didn't paint or text is missing —
        # the loop can't fix this with a CSS nudge; flag for re-render/regen.
        levers.append({"lever": "rerender", "reason": "near-empty render"})
    if gl.bottom_ink_ratio > 0.25:
        levers.append({"lever": "shrink_font", "target": "body", "reason": "bottom overflow"})
    return Critique(tier="geometry", passed=not issues, issues=issues, levers=levers)


def critic_legibility(
    png_path: Path,
    slide: dict[str, Any],
    *,
    text_box: tuple[float, float, float, float] = DEFAULT_TEXT_BOX,
    fg_rgb: tuple[int, int, int] = (255, 255, 255),
    is_hero: bool = False,
    hero_path: Path | None = None,
) -> Critique:
    """Tier 1 — measured contrast + (for hero slides) saliency placement (free).

    Levers, in remedy-ladder order (cheapest visual change first):
      1. if contrast < floor on a hero: increase scrim opacity (darken behind text)
      2. if still low: add/strengthen text stroke
      3. if the text band sits on the busiest part of the photo: move text to the
         calmest band
    On flat-background (non-hero) slides, contrast is usually fine (white on
    antracite = 13.4); this mostly guards hero slides.
    """
    # `passed` is decided by HARD issues only (measured contrast — the direct
    # legibility signal). Saliency-placement is a SOFT note: see why below.
    hard_issues: list[str] = []
    soft_issues: list[str] = []
    levers: list[dict[str, Any]] = []

    contrast = text_region_contrast(png_path, text_box, fg_rgb)
    if contrast < CONTRAST_FLOOR:
        hard_issues.append(f"text contrast {contrast:.1f} < AAA {CONTRAST_FLOOR:.0f}")
        # remedy ladder
        levers.append({"lever": "scrim_opacity", "delta": +0.15, "reason": f"contrast {contrast:.1f}"})
        levers.append({"lever": "text_stroke", "weight": "increase", "reason": "fallback legibility"})

    # saliency placement — only meaningful for hero slides with a photo.
    # We DETECT "text sits on the busiest band" but do NOT try to fix it by
    # repositioning the text (that broke the cover in E2E 2026-06-07).
    #
    # Crucially, busyness is measured on the RAW hero image, BEFORE the scrim
    # CSS overlay is composited — so stronger scrim does NOT lower the measured
    # busyness, and the only real remedy (text_anchor reposition) is disabled.
    # If this were a HARD gate it would loop to render_failed with no applicable
    # fix even when the text is perfectly legible (2026-06-12 SCAR: slide 3 of
    # draft 3e2c2923 — contrast ~12.6 ≫ AAA floor 7.0, yet blocked forever).
    # So: when contrast PASSES, the text IS legible and a busy background band
    # is a SOFT composition note (logged, visible, never blocking). It only
    # reinforces the lever ladder when contrast ALSO failed (then it's HARD).
    if is_hero and hero_path and hero_path.is_file():
        best_band, busyness = calmest_band(hero_path, n_bands=3)
        bottom_band = len(busyness) - 1
        if busyness[bottom_band] > min(busyness) * 1.5 and best_band != bottom_band:
            note = (
                f"text band (bottom, busyness {busyness[bottom_band]:.2f}) is busier "
                f"than calmest band {best_band} ({busyness[best_band]:.2f})"
            )
            if hard_issues:
                # contrast already failed → this is part of the hard problem;
                # reinforce the in-place remedy ladder (no repositioning).
                hard_issues.append(note)
                if not any(lev.get("lever") == "scrim_opacity" for lev in levers):
                    levers.append({"lever": "scrim_opacity", "delta": +0.2, "reason": "text over busy band — darken in place"})
                if not any(lev.get("lever") == "text_stroke" for lev in levers):
                    levers.append({"lever": "text_stroke", "reason": "text over busy band — outline in place"})
            else:
                # contrast PASSES → text is legible → busy background is a soft
                # composition note (scrim mitigates it at render time; the
                # measure can't see the scrim, and reposition is disabled).
                soft_issues.append(note + " (composition note — text legible, scrim mitigates)")

    return Critique(
        tier="legibility",
        passed=not hard_issues,
        issues=hard_issues + soft_issues,
        levers=levers,
        score=min(contrast / 21.0, 1.0),
    )


def critic_ocr(
    png_path: Path,
    slide: dict[str, Any],
    ocr_critic: OcrCritic | None,
) -> Critique:
    """Tier 1.5 — OCR round-trip: does the headline read back from the PNG?

    The deterministic anti-hallucination signal. If the title can't be OCR'd
    verbatim it's clipped/garbled/too-low-contrast → fail with in-place remedy
    levers (shrink heading, then deepen scrim). NEVER proposes repositioning.
    Passes (no-op) if there's no headline, no OCR critic, or OCR degraded.
    """
    headline = (slide.get("headline") or slide.get("heading") or "").strip()
    if not headline or ocr_critic is None:
        return Critique(tier="ocr", passed=True, score=None)

    verdict = ocr_critic(png_path, headline)
    if verdict.degraded:
        # OCR engine unavailable → don't block (graceful degradation)
        return Critique(tier="ocr", passed=True, issues=["ocr degraded — skipped"], score=None)

    if verdict.legible:
        return Critique(tier="ocr", passed=True, score=verdict.score)

    issues = [
        f"headline not readable in render (ocr score {verdict.score:.2f}; "
        f"read '{verdict.ocr_text[:80]}')"
    ]
    # remedy ladder, in place only: shrink the heading to fit, then darken behind
    levers = [
        {"lever": "shrink_font", "target": "heading", "reason": f"headline OCR {verdict.score:.2f} — shrink to fit"},
        {"lever": "scrim_opacity", "delta": +0.15, "reason": "headline OCR low — darken behind"},
    ]
    return Critique(tier="ocr", passed=False, issues=issues, levers=levers, score=verdict.score)


# ---------------------------------------------------------------------------
# The controller
# ---------------------------------------------------------------------------

@dataclass
class DesignerResult:
    final_png: Path | None
    iterations: int
    converged: bool
    history: list[dict[str, Any]] = field(default_factory=list)
    escalated: bool = False
    reason: str = ""
    # FIX#4: the slide is legible + brand-clean but the vision critic still flags
    # a purely EDITORIAL/composition residual (weak hero, generic photo, spacing)
    # that no CSS lever can fix. Per operator decision (2026-06-10) we ACCEPT the
    # best render rather than burn iterations / fail — the debt is recorded here
    # (and logged at WARNING) so it stays visible, never silently dropped.
    accepted_with_composition_debt: bool = False
    composition_debt: list[str] = field(default_factory=list)


async def run_designer_loop(
    *,
    slide: dict[str, Any],
    render_fn: Callable[[dict[str, Any], Path], Any],
    out_dir: Path,
    is_hero: bool = False,
    hero_path: Path | None = None,
    vision_critic: VisionCritic | None = None,
    brand_verifier: VisionCritic | None = None,
    ocr_critic: OcrCritic | None = _default_ocr_critic,
    max_iters: int = 3,
    use_vision: bool = True,
) -> DesignerResult:
    """Run the cheap→expensive critique/adjust loop on ONE slide.

    render_fn(slide_with_levers, png_path) renders the slide applying any
    accumulated levers (the renderer/composer side owns lever→CSS). It is async.

    The loop:
      1. render
      2. Tier 0 geometry → if fail with actionable lever, apply + re-render
      3. Tier 1 legibility (contrast + saliency) → same
      4. Tier 3 vision critic (Claude) ONLY if cheap tiers passed AND use_vision
         → apply levers, but a brand_verifier must approve the change (autonomy
         guardrail). Pairwise: keep the best-scoring render.
      5. stop at max_iters or when nothing improves; Legge 5 → return PNG.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    history: list[dict[str, Any]] = []
    levers_acc: dict[str, Any] = {}
    best_png: Path | None = None
    best_score = -1.0
    escalated = False
    # last vision-reject residual that was committed-and-continued (incremental
    # lever applied). Used ONLY at the max_iters exit: if after exhausting the
    # iteration budget the remembered residual is all-SOFT, accept the best
    # render as composition debt instead of a max_iters reject (deterministic
    # convergence on a healthy render rather than a ~1-in-N coin flip).
    last_reject_issues: list[str] | None = None
    last_reject_rebalance_applied = False
    last_reject_png: Path | None = None

    for it in range(1, max_iters + 1):
        png_path = out_dir / f"iter-{it:02d}.png"
        slide_with_levers = {**slide, "_levers": dict(levers_acc)}
        await render_fn(slide_with_levers, png_path)

        if not png_path.is_file():
            history.append({"iter": it, "error": "render produced no PNG"})
            break

        # --- Tier 0: geometry (free) ---
        geo = critic_geometry(png_path, slide)
        # --- Tier 1: legibility (free) ---
        leg = critic_legibility(
            png_path, slide, is_hero=is_hero, hero_path=hero_path,
            fg_rgb=(255, 255, 255),
        )
        # --- Tier 1.5: OCR round-trip (cheap, deterministic) ---
        # Does the headline actually read back from the rendered PNG? Catches
        # clipped/garbled titles that contrast/geometry miss (e.g. the broken
        # top-clipped cover whose bottom-box contrast scored a false-high). Only
        # runs if we know the expected headline.
        ocr = critic_ocr(png_path, slide, ocr_critic)

        passes_cheap = geo.passed and leg.passed and ocr.passed
        cheap_levers = geo.levers + leg.levers + ocr.levers

        # track best by the cheap legibility score (higher contrast = better)
        score = leg.score or 0.0
        if score > best_score:
            best_score = score
            best_png = png_path

        iter_record = {
            "iter": it,
            "geometry": {"passed": geo.passed, "issues": geo.issues},
            "legibility": {"passed": leg.passed, "issues": leg.issues, "score": round(score, 3)},
            "ocr": {"passed": ocr.passed, "issues": ocr.issues, "score": ocr.score},
            "levers_applied_before": dict(levers_acc),
        }

        if not passes_cheap:
            # apply the cheap remedy levers and re-render (no model cost)
            applied = _apply_levers(levers_acc, cheap_levers)
            iter_record["cheap_levers_pulled"] = applied
            if any(lev.get("lever") == "rerender" for lev in cheap_levers) and not applied:
                # nothing CSS-fixable (near-empty) → escalate
                escalated = True
                iter_record["escalated"] = "near-empty, not CSS-fixable"
                history.append(iter_record)
                break
            history.append(iter_record)
            continue  # re-render with new levers

        # --- Tier 3: vision (paid) — only when cheap tiers pass and enabled ---
        if use_vision and vision_critic is not None:
            vc = vision_critic(png_path, slide, {"iteration": it})
            iter_record["vision"] = {"passed": vc.passed, "issues": vc.issues, "levers": vc.levers}
            if vc.passed:
                iter_record["verdict"] = "PASS (cheap + vision)"
                history.append(iter_record)
                best_png = png_path  # vision-approved render is the keeper
                return DesignerResult(
                    final_png=best_png, iterations=it, converged=True, history=history
                )
            # vision wants changes → only act if at least one is an applicable
            # lever (legibility-in-place scrim/stroke/shrink, or rebalance_wrap
            # which re-wraps the headline text). Pure structural proposals
            # (rerender/regen only) are composition signals we can't safely
            # auto-apply — so we stop and keep the best render rather than spin.
            proposed = {**levers_acc}
            applied = _apply_levers(proposed, vc.levers)
            # NO-OP DETECTION: a lever that does not change the accumulated lever
            # state produces the IDENTICAL render (e.g. rebalance_wrap re-proposed
            # on an already-optimally-wrapped title — _balance_headline is
            # idempotent). It is NOT progress, so it must not keep the loop
            # spinning to max_iters. "applied" levers that leave proposed ==
            # levers_acc are reclassified as non-progressive.
            made_progress = bool(applied) and proposed != levers_acc
            if not made_progress:
                # No render-changing lever to pull (none applicable, OR the
                # applied levers are idempotent no-ops). The cheap tiers (geometry
                # + legibility + OCR) already PASSED to reach here, so the slide
                # is LEGIBLE. FIX#4 (operator decision 2026-06-10): if the
                # residual vision reject is PURELY editorial/composition (weak/
                # generic hero, awkward spacing, a no-op rebalance, rerender-only)
                # — i.e. no HARD legibility or brand claim — accept the best
                # render as composition DEBT instead of spinning out the
                # iterations to a render_failed. A legibility defect (an orphan
                # word, a clipped/garbled title) is NOT debt — it stays a hard
                # reject so FIX#2b must actually fix it.
                proposed_levers = {lev.get("lever") for lev in vc.levers}
                non_css = sorted(proposed_levers)
                # the slide already attempted the headline re-wrap if a prior
                # iteration committed _rebalance_wrap into levers_acc — this
                # relaxes the orphan grading from "any orphan = HARD" to
                # "1-word orphan = HARD, >=2-word balanced tail = editorial".
                rebalance_applied = bool(levers_acc.get("_rebalance_wrap"))
                has_hard, all_composition = _classify_residual_issues(
                    list(vc.issues), rebalance_applied=rebalance_applied
                )
                # STRUCTURAL accept gate (W82 cure): prefer the critic's own
                # boolean verdict over reverse-engineering its prose. The critic
                # JSON emits readable / hierarchy_ok / balanced directly; those are
                # not reformulable, so they end the prose whack-a-mole. Rule:
                #   - readable is False  → a real legibility defect → stays HARD
                #     (never accept unreadable text as "debt").
                #   - readable is True AND the prose carries no HARD defect that the
                #     flags don't see (orphan / clip / brand-drift, still graded by
                #     _classify) → a residual that is ONLY balance/hierarchy is
                #     editorial debt → composition-accept, regardless of how the
                #     critic phrased the dead-zone/gap/hierarchy complaint.
                # Flags are None on cheap tiers / older critics → fall back to the
                # prose classification untouched.
                if vc.readable is not None:
                    if vc.readable is False:
                        has_hard = True
                        all_composition = False
                    elif not has_hard:
                        # text is readable and no orphan/clip/brand HARD in the
                        # prose → any remaining balance/hierarchy residual is debt.
                        all_composition = True
                # The render cannot be improved when: no applicable lever, OR the
                # only proposed levers are composition-only (rerender/regen), OR
                # the applied levers were idempotent no-ops (already at optimum).
                no_op_levers = bool(applied) and proposed == levers_acc
                comp_levers_only = (
                    (not vc.levers)
                    or _is_composition_only_lever(proposed_levers)
                    or no_op_levers
                )
                if no_op_levers:
                    iter_record["noop_levers"] = sorted(
                        {lev.get("lever") for lev in applied}
                    )
                if not has_hard and all_composition and comp_levers_only:
                    debt = list(vc.issues)
                    logger.warning(
                        "designer-loop: accepting best render with composition debt "
                        "(editorial residual, not CSS-fixable): %s", debt,
                    )
                    iter_record["verdict"] = (
                        "vision flagged EDITORIAL-only residual "
                        f"(levers {non_css}, issues {debt}) — accepting best render "
                        "as composition debt (legible + brand-clean)"
                    )
                    iter_record["accepted_with_composition_debt"] = debt
                    history.append(iter_record)
                    return DesignerResult(
                        final_png=best_png or png_path,
                        iterations=it,
                        converged=True,
                        history=history,
                        accepted_with_composition_debt=True,
                        composition_debt=debt,
                        reason="accepted_with_composition_debt",
                    )
                # Otherwise there is a real (hard) residual we cannot CSS-fix →
                # keep the best render but do NOT mark converged (gate stays strict).
                # Log it — symmetric to the composition-debt accept above; without
                # this a render_failed leaves zero trace of WHY the gate rejected.
                logger.warning(
                    "designer-loop: HARD residual not auto-fixable (levers %s) — "
                    "keeping best, NOT converged: %s",
                    non_css,
                    list(vc.issues),
                )
                iter_record["verdict"] = (
                    f"vision flagged hard residual {non_css} / {list(vc.issues)} "
                    "(not auto-fixable) — keeping best, not converged"
                )
                iter_record["escalated_levers"] = non_css
                history.append(iter_record)
                break
            if brand_verifier is not None:
                # render a trial to verify the applied change didn't drift brand
                trial_png = out_dir / f"iter-{it:02d}-trial.png"
                await render_fn({**slide, "_levers": proposed}, trial_png)
                bv = brand_verifier(trial_png, slide, {"check": "brand"})
                iter_record["brand_verify"] = {"passed": bv.passed, "issues": bv.issues}
                effective_pass = bv.passed
                if not bv.passed:
                    # ANTI-HALLUCINATION: if the ONLY reasons the verifier blocked
                    # are text-legibility claims (headline garbled/clipped/cut),
                    # adjudicate with OCR — a deterministic read of the trial PNG.
                    # If OCR can read the headline verbatim, the verifier
                    # hallucinated (it does this: "5 RULES" vs "3 RULES") → override.
                    # Palette/font/logo claims are NOT overridable (not OCR's domain).
                    text_claims = [i for i in bv.issues if is_text_legibility_claim(i)]
                    other_claims = [i for i in bv.issues if not is_text_legibility_claim(i)]
                    headline = (slide.get("headline") or slide.get("heading") or "").strip()
                    if text_claims and not other_claims and headline and ocr_critic is not None:
                        ov = ocr_critic(trial_png, headline)
                        iter_record["brand_verify_ocr_adjudication"] = {
                            "ocr_score": ov.score, "legible": ov.legible,
                            "degraded": ov.degraded, "ocr_text": ov.ocr_text[:80],
                        }
                        if ov.legible and not ov.degraded:
                            effective_pass = True
                            iter_record["brand_verify_overridden_by_ocr"] = (
                                f"verifier claimed text broken {text_claims} but OCR "
                                f"read headline (score {ov.score:.2f}) — hallucination overridden"
                            )
                # BRAND-INERT DEADLOCK UNBLOCK: the brand-inert levers
                # (scrim_opacity / text_stroke / shrink_font + rebalance_wrap)
                # cannot drift the brand — legibility-in-place + headline re-wrap
                # only. If the ONLY levers applied this step are in that set, a
                # verifier rejection for a non-inert reason (hierarchy/logo/
                # palette) must NOT kill them (and must NOT kill future inert
                # steps). Commit + continue. We break only when a brand-driftable
                # lever was in play AND the verifier (after OCR adjudication)
                # still says no.
                applied_names = {lev.get("lever") for lev in applied}
                inert_only = bool(applied_names) and applied_names <= _BRAND_INERT_LEVERS
                if not effective_pass and inert_only:
                    effective_pass = True
                    iter_record["brand_verify_inert_override"] = (
                        f"verifier blocked but applied levers {sorted(applied_names)} "
                        "are brand-inert (legibility-in-place + re-wrap) — committed in place"
                    )
                if effective_pass:
                    levers_acc = proposed
                    iter_record["vision_levers_pulled"] = applied
                    # remember this reject's residual for a possible max_iters
                    # accept-as-debt (the vision still rejected; we only applied
                    # an incremental lever and continued).
                    last_reject_issues = list(vc.issues)
                    last_reject_rebalance_applied = bool(proposed.get("_rebalance_wrap"))
                    last_reject_png = png_path
                    history.append(iter_record)
                    continue
                else:
                    iter_record["vision_levers_rejected"] = "brand verifier blocked"
                    # the rejected change isn't kept; if we have no other lead,
                    # stop (don't re-propose the same blocked lever forever).
                    history.append(iter_record)
                    break
            else:
                # no verifier but we have a CSS lever — apply it and re-render
                levers_acc = proposed
                iter_record["vision_levers_pulled_unverified"] = applied
                last_reject_issues = list(vc.issues)
                last_reject_rebalance_applied = bool(proposed.get("_rebalance_wrap"))
                last_reject_png = png_path
                history.append(iter_record)
                continue
        else:
            # no vision path. Default: cheap tiers passing => converge (historical).
            # WR2_VISION_REQUIRED=1 (v4 condition E / GO#3 c5): FAIL-CLOSED — if vision
            # was supposed to run (use_vision) but no vision_critic is wired, or vision
            # is disabled, the slide must NOT converge on cheap tiers alone.
            if os.environ.get("WR2_VISION_REQUIRED") == "1" and (not use_vision or vision_critic is None):
                iter_record["verdict"] = "FAIL (vision required but not available)"
                history.append(iter_record)
                return DesignerResult(
                    final_png=png_path,
                    iterations=it,
                    converged=False,
                    history=history,
                    reason="vision_required_but_unavailable",
                )
            iter_record["verdict"] = "PASS (cheap only, vision disabled)"
            history.append(iter_record)
            return DesignerResult(final_png=png_path, iterations=it, converged=True, history=history)

    # ACCEPT-BEST AT MAX_ITERS (operator decision 2026-06-10): the loop exhausted
    # its iteration budget while the vision kept proposing incremental editorial
    # levers (made_progress=True every iter), so it never reached the
    # made_progress=False accept branch. If the LAST committed reject's residual
    # is all-SOFT (not has_hard AND all_composition), pushing further does not
    # improve a render that is already legible + brand-clean — accept it as
    # composition debt. A HARD residual at the last iteration is NOT debt and
    # falls through to the strict converged=False reject below.
    if last_reject_issues is not None and not escalated:
        has_hard, all_composition = _classify_residual_issues(
            list(last_reject_issues),
            rebalance_applied=last_reject_rebalance_applied,
        )
        if not has_hard and all_composition:
            debt = list(last_reject_issues)
            logger.warning(
                "designer-loop: max_iters reached with all-SOFT residual — accepting "
                "best render as composition debt (editorial, not CSS-fixable): %s", debt,
            )
            return DesignerResult(
                final_png=best_png or last_reject_png,
                iterations=len(history),
                converged=True,
                history=history,
                accepted_with_composition_debt=True,
                composition_debt=debt,
                reason="accepted_with_composition_debt (max_iters, soft residual)",
            )

    return DesignerResult(
        final_png=best_png,
        iterations=len(history),
        converged=False,
        history=history,
        escalated=escalated,
        reason="max_iters reached or not CSS-fixable" if not escalated else "escalated",
    )


def _apply_levers(acc: dict[str, Any], levers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fold a list of lever dicts into the accumulated lever state.

    Returns the levers actually applied. Levers NOT folded here are handled by
    the controller as escalation signals, not CSS:
      - "rerender" / "regen"  → structural; controller re-renders or escalates
      - "text_anchor"         → REMOVED entirely (E2E 2026-06-07: absolute-
        repositioning broke the cover layout + caused a false-high legibility
        score). No longer in the lever vocabulary.
    CSS / text-in-place levers the composer honors in slide["_levers"] (all
    legibility-in-place, never position/color/font):
      scrim_opacity:   float  (added darkening behind text; 0..1, clamped)
      text_stroke:     bool   (stronger outline)
      shrink_<elem>:   int    (step counter; elem = body|heading|subhead)
      grow_<elem>:     int    (step counter; elem = subhead|body — composer
                               clamps toward a thumbnail-legible min, capped)
      _rebalance_wrap: bool   (composer re-wraps the headline into balanced
                               lines via <br> — text content only, no box move)
    """
    applied: list[dict[str, Any]] = []
    for lev in levers:
        name = lev.get("lever")
        if name == "scrim_opacity":
            acc["scrim_opacity"] = min(1.0, acc.get("scrim_opacity", 0.6) + float(lev.get("delta", 0.15)))
            applied.append(lev)
        elif name == "text_stroke":
            acc["text_stroke"] = True
            applied.append(lev)
        elif name == "shrink_font":
            key = f"shrink_{lev.get('target', 'body')}"
            acc[key] = acc.get(key, 0) + 1
            applied.append(lev)
        elif name == "grow_font":
            # symmetric partner of shrink_font: step up a too-small element toward
            # a thumbnail-legible minimum. The composer clamps the grown size to a
            # per-element legible floor + an anti-overflow cap, so this only ever
            # IMPROVES legibility in place (never palette/font-family/box).
            key = f"grow_{lev.get('target', 'subhead')}"
            acc[key] = acc.get(key, 0) + 1
            applied.append(lev)
        elif name == "rebalance_wrap":
            # Re-wrap the headline into balanced lines (no orphan on the last
            # line). Legibility-in-place: the composer inserts <br> in the
            # headline text only — it never moves/colors/resizes the box, so it
            # cannot drift the brand. Marked as applied so the controller does
            # not treat a rebalance proposal as a non-CSS escalation signal.
            acc["_rebalance_wrap"] = True
            applied.append(lev)
        # "rerender" / "regen" are NOT CSS levers: structural/composition signals
        # the controller handles. ("text_anchor" was removed entirely — see note.)
    return applied
