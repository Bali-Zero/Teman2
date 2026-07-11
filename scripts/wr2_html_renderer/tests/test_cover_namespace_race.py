"""Regression test for the cover-drop bug (superscar #5 shared-namespace race /
#9 path mutation drift), 2026-06-30.

SYMPTOM: WR2 draft 62b6b577 rendered to status='rendered' but uploaded only
`02.png..08.png + logo.png` to Drive — `01.png` (the cover) was MISSING. The
carousel opened with the "OUR READ" editorial slide because the cover was gone.

ROOT CAUSE: `make_slide_render_fn` rendered every slide via `render_html_files`
with a SINGLE-element spec list. `render_html_files` names its output by the
1-based position in that list (`renderer.py: png_path = slides_out/f"{idx:02d}.png"`),
which is ALWAYS "01.png" for a 1-element list. The output landed in the SHARED
`slides_dir` (render_root = slides_dir.parent → render_root/"slides" == slides_dir).
So slide 2's render transiently wrote `slides_dir/01.png`, CLOBBERING slide 1's
already-placed cover before the upload glob ran.

CURE: render each slide into a PRIVATE scratch dir (`slides_dir/.render-NN/`),
then move the PNG to its canonical slot. The transient "01.png" can no longer
collide with another slide's canonical home.

This test drives `make_slide_render_fn` for slide index 2 with a faked
`render_html_files` that reproduces the real "always writes 01.png in its
output_dir/slides" behavior, and asserts the pre-existing cover `slides_dir/01.png`
SURVIVES and the slide-2 PNG lands at the slide-2 png_path.
"""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


@pytest.mark.asyncio
async def test_per_slide_render_does_not_clobber_the_cover(tmp_path, monkeypatch):
    from wr2_html_renderer import composer as comp

    slides_dir = tmp_path / "carousel" / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)

    # slide 1 (cover) already placed at its canonical slot by an earlier loop iter
    cover = slides_dir / "01.png"
    cover.write_bytes(b"COVER-PNG-ORIGINAL")

    # avoid real asset staging + HTML materialization + browser
    monkeypatch.setattr(comp, "_stage_assets", lambda *a, **k: None)

    async def fake_materialize(slide, sdir, *, index, total, hero_filename=None):
        # the real one writes {index:02d}.html into sdir; mimic that
        Path(sdir).mkdir(parents=True, exist_ok=True)
        (Path(sdir) / f"{index:02d}.html").write_text("<html></html>", encoding="utf-8")
        return (Path(sdir) / f"{index:02d}.html", True)

    monkeypatch.setattr(comp, "materialize_slide_html", fake_materialize)

    class _Res:
        # reproduce the REAL render_html_files contract: it writes
        # output_dir/slides/01.png (1-based position in a 1-element list) and
        # returns that path in png_paths.
        def __init__(self, png_paths):
            self.png_paths = png_paths

    async def fake_render_html_files(specs, output_dir, *, timeout_ms=30000, make_pdf=True):
        out = Path(output_dir) / "slides"
        out.mkdir(parents=True, exist_ok=True)
        png = out / "01.png"  # <-- the bug-shaped behavior: ALWAYS 01.png
        png.write_bytes(b"SLIDE-2-PNG")
        return _Res([png])

    # render_html_files is imported INSIDE make_slide_render_fn via
    # `from .renderer import render_html_files`, so patch it on the renderer module.
    from wr2_html_renderer import renderer as rnd
    monkeypatch.setattr(rnd, "render_html_files", fake_render_html_files)

    render_fn = comp.make_slide_render_fn(
        slides_dir=slides_dir, index=2, total=8, hero_filename=None, timeout_ms=1000,
    )
    slide2_png = slides_dir / "02.png"
    await render_fn({"headline": "B", "body": "x"}, slide2_png)

    # THE COVER MUST SURVIVE — this is the whole bug.
    assert cover.is_file(), "cover 01.png was clobbered by slide-2 render"
    assert cover.read_bytes() == b"COVER-PNG-ORIGINAL", "cover content was overwritten"
    # and slide 2 must land at its own slot
    assert slide2_png.is_file(), "slide-2 PNG did not land at its canonical slot"
    assert slide2_png.read_bytes() == b"SLIDE-2-PNG"
    # the private scratch dir must be cleaned up (no .render-02 pollution)
    assert not (slides_dir / ".render-02").exists(), "scratch dir not cleaned"


if __name__ == "__main__":
    import asyncio

    class _MP:
        def setattr(self, o, n, v):
            setattr(o, n, v)
    # minimal manual run not supported (needs monkeypatch fixture); use pytest.
    print("run via: pytest scripts/wr2_html_renderer/tests/test_cover_namespace_race.py -q")
