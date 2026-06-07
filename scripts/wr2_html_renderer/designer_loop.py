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

logger = logging.getLogger("wr2.designer_loop")

# Where the text block sits on a slide, in fractional coords (matches the
# templates: bottom third). Tier-1 contrast/saliency sample here.
DEFAULT_TEXT_BOX = (0.05, 0.55, 0.95, 0.92)

# Contrast floor: brand targets AAA (7.0). Below this, a remedy lever fires.
CONTRAST_FLOOR = WCAG_AAA_NORMAL


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
    if is_hero and hero_path and hero_path.is_file():
        best_band, busyness = calmest_band(hero_path, n_bands=3)
        bottom_band = len(busyness) - 1
        if busyness[bottom_band] > min(busyness) * 1.5 and best_band != bottom_band:
            issues.append(
                f"text band (bottom, busyness {busyness[bottom_band]:.2f}) is busier "
                f"than calmest band {best_band} ({busyness[best_band]:.2f})"
            )
            # remedy IN PLACE: a heavier scrim + stroke so text survives the busy
            # bottom (no repositioning). Only add if not already proposed above.
            if not any(l.get("lever") == "scrim_opacity" for l in levers):
                levers.append({"lever": "scrim_opacity", "delta": +0.2, "reason": "text over busy band — darken in place"})
            if not any(l.get("lever") == "text_stroke" for l in levers):
                levers.append({"lever": "text_stroke", "reason": "text over busy band — outline in place"})

    return Critique(tier="legibility", passed=not issues, issues=issues, levers=levers, score=min(contrast / 21.0, 1.0))


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

        passes_cheap = geo.passed and leg.passed
        cheap_levers = geo.levers + leg.levers

        # track best by the cheap legibility score (higher contrast = better)
        score = leg.score or 0.0
        if score > best_score:
            best_score = score
            best_png = png_path

        iter_record = {
            "iter": it,
            "geometry": {"passed": geo.passed, "issues": geo.issues},
            "legibility": {"passed": leg.passed, "issues": leg.issues, "score": round(score, 3)},
            "levers_applied_before": dict(levers_acc),
        }

        if not passes_cheap:
            # apply the cheap remedy levers and re-render (no model cost)
            applied = _apply_levers(levers_acc, cheap_levers)
            iter_record["cheap_levers_pulled"] = applied
            if any(l.get("lever") == "rerender" for l in cheap_levers) and not applied:
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
            # vision wants changes → only act if at least one is a CSS-applicable
            # (legibility-in-place) lever. Non-CSS proposals (text_anchor,
            # rebalance_wrap, rerender) are composition signals we can't safely
            # auto-apply — so we stop and keep the best render rather than spin.
            proposed = {**levers_acc}
            applied = _apply_levers(proposed, vc.levers)
            if not applied:
                non_css = sorted({l.get("lever") for l in vc.levers})
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
                if bv.passed:
                    levers_acc = proposed
                    iter_record["vision_levers_pulled"] = applied
                else:
                    iter_record["vision_levers_rejected"] = "brand verifier blocked"
                    # the rejected change isn't kept; if we have no other lead,
                    # stop (don't re-propose the same blocked lever forever).
                    history.append(iter_record)
                    break
                history.append(iter_record)
                continue
            else:
                # no verifier but we have a CSS lever — apply it and re-render
                levers_acc = proposed
                iter_record["vision_levers_pulled_unverified"] = applied
                history.append(iter_record)
                continue
        else:
            # no vision: cheap tiers passed → done
            iter_record["verdict"] = "PASS (cheap only, vision disabled)"
            history.append(iter_record)
            return DesignerResult(final_png=png_path, iterations=it, converged=True, history=history)

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
