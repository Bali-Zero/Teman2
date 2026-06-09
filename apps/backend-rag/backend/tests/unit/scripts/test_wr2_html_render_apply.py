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
