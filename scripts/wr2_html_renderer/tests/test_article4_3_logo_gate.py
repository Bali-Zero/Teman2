"""Article 4.3 (logo on every slide) hard-gate tests (cure item 13,
2026-07-14 — research/operations/2026-07-14-wr2-deep-audit.md §5: "Art 4.3
logo-on-every-slide (warning only, renderer.py:130)").

Two mechanisms, two test groups:
  1. _stage_assets: promoted from logger.warning to a hard FileNotFoundError
     when the master logo.png asset is missing (staging-time, fail-fast).
  2. _readiness_logo_ok: per-slide render-time gate predicate (mirrors the
     W99 BRAND FONT NOT LOADED mechanism — a boolean read off the in-page
     readiness probe), pulled out as a pure function so it's testable
     without a live Chromium page.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import renderer as R  # noqa: E402


# --- _stage_assets: staging-time hard gate ----------------------------------

def test_guilt_missing_master_logo_asset_hard_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "_BRAND_LOGO", tmp_path / "does-not-exist.png")
    out_dir = tmp_path / "out"
    with pytest.raises(FileNotFoundError, match=r"Article 4\.3"):
        R._stage_assets(out_dir)


def test_innocence_present_master_logo_asset_stages_cleanly(tmp_path, monkeypatch):
    fake_logo = tmp_path / "logo.png"
    # minimal valid PNG bytes (1x1 transparent) — _stage_assets only copies
    # the file, it doesn't decode it, so any real file proves the branch.
    fake_logo.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001080600000"
            "01f15c4890000000a49444154789c6360000002000155001e0e5a9a00"
            "0000004945454e44ae426082"
        )
    )
    out_dir = tmp_path / "out"
    monkeypatch.setattr(R, "_BRAND_LOGO", fake_logo)
    # _stage_assets also reads the brand _base.css and tokens.json — those
    # ARE expected to exist in this repo checkout (brand skill is checked
    # in), so we exercise the real path rather than mocking them away.
    if not (R.Path.home() / ".claude" / "skills" / "bali-zero-brand" / "layouts" / "_base.css").is_file():
        pytest.skip("brand skill _base.css not present on this machine")
    R._stage_assets(out_dir)
    assert (out_dir / "logo.png").is_file()
    assert (out_dir / "logo.png").read_bytes() == fake_logo.read_bytes()


# --- _readiness_logo_ok: per-slide render-time gate predicate ---------------

def test_guilt_no_logo_element_fails():
    assert not R._readiness_logo_ok({"logo_present": False, "logo_bg_ok": False})


def test_guilt_logo_element_present_but_background_unresolved_fails():
    """The element exists (a stray `.logo` div in markup) but its CSS
    background-image never loaded (e.g. logo.png 404 under file://) — must
    still fail, matching the montserrat gate's boolean-truth mechanism."""
    assert not R._readiness_logo_ok({"logo_present": True, "logo_bg_ok": False})


def test_innocence_logo_present_and_loaded_passes():
    assert R._readiness_logo_ok({"logo_present": True, "logo_bg_ok": True})


def test_innocence_missing_keys_default_to_fail_not_crash():
    """Defensive: a readiness dict from an older/odd page (missing the new
    keys entirely) must fail closed, not raise a KeyError."""
    assert not R._readiness_logo_ok({})


def test_sweep_real_layout_library_every_family_declares_a_logo_div():
    """Ground-truth precondition for the blanket (no-exception) gate: every
    layout family's skeleton bakes a `.logo` div. If a future family adds a
    legitimate no-logo variant (e.g. a full-bleed hero with no mark), this
    sweep must be updated to encode that exception explicitly — the gate
    must never silently blanket-fail a slide type that's allowed to skip it."""
    from pathlib import Path

    layouts_dir = Path.home() / ".claude" / "skills" / "bali-zero-brand" / "layouts"
    if not layouts_dir.is_dir():
        pytest.skip("brand layouts dir not present on this machine")
    checked = 0
    for md in sorted(layouts_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        if "```html" not in text:
            continue  # _base.css and other non-skeleton .md files
        assert 'data-zone-type="logo"' in text, md.name
        checked += 1
    assert checked > 0, "no skeletons checked — blind sweep (W84 guard)"
