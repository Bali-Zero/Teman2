"""Freshness stamping for the article translator (scar 2026-07-28).

The organ used to skip on the EXISTENCE of the target file, so every
translation froze at birth: correcting an English article never reached its
translations, and the hourly run reported ``0 translated`` — green and empty —
forever. Measured when found: 1275 of 2664 translations were behind their
source.

These tests pin both directions, because the cure has an opposite failure mode
that is worse than the disease: re-translating a file we cannot vouch for would
overwrite hand-written corrections with machine output.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _load():
    name = "translate_articles_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, SCRIPTS_DIR / "translate-articles.py"
    )
    assert spec and spec.loader, "cannot load translate-articles.py"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


ta = _load()

FM = '---\ntitle: "T"\nslug: "s"\n---\n'
BODY = "# Heading\n\nSome English prose that will be translated.\n"


def _write(path: Path, fm: str, body: str) -> Path:
    path.write_text(fm + body, encoding="utf-8")
    return path


# ── the pure decision ──────────────────────────────────────────────────────

def test_absent_translation_is_written():
    assert ta.freshness_verdict(None, "d" * 64) == "absent"


def test_matching_digest_is_fresh():
    d = "a" * 64
    assert ta.freshness_verdict(ta.stamp_frontmatter(FM, d), d) == "fresh"


def test_changed_source_is_stale():
    """GUILT: the whole point — a moved source must be re-translated."""
    old, new = "a" * 64, "b" * 64
    assert ta.freshness_verdict(ta.stamp_frontmatter(FM, old), new) == "stale"


def test_translation_without_a_stamp_is_unstamped_not_stale():
    """INNOCENCE: the 1592 pre-existing files must not be re-translated on a guess.

    If this ever returns 'stale', the next hourly run overwrites every
    hand-corrected translation in the corpus with machine output.
    """
    assert ta.freshness_verdict(FM, "a" * 64) == "unstamped"


# ── the stamp itself ───────────────────────────────────────────────────────

def test_stamp_is_added_then_replaced_not_duplicated():
    d1, d2 = "1" * 64, "2" * 64
    once = ta.stamp_frontmatter(FM, d1)
    assert ta.read_stamp(once) == d1
    twice = ta.stamp_frontmatter(once, d2)
    assert ta.read_stamp(twice) == d2
    assert twice.count(ta.STAMP_FIELD) == 1


def test_unstamped_frontmatter_reads_as_none():
    assert ta.read_stamp(FM) is None


def test_stamping_adds_a_line_and_changes_nothing_else():
    """A metadata pass must be byte-additive.

    FRONTMATTER_RE closes on ``---\\s*\\n`` and ``\\s`` eats newlines, so the
    blank line before the body lands INSIDE the frontmatter block. The obvious
    rstrip-then-rsplit insertion deletes it: stamping the real corpus that way
    produced 1294 insertions AND 1009 deletions — a thousand article bodies
    reflowed by a pass that was only supposed to add a line.
    """
    original = '---\ntitle: "T"\n---\n\n'  # note the blank line after ---
    stamped = ta.stamp_frontmatter(original, "c" * 64)
    assert stamped.endswith("---\n\n"), "the blank line before the body must survive"
    assert stamped.replace(f'{ta.STAMP_FIELD}: "{"c" * 64}"\n', "") == original


def test_adding_a_locale_also_leaves_the_body_separator_alone():
    original = '---\ntitle: "T"\n---\n\n'
    patched = ta.patch_frontmatter_locale(original, "it")
    assert patched.endswith("---\n\n")
    assert patched.replace('locale: "it"\n', "") == original


def test_frontmatter_without_a_delimiter_is_returned_untouched():
    assert ta.stamp_frontmatter("", "d" * 64) == ""


def test_digest_covers_the_body_only():
    """Frontmatter drift must not read as a body change — that would pay for a
    re-translation to fix a copied title."""
    _, body_a = ta.split_frontmatter(FM + BODY)
    _, body_b = ta.split_frontmatter('---\ntitle: "DIFFERENT"\n---\n' + BODY)
    assert ta.source_digest(body_a) == ta.source_digest(body_b)


# ── behaviour of translate_article, without a model ────────────────────────

def _article(tmp_path: Path, body: str = BODY) -> dict:
    src = _write(tmp_path / "guide.mdx", FM, body)
    return {"path": src, "category": "immigration", "slug": "guide"}


def test_fresh_translation_is_left_alone_and_calls_no_model(tmp_path, monkeypatch):
    art = _article(tmp_path)
    _, body = ta.split_frontmatter(art["path"].read_text())
    digest = ta.source_digest(body)
    out = _write(
        tmp_path / "guide.it.mdx",
        ta.stamp_frontmatter(ta.patch_frontmatter_locale(FM, "it"), digest),
        "Testo tradotto.\n",
    )
    before = out.read_text()

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: pytest.fail("model called"))
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "fresh"
    assert out.read_text() == before


def test_a_fresh_file_with_drifted_frontmatter_is_still_left_alone(tmp_path, monkeypatch):
    """Frontmatter drift must NOT trigger a rewrite.

    An earlier draft re-derived the translation's frontmatter from the source
    here, on the theory that it is a verbatim copy. Measured against the real
    corpus first: 1398 of 2559 translations carry frontmatter that DIFFERS
    from their source — seoDescription, excerpt, faq, seoTitle, translated by
    hand. That 'refresh' would have reverted all of it to English.
    """
    art = _article(tmp_path)
    _, body = ta.split_frontmatter(art["path"].read_text())
    digest = ta.source_digest(body)
    translated_fm = ta.stamp_frontmatter(
        '---\ntitle: "Titolo tradotto"\nlocale: "it"\n---\n', digest
    )
    out = _write(tmp_path / "guide.it.mdx", translated_fm, "Testo tradotto.\n")
    before = out.read_text()

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: pytest.fail("model called"))
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "fresh"
    assert out.read_text() == before
    assert "Titolo tradotto" in out.read_text()


def test_retranslation_keeps_the_translated_frontmatter(tmp_path, monkeypatch):
    """The stale thing is the BODY. Re-deriving frontmatter from the English
    source on every re-translation would quietly revert hand-translated
    seoDescription/excerpt/faq across half the corpus."""
    art = _article(tmp_path)
    out = _write(
        tmp_path / "guide.it.mdx",
        ta.stamp_frontmatter(
            '---\ntitle: "Titolo tradotto"\nseoDescription: "Descrizione IT"\nlocale: "it"\n---\n',
            "0" * 64,
        ),
        "Vecchia traduzione.\n",
    )

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: "Nuova traduzione, sufficientemente lunga da superare il controllo di lunghezza.")
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "retranslated"
    text = out.read_text()
    assert "Titolo tradotto" in text and "Descrizione IT" in text, "translated metadata must survive"
    assert "Nuova traduzione" in text
    _, src_body = ta.split_frontmatter(art["path"].read_text())
    assert ta.read_stamp(ta.split_frontmatter(text)[0]) == ta.source_digest(src_body)


def test_unstamped_translation_is_never_overwritten(tmp_path, monkeypatch):
    """INNOCENCE, end to end: no stamp → no model call, no write."""
    art = _article(tmp_path)
    out = _write(tmp_path / "guide.it.mdx", '---\nlocale: "it"\n---\n', "Traduzione a mano.\n")
    before = out.read_text()

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: pytest.fail("model called"))
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "unstamped"
    assert out.read_text() == before


def test_stale_translation_is_retranslated_and_restamped(tmp_path, monkeypatch):
    art = _article(tmp_path)
    out = _write(
        tmp_path / "guide.it.mdx",
        ta.stamp_frontmatter(ta.patch_frontmatter_locale(FM, "it"), "0" * 64),
        "Vecchia traduzione.\n",
    )

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: "Nuova traduzione, abbastanza lunga da passare il controllo di lunghezza minima.")
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "retranslated"
    fm_after, body_after = ta.split_frontmatter(out.read_text())
    _, src_body = ta.split_frontmatter(art["path"].read_text())
    assert ta.read_stamp(fm_after) == ta.source_digest(src_body), "must restamp, or it stays stale forever"
    assert "Nuova traduzione" in body_after


def test_a_failed_translation_leaves_the_old_file_intact(tmp_path, monkeypatch):
    art = _article(tmp_path)
    out = _write(
        tmp_path / "guide.it.mdx",
        ta.stamp_frontmatter(ta.patch_frontmatter_locale(FM, "it"), "0" * 64),
        "Vecchia traduzione.\n",
    )
    before = out.read_text()

    monkeypatch.setattr(ta, "call_ollama", lambda *a, **k: "too short")
    assert ta.translate_article(art, "it", force=False, skip_existing=False) == "failed"
    assert out.read_text() == before


# ── baseline stamping ──────────────────────────────────────────────────────

def test_empty_list_is_a_failure_not_a_silent_success(tmp_path):
    """An empty set must never read as 'stamped everything' — it has done so
    to me five times in one session on other probes."""
    lst = tmp_path / "empty.txt"
    lst.write_text("# only a comment\n", encoding="utf-8")
    assert ta.stamp_baseline(lst) == 1


def test_missing_list_file_is_a_failure(tmp_path):
    assert ta.stamp_baseline(tmp_path / "nope.txt") == 1


def test_stamping_records_the_current_digest_and_is_idempotent(tmp_path):
    art = _article(tmp_path)
    out = _write(tmp_path / "guide.it.mdx", '---\nlocale: "it"\n---\n', "Traduzione a mano.\n")
    lst = tmp_path / "list.txt"
    lst.write_text(f"{out}\n", encoding="utf-8")

    assert ta.stamp_baseline(lst) == 0
    fm, body = ta.split_frontmatter(out.read_text())
    _, src_body = ta.split_frontmatter(art["path"].read_text())
    assert ta.read_stamp(fm) == ta.source_digest(src_body)
    assert "Traduzione a mano." in body, "stamping must not touch the translated text"

    assert ta.stamp_baseline(lst) == 0
    assert ta.split_frontmatter(out.read_text())[0].count(ta.STAMP_FIELD) == 1


def test_stamping_reports_unusable_entries_instead_of_swallowing_them(tmp_path):
    lst = tmp_path / "list.txt"
    lst.write_text(f"{tmp_path / 'ghost.it.mdx'}\n", encoding="utf-8")
    assert ta.stamp_baseline(lst) == 2
