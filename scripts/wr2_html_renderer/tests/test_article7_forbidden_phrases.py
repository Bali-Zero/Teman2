"""Article 7 (forbidden phrases) hard-gate tests (cure item 13, 2026-07-14 —
research/operations/2026-07-14-wr2-deep-audit.md §5: "Art 7 forbidden-phrase
list (no scanner anywhere in the engine — grep verified)").

Guilt AND innocence per the guard-conformance doctrine (scar family #3 —
substring trapping): every guard needs a test that PROVES it fires on a real
violation and a test that PROVES it does NOT fire on a legitimate neighbor
(a banned single word appearing as a substring INSIDE a longer, innocent
word must not trigger — the exact W-shape that has bitten this repo before).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from wr2_html_renderer import composer as C  # noqa: E402


def test_loads_the_real_constitution_closed_list():
    """Ground truth: parses straight from constitution.md, not a hardcoded
    copy — 22 bullets, one ('swipe to`/`swipe for') carries 2 phrases = 23."""
    phrases = C._load_forbidden_phrases()
    assert len(phrases) == 23
    assert "delve into" in phrases
    assert "synergy" in phrases
    assert "swipe to" in phrases
    assert "swipe for" in phrases


def test_missing_constitution_file_fails_closed(tmp_path):
    """Fail-closed idiom (mirrors tokens_to_css.load_tokens /
    _brand_base_css_body): no phrase list, no render — never soft-pass."""
    with pytest.raises(FileNotFoundError):
        C._load_forbidden_phrases(tmp_path / "nope.md")


def test_missing_article_7_section_is_fail_visible(tmp_path):
    bad = tmp_path / "constitution.md"
    bad.write_text("# Bali Zero Brand Constitution\n\n## Article 1 — Format\n...\n")
    with pytest.raises(ValueError):
        C._load_forbidden_phrases(bad)


# --- GUILT: single-word phrase fires on the whole word --------------------

@pytest.mark.parametrize(
    "phrase,text",
    [
        ("unlock", "please unlock your KITAS today"),
        ("landscape", "the regulatory landscape shifted overnight"),
        ("paradise", "this is not paradise, it is paperwork"),
        ("synergy", "we found real synergy between the two filings"),
        ("game-changer", "PP 20/2026 is a real game-changer for PT PMA"),
        ("delve into", "let us delve into the new tax rules"),
        ("let's dive in", "let's dive in now"),
        ("DM us", "just DM us for a quote"),
    ],
)
def test_guilt_phrase_fires(phrase, text):
    assert C._forbidden_phrase_pattern(phrase).search(text), (phrase, text)


# --- INNOCENCE: banned word as a substring of a longer legitimate word ----

@pytest.mark.parametrize(
    "phrase,text",
    [
        ("unlock", "the unlockable feature is not available"),
        ("landscape", "the landscaper redesigned the villa garden"),
        ("realm", "the realmost setting was unrelated"),  # contrived but proves boundary
        ("journey", "journeyman electricians are in short supply"),
        ("ecosystem", "the ecosystemic study looked at soil health"),
    ],
)
def test_innocence_substring_inside_longer_word_does_not_fire(phrase, text):
    assert not C._forbidden_phrase_pattern(phrase).search(text), (phrase, text)


def test_innocence_clean_copy_no_match():
    slide = {
        "headline": "KITAS RENEWAL RULES CHANGED",
        "body": "New KITAS renewals now require the sponsor's NPWP on file "
        "before OSS will process the extension, effective this quarter for "
        "every foreign worker permit renewal filed after May.",
    }
    result = C._check_forbidden_phrases(slide, index=1)
    assert result is None  # did not raise


def test_guilt_raises_with_slide_and_phrase_named():
    slide = {"headline": "PLEASE UNLOCK YOUR KITAS TODAY"}
    with pytest.raises(ValueError) as exc_info:
        C._check_forbidden_phrases(slide, index=3)
    msg = str(exc_info.value)
    assert "slide 3" in msg
    assert "unlock" in msg


def test_guilt_collects_multiple_hits_across_fields():
    slide = {
        "headline": "LET'S DIVE IN TO PARADISE",
        "body": "our seamless synergy makes it a real game-changer for you",
    }
    with pytest.raises(ValueError) as exc_info:
        C._check_forbidden_phrases(slide, index=5)
    msg = str(exc_info.value)
    # at least the heading AND body violations are both reported, not just
    # the first hit found (single retry should fix everything at once)
    assert "heading=" in msg
    assert "body=" in msg


def test_sweep_real_manual_asset_carousels_stay_clean():
    """Regression guard: the two shipped example carousels in
    docs/wr2/manual-assets/ must not spuriously trip Article 7 (they predate
    this gate but were hand-authored to brand voice already)."""
    import glob
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    pattern = str(root / "docs" / "wr2" / "manual-assets" / "*" / "slides.json")
    files = glob.glob(pattern)
    if not files:
        pytest.skip("manual-assets fixtures not present on this machine")
    checked = 0
    for f in files:
        data = json.loads(Path(f).read_text())
        slides = data.get("slides", data) if isinstance(data, dict) else data
        for i, slide in enumerate(slides, 1):
            C._check_forbidden_phrases(slide, index=i)  # must not raise
            checked += 1
    assert checked > 0, "no slides checked — blind sweep (W84 guard)"
