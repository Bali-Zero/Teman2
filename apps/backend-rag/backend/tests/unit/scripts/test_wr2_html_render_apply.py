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
    """FIX#2c: _balance_headline splits a long headline into two balanced lines
    via <br>, with no single-word line."""
    from wr2_html_renderer.composer import _balance_headline

    out = _balance_headline("KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT")
    assert "<br>" in out
    line1, line2 = out.split("<br>")
    # neither side is a lone orphan word
    assert len(line1.split()) >= 2
    assert len(line2.split()) >= 2
    # round-trips the words (only a <br> was inserted, nothing dropped/reordered)
    assert out.replace("<br>", " ").split() == "KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT".split()
    # reasonably balanced (the split minimises the length delta)
    assert abs(len(line1) - len(line2)) <= len("KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT")


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
    """FIX#3: the pure-legibility lever set is exactly scrim/stroke/shrink."""
    from wr2_html_renderer.designer_loop import _LEGIBILITY_LEVERS

    assert _LEGIBILITY_LEVERS == {"scrim_opacity", "text_stroke", "shrink_font"}


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
    # the committed scrim lever is reflected in the history
    assert any(
        rec.get("brand_verify_legibility_override")
        for rec in res.history
    )
