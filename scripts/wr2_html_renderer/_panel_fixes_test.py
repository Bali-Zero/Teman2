"""Unit tests for the 5 BLOCKING panel fixes (Go/No-Go 2026-06-07).

Offline + deterministic: NO Playwright, NO Claude CLI, NO EasyOCR. The vision
critic, brand verifier and OCR critic are all STUBS, and `render_fn` writes a
synthetic PNG with PIL so the cheap deterministic tiers (geometry/contrast) run
on a real file. Covers the pure-logic fixes (A/C/D) end-to-end and B/E at the
signature/behavioral level.

Run:
    PYTHONPATH=<wt>/scripts <wt>/apps/backend-rag/.venv/bin/python \
        -m pytest scripts/wr2_html_renderer/_panel_fixes_test.py -q
or directly:
    PYTHONPATH=<wt>/scripts <wt>/apps/backend-rag/.venv/bin/python \
        scripts/wr2_html_renderer/_panel_fixes_test.py
"""

from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

from .designer_loop import (
    Critique,
    DesignerResult,
    _brand_block_overridable_by_ocr,
    critic_legibility,
    run_designer_loop,
)
from .ocr_check import OcrVerdict, is_text_legibility_claim

# A representative cover slide (matches the composer schema).
COVER_SLIDE = {
    "index": 1,
    "slide_type": "cover",
    "is_cover": True,
    "is_hero_image": True,
    "headline": "YOUR KITAP IS VALID. 3 RULES CHANGED.",
    "subhead": "PERMENKUMHAM 22/2023",
    "body": "Body copy here.",
}


# ---------------------------------------------------------------------------
# stubs / helpers
# ---------------------------------------------------------------------------

def _write_clean_png(png_path: Path) -> None:
    """Write a synthetic slide PNG that PASSES the cheap tiers.

    White text-band region over a dark top: high contrast (white fg vs dark
    mean), real variance (not near-empty), no bottom-edge overflow.
    """
    from PIL import Image  # lazy
    import numpy as np

    h, w = 1350, 1080
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    # top 2/3: mid photo-ish texture (variance so it's not near-empty)
    arr[: 2 * h // 3, :, :] = np.random.default_rng(0).integers(
        40, 120, size=(2 * h // 3, w, 3), dtype=np.uint8
    )
    # bottom text band: very dark fill so white text scores high contrast.
    arr[2 * h // 3 :, :, :] = 8
    png_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, "RGB").save(png_path)


def _make_render_fn(calls: list[dict[str, Any]]):
    """A render_fn that records the levers it saw and writes a clean PNG."""
    async def _render(slide_with_levers: dict[str, Any], png_path: Path) -> None:
        calls.append(dict(slide_with_levers.get("_levers") or {}))
        _write_clean_png(png_path)
    return _render


def _make_failing_render_fn():
    """A render_fn that NEVER writes a PNG (simulates a failed render)."""
    async def _render(slide_with_levers: dict[str, Any], png_path: Path) -> None:
        return  # produce nothing
    return _render


def _vision_pass(*_a, **_k) -> Critique:
    return Critique(tier="vision", passed=True, issues=[], levers=[], score=0.9)


def _brand_pass(*_a, **_k) -> Critique:
    return Critique(tier="brand", passed=True, issues=[])


def _brand_block_font(*_a, **_k) -> Critique:
    # a genuine FONT violation (not OCR-overridable)
    return Critique(tier="brand", passed=False, issues=["headline uses a serif font instead of Montserrat"])


def _brand_block_text_hallucination(*_a, **_k) -> Critique:
    # a PURE text-legibility claim — OCR may override if it reads the headline
    return Critique(tier="brand", passed=False, issues=["the headline text is garbled"])


def _ocr_legible(_png: Path, _expected: str) -> OcrVerdict:
    return OcrVerdict(legible=True, score=0.95, ocr_text=_expected, expected=_expected, mean_confidence=0.9)


def _ocr_illegible(_png: Path, _expected: str) -> OcrVerdict:
    return OcrVerdict(legible=False, score=0.2, ocr_text="garbage", expected=_expected, mean_confidence=0.5)


def _run_loop(**overrides) -> tuple[DesignerResult, list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = dict(
        slide=COVER_SLIDE,
        render_fn=_make_render_fn(calls),
        is_hero=False,  # skip saliency in A/C tests (B tests it separately)
        vision_critic=_vision_pass,
        brand_verifier=None,
        ocr_critic=_ocr_legible,
        max_iters=3,
        use_vision=True,
    )
    kwargs.update(overrides)
    out_dir = overrides.get("out_dir")
    assert out_dir is not None, "test must pass out_dir"
    res = asyncio.run(run_designer_loop(**kwargs))
    return res, calls


# ---------------------------------------------------------------------------
# Fix A — brand verifier gates a vision-PASS
# ---------------------------------------------------------------------------

def test_A_vision_pass_no_brand_verifier_converges(tmp_path: Path) -> None:
    """No brand_verifier configured → vision PASS converges (backward-compat)."""
    res, _ = _run_loop(out_dir=tmp_path / "a1", brand_verifier=None)
    assert res.converged is True
    assert res.final_png is not None


def test_A_vision_pass_brand_pass_converges(tmp_path: Path) -> None:
    """vision PASS + brand PASS → converged."""
    res, _ = _run_loop(out_dir=tmp_path / "a2", brand_verifier=_brand_pass)
    assert res.converged is True
    assert any(r.get("verdict", "").startswith("PASS (cheap + vision + brand)") for r in res.history)


def test_A_vision_pass_brand_block_does_NOT_converge(tmp_path: Path) -> None:
    """THE FIX (Fix A): vision PASS + brand BLOCK (font violation) → NOT converged.

    Before fix A the loop returned converged=True on vc.passed before the brand
    verifier ever ran. Now a brand block on the current render keeps best + stops.

    NB-4 (this fix): final_png must NOT be the brand-rejected render. With the
    block on the ONLY iteration and no earlier brand-approved render, final_png
    is None (see test_NB4_* below for the full invariant matrix).
    """
    out_dir = tmp_path / "a3"
    res, _ = _run_loop(out_dir=out_dir, brand_verifier=_brand_block_font)
    assert res.converged is False
    # the brand_verify result is recorded and it blocked
    assert any(r.get("brand_verify", {}).get("passed") is False for r in res.history)
    # NB-4: the brand-rejected render must NOT be returned as final_png. No earlier
    # iteration passed brand → final_png is None, never the rejected iter-01.png.
    assert res.final_png is None
    rejected_png = out_dir / "iter-01.png"
    assert res.final_png != rejected_png


def test_A_vision_pass_brand_block_text_hallucination_ocr_overrides(tmp_path: Path) -> None:
    """vision PASS + brand BLOCK that is a PURE text claim + OCR legible → override → converged."""
    res, _ = _run_loop(
        out_dir=tmp_path / "a4",
        brand_verifier=_brand_block_text_hallucination,
        ocr_critic=_ocr_legible,
    )
    assert res.converged is True
    assert any("brand_verify_overridden_by_ocr" in r for r in res.history)


def test_A_vision_pass_brand_block_text_but_ocr_illegible_blocks(tmp_path: Path) -> None:
    """Pure text claim but OCR CANNOT read it → NOT overridable → NOT converged."""
    res, _ = _run_loop(
        out_dir=tmp_path / "a5",
        brand_verifier=_brand_block_text_hallucination,
        ocr_critic=_ocr_illegible,
    )
    assert res.converged is False


def test_A_helper_font_claim_not_overridable(tmp_path: Path) -> None:
    """Unit: the shared adjudication helper refuses to override a font claim."""
    png = tmp_path / "x.png"
    _write_clean_png(png)
    bv = _brand_block_font()
    overridable, _detail = _brand_block_overridable_by_ocr(bv, png, COVER_SLIDE, _ocr_legible)
    assert overridable is False


def test_A_helper_pure_text_claim_overridable_when_ocr_legible(tmp_path: Path) -> None:
    png = tmp_path / "x.png"
    _write_clean_png(png)
    bv = _brand_block_text_hallucination()
    overridable, detail = _brand_block_overridable_by_ocr(bv, png, COVER_SLIDE, _ocr_legible)
    assert overridable is True
    assert "brand_verify_overridden_by_ocr" in detail


def test_A_helper_passed_verifier_not_overridable(tmp_path: Path) -> None:
    """A passing verifier has nothing to override."""
    png = tmp_path / "x.png"
    _write_clean_png(png)
    overridable, detail = _brand_block_overridable_by_ocr(_brand_pass(), png, COVER_SLIDE, _ocr_legible)
    assert overridable is False
    assert detail == {}


# ---------------------------------------------------------------------------
# NB-4 — the returned final_png must NEVER be a brand-rejected render.
#
# Defect (panel #3): best_png tracked the CHEAP legibility score BEFORE any brand
# verification, and the break-and-return-best path returned it as final_png — so a
# brand-rejected image could be published by a consumer that reads final_png while
# ignoring `converged`. The fix tracks a SEPARATE best_verified_png set only after
# a brand-pass; final_png returns THAT (or None / an earlier verified render).
# INVARIANT: final_png is (a) a brand-approved render, (b) a render with no
# brand_verifier in play (cheap-only mode), or (c) None.
# ---------------------------------------------------------------------------


def test_NB4_only_iter_brand_block_final_png_is_None_not_rejected(tmp_path: Path) -> None:
    """vision PASS + brand BLOCK on the ONLY iteration → final_png is None, NOT
    the brand-rejected render — even though that render exists on disk (the
    cheap-score "best"). converged False.
    """
    out_dir = tmp_path / "nb4_only"
    res, _ = _run_loop(out_dir=out_dir, brand_verifier=_brand_block_font)
    assert res.converged is False
    # the brand-rejected render WAS produced (proving final_png=None is the fix
    # rejecting a real image, not merely a missing-render artifact)
    rejected_png = out_dir / "iter-01.png"
    assert rejected_png.is_file()
    # NB-4: it must NOT be returned
    assert res.final_png is None
    assert res.final_png != rejected_png


def test_NB4_earlier_verified_then_later_block_returns_the_verified(tmp_path: Path) -> None:
    """An EARLIER iteration passes brand (via a vision-proposed CSS lever whose
    trial brand-passes), a LATER iteration is reached but brand-BLOCKS → final_png
    is the EARLIER brand-APPROVED render, NEVER the later rejected one. converged
    False (the later block stops the loop without convergence).
    """
    # iter 1: vision proposes a CSS lever (text_stroke) → a trial is rendered and
    #         brand PASSES it → best_verified_png = iter-01-trial.png, continue.
    # iter 2: vision PASSES → brand BLOCKS (font) → break → fallthrough returns
    #         best_verified_png (the iter-01 trial), not iter-02.png.
    vision_state = {"n": 0}

    def _vision(png_path: Path, slide: dict[str, Any], ctx: dict[str, Any]) -> Critique:
        vision_state["n"] += 1
        if vision_state["n"] == 1:
            # wants a CSS change (text_stroke is an applicable lever)
            return Critique(
                tier="vision", passed=False, issues=["needs crisper text"],
                levers=[{"lever": "text_stroke", "reason": "test"}], score=0.7,
            )
        return Critique(tier="vision", passed=True, issues=[], levers=[], score=0.9)

    brand_state = {"n": 0}

    def _brand(png_path: Path, slide: dict[str, Any], ctx: dict[str, Any]) -> Critique:
        brand_state["n"] += 1
        # 1st brand call = the iter-1 trial → PASS; 2nd = iter-2 candidate → BLOCK
        if brand_state["n"] == 1:
            return Critique(tier="brand", passed=True, issues=[])
        return Critique(tier="brand", passed=False, issues=["headline uses a serif font"])

    out_dir = tmp_path / "nb4_earlier"
    res, _ = _run_loop(
        out_dir=out_dir,
        vision_critic=_vision,
        brand_verifier=_brand,
        max_iters=3,
    )
    assert res.converged is False
    verified_png = out_dir / "iter-01-trial.png"
    rejected_png = out_dir / "iter-02.png"
    # the earlier brand-approved trial is what we return …
    assert res.final_png == verified_png
    assert Path(res.final_png).is_file()
    # … and crucially NOT the later brand-rejected render.
    assert res.final_png != rejected_png
    # sanity: the loop really did reach iter 2 and the verifier blocked there
    assert any(
        r.get("iter") == 2 and r.get("brand_verify", {}).get("passed") is False
        for r in res.history
    )


def test_NB4_happy_path_returns_verified_png_converged(tmp_path: Path) -> None:
    """Regression: vision PASS + brand PASS still returns the verified render +
    converged True (the fix must not over-block the legitimate converge path).
    """
    out_dir = tmp_path / "nb4_happy"
    res, _ = _run_loop(out_dir=out_dir, brand_verifier=_brand_pass)
    assert res.converged is True
    # the converged render is iter-01.png (vision+brand passed on the 1st pass)
    expected = out_dir / "iter-01.png"
    assert res.final_png == expected
    assert Path(res.final_png).is_file()
    assert any(r.get("verdict", "").startswith("PASS (cheap + vision + brand)") for r in res.history)


def test_NB4_cheap_only_mode_returns_png_no_brand_gate(tmp_path: Path) -> None:
    """Invariant clause (b): cheap-only mode (vision disabled) has NO brand
    verifier in play, so final_png is its rendered png (not None) + converged.
    Documents that the None-guarantee applies ONLY when a brand verifier exists.
    """
    out_dir = tmp_path / "nb4_cheap"
    res, _ = _run_loop(out_dir=out_dir, use_vision=False, brand_verifier=None)
    assert res.converged is True
    expected = out_dir / "iter-01.png"
    assert res.final_png == expected
    assert Path(res.final_png).is_file()


# ---------------------------------------------------------------------------
# Fix C — design critic fail-closed in live mode
# ---------------------------------------------------------------------------

def _patch_cli_down(monkeypatch) -> None:
    """Simulate the claude CLI being unavailable: _run_claude_json returns None.

    (We patch the function, not CLAUDE_BIN, because _CLAUDE_BIN is captured at
    import time — a late setenv would not take effect, and we must NEVER invoke
    the real CLI from a unit test.)
    """
    import wr2_html_renderer.claude_vision as cv

    monkeypatch.setattr(cv, "_run_claude_json", lambda *a, **k: None)


def test_C_critic_fail_open_by_default(monkeypatch) -> None:
    import wr2_html_renderer.claude_vision as cv

    _patch_cli_down(monkeypatch)
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)
    crit = cv.claude_design_critic(Path("/tmp/none.png"), {}, {})
    assert crit.passed is True  # fail OPEN (offline cheap-tier default)


def test_C_critic_fail_closed_when_required(monkeypatch) -> None:
    import wr2_html_renderer.claude_vision as cv

    _patch_cli_down(monkeypatch)
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")
    crit = cv.claude_design_critic(Path("/tmp/none.png"), {}, {})
    assert crit.passed is False  # fail CLOSED (live/wired)
    assert any("failing closed" in i for i in crit.issues)


def test_C_brand_verifier_always_fail_closed(monkeypatch) -> None:
    import wr2_html_renderer.claude_vision as cv

    _patch_cli_down(monkeypatch)
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)  # flag must NOT matter for verifier
    verd = cv.claude_brand_verifier(Path("/tmp/none.png"), {}, {})
    assert verd.passed is False


# ---------------------------------------------------------------------------
# Fix D — is_text_legibility_claim word-boundary + negative keywords
# ---------------------------------------------------------------------------

def test_D_font_claim_is_not_text_legibility() -> None:
    assert is_text_legibility_claim("headline uses a serif font instead of Montserrat") is False


def test_D_clipped_is_text_legibility() -> None:
    assert is_text_legibility_claim("headline is clipped at the top") is True


def test_D_negative_keywords_block_even_with_text_word() -> None:
    for s in (
        "headline color is wrong",
        "title weight is too bold",
        "headline is italic",
        "the logo overlaps the title",
        "palette violation in the headline band",
        "wrong hex on the headline",
    ):
        assert is_text_legibility_claim(s) is False, s


def test_D_pure_legibility_claims_pass() -> None:
    for s in (
        "the title is garbled",
        "headline cut off at the edge",
        "body text is illegible",
        "il titolo e illeggibile",
        "headline unreadable over the photo",
    ):
        assert is_text_legibility_claim(s) is True, s


def test_D_word_boundary_no_substring_false_positive() -> None:
    # 'title' must not match inside 'subtitle' (no other text/neg keyword present)
    assert is_text_legibility_claim("subtitle alignment looks off") is False


# ---------------------------------------------------------------------------
# Fix B — saliency busyness measured on the RENDERED png (coupling)
# ---------------------------------------------------------------------------

def test_B_critic_legibility_signature_accepts_hero_path() -> None:
    """Signature is unchanged (caller compatibility preserved)."""
    sig = inspect.signature(critic_legibility)
    assert "hero_path" in sig.parameters
    assert "text_box" in sig.parameters


def test_B_heavy_scrim_render_scores_better_on_busyness(tmp_path: Path) -> None:
    """A heavy-scrim (darker, calmer bottom band) render must score the busyness
    check BETTER than a busy-bottom render — proving the metric is now coupled to
    the rendered PNG (fix B), not the static raw hero.

    We synthesize two rendered PNGs:
      - busy_png:  noisy (high variance) bottom band → text band is busiest
      - calm_png:  flat-dark bottom band (heavy scrim) → text band is calmest
    The calm render must NOT raise the 'text over busy band' issue; the busy one
    should. (On the OLD code both would read the same raw hero → identical.)
    """
    from PIL import Image
    import numpy as np

    h, w = 1350, 1080
    rng = np.random.default_rng(1)
    band = h // 3  # bottom band start ~ 2/3

    # busy render: CALM (uniform) top 2/3 + NOISY bottom band → bottom is busiest
    # (this is the "text over a busy region" case the check must flag).
    busy = np.full((h, w, 3), 50, dtype=np.uint8)
    busy[2 * band :, :, :] = rng.integers(0, 255, size=(h - 2 * band, w, 3), dtype=np.uint8)
    busy_png = tmp_path / "busy.png"
    Image.fromarray(busy, "RGB").save(busy_png)

    # scrim render: NOISY top 2/3 + FLAT-DARK bottom band (heavy scrim applied)
    # → bottom is now the CALMEST band; the busy-band flag must clear.
    calm = rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8)
    calm[2 * band :, :, :] = 6  # flat dark bottom = heavy scrim composite
    calm_png = tmp_path / "calm.png"
    Image.fromarray(calm, "RGB").save(calm_png)

    # Coupling proof at the metric level: the busyness of the bottom (text) band
    # is now read FROM THE RENDERED PNG. The heavy-scrim (flat-dark bottom) render
    # must have a LOWER bottom-band busyness than the noisy-bottom render — i.e.
    # applying a scrim genuinely improves the metric. On the OLD code (saliency on
    # the static raw hero) the value would be identical regardless of the render.
    from .critic_signals import calmest_band

    _busy_best, busy_bands = calmest_band(busy_png, n_bands=3)
    _calm_best, calm_bands = calmest_band(calm_png, n_bands=3)
    busy_bottom = busy_bands[-1]
    calm_bottom = calm_bands[-1]
    assert calm_bottom < busy_bottom, (
        f"scrim render bottom-band busyness {calm_bottom:.4f} must be < busy render "
        f"{busy_bottom:.4f} (proves the metric is coupled to the rendered PNG)"
    )

    # And at the loop level: the noisy-bottom render flags the busy band ("busier"
    # text band); the heavy-scrim render does not raise it as the busiest band.
    busy_crit = critic_legibility(busy_png, COVER_SLIDE, is_hero=True, hero_path=None)
    busy_busyness_issue = any("busier" in i for i in busy_crit.issues)
    assert busy_busyness_issue is True, f"busy render should flag busy band; issues={busy_crit.issues}"


# ---------------------------------------------------------------------------
# NB-1 (re-panel) — Fix B deadlock: burned-in glyphs dominate bottom-band
# busyness so the scrim lever could never satisfy the gate. The metric must now
# read the BACKGROUND (glyphs masked) so a heavier scrim strictly lowers it.
# ---------------------------------------------------------------------------

# The text box the loop samples (matches designer_loop.DEFAULT_TEXT_BOX).
_NB1_TEXT_BOX = (0.05, 0.55, 0.95, 0.92)


def _write_hero_with_burned_text(
    png_path: Path, *, bg_behind_text: int, textured_bottom: bool = True, seed: int = 7
) -> None:
    """A rendered hero PNG: busy photo on top, a bottom text band that carries the
    WHITE headline glyphs burned in (as the real renderer produces). `bg_behind_text`
    is the background level behind the text — LOW simulates a heavy scrim, HIGH a
    light one. The glyphs are IDENTICAL regardless of bg level (the scrim can't
    touch them), which is the whole point of the deadlock.
    """
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    h, w = 1350, 1080
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(h, w, 3), dtype=np.uint8)  # busy photo top
    y0 = int(0.55 * h)
    if textured_bottom:
        base = rng.integers(0, 255, size=(h - y0, w, 3)).astype(np.float64)
        arr[y0:, :, :] = (base * (bg_behind_text / 255.0)).astype(np.uint8)
    else:
        arr[y0:, :, :] = bg_behind_text
    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 90)
    except Exception:  # noqa: BLE001 — any font; default is fine for the variance signal
        font = ImageFont.load_default()
    draw.text((80, int(0.62 * h)), "YOUR KITAP IS VALID", fill=(255, 255, 255), font=font)
    draw.text((80, int(0.74 * h)), "3 RULES CHANGED NOW", fill=(255, 255, 255), font=font)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(png_path)


def test_NB1_scrim_increase_strictly_lowers_gate_busyness(tmp_path: Path) -> None:
    """Lever ↔ metric coupling: with the SAME burned-in white glyphs, a render
    whose background-behind-text is darker (heavier scrim) MUST read a strictly
    lower bottom-band busyness from the gate's metric (calmest_band with the text
    box masked). On the glyph-INCLUSIVE metric (no mask, the pre-NB-1 behavior)
    the two are ~identical because the unchanged glyphs dominate — that was the
    deadlock.
    """
    from .critic_signals import calmest_band

    light = tmp_path / "light_scrim.png"   # bright bg behind text
    heavy = tmp_path / "heavy_scrim.png"   # dark bg behind text (scrim applied)
    _write_hero_with_burned_text(light, bg_behind_text=150)
    _write_hero_with_burned_text(heavy, bg_behind_text=8)

    # NEW masked metric (what the gate now reads): strictly decreases with scrim.
    _, masked_light = calmest_band(light, n_bands=3, text_mask_box=_NB1_TEXT_BOX)
    _, masked_heavy = calmest_band(heavy, n_bands=3, text_mask_box=_NB1_TEXT_BOX)
    assert masked_heavy[-1] < masked_light[-1], (
        f"heavier scrim must lower the gate's bottom-band busyness: "
        f"heavy={masked_heavy[-1]:.4f} !< light={masked_light[-1]:.4f}"
    )

    # OLD glyph-inclusive metric (no mask): glyphs dominate → lever can't move it.
    # We assert the masked metric MOVED MUCH MORE than the unmasked one, proving
    # the fix is what restores the coupling (not just noise).
    _, raw_light = calmest_band(light, n_bands=3)
    _, raw_heavy = calmest_band(heavy, n_bands=3)
    masked_drop = masked_light[-1] - masked_heavy[-1]
    raw_drop = raw_light[-1] - raw_heavy[-1]
    assert masked_drop > 10 * abs(raw_drop), (
        f"masked metric must respond to the scrim far more than the glyph-inclusive "
        f"one (masked_drop={masked_drop:.4f}, raw_drop={raw_drop:.4f})"
    )


def test_NB1_masked_busyness_monotonic_even_on_flat_background(tmp_path: Path) -> None:
    """Edge case: a FLAT (untextured) background behind the text. A pure-variance
    metric is translation-invariant → darkening a flat fill would NOT change it
    (the subtle trap). The brightness term in the masked score must still make a
    heavier scrim strictly lower the busyness.
    """
    from .critic_signals import calmest_band

    light = tmp_path / "flat_light.png"
    heavy = tmp_path / "flat_heavy.png"
    _write_hero_with_burned_text(light, bg_behind_text=150, textured_bottom=False)
    _write_hero_with_burned_text(heavy, bg_behind_text=8, textured_bottom=False)
    _, ml = calmest_band(light, n_bands=3, text_mask_box=_NB1_TEXT_BOX)
    _, mh = calmest_band(heavy, n_bands=3, text_mask_box=_NB1_TEXT_BOX)
    assert mh[-1] < ml[-1], (
        f"on a flat background the scrim must still lower busyness via brightness: "
        f"heavy={mh[-1]:.4f} !< light={ml[-1]:.4f}"
    )


def test_NB1_busy_hero_reaches_vision_within_3_iters_not_deadspin(tmp_path: Path) -> None:
    """Behavioral: a genuinely busy hero (bottom text band busier than the calmest
    band) must converge/escalate to the PAID vision tier within max_iters, NOT
    dead-spin the cheap tier all 3 iterations.

    render_fn simulates the real renderer: it reads the accumulated scrim_opacity
    and darkens the background-behind-text accordingly (heavier scrim → darker
    bottom band), keeping the white glyphs burned in. Under the OLD glyph-inclusive
    metric the bottom band stayed 'busiest' forever → the loop would pull the cheap
    scrim lever every iteration and never call the vision critic. Under NB-1 the
    scrim lowers the masked busyness, the cheap gate clears, and the vision critic
    runs (here it PASSES → converge).
    """
    vision_calls: list[int] = []

    def _vision_pass_counting(png_path: Path, slide: dict[str, Any], ctx: dict[str, Any]) -> Critique:
        vision_calls.append(ctx.get("iteration", -1))
        return Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    async def _render_with_scrim(slide_with_levers: dict[str, Any], png_path: Path) -> None:
        scrim = float((slide_with_levers.get("_levers") or {}).get("scrim_opacity", 0.0))
        # map scrim 0..~1 → background level behind text 150..6 (heavier = darker).
        bg = max(6, int(150 - scrim * 160))
        _write_hero_with_burned_text(png_path, bg_behind_text=bg)

    out_dir = tmp_path / "nb1loop"
    res = asyncio.run(
        run_designer_loop(
            slide=COVER_SLIDE,
            render_fn=_render_with_scrim,
            out_dir=out_dir,
            is_hero=True,            # exercises the saliency/busy-band gate
            hero_path=None,
            vision_critic=_vision_pass_counting,
            brand_verifier=None,
            ocr_critic=_ocr_legible,
            max_iters=3,
            use_vision=True,
        )
    )
    # The fix's whole point: the paid vision tier is REACHED (not starved). On the
    # pre-NB-1 code the busy-band gate never cleared so vision_calls would be empty.
    assert vision_calls, (
        f"busy hero never reached the vision tier in {res.iterations} iters — "
        f"cheap tier dead-spun (history={res.history})"
    )
    assert res.converged is True, f"expected convergence once vision PASSes; got {res.reason}"


# ---------------------------------------------------------------------------
# Fix E — never promote a stale 01.png on a failed render
# ---------------------------------------------------------------------------

def test_E_failed_render_does_not_promote_stale_png(tmp_path: Path) -> None:
    """make_slide_render_fn: a failed render (no png_paths) must NOT promote a
    pre-existing slides/01.png. The loop's `if not png_path.is_file(): break`
    must then fire (final_png stays None for a first-iter failure).
    """
    from .composer import make_slide_render_fn

    out_dir = tmp_path / "e"
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # plant a STALE 01.png (a previous iteration's output) where the old fallback
    # would have grabbed it.
    _write_clean_png(slides_dir / "01.png")
    stale_bytes = (slides_dir / "01.png").read_bytes()

    # a render_fn whose underlying render fails. We monkeypatch render_html_files
    # used inside make_slide_render_fn to return an empty-png result.
    import wr2_html_renderer.composer as composer_mod
    from .renderer import RenderResult

    async def _fail_render(*_a, **_k) -> RenderResult:
        return RenderResult(failures=["simulated render failure"], slides_rendered=0)

    # make_slide_render_fn does a local `from .renderer import render_html_files`,
    # so patch it on the renderer module.
    import wr2_html_renderer.renderer as renderer_mod
    orig = renderer_mod.render_html_files
    renderer_mod.render_html_files = _fail_render  # type: ignore[assignment]
    try:
        # also stub materialize so it doesn't need brand layout assets, but it
        # MUST still write the HTML to disk (the real materialize_slide_html
        # always does — NB-2's temp-dir render copies that file alongside the
        # staged assets, so it has to exist).
        async def _fake_materialize(*_a, **_k):
            (slides_dir / "01.html").write_text(
                "<html><head></head><body>stub</body></html>", encoding="utf-8"
            )
            return (slides_dir / "01.html", True)
        orig_mat = composer_mod.materialize_slide_html
        composer_mod.materialize_slide_html = _fake_materialize  # type: ignore[assignment]
        try:
            render_fn = make_slide_render_fn(
                slides_dir=slides_dir, index=1, total=9, hero_filename="hero.jpg"
            )
            target = out_dir / "iters" / "iter-01.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            asyncio.run(render_fn(dict(COVER_SLIDE, _levers={}), target))
            # THE FIX: target must NOT have been created from the stale 01.png
            assert not target.is_file(), "failed render must not promote any PNG to the iter path"
            # and the stale file is untouched (not consumed/moved)
            assert (slides_dir / "01.png").is_file()
            assert (slides_dir / "01.png").read_bytes() == stale_bytes
        finally:
            composer_mod.materialize_slide_html = orig_mat  # type: ignore[assignment]
    finally:
        renderer_mod.render_html_files = orig  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# NB-2 (re-panel) — race: every slide rendered to render_root/slides/01.png.
# Each call must render into a UNIQUE target so concurrent slides on a shared
# render_root never clobber each other before the atomic replace.
# ---------------------------------------------------------------------------

def test_NB2_concurrent_renders_same_render_root_do_not_clobber(tmp_path: Path) -> None:
    """Two _render_fn calls (different indices, SAME render_root) run concurrently.
    The stubbed renderer writes to the canonical render_root-relative
    slides/01.png path that the real renderer uses (the collision point). With the
    fix each call renders inside its OWN temp dir, so the two distinct png_paths
    each get THEIR OWN content — no cross-contamination.
    """
    from .composer import make_slide_render_fn
    import wr2_html_renderer.composer as composer_mod
    import wr2_html_renderer.renderer as renderer_mod
    from .renderer import RenderResult

    out_dir = tmp_path / "nb2"
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # stub materialize: write the per-call marker ("slide N") AS the HTML content
    # so the temp-dir copy carries it and a clobber would be detectable.
    async def _fake_materialize(_slide, sdir, *, index, total, hero_filename=None):
        (sdir / f"{index:02d}.html").write_text(f"slide {index}", encoding="utf-8")
        return (sdir / f"{index:02d}.html", True)

    # stub render: write the canonical output_dir/slides/01.png (the renderer's
    # always-"01" name — the collision point) with the marker it was handed, then
    # YIELD (await) AFTER writing but BEFORE returning. This makes the race
    # deterministic in single-threaded asyncio: with a SHARED render_root (legacy)
    # call A writes A's 01.png, yields; call B overwrites the SAME 01.png with B's
    # content, yields; A resumes and promotes 01.png (now B's content) to A's
    # png_path → clobber. With the fix each call's output_dir is its OWN temp
    # render_root, so the two 01.png files are distinct and no clobber occurs.
    async def _stub_render(html_specs, output_dir, *, timeout_ms=30000, make_pdf=True):
        import asyncio as _aio
        html_path = Path(html_specs[0][0])
        marker = html_path.read_text(encoding="utf-8")  # "slide N"
        produced = Path(output_dir) / "slides" / "01.png"
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_text(marker, encoding="utf-8")  # plain text PNG-stand-in
        await _aio.sleep(0.02)  # yield AFTER writing → sibling can clobber a shared path
        return RenderResult(
            png_paths=[produced], slides_rendered=1, heroes_expected=1, heroes_placed=1
        )

    orig_mat = composer_mod.materialize_slide_html
    orig_render = renderer_mod.render_html_files
    composer_mod.materialize_slide_html = _fake_materialize  # type: ignore[assignment]
    renderer_mod.render_html_files = _stub_render  # type: ignore[assignment]
    try:
        fn1 = make_slide_render_fn(slides_dir=slides_dir, index=1, total=9, hero_filename=None)
        fn2 = make_slide_render_fn(slides_dir=slides_dir, index=2, total=9, hero_filename=None)
        p1 = out_dir / "iters" / "iter-01.png"
        p2 = out_dir / "iters" / "iter-02.png"
        p1.parent.mkdir(parents=True, exist_ok=True)

        async def _both() -> None:
            await asyncio.gather(
                fn1(dict(COVER_SLIDE, _levers={}), p1),
                fn2(dict(COVER_SLIDE, _levers={}), p2),
            )

        asyncio.run(_both())
        assert p1.is_file() and p2.is_file(), "both slides must produce their PNG"
        # THE FIX: each png_path holds ITS OWN slide's content (no clobber). The
        # stub wrote the materialized HTML body verbatim ("slide N") as the PNG
        # stand-in, so a clobber would show up as the wrong slide's text.
        assert p1.read_text(encoding="utf-8") == "slide 1", p1.read_text(encoding="utf-8")
        assert p2.read_text(encoding="utf-8") == "slide 2", p2.read_text(encoding="utf-8")
        # And no temp render dir leaked under render_root.
        leftover = [d for d in out_dir.iterdir() if d.name.startswith("wr2-render-")]
        assert not leftover, f"temp render dirs not cleaned up: {leftover}"
    finally:
        composer_mod.materialize_slide_html = orig_mat  # type: ignore[assignment]
        renderer_mod.render_html_files = orig_render  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# NB-3 (re-panel) — promotion must gate on RenderResult.ok, not png_paths alone.
# A render that wrote a PNG but FAILED the hero-placement gate (heroes_placed !=
# heroes_expected) has non-empty png_paths yet ok=False → must NOT be promoted.
# ---------------------------------------------------------------------------

def test_NB3_hero_placement_failure_not_promoted_despite_png(tmp_path: Path) -> None:
    """ok=False (hero decoded-but-not-visible) with a non-empty png_paths must NOT
    promote: png_path stays absent so the loop treats it as a render failure.
    This proves the gate is `not res.ok or not res.png_paths`, not just png_paths.
    """
    from .composer import make_slide_render_fn
    import wr2_html_renderer.composer as composer_mod
    import wr2_html_renderer.renderer as renderer_mod
    from .renderer import RenderResult

    out_dir = tmp_path / "nb3"
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    async def _fake_materialize(_slide, sdir, *, index, total, hero_filename=None):
        (sdir / f"{index:02d}.html").write_text("<html><body>x</body></html>", encoding="utf-8")
        return (sdir / f"{index:02d}.html", True)

    async def _render_hero_missing(html_specs, output_dir, *, timeout_ms=30000, make_pdf=True):
        # The renderer DID write+dimension-verify a PNG (png_paths non-empty) but
        # the hero was decoded-yet-not-visible → heroes_placed(0) != expected(1).
        # failures=[] so ok is False PURELY on the hero count (the cleanest NB-3
        # case — gating on png_paths alone would wrongly promote this).
        produced = Path(output_dir) / "slides" / "01.png"
        produced.parent.mkdir(parents=True, exist_ok=True)
        _write_clean_png(produced)
        res = RenderResult(slides_rendered=1, heroes_expected=1, heroes_placed=0)
        res.png_paths.append(produced)
        assert res.ok is False  # sanity: this is the failed-hero, non-empty-png case
        assert res.png_paths      # sanity: png_paths IS non-empty
        return res

    orig_mat = composer_mod.materialize_slide_html
    orig_render = renderer_mod.render_html_files
    composer_mod.materialize_slide_html = _fake_materialize  # type: ignore[assignment]
    renderer_mod.render_html_files = _render_hero_missing  # type: ignore[assignment]
    try:
        fn = make_slide_render_fn(slides_dir=slides_dir, index=1, total=9, hero_filename="hero.jpg")
        target = out_dir / "iters" / "iter-01.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(fn(dict(COVER_SLIDE, _levers={}), target))
        # THE FIX: a hero-placement failure (ok=False) is NOT promoted.
        assert not target.is_file(), (
            "render with ok=False (hero not placed) must NOT be promoted even though "
            "it produced a PNG"
        )
        leftover = [d for d in out_dir.iterdir() if d.name.startswith("wr2-render-")]
        assert not leftover, f"temp render dirs not cleaned up: {leftover}"
    finally:
        composer_mod.materialize_slide_html = orig_mat  # type: ignore[assignment]
        renderer_mod.render_html_files = orig_render  # type: ignore[assignment]


def test_NB3_ok_render_IS_promoted(tmp_path: Path) -> None:
    """Positive control for NB-3: a fully OK render (ok=True, hero placed) IS
    promoted to png_path — the gate must not over-block.
    """
    from .composer import make_slide_render_fn
    import wr2_html_renderer.composer as composer_mod
    import wr2_html_renderer.renderer as renderer_mod
    from .renderer import RenderResult

    out_dir = tmp_path / "nb3ok"
    slides_dir = out_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    async def _fake_materialize(_slide, sdir, *, index, total, hero_filename=None):
        (sdir / f"{index:02d}.html").write_text("<html><body>x</body></html>", encoding="utf-8")
        return (sdir / f"{index:02d}.html", True)

    async def _render_ok(html_specs, output_dir, *, timeout_ms=30000, make_pdf=True):
        produced = Path(output_dir) / "slides" / "01.png"
        produced.parent.mkdir(parents=True, exist_ok=True)
        _write_clean_png(produced)
        res = RenderResult(slides_rendered=1, heroes_expected=1, heroes_placed=1)
        res.png_paths.append(produced)
        assert res.ok is True
        return res

    orig_mat = composer_mod.materialize_slide_html
    orig_render = renderer_mod.render_html_files
    composer_mod.materialize_slide_html = _fake_materialize  # type: ignore[assignment]
    renderer_mod.render_html_files = _render_ok  # type: ignore[assignment]
    try:
        fn = make_slide_render_fn(slides_dir=slides_dir, index=1, total=9, hero_filename="hero.jpg")
        target = out_dir / "iters" / "iter-01.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(fn(dict(COVER_SLIDE, _levers={}), target))
        assert target.is_file(), "an OK render (hero placed) MUST be promoted to png_path"
    finally:
        composer_mod.materialize_slide_html = orig_mat  # type: ignore[assignment]
        renderer_mod.render_html_files = orig_render  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# plain-python runner (so it works without pytest installed too)
# ---------------------------------------------------------------------------

def _run_all_without_pytest() -> int:
    import tempfile

    class _MP:
        """Minimal monkeypatch shim for the env-var + setattr tests."""
        def __init__(self) -> None:
            self._saved: list[tuple[str, str | None]] = []
            self._attrs: list[tuple[Any, str, Any]] = []
        def setenv(self, k: str, v: str) -> None:
            import os
            self._saved.append((k, os.environ.get(k)))
            os.environ[k] = v
        def delenv(self, k: str, raising: bool = True) -> None:
            import os
            self._saved.append((k, os.environ.get(k)))
            os.environ.pop(k, None)
        def setattr(self, target: Any, name: str, value: Any) -> None:
            self._attrs.append((target, name, getattr(target, name)))
            setattr(target, name, value)
        def undo(self) -> None:
            import os
            for k, v in reversed(self._saved):
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
            for target, name, old in reversed(self._attrs):
                setattr(target, name, old)

    tests = [obj for name, obj in sorted(globals().items())
             if name.startswith("test_") and callable(obj)]
    passed = 0
    failed = 0
    for t in tests:
        params = inspect.signature(t).parameters
        with tempfile.TemporaryDirectory(prefix="wr2-panel-fixes-") as td:
            mp = _MP()
            try:
                kwargs: dict[str, Any] = {}
                if "tmp_path" in params:
                    kwargs["tmp_path"] = Path(td)
                if "monkeypatch" in params:
                    kwargs["monkeypatch"] = mp
                t(**kwargs)
                print(f"  ✓ {t.__name__}")
                passed += 1
            except AssertionError as e:
                print(f"  ✗ {t.__name__}: {e}")
                failed += 1
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {t.__name__}: UNEXPECTED {type(e).__name__}: {e}")
                failed += 1
            finally:
                mp.undo()
    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(_run_all_without_pytest())
