"""Tests for wr2_editorial_pregate.py — the deterministic, zero-LLM
editorial pre-gate (WR2 editorial-intelligence Phase 2).

GUILT+INNOCENCE DISCIPLINE (cicatrix-superscar.md #3 — guard over/under-
match, the most recursive disease in this codebase, 8+ prior instances).
Every one of the 7 checks below gets AT LEAST one guilt case (a real
defect the check MUST fire on) and one innocence case (a legitimate
adjacent shape the check must NOT fire on) — several checks also get an
explicit SKIP case proving the check stays honestly silent when it cannot
verify structurally, rather than guessing.

The literal examples named in the build mandate are reproduced verbatim as
tests (not paraphrased): a real duplicate pair, "TIGA syarat" with 2
bullets, a caps-wall body, duplicate kickers, a closer with zero spine
tokens (guilt); two regulatory slides sharing only boilerplate, "3 syarat"
with exactly 3, a body with acronyms KITAS/NPWP/PMA not flagged, a
statement slide in caps (exempt by role), spine echoed via the regulation
code alone (innocence).

No DB, no CLI subprocess, no network, no LLM — wr2_editorial_pregate.py has
zero I/O side effects by design, so every test here runs instantly and
deterministically.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr2_carousel_ir as ir  # noqa: E402
import wr2_editorial_pregate as pg  # noqa: E402


def _typed_deck(slides: list[dict], register: str = "analitico") -> ir.SlideDeck:
    return ir.SlideDeck.model_validate({"register": register, "slides": slides})


# ─────────────────────────────────────────────────────────────────────────
# check_duplicate_slides
# ─────────────────────────────────────────────────────────────────────────


class TestDuplicateSlides:
    def test_guilt_real_duplicate_pair_fails(self):
        """Two prose slides whose bodies are near-copy-pasted (one word
        changed) — a real disco-rotto duplicate. MUST fail."""
        deck = _typed_deck([
            {"kind": "cover", "headline": "New Levy Announced"},
            {
                "kind": "prose",
                "headline": "The details",
                "body": (
                    "Immigration officials confirmed the new levy will apply to all "
                    "foreign visitors starting January covering the entire archipelago region"
                ),
            },
            {
                "kind": "prose",
                "headline": "The recap",
                "body": (
                    "Immigration officials confirmed the new levy will apply to all "
                    "foreign visitors starting January covering nearly the entire archipelago region"
                ),
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_duplicate_slides(canon)
        assert result.verdict == "FAIL"
        assert any("slide 2" in r and "slide 3" in r for r in result.reasons)

    def test_innocence_regulatory_slides_share_only_boilerplate(self):
        """Two slides about GENUINELY DIFFERENT regulations, sharing only
        Indonesian legal-citation scaffolding (Pasal/ayat/Peraturan/Menteri/
        Nomor/Tahun) — Jaccard AFTER boilerplate-stripping must be low.
        MUST pass (the whole point of stripping boilerplate first)."""
        deck = _typed_deck([
            {"kind": "cover", "headline": "Two Rules"},
            {
                "kind": "prose",
                "headline": "Capital reporting rule",
                "body": (
                    "Pasal 5 ayat 2 Peraturan Menteri Nomor 37 Tahun 2025 mengatur kewajiban "
                    "pelaporan modal disetor bagi perusahaan penanaman modal asing di sektor "
                    "pariwisata perhotelan"
                ),
            },
            {
                "kind": "prose",
                "headline": "Customs import rule",
                "body": (
                    "Pasal 12 ayat 3 Peraturan Menteri Nomor 8 Tahun 2024 mewajibkan importir "
                    "mengajukan dokumen kepabeanan sebelum barang tiba di pelabuhan utama negara"
                ),
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_duplicate_slides(canon)
        assert result.verdict == "PASS"

    def test_skip_short_slides_below_token_floor(self):
        deck = _typed_deck([
            {"kind": "prose", "headline": "A", "body": "Short note here"},
            {"kind": "prose", "headline": "B", "body": "Another brief line"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_duplicate_slides(canon)
        assert result.verdict == "SKIP"


# ─────────────────────────────────────────────────────────────────────────
# check_bullet_promise
# ─────────────────────────────────────────────────────────────────────────


class TestBulletPromise:
    def test_guilt_tiga_syarat_with_two_bullets_fails(self):
        deck = _typed_deck([
            {
                "kind": "fact_stack",
                "heading": "TIGA syarat utama",
                "facts": ["Syarat pertama", "Syarat kedua"],
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "FAIL"
        assert any("announces 3" in r and "delivers 2" in r for r in result.reasons)

    def test_innocence_3_syarat_with_exactly_three_passes(self):
        deck = _typed_deck([
            {
                "kind": "fact_stack",
                "heading": "3 syarat utama investasi",
                "facts": ["Syarat pertama", "Syarat kedua", "Syarat ketiga"],
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "PASS"

    def test_skip_no_slide_carries_a_verifiable_list(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Three big changes ahead"},
            {"kind": "prose", "headline": "Overview", "body": "Explains the shifts in plain prose."},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "SKIP"

    def test_flat_guilt_inline_numbered_body_mismatch(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": ""},
            {
                "slide_number": 2,
                "slide_type": "body",
                "headline": "Three quick checks",
                "body": "1. Check A. 2. Check B.",
            },
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "FAIL"

    def test_flat_innocence_inline_numbered_body_matches(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": ""},
            {
                "slide_number": 2,
                "slide_type": "body",
                "headline": "Three quick checks",
                "body": "1. Check A. 2. Check B. 3. Check C.",
            },
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "PASS"

    def test_flat_innocence_prose_body_never_penalized(self):
        """A prose body that happens to mention '3' in the heading but has
        NO bullet/numbered structure must SKIP, never FAIL — prose is not
        (structurally) a broken list, it was never claiming to be a list."""
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": ""},
            {
                "slide_number": 2,
                "slide_type": "body",
                "headline": "3 things changed this year",
                "body": "The rules shifted gradually over several months in ways nobody fully expected.",
            },
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_bullet_promise(canon)
        assert result.verdict == "SKIP"


# ─────────────────────────────────────────────────────────────────────────
# check_caps_policy
# ─────────────────────────────────────────────────────────────────────────


class TestCapsPolicy:
    def test_guilt_caps_wall_body_fails(self):
        deck = _typed_deck([
            {
                "kind": "prose",
                "headline": "Normal headline",
                "body": "THIS ENTIRE BODY IS SHOUTING LOUDLY AT EVERY SINGLE READER TODAY",
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_caps_policy(canon)
        assert result.verdict == "FAIL"

    def test_innocence_acronyms_in_prose_not_flagged(self):
        deck = _typed_deck([
            {
                "kind": "prose",
                "headline": "Requirements",
                "body": (
                    "Foreign investors seeking KITAS and NPWP registration must also secure "
                    "a PMA license before applying for permits"
                ),
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_caps_policy(canon)
        assert result.verdict == "PASS"

    def test_innocence_statement_slide_in_caps_exempt_by_role(self):
        """A statement-bomb closer in full caps sits in HEADING role — it is
        never inspected by this check at all. Mixed into a deck with a
        normal-case prose body so the check has something real to
        evaluate, and still passes because the shouty text is role-exempt,
        not because of a string-content escape hatch."""
        deck = _typed_deck([
            {"kind": "prose", "headline": "Context", "body": "The rule applies starting next quarter for everyone."},
            {"kind": "statement", "statement": "THIS IS A BOLD STATEMENT ABOUT THE MARKET TODAY"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_caps_policy(canon)
        assert result.verdict == "PASS"
        assert all("BOLD STATEMENT" not in r for r in result.reasons)

    def test_skip_deck_with_no_body_role_text(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover only"},
            {"kind": "statement", "statement": "A short punchy close"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_caps_policy(canon)
        assert result.verdict == "SKIP"


# ─────────────────────────────────────────────────────────────────────────
# check_cta_presence
# ─────────────────────────────────────────────────────────────────────────


class TestCtaPresence:
    def test_typed_guilt_no_cta_no_statement_closer_fails(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "prose", "headline": "Body", "body": "Some body text here for the deck."},
            {
                "kind": "triad",
                "heading": "3 forces",
                "items": [
                    {"title": "One", "desc": "First"},
                    {"title": "Two", "desc": "Second"},
                ],
            },
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_cta_presence(canon)
        assert result.verdict == "FAIL"

    def test_typed_innocence_last_slide_statement_passes(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "prose", "headline": "Body", "body": "Some body text here for the deck."},
            {"kind": "statement", "statement": "The takeaway in one line"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_cta_presence(canon)
        assert result.verdict == "PASS"

    def test_typed_innocence_cta_kind_anywhere_passes(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "cta", "invite": "Reach out to Bali Zero today"},
            {"kind": "prose", "headline": "Body", "body": "Closing thoughts in prose form here."},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_cta_presence(canon)
        assert result.verdict == "PASS"

    def test_flat_guilt_empty_closing_slide_fails(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": "x"},
            {"slide_number": 2, "slide_type": "cta", "headline": "", "subhead": "", "body": ""},
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_cta_presence(canon)
        assert result.verdict == "FAIL"

    def test_flat_innocence_closing_slide_with_content_passes(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": "x"},
            {"slide_number": 2, "slide_type": "cta", "headline": "Talk to us", "body": "Reach out any time."},
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_cta_presence(canon)
        assert result.verdict == "PASS"


# ─────────────────────────────────────────────────────────────────────────
# check_kicker_unique
# ─────────────────────────────────────────────────────────────────────────


class TestKickerUnique:
    def test_guilt_duplicate_kickers_fail(self):
        deck = _typed_deck([
            {"kind": "prose", "headline": "THE SIGNAL: a first take", "body": "Body one for the deck here."},
            {"kind": "prose", "headline": "THE SIGNAL: a different take", "body": "Body two for the deck here."},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_kicker_unique(canon)
        assert result.verdict == "FAIL"

    def test_innocence_similar_but_distinct_kickers_never_substring_collide(self):
        """Reproduces the production regression this check must NOT
        reintroduce: 'TAKEAWAY FOR SELLERS' contains 'TAKE' but must not
        match; 'THE SIGNAL TODAY' must NOT match 'THE SIGNAL' — whole-
        string comparison only."""
        deck = _typed_deck([
            {"kind": "prose", "headline": "TAKEAWAY FOR SELLERS: point one", "body": "Body one here for the deck."},
            {"kind": "prose", "headline": "THE SIGNAL TODAY: point two", "body": "Body two here for the deck."},
            {"kind": "prose", "headline": "THE SIGNAL: point three", "body": "Body three here for the deck."},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_kicker_unique(canon)
        assert result.verdict == "PASS"

    def test_skip_fewer_than_two_extractable_kickers(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "A genuinely long headline that runs past five words easily"},
            {"kind": "prose", "headline": "Another quite long headline past the five word ceiling too", "body": "x body text here"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_kicker_unique(canon)
        assert result.verdict == "SKIP"


# ─────────────────────────────────────────────────────────────────────────
# check_kind_coverage
# ─────────────────────────────────────────────────────────────────────────


class TestKindCoverage:
    def test_typed_trivially_true_after_validation(self):
        # Non-prose kinds so this test isolates "every slide has a valid
        # kind" from the SEPARATE degeneracy-tripwire behavior (covered by
        # test_typed_degeneracy_warn_when_over_70_percent_prose below).
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "statement", "statement": "A clean closing line"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_kind_coverage(canon)
        assert result.verdict == "PASS"

    def test_typed_degeneracy_warn_when_over_70_percent_prose(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "prose", "headline": "A", "body": "Body text one for the deck to read here."},
            {"kind": "prose", "headline": "B", "body": "Body text two for the deck to read here."},
            {"kind": "prose", "headline": "C", "body": "Body text three for the deck to read here."},
            {"kind": "prose", "headline": "D", "body": "Body text four for the deck to read here."},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_kind_coverage(canon)
        assert result.verdict == "WARN"

    def test_flat_guilt_missing_slide_type_fails(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": "x"},
            {"slide_number": 2, "slide_type": "", "headline": "No type", "body": "y"},
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_kind_coverage(canon)
        assert result.verdict == "FAIL"

    def test_flat_innocence_below_degeneracy_threshold(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": "x"},
            {"slide_number": 2, "slide_type": "fact", "headline": "A", "body": "y"},
            {"slide_number": 3, "slide_type": "context", "headline": "B", "body": "z"},
            {"slide_number": 4, "slide_type": "stakes", "headline": "C", "body": "w"},
            {"slide_number": 5, "slide_type": "cta", "headline": "D", "body": "v"},
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_kind_coverage(canon)
        assert result.verdict == "PASS"

    def test_flat_degeneracy_warn_matches_production_shape(self):
        """Mirrors the ACTUAL production histogram this session measured
        (187/557 slides literally slide_type='body') — a deck dominated by
        undifferentiated 'body' slides WARNs, it does not FAIL (this is a
        tripwire on today's real corpus, not a hard block)."""
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Cover", "body": "x"},
            {"slide_number": 2, "slide_type": "body", "headline": "A", "body": "y"},
            {"slide_number": 3, "slide_type": "body", "headline": "B", "body": "z"},
            {"slide_number": 4, "slide_type": "body", "headline": "C", "body": "w"},
            {"slide_number": 5, "slide_type": "cta", "headline": "D", "body": "v"},
        ]
        canon = pg._canon_from_flat(slides)
        result = pg.check_kind_coverage(canon)
        assert result.verdict == "WARN"


# ─────────────────────────────────────────────────────────────────────────
# check_spine_echo
# ─────────────────────────────────────────────────────────────────────────


class TestSpineEcho:
    def test_guilt_closer_shares_zero_spine_tokens_fails(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "New Tourism Levy"},
            {
                "kind": "statement",
                "statement": "Completely unrelated closing remarks about weather patterns elsewhere",
            },
        ])
        canon = pg._canon_from_typed(deck)
        spine = "Indonesia introduces a new tourism levy affecting foreign visitors"
        result = pg.check_spine_echo(canon, spine)
        assert result.verdict == "FAIL"

    def test_innocence_spine_echoed_via_regulation_code_alone(self):
        """No shared prose words at all — only the bare regulation-code
        number pair ('5/2025') repeats between spine and closer. MUST
        pass: the fact-key match is entity-based, not a prose-overlap
        heuristic."""
        deck = _typed_deck([
            {"kind": "cover", "headline": "Golden Visa Overhaul"},
            {
                "kind": "cta",
                "invite": "Officials clarified how 5/2025 changes bond requirements for long-term residents",
            },
        ])
        canon = pg._canon_from_typed(deck)
        spine = "Permenimipas No. 5/2025 quietly redraws the guarantor requirement for Golden Visa holders"
        result = pg.check_spine_echo(canon, spine)
        assert result.verdict == "PASS"

    def test_skip_when_no_spine_provided(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Cover"},
            {"kind": "statement", "statement": "A closing line"},
        ])
        canon = pg._canon_from_typed(deck)
        result = pg.check_spine_echo(canon, None)
        assert result.verdict == "SKIP"
        assert "never guessed" in result.reasons[0]


# ─────────────────────────────────────────────────────────────────────────
# Public entry points — pregate_typed / pregate_flat
# ─────────────────────────────────────────────────────────────────────────


class TestPregateEntryPoints:
    def test_pregate_typed_clean_deck_passes(self):
        deck = _typed_deck([
            {"kind": "cover", "headline": "Golden Visa Overhaul"},
            {
                "kind": "fact_stack",
                "heading": "3 syarat utama",
                "facts": ["Syarat pertama", "Syarat kedua", "Syarat ketiga"],
            },
            {"kind": "statement", "statement": "The takeaway in one clean line"},
        ])
        report = pg.pregate_typed(deck, spine=None)
        assert report.deck_kind == "typed"
        assert report.slide_count == 3
        assert report.verdict in ("PASS", "WARN")  # SKIPs on spine_echo are expected (no spine)
        assert len(report.checks) == 7
        d = report.to_dict()
        assert d["checks"][0]["check"] == "check_duplicate_slides"
        assert isinstance(report.to_json(), str)

    def test_pregate_flat_clean_deck_passes(self):
        slides = [
            {"slide_number": 1, "slide_type": "cover", "is_cover": True, "headline": "Golden Visa Overhaul", "body": ""},
            {"slide_number": 2, "slide_type": "fact", "headline": "The numbers", "body": "Two million arrivals this year alone."},
            {"slide_number": 3, "slide_type": "cta", "headline": "Talk to us", "body": "Reach out any time for guidance."},
        ]
        report = pg.pregate_flat(slides, spine=None)
        assert report.deck_kind == "flat"
        assert report.slide_count == 3
        assert len(report.checks) == 7

    def test_aggregate_verdict_fail_beats_warn_beats_pass(self):
        results = [
            pg.CheckResult("a", "PASS"),
            pg.CheckResult("b", "WARN"),
            pg.CheckResult("c", "FAIL"),
        ]
        assert pg._aggregate_verdict(results) == "FAIL"
        assert pg._aggregate_verdict(results[:2]) == "WARN"
        assert pg._aggregate_verdict(results[:1]) == "PASS"

    def test_check_result_rejects_invalid_verdict(self):
        import pytest
        with pytest.raises(ValueError):
            pg.CheckResult("x", "MAYBE")
