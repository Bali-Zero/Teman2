"""Unit tests for the WR2 HTML render apply-worker + the engine vision fail-closed gate.

Pytest-collectable (mock-based, no real DB / Drive / chromium). The full DB-level
behavior of the _pg HTML-lane is covered in
tests/unit/services/canva_renderer_v2/test_pg.py.
"""

from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path

import pytest

from scripts.wr2_html_render_apply import _HeroServer, _normalize_heroes


# ── hero normalizer (#13) ────────────────────────────────────────────────────


def test_normalizer_serves_present_hero_and_rewrites_url():
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    src = work / "src.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0HEROBYTES")
    slides = [{"is_hero_image": True, "hero_image_path": str(src), "headline": "A"}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert norm[0]["image_url"].startswith(f"http://127.0.0.1:{server.port}/")
        # the localhost URL serves exactly the source bytes
        got = urllib.request.urlopen(norm[0]["image_url"], timeout=5).read()
        assert got == src.read_bytes()
        assert list(hero_dir.glob("hero-01*"))


def test_normalizer_passes_through_non_hero_slide():
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    slides = [{"headline": "no hero here"}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert "image_url" not in norm[0]


def test_normalizer_no_fake_url_for_missing_hero():
    """A hero slide whose hero_image_path is missing on disk must NOT get a URL — the
    renderer's hero gate then correctly fails it (we never ship a hero slide without
    its image)."""
    work = Path(tempfile.mkdtemp(prefix="wr2-norm-"))
    hero_dir = work / "heroes"
    hero_dir.mkdir(parents=True)
    slides = [{"is_hero_image": True, "hero_image_path": str(work / "does-not-exist.jpg")}]
    with _HeroServer(hero_dir) as server:
        norm = _normalize_heroes(slides, hero_dir, server)
        assert "image_url" not in norm[0]


# ── vision fail-closed (v4 condition E / GO#3 c1/c5) ─────────────────────────


def test_vision_critic_soft_pass_by_default(monkeypatch):
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision, "_run_claude_json", lambda *a, **k: None)
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)
    png = Path(tempfile.mkdtemp()) / "x.png"
    png.write_bytes(b"PNG")
    c = claude_vision.claude_design_critic(png, {}, {})
    assert c.passed is True  # historical soft-pass when vision unavailable + env unset


def test_vision_critic_fail_closed_when_required(monkeypatch):
    from wr2_html_renderer import claude_vision

    monkeypatch.setattr(claude_vision, "_run_claude_json", lambda *a, **k: None)
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")
    png = Path(tempfile.mkdtemp()) / "x.png"
    png.write_bytes(b"PNG")
    c = claude_vision.claude_design_critic(png, {}, {})
    assert c.passed is False
    assert any("vision" in i.lower() for i in c.issues)


@pytest.mark.asyncio
async def test_designer_loop_converges_default_no_vision(monkeypatch):
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _P:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _P())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"}, render_fn=render_fn, out_dir=out,
        vision_critic=None, use_vision=True, max_iters=2,
    )
    assert res.converged is True


@pytest.mark.asyncio
async def test_designer_loop_fail_closed_when_vision_required(monkeypatch):
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _P:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _P())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _P())
    monkeypatch.setenv("WR2_VISION_REQUIRED", "1")

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"}, render_fn=render_fn, out_dir=out,
        vision_critic=None, use_vision=True, max_iters=2,
    )
    assert res.converged is False
    assert res.reason == "vision_required_but_unavailable"


# ── designer-loop deadlock + real rebalance_wrap lever (2026-06-09) ──────────


def test_apply_levers_folds_rebalance_wrap():
    """FIX#2b: rebalance_wrap is now a real, applicable lever (not excluded)."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "rebalance_wrap", "reason": "orphan"}])
    names = [lev.get("lever") for lev in applied]
    assert "rebalance_wrap" in names
    assert acc.get("_rebalance_wrap") is True


def test_apply_levers_rerender_still_not_folded():
    """Pure structural signals (rerender) remain NON-applied escalation signals."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "rerender", "reason": "near-empty"}])
    assert applied == []


def test_balance_headline_inserts_br_no_orphan():
    """_balance_headline wraps a long headline into lines via <br>, each within
    the RENDERED PIXEL-WIDTH budget (not char count) and with no orphan word."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT")
    assert "<br>" in out
    lines = out.split("<br>")
    assert len(lines) >= 2  # actually wrapped
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line too wide: {ln!r}"
        assert len(ln.split()) >= 2, f"orphan line: {ln!r}"
    # round-trips the words (only <br>s inserted, nothing dropped/reordered)
    assert out.replace("<br>", " ").split() == "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT".split()


def test_balance_headline_short_title_unchanged():
    """≤3 words: leave the headline alone (nothing to balance)."""
    from wr2_html_renderer.composer import _balance_headline

    assert _balance_headline("Clock Is Ticking") == "Clock Is Ticking"
    assert "<br>" not in _balance_headline("Two Words")


def test_balance_headline_idempotent_if_prewrapped():
    """A headline that already carries a <br> is left as-is."""
    from wr2_html_renderer.composer import _balance_headline

    pre = "KPK ARRESTS<br>A TOP MINISTER"
    assert _balance_headline(pre) == pre


def test_rebalance_wrap_only_applies_when_lever_set():
    """FIX#2c: _fill_placeholders only re-wraps the headline when the
    _rebalance_wrap lever is active in slide['_levers']."""
    from wr2_html_renderer.composer import _fill_placeholders

    html = "<h1>{{heading}}</h1>"
    slide = {"headline": "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT"}
    # no lever → no <br>
    out_off = _fill_placeholders(html, slide, hero_filename=None)
    assert "<br>" not in out_off
    # lever on → <br> present, rendered as a tag (not escaped)
    slide_on = {**slide, "_levers": {"_rebalance_wrap": True}}
    out_on = _fill_placeholders(html, slide_on, hero_filename=None)
    assert "<br>" in out_on
    assert "&lt;br&gt;" not in out_on  # not HTML-escaped


def test_text_anchor_removed_from_allowed_levers():
    """FIX#2a: text_anchor is a zombie (no CSS side) — gone from the vocabulary."""
    from wr2_html_renderer.claude_vision import _ALLOWED_LEVERS

    assert "text_anchor" not in _ALLOWED_LEVERS
    assert "rebalance_wrap" in _ALLOWED_LEVERS  # still a real lever


def test_legibility_levers_constant():
    """The pure-legibility lever set: scrim/stroke/shrink + grow (the symmetric
    grow_font partner added 2026-06-10)."""
    from wr2_html_renderer.designer_loop import _LEGIBILITY_LEVERS

    assert _LEGIBILITY_LEVERS == {"scrim_opacity", "text_stroke", "shrink_font", "grow_font"}


@pytest.mark.asyncio
async def test_designer_loop_legibility_lever_not_killed_by_brand_reject(monkeypatch):
    """FIX#3: when the brand verifier rejects for a NON-legibility reason but the
    only applied lever is pure-legibility (scrim/stroke/shrink), the loop must
    NOT break — it commits the legibility change and keeps iterating."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    # cheap tiers always pass → we reach the vision tier every iteration
    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0, "brand": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: wants a pure-legibility lever (scrim) — applicable
            return dl.Critique(
                tier="vision", passed=False, issues=["text a touch low-contrast"],
                levers=[{"lever": "scrim_opacity", "delta": 0.15, "reason": "low contrast"}],
                score=0.5,
            )
        # iter 2+: now happy
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        # rejects for a NON-text-legibility reason (palette) — OCR can't override
        # this, but the legibility-only override (FIX#3) must.
        calls["brand"] += 1
        return dl.Critique(tier="brand", passed=False, issues=["palette looks off to me"])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"}, render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=brand_verifier,
        ocr_critic=None,  # disable OCR adjudication so only FIX#3 decides
        use_vision=True, max_iters=3,
    )
    # the legibility change was committed despite the brand reject, and the loop
    # went on to a second iteration where vision passed → converged.
    assert res.converged is True
    assert calls["vision"] >= 2  # did NOT break after the first reject
    # the committed scrim lever is reflected in the history (renamed override key)
    assert any(
        rec.get("brand_verify_inert_override")
        for rec in res.history
    )


@pytest.mark.asyncio
async def test_designer_loop_rebalance_wrap_not_killed_by_brand_reject(monkeypatch):
    """Brand-inert override (fire-test residual): when the verifier rejects for a
    NON-inert reason (hierarchy/logo) but the only applied levers are
    {rebalance_wrap, shrink_font} — both brand-inert (text re-wrap + font
    down-step) — the loop must NOT break. rebalance_wrap is now covered by
    _BRAND_INERT_LEVERS, not just _LEGIBILITY_LEVERS."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0, "brand": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: proposes the exact pair the fire-test hit (rebalance + shrink)
            return dl.Critique(
                tier="vision", passed=False, issues=["title leaves an orphan word"],
                levers=[
                    {"lever": "rebalance_wrap", "reason": "orphan word on last line"},
                    {"lever": "shrink_font", "target": "heading", "reason": "a touch dense"},
                ],
                score=0.5,
            )
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        # rejects for a NON-inert reason (hierarchy/logo) — the brand-inert
        # override must still commit the rebalance+shrink change.
        calls["brand"] += 1
        return dl.Critique(tier="brand", passed=False, issues=["hierarchy unclear; logo too small"])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=brand_verifier,
        ocr_critic=None,  # disable OCR adjudication so only the inert override decides
        use_vision=True, max_iters=3,
    )
    assert res.converged is True
    assert calls["vision"] >= 2  # did NOT break after the first reject
    assert any(rec.get("brand_verify_inert_override") for rec in res.history)


def test_brand_inert_levers_includes_rebalance_wrap():
    """_BRAND_INERT_LEVERS = legibility levers + rebalance_wrap (text re-wrap)."""
    from wr2_html_renderer.designer_loop import _BRAND_INERT_LEVERS, _LEGIBILITY_LEVERS

    assert _BRAND_INERT_LEVERS == _LEGIBILITY_LEVERS | {"rebalance_wrap"}
    assert "rebalance_wrap" in _BRAND_INERT_LEVERS


# ── FIX#2b robust multi-line wrap + FIX#4 composition-debt accept (2026-06-10) ─


def test_balance_headline_real_title_pixel_width_no_orphan():
    """The real fire-test title wraps so EVERY line fits the cover box by RENDERED
    PIXEL WIDTH (84px uppercase) and NO line is a single-word orphan. At 84px the
    char-count model wrongly produced a 2-line split that overflowed the 960px
    box (→ the browser re-split → the "TOP" orphan); the pixel model yields a
    clean wrap (here 3 lines, all within box)."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("The KITAS Bribe Trail Reaches the Top")
    lines = out.split("<br>")
    assert len(lines) >= 2  # actually wrapped
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan: {ln!r}"
    assert out.replace("<br>", " ").split() == "The KITAS Bribe Trail Reaches the Top".split()


def test_balance_headline_indonesia_visa_fee_no_orphan():
    """The 'Indonesia Visa Fee Jumps to IDR 3.5M' title (the FEE-orphan case):
    each line fits the box by pixel width, no orphan. The char model put
    'Indonesia Visa Fee' (968px) on one line — overflowing the box — and the
    browser re-split it into a FEE orphan."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    out = _balance_headline("Indonesia Visa Fee Jumps to IDR 3.5M")
    lines = out.split("<br>")
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan: {ln!r}"


def test_balance_headline_never_splits_a_word():
    """FIX#2b(a): a <br> is only ever inserted BETWEEN whole words, never inside
    one — every wrapped segment's tokens are intact words from the input."""
    from wr2_html_renderer.composer import _balance_headline

    title = "Supercalifragilistic Enforcement Crackdown Begins Now Across Bali"
    out = _balance_headline(title)
    in_words = set(title.split())
    out_words = out.replace("<br>", " ").split()
    # every emitted token is an original word (nothing was cut at a <br>)
    for w in out_words:
        assert w in in_words, f"word fragment produced: {w!r}"
    assert out_words == title.split()  # order + completeness


def test_balance_headline_parametrizable_box_width():
    """The pixel budget is parametrizable via box_width_px (e.g. a wider box or a
    smaller font). A very generous box fits the whole title on one line → no
    <br>; a tiny box forces more lines."""
    from wr2_html_renderer.composer import _balance_headline

    title = "The KITAS Bribe Trail Reaches the Top"
    assert "<br>" not in _balance_headline(title, box_width_px=100000)
    assert _balance_headline(title, box_width_px=300).count("<br>") >= 2


def test_estimate_text_width_px_calibrated():
    """The em-width estimate reproduces the real rendered width of
    'INDONESIA VISA FEE' (measured 937.3px at 84px uppercase) within ±10%."""
    from wr2_html_renderer.composer import _estimate_text_width_px

    est = _estimate_text_width_px("INDONESIA VISA FEE", font_px=84)
    assert 937.3 * 0.90 <= est <= 937.3 * 1.10, f"estimate {est:.1f}px off real 937.3px"
    # lowercase input is normalized to uppercase (the .heading transform) → same
    assert _estimate_text_width_px("indonesia visa fee", 84) == est


@pytest.mark.asyncio
async def test_designer_loop_accepts_best_render_on_composition_debt(monkeypatch):
    """FIX#4: vision rejects for a PURELY editorial reason (weak/generic hero) and
    proposes only 'rerender' (no CSS lever). The slide is legible + brand-clean,
    so the loop must ACCEPT the best render (converged=True) and flag the debt."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    # cheap tiers (geometry/legibility/ocr) pass → we reach vision
    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # rejects, but only for editorial composition + a rerender-only lever
        return dl.Critique(
            tier="vision", passed=False,
            issues=[
                "hero photo is a generic dark interior, editorially weak for this story",
                "could breathe more — spacing feels tight",
            ],
            levers=[{"lever": "rerender", "reason": "swap the hero for a stronger image"}],
            score=0.6,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=None,
        ocr_critic=None, use_vision=True, max_iters=3,
    )
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert res.reason == "accepted_with_composition_debt"
    # the editorial debt is recorded (visible, not silently dropped)
    assert any("editorially weak" in d for d in res.composition_debt)
    assert res.final_png is not None


@pytest.mark.asyncio
async def test_designer_loop_does_not_accept_on_real_legibility_residual(monkeypatch):
    """FIX#4 counter-proof: a HARD residual (a single-word orphan / unreadable
    title) is NOT composition debt — the loop must NOT converge (gate strict)."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # legibility defect (orphan word) + only a rerender lever → must NOT be
        # accepted as debt.
        return dl.Critique(
            tier="vision", passed=False,
            issues=["single-word orphan 'TOP' on line 3 — the title is hard to read"],
            levers=[{"lever": "rerender", "reason": "structural"}],
            score=0.4,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X"}, render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=None,
        ocr_critic=None, use_vision=True, max_iters=2,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False
    assert res.composition_debt == []


def test_classify_residual_issues():
    """Unit: the residual-issue classifier separates editorial debt from hard
    legibility/brand defects."""
    from wr2_html_renderer.designer_loop import (
        _classify_residual_issues,
        _is_composition_only_lever,
    )

    # pure composition
    has_hard, all_comp = _classify_residual_issues(["hero photo is generic / editorially weak"])
    assert has_hard is False and all_comp is True
    # hard legibility wins even when mixed with composition
    has_hard, all_comp = _classify_residual_issues(
        ["hero is weak", "the headline has an orphan word and is hard to read"]
    )
    assert has_hard is True and all_comp is False
    # brand drift is hard
    has_hard, _ = _classify_residual_issues(["the palette uses an off-brand blue"])
    assert has_hard is True
    # empty → not all_composition (nothing to accept)
    assert _classify_residual_issues([]) == (False, False)
    # lever classifier
    assert _is_composition_only_lever({"rerender"}) is True
    assert _is_composition_only_lever({"rerender", "scrim_opacity"}) is False
    assert _is_composition_only_lever(set()) is False


def test_balance_headline_template_max_title_no_orphan():
    """A title at the template's upper word bound (≤12 words) still wraps with
    NO single-word orphan line and every line fits the box by pixel width."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    # a clean-pairing 10-word title (consecutive words pair within the box)
    title = "KPK Arrests Top Deputy Minister in a Major Graft Case"
    out = _balance_headline(title)
    lines = out.split("<br>")
    assert len(lines) >= 3  # genuinely long → several lines
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in lines:
        assert _estimate_text_width_px(ln) <= budget, f"line overflows box: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan line: {ln!r}"
    assert out.replace("<br>", " ").split() == title.split()


def test_balance_headline_never_overflows_box_even_if_orphan_unavoidable():
    """Invariant guarantee: regardless of input, NO line ever exceeds the pixel
    budget (the browser never re-wraps). A pathological over-long title may leave
    an orphan, but it must NEVER overflow — overflow is the bug we are killing."""
    from wr2_html_renderer.composer import (
        _COVER_BOX_WIDTH_PX,
        _WRAP_SAFETY,
        _balance_headline,
        _estimate_text_width_px,
    )

    title = (
        "Indonesia Tightens Investor KITAS Rules After A Major Graft Scandal "
        "Rocks The Immigration Directorate Today"
    )
    out = _balance_headline(title)
    budget = _COVER_BOX_WIDTH_PX * _WRAP_SAFETY
    for ln in out.split("<br>"):
        # a single word longer than the box is the only allowed exception (it
        # cannot be split); here no single word is that wide.
        assert _estimate_text_width_px(ln) <= budget, f"OVERFLOW: {ln!r}"  # nothing lost


def test_orphan_grading_two_word_tail_soft_one_word_hard():
    """FIX B: orphan grading is fine-grained.

    - a ≥2-word short tail on an ALREADY-balanced wrap (rebalance committed) is
      editorial rhythm → NOT hard (acceptable composition debt);
    - the SAME claim without a re-wrap attempt → HARD (fail-safe);
    - a genuine 1-word orphan → HARD even with rebalance committed."""
    from wr2_html_renderer.designer_loop import (
        _classify_residual_issues,
        _orphan_is_hard,
    )

    two_word_tail = "THE TOP sits alone on line 3 — 2 words vs 3 on lines above"
    one_word = "single-word orphan 'TOP' alone on its own line"

    # 2-word tail + rebalance applied → soft (composition, not hard)
    has_hard, all_comp = _classify_residual_issues([two_word_tail], rebalance_applied=True)
    assert has_hard is False, "a 2-word balanced tail must NOT be a hard reject"
    assert all_comp is True, "it should classify as editorial composition"

    # same claim WITHOUT a re-wrap → fail-safe HARD
    has_hard_norewrap, _ = _classify_residual_issues([two_word_tail], rebalance_applied=False)
    assert has_hard_norewrap is True, "without re-wrap any orphan claim stays HARD"

    # 1-word orphan stays HARD even with rebalance applied
    has_hard_one, _ = _classify_residual_issues([one_word], rebalance_applied=True)
    assert has_hard_one is True, "a 1-word orphan is illegibility — must stay HARD"

    # _orphan_is_hard direct contract
    assert _orphan_is_hard(two_word_tail.lower(), rebalance_applied=True) == (True, False)
    assert _orphan_is_hard(two_word_tail.lower(), rebalance_applied=False) == (True, True)
    assert _orphan_is_hard(one_word.lower(), rebalance_applied=True) == (True, True)
    # a non-orphan claim is not graded as an orphan at all
    assert _orphan_is_hard("hero photo feels generic", rebalance_applied=True) == (False, False)


@pytest.mark.asyncio
async def test_designer_loop_accepts_two_word_tail_after_rewrap(monkeypatch):
    """FIX A+B end-to-end: after _rebalance_wrap is committed, a residual vision
    reject whose only complaint is a ≥2-word short tail (editorial rhythm) +
    rerender-only lever is ACCEPTED as composition debt → converged=True."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            # iter 1: propose rebalance_wrap (brand-inert → committed via override)
            return dl.Critique(
                tier="vision", passed=False, issues=["title leaves an orphan word"],
                levers=[{"lever": "rebalance_wrap", "reason": "orphan"}], score=0.5,
            )
        # iter 2: only complaint left is a 2-word short tail (editorial rhythm)
        return dl.Critique(
            tier="vision", passed=False,
            issues=["'Reaches the Top' sits alone on line 2 — 2 words vs 4 on the line above, uneven visual rhythm"],
            levers=[{"lever": "rerender", "reason": "could be tighter"}],
            score=0.7,
        )

    def brand_verifier(png, slide, ctx):
        # brand always clean; the inert override commits the rebalance regardless
        return dl.Critique(tier="brand", passed=True, issues=[])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "The KITAS Bribe Trail Reaches the Top"},
        render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=brand_verifier,
        ocr_critic=None, use_vision=True, max_iters=3,
    )
    assert res.converged is True
    assert res.accepted_with_composition_debt is True
    assert any("rhythm" in d for d in res.composition_debt)


# ── grow_font lever: thumbnail-legible sub-headline min-size (2026-06-10) ──────


def test_apply_levers_folds_grow_font():
    """grow_font is a real, applicable lever, symmetric to shrink_font."""
    from wr2_html_renderer.designer_loop import _apply_levers

    acc: dict = {}
    applied = _apply_levers(acc, [{"lever": "grow_font", "target": "subhead", "reason": "tiny"}])
    assert "grow_font" in [lev.get("lever") for lev in applied]
    assert acc.get("grow_subhead") == 1
    # default target is subhead
    acc2: dict = {}
    _apply_levers(acc2, [{"lever": "grow_font"}])
    assert acc2.get("grow_subhead") == 1
    # accumulates per step
    _apply_levers(acc2, [{"lever": "grow_font"}])
    assert acc2.get("grow_subhead") == 2


def test_grow_font_in_lever_sets():
    """grow_font is in the allowed vocabulary AND the brand-inert/legibility sets
    (growing a too-small text toward legibility cannot drift the brand)."""
    from wr2_html_renderer.claude_vision import _ALLOWED_LEVERS
    from wr2_html_renderer.designer_loop import (
        _BRAND_INERT_LEVERS,
        _LEGIBILITY_LEVERS,
    )

    assert "grow_font" in _ALLOWED_LEVERS
    assert "grow_font" in _LEGIBILITY_LEVERS
    assert "grow_font" in _BRAND_INERT_LEVERS


def _grow_subhead_px(css: str) -> int | None:
    """Pull the absolute .subheading font-size (px) out of a lever CSS block."""
    import re

    m = re.search(r"\.subhead,\.subheading\{font-size:(\d+)px", css)
    return int(m.group(1)) if m else None


def _grow_heading_px(css: str) -> int | None:
    """Pull the absolute .heading font-size (px) out of a lever CSS block."""
    import re

    m = re.search(r"\.headline,\.heading,h1\{font-size:(\d+)px", css)
    return int(m.group(1)) if m else None


def test_levers_to_css_grow_font_floor_and_cap():
    """grow_font targets the sub-headline with an ABSOLUTE px size: step 1 lands
    on the floor and a high step is clamped to the cap, never above."""
    from wr2_html_renderer.composer import _GROW_CLAMP_PX, _levers_to_css

    min_px, cap_px = _GROW_CLAMP_PX["subhead"]
    css1 = _levers_to_css({"grow_subhead": 1})
    assert ".subhead" in css1  # targets the sub-headline element
    assert _grow_subhead_px(css1) == min_px  # step 1 == floor
    # a high step is clamped to the cap, never above
    assert _grow_subhead_px(_levers_to_css({"grow_subhead": 9})) == cap_px
    # no grow lever → no grow CSS at all
    assert _grow_subhead_px(_levers_to_css({"text_stroke": True})) is None


def test_grow_subhead_never_exceeds_title_no_hierarchy_inversion():
    """BUG #2 (hierarchy inversion): the sub-headline (kicker) grow must NEVER
    reach or exceed the cover title font-size — at ANY step. The kicker is an
    accessory tag; the title must stay the largest element. Measured at the CSS
    level here; pixel-verified in the E2E probe."""
    from wr2_html_renderer.composer import (
        _GROW_CLAMP_PX,
        _HEADING_BASE_PX,
        _levers_to_css,
    )

    sub_min, sub_cap = _GROW_CLAMP_PX["subhead"]
    # the cap itself is strictly below the cover title base
    assert sub_cap < _HEADING_BASE_PX, (
        f"subhead grow cap {sub_cap}px must stay below title {_HEADING_BASE_PX}px"
    )
    assert sub_min <= sub_cap
    # every grow step keeps the subhead below the title
    for n in (1, 2, 3, 5, 10, 20):
        px = _grow_subhead_px(_levers_to_css({"grow_subhead": n}))
        assert px < _HEADING_BASE_PX, f"grow_subhead={n} → {px}px ≥ title (inversion)"


def test_grow_heading_grows_title_and_stays_largest():
    """grow_font target=heading enlarges the TITLE above its base, and even when
    BOTH grow, the title stays larger than the kicker (hierarchy preserved)."""
    from wr2_html_renderer.composer import _HEADING_BASE_PX, _levers_to_css

    css = _levers_to_css({"grow_heading": 1})
    head_px = _grow_heading_px(css)
    assert head_px is not None and head_px >= _HEADING_BASE_PX
    # both grown at once: title still dominates the kicker
    both = _levers_to_css({"grow_heading": 1, "grow_subhead": 9})
    assert _grow_heading_px(both) > _grow_subhead_px(both)


def test_levers_to_css_grow_font_progresses_each_step():
    """REGRESSION (the (52,64)/calc(1em*) no-op bug): grow steps must RISE
    (non-decreasing, strictly rising at least once before the cap), never a flat
    constant. The subhead cap range is small, so it rises then plateaus at cap."""
    from wr2_html_renderer.composer import _GROW_CLAMP_PX, _levers_to_css

    min_px, cap_px = _GROW_CLAMP_PX["subhead"]
    sizes = [_grow_subhead_px(_levers_to_css({"grow_subhead": n})) for n in (1, 2, 3, 4)]
    assert sizes[0] == min_px  # step 1 is the floor
    assert sizes == sorted(sizes)  # non-decreasing
    assert sizes[-1] > sizes[0], f"never grew: {sizes}"  # rose at least once
    assert all(px <= cap_px for px in sizes)  # never above cap
    # a very high step is exactly the cap
    assert _grow_subhead_px(_levers_to_css({"grow_subhead": 20})) == cap_px
    # body grow (larger range) rises across consecutive steps too
    body_sizes = []
    for n in (1, 2, 3):
        import re

        css = _levers_to_css({"grow_body": n})
        m = re.search(r"font-size:(\d+)px", css)
        body_sizes.append(int(m.group(1)))
    assert body_sizes[1] > body_sizes[0] and body_sizes[2] > body_sizes[1]


@pytest.mark.asyncio
async def test_designer_loop_grow_font_repairs_small_subhead(monkeypatch):
    """The repair flow: vision flags an illegible (too-small) sub-headline and
    proposes grow_font; the loop APPLIES it (brand-clean), re-renders, and on the
    next pass the text is legible → converges. Illegibility is REPAIRED, not
    accepted as debt."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    calls = {"vision": 0}

    def vision_critic(png, slide, ctx):
        calls["vision"] += 1
        if calls["vision"] == 1:
            return dl.Critique(
                tier="vision", passed=False,
                issues=["sub-headline is illegible at Instagram thumbnail scale"],
                levers=[{"lever": "grow_font", "target": "subhead", "reason": "too small to read"}],
                score=0.5,
            )
        return dl.Critique(tier="vision", passed=True, issues=[], levers=[], score=0.95)

    def brand_verifier(png, slide, ctx):
        return dl.Critique(tier="brand", passed=True, issues=[])

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X", "subhead": "tiny sub"}, render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=brand_verifier,
        ocr_critic=None, use_vision=True, max_iters=3,
    )
    assert res.converged is True
    # grow_font was applied, NOT accepted as composition debt
    assert res.accepted_with_composition_debt is False
    assert any(rec.get("vision_levers_pulled") for rec in res.history)


@pytest.mark.asyncio
async def test_designer_loop_never_accepts_illegible_subhead_as_debt(monkeypatch):
    """Counter-proof: an illegible sub-headline with ONLY a rerender lever (no
    grow available to pull) must NEVER be accepted as composition debt — the gate
    stays strict (converged=False)."""
    import base64

    from wr2_html_renderer import designer_loop as dl

    class _Pass:
        passed = True
        levers: list = []
        score = 1.0
        issues: list = []
        tier = "mock"

    monkeypatch.setattr(dl, "critic_geometry", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_legibility", lambda *a, **k: _Pass())
    monkeypatch.setattr(dl, "critic_ocr", lambda *a, **k: _Pass())
    monkeypatch.delenv("WR2_VISION_REQUIRED", raising=False)

    def vision_critic(png, slide, ctx):
        # legibility defect but only a structural lever proposed → not CSS-fixable
        return dl.Critique(
            tier="vision", passed=False,
            issues=["sub-headline is unreadable / illegible at thumbnail scale"],
            levers=[{"lever": "rerender", "reason": "structural"}],
            score=0.3,
        )

    async def render_fn(slide, png_path):
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        ))

    out = Path(tempfile.mkdtemp())
    res = await dl.run_designer_loop(
        slide={"headline": "X", "subhead": "tiny"}, render_fn=render_fn, out_dir=out,
        vision_critic=vision_critic, brand_verifier=None,
        ocr_critic=None, use_vision=True, max_iters=2,
    )
    assert res.converged is False
    assert res.accepted_with_composition_debt is False


def test_fill_placeholders_schema_fallback_old_and_new():
    """BUG #3: _fill_placeholders reads BOTH schema variants — old Canva drafts
    (heading/subheading) and new drafts (headline/subhead) — so an old-schema
    cover is never rendered blank."""
    from wr2_html_renderer.composer import _fill_placeholders

    html = "<h1>{{heading}}</h1><div class='subheading'>{{subheading}}</div><p>{{body}}</p>"
    # OLD schema: heading/subheading/body present, headline/subhead absent
    out_old = _fill_placeholders(
        html, {"heading": "OLD TITLE", "subheading": "OLD KICKER", "body": "old body"},
        hero_filename=None,
    )
    assert "OLD TITLE" in out_old and "OLD KICKER" in out_old and "old body" in out_old
    assert "{{heading}}" not in out_old and "{{subheading}}" not in out_old
    # NEW schema still works
    out_new = _fill_placeholders(
        html, {"headline": "NEW TITLE", "subhead": "NEW KICKER", "body": "new body"},
        hero_filename=None,
    )
    assert "NEW TITLE" in out_new and "NEW KICKER" in out_new and "new body" in out_new


# ── classifier word-boundary + soft-exclusion (W68/W72/W73 class) 2026-06-10 ──


def test_classifier_editorial_conditional_claims_not_false_hard():
    """The 4 real verdict claims that the bare-substring classifier false-HARD'd
    must now classify as SOFT (editorial/conditional) so a correctly-rendered
    draft can converge. W68/W72/W73 discipline: don't clobber a correct output."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    # "wrap" inside an already-rebalanced 3-line stub complaint → editorial rhythm
    hh, ac = _classify_residual_issues(
        ["Title wrap produces a 3-line stub"], rebalance_applied=True
    )
    assert hh is False and ac is True
    # "color" as an accent SUGGESTION → not palette drift
    hh, ac = _classify_residual_issues(
        ["Consider popping the datum in a brand accent color"]
    )
    assert hh is False and ac is True
    # "legibility" in a CONDITIONAL claim ("may drop below") → hypothetical
    hh, ac = _classify_residual_issues(["Logo may drop below legibility on a busy hero"])
    assert hh is False and ac is True
    # critic AFFIRMS correct + "may be illegible" hedge → not an actual defect
    hh, ac = _classify_residual_issues(
        ["The eyebrow is the correct brand treatment but may be an illegible smear"]
    )
    assert hh is False and ac is True


def test_classifier_real_defects_stay_hard():
    """COUNTER-PROOFS: actual, categorical, blocking defects MUST stay HARD — the
    gate must not go soft. We never publish illegible/clipped/off-palette."""
    from wr2_html_renderer.designer_loop import _classify_residual_issues

    # categorical illegibility (no may/might) → HARD
    assert _classify_residual_issues(["subhead is illegible at thumbnail scale"])[0] is True
    # actual clipping → HARD
    assert _classify_residual_issues(
        ["the title is clipped at the right edge, cut off"]
    )[0] is True
    # genuine 1-word orphan → HARD (even after a re-wrap)
    assert _classify_residual_issues(
        ["single-word orphan TOP alone on line 3"], rebalance_applied=True
    )[0] is True
    # real palette drift → HARD
    assert _classify_residual_issues(["off-brand color, not in palette"])[0] is True


def test_classifier_word_boundary_not_bare_substring():
    """The markers match on WORD BOUNDARY, so they do NOT fire inside longer
    words (the W73 bare-substring trap): "rewrap"/"discolor"/"legible" must not
    trip "wrap"/"color"/"illegible"-style HARD matches."""
    from wr2_html_renderer.designer_loop import _claim_is_hard, _contains_any_word

    # word-boundary helper basics
    assert _contains_any_word("the title is clipped", ("clipped",)) is True
    assert _contains_any_word("a rewrap of the line", ("wrap",)) is False
    assert _contains_any_word("off the edge of frame", ("off the edge",)) is True
    # _claim_is_hard: "legible" (positive) is NOT illegible → not hard
    assert _claim_is_hard("the headline is legible and crisp") is False
    # "discoloration" must not trip a bare "color" hard match
    assert _claim_is_hard("a faint discoloration in the photo background") is False
    # but a real categorical defect is hard
    assert _claim_is_hard("the text is unreadable") is True


def test_classifier_conditional_marker_downgrades_legibility():
    """A 'may/might/could' hedge in front of a legibility word downgrades it from
    HARD to editorial — but the SAME claim without the hedge stays HARD."""
    from wr2_html_renderer.designer_loop import _claim_is_hard

    assert _claim_is_hard("the subhead might be illegible at small sizes") is False
    assert _claim_is_hard("the subhead is illegible at small sizes") is True
