"""
Regression tests for scripts/wr2_ig_caption.py — the WR2 Instagram caption author.

Covers the 3 bugs found by adversarial observers on real fixtures, plus a
happy-path snapshot of the real `indonesia-visafree-myth-reality` carousel:

  BUG #1 (crash) — nested-dict bilingual_lexicon does NOT crash build_caption.
  BUG #2 (crash, superscar #3 over-match) — a caption with ✓/✗ status glyphs
          SURVIVES the emoji guard (INNOCENCE), while a real emoji like 🎉 IS
          still stripped (GUILT).
  BUG #3 (cosmetic) — an all-caps nationality list keeps proper-case
          ("Thailand and Vietnam", never "...and vietnam").
  Happy-path — the real visafree carousel yields a caption that has the
          disclaimer, is under the 2200-char IG limit, and carries >=8 hashtags.

Fixtures: the carousel output dir (`apps/war-room/output/`) is gitignored, so
it is absent from the agent worktree. Tests that need real briefs copy them
from the main checkout into a tmp carousel root, or build synthetic carousels
in tmp — so the suite is self-contained and runs from any checkout.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

# Make `scripts/` importable regardless of the pytest rootdir.
_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
import sys

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import wr2_ig_caption as cap  # noqa: E402


# --------------------------------------------------------------------------- #
# Real-fixture discovery (main checkout — output/ is gitignored)
# --------------------------------------------------------------------------- #

# Walk up to find a checkout that physically has the carousel output dir.
def _find_real_carousel_base() -> Path | None:
    here = Path(__file__).resolve()
    candidates: list[Path] = []
    for parent in here.parents:
        candidates.append(parent / "apps" / "war-room" / "output" / "carousel")
    # Also try the canonical main checkout (worktrees keep output/ in the main
    # checkout only).
    candidates.append(
        Path("/Users/balizero/Desktop/nuzantara/apps/war-room/output/carousel")
    )
    for c in candidates:
        if c.is_dir():
            return c
    return None


_REAL_BASE = _find_real_carousel_base()
_VISAFREE_SLUG = "indonesia-visafree-myth-reality"


def _write_carousel(base: Path, slug: str, brief: dict, slides: dict) -> None:
    d = base / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "brief.json").write_text(json.dumps(brief), encoding="utf-8")
    (d / "slides.json").write_text(json.dumps(slides), encoding="utf-8")


def _minimal_slides(heading: str, *, extra_slides: list[dict] | None = None) -> dict:
    slides = [{"index": 1, "heading": heading, "layout_family": "cover-photo"}]
    if extra_slides:
        slides.extend(extra_slides)
    return {"carousel_id": "test", "slides": slides}


def _minimal_brief(**overrides) -> dict:
    brief = {
        "topic": "Test carousel",
        "domain": "visa",
        "hook_angle": "A real plain-language regulatory fact goes here.",
        "key_facts": ["A second fact for the body."],
    }
    brief.update(overrides)
    return brief


# --------------------------------------------------------------------------- #
# BUG #1 — nested-dict lexicon does NOT crash
# --------------------------------------------------------------------------- #


def test_bug1_nested_dict_lexicon_does_not_crash(tmp_path: Path) -> None:
    """A brief whose lexicon is the nested-dict shape must build, not crash.

    Real fixtures (e31a-spouse-visa, kep71-spt-extension-test-5) ship the
    lexicon as {"always_untranslated": [...], "assist_on_first_use": [...]}.
    The pre-fix code iterated it as a list and called .get on a str key ->
    AttributeError -> no caption.
    """
    nested_lexicon = {
        "always_untranslated": [
            {"id_term": "KITAS", "english_assist": None, "always_untranslated": True},
            {"id_term": "KITAP", "english_assist": None, "always_untranslated": True},
        ],
        "assist_on_first_use": [
            {
                "id_term": "PENJAMIN",
                "english_assist": "immigration sponsor",
                "always_untranslated": False,
            },
        ],
    }
    brief = _minimal_brief(bilingual_lexicon_with_english_assist=nested_lexicon)
    slides = _minimal_slides("E31A SPOUSE VISA — WORK WITHOUT A SPONSOR")
    _write_carousel(tmp_path, "nested-lex", brief, slides)

    caption = cap.build_caption("nested-lex", base_dir=tmp_path)
    assert isinstance(caption, str)
    assert caption  # non-empty
    assert cap.DISCLAIMER in caption


def test_bug1_normalize_lexicon_all_shapes() -> None:
    """The normalizer handles flat-list, nested-dict, None, and garbage."""
    # Flat list
    flat = [{"id_term": "BVK"}, {"id_term": "VoA"}]
    assert len(cap._normalize_lexicon(flat)) == 2
    # Nested dict
    nested = {"always_untranslated": [{"id_term": "KITAS"}], "assist_on_first_use": [{"id_term": "IMTA"}]}
    norm = cap._normalize_lexicon(nested)
    assert len(norm) == 2
    assert {t["id_term"] for t in norm} == {"KITAS", "IMTA"}
    # None / missing
    assert cap._normalize_lexicon(None) == []
    # Garbage (bare string) — must not crash
    assert cap._normalize_lexicon("nonsense") == []
    # Entries that are not dicts are dropped
    assert cap._normalize_lexicon([{"id_term": "OK"}, "junk", 42]) == [{"id_term": "OK"}]


# --------------------------------------------------------------------------- #
# BUG #2 — emoji guard over-match on legitimate ✓/✗ (superscar #3)
# --------------------------------------------------------------------------- #


def test_bug2_innocence_checkmarks_survive(tmp_path: Path) -> None:
    """INNOCENCE: a caption whose slides carry ✓/✗ status glyphs is NOT killed.

    WR2 dark-status-list slides legitimately contain ✓ (U+2713) and ✗ (U+2717),
    which live inside the historical emoji range — a naive guard swallowed them
    and emptied the caption.
    """
    status_body = "§ SUBSTANCE GATE:\n✓ STEM FIELD\n✓ 5+ YEARS\n✗ NOMAD WITHOUT STEM"
    slides = _minimal_slides(
        "WHO QUALIFIES",
        extra_slides=[{"index": 2, "heading": "GATES", "body": status_body}],
    )
    brief = _minimal_brief(
        hook_angle="The substance gate ✓ and the procedure gate ✗ both matter.",
    )
    _write_carousel(tmp_path, "glyphs", brief, slides)

    caption = cap.build_caption("glyphs", base_dir=tmp_path)
    assert isinstance(caption, str)
    assert caption.strip()  # survived — not empty
    assert cap.DISCLAIMER in caption
    # The glyphs were transliterated, not silently dropped to nothing.
    assert "✓" not in caption and "✗" not in caption  # guard ran
    assert "yes:" in caption or "no:" in caption  # transliterated, not killed


def test_bug2_innocence_strip_emoji_keeps_checkmark_content() -> None:
    """The guard itself transliterates ✓/✗ rather than deleting them."""
    out = cap._strip_emoji("✓ STEM FIELD\n✗ NO STEM")
    assert "STEM FIELD" in out
    assert "yes:" in out
    assert "no:" in out
    assert "✓" not in out and "✗" not in out
    # Heavy variants too.
    out2 = cap._strip_emoji("✔ done ✖ blocked")
    assert "yes:" in out2 and "no:" in out2


def test_bug2_guilt_real_emoji_is_stripped() -> None:
    """GUILT: a real emoji like 🎉 IS still removed by the guard."""
    out = cap._strip_emoji("We did it 🎉 today")
    assert "🎉" not in out
    assert "We did it" in out and "today" in out
    # A few more real emoji to be sure the class still bites.
    for emoji in ["🚀", "🔥", "🇮🇩", "⭐", "✅", "❌"]:
        stripped = cap._strip_emoji(f"a {emoji} b")
        assert emoji not in stripped


# --------------------------------------------------------------------------- #
# BUG #3 — all-caps nationality list keeps proper-case
# --------------------------------------------------------------------------- #


def test_bug3_nationality_list_keeps_proper_case() -> None:
    """An all-caps nationality token is Title-cased, never lowercased."""
    out = cap._sentence_case("THAILAND AND VIETNAM ARE EXEMPT")
    assert "Vietnam" in out
    assert "vietnam" not in out  # the bug: would have produced "...and vietnam"
    assert "Thailand" in out
    # 'and' is a small word -> lowercase mid-sentence (restrained).
    assert " and " in out

    out2 = cap._sentence_case("FRANCE AND SPAIN QUALIFY")
    assert "Spain" in out2
    assert "spain" not in out2
    assert "France" in out2


def test_bug3_in_caption_body_via_heading(tmp_path: Path) -> None:
    """End-to-end: an all-caps heading nationality list keeps proper case."""
    slides = _minimal_slides("THAILAND AND VIETNAM ARE EXEMPT. FRANCE AND SPAIN QUALIFY.")
    brief = _minimal_brief()
    _write_carousel(tmp_path, "nat", brief, slides)
    caption = cap.build_caption("nat", base_dir=tmp_path)
    assert "Vietnam" in caption and "vietnam" not in caption
    assert "Spain" in caption and "spain" not in caption


def test_bug3_brand_tokens_preserved() -> None:
    """Brand/technical all-caps tokens (KITAS, BVK, US) are preserved verbatim."""
    out = cap._sentence_case("BVK IS Rp 0 FOR KITAS AND VoA HOLDERS")
    assert "BVK" in out
    assert "KITAS" in out
    assert "VoA" in out
    assert "Rp" in out


# --------------------------------------------------------------------------- #
# Happy-path snapshot — real indonesia-visafree-myth-reality carousel
# --------------------------------------------------------------------------- #


@pytest.mark.skipif(_REAL_BASE is None, reason="real carousel fixtures not present")
def test_happy_path_visafree_snapshot(tmp_path: Path) -> None:
    """The real visafree carousel yields a brand-compliant caption.

    Asserts the load-bearing invariants (not an exact string): disclaimer
    present, under the 2200 IG limit, >=8 hashtags, hook + CTA present, and the
    output is emoji-free.
    """
    assert _REAL_BASE is not None
    src = _REAL_BASE / _VISAFREE_SLUG
    if not (src / "brief.json").exists():
        pytest.skip("visafree fixture missing")
    # Copy the two public JSON files into an isolated tmp carousel root.
    dst = tmp_path / _VISAFREE_SLUG
    dst.mkdir(parents=True)
    shutil.copy2(src / "brief.json", dst / "brief.json")
    shutil.copy2(src / "slides.json", dst / "slides.json")

    caption = cap.build_caption(_VISAFREE_SLUG, base_dir=tmp_path)

    # Invariants.
    assert cap.DISCLAIMER in caption
    assert len(caption) < cap.IG_CAPTION_HARD_LIMIT  # under 2200
    assert caption.count("#") >= 8  # 8-15 hashtags
    assert caption.count("#") <= 15
    assert "DM us" in caption or "link in bio" in caption  # soft CTA
    assert caption == cap._strip_emoji(caption)  # emoji-free
    # The hook line is restrained (not the shouty all-caps heading verbatim).
    assert "NATIONALITIES. THE HEADLINE" not in caption  # de-shouted
    # Niche visa hashtags surfaced.
    assert "#bali" in caption and "#indonesia" in caption


def test_law2_only_reads_carousel_public_copy(tmp_path: Path) -> None:
    """LAW 2: build_caption reads ONLY brief.json + slides.json of the slug.

    A client-PII-looking sibling file in the carousel dir must never leak into
    the caption (it is never read).
    """
    slides = _minimal_slides("VISA REALITY CHECK")
    brief = _minimal_brief()
    _write_carousel(tmp_path, "law2", brief, slides)
    # Drop a decoy PII file alongside — it must be ignored.
    (tmp_path / "law2" / "client_passport.json").write_text(
        json.dumps({"name": "SECRET CLIENT", "passport": "X1234567"}), encoding="utf-8"
    )
    caption = cap.build_caption("law2", base_dir=tmp_path)
    assert "SECRET CLIENT" not in caption
    assert "X1234567" not in caption


def test_missing_carousel_raises(tmp_path: Path) -> None:
    """A missing carousel dir raises FileNotFoundError (no silent empty)."""
    with pytest.raises(FileNotFoundError):
        cap.build_caption("does-not-exist", base_dir=tmp_path)


def test_determinism(tmp_path: Path) -> None:
    """Two builds of the same carousel produce byte-identical captions."""
    slides = _minimal_slides("DETERMINISM CHECK")
    brief = _minimal_brief(domain="tax")
    _write_carousel(tmp_path, "det", brief, slides)
    a = cap.build_caption("det", base_dir=tmp_path)
    b = cap.build_caption("det", base_dir=tmp_path)
    assert a == b
