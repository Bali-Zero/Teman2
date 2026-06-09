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
    """FIX#2b: _balance_headline wraps a long headline into one-or-more lines via
    <br>, each within the width budget and with no single-word orphan line."""
    from wr2_html_renderer.composer import _COVER_MAX_CHARS_PER_LINE, _balance_headline

    out = _balance_headline("KPK ARRESTS TOP DEPUTY MINISTER ON GRAFT")
    assert "<br>" in out
    lines = out.split("<br>")
    assert len(lines) >= 2  # actually wrapped
    # every line within budget (so the browser won't re-wrap) + no orphan word
    for ln in lines:
        assert len(ln) <= _COVER_MAX_CHARS_PER_LINE, f"line too wide: {ln!r}"
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


def test_balance_headline_real_title_multiline_no_orphan():
    """FIX#2b(a)+FIX A: at the cover default (cap 22) the real fire-test title
    settles on exactly 2 balanced lines — what the vision critic asks for — each
    within the budget, with NO single-word orphan ("TOP" eliminated)."""
    from wr2_html_renderer.composer import _COVER_MAX_CHARS_PER_LINE, _balance_headline

    out = _balance_headline("The KITAS Bribe Trail Reaches the Top")
    lines = out.split("<br>")
    # FIX A: cap 22 yields the 2-line "The KITAS Bribe Trail / Reaches the Top"
    assert len(lines) == 2, f"expected 2 balanced lines, got {lines!r}"
    # every line stays within the safe width (so the browser won't re-wrap)
    for ln in lines:
        assert len(ln) <= _COVER_MAX_CHARS_PER_LINE, f"line too wide: {ln!r}"
    # no single-word orphan line anywhere (last line has >=2 words)
    for ln in lines:
        assert len(ln.split()) >= 2, f"orphan line: {ln!r}"
    # words preserved in order (only <br>s inserted between whole words)
    assert out.replace("<br>", " ").split() == "The KITAS Bribe Trail Reaches the Top".split()


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


def test_balance_headline_parametrizable_budget():
    """The line-width budget is parametrizable (smaller fonts pass a larger one)."""
    from wr2_html_renderer.composer import _balance_headline

    title = "The KITAS Bribe Trail Reaches the Top"
    # a generous budget lets the whole title fit on one line → no <br>
    assert "<br>" not in _balance_headline(title, max_chars_per_line=200)


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


def test_balance_headline_long_title_no_one_word_orphan():
    """FIX A: a much longer title (10+ words) still wraps with NO single-word
    orphan line — the larger cap must not re-introduce a lone-word last line."""
    from wr2_html_renderer.composer import _COVER_MAX_CHARS_PER_LINE, _balance_headline

    title = (
        "Indonesia Tightens Investor KITAS Rules After A Major Graft Scandal "
        "Rocks The Immigration Directorate Today"
    )
    out = _balance_headline(title)
    lines = out.split("<br>")
    assert len(lines) >= 3  # genuinely long → several lines
    for ln in lines:
        assert len(ln) <= _COVER_MAX_CHARS_PER_LINE, f"line too wide: {ln!r}"
        assert len(ln.split()) >= 2, f"single-word orphan line: {ln!r}"
    assert out.replace("<br>", " ").split() == title.split()  # nothing lost


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


def test_levers_to_css_grow_font_clamps_to_legible_min_with_cap():
    """grow_font emits a font-size:clamp(min, grown, cap) on the sub-headline so a
    single grow already clears the thumbnail-legible floor and never overflows."""
    from wr2_html_renderer.composer import _GROW_CLAMP_PX, _levers_to_css

    min_px, cap_px = _GROW_CLAMP_PX["subhead"]
    css = _levers_to_css({"grow_subhead": 1})
    assert ".subhead" in css  # targets the sub-headline element
    assert f"clamp({min_px}px" in css  # legible-min floor present
    assert f"{cap_px}px)" in css       # anti-overflow cap present
    assert "font-size" in css
    # no grow lever → no grow CSS
    assert "clamp(" not in _levers_to_css({"text_stroke": True})


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
