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

# Absolute "calm enough" floor for the text band's (glyph-masked, background)
# busyness, on the 0..1 saliency scale (NB-1). The busy-band gate is otherwise a
# PURELY RELATIVE check (bottom > calmest * 1.5); when the photo has a near-zero
# calmest band, `calmest * 1.5` is ~0 and the relative check can NEVER be
# satisfied no matter how heavily the scrim darkens the text band — the exact
# deadlock the re-panel flagged. This floor makes the gate satisfiable: once the
# scrim brings the text band below it, the band is absolutely calm enough for
# text and the issue clears even if the photo elsewhere is calmer still. Tuned
# against rendered samples: a hostile bright/textured band reads ~0.15-0.25; a
# well-scrimmed band reads ~0.03-0.05; 0.08 sits cleanly between.
BUSY_BAND_ABS_FLOOR = 0.08


@dataclass
class Critique:
    """One critique pass result: a verdict + the levers to pull next."""

    tier: str
    passed: bool
    issues: list[str] = field(default_factory=list)
    levers: list[dict[str, Any]] = field(default_factory=list)  # ordered, actionable
    score: float | None = None  # optional 0..1 quality (for pairwise stop)


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


def _brand_block_overridable_by_ocr(
    bv: Critique,
    png_path: Path,
    slide: dict[str, Any],
    ocr_critic: OcrCritic | None,
) -> tuple[bool, dict[str, Any]]:
    """Adjudicate a brand-verifier BLOCK against OCR (anti-hallucination).

    The brand verifier (a VLM) hallucinates text specifics ("5 RULES" vs
    "3 RULES", phantom garbling). If the ONLY reasons it blocked are PURE
    text-legibility claims (garbled/clipped/cut/illegible) AND a deterministic
    OCR read of `png_path` finds the headline verbatim, the verifier
    hallucinated → the block is overridable. Palette/font/logo claims (or any
    claim carrying a negative keyword per `is_text_legibility_claim`) are NOT
    OCR's domain and are never overridable.

    Returns (overridable, detail) where detail records the adjudication for the
    iteration history. overridable is False whenever bv actually passed (no
    block to override), there are non-text claims, no headline, or OCR can't
    confirm legibility (degraded counts as cannot-confirm → fail closed).
    """
    if bv.passed:
        return False, {}
    text_claims = [i for i in bv.issues if is_text_legibility_claim(i)]
    other_claims = [i for i in bv.issues if not is_text_legibility_claim(i)]
    headline = (slide.get("headline") or slide.get("heading") or "").strip()
    if not (text_claims and not other_claims and headline and ocr_critic is not None):
        return False, {}
    ov = ocr_critic(png_path, headline)
    detail = {
        "brand_verify_ocr_adjudication": {
            "ocr_score": ov.score, "legible": ov.legible,
            "degraded": ov.degraded, "ocr_text": ov.ocr_text[:80],
        }
    }
    if ov.legible and not ov.degraded:
        detail["brand_verify_overridden_by_ocr"] = (
            f"verifier claimed text broken {text_claims} but OCR "
            f"read headline (score {ov.score:.2f}) — hallucination overridden"
        )
        return True, detail
    return False, detail


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
    issues: list[str] = []
    levers: list[dict[str, Any]] = []

    contrast = text_region_contrast(png_path, text_box, fg_rgb)
    if contrast < CONTRAST_FLOOR:
        issues.append(f"text contrast {contrast:.1f} < AAA {CONTRAST_FLOOR:.0f}")
        # remedy ladder
        levers.append({"lever": "scrim_opacity", "delta": +0.15, "reason": f"contrast {contrast:.1f}"})
        levers.append({"lever": "text_stroke", "weight": "increase", "reason": "fallback legibility"})

    # saliency placement — only meaningful for hero slides with a photo.
    # We DETECT "text sits on the busiest band" but do NOT try to fix it by
    # repositioning the text (that broke the cover in E2E 2026-06-07). Instead
    # the remedy is stronger scrim/stroke (keep text where the template put it
    # but make it survive the busy region); if that's already maxed, it's a
    # composition problem → rerender signal, not a CSS nudge.
    #
    # Measure busyness on the RENDERED png (post-scrim composite), NOT the raw
    # hero (panel fix B). On the raw hero the bottom band never changes across
    # iterations, so the scrim/stroke levers could never satisfy the check →
    # Tier-1 deadlocked and starved the paid vision tier. Measuring the render
    # couples the lever to the metric: a heavier scrim darkens the text band,
    # lowering its luminance variance → the busyness check actually improves.
    #
    # NB-1 (re-panel): measuring the glyph-INCLUSIVE render re-introduced the
    # deadlock by another route — the burned-in WHITE headline dominates the
    # bottom band's variance, and the scrim darkens the background but cannot
    # remove the letters, so the bottom band stays "busy" forever. We pass the
    # text box so calmest_band reads a BACKGROUND-only saliency map (glyphs
    # neutralized) for the text region: now a heavier scrim genuinely lowers the
    # bottom-band busyness the gate reads, so the lever can satisfy it.
    if is_hero:
        best_band, busyness = calmest_band(png_path, n_bands=3, text_mask_box=text_box)
        bottom_band = len(busyness) - 1
        # Gate is satisfiable ONLY because of the absolute floor: a band that is
        # absolutely calm enough (< BUSY_BAND_ABS_FLOOR) clears even when another
        # band is relatively calmer (min→0 makes the relative term unsatisfiable).
        # So the issue fires only when the text band is BOTH absolutely busy AND
        # relatively busier than the calmest band — and the scrim lever can drive
        # it under the floor (NB-1).
        if (
            busyness[bottom_band] > BUSY_BAND_ABS_FLOOR
            and busyness[bottom_band] > min(busyness) * 1.5
            and best_band != bottom_band
        ):
            issues.append(
                f"text band (bottom, busyness {busyness[bottom_band]:.2f}) is busier "
                f"than calmest band {best_band} ({busyness[best_band]:.2f})"
            )
            # remedy IN PLACE: a heavier scrim + stroke so text survives the busy
            # bottom (no repositioning). Only add if not already proposed above.
            if not any(lev.get("lever") == "scrim_opacity" for lev in levers):
                levers.append({"lever": "scrim_opacity", "delta": +0.2, "reason": "text over busy band — darken in place"})
            if not any(lev.get("lever") == "text_stroke" for lev in levers):
                levers.append({"lever": "text_stroke", "reason": "text over busy band — outline in place"})

    return Critique(tier="legibility", passed=not issues, issues=issues, levers=levers, score=min(contrast / 21.0, 1.0))


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
    # best_png: the highest cheap-legibility-score render — DIAGNOSTIC ONLY. It is
    # updated BEFORE any vision/brand verification, so it MUST NOT be what the loop
    # returns as final_png: when the brand verifier blocks a render, best_png may
    # be that very brand-rejected image (NB-4). It is kept only for the history.
    best_png: Path | None = None
    best_score = -1.0
    # best_verified_png: the render that final_png returns. It is set ONLY when a
    # render has passed brand verification (or when no brand_verifier is in play —
    # cheap-only mode, by design no brand gate there). INVARIANT: final_png is
    # either a brand-approved render, or None if none was ever produced. This is
    # what stops the break-and-return-best path from FAILING OPEN — a consumer
    # that reads final_png while ignoring `converged` can never get a
    # brand-rejected image (NB-4).
    best_verified_png: Path | None = None
    escalated = False

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

        # track best by the cheap legibility score (higher contrast = better).
        # DIAGNOSTIC ONLY — this never feeds final_png (NB-4); it is surfaced in the
        # history so the cheap-score winner is auditable independently of which
        # render was brand-approved.
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
            "cheap_best_png": str(best_png) if best_png else None,
            "cheap_best_score": round(best_score, 3),
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
                # A vision-PASS is the CANDIDATE — gate it on the brand verifier
                # too (the autonomy guardrail must also veto vision-*approved*
                # slides, not only vision-*proposed changes*). The current render
                # IS the candidate, so verify png_path directly (no trial).
                if brand_verifier is not None:
                    bv = brand_verifier(png_path, slide, {"check": "brand"})
                    iter_record["brand_verify"] = {"passed": bv.passed, "issues": bv.issues}
                    effective_pass = bv.passed
                    if not bv.passed:
                        # OCR may override ONLY a pure text-legibility hallucination.
                        overridable, detail = _brand_block_overridable_by_ocr(
                            bv, png_path, slide, ocr_critic
                        )
                        iter_record.update(detail)
                        effective_pass = overridable
                    if not effective_pass:
                        # brand verifier blocked (and OCR did not clear it) →
                        # treat as a brand block: do NOT converge. Keep the best
                        # render and stop (don't spin on an unfixable block).
                        iter_record["verdict"] = "vision PASS but brand verifier blocked — keeping best"
                        history.append(iter_record)
                        break
                iter_record["verdict"] = "PASS (cheap + vision + brand)"
                history.append(iter_record)
                # Reaching here means EITHER no brand_verifier was configured (no
                # brand gate by design) OR the brand verifier passed / was OCR-
                # overridden. Either way this render is brand-approved → it is the
                # verified keeper that final_png returns (NB-4).
                best_verified_png = png_path
                return DesignerResult(
                    final_png=best_verified_png, iterations=it, converged=True, history=history
                )
            # vision wants changes → only act if at least one is a CSS-applicable
            # (legibility-in-place) lever. Non-CSS proposals (text_anchor,
            # rebalance_wrap, rerender) are composition signals we can't safely
            # auto-apply — so we stop and keep the best render rather than spin.
            proposed = {**levers_acc}
            applied = _apply_levers(proposed, vc.levers)
            if not applied:
                non_css = sorted({lev.get("lever") for lev in vc.levers})
                iter_record["verdict"] = (
                    f"vision flagged but only non-CSS levers {non_css} "
                    "(composition, not auto-fixable) — keeping best"
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
                    # ANTI-HALLUCINATION: adjudicate a pure text-legibility block
                    # against a deterministic OCR read of the trial PNG (shared
                    # helper). Palette/font/logo claims are NOT overridable.
                    overridable, detail = _brand_block_overridable_by_ocr(
                        bv, trial_png, slide, ocr_critic
                    )
                    iter_record.update(detail)
                    effective_pass = overridable
                if effective_pass:
                    levers_acc = proposed
                    iter_record["vision_levers_pulled"] = applied
                    # The trial render passed brand verification (vision wanted the
                    # change but brand approved it). Capture it as the verified
                    # keeper so that if the loop later runs out of iterations we
                    # return a genuinely brand-approved image, never a rejected one
                    # (NB-4). Vision hasn't converged on it yet, so we still
                    # continue iterating — this only protects the fallthrough.
                    best_verified_png = trial_png
                    history.append(iter_record)
                    continue
                else:
                    iter_record["vision_levers_rejected"] = "brand verifier blocked"
                    # the rejected change isn't kept; if we have no other lead,
                    # stop (don't re-propose the same blocked lever forever). Do
                    # NOT touch best_verified_png — the rejected trial must never
                    # become final_png (NB-4).
                    history.append(iter_record)
                    break
            else:
                # no verifier but we have a CSS lever — apply it and re-render
                levers_acc = proposed
                iter_record["vision_levers_pulled_unverified"] = applied
                history.append(iter_record)
                continue
        else:
            # no vision: cheap tiers passed → done. Cheap-only mode has NO brand
            # verifier in play (by design — the brand gate is a vision-tier
            # check), so png_path here is the legitimate verified result: there is
            # no brand verdict that could have rejected it. (NB-4 invariant clause
            # b: "a render that passed brand verification OR had no brand_verifier
            # configured".)
            iter_record["verdict"] = "PASS (cheap only, vision disabled)"
            history.append(iter_record)
            return DesignerResult(final_png=png_path, iterations=it, converged=True, history=history)

    # Fallthrough (max_iters reached, escalated, or a brand-block break). final_png
    # is best_verified_png — a brand-APPROVED render from some iteration, or None if
    # the brand verifier blocked EVERY render. NEVER best_png (the cheap-score
    # render, which may be the brand-rejected image). This is the NB-4 fix: the
    # break-and-return path no longer fails open.
    return DesignerResult(
        final_png=best_verified_png,
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
      - "text_anchor"         → REMOVED as a CSS lever (E2E 2026-06-07: absolute-
        repositioning broke the cover layout + caused a false-high legibility
        score). Treated as a rerender/composition signal instead.
    CSS levers the composer honors in slide["_levers"] (all legibility-in-place,
    never position/color/font):
      scrim_opacity: float    (added darkening behind text; 0..1, clamped)
      text_stroke:   bool     (stronger outline)
      shrink_<elem>: int      (step counter; elem = body|heading|subhead)
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
        # "text_anchor", "rebalance_wrap", "rerender", "regen" are NOT CSS levers:
        # they're composition/structural signals the controller handles.
    return applied
